"""Write backfill CSV, summary.json, and report.md for one eval run."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .scoring import AFTER_HOURS_HANDOFF_REASON, score_handoff

DEFAULT_PROFILE_ROOT = Path(__file__).resolve().parents[1] / "profiles" / "hot70"
OUTPUT_FIELDS = [
    "用例ID",
    "用例名称",
    "执行步骤",
    "预期结果",
    "转人工触发条件",
    "测试目标",
    "前置条件",
    "测试数据",
    "测试数据（英文提问）",
    "执行阶段",
    "是否使用新会话",
    "实际回复内容（英文）",
    "是否存在知识库",
    "知识库是否命中（日志）",
    "知识库命中（人工复核）",
    "日志客户标签",
    "LLM推测预期标签",
    "LLM判定客户标签是否准确",
    "客户标签准确（人工复核）",
    "转人工预期",
    "日志转人工",
    "转人工是否准确",
    "转人工准确（人工复核）",
    "语义是否合理（LLM）",
    "回复是否准确（LLM）",
    "回复准确（人工复核）",
    "服务端真实耗时",
    "接口响应时长",
    "备注",
]


def _yn(value: bool | None) -> str:
    return "" if value is None else ("是" if value else "否")


def _set_col(row: dict, names: tuple[str, ...], value: object) -> None:
    for name in names:
        if name in row:
            row[name] = value
            return
    row[names[0]] = value


TAG_VALUES = ("未识别", "未预定低意向", "未预定高意向", "已预定未提机", "已提机")


def _norm_tag(value: object) -> str | None:
    tag = str(value or "").strip().replace("预订", "预定").replace("无法判断", "未识别")
    if not tag or tag in ("None", "NULL", "NA", "N/A"):
        return None
    return tag if tag in TAG_VALUES else None


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _rule_expected_tag(turn_result: dict) -> tuple[str, str]:
    raw = turn_result.get("raw") or {}
    messages = turn_result.get("user_context") or [turn_result.get("query", "")]
    text = " ".join(
        str(item or "")
        for item in [*messages, raw.get("用例名称"), raw.get("测试目标"), raw.get("备注")]
    )
    lowered = text.lower()

    picked_up_keywords = (
        "已提机",
        "已经提机",
        "拿到手机",
        "已拿到",
        "已购买",
        "已激活",
        "确认成交",
        "picked up",
        "collected",
        "got the phone",
        "bought",
        "purchased",
        "activated",
    )
    reserved_keywords = (
        "已预定",
        "已预订",
        "预定成功",
        "预订成功",
        "已经预定",
        "已经预订",
        "收到确认码",
        "收到确认短信",
        "paid deposit",
        "paid bdt 5,000",
        "paid bdt 5000",
        "pre-ordered",
        "preordered",
        "booking confirmed",
        "reservation confirmed",
        "confirmation code",
    )
    high_intent_keywords = (
        "价格",
        "多少钱",
        "报价",
        "规格",
        "配置",
        "参数",
        "购买方式",
        "在哪里买",
        "怎么买",
        "如何购买",
        "分期",
        "付款方式",
        "如何预定",
        "如何预订",
        "怎么预定",
        "怎么预订",
        "预定流程",
        "预订流程",
        "订金",
        "门店",
        "库存",
        "提机",
        "price",
        "spec",
        "configuration",
        "buy",
        "purchase",
        "installment",
        "payment",
        "how to pre-order",
        "how to preorder",
        "pre-order process",
        "preorder process",
        "deposit",
        "store",
        "stock",
        "availability",
        "pickup",
    )
    low_intent_keywords = (
        "活动时间",
        "什么时候开始",
        "什么时候结束",
        "抽奖",
        "中奖",
        "奖品",
        "礼品",
        "优惠",
        "福利",
        "官方",
        "官方身份",
        "真假",
        "campaign period",
        "activity time",
        "when does",
        "lucky draw",
        "lottery",
        "winner",
        "prize",
        "gift",
        "benefit",
        "discount",
        "promotion",
        "official",
    )
    unrecognized_keywords = (
        "招聘",
        "简历",
        "工资",
        "辱骂",
        "天气",
        "假设",
        "闲聊",
        "job",
        "resume",
        "salary",
        "weather",
        "hypothetical",
        "insult",
    )

    if _has_any(lowered, picked_up_keywords):
        return "已提机", "机器人标签规则：明确已提机、已购买、已激活或成交。"
    if _has_any(lowered, reserved_keywords):
        return "已预定未提机", "机器人标签规则：明确已预订、收到确认码或预订成功，但未表达已提机。"
    if _has_any(lowered, high_intent_keywords):
        return "未预定高意向", "机器人标签规则：咨询价格、配置、购买方式、分期、预订、门店或库存。"
    if _has_any(lowered, low_intent_keywords):
        return "未预定低意向", "机器人标签规则：只问活动时间、抽奖、礼品、普通优惠或官方身份。"
    if _has_any(lowered, unrecognized_keywords):
        return "未识别", "机器人标签规则：闲聊、假设问题、信息不足、招聘或辱骂等。"
    return "未识别", "机器人标签规则：缺少可判定购买或预订意向的关键信息。"


def _infer_expected_tag(turn_result: dict) -> tuple[str | None, str | None]:
    """Best-effort expected tag for backfill when LLM tag judge was not run."""
    rule_tag, rule_reason = _rule_expected_tag(turn_result)
    if rule_tag != "未识别":
        return rule_tag, rule_reason

    existing = _norm_tag(turn_result.get("expect", {}).get("expected_tag"))
    if existing and existing not in ("未预定高意向", "无法判断"):
        return existing, turn_result.get("scores", {}).get("expected_tag_reason")

    return rule_tag, rule_reason


def _ensure_expected_tag(turn: dict) -> None:
    expected_tag, reason = _infer_expected_tag(turn)
    turn.setdefault("expect", {})["expected_tag"] = expected_tag
    if reason:
        turn.setdefault("scores", {})["expected_tag_reason"] = reason
    actual_tag = _norm_tag((turn.get("signals") or {}).get("tag"))
    turn.setdefault("scores", {})["tag_correct"] = None if expected_tag is None else actual_tag == expected_tag


def _backfill_row(raw: dict, turn_result: dict) -> dict:
    _ensure_expected_tag(turn_result)
    row = dict(raw)
    signals = turn_result["signals"]
    scores = turn_result["scores"]
    row["知识库是否命中（日志）"] = _yn(signals["kb_hit"])
    row.setdefault("知识库命中（人工复核）", "")
    row["日志客户标签"] = signals["tag"] or ""
    row["LLM推测预期标签"] = turn_result["expect"].get("expected_tag") or ""
    row["LLM判定客户标签是否准确"] = (
        "待确认" if scores["tag_correct"] is None and signals["tag"] else _yn(scores["tag_correct"])
    )
    row.setdefault("客户标签准确（人工复核）", "")
    row["日志转人工"] = _yn(signals["handoff"])
    row["转人工是否准确"] = _yn(scores["handoff_correct"])
    row.setdefault("转人工准确（人工复核）", "")
    row["实际回复内容（英文）"] = turn_result["reply"] or ""
    semantic = scores["semantic_ok"]
    row["语义是否合理（LLM）"] = "待复核" if semantic in (None, "待复核") else _yn(semantic)
    row["回复是否准确（LLM）"] = "待确认" if scores["answer_correct"] is None else _yn(scores["answer_correct"])
    row.setdefault("回复准确（人工复核）", "")
    row["服务端真实耗时"] = "" if signals["latency_ms"] is None else signals["latency_ms"]
    row["接口响应时长"] = "" if turn_result.get("api_elapsed_ms") is None else turn_result["api_elapsed_ms"]

    note = f"[{turn_result['verdict']}]"
    if turn_result["expect"].get("expected_tag"):
        note += f" 期望标签={turn_result['expect']['expected_tag']}"
    if scores.get("expected_tag_reason"):
        note += f" 标签理由={scores['expected_tag_reason']}"
    if signals.get("tag_source"):
        note += f" tag_source={signals['tag_source']}"
    if scores.get("handoff_reason") == AFTER_HOURS_HANDOFF_REASON:
        note += " 转人工兜底合理：客服非工作时间话术，日志未转人工但按合理处理"
    if scores["answer_keywords"]:
        note += f" 事实关键词命中 {scores['answer_matched']}/{len(scores['answer_keywords'])}"
    if scores["kb_hit_correct"] is None and not turn_result["expect"].get("handoff") and signals.get("handoff"):
        note += " KB跳过：实际已转人工"
    if signals.get("step_note"):
        note += f" {signals['step_note']}"
    if turn_result.get("error"):
        note += f" error={turn_result['error']}"
    row["备注"] = (row.get("备注") or "") and (row["备注"] + " | " + note) or note
    return row


def _rate(hit: int, total: int) -> str:
    return f"{hit}/{total} ({hit / total * 100:.0f}%)" if total else "0/0 (—)"


def _write_latest_pointer(reports_dir: Path, run_id: str, project_root: Path) -> None:
    pointer = {
        "run_id": run_id,
        "dir": str((reports_dir / "runs" / run_id).relative_to(project_root)).replace("\\", "/"),
        "report_md": "report.md",
        "summary_json": "summary.json",
        "backfill_csv": "回填结果.csv",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    (reports_dir / "latest-run.json").write_text(
        json.dumps(pointer, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_reports(
    run_id: str,
    fieldnames: list[str],
    turns: list[dict],
    llm_used: bool,
    llm_tag_used: bool = False,
    project_root: str | Path = DEFAULT_PROFILE_ROOT,
) -> tuple[str, dict]:
    project_root = Path(project_root)
    reports_dir = project_root / "reports"
    out_dir = reports_dir / "runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    output_fieldnames = list(OUTPUT_FIELDS)
    for turn in turns:
        _ensure_expected_tag(turn)
        scores = turn.setdefault("scores", {})
        signals = turn.get("signals") or {}
        expect = turn.get("expect") or {}
        handoff_correct, handoff_reason = score_handoff(
            bool(expect.get("handoff")),
            bool(signals.get("handoff")),
            turn.get("reply"),
        )
        scores["handoff_correct"] = handoff_correct
        scores["handoff_reason"] = handoff_reason
        checks = [
            scores.get("handoff_correct"),
            scores.get("kb_hit_correct"),
            scores.get("answer_correct"),
            scores.get("tag_correct"),
        ]
        applicable = [check for check in checks if check is not None]
        if applicable and turn.get("verdict") not in ("NO_REPLY", "SEND_ERROR", "SETUP_ERROR"):
            turn["verdict"] = "PASS" if all(applicable) else "FAIL"

    csv_path = out_dir / "回填结果.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=output_fieldnames, extrasaction="ignore")
        writer.writeheader()
        for turn in turns:
            writer.writerow(_backfill_row(turn["raw"], turn))

    dims = ["kb_hit_correct", "handoff_correct", "tag_correct", "answer_correct", "semantic_ok"]
    dim_label = {
        "kb_hit_correct": "知识库命中正确",
        "handoff_correct": "转人工正确",
        "tag_correct": "客户标签正确",
        "answer_correct": "事实关键词命中正确",
        "semantic_ok": "语义合理",
    }
    overall = {dim: [0, 0] for dim in dims}
    by_phase = defaultdict(lambda: {dim: [0, 0] for dim in dims})
    verdicts = defaultdict(int)

    for turn in turns:
        verdicts[turn["verdict"]] += 1
        phase = turn["phase"] or "未分级"
        for dim in dims:
            value = turn["scores"][dim]
            if value in (None, "待复核"):
                continue
            ok = 1 if value is True else 0
            overall[dim][0] += ok
            overall[dim][1] += 1
            by_phase[phase][dim][0] += ok
            by_phase[phase][dim][1] += 1

    summary = {
        "run_id": run_id,
        "llm_judge": llm_used,
        "llm_tag_judge": llm_tag_used,
        "total_turns": len(turns),
        "verdicts": dict(verdicts),
        "overall": {
            dim_label[dim]: {
                "hit": overall[dim][0],
                "applicable": overall[dim][1],
                "rate": (overall[dim][0] / overall[dim][1]) if overall[dim][1] else None,
            }
            for dim in dims
        },
        "by_phase": {
            phase: {dim_label[dim]: {"hit": values[dim][0], "applicable": values[dim][1]} for dim in dims}
            for phase, values in by_phase.items()
        },
        "artifacts": {
            "backfill_csv": str(csv_path),
            "summary_json": str(out_dir / "summary.json"),
            "report_md": str(out_dir / "report.md"),
        },
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    markdown = [
        "# 客服机器人知识库指标评估报告\n",
        f"- run_id: `{run_id}`",
        f"- 总轮次: {len(turns)}",
        f"- LLM 语义判定: {'开启' if llm_used else '关闭（语义维度待人工复核）'}",
        f"- LLM 客户标签期望判定: {'开启' if llm_tag_used else '关闭（客户标签维度待确认）'}",
        "- 判定分布: " + ", ".join(f"{key}={value}" for key, value in sorted(verdicts.items())),
        "",
        "## 总体（确定性维度，分母=可判定轮次）\n",
        "说明：KB 命中只统计预期不转人工且实际未转人工的轮次；事实关键词命中不是整体回复准确率。",
        "| 维度 | 通过率 |",
        "|---|---|",
    ]
    for dim in dims:
        if dim == "semantic_ok" and not llm_used:
            markdown.append(f"| {dim_label[dim]} | —（未启用 LLM） |")
        elif dim == "tag_correct" and not llm_tag_used:
            markdown.append(f"| {dim_label[dim]} | —（未启用 LLM 标签判定） |")
        else:
            markdown.append(f"| {dim_label[dim]} | {_rate(*overall[dim])} |")

    markdown.extend(
        [
            "\n## 按执行阶段\n",
            "| 阶段 | 知识库命中 | 转人工 | 客户标签 | 事实关键词 |",
            "|---|---|---|---|---|",
        ]
    )
    for phase in sorted(by_phase):
        values = by_phase[phase]
        markdown.append(
            f"| {phase} | {_rate(*values['kb_hit_correct'])} | {_rate(*values['handoff_correct'])} | "
            f"{_rate(*values['tag_correct'])} | {_rate(*values['answer_correct'])} |"
        )

    failures = [turn for turn in turns if turn["verdict"] != "PASS"]
    markdown.append(f"\n## 失败明细（{len(failures)}，Top 30）\n")
    for turn in failures[:30]:
        scores = turn["scores"]
        signals = turn["signals"]
        reasons = []
        if scores["handoff_correct"] is False:
            reasons.append(f"转人工 期望={_yn(turn['expect']['handoff'])}/实际={_yn(signals['handoff'])}")
        if scores["answer_correct"] is False:
            reasons.append(f"事实关键词命中 {scores['answer_matched']}/{len(scores['answer_keywords'])}")
        if scores["kb_hit_correct"] is False:
            reasons.append("KB未命中")
        if scores["tag_correct"] is False:
            reasons.append(f"客户标签 期望={turn['expect'].get('expected_tag') or ''}/实际={signals.get('tag') or ''}")
        if turn["verdict"] == "NO_REPLY":
            reasons.append("无回复")
        if turn.get("error"):
            reasons.append(turn["error"])
        markdown.append(f"- **{turn['case_id']}** {turn['query'][:60]!r} → {'; '.join(reasons) or turn['verdict']}")
        markdown.append(f"  - 回复: {(turn['reply'] or '')[:140]!r}")

    (out_dir / "report.md").write_text("\n".join(markdown), encoding="utf-8")
    _write_latest_pointer(reports_dir, run_id, project_root)
    return str(out_dir), summary


def load_results(path: str | Path) -> list[dict]:
    results_path = Path(path)
    turns: list[dict] = []
    with results_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                turns.append(json.loads(line))
    return turns


def _fieldnames_from_results(turns: list[dict]) -> list[str]:
    if not turns:
        return []
    raw = turns[0].get("raw") or {}
    return list(raw.keys())


def write_reports_from_results(
    results_path: str | Path,
    profile_root: str | Path = DEFAULT_PROFILE_ROOT,
    llm_used: bool = False,
    llm_tag_used: bool = False,
) -> tuple[str, dict]:
    turns = load_results(results_path)
    if not turns:
        raise RuntimeError(f"empty results file: {results_path}")
    run_id = turns[0].get("run_id") or Path(results_path).stem
    return write_reports(
        str(run_id),
        _fieldnames_from_results(turns),
        turns,
        llm_used,
        llm_tag_used,
        project_root=profile_root,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate CSV / JSON / Markdown reports from results.jsonl.")
    parser.add_argument("--results", required=True)
    parser.add_argument("--profile-root", default=str(DEFAULT_PROFILE_ROOT))
    parser.add_argument("--llm-judge", action="store_true")
    parser.add_argument("--llm-tag-judge", action="store_true")
    args = parser.parse_args(argv)
    out_dir, _summary = write_reports_from_results(
        args.results,
        profile_root=args.profile_root,
        llm_used=args.llm_judge,
        llm_tag_used=args.llm_tag_judge,
    )
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
