#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Formal + L2 结果聚合缺陷清单与简约分析（见 spec/l2-fail-classification.md）。"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from l2_eval_core import classify_fail


@dataclass
class CaseLink:
    case_id: str
    title: str = ""
    module: str = ""
    business_result: str = ""
    fail_point: str = ""
    source: str = ""  # formal / corpus


@dataclass
class BugRecord:
    bug_id: str
    title: str
    severity: str  # P0 / P1
    fail_class: str  # DEV_BUG / ENV / HARNESS / SPEC_DEFECT / MANUAL
    status: str  # OPEN / ENV_BLOCK / DEFER / MANUAL
    related_cases: list[str] = field(default_factory=list)
    case_links: list[CaseLink] = field(default_factory=list)
    sample_n: int = 0
    evidence: str = ""
    analysis: str = ""
    module: str = ""
    source: str = ""  # formal / corpus / mixed


# Formal 失败 → 缺陷主题（按 notes / checks 匹配）
_FORMAL_THEMES: list[dict] = [
    {
        "key": "no_outbound",
        "patterns": (r"no outbound", r"outbound≤.*:fail", r"price_keywords:fail\(empty\)"),
        "title": "FAQ/打招呼场景无机器人 outbound 回复",
        "fail_class": "DEV_BUG",
        "severity": "P0",
        "analysis": "webhook 可达且 session 活跃，但 messages 中无有效 outbound；优先排查 Agent 编排、RAG 回调与 outbound 写入链路。",
    },
    {
        "key": "q02_bot_reply",
        "patterns": (r"no_bot_outbound:fail", r"new_outbound=\d+"),
        "title": "转人工后机器人仍自动回复（Q02）",
        "fail_class": "DEV_BUG",
        "severity": "P0",
        "analysis": "Conversation 已进入 LOCAL handoff，但 follow-up 消息仍触发 bot outbound；需确认 isActiveAgent=0 后 outbound 拦截逻辑。",
    },
    {
        "key": "no_agent",
        "patterns": (r"handoff_assigned", r"local_handoff:ok.*manual_pending"),
        "title": "LOCAL 转人工成功但未分配在线坐席",
        "fail_class": "ENV",
        "severity": "P0",
        "status": "ENV_BLOCK",
        "analysis": "handoffTarget=LOCAL 与 conversationStatus 正确，G1 测试环境无 online 坐席；配置坐席后重跑 003-LOCAL/004。",
    },
    {
        "key": "session_api",
        "patterns": (r"session_traceable:fail", r"task_type:fail"),
        "title": "Session/Conversation API 追溯字段缺失",
        "fail_class": "DEV_BUG",
        "severity": "P1",
        "analysis": "messages 有记录但 session_id 或 task_type 为空，影响 M8 审计与 L4 指标统计。",
    },
    {
        "key": "manual_send",
        "patterns": (r"manual:sendmanual", r"manual:wa送达"),
        "title": "人工回复链路需 L3 补测（sendManual/WA 送达）",
        "fail_class": "MANUAL",
        "severity": "P0",
        "status": "MANUAL",
        "analysis": "自动化无法模拟 Web 坐席发消息；依赖 G1 在线坐席 + 真机/WA 回执。",
    },
]

# L2 语料 → 缺陷主题
_CORPUS_THEMES: list[dict] = [
    {
        "key": "unexpected_handoff",
        "patterns": (r"unexpected local handoff", r"unexpected handoff"),
        "title": "FAQ 场景误触发 LOCAL 转人工",
        "fail_class": "DEV_BUG",
        "severity": "P0",
        "analysis": "应直接 FAQ 回复却进入 handoff；影响回复准确率与 L2-G2。",
    },
    {
        "key": "missing_facts",
        "patterns": (r"missing expected_facts",),
        "title": "知识库回复缺少 expected_facts 关键事实",
        "fail_class": "DEV_BUG",
        "severity": "P0",
        "analysis": "有 outbound 但未覆盖语料标注事实；排查 RAG 召回、Prompt 与 KB 切片。",
    },
    {
        "key": "handoff_miss",
        "patterns": (r"expected local handoff", r"handoff template only"),
        "title": "应转人工场景未进入 LOCAL handoff",
        "fail_class": "DEV_BUG",
        "severity": "P0",
        "analysis": "仅返回转人工话术或 Conversation 未标 LOCAL；与 Q07 双路径策略不一致。",
    },
    {
        "key": "routing_miss",
        "patterns": (r"task_type=.*not in route map",),
        "title": "意图路由 task_type 不在允许集合",
        "fail_class": "DEV_BUG",
        "severity": "P1",
        "analysis": "task_type 与 expected_intent 映射偏差；影响 L2-G1 意图路由指标。",
    },
    {
        "key": "corpus_no_outbound",
        "patterns": (r"no outbound reply", r"no outbound and no handoff"),
        "title": "L2 语料场景无 outbound 且无 handoff",
        "fail_class": "DEV_BUG",
        "severity": "P0",
        "analysis": "与 Formal 无 outbound 同类根因，语料批量暴露。",
    },
]


def _match_theme(notes: str, themes: list[dict]) -> dict | None:
    nl = (notes or "").lower()
    for th in themes:
        for pat in th["patterns"]:
            if re.search(pat, nl, re.I):
                return th
    return None


def classify_formal_fail(row: dict) -> str:
    """Formal 用例行 fail_class。"""
    br = row.get("business_result", "")
    if br in ("PASS", "NA", "—"):
        return "—"
    notes = row.get("notes") or ""
    th = _match_theme(notes, _FORMAL_THEMES)
    if th:
        return th.get("fail_class", "DEV_BUG")
    if br == "PARTIAL" and "manual_pending" in notes.lower():
        return "ENV"
    if "manual:" in notes.lower() and br == "FAIL":
        auto_fails = re.findall(r":fail", notes.lower())
        if not auto_fails:
            return "MANUAL"
    return classify_fail(
        corpus="formal",
        automation_result=row.get("automation_result", ""),
        business_result=br,
        notes=notes,
        status="FAIL" if br == "FAIL" else "PARTIAL",
    )


def _fail_point(notes: str) -> str:
    """从 notes 提取失败验证点摘要。"""
    if not notes:
        return ""
    for part in re.split(r"[|;]", notes):
        p = part.strip()
        if re.search(r":fail|fail\(", p, re.I):
            return p[:100]
    if "MANUAL_PENDING" in notes:
        return ("MANUAL: " + notes.split("MANUAL_PENDING:", 1)[-1].strip())[:100]
    return notes[:100]


def _append_case(
    bugs: dict[str, BugRecord],
    theme: dict,
    case_id: str,
    evidence: str,
    module: str,
    source: str,
    *,
    title: str = "",
    business_result: str = "",
    fail_point: str = "",
):
    key = theme["key"]
    if key not in bugs:
        bugs[key] = BugRecord(
            bug_id="",
            title=theme["title"],
            severity=theme.get("severity", "P1"),
            fail_class=theme.get("fail_class", "DEV_BUG"),
            status=theme.get("status", "OPEN"),
            analysis=theme.get("analysis", ""),
            module=module,
            source=source,
        )
    rec = bugs[key]
    if case_id not in rec.related_cases:
        rec.related_cases.append(case_id)
    fp = fail_point or _fail_point(evidence)
    existing = {lk.case_id for lk in rec.case_links}
    if case_id not in existing:
        rec.case_links.append(CaseLink(
            case_id=case_id,
            title=title,
            module=module,
            business_result=business_result,
            fail_point=fp,
            source=source,
        ))
    else:
        for lk in rec.case_links:
            if lk.case_id == case_id and fp and not lk.fail_point:
                lk.fail_point = fp
    rec.sample_n = len(rec.related_cases)
    if evidence and len(rec.evidence) < 200:
        rec.evidence = evidence[:200]


def build_bug_registry(
    run_id: str,
    formal: list[dict],
    corpus: list[dict],
) -> tuple[list[BugRecord], dict]:
    """聚合 Formal FAIL/PARTIAL + L2 FAIL → 去重缺陷清单 + 分析摘要。"""
    bugs: dict[str, BugRecord] = {}

    for row in formal:
        br = row.get("business_result", "")
        if br not in ("FAIL", "PARTIAL"):
            continue
        notes = row.get("notes") or ""
        cid = row.get("case_id", "")
        module = row.get("module", "")
        title = row.get("title", "")
        th = _match_theme(notes, _FORMAL_THEMES)
        if not th:
            if br == "PARTIAL":
                continue
            if "manual:" in notes.lower() and not re.search(r":fail", notes, re.I):
                th = next((t for t in _FORMAL_THEMES if t["key"] == "manual_send"), None)
            if not th:
                th = {
                    "key": f"formal_{cid.lower().replace('-', '_')}",
                    "title": f"{cid} 验证点未通过",
                    "fail_class": classify_formal_fail(row),
                    "severity": row.get("priority") or "P1",
                    "analysis": notes[:120],
                }
        _append_case(
            bugs, th, cid, notes[:120], module, "formal",
            title=title, business_result=br, fail_point=_fail_point(notes),
        )

    corpus_fail_by_theme: dict[str, list[str]] = {}
    for row in corpus:
        if row.get("business_result") != "FAIL":
            continue
        notes = row.get("notes") or ""
        cid = row.get("id") or row.get("case_id", "")
        th = _match_theme(notes, _CORPUS_THEMES)
        fc = row.get("fail_class") or "DEV_BUG"
        if not th:
            th = {
                "key": f"corpus_{fc.lower()}",
                "title": f"L2 语料 Fail（{fc}）",
                "fail_class": fc,
                "severity": "P1",
                "analysis": notes[:100] or fc,
            }
        key = th["key"]
        corpus_fail_by_theme.setdefault(key, []).append(cid)
        if key in bugs:
            rec = bugs[key]
            for c in corpus_fail_by_theme[key]:
                if c not in rec.related_cases:
                    rec.related_cases.append(c)
            rec.sample_n = len(rec.related_cases)
            rec.source = "mixed" if rec.source == "formal" else rec.source
        else:
            _append_case(
                bugs, th, cid, notes[:120], "L2", "corpus",
                title=(row.get("input") or "")[:40],
                business_result="FAIL",
                fail_point=_fail_point(notes),
            )
            if len(corpus_fail_by_theme[key]) > 1:
                rec = bugs[key]
                for c in corpus_fail_by_theme[key][1:]:
                    if c not in rec.related_cases:
                        rec.related_cases.append(c)
                rec.sample_n = len(rec.related_cases)
                rec.evidence = f"语料 {len(corpus_fail_by_theme[key])} 条同类 Fail"

    # 语料大批量：更新 evidence
    for key, ids in corpus_fail_by_theme.items():
        if key in bugs and len(ids) > 3:
            bugs[key].evidence = f"语料 {len(ids)} 条；样例 {', '.join(ids[:3])}…"
            bugs[key].sample_n = len(ids)

    ordered = sorted(
        bugs.values(),
        key=lambda b: (
            0 if b.severity == "P0" else 1,
            0 if b.fail_class == "DEV_BUG" else 1,
            -b.sample_n,
        ),
    )
    for i, rec in enumerate(ordered, 1):
        rec.bug_id = f"BUG-{run_id[-6:]}-{i:02d}"

    analysis = _build_analysis(ordered, formal, corpus)
    return ordered, analysis


def _build_analysis(bugs: list[BugRecord], formal: list, corpus: list) -> dict:
    open_dev = [b for b in bugs if b.fail_class == "DEV_BUG" and b.status == "OPEN"]
    env_block = [b for b in bugs if b.status == "ENV_BLOCK"]
    manual = [b for b in bugs if b.status == "MANUAL"]
    ff = sum(1 for r in formal if r.get("business_result") == "FAIL")
    fp = sum(1 for r in formal if r.get("business_result") == "PARTIAL")
    cf = sum(1 for r in corpus if r.get("business_result") == "FAIL")

    lines = []
    if not bugs:
        lines.append("本轮无待登记缺陷；Formal/L2 业务结果均为 Pass 或已 Defer。")
    else:
        lines.append(
            f"Formal Fail {ff} 条、Partial {fp} 条；L2 语料 Fail {cf} 条。"
            f" 归并后缺陷 {len(bugs)} 项，其中待开发处理 OPEN DEV_BUG {len(open_dev)} 项。"
        )
        if open_dev:
            top = "、".join(b.title[:20] for b in open_dev[:3])
            lines.append(f"优先修复：{top}。")
        if env_block:
            lines.append(f"环境阻塞 {len(env_block)} 项（如无在线坐席），修环境后重跑，不计入 Dev 缺陷。")
        if manual:
            lines.append(f"人工补测 {len(manual)} 项，需 G1 坐席 + L3 sendManual/真机。")
        if cf > 20 and open_dev:
            lines.append("L2 语料 Fail 批量出现，与 Formal 无 outbound/误转人工 根因一致，建议先修 P0 再全量重跑。")

    g3_open_p0 = len([b for b in open_dev if b.severity == "P0"])
    return {
        "summary_lines": lines,
        "open_dev_bug_p0": g3_open_p0,
        "open_dev_bug_total": len(open_dev),
        "env_block": len(env_block),
        "manual_pending": len(manual),
        "total_bugs": len(bugs),
    }


def case_to_bugs_map(bugs: list[BugRecord]) -> dict[str, list[str]]:
    """用例编号 → 缺陷 ID 列表。"""
    out: dict[str, list[str]] = {}
    for b in bugs:
        for cid in b.related_cases:
            out.setdefault(cid, [])
            if b.bug_id not in out[cid]:
                out[cid].append(b.bug_id)
    return out


def bug_case_mapping_rows(
    bugs: list[BugRecord],
    run_id: str,
    executed_at: str,
) -> list[dict]:
    """逐条用例-缺陷关联（一行一条关联）。"""
    rows: list[dict] = []
    for b in bugs:
        for lk in b.case_links:
            rows.append({
                "run_id": run_id,
                "executed_at": executed_at,
                "case_id": lk.case_id,
                "case_title": lk.title,
                "module": lk.module,
                "business_result": lk.business_result,
                "fail_point": lk.fail_point,
                "bug_id": b.bug_id,
                "bug_title": b.title,
                "fail_class": b.fail_class,
                "bug_status": b.status,
                "source": lk.source or b.source,
            })
    rows.sort(key=lambda r: (r["case_id"], r["bug_id"]))
    return rows


BUG_CASE_MAPPING_FIELDS = [
    "run_id", "executed_at", "case_id", "case_title", "module",
    "business_result", "fail_point", "bug_id", "bug_title", "fail_class", "bug_status", "source",
]


def format_bug_management_markdown(bugs: list[BugRecord], analysis: dict) -> list[str]:
    lines = [
        "## 缺陷管理（Bug Registry）",
        "",
        "| 指标 | 数量 |",
        "|------|------|",
        f"| 缺陷项（去重） | {analysis.get('total_bugs', 0)} |",
        f"| OPEN DEV_BUG（计 G3） | {analysis.get('open_dev_bug_total', 0)} |",
        f"| OPEN P0 DEV_BUG | {analysis.get('open_dev_bug_p0', 0)} |",
        f"| 环境阻塞 ENV_BLOCK | {analysis.get('env_block', 0)} |",
        f"| 待人工 MANUAL | {analysis.get('manual_pending', 0)} |",
        "",
    ]
    if bugs:
        lines += [
            "### 缺陷清单",
            "",
            "| 缺陷 ID | 用例编号 | 标题 | 严重 | 分类 | 状态 | 简要分析 |",
            "|---------|----------|------|------|------|------|----------|",
        ]
        for b in bugs:
            case_ids = "、".join(b.related_cases)
            lines.append(
                f"| {b.bug_id} | {case_ids} | {b.title} | {b.severity} | {b.fail_class} | {b.status} | "
                f"{b.analysis[:50]} |"
            )
        lines.append("")

        lines += [
            "### 用例-缺陷关联",
            "",
            "| 用例编号 | 模块 | 用例标题 | 结果 | 缺陷 ID | 失败验证点 |",
            "|----------|------|----------|------|---------|------------|",
        ]
        mapping_rows = []
        for b in bugs:
            for lk in b.case_links:
                mapping_rows.append((lk.case_id, lk, b))
        mapping_rows.sort(key=lambda x: x[0])
        for _, lk, b in mapping_rows:
            title = (lk.title or "—")[:36]
            lines.append(
                f"| {lk.case_id} | {lk.module or '—'} | {title} | {lk.business_result or '—'} | "
                f"{b.bug_id} | {lk.fail_point[:45] or '—'} |"
            )
        lines.append("")

    lines += [
        "### 本轮简约分析",
        "",
    ]
    for ln in analysis.get("summary_lines", []):
        lines.append(f"- {ln}")
    lines += [
        "",
        "> fail_class 规则见 `spec/l2-fail-classification.md`；G3 门禁仅计 OPEN 的 DEV_BUG + ENV。",
        "",
    ]
    return lines


def bugs_to_csv_rows(bugs: list[BugRecord], run_id: str, executed_at: str) -> list[dict]:
    rows = []
    for b in bugs:
        rows.append({
            "run_id": run_id,
            "executed_at": executed_at,
            "bug_id": b.bug_id,
            "case_ids": ";".join(b.related_cases),
            "case_count": len(b.related_cases),
            "title": b.title,
            "severity": b.severity,
            "fail_class": b.fail_class,
            "status": b.status,
            "module": b.module,
            "source": b.source,
            "evidence": b.evidence,
            "analysis": b.analysis,
        })
    return rows


BUG_CSV_FIELDS = [
    "run_id", "executed_at", "bug_id", "case_ids", "case_count",
    "title", "severity", "fail_class", "status", "module", "source", "evidence", "analysis",
]


def bugs_to_json(bugs: list[BugRecord], analysis: dict) -> dict:
    def _bug_dict(b: BugRecord) -> dict:
        d = asdict(b)
        d["case_links"] = [asdict(lk) for lk in b.case_links]
        return d

    return {
        "bugs": [_bug_dict(b) for b in bugs],
        "case_to_bugs": case_to_bugs_map(bugs),
        "analysis": analysis,
    }
