# PRD 意图 ↔ 后端 task_type 映射

> PRD §7.1 七类意图与 `whatsapp-bot-service` 实际路由 **不对齐**。L2 不得直接用 `corpus-intent.csv` 的 `expected_intent` 对比 `ChatMessage.intent`。

## 后端实际产出

`SupervisorAgent` 路由到专家 Agent，`ChatMessage.intent` / `AgentResult.taskType` 典型值：

| task_type | 路由 Agent | 典型触发 |
|-----------|------------|----------|
| `QA_ANSWER` | QaAnswerAgent | FAQ / 知识库问法 |
| `SALES_GUIDE` | SalesGuideAgent | 价格、推荐、购买 |
| `HUMAN_HANDOFF` | HumanHandoffAgent | 人工/投诉/退款关键词 |
| `SUPPORT` | SupportAgent | 保修、订单、售后 |
| `INVENTORY` | InventoryAgent | 库存、现货 |
| `PRODUCT_RESEARCH` | ProductResearchAgent | 排行、最新 |
| `CHITCHAT` | ChitchatAgent | 寒暄、短句 |
| `LOW_CONFIDENCE` | — | 置信度 < minConfidenceForAutoReply |

## FAQ 语料类别 → 期望 task_type（L2 断言）

| corpus `expected_intent` / category | 期望 task_type（宽松） | 备注 |
|-------------------------------------|------------------------|------|
| 产品信息 / PROD | `QA_ANSWER` 或 `SALES_GUIDE` | 含价格时可能走 Sales |
| 活动规则 / ACT | `QA_ANSWER` | |
| 活动权益 / BEN | `QA_ANSWER` | |
| 提机相关 / PICK | `QA_ANSWER` | |
| 门店信息 / STORE | `QA_ANSWER` | |
| 官方身份 / OFF | `QA_ANSWER` | |
| 人工兜底 / HANDOFF | `HUMAN_HANDOFF` 或 handoff=true | |
| 无法覆盖（adversarial） | handoff=true 或 `HUMAN_HANDOFF` | |
| 动态信息（库存/订单） | `INVENTORY`/`SUPPORT` + handoff=true | |

## L2 Pass 判定（修订）

1. **路由**：`agent/session` 中 `task_type` 落在映射表允许集合
2. **转人工**：`should_handoff` / `conversationStatus` 符合语料 `should_handoff`
3. **回复**：outbound 消息含 `expected_facts` 关键词（允许同义改写）
4. **禁止**：未命中时编造事实

## 指标说明

测试计划「意图准确率 ≥90%」在本项目指 **路由+动作正确率**（task_type 映射 + handoff 判定），不是 PRD 七类字面一致。
