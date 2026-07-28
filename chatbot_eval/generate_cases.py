"""Dispatch test-case generation to a robot profile."""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path

DEFAULT_PROFILE = "hot70"
DEFAULT_PROFILE_ROOT = Path(__file__).resolve().parents[1] / "profiles" / DEFAULT_PROFILE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate test cases from a profile knowledge source.",
        epilog="Profile-specific args are forwarded, e.g. --source feishu --disable-llm-followup.",
    )
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--profile-root", default=str(DEFAULT_PROFILE_ROOT))
    args, remaining = parser.parse_known_args(argv)

    profile_root = Path(args.profile_root)
    os.environ["AHT_PROFILE_ROOT"] = str(profile_root)
    repo_root = profile_root.parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    module = importlib.import_module(f"profiles.{args.profile}.rules")
    return module.main(remaining)


if __name__ == "__main__":
    raise SystemExit(main())
