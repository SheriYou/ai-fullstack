# L2 语料分工策略

> TestFactory 产出 | 对齐测试计划 V2.3

## 四套语料，各测各的（避免重复 Fail）

| 文件 | 测什么 | 不断言什么 | L2 Pass 判定 |
|------|--------|------------|--------------|
| `corpus-intent.csv` | **task_type 路由** + handoff 动作 | `expected_facts` 关键词 | `routing_pass=PASS` |
| `corpus-kb.csv` | **expected_facts** 关键事实 | 七类 intent 字面 | `business_result=PASS`（facts 匹配） |
| `corpus-handoff.csv` | **转人工触发**（Q07 LOCAL） | FAQ 全文 | `true` 必 handoff；`false` 必不转；`conditional` 转或答均可 |
| `corpus-adversarial.csv` | 超范围/负向/不编造 | — | handoff 或合理兜底 |

**不要**用同一问法在 intent + kb 上双重判 Fail：intent Fail = 路由错；kb Fail = 内容错。

## 规模建议（当前）

| 语料 | 条数 | 备注 |
|------|------|------|
| intent | ~408 | 含 paraphrase |
| kb | ~408 | 与 intent 同 FAQ 不同断言 |
| handoff | ~58 | 建议扩至 ≥80，补 `must_not` |
| adversarial | ~36 | |

## 字段对照

| intent | kb | handoff |
|--------|-----|---------|
| `expected_intent` | `category` (PROD/ACT/…) | `expected_action` |
| `expected_action` | — | `should_handoff` |
| `should_handoff` | `should_handoff` | `reason` |

## 脚本实现

`scripts/l2_eval_core.py` → `eval_row_by_corpus()`  
`scripts/run_full_test.py` → 全量 L2
