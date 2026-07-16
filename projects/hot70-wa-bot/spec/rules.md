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

## 待确认规则

- `customer_tag` 日志值按确认规则仅接受：`已预订未提机`、`未预订高意向`、`已提机`；其他值填 `NA`。LLM 推测标签仍使用规则规定的五类值域。
- FAQ 文本匹配规则未定义最低关键词命中数/相似度阈值。当前实现由 LLM 选择 FAQ，再按 `业务反馈` 英文词集合与实际回复的词交集大于 0 判定答复匹配。

- 旧的用例文档 CSV 已删除，当前以新生成的字段结构为准。
