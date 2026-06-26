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
    "步骤", "创建时间", "创建人", "执行人", "执行时间", "执行结果",
] + [""] * 7

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
    "TC-SMOKE-003": "用户说转人工时，成功转接人工且工作台出现新会话",
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
}


def truncate(text, max_len=40):
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def system_title(r):
    tid = r["id"]
    if tid in SYSTEM_TITLES:
        return SYSTEM_TITLES[tid]
    title = r.get("title", "").strip()
    if title and title != tid:
        inp = r.get("input", "").strip()
        if inp and inp not in ("—", "-"):
            return f"{title}：用户发送「{truncate(inp)}」时行为符合预期"
        return title
    inp = r.get("input", "").strip()
    mod = MODULE_LABEL.get(r["module"], r["module"])
    if inp and inp not in ("—", "-"):
        return f"{mod}：用户发送「{truncate(inp)}」时行为符合预期"
    return f"{mod}：{r.get('expected_result', '行为符合预期')}"


def faq_title(r):
    inp = r["input"].strip()
    intent = r.get("expected_intent", "")
    action = r.get("expected_action", "")
    ho = r.get("should_handoff", "")
    src = r.get("source", "faq")
    topic = INTENT_TOPIC.get(intent, intent or "FAQ")

    q = truncate(inp, 36)

    if src == "faq_paraphrase":
        prefix = f"相似问法识别-{topic}"
        if action == "handoff" or ho == "true":
            return f"{prefix}：用户发「{q}」时转接人工"
        return f"{prefix}：用户发「{q}」时能正确识别并回复"

    if action == "handoff" or ho == "true":
        return f"{topic}：用户问「{q}」时转接人工客服"
    if action == "none":
        return f"{topic}：用户问「{q}」时机器人不自动回复"
    if ho == "conditional":
        return f"{topic}：用户问「{q}」时机器人正确回复（必要时可转人工）"
    return f"{topic}：用户问「{q}」时机器人正确回复"


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


def format_steps(pre, inp, expected, extra=""):
    skip = {"—", "-", ""}
    parts = []
    if pre and pre not in skip:
        parts.append(f"前置条件：{pre}")
    if inp and inp not in skip:
        parts.append(f"1. 用户 WhatsApp 发送：{inp}")
    else:
        parts.append("1. 按用例场景执行操作")
    parts.append(f"2. 预期结果：{expected}")
    if extra:
        parts.append(f"3. 补充：{extra}")
    return "\n".join(parts)


def row(case_id, name, story, level, ctype, category, steps):
    return [
        case_id, name, story, PRODUCT, level, ctype, category, steps,
        "", CREATOR, "", "", "",
    ] + [""] * 7


def load_system_cases():
    path = DATA / "test-cases-full.csv"
    rows = []
    with path.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            cat = MODULE_LABEL.get(r["module"], r["module"])
            ctype = TYPE_MAP.get(r["type"], "功能测试")
            name = system_title(r)
            steps = format_steps(
                r["preconditions"],
                r["input"],
                r["expected_result"],
                f"测试层：{r['layer']}；自动化：{r['automation']}；来源：{r['source']}",
            )
            rows.append(row(r["id"], name, USER_STORY, r["priority"], ctype, cat, steps))
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
                expected = "触发转人工；handoff_flag=true"
            elif action == "none":
                expected = "机器人不自动回复"
            else:
                expected = f"意图={intent}；回复包含关键事实：{facts}" if facts else f"意图={intent}；正确回复"

            if ho == "conditional":
                expected += "；视情况可能转人工"

            steps = format_steps(
                "G1 环境就绪；FAQ 状态建议已确认",
                inp,
                expected,
                f"规则：{r.get('rule_id','')}；来源：{src}",
            )
            rows.append(row(cid, name, USER_STORY, pri, TYPE_MAP.get(src, "功能测试"), cat, steps))
    return rows


def main():
    out = PRD / "Hot70_all_test_cases.csv"
    all_rows = load_system_cases() + load_faq_cases()

    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER_ROW1)
        w.writerow(HEADER_ROW2)
        for r in all_rows:
            w.writerow(r)

    print(f"OK {out} total={len(all_rows)} (system + faq corpus)")


if __name__ == "__main__":
    main()
