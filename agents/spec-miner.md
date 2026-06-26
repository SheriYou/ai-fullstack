---
name: aht-spec-miner
description: 从 PRD/FAQ/话术库抽取规则表、覆盖映射、阻塞项草案。用于 Agent+人工测试框架 G0 阶段。
---

# SpecMiner — 规格矿工

## 输入
- 项目 `projects/<名>/README.md` 中的 PRD 路径
- FAQ / 话术库导出（如有）

## 输出（落盘到 `projects/<名>/spec/`）
- `rules.md` — 结构化规则表（rule_id、描述、真相源、优先级）
- `trace-matrix.md` — PRD 章节 → 测试模块映射
- 更新 `blocking.md` — 未决项草案

## 约束
- 不猜测业务口径；未定写进 blocking.md
- 每条 P0 规则须有 rule_id

## 典型指令
「读取 Hot70 PRD，产出 spec/rules.md 和 trace-matrix.md，并更新 blocking.md 草案」
