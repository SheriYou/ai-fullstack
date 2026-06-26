# 规则表 — Hot70 WA Bot

> SpecMiner 产出 | 依据 PRD V0.3 + 已确认 Q01/Q02 | FAQ 到位后增量更新

| rule_id | 描述 | 真相源 | P | 验证层 |
|---------|------|--------|---|--------|
| R-MSG-001 | 用户 WA 消息经智齿同步至传音机器人 | PRD §5.1 | P0 | L1/L3 |
| R-MSG-002 | 机器人回复经智齿回到用户 WA | PRD §5.1 | P0 | L3 |
| R-MSG-003 | 平均响应时间 ≤10s | PRD §8.3 | P0 | L3/L4 |
| R-INT-001 | 识别 7 类意图：产品/活动/预订/提机/门店/人工/无法覆盖 | PRD §7.1 | P0 | L2 |
| R-INT-002 | 超范围问题不编造，兜底+转人工 | PRD §7.1 | P0 | L2 |
| R-KB-001 | 只基于已确认 FAQ 回复，不编造 | PRD §7.2 | P0 | L2 |
| R-KB-002 | 库存/订单/现货/特殊优惠 → 转人工 | PRD §7.2 | P0 | L2 |
| R-KB-003 | 未命中问题记录日志可汇总 | PRD §7.2 | P0 | L4 |
| R-KB-PROD | 商品：SKU/价格/配置/颜色/内存等 | FAQ P0 | P0 | L2 |
| R-KB-ACT | 活动：时间/入口/参与/预订流程 | FAQ P0 | P0 | L2 |
| R-KB-BEN | 权益：福利/券/领取方式 | FAQ P0 | P0 | L2 |
| R-KB-PICK | 提机：时间/门店/凭证/流程 | FAQ P0 | P0 | L2 |
| R-KB-STORE | 门店：城市/地址/营业时间 | FAQ P0 | P0 | L2 |
| R-KB-OFF | 官方身份/正品/购买渠道 | FAQ P0 | P0 | L2 |
| R-HO-001 | 用户明确要求人工 → 转人工 | PRD §7.3 | P0 | L2/L3 |
| R-HO-002 | 未命中知识库 → 兜底+转人工 | PRD §7.3 | P0 | L2 |
| R-HO-003 | 推送：用户标识、最近意图、history_messages | PRD §7.3 | P0 | L1 |
| R-HO-004 | 转人工传 **groupid**（技能组） | Q01 已确认 | P0 | L1/L3 |
| R-HO-005 | 转人工后用户再发消息，**机器人不自动回复** | Q02 已确认 | P0 | L3 |
| R-HO-006 | 智齿技能组内分配坐席；传音不传 agentid | Q01 | P0 | L3 |
| R-CS-001 | 坐席回复回到用户 WA | PRD §5.1 | P0 | L3 |
| R-LOG-001 | 日志含 session_id/wa_id/intent/knowledge_hit/handoff 等 | PRD §7.5 | P0 | L4 |
| R-TAG-001 | 5 类标签明确表达才写入（P1） | PRD §7.6 | P1 | L2 |

**FAQ 已接入**（`prd/FAQ_knowledge_base.xlsx`，7 条，状态均为「待确认」— 运营签字前语料可跑但口径未冻结）。
