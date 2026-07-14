---
name: aht-test-factory
description: 从规则表和 FAQ 生成 Gold/Paraphrase/Adversarial 语料 CSV。G0 通过后执行。
---

# TestFactory — 用例工厂

## 前置
- P0 阻塞项（Q01/Q02 等）已裁决
- **SpecMiner 已产出** `spec/rules.md`（必须先于本 Agent）
- FAQ 导出在 `data/faq-export/`（**可选**；无 FAQ 时先产 `prd_draft` 草案）
- 写用例前先执行源数据校验：
`python projects/hot70-wa-bot/scripts/validate_faq_source_for_case_writer.py`

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

## Hot70 知识库指标用例规程（L2 专项）

### 适用范围
- 目标表：`projects/hot70-wa-bot/prd/Hot70_机器人_知识库指标测试.csv`
- 源知识库：`projects/hot70-wa-bot/prd/Hot 70 FAQ知识库_FAQ知识库_全部FAQ.csv`
- 执行脚本：`projects/hot70-wa-bot/scripts/run_kb_metrics_test.py`

### 用例族结构
- 每个 base 用例以 `TC-H70-xxx` 编号。
- 标准问答用例：`TC-H70-xxx-N`（单轮、标准咨询）。
- 条件式转人工用例：`TC-H70-xxx-H-C01/C02/...`（同会话追问、命中触发条件后转人工）。
- `H-Cxx` 必须从属于同 base 的 `-N`，不可独立存在。

### FAQ -> 用例字段映射
- `用户问题` -> `用例名称`中的主问题、`测试数据`（中文）。
- `问题（英文）` -> `测试数据（英文提问）`（优先用于自动执行输入）。
- `分类` -> `用例名称`中的`[分类]`前缀。
- `回复中文翻译`（缺失时回退`业务反馈`）-> `预期结果`中的核心事实点。
- `是否需要转人工` + `转人工条件/备注` -> `转人工预期`、`转人工触发条件`、`H-Cxx`追问场景。

### 转人工语义（强约束）
- 当 FAQ 的 `是否需要转人工=视情况` 时，`转人工条件（英文）`/`转人工条件/备注`中列出的场景一旦命中，**必须转人工**。
- 因此 `视情况` 不是“随机二选一”，而是“条件触发型转人工”。
- `转人工条件` 字段只是触发说明/原因说明，**不得**用于反推 `是否需要转人工=视情况`（即：不是“条件非空 => 视情况”）。
- 在用例落地上：
`-N`（标准问法、未触发条件）应设为不转人工；
`-H-Cxx`（命中条件场景）应设为转人工。

### 编写规则
1. `-N` 用例
- 标题格式：`[分类] <主问题>【标准问答场景】`。
- `转人工预期`：
`否` = 标准场景不应转人工；
`是` = 该问题本身应直接转人工；
`待确认` = 仅用于暂未固化规则的临时过渡状态，默认不建议新增。
- `预期结果`必须可提取事实点（供命中判定），并包含验收描述（不编造、信息完整）。

2. `-H-Cxx` 用例
- 标题格式：`[分类] <主问题>【条件式转人工场景：<触发条件>】`。
- `前置条件`必须写明：先执行对应 `-N`，并保持同一 WhatsApp 会话。
- `转人工预期`固定为`是`。
- `预期结果`聚焦行为断言：识别上下文 + 触发人工 + 不继续输出确定性业务结论。

### 执行器兼容约束（必须满足）
- 不得缺失：`用例ID`、`用例名称`、`测试数据`、`测试数据（英文提问）`、`转人工预期`、`预期结果`。
- `转人工预期`值域：`是/否/待确认`。
- 结果回填列（`执行结果`、`知识库是否命中`、`意图标签是否准确`等）在编写阶段保持空白，由执行脚本回填。

### 质量闸门（写完即检）
- 结构完整：每个 `H-Cxx` 都能追溯到同 base 的 `-N`。
- 语义一致：`H-Cxx` 的“场景词”应来自 FAQ 的 `转人工条件/备注`或其同义改写。
- 可执行性：`执行步骤`可在真实会话中逐条操作，无歧义动作。
- 可判定性：`预期结果`可被脚本判定（事实命中或 handoff 命中），避免纯主观描述。
