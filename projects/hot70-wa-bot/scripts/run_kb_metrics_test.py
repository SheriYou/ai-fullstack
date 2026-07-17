#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L2 知识库指标专项：以 prd/Hot70_机器人_知识库指标测试.csv 为准。"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import uuid

CASE_ID_RE = re.compile(r"^(TC-H70-\d{3})-(N|H-C\d+)$")
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from case_executor import is_handoff_reply_text, poll_turn_state
from l2_eval_core import facts_match, last_response_ms, session_id_from, session_task_type
from run_test_suite import DEFAULT_BASE, DEFAULT_PASS, DEFAULT_USER, Client

ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
if str(FRAMEWORK_ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_ROOT / "lib"))

from llm_client import LlmConfigError, chat  # noqa: E402

REPORTS = ROOT / "reports"
RESULTS_JSONL = REPORTS / "cases-results.jsonl"
BATCHES_DIR = REPORTS / "batches"
SOURCE_CSV = ROOT / "prd" / "Hot70_机器人_知识库指标测试.csv"
FAQ_CSV = ROOT / "prd" / "Hot 70 FAQ知识库_FAQ知识库_全部FAQ.csv"
ALLOWED_INTENT_TAGS = {"已预订未提机", "未预订高意向", "未预订低意向", "已提机", "NA"}
VALID_LOG_CUSTOMER_TAGS = {"已预订未提机", "未预订高意向", "已提机"}
INTENT_TAG_ALIASES = {
    "已提机": "已提机",
    "已提货": "已提机",
    "已取机": "已提机",
    "picked_up": "已提机",
    "already_picked_up": "已提机",
    "已预定": "已预订未提机",
    "已预约": "已预订未提机",
    "已预订未提机": "已预订未提机",
    "未预订高意向": "未预订高意向",
    "未预订低意向": "未预订低意向",
}


def load_rows(path: Path) -> list[dict]:
    encodings = ("utf-8-sig", "gb18030", "cp936")
    last_error: Exception | None = None
    for enc in encodings:
        try:
            with path.open(encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError as e:
            last_error = e
    if last_error:
        raise last_error
    return []


def yesno_text(value: bool) -> str:
    return "是" if value else "否"


def parse_yes_no(value) -> bool | None:
    if isinstance(value, bool):
        return value
    raw = "" if value is None else str(value).strip().lower()
    if raw in ("1", "true", "yes", "y", "on", "是"):
        return True
    if raw in ("0", "false", "no", "n", "off", "否"):
        return False
    return None

def normalize_handoff(value: str) -> str:
    raw = (value or "").strip()
    if raw in ("是", "yes", "YES", "true", "TRUE"):
        return "true"
    if raw in ("否", "no", "NO", "false", "FALSE"):
        return "false"
    return "conditional"


def normalize_intent_tag(raw: str) -> str:
    v = (raw or "").strip()
    if not v:
        return ""
    if v in ALLOWED_INTENT_TAGS:
        return v
    return INTENT_TAG_ALIASES.get(v, "")


def parse_trace_records(payload: dict) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("records"), list):
        return [r for r in payload["records"] if isinstance(r, dict)]
    d = payload.get("data") or {}
    if isinstance(d, list):
        return [r for r in d if isinstance(r, dict)]
    if isinstance(d, dict):
        d2 = d.get("data") or {}
        if isinstance(d2, dict):
            recs = d2.get("records")
            if isinstance(recs, list):
                return [r for r in recs if isinstance(r, dict)]
        recs = d.get("records")
        if isinstance(recs, list):
            return recs
    if isinstance(payload.get("records"), list):
        return payload["records"]
    return []


def fetch_trace_logs(client: Client, bl: int, session_id: str, event_type: str, size: int = 20) -> list[dict]:
    sid = quote(session_id, safe="")
    evt = quote(event_type, safe="")
    path = f"/business-lines/{bl}/trace-logs?session_id={sid}&event_type={evt}&page=1&size={size}"
    st, data = client._call("GET", path)
    if st != 200:
        return []
    recs = parse_trace_records(data)
    return [r for r in recs if (r.get("event_type") or "") == event_type]


def _fetch_trace_pages(client: Client, path_template: str, size: int) -> list[dict]:
    records: list[dict] = []
    for page in range(1, 11):
        st, data = client._call("GET", path_template.format(page=page, size=size))
        if st != 200:
            break
        page_records = parse_trace_records(data)
        records.extend(page_records)
        if len(page_records) < size:
            break
    return records


def fetch_trace_logs_by_session(client: Client, bl: int, session_id: str, size: int = 100) -> list[dict]:
    sid = quote(session_id, safe="")
    template = f"/business-lines/{bl}/trace-logs?session_id={sid}&page={{page}}&size={{size}}"
    return _fetch_trace_pages(client, template, size)


def fetch_trace_logs_by_whatsapp(client: Client, bl: int, whatsapp_id: str, size: int = 100) -> list[dict]:
    wid = quote(whatsapp_id, safe="")
    template = f"/business-lines/{bl}/trace-logs?whatsapp_id={wid}&page={{page}}&size={{size}}"
    return _fetch_trace_pages(client, template, size)


def trace_event_sort_key(rec: dict):
    def _to_int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    return (
        _to_int(rec.get("event_time") or rec.get("created_at") or rec.get("timestamp") or rec.get("createdAt")),
        _to_int(rec.get("message_id") or rec.get("messageId")),
        _to_int(rec.get("id")),
        str(rec.get("trace_id") or ""),
    )


def latest_trace_event(records: list[dict]) -> dict | None:
    if not records:
        return None
    return sorted(records, key=trace_event_sort_key)[-1]


def resolve_trace_tag_and_intent(client: Client, bl: int, session_id: str) -> dict:
    # trace 落库可能有延迟，短轮询 3 次
    tag_rec = None
    intent_rec = None
    for _ in range(3):
        tag_logs = fetch_trace_logs(client, bl, session_id, "TAG_APPLIED", size=20)
        intent_logs = fetch_trace_logs(client, bl, session_id, "INTENT_DETECTED", size=30)
        tag_rec = latest_trace_event(tag_logs)
        intent_rec = latest_trace_event(intent_logs)
        if tag_rec or intent_rec:
            break
        time.sleep(0.8)

    tag_raw = ""
    tag_reason = ""
    if tag_rec:
        tag_raw = (tag_rec.get("customer_tag") or "").strip()
        extra = tag_rec.get("extra_json")
        if extra:
            try:
                obj = json.loads(extra) if isinstance(extra, str) else extra
                if isinstance(obj, dict):
                    tag_reason = str(obj.get("reason") or "").strip()
            except json.JSONDecodeError:
                tag_reason = ""
    return {
        "trace_tag_raw": tag_raw,
        "trace_tag_norm": normalize_intent_tag(tag_raw),
        "trace_tag_reason": tag_reason,
        "trace_tag_event_id": str(tag_rec.get("id")) if tag_rec else "",
        "trace_detected_intent": (intent_rec.get("detected_intent") or "").strip() if intent_rec else "",
        "trace_intent_event_id": str(intent_rec.get("id")) if intent_rec else "",
    }


def _trace_message_id(record: dict) -> str:
    value = record.get("message_id") or record.get("messageId")
    return str(value).strip() if value is not None else ""


def _trace_id(record: dict) -> str:
    value = record.get("trace_id") or record.get("traceId")
    return str(value).strip() if value is not None else ""


def _trace_status_valid(record: dict) -> bool:
    status = str(record.get("status") or "").strip().lower()
    return status not in {"failed", "failure", "error", "err"}


def _merge_trace_records(*record_sets: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str, str, str], dict] = {}
    for records in record_sets:
        for record in records:
            if not isinstance(record, dict) or not _trace_status_valid(record):
                continue
            key = (
                _trace_message_id(record),
                str(record.get("event_type") or "").strip(),
                str(record.get("stage") or "").strip(),
                str(record.get("trace_id") or record.get("id") or "").strip(),
            )
            merged[key] = record
    return list(merged.values())


def _filter_trace_records_for_message(records: list[dict], message_id: str) -> list[dict]:
    target = str(message_id or "").strip()
    if not target:
        return []
    accepted = {target, f"local_gateway_{target}"}
    matched = [record for record in records if _trace_message_id(record) in accepted]
    return matched


def _filter_trace_records_for_trace_id(records: list[dict], trace_id: str) -> list[dict]:
    target = str(trace_id or "").strip()
    if not target:
        return []
    return [record for record in records if _trace_id(record) == target]


def _find_trace_id(records: list[dict], message_id: str) -> str:
    matched = _filter_trace_records_for_message(records, message_id)
    latest = latest_trace_event([record for record in matched if _trace_id(record)])
    return _trace_id(latest or {})


def _trace_field(record: dict, key: str):
    value = record.get(key)
    if value is not None and (not isinstance(value, str) or value.strip()):
        return value
    extra = record.get("extra_json")
    if isinstance(extra, str):
        try:
            extra = json.loads(extra)
        except json.JSONDecodeError:
            extra = None
    if isinstance(extra, dict):
        return extra.get(key)
    return None


def _latest_non_empty(records: list[dict], key: str):
    for r in sorted(records, key=trace_event_sort_key, reverse=True):
        v = _trace_field(r, key)
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        return v, r
    return None, None


def _extract_trace_id(payload) -> str:
    if isinstance(payload, dict):
        for key in ("trace_id", "traceId"):
            value = payload.get(key)
            if value:
                return str(value).strip()
        for value in payload.values():
            found = _extract_trace_id(value)
            if found:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _extract_trace_id(value)
            if found:
                return found
    return ""


def extract_handoff_reason(conv: dict | None) -> str:
    if not isinstance(conv, dict):
        return ""
    for key in ("handoff_reason", "handoffReason", "transfer_reason", "transferReason"):
        value = conv.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    result_json = conv.get("external_handoff_result_json") or conv.get("externalHandoffResultJson")
    if isinstance(result_json, str) and result_json.strip():
        try:
            result_json = json.loads(result_json)
        except json.JSONDecodeError:
            return result_json.strip()
    if isinstance(result_json, dict):
        for key in ("handoff_reason", "handoffReason", "reason", "message"):
            value = result_json.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    return ""


def resolve_trace_authoritative_fields(
    client: Client,
    bl: int,
    session_id: str,
    whatsapp_id: str = "",
    message_id: str = "",
    trace_id: str = "",
) -> dict:
    # Trace 落库可能有延迟；权威字段按当前 turn 的 trace_id 聚合。
    logs: list[dict] = []
    session_logs: list[dict] = []
    whatsapp_logs: list[dict] = []
    resolved_trace_id = str(trace_id or "").strip()
    for _ in range(5):
        session_logs = fetch_trace_logs_by_session(client, bl, session_id, size=120) if session_id else []
        whatsapp_logs = fetch_trace_logs_by_whatsapp(client, bl, whatsapp_id, size=120) if whatsapp_id else []
        merged = _merge_trace_records(session_logs, whatsapp_logs)
        if not resolved_trace_id:
            resolved_trace_id = _find_trace_id(merged, message_id)
        logs = _filter_trace_records_for_trace_id(merged, resolved_trace_id)
        if logs:
            break
        time.sleep(0.8)

    detected_intent, det_rec = _latest_non_empty(logs, "detected_intent")
    knowledge_hit, kh_rec = _latest_non_empty(logs, "knowledge_hit")
    customer_tag, ct_rec = _latest_non_empty(logs, "customer_tag")
    handoff_flag, ho_rec = _latest_non_empty(logs, "handoff_flag")
    latency_ms, lat_rec = _latest_non_empty(logs, "latency_ms")

    def _to_int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    def _event_id(record: dict | None) -> str:
        if not record:
            return ""
        return str(
            _trace_message_id(record)
            or record.get("trace_id")
            or record.get("id")
            or ""
        )

    return {
        "trace_logs_available": bool(logs),
        "trace_log_count": len(logs),
        "trace_log_fields": sorted({key for record in logs for key in record.keys()}),
        "trace_detected_intent": str(detected_intent or "").strip(),
        "trace_detected_intent_event_id": _event_id(det_rec),
        "trace_knowledge_hit": parse_yes_no(knowledge_hit),
        "trace_knowledge_hit_event_id": _event_id(kh_rec),
        "trace_customer_tag_raw": str(customer_tag or "").strip(),
        "trace_customer_tag_norm": normalize_intent_tag(str(customer_tag or "").strip()),
        "trace_customer_tag_event_id": _event_id(ct_rec),
        "trace_handoff_flag": parse_yes_no(handoff_flag),
        "trace_handoff_flag_event_id": _event_id(ho_rec),
        "trace_latency_ms": _to_int(latency_ms),
        "trace_latency_event_id": _event_id(lat_rec),
        "trace_id": resolved_trace_id,
        "trace_message_id": str(message_id or "").strip(),
    }


def extract_expected_facts(expected_result: str) -> str:
    lines = []
    for ln in (expected_result or "").splitlines():
        t = ln.strip().lstrip("-").lstrip("*").lstrip("•").strip()
        if not t:
            continue
        if "验收要求" in t:
            continue
        if "应结合上下文识别" in t:
            continue
        t = re.sub(r"^[\?\u25cf]+", "", t).strip()
        if len(t) < 4:
            continue
        lines.append(t)
    return "|".join(lines[:8])


def extract_json_object(text: str) -> dict | None:
    t = (text or "").strip()
    if not t:
        return None
    try:
        obj = json.loads(t)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", t)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def llm_judge_intent_tag(
    *,
    case_id: str,
    case_name: str,
    user_cn: str,
    user_en: str,
    actual_tag_raw: str,
    actual_tag_norm: str,
    transcript: str,
) -> tuple[str, str, str, str]:
    """
    Return (is_accurate, recommended_tag, reason, source).
    is_accurate: 是 / 否
    """
    system_prompt = (
        "你是测试评审员。只判断“日志客户标签”是否与聊天上下文一致。"
        "可用标签仅有：已预订未提机、未预订高意向、已提机、NA。"
        "如果上下文没有证据表明用户已预订/已提机，就不能判为已预订未提机或已提机。"
        "仅输出 JSON，不要输出额外文本。"
    )
    user_prompt = (
        f"用例ID: {case_id}\n"
        f"用例名称: {case_name}\n"
        f"用户问题(中文): {user_cn}\n"
        f"用户问题(英文): {user_en}\n"
        f"聊天上下文(含机器人回复):\n{transcript}\n\n"
        f"日志客户标签(raw): {actual_tag_raw}\n"
        f"日志客户标签(normalized): {actual_tag_norm or '空'}\n\n"
        "请输出 JSON："
        '{"is_accurate":"是或否","recommended_tag":"已预订未提机/未预订高意向/已提机/NA","reason":"一句话理由"}'
    )
    txt = chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        project_root=ROOT,
        temperature=0,
    )
    obj = extract_json_object(txt)
    if not obj:
        raise RuntimeError(f"LLM返回非JSON: {txt[:160]}")
    acc = str(obj.get("is_accurate", "")).strip()
    rec = str(obj.get("recommended_tag", "")).strip()
    reason = str(obj.get("reason", "")).strip()
    if acc not in ("是", "否"):
        raise RuntimeError(f"LLM返回is_accurate非法: {obj}")
    if rec in ("", "none", "null", "无", "空"):
        rec = ""
    else:
        rec = normalize_intent_tag(rec)
    if not reason:
        reason = "LLM 未提供理由"
    return acc, rec, reason, "llm"


def llm_judge_handoff(
    *,
    case_id: str,
    case_name: str,
    user_cn: str,
    user_en: str,
    transcript: str,
) -> tuple[bool, str]:
    system_prompt = (
        "You are a QA reviewer. Judge whether the actual conversation transferred "
        "the user to a human agent. Use the conversation evidence only. Return JSON only."
    )
    user_prompt = (
        f"case_id: {case_id}\n"
        f"case_name: {case_name}\n"
        f"user_question_cn: {user_cn}\n"
        f"user_question_en: {user_en}\n"
        f"transcript:\n{transcript}\n\n"
        '{"actual_handoff":"是/否","reason":"one short reason"}. '
        "Use 是 only when the conversation shows an actual handoff, not merely a handoff suggestion or fallback message."
    )
    txt = chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        project_root=ROOT,
        temperature=0,
    )
    obj = extract_json_object(txt)
    if not obj:
        raise RuntimeError(f"LLM returned invalid JSON: {txt[:160]}")
    actual = str(obj.get("actual_handoff", "")).strip()
    reason = str(obj.get("reason", "")).strip() or "LLM did not provide a reason"
    if actual not in ("是", "否"):
        raise RuntimeError(f"LLM returned invalid actual_handoff: {obj}")
    return actual == "是", reason


def has_human_agent_keyword(text: str) -> bool:
    return "human agent" in (text or "").lower()


def llm_judge_reply_semantics(*, transcript: str, reply: str) -> tuple[str, str]:
    prompt = (
        "根据用户与机器人对话，判断机器人英文回复是否语义合理且语言自然。"
        "只输出JSON：{\"is_reasonable\":\"是/否\",\"reason\":\"一句话理由\"}。\n"
        f"对话：\n{transcript}\n\n机器人实际回复：\n{reply}"
    )
    txt = chat(
        [{"role": "system", "content": "你是严格的客服质检员，只输出JSON。"}, {"role": "user", "content": prompt}],
        project_root=ROOT,
        temperature=0,
    )
    obj = extract_json_object(txt) or {}
    value = str(obj.get("is_reasonable", "")).strip()
    if value not in ("是", "否"):
        raise RuntimeError(f"LLM返回语义判断非法: {txt[:160]}")
    return value, str(obj.get("reason", "")).strip()


def faq_match_by_llm(*, question: str, reply: str, faq_rows: list[dict], conditional: bool) -> tuple[bool, str]:
    field = "转人工条件（英文）" if conditional else "问题（英文）"
    candidates = [{"index": i, "text": (r.get(field) or "").strip()} for i, r in enumerate(faq_rows)]
    candidates = [c for c in candidates if c["text"]]
    if not candidates:
        return False, "FAQ候选为空"
    prompt = ("从FAQ候选中选择与用户问题语义最匹配的一条；无匹配时matched_index为-1。仅输出JSON。\n"
              f"字段：{field}\n用户问题：{question}\n候选：{json.dumps(candidates, ensure_ascii=False)}")
    txt = chat([{"role": "system", "content": "你是FAQ语义匹配器，只输出JSON。"}, {"role": "user", "content": prompt}], project_root=ROOT, temperature=0)
    obj = extract_json_object(txt) or {}
    try:
        index = int(obj.get("matched_index", -1))
    except (TypeError, ValueError):
        index = -1
    if index < 0 or index >= len(faq_rows):
        return False, "未匹配FAQ"
    if conditional:
        return True, "FAQ转人工条件匹配"
    feedback = (faq_rows[index].get("业务反馈") or "").strip()
    reply_words = {w.lower() for w in re.findall(r"[A-Za-z0-9]+", reply)}
    feedback_words = {w.lower() for w in re.findall(r"[A-Za-z0-9]+", feedback)}
    overlap = reply_words & feedback_words
    return bool(feedback_words and overlap), f"业务反馈关键词重合{len(overlap)}个"


def last_user_question(messages: list[dict], fallback: str) -> str:
    for message in reversed(messages):
        if (message.get("direction") or "").lower() == "inbound":
            content = (message.get("content") or "").strip()
            if content:
                return content
    return fallback


def build_transcript(messages: list[dict]) -> str:
    lines: list[str] = []
    for m in messages:
        direction = (m.get("direction") or "").lower()
        content = (m.get("content") or "").strip()
        if not content:
            continue
        role = "用户" if direction == "inbound" else ("机器人" if direction == "outbound" else "系统")
        lines.append(f"{role}: {content}")
    return "\n".join(lines[-8:])


def evaluate_case(
    client: Client,
    row: dict,
    channel: str,
    bl: int,
    wait_s: float,
    *,
    enable_llm_intent_tag: bool,
    whatsapp_id: str | None = None,
    sender_name: str | None = None,
    min_outbound_count: int = 0,
    faq_rows: list[dict] | None = None,
) -> dict:
    case_id = (row.get("用例ID") or "").strip()
    case_name = (row.get("用例名称") or "").strip()
    input_cn = (row.get("测试数据") or "").strip()
    input_en = (row.get("测试数据（英文提问）") or "").strip()
    user_text = input_en or input_cn
    expected_handoff = normalize_handoff(row.get("转人工预期") or "")
    expected_facts = extract_expected_facts(row.get("预期结果") or "")
    sheet_actual_tag_raw = (row.get("日志客户标签") or "").strip()
    sheet_actual_tag_norm = normalize_intent_tag(sheet_actual_tag_raw)

    if not user_text:
        return {
            "case_id": case_id,
            "case_name": case_name,
            "是否存在知识库": row.get("是否存在知识库", ""),
            "执行步骤": row.get("执行步骤", ""),
            "预期结果": row.get("预期结果", ""),
            "前置条件": row.get("前置条件", ""),
            "测试数据": row.get("测试数据", ""),
            "测试数据（英文提问）": row.get("测试数据（英文提问）", ""),
            "转人工预期": row.get("转人工预期", ""),
            "执行阶段": row.get("执行阶段", ""),
            "是否使用新会话": row.get("是否使用新会话", ""),
            "status": "SKIP",
            "automation_result": "SKIP",
            "business_result": "NA",
            "reply_check": "NA",
            "knowledge_hit": "NA",
            "handoff_check": "NA",
            "知识库是否命中": "NA",
            "客户标签是否准确": "NA",
            "日志客户标签": "",
            "日志转人工": "",
            "转人工原因": "",
            "转人工是否准确": "NA",
            "实际回复内容（英文）": "",
            "语义是否合理": "NA",
            "回复是否准确": "NA",
            "actual_intent_tag_raw": "",
            "actual_intent_tag_norm": "",
            "actual_intent_tag_source": "none",
            "trace_detected_intent": "",
            "trace_tag_reason": "",
            "conversation_handoff_reason": "",
            "日志客户标签": "",
            "客户标签是否准确": "NA",
            "intent_tag_accuracy": "NA",
            "intent_tag_recommended": "",
            "intent_tag_reason": "empty input",
            "intent_tag_source": "none",
            "expected_handoff": expected_handoff,
            "notes": "empty input",
        }

    wa = whatsapp_id or f"kb-{uuid.uuid4().hex[:10]}@s.whatsapp.net"
    inbound_message_id = f"test-{uuid.uuid4().hex[:12]}"
    st, wh = client.webhook(
        channel,
        wa,
        user_text,
        sender_name=sender_name or case_id or "KB-METRIC",
        message_id=inbound_message_id,
    )
    inbound_trace_id = _extract_trace_id(wh)
    wh_ok = st == 200 and (wh.get("data") or {}).get("status") == "success"
    poll_wait = max(wait_s, 8.0) if expected_handoff == "true" else max(wait_s, 4.0)
    sess, msgs, conv, texts = poll_turn_state(
        client,
        bl,
        wa,
        wait_s=poll_wait,
        expect_handoff=False,
        require_outbound=(expected_handoff != "true" or min_outbound_count > 0),
        min_outbound_count=min_outbound_count,
    )
    task_type = session_task_type(sess)
    conversation_handoff_reason = extract_handoff_reason(conv)
    resp_ms = last_response_ms(msgs, fallback_wait_ms=wait_s * 1000)
    transcript = build_transcript(msgs)
    actual_reply = texts[-1] if texts else ""
    trace_info = resolve_trace_tag_and_intent(client, bl, wa)
    trace_auth = resolve_trace_authoritative_fields(
        client, bl, trace_session_id := session_id_from(sess, msgs, conv),
        whatsapp_id=wa, message_id=inbound_message_id, trace_id=inbound_trace_id,
    )
    if trace_auth["trace_customer_tag_raw"]:
        observed_tag_raw = trace_auth["trace_customer_tag_raw"]
        observed_tag_norm = trace_auth["trace_customer_tag_norm"]
        observed_tag_source = "trace_log.TAG_APPLIED"
    else:
        observed_tag_raw = ""
        observed_tag_norm = ""
        observed_tag_source = "none"

    business_result = "PASS"
    notes: list[str] = []
    if not trace_auth["trace_logs_available"]:
        notes.append("无法读取日志")
    knowledge_hit = "NA"
    handoff_check = "NA"
    trace_handoff_bool = trace_auth["trace_handoff_flag"] == 1 if trace_auth["trace_handoff_flag"] is not None else None
    trace_knowledge_bool = trace_auth["trace_knowledge_hit"] == 1 if trace_auth["trace_knowledge_hit"] is not None else None

    log_handoff_bool = trace_handoff_bool
    handoff_source = "trace.handoff_flag"
    if actual_reply and has_human_agent_keyword(actual_reply):
        log_handoff_bool = True
        handoff_source = "reply.keyword.human_agent"
        notes.append("handoff by reply keyword: human agent")

    actual_handoff_bool = log_handoff_bool
    if actual_handoff_bool is None:
        try:
            actual_handoff_bool, handoff_llm_reason = llm_judge_handoff(
                case_id=case_id,
                case_name=case_name,
                user_cn=input_cn,
                user_en=input_en,
                transcript=transcript,
            )
            handoff_source = "llm"
            notes.append(f"handoff by LLM: {handoff_llm_reason}")
        except (LlmConfigError, RuntimeError) as e:
            handoff_source = "unavailable"
            notes.append(f"handoff LLM unavailable: {str(e)[:160]}")

    if not wh_ok:
        business_result = "FAIL"
        notes.append(f"webhook http={st}")
    else:
        if expected_handoff == "true":
            if actual_handoff_bool is not None:
                handoff_ok_final = actual_handoff_bool
                notes.append(f"handoff source={handoff_source}")
            else:
                handoff_ok_final = None
            handoff_check = "PASS" if handoff_ok_final is True else ("FAIL" if handoff_ok_final is False else "NA")
            knowledge_hit = "NA"
            if handoff_ok_final is None:
                notes.append("handoff result unavailable")
            elif not handoff_ok_final:
                business_result = "FAIL"
                notes.append("actual handoff did not match expected value")
        elif expected_handoff == "false":
            if actual_handoff_bool is not None:
                no_handoff = not actual_handoff_bool
                notes.append(f"handoff source={handoff_source}")
            else:
                no_handoff = None
            handoff_check = "PASS" if no_handoff is True else ("FAIL" if no_handoff is False else "NA")
            if no_handoff is None:
                notes.append("handoff_flag unavailable in trace log")
            elif not no_handoff:
                business_result = "FAIL"
                notes.append("trace handoff_flag indicated handoff")
            elif not texts:
                business_result = "FAIL"
                knowledge_hit = "FAIL"
                notes.append("no outbound reply")
            elif is_handoff_reply_text(texts[-1]):
                business_result = "FAIL"
                knowledge_hit = "FAIL"
                notes.append("handoff template reply for non-handoff case")
            elif trace_knowledge_bool is not None:
                knowledge_hit = "PASS" if trace_knowledge_bool else "FAIL"
                if not trace_knowledge_bool:
                    business_result = "FAIL"
                    notes.append("trace knowledge_hit=0")
            elif expected_facts:
                hit = facts_match(texts, expected_facts)
                knowledge_hit = "PASS" if hit else "FAIL"
                if not hit:
                    business_result = "FAIL"
                    notes.append("missing expected facts")
            else:
                knowledge_hit = "PASS"
        else:
            # 待确认：允许 handoff 或 FAQ 回复
            handoff_cond = actual_handoff_bool
            if handoff_cond is True:
                handoff_check = "PASS"
                knowledge_hit = "NA"
            elif handoff_cond is False:
                handoff_check = "PASS"
                if texts:
                    if trace_knowledge_bool is not None:
                        knowledge_hit = "PASS" if trace_knowledge_bool else "FAIL"
                        if not trace_knowledge_bool:
                            business_result = "FAIL"
                            notes.append("trace knowledge_hit=0 (conditional)")
                    elif expected_facts:
                        hit = facts_match(texts, expected_facts)
                        knowledge_hit = "PASS" if hit else "FAIL"
                        if not hit:
                            business_result = "FAIL"
                            notes.append("conditional case missing expected facts")
                    else:
                        knowledge_hit = "PASS"
                else:
                    business_result = "FAIL"
                    knowledge_hit = "FAIL"
                    notes.append("conditional case with no handoff_flag and no outbound")
            else:
                business_result = "FAIL"
                handoff_check = "NA"
                knowledge_hit = "NA"
                notes.append("handoff_flag unavailable in trace log")

    if observed_tag_raw not in VALID_LOG_CUSTOMER_TAGS:
        observed_tag_norm = ""
        it_acc, it_rec, it_reason, it_source = "NA", "", "日志客户标签为NA", "na"
    elif enable_llm_intent_tag:
        try:
            it_acc, it_rec, it_reason, it_source = llm_judge_intent_tag(
                case_id=case_id,
                case_name=case_name,
                user_cn=input_cn,
                user_en=input_en,
                actual_tag_raw=observed_tag_norm or observed_tag_raw,
                actual_tag_norm=observed_tag_norm,
                transcript=transcript,
            )
        except (LlmConfigError, RuntimeError) as e:
            it_acc, it_rec, it_reason, it_source = "待确认", "", f"llm_unavailable:{str(e)[:160]}", "llm_unavailable"
    else:
        it_acc, it_rec, it_reason, it_source = "待确认", "", "llm_disabled_non_empty_tag", "llm_disabled"

    # Knowledge-hit is an independent trace metric. Do not downgrade it when
    # the bot reply is delayed, missing, or otherwise fails business checks.
    if trace_knowledge_bool is not None:
        knowledge_hit = "PASS" if trace_knowledge_bool else "FAIL"

    semantic_ok = "NA"
    semantic_reason = ""
    if actual_reply:
        try:
            semantic_ok, semantic_reason = llm_judge_reply_semantics(transcript=transcript, reply=actual_reply)
        except (LlmConfigError, RuntimeError) as e:
            semantic_reason = f"语义判断不可用:{str(e)[:160]}"

    if expected_handoff in ("true", "false") and actual_handoff_bool is not None:
        handoff_accuracy = "是" if (actual_handoff_bool == (expected_handoff == "true")) else "否"
    else:
        handoff_accuracy = "NA"
    if expected_handoff == "true" and handoff_accuracy == "是":
        knowledge_hit = "PASS"

    if trace_knowledge_bool is None and faq_rows is not None:
        try:
            is_conditional = bool(re.search(r"-H-C\d+$", case_id))
            matched, match_reason = faq_match_by_llm(
                question=last_user_question(msgs, input_en or input_cn),
                reply=actual_reply,
                faq_rows=faq_rows,
                conditional=is_conditional,
            )
            if is_conditional:
                matched = matched and handoff_accuracy == "是"
            knowledge_hit = "PASS" if matched else "FAIL"
            notes.append(match_reason)
        except (LlmConfigError, RuntimeError) as e:
            knowledge_hit = "NA"
            notes.append(f"知识库语义匹配不可用:{str(e)[:160]}")

    if expected_handoff == "true" and handoff_accuracy == "是":
        knowledge_hit = "PASS"
    if not actual_reply:
        components = (knowledge_hit, it_acc, handoff_accuracy)
        if all(value == "是" or value == "PASS" for value in components):
            reply_accuracy = "是"
        elif any(value == "NA" for value in components):
            reply_accuracy = "NA"
        else:
            reply_accuracy = "否"
    elif semantic_ok in ("是", "否") and handoff_accuracy in ("是", "否"):
        reply_accuracy = "是" if semantic_ok == "是" and handoff_accuracy == "是" else "否"
    else:
        reply_accuracy = "NA"

    return {
        "case_id": case_id,
        "case_name": case_name,
        "是否存在知识库": row.get("是否存在知识库", ""),
        "执行步骤": row.get("执行步骤", ""),
        "预期结果": row.get("预期结果", ""),
        "前置条件": row.get("前置条件", ""),
        "测试数据": row.get("测试数据", ""),
        "测试数据（英文提问）": row.get("测试数据（英文提问）", ""),
        "转人工预期": row.get("转人工预期", ""),
        "执行阶段": row.get("执行阶段", ""),
        "是否使用新会话": row.get("是否使用新会话", ""),
        "input_cn": input_cn,
        "input_en": input_en,
        "expected_handoff": expected_handoff,
        "status": "PASS" if business_result == "PASS" and wh_ok else "FAIL",
        "automation_result": "PASS" if wh_ok else "FAIL",
        "business_result": business_result,
        "reply_check": "PASS" if business_result == "PASS" else "FAIL",
        "knowledge_hit": knowledge_hit,
        "handoff_check": handoff_check,
        "知识库是否命中": "是" if knowledge_hit == "PASS" else ("否" if knowledge_hit == "FAIL" else "NA"),
        "知识库是否命中正确": "",
        "客户标签是否准确": it_acc,
        "回复是否准确": reply_accuracy,
        "语义是否合理": semantic_ok,
        "备注": "; ".join(notes + ([semantic_reason] if semantic_reason else [])) if notes or semantic_reason else "",
        "actual_intent_tag_raw": observed_tag_raw,
        "actual_intent_tag_norm": observed_tag_norm,
        "actual_intent_tag_source": observed_tag_source,
        "trace_detected_intent": trace_auth["trace_detected_intent"],
        "trace_knowledge_hit": trace_auth["trace_knowledge_hit"] if trace_auth["trace_knowledge_hit"] is not None else "",
        "trace_handoff_flag": trace_auth["trace_handoff_flag"] if trace_auth["trace_handoff_flag"] is not None else "",
        "trace_latency_ms": trace_auth["trace_latency_ms"] if trace_auth["trace_latency_ms"] is not None else "",
        "conversation_handoff_reason": conversation_handoff_reason,
        "trace_tag_reason": trace_info["trace_tag_reason"],
        "trace_tag_event_id": trace_auth["trace_customer_tag_event_id"] or trace_info["trace_tag_event_id"],
        "trace_intent_event_id": trace_auth["trace_detected_intent_event_id"] or trace_info["trace_intent_event_id"],
        "trace_knowledge_hit_event_id": trace_auth["trace_knowledge_hit_event_id"],
        "trace_handoff_flag_event_id": trace_auth["trace_handoff_flag_event_id"],
        "trace_latency_event_id": trace_auth["trace_latency_event_id"],
        "trace_id": trace_auth["trace_id"],
        "trace_message_id": trace_auth["trace_message_id"],
        "日志客户标签": observed_tag_raw if observed_tag_raw in VALID_LOG_CUSTOMER_TAGS else "NA",
        "客户标签是否准确": it_acc,
        "日志转人工": yesno_text(log_handoff_bool) if log_handoff_bool is not None else "NA",
        "转人工原因": conversation_handoff_reason,
        "转人工是否准确": handoff_accuracy,
        "实际回复内容（英文）": actual_reply,
        "语义是否合理": semantic_ok,
        "服务端真实耗时": trace_auth["trace_latency_ms"] if trace_auth["trace_latency_ms"] is not None else "",
        "接口响应时长": int(resp_ms) if resp_ms is not None else "",
        "intent_tag_accuracy": it_acc,
        "intent_tag_recommended": it_rec,
        "intent_tag_reason": it_reason,
        "intent_tag_source": it_source,
        "response_ms": trace_auth["trace_latency_ms"] if trace_auth["trace_latency_ms"] is not None else (int(resp_ms) if resp_ms is not None else ""),
        "task_type": task_type,
        "whatsapp_id": wa,
        "session_id": session_id_from(sess, msgs, conv),
        "outbound_preview": texts[-1][:160] if texts else "",
        "outbound_count": len(texts),
        "notes": "; ".join(notes) if notes else "OK",
    }


def result_fields() -> list[str]:
    return [
        "case_id", "case_name", "执行步骤", "预期结果", "前置条件", "测试数据", "测试数据（英文提问）", "转人工预期", "是否存在知识库", "执行阶段", "是否使用新会话", "input_cn", "input_en", "expected_handoff",
        "status", "automation_result", "business_result", "reply_check",
        "knowledge_hit", "handoff_check", "知识库是否命中", "知识库是否命中正确", "日志客户标签", "客户标签是否准确",
        "日志转人工", "转人工原因", "转人工是否准确", "实际回复内容（英文）", "语义是否合理", "回复是否准确",
        "服务端真实耗时", "接口响应时长", "备注",
        "actual_intent_tag_raw", "actual_intent_tag_norm", "actual_intent_tag_source",
        "intent_tag_accuracy", "intent_tag_recommended", "intent_tag_source", "intent_tag_reason",
        "trace_detected_intent", "trace_knowledge_hit", "trace_handoff_flag", "trace_latency_ms", "conversation_handoff_reason",
        "trace_tag_reason", "trace_tag_event_id", "trace_intent_event_id",
        "trace_knowledge_hit_event_id", "trace_handoff_flag_event_id", "trace_latency_event_id", "trace_message_id",
        "trace_id",
        "response_ms", "task_type", "whatsapp_id", "session_id", "outbound_preview", "outbound_count", "notes",
    ]


def load_result_case_ids() -> set[str]:
    if not RESULTS_JSONL.exists():
        return set()
    case_ids = set()
    with RESULTS_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                payload = json.loads(line)
                if payload.get("case_id"):
                    case_ids.add(payload["case_id"])
    return case_ids


def append_case_result(result: dict, batch_index: int, source_index: int) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    payload = {
        "batch_index": batch_index,
        "source_index": source_index,
        "executed_at": datetime.now().isoformat(timespec="seconds"),
        **result,
    }
    with RESULTS_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        f.flush()


def write_batch_state(
    batch_index: int,
    start_index: int,
    end_index: int,
    expected_count: int,
    executed_count: int,
    status: str,
    *,
    error: str = "",
    failed_case_id: str = "",
) -> Path:
    BATCHES_DIR.mkdir(parents=True, exist_ok=True)
    path = BATCHES_DIR / f"batch-{batch_index:03d}.json"
    temp_path = path.with_suffix(".json.tmp")
    payload = {
        "batch_index": batch_index,
        "start_index": start_index,
        "end_index": end_index,
        "expected_count": expected_count,
        "executed_count": executed_count,
        "status": status,
        "error": error,
        "failed_case_id": failed_case_id,
        "result_file": str(RESULTS_JSONL.relative_to(ROOT)).replace("\\", "/"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)
    return path


def cleanup_process_documents(batch_index: int) -> None:
    for path in (
        BATCHES_DIR / f"batch-{batch_index:03d}.json.tmp",
        REPORTS / f"batch-{batch_index:03d}.running.json",
    ):
        if path.exists():
            path.unlink()


def main():
    parser = argparse.ArgumentParser(description="Hot70 L2 指标专项测试：单次执行一个批次")
    parser.add_argument("--source", default=str(SOURCE_CSV))
    parser.add_argument("--batch-index", type=int, required=True, help="从 1 开始的批次编号，每批固定最多 10 条")
    parser.add_argument("--channel", default="ch_wa_01")
    parser.add_argument("--business-line-id", type=int, default=1)
    parser.add_argument("--wait", type=float, default=50.0)
    parser.add_argument("--disable-llm-intent-tag", action="store_true")
    args = parser.parse_args()

    if args.batch_index < 1:
        raise ValueError("--batch-index must be >= 1")
    source = Path(args.source)
    if not source.is_absolute():
        source = (ROOT / source).resolve()
    if not source.exists():
        raise FileNotFoundError(f"source csv not found: {source}")

    rows = load_rows(source)
    faq_rows = load_rows(FAQ_CSV) if FAQ_CSV.exists() else []
    if not rows:
        print("no rows loaded")
        return

    batch_size = 10
    batch_start = (args.batch_index - 1) * batch_size
    if batch_start >= len(rows):
        raise ValueError(f"batch {args.batch_index} is outside source range")
    batch_rows = rows[batch_start : batch_start + batch_size]
    batch_end = batch_start + len(batch_rows)
    rows_by_id = {(r.get("用例ID") or "").strip(): r for r in rows}
    batch_case_ids = {(r.get("用例ID") or "").strip() for r in batch_rows}
    for row in batch_rows:
        case_id = (row.get("用例ID") or "").strip()
        if case_id not in rows_by_id:
            raise RuntimeError(f"missing case id: {case_id}")

    duplicate_ids = batch_case_ids & load_result_case_ids()
    if duplicate_ids:
        raise RuntimeError(f"results already exist for batch cases: {sorted(duplicate_ids)}")
    batch_path = BATCHES_DIR / f"batch-{args.batch_index:03d}.json"
    if batch_path.exists():
        raise RuntimeError(f"batch state already exists: {batch_path}")

    write_batch_state(args.batch_index, batch_start + 1, batch_end, len(batch_rows), 0, "running")
    client = Client(DEFAULT_BASE, DEFAULT_USER, DEFAULT_PASS)
    if not client.login(DEFAULT_USER, DEFAULT_PASS):
        write_batch_state(args.batch_index, batch_start + 1, batch_end, len(batch_rows), 0, "interrupted", error="LOGIN FAILED")
        raise RuntimeError("LOGIN FAILED")

    enable_llm_intent_tag = not args.disable_llm_intent_tag
    completed = 0
    case_id = ""
    seen_chain_whatsapp_ids: set[str] = set()
    seen_chain_session_ids: set[str] = set()
    try:
        for offset, row in enumerate(batch_rows):
            source_index = batch_start + offset + 1
            case_id = (row.get("用例ID") or "").strip()
            match = CASE_ID_RE.match(case_id)
            if match and match.group(2).startswith("H-C"):
                prerequisite = rows_by_id[f"{match.group(1)}-N"]
                chain_whatsapp_id = f"kb-{uuid.uuid4().hex[:16]}@s.whatsapp.net"
                if chain_whatsapp_id in seen_chain_whatsapp_ids:
                    raise RuntimeError(f"duplicate chain whatsapp_id: {chain_whatsapp_id}")
                prefill = evaluate_case(
                    client, prerequisite, args.channel, args.business_line_id, args.wait,
                    enable_llm_intent_tag=enable_llm_intent_tag,
                    whatsapp_id=chain_whatsapp_id,
                    sender_name=f"{match.group(1)}-N",
                    faq_rows=faq_rows,
                )
                prefill_wa = (prefill.get("whatsapp_id") or "").strip()
                prefill_session = (prefill.get("session_id") or "").strip()
                if prefill_wa != chain_whatsapp_id:
                    raise RuntimeError(
                        f"prefill whatsapp_id mismatch for {case_id}: "
                        f"expected={chain_whatsapp_id} actual={prefill_wa}"
                    )
                if int(prefill.get("outbound_count") or 0) <= 0:
                    raise RuntimeError(f"prefill AI reply not observed before follow-up: {case_id}")
                if prefill_session and prefill_session in seen_chain_session_ids:
                    raise RuntimeError(f"session reused across H-C chains: {case_id} session={prefill_session}")
                result = evaluate_case(
                    client, row, args.channel, args.business_line_id, args.wait,
                    enable_llm_intent_tag=enable_llm_intent_tag,
                    whatsapp_id=chain_whatsapp_id,
                    sender_name=case_id,
                    min_outbound_count=int(prefill.get("outbound_count") or 0),
                    faq_rows=faq_rows,
                )
                result_wa = (result.get("whatsapp_id") or "").strip()
                result_session = (result.get("session_id") or "").strip()
                if result_wa != chain_whatsapp_id:
                    raise RuntimeError(
                        f"follow-up whatsapp_id mismatch for {case_id}: "
                        f"expected={chain_whatsapp_id} actual={result_wa}"
                    )
                if prefill_session and result_session and result_session != prefill_session:
                    raise RuntimeError(
                        f"session changed within H-C chain: {case_id} "
                        f"prefill={prefill_session} followup={result_session}"
                    )
                seen_chain_whatsapp_ids.add(chain_whatsapp_id)
                if prefill_session:
                    seen_chain_session_ids.add(prefill_session)
            else:
                result = evaluate_case(
                    client, row, args.channel, args.business_line_id, args.wait,
                    enable_llm_intent_tag=enable_llm_intent_tag,
                    sender_name=case_id or None,
                    faq_rows=faq_rows,
                )
                result_wa = (result.get("whatsapp_id") or "").strip()
                result_session = (result.get("session_id") or "").strip()
                if result_wa and result_wa in seen_chain_whatsapp_ids:
                    raise RuntimeError(f"session whatsapp_id reused: {case_id} whatsapp_id={result_wa}")
                if result_session and result_session in seen_chain_session_ids:
                    raise RuntimeError(f"session reused across cases: {case_id} session={result_session}")
                if result_wa:
                    seen_chain_whatsapp_ids.add(result_wa)
                if result_session:
                    seen_chain_session_ids.add(result_session)
            append_case_result(result, args.batch_index, source_index)
            completed += 1
            write_batch_state(args.batch_index, batch_start + 1, batch_end, len(batch_rows), completed, "running")
            print(f"progress {completed}/{len(batch_rows)}", flush=True)
            time.sleep(0.1)
    except Exception as exc:
        write_batch_state(
            args.batch_index, batch_start + 1, batch_end, len(batch_rows), completed,
            "interrupted", error=str(exc), failed_case_id=case_id,
        )
        raise RuntimeError(f"batch {args.batch_index} stopped at {case_id}: {exc}") from exc

    write_batch_state(args.batch_index, batch_start + 1, batch_end, len(batch_rows), completed, "completed")
    cleanup_process_documents(args.batch_index)
    print(f"batch={args.batch_index} status=completed executed={completed}")
    print(f"results={RESULTS_JSONL}")
    print(f"batch_state={batch_path}")

if __name__ == "__main__":
    main()
