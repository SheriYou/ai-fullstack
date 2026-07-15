#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate prd/Hot70_机器人_知识库指标测试.csv from latest FAQ CSV (new headers)."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
if str(FRAMEWORK_ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_ROOT / "lib"))

from llm_client import LlmConfigError, chat  # noqa: E402

FAQ_CSV = ROOT / "prd" / "Hot 70 FAQ知识库_FAQ知识库_全部FAQ.csv"
OUT_CSV = ROOT / "prd" / "Hot70_机器人_知识库指标测试.csv"
REPORT_JSON = ROOT / "reports" / "kb-metrics-case-gen-summary.json"

REQUIRED_COLS = [
    "序号",
    "用户问题",
    "问题（英文）",
    "分类",
    "业务反馈",
    "回复中文翻译",
    "是否转人工（英文）",
    "是否需要转人工",
    "转人工条件（英文）",
    "转人工条件/备注",
    "状态",
]

OUT_FIELDS = [
    "用例ID",
    "用例名称",
    "执行步骤",
    "预期结果",
    "转人工触发条件",
    "测试目标",
    "前置条件",
    "测试数据",
    "测试数据（英文提问）",
    "转人工预期",
    "是否使用新会话",
    "实际回复内容（英文）",
    "知识库是否命中",
    "日志客户标签",
    "客户标签是否准确",
    "日志转人工",
    "转人工是否准确",
    "回复是否准确",
    "服务端真实耗时",
    "接口响应时长",
    "执行结果",
    "备注",
]


def load_rows(path: Path) -> tuple[list[dict], str]:
    for enc in ("utf-8-sig", "utf-8", "gb18030", "cp936"):
        try:
            with path.open("r", encoding=enc, newline="") as f:
                return list(csv.DictReader(f)), enc
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, "unable to decode faq csv")


def normalize_handoff(v: str) -> str:
    raw = (v or "").strip()
    if raw in ("是", "yes", "YES", "true", "TRUE"):
        return "true"
    if raw in ("否", "no", "NO", "false", "FALSE"):
        return "false"
    if raw in ("视情况", "conditional"):
        return "conditional"
    return "empty"


def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def split_handoff_conditions(en_text: str, note_text: str, limit: int = 5) -> list[str]:
    parts: list[str] = []
    en_text = normalize_space(en_text)
    note_text = normalize_space(note_text)
    raw_items = [en_text] if en_text else [note_text]
    for raw in raw_items:
        if not raw:
            continue
        cleaned = raw
        cleaned = re.sub(r"(?i)^transfer to human(?:\s+for.*)?\s+if\s+", "", cleaned)
        cleaned = re.sub(r"(?i)^if\s+", "", cleaned)
        cleaned = re.sub(r"^如(果)?", "", cleaned)
        cleaned = re.sub(r"(，|,)?转人工.*$", "", cleaned)
        for token in re.split(r"(?:\bor\b|\band\b|[，,；;。/\n、]|以及|或者|或|并且)", cleaned):
            t = normalize_space(token).strip("：:。.!?？")
            if len(t) < 2:
                continue
            parts.append(t)

    out: list[str] = []
    seen = set()
    for p in parts:
        k = p.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(p[:120])
        if len(out) >= limit:
            break
    return out


def n_steps(expected_handoff: str) -> str:
    if expected_handoff == "是":
        return (
            "步骤1：开启新的WhatsApp会话。"
            "步骤2：发送测试问题。"
            "步骤3：核对机器人识别业务场景。"
            "步骤4：观察是否按规则触发人工转接。"
            "步骤5：确认未输出超出知识库的确定性结论。"
        )
    return (
        "步骤1：开启新的WhatsApp会话。"
        "步骤2：发送测试问题。"
        "步骤3：核对机器人识别业务场景。"
        "步骤4：等待机器人完整回复并核对核心事实。"
        "步骤5：确认回复未增加知识库之外的信息。"
        "步骤6：确认本轮未错误触发人工转接。"
    )


def n_expected_result(reply_text: str, expected_handoff: str) -> str:
    if expected_handoff == "是":
        return "该问题按知识库规则应直接触发转人工；转接前话术应与当前问题相关，不应输出超范围确定性结论。"
    if reply_text:
        return (
            f"{reply_text}\n\n验收要求：核心事实正确、关键信息完整、无知识库外编造；"
            "标准问答场景下不应错误触发人工转接。"
        )
    return "应按知识库口径给出有效回复，不得编造知识库外事实，且不应错误触发人工转接。"


def empty_result_row() -> dict[str, str]:
    return {k: "" for k in OUT_FIELDS}


def make_follow_up_cn(scene: str, base_q_cn: str) -> str:
    scene = (scene or "").strip()
    if not scene:
        return f"我遇到这个情况，需要你帮我处理。"
    # Ensure H-case prompt is a follow-up statement, not the same as base question.
    if scene == (base_q_cn or "").strip():
        return f"我遇到这个情况：{scene}，该怎么处理？"
    if re.search(r"[？?]$", scene):
        return scene
    return f"我遇到这个情况：{scene}"


def make_follow_up_en(scene: str, base_q_en: str) -> str:
    scene = (scene or "").strip()
    base_q_en = (base_q_en or "").strip()
    if not scene:
        return "I have an issue with this case, can you help me check it?"
    # Ensure H-case prompt is follow-up and not identical to base N question.
    if scene.lower() == base_q_en.lower():
        return f"I'm facing this issue: {scene}. What should I do next?"
    if re.search(r"[?]$", scene):
        return scene
    return f"I'm facing this issue: {scene}. What should I do?"


def has_handoff_hint_en(text: str) -> bool:
    t = (text or "").lower()
    # Avoid leaking handoff intent into test prompts.
    banned = (
        "human",
        "agent",
        "manual support",
        "customer service",
        "customer care",
        "transfer",
        "representative",
        "connect me",
    )
    return any(x in t for x in banned)


def llm_follow_up_en(scene: str, base_q_en: str, category: str) -> str:
    scene = (scene or "").strip()
    base_q_en = (base_q_en or "").strip()
    system_prompt = (
        "You are a QA test-case writer. "
        "Generate exactly one natural English follow-up user question for chatbot testing. "
        "It must clearly express the given scenario as a realistic user follow-up. "
        "Output plain text only, one sentence, no bullets, no quotes."
    )
    user_prompt = (
        f"Base question: {base_q_en}\n"
        f"Category: {category}\n"
        f"Condition scenario: {scene}\n\n"
        "Constraints:\n"
        "1) English only.\n"
        "2) 8-28 words.\n"
        "3) End with '?'.\n"
        "4) Must NOT repeat the base question wording.\n"
        "5) Must NOT mention human/agent/manual support/transfer/customer service.\n"
    )
    txt = chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        project_root=ROOT,
        temperature=0,
    )
    out = (txt or "").strip().strip('"').strip("'")
    out = re.sub(r"\s+", " ", out)
    if not out:
        raise RuntimeError("empty llm follow-up")
    if out.lower() == base_q_en.lower():
        raise RuntimeError("llm follow-up equals base question")
    if has_handoff_hint_en(out):
        raise RuntimeError("llm follow-up contains handoff hint")
    if not out.endswith("?"):
        out = out.rstrip(".! ") + "?"
    return out[:220]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate KB metrics test cases from FAQ csv.")
    parser.add_argument("--faq-csv", default=str(FAQ_CSV))
    parser.add_argument("--out-csv", default=str(OUT_CSV))
    parser.add_argument(
        "--disable-llm-followup",
        action="store_true",
        help="Disable LLM generation for H-case English follow-up prompts.",
    )
    args = parser.parse_args()

    faq_csv = Path(args.faq_csv)
    out_csv = Path(args.out_csv)
    rows, enc = load_rows(faq_csv)
    if not rows:
        raise RuntimeError("FAQ csv is empty")

    missing_cols = [c for c in REQUIRED_COLS if c not in (rows[0].keys())]
    if missing_cols:
        raise RuntimeError(f"FAQ csv missing columns: {missing_cols}")

    out_rows: list[dict] = []
    skipped: list[str] = []
    conditional_no_scene = 0
    faq_used = 0
    llm_followup_used = 0
    llm_followup_fallback = 0
    llm_cache: dict[tuple[str, str, str], str] = {}

    case_no = 0
    for i, r in enumerate(rows, start=2):
        q_cn = (r.get("用户问题") or "").strip()
        q_en = (r.get("问题（英文）") or "").strip()
        cat = (r.get("分类") or "").strip()
        reply_zh = (r.get("回复中文翻译") or r.get("业务反馈") or "").strip()
        handoff = normalize_handoff(r.get("是否需要转人工") or "")
        cond_en = (r.get("转人工条件（英文）") or "").strip()
        cond_note = (r.get("转人工条件/备注") or "").strip()

        if not q_cn or not q_en or not cat:
            skipped.append(f"L{i}: missing key fields(q/cat/en)")
            continue

        case_no += 1
        faq_used += 1
        base = f"TC-H70-{case_no:03d}"

        # N case
        n_row = empty_result_row()
        n_handoff = "是" if handoff == "true" else "否"
        if handoff == "conditional":
            n_handoff = "否"
        n_row.update(
            {
                "用例ID": f"{base}-N",
                "用例名称": f"[{cat}] {q_cn}【标准问答场景】",
                "执行步骤": n_steps(n_handoff),
                "预期结果": n_expected_result(reply_zh, n_handoff),
                "转人工触发条件": (
                    "该问题按规则直接转人工" if n_handoff == "是" else "无（标准咨询场景）"
                ),
                "测试目标": (
                    "验证直接转人工策略、转接话术相关性及知识边界控制"
                    if n_handoff == "是"
                    else "验证意图分类、知识命中、回答准确性及错误转人工控制"
                ),
                "前置条件": (
                    "1) 已接入Hot70 WhatsApp机器人；"
                    "2) 测试账号可正常收发消息；"
                    "3) 使用与上线一致的知识库、Prompt和模型配置；"
                    "4) 可查看会话日志或Trace。"
                ),
                "测试数据": q_cn,
                "测试数据（英文提问）": q_en,
                "转人工预期": n_handoff,
                "是否使用新会话": "是",
            }
        )
        out_rows.append(n_row)

        # H-Cxx for conditional scenarios
        if handoff == "conditional":
            scenes = split_handoff_conditions(cond_en, cond_note)
            if not scenes:
                conditional_no_scene += 1
            for j, scene in enumerate(scenes, start=1):
                h_row = empty_result_row()
                follow_cn = make_follow_up_cn(scene, q_cn)
                if args.disable_llm_followup:
                    follow_en = make_follow_up_en(scene, q_en)
                    llm_followup_fallback += 1
                else:
                    key = (scene, q_en, cat)
                    if key in llm_cache:
                        follow_en = llm_cache[key]
                    else:
                        try:
                            follow_en = llm_follow_up_en(scene, q_en, cat)
                            llm_followup_used += 1
                        except (LlmConfigError, RuntimeError):
                            follow_en = make_follow_up_en(scene, q_en)
                            llm_followup_fallback += 1
                        llm_cache[key] = follow_en
                h_row.update(
                    {
                        "用例ID": f"{base}-H-C{j:02d}",
                        "用例名称": f"[{cat}] {q_cn}【条件式转人工场景：{scene}】",
                        "执行步骤": (
                            f"步骤1：先执行关联标准用例“{base}-N”，并保持同一WhatsApp会话。"
                            f"步骤2：在同一会话继续追问场景问题：“{scene}”。"
                            "步骤3：核对机器人识别到条件场景并触发人工转接。"
                            "步骤4：确认转接前话术与当前问题相关。"
                            "步骤5：确认未继续输出超范围确定性结论。"
                        ),
                        "预期结果": (
                            f"命中条件场景“{scene}”后，机器人应触发转人工；"
                            "转接前话术应与当前问题相关，不得继续输出超范围确定性结论。"
                        ),
                        "转人工触发条件": scene,
                        "测试目标": "验证多轮上下文理解、条件式转人工召回及转接话术相关性",
                        "前置条件": (
                            f"1) 已完成“{base}-N”；"
                            "2) 机器人已给出首轮回复；"
                            "3) 当前仍保持同一会话；"
                            "4) 尚未发生人工接管。"
                        ),
                        "测试数据": follow_cn,
                        "测试数据（英文提问）": follow_en,
                        "转人工预期": "是",
                        "是否使用新会话": "否",
                    }
                )
                out_rows.append(h_row)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        writer.writeheader()
        writer.writerows(out_rows)

    summary = {
        "faq_csv": str(faq_csv),
        "faq_encoding": enc,
        "faq_total_rows": len(rows),
        "faq_used_rows": faq_used,
        "generated_cases": len(out_rows),
        "conditional_without_scene_rows": conditional_no_scene,
        "llm_followup_used": llm_followup_used,
        "llm_followup_fallback": llm_followup_fallback,
        "skipped_rows": skipped,
        "out_csv": str(out_csv),
    }
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
