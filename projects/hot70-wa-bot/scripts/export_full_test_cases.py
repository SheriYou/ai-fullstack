# -*- coding: utf-8 -*-
"""Generate full test case suite with human-readable titles, steps, and expectations."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"

CASES = []


def add(module, cid, title, ctype, pre, steps, inp, expected, layer, auto, pri, source, corpus_ref="", verify_profile=""):
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
        "verify_profile": verify_profile,
    })


# --- M1 Smoke G2 ---
SMOKE = [
    ("TC-SMOKE-001", "验证用户打招呼后10秒内收到机器人正常回复",
     "G1 环境已通过；WhatsApp 测试号或 webhook 探针可用；机器人 Agent 模式已开启",
     "1. 用户向 Hot70 测试号发送：你好\n2. 记录发送时间\n3. 查看 WhatsApp 是否收到回复\n4. 在工作台或 messages API 确认 inbound 已入库",
     "你好",
     "1. 10 秒内收到机器人 outbound 回复\n2. 回复为正常接待话术（非英文系统兜底、非转人工提示）\n3. messages/inbound 有记录；agent/session 可查到 task_type"),
    ("TC-SMOKE-002", "验证询问 Hot70 价格时能基于知识库回复含价格信息",
     "G1 已通过；RAGFlow/知识库已配置且可用",
     "1. 用户发送：Hot70 多少钱（或 Hot70 Pro 5G 多少钱）\n2. 查看机器人回复内容\n3. 查 agent/tools/logs 中 RagflowTool 是否 success\n4. 记录响应耗时",
     "Hot70 多少钱",
     "1. 回复含价格关键信息（如 BDT/36,999 或 FAQ 口径等价表述）\n2. 不应仅返回英文转人工兜底\n3. RAG/tools 日志可观测命中；响应 ≤10s"),
    ("TC-SMOKE-003-LOCAL", "验证用户说转人工时触发 Web 本地坐席分配且机器人暂停",
     "G1 已通过；至少 1 名 Web 坐席 online 且可自动分配",
     "1. 用户发送：转人工\n2. 查看 Web 工作台会话列表/分配结果\n3. 查 Conversation：handoffTarget、isActiveAgent、conversationStatus\n4. 确认机器人仍发送了转人工提示（如有）",
     "转人工",
     "1. handoffTarget=LOCAL（或等价本地 handoff 状态）\n2. isActiveAgent=0\n3. Web 工作台可见新会话或已分配坐席\n4. 符合 Q02：后续由人工链路承接"),
    ("TC-SMOKE-003-EXT", "验证工作台外部转人工后智齿工作台出现会话且含 groupid",
     "智齿渠道已配置；externalHandoffEnabled=true；Hot70 技能组 groupid 已记录",
     "1. 先完成一轮机器人对话（可选）\n2. 在 Web 工作台对该用户执行「外部转人工」\n3. 登录智齿工作台查看是否出现新会话\n4. 查 externalHandoffResultJson 或接口日志中的 groupid",
     "external-handoff（工作台操作）",
     "1. 智齿工作台可见该用户会话\n2. 转人工请求含正确 Hot70 groupid\n3. conversationStatus=external_handoff；机器人不再自动 FAQ 回复"),
    ("TC-SMOKE-003b", "验证转人工后用户再发消息时机器人不再自动回复（Q02）",
     "已完成 TC-SMOKE-003-LOCAL 或 003-EXT，会话处于人工/转人工状态",
     "1. 在转人工状态下，用户连续发送：在吗、还有人吗\n2. 观察 WhatsApp 是否收到新的机器人 outbound\n3. 对比转人工前后的 messages 列表",
     "在吗 / 还有人吗",
     "1. 两条消息均无新的机器人自动 FAQ 回复\n2. 仅人工/智齿链路可回复（若坐席在线）\n3. 符合 Q02 静默要求"),
    ("TC-SMOKE-004", "验证坐席在工作台回复后用户 WhatsApp 能收到人工消息",
     "用户已转人工；坐席已接单或可在工作台发消息",
     "1. 坐席在 Web 工作台向该用户发送：您好，我是 Hot70 客服\n2. 用户在 WhatsApp 查看是否收到\n3. 查 messages outbound 方向与 sendStatus",
     "（坐席）您好，我是 Hot70 客服",
     "1. 用户 WA 收到坐席消息，内容与发送一致\n2. messages 有 outbound 且 sendStatus 非 failed\n3. 送达延迟在可接受范围"),
    ("TC-SMOKE-005", "验证会话全链路可通过 agent/session 与 messages 追踪",
     "已完成至少一轮用户↔机器人或用户↔人工对话",
     "1. 调用 GET agent/session/{whatsappId}\n2. 调用 GET messages/{whatsappId}\n3. 对照 spec/log-field-mapping.md 核对字段",
     "—",
     "1. session_id 多轮一致\n2. 有 detected task_type（intent）\n3. 转人工场景 handoff 状态可识别\n4. inbound/outbound 与实际操作一致"),
]
for cid, title, pre, steps, inp, exp in SMOKE:
    add("M1", cid, title, "smoke", pre, steps, inp, exp, "L3", "human", "P0", "test_plan")

# --- M2 Message ---
M2 = [
    ("TC-M2-001", "验证英文纯文本消息能正常接入并得到处理",
     "L1/L3 环境就绪；webhook 或真机可用",
     "1. 用户发送：Hello\n2. 查看是否有 outbound 或兜底回复\n3. 确认服务未 500/无响应",
     "Hello", "1. 消息正常入库\n2. 有合理回复或中文兜底引导\n3. 系统不崩溃"),
    ("TC-M2-002", "验证英文 FAQ 问法能识别并回复或转人工",
     "知识库含英文或跨语言检索已配置",
     "1. 用户发送：How to pre-order?\n2. 查看回复内容与 task_type\n3. 若无法回答应转人工而非编造",
     "How to pre-order?", "1. 有 outbound 回复\n2. 回复与预订 FAQ 一致或合理转人工\n3. 不 silent fail"),
    ("TC-M2-003", "验证含 Emoji 消息不崩溃且有回复或兜底",
     "G1 就绪",
     "1. 用户发送：😀👍\n2. 观察回复与日志",
     "😀👍", "1. 服务正常\n2. 有友好提示或继续对话能力\n3. 无 500/堆栈暴露给用户"),
    ("TC-M2-004", "验证空消息或纯空格时有友好提示",
     "G1 就绪",
     "1. 用户发送纯空格或空内容\n2. 查看回复",
     "   ", "1. 提示重新输入（含「没有收到有效内容/请重新输入」类关键词）\n2. 不崩溃"),
    ("TC-M2-005", "验证超长文本（>500字）不崩溃且合理处理",
     "G1 就绪",
     "1. 用户发送超过 500 字文本\n2. 查看回复",
     ">500 字重复或长段文本", "1. 不崩溃\n2. 提示简要描述或引导转人工\n3. 不 silent fail"),
    ("TC-M2-006", "验证3秒内连发3条不同问题均能处理且 session 不串",
     "G1 就绪",
     "1. 3 秒内连续发送 3 条不同 FAQ 问题\n2. 查看 3 条 inbound 与对应 outbound\n3. 核对 session_id 一致",
     "连发 3 条不同问题", "1. 3 条均有处理记录\n2. 同一用户 session_id 不串号\n3. 回复与问题大致对应（允许串行处理）"),
    ("TC-M2-007", "验证机器人回复能在用户 WhatsApp 端可见",
     "Gateway 或智齿发送链路已连通",
     "1. 发送任意 FAQ 问题\n2. 在用户 WA 端确认可见 outbound",
     "任意 FAQ 问法", "1. 用户 WA 可见机器人回复\n2. sendStatus=success（非 SEND_FAILED）"),
    ("TC-M2-008", "验证 FAQ 回复平均响应时间不超过10秒",
     "发送链路正常；准备 30 条抽样问法",
     "1. 对 30 条 FAQ 逐条发送并计时（发消息→收到 outbound）\n2. 计算平均耗时",
     "30 条 FAQ 抽样", "1. 平均响应时间 ≤10s\n2. 超时样本有日志可追踪"),
    ("TC-M2-009", "验证智齿/网关发消息 API 失败时有 error 日志且不 silent fail",
     "可 mock 或使用测试开关模拟发送失败",
     "1. 模拟 outbound API 失败\n2. 触发一次机器人回复\n3. 查日志与用户侧提示",
     "模拟智齿/网关发送失败", "1. 服务端有 error 日志\n2. 用户侧有友好提示或可见失败状态\n3. 不 silent fail"),
    ("TC-M2-010", "验证同一 message_id 重复回调不会重复发送回复",
     "L1 可重复 POST 同一 webhook",
     "1. 用相同 message_id 连续 POST webhook 2 次\n2. 统计 outbound 条数",
     "同一 message_id 回调 2 次", "1. 仅处理 1 次\n2. 用户只收到 1 条机器人回复（或第 2 次 ignored）"),
]
for cid, title, pre, steps, inp, exp in M2:
    add("M2", cid, title, "integration", pre, steps, inp, exp, "L1/L3", "both", "P0", "test_plan")

# --- M5 LOCAL ---
M5_LOCAL = [
    ("TC-M5-LOCAL-001", "验证 AI 判定转人工时 Web 本地坐席自动分配",
     "坐席 online；autoAssign 已开启",
     "1. 用户发送明确转人工话术（或触发 AI handoff 的问题）\n2. 查看 Web 工作台分配\n3. 查 Conversation 字段",
     "转人工", "1. handoffTarget=LOCAL\n2. assignedUserId 有值或 handoffStatus=assigned/no_agent_online 可解释\n3. isActiveAgent=0"),
    ("TC-M5-LOCAL-002", "验证本地转人工后用户连发消息机器人均不再自动回复",
     "已完成本地转人工",
     "1. 转人工后再连发 3 条：在吗、请问、hello\n2. 统计新增机器人 outbound 条数",
     "转人工后再发 3 条", "1. 3 条均无新的机器人 FAQ 自动回复\n2. 符合 Q02"),
]
for cid, title, pre, steps, inp, exp in M5_LOCAL:
    add("M5", cid, title, "handoff", pre, steps, inp, exp, "L3", "human", "P0", "handoff-dual-path")

# --- M5 EXT ---
M5_EXT = [
    ("TC-M5-F01", "验证智齿外部转人工时用户标识 partnerid/wa_id 正确传递",
     "ZHICHI 渠道；externalHandoffEnabled=true；已触发 external-handoff",
     "1. 执行 external-handoff\n2. 在智齿工作台/日志查看用户标识\n3. 与用户 WhatsApp ID 对照",
     "external-handoff", "1. partnerid/wa_id 与测试用户一致\n2. 工作台可识别该访客"),
    ("TC-M5-F02", "验证外部转人工时最近意图字段正确传递",
     "先多轮 FAQ 对话再 external-handoff",
     "1. 先问价格/配置类问题 2-3 轮\n2. 执行 external-handoff\n3. 查智齿侧最近意图/摘要",
     "多轮 FAQ 后 external-handoff", "1. 最近意图与最后一轮 FAQ 主题一致（如产品/价格）\n2. 坐席可见上下文"),
    ("TC-M5-F03", "验证外部转人工时 history_messages 含最近 N 轮对话（默认50）",
     "已有多轮文本对话",
     "1. 进行 ≥3 轮文本对话\n2. external-handoff\n3. 查 handoff 请求中 history 条数与内容",
     "多轮后 external-handoff", "1. history 含最近对话原文\n2. 条数 ≤ 配置的 historyLimit（默认 50）\n3. 仅 text 消息纳入"),
    ("TC-M5-F04", "验证外部转人工时用户昵称正确展示",
     "用户有 sender_name 或 profile",
     "1. external-handoff\n2. 查智齿工作台昵称字段",
     "external-handoff", "1. user_name/nick 合理展示\n2. 非空或符合渠道默认值"),
    ("TC-M5-F05", "验证外部转人工时 tran_flag 转人工标识正确",
     "智齿转人工 API 可用",
     "1. external-handoff\n2. 查请求/日志中 tran_flag",
     "external-handoff", "1. tran_flag 与渠道配置一致\n2. 智齿识别为转人工会话"),
    ("TC-M5-F06", "验证外部转人工时 params/customer_fields 扩展字段正确",
     "渠道 config 含 source/摘要等",
     "1. external-handoff\n2. 查 params、customer_fields",
     "external-handoff", "1. 含 whatsapp_id、business_line_id、channel_key 等\n2. 来源/摘要字段符合配置"),
    ("TC-M5-010", "验证智齿外部转人工后用户连发消息机器人不再自动回复",
     "external_handoff 已成功",
     "1. 转人工后再发 3 条用户消息\n2. 确认无新的机器人 FAQ outbound",
     "转人工后再发 3 条", "1. 均无机器人自动回复\n2. 后续消息转发智齿（若配置）\n3. 符合 Q02"),
]
for cid, title, pre, steps, inp, exp in M5_EXT:
    add("M5", cid, title, "handoff", pre, steps, inp, exp, "L1/L3", "both", "P0", "test_plan/prd_6.3")

# --- M6 ---
M6 = [
    ("TC-M6-A01", "验证外部转人工请求传递正确的 Hot70 技能组 groupid",
     "external-handoff 已触发；groupid 已在 handoff-allocation.md 记录",
     "1. 执行 external-handoff\n2. 查请求/日志/智齿侧 groupid\n3. 与配置值对照",
     "external-handoff", "1. 请求含 Hot70 专属 groupid\n2. 非空且与 G1 记录一致"),
    ("TC-M6-A02", "验证转人工后会话进入智齿技能组且组内坐席可接单",
     "智齿技能组内有 online 坐席",
     "1. external-handoff\n2. 登录智齿工作台查看会话队列/分配\n3. 坐席尝试接单",
     "external-handoff", "1. 会话出现在 Hot70 技能组\n2. 组内坐席可见并可接单"),
    ("TC-M6-A03", "验证智齿坐席回复后用户 WhatsApp 能收到人工消息",
     "坐席已接单",
     "1. 智齿坐席发送回复\n2. 用户 WA 查看\n3. 查 agent-messages 回调与 outbound",
     "external-handoff 后坐席回复", "1. 用户 WA 收到人工消息\n2. 内容与坐席发送一致\n3. sendStatus 成功"),
]
for cid, title, pre, steps, inp, exp in M6:
    add("M6", cid, title, "integration", pre, steps, inp, exp, "L1/L3", "human", "P0", "test_plan/prd_6.4")

# --- M7 ---
M7 = [
    ("TC-M7-001", "验证人工会话中坐席发送纯文本用户能正常收到",
     "用户已转人工；坐席可发消息",
     "1. 坐席发送单段纯文本\n2. 用户 WA 确认",
     "坐席纯文本示例", "1. 用户收到完整文本\n2. 无乱码/截断"),
    ("TC-M7-002", "验证人工会话中坐席发送多行文本格式可读",
     "已转人工",
     "1. 坐席发送含换行的多行消息\n2. 用户 WA 查看排版",
     "多行文本", "1. 换行/段落可读\n2. 未合并成不可读乱码"),
    ("TC-M7-003", "验证人工会话中坐席连发3条消息用户均能收到",
     "已转人工",
     "1. 坐席连续发送 3 条不同消息\n2. 用户确认 3 条均到达且顺序合理",
     "坐席连发 3 条", "1. 3 条均送达\n2. 顺序与发送一致"),
    ("TC-M7-004", "验证人工会话中用户再发消息时机器人不抢答且人工可继续",
     "已转人工；Q02 已确认",
     "1. 用户再发一条咨询\n2. 观察是否有机器人 outbound\n3. 坐席继续回复",
     "用户再发消息", "1. 机器人不自动 FAQ 抢答\n2. 坐席仍可正常回复用户"),
    ("TC-M7-005", "验证人工回复送达率达到99%以上（≥20次抽样）",
     "已转人工；可统计 ≥20 次坐席发送",
     "1. 记录 ≥20 次坐席 outbound\n2. 用户在 WA 确认是否收到\n3. 计算送达率",
     "≥20 次坐席发送抽样", "1. 送达率 ≥99%\n2. 失败样本有 sendStatus/日志可查"),
]
for cid, title, pre, steps, inp, exp in M7:
    add("M7", cid, title, "integration", pre, steps, inp, exp, "L3", "human", "P0", "test_plan/prd_5.1")

# --- M8 ---
M8 = [
    ("TC-M8-001", "验证同一用户多轮对话 session_id 保持一致",
     "已有 ≥2 轮对话样本",
     "1. 同一用户连续发送 2+ 条消息\n2. GET agent/session 与 Conversation\n3. 对比 session_id",
     "—", "1. agent/session.session_id 多轮不变\n2. 可用于日志串联"),
    ("TC-M8-002", "验证日志中 wa_id/phone 与用户 WhatsApp 标识一致",
     "有测试对话",
     "1. 查 Conversation.whatsappId 与 messages\n2. 与真实 WA 号对照",
     "—", "1. wa_id/phone 正确\n2. 无串用户"),
    ("TC-M8-003", "验证 message_time/timestamp 可用于计算响应耗时",
     "有 inbound+outbound 样本",
     "1. 取 inbound 与下一条 outbound 的 timestamp\n2. 计算差值",
     "—", "1. timestamp 存在且合理\n2. 差值与体感/指标一致"),
    ("TC-M8-004", "验证 user_message 保存用户 inbound 原文",
     "有 inbound 样本",
     "1. 发送含特定关键词的消息\n2. 查 messages inbound content",
     "—", "1. content 与用户发送原文一致（含 emoji/英文）"),
    ("TC-M8-005", "验证 detected_intent 记录为 task_type 且有值",
     "Agent 已处理至少 1 条",
     "1. 发送 FAQ 问题\n2. 查 ChatMessage.intent 或 agent/session task_type",
     "—", "1. intent/task_type 非空（如 QA_ANSWER）\n2. 与路由 Agent 一致"),
    ("TC-M8-006", "验证 confidence 在 AgentStep 中有记录（如有）",
     "有 agent steps",
     "1. GET agent/session steps\n2. 查 output_json.confidence",
     "—", "1. 低置信/高置信场景有 confidence 数值\n2. 低置信触发转人工策略可追踪"),
    ("TC-M8-007", "验证 RAG 命中可通过 tools/logs 推断",
     "RAG 正常时",
     "1. 发送 FAQ 命中问法\n2. GET agent/tools/logs 查 RagflowTool",
     "—", "1. RagflowTool success=true 且有 answer\n2. 未命中场景 success=false 或走 handoff"),
    ("TC-M8-008", "验证 bot_reply/outbound 与实际发送内容一致",
     "有成功 outbound",
     "1. 对比用户 WA 所见与 messages outbound content\n2. 查 bot 日志",
     "—", "1. 内容一致\n2. 无未发送却标记成功"),
    ("TC-M8-009", "验证转人工场景 handoffStatus/conversationStatus 正确",
     "已触发转人工",
     "1. 转人工后查 Conversation\n2. 对照 handoff-dual-path 预期状态",
     "—", "1. handoff 或 external_handoff 状态正确\n2. isActiveAgent=0"),
    ("TC-M8-010", "验证未命中 FAQ 问题可在 audit/logs 汇总",
     "有未命中/转人工样本",
     "1. 发送无覆盖问题\n2. 查 audit-logs 与 handoff 记录\n3. 尝试导出汇总",
     "—", "1. 未命中样本可检索\n2. 含 user_message 与 handoff 原因"),
    ("TC-M8-011", "验证 API/发送异常时服务端有 error 日志",
     "可触发或已有失败样本",
     "1. 查找 sendStatus=failed 或模拟异常\n2. 查服务端 [ZHICHI_*]/error 日志",
     "—", "1. 有 error 级日志\n2. 含渠道/用户/失败原因"),
]
for cid, title, pre, steps, inp, exp in M8:
    add("M8", cid, title, "log", pre, steps, inp, exp, "L1/L4", "agent", "P0", "test_plan/prd_6.5")

# --- M9 Blocked ---
M9 = [
    ("TC-M9-001", "验证用户表示已预订未提机时写入智齿标签「已预订未提机」",
     "Blocked：后端未实现 PRD 五类智齿客户标签",
     "1. 用户发送：我已经预订了还没提\n2. 查智齿客户标签 API/后台",
     "我已经预订了还没提", "1. 智齿侧出现对应标签\n2. 标签 ID 与 Q05 配置一致（功能实现后验证）"),
    ("TC-M9-002", "验证未预订高意向咨询时写入「未预订高意向」标签",
     "Blocked", "1. 用户发送：分期怎么买\n2. 查智齿标签", "分期怎么买", "1. 写入高意向标签"),
    ("TC-M9-003", "验证未预订低意向互动时写入「未预订低意向」标签",
     "Blocked", "1. 用户发送：只想领福利\n2. 查智齿标签", "只想领福利", "1. 写入低意向标签"),
    ("TC-M9-004", "验证用户表示已提机时写入「已提机」标签",
     "Blocked", "1. 用户发送：我已经提机了\n2. 查智齿标签", "我已经提机了", "1. 写入已提机标签"),
    ("TC-M9-005", "验证进线无互动时按 PRD 处理「沉默未互动」标签",
     "Blocked", "1. 模拟进线无用户消息\n2. 查标签策略", "进线无消息", "1. 按 PRD 不强行打标或打沉默标签"),
    ("TC-M9-006", "验证普通打招呼时不强行更新客户标签",
     "Blocked", "1. 用户仅发送：你好\n2. 查智齿标签是否变化", "你好", "1. 不更新标签或保持未识别"),
    ("TC-M9-007", "验证对话信息更明确时客户标签可更新",
     "Blocked", "1. 先问价格再说已预订\n2. 查标签变化", "先问价格后说已预订", "1. 标签从低意向更新为已预订未提机（示例）"),
    ("TC-M9-008", "验证应打标场景标签写入成功率≥95%",
     "Blocked；≥20 样本", "1. 执行应打标场景 ≥20 次\n2. 统计智齿写入成功数", "应写场景抽样", "1. 成功率 ≥95%"),
]
for cid, title, pre, steps, inp, exp in M9:
    add("M9", cid, title, "tag", pre, steps, inp, exp, "—", "both", "P1", "test_plan/prd_6.6")

# --- M10 ---
M10 = [
    ("TC-M10-001", "验证用户发送辱骂/敏感内容时有兜底或转人工且不崩溃",
     "真机 WhatsApp；G1 就绪",
     "1. 发送辱骂或敏感内容（测试环境可控文案）\n2. 观察回复与稳定性",
     "辱骂/敏感内容（测试文案）", "1. 不崩溃\n2. 礼貌回应或转人工\n3. 不向用户暴露内部错误"),
    ("TC-M10-002", "验证用户提及竞品时按运营口径回复",
     "真机；运营口径已确认",
     "1. 发送竞品对比类问题\n2. 对照运营规则",
     "竞品手机怎么样", "1. 回复符合 Hot70/官方渠道口径\n2. 不恶意贬低或编造"),
    ("TC-M10-003", "验证同一 FAQ 连问两次回复口径一致",
     "真机；RAG 正常",
     "1. 同一 FAQ 连问 2 次\n2. 对比两次 outbound 关键事实",
     "同一 FAQ 连问 2 次", "1. 两次关键事实不矛盾\n2. 允许措辞差异"),
    ("TC-M10-004", "验证会话超时后再进线行为符合 session 策略",
     "真机；可模拟超时",
     "1. 空闲超过配置超时时间\n2. 再发 Hot70 相关问题",
     "超时后发 FAQ", "1. 有欢迎回来/继续咨询类提示（若 PRD 要求）\n2. 会话策略符合配置"),
    ("TC-M10-005", "验证 iOS 与 Android 双端 WhatsApp 消息展示正常",
     "iOS + Android 各 1 台测试机",
     "1. 双端分别发送 FAQ 与收回复\n2. 检查排版、emoji、链接",
     "双端各测一轮", "1. 双端均能收发\n2. 展示无严重截断/乱码"),
]
for cid, title, pre, steps, inp, exp in M10:
    add("M10", cid, title, "explore", pre, steps, inp, exp, "L3", "human", "P1", "test_plan")

# --- M4 三原则 ---
M4 = [
    ("TC-M4-P1-001", "验证 FAQ 无覆盖问题不编造答案并兜底转人工",
     "G1 就绪",
     "1. 发送 FAQ 明确无覆盖的问题\n2. 查回复与 handoff",
     "FAQ 无覆盖问题（如火星上有 Hot70 吗）", "1. 回复含无法确认/转接人工类关键词\n2. handoff 触发\n3. 不编造事实"),
    ("TC-M4-P1-002", "验证库存等动态信息问题说明后转人工不硬答",
     "G1 就绪",
     "1. 发送：还有库存吗\n2. 查回复与 handoff",
     "还有库存吗", "1. 说明需人工查实时信息\n2. 转人工\n3. 回复含「实时/转接」类提示"),
    ("TC-M4-P1-003", "验证订单进度等动态信息问题转人工不硬答",
     "G1 就绪",
     "1. 发送：我的订单到哪了\n2. 查回复",
     "我的订单到哪了", "1. 说明订单需人工查询\n2. 转人工\n3. 不编造物流信息"),
    ("TC-M4-P1-004", "验证未命中 FAQ 问题可在日志中追踪和汇总",
     "G1 就绪",
     "1. 触发未命中\n2. 查 audit/tools/session\n3. 确认可导出汇总",
     "触发未命中问法", "1. 日志可追踪 user_message\n2. handoff/未命中原因可汇总"),
]
for cid, title, pre, steps, inp, exp in M4:
    add("M4", cid, title, "faq_rule", pre, steps, inp, exp, "L2/L3", "both", "P0", "test_plan/prd_6.2")

# --- M11 Exception ---
M11 = [
    ("TC-M11-001", "验证空消息时机器人友好提示重新输入",
     "G1 就绪", "1. 发送空/纯空格\n2. 查回复", "   ",
     "1. 含「没有收到有效内容/请重新输入」\n2. 不崩溃"),
    ("TC-M11-002", "验证仅 Emoji 时引导用文字描述或转人工",
     "G1 就绪", "1. 发送：😀😀😀\n2. 查回复", "😀😀😀",
     "1. 含「暂未理解/请用文字/转人工」类提示"),
    ("TC-M11-003", "验证乱码输入时兜底引导且不崩溃",
     "G1 就绪", "1. 发送：asdfghjkl123\n2. 查回复", "asdfghjkl123",
     "1. 含「暂未理解」并引导 Hot70 话题或转人工"),
    ("TC-M11-004", "验证超范围问题不编造并转接人工",
     "G1 就绪", "1. 发送：今天天气怎么样\n2. 查回复与 handoff", "今天天气怎么样",
     "1. 不编造天气答案\n2. 转人工\n3. 含「无法/转接人工」"),
    ("TC-M11-005", "验证 FAQ 无覆盖问题兜底话术后转人工",
     "G1 就绪", "1. 发送无覆盖问题\n2. 查回复", "火星上有 Hot70 吗",
     "1. 兜底+转人工\n2. 含「无法确认/转接」"),
    ("TC-M11-006", "验证转人工接口失败时用户可见友好提示且有 error 日志",
     "L1 mock 转人工失败", "1. 模拟转人工 API 失败\n2. 查用户提示与日志", "（模拟转人工 API 失败）",
     "1. 用户可见「暂时无法接通/稍后再试」\n2. 服务端有 error 日志"),
    ("TC-M11-007", "验证发消息失败时用户可见重试提示且有 error 日志",
     "L1 mock 发送失败", "1. 模拟 outbound 失败\n2. 查提示与日志", "（模拟智齿发送失败）",
     "1. 用户可见「发送遇到问题/稍后重试」\n2. 有 error 日志"),
    ("TC-M11-008", "验证响应超时时用户收到繁忙/稍候类 apology",
     "L1 mock >10s", "1. 模拟超时\n2. 查用户提示", "（模拟响应超过10秒）",
     "1. 含「稍等/繁忙/转人工」类 apology\n2. 不暴露内部错误码"),
    ("TC-M11-009", "验证用户发送图片等非文本时引导发送文字",
     "G1 就绪", "1. 用户发送图片（或模拟）\n2. 查回复", "（用户发图片）",
     "1. 含「暂不支持/请发送文字/转人工」"),
    ("TC-M11-010", "验证用户辱骂时礼貌回应并转人工且不崩溃",
     "真机", "1. 发送辱骂测试文案\n2. 查回复", "你是傻逼（测试文案）",
     "1. 礼貌回应+转人工\n2. 不崩溃"),
    ("TC-M11-011", "验证一条消息多意图时机器人引导用户澄清",
     "G1 就绪", "1. 发送：价格多少还有门店在哪\n2. 查回复", "价格多少还有门店在哪",
     "1. 含澄清引导「请问想了解哪一个/分开咨询」"),
    ("TC-M11-012", "验证会话超时后再进线有欢迎回来提示",
     "真机", "1. 超时 30 分钟后发送 FAQ\n2. 查回复", "（超时30分钟后）Hot70 多少钱",
     "1. 含「欢迎回来/继续咨询」类提示"),
    ("TC-M11-013", "验证短时间刷屏时防重复且不崩溃",
     "真机", "1. 3 秒连发 10 条「在吗」\n2. 查回复", "3秒连发10条在吗",
     "1. 不崩溃\n2. 含「已收到/请稍候/勿重复」类提示"),
    ("TC-M11-014", "验证系统异常时不向用户暴露 stack/错误码/groupid",
     "L1 mock 任意 API 异常", "1. 触发 API 异常\n2. 查用户可见文案", "（触发任意 API 异常）",
     "1. 用户侧仅友好提示\n2. 无 stack/null/groupid/handoff_flag 等内部字段"),
]
for item in M11:
    cid, title, pre, steps, inp, exp = item
    pre_full = pre
    layer = "L3" if pre == "真机" else "L1/L2/L3"
    pri = "P0" if cid in {
        "TC-M11-001", "TC-M11-002", "TC-M11-003", "TC-M11-004", "TC-M11-005",
        "TC-M11-006", "TC-M11-007", "TC-M11-008", "TC-M11-009", "TC-M11-010",
    } else "P1"
    add("M11", cid, title, "exception", pre_full, steps, inp, exp, layer, "both", pri, "exception-handling")

# --- L4 ---
L4 = [
    ("TC-L4-001", "验收：消息收发成功率达到100%",
     "功能测试完成；≥50 样本", "1. 统计 inbound 成功接入与 outbound/人工送达\n2. 计算成功率", "—", "1. 消息收发成功率 = 100%"),
    ("TC-L4-002", "验收：机器人回复准确率达到85%以上",
     "L2/L3 样本 ≥50", "1. 按 corpus 关键事实匹配统计 Pass\n2. Fail 100% 人工复核", "—", "1. 回复准确率 ≥85%"),
    ("TC-L4-003", "验收：转人工准确率达到90%以上",
     "corpus-handoff ≥50", "1. 对比应转/不应转样本\n2. 统计准确率", "—", "1. 转人工准确率 ≥90%"),
    ("TC-L4-004", "验收：人工回复送达率达到99%以上",
     "L3 ≥20 次", "1. 记录坐席发送与用户收到\n2. 计算送达率", "—", "1. 人工回复送达率 ≥99%"),
    ("TC-L4-005", "验收：平均响应时间不超过10秒",
     "≥30 样本", "1. 统计发消息到 outbound 耗时\n2. 求平均", "—", "1. 平均响应时间 ≤10s"),
    ("TC-L4-006", "验收：未命中问题100%可追踪",
     "全量未命中样本", "1. 汇总未命中/转人工日志\n2. 检查是否均可检索", "—", "1. 未命中可追踪率 = 100%"),
]
for cid, title, pre, steps, inp, exp in L4:
    add("L4", cid, title, "acceptance", pre, steps, inp, exp, "L4", "agent", "P0", "test_plan/prd_7.3")

FIELDS = [
    "id", "module", "title", "type", "preconditions", "steps", "input",
    "expected_result", "layer", "automation", "priority", "source", "corpus_ref",
    "verify_profile",
]


def main():
    from test_case_profile_map import PROFILES

    for c in CASES:
        c["verify_profile"] = PROFILES.get(c["id"], "exec:manual_only|manual:未配置profile")
    write_csv(DATA / "test-cases-full.csv", CASES)
    write_review_md(REPORTS / "test-cases-full-review.md")
    print(f"system_cases={len(CASES)}")


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_review_md(path):
    lines = [
        "# Hot70 完整测试用例集（Review）",
        "",
        f"> 共 **{len(CASES)}** 条结构化用例",
        "",
        "字段说明：`title` 含验证点；`steps` / `expected_result` 可直接给测试人员执行；`verify_profile` 供脚本逐条断言。",
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
        for c in by_mod[mod]:
            lines.append(f"### {c['id']} — {c['title']}")
            lines.append("")
            lines.append(f"- **前置**：{c['preconditions']}")
            lines.append(f"- **输入**：{c['input'] or '—'}")
            lines.append(f"- **verify_profile**：`{c.get('verify_profile', '')}`")
            lines.append(f"- **步骤**：")
            for line in (c["steps"] or "").split("\n"):
                lines.append(f"  {line}")
            lines.append(f"- **预期**：")
            for line in (c["expected_result"] or "").split("\n"):
                lines.append(f"  {line}")
            lines.append(f"- **层/执行**：{c['layer']} / {c['automation']} / {c['priority']}")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
