"""Deterministic DB observations for one chatbot turn."""

from __future__ import annotations

import json
import time

from . import harness


def _norm_tag(tag: str | None) -> str | None:
    if not tag or tag in ("无", "NULL", "null", "??????"):
        return None
    return str(tag).strip().replace("预订", "预定")


def _load_output(output_json: str | None) -> dict | None:
    if not output_json or output_json in ("NULL", "null"):
        return None
    try:
        return json.loads(output_json)
    except (TypeError, ValueError):
        return None


def _is_kb_hit_status(status: str | None) -> bool:
    value = str(status or "").strip().upper()
    return value == "HIT" or value.startswith("HIT_")


def _parse_step(obj: dict | None, step_status: str | None = None) -> tuple[bool, bool, str | None]:
    kb_hit = False
    handoff = False
    grounding = None
    if step_status and str(step_status).lower() == "handoff":
        handoff = True
    if not obj:
        return kb_hit, handoff, grounding

    state = obj.get("grounding_state") or obj.get("groundingState")
    grounding = state.upper() if isinstance(state, str) else None

    for observation in obj.get("observations") or []:
        if not isinstance(observation, dict):
            continue
        tool = observation.get("tool")
        if tool == "search_knowledge_base":
            try:
                chunks = int(observation.get("retrieved_chunk_count") or 0)
            except (ValueError, TypeError):
                chunks = 0
            if _is_kb_hit_status(observation.get("status")) or chunks > 0:
                kb_hit = True
            answer_source = str(observation.get("answer_source") or "")
            if "STANDARD_REPLY" in answer_source or "POLICY_STANDARD" in answer_source:
                kb_hit = True
            if observation.get("handoff_decision") is True:
                handoff = True
        if tool == "transfer_to_human":
            handoff = True

    for action in obj.get("actions") or []:
        if not isinstance(action, dict):
            continue
        if str(action.get("type") or "").upper() in ("HANDOFF_TO_HUMAN", "TRANSFER_TO_HUMAN"):
            handoff = True

    task_type = str(obj.get("task_type") or "").upper()
    if task_type.startswith("HANDOFF") or task_type.endswith("_HANDOFF") or "HANDOFF_REQUIRED" in task_type:
        handoff = True

    return kb_hit, handoff, grounding


def _msg_id_variants(msg_id: str | None) -> list[str]:
    mid = msg_id or ""
    variants = {mid}
    if mid and not mid.startswith("local_gateway_"):
        variants.add("local_gateway_" + mid)
    if mid.startswith("local_gateway_"):
        variants.add(mid[len("local_gateway_"):])
    return [value for value in variants if value]


def read_turn_signals(wa_id: str, msg_id: str, tag_wait_s: float = 0.0) -> dict:
    wa = harness.sql_escape(wa_id)
    mids = _msg_id_variants(msg_id)
    mid_sql = " OR ".join(
        "message_id='%s' OR message_id LIKE '%%%s%%'"
        % (harness.sql_escape(mid), harness.sql_escape(mid))
        for mid in mids
    )

    handoff = False
    tag = None
    tag_source = None
    latency = None
    intent = None
    kb_hit_trace = False
    trace_id = None

    rows = harness.mysql_rows(
        "SELECT COALESCE(trace_id,'') FROM wa_chat_message WHERE whatsapp_id='%s' AND (%s) "
        "AND direction='inbound' ORDER BY `timestamp` DESC LIMIT 1" % (wa, mid_sql)
    )
    if rows and rows[0][0] not in ("", "NULL", "null"):
        trace_id = rows[0][0]

    trace_rows = harness.mysql_rows(
        "SELECT COALESCE(handoff_flag,''), COALESCE(customer_tag,''), "
        "COALESCE(latency_ms,0), COALESCE(detected_intent,''), COALESCE(knowledge_hit,''), "
        "COALESCE(event_type,''), COALESCE(extra_json,'') "
        "FROM wa_message_trace_log WHERE whatsapp_id='%s' AND (%s) ORDER BY id" % (wa, mid_sql)
    )
    if not trace_rows and trace_id:
        trace_rows = harness.mysql_rows(
            "SELECT COALESCE(handoff_flag,''), COALESCE(customer_tag,''), "
            "COALESCE(latency_ms,0), COALESCE(detected_intent,''), COALESCE(knowledge_hit,''), "
            "COALESCE(event_type,''), COALESCE(extra_json,'') "
            "FROM wa_message_trace_log WHERE trace_id='%s' ORDER BY id" % harness.sql_escape(trace_id)
        )

    for row in trace_rows:
        if len(row) < 6:
            continue
        handoff_flag, customer_tag, latency_ms, detected_intent, knowledge_hit, event_type = row[:6]
        extra_json = row[6] if len(row) > 6 else ""
        if handoff_flag == "1" or str(event_type).upper() in ("HANDOFF_REQUESTED", "HANDOFF_RESULT"):
            handoff = True
        if _norm_tag(customer_tag):
            tag = _norm_tag(customer_tag)
            tag_source = "trace"
        try:
            latency = max(latency or 0, int(latency_ms or 0))
        except ValueError:
            pass
        if detected_intent and not intent:
            intent = detected_intent
        if knowledge_hit == "1":
            kb_hit_trace = True
        if str(event_type).upper() == "KNOWLEDGE_HIT":
            if knowledge_hit == "1":
                kb_hit_trace = True
            elif extra_json and extra_json not in ("NULL", "null", ""):
                try:
                    extra = json.loads(extra_json)
                    if int(extra.get("retrieved_chunk_count") or 0) > 0:
                        kb_hit_trace = True
                except (TypeError, ValueError):
                    pass

    like_parts = " OR ".join("input_json LIKE '%%%s%%'" % harness.sql_escape(mid) for mid in mids)
    step_rows = harness.mysql_rows(
        "SELECT COALESCE(output_json,''), COALESCE(status,''), COALESCE(latency_ms,0) "
        "FROM wa_agent_step WHERE whatsapp_id='%s' AND (%s) "
        "ORDER BY created_at DESC LIMIT 1" % (wa, like_parts)
    )
    kb_hit = False
    grounding = None
    step_note = None
    if step_rows:
        step = step_rows[0]
        kb_hit, step_handoff, grounding = _parse_step(_load_output(step[0]), step[1] if len(step) > 1 else None)
        if step_handoff:
            handoff = True
        if latency is None and len(step) > 2:
            try:
                latency = int(step[2])
            except ValueError:
                pass
    else:
        step_note = "AgentStep证据不足：未找到当前message_id对应Step"

    kb_hit = kb_hit or kb_hit_trace

    def read_tag() -> str | None:
        conversation_rows = harness.mysql_rows(
            "SELECT COALESCE(tags_str,'') FROM wa_conversation "
            "WHERE whatsapp_id='%s' ORDER BY id DESC LIMIT 1" % wa
        )
        if conversation_rows and conversation_rows[0]:
            raw = conversation_rows[0][0] or ""
            return _norm_tag(raw.split(",")[-1] if raw else "")
        return None

    authoritative_tag = read_tag()
    if authoritative_tag and tag is None:
        tag = authoritative_tag
        tag_source = "conversation_fallback"
    elif tag_wait_s and tag_wait_s > 0 and tag is None:
        deadline = time.time() + tag_wait_s
        while time.time() < deadline:
            time.sleep(1.0)
            authoritative_tag = read_tag()
            if authoritative_tag:
                tag = authoritative_tag
                tag_source = "conversation_fallback"
                break

    return {
        "kb_hit": kb_hit,
        "handoff": handoff,
        "tag": tag,
        "tag_source": tag_source,
        "grounding": grounding,
        "latency_ms": latency,
        "detected_intent": intent,
        "trace_id": trace_id,
        "step_note": step_note,
    }

