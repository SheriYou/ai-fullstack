# Data

保留两类文件：

- `Hot 70 FAQ知识库_FAQ知识库_全部FAQ.csv`：知识库 FAQ 原始输入。
- `Hot70_机器人_知识库指标测试.csv`：由 `python -m chatbot_eval.generate_cases` 生成的测试用例 CSV。
- `Hot70_OOD_无关边界测试用例.csv`：由 `python -m chatbot_eval.generate_cases --case-type ood --ood-count 200` 生成的无关/边界测试用例 CSV。
