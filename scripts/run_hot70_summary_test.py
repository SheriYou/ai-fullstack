#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run Hot70 summary-conversation CSV cases against one environment.

This is intentionally separate from the existing eval framework. It executes
the CSV's own conversation semantics:

- group rows by "会话组ID" in the 备注 column
- sort rows by "同组执行序号"
- reuse one whatsapp_id for all rows in the same group
- stop immediately on send/no-reply/signal-read errors
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES_CSV = REPO_ROOT / "profiles" / "hot70" / "data" / "Hot70_汇总会话问题_测试用例.csv"
DEFAULT_OUT_DIR = REPO_ROOT / "profiles" / "hot70" / "reports" / "summary_test_runs"

CASE_ID_COL = "用例ID"
QUERY_COL = "测试数据（英文提问）"
QUERY_FALLBACK_COL = "测试数据"
NEW_SESSION_COL = "是否使用新会话"
PHASE_COL = "执行阶段"
NOTE_COL = "备注"

GROUP_RE = re.compile(r"会话组ID=([^；;]+)")
ORDER_RE = re.compile(r"同组执行序号=(\d+)")
TOTAL_RE = re.compile(r"同组问题总数=(\d+)")


def _read_rows(path: Path) -> list[dict[str, str]]:
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "cp936"):
        try:
            with path.open(encoding=encoding, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError(f"unable to read CSV: {path}")


def _note_value(pattern: re.Pattern[str], note: str) -> str:
    match = pattern.search(note or "")
    return match.group(1).strip() if match else ""


def _case_id(row: dict[str, str]) -> str:
    value = (row.get(CASE_ID_COL) or "").strip()
    if not value:
        raise RuntimeError("CSV row is missing 用例ID")
    return value


def _query(row: dict[str, str]) -> str:
    value = (row.get(QUERY_COL) or "").strip() or (row.get(QUERY_FALLBACK_COL) or "").strip()
    if not value:
        raise RuntimeError(f"{_case_id(row)} is missing test query")
    return value


def _group_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[tuple[int, int, dict[str, str]]]] = {}
    order: list[str] = []
    for row_index, row in enumerate(rows, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        case_id = _case_id(row)
        note = row.get(NOTE_COL) or ""
        group_id = _note_value(GROUP_RE, note) or case_id
        turn_order_raw = _note_value(ORDER_RE, note)
        turn_order = int(turn_order_raw) if turn_order_raw else row_index
        if group_id not in grouped:
            grouped[group_id] = []
            order.append(group_id)
        grouped[group_id].append((turn_order, row_index, row))

    groups: list[dict[str, Any]] = []
    for group_id in order:
        turns = [row for _, _, row in sorted(grouped[group_id], key=lambda item: (item[0], item[1]))]
        totals = {
            int(total)
            for total in (_note_value(TOTAL_RE, row.get(NOTE_COL) or "") for row in turns)
            if total.isdigit()
        }
        if totals and len(turns) not in totals:
            raise RuntimeError(f"group {group_id} has {len(turns)} rows, but note declares totals {sorted(totals)}")
        groups.append({"group_id": group_id, "turns": turns})
    if not groups:
        raise RuntimeError("CSV has no executable rows")
    return groups


def _safe_suffix(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _wa_id(run_tag: str, group_id: str) -> str:
    return f"evalsum{run_tag}{_safe_suffix(group_id)}@c.us"


def _write_jsonl(path: Path, item: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _message_id_variants(msg_id: str) -> list[str]:
    variants = {msg_id}
    if not msg_id.startswith("local_gateway_"):
        variants.add("local_gateway_" + msg_id)
        variants.add("out_local_gateway_" + msg_id)
    return sorted(variants)


def _wait_reply_by_msg_id(harness: Any, wa_id: str, msg_id: str, timeout_s: int, poll_s: float = 2.0) -> str | None:
    wa = harness.sql_escape(wa_id)
    mids = _message_id_variants(msg_id)
    mid_sql = " OR ".join(
        "message_id='%s' OR message_id LIKE '%%%s%%'"
        % (harness.sql_escape(mid), harness.sql_escape(mid))
        for mid in mids
    )
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        row = harness.mysql(
            "SELECT content FROM wa_chat_message "
            "WHERE whatsapp_id='%s' AND direction='outbound' AND (%s) "
            "ORDER BY `timestamp` ASC LIMIT 1" % (wa, mid_sql)
        )
        if row:
            return row
        time.sleep(poll_s)
    return None


def _build_summary(
    run_id: str,
    args: argparse.Namespace,
    out_path: Path,
    groups: list[dict[str, Any]],
    executed: list[dict[str, Any]],
    stopped_reason: str | None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "environment": args.env,
        "cases_csv": str(Path(args.cases_csv).resolve()),
        "output_jsonl": str(out_path),
        "planned_groups": len(groups),
        "planned_turns": sum(len(group["turns"]) for group in groups),
        "executed_turns": len(executed),
        "last_case_id": executed[-1]["case_id"] if executed else None,
        "stopped_reason": stopped_reason,
        "started_at": args.started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
    }


def _select_groups(groups: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    selected = groups
    if args.phase:
        selected = [
            {
                "group_id": group["group_id"],
                "turns": [row for row in group["turns"] if (row.get(PHASE_COL) or "").strip() == args.phase],
            }
            for group in selected
        ]
        selected = [group for group in selected if group["turns"]]
    if args.start_group:
        seen = False
        trimmed = []
        for group in selected:
            if group["group_id"] == args.start_group:
                seen = True
            if seen:
                trimmed.append(group)
        if not seen:
            raise RuntimeError(f"start group not found: {args.start_group}")
        selected = trimmed
    if args.limit_groups:
        selected = selected[: args.limit_groups]
    return selected


def _load_runtime(env: str):
    os.environ["TEST_ENV"] = env
    os.environ.setdefault("AHT_PROJECT_ROOT", str(REPO_ROOT / "profiles" / "hot70"))
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from chatbot_eval import harness, signals  # noqa: PLC0415

    return harness, signals


def run(args: argparse.Namespace) -> int:
    args.started_at = datetime.now().isoformat(timespec="seconds")
    harness, signals = _load_runtime(args.env)

    cases_csv = Path(args.cases_csv)
    rows = _read_rows(cases_csv)
    groups = _select_groups(_group_rows(rows), args)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    run_tag = run_id.replace("-", "")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{run_id}.jsonl"
    summary_path = out_dir / f"{run_id}.summary.json"

    print(f"run_id={run_id}")
    print(f"env={args.env}")
    print(f"bot_url={harness.BOT_URL}")
    print(f"cases_csv={cases_csv.resolve()}")
    print(f"groups={len(groups)} turns={sum(len(group['turns']) for group in groups)}")
    print(f"output={out_path}")

    if args.health_check and not harness.backend_healthy():
        raise RuntimeError(f"backend health check failed: {harness.BOT_URL}/actuator/health")

    executed: list[dict[str, Any]] = []
    stopped_reason: str | None = None
    try:
        for group_index, group in enumerate(groups, start=1):
            group_id = group["group_id"]
            wa_id = _wa_id(run_tag, group_id)
            print(f"\n[{group_index}/{len(groups)}] group={group_id} wa_id={wa_id}")
            for turn_index, row in enumerate(group["turns"], start=1):
                case_id = _case_id(row)
                query = _query(row)
                expected_new = (row.get(NEW_SESSION_COL) or "").strip()
                if turn_index == 1 and expected_new == "否":
                    raise RuntimeError(f"{case_id} is first in group {group_id}, but 是否使用新会话=否")
                if turn_index > 1 and expected_new == "是":
                    raise RuntimeError(f"{case_id} is not first in group {group_id}, but 是否使用新会话=是")

                msg_id = f"{case_id}-{run_tag}"
                print(f"  turn={turn_index}/{len(group['turns'])} case={case_id} send")
                api_start = time.perf_counter()
                harness.send(wa_id, query, msg_id, sender_name=case_id)
                reply = _wait_reply_by_msg_id(harness, wa_id, msg_id, timeout_s=args.reply_timeout)
                api_elapsed_ms = int((time.perf_counter() - api_start) * 1000)
                if reply is None:
                    raise RuntimeError(f"{case_id} no reply within {args.reply_timeout}s")
                sig = signals.read_turn_signals(wa_id, msg_id, tag_wait_s=args.tag_wait)
                result = {
                    "run_id": run_id,
                    "env": args.env,
                    "group_id": group_id,
                    "wa_id": wa_id,
                    "case_id": case_id,
                    "turn_index": turn_index,
                    "query": query,
                    "reply": reply,
                    "signals": sig,
                    "api_elapsed_ms": api_elapsed_ms,
                    "raw": row,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                }
                _write_jsonl(out_path, result)
                executed.append(result)
                print(
                    "    ok "
                    f"reply_len={len(reply)} "
                    f"kb_hit={sig.get('kb_hit')} "
                    f"handoff={sig.get('handoff')} "
                    f"tag={sig.get('tag') or ''}"
                )
    except Exception as exc:  # noqa: BLE001
        stopped_reason = str(exc)
        print(f"\nSTOPPED: {stopped_reason}", file=sys.stderr)
        summary = _build_summary(run_id, args, out_path, groups, executed, stopped_reason)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"summary={summary_path}")
        return 2

    summary = _build_summary(run_id, args, out_path, groups, executed, stopped_reason)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDONE summary={summary_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Hot70 summary conversation cases in test/uat/etc.")
    parser.add_argument("--cases-csv", default=str(DEFAULT_CASES_CSV))
    parser.add_argument("--env", default="test", help="Loads profiles/hot70/config.<env>.env through chatbot_eval.harness")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--phase", choices=("P0", "P1", "P2"))
    parser.add_argument("--start-group")
    parser.add_argument("--limit-groups", type=int, default=0)
    parser.add_argument("--reply-timeout", type=int, default=120)
    parser.add_argument("--tag-wait", type=float, default=0.0)
    parser.add_argument("--health-check", action=argparse.BooleanOptionalAction, default=True)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
