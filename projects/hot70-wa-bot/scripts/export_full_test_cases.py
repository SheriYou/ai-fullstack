# -*- coding: utf-8 -*-
"""Generate full test case suite: FAQ corpus + test plan + PRD requirements."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"

# type: smoke | faq | intent | handoff | integration | log | acceptance | explore | tag
CASES = []

def add(module, cid, title, ctype, pre, steps, inp, expected, layer, auto, pri, source, corpus_ref=""):
    CASES.append({
        "id": cid,
        "module": module,
        "title": title,
        "type": ctype,
        "preconditions": pre,
        "steps": steps,
        "input": inp,
        "expected_result": expected,
        "layer": layer,
        "automation": auto,
        "priority": pri,
        "source": source,
        "corpus_ref": corpus_ref,
    })

# --- M1 Smoke G2 ---
for cid, steps, inp, exp in [
    ("TC-SMOKE-001", "1. WA 发消息", "你好", "10s 内机器人回复；日志有 user_message"),
    ("TC-SMOKE-002", "1. WA 发 FAQ 问法", "Hot70 多少钱", "回复含价格信息；knowledge_hit=true"),
    ("TC-SMOKE-003", "1. WA 发转人工", "转人工", "handoff=true；工作台有新会话；机器人暂停"),
    ("TC-SMOKE-003b", "1. 转人工后连发 2 条", "在吗 / 还有人吗", "无机器人自动回复（Q02）"),
    ("TC-SMOKE-004", "1. 坐席在工作台回复", "（坐席）您好", "用户 WA 收到人工消息"),
    ("TC-SMOKE-005", "1. 查 session 日志", "—", "session 全链路：消息/意图/转人工/回复字段齐全"),
]:
    add("M1", cid, cid, "smoke", "G1 环境就绪", steps, inp, exp, "L3", "human", "P0", "test_plan")

# --- M2 Message ---
for cid, title, inp, exp in [
    ("TC-M2-001", "纯文本接入", "Hello", "正常处理并回复"),
    ("TC-M2-002", "英文 FAQ", "How to pre-order?", "正常回复或转人工"),
    ("TC-M2-003", "Emoji", "😀👍", "不崩溃；有回复或兜底"),
    ("TC-M2-004", "空消息", "   ", "兜底或提示重新输入"),
    ("TC-M2-005", "超长文本", ">500 字", "不崩溃；合理处理"),
    ("TC-M2-006", "3 秒连发 3 条", "连发 3 条不同问题", "均有处理；session 不串"),
    ("TC-M2-007", "回复送达", "任意 FAQ", "用户 WA 可见回复"),
    ("TC-M2-008", "响应时间", "30 条 FAQ 抽样计时", "平均 ≤10s"),
    ("TC-M2-009", "发消息 API 失败", "模拟智齿发送失败", "有 error 日志；不 silent fail"),
    ("TC-M2-010", "回调幂等", "同一 message_id 回调 2 次", "不重复回复"),
]:
    add("M2", cid, title, "integration", "L1 环境/API mock", f"1. {title}", inp, exp, "L1/L3", "both", "P0", "test_plan")

# --- M5 Handoff (non-FAQ) ---
for cid, title, inp, exp in [
    ("TC-M5-F01", "转人工字段 partnerid/wa_id", "转人工", "工作台用户标识正确"),
    ("TC-M5-F02", "转人工字段 最近意图", "先问价格再转人工", "最近意图=产品/价格"),
    ("TC-M5-F03", "转人工字段 history_messages", "多轮后转人工", "含最近 N 轮对话"),
    ("TC-M5-F04", "转人工字段 user_name", "转人工", "昵称合理展示"),
    ("TC-M5-F05", "转人工字段 tran_flag", "转人工", "转人工标识正确"),
    ("TC-M5-F06", "转人工字段 params", "转人工", "来源/摘要等扩展字段正确"),
    ("TC-M5-010", "转人工后机器人暂停", "转人工后再发 3 条", "均无机器人自动回复"),
]:
    add("M5", cid, title, "handoff", "可触发转人工", f"1. 执行场景", inp, exp, "L1/L3", "both", "P0", "test_plan/prd_6.3")

# --- M6 Skill group ---
for cid, title, exp in [
    ("TC-M6-A01", "转人工传 groupid", "请求含 Hot70 技能组 groupid"),
    ("TC-M6-A02", "技能组内分配", "工作台可见会话；组内坐席可接单"),
    ("TC-M6-A03", "用户收到人工回复", "分配后坐席回复，用户 WA 收到"),
]:
    add("M6", cid, title, "integration", "技能组已配置", "1. 触发转人工 2. 检查工作台", "转人工", exp, "L1/L3", "human", "P0", "test_plan/prd_6.4")

# --- M7 Human reply ---
for cid, title, steps, exp in [
    ("TC-M7-001", "坐席纯文本", "坐席发纯文本", "用户收到"),
    ("TC-M7-002", "坐席多行", "坐席发多行", "格式可读"),
    ("TC-M7-003", "坐席连发 3 条", "坐席连发", "用户均收到"),
    ("TC-M7-004", "人工期间用户再发", "用户再发消息", "按 Q02：机器人不抢答；人工可继续"),
    ("TC-M7-005", "送达率统计", "≥20 次抽样", "送达率 ≥99%"),
]:
    add("M7", cid, title, "integration", "已转人工", steps, "—", exp, "L3", "human", "P0", "test_plan/prd_5.1")

# --- M8 Logs ---
for cid, field in [
    ("TC-M8-001", "session_id 多轮一致"),
    ("TC-M8-002", "wa_id/phone 正确"),
    ("TC-M8-003", "message_time 可算耗时"),
    ("TC-M8-004", "user_message 原文"),
    ("TC-M8-005", "detected_intent 有值"),
    ("TC-M8-006", "confidence 如有则记录"),
    ("TC-M8-007", "knowledge_hit 正确"),
    ("TC-M8-008", "bot_reply 与发送一致"),
    ("TC-M8-009", "handoff_flag 转人工场景=true"),
    ("TC-M8-010", "未命中问题可汇总导出"),
    ("TC-M8-011", "API 异常有 error 日志"),
]:
    add("M8", cid, f"日志字段 {field}", "log", "有测试对话样本", f"1. 查日志 2. 验 {field}", "—", field, "L1/L4", "agent", "P0", "test_plan/prd_6.5")

# --- M9 Tags P1 ---
for cid, title, inp, exp in [
    ("TC-M9-001", "已预订未提机", "我已经预订了还没提", "智齿标签写入"),
    ("TC-M9-002", "未预订高意向", "分期怎么买", "标签写入"),
    ("TC-M9-003", "未预订低意向", "只想领福利", "标签写入"),
    ("TC-M9-004", "已提机", "我已经提机了", "标签写入"),
    ("TC-M9-005", "沉默未互动", "进线无消息", "按 PRD 处理"),
    ("TC-M9-006", "不强行打标", "你好", "不更新标签"),
    ("TC-M9-007", "标签可更新", "先问价格后说已预订", "标签更新"),
    ("TC-M9-008", "写入成功率", "应写场景抽样", "≥95%"),
]:
    add("M9", cid, title, "tag", "P1 标签 API 可用", "1. 发消息", inp, exp, "L2/L3", "both", "P1", "test_plan/prd_6.6")

# --- M10 Explore ---
for cid, title, inp, exp in [
    ("TC-M10-001", "敏感词", "辱骂/敏感内容", "兜底或转人工；不崩溃"),
    ("TC-M10-002", "竞品提及", "竞品手机", "按运营规则"),
    ("TC-M10-003", "重复同一 FAQ", "同一问题连问 2 次", "回复一致"),
    ("TC-M10-004", "会话超时后再发", "超时后发消息", "符合 session 策略"),
    ("TC-M10-005", "iOS+Android", "双端各测", "消息展示正常"),
]:
    add("M10", cid, title, "explore", "真机", "1. 执行", inp, exp, "L3", "human", "P1", "test_plan")

# --- PRD 三原则 ---
for cid, title, inp, exp in [
    ("TC-M4-P1-001", "不编造", "FAQ 无覆盖问题", "兜底话术+转人工；回复含「无法确认/转接人工」；不编造"),
    ("TC-M4-P1-002", "动态信息转人工", "还有库存吗", "说明需人工查实时信息；转人工；回复含「实时/转接」"),
    ("TC-M4-P1-003", "动态信息转人工2", "我的订单到哪了", "说明订单需人工查询；转人工"),
    ("TC-M4-P1-004", "未命中沉淀", "触发未命中", "日志可追踪可汇总"),
]:
    add("M4", cid, title, "faq_rule", "—", "1. 发消息", inp, exp, "L2/L3", "both", "P0", "test_plan/prd_6.2")

# --- M11 Exception scenarios (see spec/exception-handling.md) ---
for cid, title, inp, exp in [
    ("TC-M11-001", "空消息友好提示", "   ", "回复含「没有收到有效内容/请重新输入」；不崩溃"),
    ("TC-M11-002", "仅Emoji提示", "😀😀😀", "回复含「暂未理解/请用文字/转人工」"),
    ("TC-M11-003", "乱码兜底", "asdfghjkl123", "回复含「暂未理解」并引导 Hot70 话题或转人工"),
    ("TC-M11-004", "超范围不编造", "今天天气怎么样", "不编造；转人工；回复含「无法/转接人工」"),
    ("TC-M11-005", "无覆盖问题兜底", "火星上有 Hot70 吗", "兜底+转人工；回复含「无法确认/转接」"),
    ("TC-M11-006", "转人工失败提示", "（模拟转人工 API 失败）", "用户可见「暂时无法接通/稍后再试」；有 error 日志"),
    ("TC-M11-007", "发消息失败提示", "（模拟智齿发送失败）", "用户可见「发送遇到问题/稍后重试」；有 error 日志"),
    ("TC-M11-008", "响应超时提示", "（模拟>10s）", "用户可见「稍等/繁忙/转人工」 apology"),
    ("TC-M11-009", "非文本消息引导", "（用户发图片）", "回复含「暂不支持/请发送文字/转人工」"),
    ("TC-M11-010", "辱骂转人工", "你是傻逼", "礼貌回应+转人工；不崩溃"),
    ("TC-M11-011", "多意图澄清", "价格多少还有门店在哪", "回复含澄清引导「请问想了解哪一个/分开咨询」"),
    ("TC-M11-012", "会话超时欢迎", "（超时30分钟后）Hot70 多少钱", "回复含「欢迎回来/继续咨询」"),
    ("TC-M11-013", "刷屏防重复", "3秒连发10条在吗", "不崩溃；回复含「已收到/请稍候」"),
    ("TC-M11-014", "不向用户暴露内部错误", "（触发任意 API 异常）", "用户侧无 stack/错误码/groupid；仅友好提示"),
]:
    pre = "L1 环境/API mock" if "模拟" in inp or "触发" in inp else ("真机" if cid in ("TC-M11-010", "TC-M11-012", "TC-M11-013") else "G1 环境就绪")
    layer = "L3" if pre == "真机" else "L1/L2/L3"
    pri = "P0" if cid in {
        "TC-M11-001", "TC-M11-002", "TC-M11-003", "TC-M11-004", "TC-M11-005",
        "TC-M11-006", "TC-M11-007", "TC-M11-008", "TC-M11-009", "TC-M11-010",
    } else "P1"
    add("M11", cid, title, "exception", pre, "1. 执行异常场景", inp, exp, layer, "both", pri, "exception-handling")

# --- Acceptance L4 ---
for cid, title, exp in [
    ("TC-L4-001", "消息收发成功率", "100%"),
    ("TC-L4-002", "回复准确率", "≥85%"),
    ("TC-L4-003", "转人工准确率", "≥90%"),
    ("TC-L4-004", "人工回复送达率", "≥99%"),
    ("TC-L4-005", "平均响应时间", "≤10s"),
    ("TC-L4-006", "未命中可追踪率", "100%"),
]:
    add("L4", cid, title, "acceptance", "功能测试完成", "1. 统计指标", "—", exp, "L4", "agent", "P0", "test_plan/prd_7.3")

FIELDS = [
    "id", "module", "title", "type", "preconditions", "steps", "input",
    "expected_result", "layer", "automation", "priority", "source", "corpus_ref",
]

def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def write_review_md(path):
    lines = [
        "# Hot70 完整测试用例集（Review）",
        "",
        f"> 共 **{len(CASES)}** 条结构化用例（含 FAQ 语料引用说明）",
        "",
        "## 两层用例体系",
        "",
        "| 层级 | 文件 | 用途 |",
        "|------|------|------|",
        "| **L2 语料** | `data/corpus-*.csv`（271+ 条） | 用户问法 + 预期意图/回复/转人工；Agent 批量跑 |",
        "| **完整用例** | `data/test-cases-full.csv`（本文） | 冒烟/链路/字段/日志/指标/异常；人工+L1/L3 执行 |",
        "",
        "> FAQ Review 仍看 `corpus-review-for-ops.md`；系统测试看本文。",
        "",
        "---",
        "",
    ]
    by_mod = {}
    for c in CASES:
        by_mod.setdefault(c["module"], []).append(c)
    for mod in sorted(by_mod.keys()):
        lines.append(f"## {mod}（{len(by_mod[mod])} 条）")
        lines.append("")
        lines.append("| ID | 标题 | 类型 | 步骤/输入 | 预期 | 层 | 执行 |")
        lines.append("|----|------|------|-----------|------|-----|------|")
        for c in by_mod[mod]:
            inp = (c["input"] or "—").replace("|", "/")[:30]
            exp = c["expected_result"].replace("|", "/")[:40]
            steps = c["steps"].replace("|", "/")[:30]
            lines.append(
                f"| {c['id']} | {c['title']} | {c['type']} | {steps}/{inp} | {exp} | {c['layer']} | {c['automation']} |"
            )
        lines.append("")
    lines += [
        "---",
        "",
        "## FAQ 语料（M3/M4）",
        "",
        "完整 69 主问 + 271 扩展见：`corpus-review-for-ops.md` + `corpus-intent.csv`",
        "",
        "PRD 要求但不在语料中的：**M2/M5/M6/M7/M8/M9/M10/M11/验收指标** — 已在本文件系统用例中覆盖。",
        "",
        "异常场景规则见 `spec/exception-handling.md`；L2 语料见 `corpus-adversarial.csv`。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")

def main():
    write_csv(DATA / "test-cases-full.csv", CASES)
    write_review_md(REPORTS / "test-cases-full-review.md")
    print(f"system_cases={len(CASES)}")

if __name__ == "__main__":
    main()
