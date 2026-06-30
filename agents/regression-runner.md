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
2. `python scripts/run_l2_eval.py --corpus intent --limit 100`
3. POST webhook 注入语料 → GET `agent/session` 取 task_type
4. 按 `intent-task-mapping.md` 判定 Pass/Fail（非 PRD 七类字面）
5. Fail 样例 100% 人工复核

## 约束
- G1 环境 OK；建议 G2 冒烟 Pass 后再跑指标
- 失败 >5% 告警
- 不修改业务代码；只写报告

## 典型指令
「对 hot70-wa-bot 跑 corpus-intent.csv 批量评测，输出 offline-eval 报告」
