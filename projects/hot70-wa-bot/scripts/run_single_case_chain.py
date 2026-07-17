#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run one case by ID with deterministic session-chain rule.

Rules:
- `TC-H70-xxx-N`: run once in a new session.
- `TC-H70-xxx-H-Cyy`: first run `TC-H70-xxx-N`, then ask the H-C question
  in the same session.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import time
import uuid
from pathlib import Path

from run_test_suite import (
    Client,
    DEFAULT_BASE,
    DEFAULT_PASS,
    DEFAULT_USER,
    find_conversation,
    outbound_texts,
)


ROOT = Path(__file__).resolve().parents[1]
SHEET_CANDIDATES = [
    ROOT / "prd" / "Hot70_机器人_人工复核结果 - Sheet1.csv",
    ROOT / "prd" / "Hot70_机器人_知识库指标测试.csv",
]


def resolve_sheet() -> Path:
    for p in SHEET_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError("missing sheet file, checked: " + ", ".join(str(p) for p in SHEET_CANDIDATES))


def load_question(case_id: str) -> tuple[str, str]:
    sheet = resolve_sheet()
    is_hc = bool(re.match(r"^TC-H70-\d{3}-H-C\d+$", case_id))
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            with sheet.open("r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if (row.get("用例ID") or "").strip() == case_id:
                        q_cn = (row.get("测试数据") or "").strip()
                        q_en = (row.get("测试数据（英文提问）") or "").strip()
                        if is_hc:
                            if not q_en:
                                return "", "H-C case requires non-empty 测试数据（英文提问）"
                            return q_en, ""
                        # N case: prefer English, fallback to CN.
                        return (q_en or q_cn), ""
        except UnicodeDecodeError:
            continue
    return "", "case not found or unreadable in sheet"


def chain_for_case(case_id: str) -> list[str]:
    m_hc = re.match(r"^(TC-H70-\d{3})-H-C\d+$", case_id)
    if m_hc:
        return [f"{m_hc.group(1)}-N", case_id]
    return [case_id]


def wait_new_outbound(client: Client, bl: int, wa: str, before: int, timeout_s: float) -> list[str]:
    end = time.time() + timeout_s
    latest = []
    while time.time() < end:
        latest = outbound_texts(client.messages(bl, wa))
        if len(latest) > before:
            return latest
        time.sleep(0.6)
    return outbound_texts(client.messages(bl, wa))


def safe_print(line: str) -> None:
    sys.stdout.buffer.write((line + "\n").encode("gbk", errors="backslashreplace"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a single Hot70 case with N->H chain behavior.")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--channel", default="ch_wa_01")
    parser.add_argument("--business-line-id", type=int, default=1)
    parser.add_argument("--wait-seconds", type=float, default=18.0)
    args = parser.parse_args()

    chain = chain_for_case(args.case_id.strip())
    prompts = []
    for cid in chain:
        q, err = load_question(cid)
        if not q:
            print("result=FAIL")
            print(f"note={err}; case={cid}")
            raise SystemExit(2)
        prompts.append((cid, q))

    client = Client(DEFAULT_BASE, DEFAULT_USER, DEFAULT_PASS)
    if not client.login(DEFAULT_USER, DEFAULT_PASS):
        raise SystemExit("LOGIN FAILED")

    wa = f"tc-{uuid.uuid4().hex[:10]}@s.whatsapp.net"
    print(f"LOGIN OK")
    print(f"whatsapp_id={wa}")
    print(f"chain={chain}")

    all_texts: list[str] = []
    exec_case_id = args.case_id.strip()
    for cid, question in prompts:
        before = len(all_texts)
        turn_sender_name = cid if cid.endswith("-N") else exec_case_id
        st, wh = client.webhook(args.channel, wa, question, sender_name=turn_sender_name)
        ok = st == 200 and (wh.get("data") or {}).get("status") == "success"
        all_texts = wait_new_outbound(
            client=client,
            bl=args.business_line_id,
            wa=wa,
            before=before,
            timeout_s=args.wait_seconds,
        )
        new = all_texts[before:] if len(all_texts) >= before else []
        prefix = "prefill_case" if cid != exec_case_id else "case"
        print(f"\n{prefix}={cid}")
        print(f"webhook_http={st} webhook_ok={ok}")
        print(f"outbound_total={len(all_texts)} outbound_new={len(new)}")
        safe_print(f"reply={(new[-1] if new else '')[:2500]}")

    sess = client.session(args.business_line_id, wa)
    conv = find_conversation(client.conversations(args.business_line_id), wa) or {}
    sess_obj = sess.get("session") or sess
    tags = conv.get("tags") if isinstance(conv.get("tags"), list) else []

    print("\nfinal_state")
    print(f"session_id={(sess_obj.get('session_id') or sess_obj.get('sessionId') or '')}")
    print(f"task_type={(sess_obj.get('task_type') or sess_obj.get('taskType') or '')}")
    print(f"conversation_sender_name={conv.get('sender_name') or conv.get('senderName') or ''}")
    print(f"conversation_tags={tags}")
    print(f"conversation_status={conv.get('conversation_status') or conv.get('conversationStatus') or ''}")
    print(f"handoff_target={conv.get('handoff_target') or conv.get('handoffTarget') or ''}")


if __name__ == "__main__":
    main()
