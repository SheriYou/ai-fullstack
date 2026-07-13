#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Optional LLM report agent for concise run-level insights."""
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


def report_enabled() -> bool:
    return _truthy("USE_LLM_REPORT", "0")


def _consume_budget() -> None:
    global _CALL_COUNT
    if _DISABLED_BY_QUOTA:
        raise RuntimeError("llm_report_quota_exhausted")
    max_calls = _int_env("LLM_REPORT_MAX_CALLS", 1)
    if max_calls > 0 and _CALL_COUNT >= max_calls:
        raise RuntimeError("llm_report_budget_exhausted")
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
        raise RuntimeError("llm_report_missing_key")
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
            raise RuntimeError("llm_report_quota_exhausted") from e
        raise RuntimeError(f"llm_report_http_{e.code}:{detail[:180]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"llm_report_url_error:{e.reason}") from e
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"llm_report_bad_response:{data!r}") from e


def _extract_json(text: str) -> dict:
    t = (text or "").strip()
    m = re.search(r"\{[\s\S]*\}", t)
    if not m:
        raise RuntimeError(f"llm_report_no_json:{t[:160]}")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"llm_report_bad_json:{t[:160]}") from e


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


def build_report_insights(
    *,
    run_id: str,
    suite: str,
    metrics: dict,
    bug_analysis: dict,
    bugs: list[dict],
    project_root: Path | None = None,
) -> dict:
    """Return report-level insight lines for markdown section."""
    payload = {
        "run_id": run_id,
        "suite": suite,
        "metrics": metrics,
        "bug_analysis": {
            "total_bugs": bug_analysis.get("total_bugs", 0),
            "open_dev_bug_total": bug_analysis.get("open_dev_bug_total", 0),
            "open_dev_bug_p0": bug_analysis.get("open_dev_bug_p0", 0),
            "env_block": bug_analysis.get("env_block", 0),
            "manual_pending": bug_analysis.get("manual_pending", 0),
        },
        "top_bugs": bugs[:8],
    }
    prompt = (
        "你是测试报告洞察Agent。请基于输入指标和缺陷概览，输出给研发与测试的简短结论。"
        "不要重复原始数字表格，不要编造。"
        "只返回JSON："
        '{"headline":"一句话","insight_lines":[最多4条],"next_actions":[最多3条]}'
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    raw = _chat(messages, project_root=project_root)
    obj = _extract_json(raw)

    headline = str(obj.get("headline", "")).strip()[:120]
    insight_lines = _clean_lines(obj.get("insight_lines") or [], limit=4)
    next_actions = _clean_lines(obj.get("next_actions") or [], limit=3)
    if not headline and not insight_lines and not next_actions:
        raise RuntimeError("llm_report_empty_output")
    return {
        "headline": headline,
        "insight_lines": insight_lines,
        "next_actions": next_actions,
        "note": "llm_report_applied",
    }
