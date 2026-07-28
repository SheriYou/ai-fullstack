"""Build executable scenarios from the existing KB-generated test-case CSV.

This keeps the current knowledge-base-to-CSV generation unchanged. The output
CSV remains the source of truth for cases, phases, handoff expectations, and raw
backfill columns. This module only transforms that CSV into grouped scenarios
consumed by the runner.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

DEFAULT_PROFILE_ROOT = Path(__file__).resolve().parents[1] / "profiles" / "hot70"
DEFAULT_CASES_CSV = DEFAULT_PROFILE_ROOT / "data" / "Hot70_机器人_知识库指标测试.csv"
DEFAULT_SCENARIOS = DEFAULT_PROFILE_ROOT / "tmp" / "scenarios.json"

CASE_ID_RE = re.compile(r"^(.+)-(N|H-C\d+)$")
MONTHS = (
    "January|February|March|April|May|June|July|August|"
    "September|October|November|December"
)
KEYWORD_PATTERNS = [
    re.compile(r"IP\d+(?:/IP\d+)?", re.I),
    re.compile(r"\d[\d,]*\s?(?:mAh|Hz|nits|GB|MP|W)\b", re.I),
    re.compile(r"BDT\s?\d[\d,]*", re.I),
    re.compile(r"\d{1,3}(?:,\d{3})+"),
    re.compile(r"\b\d+\s?(?:years?|days?|hours?|months?)\b", re.I),
    re.compile(rf"\b(?:{MONTHS})\s?\d{{1,2}}(?:[–\-]\d{{1,2}})?", re.I),
    re.compile(r'"([^"]{2,60})"'),
    re.compile(r"\b(?:SONY|IBP|IBO|SIM|IMEI)\b", re.I),
]


def _read_csv_rows(path: Path) -> tuple[list[dict[str, str]], str]:
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "cp936"):
        try:
            with path.open(encoding=encoding, newline="") as f:
                return list(csv.DictReader(f)), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError(f"unable to decode CSV: {path}")


def _value(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _is_empty_row(row: dict[str, str]) -> bool:
    return not any(str(value or "").strip() for key, value in row.items() if key is not None)


def extract_keywords(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for pattern in KEYWORD_PATTERNS:
        for match in pattern.findall(text or ""):
            value = str(match).strip()
            key = value.lower()
            if value and key not in seen:
                seen.add(key)
                out.append(value)
    return out


def _scenario_kind(case_id: str) -> tuple[str, str]:
    match = CASE_ID_RE.match(case_id)
    if not match:
        return case_id, "N"
    return match.group(1), match.group(2)


def build(
    cases_csv: str | Path = DEFAULT_CASES_CSV,
    out_path: str | Path = DEFAULT_SCENARIOS,
) -> dict:
    cases_csv = Path(cases_csv)
    out_path = Path(out_path)
    rows, encoding = _read_csv_rows(cases_csv)
    if not rows:
        raise RuntimeError(f"cases CSV is empty: {cases_csv}")

    required = ["用例ID", "测试数据（英文提问）", "转人工预期", "是否存在知识库"]
    missing = [name for name in required if name not in rows[0]]
    if missing:
        raise RuntimeError(f"cases CSV missing columns: {missing}")

    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    warnings: list[str] = []

    empty_rows = 0
    bad_rows: list[int] = []

    for index, row in enumerate(rows, start=2):
        if _is_empty_row(row):
            empty_rows += 1
            continue
        case_id = _value(row, "用例ID")
        if not case_id:
            bad_rows.append(index)
            continue
        group_id, kind = _scenario_kind(case_id)
        if group_id not in groups:
            groups[group_id] = []
            order.append(group_id)

        query = _value(row, "测试数据（英文提问）", "测试数据")
        expected_handoff = _value(row, "转人工预期") == "是"
        kb_should_hit = _value(row, "是否存在知识库") == "是"
        expected_result = _value(row, "预期结果")
        answer_keywords = extract_keywords(expected_result) if kind == "N" and not expected_handoff else []

        groups[group_id].append(
            {
                "case_id": case_id,
                "kind": kind,
                "query": query,
                "phase": _value(row, "执行阶段"),
                "expect": {
                    "handoff": expected_handoff,
                    "kb_should_hit": kb_should_hit,
                    "answer_keywords": answer_keywords,
                    "expected_tag": None,
                },
                "raw": row,
            }
        )

    if bad_rows:
        preview = ", ".join(str(index) for index in bad_rows[:10])
        raise RuntimeError(f"cases CSV has non-empty rows without 用例ID at lines: {preview}")
    if not groups:
        raise RuntimeError(f"cases CSV has no valid case rows: {cases_csv}")
    if empty_rows:
        warnings.append(f"ignored empty rows: {empty_rows}")

    scenarios = [{"group_id": group_id, "turns": groups[group_id]} for group_id in order]
    payload = {
        "source_csv": str(cases_csv),
        "csv_encoding": encoding,
        "fieldnames": list(rows[0].keys()),
        "groups": scenarios,
        "warnings": warnings,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    n_turns = sum(len(group["turns"]) for group in scenarios)
    no_keywords = [
        turn["case_id"]
        for group in scenarios
        for turn in group["turns"]
        if turn["kind"] == "N" and not turn["expect"]["answer_keywords"] and not turn["expect"]["handoff"]
    ]
    print(f"生成 {out_path}")
    print(f"   会话组 {len(scenarios)}，轮次 {n_turns}（CSV 行 {len(rows)}，编码 {encoding}）")
    print(f"   -N 无事实关键词（回复准确维度将跳过）: {len(no_keywords)} 条")
    if warnings:
        print(f"warnings: {len(warnings)}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build scenarios.json from generated cases CSV.")
    parser.add_argument("--cases-csv", default=str(DEFAULT_CASES_CSV))
    parser.add_argument("--out", default=str(DEFAULT_SCENARIOS))
    args = parser.parse_args()
    build(args.cases_csv, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
