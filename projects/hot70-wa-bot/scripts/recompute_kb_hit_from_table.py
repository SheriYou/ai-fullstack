#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Recompute `知识库是否命中` and `执行结果`, and apply handoff-fallback
consistency overrides.

Base rule:
- Authoritative trace priority (wa_message_trace_log):
  - `knowledge_hit` takes precedence for `知识库是否命中`
  - `handoff_flag` takes precedence for `转人工是否准确`
  - if trace is unavailable, fallback to deterministic table/KB matching rules below
- Semantic lookup against KB table (allowing paraphrase/polish):
  - question source: user actual language field in case sheet
    (prefer `测试数据（英文提问）`, fallback `测试数据`)
- locate KB row by question: `问题（英文）` OR `转人工条件（英文）`
  (fallback `用户问题`)
    and `转人工条件（英文）` uses keyword-hit rule
  - compare bot reply with KB expected answer:
    `业务反馈` (fallback `回复（用户实际使用语种）`)

Override rule (business confirmed):
- If `转人工预期=是` and `转人工是否准确=是` (fallback template optional),
  then force:
  - `知识库是否命中=是`
  - `回复是否准确=是`
  - remove `kb_not_hit` / `answer_incorrect` from `缺陷记录`

Execution result rule (business confirmed):
- Recompute `执行结果` with key gates only (not strict all-fields):
  - PASS: `回复是否准确=是` and `转人工是否准确=是` and no api/script error
  - FAIL: otherwise

Notes:
- `知识库是否命中` / `意图标签` fields are quality signals and do not
  directly fail `执行结果`.
- Optional row range can be applied via `--row-start/--row-end`
  (CSV line numbers, header is line 1).

Usage:
  python scripts/recompute_kb_hit_from_table.py
  python scripts/recompute_kb_hit_from_table.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import difflib
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from run_test_suite import Client, DEFAULT_BASE, DEFAULT_PASS, DEFAULT_USER

FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
if str(FRAMEWORK_ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_ROOT / "lib"))

from llm_client import LlmConfigError, chat  # noqa: E402


DEFAULT_RESULT_CSV = Path(
    r"D:\CMP\agent-human-test\projects\hot70-wa-bot\prd\Hot70_机器人_知识库指标测试.csv"
)
DEFAULT_KB_CSV = Path(
    r"D:\CMP\agent-human-test\projects\hot70-wa-bot\prd\Hot 70 FAQ知识库_FAQ知识库_全部FAQ.csv"
)

FALLBACK_TEMPLATE = (
    "A human agent is not available right now, so I will keep helping you here. "
    "You can share more details, and I will do my best based on the available information."
)


def yesno_text(v: bool) -> str:
    return "是" if v else "否"


def extract_json_object(text: str) -> dict | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        import json

        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return None
    try:
        import json

        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def llm_judge_reply_accuracy(
    *,
    row: dict,
    user_text: str,
    bot_reply: str,
    expected_handoff: bool,
    handoff_timing_ok: bool,
    knowledge_hit: bool,
    project_root: Path,
) -> tuple[bool, str]:
    case_id = (row.get("用例ID") or "").strip()
    case_name = (row.get("用例名称") or "").strip()
    expected_result = (row.get("预期结果") or "").strip()
    handoff_cond = (row.get("转人工触发条件") or "").strip()
    system_prompt = (
        "You are a QA reviewer. Judge whether `reply_accuracy` should be Yes/No.\n"
        "You must jointly evaluate:\n"
        "1) answer reasonableness to user question\n"
        "2) handoff reasonableness and timing for this case expectation\n"
        "Return JSON only."
    )
    user_prompt = (
        f"case_id: {case_id}\n"
        f"case_name: {case_name}\n"
        f"user_question: {user_text}\n"
        f"bot_reply: {bot_reply}\n"
        f"expected_result: {expected_result}\n"
        f"handoff_trigger_condition: {handoff_cond}\n"
        f"expected_handoff: {expected_handoff}\n"
        f"handoff_timing_ok: {handoff_timing_ok}\n"
        f"knowledge_hit: {knowledge_hit}\n\n"
        "Output JSON:\n"
        '{"reply_accuracy":"是|否","reason":"<=120 chars","confidence":0~1}'
    )
    txt = chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        project_root=project_root,
        temperature=0,
    )
    obj = extract_json_object(txt)
    if not obj:
        raise RuntimeError(f"LLM non-json output: {txt[:200]}")
    val = str(obj.get("reply_accuracy", "")).strip()
    if val not in ("是", "否"):
        raise RuntimeError(f"LLM invalid reply_accuracy: {obj}")
    reason = str(obj.get("reason", "")).strip()
    conf = obj.get("confidence", "")
    suffix = f"; confidence={conf}" if conf != "" else ""
    return val == "是", (f"llm:{reason}{suffix}" if reason else f"llm{suffix}")


def rule_judge_reply_accuracy(
    *,
    expected_handoff: bool,
    handoff_timing_ok: bool,
    knowledge_hit: bool,
    has_bot_reply: bool,
) -> tuple[bool, str]:
    if expected_handoff:
        ok = handoff_timing_ok
        return ok, (
            f"rule:expected_handoff={expected_handoff}; handoff_timing_ok={handoff_timing_ok}"
        )
    ok = handoff_timing_ok and knowledge_hit and has_bot_reply
    return ok, (
        f"rule:expected_handoff={expected_handoff}; handoff_timing_ok={handoff_timing_ok}; "
        f"knowledge_hit={knowledge_hit}; has_bot_reply={has_bot_reply}"
    )


def yesno_to_bool(value: str) -> bool | None:
    v = (value or "").strip().lower()
    if v in {"是", "y", "yes", "true", "1"}:
        return True
    if v in {"否", "n", "no", "false", "0"}:
        return False
    return None


def normalize_reply(value: str) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip().lower()


def is_handoff_fallback_reply(reply_en: str) -> bool:
    if not reply_en:
        return False
    return normalize_reply(FALLBACK_TEMPLATE) in normalize_reply(reply_en)


def should_use_new_session(value: str) -> bool | None:
    v = (value or "").strip().lower()
    if v in {"是", "y", "yes", "true", "1"}:
        return True
    if v in {"否", "n", "no", "false", "0"}:
        return False
    return None


def pick_final_robot_reply(raw_reply: str) -> str:
    text = (raw_reply or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""

    # Only split when explicit multi-turn role markers exist.
    role_mark = re.search(
        r"(?im)(^|\n)\s*(user|customer|bot|assistant|agent|robot)\s*[:：]",
        text,
    )
    if not role_mark:
        return text

    chunks = re.split(
        r"(?im)(?=(?:^|\n)\s*(?:user|customer|bot|assistant|agent|robot)\s*[:：])",
        text,
    )
    chunks = [c.strip() for c in chunks if c.strip()]
    if not chunks:
        return text
    return chunks[-1]


def case_reply_for_kb(row: dict) -> str:
    raw_reply = row.get("实际回复内容（英文）", "") or ""
    use_new = should_use_new_session(row.get("是否使用新会话", ""))
    if use_new is False:
        return pick_final_robot_reply(raw_reply)
    return raw_reply.strip()


def cleanup_defect_codes(raw: str, remove_codes: set[str]) -> str:
    parts = [p.strip() for p in (raw or "").split(";") if p.strip()]
    kept = [p for p in parts if p not in remove_codes]
    return "; ".join(kept)


def defect_codes(raw: str) -> list[str]:
    return [p.strip() for p in (raw or "").split(";") if p.strip()]


def has_api_or_script_error(raw: str) -> bool:
    for code in defect_codes(raw):
        lc = code.lower()
        if lc == "api_error" or lc.startswith("api_error"):
            return True
        if lc == "script_error" or lc.startswith("script_error"):
            return True
    return False


def has_any_execution_signal(row: dict) -> bool:
    keys = [
        "回复是否准确",
        "转人工是否准确",
        "实际回复内容（英文）",
        "缺陷记录",
        "知识库是否命中",
        "执行结果",
    ]
    return any((row.get(k) or "").strip() for k in keys)


def recompute_execution_result(row: dict) -> str:
    old = (row.get("执行结果") or "").strip()
    if not has_any_execution_signal(row):
        return old

    reply_raw = yesno_to_bool(row.get("回复是否准确", ""))
    handoff_raw = yesno_to_bool(row.get("转人工是否准确", ""))
    api_or_script_error = has_api_or_script_error(row.get("缺陷记录", ""))
    if api_or_script_error:
        return "FAIL"
    if handoff_raw is None or reply_raw is None:
        return "NA"
    return "PASS" if (reply_raw is True and handoff_raw is True) else "FAIL"


def score_to_level(score: int, uncertain: bool = False) -> str:
    if uncertain:
        return "待确认"
    if score >= 80:
        return "高"
    if score >= 60:
        return "中"
    return "低"


def extract_step_http(note: str) -> str:
    if not note:
        return ""
    m = re.search(r"step_http=([^;]+)", note)
    return (m.group(1) if m else "").strip()


def extract_note_value(note: str, key: str) -> str:
    if not note:
        return ""
    m = re.search(rf"{re.escape(key)}=([^;]+)", note)
    return (m.group(1) if m else "").strip()


TRUE_TASK_TYPES = {
    "TRANSFER_FAILED_AI_FALLBACK",
    "TRANSFER_SUCCESS",
    "TRANSFERRED",
    "HANDOFF_SUCCESS",
    "HANDOFF_ATTEMPTED",
}


def parse_task_type_from_note(note: str) -> str:
    return extract_note_value(note, "task_type")


def infer_actual_handoff_from_task_type(task_type: str) -> bool | None:
    if not task_type:
        return None
    return task_type in TRUE_TASK_TYPES


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


def trace_event_sort_key(rec: dict) -> tuple[int, int, int]:
    def _to_int(v) -> int:
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    return (
        _to_int(rec.get("event_time")),
        _to_int(rec.get("created_at")),
        _to_int(rec.get("id")),
    )


def latest_non_empty_trace(records: list[dict], key: str):
    for r in sorted(records, key=trace_event_sort_key, reverse=True):
        v = r.get(key)
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        return v
    return None


def to_int_or_none(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def fetch_trace_records(
    client: Client,
    business_line_id: int,
    session_key: str,
) -> list[dict]:
    if not session_key:
        return []
    sk = quote(session_key, safe="")
    path = f"/business-lines/{business_line_id}/trace-logs?session_id={sk}&page=1&size=120"
    status, data = client._call("GET", path)
    if status != 200:
        return []
    return parse_trace_records(data)


def build_trace_authoritative_payload(records: list[dict]) -> dict:
    if not records:
        return {}
    return {
        "trace_detected_intent": str(latest_non_empty_trace(records, "detected_intent") or "").strip(),
        "trace_knowledge_hit": to_int_or_none(latest_non_empty_trace(records, "knowledge_hit")),
        "trace_customer_tag": str(latest_non_empty_trace(records, "customer_tag") or "").strip(),
        "trace_handoff_flag": to_int_or_none(latest_non_empty_trace(records, "handoff_flag")),
        "trace_latency_ms": to_int_or_none(latest_non_empty_trace(records, "latency_ms")),
    }


def trace_text_similarity(a: str, b: str) -> float:
    aa = normalize_loose_text(a)
    bb = normalize_loose_text(b)
    if not aa or not bb:
        return 0.0
    if aa in bb or bb in aa:
        return 1.0
    ratio = difflib.SequenceMatcher(None, aa, bb).ratio()
    aw = tokenize_words(aa)
    bw = tokenize_words(bb)
    overlap = token_overlap(aw, bw) if aw and bw else 0.0
    overlap2 = token_overlap(bw, aw) if aw and bw else 0.0
    return max(ratio, overlap, overlap2)


def resolve_trace_from_records(records: list[dict], case_q_raw: str, case_a_raw: str) -> dict:
    if not records:
        return {}

    groups: dict[str, list[dict]] = {}
    for r in records:
        mid = str((r.get("message_id") or f"__id_{r.get('id')}")).strip()
        groups.setdefault(mid, []).append(r)

    best_payload: dict = {}
    best_rank: tuple[float, int, tuple[int, int, int]] | None = None
    case_q = case_q_raw or ""
    case_a = case_a_raw or ""
    for _, grecs in groups.items():
        q_score = 0.0
        a_score = 0.0
        for r in grecs:
            q_score = max(q_score, trace_text_similarity(case_q, str(r.get("user_message") or "")))
            a_score = max(a_score, trace_text_similarity(case_a, str(r.get("bot_reply") or "")))
        if case_a.strip():
            match_score = max(a_score, (0.65 * a_score + 0.35 * q_score))
        else:
            match_score = q_score

        payload = build_trace_authoritative_payload(grecs)
        field_score = trace_field_score(payload)
        newest = max(grecs, key=trace_event_sort_key)
        rank = (match_score, field_score, trace_event_sort_key(newest))
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best_payload = payload

    fallback_payload = build_trace_authoritative_payload(records)
    if not best_payload:
        best_payload = fallback_payload

    match_score = (best_rank[0] if best_rank else 0.0)
    if match_score < 0.35:
        # match confidence too low -> use session-level latest authoritative fields
        best_payload = fallback_payload
    best_payload["__trace_match_score"] = match_score
    return best_payload


def trace_field_score(payload: dict) -> int:
    if not payload:
        return 0
    score = 0
    if payload.get("trace_knowledge_hit") is not None:
        score += 1
    if payload.get("trace_handoff_flag") is not None:
        score += 1
    if payload.get("trace_customer_tag"):
        score += 1
    if payload.get("trace_detected_intent"):
        score += 1
    if payload.get("trace_latency_ms") is not None:
        score += 1
    return score


def resolve_trace_for_row(
    row: dict,
    trace_cache: dict[str, list[dict]],
    trace_client: Client | None,
    business_line_id: int,
    case_q_raw: str,
    case_a_raw: str,
) -> dict:
    if trace_client is None:
        return {}
    note = row.get("备注", "")
    candidates = [
        extract_note_value(note, "session_id"),
        extract_note_value(note, "whatsapp_id"),
    ]
    uniq = []
    for c in candidates:
        if c and c not in uniq:
            uniq.append(c)
    if not uniq:
        return {}

    best_payload: dict = {}
    best_score: tuple[float, int] = (-1.0, -1)
    for key in uniq:
        if key not in trace_cache:
            trace_cache[key] = fetch_trace_records(
                trace_client, business_line_id, key
            )
        records = trace_cache.get(key, [])
        payload = resolve_trace_from_records(records, case_q_raw=case_q_raw, case_a_raw=case_a_raw)
        score = (float(payload.get("__trace_match_score") or 0.0), trace_field_score(payload))
        if score > best_score:
            best_payload = payload
            best_score = score
    return best_payload


def resolve_handoff_timing_accuracy(
    *,
    row: dict,
    trace_payload: dict,
    expected_handoff: bool | None,
) -> tuple[str, bool | None, str]:
    trace_handoff = trace_payload.get("trace_handoff_flag")
    if trace_handoff is not None and expected_handoff is not None:
        ok = (trace_handoff == 1) == expected_handoff
        return yesno_text(ok), ok, "trace_handoff_flag"

    task_type = parse_task_type_from_note(row.get("备注", "") or row.get("澶囨敞", ""))
    inferred_actual = infer_actual_handoff_from_task_type(task_type)
    if inferred_actual is not None and expected_handoff is not None:
        ok = inferred_actual == expected_handoff
        return yesno_text(ok), ok, f"task_type:{task_type}"

    existing = (row.get("转人工是否准确") or "").strip()
    if existing in {"是", "否"}:
        return existing, yesno_to_bool(existing), "existing_value"

    return "待确认", None, "unknown"


def normalize_text(value: str) -> str:
    if not value:
        return ""
    v = value.strip().lower()
    # Keep only alnum + CJK to make matching deterministic and punctuation-insensitive.
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", v)


def normalize_loose_text(value: str) -> str:
    if not value:
        return ""
    v = value.strip().lower()
    v = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", v)
    return re.sub(r"\s+", " ", v).strip()


def tokenize_words(value: str) -> set[str]:
    if not value:
        return set()
    return set(re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", value.lower()))


EN_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "can",
    "do",
    "for",
    "from",
    "get",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "please",
    "the",
    "to",
    "today",
    "we",
    "what",
    "when",
    "where",
    "who",
    "why",
    "with",
    "you",
    "your",
}


def extract_question_keywords(case_q_loose: str) -> set[str]:
    if not case_q_loose:
        return set()
    out: set[str] = set()
    for tok in re.findall(r"[a-z0-9]+", case_q_loose):
        if tok in EN_STOPWORDS:
            continue
        if len(tok) >= 3 or tok in {"5g", "4g", "bdt"}:
            out.add(tok)
    for tok in re.findall(r"[\u4e00-\u9fff]{2,}", case_q_loose):
        out.add(tok)
    return out


def note_keyword_similarity(case_keywords: set[str], note_loose: str) -> float:
    if not case_keywords or not note_loose:
        return 0.0
    hits = sum(1 for kw in case_keywords if kw in note_loose)
    if hits <= 0:
        return 0.0
    # Business rule: once handoff-note contains a question keyword, treat as a weak
    # but valid question match; more keywords => stronger confidence.
    if hits >= 3:
        return 0.80
    if hits == 2:
        return 0.72
    return 0.66


def token_overlap(reference_tokens: set[str], actual_tokens: set[str]) -> float:
    if not reference_tokens or not actual_tokens:
        return 0.0
    return len(reference_tokens & actual_tokens) / len(reference_tokens)


def question_similarity(case_q_norm: str, case_q_loose: str, case_q_tokens: set[str], kb_entry: dict) -> float:
    q_norm = kb_entry["q_norm"]
    q_loose = kb_entry["q_loose"]
    q_tokens = kb_entry["q_tokens"]
    note_loose = kb_entry["note_loose"]

    base_score = 0.0
    if case_q_norm and q_norm:
        if case_q_norm in q_norm or q_norm in case_q_norm:
            base_score = 1.0
        else:
            ratio_norm = difflib.SequenceMatcher(None, case_q_norm, q_norm).ratio()
            ratio_loose = difflib.SequenceMatcher(None, case_q_loose, q_loose).ratio()
            overlap_a = token_overlap(case_q_tokens, q_tokens)
            overlap_b = token_overlap(q_tokens, case_q_tokens)
            base_score = max(ratio_norm, ratio_loose, overlap_a, overlap_b)

    note_score = note_keyword_similarity(extract_question_keywords(case_q_loose), note_loose)
    return max(base_score, note_score)


def reply_similarity(case_a_norm: str, case_a_loose: str, case_a_tokens: set[str], kb_entry: dict) -> float:
    expected_norm = kb_entry["a_norm"]
    expected_loose = kb_entry["a_loose"]
    expected_tokens = kb_entry["a_tokens"]

    if not case_a_norm or not expected_norm:
        return 0.0
    if expected_norm in case_a_norm or case_a_norm in expected_norm:
        return 1.0

    ratio_norm = difflib.SequenceMatcher(None, expected_norm, case_a_norm).ratio()
    ratio_loose = difflib.SequenceMatcher(None, expected_loose, case_a_loose).ratio()
    overlap = token_overlap(expected_tokens, case_a_tokens)
    return max(ratio_norm, ratio_loose, overlap)


def answer_matches(case_a_norm: str, case_a_loose: str, case_a_tokens: set[str], kb_entry: dict) -> bool:
    if not case_a_norm:
        return False
    expected_norm = kb_entry["a_norm"]
    if not expected_norm:
        return False

    score = reply_similarity(case_a_norm, case_a_loose, case_a_tokens, kb_entry)
    ratio_loose = difflib.SequenceMatcher(None, kb_entry["a_loose"], case_a_loose).ratio()
    coverage = token_overlap(kb_entry["a_tokens"], case_a_tokens)

    if score >= 0.55:
        return True
    if ratio_loose >= 0.45 and coverage >= 0.42:
        return True
    return False


def load_kb_entries(kb_csv: Path, encoding: str) -> list[dict]:
    with kb_csv.open("r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f)
        entries: list[dict] = []
        for row in reader:
            q = row.get("问题（英文）", "") or row.get("用户问题", "")
            note = row.get("转人工条件（英文）", "")
            a = row.get("业务反馈", "") or row.get("回复（用户实际使用语种）", "")
            q_norm = normalize_text(q)
            a_norm = normalize_text(a)
            q_loose = normalize_loose_text(q)
            note_loose = normalize_loose_text(note)
            a_loose = normalize_loose_text(a)
            if not q or not a:
                continue
            entries.append(
                {
                    "q_norm": q_norm,
                    "q_loose": q_loose,
                    "q_tokens": tokenize_words(q_loose),
                    "note_loose": note_loose,
                    "a_norm": a_norm,
                    "a_loose": a_loose,
                    "a_tokens": tokenize_words(a_loose),
                }
            )
    return entries


def recompute(
    result_csv: Path,
    result_encoding: str,
    kb_entries: list[dict],
    trace_client: Client | None,
    business_line_id: int,
    enable_llm_reply_accuracy: bool,
    row_start: int | None = None,
    row_end: int | None = None,
) -> tuple[list[dict], dict]:
    with result_csv.open("r", encoding=result_encoding, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    changed_rows: list[dict] = []
    override_rows = 0
    reply_fixed_rows = 0
    defects_cleaned_rows = 0
    exec_changed_rows = 0
    trace_knowledge_rows = 0
    trace_handoff_rows = 0
    handoff_task_type_rows = 0
    handoff_unknown_rows = 0
    llm_reply_rows = 0
    llm_reply_fallback_rows = 0
    trace_cache: dict[str, list[dict]] = {}

    for idx, row in enumerate(rows, start=2):
        in_scope = True
        if row_start is not None and idx < row_start:
            in_scope = False
        if row_end is not None and idx > row_end:
            in_scope = False
        if not in_scope:
            continue

        case_q_raw = row.get("测试数据（英文提问）", "") or row.get("测试数据", "")
        case_q_norm = normalize_text(case_q_raw)
        case_q_loose = normalize_loose_text(case_q_raw)
        case_q_tokens = tokenize_words(case_q_loose)

        case_a_raw = case_reply_for_kb(row)
        case_a_norm = normalize_text(case_a_raw)
        case_a_loose = normalize_loose_text(case_a_raw)
        case_a_tokens = tokenize_words(case_a_loose)

        trace_payload = resolve_trace_for_row(
            row,
            trace_cache=trace_cache,
            trace_client=trace_client,
            business_line_id=business_line_id,
            case_q_raw=case_q_raw,
            case_a_raw=case_a_raw,
        )

        top_q_score = 0.0
        candidate_pool: list[dict] = []
        for entry in kb_entries:
            q_score = question_similarity(case_q_norm, case_q_loose, case_q_tokens, entry)
            if q_score < 0.62:
                continue
            if q_score > top_q_score:
                top_q_score = q_score
            candidate_pool.append({"entry": entry, "q_score": q_score})

        near_candidates = [
            c for c in candidate_pool if c["q_score"] >= (top_q_score - 0.03)
        ]
        hit_by_kb = any(
            answer_matches(case_a_norm, case_a_loose, case_a_tokens, c["entry"])
            for c in near_candidates
        )
        trace_kh = trace_payload.get("trace_knowledge_hit")
        if trace_kh is not None:
            hit_by_kb = trace_kh == 1
            trace_knowledge_rows += 1

        expected_handoff = yesno_to_bool(row.get("转人工预期", ""))
        handoff_text, handoff_timing_ok, handoff_source = resolve_handoff_timing_accuracy(
            row=row,
            trace_payload=trace_payload,
            expected_handoff=expected_handoff,
        )
        row["转人工是否准确"] = handoff_text
        if handoff_source == "trace_handoff_flag":
            trace_handoff_rows += 1
        elif handoff_source.startswith("task_type:"):
            handoff_task_type_rows += 1
        elif handoff_source == "unknown":
            handoff_unknown_rows += 1

        handoff_override = (expected_handoff is True) and (handoff_timing_ok is True)
        new_value = yesno_text(hit_by_kb or handoff_override)


        old_value = (row.get("知识库是否命中") or "").strip()
        old_reply_acc = (row.get("回复是否准确") or "").strip()
        old_defects = row.get("缺陷记录", "")
        old_exec = (row.get("执行结果") or "").strip()
        has_bot_reply = bool(case_a_raw.strip())
        if enable_llm_reply_accuracy:
            try:
                reply_ok, reply_reason = llm_judge_reply_accuracy(
                    row=row,
                    user_text=case_q_raw,
                    bot_reply=case_a_raw,
                    expected_handoff=(expected_handoff is True),
                    handoff_timing_ok=(handoff_timing_ok is True),
                    knowledge_hit=(new_value == "是"),
                    project_root=Path(__file__).resolve().parents[1],
                )
                llm_reply_rows += 1
            except (LlmConfigError, RuntimeError):
                reply_ok, reply_reason = rule_judge_reply_accuracy(
                    expected_handoff=(expected_handoff is True),
                    handoff_timing_ok=(handoff_timing_ok is True),
                    knowledge_hit=(new_value == "是"),
                    has_bot_reply=has_bot_reply,
                )
                llm_reply_fallback_rows += 1
        else:
            reply_ok, reply_reason = rule_judge_reply_accuracy(
                expected_handoff=(expected_handoff is True),
                handoff_timing_ok=(handoff_timing_ok is True),
                knowledge_hit=(new_value == "是"),
                has_bot_reply=has_bot_reply,
            )
        row["回复是否准确"] = yesno_text(reply_ok)
        handoff_fallback_ok = is_handoff_fallback_reply(case_a_raw) or bool(
            re.search(r"human agent|transfer to human|转人工|人工客服|坐席", (case_a_raw or "").lower())
        )
        if (expected_handoff is True) and (handoff_timing_ok is True) and (not has_bot_reply or handoff_fallback_ok):
            row["回复是否准确"] = "是"
            if not reply_reason:
                reply_reason = "handoff_rule_override"
            elif "handoff_rule_override" not in reply_reason:
                reply_reason = f"{reply_reason}; handoff_rule_override"

        if handoff_override:
            override_rows += 1
            row["回复是否准确"] = "是"
            row["缺陷记录"] = cleanup_defect_codes(
                old_defects, remove_codes={"kb_not_hit", "answer_incorrect"}
            )
            if old_reply_acc != row["回复是否准确"]:
                reply_fixed_rows += 1
            if (old_defects or "").strip() != (row["缺陷记录"] or "").strip():
                defects_cleaned_rows += 1

        row["知识库是否命中"] = new_value
        row["执行结果"] = recompute_execution_result(row)
        if old_exec != (row.get("执行结果") or "").strip():
            exec_changed_rows += 1

        if (
            old_value != new_value
            or old_reply_acc != (row.get("回复是否准确") or "").strip()
            or (old_defects or "").strip() != (row.get("缺陷记录") or "").strip()
            or old_exec != (row.get("执行结果") or "").strip()
        ):
            changed_rows.append(
                {
                    "line_no": idx,
                    "用例ID": row.get("用例ID", ""),
                    "old_hit": old_value,
                    "new_hit": new_value,
                    "handoff_override": "是" if handoff_override else "否",
                    "old_reply_acc": old_reply_acc,
                    "new_reply_acc": (row.get("回复是否准确") or "").strip(),
                    "old_defects": (old_defects or "").strip(),
                    "new_defects": (row.get("缺陷记录") or "").strip(),
                    "old_exec": old_exec,
                    "new_exec": (row.get("执行结果") or "").strip(),
                    "测试数据（英文提问）": row.get("测试数据（英文提问）", ""),
                }
            )

    stats = {
        "total_rows": len(rows),
        "changed_rows": len(changed_rows),
        "new_yes": sum(1 for r in rows if (r.get("知识库是否命中") or "").strip() == "是"),
        "new_no": sum(1 for r in rows if (r.get("知识库是否命中") or "").strip() == "否"),
        "exec_pass_rows": sum(1 for r in rows if (r.get("执行结果") or "").strip() == "PASS"),
        "exec_fail_rows": sum(1 for r in rows if (r.get("执行结果") or "").strip() == "FAIL"),
        "exec_pending_rows": sum(1 for r in rows if (r.get("执行结果") or "").strip() in ("待确认", "NA")),
        "override_rows": override_rows,
        "reply_fixed_rows": reply_fixed_rows,
        "defects_cleaned_rows": defects_cleaned_rows,
        "exec_changed_rows": exec_changed_rows,
        "trace_knowledge_rows": trace_knowledge_rows,
        "trace_handoff_rows": trace_handoff_rows,
        "handoff_task_type_rows": handoff_task_type_rows,
        "handoff_unknown_rows": handoff_unknown_rows,
        "row_start": row_start if row_start is not None else "",
        "row_end": row_end if row_end is not None else "",
        "kb_match_mode": "faq_text5_or_handoff_condition_en_keyword_then_business_feedback_semantic_compare",
        "fieldnames": fieldnames,
    }
    return rows, {"stats": stats, "changed_rows": changed_rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-csv", default=str(DEFAULT_RESULT_CSV))
    parser.add_argument("--kb-csv", default=str(DEFAULT_KB_CSV))
    parser.add_argument("--result-encoding", default="gb18030")
    parser.add_argument("--kb-encoding", default="utf-8-sig")
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--password", default=DEFAULT_PASS)
    parser.add_argument("--business-line-id", type=int, default=1)
    parser.add_argument(
        "--disable-trace-priority",
        action="store_true",
        help="Disable wa_message_trace_log priority for knowledge_hit/handoff_flag.",
    )
    parser.add_argument("--row-start", type=int, default=None)
    parser.add_argument("--row-end", type=int, default=None)
    parser.add_argument(
        "--disable-llm-reply-accuracy",
        action="store_true",
        help="Disable LLM judge for 回复是否准确; fallback to deterministic rules only.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write-backup", action="store_true")
    args = parser.parse_args()

    result_csv = Path(args.result_csv)
    kb_csv = Path(args.kb_csv)

    trace_client: Client | None = None
    trace_enabled = not args.disable_trace_priority
    trace_login_ok = False
    if trace_enabled:
        try:
            c = Client(args.base, args.user, args.password)
            if c.login(args.user, args.password):
                trace_client = c
                trace_login_ok = True
        except Exception:
            trace_client = None
            trace_login_ok = False

    kb_entries = load_kb_entries(kb_csv, args.kb_encoding)
    rows, payload = recompute(
        result_csv,
        args.result_encoding,
        kb_entries,
        trace_client=trace_client,
        business_line_id=args.business_line_id,
        enable_llm_reply_accuracy=(not args.disable_llm_reply_accuracy),
        row_start=args.row_start,
        row_end=args.row_end,
    )
    stats = payload["stats"]
    changed_rows = payload["changed_rows"]

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = Path(r"D:\CMP\agent-human-test\projects\hot70-wa-bot\reports\runs") / ts
    report_dir.mkdir(parents=True, exist_ok=True)
    delta_csv = report_dir / "kb-hit-recompute-delta.csv"

    with delta_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "用例ID",
                "old_hit",
                "new_hit",
                "handoff_override",
                "old_reply_acc",
                "new_reply_acc",
                "old_defects",
                "new_defects",
                "old_exec",
                "new_exec",
                "old_score",
                "new_score",
                "old_level",
                "new_level",
                "line_no",
                "测试数据（英文提问）",
            ],
        )
        writer.writeheader()
        writer.writerows(changed_rows)

    backup_path = None
    if not args.dry_run:
        if args.write_backup:
            backup_path = report_dir / (
                f"{result_csv.stem}.kbhit-backup-{ts}{result_csv.suffix}"
            )
            shutil.copyfile(result_csv, backup_path)

        with result_csv.open("w", encoding=args.result_encoding, newline="") as f:
            writer = csv.DictWriter(f, fieldnames=stats["fieldnames"])
            writer.writeheader()
            writer.writerows(rows)

    print(f"kb_csv={kb_csv}")
    print(f"result_csv={result_csv}")
    print(f"total_rows={stats['total_rows']}")
    print(f"changed_rows={stats['changed_rows']}")
    print(f"new_yes={stats['new_yes']}")
    print(f"new_no={stats['new_no']}")
    print(f"exec_pass_rows={stats['exec_pass_rows']}")
    print(f"exec_fail_rows={stats['exec_fail_rows']}")
    print(f"exec_pending_rows={stats['exec_pending_rows']}")
    print(f"override_rows={stats['override_rows']}")
    print(f"reply_fixed_rows={stats['reply_fixed_rows']}")
    print(f"defects_cleaned_rows={stats['defects_cleaned_rows']}")
    print(f"exec_changed_rows={stats['exec_changed_rows']}")
    print(f"trace_priority_enabled={trace_enabled}")
    print(f"trace_login_ok={trace_login_ok}")
    print(f"trace_knowledge_rows={stats['trace_knowledge_rows']}")
    print(f"trace_handoff_rows={stats['trace_handoff_rows']}")
    print(f"handoff_task_type_rows={stats['handoff_task_type_rows']}")
    print(f"handoff_unknown_rows={stats['handoff_unknown_rows']}")
    print(f"row_start={stats['row_start']}")
    print(f"row_end={stats['row_end']}")
    print(f"kb_match_mode={stats['kb_match_mode']}")
    print(f"delta_csv={delta_csv}")
    if backup_path:
        print(f"backup_csv={backup_path}")
    print(f"dry_run={args.dry_run}")


if __name__ == "__main__":
    main()
