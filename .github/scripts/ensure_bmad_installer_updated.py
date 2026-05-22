#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath


REQUIRED_INSTALLER_FILES = {
    "_bmad/_config/skill-manifest.csv",
    "_bmad/_config/files-manifest.csv",
}


@dataclass(frozen=True)
class DiffEntry:
    status: str
    path: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fail when a new skill is added without updating BMAD installer manifests."
        )
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Git ref used as merge base for diff detection.",
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


def main() -> int:
    args = parse_args()

    try:
        entries = read_diff(args.base_ref)
    except RuntimeError as error:
        print(f"::error::{error}")
        return 2

    added_skill_files = sorted(
        entry.path for entry in entries if entry.status == "A" and is_new_skill_file(entry.path)
    )

    if not added_skill_files:
        print("No new skills detected in diff.")
        return 0

    changed_paths = {entry.path for entry in entries}
    missing_required = sorted(REQUIRED_INSTALLER_FILES - changed_paths)

    if not missing_required:
        print("New skills detected and BMAD installer manifests were updated.")
        return 0

    print("::error::New skills were added but BMAD installer manifests were not fully updated.")
    print("Added skills:")
    for path in added_skill_files:
        print(f"  - {path}")

    print("Required manifest updates missing:")
    for path in missing_required:
        print(f"  - {path}")

    print("Run the BMAD installer update flow and commit regenerated _bmad/_config manifests.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
