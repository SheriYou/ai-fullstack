# Hot70 WhatsApp 机器人 — 测试计划

> **版本**：V2.3 | **日期**：2026-06-30  
> **依据**：Hot70 WhatsApp Bot PRD V0.3 | **协作模式**：Agent 量产 + 人工裁决  
> **参考**：`docs/ai-activity-platform/03-reusable-test-scheme-v1.md`  
> **框架落地**：`agent-human-test/`（独立可复用，不依赖 ship-pipeline）

---

## 1. 概述

Hot70 活动引导用户进入 WhatsApp 完成咨询、预订、提机。传音机器人负责 FAQ 自动回复、预订/提机引导、转人工兜底及日志沉淀（标签写入 P1 可选）。

**本计划解决四件事**：测什么 → 怎么分层测 → Agent/人如何分工 → 何时可上线。

**不在范围**：H5 活动页本体、智齿平台底层、大规模压测、多语言扩展。

---

## 2. 测试思路

### 2.1 核心原则

| 原则 | 说明 |
|------|------|
| **规格先行** | PRD + FAQ + 话术库冻结后再写用例；未定规则 = 阻塞项 |
| **测行为不测措辞** | 断言「关键事实 + 动作（回复/转人工）」，不断言逐字一致 |
| **契约优先** | 先验消息进/出、转人工字段、日志字段，再验业务话术 |
| **Agent 量产、人工裁决** | Agent 生成语料、跑批量、出报告；人做真机 E2E 与 Go/No-Go |
| **规格缺陷单列** | FAQ 与 PRD 矛盾记 Spec Defect，不强行判 Dev Bug |

### 2.2 两条链路（为何分开测）

用户侧只有一个 WhatsApp 窗口，但存在 **两种处理模式**：

**链路 1 — 机器人接待（默认）**

```
WhatsApp 用户 → 智齿 WA API → 传音机器人 → 回复/转人工判断 → 智齿 WA API → 用户
```

- 验：意图识别、知识库命中、响应时间、转人工触发

**链路 2 — 人工接待（转人工后，Q07 ✅ LOCAL 首版）**

```
用户 → 机器人 LOCAL handoff → 传音 Web 坐席（whatsapp-bot-frontend）→ sendManual → 智齿 WA API → 用户
```

- 验：Web 登录、认领/分配、**sendManual 回传**、机器人暂停（Q02）
- **Defer**：智齿工作台 EXT 链路（external-handoff）见 `spec/handoff-dual-path.md`

### 2.3 标准执行顺序（Agent 流水线）

```
SpecMiner → TestFactory → [FAQ Review] → RegressionRunner → 人工 L3 → ReportScribe
```

阻塞项（Q01/Q02）可与 SpecMiner **并行追**，但不替代读需求写用例。详见各项目 `WORKFLOW.md`。

### 2.4 入手顺序（Hot70，Q01/Q02 已确认后）

```
① SpecMiner + TestFactory（读 PRD 写规则/用例）  ← 已执行，见 data/corpus-*.csv
② FAQ 到位 → TestFactory 增量补 faq_ref
③ 环境 G1 → 人工冒烟 G2
④ 有测试 API → RegressionRunner L2
⑤ L4 验收
```

### 2.5 人机分工概览

| Agent（约 65%） | 人工（约 35%，不可省） |
|-----------------|------------------------|
| 规则表、语料、用例 CSV | 真机 WhatsApp 冒烟 |
| L1 接口脚本、L2 批量评测 | 智齿工作台坐席操作 |
| 日志指标统计、报告草稿 | FAQ 口径签字、Go/No-Go |

---

## 3. 测试框架

### 3.1 五层测试模型（L0–L4）

| 层 | 名称 | 内容 | 执行方 | 阻塞上线 |
|----|------|------|--------|----------|
| **L0** | 规则 | PRD 规则表、FAQ 覆盖、转人工规则一致性 | Agent + 人 Review | 规则未冻结 |
| **L1** | 接口 | 智齿回调、发消息、转人工、标签 API | 脚本 / Agent | 核心接口失败 |
| **L2** | 离线逻辑 | 意图/知识库/转人工判断（不经真机） | Agent 批量语料 | 准确率不达标 |
| **L3** | E2E | 真机 WA + 工作台人工回复 | **人工** + Agent 记录 | 冒烟失败 |
| **L4** | 验收 | 核心指标、Go/No-Go 报告 | Agent 聚合 + 人签字 | 指标不达标 |

**模块 × 层级矩阵**

| 模块 | L0 | L1 | L2 | L3 | L4 |
|------|:--:|:--:|:--:|:--:|:--:|
| 消息接入 | — | ✓ | — | ✓ | ✓ |
| 意图识别 | ✓ | — | ✓ | ✓ | ✓ |
| 知识库问答 | ✓ | — | ✓ | ✓ | ✓ |
| 转人工 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 坐席分配 | — | ✓ | ✓ | ✓ | — |
| 人工回传 | — | ✓ | — | ✓ | ✓ |
| **Web 坐席 M11** | — | ✓ | — | ✓ | — |
| 日志 | — | ✓ | ✓ | ✓ | ✓ |
| 客户标签 P1 | ✓ | ✓ | ✓ | ✓ | △ |

### 3.2 质量门禁（G0–G4）

| 门禁 | 条件 | 负责人 |
|------|------|--------|
| **G0** | FAQ/话术/转人工规则冻结；Q01/Q02 已裁决 | 产品 + 运营 |
| **G1** | §8 环境 Checklist 全 ✓ | 开发 + 测试 |
| **G2** | 冒烟 TC-SMOKE-001~005 + **M11** 必过项 | 测试 |
| **G2.5** | **L2 门禁** L2-G1~G3 达标（见 §3.2.1） | Agent + 测试 |
| **G3** | P0 用例通过率 ≥95%；Open P0/P1 = 0（Fail 分类见 §9.1） | 测试 |
| **G4** | §10 指标达标或书面豁免 | 产品 + 测试 |

### 3.2.1 L2 门禁（G2.5）

| 门禁 | 条件 | 数据源 | 阻塞 |
|------|------|--------|------|
| **L2-G1** | intent 路由 Pass ≥ **60%** | `corpus-intent` → `routing_pass` | 进 L3 P0 全量 |
| **L2-G2** | kb 回复 Pass ≥ **60%** | `corpus-kb` → `business_result` | 进 L4 指标签字 |
| **L2-G3** | `should_handoff=true` Pass ≥ **70%** | `corpus-handoff` | 转人工指标解读 |

报告：`run_full_test.py` → §「L2 门禁」。Fail 须分类：`spec/l2-fail-classification.md`。

### 3.3 阶段排期（T0 = 提测日）

| 阶段 | 时间 | 内容 | 出口 |
|------|------|------|------|
| Phase 0 准备 | T0-5 ~ T0-1 | 规则冻结、Agent 产语料 | G0 + G1 |
| Phase 1 冒烟 | T0 ~ T0+1 | L3 完整链路 | G2 |
| Phase 2 接口+逻辑 | T0+1 ~ T0+4 | L1 + L2 | 离线准确率预检 |
| Phase 3 功能全量 | T0+4 ~ T0+8 | L3 P0 全量 | G3 |
| Phase 4 回归 | T0+8 ~ T0+9 | 缺陷修复回归 | — |
| Phase 5 验收 | T0+9 ~ T0+10 | L4 指标 + 报告 | G4 |

**日节奏**：上午 Agent 跑 L2 → 下午人工 L3 → 收尾更新缺陷与日报。

### 3.4 测试目标与范围

| # | 目标 | 指标 |
|---|------|------|
| T1 | 消息进入机器人 | 接入成功率 100% |
| T2 | 知识库正确回复 | 回复准确率 ≥85% |
| T3 | 正确转人工 | 转人工准确率 ≥90% |
| T4 | 人工回复回 WA | 送达率 ≥99% |
| T5 | 日志可追踪 | 未命中追踪率 100% |
| T6 | 意图路由正确 | 意图准确率 ≥90% |
| T7 | 响应及时 | 平均 ≤10s |

**P0 模块**：消息接入、意图识别、知识库、转人工（LOCAL）、**Web 坐席 M11**、人工回传（Web）、日志、转人工后机器人暂停。  
**Defer**：M6 智齿分配、M5-EXT。  
**P1 可选**：客户标签。  
**非功能**：可靠性、响应时间、iOS/Android 各 1 台、日志完整性。

---

## 4. Agent 设计

### 4.1 设计定位

Agent 是 **测试流水线中的数字执行层**，负责从规格到语料、从批量评测到报告的可重复产出；**无签字权、不替业务定口径、不操作真机 WhatsApp**。

协作范式（对齐可复用测试方案）：

```
PRD/FAQ → 规则建模 → 风险/矩阵 → 语料与用例 → L1/L2 批量执行 → 报告 → 人工 L3 验收 → Go/No-Go
```

### 4.2 Agent 编制（9 + 1 可选）

| Agent | 职责 | 本计划产出 | 阶段 |
|-------|------|------------|------|
| **SpecMiner** | PRD/FAQ → 规则表、覆盖映射 | 规则表、追溯矩阵 | Phase 0 |
| **ConflictSheriff** | 多源规格交叉对比 | G1 冲突报告 | Phase 0 |
| **RiskCartographer** | 规则 → 失效路径 | 风险地图（§9） | Phase 0 |
| **MatrixArchitect** | 模块×场景×优先级 | 测试点矩阵 | Phase 0 |
| **TestFactory** | Gold/Paraphrase/Adversarial 语料 | `corpus-*.csv` | Phase 0–1 |
| **RegressionRunner** | L1 脚本 + L2 批量跑测 | `offline-eval-*.md` | Phase 2–4 |
| **PathGuardian** | E2E 检查单、证据模板 | 附录记录表 | Phase 1–3 |
| **ReportScribe** | 指标统计、验收报告 | `metrics-*.md` | Phase 5 |
| **OpsOracle** | 上线后未命中聚类 | FAQ 补全建议 | 上线后 |
| *ship-verifier* | API 契约 + 红队（可选） | L1 接口回归 | Phase 2 |

**最小 4 件套**（资源有限时）：TestFactory + RegressionRunner + ReportScribe + Cursor 通用 Agent。

### 4.3 Agent × 阶段映射

| 阶段 | 主力 Agent | 人工 |
|------|------------|------|
| Phase 0 | SpecMiner, ConflictSheriff, MatrixArchitect, TestFactory | 冻结规则、补边界 |
| Phase 1 | PathGuardian, ReportScribe | **真机冒烟 5 条** |
| Phase 2 | RegressionRunner, ship-verifier（可选） | Review 失败样例 |
| Phase 3 | RegressionRunner, PathGuardian | **L3 E2E、坐席操作** |
| Phase 4 | RegressionRunner | 缺陷验证 |
| Phase 5 | ReportScribe | **指标签字、Go/No-Go** |

### 4.4 框架落地目录（`agent-human-test/`）

```
agent-human-test/
├── FRAMEWORK.md              # 通用 L0-L4 / G0-G4
├── agents/                   # spec-miner, test-factory, regression-runner, report-scribe
└── projects/hot70-wa-bot/    # 本项目实例
    ├── blocking.md           # G0 阻塞项
    ├── checklist-env.md      # G1
    ├── checklist-smoke.md    # G2
    ├── checklist-m11-web-agent.md  # M11 Web 坐席
    ├── data/corpus-*.csv     # TestFactory 产出
    ├── scripts/run_full_test.py  # RegressionRunner 全量 L2
    └── reports/runs/{run_id}/  # 报告归档
```

新项目：复制 `projects/_template/` 或参照 `hot70-wa-bot/` 结构。

### 4.5 Agent 首批任务（Phase 0 启动）

1. FAQ 导出 → `corpus-kb.csv`（7 类各 ≥10 条）
2. 生成 `corpus-intent.csv`（7 意图各 ≥10 条 + paraphrase）
3. 生成 `corpus-handoff.csv`（≥30 条）
4. PRD 规则表 + 完整追溯矩阵
5. L2 评测脚本骨架（CSV → 测试 API → 报告）

---

## 5. 风险地图

| ID | 失效路径 | 级 | 策略 |
|----|----------|-----|------|
| R03 | 未命中却编造答案 | 高 | L2 负向语料 + 人工抽检 |
| R04 | 动态信息硬答 | 高 | 库存/订单/现货专项 |
| R05 | 应转未转 | 高 | corpus-handoff |
| R07 | 转人工后机器人仍回复 | 高 | L3 转人工后连发 3 条 |
| R10 | 人工回复未回 WA | 高 | 每坐席 ≥1 次 L3 |
| R01/R02 | 消息进/出失败 | 中 | L1 + 接入/发送成功率 |
| R06/R08/R09 | 误转人工/字段缺失/分配错 | 中 | L1 字段断言 + 多账号 |
| R11/R12 | 日志缺失/超时 | 中 | L4 字段完整性 + 30 样本计时 |
| R13 | 标签误打 P1 | 低 | L2 标签语料 |

---

## 6. 环境与前置

| 资源 | 要求 |
|------|------|
| 智齿沙箱 | WA API、在线客服、回调指向测试环境 |
| 传音机器人测试环境 | 已部署，接口/日志文档齐全 |
| **Web 坐席前端** | `whatsapp-bot-frontend` 部署至 test-paas；坐席测试账号 |
| 代码仓库 | 后端 `whatsapp-bot-service`；前端 `whatsapp-bot-frontend` |
| WhatsApp 测试号 | ≥2 |
| 智齿工作台 | Hot70 专属技能组（传 groupid，已确认） |
| 日志平台 | 可按 session_id / wa_id 查询 |

**启动 L1+ 前 Checklist**

- [ ] PRD V0.3 + FAQ + 话术库 + 转人工规则已就绪
- [ ] Q01 ✅ 技能组 ID；Q02 ✅ 转人工后机器人不自动回复
- [ ] 回调、测试号、坐席、日志权限可用
- [ ] history_messages 的 N 值、测试探针/模拟消息方式已文档化

---

## 7. 测试用例摘要

> 编号：`TC-{模块}-{序号}` | 完整语料由 TestFactory 维护于 `corpus-*.csv`

### 7.1 冒烟（G2 必过，L3）

| ID | 步骤 | 预期 |
|----|------|------|
| TC-SMOKE-001 | 发「你好」 | 10s 内机器人回复；messages 有 inbound |
| TC-SMOKE-002 | 发「Hot70 多少钱」 | 含价格；RAG/tools 日志可观测 |
| TC-SMOKE-003-LOCAL | 发「转人工」 | **Web 本地**分配；`isActiveAgent=0`（**Q07 P0**） |
| TC-SMOKE-003-EXT | 工作台 external-handoff → 智齿 | 智齿工作台有会话；含 groupid（**Defer**，非 G2 阻塞） |
| TC-SMOKE-003b | 转人工后再发 2 条 | 无机器人自动回复（Q02） |
| TC-SMOKE-004 | **Web 坐席** ChatPanel 发回复 | 用户 WA / messages 收到（LOCAL M7） |
| TC-SMOKE-005 | 查 agent/session + messages | 见 `spec/log-field-mapping.md` |

### 7.2 模块覆盖要点

| 模块 | 关键测点 | 规模建议 | 层 |
|------|----------|----------|-----|
| **M2 消息** | 文本/英文/emoji/连发/超时/幂等 | 10 条 | L1/L3 |
| **M3 意图** | 7 类意图 + 混合/超范围/低置信 | 每类 ≥10 + paraphrase | L2 |
| **M4 知识库** | 7 类 FAQ 正向；动态信息/未命中/不编造 | 每类 ≥10 正 + 3 负 | L2/L3 |
| **M5 转人工** | **P0 LOCAL**：AI/用户触发 → Web 分配；L2 验 handoff 状态。**EXT Defer** | 16+ | L1/L2/L3 |
| **M6 坐席** | 智齿 groupid 分配 — **Defer**（Q07；须 external-handoff） | 3 条 | — |
| **M7 人工回传** | **P0 Web sendManual**；送达率 ≥20 样本；智齿回传 Defer | 5 | L3 |
| **M8 日志** | agent/session + audit-logs + tools/logs（见映射表） | 11 | L1/L4 |
| **M9 标签 P1** | 5 类智齿标签 — **Blocked**（后端未实现） | 8 | — |
| **M10 探索** | 敏感词/重复问/双端 | 5 | L3 |
| **M11 Web 坐席** | 登录、列表、claim、**sendManual**、Q02 静默；见 `checklist-m11-web-agent.md` | 6+ | L1/L3 |

**语料分工（V2.3）** — 详见 `spec/corpus-strategy.md`

| 语料 | L2 断言重点 |
|------|-------------|
| `corpus-intent` | 仅 **task_type 路由**，不断言 facts |
| `corpus-kb` | **expected_facts** 关键事实 |
| `corpus-handoff` | LOCAL **handoff**；conditional 放宽 |
| `corpus-adversarial` | 不编造 / 转人工 |

**知识库三原则（必测）**

1. FAQ 无覆盖 → 不编造，兜底 + 转人工  
2. 库存/订单/现货/特殊优惠 → 转人工  
3. 未命中 → 日志 100% 可追踪  

**意图 7 类**：产品、活动、预订、提机、门店、人工诉求、无法覆盖

---

## 8. 验收指标

| 指标 | 目标 | 样本 | 统计 |
|------|------|------|------|
| 消息接入成功率 | 100% | ≥50 | 日志 |
| 消息发送成功率 | ≥99% | ≥50 | 日志 + 真机 |
| 意图识别准确率 | ≥90% | ≥100 L2 | `corpus-intent` **routing_pass**（§8 自动化） |
| 回复准确率 | ≥85% | ≥50 | `corpus-kb` 关键事实；Fail 人工复核 |
| 转人工准确率 | ≥90% | ≥50 | `corpus-handoff`（LOCAL handoff） |
| 人工回复送达率 | ≥99% | ≥20 | **L3 M11** sendManual 记录 |
| 平均响应时间 | ≤10s | ≥30 | messages **timestamp**（L2 代理） |
| 未命中可追踪率 | 100% | 全量 | 日志汇总 |
| 标签写入成功率 P1 | ≥95% | ≥20 | 智齿后台 |

**Pass 判定（回复）**：含 expected_facts 全部关键词；无矛盾；未编造。  
**Fail 分类**：DEV_BUG / SPEC_DEFECT / HARNESS / ENV（`spec/l2-fail-classification.md`）。G3  Open P0 不含 SPEC_DEFECT。  
**上线阈值**：Open P0 = 0；P1 ≤2 且书面接受；规格缺陷需产品修订计划。

### 8.1 L2 自动化报告项

`run_full_test.py` 产出：`reports/runs/{run_id}/test-report.md`（含 PRD §7.3、§8 意图/响应时间、L2 门禁、Fail 汇总）。

---

## 9. 缺陷、回归与交付

**缺陷分级**：P0 阻塞上线（链路断/编造）→ P1 严重 → P2 一般 → P3 建议。

### 9.1 L2 Fail 分类（G3 统计口径）

| 分类 | 是否计 Open P0 |
|------|----------------|
| DEV_BUG | ✅ |
| ENV | ✅ |
| HARNESS | 视情况（脚本 fix 后重跑） |
| SPEC_DEFECT | ❌ 走 FAQ/PRD 修订 |

**回归触发**

| 变更 | 范围 |
|------|------|
| 消息/回调 | 冒烟 + M2 |
| 意图模型 | M3 全量语料 |
| FAQ/话术 | M4 受影响类 + diff |
| 转人工/分配 | M5-LOCAL + **M11** + M7 |
| 前端 ChatPanel/分配 | 冒烟 + M11 |
| 发版前 | 冒烟 + P0 + L2 快跑（`run_full_test.py`） |

**Agent 自动化回归**：每日 L2（失败 >5% 告警）；FAQ 变更 diff；发版前 `run_full_test.py`。

**交付物**

| 交付物 | 负责 | 时间 |
|--------|------|------|
| 本计划 + 规则表/语料 CSV | Agent + 测试 | T0-3 |
| 环境确认 | 开发 | T0-1 |
| 冒烟/功能/验收报告 | 测试 + ReportScribe | T0+1 / +8 / +10 |
| 未命中汇总 | TestFactory/OpsOracle | T0+10 |
| Go/No-Go 纪要 | 产品 | T0+10 |

---

## 10. 待确认项（G0 阻塞）

| ID | 问题 | 影响 | 裁决人 | 状态 |
|----|------|------|--------|------|
| Q01 | 技能组 ID 还是坐席轮询？ | M5, M6 | 产品 + 智齿 | ✅ **技能组 ID** |
| Q02 | 转人工后用户再发消息，机器人是否仍响应？ | M5, M7 | 产品 | ✅ **不自动回复** |
| Q03 | 同一会话 / 回原坐席（技能组下由智齿负责） | M6 | 产品 + 智齿 | ⬜ 首版不测传音轮询 |
| Q04 | history_messages 的 N？ | M5-EXT | 开发 | ✅ 默认 50 |
| Q05 | 5 类标签智齿 tag ID？ | M9 | 运营 | 🚫 Blocked |
| Q06 | 低置信度阈值与兜底？ | M3 | 产品 | ✅ 默认 0.65 |
| Q07 | AI 转人工：本地 vs 智齿？ | M5,M6 | 产品 | ✅ **以代码为准：LOCAL Web**；EXT/M6 Defer |

---

## 11. 附录

### A. 冒烟 Checklist

```
[ ] WA 测试号、坐席账号可用
[ ] TC-SMOKE-001 ~ 005 Pass
[ ] G2 签字：________ 日期：________
```

### B. E2E 记录表（PathGuardian 模板）

| 日期 | 测试人 | WA 号 | session_id | 输入 | 回复 | intent | hit | handoff | 耗时 | P/F |

### C. PRD → 用例追溯（节选）

| PRD | 要点 | 用例 |
|-----|------|------|
| §7.1 | 7 类意图 | M3 |
| §7.2 | 三原则 | M4-P1 |
| §7.3–7.4 | 转人工/分配 | M5, M6 |
| §7.5 | 日志 | M8 |
| §7.6 | 标签 P1 | M9 |
| §8.3 | 指标 | §8 |

---

## 修订记录

| 版本 | 日期 | 修改内容 |
|------|------|----------|
| V1.0 | 2026-06-26 | 初版 |
| V2.0 | 2026-06-26 | 增测试思路/框架/Agent 设计；精简用例明细 |
| V2.3 | 2026-06-30 | M11 Web 坐席；L2 门禁 G2.5；语料分工；Fail 分类；意图/响应时间自动化 |
| V2.2 | 2026-06-30 | Q07 LOCAL；G2/M7 P0；003-EXT/M6 Defer |
| V2.1 | 2026-06-30 | 对齐 whatsapp-bot-service：双路径转人工、L2 映射、M9 Blocked、日志字段 |

---

## 12. 实现差异与测试调整（V2.1）

依据 `whatsapp-bot-service` 源码，测试资产已同步更新：

| 差异 | 测试调整 | 文档 |
|------|----------|------|
| AI 转人工默认 **本地 Web 坐席**，非智齿 | G2/M5/M7 以 LOCAL 为 P0；003-EXT/M6 Defer | `spec/handoff-dual-path.md` |
| `ChatMessage.intent` = task_type，非 PRD 七类 | L2 用映射表断言 | `spec/intent-task-mapping.md` |
| 无 knowledge_hit / 智齿客户标签字段 | M8 改查组合 API；M9 Blocked | `spec/log-field-mapping.md` |
| L2 无专用 chat API | webhook + agent/session | `spec/api-notes.md`、`run_full_test.py` |
| 语料 intent/kb 重叠 | 分 corpus 断言 | `spec/corpus-strategy.md` |

**Q07 ✅（2026-06-30）**：首版以 **代码为准** — 用户「转人工」→ **本地 Web 坐席**；智齿 EXT / M6 为 **Defer**（见 `spec/handoff-dual-path.md`）。
