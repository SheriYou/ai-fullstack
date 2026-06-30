# -*- coding: utf-8 -*-
"""Export all test cases into prd/test_case_temp.csv template format."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRD = ROOT / "prd"
DATA = ROOT / "data"

PRODUCT = "Hot70 WhatsApp Bot"
USER_STORY = "US-01 用户进入WhatsApp后能及时收到回复并完成咨询/预订/提机或转人工"
CREATOR = ""

HEADER_ROW1 = ["默认分组"] + [""] * 19
HEADER_ROW2 = [
    "ID", "用例名称", "关联用户故事", "所属产品", "用例等级", "用例类型", "用例分类",
    "前置条件", "操作步骤", "预期结果",
    "测试层", "自动化", "来源", "规则编号", "补充说明",
    "创建时间", "创建人", "执行人", "执行时间", "执行结果",
]

TYPE_MAP = {
    "smoke": "冒烟测试",
    "integration": "集成测试",
    "handoff": "功能测试",
    "log": "非功能测试",
    "acceptance": "验收测试",
    "explore": "探索测试",
    "tag": "功能测试",
    "faq_rule": "功能测试",
    "faq": "功能测试",
    "faq_paraphrase": "功能测试",
    "exception": "异常测试",
    "adversarial": "异常测试",
}

MODULE_LABEL = {
    "M1": "冒烟",
    "M2": "消息接入",
    "M3": "意图识别",
    "M4": "知识库",
    "M5": "转人工",
    "M6": "坐席分配",
    "M7": "人工回传",
    "M8": "日志",
    "M9": "客户标签",
    "M10": "探索性",
    "M11": "异常场景",
    "L4": "验收指标",
    "PROD": "商品信息",
    "ACT": "活动规则",
    "BEN": "活动权益",
    "PICK": "提机规则",
    "STORE": "门店信息",
    "OFF": "官方身份",
    "HANDOFF": "人工兜底",
    "OTHER": "其他",
}

INTENT_TOPIC = {
    "产品信息": "产品咨询",
    "活动规则": "活动参与",
    "活动权益": "预购福利",
    "提机相关": "提机取货",
    "门店相关": "门店查询",
    "官方身份": "官方身份",
    "人工兜底": "异常兜底",
    "人工客服": "转人工",
    "无法覆盖": "未知问题兜底",
}

# 系统用例：自然语言标题（从标题即可看出验证什么）
SYSTEM_TITLES = {
    "TC-SMOKE-001": "用户打招呼后，机器人能在10秒内回复",
    "TC-SMOKE-002": "用户询问产品价格时，机器人能正确回复价格信息",
    "TC-SMOKE-003-LOCAL": "用户说转人工时，Web 本地坐席分配且机器人暂停",
    "TC-SMOKE-003-EXT": "工作台外部转人工时，智齿工作台出现会话且含 groupid",
    "TC-SMOKE-003b": "转人工后用户再发消息，机器人不再自动回复",
    "TC-SMOKE-004": "坐席在工作台回复后，用户 WhatsApp 能收到人工消息",
    "TC-SMOKE-005": "会话日志能完整记录从用户消息到机器人/人工回复的全链路",
    "TC-M2-001": "WhatsApp 纯文本消息能正常接入并得到回复",
    "TC-M2-002": "英文 FAQ 问法能正常识别并回复",
    "TC-M2-003": "含 Emoji 的消息不会崩溃，且有合理回复或兜底",
    "TC-M2-004": "空消息或纯空格时，有兜底提示或引导重新输入",
    "TC-M2-005": "超长文本消息不会导致系统崩溃",
    "TC-M2-006": "3秒内连发多条不同问题，均能处理且会话不串",
    "TC-M2-007": "机器人回复能在用户 WhatsApp 端正常显示",
    "TC-M2-008": "FAQ 回复平均响应时间不超过10秒",
    "TC-M2-009": "智齿发消息 API 失败时，有错误日志且不静默失败",
    "TC-M2-010": "同一消息重复回调时，不会重复发送回复",
    "TC-M5-F01": "转人工时，工作台能正确显示用户 WhatsApp 标识",
    "TC-M5-F02": "转人工时，工作台能带上用户最近一次咨询意图",
    "TC-M5-F03": "转人工时，工作台能展示最近几轮对话历史",
    "TC-M5-F04": "转人工时，工作台能正确显示用户昵称",
    "TC-M5-F05": "转人工时，转人工标识字段正确传递",
    "TC-M5-F06": "转人工时，来源和摘要等扩展字段正确传递",
    "TC-M5-010": "转人工后用户连续发消息，机器人均不再自动回复",
    "TC-M6-A01": "转人工请求传递正确的 Hot70 技能组 ID",
    "TC-M6-A02": "转人工后，会话在技能组内正确分配给坐席",
    "TC-M6-A03": "坐席接单并回复后，用户 WhatsApp 能收到人工消息",
    "TC-M7-001": "人工会话中，坐席发送纯文本用户能正常收到",
    "TC-M7-002": "人工会话中，坐席发送多行文本格式可读",
    "TC-M7-003": "人工会话中，坐席连续发送多条消息用户均能收到",
    "TC-M7-004": "人工会话中用户再发消息，机器人不抢答且人工可继续回复",
    "TC-M7-005": "人工回复送达率达到99%以上",
    "TC-M8-001": "日志中同一用户多轮对话的 session_id 保持一致",
    "TC-M8-002": "日志中用户 wa_id/phone 记录正确",
    "TC-M8-003": "日志中 message_time 可用于计算响应耗时",
    "TC-M8-004": "日志中 user_message 保存用户原文",
    "TC-M8-005": "日志中 detected_intent 有识别结果",
    "TC-M8-006": "日志中 confidence 如有则正确记录",
    "TC-M8-007": "日志中 knowledge_hit 与是否命中知识库一致",
    "TC-M8-008": "日志中 bot_reply 与实际发送内容一致",
    "TC-M8-009": "转人工场景下日志 handoff_flag 为 true",
    "TC-M8-010": "未命中 FAQ 的问题可汇总导出",
    "TC-M8-011": "API 异常时日志中有 error 记录",
    "TC-M9-001": "用户表示已预订未提机时，写入对应客户标签",
    "TC-M9-002": "用户未预订但高意向咨询时，写入对应客户标签",
    "TC-M9-003": "用户未预订低意向时，写入对应客户标签",
    "TC-M9-004": "用户表示已提机时，写入对应客户标签",
    "TC-M9-005": "用户进线但无互动时，按规则处理沉默标签",
    "TC-M9-006": "普通打招呼等场景，不强行打客户标签",
    "TC-M9-007": "用户意图变化时，客户标签能正确更新",
    "TC-M9-008": "应打标场景的标签写入成功率达到95%以上",
    "TC-M10-001": "用户发送辱骂或敏感内容时，有兜底或转人工且不崩溃",
    "TC-M10-002": "用户提及竞品时，按运营规则合理回复",
    "TC-M10-003": "用户连续两次问同一 FAQ，回复内容保持一致",
    "TC-M10-004": "会话超时后用户再发消息，行为符合 session 策略",
    "TC-M10-005": "iOS 与 Android 双端 WhatsApp 消息展示均正常",
    "TC-M4-P1-001": "FAQ 无覆盖的问题不编造答案，兜底并引导转人工",
    "TC-M4-P1-002": "库存等动态信息问题转人工，不硬答",
    "TC-M4-P1-003": "订单进度等动态信息问题转人工处理",
    "TC-M4-P1-004": "未命中 FAQ 的问题可在日志中追踪和汇总",
    "TC-L4-001": "验收指标：消息收发成功率100%",
    "TC-L4-002": "验收指标：机器人回复准确率≥85%",
    "TC-L4-003": "验收指标：转人工准确率≥90%",
    "TC-L4-004": "验收指标：人工回复送达率≥99%",
    "TC-L4-005": "验收指标：平均响应时间≤10秒",
    "TC-L4-006": "验收指标：未命中问题100%可追踪",
    "TC-M11-001": "用户发送空消息时，机器人友好提示重新输入",
    "TC-M11-002": "用户只发 Emoji 时，机器人引导用文字描述或转人工",
    "TC-M11-003": "用户发送乱码时，机器人兜底引导且不崩溃",
    "TC-M11-004": "用户问超范围问题时，机器人不编造并转接人工",
    "TC-M11-005": "FAQ 无覆盖的问题，机器人兜底话术后转人工",
    "TC-M11-006": "转人工接口失败时，用户看到友好提示且日志有 error",
    "TC-M11-007": "消息发送失败时，用户看到重试提示且日志有 error",
    "TC-M11-008": "响应超时时，用户收到繁忙/稍候类 apology",
    "TC-M11-009": "用户发送图片等非文本时，机器人引导发送文字",
    "TC-M11-010": "用户辱骂时，机器人礼貌回应并转人工",
    "TC-M11-011": "一条消息含多个意图时，机器人引导用户澄清",
    "TC-M11-012": "会话超时后再进线，机器人欢迎回来并继续接待",
    "TC-M11-013": "用户短时间刷屏时，机器人防重复且不崩溃",
    "TC-M11-014": "系统异常时不向用户暴露内部错误码或字段名",
}


def truncate(text, max_len=40):
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def system_title(r):
    title = (r.get("title") or "").strip()
    if title and title != r["id"]:
        return title
    tid = r["id"]
    if tid in SYSTEM_TITLES:
        return SYSTEM_TITLES[tid]
    inp = r.get("input", "").strip()
    mod = MODULE_LABEL.get(r["module"], r["module"])
    if inp and inp not in ("—", "-"):
        return f"{mod}：用户发送「{truncate(inp)}」时行为符合预期"
    return f"{mod}：{truncate(r.get('expected_result', '行为符合预期'), 60)}"


def faq_title(r):
    inp = r["input"].strip()
    intent = r.get("expected_intent", "")
    action = r.get("expected_action", "")
    ho = r.get("should_handoff", "")
    src = r.get("source", "faq")
    facts = (r.get("expected_facts") or "").strip()
    topic = INTENT_TOPIC.get(intent, intent or "FAQ")

    q = truncate(inp, 36)
    fact_hint = ""
    if facts and action not in ("handoff", "none") and ho != "true":
        first_fact = facts.split("|")[0].strip()
        if first_fact:
            fact_hint = f"，回复含「{truncate(first_fact, 20)}」"

    if src == "faq_paraphrase":
        prefix = f"相似问法识别-{topic}"
        if action == "handoff" or ho == "true":
            return f"{prefix}：用户发「{q}」时应转接人工"
        return f"{prefix}：用户发「{q}」时应正确识别并回复{fact_hint}"

    if action == "handoff" or ho == "true":
        return f"{topic}：用户问「{q}」时应转接人工客服"
    if action == "none":
        return f"{topic}：用户问「{q}」时机器人不应自动回复"
    if ho == "conditional":
        return f"{topic}：用户问「{q}」时应正确回复{fact_hint or ''}（必要时可转人工）"
    return f"{topic}：用户问「{q}」时应正确回复{fact_hint}"


def adversarial_title(r):
    cat = r.get("category", "异常")
    reason = r.get("reason", "")
    inp = truncate(r.get("input", ""), 28)
    action = r.get("expected_action", "")
    hint = r.get("expected_prompt_hint", "")

    if action == "none":
        return f"{cat}：验证{reason or '转人工后'}机器人不再自动回复（Q02）"
    if action == "handoff":
        hint_part = f"，提示含「{hint.split('|')[0]}」" if hint else ""
        return f"{cat}：用户发「{inp}」时应说明原因并转接人工{hint_part}"
    if hint:
        return f"{cat}：用户发「{inp}」时应友好回复且提示含「{hint.split('|')[0]}」"
    return f"{cat}：{reason or '异常输入'}时系统有合理提示且不崩溃"


def load_adversarial_cases():
    path = DATA / "corpus-adversarial.csv"
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            cid = r["id"]
            inp = r["input"]
            action = r.get("expected_action", "")
            hint = r.get("expected_prompt_hint", "")
            reason = r.get("reason", "")
            pri = r.get("priority", "P0")
            cat_label = r.get("category", "异常场景")

            name = adversarial_title(r)

            if action == "none":
                expected = "1. 机器人不自动回复（Q02）\n2. 会话由人工/智齿链路承接"
            elif action == "handoff":
                expected = "1. 触发转人工；说明原因且不编造事实"
                if hint:
                    expected += f"\n2. 用户可见提示含关键词：{hint.replace('|', ' 或 ')}"
            else:
                expected = "1. 机器人友好回复，服务不崩溃"
                if hint:
                    expected += f"\n2. 用户可见提示含关键词：{hint.replace('|', ' 或 ')}"

            operation = format_operation_steps(
                "G1 环境就绪；参见 spec/exception-handling.md",
                inp,
                expected,
                f"1. 用户发送或模拟：{inp if inp and not inp.startswith('(') else reason}\n2. 查看 WhatsApp/工作台回复与日志",
            )
            rows.append(
                case_row(
                    cid,
                    name,
                    USER_STORY,
                    pri,
                    "异常测试",
                    cat_label,
                    "G1 环境就绪；参见 spec/exception-handling.md",
                    operation,
                    expected,
                    layer="L2/L3",
                    automation="agent",
                    source="corpus-adversarial",
                    rule_id=r.get("rule_id", ""),
                    note=reason,
                )
            )
    return rows


INTENT_CAT = {
    "产品信息": "M3/M4-商品",
    "活动规则": "M3/M4-活动",
    "活动权益": "M3/M4-权益",
    "提机相关": "M3/M4-提机",
    "门店相关": "M3/M4-门店",
    "官方身份": "M3/M4-官方",
    "人工兜底": "M3/M4-兜底",
    "人工客服": "M5-转人工",
    "无法覆盖": "M3-兜底",
}


def format_operation_steps(pre, inp, expected, steps_text=""):
    """仅生成操作步骤文本（不含前置、预期、补充）。"""
    skip = {"—", "-", ""}
    if steps_text and steps_text.strip():
        return steps_text.strip()
    if inp and inp not in skip:
        return f"1. 用户 WhatsApp 发送：{inp}"
    return "1. 按用例场景执行操作"


def case_row(
    case_id,
    name,
    story,
    level,
    ctype,
    category,
    preconditions,
    operation_steps,
    expected_result,
    layer="",
    automation="",
    source="",
    rule_id="",
    note="",
):
    return [
        case_id,
        name,
        story,
        PRODUCT,
        level,
        ctype,
        category,
        preconditions,
        operation_steps,
        expected_result,
        layer,
        automation,
        source,
        rule_id,
        note,
        "",
        CREATOR,
        "",
        "",
        "",
    ]


def load_system_cases():
    path = DATA / "test-cases-full.csv"
    rows = []
    with path.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            cat = MODULE_LABEL.get(r["module"], r["module"])
            ctype = TYPE_MAP.get(r["type"], "功能测试")
            name = system_title(r)
            rows.append(
                case_row(
                    r["id"],
                    name,
                    USER_STORY,
                    r["priority"],
                    ctype,
                    cat,
                    r.get("preconditions", ""),
                    format_operation_steps(
                        r.get("preconditions", ""),
                        r.get("input", ""),
                        r.get("expected_result", ""),
                        r.get("steps", ""),
                    ),
                    r.get("expected_result", ""),
                    layer=r.get("layer", ""),
                    automation=r.get("automation", ""),
                    source=r.get("source", ""),
                    rule_id="",
                    note=r.get("corpus_ref", ""),
                )
            )
    return rows


def load_faq_cases():
    path = DATA / "corpus-intent.csv"
    rows = []
    with path.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            cid = r["id"]
            inp = r["input"]
            intent = r.get("expected_intent", "")
            action = r.get("expected_action", "")
            facts = r.get("expected_facts", "")
            ho = r.get("should_handoff", "")
            pri = r.get("priority", "P0")
            src = r.get("source", "faq")
            cat = INTENT_CAT.get(intent, f"M3/M4-{intent}")

            name = faq_title(r)

            if action == "handoff" or ho == "true":
                expected = "1. 触发转人工（handoff=true）\n2. 不编造 FAQ 外事实\n3. 用户可见转人工或说明类提示"
            elif action == "none":
                expected = "1. 机器人不自动回复\n2. 符合 Q02 或静默场景"
            else:
                if facts:
                    facts_short = facts.replace("|", "、")[:120]
                    expected = (
                        f"1. 意图识别为：{intent}\n"
                        f"2. 回复包含关键事实：{facts_short}\n"
                        f"3. 不编造 FAQ 未覆盖内容"
                    )
                else:
                    expected = f"1. 意图识别为：{intent}\n2. 回复与 FAQ 口径一致"

            if ho == "conditional":
                expected += "\n4. 若用户追问特殊/动态信息，应视情况转人工"

            operation = format_operation_steps(
                "G1 环境就绪；FAQ 状态建议已确认；RAGFlow 可用",
                inp,
                expected,
                f"1. 用户 WhatsApp 发送：{inp}\n2. 查看机器人回复是否含 expected_facts 关键词\n3. 查 agent/session 的 task_type 与 handoff 状态",
            )
            rows.append(
                case_row(
                    cid,
                    name,
                    USER_STORY,
                    pri,
                    TYPE_MAP.get(src, "功能测试"),
                    cat,
                    "G1 环境就绪；FAQ 状态建议已确认；RAGFlow 可用",
                    operation,
                    expected,
                    layer="L2",
                    automation="agent",
                    source=src,
                    rule_id=r.get("rule_id", ""),
                    note=f"意图：{intent}" if intent else "",
                )
            )
    return rows


def main():
    out = DATA / "Hot70_all_test_cases.csv"
    all_rows = load_system_cases() + load_adversarial_cases() + load_faq_cases()

    def write_csv(path: Path):
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(HEADER_ROW1)
            w.writerow(HEADER_ROW2)
            for r in all_rows:
                w.writerow(r)

    try:
        write_csv(out)
        print(f"OK {out} total={len(all_rows)} (system + adversarial + faq corpus)")
    except PermissionError:
        fallback = PRD / "Hot70_all_test_cases.csv"
        write_csv(fallback)
        print(
            f"WARN: {out} locked (close in editor); wrote {fallback} total={len(all_rows)}",
            file=__import__("sys").stderr,
        )


if __name__ == "__main__":
    main()
