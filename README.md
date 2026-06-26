# Agent + 人工 测试框架

独立于 ship-pipeline 的轻量测试框架，适用于 **外部集成型需求**（WhatsApp Bot、第三方 API、运营内容驱动等）。

## 结构

```
agent-human-test/
├── FRAMEWORK.md          # 通用流程（L0-L4、G0-G4、Agent 编制）
├── agents/               # 可复用 Agent 角色定义（Cursor 子 Agent / Prompt）
├── templates/            # 跨项目模板
├── lib/                  # 共享脚本
└── projects/<项目>/      # 各需求实例（语料、报告、阻塞项）
```

## 新项目接入（10 分钟）

1. 复制 `projects/_template/` → `projects/<新项目名>/`
2. 填 `blocking.md`、`README.md`
3. 按 `FRAMEWORK.md` 跑 G0 → G1 → 冒烟 → L2
4. 在 Cursor 中 `@agents/test-factory.md` 等派发任务

## 当前项目

| 项目 | 路径 | 测试计划 |
|------|------|----------|
| Hot70 WhatsApp Bot | `projects/hot70-wa-bot/` | `docs/Hot70_WhatsApp_Bot_Test_Plan.md` |
