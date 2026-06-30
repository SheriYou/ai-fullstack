#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge test-cases-full.csv with execution results -> reports/test-results-*.csv"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"

RUN_ID = "20260630-110905"
EXECUTED_AT = "2026-06-30T11:09:05"

# 本轮实际执行结果（automation=接口可达；business=业务预期）
EXECUTED = {
    "TC-SMOKE-001": ("PASS", "FAIL", "收到 outbound 但为英文转人工兜底，非正常问候；RAGFlow 404"),
    "TC-SMOKE-002": ("PASS", "FAIL", "无价格信息；RagflowTool 404 转人工"),
    "TC-SMOKE-003-LOCAL": ("PASS", "FAIL", "触发 handoff 但话术为英文兜底；未验证 Web 坐席分配 UI"),
    "TC-SMOKE-003b": ("PASS", "PASS", "转人工后无新增机器人 outbound"),
    "INT-FAQ-A001": ("PASS", "FAIL", "webhook OK；RAG 失败无法验 expected_facts"),
    "INT-FAQ-A001-P1": ("PASS", "FAIL", "webhook OK；task_type=QA_ANSWER；未验回复内容"),
    "INT-FAQ-A001-P2": ("PASS", "FAIL", "同上"),
    "INT-FAQ-A001-P3": ("PASS", "FAIL", "同上"),
    "INT-FAQ-A001-P4": ("PASS", "FAIL", "同上"),
    "INT-FAQ-A001-P5": ("PASS", "FAIL", "同上"),
    "INT-FAQ-A001-P6": ("PASS", "FAIL", "同上"),
    "INT-FAQ-A001-P7": ("PASS", "FAIL", "task_type=PRODUCT_RECOMMENDATION"),
    "INT-FAQ-A001-P8": ("PASS", "FAIL", "同上"),
    "INT-FAQ-A002": ("PASS", "FAIL", "webhook OK；RAG 失败"),
    "INT-FAQ-A002-P1": ("PASS", "FAIL", "task_type=QA_ANSWER"),
    "INT-FAQ-A002-P2": ("PASS", "FAIL", "同上"),
    "INT-FAQ-A002-P3": ("PASS", "FAIL", "同上"),
    "INT-FAQ-A002-P4": ("PASS", "FAIL", "同上"),
    "INT-FAQ-A002-P5": ("PASS", "FAIL", "同上"),
    "INT-FAQ-A002-P6": ("PASS", "FAIL", "task_type=SUPPORT"),
}

BLOCKED_PREFIXES = ("TC-M9-",)


def main():
    cases_path = DATA / "test-cases-full.csv"
    rows = list(csv.DictReader(cases_path.open(encoding="utf-8-sig")))

    out_fields = [
        "run_id", "executed_at", "case_id", "module", "title", "layer", "priority",
        "execution_status", "automation_result", "business_result", "notes",
    ]
    out_rows = []

    for c in rows:
        cid = c["id"]
        if cid.startswith(BLOCKED_PREFIXES):
            out_rows.append({
                "run_id": RUN_ID,
                "executed_at": EXECUTED_AT,
                "case_id": cid,
                "module": c["module"],
                "title": c["title"],
                "layer": c["layer"],
                "priority": c["priority"],
                "execution_status": "BLOCKED",
                "automation_result": "NA",
                "business_result": "NA",
                "notes": "PRD 智齿五类标签后端未实现",
            })
            continue
        if cid in EXECUTED:
            auto, biz, note = EXECUTED[cid]
            out_rows.append({
                "run_id": RUN_ID,
                "executed_at": EXECUTED_AT,
                "case_id": cid,
                "module": c["module"],
                "title": c["title"],
                "layer": c["layer"],
                "priority": c["priority"],
                "execution_status": "EXECUTED",
                "automation_result": auto,
                "business_result": biz,
                "notes": note,
            })
        else:
            out_rows.append({
                "run_id": RUN_ID,
                "executed_at": EXECUTED_AT,
                "case_id": cid,
                "module": c["module"],
                "title": c["title"],
                "layer": c["layer"],
                "priority": c["priority"],
                "execution_status": "NOT_RUN",
                "automation_result": "NA",
                "business_result": "NA",
                "notes": "",
            })

    REPORTS.mkdir(parents=True, exist_ok=True)
    dated = REPORTS / f"test-results-{RUN_ID}.csv"
    latest = REPORTS / "test-results-latest.csv"
    for path in (dated, latest):
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=out_fields)
            w.writeheader()
            w.writerows(out_rows)

    executed = sum(1 for r in out_rows if r["execution_status"] == "EXECUTED")
    biz_pass = sum(1 for r in out_rows if r["business_result"] == "PASS")
    biz_fail = sum(1 for r in out_rows if r["business_result"] == "FAIL")
    print(f"written={dated}")
    print(f"written={latest}")
    print(f"structured_total={len(out_rows)} executed={executed} business_pass={biz_pass} business_fail={biz_fail}")

    # L2 语料（corpus-intent 抽样，不在 test-cases-full 中）
    corpus_path = DATA / "corpus-intent.csv"
    corpus_rows = list(csv.DictReader(corpus_path.open(encoding="utf-8-sig")))[:15]
    corpus_out = []
    for row in corpus_rows:
        cid = row["id"]
        if cid in EXECUTED:
            auto, biz, note = EXECUTED[cid]
        else:
            auto, biz, note = "NA", "NA", ""
        corpus_out.append({
            "run_id": RUN_ID,
            "executed_at": EXECUTED_AT,
            "case_id": cid,
            "corpus": "intent",
            "input": row.get("input", "")[:80],
            "execution_status": "EXECUTED" if cid in EXECUTED else "NOT_RUN",
            "automation_result": auto if cid in EXECUTED else "NA",
            "business_result": biz if cid in EXECUTED else "NA",
            "notes": note,
        })
    corpus_file = REPORTS / f"test-results-corpus-{RUN_ID}.csv"
    corpus_latest = REPORTS / "test-results-corpus-latest.csv"
    cfields = ["run_id", "executed_at", "case_id", "corpus", "input", "execution_status",
               "automation_result", "business_result", "notes"]
    for path in (corpus_file, corpus_latest):
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cfields)
            w.writeheader()
            w.writerows(corpus_out)
    print(f"corpus_sample={len(corpus_out)} written={corpus_latest}")


if __name__ == "__main__":
    main()
