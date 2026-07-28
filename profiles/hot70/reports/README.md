# Reports

执行报告只保留在本地，不提交运行产物。

```text
reports/
├── README.md
├── latest-run.json          # gitignored
└── runs/{run_id}/           # gitignored
    ├── 回填结果.csv
    ├── summary.json
    └── report.md
```

生成方式：

```powershell
python run_eval.py --generate-cases --disable-llm-followup --limit-groups 3 --workers 1
```
