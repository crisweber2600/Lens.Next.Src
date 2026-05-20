#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Structural scaffold validator for the Bottom-Up LENS module."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_PATHS = [
    ".claude-plugin/marketplace.json",
    "README.md",
    "LICENSE",
    "skills/bul-setup/SKILL.md",
    "skills/bul-setup/assets/module.yaml",
    "skills/bul-setup/assets/module-help.csv",
    "skills/bul-setup/scripts/merge-config.py",
    "skills/bul-setup/scripts/merge-help-csv.py",
    "skills/bul-setup/scripts/cleanup-legacy.py",
    "skills/bul-create-packet/SKILL.md",
    "skills/bul-validate-packet/SKILL.md",
    "skills/bul-verify-receipt/SKILL.md",
    "evals/bul-create-packet/evals.json",
    "evals/bul-create-packet/triggers.json",
    "evals/bul-validate-packet/evals.json",
    "evals/bul-verify-receipt/evals.json",
]

FORBIDDEN_DEPENDENCY_MARKERS = [
    "publish-to-governance",
    "lens-constitution",
    "lens-git-orchestration",
    "bmad-nextlens/scripts",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the Bottom-Up LENS scaffold surface.")
    parser.add_argument("--repo-root", default=".")
    return parser.parse_args()


def validate(repo_root: Path) -> dict[str, object]:
    missing = [relative_path for relative_path in REQUIRED_PATHS if not (repo_root / relative_path).exists()]
    skill_text = "\n".join(
        (repo_root / relative_path).read_text(encoding="utf-8")
        for relative_path in REQUIRED_PATHS
        if relative_path.endswith("SKILL.md") and (repo_root / relative_path).exists()
    )
    forbidden_hits = [marker for marker in FORBIDDEN_DEPENDENCY_MARKERS if marker in skill_text]
    status = "pass" if not missing and not forbidden_hits else "fail"
    return {
        "status": status,
        "required_paths_checked": REQUIRED_PATHS,
        "missing_paths": missing,
        "forbidden_dependency_markers": forbidden_hits,
    }


def main() -> int:
    result = validate(Path(parse_args().repo_root).resolve())
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
