"""Concurrent scenario runner + deterministic scoring."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from . import build_scenarios, cleanup, harness, signals

DEFAULT_PROFILE_ROOT = Path(__file__).resolve().parents[1] / "profiles" / "hot70"
DEFAULT_SCENARIOS = DEFAULT_PROFILE_ROOT / "tmp" / "scenarios.json"
DEFAULT_CASES_CSV = DEFAULT_PROFILE_ROOT / "data" / "Hot70_机器人_知识库指标测试.csv"
DEFAULT_RESULTS = DEFAULT_PROFILE_ROOT / "tmp" / "results.jsonl"


def _default_profile_paths(profile_root: str | Path) -> tuple[Path, Path, Path]:
    root = Path(profile_root)
    profile_json = root / "profile.json"
    if profile_json.exists():
        profile = json.loads(profile_json.read_text(encoding="utf-8"))
        return (
            root / profile.get("cases_csv", "data/cases.csv"),
            root / profile.get("scenarios_json", "tmp/scenarios.json"),
            root / profile.get("results_jsonl", "tmp/results.jsonl"),
        )
    return (
        root / "data" / "Hot70_机器人_知识库指标测试.csv",
        root / "tmp" / "scenarios.json",
        root / "tmp" / "results.jsonl",
    )


def _csv_fieldnames(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f).fieldnames or [])


def score_turn(turn: dict, sig: dict, reply: str | None, answer_threshold: float) -> dict:
    expect = turn["expect"]
    keywords = expect["answer_keywords"]
    matched = [keyword for keyword in keywords if keyword.lower() in (reply or "").lower()] if keywords else []
    answer_correct = None
    if keywords and not expect["handoff"]:
        answer_correct = (len(matched) / len(keywords)) >= answer_threshold
    tag_correct = None
    if expect["expected_tag"]:
        tag_correct = sig["tag"] == expect["expected_tag"]
    kb_hit_correct = None
    if not expect["handoff"] and not sig["handoff"]:
        kb_hit_correct = sig["kb_hit"] == expect["kb_should_hit"]
    return {
        "kb_hit_correct": kb_hit_correct,
        "handoff_correct": sig["handoff"] == expect["handoff"],
        "tag_correct": tag_correct,
        "answer_keywords": keywords,
        "answer_matched": len(matched),
        "answer_correct": answer_correct,
        "semantic_ok": "待复核",
    }


def _norm_tag(tag: str | None) -> str | None:
    if not tag or tag in ("无", "NULL", "null", "NA", "N/A", "无法判断"):
        return None
    return str(tag).strip().replace("预订", "预定")


def _session_suffix(case_id: str) -> str:
    return re.sub(r"[^a-z0-9]", "", case_id.lower())


def _wa_id(run_tag: str, case_id: str) -> str:
    return f"eval{run_tag}{_session_suffix(case_id)}@c.us"


def _empty_sig() -> dict:
    return {
        "kb_hit": False,
        "handoff": False,
        "tag": None,
        "tag_source": None,
        "grounding": None,
        "latency_ms": None,
        "detected_intent": None,
        "trace_id": None,
        "step_note": None,
    }


def _verdict(scores: dict) -> str:
    checks = [scores["handoff_correct"], scores["kb_hit_correct"], scores["answer_correct"], scores["tag_correct"]]
    applicable = [check for check in checks if check is not None]
    return "PASS" if applicable and all(applicable) else "FAIL"


def _turn_result(
    turn: dict,
    group_id: str,
    reply: str | None,
    sig: dict,
    verdict: str,
    answer_threshold: float,
    err: str | None = None,
    scores: dict | None = None,
    user_context: list[str] | None = None,
    api_elapsed_ms: int | None = None,
    setup_only: bool = False,
) -> dict:
    if scores is None:
        scores = score_turn(turn, sig, reply or "", answer_threshold)
    return {
        "case_id": turn["case_id"],
        "group_id": group_id,
        "kind": turn["kind"],
        "query": turn["query"],
        "phase": turn["phase"],
        "reply": reply,
        "signals": sig,
        "expect": turn["expect"],
        "scores": scores,
        "verdict": verdict,
        "raw": turn["raw"],
        "error": err,
        "user_context": user_context or [turn["query"]],
        "api_elapsed_ms": api_elapsed_ms,
        "setup_only": setup_only,
    }


def _tick(verdict: str, case_id: str, detail: str) -> None:
    line = f"  [{verdict:11}] {case_id} -> {detail!r}"
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(line.encode(encoding, errors="replace").decode(encoding, errors="replace"))


def _send_turn(
    turn: dict,
    group_id: str,
    wa_id: str,
    run_tag: str,
    answer_threshold: float,
    msg_id_suffix: str | None = None,
    user_context: list[str] | None = None,
    tag_wait_s: float = 0.0,
    tick: bool = True,
    setup_only: bool = False,
) -> list[dict]:
    case_id = turn["case_id"]
    suffix = f"-{msg_id_suffix}" if msg_id_suffix else ""
    msg_id = f"{case_id}-{run_tag}{suffix}"
    start_ms = harness.now_ms()
    api_start = time.perf_counter()
    api_elapsed_ms: int | None = None
    try:
        harness.send(wa_id, turn["query"], msg_id, sender_name=case_id)
        reply = harness.wait_reply(wa_id, start_ms, timeout_s=120, msg_id=msg_id)
        api_elapsed_ms = int((time.perf_counter() - api_start) * 1000)
        tag_wait = tag_wait_s or (10.0 if turn.get("expect", {}).get("expected_tag") else 0.0)
        sig = signals.read_turn_signals(wa_id, msg_id, tag_wait_s=tag_wait)
    except Exception as exc:  # noqa: BLE001
        api_elapsed_ms = int((time.perf_counter() - api_start) * 1000)
        if tick:
            _tick("SEND_ERROR", case_id, str(exc))
        return [
            _turn_result(
                turn,
                group_id,
                None,
                _empty_sig(),
                "SEND_ERROR",
                answer_threshold,
                str(exc),
                user_context=user_context,
                api_elapsed_ms=api_elapsed_ms,
                setup_only=setup_only,
            )
        ]

    if reply is None:
        if tick:
            _tick("NO_REPLY", case_id, "")
        return [
            _turn_result(
                turn,
                group_id,
                None,
                sig,
                "NO_REPLY",
                answer_threshold,
                user_context=user_context,
                api_elapsed_ms=api_elapsed_ms,
                setup_only=setup_only,
            )
        ]

    scores = score_turn(turn, sig, reply, answer_threshold)
    verdict = _verdict(scores)
    if tick:
        _tick(verdict, case_id, (reply or "")[:60])
    return [
        _turn_result(
            turn,
            group_id,
            reply,
            sig,
            verdict,
            answer_threshold,
            scores=scores,
            user_context=user_context,
            api_elapsed_ms=api_elapsed_ms,
            setup_only=setup_only,
        )
    ]


def run_group(
    group: dict,
    run_tag: str,
    answer_threshold: float,
    tag_wait_s: float = 0.0,
    phase: str | None = None,
    stop_on_failure: bool = False,
) -> list[dict]:
    group_id = group["group_id"]
    turns = group["turns"]
    base_turn = next((turn for turn in turns if turn["kind"] == "N"), None)
    condition_turns = [turn for turn in turns if turn["kind"] != "N"]
    if phase:
        run_base = bool(base_turn and base_turn.get("phase") == phase)
        condition_turns = [turn for turn in condition_turns if turn.get("phase") == phase]
    else:
        run_base = bool(base_turn)
    results: list[dict] = []

    if run_base and base_turn:
        results.extend(
            _send_turn(
                base_turn,
                group_id,
                _wa_id(run_tag, base_turn["case_id"]),
                run_tag,
                answer_threshold,
                user_context=[base_turn["query"]],
                tag_wait_s=tag_wait_s,
            )
        )
        if stop_on_failure and results[-1]["verdict"] != "PASS":
            return results

    for turn in condition_turns:
        wa_id = _wa_id(run_tag, turn["case_id"])
        if base_turn:
            setup = _send_turn(
                base_turn,
                group_id,
                wa_id,
                run_tag,
                answer_threshold,
                msg_id_suffix=_session_suffix(turn["case_id"]),
                user_context=[base_turn["query"]],
                tag_wait_s=tag_wait_s,
                tick=False,
                setup_only=True,
            )
            if not setup or setup[0]["verdict"] in ("SEND_ERROR", "NO_REPLY"):
                setup_verdict = setup[0]["verdict"] if setup else "UNKNOWN"
                err = f"setup {base_turn['case_id']} failed: {setup_verdict}"
                _tick("SETUP_ERROR", turn["case_id"], err)
                results.append(
                    _turn_result(
                        turn,
                        group_id,
                        None,
                        _empty_sig(),
                        "SETUP_ERROR",
                        answer_threshold,
                        err=err,
                        user_context=[base_turn["query"], turn["query"]],
                    )
                )
                continue
            if stop_on_failure and setup[0]["verdict"] != "PASS":
                return results
        context = [base_turn["query"], turn["query"]] if base_turn else [turn["query"]]
        results.extend(
            _send_turn(
                turn,
                group_id,
                wa_id,
                run_tag,
                answer_threshold,
                user_context=context,
                tag_wait_s=tag_wait_s,
            )
        )
        if stop_on_failure and results[-1]["verdict"] != "PASS":
            return results
    return results


def _run_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]


def _load_or_build(args: argparse.Namespace) -> dict:
    scenarios_path = Path(args.scenarios)
    cases_csv = Path(args.cases_csv)
    should_rebuild = args.rebuild or not scenarios_path.exists()
    if not should_rebuild:
        payload = json.loads(scenarios_path.read_text(encoding="utf-8"))
        source_csv = Path(payload.get("source_csv") or cases_csv)
        if not source_csv.is_absolute():
            source_csv = Path.cwd() / source_csv
        try:
            should_rebuild = (
                not source_csv.exists()
                or source_csv.resolve() != cases_csv.resolve()
                or cases_csv.stat().st_mtime > scenarios_path.stat().st_mtime
                or payload.get("fieldnames") != _csv_fieldnames(cases_csv)
            )
        except OSError:
            should_rebuild = True
        if not should_rebuild:
            return payload
    if should_rebuild:
        print("生成 scenarios.json ...")
        return build_scenarios.build(cases_csv, scenarios_path)
    raise RuntimeError("unable to load or build scenarios")


def _filter_groups_by_phase(groups: list[dict], phase: str | None) -> list[dict]:
    if not phase:
        return groups
    filtered: list[dict] = []
    for group in groups:
        turns = group.get("turns") or []
        if any(turn.get("phase") == phase for turn in turns):
            filtered.append(group)
    return filtered


def _write_results(results_path: str | Path, turns: list[dict], run_id: str) -> Path:
    path = Path(results_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for turn in turns:
            turn["run_id"] = run_id
            f.write(json.dumps(turn, ensure_ascii=False) + "\n")
    return path


def _load_results(results_path: str | Path, run_id: str | None = None) -> list[dict]:
    path = Path(results_path)
    turns: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            turn = json.loads(line)
            if run_id and turn.get("run_id") != run_id:
                continue
            turns.append(turn)
    if not turns:
        suffix = f" for run_id={run_id}" if run_id else ""
        raise RuntimeError(f"empty results file{suffix}: {path}")
    return turns


def _apply_llm_judges(turns: list[dict], args: argparse.Namespace, run_id: str) -> None:
    results_path = Path(args.results)
    if args.llm_judge:
        from . import judge

        items = [
            {
                "case_id": turn["case_id"],
                "query": turn["query"],
                "reply": turn["reply"],
                "expected_handoff": turn["expect"]["handoff"],
                "answer_keywords": turn["expect"]["answer_keywords"],
            }
            for turn in turns
            if turn["reply"]
        ]
        print(f"\nLLM semantic judge: {len(items)} items ...")
        verdicts = judge.judge_semantic(items)
        for turn in turns:
            judgement = verdicts.get(turn["case_id"])
            if judgement:
                turn["scores"]["semantic_ok"] = judgement["ok"]
                turn["scores"]["semantic_reason"] = judgement.get("reason")
        _write_results(results_path, turns, run_id)

    if args.llm_tag_judge:
        from . import judge

        items = [
            {"case_id": turn["case_id"], "user_context": turn.get("user_context") or [turn["query"]]}
            for turn in turns
            if turn["verdict"] != "SETUP_ERROR"
        ]
        print(f"\nLLM expected-tag judge: {len(items)} items ...")
        tag_judgements = judge.judge_expected_tags(items)
        for turn in turns:
            judgement = tag_judgements.get(turn["case_id"])
            if not judgement:
                continue
            expected_tag = _norm_tag(judgement.get("tag"))
            actual_tag = _norm_tag(turn["signals"].get("tag"))
            turn["expect"]["expected_tag"] = expected_tag
            turn["scores"]["expected_tag_reason"] = judgement.get("reason")
            turn["scores"]["tag_correct"] = None if expected_tag is None else actual_tag == expected_tag
            turn["verdict"] = _verdict(turn["scores"])
        _write_results(results_path, turns, run_id)


def _print_summary(turns: list[dict], results_path: str | Path) -> None:
    print("\n=== 汇总 ===")
    verdicts: dict[str, int] = {}
    for turn in turns:
        verdicts[turn["verdict"]] = verdicts.get(turn["verdict"], 0) + 1
    print("  判定分布: " + ", ".join(f"{key}={value}" for key, value in sorted(verdicts.items())))
    print(f"\n结果文件: {results_path}")
    print("  - 如需报告：python -m chatbot_eval.report --results <results.jsonl>")


def _write_report_if_requested(args: argparse.Namespace, turns: list[dict], run_id: str) -> None:
    if not args.report:
        return
    from . import report

    out_dir, _summary = report.write_reports(
        run_id,
        [],
        turns,
        llm_used=args.llm_judge,
        llm_tag_used=args.llm_tag_judge,
        project_root=Path(args.profile_root),
    )
    print(f"报告目录: {out_dir}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run chatbot eval scenarios and write results.jsonl.")
    parser.add_argument("--profile-root", default=str(DEFAULT_PROFILE_ROOT))
    parser.add_argument("--cases-csv", default=None)
    parser.add_argument("--scenarios", default=None)
    parser.add_argument("--results", default=None)
    parser.add_argument("--limit-groups", type=int, default=0)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--llm-judge", action="store_true")
    parser.add_argument("--llm-tag-judge", action="store_true")
    parser.add_argument("--answer-threshold", type=float, default=0.5)
    parser.add_argument("--phase", choices=("P0", "P1", "P2"), help="Only execute cases in this phase.")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--report", action="store_true", help="Generate reports after writing results.jsonl")
    parser.add_argument("--keep-data", action="store_true", help="Deprecated; data is kept by default.")
    parser.add_argument("--cleanup-data", action="store_true", help="Delete eval test data after the run.")
    parser.add_argument("--stop-on-failure", action="store_true", help="Stop after the first non-PASS result.")
    parser.add_argument("--fail-on-unhealthy", action="store_true", help="Abort if the backend health check fails.")
    parser.add_argument("--postprocess-only", action="store_true", help="Run LLM judges/report from an existing results file.")
    parser.add_argument("--run-id", help="Run id to postprocess when results file contains multiple runs.")
    args = parser.parse_args(argv)
    profile_cases_csv, profile_scenarios, profile_results = _default_profile_paths(args.profile_root)
    args.cases_csv = args.cases_csv or str(profile_cases_csv)
    args.scenarios = args.scenarios or str(profile_scenarios)
    args.results = args.results or str(profile_results)

    if args.postprocess_only:
        report_turns = _load_results(args.results, args.run_id)
        run_tag = args.run_id or str(report_turns[0].get("run_id") or Path(args.results).stem)
        _apply_llm_judges(report_turns, args, run_tag)
        _print_summary(report_turns, args.results)
        _write_report_if_requested(args, report_turns, run_tag)
        return 0

    payload = _load_or_build(args)
    groups = payload["groups"]
    groups = _filter_groups_by_phase(groups, args.phase)
    if args.limit_groups:
        groups = groups[: args.limit_groups]

    if args.fail_on_unhealthy and not harness.backend_healthy():
        raise RuntimeError(f"backend {harness.BOT_URL} health check failed")

    if not harness.backend_healthy():
        print(f"backend {harness.BOT_URL} health check failed; continuing anyway.")

    run_tag = _run_id()
    total_turns = sum(
        1
        for group in groups
        for turn in group["turns"]
        if not args.phase or turn.get("phase") == args.phase
    )
    print(
        f"=== eval start run_tag={run_tag} groups={len(groups)} turns={total_turns} "
        f"workers={args.workers} llm_judge={'on' if args.llm_judge else 'off'} "
        f"llm_tag_judge={'on' if args.llm_tag_judge else 'off'} ==="
    )

    all_turns: list[dict] = []
    if args.stop_on_failure:
        for group in groups:
            result = run_group(
                group,
                run_tag,
                args.answer_threshold,
                tag_wait_s=10.0 if args.llm_tag_judge else 0.0,
                phase=args.phase,
                stop_on_failure=True,
            )
            all_turns.extend(result)
            print(f"progress: {len(all_turns)}/{total_turns}")
            if any(turn.get("verdict") != "PASS" for turn in result if not turn.get("setup_only")):
                print("Stop on first failure requested; aborting remaining groups.")
                break
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for result in pool.map(
                lambda group: run_group(
                    group,
                    run_tag,
                    args.answer_threshold,
                    tag_wait_s=10.0 if args.llm_tag_judge else 0.0,
                    phase=args.phase,
                ),
                groups,
            ):
                all_turns.extend(result)
                print(f"进度: {len(all_turns)}/{total_turns}")

    report_turns = [turn for turn in all_turns if not turn.get("setup_only")]
    results_path = _write_results(args.results, report_turns, run_tag)
    print(f"\n原始执行结果已写入: {results_path}")

    try:
        _apply_llm_judges(report_turns, args, run_tag)
        _print_summary(report_turns, results_path)
        _write_report_if_requested(args, report_turns, run_tag)
    finally:
        if args.cleanup_data:
            cleanup.purge(f"eval{run_tag}")
        else:
            print(f"\n(default) keeping DB rows with prefix eval{run_tag}; pass --cleanup-data to delete them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
