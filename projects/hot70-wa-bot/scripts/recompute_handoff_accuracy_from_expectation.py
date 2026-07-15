#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Recompute `转人工是否准确` by direct comparison:
  accurate = (actual_handoff == expected_handoff)

`expected_handoff` is read from `转人工预期` (是/否).
`actual_handoff` is inferred deterministically from `备注` field's `task_type=...`.
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
from datetime import datetime
from pathlib import Path


DEFAULT_RESULT_CSV = Path(
    r"D:\CMP\agent-human-test\projects\hot70-wa-bot\prd\Hot70_机器人_人工复核结果 - Sheet1.csv"
)


TRUE_TASK_TYPES = {
    "TRANSFER_FAILED_AI_FALLBACK",  # transfer path triggered but human unavailable
    "TRANSFER_SUCCESS",
    "TRANSFERRED",
    "HANDOFF_SUCCESS",
    "HANDOFF_ATTEMPTED",
}


def parse_task_type(note: str) -> str:
    if not note:
        return ""
    m = re.search(r"task_type=([^;\s]+)", note)
    return m.group(1).strip() if m else ""


def yesno_to_bool(v: str) -> bool:
    return (v or "").strip() == "是"


def bool_to_yesno(v: bool) -> str:
    return "是" if v else "否"


def infer_actual_handoff(task_type: str) -> bool:
    return task_type in TRUE_TASK_TYPES


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-csv", default=str(DEFAULT_RESULT_CSV))
    parser.add_argument("--result-encoding", default="gb18030")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result_csv = Path(args.result_csv)
    with result_csv.open("r", encoding=args.result_encoding, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    changed = 0
    mismatch = 0
    unknown_task_type = 0
    samples = []

    for row in rows:
        expected = yesno_to_bool(row.get("转人工预期", ""))
        task_type = parse_task_type(row.get("备注", ""))
        actual = infer_actual_handoff(task_type)
        accurate = expected == actual
        new_value = bool_to_yesno(accurate)

        old_value = (row.get("转人工是否准确") or "").strip()
        if old_value != new_value:
            changed += 1
            if len(samples) < 30:
                samples.append(
                    {
                        "用例ID": row.get("用例ID", ""),
                        "old": old_value,
                        "new": new_value,
                        "预期": row.get("转人工预期", ""),
                        "task_type": task_type,
                    }
                )
            row["转人工是否准确"] = new_value

        if not accurate:
            mismatch += 1
        if not task_type:
            unknown_task_type += 1

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = Path(r"D:\CMP\agent-human-test\projects\hot70-wa-bot\reports\runs") / ts
    report_dir.mkdir(parents=True, exist_ok=True)
    delta_csv = report_dir / "handoff-accuracy-recompute-delta.csv"
    with delta_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["用例ID", "old", "new", "预期", "task_type"]
        )
        writer.writeheader()
        writer.writerows(samples)

    backup_path = None
    if not args.dry_run:
        backup_path = result_csv.with_suffix(
            f".handoff-backup-{ts}{result_csv.suffix}"
        )
        shutil.copyfile(result_csv, backup_path)
        with result_csv.open("w", encoding=args.result_encoding, newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    print(f"result_csv={result_csv}")
    print(f"total_rows={len(rows)}")
    print(f"changed_rows={changed}")
    print(f"mismatch_rows={mismatch}")
    print(f"unknown_task_type_rows={unknown_task_type}")
    print(f"delta_csv={delta_csv}")
    if backup_path:
        print(f"backup_csv={backup_path}")
    print(f"dry_run={args.dry_run}")


if __name__ == "__main__":
    main()
