#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Merge NextLens module help entries into shared BMad module-help.csv."""

from __future__ import annotations

import argparse
import csv
import json
from io import StringIO
from pathlib import Path

HEADER = [
    "module",
    "skill",
    "display-name",
    "menu-code",
    "description",
    "action",
    "args",
    "phase",
    "after",
    "before",
    "required",
    "output-location",
    "outputs",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge module help entries into _bmad/module-help.csv.")
    parser.add_argument("--target", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--legacy-dir")
    parser.add_argument("--module-code")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def read_csv(path: str) -> tuple[list[str], list[list[str]]]:
    file_path = Path(path)
    if not file_path.exists():
        return [], []
    with file_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(StringIO(handle.read())))
    if not rows:
        return [], []
    return rows[0], rows[1:]


def write_csv(path: str, header: list[str], rows: list[list[str]]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def cleanup_legacy_csvs(legacy_dir: str | None, module_code: str | None) -> list[str]:
    if not legacy_dir or not module_code:
        return []
    deleted: list[str] = []
    for subdir in (module_code, "core"):
        path = Path(legacy_dir) / subdir / "module-help.csv"
        if path.exists():
            path.unlink()
            deleted.append(str(path))
    return deleted


def _row_skill(row: list[str]) -> str:
    return row[1].strip() if len(row) > 1 else ""


def _legacy_row_module_code(row: list[str]) -> str:
    return row[0].strip() if len(row) == 5 else ""


def main() -> int:
    args = parse_args()
    source_header, source_rows = read_csv(args.source)
    if source_header != HEADER:
        raise ValueError("source CSV header does not match BMad module-help schema")
    if not source_rows:
        raise ValueError("source CSV has no entries")

    module_names = {row[0].strip() for row in source_rows if row and row[0].strip()}
    skills = {_row_skill(row) for row in source_rows if _row_skill(row)}
    legacy_module_codes = {args.module_code} if args.module_code else set()
    target_header, target_rows = read_csv(args.target)
    header = target_header or source_header
    if header != HEADER:
        header = HEADER

    filtered_rows = [
        row
        for row in target_rows
        if not row
        or (row[0].strip() not in module_names and _row_skill(row) not in skills and _legacy_row_module_code(row) not in legacy_module_codes)
    ]
    removed_count = len(target_rows) - len(filtered_rows)
    merged_rows = filtered_rows + source_rows
    write_csv(args.target, header, merged_rows)

    legacy_deleted = cleanup_legacy_csvs(args.legacy_dir, args.module_code)
    print(json.dumps({
        "status": "success",
        "target_path": str(Path(args.target).resolve()),
        "module_names": sorted(module_names),
        "skills": sorted(skills),
        "legacy_module_codes": sorted(legacy_module_codes),
        "rows_removed": removed_count,
        "rows_added": len(source_rows),
        "total_rows": len(merged_rows),
        "legacy_csvs_deleted": legacy_deleted,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI safety
        print(f"Error: {exc}")
        raise SystemExit(2)