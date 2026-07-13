#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析 test-cases-full.verify_profile 并执行 Formal 用例。"""
from __future__ import annotations

import csv
import re
import uuid
from pathlib import Path

from case_executor import poll_turn_state, settle_outbound_count, user_message_from_input
from l2_eval_core import first_response_ms, session_id_from
from run_test_suite import find_conversation, outbound_texts
from test_case_verify import CaseContext, run_checks, summarize_checks

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# 共享会话：003-LOCAL 建立 handoff 后供 003b / 005 等使用
_shared: dict = {}


def parse_profile(raw: str) -> dict:
    out: dict = {"exec": "webhook", "checks": [], "manual_checks": [], "messages": None}
    if not raw or not raw.strip():
        out["checks"] = ["manual_only"]
        return out
    for part in raw.split("|"):
        part = part.strip()
        if not part:
            continue
        if part.startswith("exec:"):
            out["exec"] = part[5:]
        elif part.startswith("checks:"):
            out["checks"] = [c.strip() for c in part[7:].split(",") if c.strip()]
        elif part.startswith("manual:"):
            out["manual_checks"] = [c.strip() for c in part[7:].split(",") if c.strip()]
        elif part.startswith("messages:"):
            out["messages"] = [m.strip() for m in part[9:].split(";") if m.strip()]
        elif part.startswith("corpus:"):
            out["corpus_ref"] = part[7:]
    return out


def _resolve_messages(case: dict, profile: dict) -> list[str] | None:
    if profile.get("messages"):
        return profile["messages"]
    inp = case.get("input") or ""
    if profile["exec"] in ("defer_ext", "blocked", "metrics", "api_probe"):
        return None
    if profile["exec"] == "handoff_then_silence":
        return None
    msg = user_message_from_input(inp)
    if msg and " / " in msg:
        return [x.strip() for x in msg.split(" / ") if x.strip()]
    if msg:
        return [msg]
    if inp.strip() in ("—", "-", "external-handoff（工作台操作）"):
        return None
    return None


def _long_text(n: int = 520) -> str:
    return ("Hot70测试长文本。" * (n // 8 + 1))[:n]


def execute_case(client, channel: str, bl: int, wait: float, case: dict) -> dict:
    cid = case["id"]
    profile = parse_profile(case.get("verify_profile") or "")
    automation = (case.get("automation") or "").lower()
    checks = list(profile.get("checks") or [])
    manual_checks = list(profile.get("manual_checks") or [])

    if profile["exec"] == "blocked" or cid.startswith("TC-M9-"):
        checks = ["blocked"]
    elif profile["exec"] == "defer_ext":
        checks = ["defer_ext"]
    elif profile["exec"] == "metrics":
        checks = ["metrics_aggregate"]
    elif profile["exec"] == "manual_only" or (
        automation == "human" and not checks and not manual_checks and profile["exec"] == "webhook"
    ):
        checks = ["manual_only"]

    wa = f"tc-{uuid.uuid4().hex[:8]}@s.whatsapp.net"
    ctx = CaseContext(client=client, channel=channel, bl=bl, wait_s=wait, case_id=cid, whatsapp_id=wa)
    exec_type = profile["exec"]

    try:
        if exec_type == "handoff_then_silence":
            wa_h = _shared.get("handoff_wa")
            if not wa_h:
                wa_h = f"tc-{uuid.uuid4().hex[:8]}@s.whatsapp.net"
                st, wh = client.webhook(channel, wa_h, "转人工", sender_name=cid)
                ok = st == 200 and (wh.get("data") or {}).get("status") == "success"
                if not ok:
                    return _result(
                        case, "EXECUTED", "FAIL", "FAIL",
                        f"api_error:webhook_http={st}; phase=handoff_init",
                    )
                sess, msgs, conv, texts = poll_turn_state(
                    client, bl, wa_h, wait_s=max(wait, 12.0), expect_handoff=True,
                )
                _shared["handoff_wa"] = wa_h
                _shared["handoff_outbound_before"] = settle_outbound_count(client, bl, wa_h, settle_s=3.0)
            ctx.whatsapp_id = wa_h
            before = _shared.get("handoff_outbound_before", 0)
            followups = profile.get("messages") or ["在吗", "还有人吗"]
            ctx.extra["outbound_before"] = _shared.get("handoff_outbound_before", 0)
            for fu in followups:
                st, wh = client.webhook(channel, wa_h, fu, sender_name=cid)
                ok = st == 200 and (wh.get("data") or {}).get("status") == "success"
                if not ok:
                    return _result(
                        case, "EXECUTED", "FAIL", "FAIL",
                        f"api_error:webhook_http={st}; phase=handoff_followup",
                    )
                poll_turn_state(
                    client, bl, wa_h, wait_s=wait, expect_handoff=False, require_outbound=False,
                )
            import time
            time.sleep(2.0)
            ctx.messages = client.messages(bl, wa_h)
            ctx.outbound_texts = outbound_texts(ctx.messages)
            ctx.conversation = find_conversation(client.conversations(bl), wa_h)
            ctx.session = client.session(bl, wa_h)
            ctx.webhook_ok = True
            ctx.webhook_status = 200

        elif exec_type == "use_handoff_session":
            wa_h = _shared.get("handoff_wa")
            if not wa_h:
                checks = ["manual_only"]
            else:
                ctx.whatsapp_id = wa_h
                ctx.session = client.session(bl, wa_h)
                ctx.messages = client.messages(bl, wa_h)
                ctx.outbound_texts = outbound_texts(ctx.messages)
                ctx.conversation = find_conversation(client.conversations(bl), wa_h)
                ctx.webhook_ok = True

        elif exec_type == "webhook_multi":
            msgs = _resolve_messages(case, profile) or ["你好", "Hot70 多少钱", "转人工"]
            if case.get("input") and "连发" in case.get("input", ""):
                msgs = ["Hot70 多少钱", "什么时候提机", "门店在哪"]
            sids = []
            for i, text in enumerate(msgs):
                if text.startswith(">500") or "500" in text and "字" in (case.get("input") or ""):
                    text = _long_text(520)
                ctx.t_send = __import__("time").perf_counter()
                st, wh = client.webhook(channel, wa, text, sender_name=cid)
                ctx.webhook_status = st
                ctx.webhook_ok = st == 200 and (wh.get("data") or {}).get("status") == "success"
                if not ctx.webhook_ok:
                    return _result(
                        case, "EXECUTED", "FAIL", "FAIL",
                        f"api_error:webhook_http={st}; phase=webhook_multi; step={i+1}",
                    )
                sess_step, msgs_step, conv_step, _ = poll_turn_state(
                    client, bl, wa, wait_s=wait, expect_handoff=False, require_outbound=True,
                )
                ctx.session = sess_step
                sids.append(session_id_from(sess_step, msgs_step, conv_step))
            ctx.messages = client.messages(bl, wa)
            ctx.outbound_texts = outbound_texts(ctx.messages)
            ctx.conversation = find_conversation(client.conversations(bl), wa)
            ctx.response_ms = first_response_ms(ctx.messages, fallback_wait_ms=wait * 1000)
            ctx.extra["session_ids"] = sids
            ctx.extra["multi_count"] = len(msgs)

        elif exec_type == "webhook":
            msgs = _resolve_messages(case, profile)
            if not msgs:
                return _result(case, "SKIP", "NA", "NA", "无法解析用户消息；需人工执行 steps")
            text = msgs[0]
            if "500" in (case.get("input") or "") and "字" in (case.get("input") or ""):
                text = _long_text(520)
            ctx.t_send = __import__("time").perf_counter()
            st, wh = client.webhook(channel, wa, text, sender_name=cid)
            ctx.webhook_status = st
            ctx.webhook_ok = st == 200 and (wh.get("data") or {}).get("status") == "success"
            if not ctx.webhook_ok:
                return _result(
                    case, "EXECUTED", "FAIL", "FAIL",
                    f"api_error:webhook_http={st}; phase=webhook",
                )
            expect_ho = "local_handoff" in checks or "handoff_required" in checks or cid in (
                "TC-SMOKE-003-LOCAL", "TC-M5-LOCAL-001",
            )
            if text == "转人工":
                expect_ho = True
            sess, msgs, conv, texts = poll_turn_state(
                client, bl, wa,
                wait_s=max(wait, 12.0) if expect_ho else max(wait, 12.0),
                expect_handoff=expect_ho,
                require_outbound=not expect_ho,
            )
            ctx.session, ctx.messages, ctx.conversation, ctx.outbound_texts = sess, msgs, conv, texts
            ctx.response_ms = first_response_ms(msgs, fallback_wait_ms=wait * 1000)
            if cid == "TC-SMOKE-003-LOCAL":
                _shared["handoff_wa"] = wa
                _shared["handoff_outbound_before"] = settle_outbound_count(client, bl, wa, settle_s=3.0)

        elif exec_type in ("blocked", "defer_ext", "metrics", "manual_only"):
            pass

        else:
            return _result(case, "SKIP", "NA", "NA", f"unknown exec:{exec_type}")

    except Exception as e:
        # Script/runtime error: stop the whole run immediately.
        raise RuntimeError(f"script_error case={cid}: {e}") from e

    check_results = run_checks(checks, ctx)
    from test_case_verify import CheckResult

    for mc in manual_checks:
        check_results.append(CheckResult(f"manual:{mc}", False, f"待人工:{mc}", manual=True))

    biz, est, notes = summarize_checks(check_results)
    auto = "PASS" if ctx.webhook_ok or exec_type in ("blocked", "defer_ext", "metrics", "use_handoff_session", "handoff_then_silence") else "FAIL"
    if exec_type in ("blocked",):
        est = "BLOCKED"
    if exec_type == "defer_ext":
        est = "NOT_RUN"
        biz = "NA"

    return _result(
        case, est, auto if est == "EXECUTED" else "NA", biz, notes,
        whatsapp_id=ctx.whatsapp_id,
        session_id=session_id_from(ctx.session, ctx.messages, ctx.conversation),
        response_ms=int(ctx.response_ms) if ctx.response_ms else "",
        outbound_preview=ctx.outbound_texts[-1][:120] if ctx.outbound_texts else "",
        checks=[{"check": r.check, "pass": r.passed, "note": r.note, "manual": r.manual} for r in check_results],
    )


def _result(case, est, auto, biz, notes, **extra):
    row = {
        "case_id": case["id"],
        "module": case.get("module", ""),
        "title": case.get("title", ""),
        "layer": case.get("layer", ""),
        "priority": case.get("priority", ""),
        "execution_status": est,
        "automation_result": auto,
        "business_result": biz,
        "notes": notes,
    }
    row.update(extra)
    return row


def load_cases() -> list[dict]:
    from test_case_profile_map import PROFILES

    path = DATA / "test-cases-full.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    for r in rows:
        if not (r.get("verify_profile") or "").strip():
            r["verify_profile"] = PROFILES.get(r["id"], "exec:manual_only|manual:未配置profile")
    return rows


def run_smoke_formal_cases(client, channel: str, bl: int, wait: float) -> list[dict]:
    """仅执行 TC-SMOKE-*（verify_profile），保持 003-LOCAL → 003b 会话顺序。"""
    global _shared
    _shared = {}
    wait = max(wait, 12.0)
    results = []
    cases = [c for c in load_cases() if str(c.get("id", "")).startswith("TC-SMOKE")]
    for case in cases:
        results.append(execute_case(client, channel, bl, wait, case))
    return results


def run_all_formal_cases(client, channel: str, bl: int, wait: float) -> list[dict]:
    global _shared
    _shared = {}
    results = []
    for case in load_cases():
        results.append(execute_case(client, channel, bl, wait, case))
    return results
