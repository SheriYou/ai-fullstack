---
name: aht-regression-runner
description: 跑 L1 接口脚本与 L2 离线语料批量评测，输出通过率报告。
---

# RegressionRunner — 回归跑者

## 输入
- `projects/<名>/data/corpus-*.csv`
- 测试 API 地址（`projects/<名>/config.env` 或环境变量）
- L1：`scripts/api_*.py`

## 输出
- `reports/offline-eval-YYYYMMDD.md` — L2 通过率、失败清单
- `reports/api-YYYYMMDD.md` — L1 结果（如有）

## L2 流程
1. 读 CSV → 调机器人测试接口（或 mock）
2. 对比 expected_intent / expected_action / expected_facts
3. 统计准确率，列出 Fail 样例供人工复核

## 约束
- 失败 >5% 告警
- 不修改业务代码；只写报告和回归 check

## 典型指令
「对 hot70-wa-bot 跑 corpus-intent.csv 批量评测，输出 offline-eval 报告」
