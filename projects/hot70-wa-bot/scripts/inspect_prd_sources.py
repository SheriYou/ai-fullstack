# -*- coding: utf-8 -*-
"""Inspect all prd/*.xlsx and write UTF-8 sources.json + CSV snapshots."""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRD = ROOT / "prd"
OUT = ROOT / "data" / "faq-export"
OUT.mkdir(parents=True, exist_ok=True)


def df_to_records(df):
    return df.fillna("").to_dict(orient="records")


def main():
    summary = {}
    for path in sorted(PRD.glob("*.xlsx")):
        xl = pd.ExcelFile(path)
        key = path.stem
        summary[key] = {"file": path.name, "sheets": xl.sheet_names, "data": {}}
        for sheet in xl.sheet_names:
            df = pd.read_excel(path, sheet_name=sheet)
            summary[key]["data"][sheet] = {
                "columns": [str(c) for c in df.columns],
                "rows": df_to_records(df),
            }
        safe = key.replace(" ", "_")
        pd.read_excel(path, sheet_name=xl.sheet_names[0]).to_csv(
            OUT / f"{safe}.csv", index=False, encoding="utf-8-sig"
        )
    meta = {
        "files": [p.name for p in sorted(PRD.glob("*.xlsx"))],
        "workbooks": summary,
    }
    (OUT / "sources.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"OK -> {OUT / 'sources.json'} ({len(meta['files'])} xlsx)")


if __name__ == "__main__":
    main()
