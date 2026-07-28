#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-file project entry for the Hot70 FAQ eval chain."""

from __future__ import annotations

import argparse

from chatbot_eval import generate_cases
from chatbot_eval.run import main as run_main


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hot70 FAQ → cases → scenarios → eval reports",
        epilog=(
            "Other arguments are passed to chatbot_eval.run, for example: "
            "--limit-groups 3 --workers 1 --llm-judge --keep-data"
        ),
    )
    parser.add_argument(
        "--generate-cases",
        action="store_true",
        help="Regenerate profiles/hot70/data/Hot70_机器人_知识库指标测试.csv from the FAQ CSV before running.",
    )
    parser.add_argument(
        "--disable-llm-followup",
        action="store_true",
        help="When generating cases, use deterministic fallback follow-up questions instead of LLM.",
    )
    args, remaining = parser.parse_known_args()
    if args.generate_cases:
        generate_args = ["--disable-llm-followup"] if args.disable_llm_followup else []
        generate_cases.main(generate_args)
        remaining = ["--rebuild", *remaining] if "--rebuild" not in remaining else remaining
    remaining = ["--report", *remaining] if "--report" not in remaining else remaining
    return run_main(remaining)


if __name__ == "__main__":
    raise SystemExit(main())
