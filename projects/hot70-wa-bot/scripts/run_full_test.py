#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Full automated test: G2 smoke + all L2 corpus via webhook API."""
from __future__ import annotations

import csv
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "scripts"))

from l2_eval_core import (  # noqa: E402
    classify_fail,
    eval_row_by_corpus,
    first_response_ms,
    is_handoff,
    session_id_from,
    session_task_type,
)
from prd_acceptance_metrics import (  # noqa: E402
    compute_all_metrics,
    format_l2_gates_markdown,
    format_metrics_markdown,
    l4_case_notes,
    metrics_to_summary_dict,
)
from run_bundle import finalize_run_bundle, run_dir  # noqa: E402
from bug_registry import (  # noqa: E402
    BUG_CASE_MAPPING_FIELDS,
    BUG_CSV_FIELDS,
    build_bug_registry,
    bug_case_mapping_rows,
    bugs_to_csv_rows,
    bugs_to_json,
    case_to_bugs_map,
    classify_formal_fail,
    format_bug_management_markdown,
)
from run_test_suite import (  # noqa: E402
    DEFAULT_BASE,
    DEFAULT_PASS,
    DEFAULT_USER,
    Client,
    find_conversation,
    outbound_texts,
)
from case_executor import poll_turn_state, user_message_from_input  # noqa: E402
from test_case_runner import run_all_formal_cases  # noqa: E402

CORPUS_FILES = {
    "intent": DATA / "corpus-intent.csv",
    "kb": DATA / "corpus-kb.csv",
    "handoff": DATA / "corpus-handoff.csv",
    "adversarial": DATA / "corpus-adversarial.csv",
}

BLOCKED_PREFIXES = ("TC-M9-",)


def load_rows(path: Path) -> list[dict]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig")))


def eval_corpus_row(client: Client, channel: str, bl: int, row: dict, wait: float) -> dict:
    cid = row.get("id", "")
    text = user_message_from_input(row.get("input") or "")
    if not text:
        return {
            "id": cid,
            "corpus": row.get("_corpus", ""),
            "input": (row.get("input") or "")[:80],
            "whatsapp_id": "",
            "session_id": "",
            "response_ms": "",
            "routing_pass": "NA",
            "status": "SKIP",
            "automation_result": "SKIP",
            "business_result": "NA",
            "fail_class": "NA",
            "notes": "non-simulatable input (steps/preconditions only)",
        }

    corpus_name = row.get("_corpus", "")
    should_ho = (row.get("should_handoff") or "").lower()
    action = (row.get("expected_action") or "").lower()
    expect_handoff = should_ho == "true" or action == "handoff"

    wa = f"l2-{uuid.uuid4().hex[:10]}@s.whatsapp.net"
    t0 = time.perf_counter()
    st, wh = client.webhook(channel, wa, text)
    poll_wait = max(wait, 4.0) if expect_handoff else wait
    sess, msgs, conv, texts = poll_turn_state(
        client, bl, wa, wait_s=poll_wait, expect_handoff=expect_handoff,
    )
    task_type = session_task_type(sess)
    handoff = is_handoff(sess, conv)
    wh_ok = st == 200 and (wh.get("data") or {}).get("status") == "success"
    auto = "PASS" if wh_ok else "FAIL"
    resp_ms = first_response_ms(msgs, fallback_wait_ms=wait * 1000)

    biz, note_list, routing_pass = eval_row_by_corpus(
        corpus=corpus_name,
        row=row,
        wh_ok=wh_ok,
        wh_st=st,
        sess=sess,
        conv=conv,
        texts=texts,
        task_type=task_type,
        handoff=handoff,
    )
    notes = "; ".join(note_list)
    status = "PASS" if auto == "PASS" and biz == "PASS" else ("SKIP" if auto == "SKIP" else "FAIL")
    fail_class = classify_fail(
        corpus=corpus_name,
        automation_result=auto,
        business_result=biz,
        notes=notes,
        status=status,
    )

    return {
        "id": cid,
        "corpus": corpus_name,
        "input": text[:80],
        "whatsapp_id": wa,
        "session_id": session_id_from(sess),
        "response_ms": int(resp_ms) if resp_ms is not None else "",
        "routing_pass": "PASS" if routing_pass else "FAIL",
        "status": status,
        "automation_result": auto,
        "business_result": biz,
        "fail_class": fail_class,
        "task_type": task_type,
        "should_handoff": row.get("should_handoff", ""),
        "outbound_preview": texts[-1][:120] if texts else "",
        "notes": notes or ("OK" if biz == "PASS" else ""),
        "_elapsed_s": round(time.perf_counter() - t0, 2),
    }


def run_all_corpus(client: Client, channel: str, bl: int, wait: float) -> list[dict]:
    results = []
    for name, path in CORPUS_FILES.items():
        if not path.exists():
            continue
        rows = load_rows(path)
        for row in rows:
            row = dict(row)
            row["_corpus"] = name
            results.append(eval_corpus_row(client, channel, bl, row, wait))
            if len(results) % 50 == 0:
                print(f"  corpus progress {len(results)}...", flush=True)
    return results


def write_reports(run_id: str, executed_at: str, formal: list, corpus: list, meta: dict):
    REPORTS.mkdir(parents=True, exist_ok=True)

    smoke = [r for r in formal if str(r.get("case_id", "")).startswith("TC-SMOKE")]
    sp = sum(1 for r in smoke if r.get("business_result") == "PASS")
    sf = sum(1 for r in smoke if r.get("business_result") in ("FAIL", "PARTIAL"))
    fp = sum(1 for r in formal if r.get("business_result") == "PASS")
    ff = sum(1 for r in formal if r.get("business_result") == "FAIL")
    fpartial = sum(1 for r in formal if r.get("business_result") == "PARTIAL")
    cp = sum(1 for r in corpus if r.get("business_result") == "PASS")
    cf = sum(1 for r in corpus if r.get("business_result") == "FAIL")
    cs = sum(1 for r in corpus if r.get("status") == "SKIP")
    ca = sum(1 for r in corpus if r.get("automation_result") == "PASS")

    smoke_for_metrics = [
        {"id": r["case_id"], "status": "PASS" if r.get("business_result") == "PASS" else "FAIL"}
        for r in smoke
    ]
    prd_metrics = compute_all_metrics(smoke_for_metrics, corpus)
    l4_notes = l4_case_notes(prd_metrics)

    bundle = run_dir(run_id)
    lines = [
        "# Hot70 全量自动化测试报告",
        "",
        f"> {executed_at}",
        "",
        f"> 产出物目录：`{bundle.relative_to(ROOT).as_posix()}/`",
        "",
        "## 环境",
        "",
        f"- API: `{meta['base']}`",
        f"- channel: `{meta['channel']}`",
        f"- business_line_id: `{meta['business_line_id']}`",
        f"- wait: `{meta['wait']}s`",
        "",
        "## 汇总",
        "",
        f"| 范围 | 总数 | 业务Pass | Fail | Partial | Skip/Defer |",
        f"|------|------|----------|------|---------|------------|",
        f"| Formal 用例 (TC-*) | {len(formal)} | {fp} | {ff} | {fpartial} | {sum(1 for r in formal if r.get('execution_status') in ('NOT_RUN','BLOCKED','SKIP'))} |",
        f"| G2 冒烟 | {len(smoke)} | {sp} | {sf} | 0 | 0 |",
        f"| L2 语料 | {len(corpus)} | {cp} | {cf} | 0 | {cs} |",
        "",
    ]
    lines += format_metrics_markdown(prd_metrics)
    lines += [
        "## G2 冒烟（Formal verify_profile）",
        "",
        "| ID | 结果 | 验证点摘要 |",
        "|----|------|------------|",
    ]
    for r in smoke:
        lines.append(
            f"| {r.get('case_id','')} | {r.get('business_result','')} | {str(r.get('notes',''))[:70]} |"
        )

    formal_fails = [r for r in formal if r.get("business_result") == "FAIL"][:25]
    lines += [
        "",
        "## Formal 用例 Fail 样例 Top25",
        "",
        "| ID | 模块 | 结果 | notes |",
        "|----|------|------|-------|",
    ]
    for r in formal_fails:
        lines.append(
            f"| {r.get('case_id','')} | {r.get('module','')} | {r.get('business_result','')} | {str(r.get('notes',''))[:50]} |"
        )

    fails = [r for r in corpus if r.get("business_result") == "FAIL"][:30]
    lines += [
        "",
        "## L2 语料（业务 Fail 样例 Top30）",
        "",
        "| ID | corpus | 业务 | fail_class | task_type | notes |",
        "|----|--------|------|------------|-----------|-------|",
    ]
    if fails:
        for r in fails:
            lines.append(
                f"| {r['id']} | {r.get('corpus','')} | {r.get('business_result','')} | "
                f"{r.get('fail_class','')} | {r.get('task_type','')} | {str(r.get('notes',''))[:40]} |"
            )
    else:
        lines.append("| — | — | — | — | — | 本轮未执行或无 Fail |")
    lines.append("")

    bugs, bug_analysis = build_bug_registry(run_id, formal, corpus)
    case_bugs = case_to_bugs_map(bugs)
    lines += format_bug_management_markdown(bugs, bug_analysis)

    lines += [
        "",
        "## 说明",
        "",
        "- Formal 用例按 `verify_profile` 逐条断言；`MANUAL_PENDING` 项需 L3 人工补测",
        "- L2 语料为 FAQ 批量回归，补充 intent/kb/handoff 指标",
        "- 缺陷清单见 `bug-registry.csv`；用例↔缺陷见 `bug-case-mapping.csv`",
        f"- 本轮全部产出物见 `{bundle.relative_to(ROOT).as_posix()}/`（含 Word 报告 `test-report.docx`）",
        "",
    ]
    report_md_text = "\n".join(lines)

    formal_by_id = {r["case_id"]: r for r in formal}

    cases = load_rows(DATA / "test-cases-full.csv")
    out_fields = [
        "run_id", "executed_at", "case_id", "module", "title", "layer", "priority",
        "execution_status", "automation_result", "business_result", "fail_class", "bug_ids", "notes",
    ]
    structured = []
    for c in cases:
        cid = c["id"]
        if cid in formal_by_id:
            r = formal_by_id[cid]
            note = r.get("notes") or ""
            if r.get("session_id"):
                note = f"session_id={r['session_id']}; {note}".strip("; ")
            structured.append({
                "run_id": run_id, "executed_at": executed_at, "case_id": cid,
                "module": c["module"], "title": c["title"], "layer": c["layer"],
                "priority": c["priority"],
                "execution_status": r.get("execution_status", "NOT_RUN"),
                "automation_result": r.get("automation_result", "NA"),
                "business_result": r.get("business_result", "NA"),
                "fail_class": classify_formal_fail(r),
                "bug_ids": ";".join(case_bugs.get(cid, [])),
                "notes": note,
            })
        elif cid.startswith(BLOCKED_PREFIXES):
            structured.append({
                "run_id": run_id, "executed_at": executed_at, "case_id": cid,
                "module": c["module"], "title": c["title"], "layer": c["layer"],
                "priority": c["priority"],
                "execution_status": "BLOCKED",
                "automation_result": "NA", "business_result": "NA",
                "fail_class": "NA",
                "bug_ids": "",
                "notes": "PRD 智齿五类标签后端未实现",
            })
        elif cid in l4_notes:
            note = l4_notes[cid]
            metric_rows = list(prd_metrics.get("prd_7_3", [])) + list(prd_metrics.get("plan_8", []))
            m = next((x for x in metric_rows if x.case_id == cid), None)
            if m and m.verdict in ("PASS", "FAIL", "INSUFFICIENT"):
                structured.append({
                    "run_id": run_id, "executed_at": executed_at, "case_id": cid,
                    "module": c["module"], "title": c["title"], "layer": c["layer"],
                    "priority": c["priority"], "execution_status": "EXECUTED",
                    "automation_result": "NA",
                    "business_result": m.verdict if m.verdict in ("PASS", "FAIL") else "NA",
                    "fail_class": "—" if m.verdict == "PASS" else "NA",
                    "bug_ids": "",
                    "notes": note,
                })
            else:
                structured.append({
                    "run_id": run_id, "executed_at": executed_at, "case_id": cid,
                    "module": c["module"], "title": c["title"], "layer": c["layer"],
                    "priority": c["priority"], "execution_status": "NOT_RUN",
                    "automation_result": "NA", "business_result": "NA",
                    "fail_class": "NA",
                    "bug_ids": "",
                    "notes": note,
                })
        else:
            structured.append({
                "run_id": run_id, "executed_at": executed_at, "case_id": cid,
                "module": c["module"], "title": c["title"], "layer": c["layer"],
                "priority": c["priority"], "execution_status": "NOT_RUN",
                "automation_result": "NA", "business_result": "NA",
                "fail_class": "NA",
                "bug_ids": "",
                "notes": "未在 profile 中配置或未执行",
            })

    cfields = [
        "run_id", "executed_at", "case_id", "corpus", "input",
        "whatsapp_id", "session_id", "response_ms", "routing_pass",
        "execution_status", "automation_result", "business_result", "fail_class", "bug_ids",
        "task_type", "should_handoff", "notes",
    ]
    corpus_out = []
    for r in corpus:
        corpus_out.append({
            "run_id": run_id,
            "executed_at": executed_at,
            "case_id": r["id"],
            "corpus": r.get("corpus", ""),
            "input": r.get("input", ""),
            "whatsapp_id": r.get("whatsapp_id", ""),
            "session_id": r.get("session_id", ""),
            "response_ms": r.get("response_ms", ""),
            "routing_pass": r.get("routing_pass", ""),
            "execution_status": "EXECUTED" if r.get("status") != "SKIP" else "SKIP",
            "automation_result": r.get("automation_result", ""),
            "business_result": r.get("business_result", ""),
            "fail_class": r.get("fail_class", ""),
            "bug_ids": ";".join(case_bugs.get(r["id"], [])),
            "task_type": r.get("task_type", ""),
            "should_handoff": r.get("should_handoff", ""),
            "notes": r.get("notes", ""),
        })

    summary = {
        "run_id": run_id,
        "executed_at": executed_at,
        "formal_total": len(formal),
        "formal_pass": fp,
        "formal_fail": ff,
        "formal_partial": fpartial,
        "smoke_pass": sp,
        "smoke_fail": sf,
        "corpus_total": len(corpus),
        "corpus_auto_pass": ca,
        "corpus_biz_pass": cp,
        "corpus_biz_fail": cf,
        "corpus_skip": cs,
        "metrics": metrics_to_summary_dict(prd_metrics),
        "l2_gates_pass": all(g.verdict == "PASS" for g in prd_metrics["l2_gates"]),
        "bugs": bugs_to_json(bugs, bug_analysis),
    }

    bug_rows = bugs_to_csv_rows(bugs, run_id, executed_at)
    mapping_rows = bug_case_mapping_rows(bugs, run_id, executed_at)

    paths = finalize_run_bundle(
        run_id=run_id,
        executed_at=executed_at,
        report_md_text=report_md_text,
        summary=summary,
        structured_rows=structured,
        structured_fields=list(out_fields),
        corpus_rows=corpus_out,
        corpus_fields=cfields,
        bug_rows=bug_rows,
        bug_fields=BUG_CSV_FIELDS,
        bug_mapping_rows=mapping_rows,
        bug_mapping_fields=BUG_CASE_MAPPING_FIELDS,
    )
    summary["report_md"] = str(paths["report_md"].relative_to(ROOT)).replace("\\", "/")
    summary["report_docx"] = str(paths["report_docx"].relative_to(ROOT)).replace("\\", "/")
    summary["bundle_dir"] = str(run_dir(run_id).relative_to(ROOT)).replace("\\", "/")
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md = paths["report_md"]
    return md, summary


def main():
    wait = 2.0
    channel = "ch_wa_01"
    bl = 1
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    executed_at = datetime.now().isoformat(timespec="seconds")

    client = Client(DEFAULT_BASE, DEFAULT_USER, DEFAULT_PASS)
    if not client.login(DEFAULT_USER, DEFAULT_PASS):
        print("LOGIN FAILED", file=sys.stderr)
        sys.exit(1)
    print("LOGIN OK", flush=True)

    print("running formal test cases (verify_profile)...", flush=True)
    formal = run_all_formal_cases(client, channel, bl, max(wait, 4.0))
    fp = sum(1 for r in formal if r.get("business_result") == "PASS")
    ff = sum(1 for r in formal if r.get("business_result") == "FAIL")
    print(f"formal done pass={fp} fail={ff} partial={sum(1 for r in formal if r.get('business_result')=='PARTIAL')}", flush=True)

    print("running L2 corpus...", flush=True)
    corpus = run_all_corpus(client, channel, bl, wait)
    print(
        f"corpus done auto_pass={sum(1 for r in corpus if r.get('automation_result')=='PASS')} "
        f"biz_pass={sum(1 for r in corpus if r.get('business_result')=='PASS')} "
        f"biz_fail={sum(1 for r in corpus if r.get('business_result')=='FAIL')} "
        f"skip={sum(1 for r in corpus if r.get('status')=='SKIP')}",
        flush=True,
    )

    md, summary = write_reports(run_id, executed_at, formal, corpus, {
        "base": DEFAULT_BASE,
        "channel": channel,
        "business_line_id": bl,
        "wait": wait,
    })
    print(f"bundle={summary.get('bundle_dir')}")
    print(f"report_md={md}")
    print(f"report_docx={summary.get('report_docx')}")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
