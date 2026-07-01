#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将已有测试产出物迁入 reports/runs/{run_id}/ 并生成 Word。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT.parents[1] / "lib"))

from run_paths import resolve_latest_run_id  # noqa: E402
from run_bundle import bundle_existing_run  # noqa: E402


def main():
    if len(sys.argv) >= 2:
        run_id = sys.argv[1]
    else:
        run_id = resolve_latest_run_id(REPORTS)
        if not run_id:
            print("usage: python bundle_run.py <run_id>", file=sys.stderr)
            raise SystemExit(1)

    d = bundle_existing_run(run_id)
    if not d:
        print(f"not found: runs/{run_id}/ or legacy test-run-{run_id}.md", file=sys.stderr)
        raise SystemExit(1)
    print(f"bundled -> {d}")
    print(f"  test-report.docx")


if __name__ == "__main__":
    main()
