"""Agent-style orchestration entrypoint for chatbot eval runs.

The core framework stays modular: case generation, scenario building, running,
and reporting still live in their own modules. This file adds a thin control
layer that can turn a concise human request into a repeatable eval run and then
summarize the produced artifacts.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import generate_cases
from .run import main as run_main

DEFAULT_PROFILE = "hot70"
DEFAULT_PROFILE_ROOT = Path(__file__).resolve().parents[1] / "profiles" / DEFAULT_PROFILE


@dataclass
class EvalAgentPlan:
    """A small, serializable plan for one eval-agent action."""

    profile: str = DEFAULT_PROFILE
    profile_root: Path = DEFAULT_PROFILE_ROOT
    generate_cases: bool = False
    disable_llm_followup: bool = False
    rebuild: bool = False
    report: bool = True
    phase: str | None = None
    limit_groups: int = 0
    workers: int = 6
    llm_judge: bool = False
    llm_tag_judge: bool = False
    keep_data: bool = False
    extra_run_args: list[str] = field(default_factory=list)

    def run_args(self) -> list[str]:
        args = ["--profile-root", str(self.profile_root)]
        if self.rebuild:
            args.append("--rebuild")
        if self.report:
            args.append("--report")
        if self.phase:
            args.extend(["--phase", self.phase])
        if self.limit_groups:
            args.extend(["--limit-groups", str(self.limit_groups)])
        if self.workers:
            args.extend(["--workers", str(self.workers)])
        if self.llm_judge:
            args.append("--llm-judge")
        if self.llm_tag_judge:
            args.append("--llm-tag-judge")
        if self.keep_data:
            args.append("--keep-data")
        args.extend(self.extra_run_args)
        return args

    def generate_args(self) -> list[str]:
        args = ["--profile", self.profile, "--profile-root", str(self.profile_root)]
        if self.disable_llm_followup:
            args.append("--disable-llm-followup")
        return args

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "profile_root": str(self.profile_root),
            "generate_cases": self.generate_cases,
            "disable_llm_followup": self.disable_llm_followup,
            "rebuild": self.rebuild,
            "report": self.report,
            "phase": self.phase,
            "limit_groups": self.limit_groups,
            "workers": self.workers,
            "llm_judge": self.llm_judge,
            "llm_tag_judge": self.llm_tag_judge,
            "keep_data": self.keep_data,
            "run_args": self.run_args(),
        }


def _has_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _parse_limit(text: str) -> int:
    patterns = (
        r"(?:limit(?:-groups)?|限制|前|只跑|跑)\s*[:=：]?\s*(\d+)\s*(?:组|groups?)",
        r"(\d+)\s*(?:组|groups?)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return int(match.group(1))
    return 0


def _parse_workers(text: str, default: int) -> int:
    match = re.search(r"(?:workers?|并发)\s*[:=：]?\s*(\d+)", text, re.I)
    return int(match.group(1)) if match else default


def parse_request(request: str, defaults: EvalAgentPlan | None = None) -> EvalAgentPlan:
    """Parse a practical subset of natural language into an eval plan."""

    plan = defaults or EvalAgentPlan()
    text = request.strip()
    lowered = text.lower()

    phase = re.search(r"\b(P[012])\b", text, re.I)
    if phase:
        plan.phase = phase.group(1).upper()

    limit_groups = _parse_limit(text)
    if limit_groups:
        plan.limit_groups = limit_groups

    plan.workers = _parse_workers(text, plan.workers)

    if _has_any(lowered, ("generate cases", "refresh cases")) or _has_any(text, ("生成用例", "刷新用例", "重建用例")):
        plan.generate_cases = True
        plan.rebuild = True
    if _has_any(text, ("不生成用例", "不要生成用例")) or "no generate" in lowered:
        plan.generate_cases = False

    if _has_any(text, ("禁用追问LLM", "不用LLM追问", "不用 llm 追问")) or "disable-llm-followup" in lowered:
        plan.disable_llm_followup = True

    if _has_any(text, ("重建场景", "重建 scenarios")) or "--rebuild" in lowered:
        plan.rebuild = True

    if _has_any(text, ("不生成报告", "不要报告")) or "no report" in lowered:
        plan.report = False

    if _has_any(lowered, ("llm judge", "semantic judge")) or _has_any(text, ("语义判定", "LLM判定", "LLM judge")):
        plan.llm_judge = True
    if _has_any(lowered, ("tag judge", "llm tag")) or _has_any(text, ("标签判定", "客户标签判定")):
        plan.llm_tag_judge = True

    if _has_any(text, ("保留数据", "不清理数据")) or "keep data" in lowered:
        plan.keep_data = True

    return plan


def _latest_pointer(profile_root: Path) -> dict[str, Any] | None:
    pointer_path = profile_root / "reports" / "latest-run.json"
    if not pointer_path.exists():
        return None
    return json.loads(pointer_path.read_text(encoding="utf-8"))


def _load_summary(profile_root: Path, pointer: dict[str, Any]) -> dict[str, Any] | None:
    run_dir = profile_root / pointer.get("dir", "")
    summary_path = run_dir / pointer.get("summary_json", "summary.json")
    if not summary_path.exists():
        return None
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _load_failures(profile_root: Path, pointer: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    run_id = pointer.get("run_id")
    candidates = [
        profile_root / "tmp" / "results.jsonl",
        profile_root / "reports" / "runs" / str(run_id) / "results.jsonl",
    ]
    results_path = next((path for path in candidates if path.exists()), None)
    if not results_path:
        return []
    failures: list[dict[str, Any]] = []
    with results_path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("run_id") == run_id and item.get("verdict") != "PASS":
                failures.append(item)
            if len(failures) >= limit:
                break
    return failures


def summarize_latest(profile_root: Path, failure_limit: int = 10) -> dict[str, Any]:
    pointer = _latest_pointer(profile_root)
    if not pointer:
        return {"status": "NO_REPORT", "message": f"No latest report found under {profile_root / 'reports'}"}
    summary = _load_summary(profile_root, pointer) or {}
    failures = _load_failures(profile_root, pointer, limit=failure_limit)
    return {
        "status": "OK",
        "run_id": pointer.get("run_id"),
        "report_dir": str((profile_root / pointer.get("dir", "")).resolve()),
        "summary": summary,
        "failures": [
            {
                "case_id": item.get("case_id"),
                "verdict": item.get("verdict"),
                "phase": item.get("phase"),
                "query": item.get("query"),
                "reply": item.get("reply"),
                "scores": item.get("scores"),
                "signals": item.get("signals"),
                "error": item.get("error"),
            }
            for item in failures
        ],
    }


def _print_agent_summary(summary: dict[str, Any]) -> None:
    if summary.get("status") != "OK":
        print(summary.get("message", "No report summary available."))
        return

    data = summary.get("summary") or {}
    print("\n=== Agent Summary ===")
    print(f"run_id: {summary.get('run_id')}")
    print(f"report_dir: {summary.get('report_dir')}")
    if data:
        print(f"total_turns: {data.get('total_turns')}")
        verdicts = data.get("verdicts") or {}
        print("verdicts: " + ", ".join(f"{key}={value}" for key, value in sorted(verdicts.items())))
    failures = summary.get("failures") or []
    if not failures:
        print("failures: none in latest results")
        return
    print(f"failures_top{len(failures)}:")
    for item in failures:
        query = (item.get("query") or "")[:80]
        print(f"  - {item.get('case_id')} [{item.get('verdict')}] {query!r}")


def execute_plan(plan: EvalAgentPlan, dry_run: bool = False) -> int:
    print("=== Eval Agent Plan ===")
    print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
    if dry_run:
        return 0

    if plan.generate_cases:
        rc = generate_cases.main(plan.generate_args())
        if rc:
            return rc
        plan.rebuild = True

    rc = run_main(plan.run_args())
    if rc:
        return rc

    if plan.report:
        _print_agent_summary(summarize_latest(plan.profile_root))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Agent-style entrypoint for chatbot eval. Accepts options or a short natural-language request.",
    )
    parser.add_argument("request", nargs="*", help="Natural-language request, e.g. 跑 P0 3组 并发1 生成报告")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--profile-root", default=str(DEFAULT_PROFILE_ROOT))
    parser.add_argument("--generate-cases", action="store_true")
    parser.add_argument("--disable-llm-followup", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--no-report", action="store_true")
    parser.add_argument("--phase", choices=("P0", "P1", "P2"))
    parser.add_argument("--limit-groups", type=int, default=0)
    parser.add_argument("--workers", type=int)
    parser.add_argument("--llm-judge", action="store_true")
    parser.add_argument("--llm-tag-judge", action="store_true")
    parser.add_argument("--keep-data", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--show-latest", action="store_true", help="Only summarize the latest report.")
    parser.add_argument("--extra-run-arg", action="append", default=[], help="Forward one raw arg to chatbot_eval.run.")
    args = parser.parse_args(argv)

    profile_root = Path(args.profile_root)
    if args.show_latest:
        _print_agent_summary(summarize_latest(profile_root))
        return 0

    plan = EvalAgentPlan(profile=args.profile, profile_root=profile_root)
    if args.request:
        plan = parse_request(" ".join(args.request), plan)

    plan.generate_cases = plan.generate_cases or args.generate_cases
    plan.disable_llm_followup = plan.disable_llm_followup or args.disable_llm_followup
    plan.rebuild = plan.rebuild or args.rebuild
    plan.report = not args.no_report and plan.report
    plan.phase = args.phase or plan.phase
    plan.limit_groups = args.limit_groups or plan.limit_groups
    plan.workers = args.workers if args.workers is not None else plan.workers
    plan.llm_judge = plan.llm_judge or args.llm_judge
    plan.llm_tag_judge = plan.llm_tag_judge or args.llm_tag_judge
    plan.keep_data = plan.keep_data or args.keep_data
    plan.extra_run_args = args.extra_run_arg

    try:
        return execute_plan(plan, dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
