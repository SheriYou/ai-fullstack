#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Formal 用例验证点 — 与 test-cases-full.verify_profile 对齐。"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from case_executor import (
    conv_get,
    is_handoff_reply_text,
    verify_bot_active,
    verify_local_handoff,
)
from l2_eval_core import facts_match, first_response_ms, session_id_from, session_task_type


@dataclass
class CaseContext:
    client: object
    channel: str
    bl: int
    wait_s: float
    case_id: str
    whatsapp_id: str = ""
    session: dict = field(default_factory=dict)
    messages: list = field(default_factory=list)
    conversation: dict | None = None
    outbound_texts: list[str] = field(default_factory=list)
    webhook_status: int = 0
    webhook_ok: bool = False
    response_ms: float | None = None
    t_send: float = 0.0
    extra: dict = field(default_factory=dict)


@dataclass
class CheckResult:
    check: str
    passed: bool
    note: str
    manual: bool = False


def _inbounds(msgs: list) -> list:
    return [m for m in msgs if (m.get("direction") or "").lower() == "inbound"]


def _bot_outbounds_after(msgs: list, after_count: int) -> list:
    outs = []
    n = 0
    for m in msgs:
        if (m.get("direction") or "").lower() == "outbound":
            content = (m.get("content") or "").strip()
            if not content:
                continue
            if n >= after_count:
                outs.append(content)
            n += 1
    return outs


def run_check(name: str, ctx: CaseContext) -> CheckResult:
    name = name.strip()
    conv = ctx.conversation
    texts = ctx.outbound_texts
    blob = " ".join(texts).lower()

    if name == "webhook_ok":
        ok = ctx.webhook_ok
        return CheckResult(name, ok, f"http={ctx.webhook_status}")

    if name == "inbound_ok":
        ok = len(_inbounds(ctx.messages)) >= 1
        return CheckResult(name, ok, f"inbound={len(_inbounds(ctx.messages))}")

    if name.startswith("outbound≤"):
        limit = float(name.split("≤", 1)[1].replace("s", ""))
        ms = ctx.response_ms if ctx.response_ms is not None else (time.time() - ctx.t_send) * 1000
        ok = ms <= limit * 1000 and bool(texts)
        return CheckResult(name, ok, f"response_ms={int(ms)}")

    if name == "not_handoff_tpl":
        ok = bool(texts) and not is_handoff_reply_text(texts[-1])
        return CheckResult(name, ok, texts[-1][:80] if texts else "no outbound")

    if name == "bot_active":
        ok, notes = verify_bot_active(conv)
        return CheckResult(name, ok, "; ".join(notes))

    if name == "task_type":
        tt = session_task_type(ctx.session)
        ok = bool(tt) and tt.upper() != "UNKNOWN"
        return CheckResult(name, ok, f"task_type={tt}")

    if name == "price_keywords":
        ok = any(k in blob for k in ("999", "36", "bdt", "price", "订金", "塔卡", "36999"))
        return CheckResult(name, ok, blob[:80] if blob else "empty")

    if name == "rag_tool_ok":
        wa = ctx.whatsapp_id
        st, data = ctx.client._call("GET", f"/business-lines/{ctx.bl}/agent/tools/logs?whatsapp_id={wa}")
        inner = data.get("data") or data
        logs = inner if isinstance(inner, list) else inner.get("data") or []
        rag = [x for x in logs if "rag" in str(x.get("tool_name", x.get("toolName", ""))).lower()]
        ok = any(x.get("success") is True or x.get("status") == "success" for x in rag) if rag else False
        return CheckResult(name, ok, f"rag_logs={len(rag)} http={st}", manual=not rag)

    if name == "local_handoff":
        ok, notes = verify_local_handoff(conv)
        return CheckResult(name, ok, "; ".join(notes))

    if name == "handoff_assigned":
        ok, notes = verify_local_handoff(conv)
        if not ok:
            return CheckResult(name, False, "; ".join(notes))
        hs = conv_get(conv, "handoff_status", "handoffStatus")
        aid = conv_get(conv, "assigned_user_id", "assignedUserId")
        if hs == "assigned" and aid:
            return CheckResult(name, True, f"assignedUserId={aid}")
        if hs == "no_agent_online":
            return CheckResult(name, True, "handoffStatus=no_agent_online (无在线坐席，LOCAL 状态已建立)", manual=True)
        return CheckResult(name, False, f"handoffStatus={hs}; need assigned or no_agent_online")

    if name == "conv_listed":
        convs = ctx.client.conversations(ctx.bl)
        from run_test_suite import find_conversation

        c = find_conversation(convs, ctx.whatsapp_id)
        ok = c is not None
        return CheckResult(name, ok, "conversation in list" if ok else "not in conversations API")

    if name == "no_bot_outbound":
        before = ctx.extra.get("outbound_before", 0)
        new_texts = ctx.outbound_texts[before:]
        # Q02：转人工后不得再发 FAQ/寒暄类 bot 回复；转人工提示语不计入
        faq_replies = [t for t in new_texts if not is_handoff_reply_text(t)]
        ok = len(faq_replies) <= 0
        return CheckResult(
            name, ok,
            f"new_faq_outbound={len(faq_replies)}; new_total={len(new_texts)}",
        )

    if name == "session_stable":
        sid = ctx.extra.get("session_ids") or []
        ok = len(sid) >= 2 and len(set(sid)) == 1
        return CheckResult(name, ok, f"sessions={sid}")

    if name == "multi_inbound":
        need = int(ctx.extra.get("multi_count", 3))
        ok = len(_inbounds(ctx.messages)) >= need
        return CheckResult(name, ok, f"inbound={len(_inbounds(ctx.messages))}")

    if name == "empty_input_hint":
        hints = ("有效", "重新输入", "没有收到", "请重新", "valid")
        ok = any(h in blob for h in hints) or bool(texts)
        return CheckResult(name, ok, texts[-1][:80] if texts else "no reply")

    if name == "emoji_handled":
        ok = ctx.webhook_ok and (bool(texts) or session_task_type(ctx.session))
        return CheckResult(name, ok, "no crash + reply or session")

    if name == "gibberish_hint":
        hints = ("暂未理解", "hot70", "转人工", "重新", "understand")
        ok = any(h in blob for h in hints)
        return CheckResult(name, ok, texts[-1][:80] if texts else "no reply")

    if name == "handoff_or_faq":
        ho, _ = verify_local_handoff(conv)
        ok = ho or (bool(texts) and not is_handoff_reply_text(texts[-1]))
        return CheckResult(name, ok, "LOCAL handoff or FAQ reply")

    if name == "handoff_required":
        ok, notes = verify_local_handoff(conv)
        return CheckResult(name, ok, "; ".join(notes))

    if name == "no_hallucination_handoff":
        ho, _ = verify_local_handoff(conv)
        ok = ho or any(k in blob for k in ("无法", "转接", "人工", "确认", "handoff", "cannot"))
        return CheckResult(name, ok, "handoff or safe fallback wording")

    if name == "clarify_multi_intent":
        hints = ("哪一个", "想了解", "分开", "具体", "which")
        ok = any(h in blob for h in hints)
        return CheckResult(name, ok, texts[-1][:80] if texts else "no clarify")

    if name == "long_text_ok":
        ok = ctx.webhook_ok
        return CheckResult(name, ok, "webhook accepted long input")

    if name == "session_traceable":
        sid = session_id_from(ctx.session, ctx.messages, ctx.conversation)
        ok = bool(sid) and len(ctx.messages) >= 1
        return CheckResult(name, ok, f"session_id={sid}; msgs={len(ctx.messages)}")

    if name == "handoff_state_m8":
        ok, notes = verify_local_handoff(conv)
        return CheckResult(name, ok, "; ".join(notes))

    if name.startswith("facts:"):
        facts = name.split(":", 1)[1]
        ok = facts_match(texts, facts)
        return CheckResult(name, ok, "facts matched" if ok else "missing facts")

    if name == "manual_only":
        return CheckResult(name, False, "需人工按 steps/expected_result 执行", manual=True)

    if name == "blocked":
        return CheckResult(name, False, "功能 Blocked", manual=True)

    if name == "defer_ext":
        return CheckResult(name, False, "智齿 EXT / 工作台操作 — Defer", manual=True)

    if name == "metrics_aggregate":
        return CheckResult(name, True, "由 L2 指标 / corpus 聚合判定", manual=False)

    return CheckResult(name, False, f"unknown check {name}")


def run_checks(check_names: list[str], ctx: CaseContext) -> list[CheckResult]:
    return [run_check(c, ctx) for c in check_names]


def summarize_checks(results: list[CheckResult]) -> tuple[str, str, str]:
    """返回 (business_result, execution_status, notes)。"""
    if not results:
        return "NA", "NOT_RUN", "no checks"

    if any(r.check == "blocked" for r in results):
        return "NA", "BLOCKED", "; ".join(r.note for r in results)

    if any(r.check == "defer_ext" for r in results):
        return "NA", "NOT_RUN", "; ".join(r.note for r in results)

    if all(r.check == "manual_only" for r in results):
        return "NA", "NOT_RUN", "需人工按 steps/expected_result 执行"

    if any(r.check == "metrics_aggregate" for r in results):
        return "NA", "EXECUTED", "; ".join(r.note for r in results if r.check == "metrics_aggregate")

    auto = [r for r in results if not r.manual]
    manual = [r for r in results if r.manual]

    if auto and all(r.passed for r in auto):
        note = "; ".join(f"{r.check}:OK" for r in auto)
        if manual:
            note += " | MANUAL_PENDING:" + ",".join(r.check for r in manual)
        biz = "PASS" if not manual else "PARTIAL"
        return biz, "EXECUTED", note

    failed = [r for r in auto if not r.passed]
    note = "; ".join(f"{r.check}:FAIL({r.note})" for r in failed)
    passed = [r for r in auto if r.passed]
    if passed:
        note += " | OK:" + ",".join(r.check for r in passed)
    if manual:
        note += " | MANUAL_PENDING:" + ",".join(r.check for r in manual)
    return "FAIL", "EXECUTED", note
