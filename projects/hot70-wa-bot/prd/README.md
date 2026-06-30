# 规格材料目录（真相源）

| 文件 | 用途 |
|------|------|
| `Hot70_WhatsApp_Bot_Test_Plan.docx` / `.md` | 测试计划 V2.1（由 `.md` 生成 docx） |
| `Hot70_WhatsApp_Bot_PRD.docx` / `.md` | 最新 PRD |
| `Hot70_all_test_cases.csv` | 平台导入用例（526 条，见 `data/`） |
| `Hot70_Script.xlsx` | **FAQ 知识库**（sheet: FAQ知识库） |

> 说明：FAQ 与话术已合并入 `Hot70_Script.xlsx`；若后续增加「话术库」sheet，构建脚本会自动识别。

## 材料刷新

```powershell
cd agent-human-test/projects/hot70-wa-bot
python scripts/inspect_prd_sources.py
python scripts/build_corpus_from_prd.py
```

产物：`data/faq-export/sources.json`、`data/corpus-*.csv`、`data/faq-export/build-summary.json`
