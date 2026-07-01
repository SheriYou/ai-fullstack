# Hot70 完整测试用例集（Review）

> 共 **82** 条结构化用例

字段说明：`title` 含验证点；`steps` / `expected_result` 可直接给测试人员执行；`verify_profile` 供脚本逐条断言。

---

## L4（6 条）

### TC-L4-001 — 验收：消息收发成功率达到100%

- **前置**：功能测试完成；≥50 样本
- **输入**：—
- **verify_profile**：`exec:metrics|checks:metrics_aggregate`
- **步骤**：
  1. 统计 inbound 成功接入与 outbound/人工送达
  2. 计算成功率
- **预期**：
  1. 消息收发成功率 = 100%
- **层/执行**：L4 / agent / P0

### TC-L4-002 — 验收：机器人回复准确率达到85%以上

- **前置**：L2/L3 样本 ≥50
- **输入**：—
- **verify_profile**：`exec:metrics|checks:metrics_aggregate`
- **步骤**：
  1. 按 corpus 关键事实匹配统计 Pass
  2. Fail 100% 人工复核
- **预期**：
  1. 回复准确率 ≥85%
- **层/执行**：L4 / agent / P0

### TC-L4-003 — 验收：转人工准确率达到90%以上

- **前置**：corpus-handoff ≥50
- **输入**：—
- **verify_profile**：`exec:metrics|checks:metrics_aggregate`
- **步骤**：
  1. 对比应转/不应转样本
  2. 统计准确率
- **预期**：
  1. 转人工准确率 ≥90%
- **层/执行**：L4 / agent / P0

### TC-L4-004 — 验收：人工回复送达率达到99%以上

- **前置**：L3 ≥20 次
- **输入**：—
- **verify_profile**：`exec:metrics|manual:人工送达率L3`
- **步骤**：
  1. 记录坐席发送与用户收到
  2. 计算送达率
- **预期**：
  1. 人工回复送达率 ≥99%
- **层/执行**：L4 / agent / P0

### TC-L4-005 — 验收：平均响应时间不超过10秒

- **前置**：≥30 样本
- **输入**：—
- **verify_profile**：`exec:metrics|checks:metrics_aggregate`
- **步骤**：
  1. 统计发消息到 outbound 耗时
  2. 求平均
- **预期**：
  1. 平均响应时间 ≤10s
- **层/执行**：L4 / agent / P0

### TC-L4-006 — 验收：未命中问题100%可追踪

- **前置**：全量未命中样本
- **输入**：—
- **verify_profile**：`exec:metrics|manual:未命中追踪汇总`
- **步骤**：
  1. 汇总未命中/转人工日志
  2. 检查是否均可检索
- **预期**：
  1. 未命中可追踪率 = 100%
- **层/执行**：L4 / agent / P0

## M1（7 条）

### TC-SMOKE-001 — 验证用户打招呼后10秒内收到机器人正常回复

- **前置**：G1 环境已通过；WhatsApp 测试号或 webhook 探针可用；机器人 Agent 模式已开启
- **输入**：你好
- **verify_profile**：`exec:webhook|messages:你好|checks:webhook_ok,inbound_ok,outbound≤10s,not_handoff_tpl,bot_active,task_type`
- **步骤**：
  1. 用户向 Hot70 测试号发送：你好
  2. 记录发送时间
  3. 查看 WhatsApp 是否收到回复
  4. 在工作台或 messages API 确认 inbound 已入库
- **预期**：
  1. 10 秒内收到机器人 outbound 回复
  2. 回复为正常接待话术（非英文系统兜底、非转人工提示）
  3. messages/inbound 有记录；agent/session 可查到 task_type
- **层/执行**：L3 / human / P0

### TC-SMOKE-002 — 验证询问 Hot70 价格时能基于知识库回复含价格信息

- **前置**：G1 已通过；RAGFlow/知识库已配置且可用
- **输入**：Hot70 多少钱
- **verify_profile**：`exec:webhook|messages:Hot70 多少钱|checks:webhook_ok,outbound≤10s,price_keywords,not_handoff_tpl,rag_tool_ok`
- **步骤**：
  1. 用户发送：Hot70 多少钱（或 Hot70 Pro 5G 多少钱）
  2. 查看机器人回复内容
  3. 查 agent/tools/logs 中 RagflowTool 是否 success
  4. 记录响应耗时
- **预期**：
  1. 回复含价格关键信息（如 BDT/36,999 或 FAQ 口径等价表述）
  2. 不应仅返回英文转人工兜底
  3. RAG/tools 日志可观测命中；响应 ≤10s
- **层/执行**：L3 / human / P0

### TC-SMOKE-003-LOCAL — 验证用户说转人工时触发 Web 本地坐席分配且机器人暂停

- **前置**：G1 已通过；至少 1 名 Web 坐席 online 且可自动分配
- **输入**：转人工
- **verify_profile**：`exec:webhook|messages:转人工|checks:webhook_ok,local_handoff,handoff_assigned,conv_listed`
- **步骤**：
  1. 用户发送：转人工
  2. 查看 Web 工作台会话列表/分配结果
  3. 查 Conversation：handoffTarget、isActiveAgent、conversationStatus
  4. 确认机器人仍发送了转人工提示（如有）
- **预期**：
  1. handoffTarget=LOCAL（或等价本地 handoff 状态）
  2. isActiveAgent=0
  3. Web 工作台可见新会话或已分配坐席
  4. 符合 Q02：后续由人工链路承接
- **层/执行**：L3 / human / P0

### TC-SMOKE-003-EXT — 验证工作台外部转人工后智齿工作台出现会话且含 groupid

- **前置**：智齿渠道已配置；externalHandoffEnabled=true；Hot70 技能组 groupid 已记录
- **输入**：external-handoff（工作台操作）
- **verify_profile**：`exec:defer_ext|manual:智齿工作台,groupid,external_handoff状态`
- **步骤**：
  1. 先完成一轮机器人对话（可选）
  2. 在 Web 工作台对该用户执行「外部转人工」
  3. 登录智齿工作台查看是否出现新会话
  4. 查 externalHandoffResultJson 或接口日志中的 groupid
- **预期**：
  1. 智齿工作台可见该用户会话
  2. 转人工请求含正确 Hot70 groupid
  3. conversationStatus=external_handoff；机器人不再自动 FAQ 回复
- **层/执行**：L3 / human / P0

### TC-SMOKE-003b — 验证转人工后用户再发消息时机器人不再自动回复（Q02）

- **前置**：已完成 TC-SMOKE-003-LOCAL 或 003-EXT，会话处于人工/转人工状态
- **输入**：在吗 / 还有人吗
- **verify_profile**：`exec:handoff_then_silence|messages:在吗;还有人吗|checks:no_bot_outbound`
- **步骤**：
  1. 在转人工状态下，用户连续发送：在吗、还有人吗
  2. 观察 WhatsApp 是否收到新的机器人 outbound
  3. 对比转人工前后的 messages 列表
- **预期**：
  1. 两条消息均无新的机器人自动 FAQ 回复
  2. 仅人工/智齿链路可回复（若坐席在线）
  3. 符合 Q02 静默要求
- **层/执行**：L3 / human / P0

### TC-SMOKE-004 — 验证坐席在工作台回复后用户 WhatsApp 能收到人工消息

- **前置**：用户已转人工；坐席已接单或可在工作台发消息
- **输入**：（坐席）您好，我是 Hot70 客服
- **verify_profile**：`exec:use_handoff_session|manual:sendManual,WA送达,sendStatus`
- **步骤**：
  1. 坐席在 Web 工作台向该用户发送：您好，我是 Hot70 客服
  2. 用户在 WhatsApp 查看是否收到
  3. 查 messages outbound 方向与 sendStatus
- **预期**：
  1. 用户 WA 收到坐席消息，内容与发送一致
  2. messages 有 outbound 且 sendStatus 非 failed
  3. 送达延迟在可接受范围
- **层/执行**：L3 / human / P0

### TC-SMOKE-005 — 验证会话全链路可通过 agent/session 与 messages 追踪

- **前置**：已完成至少一轮用户↔机器人或用户↔人工对话
- **输入**：—
- **verify_profile**：`exec:use_handoff_session|checks:session_traceable,task_type,handoff_state_m8`
- **步骤**：
  1. 调用 GET agent/session/{whatsappId}
  2. 调用 GET messages/{whatsappId}
  3. 对照 spec/log-field-mapping.md 核对字段
- **预期**：
  1. session_id 多轮一致
  2. 有 detected task_type（intent）
  3. 转人工场景 handoff 状态可识别
  4. inbound/outbound 与实际操作一致
- **层/执行**：L3 / human / P0

## M10（5 条）

### TC-M10-001 — 验证用户发送辱骂/敏感内容时有兜底或转人工且不崩溃

- **前置**：真机 WhatsApp；G1 就绪
- **输入**：辱骂/敏感内容（测试文案）
- **verify_profile**：`exec:manual_only|manual:真机辱骂敏感`
- **步骤**：
  1. 发送辱骂或敏感内容（测试环境可控文案）
  2. 观察回复与稳定性
- **预期**：
  1. 不崩溃
  2. 礼貌回应或转人工
  3. 不向用户暴露内部错误
- **层/执行**：L3 / human / P1

### TC-M10-002 — 验证用户提及竞品时按运营口径回复

- **前置**：真机；运营口径已确认
- **输入**：竞品手机怎么样
- **verify_profile**：`exec:webhook|messages:竞品手机怎么样|checks:webhook_ok|manual:运营口径`
- **步骤**：
  1. 发送竞品对比类问题
  2. 对照运营规则
- **预期**：
  1. 回复符合 Hot70/官方渠道口径
  2. 不恶意贬低或编造
- **层/执行**：L3 / human / P1

### TC-M10-003 — 验证同一 FAQ 连问两次回复口径一致

- **前置**：真机；RAG 正常
- **输入**：同一 FAQ 连问 2 次
- **verify_profile**：`exec:webhook_multi|messages:Hot70 多少钱;Hot70 多少钱|manual:口径一致`
- **步骤**：
  1. 同一 FAQ 连问 2 次
  2. 对比两次 outbound 关键事实
- **预期**：
  1. 两次关键事实不矛盾
  2. 允许措辞差异
- **层/执行**：L3 / human / P1

### TC-M10-004 — 验证会话超时后再进线行为符合 session 策略

- **前置**：真机；可模拟超时
- **输入**：超时后发 FAQ
- **verify_profile**：`exec:manual_only|manual:会话超时`
- **步骤**：
  1. 空闲超过配置超时时间
  2. 再发 Hot70 相关问题
- **预期**：
  1. 有欢迎回来/继续咨询类提示（若 PRD 要求）
  2. 会话策略符合配置
- **层/执行**：L3 / human / P1

### TC-M10-005 — 验证 iOS 与 Android 双端 WhatsApp 消息展示正常

- **前置**：iOS + Android 各 1 台测试机
- **输入**：双端各测一轮
- **verify_profile**：`exec:manual_only|manual:双端真机`
- **步骤**：
  1. 双端分别发送 FAQ 与收回复
  2. 检查排版、emoji、链接
- **预期**：
  1. 双端均能收发
  2. 展示无严重截断/乱码
- **层/执行**：L3 / human / P1

## M11（14 条）

### TC-M11-001 — 验证空消息时机器人友好提示重新输入

- **前置**：G1 就绪
- **输入**：   
- **verify_profile**：`exec:webhook|messages:   |checks:empty_input_hint`
- **步骤**：
  1. 发送空/纯空格
  2. 查回复
- **预期**：
  1. 含「没有收到有效内容/请重新输入」
  2. 不崩溃
- **层/执行**：L1/L2/L3 / both / P0

### TC-M11-002 — 验证仅 Emoji 时引导用文字描述或转人工

- **前置**：G1 就绪
- **输入**：😀😀😀
- **verify_profile**：`exec:webhook|messages:😀😀😀|checks:gibberish_hint,emoji_handled`
- **步骤**：
  1. 发送：😀😀😀
  2. 查回复
- **预期**：
  1. 含「暂未理解/请用文字/转人工」类提示
- **层/执行**：L1/L2/L3 / both / P0

### TC-M11-003 — 验证乱码输入时兜底引导且不崩溃

- **前置**：G1 就绪
- **输入**：asdfghjkl123
- **verify_profile**：`exec:webhook|messages:asdfghjkl123|checks:gibberish_hint`
- **步骤**：
  1. 发送：asdfghjkl123
  2. 查回复
- **预期**：
  1. 含「暂未理解」并引导 Hot70 话题或转人工
- **层/执行**：L1/L2/L3 / both / P0

### TC-M11-004 — 验证超范围问题不编造并转接人工

- **前置**：G1 就绪
- **输入**：今天天气怎么样
- **verify_profile**：`exec:webhook|messages:今天天气怎么样|checks:handoff_required,no_hallucination_handoff`
- **步骤**：
  1. 发送：今天天气怎么样
  2. 查回复与 handoff
- **预期**：
  1. 不编造天气答案
  2. 转人工
  3. 含「无法/转接人工」
- **层/执行**：L1/L2/L3 / both / P0

### TC-M11-005 — 验证 FAQ 无覆盖问题兜底话术后转人工

- **前置**：G1 就绪
- **输入**：火星上有 Hot70 吗
- **verify_profile**：`exec:webhook|messages:火星上有 Hot70 吗|checks:handoff_required`
- **步骤**：
  1. 发送无覆盖问题
  2. 查回复
- **预期**：
  1. 兜底+转人工
  2. 含「无法确认/转接」
- **层/执行**：L1/L2/L3 / both / P0

### TC-M11-006 — 验证转人工接口失败时用户可见友好提示且有 error 日志

- **前置**：L1 mock 转人工失败
- **输入**：（模拟转人工 API 失败）
- **verify_profile**：`exec:manual_only|manual:mock转人工失败`
- **步骤**：
  1. 模拟转人工 API 失败
  2. 查用户提示与日志
- **预期**：
  1. 用户可见「暂时无法接通/稍后再试」
  2. 服务端有 error 日志
- **层/执行**：L1/L2/L3 / both / P0

### TC-M11-007 — 验证发消息失败时用户可见重试提示且有 error 日志

- **前置**：L1 mock 发送失败
- **输入**：（模拟智齿发送失败）
- **verify_profile**：`exec:manual_only|manual:mock发送失败`
- **步骤**：
  1. 模拟 outbound 失败
  2. 查提示与日志
- **预期**：
  1. 用户可见「发送遇到问题/稍后重试」
  2. 有 error 日志
- **层/执行**：L1/L2/L3 / both / P0

### TC-M11-008 — 验证响应超时时用户收到繁忙/稍候类 apology

- **前置**：L1 mock >10s
- **输入**：（模拟响应超过10秒）
- **verify_profile**：`exec:manual_only|manual:mock超时`
- **步骤**：
  1. 模拟超时
  2. 查用户提示
- **预期**：
  1. 含「稍等/繁忙/转人工」类 apology
  2. 不暴露内部错误码
- **层/执行**：L1/L2/L3 / both / P0

### TC-M11-009 — 验证用户发送图片等非文本时引导发送文字

- **前置**：G1 就绪
- **输入**：（用户发图片）
- **verify_profile**：`exec:manual_only|manual:非文本消息`
- **步骤**：
  1. 用户发送图片（或模拟）
  2. 查回复
- **预期**：
  1. 含「暂不支持/请发送文字/转人工」
- **层/执行**：L1/L2/L3 / both / P0

### TC-M11-010 — 验证用户辱骂时礼貌回应并转人工且不崩溃

- **前置**：真机
- **输入**：你是傻逼（测试文案）
- **verify_profile**：`exec:webhook|messages:测试辱骂文案|checks:handoff_required|manual:礼貌回应`
- **步骤**：
  1. 发送辱骂测试文案
  2. 查回复
- **预期**：
  1. 礼貌回应+转人工
  2. 不崩溃
- **层/执行**：L3 / both / P0

### TC-M11-011 — 验证一条消息多意图时机器人引导用户澄清

- **前置**：G1 就绪
- **输入**：价格多少还有门店在哪
- **verify_profile**：`exec:webhook|messages:价格多少还有门店在哪|checks:clarify_multi_intent`
- **步骤**：
  1. 发送：价格多少还有门店在哪
  2. 查回复
- **预期**：
  1. 含澄清引导「请问想了解哪一个/分开咨询」
- **层/执行**：L1/L2/L3 / both / P1

### TC-M11-012 — 验证会话超时后再进线有欢迎回来提示

- **前置**：真机
- **输入**：（超时30分钟后）Hot70 多少钱
- **verify_profile**：`exec:manual_only|manual:超时后再进线`
- **步骤**：
  1. 超时 30 分钟后发送 FAQ
  2. 查回复
- **预期**：
  1. 含「欢迎回来/继续咨询」类提示
- **层/执行**：L3 / both / P1

### TC-M11-013 — 验证短时间刷屏时防重复且不崩溃

- **前置**：真机
- **输入**：3秒连发10条在吗
- **verify_profile**：`exec:manual_only|manual:刷屏10条`
- **步骤**：
  1. 3 秒连发 10 条「在吗」
  2. 查回复
- **预期**：
  1. 不崩溃
  2. 含「已收到/请稍候/勿重复」类提示
- **层/执行**：L3 / both / P1

### TC-M11-014 — 验证系统异常时不向用户暴露 stack/错误码/groupid

- **前置**：L1 mock 任意 API 异常
- **输入**：（触发任意 API 异常）
- **verify_profile**：`exec:manual_only|manual:API异常文案`
- **步骤**：
  1. 触发 API 异常
  2. 查用户可见文案
- **预期**：
  1. 用户侧仅友好提示
  2. 无 stack/null/groupid/handoff_flag 等内部字段
- **层/执行**：L1/L2/L3 / both / P1

## M2（10 条）

### TC-M2-001 — 验证英文纯文本消息能正常接入并得到处理

- **前置**：L1/L3 环境就绪；webhook 或真机可用
- **输入**：Hello
- **verify_profile**：`exec:webhook|messages:Hello|checks:webhook_ok,inbound_ok,handoff_or_faq`
- **步骤**：
  1. 用户发送：Hello
  2. 查看是否有 outbound 或兜底回复
  3. 确认服务未 500/无响应
- **预期**：
  1. 消息正常入库
  2. 有合理回复或中文兜底引导
  3. 系统不崩溃
- **层/执行**：L1/L3 / both / P0

### TC-M2-002 — 验证英文 FAQ 问法能识别并回复或转人工

- **前置**：知识库含英文或跨语言检索已配置
- **输入**：How to pre-order?
- **verify_profile**：`exec:webhook|messages:How to pre-order?|checks:webhook_ok,handoff_or_faq,task_type`
- **步骤**：
  1. 用户发送：How to pre-order?
  2. 查看回复内容与 task_type
  3. 若无法回答应转人工而非编造
- **预期**：
  1. 有 outbound 回复
  2. 回复与预订 FAQ 一致或合理转人工
  3. 不 silent fail
- **层/执行**：L1/L3 / both / P0

### TC-M2-003 — 验证含 Emoji 消息不崩溃且有回复或兜底

- **前置**：G1 就绪
- **输入**：😀👍
- **verify_profile**：`exec:webhook|messages:😀👍|checks:webhook_ok,emoji_handled`
- **步骤**：
  1. 用户发送：😀👍
  2. 观察回复与日志
- **预期**：
  1. 服务正常
  2. 有友好提示或继续对话能力
  3. 无 500/堆栈暴露给用户
- **层/执行**：L1/L3 / both / P0

### TC-M2-004 — 验证空消息或纯空格时有友好提示

- **前置**：G1 就绪
- **输入**：   
- **verify_profile**：`exec:webhook|messages:   |checks:webhook_ok,empty_input_hint`
- **步骤**：
  1. 用户发送纯空格或空内容
  2. 查看回复
- **预期**：
  1. 提示重新输入（含「没有收到有效内容/请重新输入」类关键词）
  2. 不崩溃
- **层/执行**：L1/L3 / both / P0

### TC-M2-005 — 验证超长文本（>500字）不崩溃且合理处理

- **前置**：G1 就绪
- **输入**：>500 字重复或长段文本
- **verify_profile**：`exec:webhook|messages:>500字|checks:webhook_ok,long_text_ok`
- **步骤**：
  1. 用户发送超过 500 字文本
  2. 查看回复
- **预期**：
  1. 不崩溃
  2. 提示简要描述或引导转人工
  3. 不 silent fail
- **层/执行**：L1/L3 / both / P0

### TC-M2-006 — 验证3秒内连发3条不同问题均能处理且 session 不串

- **前置**：G1 就绪
- **输入**：连发 3 条不同问题
- **verify_profile**：`exec:webhook_multi|checks:webhook_ok,multi_inbound,session_stable`
- **步骤**：
  1. 3 秒内连续发送 3 条不同 FAQ 问题
  2. 查看 3 条 inbound 与对应 outbound
  3. 核对 session_id 一致
- **预期**：
  1. 3 条均有处理记录
  2. 同一用户 session_id 不串号
  3. 回复与问题大致对应（允许串行处理）
- **层/执行**：L1/L3 / both / P0

### TC-M2-007 — 验证机器人回复能在用户 WhatsApp 端可见

- **前置**：Gateway 或智齿发送链路已连通
- **输入**：任意 FAQ 问法
- **verify_profile**：`exec:webhook|messages:Hot70 多少钱|checks:webhook_ok,outbound≤10s|manual:真机WA可见`
- **步骤**：
  1. 发送任意 FAQ 问题
  2. 在用户 WA 端确认可见 outbound
- **预期**：
  1. 用户 WA 可见机器人回复
  2. sendStatus=success（非 SEND_FAILED）
- **层/执行**：L1/L3 / both / P0

### TC-M2-008 — 验证 FAQ 回复平均响应时间不超过10秒

- **前置**：发送链路正常；准备 30 条抽样问法
- **输入**：30 条 FAQ 抽样
- **verify_profile**：`exec:metrics|corpus:kb-sample|checks:metrics_aggregate`
- **步骤**：
  1. 对 30 条 FAQ 逐条发送并计时（发消息→收到 outbound）
  2. 计算平均耗时
- **预期**：
  1. 平均响应时间 ≤10s
  2. 超时样本有日志可追踪
- **层/执行**：L1/L3 / both / P0

### TC-M2-009 — 验证智齿/网关发消息 API 失败时有 error 日志且不 silent fail

- **前置**：可 mock 或使用测试开关模拟发送失败
- **输入**：模拟智齿/网关发送失败
- **verify_profile**：`exec:manual_only|manual:mock发送失败,error日志`
- **步骤**：
  1. 模拟 outbound API 失败
  2. 触发一次机器人回复
  3. 查日志与用户侧提示
- **预期**：
  1. 服务端有 error 日志
  2. 用户侧有友好提示或可见失败状态
  3. 不 silent fail
- **层/执行**：L1/L3 / both / P0

### TC-M2-010 — 验证同一 message_id 重复回调不会重复发送回复

- **前置**：L1 可重复 POST 同一 webhook
- **输入**：同一 message_id 回调 2 次
- **verify_profile**：`exec:manual_only|manual:重复message_id`
- **步骤**：
  1. 用相同 message_id 连续 POST webhook 2 次
  2. 统计 outbound 条数
- **预期**：
  1. 仅处理 1 次
  2. 用户只收到 1 条机器人回复（或第 2 次 ignored）
- **层/执行**：L1/L3 / both / P0

## M4（4 条）

### TC-M4-P1-001 — 验证 FAQ 无覆盖问题不编造答案并兜底转人工

- **前置**：G1 就绪
- **输入**：FAQ 无覆盖问题（如火星上有 Hot70 吗）
- **verify_profile**：`exec:webhook|messages:火星上有 Hot70 吗|checks:handoff_required,no_hallucination_handoff`
- **步骤**：
  1. 发送 FAQ 明确无覆盖的问题
  2. 查回复与 handoff
- **预期**：
  1. 回复含无法确认/转接人工类关键词
  2. handoff 触发
  3. 不编造事实
- **层/执行**：L2/L3 / both / P0

### TC-M4-P1-002 — 验证库存等动态信息问题说明后转人工不硬答

- **前置**：G1 就绪
- **输入**：还有库存吗
- **verify_profile**：`exec:webhook|messages:还有库存吗|checks:handoff_required,no_hallucination_handoff`
- **步骤**：
  1. 发送：还有库存吗
  2. 查回复与 handoff
- **预期**：
  1. 说明需人工查实时信息
  2. 转人工
  3. 回复含「实时/转接」类提示
- **层/执行**：L2/L3 / both / P0

### TC-M4-P1-003 — 验证订单进度等动态信息问题转人工不硬答

- **前置**：G1 就绪
- **输入**：我的订单到哪了
- **verify_profile**：`exec:webhook|messages:我的订单到哪了|checks:handoff_required,no_hallucination_handoff`
- **步骤**：
  1. 发送：我的订单到哪了
  2. 查回复
- **预期**：
  1. 说明订单需人工查询
  2. 转人工
  3. 不编造物流信息
- **层/执行**：L2/L3 / both / P0

### TC-M4-P1-004 — 验证未命中 FAQ 问题可在日志中追踪和汇总

- **前置**：G1 就绪
- **输入**：触发未命中问法
- **verify_profile**：`exec:webhook|messages:随便乱问xyz|checks:handoff_required|manual:audit汇总`
- **步骤**：
  1. 触发未命中
  2. 查 audit/tools/session
  3. 确认可导出汇总
- **预期**：
  1. 日志可追踪 user_message
  2. handoff/未命中原因可汇总
- **层/执行**：L2/L3 / both / P0

## M5（9 条）

### TC-M5-LOCAL-001 — 验证 AI 判定转人工时 Web 本地坐席自动分配

- **前置**：坐席 online；autoAssign 已开启
- **输入**：转人工
- **verify_profile**：`exec:webhook|messages:转人工|checks:local_handoff,handoff_assigned`
- **步骤**：
  1. 用户发送明确转人工话术（或触发 AI handoff 的问题）
  2. 查看 Web 工作台分配
  3. 查 Conversation 字段
- **预期**：
  1. handoffTarget=LOCAL
  2. assignedUserId 有值或 handoffStatus=assigned/no_agent_online 可解释
  3. isActiveAgent=0
- **层/执行**：L3 / human / P0

### TC-M5-LOCAL-002 — 验证本地转人工后用户连发消息机器人均不再自动回复

- **前置**：已完成本地转人工
- **输入**：转人工后再发 3 条
- **verify_profile**：`exec:handoff_then_silence|messages:在吗;请问;hello|checks:no_bot_outbound`
- **步骤**：
  1. 转人工后再连发 3 条：在吗、请问、hello
  2. 统计新增机器人 outbound 条数
- **预期**：
  1. 3 条均无新的机器人 FAQ 自动回复
  2. 符合 Q02
- **层/执行**：L3 / human / P0

### TC-M5-F01 — 验证智齿外部转人工时用户标识 partnerid/wa_id 正确传递

- **前置**：ZHICHI 渠道；externalHandoffEnabled=true；已触发 external-handoff
- **输入**：external-handoff
- **verify_profile**：`exec:defer_ext|manual:partnerid,wa_id`
- **步骤**：
  1. 执行 external-handoff
  2. 在智齿工作台/日志查看用户标识
  3. 与用户 WhatsApp ID 对照
- **预期**：
  1. partnerid/wa_id 与测试用户一致
  2. 工作台可识别该访客
- **层/执行**：L1/L3 / both / P0

### TC-M5-F02 — 验证外部转人工时最近意图字段正确传递

- **前置**：先多轮 FAQ 对话再 external-handoff
- **输入**：多轮 FAQ 后 external-handoff
- **verify_profile**：`exec:defer_ext|manual:多轮FAQ后EXT,最近意图`
- **步骤**：
  1. 先问价格/配置类问题 2-3 轮
  2. 执行 external-handoff
  3. 查智齿侧最近意图/摘要
- **预期**：
  1. 最近意图与最后一轮 FAQ 主题一致（如产品/价格）
  2. 坐席可见上下文
- **层/执行**：L1/L3 / both / P0

### TC-M5-F03 — 验证外部转人工时 history_messages 含最近 N 轮对话（默认50）

- **前置**：已有多轮文本对话
- **输入**：多轮后 external-handoff
- **verify_profile**：`exec:defer_ext|manual:history_messages条数`
- **步骤**：
  1. 进行 ≥3 轮文本对话
  2. external-handoff
  3. 查 handoff 请求中 history 条数与内容
- **预期**：
  1. history 含最近对话原文
  2. 条数 ≤ 配置的 historyLimit（默认 50）
  3. 仅 text 消息纳入
- **层/执行**：L1/L3 / both / P0

### TC-M5-F04 — 验证外部转人工时用户昵称正确展示

- **前置**：用户有 sender_name 或 profile
- **输入**：external-handoff
- **verify_profile**：`exec:defer_ext|manual:昵称字段`
- **步骤**：
  1. external-handoff
  2. 查智齿工作台昵称字段
- **预期**：
  1. user_name/nick 合理展示
  2. 非空或符合渠道默认值
- **层/执行**：L1/L3 / both / P0

### TC-M5-F05 — 验证外部转人工时 tran_flag 转人工标识正确

- **前置**：智齿转人工 API 可用
- **输入**：external-handoff
- **verify_profile**：`exec:defer_ext|manual:tran_flag`
- **步骤**：
  1. external-handoff
  2. 查请求/日志中 tran_flag
- **预期**：
  1. tran_flag 与渠道配置一致
  2. 智齿识别为转人工会话
- **层/执行**：L1/L3 / both / P0

### TC-M5-F06 — 验证外部转人工时 params/customer_fields 扩展字段正确

- **前置**：渠道 config 含 source/摘要等
- **输入**：external-handoff
- **verify_profile**：`exec:defer_ext|manual:params,customer_fields`
- **步骤**：
  1. external-handoff
  2. 查 params、customer_fields
- **预期**：
  1. 含 whatsapp_id、business_line_id、channel_key 等
  2. 来源/摘要字段符合配置
- **层/执行**：L1/L3 / both / P0

### TC-M5-010 — 验证智齿外部转人工后用户连发消息机器人不再自动回复

- **前置**：external_handoff 已成功
- **输入**：转人工后再发 3 条
- **verify_profile**：`exec:defer_ext|manual:EXT后静默`
- **步骤**：
  1. 转人工后再发 3 条用户消息
  2. 确认无新的机器人 FAQ outbound
- **预期**：
  1. 均无机器人自动回复
  2. 后续消息转发智齿（若配置）
  3. 符合 Q02
- **层/执行**：L1/L3 / both / P0

## M6（3 条）

### TC-M6-A01 — 验证外部转人工请求传递正确的 Hot70 技能组 groupid

- **前置**：external-handoff 已触发；groupid 已在 handoff-allocation.md 记录
- **输入**：external-handoff
- **verify_profile**：`exec:defer_ext|manual:groupid`
- **步骤**：
  1. 执行 external-handoff
  2. 查请求/日志/智齿侧 groupid
  3. 与配置值对照
- **预期**：
  1. 请求含 Hot70 专属 groupid
  2. 非空且与 G1 记录一致
- **层/执行**：L1/L3 / human / P0

### TC-M6-A02 — 验证转人工后会话进入智齿技能组且组内坐席可接单

- **前置**：智齿技能组内有 online 坐席
- **输入**：external-handoff
- **verify_profile**：`exec:defer_ext|manual:技能组接单`
- **步骤**：
  1. external-handoff
  2. 登录智齿工作台查看会话队列/分配
  3. 坐席尝试接单
- **预期**：
  1. 会话出现在 Hot70 技能组
  2. 组内坐席可见并可接单
- **层/执行**：L1/L3 / human / P0

### TC-M6-A03 — 验证智齿坐席回复后用户 WhatsApp 能收到人工消息

- **前置**：坐席已接单
- **输入**：external-handoff 后坐席回复
- **verify_profile**：`exec:defer_ext|manual:智齿坐席回传`
- **步骤**：
  1. 智齿坐席发送回复
  2. 用户 WA 查看
  3. 查 agent-messages 回调与 outbound
- **预期**：
  1. 用户 WA 收到人工消息
  2. 内容与坐席发送一致
  3. sendStatus 成功
- **层/执行**：L1/L3 / human / P0

## M7（5 条）

### TC-M7-001 — 验证人工会话中坐席发送纯文本用户能正常收到

- **前置**：用户已转人工；坐席可发消息
- **输入**：坐席纯文本示例
- **verify_profile**：`exec:use_handoff_session|manual:sendManual纯文本`
- **步骤**：
  1. 坐席发送单段纯文本
  2. 用户 WA 确认
- **预期**：
  1. 用户收到完整文本
  2. 无乱码/截断
- **层/执行**：L3 / human / P0

### TC-M7-002 — 验证人工会话中坐席发送多行文本格式可读

- **前置**：已转人工
- **输入**：多行文本
- **verify_profile**：`exec:use_handoff_session|manual:多行文本`
- **步骤**：
  1. 坐席发送含换行的多行消息
  2. 用户 WA 查看排版
- **预期**：
  1. 换行/段落可读
  2. 未合并成不可读乱码
- **层/执行**：L3 / human / P0

### TC-M7-003 — 验证人工会话中坐席连发3条消息用户均能收到

- **前置**：已转人工
- **输入**：坐席连发 3 条
- **verify_profile**：`exec:use_handoff_session|manual:连发3条`
- **步骤**：
  1. 坐席连续发送 3 条不同消息
  2. 用户确认 3 条均到达且顺序合理
- **预期**：
  1. 3 条均送达
  2. 顺序与发送一致
- **层/执行**：L3 / human / P0

### TC-M7-004 — 验证人工会话中用户再发消息时机器人不抢答且人工可继续

- **前置**：已转人工；Q02 已确认
- **输入**：用户再发消息
- **verify_profile**：`exec:handoff_then_silence|messages:再咨询一条|checks:no_bot_outbound|manual:坐席继续回复`
- **步骤**：
  1. 用户再发一条咨询
  2. 观察是否有机器人 outbound
  3. 坐席继续回复
- **预期**：
  1. 机器人不自动 FAQ 抢答
  2. 坐席仍可正常回复用户
- **层/执行**：L3 / human / P0

### TC-M7-005 — 验证人工回复送达率达到99%以上（≥20次抽样）

- **前置**：已转人工；可统计 ≥20 次坐席发送
- **输入**：≥20 次坐席发送抽样
- **verify_profile**：`exec:manual_only|manual:送达率≥20样本`
- **步骤**：
  1. 记录 ≥20 次坐席 outbound
  2. 用户在 WA 确认是否收到
  3. 计算送达率
- **预期**：
  1. 送达率 ≥99%
  2. 失败样本有 sendStatus/日志可查
- **层/执行**：L3 / human / P0

## M8（11 条）

### TC-M8-001 — 验证同一用户多轮对话 session_id 保持一致

- **前置**：已有 ≥2 轮对话样本
- **输入**：—
- **verify_profile**：`exec:webhook_multi|checks:session_stable,multi_inbound`
- **步骤**：
  1. 同一用户连续发送 2+ 条消息
  2. GET agent/session 与 Conversation
  3. 对比 session_id
- **预期**：
  1. agent/session.session_id 多轮不变
  2. 可用于日志串联
- **层/执行**：L1/L4 / agent / P0

### TC-M8-002 — 验证日志中 wa_id/phone 与用户 WhatsApp 标识一致

- **前置**：有测试对话
- **输入**：—
- **verify_profile**：`exec:webhook|messages:你好|checks:inbound_ok|manual:wa_id对照`
- **步骤**：
  1. 查 Conversation.whatsappId 与 messages
  2. 与真实 WA 号对照
- **预期**：
  1. wa_id/phone 正确
  2. 无串用户
- **层/执行**：L1/L4 / agent / P0

### TC-M8-003 — 验证 message_time/timestamp 可用于计算响应耗时

- **前置**：有 inbound+outbound 样本
- **输入**：—
- **verify_profile**：`exec:webhook|messages:Hot70 多少钱|checks:outbound≤10s,inbound_ok`
- **步骤**：
  1. 取 inbound 与下一条 outbound 的 timestamp
  2. 计算差值
- **预期**：
  1. timestamp 存在且合理
  2. 差值与体感/指标一致
- **层/执行**：L1/L4 / agent / P0

### TC-M8-004 — 验证 user_message 保存用户 inbound 原文

- **前置**：有 inbound 样本
- **输入**：—
- **verify_profile**：`exec:webhook|messages:测试关键词ABC|checks:inbound_ok`
- **步骤**：
  1. 发送含特定关键词的消息
  2. 查 messages inbound content
- **预期**：
  1. content 与用户发送原文一致（含 emoji/英文）
- **层/执行**：L1/L4 / agent / P0

### TC-M8-005 — 验证 detected_intent 记录为 task_type 且有值

- **前置**：Agent 已处理至少 1 条
- **输入**：—
- **verify_profile**：`exec:webhook|messages:Hot70 多少钱|checks:task_type`
- **步骤**：
  1. 发送 FAQ 问题
  2. 查 ChatMessage.intent 或 agent/session task_type
- **预期**：
  1. intent/task_type 非空（如 QA_ANSWER）
  2. 与路由 Agent 一致
- **层/执行**：L1/L4 / agent / P0

### TC-M8-006 — 验证 confidence 在 AgentStep 中有记录（如有）

- **前置**：有 agent steps
- **输入**：—
- **verify_profile**：`exec:webhook|messages:Hot70 多少钱|checks:task_type|manual:confidence_in_steps`
- **步骤**：
  1. GET agent/session steps
  2. 查 output_json.confidence
- **预期**：
  1. 低置信/高置信场景有 confidence 数值
  2. 低置信触发转人工策略可追踪
- **层/执行**：L1/L4 / agent / P0

### TC-M8-007 — 验证 RAG 命中可通过 tools/logs 推断

- **前置**：RAG 正常时
- **输入**：—
- **verify_profile**：`exec:webhook|messages:Hot70 多少钱|checks:rag_tool_ok`
- **步骤**：
  1. 发送 FAQ 命中问法
  2. GET agent/tools/logs 查 RagflowTool
- **预期**：
  1. RagflowTool success=true 且有 answer
  2. 未命中场景 success=false 或走 handoff
- **层/执行**：L1/L4 / agent / P0

### TC-M8-008 — 验证 bot_reply/outbound 与实际发送内容一致

- **前置**：有成功 outbound
- **输入**：—
- **verify_profile**：`exec:webhook|messages:Hot70 多少钱|checks:webhook_ok|manual:WA对照`
- **步骤**：
  1. 对比用户 WA 所见与 messages outbound content
  2. 查 bot 日志
- **预期**：
  1. 内容一致
  2. 无未发送却标记成功
- **层/执行**：L1/L4 / agent / P0

### TC-M8-009 — 验证转人工场景 handoffStatus/conversationStatus 正确

- **前置**：已触发转人工
- **输入**：—
- **verify_profile**：`exec:use_handoff_session|checks:handoff_state_m8`
- **步骤**：
  1. 转人工后查 Conversation
  2. 对照 handoff-dual-path 预期状态
- **预期**：
  1. handoff 或 external_handoff 状态正确
  2. isActiveAgent=0
- **层/执行**：L1/L4 / agent / P0

### TC-M8-010 — 验证未命中 FAQ 问题可在 audit/logs 汇总

- **前置**：有未命中/转人工样本
- **输入**：—
- **verify_profile**：`exec:webhook|messages:火星上有 Hot70 吗|checks:handoff_required|manual:audit汇总`
- **步骤**：
  1. 发送无覆盖问题
  2. 查 audit-logs 与 handoff 记录
  3. 尝试导出汇总
- **预期**：
  1. 未命中样本可检索
  2. 含 user_message 与 handoff 原因
- **层/执行**：L1/L4 / agent / P0

### TC-M8-011 — 验证 API/发送异常时服务端有 error 日志

- **前置**：可触发或已有失败样本
- **输入**：—
- **verify_profile**：`exec:manual_only|manual:error日志`
- **步骤**：
  1. 查找 sendStatus=failed 或模拟异常
  2. 查服务端 [ZHICHI_*]/error 日志
- **预期**：
  1. 有 error 级日志
  2. 含渠道/用户/失败原因
- **层/执行**：L1/L4 / agent / P0

## M9（8 条）

### TC-M9-001 — 验证用户表示已预订未提机时写入智齿标签「已预订未提机」

- **前置**：Blocked：后端未实现 PRD 五类智齿客户标签
- **输入**：我已经预订了还没提
- **verify_profile**：`exec:blocked`
- **步骤**：
  1. 用户发送：我已经预订了还没提
  2. 查智齿客户标签 API/后台
- **预期**：
  1. 智齿侧出现对应标签
  2. 标签 ID 与 Q05 配置一致（功能实现后验证）
- **层/执行**：— / both / P1

### TC-M9-002 — 验证未预订高意向咨询时写入「未预订高意向」标签

- **前置**：Blocked
- **输入**：分期怎么买
- **verify_profile**：`exec:blocked`
- **步骤**：
  1. 用户发送：分期怎么买
  2. 查智齿标签
- **预期**：
  1. 写入高意向标签
- **层/执行**：— / both / P1

### TC-M9-003 — 验证未预订低意向互动时写入「未预订低意向」标签

- **前置**：Blocked
- **输入**：只想领福利
- **verify_profile**：`exec:blocked`
- **步骤**：
  1. 用户发送：只想领福利
  2. 查智齿标签
- **预期**：
  1. 写入低意向标签
- **层/执行**：— / both / P1

### TC-M9-004 — 验证用户表示已提机时写入「已提机」标签

- **前置**：Blocked
- **输入**：我已经提机了
- **verify_profile**：`exec:blocked`
- **步骤**：
  1. 用户发送：我已经提机了
  2. 查智齿标签
- **预期**：
  1. 写入已提机标签
- **层/执行**：— / both / P1

### TC-M9-005 — 验证进线无互动时按 PRD 处理「沉默未互动」标签

- **前置**：Blocked
- **输入**：进线无消息
- **verify_profile**：`exec:blocked`
- **步骤**：
  1. 模拟进线无用户消息
  2. 查标签策略
- **预期**：
  1. 按 PRD 不强行打标或打沉默标签
- **层/执行**：— / both / P1

### TC-M9-006 — 验证普通打招呼时不强行更新客户标签

- **前置**：Blocked
- **输入**：你好
- **verify_profile**：`exec:blocked`
- **步骤**：
  1. 用户仅发送：你好
  2. 查智齿标签是否变化
- **预期**：
  1. 不更新标签或保持未识别
- **层/执行**：— / both / P1

### TC-M9-007 — 验证对话信息更明确时客户标签可更新

- **前置**：Blocked
- **输入**：先问价格后说已预订
- **verify_profile**：`exec:blocked`
- **步骤**：
  1. 先问价格再说已预订
  2. 查标签变化
- **预期**：
  1. 标签从低意向更新为已预订未提机（示例）
- **层/执行**：— / both / P1

### TC-M9-008 — 验证应打标场景标签写入成功率≥95%

- **前置**：Blocked；≥20 样本
- **输入**：应写场景抽样
- **verify_profile**：`exec:blocked`
- **步骤**：
  1. 执行应打标场景 ≥20 次
  2. 统计智齿写入成功数
- **预期**：
  1. 成功率 ≥95%
- **层/执行**：— / both / P1
