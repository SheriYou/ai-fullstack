#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 test-cases-full / checklist 验证点执行，而非仅发送语料字符串。"""
from __future__ import annotations

import re
import time
from typing import Callable

# 英文/中文「转人工提示语」——仅有此类 outbound 不算 LOCAL 转人工成功
HANDOFF_REPLY_MARKERS = (
    "human agent will continue",
    "handled correctly",
    "人工坐席",
    "稍后会有",
    "由人工",
    "转人工",
)


def conv_get(conv: dict | None, *keys: str):
    if not conv:
        return None
    for key in keys:
        if key in conv and conv[key] is not None:
            return conv[key]
    return None


def is_handoff_reply_text(text: str) -> bool:
    blob = (text or "").lower()
    return any(m in blob for m in HANDOFF_REPLY_MARKERS)


def verify_local_handoff(conv: dict | None) -> tuple[bool, list[str]]:
    """Q07 LOCAL：以 Conversation 字段为准（对齐 TC-SMOKE-003-LOCAL / M5-LOCAL-001）。"""
    if not conv:
        return False, ["no conversation"]
    target = conv_get(conv, "handoff_target", "handoffTarget")
    status = conv_get(conv, "conversation_status", "conversationStatus")
    active = conv_get(conv, "is_active_agent", "isActiveAgent")
    ho_status = conv_get(conv, "handoff_status", "handoffStatus")
    assigned = conv_get(conv, "assigned_user_id", "assignedUserId")
    if target == "LOCAL" and status == "handoff" and active == 0:
        detail = f"handoffStatus={ho_status}"
        if assigned:
            detail += f"; assignedUserId={assigned}"
        return True, [detail]
    return False, [
        f"handoffTarget={target}",
        f"conversationStatus={status}",
        f"isActiveAgent={active}",
    ]


def verify_bot_active(conv: dict | None) -> tuple[bool, list[str]]:
    """机器人仍接管：未进入 LOCAL handoff。"""
    ok, notes = verify_local_handoff(conv)
    if ok:
        return False, ["unexpected LOCAL handoff"] + notes
    active = conv_get(conv, "is_active_agent", "isActiveAgent")
    if active == 1:
        return True, ["isActiveAgent=1"]
    if active is None and conv:
        return True, ["isActiveAgent not set; not in LOCAL handoff"]
    return False, [f"isActiveAgent={active}"]


def user_message_from_input(raw: str) -> str | None:
    """从 test-cases-full 的 input 列提取用户发送内容（非整段 steps 原文）。"""
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.startswith("("):
        return None

    extracted: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        for pat in (
            r"用户(?:向.*?)?发送[：:]\s*(.+)$",
            r"发送[：:]\s*(.+)$",
        ):
            m = re.search(pat, line)
            if m:
                extracted.append(m.group(1).strip().strip('"').strip("「").strip("」"))
    if extracted:
        return extracted[-1]

    if raw.startswith(("1.", "2.", "3.")) or "用户" in raw[:30]:
        return None

    if " / " in raw and len(raw) < 120:
        return raw.split(" / ")[0].strip()
    return raw


def poll_turn_state(
    client,
    bl: int,
    wa: str,
    *,
    wait_s: float,
    expect_handoff: bool = False,
) -> tuple[dict, list, dict | None, list[str]]:
    """等待 Agent 处理完成；转人工用例轮询 Conversation 直至 LOCAL 或超时。"""
    deadline = time.time() + wait_s
    sess: dict = {}
    msgs: list = []
    conv = None
    texts: list[str] = []
    interval = min(0.5, wait_s / 4) if wait_s else 0.5

    while time.time() < deadline:
        time.sleep(interval)
        sess = client.session(bl, wa)
        msgs = client.messages(bl, wa)
        convs = client.conversations(bl)
        from run_test_suite import find_conversation, outbound_texts

        conv = find_conversation(convs, wa)
        texts = outbound_texts(msgs)
        if expect_handoff:
            ok, _ = verify_local_handoff(conv)
            if ok:
                break
        elif texts or (sess.get("session") or sess).get("task_type"):
            break
    else:
        sess = client.session(bl, wa)
        msgs = client.messages(bl, wa)
        from run_test_suite import find_conversation, outbound_texts

        conv = find_conversation(client.conversations(bl), wa)
        texts = outbound_texts(msgs)

    return sess, msgs, conv, texts


def run_smoke_cases(client, channel: str, bl: int, wait: float) -> list[dict]:
    """G2 冒烟：独立会话 + 用例级验证点（见 test-cases-full.csv / checklist-smoke.md）。"""
    import uuid
    from run_test_suite import outbound_texts

    results: list[dict] = []

    def _record(cid: str, inp: str, wa: str, ok: bool, notes: list[str], extra: dict | None = None):
        row = {
            "id": cid,
            "input": inp,
            "whatsapp_id": wa,
            "status": "PASS" if ok else "FAIL",
            "notes": "; ".join(notes),
            "note": "; ".join(notes),
            "outbound_preview": extra.get("outbound_preview", "") if extra else "",
            "session_id": extra.get("session_id", "") if extra else "",
            "conversation_status": extra.get("conversation_status") if extra else None,
            "is_active_agent": extra.get("is_active_agent") if extra else None,
            "handoff_target": extra.get("handoff_target") if extra else None,
        }
        if extra:
            row.update({k: v for k, v in extra.items() if k not in row})
        results.append(row)

    # TC-SMOKE-001：独立会话，正常寒暄，非转人工兜底
    wa1 = f"smoke-{uuid.uuid4().hex[:8]}@s.whatsapp.net"
    client.webhook(channel, wa1, "你好")
    sess, msgs, conv, texts = poll_turn_state(client, bl, wa1, wait_s=wait, expect_handoff=False)
    ok = bool(texts) and not is_handoff_reply_text(texts[-1])
    active_ok, active_notes = verify_bot_active(conv)
    ok = ok and active_ok
    notes = ([] if ok else ["expected greeting reply"]) + active_notes
    if texts and is_handoff_reply_text(texts[-1]):
        notes.append("got handoff template instead of greeting")
    from l2_eval_core import session_id_from

    _record("TC-SMOKE-001", "你好", wa1, ok, notes, {
        "outbound_preview": texts[-1][:120] if texts else "",
        "session_id": session_id_from(sess),
        "conversation_status": conv_get(conv, "conversation_status", "conversationStatus"),
        "is_active_agent": conv_get(conv, "is_active_agent", "isActiveAgent"),
    })

    # TC-SMOKE-002：独立会话，知识库含价格
    wa2 = f"smoke-{uuid.uuid4().hex[:8]}@s.whatsapp.net"
    client.webhook(channel, wa2, "Hot70 多少钱")
    sess, msgs, conv, texts = poll_turn_state(client, bl, wa2, wait_s=wait, expect_handoff=False)
    blob = " ".join(texts).lower()
    price_ok = any(k in blob for k in ("999", "36", "bdt", "price", "订金", "塔卡"))
    ok = price_ok and not (len(texts) == 1 and is_handoff_reply_text(texts[-1]))
    notes = []
    if not texts:
        notes.append("no outbound")
    elif not price_ok:
        notes.append("missing price/amount in reply")
    if texts and is_handoff_reply_text(texts[-1]) and not price_ok:
        notes.append("only handoff template, no FAQ price")
    _record("TC-SMOKE-002", "Hot70 多少钱", wa2, ok, notes or ["price in reply"], {
        "outbound_preview": texts[-1][:120] if texts else "",
        "session_id": session_id_from(sess),
    })

    # TC-SMOKE-003-LOCAL：发「转人工」→ LOCAL handoff 字段
    wa3 = f"smoke-{uuid.uuid4().hex[:8]}@s.whatsapp.net"
    client.webhook(channel, wa3, "转人工")
    sess, msgs, conv, texts = poll_turn_state(client, bl, wa3, wait_s=max(wait, 4.0), expect_handoff=True)
    ok, notes = verify_local_handoff(conv)
    outbound_before = len(texts)
    _record("TC-SMOKE-003-LOCAL", "转人工", wa3, ok, notes, {
        "outbound_preview": texts[-1][:120] if texts else "",
        "session_id": session_id_from(sess),
        "conversation_status": conv_get(conv, "conversation_status", "conversationStatus"),
        "is_active_agent": conv_get(conv, "is_active_agent", "isActiveAgent"),
        "handoff_target": conv_get(conv, "handoff_target", "handoffTarget"),
        "handoff_status": conv_get(conv, "handoff_status", "handoffStatus"),
        "_outbound_before_followup": outbound_before,
    })

    # TC-SMOKE-003b：同一会话转人工后再发，无新增机器人 outbound
    client.webhook(channel, wa3, "在吗")
    time.sleep(wait)
    msgs_after = client.messages(bl, wa3)
    texts_after = outbound_texts(msgs_after)
    new_bot = len(texts_after) > outbound_before
    ok_b = not new_bot
    _record("TC-SMOKE-003b", "在吗（转人工后）", wa3, ok_b,
            ["转人工后不应新增机器人 outbound"] if ok_b else [f"new outbound: {len(texts_after) - outbound_before}条"],
            {
                "outbound_count": len(texts_after),
                "session_id": session_id_from(client.session(bl, wa3)),
            })

    return results
