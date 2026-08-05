"""Translate the executable test-question column in a cases CSV on demand."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

from .llm_client import chat

DEFAULT_PROFILE_ROOT = Path(__file__).resolve().parents[1] / "profiles" / "hot70"
QUESTION_COLUMN = "测试数据（英文提问）"


def _read_csv(path: Path) -> tuple[list[dict[str, str]], list[str], str]:
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "cp936"):
        try:
            with path.open(encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                return list(reader), list(reader.fieldnames or []), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError(f"unable to read CSV: {path}")


def _default_cases_csv(profile_root: Path) -> Path:
    profile_json = profile_root / "profile.json"
    if profile_json.exists():
        profile = json.loads(profile_json.read_text(encoding="utf-8"))
        return profile_root / profile.get("cases_csv", "data/cases.csv")
    return profile_root / "data" / "Hot70_机器人_知识库指标测试.csv"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "translated"


def _default_output_path(input_path: Path, language: str) -> Path:
    return input_path.with_name(f"{input_path.stem}.{_slug(language)}{input_path.suffix}")


def _chunks(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _json_from_text(text: str) -> Any:
    text = str(text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        raise RuntimeError(f"LLM response is not JSON array: {text[:200]}")
    return json.loads(match.group(0))


def _translate_batch(
    items: list[dict[str, str]],
    *,
    language: str,
    source_language: str,
    profile_root: Path,
) -> dict[str, str]:
    payload = [{"id": item["id"], "text": item["text"]} for item in items]
    content = chat(
        [
            {
                "role": "system",
                "content": (
                    "You translate chatbot test questions for QA execution. "
                    "Translate only the user question text from "
                    f"{source_language} to {language}. Preserve meaning, intent, tone, question form, "
                    "numbers, dates, currency, URLs, IDs, brand/product names, and placeholders. "
                    "Do not add explanations. Return only a JSON array of objects with id and translation. "
                    "Keep HOT 70, HOT 70 Pro, HOT 70 Pro 5G, Infinix, WhatsApp, Palmpay, IBP, IBO unchanged."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
        ],
        project_root=profile_root,
        temperature=0,
    )
    data = _json_from_text(content)
    if not isinstance(data, list):
        raise RuntimeError("LLM translation response must be a JSON array")
    translations: dict[str, str] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id", "")).strip()
        translated = str(item.get("translation") or item.get("translated_text") or item.get("text") or "").strip()
        if item_id and translated:
            translations[item_id] = translated
    missing = [item["id"] for item in items if item["id"] not in translations]
    if missing:
        raise RuntimeError(f"LLM translation response missing ids: {missing[:10]}")
    return translations


def translate_cases(
    *,
    input_path: Path,
    output_path: Path,
    language: str,
    source_language: str,
    profile_root: Path,
    column: str = QUESTION_COLUMN,
    batch_size: int = 20,
    limit: int = 0,
) -> dict[str, Any]:
    rows, fieldnames, encoding = _read_csv(input_path)
    if column not in fieldnames:
        raise RuntimeError(f"cases CSV missing column: {column}")
    targets = [
        {"id": str(index), "text": (row.get(column) or "").strip()}
        for index, row in enumerate(rows)
        if (row.get(column) or "").strip()
    ]
    if limit:
        targets = targets[:limit]
    translations: dict[str, str] = {}
    for batch in _chunks(targets, batch_size):
        translations.update(
            _translate_batch(
                batch,
                language=language,
                source_language=source_language,
                profile_root=profile_root,
            )
        )
        print(f"translated {len(translations)}/{len(targets)}")

    for index, row in enumerate(rows):
        key = str(index)
        if key in translations:
            row[column] = translations[key]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return {
        "input": str(input_path),
        "output": str(output_path),
        "source_encoding": encoding,
        "language": language,
        "column": column,
        "rows": len(rows),
        "translated_rows": len(translations),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Translate the 测试数据（英文提问） column in a cases CSV on demand.",
    )
    parser.add_argument("--profile-root", default=str(DEFAULT_PROFILE_ROOT))
    parser.add_argument("--input", help="Cases CSV. Defaults to profile.json cases_csv.")
    parser.add_argument("--output", help="Output CSV. Defaults to <input>.<language>.csv.")
    parser.add_argument("--language", required=True, help="Target language, e.g. Hausa, Bangla, Arabic.")
    parser.add_argument("--source-language", default="English")
    parser.add_argument("--column", default=QUESTION_COLUMN)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--limit", type=int, default=0, help="Translate only the first N non-empty rows.")
    parser.add_argument("--in-place", action="store_true", help="Overwrite the input CSV.")
    args = parser.parse_args(argv)

    profile_root = Path(args.profile_root)
    input_path = Path(args.input) if args.input else _default_cases_csv(profile_root)
    output_path = input_path if args.in_place else Path(args.output) if args.output else _default_output_path(input_path, args.language)
    summary = translate_cases(
        input_path=input_path,
        output_path=output_path,
        language=args.language,
        source_language=args.source_language,
        profile_root=profile_root,
        column=args.column,
        batch_size=args.batch_size,
        limit=args.limit,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
