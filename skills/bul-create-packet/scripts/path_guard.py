#!/usr/bin/env python3
"""Path guard for Bottom-Up LENS write-capable workflows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DENIED_CATEGORIES: dict[str, tuple[str, ...]] = {
    "git": (".git",),
    "governance": ("governance", "lens-governance", "lens.core.governance", "governance-mirror"),
    "release": ("release", "release-clone", "release-clones"),
    "landscape": ("landscape", "living-landscape"),
    "graph": ("graph", "derived-graph", "derivedgraph"),
    "salmon": ("salmon",),
    "promotion": ("promotion", "promote", "promoted"),
    "adjacency": ("adjacency", "adjacent"),
    "pressure": ("pressure",),
    "roadmap": ("roadmap",),
    "lens-lifecycle-metadata": ("feature.yaml", "feature-yaml", "sprint-status.yaml", "dev-session.yaml"),
    "service-domain-program-truth": ("service.yaml", "domain.yaml", "program.yaml", "services", "domains", "programs"),
    "top-down-runtime": ("bmad-nextlens", "bmad-nextlens-doctor", "bmad-nextlens-salmon", "nextlens-top-down", "nextlens-doctor", "nextlens-salmon"),
    "control-github": (".github",),
}

COMPOUND_MARKERS = {
    "derived-graph",
    "derivedgraph",
    "lens.core.governance",
    "governance-mirror",
    "release-clone",
    "release-clones",
    "living-landscape",
    "bmad-nextlens",
    "bmad-nextlens-doctor",
    "bmad-nextlens-salmon",
    "top-down-runtime",
    "nextlens-top-down",
    "nextlens-doctor",
    "nextlens-salmon",
}


def _error(category: str, field: str, message: str, recommendation: str, path: str | None = None) -> dict[str, str]:
    result = {
        "category": category,
        "field": field,
        "message": message,
        "recommendation": recommendation,
    }
    if path is not None:
        result["path"] = path
    return result


def _resolve(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def denied_category_for(path: Path) -> str | None:
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    stem = path.stem.lower()
    normalized = str(path).lower().replace("\\", "/")
    for category, markers in DENIED_CATEGORIES.items():
        for marker in markers:
            marker_l = marker.lower()
            if marker_l in parts or marker_l == name or marker_l == stem:
                return category
            if marker_l in COMPOUND_MARKERS and marker_l in normalized:
                return category
    return None


def guard_path(path: str | Path, allowed_roots: list[str | Path], field: str = "path") -> dict[str, Any]:
    resolved_path = _resolve(path)
    resolved_roots = [_resolve(root) for root in allowed_roots]

    denied = denied_category_for(resolved_path)
    if denied:
        return {
            "status": "fail",
            "pathGuard": _error(
                denied,
                field,
                f"Path is denied by Bottom-Up LENS write boundary category: {denied}.",
                "Choose a path under packet_output_path or reports_output_path that does not contain governance, release, topology, runtime, or metadata surfaces.",
                str(resolved_path),
            ),
            "normalizedPath": str(resolved_path),
            "allowedRoots": [str(root) for root in resolved_roots],
        }

    for root in resolved_roots:
        if _is_relative_to(resolved_path, root):
            return {
                "status": "pass",
                "pathGuard": {
                    "category": "allowed-root",
                    "field": field,
                    "message": "Path is contained by a configured Bottom-Up LENS output root.",
                    "recommendation": "Proceed only after validation and confirmation gates pass.",
                    "path": str(resolved_path),
                },
                "normalizedPath": str(resolved_path),
                "matchedRoot": str(root),
                "allowedRoots": [str(candidate) for candidate in resolved_roots],
            }

    return {
        "status": "fail",
        "pathGuard": _error(
            "outside-allowed-roots",
            field,
            "Path is outside configured Bottom-Up LENS output roots.",
            "Use packet_output_path or reports_output_path from module config; do not infer paths from branch, editor, or cwd.",
            str(resolved_path),
        ),
        "normalizedPath": str(resolved_path),
        "allowedRoots": [str(root) for root in resolved_roots],
    }


def guard_write_plan(paths: list[str | Path], allowed_roots: list[str | Path], field_prefix: str = "plannedWrites") -> dict[str, Any]:
    checks = [guard_path(path, allowed_roots, f"{field_prefix}[{index}]") for index, path in enumerate(paths)]
    failures = [check for check in checks if check["status"] != "pass"]
    return {
        "status": "pass" if not failures else "fail",
        "checks": checks,
        "failures": failures,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guard Bottom-Up LENS planned write paths.")
    parser.add_argument("--path", action="append", required=True)
    parser.add_argument("--allowed-root", action="append", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = guard_write_plan(args.path, args.allowed_root)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
