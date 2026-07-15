# Hot70 指标专项规则

当前主链路只维护知识库指标专项：

- 用例来源：`prd/Hot70_机器人_知识库指标测试.csv`
- 知识库事实来源：`prd/Hot 70 FAQ知识库_FAQ知识库_全部FAQ.csv`
- 执行入口：`scripts/run_kb_metrics_test.py`
- 用例生成：`scripts/generate_kb_metrics_cases.py`
- 转人工路径：首版以 LOCAL Web 坐席为准
- 日志权威字段：`detected_intent`、`knowledge_hit`、`customer_tag`、`handoff_flag`、`latency_ms`

旧 Formal、G2、Corpus、异常场景和 PRD 全量规则已归档到 `archive/legacy-test-plan/`。

## 文档规则落地

- 用例 ID 按 `TC-H70-xxx-N` 与 `TC-H70-xxx-H-Cxx` 识别；H-Cxx 不允许独立执行。
- 每个 H-Cxx 执行时先执行同 base 的 N，再在同一 `whatsapp_id` 会话中追问，并使用 H-Cxx 作为 `sender_name`。
- Webhook 网络错误、连接错误、超时和 5xx 最多重试 3 次；轮询使用截止时间，不允许无限等待。
- `knowledge_hit`、`handoff_flag`、`customer_tag`、`latency_ms` 优先使用 trace 日志字段；日志字段缺失时保留现有回退逻辑。
- 文档中标注为“具体取值待定”的 LLM 转人工兜底判断、以及需要人工复核的回复语义判断暂不改变。
