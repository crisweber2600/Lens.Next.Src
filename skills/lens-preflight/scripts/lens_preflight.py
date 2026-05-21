#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Lens-owned preflight checks and optional Lens context discovery."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


DEFAULT_WORK_INTAKE_PATH = "docs/features"
DEFAULT_FEATURE_ARCHIVE_PATH = "docs/features"
DEFAULT_LANDSCAPE_ROOT = "docs"
DEFAULT_REPORTING_OUTPUT_PATH = "_bmad-output/lens"


def parse_scalar(raw_value: str):
    value = raw_value.strip()
    if not value:
        return ""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def read_simple_mapping(path: Path) -> dict:
    if not path.exists():
        return {}
    result: dict[str, object] = {}
    current_parent: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if indent == 0:
            current_parent = key if not value.strip() else None
            result[key] = {} if current_parent else parse_scalar(value)
            continue
        if current_parent:
            parent = result.setdefault(current_parent, {})
            if isinstance(parent, dict):
                parent[key] = parse_scalar(value)
    return result


def resolve_path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path_value = value
    if path_value.startswith("{project-root}/"):
        path_value = path_value.removeprefix("{project-root}/")
    path = Path(path_value)
    if path.is_absolute():
        return path
    return root / path


def rel_or_abs(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def finding(severity: str, code: str, path: Path | None, problem: str, fix: str) -> dict:
    return {
        "severity": severity,
        "code": code,
        "path": path.as_posix() if path else "",
        "problem": problem,
        "recommended_fix": fix,
    }


def detect_lens_contract(root: Path, args: argparse.Namespace) -> dict:
    lifecycle_candidates = [
        resolve_path(root, args.lens_lifecycle_contract),
        root / "lens.core" / "_bmad" / "lens-work" / "lifecycle.yaml",
        root / "_bmad" / "lens-work" / "lifecycle.yaml",
    ]
    lifecycle_path = next(
        (candidate for candidate in lifecycle_candidates if candidate and candidate.exists()),
        None,
    )
    agents_path = root / "lens.core" / "AGENTS.md"
    governance_setup_path = root / ".lens" / "governance-setup.yaml"
    context_path = resolve_path(root, args.lens_context_path) or root / ".lens" / "personal" / "context.yaml"
    governance_setup = read_simple_mapping(governance_setup_path)
    context = read_simple_mapping(context_path)
    docs = context.get("docs") if isinstance(context.get("docs"), dict) else {}
    explicit_governance = args.lens_governance_repo_path or str(
        governance_setup.get("governance_repo_path")
        or governance_setup.get("governance_path")
        or ""
    )
    governance_repo_path = resolve_path(root, explicit_governance)
    detected = bool(
        args.lens_enabled
        or lifecycle_path
        or agents_path.exists()
        or governance_setup_path.exists()
        or context_path.exists()
    )
    return {
        "detected": detected,
        "requested": bool(args.lens_enabled),
        "agents_contract_path": agents_path.as_posix() if agents_path.exists() else "",
        "lifecycle_contract_path": lifecycle_path.as_posix() if lifecycle_path else "",
        "governance_setup_path": governance_setup_path.as_posix()
        if governance_setup_path.exists()
        else "",
        "governance_repo_path": governance_repo_path.as_posix()
        if governance_repo_path
        else "",
        "governance_repo_ready": bool(governance_repo_path and governance_repo_path.exists()),
        "context_path": context_path.as_posix() if context_path.exists() else "",
        "feature_id": str(context.get("feature_id") or context.get("featureId") or ""),
        "track": str(context.get("track") or ""),
        "phase": str(context.get("phase") or ""),
        "docs_path": str(
            context.get("docs_path")
            or context.get("docsPath")
            or docs.get("path")
            or ""
        ),
    }


def validate_project_paths(root: Path, args: argparse.Namespace) -> tuple[dict, list[dict], list[dict]]:
    blocking: list[dict] = []
    advisory: list[dict] = []
    paths = {
        "work_intake_path": resolve_path(root, args.work_intake_path),
        "feature_archive_path": resolve_path(root, args.feature_archive_path),
        "landscape_root": resolve_path(root, args.landscape_root),
        "reporting_output_path": resolve_path(root, args.reporting_output_path),
        "metadata_schema_path": root / "skills" / "lens-setup" / "assets" / "metadata-schema.md",
    }
    for key in ("work_intake_path", "feature_archive_path", "landscape_root"):
        path = paths[key]
        if path and not path.exists():
            advisory.append(
                finding(
                    "advisory",
                    f"missing_{key}",
                    path,
                    f"Configured `{key}` does not exist yet.",
                    "Create the directory or update Lens config before running source scans.",
                )
            )
    reporting_path = paths["reporting_output_path"]
    if reporting_path and root not in [reporting_path, *reporting_path.parents]:
        blocking.append(
            finding(
                "blocking",
                "reporting_output_outside_project",
                reporting_path,
                "Configured reporting output path is outside the project root.",
                "Use a reporting output path under the project root.",
            )
        )
    metadata_schema_path = paths["metadata_schema_path"]
    if metadata_schema_path and not metadata_schema_path.exists():
        blocking.append(
            finding(
                "blocking",
                "missing_metadata_schema",
                metadata_schema_path,
                "Lens metadata schema was not found.",
                "Restore skills/lens-setup/assets/metadata-schema.md or reinstall Lens.",
            )
        )
    return {
        key: rel_or_abs(path, root) if path else "" for key, path in paths.items()
    }, blocking, advisory


def validate_lens_context(lens: dict) -> tuple[list[dict], list[dict]]:
    blocking: list[dict] = []
    advisory: list[dict] = []
    if lens["requested"] and not lens["detected"]:
        blocking.append(
            finding(
                "blocking",
                "lens_not_detected",
                None,
                "Lens mode was requested but no Lens workspace markers were found.",
                "Run without Lens mode or provide Lens context paths.",
            )
        )
    if not lens["detected"]:
        return blocking, advisory
    if not lens["lifecycle_contract_path"]:
        advisory.append(
            finding(
                "advisory",
                "missing_lens_lifecycle_contract",
                None,
                "Lens markers were found, but no lifecycle contract was discovered.",
                "Provide lens_lifecycle_contract or run through Lens wrappers.",
            )
        )
    if lens["requested"] and not lens["governance_repo_ready"]:
        blocking.append(
            finding(
                "blocking",
                "lens_governance_repo_unavailable",
                None,
                "Lens mode was requested but the governance repo path is missing or unavailable.",
                "Configure lens_governance_repo_path or run Lens preflight first.",
            )
        )
    elif not lens["governance_repo_ready"]:
        advisory.append(
            finding(
                "advisory",
                "lens_governance_repo_unavailable",
                None,
                "Lens was detected, but the governance repo path is missing or unavailable.",
                "Run Lens preflight before relying on governance lifecycle context.",
            )
        )
    return blocking, advisory


def run_preflight(args: argparse.Namespace) -> dict:
    root = args.project_root.resolve()
    paths, path_blocking, path_advisory = validate_project_paths(root, args)
    lens = detect_lens_contract(root, args)
    lens_blocking, lens_advisory = validate_lens_context(lens)
    blocking = path_blocking + lens_blocking
    advisory = path_advisory + lens_advisory
    return {
        "module": "lens",
        "report_type": "preflight",
        "status": "blocked" if blocking else "pass",
        "project_root": root.as_posix(),
        "paths": paths,
        "lens": lens,
        "blocking": blocking,
        "advisory": advisory,
        "blocking_count": len(blocking),
        "advisory_count": len(advisory),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Lens preflight checks and optional Lens context discovery.",
    )
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--work-intake-path", default=DEFAULT_WORK_INTAKE_PATH)
    parser.add_argument("--feature-archive-path", default=DEFAULT_FEATURE_ARCHIVE_PATH)
    parser.add_argument("--landscape-root", default=DEFAULT_LANDSCAPE_ROOT)
    parser.add_argument("--reporting-output-path", default=DEFAULT_REPORTING_OUTPUT_PATH)
    parser.add_argument("--lens-enabled", action="store_true")
    parser.add_argument("--lens-governance-repo-path", default="")
    parser.add_argument("--lens-lifecycle-contract", default="")
    parser.add_argument("--lens-context-path", default="")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = run_preflight(args)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())