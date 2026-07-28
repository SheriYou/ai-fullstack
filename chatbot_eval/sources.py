"""Knowledge-base source adapters."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _run_lark(args: list[str]) -> dict:
    executable = shutil.which("lark-cli") or shutil.which("lark-cli.cmd") or shutil.which("lark-cli.exe")
    if not executable:
        raise RuntimeError("lark-cli not found in PATH")
    result = subprocess.run(
        [executable, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    output = (result.stdout or result.stderr).strip()
    try:
        data = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"lark-cli returned non-JSON output: {output[:500]}") from exc
    if not data.get("ok", False):
        error = data.get("error") or {}
        hint = error.get("hint") or data.get("message") or output[:500]
        raise RuntimeError(f"lark-cli failed: {hint}")
    return data


def _resolve_base_url(url: str) -> tuple[str, str, str | None]:
    data = _run_lark(["base", "+url-resolve", "--url", url, "--as", "user"])
    payload = data.get("data") or {}
    base_token = payload.get("base_token")
    table_id = payload.get("table_id")
    view_id = payload.get("view_id")
    if not base_token or not table_id:
        raise RuntimeError(f"unable to resolve base url: {payload}")
    return base_token, table_id, view_id


def _cell_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(_cell_to_text(item) for item in value if _cell_to_text(item))
    if isinstance(value, dict):
        for key in ("text", "name", "value", "link", "url"):
            if key in value:
                return _cell_to_text(value[key])
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _extract_records(envelope: dict) -> tuple[list[dict[str, str]], bool]:
    data = envelope.get("data") or {}
    if isinstance(data.get("fields"), list) and isinstance(data.get("data"), list):
        fieldnames = [str(field) for field in data["fields"]]
        rows: list[dict[str, str]] = []
        for raw_row in data["data"]:
            if not isinstance(raw_row, list):
                continue
            rows.append(
                {
                    fieldname: _cell_to_text(raw_row[index] if index < len(raw_row) else "")
                    for index, fieldname in enumerate(fieldnames)
                }
            )
        return rows, bool(data.get("has_more"))

    raw_records = data.get("items") or data.get("records") or []
    records: list[dict[str, str]] = []
    for raw in raw_records:
        fields = raw.get("fields") if isinstance(raw, dict) else None
        if not isinstance(fields, dict):
            continue
        records.append({str(key): _cell_to_text(value) for key, value in fields.items()})
    return records, bool(data.get("has_more"))


def export_feishu_base_to_csv(
    url: str,
    out_csv: str | Path,
    *,
    limit: int = 200,
) -> Path:
    """Export a Feishu Base view/table to a local CSV using lark-cli."""
    base_token, table_id, view_id = _resolve_base_url(url)
    out_path = Path(out_csv)
    all_rows: list[dict[str, str]] = []
    offset = 0
    while True:
        args = [
            "base",
            "+record-list",
            "--base-token",
            base_token,
            "--table-id",
            table_id,
            "--limit",
            str(limit),
            "--offset",
            str(offset),
            "--format",
            "json",
            "--as",
            "user",
        ]
        if view_id:
            args.extend(["--view-id", view_id])
        rows, has_more = _extract_records(_run_lark(args))
        all_rows.extend(rows)
        if not has_more or not rows:
            break
        offset += len(rows)

    if not all_rows:
        raise RuntimeError("Feishu Base returned no records")

    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in all_rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    return out_path
