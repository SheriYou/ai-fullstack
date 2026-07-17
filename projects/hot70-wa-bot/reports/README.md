# 指标专项报告

## 运行

```powershell
python scripts/run_kb_metrics_test.py --batch-index 1
```

## 结果目录

每次运行写入：

```text
reports/
```

主要产物：

- `cases-results.jsonl`：逐条追加的本地结果与 Trace 字段
- `batches/batch-*.json`：批次状态
- 聚合产物：`aggregated-results.csv`、`aggregated-results.json`、`aggregated-report.md`

指标专项以 `prd/Hot70_机器人_知识库指标测试.csv` 为唯一正式用例来源。

## 不再作为主入口的内容

旧全量报告、Formal、G2、Corpus 和 PRD 验收链路已归档到：

`archive/legacy-test-plan/`

归档内容保留用于历史复现，不应作为当前专项测试的输入或汇总来源。
