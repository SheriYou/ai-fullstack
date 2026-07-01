#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L2 语料评估：分 corpus 断言、Fail 分类、响应耗时。"""
from __future__ import annotations

try:
    from case_executor import is_handoff_reply_text
except ImportError:
    def is_handoff_reply_text(text: str) -> bool:
        blob = (text or "").lower()
        return "human agent" in blob or "人工" in blob

INTENT_TASK_ALLOW = {
    "产品信息": {"QA_ANSWER", "SALES_GUIDE", "PRODUCT_RESEARCH", "PRODUCT_RECOMMENDATION", "SUPPORT"},
    "活动规则": {"QA_ANSWER", "SUPPORT"},
    "活动权益": {"QA_ANSWER", "SALES_GUIDE", "SUPPORT"},
    "提机相关": {"QA_ANSWER", "SUPPORT"},
    "门店相关": {"QA_ANSWER", "SUPPORT"},
    "官方身份": {"QA_ANSWER", "CHITCHAT", "SUPPORT"},
    "人工兜底": {"HUMAN_HANDOFF"},
    "人工客服": {"HUMAN_HANDOFF"},
    "无法覆盖": {"HUMAN_HANDOFF", "QA_ANSWER", "LOW_CONFIDENCE", "UNKNOWN"},
}

KB_CATEGORY_TO_INTENT = {
    "PROD": "产品信息",
    "ACT": "活动规则",
    "BEN": "活动权益",
    "PICK": "提机相关",
    "STORE": "门店相关",
    "OFF": "官方身份",
    "HANDOFF": "人工兜底",
}


def session_task_type(sess: dict) -> str:
    if not sess:
        return ""
    inner = sess.get("session") or sess
    return (inner.get("task_type") or inner.get("taskType") or "").strip()


def session_id_from(sess: dict) -> str:
    if not sess:
        return ""
    inner = sess.get("session") or sess
    return (inner.get("session_id") or inner.get("sessionId") or "").strip()


def is_handoff(sess: dict, conv: dict | None) -> bool:
    """是否已进入 Q07 LOCAL 转人工（Conversation 字段，非 outbound 文案）。"""
    try:
        from case_executor import verify_local_handoff
    except ImportError:
        verify_local_handoff = _legacy_is_handoff_conv
    ok, _ = verify_local_handoff(conv)
    return ok


def _legacy_is_handoff_conv(conv: dict | None) -> tuple[bool, list[str]]:
    if not conv:
        return False, []
    st = conv.get("conversation_status") or conv.get("conversationStatus") or ""
    if st in ("handoff", "external_handoff"):
        return True, []
    if conv.get("is_active_agent") == 0 or conv.get("isActiveAgent") == 0:
        return True, []
    return False, []


def facts_match(texts: list[str], facts: str) -> bool:
    if not facts:
        return True
    blob = " ".join(texts).lower()
    for part in facts.split("|"):
        kw = part.strip()
        if kw and kw.lower() not in blob:
            return False
    return True


def _msg_ts(m: dict) -> int | None:
    for key in ("timestamp", "message_time", "created_at", "createdAt"):
        v = m.get(key)
        if v is None or v == "":
            continue
        try:
            return int(v)
        except (TypeError, ValueError):
            continue
    return None


def first_response_ms(messages: list, fallback_wait_ms: float | None = None) -> float | None:
    """最近一条 inbound 到其后首条 outbound 的毫秒差。"""
    if not messages:
        return fallback_wait_ms
    in_ts = []
    out_ts = []
    for m in messages:
        ts = _msg_ts(m)
        if ts is None:
            continue
        direction = (m.get("direction") or "").lower()
        if direction == "inbound":
            in_ts.append(ts)
        elif direction == "outbound" and (m.get("content") or "").strip():
            out_ts.append(ts)
    if not in_ts or not out_ts:
        return fallback_wait_ms
    anchor = max(in_ts)
    later = [t for t in out_ts if t >= anchor]
    if not later:
        later = out_ts
    delta = min(later) - anchor
    if delta < 0:
        return fallback_wait_ms
    return float(delta)


def classify_fail(
    *,
    corpus: str,
    automation_result: str,
    business_result: str,
    notes: str,
    status: str,
) -> str:
    if status == "SKIP" or business_result == "NA":
        return "NA"
    if business_result == "PASS":
        return "—"
    note_l = (notes or "").lower()
    if automation_result == "FAIL" or "webhook http" in note_l:
        if any(x in note_l for x in ("404", "401", "500", "login", "ragflow")):
            return "ENV"
        return "HARNESS"
    if "missing expected_facts" in note_l:
        return "DEV_BUG"
    if "no outbound" in note_l:
        return "DEV_BUG"
    if "task_type" in note_l or "handoff" in note_l:
        return "DEV_BUG"
    return "DEV_BUG"


def _routing_ok(intent: str, task_type: str) -> bool:
    allowed = INTENT_TASK_ALLOW.get(intent, set())
    if not allowed:
        return True
    if not task_type:
        return False
    return task_type in allowed


def eval_row_by_corpus(
    *,
    corpus: str,
    row: dict,
    wh_ok: bool,
    wh_st: int,
    sess: dict,
    conv: dict | None,
    texts: list[str],
    task_type: str,
    handoff: bool,
) -> tuple[str, list[str], bool]:
    """返回 (business_result, notes, routing_pass)。"""
    notes: list[str] = []
    routing_pass = True

    intent = row.get("expected_intent") or KB_CATEGORY_TO_INTENT.get(row.get("category", ""), "") or ""
    should_ho = (row.get("should_handoff") or "").lower()
    action = (row.get("expected_action") or "").lower()
    facts = row.get("expected_facts") or ""

    if not wh_ok:
        return "FAIL", [f"webhook http={wh_st}"], False

    if corpus == "intent":
        if should_ho == "true" or action == "handoff":
            if not handoff:
                notes.append(f"expected LOCAL handoff; task_type={task_type}")
                if texts and is_handoff_reply_text(texts[-1]):
                    notes.append("only handoff reply text, Conversation not LOCAL")
                return "FAIL", notes, False
            return "PASS", ["LOCAL handoff OK"], True
        if should_ho == "false":
            if handoff:
                notes.append("unexpected LOCAL handoff")
                return "FAIL", notes, False
            if texts and is_handoff_reply_text(texts[-1]):
                notes.append("handoff template reply but should auto-reply FAQ")
                return "FAIL", notes, False
        if intent and task_type:
            routing_pass = _routing_ok(intent, task_type)
            if not routing_pass:
                notes.append(f"task_type={task_type} not in route map for {intent}")
                return "FAIL", notes, False
        return "PASS", ["routing OK"], routing_pass

    if corpus == "kb":
        if should_ho == "true":
            if not handoff:
                notes.append(f"expected LOCAL handoff; task_type={task_type}")
                return "FAIL", notes, False
            return "PASS", ["LOCAL handoff OK"], True
        if handoff:
            notes.append("unexpected LOCAL handoff on kb reply case")
            return "FAIL", notes, False
        if facts:
            if not texts:
                notes.append("no outbound reply")
                return "FAIL", notes, False
            if not facts_match(texts, facts):
                notes.append("missing expected_facts in outbound")
                return "FAIL", notes, True
        elif not texts:
            notes.append("no outbound reply")
            return "FAIL", notes, False
        intent_key = KB_CATEGORY_TO_INTENT.get(row.get("category", ""), "")
        if intent_key and task_type:
            routing_pass = _routing_ok(intent_key, task_type)
        return "PASS", ["facts OK" if facts else "reply OK"], routing_pass

    if corpus == "handoff":
        if should_ho == "true" or action == "handoff":
            if not handoff:
                notes.append(f"expected LOCAL handoff; task_type={task_type}")
                if texts and is_handoff_reply_text(texts[-1]):
                    notes.append("reply looks like handoff but Conversation not LOCAL")
                return "FAIL", notes, False
            return "PASS", ["LOCAL handoff OK"], True
        if should_ho == "false":
            if handoff:
                notes.append("unexpected LOCAL handoff")
                return "FAIL", notes, False
            return "PASS", ["no handoff OK"], True
        # conditional：LOCAL 转人工，或机器人 FAQ 回复（且未进入 handoff 状态）
        if handoff:
            return "PASS", ["conditional: LOCAL handoff"], True
        if texts and not is_handoff_reply_text(texts[-1]):
            return "PASS", ["conditional: FAQ reply"], True
        if texts and is_handoff_reply_text(texts[-1]):
            notes.append("handoff template only, not LOCAL assignment")
            return "FAIL", notes, False
        notes.append("conditional: no handoff and no reply")
        return "FAIL", notes, False

    if corpus == "adversarial":
        if handoff or (not facts or facts_match(texts, facts)):
            if not texts and not handoff:
                notes.append("no outbound and no handoff")
                return "FAIL", notes, False
            return "PASS", ["adversarial handled"], handoff
        notes.append("unexpected reply without handoff/facts")
        return "FAIL", notes, False

    # fallback legacy
    if action == "none":
        if texts:
            return "FAIL", ["expected no bot reply"], False
        return "PASS", ["OK"], True
    if action == "handoff" or should_ho == "true":
        if not handoff:
            return "FAIL", [f"expected handoff; task_type={task_type}"], False
        return "PASS", ["OK"], True
    if facts and texts and not facts_match(texts, facts):
        return "FAIL", ["missing expected_facts in outbound"], True
    if not texts and should_ho != "true":
        return "FAIL", ["no outbound reply"], False
    return "PASS", ["OK"], True
