#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analyze a Hot70 backfill CSV and generate release-report style summaries.

The script is intentionally offline and conservative: manual review columns win,
automatic/LLM columns are used as fallback, and text classification only provides
reason suggestions for rows that still need human review.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


DEFAULT_INPUT = Path("profiles/hot70/reports/latest-run.json")

METRICS = [
    {
        "key": "kb_hit",
        "label": "知识库命中正确",
        "target": "90%",
        "manual": ("知识库命中（人工复核）", "知识库命中(人工复核)", "知识库命中人工复核"),
        "auto": ("知识库是否命中正确", "知识库是否命中（是否准确）"),
        "derived": ("是否存在知识库", "知识库是否命中（日志）"),
    },
    {
        "key": "handoff",
        "label": "转人工正确率",
        "target": "90%",
        "manual": ("转人工准确（人工复核）", "转人工准确(人工复核)", "转人工人工复核"),
        "auto": ("转人工是否准确",),
    },
    {
        "key": "tag",
        "label": "客户标签正确率",
        "target": "85%",
        "manual": ("客户标签准确（人工复核）", "客户标签准确(人工复核)", "客户标签人工复核"),
        "auto": ("LLM判定客户标签是否准确", "客户标签是否准确"),
    },
    {
        "key": "answer",
        "label": "回复答案正确",
        "target": "85%",
        "manual": ("回复准确（人工复核）", "回复准确(人工复核)", "回复人工复核"),
        "auto": ("回复是否准确（LLM）", "回复是否准确"),
    },
    {
        "key": "semantic",
        "label": "语义合理",
        "target": "NA",
        "manual": ("语义合理（人工复核）", "语义是否合理（人工复核）", "语义人工复核"),
        "auto": ("语义是否合理（LLM）", "语义是否合理"),
    },
]

ID_COLUMNS = ("用例ID", "case_id", "Case ID")
QUESTION_COLUMNS = ("测试数据（英文提问）", "测试数据", "用户问题", "问题")
REPLY_COLUMNS = ("实际回复内容（英文）", "实际回复内容", "回复内容", "bot_reply")
PHASE_COLUMNS = ("执行阶段", "批次", "阶段")

POSITIVE = {"是", "符合", "通过", "pass", "true", "yes", "y", "1", "ok", "正确", "合理"}
NEGATIVE = {"否", "不符合", "不通过", "fail", "false", "no", "n", "0", "错误", "不合理"}
PENDING = {"待确认", "待复核", "待判定", "待验证", "na", "n/a", "null", "none", "-", "—", ""}

UNRELATED_KEYWORDS = (
    "job",
    "resume",
    "salary",
    "weather",
    "medical",
    "doctor",
    "loan",
    "bank",
    "password",
    "privacy",
    "complaint",
    "scam",
    "link",
    "招聘",
    "简历",
    "薪资",
    "天气",
    "医疗",
    "贷款",
    "隐私",
    "投诉",
    "诈骗",
    "链接",
)
HOT70_KEYWORDS = ("hot 70", "hot70", "hot 70 pro", "infinix", "whatsapp channel handles")
GENERIC_FALLBACKS = (
    "how can i assist",
    "how may i assist",
    "can you clarify",
    "please clarify",
    "i'm sorry",
    "i am sorry",
    "unable to answer",
)
HUMAN_UNAVAILABLE = (
    "human agent is not available",
    "agent is not available",
    "no human agent",
    "人工暂不可用",
    "人工客服暂不可用",
)


@dataclass
class MetricStats:
    key: str
    label: str
    target: str
    total: int = 0
    yes: int = 0
    no: int = 0
    pending: int = 0
    blank: int = 0
    manual_total: int = 0
    raw_yes: int = 0
    raw_no: int = 0
    raw_pending: int = 0
    reason_counts: Counter = field(default_factory=Counter)

    @property
    def denominator(self) -> int:
        return self.yes + self.no

    def rate_text(self) -> str:
        if not self.denominator:
            return "0/0 (—)"
        return f"{self.yes}/{self.denominator} ({self.yes / self.denominator * 100:.0f}%)"


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "cp936"):
        try:
            with path.open("r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                return list(reader), list(reader.fieldnames or [])
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"unable to decode CSV: {path}")


def resolve_latest_input(path: Path) -> Path:
    if path.name == "latest-run.json" and path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        base = path.parent.parent if path.parent.name == "reports" else Path.cwd()
        run_dir = base / data["dir"]
        return run_dir / data.get("backfill_csv", "回填结果.csv")
    return path


def normalize_value(value: object) -> str:
    raw = str(value or "").strip()
    cleaned = raw.replace("（人工复核）", "").replace("(人工复核)", "").strip()
    lowered = cleaned.lower()
    if lowered in POSITIVE or cleaned in POSITIVE:
        return "是"
    if lowered in NEGATIVE or cleaned in NEGATIVE:
        return "否"
    if lowered in PENDING or cleaned in PENDING:
        return "待确认" if cleaned else ""
    return cleaned


def first_value(row: dict[str, str], names: Iterable[str]) -> str:
    for name in names:
        if name in row and str(row.get(name) or "").strip():
            return str(row.get(name) or "").strip()
    return ""


def first_existing(names: Iterable[str], header: Iterable[str]) -> str:
    header_set = set(header)
    return next((name for name in names if name in header_set), "")


def derive_kb_correct(row: dict[str, str]) -> str:
    expected = normalize_value(row.get("是否存在知识库"))
    actual = normalize_value(row.get("知识库是否命中（日志）"))
    if expected in ("是", "否") and actual in ("是", "否"):
        return "是" if expected == actual else "否"
    return ""


def metric_values(row: dict[str, str], metric: dict) -> tuple[str, str, bool]:
    manual_value = normalize_value(first_value(row, metric["manual"]))
    auto_value = normalize_value(first_value(row, metric["auto"]))
    if manual_value:
        return manual_value, auto_value, True
    if auto_value:
        return auto_value, auto_value, False
    if metric["key"] == "kb_hit":
        derived = derive_kb_correct(row)
        return derived, derived, False
    return "", "", False


def split_reasons(reason_text: str) -> list[str]:
    return [item.strip() for item in reason_text.split(";") if item.strip()]


def has_any(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def classify_issue(row: dict[str, str], metric: dict, final_value: str) -> str:
    question = first_value(row, QUESTION_COLUMNS)
    reply = first_value(row, REPLY_COLUMNS)
    q = question.lower()
    r = reply.lower()
    expected_handoff = normalize_value(row.get("转人工预期"))
    actual_handoff = normalize_value(row.get("日志转人工"))
    expected_kb = normalize_value(row.get("是否存在知识库"))
    actual_kb = normalize_value(row.get("知识库是否命中（日志）"))

    if not reply:
        return "无实际回复，需补充日志或重新执行"
    if final_value in ("待确认", "待复核", "待判定", "待验证"):
        return "自动判定口径不足，需人工复核"
    if metric["key"] == "handoff":
        if expected_handoff == "是" and actual_handoff == "否":
            return "应转人工但未触发转人工"
        if expected_handoff == "否" and actual_handoff == "是":
            return "非必要转人工或意图规则过宽"
        if has_any(r, HUMAN_UNAVAILABLE):
            return "转人工/人工兜底话术不充分"
    if metric["key"] == "kb_hit":
        if expected_kb == "是" and actual_kb == "否":
            return "知识库应命中但日志未命中"
        if expected_kb == "否" and actual_kb == "是":
            return "无关问题被知识库低相似度命中"
    if metric["key"] == "tag":
        return "客户标签或预订意图误判"
    if has_any(r, HUMAN_UNAVAILABLE):
        return "回复为人工暂不可用，未充分回应当前问题"
    if has_any(q, UNRELATED_KEYWORDS) and has_any(r, HOT70_KEYWORDS):
        return "无关问题回复强行拉回Hot70/产品业务"
    if has_any(r, GENERIC_FALLBACKS):
        return "泛化追问或兜底回复，未处理当前问题"
    if metric["key"] == "answer":
        return "关键事实未命中或回复不完整"
    if metric["key"] == "semantic":
        return "回复不贴题或语义充分性不足"
    return "需人工复核归因"


def safe_cell(value: object, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = text.replace("|", "\\|")
    return text[: limit - 1] + "…" if len(text) > limit else text


def analyze(rows: list[dict[str, str]], header: list[str]) -> tuple[dict[str, MetricStats], list[dict[str, str]]]:
    stats = {metric["key"]: MetricStats(metric["key"], metric["label"], metric["target"]) for metric in METRICS}
    review_items: list[dict[str, str]] = []

    for index, row in enumerate(rows, start=1):
        for metric in METRICS:
            final_value, raw_value, used_manual = metric_values(row, metric)
            stat = stats[metric["key"]]
            stat.total += 1
            if used_manual:
                stat.manual_total += 1
            if raw_value == "是":
                stat.raw_yes += 1
            elif raw_value == "否":
                stat.raw_no += 1
            elif raw_value:
                stat.raw_pending += 1

            if final_value == "是":
                stat.yes += 1
                continue
            if final_value == "否":
                stat.no += 1
            elif final_value:
                stat.pending += 1
            else:
                stat.blank += 1

            if final_value and final_value != "是":
                reason = classify_issue(row, metric, final_value)
                stat.reason_counts[reason] += 1
                review_items.append(
                    {
                        "行号": str(index),
                        "用例ID": first_value(row, ID_COLUMNS),
                        "执行阶段": first_value(row, PHASE_COLUMNS),
                        "指标": metric["label"],
                        "判定": final_value,
                        "自动判定": raw_value,
                        "使用人工复核": "是" if used_manual else "否",
                        "归因建议": reason,
                        "测试数据": first_value(row, QUESTION_COLUMNS),
                        "实际回复内容": first_value(row, REPLY_COLUMNS),
                    }
                )

    return stats, review_items


def make_markdown(input_path: Path, rows: list[dict[str, str]], stats: dict[str, MetricStats], review_items: list[dict[str, str]]) -> str:
    lines = [
        "# 回填表格指标分析",
        "",
        f"- 输入文件: `{input_path}`",
        f"- 样本量: {len(rows)}",
        "- 口径: 人工复核字段优先；无人工复核时使用 LLM/日志字段；`待确认/待复核/空` 不进入通过率分母。",
        "",
        "## 核心验收指标对比",
        "",
        "| 指标 | 验收标准 | 复核优先结果 | 自动原始结果 | 待复核/空 | 说明 |",
        "|---|---:|---:|---:|---:|---|",
    ]

    for metric in METRICS:
        stat = stats[metric["key"]]
        raw_den = stat.raw_yes + stat.raw_no
        raw_rate = f"{stat.raw_yes}/{raw_den} ({stat.raw_yes / raw_den * 100:.0f}%)" if raw_den else "0/0 (—)"
        top_reasons = "；".join(f"{reason}：{count}条" for reason, count in stat.reason_counts.most_common(3))
        if not top_reasons:
            top_reasons = "未发现需复核的否/待确认数据"
        pending_text = f"待确认 {stat.pending} / 空 {stat.blank}"
        manual_text = f"人工复核覆盖 {stat.manual_total} 条。{top_reasons}"
        lines.append(
            f"| {stat.label} | {stat.target} | {stat.rate_text()} | {raw_rate} | {pending_text} | {manual_text} |"
        )

    lines.extend(["", "## 否/待确认归因汇总", ""])
    for metric in METRICS:
        stat = stats[metric["key"]]
        lines.append(f"### {stat.label}")
        if not stat.reason_counts:
            lines.append("- 无")
            continue
        for reason, count in stat.reason_counts.most_common():
            lines.append(f"- {reason}：{count} 条")

    lines.extend(
        [
            "",
            "## 复核明细 Top 50",
            "",
            "| 行号 | 用例ID | 指标 | 判定 | 归因建议 | 测试数据 | 实际回复内容 |",
            "|---:|---|---|---|---|---|---|",
        ]
    )
    for item in review_items[:50]:
        lines.append(
            "| {row} | {case} | {metric} | {value} | {reason} | {question} | {reply} |".format(
                row=safe_cell(item["行号"], 20),
                case=safe_cell(item["用例ID"], 40),
                metric=safe_cell(item["指标"], 40),
                value=safe_cell(item["判定"], 20),
                reason=safe_cell(item["归因建议"], 80),
                question=safe_cell(item["测试数据"], 120),
                reply=safe_cell(item["实际回复内容"], 140),
            )
        )

    return "\n".join(lines) + "\n"


def write_review_csv(path: Path, review_items: list[dict[str, str]]) -> None:
    fields = [
        "行号",
        "用例ID",
        "执行阶段",
        "指标",
        "判定",
        "自动判定",
        "使用人工复核",
        "归因建议",
        "测试数据",
        "实际回复内容",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(review_items)


def write_json(path: Path, input_path: Path, rows: list[dict[str, str]], stats: dict[str, MetricStats], review_items: list[dict[str, str]]) -> None:
    payload = {
        "input": str(input_path),
        "sample_size": len(rows),
        "metrics": {
            key: {
                "label": stat.label,
                "target": stat.target,
                "yes": stat.yes,
                "no": stat.no,
                "pending": stat.pending,
                "blank": stat.blank,
                "denominator": stat.denominator,
                "rate": (stat.yes / stat.denominator) if stat.denominator else None,
                "manual_total": stat.manual_total,
                "raw_yes": stat.raw_yes,
                "raw_no": stat.raw_no,
                "raw_pending": stat.raw_pending,
                "reasons": dict(stat.reason_counts),
            }
            for key, stat in stats.items()
        },
        "review_items_count": len(review_items),
        "review_items_preview": review_items[:50],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Hot70 backfill CSV with manual review priority.")
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help="Backfill CSV path, or profiles/hot70/reports/latest-run.json. Defaults to latest run.",
    )
    parser.add_argument(
        "--out-dir",
        default="",
        help="Output directory. Defaults to <input directory>/analysis.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = resolve_latest_input(Path(args.input))
    rows, header = read_csv(input_path)
    out_dir = Path(args.out_dir) if args.out_dir else input_path.parent / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    stats, review_items = analyze(rows, header)
    (out_dir / "analysis.md").write_text(make_markdown(input_path, rows, stats, review_items), encoding="utf-8")
    write_json(out_dir / "analysis.json", input_path, rows, stats, review_items)
    write_review_csv(out_dir / "review_items.csv", review_items)

    print(f"input: {input_path}")
    print(f"rows: {len(rows)}")
    print(f"review_items: {len(review_items)}")
    print(f"analysis_md: {out_dir / 'analysis.md'}")
    print(f"analysis_json: {out_dir / 'analysis.json'}")
    print(f"review_csv: {out_dir / 'review_items.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
