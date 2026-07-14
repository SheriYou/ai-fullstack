#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate FAQ source quality before case generation (new header only)."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FAQ_CSV = ROOT / "prd" / "Hot 70 FAQ知识库_FAQ知识库_全部FAQ.csv"

REQUIRED_COLUMNS = [
    "序号",
    "用户问题",
    "问题（英文）",
    "分类",
    "业务反馈",
    "回复中文翻译",
    "是否转人工（英文）",
    "是否需要转人工",
    "转人工条件（英文）",
    "转人工条件/备注",
    "状态",
]


def load_rows(path: Path) -> tuple[list[dict], str]:
    for enc in ("utf-8-sig", "utf-8", "gb18030", "cp936"):
        try:
            with path.open("r", encoding=enc, newline="") as f:
                return list(csv.DictReader(f)), enc
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, "failed to decode csv")


def normalize_handoff(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return "empty"
    if v in ("是", "yes", "YES", "true", "TRUE"):
        return "true"
    if v in ("否", "no", "NO", "false", "FALSE"):
        return "false"
    if v in ("视情况", "conditional", "maybe"):
        return "conditional"
    return "unknown"


def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def split_handoff_conditions(en_text: str, note_text: str, limit: int = 5) -> list[str]:
    parts: list[str] = []
    raw_items = [normalize_space(en_text), normalize_space(note_text)]
    for raw in raw_items:
        if not raw:
            continue
        cleaned = raw
        cleaned = re.sub(r"(?i)^transfer to human(?:\s+for.*)?\s+if\s+", "", cleaned)
        cleaned = re.sub(r"(?i)^if\s+", "", cleaned)
        cleaned = re.sub(r"^如(果)?", "", cleaned)
        cleaned = re.sub(r"(，|,)?转人工.*$", "", cleaned)
        for token in re.split(r"(?:\bor\b|\band\b|[，,；;。/\n、]|以及|或者|或|并且)", cleaned):
            t = normalize_space(token).strip("：:。.!?？")
            if len(t) < 2:
                continue
            parts.append(t)

    out: list[str] = []
    seen = set()
    for p in parts:
        k = p.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(p[:120])
        if len(out) >= limit:
            break
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate FAQ source before case writing.")
    parser.add_argument("--faq-csv", default=str(DEFAULT_FAQ_CSV), help="FAQ csv path")
    args = parser.parse_args()

    faq_csv = Path(args.faq_csv)
    if not faq_csv.exists():
        print(json.dumps({"ok": False, "error": f"file not found: {faq_csv}"}, ensure_ascii=False))
        return 2

    rows, enc = load_rows(faq_csv)
    if not rows:
        print(json.dumps({"ok": False, "error": "empty csv"}, ensure_ascii=False))
        return 2

    fieldnames = list(rows[0].keys())
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in fieldnames]

    errors: list[str] = []
    warnings: list[str] = []
    q_seen: dict[str, int] = {}

    for idx, row in enumerate(rows, start=2):
        q = (row.get("用户问题") or "").strip()
        q_en = (row.get("问题（英文）") or "").strip()
        cat = (row.get("分类") or "").strip()
        handoff_raw = (row.get("是否需要转人工") or "").strip()
        handoff = normalize_handoff(handoff_raw)
        cond_en = (row.get("转人工条件（英文）") or "").strip()
        cond_note = (row.get("转人工条件/备注") or "").strip()
        reply = (row.get("回复中文翻译") or row.get("业务反馈") or "").strip()

        if not q:
            errors.append(f"L{idx}: 用户问题为空")
        if not q_en:
            errors.append(f"L{idx}: 问题（英文）为空")
        if not cat:
            errors.append(f"L{idx}: 分类为空")
        if not reply:
            errors.append(f"L{idx}: 回复中文翻译/业务反馈均为空")
        if handoff == "empty":
            warnings.append(f"L{idx}: 是否需要转人工为空（建议补齐为 是/否/视情况）")
        elif handoff == "unknown":
            errors.append(f"L{idx}: 是否需要转人工值非法: {handoff_raw!r}")

        if q:
            if q in q_seen:
                warnings.append(f"L{idx}: 用户问题重复，首次出现在L{q_seen[q]}: {q}")
            else:
                q_seen[q] = idx

        if handoff == "conditional":
            scenes = split_handoff_conditions(cond_en, cond_note)
            if not scenes:
                errors.append(
                    f"L{idx}: 是否需要转人工=视情况，但转人工条件未提供可解析场景"
                )

    if missing_cols:
        errors.insert(0, f"缺少字段: {', '.join(missing_cols)}")

    payload = {
        "ok": len(errors) == 0,
        "faq_csv": str(faq_csv),
        "encoding": enc,
        "rows": len(rows),
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

