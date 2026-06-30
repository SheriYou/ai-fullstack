#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PRD §7.3 + 测试计划 §8 指标 + L2 门禁 — 从 L2 结果聚合。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Verdict = Literal["PASS", "FAIL", "INSUFFICIENT", "NOT_RUN", "BLOCKED", "PARTIAL"]

PRD_73_METRICS = [
    {"key": "msg_delivery", "name": "消息收发成功率", "definition": "用户消息接入链路成功比例", "target": "100%", "target_num": 100.0, "min_sample": 50, "case_id": "TC-L4-001"},
    {"key": "reply_accuracy", "name": "回复准确率", "definition": "知识库关键事实匹配比例", "target": "≥85%", "target_num": 85.0, "min_sample": 50, "case_id": "TC-L4-002"},
    {"key": "tag_write", "name": "标签写入成功率", "definition": "智齿客户标签写入比例", "target": "≥95%", "target_num": 95.0, "min_sample": 20, "case_id": "TC-M9-008"},
    {"key": "handoff_accuracy", "name": "转人工准确率", "definition": "应转人工场景触发 LOCAL handoff 比例", "target": "≥90%", "target_num": 90.0, "min_sample": 50, "case_id": "TC-L4-003"},
    {"key": "avg_response_time", "name": "平均响应时间", "definition": "inbound 到首条 outbound 平均耗时", "target": "≤10 秒", "target_num": 10.0, "min_sample": 30, "case_id": "TC-L4-005"},
]

PLAN_8_EXTRA = [
    {"key": "intent_routing", "name": "意图路由准确率", "definition": "task_type 路由+handoff 动作正确率", "target": "≥90%", "target_num": 90.0, "min_sample": 100, "case_id": "TC-L4-INT"},
]

L2_GATES = [
    {"key": "L2-G1", "name": "L2 预检（进 L3 全量前）", "target": "≥60%", "target_num": 60.0, "scope": "intent", "field": "routing_pass"},
    {"key": "L2-G2", "name": "L2 预检（进 L4 签字前）", "target": "≥60%", "target_num": 60.0, "scope": "kb", "field": "business_result"},
    {"key": "L2-G3", "name": "L2 预检（handoff 必转）", "target": "≥70%", "target_num": 70.0, "scope": "handoff_must", "field": "business_result"},
]

REPLY_CORPUS = frozenset({"kb", "adversarial"})
INTENT_CORPUS = frozenset({"intent"})


@dataclass
class MetricResult:
    key: str
    name: str
    definition: str
    target: str
    case_id: str
    sample_n: int
    pass_n: int
    rate: float | None
    rate_display: str
    verdict: Verdict
    notes: str
    source: str = ""


@dataclass
class GateResult:
    key: str
    name: str
    target: str
    sample_n: int
    pass_n: int
    rate: float | None
    verdict: Verdict
    notes: str


def _pct(num: float) -> str:
    return f"{num:.1f}%"


def _verdict_ge(rate: float | None, target: float, sample: int, min_sample: int) -> Verdict:
    if rate is None:
        return "NOT_RUN"
    if sample < min_sample:
        return "INSUFFICIENT"
    return "PASS" if rate >= target else "FAIL"


def _verdict_le(value: float | None, target: float, sample: int, min_sample: int) -> Verdict:
    if value is None:
        return "NOT_RUN"
    if sample < min_sample:
        return "INSUFFICIENT"
    return "PASS" if value <= target else "FAIL"


def _evaluated(corpus: list[dict]) -> list[dict]:
    return [r for r in corpus if r.get("status") != "SKIP" and r.get("execution_status") != "SKIP"]


def _rate(rows: list[dict], field: str, pass_val: str = "PASS") -> tuple[int, int, float | None]:
    n = len(rows)
    if not n:
        return 0, 0, None
    p = sum(1 for r in rows if r.get(field) == pass_val)
    return p, n, p / n * 100


def compute_prd_73_metrics(smoke: list, corpus: list[dict]) -> list[MetricResult]:
    results: list[MetricResult] = []
    auto_rows = _evaluated(corpus)
    p, n, rate = _rate(auto_rows, "automation_result")
    m0 = PRD_73_METRICS[0]
    results.append(MetricResult(m0["key"], m0["name"], m0["definition"], m0["target"], m0["case_id"], n, p, rate, _pct(rate) if rate else "—", _verdict_ge(rate, m0["target_num"], n, m0["min_sample"]), "L2 webhook 接入"))

    kb_rows = [r for r in _evaluated(corpus) if r.get("corpus") == "kb"]
    p, n, rate = _rate(kb_rows, "business_result")
    m1 = PRD_73_METRICS[1]
    results.append(MetricResult(m1["key"], m1["name"], m1["definition"], m1["target"], m1["case_id"], n, p, rate, _pct(rate) if rate else "—", _verdict_ge(rate, m1["target_num"], n, m1["min_sample"]), "corpus-kb 关键事实"))

    m2 = PRD_73_METRICS[2]
    results.append(MetricResult(m2["key"], m2["name"], m2["definition"], m2["target"], m2["case_id"], 0, 0, None, "—", "BLOCKED", "M9 Blocked"))

    ho_must = [r for r in _evaluated(corpus) if r.get("corpus") == "handoff" and (r.get("should_handoff") or "").lower() == "true"]
    ho_rows = ho_must if ho_must else [r for r in _evaluated(corpus) if r.get("corpus") == "handoff"]
    p, n, rate = _rate(ho_rows, "business_result")
    m3 = PRD_73_METRICS[3]
    results.append(MetricResult(m3["key"], m3["name"], m3["definition"], m3["target"], m3["case_id"], n, p, rate, _pct(rate) if rate else "—", _verdict_ge(rate, m3["target_num"], n, m3["min_sample"]), "corpus-handoff（含 conditional）"))

    resp_rows = [r for r in _evaluated(corpus) if r.get("response_ms") not in ("", None)]
    vals = [float(r["response_ms"]) / 1000.0 for r in resp_rows if str(r.get("response_ms", "")).isdigit()]
    avg_s = sum(vals) / len(vals) if vals else None
    m4 = PRD_73_METRICS[4]
    under = sum(1 for v in vals if v <= m4["target_num"]) if vals else 0
    results.append(MetricResult(
        m4["key"], m4["name"], m4["definition"], m4["target"], m4["case_id"],
        len(vals), under, avg_s, f"{avg_s:.2f}s" if avg_s is not None else "—",
        _verdict_le(avg_s, m4["target_num"], len(vals), m4["min_sample"]),
        f"messages timestamp 样本 {len(vals)} 条",
    ))
    return results


def compute_plan8_metrics(corpus: list[dict]) -> list[MetricResult]:
    intent_rows = [r for r in _evaluated(corpus) if r.get("corpus") in INTENT_CORPUS]
    p, n, rate = _rate(intent_rows, "routing_pass")
    m = PLAN_8_EXTRA[0]
    return [MetricResult(
        m["key"], m["name"], m["definition"], m["target"], m["case_id"],
        n, p, rate, _pct(rate) if rate else "—",
        _verdict_ge(rate, m["target_num"], n, m["min_sample"]),
        "corpus-intent 仅路由，不断言 facts",
    )]


def compute_l2_gates(corpus: list[dict]) -> list[GateResult]:
    gates: list[GateResult] = []
    for g in L2_GATES:
        if g["scope"] == "intent":
            rows = [r for r in _evaluated(corpus) if r.get("corpus") == "intent"]
            p, n, rate = _rate(rows, g["field"])
        elif g["scope"] == "kb":
            rows = [r for r in _evaluated(corpus) if r.get("corpus") == "kb"]
            p, n, rate = _rate(rows, g["field"])
        elif g["scope"] == "handoff_must":
            rows = [r for r in _evaluated(corpus) if r.get("corpus") == "handoff" and (r.get("should_handoff") or "").lower() == "true"]
            p, n, rate = _rate(rows, g["field"])
        else:
            rows, p, n, rate = [], 0, 0, None
        gates.append(GateResult(
            g["key"], g["name"], g["target"], n, p, rate,
            _verdict_ge(rate, g["target_num"], n, 1 if g["scope"] == "handoff_must" else 10),
            f"{g['scope']} {p}/{n}",
        ))
    return gates


def compute_fail_summary(corpus: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in _evaluated(corpus):
        if r.get("business_result") != "FAIL":
            continue
        fc = r.get("fail_class") or "DEV_BUG"
        out[fc] = out.get(fc, 0) + 1
    return out


def compute_all_metrics(smoke: list, corpus: list[dict]) -> dict:
    prd = compute_prd_73_metrics(smoke, corpus)
    plan8 = compute_plan8_metrics(corpus)
    gates = compute_l2_gates(corpus)
    fail_summary = compute_fail_summary(corpus)
    return {"prd_7_3": prd, "plan_8": plan8, "l2_gates": gates, "fail_summary": fail_summary}


def format_metrics_markdown(block: dict) -> list[str]:
    lines = format_prd_73_section(block["prd_7_3"])
    lines += format_plan8_section(block["plan_8"])
    lines += format_l2_gates_markdown(block["l2_gates"])
    lines += format_fail_summary_markdown(block["fail_summary"])
    return lines


def format_prd_73_section(metrics: list[MetricResult]) -> list[str]:
    lines = [
        "## PRD §7.3 核心验收指标",
        "",
        "> L2 代理指标；人工回传/智齿 EXT 见 L3。",
        "",
        "| 指标 | 目标 | 样本 | 实测 | 判定 | 用例 |",
        "|------|------|------|------|------|------|",
    ]
    for m in metrics:
        measured = m.rate_display
        if m.sample_n and m.rate is not None and m.key != "avg_response_time":
            measured = f"{m.rate_display} ({m.pass_n}/{m.sample_n})"
        elif m.key == "avg_response_time" and m.sample_n:
            measured = f"{m.rate_display} ({m.pass_n}/{m.sample_n}≤10s)"
        lines.append(f"| {m.name} | {m.target} | {m.sample_n or '—'} | {measured} | **{m.verdict}** | {m.case_id} |")
    lines.append("")
    return lines


def format_plan8_section(metrics: list[MetricResult]) -> list[str]:
    lines = [
        "## 测试计划 §8 补充指标（L2 自动化）",
        "",
        "| 指标 | 目标 | 样本 | 实测 | 判定 |",
        "|------|------|------|------|------|",
    ]
    for m in metrics:
        measured = f"{m.rate_display} ({m.pass_n}/{m.sample_n})" if m.sample_n and m.rate is not None else m.rate_display
        lines.append(f"| {m.name} | {m.target} | {m.sample_n} | {measured} | **{m.verdict}** |")
    lines.append("")
    return lines


def format_l2_gates_markdown(gates: list[GateResult]) -> list[str]:
    lines = [
        "## L2 门禁（进 L3 / L4 前）",
        "",
        "| 门禁 | 条件 | 样本 | 实测 | 判定 |",
        "|------|------|------|------|------|",
    ]
    for g in gates:
        measured = f"{_pct(g.rate)} ({g.pass_n}/{g.sample_n})" if g.rate is not None else "—"
        lines.append(f"| {g.key} | {g.name} {g.target} | {g.sample_n} | {measured} | **{g.verdict}** |")
    lines.append("")
    return lines


def format_fail_summary_markdown(summary: dict[str, int]) -> list[str]:
    if not summary:
        return []
    lines = [
        "## L2 Fail 分类汇总",
        "",
        "| 分类 | 数量 | 说明 |",
        "|------|------|------|",
    ]
    desc = {
        "DEV_BUG": "实现/模型/RAG 问题",
        "SPEC_DEFECT": "FAQ/PRD 口径矛盾",
        "HARNESS": "脚本/断言/等待问题",
        "ENV": "环境/RAG/登录不可用",
    }
    for k, v in sorted(summary.items(), key=lambda x: -x[1]):
        lines.append(f"| {k} | {v} | {desc.get(k, '')} |")
    lines.append("")
    return lines


# 兼容旧名
format_prd_73_markdown = format_prd_73_section


def metrics_to_summary_dict(block: dict) -> dict:
    def _m(m: MetricResult) -> dict:
        return {"name": m.name, "target": m.target, "case_id": m.case_id, "sample_n": m.sample_n,
                "pass_n": m.pass_n, "rate": m.rate, "verdict": m.verdict, "notes": m.notes}

    return {
        "prd_7_3": {m.key: _m(m) for m in block["prd_7_3"]},
        "plan_8": {m.key: _m(m) for m in block["plan_8"]},
        "l2_gates": {g.key: {"name": g.name, "target": g.target, "sample_n": g.sample_n, "pass_n": g.pass_n,
                             "rate": g.rate, "verdict": g.verdict, "notes": g.notes} for g in block["l2_gates"]},
        "fail_summary": block["fail_summary"],
    }


def l4_case_notes(block: dict) -> dict[str, str]:
    metrics = block["prd_7_3"]
    by_case = {m.case_id: m for m in metrics}
    notes: dict[str, str] = {}
    mapping = {"TC-L4-001": "msg_delivery", "TC-L4-002": "reply_accuracy", "TC-L4-003": "handoff_accuracy", "TC-L4-005": "avg_response_time"}
    key_to_metric = {m.key: m for m in metrics}
    for case_id, key in mapping.items():
        m = key_to_metric.get(key)
        if not m:
            continue
        if m.verdict in ("NOT_RUN", "BLOCKED"):
            notes[case_id] = m.notes
        elif m.rate is not None or m.key == "avg_response_time":
            notes[case_id] = f"PRD7.3：{m.rate_display} ({m.pass_n}/{m.sample_n}) → {m.verdict}"
        else:
            notes[case_id] = f"PRD7.3 → {m.verdict}"
    notes["TC-L4-004"] = "人工回复送达率：L3 Web sendManual（M11/M7）"
    notes["TC-L4-006"] = "未命中可追踪率：日志汇总"
    ir = block["plan_8"][0] if block.get("plan_8") else None
    if ir:
        notes["TC-L4-INT"] = f"意图路由：{ir.rate_display} ({ir.pass_n}/{ir.sample_n}) → {ir.verdict}"
    return notes
