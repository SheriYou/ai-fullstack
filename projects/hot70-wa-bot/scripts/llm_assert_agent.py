#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Optional LLM assertion agent for fuzzy/semantic checks.

Behavior:
- Rule assertions remain primary.
- LLM assertions are optional and case-gated.
- When LLM budget/quota is exhausted, fall back to rule assertion automatically.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "lib"))

from llm_client import LlmConfigError, chat  # noqa: E402


DEFAULT_LLM_BASE = "https://newapi-hk.transsion.com/v1"
DEFAULT_LLM_MODEL = "deepseek-v4-flash"

_LLM_CALL_COUNT = 0
_LLM_DISABLED_AFTER_QUOTA = False


class LlmAssertError(RuntimeError):
    pass


def _truthy(name: str, default: str = "0") -> bool:
    val = (os.getenv(name, default) or "").strip().lower()
    return val in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = (os.getenv(name, str(default)) or "").strip()
    try:
        return int(raw)
    except ValueError:
        return default


def llm_assert_enabled_for_case(case_id: str) -> bool:
    if not _truthy("USE_LLM_ASSERT", "0"):
        return False
    raw = (os.getenv("LLM_ASSERT_CASE_IDS", "*") or "").strip()
    if not raw or raw == "*":
        return True
    allow = {x.strip() for x in raw.split(",") if x.strip()}
    return case_id in allow


def llm_assert_enabled_for_check(case_id: str, check_name: str) -> bool:
    if not llm_assert_enabled_for_case(case_id):
        return False
    raw = (os.getenv("LLM_ASSERT_CHECKS", "*") or "").strip().lower()
    if not raw or raw == "*":
        return True
    allow = {x.strip() for x in raw.split(",") if x.strip()}
    return check_name.strip().lower() in allow


def _check_and_consume_budget() -> None:
    global _LLM_CALL_COUNT
    if _LLM_DISABLED_AFTER_QUOTA:
        raise LlmAssertError("llm_quota_exhausted_fallback_to_rule")
    # Max LLM calls per run process; <=0 means unlimited.
    max_calls = _int_env("LLM_ASSERT_MAX_CALLS", 120)
    if max_calls > 0 and _LLM_CALL_COUNT >= max_calls:
        raise LlmAssertError("llm_budget_exhausted_fallback_to_rule")
    _LLM_CALL_COUNT += 1


def _extract_json_object(text: str) -> dict:
    t = (text or "").strip()
    if not t:
        raise LlmAssertError("llm_empty_output")
    m = re.search(r"\{[\s\S]*\}", t)
    if not m:
        raise LlmAssertError(f"llm_no_json:{t[:160]}")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise LlmAssertError(f"llm_bad_json:{t[:160]}") from e


def _is_quota_like_error(detail: str) -> bool:
    d = (detail or "").lower()
    markers = (
        "insufficient_quota",
        "quota",
        "balance",
        "credit",
        "token",
        "billing",
    )
    return any(m in d for m in markers)


def _chat_with_env_or_config(messages: list[dict], project_root: Path | None = None) -> str:
    global _LLM_DISABLED_AFTER_QUOTA
    _check_and_consume_budget()

    api_key = (os.getenv("LLM_API_KEY", "") or "").strip()
    base = (os.getenv("LLM_API_BASE", "") or DEFAULT_LLM_BASE).strip().rstrip("/")
    model = (os.getenv("LLM_MODEL", "") or DEFAULT_LLM_MODEL).strip()

    # Prefer env for runtime security; if key missing, fallback to project config via llm_client.chat.
    if api_key:
        url = f"{base}/chat/completions"
        body = json.dumps(
            {"model": model, "messages": messages, "temperature": 0},
            ensure_ascii=False,
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:500]
            if e.code == 429 or _is_quota_like_error(detail):
                _LLM_DISABLED_AFTER_QUOTA = True
                raise LlmAssertError("llm_quota_exhausted_fallback_to_rule") from e
            raise LlmAssertError(f"llm_http_{e.code}:{detail[:180]}") from e
        except urllib.error.URLError as e:
            raise LlmAssertError(f"llm_url_error:{e.reason}") from e
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LlmAssertError(f"llm_bad_response:{data!r}") from e

    try:
        return chat(messages, project_root=project_root, temperature=0)
    except LlmConfigError as e:
        raise LlmAssertError(f"llm_config_error:{e}") from e
    except Exception as e:  # pragma: no cover - runtime/network dependent
        msg = str(e)
        if _is_quota_like_error(msg):
            _LLM_DISABLED_AFTER_QUOTA = True
            raise LlmAssertError("llm_quota_exhausted_fallback_to_rule") from e
        raise LlmAssertError(f"llm_call_error:{e}") from e


def judge_price_semantic(
    *,
    case_id: str,
    input_text: str,
    outbound_texts: list[str],
    project_root: Path | None = None,
) -> tuple[bool, str]:
    if not outbound_texts:
        return False, "no outbound to evaluate"

    latest = outbound_texts[-1]
    prompt = (
        "You are a test assertion agent. Judge if the bot reply is acceptable for a price inquiry.\n"
        "Pass criteria:\n"
        "1) Reply contains explicit price amount; OR\n"
        "2) Reply is a model/version clarification that clearly indicates pricing info will follow.\n"
        "Fail when irrelevant or clearly off-topic.\n"
        "Return JSON only: "
        '{"passed": true/false, "reason": "<=80 chars", "confidence": 0~1}'
    )
    user_payload = {
        "case_id": case_id,
        "user_input": input_text,
        "latest_outbound": latest,
        "all_outbounds": outbound_texts[-3:],
    }
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]
    raw = _chat_with_env_or_config(messages, project_root=project_root)

    obj = _extract_json_object(raw)
    passed = bool(obj.get("passed", False))
    reason = str(obj.get("reason", "")).strip() or "no reason"
    conf = obj.get("confidence", "")
    suffix = f"; confidence={conf}" if conf != "" else ""
    return passed, f"{reason[:80]}{suffix}"


def judge_check_semantic(
    *,
    case_id: str,
    check_name: str,
    input_text: str,
    outbound_texts: list[str],
    conversation_state: dict | None = None,
    project_root: Path | None = None,
) -> tuple[bool, str]:
    """Generic semantic fallback for flexible functional assertions."""
    if not outbound_texts and check_name not in {"handoff_required", "outbound_sla"}:
        return False, "no outbound to evaluate"

    latest = outbound_texts[-1] if outbound_texts else ""
    prompt = (
        "You are a QA assertion agent for WhatsApp bot tests.\n"
        "We prioritize functional availability over strict keyword matching.\n"
        "Judge pass/fail by check_name semantics:\n"
        "- outbound_sla: pass if user got a relevant bot reply, even if slower than SLA.\n"
        "- gibberish_hint: pass if reply safely clarifies/redirects/handoffs, no crash.\n"
        "- clarify_multi_intent: pass if reply asks clarification OR safely handles one intent and asks follow-up.\n"
        "- handoff_required: pass if LOCAL handoff happened OR reply clearly directs to human support.\n"
        "- no_hallucination_handoff: pass if reply avoids fabricated facts and uses safe fallback/handoff wording.\n"
        "Return JSON only: "
        '{"passed": true/false, "reason": "<=100 chars", "confidence": 0~1}'
    )
    user_payload = {
        "case_id": case_id,
        "check_name": check_name,
        "user_input": input_text,
        "latest_outbound": latest,
        "all_outbounds": outbound_texts[-3:],
        "conversation_state": conversation_state or {},
    }
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]
    raw = _chat_with_env_or_config(messages, project_root=project_root)
    obj = _extract_json_object(raw)
    passed = bool(obj.get("passed", False))
    reason = str(obj.get("reason", "")).strip() or "no reason"
    conf = obj.get("confidence", "")
    suffix = f"; confidence={conf}" if conf != "" else ""
    return passed, f"{reason[:100]}{suffix}"


def judge_intent_semantic(
    *,
    case_id: str,
    input_text: str,
    expected_intent: str,
    expected_label: str = "",
    expected_action: str,
    expected_facts: str,
    should_handoff: str,
    outbound_texts: list[str],
    handoff: bool,
    task_type: str = "",
    detected_intent: str = "",
    project_root: Path | None = None,
) -> tuple[bool, str]:
    """Judge intent correctness primarily from visible reply semantics."""
    if not outbound_texts and not handoff:
        return False, "no reply and no handoff to evaluate"

    prompt = (
        "You are a senior QA assertion agent for WhatsApp bot tests.\n"
        "Judge whether the bot handled the user's intent correctly.\n"
        "Priority order:\n"
        "1) Judge by user-visible reply semantics.\n"
        "2) Handoff action is valid evidence when expected_action/handoff requires human support.\n"
        "3) task_type or detected_intent are only supporting evidence, not the primary basis.\n"
        "Rules:\n"
        "- If should_handoff=true or expected_action=handoff: pass when the bot clearly routes the user to human support, or actual LOCAL handoff happened.\n"
        "- Otherwise, pass when the reply mainly answers the expected intent category.\n"
        "- If expected_label is provided, infer whether the bot's reply and the user request are semantically consistent with that label. Do not treat backend fields as the primary evidence.\n"
        "- expected_facts are hints for the intent topic, not strict keyword assertions.\n"
        "- Fail only when the reply is clearly off-topic, unsafe, or the action contradicts the expected intent.\n"
        "Return JSON only: "
        '{"passed": true/false, "reason": "<=120 chars", "inferred_intent": "<short>", "confidence": 0~1}'
    )
    payload = {
        "case_id": case_id,
        "user_input": input_text,
        "expected_intent": expected_intent,
        "expected_label": expected_label,
        "expected_action": expected_action,
        "expected_facts_hint": expected_facts[:600],
        "should_handoff": should_handoff,
        "actual_handoff": handoff,
        "task_type": task_type,
        "detected_intent": detected_intent,
        "latest_outbound": outbound_texts[-1] if outbound_texts else "",
        "all_outbounds": outbound_texts[-3:],
    }
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    raw = _chat_with_env_or_config(messages, project_root=project_root)
    obj = _extract_json_object(raw)
    passed = bool(obj.get("passed", False))
    reason = str(obj.get("reason", "")).strip() or "no reason"
    inferred = str(obj.get("inferred_intent", "")).strip()
    conf = obj.get("confidence", "")
    extras = []
    if inferred:
        extras.append(f"inferred={inferred[:40]}")
    if conf != "":
        extras.append(f"confidence={conf}")
    suffix = f"; {'; '.join(extras)}" if extras else ""
    return passed, f"{reason[:120]}{suffix}"


def judge_case_by_title(
    *,
    case_id: str,
    case_title: str,
    input_text: str,
    expected_result: str,
    outbound_texts: list[str],
    rule_fail_notes: str,
    conversation_state: dict | None = None,
    project_root: Path | None = None,
) -> tuple[bool, str]:
    """Case-level flexible recheck based on test-case title and actual reply."""
    if not outbound_texts:
        return False, "no outbound to evaluate"

    prompt = (
        "You are a senior QA assertion agent.\n"
        "Goal: prioritize functional availability. If bot's actual reply reasonably satisfies the test case title intent, pass.\n"
        "Input includes case title, expected result text, user input, latest outbound, and rule-fail notes.\n"
        "Pass when user got a relevant and safe reply, even if strict keyword/timing checks failed.\n"
        "Fail only when reply is clearly irrelevant, unsafe, or missing core intent.\n"
        "Return JSON only: "
        '{"passed": true/false, "reason": "<=120 chars", "confidence": 0~1}'
    )
    payload = {
        "case_id": case_id,
        "case_title": case_title,
        "expected_result": expected_result[:600],
        "user_input": input_text,
        "latest_outbound": outbound_texts[-1],
        "all_outbounds": outbound_texts[-3:],
        "rule_fail_notes": rule_fail_notes[:600],
        "conversation_state": conversation_state or {},
    }
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    raw = _chat_with_env_or_config(messages, project_root=project_root)
    obj = _extract_json_object(raw)
    passed = bool(obj.get("passed", False))
    reason = str(obj.get("reason", "")).strip() or "no reason"
    conf = obj.get("confidence", "")
    suffix = f"; confidence={conf}" if conf != "" else ""
    return passed, f"{reason[:120]}{suffix}"
