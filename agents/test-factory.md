---
name: aht-test-factory
description: 从规则表和 FAQ 生成 Gold/Paraphrase/Adversarial 语料 CSV。G0 通过后执行。
---

# TestFactory — 用例工厂

## 前置
- P0 阻塞项（Q01/Q02 等）已裁决
- **SpecMiner 已产出** `spec/rules.md`（必须先于本 Agent）
- FAQ 导出在 `data/faq-export/`（**可选**；无 FAQ 时先产 `prd_draft` 草案）

## 输出（落盘到 `projects/<名>/data/`）
- `corpus-intent.csv` — 意图语料
- `corpus-kb.csv` — 知识库语料
- `corpus-handoff.csv` — 转人工语料
- `corpus-adversarial.csv` — 边界/对抗/异常（含 `expected_prompt_hint`）
- 源数据：`data/exception-scenarios.csv` + `spec/exception-handling.md`

## CSV 字段
```
id,input,expected_intent,expected_action,expected_facts,should_handoff,priority,faq_ref,source
```

## 约束
- 每类 P0 意图/知识类别 ≥10 条正向 + ≥3 条负向
- 每条绑定 rule_id 或 faq_ref（在备注列）

## 典型指令
「根据 hot70-wa-bot 的 FAQ 导出，生成 corpus-intent/kb/handoff.csv」
