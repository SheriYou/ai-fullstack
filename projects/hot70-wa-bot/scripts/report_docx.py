#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Markdown 测试报告 → Word (.docx)。"""
from __future__ import annotations

import sys
from pathlib import Path


def _load_converter():
    here = Path(__file__).resolve()
    candidates = [
        here.parent / "md_to_docx.py",
        here.parents[4] / "docs" / "scripts" / "md_to_docx.py",
    ]
    for path in candidates:
        if path.exists():
            import importlib.util

            spec = importlib.util.spec_from_file_location("md_to_docx", path)
            mod = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(mod)
            return mod.convert_md_to_docx
    raise ImportError("md_to_docx.py not found; copy from docs/scripts or install python-docx")


def md_to_docx(md_path: Path, docx_path: Path) -> Path:
    convert = _load_converter()
    docx_path.parent.mkdir(parents=True, exist_ok=True)
    convert(md_path.resolve(), docx_path.resolve())
    return docx_path


def main():
    if len(sys.argv) < 2:
        print("usage: python report_docx.py <input.md> [-o output.docx]", file=sys.stderr)
        raise SystemExit(1)
    src = Path(sys.argv[1]).resolve()
    dst = Path(sys.argv[3]).resolve() if len(sys.argv) >= 4 and sys.argv[2] == "-o" else src.with_suffix(".docx")
    out = md_to_docx(src, dst)
    print(f"OK: {src} -> {out}")


if __name__ == "__main__":
    main()
