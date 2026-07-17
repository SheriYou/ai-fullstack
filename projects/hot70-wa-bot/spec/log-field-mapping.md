# test 环境日志字段映射

> 当前 Hot70 test 环境以 `wa_message_trace_log` 为日志权威来源。指标取数必须按当前入站消息的 `message_id` 关联，禁止跨消息、跨轮次读取同一会话的历史字段。

| 指标/字段 | `wa_message_trace_log` 字段 | 取值规则 |
|----------|-----------------------------|----------|
| 会话 | `session_id` | 优先按 session 查询；仅用于定位当前会话 |
| WhatsApp | `whatsapp_id` | session 查询补充/兜底条件 |
| 当前消息 | `message_id` | 必须与本次 webhook 入站消息 ID 精确匹配 |
| 意图标签 | `detected_intent` | 当前 `message_id` 日志中最新非空值 |
| 知识库命中 | `knowledge_hit` | 当前 `message_id` 日志中的 tinyint 权威值 |
| 客户标签 | `customer_tag` | 当前 `message_id` 日志中最新非空值；不在允许集合时回填 `NA` |
| 转人工标志 | `handoff_flag` | 当前 `trace_id` 日志中的 tinyint 权威值；若机器人实际回复命中 `human agent` 关键词，则回填 `日志转人工=是` |
| 转人工原因 | conversation.`handoff_reason` | 从会话接口当前 WhatsApp 会话读取；无值时留空 |
| 服务端耗时 | `latency_ms` | 当前 `message_id` 日志中的毫秒值 |
| 回复内容 | `bot_reply` | 主要用于日志核对，实际回复仍以 outbound message 为准 |
| 诊断信息 | `stage`、`status`、`tool_name`、`error_message`、`extra_json` | 保留用于追溯；失败状态不作为权威指标值 |

## 查询与过滤顺序

```text
session_id 查询 + whatsapp_id 查询
  -> 合并去重
  -> 排除 failed/error 状态
  -> 精确过滤当前 message_id
  -> 按字段分别取最新非空值
```

当前消息日志在轮询截止前未落库时，指标字段保持缺失；不得回退到前置 N、同 session 其他消息或其他 H-Cxx 的日志。
