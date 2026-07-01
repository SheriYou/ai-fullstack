#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单次测试产出物归档：reports/runs/{run_id}/（根目录不复制 dated 副本）。"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
RUNS = REPORTS / "runs"
FRAMEWORK_LIB = Path(__file__).resolve().parents[3] / "lib"
if str(FRAMEWORK_LIB) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_LIB))

from run_paths import purge_root_run_artifacts, write_latest_pointer  # noqa: E402

# 归档目录内固定文件名（run_id 已在父目录名中）
ARTIFACT_NAMES = {
    "report_md": "test-report.md",
    "report_docx": "test-report.docx",
    "summary": "summary.json",
    "test_results": "test-results.csv",
    "corpus_results": "test-results-corpus.csv",
    "bug_registry": "bug-registry.csv",
    "bug_case_mapping": "bug-case-mapping.csv",
    "bugs_json": "bugs.json",
    "manifest": "manifest.json",
}


def run_dir(run_id: str) -> Path:
    return RUNS / run_id


def artifact_paths(run_id: str) -> dict[str, Path]:
    d = run_dir(run_id)
    return {key: d / name for key, name in ARTIFACT_NAMES.items()}


def write_manifest(
    run_id: str,
    executed_at: str,
    paths: dict[str, Path],
    extra: dict | None = None,
) -> Path:
    d = run_dir(run_id)
    d.mkdir(parents=True, exist_ok=True)
    manifest_path = paths["manifest"]
    items = []
    descriptions = {
        "report_md": "测试报告（Markdown）",
        "report_docx": "测试报告（Word）",
        "summary": "机器可读汇总（含 PRD §7.3）",
        "test_results": "结构化用例逐条结果",
        "corpus_results": "L2 语料逐条结果",
        "bug_registry": "缺陷清单（去重 + 分析）",
        "bug_case_mapping": "用例编号 ↔ 缺陷 ID 关联表",
        "bugs_json": "缺陷 JSON（机器可读）",
    }
    for key, desc in descriptions.items():
        p = paths.get(key)
        if p and p.exists():
            items.append({
                "key": key,
                "file": p.name,
                "description": desc,
                "size_bytes": p.stat().st_size,
            })
    payload = {
        "run_id": run_id,
        "executed_at": executed_at,
        "bundle_dir": str(d.relative_to(ROOT)).replace("\\", "/"),
        "artifacts": items,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if extra:
        payload.update(extra)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def update_latest_pointer(run_id: str, paths: dict[str, Path]) -> None:
    """更新 latest-run.json；产出物仅在 runs/{run_id}/。"""
    write_latest_pointer(REPORTS, run_id, project_root=ROOT)


def finalize_run_bundle(
    run_id: str,
    executed_at: str,
    report_md_text: str,
    summary: dict,
    structured_rows: list[dict],
    structured_fields: list[str],
    corpus_rows: list[dict],
    corpus_fields: list[str],
    bug_rows: list[dict] | None = None,
    bug_fields: list[str] | None = None,
    bug_mapping_rows: list[dict] | None = None,
    bug_mapping_fields: list[str] | None = None,
) -> dict[str, Path]:
    """写入 run 目录全部产出物并生成 Word。"""
    from report_docx import md_to_docx

    paths = artifact_paths(run_id)
    d = run_dir(run_id)
    d.mkdir(parents=True, exist_ok=True)

    md_path = paths["report_md"]
    md_path.write_text(report_md_text, encoding="utf-8")

    with paths["test_results"].open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=structured_fields)
        w.writeheader()
        w.writerows(structured_rows)

    with paths["corpus_results"].open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=corpus_fields)
        w.writeheader()
        w.writerows(corpus_rows)

    if bug_rows is not None and bug_fields:
        with paths["bug_registry"].open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=bug_fields)
            w.writeheader()
            w.writerows(bug_rows)
        if summary.get("bugs"):
            paths["bugs_json"].write_text(
                json.dumps(summary["bugs"], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    if bug_mapping_rows is not None and bug_mapping_fields:
        with paths["bug_case_mapping"].open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=bug_mapping_fields)
            w.writeheader()
            w.writerows(bug_mapping_rows)

    summary = dict(summary)
    summary["run_id"] = run_id
    summary["bundle_dir"] = str(d.relative_to(ROOT)).replace("\\", "/")
    summary["report_md"] = str(md_path.relative_to(ROOT)).replace("\\", "/")
    summary["report_docx"] = str(paths["report_docx"].relative_to(ROOT)).replace("\\", "/")
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md_to_docx(md_path, paths["report_docx"])

    write_manifest(run_id, executed_at, paths, extra={"summary": summary})
    update_latest_pointer(run_id, paths)

    removed = purge_root_run_artifacts(REPORTS)
    if removed:
        print(f"purged {len(removed)} root artifact(s); see runs/{run_id}/", flush=True)

    return paths


def bundle_existing_run(run_id: str) -> Path | None:
    """将根目录遗留产出物迁入 runs/{run_id}/（兼容旧布局）。"""
    from report_docx import md_to_docx

    paths = artifact_paths(run_id)
    d = run_dir(run_id)
    if paths["report_md"].exists():
        update_latest_pointer(run_id, paths)
        purge_root_run_artifacts(REPORTS)
        return d

    md_legacy = REPORTS / f"test-run-{run_id}.md"
    if not md_legacy.exists():
        return None

    d.mkdir(parents=True, exist_ok=True)
    import shutil

    shutil.copy2(md_legacy, paths["report_md"])

    for key, legacy_name in (
        ("summary", f"test-run-summary-{run_id}.json"),
        ("test_results", f"test-results-{run_id}.csv"),
        ("corpus_results", f"test-results-corpus-{run_id}.csv"),
    ):
        src = REPORTS / legacy_name
        if src.exists():
            shutil.copy2(src, paths[key])

    if not paths["report_docx"].exists():
        md_to_docx(paths["report_md"], paths["report_docx"])

    executed_at = ""
    summary_data: dict = {}
    if paths["summary"].exists():
        summary_data = json.loads(paths["summary"].read_text(encoding="utf-8"))
        executed_at = summary_data.get("executed_at", "")
        summary_data["bundle_dir"] = str(d.relative_to(ROOT)).replace("\\", "/")
        summary_data["report_md"] = str(paths["report_md"].relative_to(ROOT)).replace("\\", "/")
        summary_data["report_docx"] = str(paths["report_docx"].relative_to(ROOT)).replace("\\", "/")
        paths["summary"].write_text(json.dumps(summary_data, ensure_ascii=False, indent=2), encoding="utf-8")

    write_manifest(run_id, executed_at, paths, extra={"summary": summary_data} if summary_data else None)
    update_latest_pointer(run_id, paths)
    purge_root_run_artifacts(REPORTS)
    return d
