#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Optional LLM case-writer agent for test-case drafting/polishing.

Default is OFF. If enabled, this agent rewrites title/steps/expected fields
for readability while preserving original test intent.
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

from load_config import load_config  # noqa: E402


DEFAULT_LLM_BASE = "https://newapi-hk.transsion.com/v1"
DEFAULT_LLM_MODEL = "deepseek-v4-flash"

_CALL_COUNT = 0
_DISABLED_BY_QUOTA = False


def _truthy(name: str, default: str = "0") -> bool:
    val = (os.getenv(name, default) or "").strip().lower()
    return val in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = (os.getenv(name, str(default)) or "").strip()
    try:
        return int(raw)
    except ValueError:
        return default


def case_writer_enabled(section: str, case_id: str) -> bool:
    if not _truthy("USE_LLM_CASE_WRITER", "0"):
        return False
    scope_raw = (os.getenv("LLM_CASE_WRITER_SCOPE", "faq,adversarial") or "").strip().lower()
    if scope_raw and scope_raw != "*":
        allowed = {x.strip() for x in scope_raw.split(",") if x.strip()}
        if section.lower() not in allowed:
            return False
    ids_raw = (os.getenv("LLM_CASE_WRITER_CASE_IDS", "") or "").strip()
    if ids_raw and ids_raw != "*":
        allow_ids = {x.strip() for x in ids_raw.split(",") if x.strip()}
        return case_id in allow_ids
    return True


def _consume_budget() -> None:
    global _CALL_COUNT
    if _DISABLED_BY_QUOTA:
        raise RuntimeError("llm_case_writer_quota_exhausted")
    max_calls = _int_env("LLM_CASE_WRITER_MAX_CALLS", 80)
    if max_calls > 0 and _CALL_COUNT >= max_calls:
        raise RuntimeError("llm_case_writer_budget_exhausted")
    _CALL_COUNT += 1


def _is_quota_error(detail: str) -> bool:
    d = (detail or "").lower()
    markers = ("quota", "insufficient_quota", "credit", "balance", "billing", "token")
    return any(m in d for m in markers)


def _llm_config(project_root: Path | None = None) -> tuple[str, str, str]:
    key = (os.getenv("LLM_API_KEY", "") or "").strip()
    base = (os.getenv("LLM_API_BASE", "") or "").strip().rstrip("/")
    model = (os.getenv("LLM_MODEL", "") or "").strip()
    if key and base:
        return key, base, (model or DEFAULT_LLM_MODEL)
    cfg = load_config(project_root)
    key = (cfg.get("LLM_API_KEY", "") or "").strip()
    base = (cfg.get("LLM_API_BASE", "") or DEFAULT_LLM_BASE).strip().rstrip("/")
    model = (cfg.get("LLM_MODEL", "") or DEFAULT_LLM_MODEL).strip()
    if not key:
        raise RuntimeError("llm_case_writer_missing_key")
    return key, base, model


def _chat(messages: list[dict], project_root: Path | None = None) -> str:
    global _DISABLED_BY_QUOTA
    _consume_budget()
    key, base, model = _llm_config(project_root)
    url = f"{base}/chat/completions"
    body = json.dumps(
        {"model": model, "messages": messages, "temperature": 0},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        if e.code == 429 or _is_quota_error(detail):
            _DISABLED_BY_QUOTA = True
            raise RuntimeError("llm_case_writer_quota_exhausted") from e
        raise RuntimeError(f"llm_case_writer_http_{e.code}:{detail[:180]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"llm_case_writer_url_error:{e.reason}") from e
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"llm_case_writer_bad_response:{data!r}") from e


def _extract_json(text: str) -> dict:
    t = (text or "").strip()
    m = re.search(r"\{[\s\S]*\}", t)
    if not m:
        raise RuntimeError(f"llm_case_writer_no_json:{t[:160]}")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"llm_case_writer_bad_json:{t[:160]}") from e


def rewrite_case_fields(
    *,
    case_id: str,
    section: str,
    title: str,
    steps: str,
    expected: str,
    context: dict | None = None,
    project_root: Path | None = None,
) -> tuple[str, str, str, str]:
    """Return (new_title, new_steps, new_expected, note)."""
    payload = {
        "case_id": case_id,
        "section": section,
        "title": title,
        "steps": steps,
        "expected": expected,
        "context": context or {},
    }
    prompt = (
        "You are a QA test-case writing agent.\n"
        "Rewrite the provided test case fields for clarity and execution quality.\n"
        "Constraints:\n"
        "1) Keep original test intent unchanged.\n"
        "2) Keep language Chinese.\n"
        "3) Keep steps/expected concise and executable.\n"
        "4) Do NOT add new requirements beyond input context.\n"
        "Return JSON only with keys: title, steps, expected."
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    raw = _chat(messages, project_root=project_root)
    obj = _extract_json(raw)
    nt = str(obj.get("title", "")).strip() or title
    ns = str(obj.get("steps", "")).strip() or steps
    ne = str(obj.get("expected", "")).strip() or expected
    return nt, ns, ne, "llm_case_writer_applied"
