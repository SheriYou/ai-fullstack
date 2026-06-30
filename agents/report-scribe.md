---
name: aht-report-scribe
description: 聚合日志与执行结果，产出指标表、验收报告、测试日报草稿。
---

# ReportScribe — 报告书记官

## 输入
- `reports/offline-eval-*.md`
- 人工 L3 E2E 记录（`reports/e2e-log.csv`）
- 日志查询结果（session_id 样本）

## 输出
- `reports/runs/{run_id}/` — 单次测试全部产出物（md、docx、csv、summary、manifest）
- 报告含：**PRD §7.3**、**§8 意图/响应时间**、**L2 门禁 G2.5**、**Fail 分类汇总**
- `reports/latest-run.json` — 指向最新一轮
- `reports/metrics-YYYYMMDD.md` — 对照测试计划 §8 指标
- `reports/acceptance-draft.md` — 验收报告草稿
- `reports/daily-YYYYMMDD.md` — 日报
- 全量/冒烟报告中的 **PRD §7.3 核心验收指标** 段（由 `scripts/prd_acceptance_metrics.py` 聚合）

## 约束
- 指标须注明样本量与统计方式
- PRD §7.3 五项须与 `prd/Hot70_WhatsApp_Bot_PRD.md` 定义一致；L2 可算项标注为代理指标
- Go/No-Go 建议供人签字，Agent 不代签

## 典型指令
「汇总 hot70-wa-bot 本周 L2+L3 结果，生成 metrics 报告和 acceptance 草稿」
