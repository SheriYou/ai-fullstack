# -*- coding: utf-8 -*-
"""OpenAI-compatible LLM client for L2 eval / RegressionRunner."""
import json
import urllib.error
import urllib.request
from pathlib import Path

from load_config import load_config


class LlmConfigError(RuntimeError):
    pass


def get_llm_config(project_root: Path | None = None) -> dict[str, str]:
    cfg = load_config(project_root)
    key = cfg.get("LLM_API_KEY", "")
    base = cfg.get("LLM_API_BASE", "").rstrip("/")
    model = cfg.get("LLM_MODEL", "gpt-4o-mini")
    if not key:
        raise LlmConfigError("缺少 LLM_API_KEY，请填写 projects/hot70-wa-bot/config.env")
    if not base:
        raise LlmConfigError("缺少 LLM_API_BASE")
    return {"api_key": key, "base_url": base, "model": model}


def chat(messages: list[dict], *, project_root: Path | None = None, temperature: float = 0) -> str:
    c = get_llm_config(project_root)
    url = f"{c['base_url']}/chat/completions"
    body = json.dumps(
        {"model": c["model"], "messages": messages, "temperature": temperature},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {c['api_key']}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"LLM HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"LLM 连接失败: {e.reason}") from e
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"LLM 响应格式异常: {data!r}") from e
