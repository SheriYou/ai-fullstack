# Hot70 完整测试用例集（Review）

> 共 **79** 条结构化用例（含 FAQ 语料引用说明）

## 两层用例体系

| 层级 | 文件 | 用途 |
|------|------|------|
| **L2 语料** | `data/corpus-*.csv`（271+ 条） | 用户问法 + 预期意图/回复/转人工；Agent 批量跑 |
| **完整用例** | `data/test-cases-full.csv`（本文） | 冒烟/链路/字段/日志/指标/异常；人工+L1/L3 执行 |

> FAQ Review 仍看 `corpus-review-for-ops.md`；系统测试看本文。

---

## L4（6 条）

| ID | 标题 | 类型 | 步骤/输入 | 预期 | 层 | 执行 |
|----|------|------|-----------|------|-----|------|
| TC-L4-001 | 消息收发成功率 | acceptance | 1. 统计指标/— | 100% | L4 | agent |
| TC-L4-002 | 回复准确率 | acceptance | 1. 统计指标/— | ≥85% | L4 | agent |
| TC-L4-003 | 转人工准确率 | acceptance | 1. 统计指标/— | ≥90% | L4 | agent |
| TC-L4-004 | 人工回复送达率 | acceptance | 1. 统计指标/— | ≥99% | L4 | agent |
| TC-L4-005 | 平均响应时间 | acceptance | 1. 统计指标/— | ≤10s | L4 | agent |
| TC-L4-006 | 未命中可追踪率 | acceptance | 1. 统计指标/— | 100% | L4 | agent |

## M1（6 条）

| ID | 标题 | 类型 | 步骤/输入 | 预期 | 层 | 执行 |
|----|------|------|-----------|------|-----|------|
| TC-SMOKE-001 | TC-SMOKE-001 | smoke | 1. WA 发消息/你好 | 10s 内机器人回复；日志有 user_message | L3 | human |
| TC-SMOKE-002 | TC-SMOKE-002 | smoke | 1. WA 发 FAQ 问法/Hot70 多少钱 | 回复含价格信息；knowledge_hit=true | L3 | human |
| TC-SMOKE-003 | TC-SMOKE-003 | smoke | 1. WA 发转人工/转人工 | handoff=true；工作台有新会话；机器人暂停 | L3 | human |
| TC-SMOKE-003b | TC-SMOKE-003b | smoke | 1. 转人工后连发 2 条/在吗 / 还有人吗 | 无机器人自动回复（Q02） | L3 | human |
| TC-SMOKE-004 | TC-SMOKE-004 | smoke | 1. 坐席在工作台回复/（坐席）您好 | 用户 WA 收到人工消息 | L3 | human |
| TC-SMOKE-005 | TC-SMOKE-005 | smoke | 1. 查 session 日志/— | session 全链路：消息/意图/转人工/回复字段齐全 | L3 | human |

## M10（5 条）

| ID | 标题 | 类型 | 步骤/输入 | 预期 | 层 | 执行 |
|----|------|------|-----------|------|-----|------|
| TC-M10-001 | 敏感词 | explore | 1. 执行/辱骂/敏感内容 | 兜底或转人工；不崩溃 | L3 | human |
| TC-M10-002 | 竞品提及 | explore | 1. 执行/竞品手机 | 按运营规则 | L3 | human |
| TC-M10-003 | 重复同一 FAQ | explore | 1. 执行/同一问题连问 2 次 | 回复一致 | L3 | human |
| TC-M10-004 | 会话超时后再发 | explore | 1. 执行/超时后发消息 | 符合 session 策略 | L3 | human |
| TC-M10-005 | iOS+Android | explore | 1. 执行/双端各测 | 消息展示正常 | L3 | human |

## M11（14 条）

| ID | 标题 | 类型 | 步骤/输入 | 预期 | 层 | 执行 |
|----|------|------|-----------|------|-----|------|
| TC-M11-001 | 空消息友好提示 | exception | 1. 执行异常场景/    | 回复含「没有收到有效内容/请重新输入」；不崩溃 | L1/L2/L3 | both |
| TC-M11-002 | 仅Emoji提示 | exception | 1. 执行异常场景/😀😀😀 | 回复含「暂未理解/请用文字/转人工」 | L1/L2/L3 | both |
| TC-M11-003 | 乱码兜底 | exception | 1. 执行异常场景/asdfghjkl123 | 回复含「暂未理解」并引导 Hot70 话题或转人工 | L1/L2/L3 | both |
| TC-M11-004 | 超范围不编造 | exception | 1. 执行异常场景/今天天气怎么样 | 不编造；转人工；回复含「无法/转接人工」 | L1/L2/L3 | both |
| TC-M11-005 | 无覆盖问题兜底 | exception | 1. 执行异常场景/火星上有 Hot70 吗 | 兜底+转人工；回复含「无法确认/转接」 | L1/L2/L3 | both |
| TC-M11-006 | 转人工失败提示 | exception | 1. 执行异常场景/（模拟转人工 API 失败） | 用户可见「暂时无法接通/稍后再试」；有 error 日志 | L1/L2/L3 | both |
| TC-M11-007 | 发消息失败提示 | exception | 1. 执行异常场景/（模拟智齿发送失败） | 用户可见「发送遇到问题/稍后重试」；有 error 日志 | L1/L2/L3 | both |
| TC-M11-008 | 响应超时提示 | exception | 1. 执行异常场景/（模拟>10s） | 用户可见「稍等/繁忙/转人工」 apology | L1/L2/L3 | both |
| TC-M11-009 | 非文本消息引导 | exception | 1. 执行异常场景/（用户发图片） | 回复含「暂不支持/请发送文字/转人工」 | L1/L2/L3 | both |
| TC-M11-010 | 辱骂转人工 | exception | 1. 执行异常场景/你是傻逼 | 礼貌回应+转人工；不崩溃 | L3 | both |
| TC-M11-011 | 多意图澄清 | exception | 1. 执行异常场景/价格多少还有门店在哪 | 回复含澄清引导「请问想了解哪一个/分开咨询」 | L1/L2/L3 | both |
| TC-M11-012 | 会话超时欢迎 | exception | 1. 执行异常场景/（超时30分钟后）Hot70 多少钱 | 回复含「欢迎回来/继续咨询」 | L3 | both |
| TC-M11-013 | 刷屏防重复 | exception | 1. 执行异常场景/3秒连发10条在吗 | 不崩溃；回复含「已收到/请稍候」 | L3 | both |
| TC-M11-014 | 不向用户暴露内部错误 | exception | 1. 执行异常场景/（触发任意 API 异常） | 用户侧无 stack/错误码/groupid；仅友好提示 | L1/L2/L3 | both |

## M2（10 条）

| ID | 标题 | 类型 | 步骤/输入 | 预期 | 层 | 执行 |
|----|------|------|-----------|------|-----|------|
| TC-M2-001 | 纯文本接入 | integration | 1. 纯文本接入/Hello | 正常处理并回复 | L1/L3 | both |
| TC-M2-002 | 英文 FAQ | integration | 1. 英文 FAQ/How to pre-order? | 正常回复或转人工 | L1/L3 | both |
| TC-M2-003 | Emoji | integration | 1. Emoji/😀👍 | 不崩溃；有回复或兜底 | L1/L3 | both |
| TC-M2-004 | 空消息 | integration | 1. 空消息/    | 兜底或提示重新输入 | L1/L3 | both |
| TC-M2-005 | 超长文本 | integration | 1. 超长文本/>500 字 | 不崩溃；合理处理 | L1/L3 | both |
| TC-M2-006 | 3 秒连发 3 条 | integration | 1. 3 秒连发 3 条/连发 3 条不同问题 | 均有处理；session 不串 | L1/L3 | both |
| TC-M2-007 | 回复送达 | integration | 1. 回复送达/任意 FAQ | 用户 WA 可见回复 | L1/L3 | both |
| TC-M2-008 | 响应时间 | integration | 1. 响应时间/30 条 FAQ 抽样计时 | 平均 ≤10s | L1/L3 | both |
| TC-M2-009 | 发消息 API 失败 | integration | 1. 发消息 API 失败/模拟智齿发送失败 | 有 error 日志；不 silent fail | L1/L3 | both |
| TC-M2-010 | 回调幂等 | integration | 1. 回调幂等/同一 message_id 回调 2 次 | 不重复回复 | L1/L3 | both |

## M4（4 条）

| ID | 标题 | 类型 | 步骤/输入 | 预期 | 层 | 执行 |
|----|------|------|-----------|------|-----|------|
| TC-M4-P1-001 | 不编造 | faq_rule | 1. 发消息/FAQ 无覆盖问题 | 兜底话术+转人工；回复含「无法确认/转接人工」；不编造 | L2/L3 | both |
| TC-M4-P1-002 | 动态信息转人工 | faq_rule | 1. 发消息/还有库存吗 | 说明需人工查实时信息；转人工；回复含「实时/转接」 | L2/L3 | both |
| TC-M4-P1-003 | 动态信息转人工2 | faq_rule | 1. 发消息/我的订单到哪了 | 说明订单需人工查询；转人工 | L2/L3 | both |
| TC-M4-P1-004 | 未命中沉淀 | faq_rule | 1. 发消息/触发未命中 | 日志可追踪可汇总 | L2/L3 | both |

## M5（7 条）

| ID | 标题 | 类型 | 步骤/输入 | 预期 | 层 | 执行 |
|----|------|------|-----------|------|-----|------|
| TC-M5-F01 | 转人工字段 partnerid/wa_id | handoff | 1. 执行场景/转人工 | 工作台用户标识正确 | L1/L3 | both |
| TC-M5-F02 | 转人工字段 最近意图 | handoff | 1. 执行场景/先问价格再转人工 | 最近意图=产品/价格 | L1/L3 | both |
| TC-M5-F03 | 转人工字段 history_messages | handoff | 1. 执行场景/多轮后转人工 | 含最近 N 轮对话 | L1/L3 | both |
| TC-M5-F04 | 转人工字段 user_name | handoff | 1. 执行场景/转人工 | 昵称合理展示 | L1/L3 | both |
| TC-M5-F05 | 转人工字段 tran_flag | handoff | 1. 执行场景/转人工 | 转人工标识正确 | L1/L3 | both |
| TC-M5-F06 | 转人工字段 params | handoff | 1. 执行场景/转人工 | 来源/摘要等扩展字段正确 | L1/L3 | both |
| TC-M5-010 | 转人工后机器人暂停 | handoff | 1. 执行场景/转人工后再发 3 条 | 均无机器人自动回复 | L1/L3 | both |

## M6（3 条）

| ID | 标题 | 类型 | 步骤/输入 | 预期 | 层 | 执行 |
|----|------|------|-----------|------|-----|------|
| TC-M6-A01 | 转人工传 groupid | integration | 1. 触发转人工 2. 检查工作台/转人工 | 请求含 Hot70 技能组 groupid | L1/L3 | human |
| TC-M6-A02 | 技能组内分配 | integration | 1. 触发转人工 2. 检查工作台/转人工 | 工作台可见会话；组内坐席可接单 | L1/L3 | human |
| TC-M6-A03 | 用户收到人工回复 | integration | 1. 触发转人工 2. 检查工作台/转人工 | 分配后坐席回复，用户 WA 收到 | L1/L3 | human |

## M7（5 条）

| ID | 标题 | 类型 | 步骤/输入 | 预期 | 层 | 执行 |
|----|------|------|-----------|------|-----|------|
| TC-M7-001 | 坐席纯文本 | integration | 坐席发纯文本/— | 用户收到 | L3 | human |
| TC-M7-002 | 坐席多行 | integration | 坐席发多行/— | 格式可读 | L3 | human |
| TC-M7-003 | 坐席连发 3 条 | integration | 坐席连发/— | 用户均收到 | L3 | human |
| TC-M7-004 | 人工期间用户再发 | integration | 用户再发消息/— | 按 Q02：机器人不抢答；人工可继续 | L3 | human |
| TC-M7-005 | 送达率统计 | integration | ≥20 次抽样/— | 送达率 ≥99% | L3 | human |

## M8（11 条）

| ID | 标题 | 类型 | 步骤/输入 | 预期 | 层 | 执行 |
|----|------|------|-----------|------|-----|------|
| TC-M8-001 | 日志字段 session_id 多轮一致 | log | 1. 查日志 2. 验 session_id 多轮一致/— | session_id 多轮一致 | L1/L4 | agent |
| TC-M8-002 | 日志字段 wa_id/phone 正确 | log | 1. 查日志 2. 验 wa_id/phone 正确/— | wa_id/phone 正确 | L1/L4 | agent |
| TC-M8-003 | 日志字段 message_time 可算耗时 | log | 1. 查日志 2. 验 message_time 可算耗时/— | message_time 可算耗时 | L1/L4 | agent |
| TC-M8-004 | 日志字段 user_message 原文 | log | 1. 查日志 2. 验 user_message 原文/— | user_message 原文 | L1/L4 | agent |
| TC-M8-005 | 日志字段 detected_intent 有值 | log | 1. 查日志 2. 验 detected_intent 有值/— | detected_intent 有值 | L1/L4 | agent |
| TC-M8-006 | 日志字段 confidence 如有则记录 | log | 1. 查日志 2. 验 confidence 如有则记录/— | confidence 如有则记录 | L1/L4 | agent |
| TC-M8-007 | 日志字段 knowledge_hit 正确 | log | 1. 查日志 2. 验 knowledge_hit 正确/— | knowledge_hit 正确 | L1/L4 | agent |
| TC-M8-008 | 日志字段 bot_reply 与发送一致 | log | 1. 查日志 2. 验 bot_reply 与发送一致/— | bot_reply 与发送一致 | L1/L4 | agent |
| TC-M8-009 | 日志字段 handoff_flag 转人工场景=true | log | 1. 查日志 2. 验 handoff_flag 转人工场景/— | handoff_flag 转人工场景=true | L1/L4 | agent |
| TC-M8-010 | 日志字段 未命中问题可汇总导出 | log | 1. 查日志 2. 验 未命中问题可汇总导出/— | 未命中问题可汇总导出 | L1/L4 | agent |
| TC-M8-011 | 日志字段 API 异常有 error 日志 | log | 1. 查日志 2. 验 API 异常有 error 日志/— | API 异常有 error 日志 | L1/L4 | agent |

## M9（8 条）

| ID | 标题 | 类型 | 步骤/输入 | 预期 | 层 | 执行 |
|----|------|------|-----------|------|-----|------|
| TC-M9-001 | 已预订未提机 | tag | 1. 发消息/我已经预订了还没提 | 智齿标签写入 | L2/L3 | both |
| TC-M9-002 | 未预订高意向 | tag | 1. 发消息/分期怎么买 | 标签写入 | L2/L3 | both |
| TC-M9-003 | 未预订低意向 | tag | 1. 发消息/只想领福利 | 标签写入 | L2/L3 | both |
| TC-M9-004 | 已提机 | tag | 1. 发消息/我已经提机了 | 标签写入 | L2/L3 | both |
| TC-M9-005 | 沉默未互动 | tag | 1. 发消息/进线无消息 | 按 PRD 处理 | L2/L3 | both |
| TC-M9-006 | 不强行打标 | tag | 1. 发消息/你好 | 不更新标签 | L2/L3 | both |
| TC-M9-007 | 标签可更新 | tag | 1. 发消息/先问价格后说已预订 | 标签更新 | L2/L3 | both |
| TC-M9-008 | 写入成功率 | tag | 1. 发消息/应写场景抽样 | ≥95% | L2/L3 | both |

---

## FAQ 语料（M3/M4）

完整 69 主问 + 271 扩展见：`corpus-review-for-ops.md` + `corpus-intent.csv`

PRD 要求但不在语料中的：**M2/M5字段/M6/M7/M8/M9/M10/验收指标** — 已在本文件系统用例中覆盖。
