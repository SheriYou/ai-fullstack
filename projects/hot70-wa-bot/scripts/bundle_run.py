#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将已有测试产出物迁入 reports/runs/{run_id}/ 并生成 Word。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_bundle import bundle_existing_run  # noqa: E402


def main():
    if len(sys.argv) < 2:
        # 默认最新一轮
        reports = ROOT / "reports"
        mds = sorted(reports.glob("test-run-*.md"), reverse=True)
        if not mds:
            print("usage: python bundle_run.py <run_id>", file=sys.stderr)
            raise SystemExit(1)
        run_id = mds[0].stem.replace("test-run-", "")
    else:
        run_id = sys.argv[1]

    d = bundle_existing_run(run_id)
    if not d:
        print(f"not found: test-run-{run_id}.md", file=sys.stderr)
        raise SystemExit(1)
    print(f"bundled -> {d}")
    print(f"  test-report.docx")


if __name__ == "__main__":
    main()
