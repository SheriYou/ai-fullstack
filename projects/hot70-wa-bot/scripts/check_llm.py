# -*- coding: utf-8 -*-
"""Verify LLM API connectivity (集采 OpenAI 兼容网关)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "lib"))

from llm_client import LlmConfigError, chat, get_llm_config  # noqa: E402


def main():
    proj = Path(__file__).resolve().parents[1]
    try:
        cfg = get_llm_config(proj)
    except LlmConfigError as e:
        print(f"配置不完整: {e}")
        sys.exit(1)

    print(f"检查 LLM: base={cfg['base_url']} model={cfg['model']}")
    reply = chat(
        [{"role": "user", "content": "回复 OK 两个字母即可"}],
        project_root=proj,
    )
    print(f"连通成功，模型回复: {reply.strip()[:80]}")


if __name__ == "__main__":
    main()
