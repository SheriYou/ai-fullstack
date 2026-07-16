#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate KB metric cases generated from the Hot70 FAQ CSV."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FAQ = ROOT / "prd" / "Hot 70 FAQ知识库_FAQ知识库_全部FAQ.csv"
DEFAULT_CASES = ROOT / "prd" / "Hot70_机器人_知识库指标测试.csv"

EXPECTED_FIELDS = [
    "用例ID", "用例名称", "执行步骤", "预期结果", "转人工触发条件", "测试目标",
    "前置条件", "测试数据", "测试数据（英文提问）", "转人工预期", "是否存在知识库",
    "执行阶段", "是否使用新会话", "知识库是否命中", "知识库是否命中正确", "日志客户标签",
    "客户标签是否准确", "日志转人工", "转人工是否准确", "实际回复内容（英文）", "语义是否合理", "回复是否准确",
    "服务端真实耗时", "接口响应时长", "备注",
]
RESULT_FIELDS = {
    "知识库是否命中", "知识库是否命中正确", "日志客户标签", "客户标签是否准确",
    "日志转人工", "转人工是否准确", "实际回复内容（英文）", "语义是否合理", "回复是否准确",
    "服务端真实耗时", "接口响应时长", "备注",
}
CASE_ID_RE = re.compile(r"^(TC-H70-(\d{3}))-(N|H-C(\d{2}))$")


def load_csv(path: Path) -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "cp936"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"cannot decode CSV: {path}")


def add_error(errors: list[str], message: str) -> None:
    errors.append(message)


def validate(rows: list[dict[str, str]], faq_rows: list[dict[str, str]], status: str) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if not rows:
        add_error(errors, "case CSV is empty")
        return {"errors": errors, "warnings": warnings}

    actual_fields = list(rows[0].keys())
    if actual_fields != EXPECTED_FIELDS:
        add_error(errors, f"unexpected fields/order: {actual_fields}")

    filtered_faq = [
        row for row in faq_rows
        if status.lower() == "all" or (row.get("状态") or "").strip() == status
    ]
    usable_faq = [
        row for row in filtered_faq
        if (row.get("用户问题") or "").strip()
        and (row.get("问题（英文）") or "").strip()
        and (row.get("分类") or "").strip()
    ]
    expected_n = len(usable_faq)
    n_rows = [row for row in rows if (row.get("用例ID") or "").endswith("-N")]
    h_rows = [row for row in rows if "-H-C" in (row.get("用例ID") or "")]
    if len(n_rows) != expected_n:
        add_error(errors, f"N count {len(n_rows)} != usable FAQ count {expected_n}")

    expected_base_numbers = list(range(1, len(n_rows) + 1))
    actual_base_numbers = []
    for row in n_rows:
        match = CASE_ID_RE.fullmatch((row.get("用例ID") or "").strip())
        if match:
            actual_base_numbers.append(int(match.group(2)))
    if actual_base_numbers != expected_base_numbers:
        add_error(errors, f"N base IDs are not sequential: {actual_base_numbers}")

    base_ids: dict[str, dict] = {}
    for index, row in enumerate(rows, start=2):
        case_id = (row.get("用例ID") or "").strip()
        match = CASE_ID_RE.fullmatch(case_id)
        if not match:
            add_error(errors, f"row {index}: invalid case ID {case_id!r}")
            continue
        base, suffix = match.group(1), match.group(3)
        if case_id in base_ids:
            add_error(errors, f"row {index}: duplicate case ID {case_id}")
        base_ids[case_id] = row
        required = [
            "用例ID", "用例名称", "执行步骤", "预期结果", "前置条件", "测试数据",
            "测试数据（英文提问）", "转人工预期", "是否存在知识库", "是否使用新会话",
        ]
        for field in required:
            if not (row.get(field) or "").strip():
                add_error(errors, f"row {index} {case_id}: empty required field {field}")
        if row.get("是否存在知识库") not in {"是", "否"}:
            add_error(errors, f"row {index} {case_id}: invalid knowledge flag")
        if row.get("执行阶段") not in {"", "P0", "P1", "P2"}:
            add_error(errors, f"row {index} {case_id}: invalid execution stage")
        if suffix == "N" and row.get("是否使用新会话") != "是":
            add_error(errors, f"row {index} {case_id}: N must use new session")
        if suffix.startswith("H-C"):
            if row.get("是否使用新会话") != "否":
                add_error(errors, f"row {index} {case_id}: H must reuse session")
            if row.get("转人工预期") != "是":
                add_error(errors, f"row {index} {case_id}: H handoff expectation must be 是")
            if f"{base}-N" not in base_ids and f"{base}-N" not in {r.get("用例ID") for r in rows}:
                add_error(errors, f"row {index} {case_id}: missing parent N")
        for field in RESULT_FIELDS:
            if (row.get(field) or "").strip():
                warnings.append(f"row {index} {case_id}: result field already populated: {field}")

    h_by_base: dict[str, list[int]] = {}
    for row in h_rows:
        match = CASE_ID_RE.fullmatch((row.get("用例ID") or "").strip())
        if not match:
            continue
        h_by_base.setdefault(match.group(1), []).append(int(match.group(4)))
    for base, condition_numbers in h_by_base.items():
        expected_conditions = list(range(1, len(condition_numbers) + 1))
        if sorted(condition_numbers) != expected_conditions:
            add_error(errors, f"{base}: H-Cxx IDs are not sequential: {condition_numbers}")

    stage_counts = Counter((row.get("执行阶段") or "").strip() for row in rows)
    if stage_counts["P0"] > min(20, len(rows)):
        add_error(errors, "P0 exceeds maximum 20")
    if stage_counts["P1"] > int(len(rows) * 0.10):
        add_error(errors, "P1 exceeds 10% quota")
    if stage_counts["P2"] > int(len(rows) * 0.30):
        add_error(errors, "P2 exceeds 30% quota")
    return {
        "errors": errors,
        "warnings": warnings,
        "case_count": len(rows),
        "n_count": len(n_rows),
        "h_count": len(h_rows),
        "stage_counts": dict(stage_counts),
        "faq_status": status,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generated Hot70 KB metric cases.")
    parser.add_argument("--faq-csv", default=str(DEFAULT_FAQ))
    parser.add_argument("--cases-csv", default=str(DEFAULT_CASES))
    parser.add_argument("--status", default="已确认")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = validate(load_csv(Path(args.cases_csv)), load_csv(Path(args.faq_csv)), args.status)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"cases={result.get('case_count', 0)} N={result.get('n_count', 0)} H={result.get('h_count', 0)}")
        print(f"stages={result.get('stage_counts', {})}")
        for message in result.get("warnings", []):
            print(f"WARNING: {message}")
        for message in result.get("errors", []):
            print(f"ERROR: {message}")
    return 1 if result.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
