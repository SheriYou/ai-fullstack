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
    "是否存在知识库",
    "执行阶段",
    "是否使用新会话",
    "知识库是否命中",
    "知识库是否命中正确",
    "日志客户标签",
    "客户标签是否准确",
    "日志转人工",
    "转人工原因",
    "转人工是否准确",
    "实际回复内容（英文）",
    "语义是否合理",
    "回复是否准确",
    "服务端真实耗时",
    "接口响应时长",
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
    if raw.lower() in ("视情况", "conditional", "depends on the situation", "depends on situation"):
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


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text or ""))


SCENE_FOLLOW_UP_EN = {
    "涉及价格不确定": "The price I saw seems uncertain. Can you confirm the final price?",
    "商品状态变化": "The product status seems to have changed. Can you check the latest availability?",
    "特殊报价": "I received a special quote. Can you confirm whether it is valid?",
    "用户预订失败": "My pre-order submission failed. What should I do next?",
    "入口打不开": "The pre-order page will not open for me. How can I complete the booking?",
    "流程异常": "Something went wrong during the booking process. Can you help me check it?",
    "用户询问特殊优惠": "Are there any special promotions available for my order?",
    "权益领取失败": "I could not claim my pre-order benefits. Can you help me check why?",
    "优惠是否可叠加": "Can this offer be combined with other discounts?",
    "涉及实时库存": "Can you check the real-time stock at my selected store?",
    "门店异常": "The store information looks abnormal. Can you help me verify it?",
    "城市未覆盖": "My city does not appear in the store list. What should I do?",
    "具体门店确认": "Can you confirm whether a specific store supports pickup for this model?",
    "用户仍不信任": "I am still not sure this WhatsApp account is official. Can you verify it?",
    "要求人工确认": "Can someone verify that this is the official Infinix WhatsApp channel?",
    "具体分期方案": "Can you confirm the available installment plans for this purchase?",
    "门店报价不一致": "The store quoted a different price. Can you confirm which price is correct?",
    "特殊价格": "Can you confirm whether a special price applies to my purchase?",
    "优惠叠加": "Can I stack this discount with another promotion?",
    "价格争议时": "There is a dispute about the price. Can you help confirm the correct amount?",
    "用户询问收据": "Can I get a receipt for my payment?",
    "发票": "Can I get an invoice for this purchase?",
    "门店无法收款时": "The store cannot accept my payment. What should I do?",
    "用户已享受其他优惠": "I already used another promotion. Can I still get this offer?",
    "门店金额不一致": "The amount shown at the store is different. Can you help confirm it?",
    "付款争议时": "There is a dispute about my payment. Can you help verify it?",
    "用户已提交但门店查不到记录": "I submitted my booking, but the store cannot find my record. Can you check it?",
    "没收到确认信息": "I did not receive a confirmation message after booking. Can you check my status?",
    "是否能保留名额时": "Can my booking slot be kept if the store cannot find my record?",
    "用户支付失败": "My payment failed. What should I do next?",
    "要求线上转账时": "The store asked me to transfer money online. Can you confirm if that is allowed?",
    "多台购买": "I want to buy multiple units. Can you confirm whether that is supported?",
    "团购": "Can you confirm whether group purchases are supported?",
    "批量采购": "Can you help confirm the process for bulk purchases?",
    "门店特殊处理时": "The store offered special handling. Can you confirm whether that is valid?",
    "用户强烈要求某一颜色": "I really want a specific color. Can you help confirm availability?",
    "查询具体门店颜色库存": "Can you check color availability at a specific store?",
    "投诉颜色不一致时": "The color I received is not what I expected. Can you help check this?",
    "用户问赠品型号": "Can you confirm the exact gift model for this promotion?",
    "颜色": "Can you confirm which gift color is available?",
    "库存": "Can you confirm whether the gift is still in stock?",
    "是否一定有": "Can you confirm whether the gift is guaranteed with my purchase?",
    "是否可换时": "Can I exchange the gift if the model or color is not suitable?",
    "用户问激活多久生效": "How long does SIM activation take before the benefit becomes valid?",
    "赠品未收到": "I have not received the gift. Can you help me check it?",
    "门店不给赠品": "The store refused to provide the gift. Can you help me verify eligibility?",
    "SIM 激活异常时": "My SIM activation seems abnormal. Can you help me check it?",
    "用户对激活规则有异议": "I disagree with the SIM activation rule. Can you help confirm it?",
    "SIM 激活失败": "My SIM activation failed. Can you help me resolve it?",
    "赠品资格争议时": "There is a dispute about my gift eligibility. Can you help confirm it?",
    "用户询问具体门店是否属于 IBP": "Can you confirm whether this specific store is an IBP store?",
    "IBO": "Can you confirm whether this specific store is an IBO store?",
    "门店资质时": "Can you verify whether this store is authorized for the promotion?",
    "用户询问具体瓦数": "Can you confirm the exact charging wattage for this model?",
    "充电时长时": "Can you confirm how long it takes to fully charge this phone?",
    "用户询问具体保修范围": "Can you confirm the exact warranty coverage for this device?",
    "配件保修": "Can you confirm whether accessories are covered by warranty?",
    "延保时": "Can you confirm whether extended warranty is available?",
    "远程无法解决的硬件故障": "The hardware issue cannot be solved remotely. What should I do next?",
    "保修争议时": "There is a dispute about my warranty coverage. Can you help confirm it?",
    "用户询问特定门店支持的付款方式": "Can you confirm which payment methods a specific store supports?",
    "支付失败时": "My payment failed at the store. Can you help me check what happened?",
    "用户需要详细参数对比": "Can you provide a detailed specification comparison before I decide?",
    "选购建议时": "Can you help me choose the best option for my needs?",
    "用户询问特定门店营业时间时": "Can you confirm the business hours of a specific store?",
}


def make_follow_up_en(scene: str, base_q_en: str) -> str:
    scene = (scene or "").strip()
    base_q_en = (base_q_en or "").strip()
    if scene in SCENE_FOLLOW_UP_EN:
        return SCENE_FOLLOW_UP_EN[scene]
    if not scene or contains_cjk(scene) or not re.search(r"[A-Za-z]", scene):
        return "Could you help me resolve this issue related to my request?"
    if scene.lower() == base_q_en.lower():
        return "Could you clarify what I should do about this issue?"
    if re.search(r"[?]$", scene):
        return scene
    return f"Could you help me with {scene}?"

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
    if contains_cjk(out) or not re.search(r"[A-Za-z]", out):
        raise RuntimeError("llm follow-up is not English")
    if out.lower() == base_q_en.lower():
        raise RuntimeError("llm follow-up equals base question")
    if re.search(r"(?i)\b(i\s*['’]?m|i am)\s+facing\s+this\s+issue\s*:", out):
        raise RuntimeError("llm follow-up contains mechanical prefix")
    if has_handoff_hint_en(out):
        raise RuntimeError("llm follow-up contains handoff hint")
    if not out.endswith("?"):
        out = out.rstrip(".! ") + "?"
    return out[:220]


def assign_execution_stages(rows: list[dict[str, str]]) -> None:
    """Assign mutually exclusive P0/P1/P2 stages by total generated case count."""
    total = len(rows)
    quotas = {
        "P0": min(20, total),
        "P1": int(total * 0.10),
        "P2": int(total * 0.30),
    }
    available = list(range(total))

    for stage, quota in quotas.items():
        if not available or quota <= 0:
            continue
        target_n = min((quota + 2) // 4, quota)
        target_h = quota - target_n
        selected: list[int] = []

        for suffix, target in (("-N", target_n), ("-H-C", target_h)):
            matches = [
                index
                for index in available
                if (
                    rows[index].get("用例ID", "").endswith(suffix)
                    if suffix == "-N"
                    else suffix in rows[index].get("用例ID", "")
                )
            ]
            selected.extend(matches[:target])

        if len(selected) < quota:
            selected.extend(index for index in available if index not in selected)
            selected = selected[:quota]

        for index in selected:
            rows[index]["执行阶段"] = stage
        available = [index for index in available if index not in selected]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate KB metrics test cases from FAQ csv.")
    parser.add_argument("--faq-csv", default=str(FAQ_CSV))
    parser.add_argument(
        "--status",
        default="已确认",
        help="Only generate rows with this FAQ status (default: 已确认). Use --status all to include every status.",
    )
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

    header = set(rows[0].keys())
    if "是否需要转人工" not in header and "是否转人工（英文）" in header:
        for row in rows:
            row["是否需要转人工"] = row.get("是否转人工（英文）", "")
    if "转人工条件（英文）" not in header:
        for row in rows:
            row["转人工条件（英文）"] = row.get("转人工条件/备注", "")

    missing_cols = [c for c in REQUIRED_COLS if c not in rows[0].keys()]
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
        row_status = (r.get("状态") or "").strip()
        if args.status.lower() != "all" and row_status != args.status:
            skipped.append(f"L{i}: status={row_status or '<empty>'}")
            continue

        q_cn = (r.get("用户问题") or "").strip()
        q_en = (r.get("问题（英文）") or "").strip()
        cat = (r.get("分类") or "").strip()
        reply_zh = (r.get("业务反馈") or r.get("回复中文翻译") or "").strip()
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
                "是否存在知识库": "是",
                "执行阶段": "",
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
                if scene in SCENE_FOLLOW_UP_EN:
                    follow_en = make_follow_up_en(scene, q_en)
                    llm_followup_fallback += 1
                elif args.disable_llm_followup:
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
                        "是否存在知识库": "是",
                        "执行阶段": "",
                        "是否使用新会话": "否",
                    }
                )
                out_rows.append(h_row)

    assign_execution_stages(out_rows)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        writer.writeheader()
        writer.writerows(out_rows)

    summary = {
        "faq_csv": str(faq_csv),
        "faq_encoding": enc,
        "faq_total_rows": len(rows),
        "faq_status_filter": args.status,
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


