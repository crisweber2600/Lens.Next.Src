#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


REQUIRED_INSTALLER_FILES = {
    "_bmad/_config/skill-manifest.csv",
    "_bmad/_config/files-manifest.csv",
}

INSPECTED_SKILL_GLOBS = (
    "skills/*/SKILL.md",
)


@dataclass(frozen=True)
class DiffEntry:
    status: str
    path: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate BMAD installer manifests against both git diff and filesystem state."
        )
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Git ref used as merge base for diff detection.",
    )
    parser.add_argument(
        "--mode",
        choices=("diff", "strict", "both"),
        default="both",
        help="Validation mode. 'diff' checks changed files, 'strict' inspects filesystem, 'both' runs both.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root path used for strict filesystem inspection.",
    )
    return parser.parse_args()


def run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout


def normalize_path(path: str) -> str:
    return str(PurePosixPath(path.replace("\\", "/")))


def read_diff(base_ref: str) -> list[DiffEntry]:
    raw = run_git(["diff", "--name-status", "--find-renames", f"{base_ref}...HEAD"])
    entries: list[DiffEntry] = []

    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue

        status = parts[0]
        if status.startswith("R") and len(parts) >= 3:
            entries.append(DiffEntry(status="A", path=normalize_path(parts[2])))
            continue

        entries.append(DiffEntry(status=status[0], path=normalize_path(parts[1])))

    return entries


def is_new_skill_file(path: str) -> bool:
    # Enforce for top-level custom skills and local agent skills.
    if path.startswith("skills/") and path.endswith("/SKILL.md"):
        return True
    if path.startswith(".agents/skills/") and path.endswith("/SKILL.md"):
        return True
    return False


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def discover_expected_skill_paths(repo_root: Path) -> set[str]:
    paths: set[str] = set()
    for pattern in INSPECTED_SKILL_GLOBS:
        for file_path in repo_root.glob(pattern):
            if file_path.is_file():
                rel = file_path.relative_to(repo_root)
                paths.add(normalize_path(str(rel)))
    return paths


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_diff(entries: list[DiffEntry]) -> int:
    added_skill_files = sorted(
        entry.path for entry in entries if entry.status == "A" and is_new_skill_file(entry.path)
    )

    if not added_skill_files:
        print("[diff] No new skills detected in diff.")
        return 0

    changed_paths = {entry.path for entry in entries}
    missing_required = sorted(REQUIRED_INSTALLER_FILES - changed_paths)

    if not missing_required:
        print("[diff] New skills detected and BMAD installer manifests were updated.")
        return 0

    print("::error::[diff] New skills were added but BMAD installer manifests were not fully updated.")
    print("Added skills:")
    for path in added_skill_files:
        print(f"  - {path}")

    print("Required manifest updates missing:")
    for path in missing_required:
        print(f"  - {path}")

    return 1


def validate_strict(repo_root: Path) -> int:
    skill_manifest_path = repo_root / "_bmad/_config/skill-manifest.csv"
    files_manifest_path = repo_root / "_bmad/_config/files-manifest.csv"

    expected_paths = discover_expected_skill_paths(repo_root)
    skill_rows = load_csv_rows(skill_manifest_path)
    file_rows = load_csv_rows(files_manifest_path)

    manifest_skill_paths = {
        normalize_path(row["path"])
        for row in skill_rows
        if normalize_path(row.get("path", "")).startswith("skills/")
        and normalize_path(row.get("path", "")).endswith("/SKILL.md")
    }

    files_manifest_index = {
        normalize_path(row["path"]): row.get("hash", "")
        for row in file_rows
        if normalize_path(row.get("path", "")).startswith("skills/")
        and normalize_path(row.get("path", "")).endswith("/SKILL.md")
    }

    missing_in_skill_manifest = sorted(expected_paths - manifest_skill_paths)
    missing_on_disk = sorted(manifest_skill_paths - expected_paths)
    missing_in_files_manifest = sorted(expected_paths - set(files_manifest_index.keys()))

    hash_mismatch: list[str] = []
    for rel_path in sorted(expected_paths):
        expected_hash = files_manifest_index.get(rel_path)
        if not expected_hash:
            continue
        actual_hash = sha256(repo_root / rel_path)
        if actual_hash != expected_hash:
            hash_mismatch.append(rel_path)

    failures = []
    if missing_in_skill_manifest:
        failures.append(("missing_in_skill_manifest", missing_in_skill_manifest))
    if missing_on_disk:
        failures.append(("missing_on_disk", missing_on_disk))
    if missing_in_files_manifest:
        failures.append(("missing_in_files_manifest", missing_in_files_manifest))
    if hash_mismatch:
        failures.append(("hash_mismatch", hash_mismatch))

    if not failures:
        print(f"[strict] Validated {len(expected_paths)} skills from filesystem against installer manifests.")
        return 0

    print("::error::[strict] BMAD installer manifest validation failed.")
    for category, paths in failures:
        print(f"{category}:")
        for path in paths:
            print(f"  - {path}")
    return 1


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()

    status = 0
    if args.mode in {"diff", "both"}:
        try:
            entries = read_diff(args.base_ref)
        except RuntimeError as error:
            print(f"::error::{error}")
            return 2
        status = max(status, validate_diff(entries))

    if args.mode in {"strict", "both"}:
        status = max(status, validate_strict(repo_root))

    if status != 0:
        print("Run the BMAD installer update flow and commit regenerated _bmad/_config manifests.")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
