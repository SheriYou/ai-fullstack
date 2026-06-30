# L2 Fail 分类

> 报告字段 `fail_class` | 人工复核时更新

| 分类 | 含义 | 典型信号 | 处理 |
|------|------|----------|------|
| **DEV_BUG** | 实现/模型/RAG/路由问题 | no outbound、task_type 错、应转未转 | 提缺陷给开发 |
| **SPEC_DEFECT** | FAQ/PRD/语料口径矛盾 | 运营确认 expected_facts 有误 | 改语料或 FAQ，不计 Dev |
| **HARNESS** | 脚本/等待/断言过严 | wait 不足、conditional 判错 | 改脚本或语料标签 |
| **ENV** | 环境不可用 | RAG 404、登录失败、webhook 5xx | 修环境后重跑 |
| **—** | Pass | — | — |
| **NA** | Skip | 不可模拟输入 | — |

## 自动化规则（`l2_eval_core.classify_fail`）

1. `automation_result=FAIL` → ENV 或 HARNESS  
2. webhook OK + 业务 Fail → 默认 DEV_BUG  
3. 人工 Review 可将 DEV_BUG 改为 SPEC_DEFECT / HARNESS（写入缺陷单）

## 报告中的使用

- `test-results-corpus.csv` 列 `fail_class`
- 测试报告 §「L2 Fail 分类汇总」
- **G3 门禁**：Open P0 仅计 DEV_BUG + ENV（不含 SPEC_DEFECT）
