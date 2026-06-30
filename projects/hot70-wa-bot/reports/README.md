# 测试报告目录

## 目录结构

每次测试的全部产出物归档在 **`runs/{run_id}/`**：

```
reports/
├── latest-run.json              # 指向最新一轮
├── test-results-latest.csv      # 最新结构化结果（副本）
├── test-results-corpus-latest.csv
└── runs/
    └── 20260630-135252/
        ├── manifest.json        # 产出物清单
        ├── test-report.md       # Markdown 报告
        ├── test-report.docx     # Word 报告
        ├── summary.json         # 机器可读汇总（含 prd_7_3）
        ├── test-results.csv     # 82 条结构化用例
        └── test-results-corpus.csv
```

根目录仍保留 `test-run-{run_id}.*` 副本，便于按文件名搜索。

## 常用命令

```bash
# 全量测试（自动归档 + 生成 Word）
python scripts/run_full_test.py

# 将已有产出物迁入 runs/ 并补 Word
python scripts/bundle_run.py 20260630-135252

# 刷新 PRD §7.3 指标并重新生成 Word
python scripts/refresh_prd73_report.py

# 单独 Markdown → Word
python scripts/report_docx.py reports/runs/20260630-135252/test-report.md
```

## 产出物自动清理

框架级脚本 `agent-human-test/scripts/daily_cleanup.py` 会删除超过保留期的 run 目录及根目录副本（默认 7 天，至少保留最近 1 轮）。同一天内重复执行会自动跳过。

```bash
# 在项目根或框架根执行
python ../../../scripts/daily_cleanup.py --project hot70-wa-bot --dry-run
```

## 结果字段说明

| 字段 | 含义 |
|------|------|
| `execution_status` | `EXECUTED` 已跑 / `NOT_RUN` 未跑 / `BLOCKED` 功能未实现 |
| `automation_result` | 接口层：webhook/API 是否可达 |
| `business_result` | 业务层：是否符合用例预期（**验收以此为准**） |
| `whatsapp_id` / `session_id` | 测试 WA 标识 / 会话 ID（日志追溯） |
| `routing_pass` | intent 语料：task_type 路由是否正确 |
| `fail_class` | DEV_BUG / SPEC_DEFECT / HARNESS / ENV（见 `spec/l2-fail-classification.md`） |
| `response_ms` | inbound→首条 outbound 毫秒（L2 代理响应时间） |

## 报告章节（V2.3）

| 章节 | 内容 |
|------|------|
| PRD §7.3 | 五项核心指标 |
| 测试计划 §8 | 意图路由准确率 |
| L2 门禁 | L2-G1~G3（G2.5） |
| Fail 分类汇总 | DEV_BUG / ENV / … |

## PRD §7.3 与语料分工

| 指标 | 目标 | L2 统计 |
|------|------|---------|
| 回复准确率 | ≥85% | **corpus-kb** `business_result` |
| 意图路由 | ≥90% | **corpus-intent** `routing_pass` |
| 转人工 | ≥90% | **corpus-handoff**（LOCAL） |
| 平均响应时间 | ≤10s | `response_ms` 字段 |

## 静态参考文档（非单次 run 产出）

| 文件 | 内容 |
|------|------|
| `test-cases-full-review.md` | 全量用例审阅 |
| `corpus-review-for-ops.md` | 语料运营审阅 |
| `e2e-log.csv` | L3 真机人工记录模板 |
