# G0 阻塞项 — Hot70 WA Bot

> G0 通过条件：P0 阻塞全部 ✅ 后，才可全量 L3 与 G4 验收。L2 语料批量可在 G1 就绪后启动。

| ID | 问题 | 影响 | 负责人 | 状态 | 结论 |
|----|------|------|--------|------|------|
| Q01 | 转人工：技能组 ID 还是坐席轮询？ | M5-EXT, M6 | 产品+智齿 | ✅ 已确认 | **传技能组 ID**；智齿技能组内分配；传音不传 agentid |
| Q02 | 转人工后用户再发消息，机器人还自动回吗？ | M5, M7 | 产品 | ✅ 已确认 | **不再自动回复**（`isActiveAgent=0` 或 `external_handoff`） |
| Q03 | 同一会话 / 回原坐席？ | M6 | 产品+智齿 | ⬜ 待确认 | 智齿内部分配；首版不测传音轮询 |
| Q04 | history_messages 的 N？ | M5-EXT | 开发 | ✅ 代码已确认 | 渠道 `historyLimit` **默认 50**，上限 500；G1 记录测试环境实际值 |
| Q05 | 5 类标签智齿 tag ID？ | M9 | 运营 | 🚫 **Blocked** | 后端 **未实现** PRD 智齿客户标签；M9 整模块豁免至功能开发 |
| Q06 | 低置信度阈值与兜底？ | M3 | 产品 | ✅ 代码已确认 | `minConfidenceForAutoReply` **默认 0.65**；低于阈值 → 转人工；G1 核验环境配置 |
| Q07 | AI 自动转人工走本地还是智齿？ | M5, M6, G2 | 产品 | ✅ **已确认** | **以代码为准**：用户说「转人工」→ **本地 Web 坐席**（`handoffTarget=LOCAL`）；智齿 EXT 仅 **external-handoff API**，**非 G2/G4 阻塞** |

## 材料清单（G0 同步追）

| 材料 | 负责人 | 状态 | 存放位置 |
|------|--------|------|----------|
| FAQ + 话术 | 运营 | ✅ | `prd/Hot70_Script.xlsx` |
| 最新 PRD | 产品 | ✅ | `prd/Hot70_WhatsApp_Bot_PRD.md` |
| 转人工双路径说明 | 测试 | ✅ | `spec/handoff-dual-path.md` |
| 接口与测试探针 | 开发+测试 | ✅ | `spec/api-notes.md` |
| 意图/日志字段映射 | 测试 | ✅ | `spec/intent-task-mapping.md`、`spec/log-field-mapping.md` |
| 测试环境 Web/API | 开发 | ⬜ G1 | `checklist-env.md` |

**当前**：Q07 已确认。G2/G4 以 **LOCAL 路径** 为准（003-LOCAL、003b、Web 坐席回消息）；**TC-SMOKE-003-EXT / M6 / M5-F\*** 标记 **Defer**（下迭代或专项联调智齿时再测）。
