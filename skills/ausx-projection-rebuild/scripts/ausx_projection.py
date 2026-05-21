#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Doctor and rebuild commands for derived Auspex governance maps."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote


PREFIX_BY_TYPE = {
    "program": "program:",
    "domain": "domain:",
    "service": "service:",
    "feature": "feature:",
    "projection": "projection:",
}

PARENT_PREFIXES = {
    "domain": {"program:"},
    "service": {"domain:"},
    "feature": {"service:", "domain:", "program:"},
}

CORE_FIELDS = (
    "stable_id",
    "entity_type",
    "title",
    "status",
    "publication_state",
    "updated_at",
)

GOVERNED_KEYS = {
    "stable_id",
    "entity_type",
    "belongs_to",
    "work_id",
    "publication_state",
    "promotion_status",
    "salmon_upstream",
}


def parse_scalar(raw_value: str):
    value = raw_value.strip()
    if not value:
        return ""
    if value == "[]":
        return []
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part) for part in inner.split(",")]
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_frontmatter(path: Path) -> tuple[dict, str] | None:
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 3)
    if end == -1:
        return None
    raw_frontmatter = content[3:end].strip()
    body = content[end + 4 :]
    metadata = {}
    current_list_key = None
    for raw_line in raw_frontmatter.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if current_list_key and line.startswith(("  - ", "- ")):
            item = line.split("- ", 1)[1]
            metadata[current_list_key].append(parse_scalar(item))
            continue
        current_list_key = None
        if ":" not in line or line.startswith(" "):
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        parsed_value = parse_scalar(value)
        metadata[key] = parsed_value
        if value.strip() == "":
            metadata[key] = []
            current_list_key = key
    return metadata, body


def as_list(value) -> list:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def rel_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_path(root: Path, value: str) -> Path:
    if value.startswith("{project-root}/"):
        value = value.removeprefix("{project-root}/")
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def discover_markdown(root: Path, paths: list[Path]) -> list[Path]:
    discovered = []
    seen = set()
    for source_path in paths:
        if not source_path.exists():
            continue
        candidates = [source_path] if source_path.is_file() else source_path.rglob("*.md")
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            discovered.append(candidate)
    return sorted(discovered, key=lambda item: rel_path(item, root))


def collect_entities(args: argparse.Namespace) -> list[dict]:
    root = args.project_root.resolve()
    source_paths = [
        resolve_path(root, args.work_intake_path),
        resolve_path(root, args.feature_archive_path),
        resolve_path(root, args.landscape_root),
    ]
    entities = []
    for markdown_path in discover_markdown(root, source_paths):
        parsed = parse_frontmatter(markdown_path)
        if not parsed:
            continue
        metadata, body = parsed
        if not (GOVERNED_KEYS & set(metadata)):
            continue
        stable_id = str(metadata.get("stable_id", ""))
        entity = {
            "stable_id": stable_id,
            "entity_type": str(metadata.get("entity_type", "")),
            "title": str(metadata.get("title", "")),
            "status": str(metadata.get("status", "")),
            "publication_state": str(metadata.get("publication_state", "")),
            "updated_at": str(metadata.get("updated_at", "")),
            "belongs_to": str(metadata.get("belongs_to", "")),
            "promotion_status": str(metadata.get("promotion_status", "")),
            "salmon_upstream": metadata.get("salmon_upstream", False),
            "links": as_list(metadata.get("links")),
            "path": rel_path(markdown_path, root),
            "body": body,
            "metadata": metadata,
        }
        entities.append(entity)
    return entities


def finding(severity: str, code: str, entity: dict, problem: str, fix: str) -> dict:
    return {
        "severity": severity,
        "code": code,
        "stable_id": entity.get("stable_id") or "unknown",
        "entity_type": entity.get("entity_type") or "unknown",
        "path": entity.get("path", ""),
        "problem": problem,
        "recommended_fix": fix,
    }


def severity_for(entity: dict) -> str:
    return "advisory" if entity.get("publication_state") == "draft" else "blocking"


def validate_required_fields(entities: list[dict]) -> list[dict]:
    findings = []
    for entity in entities:
        for field_name in CORE_FIELDS:
            if not entity.get(field_name):
                findings.append(
                    finding(
                        severity_for(entity),
                        "missing_field",
                        entity,
                        f"Missing required metadata field `{field_name}`.",
                        f"Add `{field_name}` to the artifact frontmatter.",
                    )
                )
    return findings


def validate_prefixes(entities: list[dict]) -> list[dict]:
    findings = []
    for entity in entities:
        entity_type = entity.get("entity_type")
        stable_id = entity.get("stable_id")
        expected = PREFIX_BY_TYPE.get(entity_type)
        if stable_id and expected and not stable_id.startswith(expected):
            findings.append(
                finding(
                    severity_for(entity),
                    "stable_id_prefix",
                    entity,
                    f"Stable ID `{stable_id}` does not match entity type `{entity_type}`.",
                    f"Use a stable ID beginning with `{expected}`.",
                )
            )
    return findings


def validate_duplicates(entities: list[dict], include_drafts: bool) -> list[dict]:
    grouped = defaultdict(list)
    for entity in entities:
        stable_id = entity.get("stable_id")
        if not stable_id or entity.get("publication_state") == "retired":
            continue
        if entity.get("publication_state") == "draft" and not include_drafts:
            continue
        grouped[stable_id].append(entity)
    findings = []
    for stable_id, matches in grouped.items():
        if len(matches) < 2:
            continue
        severity = "advisory" if all(
            item.get("publication_state") == "draft" for item in matches
        ) else "blocking"
        paths = ", ".join(item["path"] for item in matches)
        for entity in matches:
            findings.append(
                finding(
                    severity,
                    "duplicate_stable_id",
                    entity,
                    f"Duplicate stable ID `{stable_id}` also appears in {paths}.",
                    "Give each governed entity a unique stable ID.",
                )
            )
    return findings


def validate_parentage(entities: list[dict]) -> list[dict]:
    by_id = {entity["stable_id"]: entity for entity in entities if entity.get("stable_id")}
    findings = []
    for entity in entities:
        entity_type = entity.get("entity_type")
        if entity_type not in PARENT_PREFIXES:
            continue
        parent_id = entity.get("belongs_to")
        if not parent_id or parent_id == "unknown":
            findings.append(
                finding(
                    severity_for(entity),
                    "missing_parent",
                    entity,
                    "Missing or unknown `belongs_to` parent reference.",
                    "Set `belongs_to` to a valid parent stable ID.",
                )
            )
            continue
        expected_prefixes = PARENT_PREFIXES[entity_type]
        if not any(parent_id.startswith(prefix) for prefix in expected_prefixes):
            expected = ", ".join(sorted(expected_prefixes))
            findings.append(
                finding(
                    severity_for(entity),
                    "parent_type_mismatch",
                    entity,
                    f"Parent `{parent_id}` is not valid for `{entity_type}`.",
                    f"Use a parent stable ID beginning with one of: {expected}.",
                )
            )
        if parent_id not in by_id:
            findings.append(
                finding(
                    severity_for(entity),
                    "missing_parent_entity",
                    entity,
                    f"Parent `{parent_id}` was not found in authored sources.",
                    "Create the parent ledger or correct `belongs_to`.",
                )
            )
    return findings


def validate_cycles(entities: list[dict]) -> list[dict]:
    by_id = {entity["stable_id"]: entity for entity in entities if entity.get("stable_id")}
    graph = {
        entity["stable_id"]: entity.get("belongs_to")
        for entity in entities
        if entity.get("stable_id") and entity.get("belongs_to") in by_id
    }
    findings = []
    for stable_id in graph:
        seen = []
        current = stable_id
        while current in graph:
            if current in seen:
                cycle = seen[seen.index(current) :] + [current]
                entity = by_id[stable_id]
                findings.append(
                    finding(
                        "blocking",
                        "parent_cycle",
                        entity,
                        f"Parent graph contains a cycle: {' -> '.join(cycle)}.",
                        "Break the cycle by correcting one `belongs_to` reference.",
                    )
                )
                break
            seen.append(current)
            current = graph[current]
    return findings


def local_links(body: str) -> list[str]:
    matches = re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", body)
    return [match.strip() for match in matches]


def is_external_link(target: str) -> bool:
    lowered = target.lower()
    return (
        lowered.startswith(("http://", "https://", "mailto:", "#"))
        or "://" in target
    )


def validate_links(entities: list[dict], root: Path) -> list[dict]:
    findings = []
    for entity in entities:
        source_path = root / entity["path"]
        for target in local_links(entity.get("body", "")):
            if is_external_link(target):
                continue
            clean_target = unquote(target.split("#", 1)[0])
            if not clean_target:
                continue
            resolved = (source_path.parent / clean_target).resolve()
            if not resolved.exists():
                findings.append(
                    finding(
                        severity_for(entity),
                        "broken_link",
                        entity,
                        f"Local link target `{target}` does not exist.",
                        "Update or remove the broken Markdown link.",
                    )
                )
    return findings


def validate_promotion_and_salmon(entities: list[dict]) -> list[dict]:
    findings = []
    for entity in entities:
        status = entity.get("status", "").lower()
        promotion_status = entity.get("promotion_status", "").lower()
        if entity.get("entity_type") == "feature" and status in {"completed", "done"}:
            if promotion_status in {"", "pending", "not_started", "planned"}:
                findings.append(
                    finding(
                        "advisory",
                        "completed_unpromoted",
                        entity,
                        "Completed feature knowledge has not been promoted to a living ledger.",
                        "Run `ausx-ledger-promotion` after parentage is valid.",
                    )
                )
        body = entity.get("body", "")
        if entity.get("salmon_upstream") is True or "UPSTREAM IMPACT" in body:
            findings.append(
                finding(
                    "advisory",
                    "salmon_signal",
                    entity,
                    "Artifact contains an upstream-impact signal.",
                    "Run `ausx-salmon-impact` for recursive consistency review.",
                )
            )
    return findings


def run_doctor(args: argparse.Namespace) -> dict:
    root = args.project_root.resolve()
    entities = collect_entities(args)
    findings = []
    findings.extend(validate_required_fields(entities))
    findings.extend(validate_prefixes(entities))
    findings.extend(validate_duplicates(entities, args.include_drafts))
    findings.extend(validate_parentage(entities))
    findings.extend(validate_cycles(entities))
    findings.extend(validate_links(entities, root))
    findings.extend(validate_promotion_and_salmon(entities))
    blocking = [item for item in findings if item["severity"] == "blocking"]
    advisory = [item for item in findings if item["severity"] == "advisory"]
    result = {
        "module": "ausx",
        "report_type": "lens_doctor",
        "status": "blocked" if blocking else "pass",
        "project_root": root.as_posix(),
        "entity_count": len(entities),
        "blocking_count": len(blocking),
        "advisory_count": len(advisory),
        "projection_rebuild_ready": not blocking,
        "include_drafts": args.include_drafts,
        "findings": findings,
    }
    if args.verbose:
        result["entities"] = [public_entity(entity) for entity in entities]
    return result


def public_entity(entity: dict) -> dict:
    return {
        "stable_id": entity.get("stable_id"),
        "entity_type": entity.get("entity_type"),
        "title": entity.get("title"),
        "status": entity.get("status"),
        "publication_state": entity.get("publication_state"),
        "belongs_to": entity.get("belongs_to"),
        "updated_at": entity.get("updated_at"),
        "path": entity.get("path"),
    }


def projection_entities(entities: list[dict], include_drafts: bool) -> list[dict]:
    projected = []
    for entity in entities:
        publication_state = entity.get("publication_state")
        if publication_state == "retired":
            continue
        if publication_state == "draft" and not include_drafts:
            continue
        projected.append(public_entity(entity))
    return projected


def write_markdown(output_path: Path, projection: dict) -> None:
    lines = [
        "---",
        "stable_id: projection:governance-map",
        "entity_type: projection",
        "title: Auspex Governance Map",
        "status: derived",
        "publication_state: published",
        f"generated_at: {projection['generated_at']}",
        f"doctor_status: {projection['doctor']['status']}",
        "---",
        "",
        "# Auspex Governance Map",
        "",
        "This file is generated from authored frontmatter. Do not edit it as source truth.",
        "",
        "## Summary",
        "",
        f"- Entity count: {projection['entity_count']}",
        f"- Blocking findings: {projection['doctor']['blocking_count']}",
        f"- Advisory findings: {projection['doctor']['advisory_count']}",
        f"- Drafts included: {str(projection['include_drafts']).lower()}",
        "",
        "## Entities",
        "",
        "| Stable ID | Type | Parent | State | Path |",
        "| --------- | ---- | ------ | ----- | ---- |",
    ]
    for entity in projection["entities"]:
        lines.append(
            "| {stable_id} | {entity_type} | {belongs_to} | {publication_state} | {path} |".format(
                stable_id=entity.get("stable_id") or "unknown",
                entity_type=entity.get("entity_type") or "unknown",
                belongs_to=entity.get("belongs_to") or "",
                publication_state=entity.get("publication_state") or "",
                path=entity.get("path") or "",
            )
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_rebuild(args: argparse.Namespace) -> tuple[int, dict]:
    doctor = run_doctor(args)
    root = args.project_root.resolve()
    output_dir = resolve_path(root, args.reporting_output_path)
    if doctor["blocking_count"] and not args.force:
        return 1, {
            "module": "ausx",
            "report_type": "projection_rebuild",
            "status": "blocked",
            "reason": "Doctor found blocking issues; rerun with --force only for an explicit preview.",
            "doctor": doctor,
        }
    entities = collect_entities(args)
    generated_at = datetime.now(timezone.utc).isoformat()
    projection = {
        "module": "ausx",
        "report_type": "governance_map",
        "generated_at": generated_at,
        "derived": True,
        "source_model": "authored_frontmatter",
        "include_drafts": args.include_drafts,
        "doctor": {
            "status": doctor["status"],
            "blocking_count": doctor["blocking_count"],
            "advisory_count": doctor["advisory_count"],
        },
        "entities": projection_entities(entities, args.include_drafts),
    }
    projection["entity_count"] = len(projection["entities"])
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "governance-map.json"
    markdown_path = output_dir / "governance-map.md"
    json_path.write_text(json.dumps(projection, indent=2) + "\n", encoding="utf-8")
    write_markdown(markdown_path, projection)
    return 0, {
        "module": "ausx",
        "report_type": "projection_rebuild",
        "status": "complete" if not doctor["blocking_count"] else "forced",
        "json_path": json_path.as_posix(),
        "markdown_path": markdown_path.as_posix(),
        "entity_count": projection["entity_count"],
        "blocking_count": doctor["blocking_count"],
        "advisory_count": doctor["advisory_count"],
        "include_drafts": args.include_drafts,
    }


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("project_root", type=Path, help="Project root containing docs.")
    parser.add_argument("--work-intake-path", default="docs/features")
    parser.add_argument("--feature-archive-path", default="docs/features")
    parser.add_argument("--landscape-root", default="docs")
    parser.add_argument("--reporting-output-path", default="_bmad-output/auspex")
    parser.add_argument("--include-drafts", action="store_true")
    parser.add_argument("--verbose", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Auspex doctor checks or rebuild a derived governance map.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    doctor = subcommands.add_parser("doctor", help="Validate authored topology metadata.")
    add_common_arguments(doctor)
    rebuild = subcommands.add_parser("rebuild", help="Write derived governance-map files.")
    add_common_arguments(rebuild)
    rebuild.add_argument("--force", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "doctor":
        result = run_doctor(args)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "pass" else 1
    if args.command == "rebuild":
        exit_code, result = run_rebuild(args)
        print(json.dumps(result, indent=2))
        return exit_code
    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())