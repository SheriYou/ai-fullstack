# PRD 日志字段 ↔ 后端可观测数据

> PRD §7.5 字段与 `whatsapp-bot-service` DB/API **无 1:1 对应**。M8 用例改查下列组合。

| PRD 字段 | 后端来源 | 说明 |
|----------|----------|------|
| `session_id` | `AgentSession.sessionId` | GET `agent/session/{whatsappId}` |
| `wa_id` / `phone` | `Conversation.whatsappId` | 会话表 / messages API |
| `message_time` | `ChatMessage.timestamp` | messages API |
| `user_message` | `ChatMessage.content`（inbound） | messages API |
| `detected_intent` | `ChatMessage.intent` | 存 **task_type**（如 `QA_ANSWER`），非 PRD 七类 |
| `confidence` | `AgentStep.outputJson` → `confidence` | agent/session steps |
| `knowledge_hit` | **无独立字段** | 从 `ToolCallLog`（RagflowTool）success + 有 answer 推断 |
| `bot_reply` | outbound `ChatMessage.content` | messages API |
| `customer_tag` | **P1 未实现** | 仅有会话 tags（Sales Lead 等），非智齿五类标签 |
| `handoff_flag` | `Conversation.handoffStatus` + `conversationStatus` | `handoff` / `external_handoff` |

## M8 执行方式

| 用例 | 查什么 |
|------|--------|
| TC-M8-001~004 | messages API + Conversation |
| TC-M8-005~006 | agent/session + audit-logs |
| TC-M8-007 | agent/tools/logs（RagflowTool） |
| TC-M8-008 | messages outbound vs 实际发送 |
| TC-M8-009 | Conversation handoff 字段 |
| TC-M8-010 | audit-logs + 未命中 handoff 样本汇总 |
| TC-M8-011 | 服务端 `[ZHICHI_*]` / error 日志或 failed sendStatus |
