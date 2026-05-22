#!/usr/bin/env python3
"""Execute clean-room NextLens bugfix conductor prepare and close gates."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_command(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)


def fail(code: str, message: str, details: dict | None = None) -> int:
    payload = {"status": "blocked", "code": code, "message": message}
    if details:
        payload.update(details)
    print(json.dumps(payload, indent=2))
    return 1


def parse_json_output(result: subprocess.CompletedProcess[str], context: str) -> dict:
    if result.returncode != 0:
        raise RuntimeError(f"{context} failed: {result.stderr.strip() or result.stdout.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{context} did not return JSON") from exc


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run_command(["git", "-C", str(repo), *args])


def is_clean_worktree(repo: Path) -> bool:
    result = git(repo, "status", "--porcelain")
    return result.returncode == 0 and not result.stdout.strip()


def current_branch(repo: Path) -> str:
    result = git(repo, "branch", "--show-current")
    return result.stdout.strip() if result.returncode == 0 else ""


def rev_parse(repo: Path, rev: str = "HEAD") -> str:
    result = git(repo, "rev-parse", rev)
    return result.stdout.strip() if result.returncode == 0 else ""


def branch_exists(repo: Path, branch: str) -> bool:
    result = git(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}")
    return result.returncode == 0


def changed_files_since(repo: Path, starting_head: str) -> list[str]:
    result = git(repo, "diff", "--name-only", f"{starting_head}..HEAD")
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def all_files_within(files: list[str], repo: Path, allowed_root: Path) -> bool:
    for rel in files:
        candidate = (repo / rel).resolve()
        if allowed_root not in [candidate, *candidate.parents]:
            return False
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NextLens bugfix conductor.")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--project-root", default=".")
    prepare.add_argument("--feature-id", default="")
    prepare.add_argument("--repo", default="TargetProjects/lens.next.src")
    prepare.add_argument("--what-happened", required=True)
    prepare.add_argument("--what-should-have-happened", required=True)
    prepare.add_argument("--chat-history", required=True)

    close = sub.add_parser("close")
    close.add_argument("--project-root", default=".")
    close.add_argument("--repo", default="TargetProjects/lens.next.src")
    close.add_argument("--bug-slug", required=True)
    close.add_argument("--working-branch", required=True)
    close.add_argument("--base-branch", required=True)
    close.add_argument("--starting-head", required=True)
    close.add_argument("--allowed-write-root", required=True)
    close.add_argument("--summary", required=True)
    close.add_argument("--validation-summary", required=True)
    close.add_argument("--doctor-status", required=True, choices=["passed", "deferred", "not-applicable"])
    close.add_argument("--doctor-evidence", default="")
    close.add_argument("--doctor-rationale", default="")
    close.add_argument("--pr-url", default="")
    close.add_argument("--skip-push", action="store_true")

    return parser


def cmd_prepare(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    repo = (project_root / args.repo).resolve()

    if not repo.exists():
        return fail("repo_not_found", f"Target repo not found: {repo.as_posix()}")

    if not is_clean_worktree(repo):
        return fail("dirty_working_tree", "Target repository has uncommitted changes.")

    fix_spec_cmd = [
        sys.executable,
        str(project_root / "skills" / "lens-nextlens-bugfix" / "scripts" / "nextlens_fix_spec.py"),
        "--project-root",
        str(project_root),
        "--feature-id",
        args.feature_id,
        "--what-happened",
        args.what_happened,
        "--what-should-have-happened",
        args.what_should_have_happened,
        "--chat-history",
        args.chat_history,
    ]
    spec_result = run_command(fix_spec_cmd)
    try:
        spec = json.loads(spec_result.stdout)
    except json.JSONDecodeError:
        return fail("fix_spec_invalid", "nextlens_fix_spec did not return JSON")

    if spec_result.returncode != 0 or spec.get("delegation_blocked"):
        return fail(
            "delegation_blocked",
            "Fix spec blocked delegation.",
            {"delegation_blockers": spec.get("delegation_blockers", [])},
        )

    working_branch = spec["bugfix_working_branch"]
    if not working_branch.startswith("feature/nextlens-bugfix-"):
        return fail("branch_scope_mismatch", "Working branch does not match required prefix.")

    create_bug_cmd = [
        sys.executable,
        str(project_root / "skills" / "lens-nextlens-bugfix" / "scripts" / "bug_reporter_ops.py"),
        "create-bug",
        "--project-root",
        str(project_root),
        "--feature-id",
        spec["feature_id"],
        "--slug",
        spec["bug_slug"],
        "--title",
        spec["bug_reporter_fields"]["title"],
        "--what-happened",
        spec["bug_reporter_fields"]["what_happened"],
        "--what-should-have-happened",
        spec["bug_reporter_fields"]["what_should_have_happened"],
        "--chat-history",
        spec["bug_reporter_fields"]["chat_history"],
        "--namespace",
        "nextlens",
    ]
    create_result = run_command(create_bug_cmd)
    if create_result.returncode != 0:
        return fail("bug_create_failed", create_result.stderr.strip() or create_result.stdout.strip())

    base_branch = current_branch(repo)
    reused = branch_exists(repo, working_branch)
    if reused:
        checkout = git(repo, "checkout", working_branch)
    else:
        checkout = git(repo, "checkout", "-b", working_branch)

    if checkout.returncode != 0:
        return fail("branch_checkout_failed", checkout.stderr.strip() or checkout.stdout.strip())

    starting_head = rev_parse(repo, "HEAD")

    payload = {
        "status": "ok",
        "bug_slug": spec["bug_slug"],
        "feature_id": spec["feature_id"],
        "working_branch": working_branch,
        "base_branch": base_branch,
        "starting_head": starting_head,
        "allowed_write_root": spec["allowed_write_root"],
        "bug_artifact_path": spec["bug_artifact_path"],
        "reused": reused,
    }
    print(json.dumps(payload, indent=2))
    return 0


def create_or_reuse_pr(repo: Path, base_branch: str, working_branch: str, pr_title: str, pr_body: str) -> tuple[str, str]:
    view = run_command(["gh", "pr", "view", "--json", "url"], cwd=repo)
    if view.returncode == 0:
        try:
            data = json.loads(view.stdout)
            url = str(data.get("url", "")).strip()
            if url:
                return url, "existing"
        except json.JSONDecodeError:
            pass

    create = run_command(
        [
            "gh",
            "pr",
            "create",
            "--base",
            base_branch,
            "--head",
            working_branch,
            "--title",
            pr_title,
            "--body",
            pr_body,
        ],
        cwd=repo,
    )
    if create.returncode != 0:
        return "", create.stderr.strip() or create.stdout.strip()
    return create.stdout.strip().splitlines()[-1].strip(), "created"


def cmd_close(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    repo = (project_root / args.repo).resolve()
    allowed_root = Path(args.allowed_write_root).resolve()

    if current_branch(repo) != args.working_branch:
        return fail("branch_scope_mismatch", "Repository is not on expected working branch.")

    if not is_clean_worktree(repo):
        return fail("dirty_working_tree", "Target repository has uncommitted changes.")

    commit_hash = rev_parse(repo, "--short HEAD")
    full_head = rev_parse(repo, "HEAD")

    if full_head == args.starting_head:
        return fail("bugfix_no_changes", "No new commit detected since branch preparation.")

    changed_files = changed_files_since(repo, args.starting_head)
    if not changed_files:
        return fail("bugfix_no_changes", "No files changed since starting head.")

    if not all_files_within(changed_files, repo, allowed_root):
        return fail("target_boundary_violation", "Changed files escape allowed write root.")

    pr_url = args.pr_url.strip()
    if not args.skip_push:
        push = git(repo, "push", "-u", "origin", args.working_branch)
        if push.returncode != 0:
            return fail("push_failed", push.stderr.strip() or push.stdout.strip())

        verify_remote = git(repo, "ls-remote", "--heads", "origin", args.working_branch)
        if verify_remote.returncode != 0 or not verify_remote.stdout.strip():
            return fail("push_failed", "Remote branch not found after push.")

        if not pr_url:
            pr_url, _ = create_or_reuse_pr(
                repo,
                args.base_branch,
                args.working_branch,
                f"fix(nextlens): {args.bug_slug}",
                args.validation_summary,
            )

    if not pr_url:
        return fail("pr_creation_failed", "PR URL is required and could not be created.")

    record_pr = run_command(
        [
            sys.executable,
            str(project_root / "skills" / "lens-nextlens-bugfix" / "scripts" / "bug_reporter_ops.py"),
            "record-quickdev-pr",
            "--project-root",
            str(project_root),
            "--slug",
            args.bug_slug,
            "--pr-url",
            pr_url,
            "--namespace",
            "nextlens",
        ]
    )
    if record_pr.returncode != 0:
        return fail("record_pr_failed", record_pr.stderr.strip() or record_pr.stdout.strip())

    close_bug = run_command(
        [
            sys.executable,
            str(project_root / "skills" / "lens-nextlens-bugfix" / "scripts" / "bug_reporter_ops.py"),
            "close-quickdev-bug",
            "--project-root",
            str(project_root),
            "--slug",
            args.bug_slug,
            "--summary",
            args.summary,
            "--validation-summary",
            args.validation_summary,
            "--namespace",
            "nextlens",
            "--doctor-status",
            args.doctor_status,
            "--doctor-evidence",
            args.doctor_evidence,
            "--doctor-rationale",
            args.doctor_rationale,
        ]
    )
    if close_bug.returncode != 0:
        return fail("bug_close_failed", close_bug.stderr.strip() or close_bug.stdout.strip())

    close_payload = json.loads(close_bug.stdout)

    payload = {
        "status": "ok",
        "bug_slug": args.bug_slug,
        "working_branch": args.working_branch,
        "base_branch": args.base_branch,
        "commit_hash": commit_hash,
        "PR URL": pr_url,
        "bug_artifact_path": close_payload.get("path", ""),
        "changed_files": changed_files,
        "validation_summary": args.validation_summary,
        "doctor": {
            "status": args.doctor_status,
            "evidence": args.doctor_evidence,
            "rationale": args.doctor_rationale,
        },
    }
    print(json.dumps(payload, indent=2))
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "prepare":
        return cmd_prepare(args)
    if args.command == "close":
        return cmd_close(args)
    return fail("unknown_command", "Unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
