#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Recompute intent-tag related fields in review CSV.

Rules:
1) `实际识别的意图标签` must be one of:
   - 已预定未提机
   - 未预定高意向
   - 未预定低意向
   - 已提交
   Otherwise set to empty.
2) `意图标签是否准确` is judged by conversation content:
   - infer expected tag from user text
   - accurate = (actual_tag == expected_tag) if expected exists else (actual_tag == "")
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

ALLOWED_TAGS = {
    "已预定未提机",
    "未预定高意向",
    "未预定低意向",
    "已提交",
}

TAG_ALIASES = {
    "已提机": "已提交",
    "已提货": "已提交",
    "已取机": "已提交",
    "already_picked_up": "已提交",
    "picked_up": "已提交",
    "preordered_not_picked": "已预定未提机",
    "high_intent_not_preordered": "未预定高意向",
    "low_intent_not_preordered": "未预定低意向",
}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def normalize_tag(raw: str) -> str:
    v = norm(raw)
    if not v:
        return ""
    if v in ALLOWED_TAGS:
        return v
    return TAG_ALIASES.get(v, "")


def extract_tag_from_note(note: str) -> str:
    if not note:
        return ""
    patterns = [
        r"customer_tag=([^;\s]+)",
        r"customerTag=([^;\s]+)",
        r"intent_tag=([^;\s]+)",
        r"intentTag=([^;\s]+)",
    ]
    for p in patterns:
        m = re.search(p, note)
        if m:
            return normalize_tag(m.group(1))
    return ""


def contains_any(text: str, keywords: list[str]) -> bool:
    t = (text or "").lower()
    return any(k in t for k in keywords)


def infer_expected_tag(user_cn: str, user_en: str) -> str:
    cn = user_cn or ""
    en = (user_en or "").lower()

    picked_cn = ["已经提机", "已提机", "已经提货", "已提货", "已经取机", "已取机"]
    picked_en = ["already picked up", "have already picked up", "i have already picked up"]
    if any(k in cn for k in picked_cn) or contains_any(en, picked_en):
        return "已提交"

    preordered_cn = ["已经预订", "已预订", "已经预约", "已预约"]
    not_picked_cn = ["还没提", "未提机", "没提机", "尚未提机", "还未提机"]
    preordered_en = ["already pre-order", "already preordered", "already booked"]
    not_picked_en = ["not picked up", "haven't picked up", "have not picked up", "not picked it up yet"]
    if (
        any(k in cn for k in preordered_cn)
        and any(k in cn for k in not_picked_cn)
    ) or (
        contains_any(en, preordered_en)
        and contains_any(en, not_picked_en)
    ):
        return "已预定未提机"

    low_cn = ["只想领福利", "只领福利", "只想薅羊毛", "先领福利"]
    low_en = ["only want to claim", "only want benefits", "just want benefits", "only for benefits"]
    if any(k in cn for k in low_cn) or contains_any(en, low_en):
        return "未预定低意向"

    high_cn = ["分期怎么买", "想分期", "我想买", "怎么买", "想购买", "想入手"]
    high_en = [
        "how can i buy in installments",
        "how to buy in installments",
        "can i pay in installments",
        "i want to buy",
        "i want to purchase",
    ]
    if any(k in cn for k in high_cn) or contains_any(en, high_en):
        return "未预定高意向"

    return ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-csv", default=str(DEFAULT_RESULT_CSV))
    parser.add_argument("--result-encoding", default="gb18030")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    p = Path(args.result_csv)
    with p.open("r", encoding=args.result_encoding, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    changed_tag = 0
    changed_acc = 0
    stats = {
        "total": len(rows),
        "actual_non_empty": 0,
        "accuracy_yes": 0,
        "accuracy_no": 0,
        "expected_non_empty": 0,
    }
    deltas: list[dict] = []

    for row in rows:
        cid = row.get("用例ID", "")
        old_tag = norm(row.get("实际识别的意图标签", ""))
        old_acc = norm(row.get("意图标签是否准确", ""))

        note_tag = extract_tag_from_note(row.get("备注", ""))
        actual_tag = note_tag or normalize_tag(old_tag)

        expected_tag = infer_expected_tag(
            row.get("测试数据", ""),
            row.get("测试数据（英文提问）", ""),
        )

        accurate = (actual_tag == expected_tag) if expected_tag else (actual_tag == "")
        new_acc = "是" if accurate else "否"

        if old_tag != actual_tag:
            changed_tag += 1
        if old_acc != new_acc:
            changed_acc += 1

        row["实际识别的意图标签"] = actual_tag
        row["意图标签是否准确"] = new_acc

        if actual_tag:
            stats["actual_non_empty"] += 1
        if expected_tag:
            stats["expected_non_empty"] += 1
        if new_acc == "是":
            stats["accuracy_yes"] += 1
        else:
            stats["accuracy_no"] += 1

        if old_tag != actual_tag or old_acc != new_acc:
            deltas.append(
                {
                    "用例ID": cid,
                    "old_actual": old_tag,
                    "new_actual": actual_tag,
                    "expected": expected_tag,
                    "old_accuracy": old_acc,
                    "new_accuracy": new_acc,
                }
            )

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = Path(r"D:\CMP\agent-human-test\projects\hot70-wa-bot\reports\runs") / ts
    report_dir.mkdir(parents=True, exist_ok=True)
    delta_csv = report_dir / "intent-tag-recompute-delta.csv"
    with delta_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "用例ID",
                "old_actual",
                "new_actual",
                "expected",
                "old_accuracy",
                "new_accuracy",
            ],
        )
        writer.writeheader()
        writer.writerows(deltas)

    backup = None
    if not args.dry_run:
        backup = p.with_suffix(f".intent-tag-backup-{ts}{p.suffix}")
        shutil.copyfile(p, backup)
        with p.open("w", encoding=args.result_encoding, newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    print(f"result_csv={p}")
    print(f"total_rows={stats['total']}")
    print(f"changed_actual_tag_rows={changed_tag}")
    print(f"changed_accuracy_rows={changed_acc}")
    print(f"actual_non_empty={stats['actual_non_empty']}")
    print(f"expected_non_empty={stats['expected_non_empty']}")
    print(f"accuracy_yes={stats['accuracy_yes']}")
    print(f"accuracy_no={stats['accuracy_no']}")
    print(f"delta_csv={delta_csv}")
    if backup:
        print(f"backup_csv={backup}")
    print(f"dry_run={args.dry_run}")


if __name__ == "__main__":
    main()
