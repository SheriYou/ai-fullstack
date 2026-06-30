# PRD → 测试追溯矩阵

| PRD | 规则 | 模块 | 测试资产 | 备注 |
|-----|------|------|----------|------|
| §5.1 消息链路 | R-MSG-* | M2 | webhook + L3 | `spec/api-notes.md` |
| §7.1 意图 | R-INT-* | M3 | `corpus-intent.csv` | L2 断言见 `intent-task-mapping.md` |
| §7.2 知识库 | R-KB-* | M4 | `corpus-kb.csv` + TC-M4-P1-* | RAG 命中见 tools/logs |
| §7.3 转人工 | R-HO-001~002, R-HO-LOCAL | M5 | `corpus-handoff.csv` + M5-* | **Q07：默认 LOCAL** |
| §7.4 技能组 | R-HO-004~006, R-HO-EXT | M6 | TC-M6-* | **Defer**；须 external-handoff |
| §7.4 转人工后暂停 | R-HO-005 | M5 | TC-SMOKE-003b, TC-M5-010 | |
| §5.1 人工回传 | R-CS-001 | M7 | L3 Web sendManual | 智齿回传 Defer |
| §7.5 日志 | R-LOG-001 | M8 | TC-M8-* | 见 `log-field-mapping.md` |
| §7.6 标签 | R-TAG-001 | M9 | TC-M9-* | **Blocked** 后端未实现 |
| §8.3 指标 | — | L4 | TC-L4-* | 意图指标=路由+动作正确率 |

## 后端代码对照

| 能力 | 代码位置 | 测试层 |
|------|----------|--------|
| Webhook 入站 | `ChannelMessageServiceImpl.receiveInbound` | L1/L2 |
| Agent 路由 | `SupervisorAgent` | L2 |
| 本地转人工 | `AgentAssignmentServiceImpl` | L3 |
| 智齿转人工 | `HumanHandoffServiceImpl` | L1/L3 |
| Agent 调试 | `GET .../agent/session/{wid}` | L2/L4 |
