# PRD → 测试追溯矩阵

| PRD | 规则 | 模块 | 语料文件 |
|-----|------|------|----------|
| §5.1 消息链路 | R-MSG-* | M2 | — |
| §7.1 意图 | R-INT-* | M3 | corpus-intent.csv |
| §7.2 知识库 | R-KB-* | M4 | corpus-kb.csv |
| §7.3 转人工 | R-HO-001~003 | M5 | corpus-handoff.csv |
| §7.4 技能组 | R-HO-004~006 | M6 | checklist-smoke + handoff-allocation |
| §7.4 转人工后暂停 | R-HO-005 | M5 | corpus-handoff.csv |
| §5.1 人工回传 | R-CS-001 | M7 | checklist-smoke |
| §7.5 日志 | R-LOG-001 | M8 | — |
| §7.6 标签 | R-TAG-001 | M9 | corpus-tags.csv（P1） |
| §8.3 指标 | — | L4 | ReportScribe |
