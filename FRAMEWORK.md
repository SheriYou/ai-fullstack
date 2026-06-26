# Agent + 人工 测试框架 — 通用流程

> 任意新项目复用本文件；项目差异只体现在 `projects/<名>/` 下的语料与配置。

## 1. 五层测试（L0–L4）

| 层 | 测什么 | Agent | 人工 |
|----|--------|-------|------|
| L0 | 规则表、FAQ 覆盖、多源一致性 | SpecMiner, ConflictSheriff | 冻结规则、签字 |
| L1 | 外部 API 回调/调用 | RegressionRunner | Review 契约 |
| L2 | 离线逻辑批量（语料 CSV） | RegressionRunner | 复核 Fail 样例 |
| L3 | 真机/真实环境 E2E | PathGuardian（模板） | **必做** |
| L4 | 指标 + Go/No-Go | ReportScribe | **签字** |

## 2. 门禁（G0–G4）

| 门禁 | 通过条件 |
|------|----------|
| G0 | 阻塞项清零、FAQ/规则就绪 |
| G1 | 环境 Checklist 全 ✓ |
| G2 | 冒烟全 Pass |
| G3 | P0 通过率 ≥95%，Open P0/P1 = 0 |
| G4 | 指标达标或书面豁免 |

## 3. Agent 编制（最小 4 件套）

| Agent | 输入 | 输出 |
|-------|------|------|
| **SpecMiner** | PRD、FAQ | `spec/rules.md`、追溯矩阵 |
| **TestFactory** | 规则表、FAQ | `data/corpus-*.csv` |
| **RegressionRunner** | 语料 CSV、测试 API | `reports/offline-eval-*.md` |
| **ReportScribe** | 日志、执行结果 | `reports/metrics-*.md`、验收报告 |

扩展（按需）：ConflictSheriff、PathGuardian、OpsOracle。

## 4. 阶段顺序

```
G0 阻塞+规则 → G1 环境 → G2 冒烟(L3) → L1/L2 批量 → L3 全量 → 回归 → G4 验收
```

**铁律**：规格未冻结不产语料；链路未冒烟不跑 L2 指标；Agent 无签字权。

## 5. 项目目录约定

```
projects/<名>/
├── README.md           # 本项目说明、文档链接
├── blocking.md         # 阻塞项跟踪（G0）
├── checklist-env.md    # 环境 Checklist（G1）
├── spec/rules.md       # 规则表（SpecMiner 产出）
├── data/corpus-*.csv   # 语料（TestFactory 产出）
├── scripts/            # L1/L2 脚本
└── reports/            # 报告输出
```
