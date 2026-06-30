#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从已有 corpus CSV 刷新 PRD §7.3 指标段（无需重跑全量测试）。"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "scripts"))

from prd_acceptance_metrics import (  # noqa: E402
    compute_all_metrics,
    format_metrics_markdown,
    l4_case_notes,
    metrics_to_summary_dict,
)
from report_docx import md_to_docx  # noqa: E402
from run_bundle import RUNS, artifact_paths, bundle_existing_run, update_latest_pointer, write_manifest  # noqa: E402


def load_corpus_results(path: Path) -> list[dict]:
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    out = []
    for r in rows:
        exec_st = r.get("execution_status", "")
        out.append({
            "id": r.get("case_id", ""),
            "corpus": r.get("corpus", ""),
            "status": "SKIP" if exec_st == "SKIP" else exec_st or "EXECUTED",
            "automation_result": r.get("automation_result", ""),
            "business_result": r.get("business_result", ""),
            "routing_pass": r.get("routing_pass", ""),
            "should_handoff": r.get("should_handoff", ""),
        })
    return out


def patch_markdown(md_path: Path, metrics_section: list[str]) -> None:
    text = md_path.read_text(encoding="utf-8")
    start = "## PRD §7.3 核心验收指标"
    end_markers = ("## G2 冒烟", "## 汇总", "## 冒烟")
    if start in text:
        before = text.split(start)[0].rstrip()
        rest = text.split(start, 1)[1]
        for em in end_markers:
            if em in rest:
                after = rest.split(em, 1)[1]
                text = before + "\n\n" + "\n".join(metrics_section).rstrip() + "\n\n" + em + after
                break
        else:
            text = before + "\n\n" + "\n".join(metrics_section)
    else:
        # 插在「汇总」段之后
        anchor = "## 汇总"
        if anchor not in text:
            print(f"skip markdown patch: no anchor in {md_path}", file=sys.stderr)
            return
        parts = text.split(anchor, 1)
        body = parts[1]
        for em in ("## G2 冒烟", "## 冒烟 G2", "## L2"):
            if em in body:
                pre, post = body.split(em, 1)
                text = parts[0] + anchor + pre + "\n\n" + "\n".join(metrics_section).rstrip() + "\n\n" + em + post
                break
        else:
            text = text + "\n\n" + "\n".join(metrics_section)
    md_path.write_text(text, encoding="utf-8")


def patch_structured_csv(csv_path: Path, run_id: str, l4_notes: dict, metrics) -> None:
    if not csv_path.exists():
        return
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig")))
    if not rows:
        return
    fields = rows[0].keys()
    by_case = {m.case_id: m for m in metrics}
    for r in rows:
        cid = r.get("case_id", "")
        if cid not in l4_notes:
            continue
        note = l4_notes[cid]
        r["notes"] = note
        m = by_case.get(cid)
        if m and m.verdict in ("PASS", "FAIL", "INSUFFICIENT"):
            r["execution_status"] = "EXECUTED"
            r["business_result"] = m.verdict if m.verdict in ("PASS", "FAIL") else "NA"
        elif cid in l4_notes:
            r["execution_status"] = "NOT_RUN"
            r["business_result"] = "NA"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _resolve_run(run_id: str | None) -> tuple[str, Path]:
    if run_id:
        return run_id, RUNS / run_id
    pointer = REPORTS / "latest-run.json"
    if pointer.exists():
        data = json.loads(pointer.read_text(encoding="utf-8"))
        rid = data.get("run_id", "")
        if rid:
            return rid, RUNS / rid
    md_candidates = sorted(REPORTS.glob("test-run-*.md"), reverse=True)
    if md_candidates:
        rid = md_candidates[0].stem.replace("test-run-", "")
        return rid, RUNS / rid
    raise SystemExit("cannot resolve run_id; pass as argv[1]")


def main():
    run_id_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_id, bundle_dir = _resolve_run(run_id_arg)

    paths = artifact_paths(run_id)
    md_path = paths["report_md"] if paths["report_md"].exists() else REPORTS / f"test-run-{run_id}.md"
    corpus_path = paths["corpus_results"] if paths["corpus_results"].exists() else REPORTS / f"test-results-corpus-{run_id}.csv"

    if not md_path.exists():
        bundle_existing_run(run_id)
        md_path = paths["report_md"] if paths["report_md"].exists() else md_path

    if not corpus_path.exists():
        print(f"missing corpus results for {run_id}", file=sys.stderr)
        sys.exit(1)

    corpus = load_corpus_results(corpus_path)
    smoke: list[dict] = []
    metrics = compute_all_metrics(smoke, corpus)
    section = format_metrics_markdown(metrics)
    l4_notes = l4_case_notes(metrics)

    patch_markdown(md_path, section)
    print(f"patched {md_path}")

    for csv_name, csv_path in (
        ("test-results", paths["test_results"] if paths["test_results"].exists() else REPORTS / f"test-results-{run_id}.csv"),
        ("test-results-latest", REPORTS / "test-results-latest.csv"),
    ):
        if csv_path.exists():
            patch_structured_csv(csv_path, run_id, l4_notes, metrics)
            print(f"patched {csv_path}")

    summary_path = paths["summary"] if paths["summary"].exists() else REPORTS / f"test-run-summary-{run_id}.json"
    summary: dict = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["metrics"] = metrics_to_summary_dict(metrics)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"patched {summary_path}")

    docx_path = paths["report_docx"]
    md_to_docx(md_path, docx_path)
    print(f"generated {docx_path}")

    if bundle_dir.exists() or paths["report_md"].exists():
        write_manifest(run_id, summary.get("executed_at", "") if summary_path.exists() else "", paths)
        update_latest_pointer(run_id, paths)
        legacy_docx = REPORTS / f"test-run-{run_id}.docx"
        if docx_path.exists():
            import shutil
            shutil.copy2(md_path, REPORTS / f"test-run-{run_id}.md")
            shutil.copy2(docx_path, legacy_docx)
            if paths["summary"].exists():
                shutil.copy2(paths["summary"], REPORTS / f"test-run-summary-{run_id}.json")

    print("\nPRD §7.3 metrics:")
    for m in metrics:
        print(f"  {m.name}: {m.rate_display} ({m.verdict}) n={m.sample_n}")


if __name__ == "__main__":
    main()
