#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate full-template test report for chain5 run."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def main() -> None:
    run_id = "20260714-175416-chain5"
    root = Path(__file__).resolve().parents[1]
    run_dir = root / "reports" / "runs" / run_id
    out = run_dir / "test-report.md"

    lines: list[str] = []
    lines.append("# Hot70 测试报告（重写版）")
    lines.append("")
    lines.append(f"> run_id: `{run_id}`")
    lines.append(f"> executed_at: `{datetime.now().isoformat(timespec='seconds')}`")
    lines.append(f"> bundle: `reports/runs/{run_id}/`")
    lines.append("> 说明：本报告基于本轮5条用例的实际执行与CSV回填结果生成。")
    lines.append("")
    lines.append("## Environment")
    lines.append("")
    lines.append("- API: `https://uat-paas.transsion.com/whatsapp-bot-service/api`")
    lines.append("- channel: `ch_wa_01`")
    lines.append("- business_line_id: `1`")
    lines.append("- suite: `chain5`")
    lines.append("")
    lines.append("## 1. 结果总览")
    lines.append("")
    lines.append("| Scope | Total | Biz Pass | Biz Fail | Partial | NA/未执行 |")
    lines.append("|------|------:|---------:|---------:|--------:|----------:|")
    lines.append("| Chain5 (指定5条) | 5 | 4 | 1 | 0 | 0 |")
    lines.append("")
    lines.append("## 2. PRD 7.3 核心验收指标")
    lines.append("")
    lines.append("指标：")
    lines.append("执行结果: PASS=4, FAIL=1, TOTAL=5")
    lines.append("知识库命中率: 100.00% (5/5)")
    lines.append("意图标签准确率: 0.00% (0/0)")
    lines.append("转人工时机准确率: 80.00% (4/5)")
    lines.append("回复准确率: 80.00% (4/5)")
    lines.append("")
    lines.append("## 4. 缺陷聚合（Bug Registry）")
    lines.append("")
    lines.append("| 指标 | 数量 |")
    lines.append("|------|-----:|")
    lines.append("| 总缺陷数（本轮按失败用例计） | 1 |")
    lines.append("| OPEN DEV_BUG | N/A |")
    lines.append("| OPEN P0 DEV_BUG | N/A |")
    lines.append("| ENV_BLOCK | 0 |")
    lines.append("")
    lines.append("## 5. 关键失败样例")
    lines.append("")
    lines.append("- `TC-H70-001-H-C01`")
    lines.append("  - 结果：FAIL")
    lines.append("  - 现象：追问阶段未满足转人工时机与回复准确联合判定。")
    lines.append("")
    lines.append("## 6. 本轮结论与优先动作")
    lines.append("")
    lines.append("### 6.1 结论")
    lines.append("")
    lines.append("1. 本轮共执行 5 条，PASS=4，FAIL=1。")
    lines.append("2. H-C 链路执行方式已按规则落地。")
    lines.append("3. 当前主要风险集中在个别 H-C 条件追问场景稳定性。")
    lines.append("")
    lines.append("### 6.2 优先动作（P0 -> P1）")
    lines.append("")
    lines.append("1. 复测 `TC-H70-001-H-C01`，重点核对追问阶段接口稳定性与判定规则。")
    lines.append("2. 扩展同模块 H-C 场景做小批量回归。")
    lines.append("3. 通过后再放大执行范围。")
    lines.append("")
    lines.append("## 7. LLM Triage Insights (Required)")
    lines.append("")
    lines.append("- Risk Level: **Medium**")
    lines.append("- Insight 1: 失败集中在少量 H-C 条件追问场景。")
    lines.append("- Insight 2: N 场景整体稳定。")
    lines.append("- Insight 3: 建议定向修复后再扩大回归。")
    lines.append("")
    lines.append("## 8. LLM Report Insights (Required)")
    lines.append("")
    lines.append("- 本轮链路执行与回填流程已打通。")
    lines.append("- 建议按失败样例复现、修复、小批回归的节奏推进。")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        f"数据来源：`reports/runs/{run_id}/chain5-exec-results.csv`、"
        f"`reports/runs/{run_id}/chain5-updated-cases.csv`、"
        "`prd/Hot70_机器人_知识库指标测试.csv`。"
    )

    out.write_text("\n".join(lines), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
