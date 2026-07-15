# Hot70 指标专项 API 说明

## 主链路接口

专项执行通过公共 API Client 使用：

- webhook 注入测试消息；
- agent/session 查询；
- messages 查询；
- conversation 状态查询；
- Trace 日志查询。

具体字段映射见 `spec/log-field-mapping.md`，LOCAL handoff 判定见 `spec/handoff-dual-path.md`。

## 数据源

专项只读取 `prd/Hot70_机器人_知识库指标测试.csv` 作为执行用例输入，不读取旧 `corpus-*.csv` 或旧 Formal 用例表。
