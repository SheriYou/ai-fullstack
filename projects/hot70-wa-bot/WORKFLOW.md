# Agent 执行顺序（Hot70 及后续项目）

## 两层测试资产

| 资产 | 文件 | 覆盖什么 | 谁 Review |
|------|------|----------|-----------|
| 知识库指标用例 | `prd/Hot70_机器人_知识库指标测试.csv` | L2 知识命中/转人工专项 | 测试 |
| 完整用例 | `test-cases-full.csv` + `test-cases-full-review.md` | 冒烟/链路/字段/日志/指标/异常 | 测试 |
| 实现映射 | `spec/intent-task-mapping.md`、`log-field-mapping.md`、`handoff-dual-path.md` | L2 断言与 PRD 差异 | 测试+开发 |
| 语料分工 | `spec/corpus-strategy.md` | intent 路由 vs kb 事实 | 测试 |
| Fail 分类 | `spec/l2-fail-classification.md` | L2 Fail 归因 | 测试 |
| 接口探针 | `spec/api-notes.md` | L1/L2 webhook 与 debug API | 开发 |

```
① SpecMiner     PRD + 后端/前端代码 → rules / trace / handoff-dual-path
② TestFactory   规则 → `Hot70_机器人_知识库指标测试.csv`（L2 专项）
③ 人工 Review   运营确认 FAQ 口径
④ RegressionRunner  python scripts/run_full_test.py
   - **Formal 82 条**：按 `verify_profile` 逐条断言（`test_case_runner.py`）
   - **L2 专项**：`python scripts/run_kb_metrics_test.py`
⑤ 人工 L3       checklist-smoke.md + checklist-m11-web-agent.md
⑥ ReportScribe  reports/runs/{run_id}/（md + docx + csv）
```

**铁律**：
- L2 **intent 只验路由**，**kb 只验 facts**（`spec/corpus-strategy.md`）
- **Q07 ✅**：用户「转人工」→ **LOCAL Web**；M6 / 003-EXT **Defer**
- L2 未过 **G2.5 门禁** 不推进 L3 全量 / L4 签字
- Fail 必须带 **fail_class**（DEV_BUG / SPEC_DEFECT / HARNESS / ENV）
- M9 **Blocked** 直至智齿客户标签功能开发

## L2 执行前提

1. G1 checklist 全 ✓
2. `config.env` 填写 `BOT_TEST_API_URL`、`BOT_CHANNEL_KEY`
3. G2 冒烟 Pass 后再解读 L2 指标

## 代码仓库

| 组件 | 路径 |
|------|------|
| 后端 | `whatsapp-bot-service` |
| 前端 Web 坐席 | `whatsapp-bot-frontend` |
| 测试框架 | `agent-human-test/projects/hot70-wa-bot/` |

## Cursor 派发示例

```
Step1: 读 spec/handoff-dual-path.md + spec/corpus-strategy.md
Step2: G1 checklist-env.md
Step3: python scripts/run_full_test.py
Step3b: python scripts/run_kb_metrics_test.py
Step4: 看报告 L2 门禁 + Fail 分类 → 人工 L3 checklist-m11-web-agent.md
```
