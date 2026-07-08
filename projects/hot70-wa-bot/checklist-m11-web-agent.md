# M11 Web 坐席 — G2 / L3 Checklist

> **Q07 ✅ LOCAL** | 前端：`whatsapp-bot-frontend` | API：`spec/api-notes.md`

Web 工作台：`https://uat-paas.transsion.com/whatsapp-bot-web/`

## G2 必过（与 TC-SMOKE-003/004 对应）

| # | 操作 | 预期 | Pass |
|---|------|------|------|
| M11-1 | 坐席账号登录 Web | 进入 Dashboard / 会话列表 | ⬜ |
| M11-2 | 用户 webhook 发「转人工」后刷新列表 | 出现该 WA 会话；状态 handoff / 待认领 | ⬜ |
| M11-3 | **Claim** 认领会话 | 会话进入 ChatPanel | ⬜ |
| M11-4 | ChatPanel **发送一条文本** | `POST .../messages/send_manual` 200 | ⬜ |
| M11-5 | 查 `GET .../messages/{wa}` | 有 outbound；用户侧可见（真机或同 API） | ⬜ |
| M11-6 | 转人工后用户再发消息 | 无新的机器人 outbound（Q02） | ⬜ |

## L3 扩展（可选）

| # | 操作 | 预期 |
|---|------|------|
| M11-7 | Assign 分配给其他坐席 | 目标坐席可见会话 |
| M11-8 | Resolve 结束会话 | 状态关闭；策略允许则机器人可再接待 |
| M11-9 | SSE `/events` | 新消息实时出现在列表 |

## 记录

填写 `reports/e2e-log.csv`：`session_id`、`whatsapp_id`、耗时。

**对应用例**：TC-SMOKE-003-LOCAL、003b、004；M7-LOCAL

签字：________ 日期：________
