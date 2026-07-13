#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Recompute `知识库是否命中` and `执行结果`, and apply handoff-fallback
consistency overrides.

Base rule:
- Deterministic lookup against KB table.

Override rule (business confirmed):
- If `转人工预期=是` and `转人工时机是否准确=是`, and the reply is the
  standard fallback template ("A human agent is not available right now ..."),
  then force:
  - `知识库是否命中=是`
  - `回复是否准确=是`
  - remove `kb_not_hit` / `answer_incorrect` from `缺陷记录`

Execution result rule (business confirmed):
- Recompute `执行结果` with key gates only (not strict all-fields):
  - PASS: `回复是否准确=是` and `转人工时机是否准确=是` and no api/script error
  - FAIL: otherwise

Notes:
- `知识库是否命中` / `意图标签` fields are quality signals and do not
  directly fail `执行结果`.
- Optional row range can be applied via `--row-start/--row-end`
  (CSV line numbers, header is line 1).

Usage:
  python scripts/recompute_kb_hit_from_table.py
  python scripts/recompute_kb_hit_from_table.py --dry-run
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
DEFAULT_KB_CSV = Path(
    r"D:\CMP\agent-human-test\projects\hot70-wa-bot\prd\Hot70_Script.csv"
)

FALLBACK_TEMPLATE = (
    "A human agent is not available right now, so I will keep helping you here. "
    "You can share more details, and I will do my best based on the available information."
)


def yesno_to_bool(value: str) -> bool | None:
    v = (value or "").strip().lower()
    if v in {"是", "y", "yes", "true", "1"}:
        return True
    if v in {"否", "n", "no", "false", "0"}:
        return False
    return None


def normalize_reply(value: str) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip().lower()


def is_handoff_fallback_reply(reply_en: str) -> bool:
    if not reply_en:
        return False
    return normalize_reply(FALLBACK_TEMPLATE) in normalize_reply(reply_en)


def cleanup_defect_codes(raw: str, remove_codes: set[str]) -> str:
    parts = [p.strip() for p in (raw or "").split(";") if p.strip()]
    kept = [p for p in parts if p not in remove_codes]
    return "; ".join(kept)


def defect_codes(raw: str) -> list[str]:
    return [p.strip() for p in (raw or "").split(";") if p.strip()]


def has_api_or_script_error(raw: str) -> bool:
    for code in defect_codes(raw):
        lc = code.lower()
        if lc == "api_error" or lc.startswith("api_error"):
            return True
        if lc == "script_error" or lc.startswith("script_error"):
            return True
    return False


def has_any_execution_signal(row: dict) -> bool:
    keys = [
        "回复是否准确",
        "转人工时机是否准确",
        "实际回复内容（英文）",
        "缺陷记录",
        "知识库是否命中",
        "执行结果",
    ]
    return any((row.get(k) or "").strip() for k in keys)


def recompute_execution_result(row: dict) -> str:
    old = (row.get("执行结果") or "").strip()
    if not has_any_execution_signal(row):
        return old

    reply_ok = yesno_to_bool(row.get("回复是否准确", "")) is True
    handoff_ok = yesno_to_bool(row.get("转人工时机是否准确", "")) is True
    api_or_script_error = has_api_or_script_error(row.get("缺陷记录", ""))
    return "PASS" if (reply_ok and handoff_ok and not api_or_script_error) else "FAIL"


def normalize_text(value: str) -> str:
    if not value:
        return ""
    v = value.strip().lower()
    # Keep only alnum + CJK to make matching deterministic and punctuation-insensitive.
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", v)


def load_kb_keys(kb_csv: Path, encoding: str) -> tuple[set[str], set[str]]:
    with kb_csv.open("r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f)
        en_keys: set[str] = set()
        cn_keys: set[str] = set()
        for row in reader:
            en = normalize_text(row.get("文本 5", ""))
            cn = normalize_text(row.get("用户问题（用户实际使用语种）", ""))
            if en:
                en_keys.add(en)
            if cn:
                cn_keys.add(cn)
    return en_keys, cn_keys


def recompute(
    result_csv: Path,
    result_encoding: str,
    en_keys: set[str],
    cn_keys: set[str],
    row_start: int | None = None,
    row_end: int | None = None,
) -> tuple[list[dict], dict]:
    with result_csv.open("r", encoding=result_encoding, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    changed_rows: list[dict] = []
    override_rows = 0
    reply_fixed_rows = 0
    defects_cleaned_rows = 0
    exec_changed_rows = 0

    for idx, row in enumerate(rows, start=2):
        in_scope = True
        if row_start is not None and idx < row_start:
            in_scope = False
        if row_end is not None and idx > row_end:
            in_scope = False
        if not in_scope:
            continue

        en_q = normalize_text(row.get("测试数据（英文提问）", ""))
        cn_q = normalize_text(row.get("测试数据", ""))
        hit_by_kb = (en_q and en_q in en_keys) or (cn_q and cn_q in cn_keys)

        expected_handoff = yesno_to_bool(row.get("转人工预期", "")) is True
        handoff_timing_ok = yesno_to_bool(row.get("转人工时机是否准确", "")) is True
        fallback_reply = is_handoff_fallback_reply(row.get("实际回复内容（英文）", ""))
        handoff_override = expected_handoff and handoff_timing_ok and fallback_reply

        new_value = "是" if (hit_by_kb or handoff_override) else "否"

        old_value = (row.get("知识库是否命中") or "").strip()
        old_reply_acc = (row.get("回复是否准确") or "").strip()
        old_defects = row.get("缺陷记录", "")
        old_exec = (row.get("执行结果") or "").strip()

        if handoff_override:
            override_rows += 1
            row["回复是否准确"] = "是"
            row["缺陷记录"] = cleanup_defect_codes(
                old_defects, remove_codes={"kb_not_hit", "answer_incorrect"}
            )
            if old_reply_acc != row["回复是否准确"]:
                reply_fixed_rows += 1
            if (old_defects or "").strip() != (row["缺陷记录"] or "").strip():
                defects_cleaned_rows += 1

        row["知识库是否命中"] = new_value
        row["执行结果"] = recompute_execution_result(row)
        if old_exec != (row.get("执行结果") or "").strip():
            exec_changed_rows += 1

        if (
            old_value != new_value
            or old_reply_acc != (row.get("回复是否准确") or "").strip()
            or (old_defects or "").strip() != (row.get("缺陷记录") or "").strip()
            or old_exec != (row.get("执行结果") or "").strip()
        ):
            changed_rows.append(
                {
                    "line_no": idx,
                    "用例ID": row.get("用例ID", ""),
                    "old_hit": old_value,
                    "new_hit": new_value,
                    "handoff_override": "是" if handoff_override else "否",
                    "old_reply_acc": old_reply_acc,
                    "new_reply_acc": (row.get("回复是否准确") or "").strip(),
                    "old_defects": (old_defects or "").strip(),
                    "new_defects": (row.get("缺陷记录") or "").strip(),
                    "old_exec": old_exec,
                    "new_exec": (row.get("执行结果") or "").strip(),
                    "测试数据（英文提问）": row.get("测试数据（英文提问）", ""),
                }
            )

    stats = {
        "total_rows": len(rows),
        "changed_rows": len(changed_rows),
        "new_yes": sum(1 for r in rows if (r.get("知识库是否命中") or "").strip() == "是"),
        "new_no": sum(1 for r in rows if (r.get("知识库是否命中") or "").strip() == "否"),
        "override_rows": override_rows,
        "reply_fixed_rows": reply_fixed_rows,
        "defects_cleaned_rows": defects_cleaned_rows,
        "exec_changed_rows": exec_changed_rows,
        "row_start": row_start if row_start is not None else "",
        "row_end": row_end if row_end is not None else "",
        "fieldnames": fieldnames,
    }
    return rows, {"stats": stats, "changed_rows": changed_rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-csv", default=str(DEFAULT_RESULT_CSV))
    parser.add_argument("--kb-csv", default=str(DEFAULT_KB_CSV))
    parser.add_argument("--result-encoding", default="gb18030")
    parser.add_argument("--kb-encoding", default="utf-8-sig")
    parser.add_argument("--row-start", type=int, default=None)
    parser.add_argument("--row-end", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write-backup", action="store_true")
    args = parser.parse_args()

    result_csv = Path(args.result_csv)
    kb_csv = Path(args.kb_csv)

    en_keys, cn_keys = load_kb_keys(kb_csv, args.kb_encoding)
    rows, payload = recompute(
        result_csv,
        args.result_encoding,
        en_keys,
        cn_keys,
        row_start=args.row_start,
        row_end=args.row_end,
    )
    stats = payload["stats"]
    changed_rows = payload["changed_rows"]

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = Path(r"D:\CMP\agent-human-test\projects\hot70-wa-bot\reports\runs") / ts
    report_dir.mkdir(parents=True, exist_ok=True)
    delta_csv = report_dir / "kb-hit-recompute-delta.csv"

    with delta_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "用例ID",
                "old_hit",
                "new_hit",
                "handoff_override",
                "old_reply_acc",
                "new_reply_acc",
                "old_defects",
                "new_defects",
                "old_exec",
                "new_exec",
                "line_no",
                "测试数据（英文提问）",
            ],
        )
        writer.writeheader()
        writer.writerows(changed_rows)

    backup_path = None
    if not args.dry_run:
        if args.write_backup:
            backup_path = result_csv.with_suffix(
                f".kbhit-backup-{ts}{result_csv.suffix}"
            )
            shutil.copyfile(result_csv, backup_path)

        with result_csv.open("w", encoding=args.result_encoding, newline="") as f:
            writer = csv.DictWriter(f, fieldnames=stats["fieldnames"])
            writer.writeheader()
            writer.writerows(rows)

    print(f"kb_csv={kb_csv}")
    print(f"result_csv={result_csv}")
    print(f"total_rows={stats['total_rows']}")
    print(f"changed_rows={stats['changed_rows']}")
    print(f"new_yes={stats['new_yes']}")
    print(f"new_no={stats['new_no']}")
    print(f"override_rows={stats['override_rows']}")
    print(f"reply_fixed_rows={stats['reply_fixed_rows']}")
    print(f"defects_cleaned_rows={stats['defects_cleaned_rows']}")
    print(f"exec_changed_rows={stats['exec_changed_rows']}")
    print(f"row_start={stats['row_start']}")
    print(f"row_end={stats['row_end']}")
    print(f"delta_csv={delta_csv}")
    if backup_path:
        print(f"backup_csv={backup_path}")
    print(f"dry_run={args.dry_run}")


if __name__ == "__main__":
    main()
