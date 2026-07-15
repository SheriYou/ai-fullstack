# 指标专项报告

## 运行

```powershell
python scripts/run_kb_metrics_test.py
```

## 结果目录

每次运行写入：

```text
reports/runs/{run_id}/
```

主要产物：

- `kb-metrics-results.csv`：逐用例结果与 Trace 字段
- `kb-metrics-summary.json`：指标汇总
- `kb-metrics-report.md`：可读测试报告

指标专项以 `prd/Hot70_机器人_知识库指标测试.csv` 为唯一正式用例来源。

## 不再作为主入口的内容

旧全量报告、Formal、G2、Corpus 和 PRD 验收链路已归档到：

`archive/legacy-test-plan/`

归档内容保留用于历史复现，不应作为当前专项测试的输入或汇总来源。
