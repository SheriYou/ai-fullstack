#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试 run 路径解析与 reports 根目录产出物清理。"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

RUN_ID_RE = re.compile(r"^(\d{8})-(\d{6})$")

# reports/ 根目录仅保留静态文档 + latest-run.json；其余执行产出物在 runs/{run_id}/
ROOT_ARTIFACT_GLOBS = (
    "test-run-*.md",
    "test-run-*.docx",
    "test-results-*.csv",
    "test-results-corpus-*.csv",
    "test-run-summary-*.json",
    "test-results-latest.csv",
    "test-results-corpus-latest.csv",
)


def parse_run_id(run_id: str) -> datetime | None:
    m = RUN_ID_RE.match(run_id.strip())
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)}{m.group(2)}", "%Y%m%d%H%M%S")
    except ValueError:
        return None


def list_run_dirs(reports_dir: Path) -> list[tuple[str, datetime, Path]]:
    runs_root = reports_dir / "runs"
    if not runs_root.is_dir():
        return []
    out: list[tuple[str, datetime, Path]] = []
    for p in runs_root.iterdir():
        if not p.is_dir():
            continue
        dt = parse_run_id(p.name)
        if dt:
            out.append((p.name, dt, p))
    out.sort(key=lambda x: x[1], reverse=True)
    return out


def resolve_latest_run(reports_dir: Path) -> tuple[str, Path] | None:
    """返回 (run_id, runs/{run_id})；优先 latest-run.json。"""
    pointer = reports_dir / "latest-run.json"
    if pointer.exists():
        try:
            data = json.loads(pointer.read_text(encoding="utf-8"))
            rid = (data.get("run_id") or "").strip()
            if rid:
                d = reports_dir / "runs" / rid
                if d.is_dir():
                    return rid, d
        except (json.JSONDecodeError, OSError):
            pass
    runs = list_run_dirs(reports_dir)
    if runs:
        return runs[0][0], runs[0][2]
    return None


def resolve_latest_run_id(reports_dir: Path) -> str | None:
    pair = resolve_latest_run(reports_dir)
    return pair[0] if pair else None


def write_latest_pointer(reports_dir: Path, run_id: str, project_root: Path | None = None) -> Path:
    """仅写入 latest-run.json，不在根目录复制 CSV/报告。"""
    reports_dir.mkdir(parents=True, exist_ok=True)
    rel_base = project_root or reports_dir.parent
    pointer = {
        "run_id": run_id,
        "dir": str((reports_dir / "runs" / run_id).relative_to(rel_base)).replace("\\", "/"),
        "report_md": "test-report.md",
        "report_docx": "test-report.docx",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    path = reports_dir / "latest-run.json"
    path.write_text(json.dumps(pointer, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def purge_root_run_artifacts(reports_dir: Path, *, dry_run: bool = False) -> list[str]:
    """删除 reports 根目录下的 run 副本（runs/ 内不动）。"""
    removed: list[str] = []
    if not reports_dir.is_dir():
        return removed
    for pattern in ROOT_ARTIFACT_GLOBS:
        for path in reports_dir.glob(pattern):
            if dry_run:
                removed.append(str(path))
                continue
            try:
                path.unlink()
                removed.append(str(path))
            except OSError:
                pass
    return removed
