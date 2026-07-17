#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the six-metric Hot70 test report from persisted case results."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
RESULTS_JSONL = REPORTS / "cases-results.jsonl"


def load_results() -> list[dict]:
    if not RESULTS_JSONL.exists():
        return []
    results: list[dict] = []
    with RESULTS_JSONL.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                results.append(json.loads(line))
    return results


def percentage(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator * 100, 2)


def numeric_values(results: list[dict], field: str) -> list[float]:
    values: list[float] = []
    for row in results:
        try:
            value = float(row.get(field, ""))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            values.append(value)
    return values


def summarize(results: list[dict]) -> dict:
    kb_exists = [row for row in results if row.get("是否存在知识库") == "是"]
    kb_hit = sum(row.get("知识库是否命中") == "是" for row in kb_exists)

    tag_values = [row.get("客户标签是否准确") for row in results]
    tag_denominator = sum(value in {"是", "否"} for value in tag_values)
    tag_numerator = sum(value == "是" for value in tag_values)

    handoff_values = [row.get("转人工是否准确") for row in results]
    handoff_denominator = sum(value in {"是", "否"} for value in handoff_values)
    handoff_numerator = sum(value == "是" for value in handoff_values)

    reply_values = [row.get("回复是否准确") for row in results]
    reply_denominator = sum(value in {"是", "否", "NA"} for value in reply_values)
    reply_numerator = sum(value == "是" for value in reply_values)

    service_values = numeric_values(results, "服务端真实耗时")
    response_values = numeric_values(results, "接口响应时长")

    return {
        "知识库命中率": percentage(kb_hit, len(kb_exists)),
        "标签准确率": percentage(tag_numerator, tag_denominator),
        "转人工准确率": percentage(handoff_numerator, handoff_denominator),
        "回复准确率": percentage(reply_numerator, reply_denominator),
        "平均服务端真实耗时": round(sum(service_values) / len(service_values), 2) if service_values else None,
        "平均接口响应时长": round(sum(response_values) / len(response_values), 2) if response_values else None,
    }


def format_metric(value: float | None, unit: str = "%") -> str:
    return "NA" if value is None else f"{value:.2f}{unit}"


def write_report(summary: dict) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "aggregated-results.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Hot70 测试报告",
        "",
        f"1. 知识库命中率：（知识库是否命中=是）÷（是否存在知识库=是）×100% = {format_metric(summary['知识库命中率'])}",
        f"2. 标签准确率：（客户标签是否准确=是）÷（客户标签是否准确=是/否）×100% = {format_metric(summary['标签准确率'])}",
        f"3. 转人工准确率：（转人工是否准确=是）÷（转人工是否准确=是/否）×100% = {format_metric(summary['转人工准确率'])}",
        f"4. 回复准确率：（回复是否准确=是）÷（回复是否准确=是/否/NA）×100% = {format_metric(summary['回复准确率'])}",
        f"5. 平均服务端真实耗时：{format_metric(summary['平均服务端真实耗时'], ' ms')}",
        f"6. 平均接口响应时长：{format_metric(summary['平均接口响应时长'], ' ms')}",
    ]
    (REPORTS / "aggregated-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="按六项指定指标生成测试报告")
    parser.parse_args()
    write_report(summarize(load_results()))


if __name__ == "__main__":
    main()
