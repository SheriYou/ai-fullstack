---
name: aht-regression-runner
description: 跑 L1 接口脚本与 L2 离线语料批量评测，输出通过率报告。
---

# RegressionRunner — 回归跑者

## 输入
- `projects/<名>/data/corpus-*.csv`
- `projects/<名>/config.env` — `BOT_TEST_API_URL`、`BOT_CHANNEL_KEY`（L2 webhook）
- `spec/intent-task-mapping.md` — L2 断言映射（Hot70 必用）
- L1：`spec/api-notes.md`

## 输出
- `reports/offline-eval-*.md` — L2 通过率、失败清单
- `reports/api-YYYYMMDD.md` — L1 结果（如有）

## L2 流程（Hot70）
1. 配置 `config.env`（见 `config.env.example`）
2. **推荐** `python scripts/run_full_test.py`（G2 冒烟 + 全量 L2 + 报告归档）
3. POST webhook 注入语料 **用户问句**（`input` 列）→ 轮询 `Conversation` + `messages`
4. **转人工**：断言 `handoffTarget=LOCAL` + `isActiveAgent=0`（见 `scripts/case_executor.py`），**不能**仅用 outbound 英文兜底判定 Pass
5. **冒烟**：001/002 独立会话；003-LOCAL 后再跑 003b（同会话）
6. Fail 样例人工复核 + `fail_class`

## 约束
- G1 环境 OK；建议 G2 冒烟 Pass 后再跑指标
- 失败 >5% 告警
- 不修改业务代码；只写报告

## 典型指令
「对 hot70-wa-bot 跑 corpus-intent.csv 批量评测，输出 offline-eval 报告」
