# Agent 执行顺序（Hot70 及后续项目）

## 两层测试资产

| 资产 | 文件 | 覆盖什么 | 谁 Review |
|------|------|----------|-----------|
| FAQ 语料 | `corpus-*.csv` + `corpus-review-for-ops.md` | M3/M4 问法+预期回复 | 运营 |
| 完整用例 | `test-cases-full.csv` + `test-cases-full-review.md` | 冒烟/链路/字段/日志/指标 | 测试 |

```① SpecMiner     读 PRD/FAQ → spec/rules.md + trace-matrix.md
② TestFactory   规则 → data/corpus-*.csv（用例语料）
③ 人工 Review   运营确认口径（FAQ 到位后 diff 补全）
④ RegressionRunner  有测试 API 后跑 L2 批量
⑤ 人工 L3       真机冒烟 checklist-smoke.md
⑥ ReportScribe  指标与验收报告
```

**阻塞项（Q01/Q02 等）与 ① 可并行**，但不替代 ①②。  
**没有 FAQ 时**：SpecMiner/TestFactory 仍可基于 PRD 产 **草案用例**（`source=prd_draft`，`faq_ref=TBD`）。

## Cursor 派发示例

```
Step1: 读 agents/spec-miner.md + docs/Hot70_WhatsApp_Bot_PRD.md
       → 更新 projects/hot70-wa-bot/spec/

Step2: 读 agents/test-factory.md + spec/rules.md
       → 填充 projects/hot70-wa-bot/data/corpus-*.csv

Step3: FAQ 导出后 → 再跑 TestFactory 增量更新 faq_ref 和 expected_facts
```
