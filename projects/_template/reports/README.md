# reports/ 目录说明

## 入库（Git）

| 类型 | 示例 | 是否 push |
|------|------|-----------|
| 说明文档 | `README.md`、`*-review.md` | ✓ |
| L3 人工记录模板 | `e2e-log.csv` | ✓ |
| **执行产出物** | `runs/{run_id}/` 下全部文件 | ✗ |
| **根目录指针** | `latest-run.json` | ✗（本地，gitignore） |

每次执行仅写入 `reports/runs/{run_id}/`；`daily_cleanup.py` 按保留期清理过期 run。
