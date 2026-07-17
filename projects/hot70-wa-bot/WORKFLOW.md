# Hot70 指标专项工作流

## 主链路

```text
FAQ / 知识库
  -> scripts/generate_kb_metrics_cases.py
  -> prd/Hot70_机器人_知识库指标测试.csv
  -> scripts/run_kb_metrics_test.py
  -> Trace / session / messages / conversation
  -> 指标判定与测试报告
```

## 生成用例

```powershell
python scripts/generate_kb_metrics_cases.py
```

默认从 `prd/Hot 70 FAQ知识库_FAQ知识库_全部FAQ.csv` 生成专项用例，仅处理 `状态=已确认` 的 FAQ。

生成后校验：

```powershell
python scripts/validate_kb_metrics_cases.py
```

## 执行与报告

```powershell
python scripts/run_kb_metrics_test.py --batch-index 1
```

每次执行一个固定最多 10 条的批次，结果逐条写入 `reports/cases-results.jsonl`，批次状态写入 `reports/batches/`。成功完成后删除临时过程文件；框架错误立即停止并保留已执行结果。全部批次完成后运行 `python scripts/aggregate_kb_metrics_results.py` 聚合。

## 公共能力

专项复用 API Client、环境配置、webhook、session/messages/conversation 查询、轮询、LOCAL handoff 校验、Trace 读取和运行归档能力。

## 归档

旧 Formal、G2、Corpus、PRD 全量测试链路位于 `archive/legacy-test-plan/`，不作为当前专项测试输入或主入口。确认无需历史复现后再删除。
