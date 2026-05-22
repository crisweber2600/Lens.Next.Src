#!/usr/bin/env python3
"""Generate deterministic fix-spec payload for NextLens bugfix flow."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


DEFAULT_WRITE_ROOT = "TargetProjects/lens.next.src"


def slugify(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    if not words:
        return "unspecified"
    return "-".join(words[:8])


def read_context_feature_id(project_root: Path) -> str:
    context_path = project_root / ".lens" / "personal" / "context.yaml"
    if not context_path.exists():
        return ""
    for raw_line in context_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("feature_id:"):
            return line.split(":", 1)[1].strip()
    return ""


def discover_single_feature(project_root: Path) -> str:
    features_root = project_root / "docs" / "features"
    if not features_root.exists():
        return ""
    candidates = [
        child.name
        for child in features_root.iterdir()
        if child.is_dir() and (child / "feature.yaml").exists()
    ]
    if len(candidates) == 1:
        return candidates[0]
    return ""


def resolve_feature_id(project_root: Path, provided: str) -> str:
    if provided:
        return provided
    from_context = read_context_feature_id(project_root)
    if from_context:
        return from_context
    return discover_single_feature(project_root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate NextLens bugfix spec payload.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--feature-id", default="")
    parser.add_argument("--what-happened", required=True)
    parser.add_argument("--what-should-have-happened", required=True)
    parser.add_argument("--chat-history", required=True)
    parser.add_argument("--allowed-write-root", default=DEFAULT_WRITE_ROOT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    project_root = Path(args.project_root).resolve()
    allowed_root = (project_root / args.allowed_write_root).resolve()

    blockers: list[str] = []
    feature_id = resolve_feature_id(project_root, args.feature_id)
    if not feature_id:
        blockers.append("missing_feature_context")

    if not args.what_happened.strip():
        blockers.append("missing_what_happened")
    if not args.what_should_have_happened.strip():
        blockers.append("missing_what_should_have_happened")
    if not args.chat_history.strip():
        blockers.append("missing_chat_history")

    if not allowed_root.exists():
        blockers.append("allowed_write_root_missing")

    if project_root not in [allowed_root, *allowed_root.parents]:
        blockers.append("allowed_write_root_outside_project")

    bug_slug = slugify(args.what_happened)
    bugfix_feature_id = f"nextlens-bugfix-{bug_slug}"
    working_branch = f"feature/{bugfix_feature_id}"

    bug_artifact_path = ""
    if feature_id:
        bug_artifact_path = (
            f"docs/features/{feature_id}/bugs/nextlens/Open/{bug_slug}.md"
        )

    payload = {
        "bug_slug": bug_slug,
        "feature_id": feature_id,
        "bug_artifact_path": bug_artifact_path,
        "bug_reporter_fields": {
            "title": args.what_happened.strip()[:120],
            "what_happened": args.what_happened.strip(),
            "what_should_have_happened": args.what_should_have_happened.strip(),
            "chat_history": args.chat_history.strip(),
        },
        "bugfix_feature_id": bugfix_feature_id,
        "bugfix_feature_slug": bugfix_feature_id,
        "bugfix_working_branch": working_branch,
        "allowed_write_root": str(allowed_root),
        "allowed_write_root_display": args.allowed_write_root,
        "delegation_blocked": bool(blockers),
        "delegation_blockers": blockers,
    }

    print(json.dumps(payload, indent=2))
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
