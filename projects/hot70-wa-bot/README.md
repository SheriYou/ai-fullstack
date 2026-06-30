# Hot70 WhatsApp Bot — 测试项目

| 项 | 路径 |
|----|------|
| 测试计划 | `prd/Hot70_WhatsApp_Bot_Test_Plan.md` |
| PRD / FAQ（真相源） | `prd/` |
| 框架说明 | `../../FRAMEWORK.md` |
| 后端实现 | `../../../whatsapp-bot-service` |
| 前端 Web 坐席 | `../../../whatsapp-bot-frontend` |
| 测试环境 Web | https://test-paas.transsion.com/whatsapp-bot-web/ |

## 当前阶段

**Phase 2 L2 已跑通脚本；G2/G2.5 待人工 L3+M11**

- **Q07 ✅**：转人工 → 本地 Web 坐席（`spec/handoff-dual-path.md`）
- L2 全量：`python scripts/run_full_test.py`
- L3 坐席：`checklist-m11-web-agent.md`

## 目录

```
hot70-wa-bot/
├── blocking.md              ← G0 阻塞项（含 Q07 双路径）
├── checklist-env.md         ← G1
├── checklist-smoke.md       ← G2
├── checklist-m11-web-agent.md ← M11 Web 坐席（Q07 LOCAL）
├── spec/
│   ├── handoff-dual-path.md ← Q07 LOCAL 首版
│   ├── corpus-strategy.md   ← intent/kb 分工
│   ├── l2-fail-classification.md
│   ├── api-notes.md         ← webhook / debug API
│   ├── intent-task-mapping.md
│   └── log-field-mapping.md
├── data/corpus-*.csv
├── scripts/run_l2_eval.py   ← L2 批量
└── reports/
```

## 关键差异（必读）

1. AI 自动转人工 → **Web 本地坐席**；智齿 → **external-handoff API**
2. L2 意图断言用 **task_type 映射**，非 PRD 七类字面
3. M9 智齿客户标签 **未实现**，整模块 Blocked
