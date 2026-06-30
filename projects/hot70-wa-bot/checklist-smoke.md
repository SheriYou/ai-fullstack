# G2 冒烟 Checklist — Hot70 WA Bot

> **Q07 ✅**：用户说「转人工」走 **本地 Web 坐席**（`whatsapp-bot-frontend`）。3c 智齿路径 **非 G2 阻塞**。

人工 + webhook 模拟或真机 WA + Web 工作台。下列 **1–5、3a、3b、4** 全 Pass = G2 通过。

| # | 操作 | 预期 | Pass |
|---|------|------|------|
| 1 | 发「你好」 | 10s 内机器人回复 | ⬜ |
| 2 | 发「Hot70 多少钱」 | 含价格；RAG/回复可观测（见 log-field-mapping） | ⬜ |
| 3a | 发「转人工」（**LOCAL，Q07**） | Web 工作台有新会话/分配；`isActiveAgent=0` | ⬜ |
| 3b | 转人工后再发 2 条 | **无机器人自动回复**（Q02） | ⬜ |
| 3c | ~~外部转人工（智齿）~~ | **Defer** — 下迭代 / 智齿专项 | — |
| 4 | Web 坐席 ChatPanel **发一条回复** | 用户 WA（或 webhook 侧 messages）收到 | ⬜ |
| 5 | 查 agent/session + messages | session_id、task_type、handoff 状态可追踪 | ⬜ |

**对应用例**：TC-SMOKE-001~005、003-LOCAL、003b（003-EXT Defer）

**记录**：填写 `reports/e2e-log.csv`

签字：________ 日期：________
