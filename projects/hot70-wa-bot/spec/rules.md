# 规则表 — Hot70 WA Bot

> SpecMiner 产出 | 依据 PRD V0.3 + 后端实现对照（`whatsapp-bot-service`）| 更新 2026-06-30

| rule_id | 描述 | 真相源 | P | 验证层 |
|---------|------|--------|---|--------|
| R-MSG-001 | 用户 WA 消息经智齿同步至传音机器人 | PRD §5.1 | P0 | L1/L3 |
| R-MSG-002 | 机器人回复经智齿回到用户 WA | PRD §5.1 | P0 | L3 |
| R-MSG-003 | 平均响应时间 ≤10s | PRD §8.3 | P0 | L3/L4 |
| R-INT-001 | 用户问题路由到合适 Agent（task_type） | PRD §7.1 + 后端 | P0 | L2 |
| R-INT-002 | 超范围问题不编造，兜底+转人工 | PRD §7.1 | P0 | L2 |
| R-KB-001 | 只基于已确认 FAQ/RAG 回复，不编造 | PRD §7.2 | P0 | L2 |
| R-KB-002 | 库存/订单/现货/特殊优惠 → 转人工 | PRD §7.2 | P0 | L2 |
| R-KB-003 | 未命中问题可追踪（audit/tools 日志） | PRD §7.2 | P0 | L4 |
| R-KB-PROD | 商品：SKU/价格/配置/颜色/内存等 | FAQ P0 | P0 | L2 |
| R-KB-ACT | 活动：时间/入口/参与/预订流程 | FAQ P0 | P0 | L2 |
| R-KB-BEN | 权益：福利/券/领取方式 | FAQ P0 | P0 | L2 |
| R-KB-PICK | 提机：时间/门店/凭证/流程 | FAQ P0 | P0 | L2 |
| R-KB-STORE | 门店：城市/地址/营业时间 | FAQ P0 | P0 | L2 |
| R-KB-OFF | 官方身份/正品/购买渠道 | FAQ P0 | P0 | L2 |
| R-HO-001 | 用户明确要求人工 → **LOCAL Web** 转人工 | Q07 + 后端 | P0 | L2/L3 |
| R-HO-002 | 未命中知识库 → 兜底+转人工 | PRD §7.3 | P0 | L2 |
| R-HO-003 | 智齿推送：用户标识、意图、history_messages | PRD §7.3 | P2 | L1 — **Defer**（EXT 专项） |
| R-HO-004 | 智齿转人工传 **groupid** | Q01 | P2 | L1/L3 — **Defer** |
| R-HO-005 | 转人工后用户再发消息，**机器人不自动回复** | Q02 | P0 | L3 |
| R-HO-006 | 智齿技能组内分配；传音不传 agentid | Q01 | P2 | L3 — **Defer** |
| R-HO-LOCAL | AI/用户触发 → **Web 本地坐席**分配 | Q07 + 后端 | P0 | L2/L3 |
| R-HO-EXT | 智齿 external-handoff API | 后端实现 | P2 | L1/L3 — **Defer** |
| R-CS-001 | **Web 坐席**回复回到用户 WA | Q07 + 前端 | P0 | L3 |
| R-LOG-001 | 可观测：session/intent/confidence/RAG/handoff | PRD §7.5 + 映射表 | P0 | L4 |
| R-TAG-001 | 5 类智齿客户标签（P1） | PRD §7.6 | P1 | — **Blocked** |
| R-ERR-001 | 空/无效/非文本输入 → 友好提示重问，不崩溃 | exception-handling §2 | P0 | L2/L3 |
| R-ERR-002 | 超范围/无覆盖 → 不编造，兜底话术+转人工 | exception-handling §2 | P0 | L2 |
| R-ERR-003 | 库存/订单/现货/特殊优惠 → 说明后转人工 | exception-handling §2 | P0 | L2 |
| R-ERR-004 | 通道/超时/API 异常 → 用户可见 apology + error 日志 | exception-handling §2 | P0 | L1/L3 |
| R-ERR-005 | 低置信度/多意图 → 澄清或转人工（阈值 0.65） | Q06 + exception-handling | P0 | L2 |
| R-ERR-006 | 辱骂/竞品/信任质疑 → 按运营口径，必要时转人工 | exception-handling §2 | P1 | L2/L3 |
| R-ERR-007 | 转人工后机器人静默（同 R-HO-005） | Q02 | P0 | L3 |
| R-ERR-008 | 图片/语音等非文本 → 引导发文字 | exception-handling §2 | P1 | L3 |

**L2 断言**：意图/转人工见 `spec/intent-task-mapping.md`；日志见 `spec/log-field-mapping.md`；转人工路径见 `spec/handoff-dual-path.md`。

**异常场景**：`spec/exception-handling.md` + `data/exception-scenarios.csv`（36 条）。

**FAQ 状态**：运营 Review 见 `reports/corpus-review-for-ops.md`；口径变更后重新 build 语料。
