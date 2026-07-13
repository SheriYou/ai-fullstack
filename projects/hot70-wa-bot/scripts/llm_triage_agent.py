#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Optional LLM triage agent for failed-case root-cause summarization."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
import sys

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


def triage_enabled() -> bool:
    return _truthy("USE_LLM_TRIAGE", "0")


def _consume_budget() -> None:
    global _CALL_COUNT
    if _DISABLED_BY_QUOTA:
        raise RuntimeError("llm_triage_quota_exhausted")
    max_calls = _int_env("LLM_TRIAGE_MAX_CALLS", 1)
    if max_calls > 0 and _CALL_COUNT >= max_calls:
        raise RuntimeError("llm_triage_budget_exhausted")
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
        raise RuntimeError("llm_triage_missing_key")
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
            raise RuntimeError("llm_triage_quota_exhausted") from e
        raise RuntimeError(f"llm_triage_http_{e.code}:{detail[:180]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"llm_triage_url_error:{e.reason}") from e
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"llm_triage_bad_response:{data!r}") from e


def _extract_json(text: str) -> dict:
    t = (text or "").strip()
    m = re.search(r"\{[\s\S]*\}", t)
    if not m:
        raise RuntimeError(f"llm_triage_no_json:{t[:160]}")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"llm_triage_bad_json:{t[:160]}") from e


def _clean_lines(items: list, limit: int = 4) -> list[str]:
    out: list[str] = []
    for x in items:
        s = str(x).strip()
        if not s:
            continue
        out.append(s[:120])
        if len(out) >= limit:
            break
    return out


def triage_failures(
    *,
    run_id: str,
    suite: str,
    bugs: list[dict],
    bug_analysis: dict,
    formal_fail_samples: list[dict],
    corpus_fail_samples: list[dict],
    project_root: Path | None = None,
) -> dict:
    """Return triage insight dict with summary lines and action hints."""
    payload = {
        "run_id": run_id,
        "suite": suite,
        "bug_analysis": {
            "total_bugs": bug_analysis.get("total_bugs", 0),
            "open_dev_bug_total": bug_analysis.get("open_dev_bug_total", 0),
            "open_dev_bug_p0": bug_analysis.get("open_dev_bug_p0", 0),
            "env_block": bug_analysis.get("env_block", 0),
            "manual_pending": bug_analysis.get("manual_pending", 0),
        },
        "bugs": bugs[:20],
        "formal_fail_samples": formal_fail_samples[:20],
        "corpus_fail_samples": corpus_fail_samples[:20],
    }
    prompt = (
        "你是QA失败归因分析Agent。根据输入的失败样本与缺陷聚合结果，"
        "输出可执行的根因归纳和优先级建议。"
        "不要编造不存在的系统字段。"
        "只返回JSON："
        '{"summary_lines":[最多4条],"priority_actions":[最多3条],"risk_level":"高/中/低"}'
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    raw = _chat(messages, project_root=project_root)
    obj = _extract_json(raw)

    summary_lines = _clean_lines(obj.get("summary_lines") or [])
    priority_actions = _clean_lines(obj.get("priority_actions") or [], limit=3)
    risk_level = str(obj.get("risk_level", "")).strip()[:8]
    if not summary_lines:
        raise RuntimeError("llm_triage_empty_summary")
    return {
        "summary_lines": summary_lines,
        "priority_actions": priority_actions,
        "risk_level": risk_level,
        "note": "llm_triage_applied",
    }
