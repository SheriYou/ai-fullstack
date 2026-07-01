#!/usr/bin/env python3
"""从已有 run 目录重生成报告（含缺陷管理章节）与 Word。"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_bundle import run_dir
from run_full_test import write_reports


def _load_formal_from_csv(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for r in csv.DictReader(path.open(encoding="utf-8-sig")):
        if r.get("execution_status") != "EXECUTED":
            continue
        rows.append({
            "case_id": r["case_id"],
            "module": r.get("module", ""),
            "title": r.get("title", ""),
            "layer": r.get("layer", ""),
            "priority": r.get("priority", ""),
            "execution_status": r.get("execution_status", ""),
            "automation_result": r.get("automation_result", ""),
            "business_result": r.get("business_result", ""),
            "title": r.get("title", ""),
            "notes": r.get("notes", ""),
            "session_id": "",
        })
        if "session_id=" in (r.get("notes") or ""):
            part = r["notes"].split("session_id=", 1)[1].split(";", 1)[0].strip()
            rows[-1]["session_id"] = part
    return rows


def _load_corpus_from_csv(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for r in csv.DictReader(path.open(encoding="utf-8-sig")):
        rows.append({
            "id": r.get("case_id", r.get("id", "")),
            "corpus": r.get("corpus", ""),
            "business_result": r.get("business_result", ""),
            "automation_result": r.get("automation_result", ""),
            "fail_class": r.get("fail_class", ""),
            "status": "SKIP" if r.get("execution_status") == "SKIP" else "FAIL",
            "notes": r.get("notes", ""),
            "task_type": r.get("task_type", ""),
        })
        if r.get("business_result") == "PASS":
            rows[-1]["status"] = "PASS"
    return rows


def main():
    run_id = sys.argv[1] if len(sys.argv) > 1 else ""
    if not run_id:
        ptr = ROOT / "reports" / "latest-run.json"
        if ptr.exists():
            run_id = json.loads(ptr.read_text(encoding="utf-8")).get("run_id", "")
    if not run_id:
        print("usage: python refresh_run_report.py <run_id>", file=sys.stderr)
        raise SystemExit(1)

    bundle = run_dir(run_id)
    summary_path = bundle / "summary.json"
    if not summary_path.exists():
        print(f"run not found: {bundle}", file=sys.stderr)
        raise SystemExit(1)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    executed_at = summary.get("executed_at", "")
    formal = _load_formal_from_csv(bundle / "test-results.csv")
    corpus = _load_corpus_from_csv(bundle / "test-results-corpus.csv")

    meta = {
        "base": "https://test-paas.transsion.com/whatsapp-bot-service/api",
        "channel": "ch_wa_01",
        "business_line_id": 1,
        "wait": 4.0,
    }
    md, new_summary = write_reports(run_id, executed_at, formal, corpus, meta)
    print(f"refreshed: {md}")
    print(f"bugs: {new_summary.get('bugs', {}).get('analysis', {})}")


if __name__ == "__main__":
    main()
