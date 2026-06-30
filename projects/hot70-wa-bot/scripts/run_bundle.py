#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单次测试产出物归档：reports/runs/{run_id}/"""
from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
RUNS = REPORTS / "runs"

# 归档目录内固定文件名（run_id 已在父目录名中）
ARTIFACT_NAMES = {
    "report_md": "test-report.md",
    "report_docx": "test-report.docx",
    "summary": "summary.json",
    "test_results": "test-results.csv",
    "corpus_results": "test-results-corpus.csv",
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
    """根目录保留 -latest 副本，兼容现有脚本。"""
    REPORTS.mkdir(parents=True, exist_ok=True)
    mapping = {
        REPORTS / "test-results-latest.csv": paths["test_results"],
        REPORTS / "test-results-corpus-latest.csv": paths["corpus_results"],
    }
    for dst, src in mapping.items():
        if src.exists():
            try:
                shutil.copy2(src, dst)
            except OSError as e:
                print(f"warn: could not update {dst.name}: {e}", flush=True)

    pointer = {
        "run_id": run_id,
        "dir": str(run_dir(run_id).relative_to(ROOT)).replace("\\", "/"),
        "report_md": ARTIFACT_NAMES["report_md"],
        "report_docx": ARTIFACT_NAMES["report_docx"],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    (REPORTS / "latest-run.json").write_text(
        json.dumps(pointer, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def finalize_run_bundle(
    run_id: str,
    executed_at: str,
    report_md_text: str,
    summary: dict,
    structured_rows: list[dict],
    structured_fields: list[str],
    corpus_rows: list[dict],
    corpus_fields: list[str],
) -> dict[str, Path]:
    """写入 run 目录全部产出物并生成 Word。"""
    from report_docx import md_to_docx

    paths = artifact_paths(run_id)
    d = run_dir(run_id)
    d.mkdir(parents=True, exist_ok=True)

    # Markdown 报告
    md_path = paths["report_md"]
    md_path.write_text(report_md_text, encoding="utf-8")

    # 结构化 CSV
    with paths["test_results"].open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=structured_fields)
        w.writeheader()
        w.writerows(structured_rows)

    with paths["corpus_results"].open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=corpus_fields)
        w.writeheader()
        w.writerows(corpus_rows)

    # JSON 汇总
    summary = dict(summary)
    summary["run_id"] = run_id
    summary["bundle_dir"] = str(d.relative_to(ROOT)).replace("\\", "/")
    summary["report_md"] = str(md_path.relative_to(ROOT)).replace("\\", "/")
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # Word
    md_to_docx(md_path, paths["report_docx"])

    write_manifest(run_id, executed_at, paths, extra={"summary": summary})
    update_latest_pointer(run_id, paths)

    # 根目录保留带 run_id 的副本，便于按文件名搜索
    legacy = {
        REPORTS / f"test-run-{run_id}.md": md_path,
        REPORTS / f"test-run-summary-{run_id}.json": paths["summary"],
        REPORTS / f"test-results-{run_id}.csv": paths["test_results"],
        REPORTS / f"test-results-corpus-{run_id}.csv": paths["corpus_results"],
        REPORTS / f"test-run-{run_id}.docx": paths["report_docx"],
    }
    for dst, src in legacy.items():
        shutil.copy2(src, dst)

    return paths


def bundle_existing_run(run_id: str) -> Path | None:
    """将根目录已有产出物迁入 runs/{run_id}/ 并补 Word。"""
    from report_docx import md_to_docx

    md_legacy = REPORTS / f"test-run-{run_id}.md"
    if not md_legacy.exists():
        return None

    paths = artifact_paths(run_id)
    d = run_dir(run_id)
    d.mkdir(parents=True, exist_ok=True)

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

    legacy_docx = REPORTS / f"test-run-{run_id}.docx"
    if paths["report_docx"].exists():
        shutil.copy2(paths["report_docx"], legacy_docx)

    return d
