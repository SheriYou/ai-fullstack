# 转人工坐席分配 — 已确认（PRD §7.4）

**方案**：传 **技能组 ID（groupid）**，已确认（Q01）。

> ⚠️ 仅适用于 **智齿外部转人工** 路径。AI 说「转人工」默认走 **本地 Web 坐席**，见 `handoff-dual-path.md`。

## 智齿外部转人工行为

- 触发：`POST .../external-handoff` 或工作台手动外部转人工
- 传音传入 Hot70 专属 **技能组 groupid**
- **智齿**在技能组内分配坐席；传音 **不传 agentid**
- 需渠道 `providerType=ZHICHI` 且 `configJson.externalHandoffEnabled=true`

## M6 测试要点（L1/L3，external-handoff 后）

| ID | 验证 |
|----|------|
| TC-M6-A01 | 请求含正确 **groupid** |
| TC-M6-A02 | 智齿工作台可见会话 |
| TC-M6-A03 | 智齿坐席回复；用户 WA 收到 |

## 本地转人工（M5-LOCAL，AI 自动）

| ID | 验证 |
|----|------|
| TC-M5-LOCAL-001 | 用户「转人工」→ Web 工作台分配在线坐席 |
| TC-M5-LOCAL-002 | `handoffTarget=LOCAL`；`isActiveAgent=0` |

## 不测（本方案范围外）

- 传音侧 A→E 坐席轮询
- 传音维护 agentid / 接待量

## 转人工后机器人状态（Q02 已确认）

- 转人工后用户再发消息 → **机器人不自动回复**
- 必测：**TC-SMOKE-003b** / **TC-M5-010**

## 待补信息（G1）

- [ ] Hot70 技能组 **groupid** 具体值
- [ ] 测试环境 **channelKey**、webhook secret
- [ ] `historyLimit` 实测值（默认 50）
