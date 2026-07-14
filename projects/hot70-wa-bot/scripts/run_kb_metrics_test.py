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
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from case_executor import is_handoff_reply_text, poll_turn_state, verify_local_handoff
from l2_eval_core import facts_match, first_response_ms, session_id_from, session_task_type
from run_bundle import run_dir
from run_test_suite import DEFAULT_BASE, DEFAULT_PASS, DEFAULT_USER, Client

ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
if str(FRAMEWORK_ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_ROOT / "lib"))

from llm_client import LlmConfigError, chat  # noqa: E402

REPORTS = ROOT / "reports"
SOURCE_CSV = ROOT / "prd" / "Hot70_机器人_知识库指标测试.csv"
ALLOWED_INTENT_TAGS = {"已预定未提机", "未预定高意向", "未预定低意向", "已提交"}
INTENT_TAG_ALIASES = {
    "已提机": "已提交",
    "已提货": "已提交",
    "已取机": "已提交",
    "picked_up": "已提交",
    "already_picked_up": "已提交",
    "已预定": "已预定未提机",
    "已预约": "已预定未提机",
    "已预订未提机": "已预定未提机",
    "未预订高意向": "未预定高意向",
    "未预订低意向": "未预定低意向",
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


def conversation_tag(conv: dict | None) -> str:
    if not conv:
        return ""
    tags = conv.get("tags")
    if isinstance(tags, list):
        for t in tags:
            if isinstance(t, str):
                n = normalize_intent_tag(t)
                if n:
                    return n
    for k in ("customer_tag", "customerTag", "intent_tag", "intentTag"):
        v = conv.get(k)
        if isinstance(v, str):
            n = normalize_intent_tag(v)
            if n:
                return n
    return ""


def parse_trace_records(payload: dict) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    d = payload.get("data") or {}
    if isinstance(d, dict):
        d2 = d.get("data") or {}
        if isinstance(d2, dict):
            recs = d2.get("records")
            if isinstance(recs, list):
                return recs
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


def fetch_trace_logs_by_session(client: Client, bl: int, session_id: str, size: int = 100) -> list[dict]:
    sid = quote(session_id, safe="")
    path = f"/business-lines/{bl}/trace-logs?session_id={sid}&page=1&size={size}"
    st, data = client._call("GET", path)
    if st != 200:
        return []
    return parse_trace_records(data)


def trace_event_sort_key(rec: dict):
    def _to_int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    return (
        _to_int(rec.get("event_time")),
        _to_int(rec.get("created_at")),
        _to_int(rec.get("id")),
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


def _latest_non_empty(records: list[dict], key: str):
    for r in sorted(records, key=trace_event_sort_key, reverse=True):
        v = r.get(key)
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        return v, r
    return None, None


def resolve_trace_authoritative_fields(client: Client, bl: int, session_id: str) -> dict:
    # 轮询几次，给异步落库留时间
    logs: list[dict] = []
    for _ in range(3):
        logs = fetch_trace_logs_by_session(client, bl, session_id, size=120)
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

    return {
        "trace_detected_intent": str(detected_intent or "").strip(),
        "trace_detected_intent_event_id": str((det_rec or {}).get("id") or ""),
        "trace_knowledge_hit": _to_int(knowledge_hit),
        "trace_knowledge_hit_event_id": str((kh_rec or {}).get("id") or ""),
        "trace_customer_tag_raw": str(customer_tag or "").strip(),
        "trace_customer_tag_norm": normalize_intent_tag(str(customer_tag or "").strip()),
        "trace_customer_tag_event_id": str((ct_rec or {}).get("id") or ""),
        "trace_handoff_flag": _to_int(handoff_flag),
        "trace_handoff_flag_event_id": str((ho_rec or {}).get("id") or ""),
        "trace_latency_ms": _to_int(latency_ms),
        "trace_latency_event_id": str((lat_rec or {}).get("id") or ""),
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


def infer_expected_tag_rule(user_cn: str, user_en: str, transcript: str) -> str:
    cn = (user_cn or "") + " " + (transcript or "")
    en = ((user_en or "") + " " + (transcript or "")).lower()
    if any(k in cn for k in ("已经提机", "已提机", "已提货", "已取机")) or any(
        k in en for k in ("already picked up", "have already picked up", "picked up")
    ):
        return "已提交"
    preordered = any(k in cn for k in ("已经预订", "已预订", "已经预约", "已预约")) or any(
        k in en for k in ("already preordered", "already pre-order", "already booked")
    )
    not_picked = any(k in cn for k in ("未提机", "没提机", "尚未提机", "还未提机", "还没提")) or any(
        k in en for k in ("not picked up", "haven't picked up", "have not picked up")
    )
    if preordered and not_picked:
        return "已预定未提机"
    if any(k in cn for k in ("只想领福利", "只领福利", "先领福利")) or any(
        k in en for k in ("only want benefits", "only want to claim", "just want benefits")
    ):
        return "未预定低意向"
    if any(k in cn for k in ("分期怎么买", "想分期", "我想买", "怎么买", "想购买", "想入手", "咨询配置", "问配置")) or any(
        k in en for k in (
            "how can i buy in installments",
            "how to buy in installments",
            "can i pay in installments",
            "i want to buy",
            "i want to purchase",
            "specification",
            "specifications",
        )
    ):
        return "未预定高意向"
    return ""


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
        "你是测试评审员。只判断“实际识别的意图标签”是否与聊天上下文一致。"
        "可用标签仅有：已预定未提机、未预定高意向、未预定低意向、已提交、空。"
        "如果上下文没有证据表明用户已预定/已提机，就不能判为已预定未提机或已提交。"
        "仅输出 JSON，不要输出额外文本。"
    )
    user_prompt = (
        f"用例ID: {case_id}\n"
        f"用例名称: {case_name}\n"
        f"用户问题(中文): {user_cn}\n"
        f"用户问题(英文): {user_en}\n"
        f"聊天上下文(含机器人回复):\n{transcript}\n\n"
        f"实际识别的意图标签(raw): {actual_tag_raw}\n"
        f"实际识别的意图标签(normalized): {actual_tag_norm or '空'}\n\n"
        "请输出 JSON："
        '{"is_accurate":"是或否","recommended_tag":"已预定未提机/未预定高意向/未预定低意向/已提交/空","reason":"一句话理由"}'
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


def rule_judge_intent_tag(
    *,
    user_cn: str,
    user_en: str,
    transcript: str,
    actual_tag_norm: str,
) -> tuple[str, str, str, str]:
    expected = infer_expected_tag_rule(user_cn, user_en, transcript)
    accurate = (actual_tag_norm == expected) if expected else (actual_tag_norm == "")
    acc = "是" if accurate else "否"
    reason = f"rule_expected={expected or '空'}; actual={actual_tag_norm or '空'}"
    return acc, expected, reason, "rule_fallback"


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
) -> dict:
    case_id = (row.get("用例ID") or "").strip()
    case_name = (row.get("用例名称") or "").strip()
    input_cn = (row.get("测试数据") or "").strip()
    input_en = (row.get("测试数据（英文提问）") or "").strip()
    user_text = input_en or input_cn
    expected_handoff = normalize_handoff(row.get("转人工预期") or "")
    expected_facts = extract_expected_facts(row.get("预期结果") or "")
    sheet_actual_tag_raw = (row.get("实际识别的意图标签") or "").strip()
    sheet_actual_tag_norm = normalize_intent_tag(sheet_actual_tag_raw)

    if not user_text:
        return {
            "case_id": case_id,
            "case_name": case_name,
            "status": "SKIP",
            "automation_result": "SKIP",
            "business_result": "NA",
            "reply_check": "NA",
            "knowledge_hit": "NA",
            "handoff_check": "NA",
            "知识库是否命中": "NA",
            "意图标签是否准确": "NA",
            "回复是否准确": "NA",
            "actual_intent_tag_raw": "",
            "actual_intent_tag_norm": "",
            "actual_intent_tag_source": "none",
            "trace_detected_intent": "",
            "trace_tag_reason": "",
            "实际识别的意图标签": "",
            "意图标签是否准确": "NA",
            "intent_tag_accuracy": "NA",
            "intent_tag_recommended": "",
            "intent_tag_reason": "empty input",
            "intent_tag_source": "none",
            "expected_handoff": expected_handoff,
            "notes": "empty input",
        }

    wa = f"kb-{uuid.uuid4().hex[:10]}@s.whatsapp.net"
    st, wh = client.webhook(channel, wa, user_text, sender_name=case_id or "KB-METRIC")
    wh_ok = st == 200 and (wh.get("data") or {}).get("status") == "success"
    poll_wait = max(wait_s, 8.0) if expected_handoff == "true" else max(wait_s, 4.0)
    sess, msgs, conv, texts = poll_turn_state(
        client,
        bl,
        wa,
        wait_s=poll_wait,
        expect_handoff=(expected_handoff == "true"),
        require_outbound=(expected_handoff != "true"),
    )
    task_type = session_task_type(sess)
    handoff_ok, handoff_notes = verify_local_handoff(conv)
    resp_ms = first_response_ms(msgs, fallback_wait_ms=wait_s * 1000)
    transcript = build_transcript(msgs)
    trace_info = resolve_trace_tag_and_intent(client, bl, wa)
    trace_auth = resolve_trace_authoritative_fields(client, bl, wa)
    conv_tag_norm = conversation_tag(conv)
    if trace_auth["trace_customer_tag_raw"]:
        observed_tag_raw = trace_auth["trace_customer_tag_raw"]
        observed_tag_norm = trace_auth["trace_customer_tag_norm"]
        observed_tag_source = "trace_log.TAG_APPLIED"
    elif conv_tag_norm:
        observed_tag_raw = conv_tag_norm
        observed_tag_norm = conv_tag_norm
        observed_tag_source = "conversations.tags"
    else:
        observed_tag_raw = ""
        observed_tag_norm = ""
        observed_tag_source = "none"

    business_result = "PASS"
    notes: list[str] = []
    knowledge_hit = "NA"
    handoff_check = "NA"
    trace_handoff_bool = trace_auth["trace_handoff_flag"] == 1 if trace_auth["trace_handoff_flag"] is not None else None
    trace_knowledge_bool = trace_auth["trace_knowledge_hit"] == 1 if trace_auth["trace_knowledge_hit"] is not None else None

    if not wh_ok:
        business_result = "FAIL"
        notes.append(f"webhook http={st}")
    else:
        if expected_handoff == "true":
            if trace_handoff_bool is not None:
                handoff_ok_final = trace_handoff_bool
                notes.append("handoff by trace_handoff_flag")
            else:
                handoff_ok_final = handoff_ok
            handoff_check = "PASS" if handoff_ok_final else "FAIL"
            knowledge_hit = "NA"
            if not handoff_ok_final:
                business_result = "FAIL"
                notes.append("expected LOCAL handoff")
                notes.extend(handoff_notes)
        elif expected_handoff == "false":
            if trace_handoff_bool is not None:
                no_handoff = not trace_handoff_bool
                notes.append("handoff by trace_handoff_flag")
            else:
                no_handoff = not handoff_ok
            handoff_check = "PASS" if no_handoff else "FAIL"
            if not no_handoff:
                business_result = "FAIL"
                notes.append("unexpected LOCAL handoff")
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
            handoff_cond = trace_handoff_bool if trace_handoff_bool is not None else handoff_ok
            if handoff_cond:
                handoff_check = "PASS"
                knowledge_hit = "NA"
            elif texts:
                handoff_check = "PASS"
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
                handoff_check = "FAIL"
                knowledge_hit = "FAIL"
                notes.append("conditional case with no handoff and no outbound")

    if enable_llm_intent_tag:
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
            it_acc, it_rec, it_reason, it_source = rule_judge_intent_tag(
                user_cn=input_cn,
                user_en=input_en,
                transcript=transcript,
                actual_tag_norm=observed_tag_norm,
            )
            it_reason = f"{it_reason}; llm_error={str(e)[:160]}"
    else:
        it_acc, it_rec, it_reason, it_source = rule_judge_intent_tag(
            user_cn=input_cn,
            user_en=input_en,
            transcript=transcript,
            actual_tag_norm=observed_tag_norm,
        )

    return {
        "case_id": case_id,
        "case_name": case_name,
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
        "意图标签是否准确": it_acc,
        "回复是否准确": "是" if business_result == "PASS" else "否",
        "actual_intent_tag_raw": observed_tag_raw,
        "actual_intent_tag_norm": observed_tag_norm,
        "actual_intent_tag_source": observed_tag_source,
        "trace_detected_intent": trace_auth["trace_detected_intent"] or trace_info["trace_detected_intent"],
        "trace_knowledge_hit": trace_auth["trace_knowledge_hit"] if trace_auth["trace_knowledge_hit"] is not None else "",
        "trace_handoff_flag": trace_auth["trace_handoff_flag"] if trace_auth["trace_handoff_flag"] is not None else "",
        "trace_latency_ms": trace_auth["trace_latency_ms"] if trace_auth["trace_latency_ms"] is not None else "",
        "trace_tag_reason": trace_info["trace_tag_reason"],
        "trace_tag_event_id": trace_auth["trace_customer_tag_event_id"] or trace_info["trace_tag_event_id"],
        "trace_intent_event_id": trace_auth["trace_detected_intent_event_id"] or trace_info["trace_intent_event_id"],
        "trace_knowledge_hit_event_id": trace_auth["trace_knowledge_hit_event_id"],
        "trace_handoff_flag_event_id": trace_auth["trace_handoff_flag_event_id"],
        "trace_latency_event_id": trace_auth["trace_latency_event_id"],
        "实际识别的意图标签": observed_tag_norm or observed_tag_raw,
        "意图标签是否准确": it_acc,
        "intent_tag_accuracy": it_acc,
        "intent_tag_recommended": it_rec,
        "intent_tag_reason": it_reason,
        "intent_tag_source": it_source,
        "response_ms": trace_auth["trace_latency_ms"] if trace_auth["trace_latency_ms"] is not None else (int(resp_ms) if resp_ms is not None else ""),
        "task_type": task_type,
        "whatsapp_id": wa,
        "session_id": session_id_from(sess, msgs, conv),
        "outbound_preview": texts[-1][:160] if texts else "",
        "notes": "; ".join(notes) if notes else "OK",
    }


def summarize(results: list[dict]) -> dict:
    executed = [r for r in results if r.get("status") != "SKIP"]
    total = len(results)
    pass_n = sum(1 for r in executed if r.get("business_result") == "PASS")
    fail_n = sum(1 for r in executed if r.get("business_result") == "FAIL")
    skip_n = total - len(executed)

    def _yn(val: str) -> str:
        v = (val or "").strip()
        if v in ("是", "yes", "YES", "true", "TRUE", "PASS"):
            return "是"
        if v in ("否", "no", "NO", "false", "FALSE", "FAIL"):
            return "否"
        return ""

    kb_rows = [r for r in executed if _yn(r.get("知识库是否命中", "") or r.get("knowledge_hit", "")) in ("是", "否")]
    kb_pass = sum(1 for r in kb_rows if _yn(r.get("知识库是否命中", "") or r.get("knowledge_hit", "")) == "是")
    kb_rate = (kb_pass / len(kb_rows) * 100) if kb_rows else None

    reply_rows = [r for r in executed if _yn(r.get("回复是否准确", "") or r.get("reply_check", "")) in ("是", "否")]
    reply_pass = sum(1 for r in reply_rows if _yn(r.get("回复是否准确", "") or r.get("reply_check", "")) == "是")
    reply_rate = (reply_pass / len(reply_rows) * 100) if reply_rows else None

    # 按需求：转人工准确率使用【回复是否准确】计算
    ho_rows = reply_rows
    ho_pass = reply_pass
    ho_rate = (ho_pass / len(ho_rows) * 100) if ho_rows else None

    intent_rows = [r for r in executed if _yn(r.get("意图标签是否准确", "") or r.get("intent_tag_accuracy", "")) in ("是", "否")]
    intent_ok = sum(1 for r in intent_rows if _yn(r.get("意图标签是否准确", "") or r.get("intent_tag_accuracy", "")) == "是")
    intent_rate = (intent_ok / len(intent_rows) * 100) if intent_rows else None
    intent_llm_n = sum(1 for r in intent_rows if r.get("intent_tag_source") == "llm")
    intent_rule_n = sum(1 for r in intent_rows if r.get("intent_tag_source") == "rule_fallback")

    resp_vals = [float(r["response_ms"]) for r in executed if str(r.get("response_ms", "")).isdigit()]
    avg_resp = (sum(resp_vals) / len(resp_vals)) if resp_vals else None

    return {
        "total": total,
        "executed": len(executed),
        "pass": pass_n,
        "fail": fail_n,
        "skip": skip_n,
        "kb_sample": len(kb_rows),
        "kb_pass": kb_pass,
        "kb_hit_rate": round(kb_rate, 2) if kb_rate is not None else None,
        "reply_sample": len(reply_rows),
        "reply_pass": reply_pass,
        "reply_accuracy": round(reply_rate, 2) if reply_rate is not None else None,
        "handoff_sample": len(ho_rows),
        "handoff_pass": ho_pass,
        "handoff_accuracy": round(ho_rate, 2) if ho_rate is not None else None,
        "intent_tag_sample": len(intent_rows),
        "intent_tag_pass": intent_ok,
        "intent_tag_accuracy": round(intent_rate, 2) if intent_rate is not None else None,
        "intent_tag_llm": intent_llm_n,
        "intent_tag_rule_fallback": intent_rule_n,
        "avg_response_ms": round(avg_resp, 1) if avg_resp is not None else None,
    }


def write_outputs(run_id: str, executed_at: str, source_csv: Path, results: list[dict], summary: dict) -> dict[str, Path]:
    REPORTS.mkdir(parents=True, exist_ok=True)
    out_dir = run_dir(run_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    result_csv = out_dir / "kb-metrics-results.csv"
    summary_json = out_dir / "kb-metrics-summary.json"
    report_md = out_dir / "kb-metrics-report.md"

    fields = [
        "case_id", "case_name", "input_cn", "input_en", "expected_handoff",
        "status", "automation_result", "business_result", "reply_check",
        "knowledge_hit", "handoff_check", "知识库是否命中", "意图标签是否准确", "回复是否准确",
        "actual_intent_tag_raw", "actual_intent_tag_norm", "actual_intent_tag_source",
        "intent_tag_accuracy", "intent_tag_recommended", "intent_tag_source", "intent_tag_reason",
        "trace_detected_intent", "trace_knowledge_hit", "trace_handoff_flag", "trace_latency_ms",
        "trace_tag_reason", "trace_tag_event_id", "trace_intent_event_id",
        "trace_knowledge_hit_event_id", "trace_handoff_flag_event_id", "trace_latency_event_id",
        "response_ms", "task_type", "whatsapp_id", "session_id", "outbound_preview", "notes",
    ]
    with result_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(results)

    summary_payload = {
        "run_id": run_id,
        "executed_at": executed_at,
        "source_csv": str(source_csv.relative_to(ROOT)).replace("\\", "/"),
        **summary,
    }
    summary_json.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    fail_top = [r for r in results if r.get("business_result") == "FAIL"][:30]
    lines = [
        "# Hot70 知识库指标专项测试报告（L2）",
        "",
        f"> {executed_at}",
        "",
        f"- source: `{source_csv.relative_to(ROOT).as_posix()}`",
        f"- run_id: `{run_id}`",
        "",
        "## 汇总",
        "",
        f"- 执行：{summary['executed']} / {summary['total']}（skip={summary['skip']}）",
        f"- 业务结果：PASS={summary['pass']} FAIL={summary['fail']}",
        f"- 知识库命中率：{summary['kb_hit_rate']}% ({summary['kb_pass']}/{summary['kb_sample']})" if summary["kb_hit_rate"] is not None else "- 知识库命中率：—",
        f"- 回复准确率：{summary['reply_accuracy']}% ({summary['reply_pass']}/{summary['reply_sample']})" if summary["reply_accuracy"] is not None else "- 回复准确率：—",
        f"- 转人工准确率：{summary['handoff_accuracy']}% ({summary['handoff_pass']}/{summary['handoff_sample']})" if summary["handoff_accuracy"] is not None else "- 转人工准确率：—",
        f"- 标签准确率：{summary['intent_tag_accuracy']}% ({summary['intent_tag_pass']}/{summary['intent_tag_sample']})" if summary["intent_tag_accuracy"] is not None else "- 标签准确率：—",
        f"- 意图标签判定来源：LLM={summary['intent_tag_llm']}，规则回退={summary['intent_tag_rule_fallback']}",
        f"- 平均响应：{summary['avg_response_ms']} ms" if summary["avg_response_ms"] is not None else "- 平均响应：—",
        "",
        "## 指标计算",
        "",
        "- 知识库命中率 = `知识库是否命中=是` 用例数 / `知识库是否命中 in (是, 否)` 用例数",
        "- 标签准确率 = `意图标签是否准确=是` 用例数 / `意图标签是否准确 in (是, 否)` 用例数",
        "- 转人工准确率 = `回复是否准确=是` 用例数 / `回复是否准确 in (是, 否)` 用例数",
        "- 回复准确率 = `回复是否准确=是` 用例数 / `回复是否准确 in (是, 否)` 用例数",
        "",
        "## Fail Top30",
        "",
        "| case_id | expected_handoff | task_type | notes |",
        "|---|---|---|---|",
    ]
    if fail_top:
        for r in fail_top:
            lines.append(
                f"| {r.get('case_id','')} | {r.get('expected_handoff','')} | {r.get('task_type','')} | {str(r.get('notes',''))[:120]} |"
            )
    else:
        lines.append("| — | — | — | 本轮无 FAIL |")
    lines.append("")

    report_md.write_text("\n".join(lines), encoding="utf-8")
    return {"result_csv": result_csv, "summary_json": summary_json, "report_md": report_md}


def write_updated_source_csv(run_id: str, source_rows: list[dict], results: list[dict]) -> Path:
    out_dir = run_dir(run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "Hot70_机器人_知识库指标测试.回填结果.csv"
    by_id = {r.get("case_id", ""): r for r in results}
    rows_out: list[dict] = []
    for row in source_rows:
        new_row = dict(row)
        cid = (row.get("用例ID") or "").strip()
        rr = by_id.get(cid)
        if rr:
            new_row["实际识别的意图标签"] = rr.get("实际识别的意图标签", "") or ""
            new_row["意图标签是否准确"] = rr.get("意图标签是否准确", "") or ""
        rows_out.append(new_row)

    if rows_out:
        fieldnames = list(rows_out[0].keys())
    else:
        fieldnames = []
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_out)
    return out


def main():
    parser = argparse.ArgumentParser(description="Hot70 L2 知识库指标专项测试")
    parser.add_argument(
        "--source",
        default=str(SOURCE_CSV),
        help="知识库指标 CSV 路径（默认 prd/Hot70_机器人_知识库指标测试.csv）",
    )
    parser.add_argument("--channel", default="ch_wa_01")
    parser.add_argument("--business-line-id", type=int, default=1)
    parser.add_argument("--wait", type=float, default=3.0)
    parser.add_argument("--limit", type=int, default=0, help="仅执行前 N 条，0 表示全量")
    parser.add_argument(
        "--disable-llm-intent-tag",
        action="store_true",
        help="关闭 LLM 意图标签准确性判定（仅用规则回退）",
    )
    args = parser.parse_args()

    source = Path(args.source)
    if not source.is_absolute():
        source = (ROOT / source).resolve()
    if not source.exists():
        raise FileNotFoundError(f"source csv not found: {source}")

    rows = load_rows(source)
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]
    if not rows:
        print("no rows loaded")
        return

    client = Client(DEFAULT_BASE, DEFAULT_USER, DEFAULT_PASS)
    if not client.login(DEFAULT_USER, DEFAULT_PASS):
        raise RuntimeError("LOGIN FAILED")

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    executed_at = datetime.now().isoformat(timespec="seconds")

    results = []
    enable_llm_intent_tag = not args.disable_llm_intent_tag
    for idx, row in enumerate(rows, start=1):
        results.append(
            evaluate_case(
                client,
                row,
                args.channel,
                args.business_line_id,
                args.wait,
                enable_llm_intent_tag=enable_llm_intent_tag,
            )
        )
        if idx % 20 == 0:
            print(f"progress {idx}/{len(rows)}", flush=True)
        time.sleep(0.1)

    summary = summarize(results)
    outputs = write_outputs(run_id, executed_at, source, results, summary)
    updated_source_csv = write_updated_source_csv(run_id, rows, results)
    print(f"run_id={run_id}")
    print(f"report_md={outputs['report_md']}")
    print(f"result_csv={outputs['result_csv']}")
    print(f"summary_json={outputs['summary_json']}")
    print(f"updated_source_csv={updated_source_csv}")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
