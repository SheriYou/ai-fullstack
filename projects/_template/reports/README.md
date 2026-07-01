# reports/ 目录说明

## 入库（Git）

| 类型 | 示例 | 是否 push |
|------|------|-----------|
| 说明文档 | `README.md`、`*-review.md` | ✓ |
| L3 人工记录模板 | `e2e-log.csv` | ✓ |
| **执行产出物** | `runs/`、`test-run-*`、`test-results-*` | ✗ |

框架根 `.gitignore` 已配置：`git push` 时**只传代码与规格**，测试 run 结果留在本地。

## 本地产出

每次执行归档在 `runs/{run_id}/`；根目录保留 `-latest` 与 `test-run-{run_id}.*` 副本便于搜索。

清理：`python ../../../scripts/daily_cleanup.py --project <项目名>`
