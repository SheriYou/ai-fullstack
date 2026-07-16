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
python scripts/run_kb_metrics_test.py
```

专项结果写入 `reports/runs/{run_id}/`，包括逐用例 CSV、汇总 JSON 和 Markdown 报告。

## 公共能力

专项复用 API Client、环境配置、webhook、session/messages/conversation 查询、轮询、LOCAL handoff 校验、Trace 读取和运行归档能力。

## 归档

旧 Formal、G2、Corpus、PRD 全量测试链路位于 `archive/legacy-test-plan/`，不作为当前专项测试输入或主入口。确认无需历史复现后再删除。
