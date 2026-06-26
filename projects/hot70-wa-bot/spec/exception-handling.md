# 异常场景处理规则 — Hot70 WA Bot

> TestFactory / RegressionRunner 引用 | 与 `data/exception-scenarios.csv` 同步

## 1. 原则

| # | 原则 | 说明 |
|---|------|------|
| E1 | **不沉默** | 任何用户输入都须有可见反馈或明确转人工，禁止 silent fail |
| E2 | **不编造** | 异常/未知/动态信息不硬答，说明原因后转人工或引导重问 |
| E3 | **语气一致** | 报错/兜底用语礼貌、简短，符合 Infinix 官方客服口吻 |
| E4 | **可追踪** | 系统侧异常写 error 日志；用户侧不出现堆栈、错误码、内部字段名 |
| E5 | **转人工后静默** | Q02：已转人工后机器人不再自动回复 |

## 2. 标准提示话术（验收关键字）

运营可微调措辞，但须包含 **hint 关键词** 供 L2/L3 断言。

| 场景 code | 触发条件 | 预期动作 | 用户可见提示要点（hint） |
|-----------|----------|----------|--------------------------|
| ERR-EMPTY | 空消息 / 纯空格 | reply | 没有收到有效内容 / 请重新输入 |
| ERR-EMOJI-ONLY | 仅 Emoji、无文字 | reply | 暂未理解 / 请用文字描述 / 转人工 |
| ERR-GIBBERISH | 乱码、无意义字符 | reply | 暂未理解 / 产品、活动、预订、提机 / 转人工 |
| ERR-TOOLONG | 超长文本（>500 字） | reply | 内容较长 / 简要描述 / 转人工 |
| ERR-OFFTOPIC | 与 Hot70 无关（天气等） | handoff | 无法直接回答 / 转接人工 /  Hot70 |
| ERR-NOCOVER | FAQ 无覆盖 | handoff | 无法确认 / 转接人工 / 不编造 |
| ERR-DYNAMIC | 库存/订单/现货/特殊优惠 | handoff | 实时信息 / 人工查询 / 转接 |
| ERR-LOWCONF | 意图置信度低 | reply | 您是想了解 / 换种说法 / 转人工 |
| ERR-MIXED | 一条消息多意图冲突 | reply | 请问您想了解哪一个 / 分开咨询 |
| ERR-HANDOFF-FAIL | 转人工接口失败 | reply | 暂时无法接通 / 稍后再试 / 转人工 |
| ERR-SEND-FAIL | 智齿发消息失败 | reply | 发送遇到问题 / 稍后重试 |
| ERR-TIMEOUT | 响应超过 10s | reply | 稍等 / 繁忙 / 转人工 |
| ERR-KB-TIMEOUT | 知识库检索超时 | handoff | 暂时无法查询 / 转接人工 |
| ERR-ABUSE | 辱骂/敏感词 | handoff | 理解您的心情 / 转人工 |
| ERR-COMPETITOR | 竞品对比 | reply | 官方渠道 / Hot70 / 按运营口径 |
| ERR-AFTER-HO | 转人工后再发 | none | （机器人不回复） |
| ERR-DUP-CB | 重复回调同一 message_id | none | （不重复发送给用户） |
| ERR-SESSION-EXP | 会话超时后再进线 | reply | 欢迎回来 / Hot70 / 继续咨询 |
| ERR-API-DOWN | 机器人服务不可用 | reply | 系统维护或繁忙 / 稍后重试 |
| ERR-MEDIA | 图片/语音等非文本 | reply | 暂不支持 / 请发送文字 / 转人工 |
| ERR-SPAM | 极短时间大量重复相同内容 | reply | 已收到 / 请稍候 / 勿重复发送 |

## 3. 与规则表映射

| rule_id | 描述 |
|---------|------|
| R-ERR-001 | 空/无效输入 → ERR-EMPTY / ERR-EMOJI-ONLY |
| R-ERR-002 | 超范围/无覆盖 → ERR-OFFTOPIC / ERR-NOCOVER，不编造 |
| R-ERR-003 | 动态信息 → ERR-DYNAMIC |
| R-ERR-004 | 系统/通道异常 → ERR-SEND-FAIL / ERR-TIMEOUT / ERR-API-DOWN，有 error 日志 |
| R-ERR-005 | 低置信度/多意图 → ERR-LOWCONF / ERR-MIXED |
| R-ERR-006 | 敏感/辱骂 → ERR-ABUSE |
| R-ERR-007 | 转人工后机器人静默 → ERR-AFTER-HO（R-HO-005） |
| R-ERR-008 | 非文本消息 → ERR-MEDIA |

## 4. 语料与用例

| 资产 | 文件 | 说明 |
|------|------|------|
| 异常语料（L2） | `data/corpus-adversarial.csv` | 由 `exception-scenarios.csv` 生成 |
| 系统用例（L1/L3） | `data/test-cases-full.csv` M11 | 接口/真机异常链路 |
| 源数据 | `data/exception-scenarios.csv` | 编辑此文件后跑 build + export |

## 5. 验收方式

- **L2**：`expected_prompt_hint` 字段关键词出现在 `bot_reply` 中（允许同义改写）
- **L3**：真机目视 + 日志有 `error_code` / `handoff_flag` 等
- **禁止**：向用户展示 `500`、`null`、`groupid`、`handoff_flag` 等内部信息
