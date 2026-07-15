#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run Hot70 smoke + L2 sample against test-paas bot API."""
from __future__ import annotations

import csv
import http.cookiejar
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
DATA = ROOT / "data"

DEFAULT_BASE = "https://uat-paas.transsion.com/whatsapp-bot-service/api"
DEFAULT_USER = "admin"
DEFAULT_PASS = "admin123456"
WEBHOOK_MAX_ATTEMPTS = 3


class Client:
    def __init__(self, base: str, user: str, password: str):
        self.base = base.rstrip("/")
        self.cj = http.cookiejar.CookieJar()
        self.opener = request.build_opener(request.HTTPCookieProcessor(self.cj))

    def _call(self, method: str, path: str, body: dict | None = None, timeout: int = 60):
        url = self.base + path
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = request.Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        for attempt in range(4):
            try:
                with self.opener.open(req, timeout=timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    return resp.status, json.loads(raw) if raw else {}
            except error.HTTPError as e:
                raw = e.read().decode("utf-8", errors="replace")
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    payload = {"raw": raw}
                return e.code, payload
            except (error.URLError, ConnectionResetError, TimeoutError, OSError):
                if attempt >= 3:
                    raise
                time.sleep(0.6 * (attempt + 1))

    def login(self, user: str, password: str) -> bool:
        status, data = self._call("POST", "/auth/login", {"username": user, "password": password})
        return status == 200 and data.get("success") is not False

    def webhook(
        self, channel: str, whatsapp_id: str, text: str, sender_name: str = "WhatsApp User"
    ) -> tuple[int, dict]:
        payload = {
            "whatsapp_id": whatsapp_id,
            "sender_name": sender_name,
            "content": text,
            "message_id": f"test-{uuid.uuid4().hex[:12]}",
            "direction": "inbound",
        }
        url = f"{self.base}/webhook/{channel}"
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        for attempt in range(WEBHOOK_MAX_ATTEMPTS):
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
                if e.code >= 500 and attempt + 1 < WEBHOOK_MAX_ATTEMPTS:
                    time.sleep(0.6 * (attempt + 1))
                    continue
                return e.code, body
            except (error.URLError, ConnectionResetError, TimeoutError, OSError) as e:
                if attempt + 1 >= WEBHOOK_MAX_ATTEMPTS:
                    return 599, {"error": str(e), "attempts": WEBHOOK_MAX_ATTEMPTS}
                time.sleep(0.6 * (attempt + 1))
        return 599, {"error": "webhook retry limit exceeded", "attempts": WEBHOOK_MAX_ATTEMPTS}

    def session(self, business_line_id: int, whatsapp_id: str) -> dict:
        _, data = self._call("GET", f"/business-lines/{business_line_id}/agent/session/{whatsapp_id}")
        inner = data.get("data") or {}
        if isinstance(inner, dict) and "data" in inner:
            return inner.get("data") or {}
        return inner if isinstance(inner, dict) else {}

    def messages(self, business_line_id: int, whatsapp_id: str) -> list:
        _, data = self._call("GET", f"/business-lines/{business_line_id}/messages/{whatsapp_id}")
        inner = data.get("data") or {}
        if isinstance(inner, dict):
            return inner.get("data") or []
        return inner if isinstance(inner, list) else []

    def conversations(self, business_line_id: int) -> list:
        _, data = self._call("GET", f"/business-lines/{business_line_id}/conversations")
        inner = data.get("data") or {}
        if isinstance(inner, dict):
            return inner.get("data") or []
        return inner if isinstance(inner, list) else []


def find_conversation(conversations: list, whatsapp_id: str) -> dict | None:
    for c in conversations:
        if c.get("whatsapp_id") == whatsapp_id or c.get("whatsappId") == whatsapp_id:
            return c
    return None


def outbound_texts(messages: list) -> list[str]:
    texts = []
    for m in messages:
        direction = (m.get("direction") or "").lower()
        if direction == "outbound":
            content = m.get("content") or ""
            if content.strip():
                texts.append(content.strip())
    return texts


def session_id_from(sess: dict) -> str:
    if not sess:
        return ""
    inner = sess.get("session") or sess
    return (inner.get("session_id") or inner.get("sessionId") or "").strip()


def run_smoke(client: Client, channel: str, bl: int, wa: str, wait: float) -> list[dict]:
    """Formal 冒烟用例（TC-SMOKE-*，verify_profile 驱动）。"""
    from test_case_runner import run_smoke_formal_cases

    formal = run_smoke_formal_cases(client, channel, bl, max(wait, 4.0))
    out = []
    for r in formal:
        out.append({
            "id": r["case_id"],
            "input": "",
            "whatsapp_id": r.get("whatsapp_id", ""),
            "session_id": r.get("session_id", ""),
            "status": "PASS" if r.get("business_result") == "PASS" else "FAIL",
            "outbound_preview": r.get("outbound_preview", ""),
            "note": r.get("notes", ""),
            "notes": r.get("notes", ""),
        })
    return out


def write_report(smoke: list, corpus: list, meta: dict):
    """轻量报告写入 runs/{run_id}/suite-report.md（不在 reports 根目录落盘）。"""
    from run_bundle import run_dir

    REPORTS.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_d = run_dir(ts)
    run_d.mkdir(parents=True, exist_ok=True)
    out = run_d / "suite-report.md"
    sp = sum(1 for r in smoke if r["status"] == "PASS")
    sf = sum(1 for r in smoke if r["status"] == "FAIL")
    cp = sum(1 for r in corpus if r["status"] == "PASS")
    cf = sum(1 for r in corpus if r["status"] == "FAIL")
    cs = sum(1 for r in corpus if r["status"] == "SKIP")
    lines = [
        f"# Hot70 测试执行报告",
        "",
        f"> {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## 环境",
        "",
        f"- API: `{meta['base']}`",
        f"- channel: `{meta['channel']}`",
        f"- business_line_id: `{meta['business_line_id']}`",
        f"- whatsapp_id (smoke): `{meta['whatsapp_id']}`",
        "",
        "## 冒烟 G2",
        "",
        f"Pass={sp} Fail={sf}",
        "",
        "| ID | 结果 | 输入 | 说明 |",
        "|----|------|------|------|",
    ]
    for r in smoke:
        note = r.get("outbound_preview") or r.get("note") or r.get("conversation_status") or ""
        lines.append(f"| {r['id']} | {r['status']} | {r.get('input','')[:30]} | {str(note)[:50]} |")
    lines += [
        "",
        "## L2 语料",
        "",
        "旧 corpus 抽样回归已下线；L2 统一改用 `python scripts/run_kb_metrics_test.py`。",
        "",
        "| ID | 结果 | 输入 | task_type |",
        "|----|------|------|-----------|--------------|",
    ]
    for r in corpus:
        lines.append(f"| {r.get('id','')} | {r['status']} | {str(r.get('input',''))[:40]} | {r.get('task_type','')} | {r.get('customer_tag','')} |")
    lines += [
        "",
        "## 说明",
        "",
        "- webhook 使用 LocalGateway 格式：`whatsapp_id` + `content` + `message_id`",
        "- `/api/webhook/channels/...` 在测试环境返回 404，已改用 `/api/webhook/{channelKey}`",
        "- 智齿 external-handoff / 真机 WA 未在本轮执行",
        "- 知识库指标专项：`scripts/run_kb_metrics_test.py`",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"report={out}")
    return out


def main():
    base = DEFAULT_BASE
    user = DEFAULT_USER
    password = DEFAULT_PASS
    channel = "ch_wa_01"
    bl = 1
    wait = 4.0
    client = Client(base, user, password)
    if not client.login(user, password):
        print("LOGIN FAILED", file=sys.stderr)
        sys.exit(1)
    print("LOGIN OK")

    wa = f"smoke-{uuid.uuid4().hex[:8]}@s.whatsapp.net"
    print(f"smoke wa={wa}")

    smoke = run_smoke(client, channel, bl, wa, wait)
    corpus: list[dict] = []
    report = write_report(smoke, corpus, {
        "base": base,
        "channel": channel,
        "business_line_id": bl,
        "whatsapp_id": wa,
    })

    print("\n=== SMOKE ===")
    for r in smoke:
        print(r["id"], r["status"], r.get("outbound_preview", r.get("note", ""))[:80])

    print("\n=== CORPUS SAMPLE ===")
    print(f"PASS={sum(1 for r in corpus if r['status']=='PASS')} FAIL={sum(1 for r in corpus if r['status']=='FAIL')} SKIP={sum(1 for r in corpus if r['status']=='SKIP')}")
    print(f"report written: {report}")


if __name__ == "__main__":
    main()
