#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""框架级测试产出物每日清理（默认保留 7 天，每天至少执行 1 次）。"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT / "lib"))

from artifact_cleanup import (  # noqa: E402
    already_ran_today,
    cleanup_all_projects,
    save_cleanup_state,
)

STATE_DIR = FRAMEWORK_ROOT / ".cleanup"
STATE_FILE = STATE_DIR / "last-run.json"
LOG_DIR = STATE_DIR / "logs"


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete expired test artifacts (once per day by default)")
    parser.add_argument(
        "--retention-days",
        type=int,
        default=int(os.environ.get("AHT_CLEANUP_RETENTION_DAYS", "7")),
        help="Keep runs newer than N days (default: 7, env AHT_CLEANUP_RETENTION_DAYS)",
    )
    parser.add_argument(
        "--min-runs",
        type=int,
        default=int(os.environ.get("AHT_CLEANUP_MIN_RUNS", "1")),
        help="Always keep at least N most recent runs (default: 1)",
    )
    parser.add_argument("--force", action="store_true", help="Run even if already ran today")
    parser.add_argument("--dry-run", action="store_true", help="List what would be deleted")
    parser.add_argument("--project", type=str, default="", help="Only clean projects/<name>/reports")
    args = parser.parse_args()

    if not args.force and not args.dry_run and already_ran_today(STATE_FILE):
        print(f"skip: cleanup already ran today ({date.today().isoformat()}); use --force to rerun")
        return 0

    if args.project:
        reports = FRAMEWORK_ROOT / "projects" / args.project / "reports"
        if not reports.is_dir():
            print(f"error: reports not found: {reports}", file=sys.stderr)
            return 1
        from artifact_cleanup import cleanup_project_reports  # noqa: E402

        results = [
            cleanup_project_reports(
                reports,
                retention_days=args.retention_days,
                min_runs=args.min_runs,
                dry_run=args.dry_run,
            )
        ]
    else:
        results = cleanup_all_projects(
            FRAMEWORK_ROOT,
            retention_days=args.retention_days,
            min_runs=args.min_runs,
            dry_run=args.dry_run,
        )

    total_deleted = sum(len(r.deleted_paths) for r in results)
    total_errors = sum(len(r.errors) for r in results)

    for r in results:
        if r.skipped:
            print(f"[{r.project}] skipped: {r.skip_reason}")
            continue
        print(f"[{r.project}] kept_runs={r.kept_runs} deleted={len(r.deleted_paths)}")
        for p in r.deleted_paths:
            print(f"  - {p}")
        for err in r.errors:
            print(f"  ! {err}", file=sys.stderr)

    payload = {
        "date": date.today().isoformat(),
        "executed_at": datetime.now().isoformat(timespec="seconds"),
        "retention_days": args.retention_days,
        "min_runs": args.min_runs,
        "dry_run": args.dry_run,
        "projects": [
            {
                "project": r.project,
                "kept_runs": r.kept_runs,
                "deleted_count": len(r.deleted_paths),
                "deleted": r.deleted_paths,
                "errors": r.errors,
            }
            for r in results
        ],
        "total_deleted": total_deleted,
        "total_errors": total_errors,
    }

    if not args.dry_run:
        save_cleanup_state(STATE_FILE, payload)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / f"cleanup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"log={log_path}")

    print(f"done: deleted={total_deleted} errors={total_errors}")
    return 1 if total_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
