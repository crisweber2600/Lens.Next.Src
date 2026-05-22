#!/usr/bin/env python3
"""Minimal bug artifact lifecycle helpers for NextLens clean-room bugfix flow."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime(TIMESTAMP_FMT)


def read_context_feature_id(project_root: Path) -> str:
    context_path = project_root / ".lens" / "personal" / "context.yaml"
    if not context_path.exists():
        return ""
    for raw_line in context_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
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
    return provided or read_context_feature_id(project_root) or discover_single_feature(project_root)


def namespace_root(project_root: Path, feature_id: str, namespace: str) -> Path:
    return project_root / "docs" / "features" / feature_id / "bugs" / namespace


def open_bug_path(project_root: Path, feature_id: str, namespace: str, slug: str) -> Path:
    return namespace_root(project_root, feature_id, namespace) / "Open" / f"{slug}.md"


def fixed_bug_path(project_root: Path, feature_id: str, namespace: str, slug: str) -> Path:
    return namespace_root(project_root, feature_id, namespace) / "Fixed" / f"{slug}.md"


def find_bug(project_root: Path, namespace: str, slug: str) -> tuple[str, Path] | tuple[None, None]:
    features_root = project_root / "docs" / "features"
    if not features_root.exists():
        return None, None
    for feature in features_root.iterdir():
        if not feature.is_dir():
            continue
        for state in ("Open", "Fixed"):
            candidate = feature / "bugs" / namespace / state / f"{slug}.md"
            if candidate.exists():
                return feature.name, candidate
    return None, None


def cmd_create_bug(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    feature_id = resolve_feature_id(project_root, args.feature_id)
    if not feature_id:
        print(json.dumps({"status": "error", "error": "missing_feature_context"}, indent=2))
        return 1

    path = open_bug_path(project_root, feature_id, args.namespace, args.slug)
    path.parent.mkdir(parents=True, exist_ok=True)

    reused = path.exists()
    if not reused:
        body = (
            f"# {args.title}\n\n"
            f"- slug: {args.slug}\n"
            f"- namespace: {args.namespace}\n"
            f"- state: open\n"
            f"- created_at: {utc_now()}\n\n"
            "## What Happened\n\n"
            f"{args.what_happened}\n\n"
            "## What Should Have Happened\n\n"
            f"{args.what_should_have_happened}\n\n"
            "## Chat History\n\n"
            f"{args.chat_history}\n"
        )
        path.write_text(body, encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ok",
                "slug": args.slug,
                "feature_id": feature_id,
                "path": path.as_posix(),
                "reused": reused,
            },
            indent=2,
        )
    )
    return 0


def cmd_record_pr(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    feature_id, bug_path = find_bug(project_root, args.namespace, args.slug)
    if not bug_path:
        print(json.dumps({"status": "error", "error": "bug_not_found"}, indent=2))
        return 1

    content = bug_path.read_text(encoding="utf-8")
    marker = "## PR URL"
    block = f"{marker}\n\n{args.pr_url}\n"

    if marker in content:
        before, _, after = content.partition(marker)
        if "## " in after:
            _, next_header, tail = after.partition("## ")
            content = before + block + "## " + next_header + tail
        else:
            content = before + block
    else:
        content = content.rstrip() + "\n\n" + block

    bug_path.write_text(content, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "ok",
                "slug": args.slug,
                "feature_id": feature_id,
                "path": bug_path.as_posix(),
                "pr_url": args.pr_url,
            },
            indent=2,
        )
    )
    return 0


def cmd_close_bug(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    feature_id, bug_path = find_bug(project_root, args.namespace, args.slug)
    if not bug_path:
        print(json.dumps({"status": "error", "error": "bug_not_found"}, indent=2))
        return 1

    if args.doctor_status == "passed" and not args.doctor_evidence.strip():
        print(json.dumps({"status": "error", "error": "missing_doctor_evidence"}, indent=2))
        return 1

    if args.doctor_status in {"deferred", "not-applicable"} and not args.doctor_rationale.strip():
        print(json.dumps({"status": "error", "error": "missing_doctor_rationale"}, indent=2))
        return 1

    fixed_path = fixed_bug_path(project_root, feature_id, args.namespace, args.slug)
    fixed_path.parent.mkdir(parents=True, exist_ok=True)

    existing = bug_path.read_text(encoding="utf-8")
    closeout = (
        "\n\n## QuickDev Closeout\n\n"
        f"- closed_at: {utc_now()}\n"
        f"- summary: {args.summary}\n"
        f"- validation_summary: {args.validation_summary}\n"
        f"- doctor_status: {args.doctor_status}\n"
        f"- doctor_evidence: {args.doctor_evidence}\n"
        f"- doctor_rationale: {args.doctor_rationale}\n"
    )
    fixed_path.write_text(existing.rstrip() + closeout + "\n", encoding="utf-8")

    if bug_path != fixed_path and bug_path.exists():
        bug_path.unlink()

    print(
        json.dumps(
            {
                "status": "ok",
                "slug": args.slug,
                "feature_id": feature_id,
                "path": fixed_path.as_posix(),
            },
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NextLens bug reporter operations.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-bug")
    create.add_argument("--project-root", default=".")
    create.add_argument("--feature-id", default="")
    create.add_argument("--slug", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--what-happened", required=True)
    create.add_argument("--what-should-have-happened", required=True)
    create.add_argument("--chat-history", required=True)
    create.add_argument("--namespace", default="nextlens")
    create.set_defaults(handler=cmd_create_bug)

    record = subparsers.add_parser("record-quickdev-pr")
    record.add_argument("--project-root", default=".")
    record.add_argument("--slug", required=True)
    record.add_argument("--pr-url", required=True)
    record.add_argument("--namespace", default="nextlens")
    record.set_defaults(handler=cmd_record_pr)

    close = subparsers.add_parser("close-quickdev-bug")
    close.add_argument("--project-root", default=".")
    close.add_argument("--slug", required=True)
    close.add_argument("--summary", required=True)
    close.add_argument("--validation-summary", required=True)
    close.add_argument("--namespace", default="nextlens")
    close.add_argument("--doctor-status", required=True, choices=["passed", "deferred", "not-applicable"])
    close.add_argument("--doctor-evidence", default="")
    close.add_argument("--doctor-rationale", default="")
    close.set_defaults(handler=cmd_close_bug)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
