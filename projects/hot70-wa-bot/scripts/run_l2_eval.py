#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L2 batch eval: POST webhook -> poll agent/session -> compare corpus expectations."""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1] / "lib"))

try:
    from load_config import load_project_config
except ImportError:
    def load_project_config(root):
        cfg = {}
        env = root / "config.env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
        return cfg

DATA = ROOT / "data"
REPORTS = ROOT / "reports"

CORPUS_FILES = {
    "intent": DATA / "corpus-intent.csv",
    "kb": DATA / "corpus-kb.csv",
    "handoff": DATA / "corpus-handoff.csv",
    "adversarial": DATA / "corpus-adversarial.csv",
}


def http_json(method: str, url: str, body: dict | None = None, headers: dict | None = None):
    data = None
    hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return e.code, payload


def load_corpus(path: Path, limit: int | None):
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    if limit:
        rows = rows[:limit]
    return rows


def simulate_inbound(cfg: dict, whatsapp_id: str, text: str) -> tuple[int, dict]:
    base = cfg.get("BOT_TEST_API_URL", "").rstrip("/")
    channel = cfg.get("BOT_CHANNEL_KEY", "ch_wa_01")
    # LocalGateway 格式（test-paas 可用 /api/webhook/{channelKey}）
    payload = {
        "whatsapp_id": whatsapp_id,
        "content": text,
        "message_id": f"test-{uuid.uuid4().hex[:12]}",
        "direction": "inbound",
    }
    url = f"{base}/webhook/{channel}"
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw": raw}
        return e.code, body


def fetch_session(cfg: dict, whatsapp_id: str) -> dict:
    base = cfg.get("BOT_TEST_API_URL", "").rstrip("/")
    bl = cfg.get("BOT_BUSINESS_LINE_ID", "1")
    url = f"{base}/business-lines/{bl}/agent/session/{whatsapp_id}"
    status, data = http_json("GET", url)
    if status != 200:
        return {"error": data, "status": status}
    return data.get("data", data)


def eval_row(cfg: dict, row: dict, whatsapp_id: str, wait_s: float) -> dict:
    text = row.get("input", "").strip()
    if not text or text.startswith("("):
        return {"id": row.get("id"), "status": "SKIP", "reason": "non-simulatable input"}

    status, resp = simulate_inbound(cfg, whatsapp_id, text)
    time.sleep(wait_s)
    session = fetch_session(cfg, whatsapp_id)
    task_type = session.get("task_type") or session.get("active_agent")
    return {
        "id": row.get("id"),
        "input": text[:80],
        "http_status": status,
        "webhook": resp,
        "task_type": task_type,
        "session": session,
        "expected_intent": row.get("expected_intent") or row.get("category"),
        "should_handoff": row.get("should_handoff"),
        "status": "PASS" if status == 200 else "FAIL",
    }


def write_report(name: str, results: list[dict]):
    REPORTS.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = REPORTS / f"offline-eval-{name}-{ts}.md"
    passed = sum(1 for r in results if r.get("status") == "PASS")
    failed = sum(1 for r in results if r.get("status") == "FAIL")
    skipped = sum(1 for r in results if r.get("status") == "SKIP")
    lines = [
        f"# L2 Offline Eval — {name}",
        "",
        f"> {ts} | Pass={passed} Fail={failed} Skip={skipped}",
        "",
        "断言规则见 `spec/intent-task-mapping.md`。本脚本仅验证 webhook 可达与 session 可观测。",
        "",
        "| id | status | input | task_type | should_handoff |",
        "|----|--------|-------|-----------|----------------|",
    ]
    for r in results:
        lines.append(
            f"| {r.get('id','')} | {r.get('status','')} | {str(r.get('input',''))[:40]} | "
            f"{r.get('task_type','')} | {r.get('should_handoff','')} |"
        )
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"report={out}")
    return out


def main():
    parser = argparse.ArgumentParser(description="Hot70 L2 batch eval via webhook")
    parser.add_argument("--corpus", choices=list(CORPUS_FILES.keys()), default="intent")
    parser.add_argument("--limit", type=int, default=10, help="max rows (default 10 for smoke)")
    parser.add_argument("--wait", type=float, default=3.0, help="seconds after webhook")
    parser.add_argument("--whatsapp-id", default="8613800000001@s.whatsapp.net")
    args = parser.parse_args()

    cfg = load_project_config(ROOT)
    if not cfg.get("BOT_TEST_API_URL"):
        print("ERROR: set BOT_TEST_API_URL in config.env", file=sys.stderr)
        sys.exit(1)

    path = CORPUS_FILES[args.corpus]
    rows = load_corpus(path, args.limit)
    results = [eval_row(cfg, row, args.whatsapp_id, args.wait) for row in rows]
    write_report(args.corpus, results)


if __name__ == "__main__":
    main()
