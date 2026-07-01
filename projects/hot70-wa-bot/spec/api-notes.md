# 接口与测试探针 — Hot70 WA Bot

> 依据 `whatsapp-bot-service` 源码整理 | G1 环境核验时对照填写

## 测试环境

| 项 | 值 |
|----|-----|
| Web 工作台 | `https://test-paas.transsion.com/whatsapp-bot-web/` |
| 后端 API 前缀 | `https://test-paas.transsion.com/whatsapp-bot-service/api` |
| 登录 | `POST /api/auth/login` → Cookie `WA_SESSION` |

## 入站消息（L1 / L2 模拟用户）

| 用途 | 方法 | 路径 |
|------|------|------|
| 入站（**test-paas 可用**） | POST | `/api/webhook/{channelKey}` |
| 入站（代码新版，test-paas 404） | POST | `/api/webhook/channels/{channelKey}/messages` |

**LocalGateway 请求体**（`ch_wa_01` 默认渠道）：

```json
{
  "whatsapp_id": "8613800000001@s.whatsapp.net",
  "content": "你好",
  "message_id": "test-unique-id",
  "direction": "inbound"
}
```

**说明**：L2 RegressionRunner 通过 webhook 注入用户消息，无需真机 WA。需记录测试环境的 `channelKey` 与 `webhookSecret`。

## 智齿人工回传（L1 / L3）

| 用途 | 方法 | 路径 |
|------|------|------|
| 坐席消息推送 | POST | `/api/webhook/channels/{channelKey}/agent-messages` |
| 消息状态 | POST | `/api/webhook/channels/{channelKey}/statuses` |

## 转人工

| 路径 | 触发方 | 目标 |
|------|--------|------|
| **AI 自动**（`shouldHandoff=true`） | AgentRuntime | **Web 本地坐席**（`handoffTarget=LOCAL`） |
| **外部转人工** | `POST /api/business-lines/{id}/conversations/{wid}/external-handoff` | **智齿**（需渠道 `providerType=ZHICHI` 且 `externalHandoffEnabled=true`） |

**智齿转人工请求字段**（`ExternalHandoffRequest`）：`groupId`、`agentId`（可选，首版不传）、`reason`、`includeHistory`、`historyLimit`

**history_messages N**（Q04）：渠道配置 `historyLimit`，**默认 50**，上限 500。

## 调试与日志（替代 PRD 单表日志）

| 用途 | 方法 | 路径 |
|------|------|------|
| Agent 决策 | GET | `/api/business-lines/{id}/agent/session/{whatsappId}` |
| LLM 审计 | GET | `/api/business-lines/{id}/audit-logs` |
| Tool 调用（含 RAG） | GET | `/api/business-lines/{id}/agent/tools/logs?whatsapp_id=` |
| 会话消息 | GET | `/api/business-lines/{id}/messages/{whatsappId}` |
| 技能组列表 | GET | `/api/business-lines/{id}/channels/{channelKey}/skill-groups` |

字段映射见 `spec/log-field-mapping.md`。

## 配置项（G1 需记录）

| 配置 | 位置 | 默认值 / 说明 |
|------|------|----------------|
| `minConfidenceForAutoReply` | `wa_bot_config` | **0.65**（Q06） |
| `humanHandoffMode` | `wa_bot_config` | `LOCAL_ONLY`（**仅存库，运行时不读**） |
| `externalHandoffEnabled` | 渠道 `configJson` | 智齿外部转人工开关 |
| `defaultGroupId` | 渠道 `configJson` | Hot70 技能组 groupid |
| `historyLimit` | 渠道 `configJson` | 默认 50 |

## L2 批量评测约定

1. POST webhook 注入 `corpus-*.csv` 的 `input`
2. 等待 Agent 处理（轮询 session 或固定 sleep）
3. GET `agent/session` + `messages` + `tools/logs`
4. 断言：**LOCAL 转人工**查 `Conversation.handoffTarget=LOCAL` + `isActiveAgent=0`（**非** outbound 英文兜底文案）；FAQ 查 facts / 路由。见 `scripts/case_executor.py`

脚本：`scripts/run_l2_eval.py`（需 `config.env` 中 `BOT_TEST_API_URL`）
