#!/usr/bin/env python3
"""NextLens clean-room constitution operations.

This script ports the Lens constitution resolver into the local NextLens skill
surface. It resolves constitutions from a workspace-local constitution tree,
derives domain/service scope from local feature records and the Two-Tree
authored metadata graph, and exposes the same three core operations as the
Lens source implementation: resolve, check-compliance, and progressive-display.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import tomllib
from pathlib import Path

import yaml


TRACK_NAMES = [
    "standard",
    "express",
    "quickdev",
    "hotfix-express",
    "spike",
    "quickplan",
    "full",
    "hotfix",
    "tech-change",
    "expressplan",
]
VALID_TRACKS = set(TRACK_NAMES)
VALID_GATE_MODES = {"informational", "hard"}
KNOWN_CONSTITUTION_KEYS = frozenset(
    {
        "permitted_tracks",
        "required_artifacts",
        "gate_mode",
        "sensing_gate_mode",
        "additional_review_participants",
        "enforce_stories",
        "enforce_review",
    }
)
LOCAL_PHASE_MAP = {
    "preplan": "planning",
    "businessplan": "planning",
    "techplan": "planning",
    "expressplan": "planning",
    "finalizeplan": "planning",
    "planning": "planning",
    "dev": "dev",
    "complete": "complete",
}
DEFAULTS: dict = {
    "permitted_tracks": list(TRACK_NAMES),
    "required_artifacts": {
        "planning": [],
        "dev": [],
    },
    "gate_mode": "informational",
    "sensing_gate_mode": "informational",
    "additional_review_participants": [],
    "enforce_stories": False,
    "enforce_review": False,
}
DEFAULT_CONSTITUTION_ROOT = Path(".lens") / ".constitution"
GOVERNED_KEYS = {
    "stable_id",
    "entity_type",
    "belongs_to",
    "feature_id",
    "track",
    "phase",
    "work_id",
    "publication_state",
    "promotion_status",
    "salmon_upstream",
}
ARTIFACT_ALIASES = {
    "business-plan": ["business-plan.md", "product-brief.md", "prd.md"],
    "tech-plan": ["tech-plan.md", "architecture.md"],
    "stories": ["stories.md", "stories/*.md"],
}

_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_FM_DELIM = re.compile(r"^---\s*$", re.MULTILINE)


def _validate_slug(value: str, name: str) -> tuple[dict | None, int]:
    if not value or not value.strip():
        return {
            "error": "invalid_slug",
            "field": name,
            "detail": f"'{name}' must not be empty",
        }, 1
    if not _SLUG_RE.match(value):
        return {
            "error": "invalid_slug",
            "field": name,
            "detail": (
                f"'{name}' contains invalid characters — use only alphanumeric, "
                "dots, hyphens, or underscores"
            ),
            "value": value,
        }, 1
    return None, 0


def _assert_within(candidate: Path, base: Path) -> bool:
    try:
        candidate.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _resolve_path(root: Path, raw_value: str | Path) -> Path:
    value = str(raw_value).strip()
    if value.startswith("{project-root}/"):
        value = value.removeprefix("{project-root}/")
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def _read_yaml_mapping(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _read_toml_mapping(path: Path) -> dict:
    if not path.exists():
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _constitution_value_from_mapping(data: dict) -> str:
    if not isinstance(data, dict):
        return ""
    for key in (
        "lens_constitution_root",
        "constitution_root",
        "constitution_path",
    ):
        value = str(data.get(key) or "").strip()
        if value:
            return value

    lens = data.get("lens")
    if isinstance(lens, dict):
        value = _constitution_value_from_mapping(lens)
        if value:
            return value

    modules = data.get("modules")
    if isinstance(modules, dict):
        lens_module = modules.get("lens")
        if isinstance(lens_module, dict):
            value = _constitution_value_from_mapping(lens_module)
            if value:
                return value
    return ""


def _normalize_constitution_root(root: Path, raw_value: str | Path) -> Path:
    return _resolve_path(root, raw_value)


def _resolve_constitution_root(root: Path, feature: dict | None, override: str | None) -> Path:
    if override and str(override).strip():
        return _normalize_constitution_root(root, override)

    if feature:
        for key in ("lens_constitution_root", "constitution_root", "constitution_path"):
            feature_value = str(feature.get(key) or "").strip()
            if feature_value:
                return _normalize_constitution_root(root, feature_value)

    default_root = (root / DEFAULT_CONSTITUTION_ROOT).resolve()
    if default_root.exists():
        return default_root

    for config_path in (
        root / "_bmad" / "config.yaml",
        root / "_bmad" / "config.user.yaml",
    ):
        value = _constitution_value_from_mapping(_read_yaml_mapping(config_path))
        if value:
            return _normalize_constitution_root(root, value)

    for config_path in (
        root / "_bmad" / "config.toml",
        root / "_bmad" / "config.user.toml",
    ):
        value = _constitution_value_from_mapping(_read_toml_mapping(config_path))
        if value:
            return _normalize_constitution_root(root, value)

    return default_root


def _split_frontmatter(text: str) -> tuple[str, str] | None:
    parts = _FM_DELIM.split(text, maxsplit=2)
    if len(parts) < 3 or parts[0].strip():
        return None
    return parts[1], parts[2]


def load_constitution(path: Path) -> dict:
    if not path.exists():
        return {}

    split = _split_frontmatter(path.read_text(encoding="utf-8"))
    if not split:
        return {}

    frontmatter, prose = split
    try:
        data = yaml.safe_load(frontmatter)
        if not isinstance(data, dict):
            return {}
    except yaml.YAMLError:
        return {"_parse_error": str(path)}

    unknown = set(data.keys()) - KNOWN_CONSTITUTION_KEYS
    if unknown:
        data["_unknown_keys"] = sorted(unknown)

    data["_prose"] = prose.strip()
    data["_source_path"] = str(path)
    return data


def merge_constitutions(levels: list[dict]) -> tuple[dict, list[dict]]:
    result = copy.deepcopy(DEFAULTS)
    warnings: list[dict] = []

    for level in levels:
        if not level:
            continue

        if "permitted_tracks" in level:
            incoming = level["permitted_tracks"]
            if isinstance(incoming, list):
                unknown_tracks = [track for track in incoming if track not in VALID_TRACKS]
                if unknown_tracks:
                    warnings.append(
                        {
                            "type": "unknown_tracks",
                            "detail": f"Unknown track values ignored: {unknown_tracks}",
                        }
                    )
                result["permitted_tracks"] = [
                    track for track in result["permitted_tracks"] if track in incoming
                ]

        if "required_artifacts" in level:
            incoming = level["required_artifacts"]
            if isinstance(incoming, dict):
                for phase, artifacts in incoming.items():
                    if not isinstance(artifacts, list):
                        continue
                    if phase not in result["required_artifacts"]:
                        result["required_artifacts"][phase] = []
                    for artifact in artifacts:
                        if artifact not in result["required_artifacts"][phase]:
                            result["required_artifacts"][phase].append(artifact)

        if "gate_mode" in level:
            mode = level["gate_mode"]
            if mode == "hard":
                result["gate_mode"] = "hard"
            elif mode not in VALID_GATE_MODES:
                warnings.append(
                    {
                        "type": "unknown_gate_mode",
                        "detail": (
                            f"Unknown gate_mode '{mode}' ignored — must be 'informational' "
                            "or 'hard'"
                        ),
                    }
                )

        if "sensing_gate_mode" in level:
            mode = level["sensing_gate_mode"]
            if mode == "hard":
                result["sensing_gate_mode"] = "hard"
            elif mode not in VALID_GATE_MODES:
                warnings.append(
                    {
                        "type": "unknown_sensing_gate_mode",
                        "detail": (
                            f"Unknown sensing_gate_mode '{mode}' ignored — must be "
                            "'informational' or 'hard'"
                        ),
                    }
                )

        if "additional_review_participants" in level:
            incoming = level["additional_review_participants"]
            if isinstance(incoming, list):
                for participant in incoming:
                    if participant not in result["additional_review_participants"]:
                        result["additional_review_participants"].append(participant)

        if "enforce_stories" in level and bool(level["enforce_stories"]):
            result["enforce_stories"] = True

        if "enforce_review" in level and bool(level["enforce_review"]):
            result["enforce_review"] = True

        if "_unknown_keys" in level:
            warnings.append(
                {
                    "type": "unknown_constitution_keys",
                    "detail": f"Unknown keys ignored: {level['_unknown_keys']}",
                }
            )

    if result["enforce_stories"]:
        if "dev" not in result["required_artifacts"]:
            result["required_artifacts"]["dev"] = []
        if "stories" not in result["required_artifacts"]["dev"]:
            result["required_artifacts"]["dev"].append("stories")

    if not result["permitted_tracks"]:
        warnings.append(
            {
                "type": "empty_permitted_tracks",
                "detail": "No tracks remain after intersection — probable governance misconfiguration",
            }
        )

    return result, warnings


def _parse_frontmatter(path: Path) -> tuple[dict, str] | None:
    split = _split_frontmatter(path.read_text(encoding="utf-8"))
    if not split:
        return None
    frontmatter, body = split
    data = yaml.safe_load(frontmatter) or {}
    if not isinstance(data, dict):
        return None
    return data, body


def _parse_yaml_metadata(path: Path) -> tuple[dict, str] | None:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return None
    return data, ""


def _parse_metadata_file(path: Path) -> tuple[dict, str] | None:
    if path.suffix.lower() == ".md":
        return _parse_frontmatter(path)
    if path.suffix.lower() in {".yaml", ".yml"}:
        return _parse_yaml_metadata(path)
    return None


def _as_list(value) -> list:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def _discover_authored_files(root: Path, source_paths: list[Path]) -> list[Path]:
    discovered: list[Path] = []
    seen: set[Path] = set()
    for source_path in source_paths:
        if not source_path.exists():
            continue
        if source_path.is_file():
            candidates = [source_path]
        else:
            candidates = [
                candidate
                for candidate in source_path.rglob("*")
                if candidate.suffix.lower() in {".md", ".yaml", ".yml"}
            ]
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            discovered.append(candidate)
    return sorted(discovered)


def _collect_entities(root: Path, docs_path: Path) -> list[dict]:
    source_paths = [root / "docs", docs_path]
    entities: list[dict] = []
    for artifact_path in _discover_authored_files(root, source_paths):
        parsed = _parse_metadata_file(artifact_path)
        if not parsed:
            continue
        metadata, body = parsed
        if not (GOVERNED_KEYS & set(metadata)):
            continue
        entities.append(
            {
                "stable_id": str(metadata.get("stable_id", "")),
                "entity_type": str(metadata.get("entity_type", "")),
                "belongs_to": str(metadata.get("belongs_to", "")),
                "feature_id": str(metadata.get("feature_id", "")),
                "target_repos": _as_list(metadata.get("target_repos")),
                "metadata": metadata,
                "body": body,
                "path": artifact_path.as_posix(),
            }
        )
    return entities


def _feature_path(root: Path, feature_id: str | None, explicit_path: str | None) -> Path:
    if explicit_path:
        return Path(explicit_path).resolve()
    if not feature_id:
        raise ValueError("feature_id_required")
    return (root / "docs" / "features" / feature_id / "feature.yaml").resolve()


def _docs_path_for(feature_yaml: Path, feature: dict, root: Path) -> Path:
    raw_docs_path = str(feature.get("docs_path") or feature.get("lens_docs_path") or "").strip()
    if raw_docs_path:
        return _resolve_path(root, raw_docs_path)
    return feature_yaml.parent.resolve()


def _load_feature_context(
    root: Path,
    feature_id: str | None,
    feature_path: str | None,
) -> tuple[Path, dict, Path, str]:
    resolved_path = _feature_path(root, feature_id, feature_path)
    if not resolved_path.exists():
        raise FileNotFoundError(resolved_path)
    feature = yaml.safe_load(resolved_path.read_text(encoding="utf-8")) or {}
    if not isinstance(feature, dict):
        raise ValueError(f"feature_yaml_invalid: {resolved_path}")
    resolved_feature_id = str(feature.get("feature_id") or feature_id or resolved_path.parent.name)
    feature.setdefault("feature_id", resolved_feature_id)
    feature.setdefault("stable_id", f"feature:{resolved_feature_id}")
    feature.setdefault("track", "full")
    feature.setdefault("phase", "preplan")
    docs_path = _docs_path_for(resolved_path, feature, root)
    return resolved_path, feature, docs_path, resolved_feature_id


def _normalize_phase(phase: str) -> tuple[str, bool]:
    clean_phase = str(phase or "").strip().lower()
    if clean_phase.endswith("-complete"):
        return clean_phase[: -len("-complete")], True
    return clean_phase, False


def _constitution_phase(local_phase: str) -> str:
    phase, is_complete = _normalize_phase(local_phase)
    if phase == "dev" and is_complete:
        return "complete"
    return LOCAL_PHASE_MAP.get(phase, phase or "planning")


def _resolve_scope_from_feature(root: Path, feature: dict, docs_path: Path) -> dict:
    explicit_domain = str(feature.get("domain") or "").strip() or None
    explicit_service = str(feature.get("service") or "").strip() or None
    explicit_repo = str(feature.get("constitution_repo") or feature.get("repo") or "").strip() or None
    if explicit_domain or explicit_service or explicit_repo:
        return {
            "domain": explicit_domain,
            "service": explicit_service,
            "repo": explicit_repo,
            "source": "feature-fields",
            "lineage": [],
        }

    entities = _collect_entities(root, docs_path)
    by_id = {entity["stable_id"]: entity for entity in entities if entity.get("stable_id")}
    feature_parent = str(feature.get("belongs_to") or "").strip()
    if not feature_parent:
        feature_entity = by_id.get(str(feature.get("stable_id") or ""))
        if feature_entity:
            feature_parent = str(feature_entity.get("belongs_to") or "").strip()

    lineage: list[str] = []
    domain = None
    service = None
    if feature_parent.startswith("service:"):
        service = feature_parent.split(":", 1)[1]
        lineage.append(feature_parent)
        service_entity = by_id.get(feature_parent)
        if service_entity:
            domain_parent = str(service_entity.get("belongs_to") or "").strip()
            if domain_parent.startswith("domain:"):
                domain = domain_parent.split(":", 1)[1]
                lineage.append(domain_parent)
    elif feature_parent.startswith("domain:"):
        domain = feature_parent.split(":", 1)[1]
        lineage.append(feature_parent)

    repo = None
    target_repos = _as_list(feature.get("target_repos"))
    if len(target_repos) == 1:
        repo = Path(str(target_repos[0])).name or None

    return {
        "domain": domain,
        "service": service,
        "repo": repo,
        "source": "lineage",
        "lineage": lineage,
    }


def _candidate_paths(artifacts_path: Path, artifact: str) -> tuple[list[Path], list[str]]:
    alias_patterns = ARTIFACT_ALIASES.get(
        artifact,
        [f"{artifact}.md", f"{artifact}.yaml", artifact],
    )
    direct_paths: list[Path] = []
    glob_patterns: list[str] = []
    for pattern in alias_patterns:
        if "*" in pattern:
            glob_patterns.append(pattern)
        else:
            direct_paths.append(artifacts_path / pattern)
    return direct_paths, glob_patterns


def _resolve_scope_inputs(args: argparse.Namespace) -> tuple[Path, dict | None, Path | None, dict, str | None]:
    root = Path(getattr(args, "project_root", ".")).resolve()
    feature = None
    docs_path = None
    feature_id = None
    if getattr(args, "feature_id", None) or getattr(args, "feature_path", None):
        _, feature, docs_path, feature_id = _load_feature_context(
            root,
            getattr(args, "feature_id", None),
            getattr(args, "feature_path", None),
        )

    scope = {
        "domain": getattr(args, "domain", None),
        "service": getattr(args, "service", None),
        "repo": getattr(args, "repo", None),
        "source": "explicit",
        "lineage": [],
    }
    if not scope["domain"] and feature and docs_path:
        scope = _resolve_scope_from_feature(root, feature, docs_path)
        if getattr(args, "repo", None):
            scope["repo"] = getattr(args, "repo", None)

    return root, feature, docs_path, scope, feature_id


def _resolve_constitution(args: argparse.Namespace) -> tuple[dict, int]:
    root, feature, docs_path, scope, feature_id = _resolve_scope_inputs(args)

    domain = str(scope.get("domain") or "").strip() or None
    service = str(scope.get("service") or "").strip() or None
    repo = str(scope.get("repo") or "").strip() or None

    for slug_name, slug_val in (("domain", domain), ("service", service), ("repo", repo)):
        if not slug_val:
            continue
        err, code = _validate_slug(slug_val, slug_name)
        if err:
            return err, code

    constitution_root = _resolve_constitution_root(
        root,
        feature,
        getattr(args, "constitution_root", None),
    )

    if not constitution_root.exists():
        suggested_org = constitution_root / "org" / "constitution.md"
        return {
            "error": "constitution_root_not_found",
            "path": str(constitution_root),
            "detail": (
                "Constitution root not found. Default location is .lens/.constitution; "
                "create it or use --constitution-root to override."
            ),
            "recovery": {
                "action": "bootstrap_constitution",
                "suggested_org_constitution": str(suggested_org),
                "suggested_command": (
                    "python skills/lens-constitution/scripts/constitution_ops.py bootstrap "
                    f"--project-root {root}"
                ),
            },
        }, 1

    level_specs: list[tuple[str, Path]] = [("org", constitution_root / "org" / "constitution.md")]
    if domain:
        level_specs.append(("domain", constitution_root / domain / "constitution.md"))
    if domain and service:
        level_specs.append(("service", constitution_root / domain / service / "constitution.md"))
    if domain and service and repo:
        level_specs.append(("repo", constitution_root / domain / service / repo / "constitution.md"))

    for level_name, path in level_specs:
        if not _assert_within(path, constitution_root):
            return {
                "error": "path_traversal_detected",
                "level": level_name,
                "detail": "Computed path escapes the constitution root directory",
            }, 1

    levels_loaded: list[str] = []
    level_data: list[dict] = []
    parse_errors: list[dict] = []
    level_details: list[dict] = []

    for level_name, path in level_specs:
        data = load_constitution(path)
        if "_parse_error" in data:
            if level_name == "org":
                return {
                    "error": "org_constitution_parse_error",
                    "path": str(path),
                    "detail": "org/constitution.md has invalid YAML frontmatter — fix it to restore constitution checks",
                }, 1
            parse_errors.append({"level": level_name, "path": str(path)})
            data = {}
        if path.exists():
            levels_loaded.append(level_name)
        level_data.append(data)
        if path.exists():
            level_details.append(
                {
                    "level": level_name,
                    "path": str(path),
                    "prose": str(data.get("_prose") or "").strip(),
                    "structured": {
                        key: value
                        for key, value in data.items()
                        if not key.startswith("_")
                    },
                }
            )

    if "org" not in levels_loaded:
        return {
            "error": "org_constitution_missing",
            "path": str(constitution_root / "org" / "constitution.md"),
            "detail": "org/constitution.md is required inside the constitution root",
            "recovery": {
                "action": "bootstrap_constitution",
                "suggested_command": (
                    "python skills/lens-constitution/scripts/constitution_ops.py bootstrap "
                    f"--project-root {root}"
                ),
            },
        }, 1

    merged, merge_warnings = merge_constitutions(level_data)
    warnings: list[dict] = []
    if parse_errors:
        warnings.extend({"type": "parse_error", **error} for error in parse_errors)
    warnings.extend(merge_warnings)

    local_phase = None
    constitution_phase = None
    track = None
    if feature:
        local_phase = str(feature.get("phase") or "")
        constitution_phase = _constitution_phase(local_phase)
        track = str(feature.get("track") or "")
    if getattr(args, "phase", None):
        local_phase = str(getattr(args, "phase"))
        constitution_phase = _constitution_phase(local_phase)
    if getattr(args, "track", None):
        track = str(getattr(args, "track"))

    prose_sections = []
    for detail in level_details:
        prose = detail["prose"]
        if not prose:
            continue
        prose_sections.append(f"[{detail['level']}]\n{prose}")

    result: dict = {
        "feature_id": feature_id,
        "constitution_root": str(constitution_root),
        "scope": {
            "domain": domain,
            "service": service,
            "repo": repo,
            "source": scope.get("source"),
            "lineage": scope.get("lineage", []),
        },
        "levels_loaded": levels_loaded,
        "level_details": level_details,
        "resolved_constitution": merged,
        "combined_prose": "\n\n".join(prose_sections),
    }
    if local_phase:
        result["local_phase"] = local_phase
        result["constitution_phase"] = constitution_phase
    if track:
        result["track"] = track
    if docs_path:
        result["docs_path"] = str(docs_path)
    if warnings:
        result["warnings"] = warnings
    if getattr(args, "dry_run", False):
        result["dry_run"] = True
    return result, 0


def cmd_resolve(args: argparse.Namespace) -> tuple[dict, int]:
    return _resolve_constitution(args)


def cmd_check_compliance(args: argparse.Namespace) -> tuple[dict, int]:
    resolved, code = _resolve_constitution(args)
    if code != 0:
        return resolved, code

    constitution = resolved["resolved_constitution"]
    feature = None
    docs_path = None
    root = Path(getattr(args, "project_root", ".")).resolve()
    feature_id = getattr(args, "feature_id", None)
    if getattr(args, "feature_id", None) or getattr(args, "feature_path", None):
        _, feature, docs_path, feature_id = _load_feature_context(
            root,
            getattr(args, "feature_id", None),
            getattr(args, "feature_path", None),
        )

    local_phase = str(getattr(args, "phase", None) or resolved.get("local_phase") or "planning")
    constitution_phase = _constitution_phase(local_phase)
    track = str(
        getattr(args, "track", None)
        or resolved.get("track")
        or (feature or {}).get("track")
        or "full"
    )
    gate = constitution.get("gate_mode", "informational")
    artifacts_path_value = getattr(args, "artifacts_path", None)
    artifacts_path = _resolve_path(root, artifacts_path_value) if artifacts_path_value else docs_path

    checks: list[dict] = []
    hard_failures: list[str] = []
    informational_failures: list[str] = []
    skipped_artifact_count = 0

    permitted_tracks = constitution.get("permitted_tracks", [])
    requirement = f"Track '{track}' permitted"
    if track in permitted_tracks:
        checks.append(
            {
                "requirement": requirement,
                "status": "PASS",
                "detail": "Track permitted by constitution",
            }
        )
    else:
        checks.append(
            {
                "requirement": requirement,
                "status": "FAIL",
                "gate": gate,
                "detail": f"Track '{track}' not in permitted_tracks: {permitted_tracks}",
            }
        )
        (hard_failures if gate == "hard" else informational_failures).append(requirement)

    required_artifacts = constitution.get("required_artifacts", {}).get(constitution_phase, [])
    for artifact in required_artifacts:
        requirement = f"Artifact '{artifact}' present for phase '{constitution_phase}'"
        if artifacts_path is None:
            checks.append(
                {
                    "requirement": requirement,
                    "status": "SKIP",
                    "detail": "No artifacts path available — artifact check skipped",
                }
            )
            skipped_artifact_count += 1
            continue

        direct_paths, glob_patterns = _candidate_paths(artifacts_path, artifact)
        found_paths = [path for path in direct_paths if path.exists()]
        matched_globs = []
        for pattern in glob_patterns:
            matched_globs.extend(str(path) for path in artifacts_path.glob(pattern))

        if found_paths or matched_globs:
            checks.append(
                {
                    "requirement": requirement,
                    "status": "PASS",
                    "gate": gate,
                    "detail": (
                        "Found: "
                        + ", ".join(
                            [str(path) for path in found_paths] + matched_globs
                        )
                    ),
                }
            )
        else:
            expected = [str(path) for path in direct_paths] + glob_patterns
            checks.append(
                {
                    "requirement": requirement,
                    "status": "FAIL",
                    "gate": gate,
                    "detail": f"Missing expected artifact(s): {expected}",
                }
            )
            (hard_failures if gate == "hard" else informational_failures).append(requirement)

    if constitution.get("enforce_review"):
        participants = constitution.get("additional_review_participants", [])
        requirement = "Reviewers configured (enforce_review=true)"
        if participants:
            checks.append(
                {
                    "requirement": requirement,
                    "status": "PASS",
                    "detail": f"Reviewers: {', '.join(str(item) for item in participants)}",
                }
            )
        else:
            checks.append(
                {
                    "requirement": requirement,
                    "status": "FAIL",
                    "gate": gate,
                    "detail": "enforce_review=true but additional_review_participants is empty",
                }
            )
            (hard_failures if gate == "hard" else informational_failures).append(requirement)

    if skipped_artifact_count > 0 and not hard_failures:
        overall_status = "INCOMPLETE"
        exit_code = 0
    elif hard_failures:
        overall_status = "FAIL"
        exit_code = 2
    else:
        overall_status = "PASS"
        exit_code = 0

    result: dict = {
        "feature_id": feature_id,
        "scope": resolved["scope"],
        "track": track,
        "local_phase": local_phase,
        "constitution_phase": constitution_phase,
        "status": overall_status,
        "checks": checks,
        "hard_gate_failures": hard_failures,
        "informational_failures": informational_failures,
        "combined_prose": resolved.get("combined_prose", ""),
    }
    if artifacts_path is not None:
        result["artifacts_path"] = str(artifacts_path)
    if skipped_artifact_count:
        result["skipped_artifact_count"] = skipped_artifact_count
    if resolved.get("warnings"):
        result["warnings"] = resolved["warnings"]
    if getattr(args, "dry_run", False):
        result["dry_run"] = True
    return result, exit_code


def cmd_progressive_display(args: argparse.Namespace) -> tuple[dict, int]:
    resolved, code = _resolve_constitution(args)
    if code != 0:
        return resolved, code

    constitution = resolved["resolved_constitution"]
    local_phase = str(getattr(args, "phase", None) or resolved.get("local_phase") or "")
    constitution_phase = _constitution_phase(local_phase) if local_phase else None
    track = str(getattr(args, "track", None) or resolved.get("track") or "")
    permitted = constitution.get("permitted_tracks", [])

    display: dict = {
        "feature_id": resolved.get("feature_id"),
        "scope": resolved["scope"],
        "levels_loaded": resolved["levels_loaded"],
        "gate_mode": constitution.get("gate_mode", "informational"),
        "sensing_gate_mode": constitution.get("sensing_gate_mode", "informational"),
        "additional_review_participants": constitution.get("additional_review_participants", []),
        "enforce_stories": constitution.get("enforce_stories", False),
        "enforce_review": constitution.get("enforce_review", False),
        "full_constitution_available": "org" in resolved["levels_loaded"],
        "combined_prose": resolved.get("combined_prose", ""),
    }
    if local_phase:
        display["local_phase"] = local_phase
        display["constitution_phase"] = constitution_phase
        display["required_artifacts_for_phase"] = constitution.get("required_artifacts", {}).get(
            constitution_phase,
            [],
        )
    if track:
        display["track"] = track
        display["track_permitted"] = track in permitted
        display["permitted_tracks"] = permitted
    if resolved.get("warnings"):
        display["warnings"] = resolved["warnings"]
    if getattr(args, "dry_run", False):
        display["dry_run"] = True
    return display, 0


def cmd_bootstrap(args: argparse.Namespace) -> tuple[dict, int]:
    root = Path(getattr(args, "project_root", ".")).resolve()
    constitution_root = _resolve_constitution_root(
        root,
        feature=None,
        override=getattr(args, "constitution_root", None),
    )
    org_constitution = constitution_root / "org" / "constitution.md"

    if not _assert_within(org_constitution, constitution_root):
        return {
            "error": "path_traversal_detected",
            "detail": "Computed constitution bootstrap path escapes the constitution root directory",
        }, 1

    if getattr(args, "dry_run", False):
        return {
            "status": "dry-run",
            "constitution_root": str(constitution_root),
            "org_constitution": str(org_constitution),
        }, 0

    created = False
    if not org_constitution.exists():
        org_constitution.parent.mkdir(parents=True, exist_ok=True)
        org_constitution.write_text(
            "---\n"
            "permitted_tracks:\n"
            "  - full\n"
            "  - express\n"
            "  - quickdev\n"
            "required_artifacts:\n"
            "  planning: []\n"
            "  dev: []\n"
            "gate_mode: informational\n"
            "sensing_gate_mode: informational\n"
            "additional_review_participants: []\n"
            "enforce_stories: false\n"
            "enforce_review: false\n"
            "---\n"
            "# Organization Constitution\n\n"
            "Add domain and service constitutions under this root as needed.\n",
            encoding="utf-8",
        )
        created = True

    return {
        "status": "created" if created else "exists",
        "constitution_root": str(constitution_root),
        "org_constitution": str(org_constitution),
    }, 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="NextLens clean-room constitution operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    def add_common_scope_arguments(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--project-root", default=".", help="NextLens project root")
        subparser.add_argument(
            "--constitution-root",
            default=None,
            help="Override constitution root path; defaults to .lens/.constitution",
        )
        subparser.add_argument("--feature-id", default=None, help="Local feature ID under docs/features")
        subparser.add_argument("--feature-path", default=None, help="Explicit path to feature.yaml")
        subparser.add_argument("--domain", default=None, help="Explicit domain scope")
        subparser.add_argument("--service", default=None, help="Explicit service scope")
        subparser.add_argument("--repo", default=None, help="Optional repo scope")
        subparser.add_argument("--phase", default=None, help="Local or constitution phase")
        subparser.add_argument("--track", default=None, help="Track filter or compliance track")
        subparser.add_argument("--dry-run", action="store_true")

    resolve_parser = sub.add_parser("resolve", help="Resolve effective constitution for a scope")
    add_common_scope_arguments(resolve_parser)

    check_parser = sub.add_parser("check-compliance", help="Validate a feature against its constitution")
    add_common_scope_arguments(check_parser)
    check_parser.add_argument(
        "--artifacts-path",
        default=None,
        help="Explicit artifact directory; defaults to the feature docs path when feature context is available",
    )

    display_parser = sub.add_parser("progressive-display", help="Return context-filtered constitution rules")
    add_common_scope_arguments(display_parser)

    bootstrap_parser = sub.add_parser("bootstrap", help="Create a minimal org constitution when missing")
    bootstrap_parser.add_argument("--project-root", default=".", help="NextLens project root")
    bootstrap_parser.add_argument(
        "--constitution-root",
        default=None,
        help="Override constitution root path; defaults to .lens/.constitution",
    )
    bootstrap_parser.add_argument("--dry-run", action="store_true")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "resolve": cmd_resolve,
        "check-compliance": cmd_check_compliance,
        "progressive-display": cmd_progressive_display,
        "bootstrap": cmd_bootstrap,
    }
    handler = dispatch[args.subcommand]
    result, code = handler(args)
    print(json.dumps(result, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())