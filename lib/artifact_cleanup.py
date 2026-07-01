#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试产出物定期清理：按保留天数删除过期 run 与根目录副本。"""
from __future__ import annotations

import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

FRAMEWORK_LIB = Path(__file__).resolve().parent
if str(FRAMEWORK_LIB) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_LIB))

from run_paths import (  # noqa: E402
    list_run_dirs,
    parse_run_id,
    purge_root_run_artifacts,
    write_latest_pointer,
)

RUN_ID_RE = re.compile(r"^(\d{8})-(\d{6})$")

# 根目录 reports/ 下永不自动删除的文件名
PROTECTED_REPORT_FILES = frozenset({
    "README.md",
    "e2e-log.csv",
    "test-cases-full-review.md",
    "corpus-review-for-ops.md",
    "latest-run.json",
})

# 带 run_id 的根目录副本 glob（兼容旧布局，清理时删除）
LEGACY_GLOBS = (
    "test-run-*.md",
    "test-run-*.docx",
    "test-results-*.csv",
    "test-results-corpus-*.csv",
    "test-run-summary-*.json",
    "test-results-latest.csv",
    "test-results-corpus-latest.csv",
)

# 其他可过期报告
OTHER_GLOBS = ("offline-eval-*.md", "full-test-run.log")


@dataclass
class CleanupResult:
    project: str
    skipped: bool = False
    skip_reason: str = ""
    deleted_paths: list[str] = field(default_factory=list)
    kept_runs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def extract_run_id_from_name(name: str) -> str | None:
    m = re.search(r"(\d{8}-\d{6})", name)
    return m.group(1) if m else None


def _unlink_or_rmtree(path: Path, deleted: list[str], errors: list[str]) -> None:
    try:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.is_file():
            path.unlink()
        else:
            return
        deleted.append(str(path))
    except OSError as e:
        errors.append(f"{path}: {e}")


def cleanup_project_reports(
    reports_dir: Path,
    *,
    retention_days: int = 7,
    min_runs: int = 1,
    dry_run: bool = False,
) -> CleanupResult:
    project = reports_dir.parent.name
    result = CleanupResult(project=project)
    if not reports_dir.is_dir():
        result.skipped = True
        result.skip_reason = "reports dir missing"
        return result

    cutoff = datetime.now() - timedelta(days=retention_days)
    runs = list_run_dirs(reports_dir)
    keep_ids = {rid for i, (rid, _, _) in enumerate(runs) if i < min_runs}

    for run_id, run_dt, run_path in runs:
        if run_id in keep_ids:
            result.kept_runs.append(run_id)
            continue
        if run_dt >= cutoff:
            result.kept_runs.append(run_id)
            continue
        if dry_run:
            result.deleted_paths.append(str(run_path) + " [dry-run]")
        else:
            _unlink_or_rmtree(run_path, result.deleted_paths, result.errors)

    # 根目录遗留副本（旧版框架会在 reports/ 根目录复制 dated 文件）
    if dry_run:
        for pattern in LEGACY_GLOBS:
            for path in reports_dir.glob(pattern):
                if path.name not in PROTECTED_REPORT_FILES:
                    result.deleted_paths.append(str(path) + " [dry-run]")
    else:
        for path_str in purge_root_run_artifacts(reports_dir):
            result.deleted_paths.append(path_str)

    for pattern in OTHER_GLOBS:
        for path in reports_dir.glob(pattern):
            if path.name in PROTECTED_REPORT_FILES:
                continue
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            if mtime >= cutoff:
                continue
            if dry_run:
                result.deleted_paths.append(str(path) + " [dry-run]")
            else:
                _unlink_or_rmtree(path, result.deleted_paths, result.errors)

    if not dry_run:
        _refresh_latest_pointer(reports_dir, result)

    return result


def _refresh_latest_pointer(reports_dir: Path, result: CleanupResult) -> None:
    """清理后更新 latest-run.json（不再复制 -latest CSV）。"""
    runs = list_run_dirs(reports_dir)
    if not runs:
        pointer = reports_dir / "latest-run.json"
        if pointer.exists():
            try:
                pointer.unlink()
            except OSError as e:
                result.errors.append(f"{pointer}: {e}")
        return

    run_id = runs[0][0]
    try:
        write_latest_pointer(reports_dir, run_id, project_root=reports_dir.parent)
    except OSError as e:
        result.errors.append(f"latest-run.json: {e}")


def cleanup_all_projects(
    framework_root: Path,
    *,
    retention_days: int = 7,
    min_runs: int = 1,
    dry_run: bool = False,
) -> list[CleanupResult]:
    projects_root = framework_root / "projects"
    results: list[CleanupResult] = []
    if not projects_root.is_dir():
        return results
    for project_dir in sorted(projects_root.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith("_"):
            continue
        reports = project_dir / "reports"
        if reports.is_dir():
            results.append(
                cleanup_project_reports(
                    reports,
                    retention_days=retention_days,
                    min_runs=min_runs,
                    dry_run=dry_run,
                )
            )
    return results


def load_cleanup_state(state_file: Path) -> dict:
    if not state_file.exists():
        return {}
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_cleanup_state(state_file: Path, payload: dict) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def already_ran_today(state_file: Path) -> bool:
    state = load_cleanup_state(state_file)
    return state.get("date") == date.today().isoformat()
