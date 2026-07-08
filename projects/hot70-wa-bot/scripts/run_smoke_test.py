#!/usr/bin/env python3
"""G2 冒烟测试：仅 TC-SMOKE-*，verify_profile 驱动，产出 runs 归档。"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_full_test import DEFAULT_BASE, DEFAULT_PASS, DEFAULT_USER, Client, write_reports
from test_case_runner import run_smoke_formal_cases


def main():
    wait = 12.0
    channel = "ch_wa_01"
    bl = 1
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    executed_at = datetime.now().isoformat(timespec="seconds")

    client = Client(DEFAULT_BASE, DEFAULT_USER, DEFAULT_PASS)
    if not client.login(DEFAULT_USER, DEFAULT_PASS):
        print("LOGIN FAILED", file=sys.stderr)
        sys.exit(1)
    print("LOGIN OK", flush=True)
    print(f"API={DEFAULT_BASE}", flush=True)

    print("running smoke cases (TC-SMOKE-*)...", flush=True)
    formal = run_smoke_formal_cases(client, channel, bl, wait)
    sp = sum(1 for r in formal if r.get("business_result") == "PASS")
    sf = sum(1 for r in formal if r.get("business_result") == "FAIL")
    spartial = sum(1 for r in formal if r.get("business_result") == "PARTIAL")
    print(f"smoke done pass={sp} fail={sf} partial={spartial}", flush=True)

    md, summary = write_reports(run_id, executed_at, formal, [], {
        "base": DEFAULT_BASE,
        "channel": channel,
        "business_line_id": bl,
        "wait": wait,
        "suite": "smoke",
    })
    print(f"bundle={summary.get('bundle_dir')}")
    print(f"report_md={md}")
    print(f"report_docx={summary.get('report_docx')}")
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == "__main__":
    main()
