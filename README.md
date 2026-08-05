# Agent Human Test

通用客服机器人评估引擎，当前内置 `hot70` profile。

## 目录结构

```text
agent-human-test/
├── chatbot_eval/              # 通用引擎：生成、构建、执行、日志信号、报告
├── profiles/
│   └── hot70/
│       ├── profile.json       # Hot70 数据源、路径和默认配置
│       ├── data/              # 知识库 CSV 与生成后的测试用例 CSV
│       ├── tmp/               # scenarios.json / results.jsonl
│       ├── reports/           # reports/runs/{run_id}/
│       └── config.env.example
└── run_eval.py                # Hot70 全链路便捷入口
```

## 主链路

```text
Feishu Base / local knowledge CSV
  ↓
chatbot_eval.generate_cases
  ↓
cases.csv
  ↓
chatbot_eval.build_scenarios
  ↓
scenarios.json
  ↓
chatbot_eval.run
  ↓
results.jsonl
  ↓
chatbot_eval.report
  ↓
CSV / JSON / Markdown reports
```

## 快速运行 Hot70

```powershell
copy profiles\hot70\config.env.example profiles\hot70\config.env
python run_eval.py --generate-cases --disable-llm-followup --limit-groups 3 --workers 1
```

## Agent 化入口

框架新增了一个轻量 Agent 入口：`chatbot_eval.agent`。它会把简短的人类请求解析成评测计划，
执行现有链路，并在生成报告后读取最新产物，输出本次 run 的判定分布和失败 Top N。

如果直接使用 `python -m chatbot_eval.agent`，请先进入仓库根目录：

```powershell
cd D:\CMP\agent-human-test
python -m chatbot_eval.agent "跑 P0 3组 并发1"
```

也可以安装成本地命令，之后在任意目录运行：

```powershell
python -m pip install -e D:\CMP\agent-human-test
aht-agent "跑 P0 3组 并发1"
```

```powershell
# 先只看计划，不真正发送消息
python -m chatbot_eval.agent "生成用例 跑 P0 3组 并发1 不用LLM追问" --dry-run

# 执行一次小规模冒烟评测，并生成报告摘要
python -m chatbot_eval.agent "跑 P0 3组 并发1"

# 开启 LLM 语义判定和客户标签判定
python -m chatbot_eval.agent "跑 P1 10组 并发2 LLM judge 标签判定"

# 不跑测试，只读取最近一次报告摘要
python -m chatbot_eval.agent --show-latest
```

当前自然语言解析支持：

- 阶段：`P0` / `P1` / `P2`
- 组数：`3组`、`限制 10 组`、`limit-groups 10`
- 并发：`并发1`、`workers=2`
- 用例：`生成用例`、`刷新用例`、`不用LLM追问`
- 判定：`LLM judge`、`语义判定`、`标签判定`
- 数据：`保留数据`、`不清理数据`

## 分段运行

```powershell
python -m chatbot_eval.generate_cases --source local
python -m chatbot_eval.generate_cases --source feishu
python -m chatbot_eval.generate_cases --case-type ood --ood-count 200
python -m chatbot_eval.build_scenarios
python -m chatbot_eval.run --rebuild --limit-groups 3 --workers 1 --results profiles/hot70/tmp/results.jsonl
python -m chatbot_eval.report --results profiles/hot70/tmp/results.jsonl
```

## 按需翻译测试提问

多语言翻译不是生成用例的默认步骤；只有明确需要多语言用例时单独执行。默认读取 profile 的用例 CSV，把 `测试数据（英文提问）` 字段翻译为指定语言，并输出一个新 CSV，不覆盖原文件：

```powershell
python -m chatbot_eval.translate_cases --language Hausa
```

如需指定输入/输出：

```powershell
python -m chatbot_eval.translate_cases --language Bangla --input profiles/hot70/data/Hot70_机器人_知识库指标测试.csv --output profiles/hot70/data/Hot70_机器人_知识库指标测试.bn.csv
```

## 回填表格分析

跑完评测并生成 `回填结果.csv` 后，可以用独立脚本按“人工复核优先”的口径生成报告分析材料：

```powershell
# 默认读取 profiles/hot70/reports/latest-run.json 指向的最新回填表
python scripts/analyze_backfill_report.py

# 或指定某个回填表
python scripts/analyze_backfill_report.py --input profiles/hot70/reports/runs/<run_id>/回填结果.csv
```

脚本会输出：

- `analysis.md`：可复制到测试报告的指标表、归因汇总和复核明细。
- `analysis.json`：结构化统计结果，方便后续自动处理。
- `review_items.csv`：所有指标为【否/待确认/待复核】的数据，附带基于回复内容的归因建议。

默认生成知识库用例时会纳入 `状态=已确认` 和 `状态=后续需要更新`；如需调整可使用
`--status 已确认` 或 `--status all`。执行时如果 `cases.csv` 比 `scenarios.json` 新，
或表头已变化，会自动重建 `scenarios.json`。

OOD 用例默认输出：

```text
profiles/hot70/data/Hot70_OOD_无关边界测试用例.csv
```

OOD 规则会复用测试用例模板，默认生成 200 条，包含基础用例和同会话条件追问；语料覆盖招聘、闲聊、辱骂、外链/推广、自动回复探测、竞品、医疗、金融、隐私、无意义输入等无关/边界场景，并过滤机械化表达。

飞书来源默认使用 `profiles/hot70/profile.json` 中记录的 Base 链接：

```text
https://transsioner.feishu.cn/base/FCPTbUJySadmh1sHlEZcgESLnWc?table=tbltryrzbigm3WgV&view=vewR58QybE
```
