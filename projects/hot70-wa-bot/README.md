# Hot70 指标专项测试

当前项目聚焦一条独立链路：

> 基于知识库生成用例 → 执行用例 → 读取 Trace / 会话结果 → 判定指标 → 生成测试报告

## 主数据源

- 测试用例：`prd/Hot70_机器人_知识库指标测试.csv`
- FAQ / 知识库源：`prd/Hot 70 FAQ知识库_FAQ知识库_全部FAQ.csv`
- 运行配置：`config.env.example`

指标专项 CSV 是本链路的唯一正式用例输入，不依赖旧 Formal、Corpus 或全量测试计划用例。

## 主入口

```powershell
python scripts/run_kb_metrics_test.py --batch-index 1
```

该入口负责：

1. 从指标专项 CSV 读取标准问答和多轮追问用例；
2. 按用例链规则执行 webhook / session / messages 流程；
3. 读取 Trace 中的 `detected_intent`、`knowledge_hit`、`customer_tag`、`handoff_flag`、`latency_ms`；
4. 校验回复事实、LOCAL 转人工和多轮会话结果；
5. 每次固定执行一个最多 10 条用例的批次，逐条持久化结果；全部批次完成后单独聚合。

## 核心指标

- 知识库命中率
- 回复准确率
- 转人工准确率
- 客户标签准确率
- 服务端真实耗时

## 公共能力

指标专项继续复用以下基础能力：

- API Client 与环境配置
- webhook、session、messages、conversation 查询
- 轮询与会话状态解析
- LOCAL handoff 校验
- Trace 日志读取
- 运行目录和结果归档
- LLM 配置与可选辅助判定

对应实现目前仍位于 `scripts/` 中，后续可进一步抽取到公共模块，但不改变专项入口。

## 输出

结果分层写入 `reports/`，执行脚本只负责一个批次：

- `cases-results.jsonl`：逐条追加的本地执行结果
- `batches/batch-*.json`：批次状态
- 聚合产物：`aggregated-results.csv`、`aggregated-results.json`、`aggregated-report.md`

## 归档内容

旧 Formal / G2 / Corpus / PRD 全量测试链路已移动到：

`archive/legacy-test-plan/`

归档内容暂不删除，待确认无需历史复现后再清理。
