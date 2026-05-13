#!/usr/bin/env python3
"""Deterministic helpers for LENS archive, landscape, graph, and status artifacts.

The helpers project existing LENS source truth into generated graph/status files.
They do not decide product truth and they do not mutate archive or landscape
records except for creating an empty starter tree during `init`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DIRS = [
    "archive/capture/sessions",
    "archive/capture/uploads",
    "archive/extractions",
    "archive/slices",
    "archive/bmad-packets",
    "archive/implementation-evidence",
    "archive/validation-results",
    "archive/salmon-signals",
    "intent",
    "journeys",
    "slices",
    "landscape/systems",
    "landscape/programs",
    "landscape/domains",
    "landscape/capabilities",
    "landscape/services",
    "landscape/journeys",
    "landscape/workstreams",
    "landscape/decisions",
    "landscape/risks",
    "graph",
    "bmad-bridge",
    "implementation/story-traceability",
    "implementation/validation",
    "implementation/salmon-signals",
    "validation",
    "salmon/signals",
    "salmon/propagation",
    "salmon/decisions",
    "auspex",
    "gates",
]

LEDGER_DIRS = [
    "landscape/systems",
    "landscape/programs",
    "landscape/domains",
    "landscape/capabilities",
    "landscape/services",
    "landscape/journeys",
    "landscape/workstreams",
    "landscape/decisions",
    "landscape/risks",
]

IDISH_RE = re.compile(r"^[a-z][a-z0-9_]*\.[A-Za-z0-9_.-]+$")
MD_ID_RE = re.compile(r"^\s*id:\s*['\"]?([^'\"#\n]+)", re.MULTILINE)
MD_KIND_RE = re.compile(r"^\s*kind:\s*['\"]?([^'\"#\n]+)", re.MULTILINE)
STALE_DAYS = 90


@dataclass
class Projection:
    nodes: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    traceability: dict[str, dict[str, Any]] = field(default_factory=dict)
    freshness: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    duplicate_ids: dict[str, list[str]] = field(default_factory=dict)
    id_to_node: dict[str, dict[str, Any]] = field(default_factory=dict)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def lens_root(project_root: Path) -> Path:
    return project_root / "_bmad-output" / "lens"


def fixtures_root(project_root: Path) -> Path:
    return project_root / "skills" / "bmad-lens-setup" / "assets" / "lens" / "fixtures"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_yaml(path: Path, data: Any) -> None:
    write_text(path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def load_structured_file(path: Path) -> Any:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(text) or {}
    ids = MD_ID_RE.findall(text)
    kind = MD_KIND_RE.search(text)
    if ids:
        return {
            "id": ids[0].strip(),
            "kind": kind.group(1).strip() if kind else "document",
            "name": path.stem,
            "raw_refs": ids[1:],
        }
    return {}


def source_files(project_root: Path) -> list[Path]:
    roots = [lens_root(project_root), fixtures_root(project_root)]
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".yaml", ".yml", ".md"}:
                continue
            if "/graph/" in path.as_posix() or "/auspex/" in path.as_posix():
                continue
            files.append(path)
    return files


def is_id(value: Any) -> bool:
    return isinstance(value, str) and bool(IDISH_RE.match(value.strip()))


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def iter_dicts(data: Any, parent_key: str | None = None):
    if isinstance(data, dict):
        yield parent_key, data
        for key, value in data.items():
            yield from iter_dicts(value, str(key))
    elif isinstance(data, list):
        for value in data:
            yield from iter_dicts(value, parent_key)


def entity_kind(parent_key: str | None, item: dict[str, Any]) -> str:
    if item.get("kind"):
        return str(item["kind"])
    if parent_key and parent_key.endswith("_example"):
        return parent_key.removesuffix("_example")
    if parent_key:
        return parent_key
    entity_id = str(item.get("id", ""))
    return entity_id.split(".", 1)[0] if "." in entity_id else "unknown"


def add_node(projection: Projection, item: dict[str, Any], path: Path, parent_key: str | None) -> None:
    entity_id = str(item.get("id", "")).strip()
    if not is_id(entity_id):
        return
    node = {
        "id": entity_id,
        "kind": entity_kind(parent_key, item),
        "name": item.get("name") or item.get("goal") or path.stem,
        "status": item.get("status"),
        "confidence": item.get("confidence"),
        "validity": item.get("validity"),
        "updated_at": item.get("updated_at"),
        "source_path": str(path),
    }
    projection.nodes.append(node)
    if entity_id in projection.id_to_node:
        projection.duplicate_ids.setdefault(entity_id, [projection.id_to_node[entity_id]["source_path"]]).append(str(path))
    else:
        projection.id_to_node[entity_id] = node


def add_relationship(
    projection: Projection,
    source: str,
    rel_type: str,
    target: str,
    path: Path,
    *,
    evidence: str | None = None,
) -> None:
    if not (is_id(source) and is_id(target)):
        return
    projection.relationships.append(
        {
            "from": source,
            "type": rel_type,
            "to": target,
            "source_path": str(path),
            "evidence": evidence,
        }
    )


def add_trace(projection: Projection, slice_id: str, key: str, value: Any) -> None:
    if not is_id(slice_id):
        return
    record = projection.traceability.setdefault(
        slice_id,
        {
            "slice": slice_id,
            "systems": [],
            "outcomes": [],
            "journeys": [],
            "capabilities": [],
            "artifacts": [],
            "bmad_artifacts": [],
            "stories": [],
            "validation_results": [],
            "salmon_signals": [],
        },
    )
    for item in as_list(value):
        if item and item not in record[key]:
            record[key].append(item)


def collect_relationships(projection: Projection, item: dict[str, Any], path: Path, parent_key: str | None) -> None:
    entity_id = str(item.get("id", "")).strip()

    if item.get("from") and item.get("to"):
        rel_type = str(item.get("type") or item.get("reason") or "related_to")
        add_relationship(projection, str(item["from"]), rel_type, str(item["to"]), path, evidence=entity_id or parent_key)

    if parent_key == "adjacency" or {"from", "to", "shared_artifacts"} <= set(item.keys()):
        if item.get("from") and item.get("to"):
            add_relationship(projection, str(item["from"]), "adjacent_to", str(item["to"]), path, evidence=str(item.get("reason", "")))

    for artifact in as_list(item.get("produces")) + as_list(item.get("artifacts_produced")):
        add_relationship(projection, entity_id, "produces_artifact", str(artifact), path)
        if entity_id.startswith("slice."):
            add_trace(projection, entity_id, "artifacts", artifact)
        elif is_id(item.get("active_slice")):
            add_trace(projection, str(item["active_slice"]), "artifacts", artifact)
    for artifact in as_list(item.get("consumes")) + as_list(item.get("artifacts_consumed")):
        add_relationship(projection, entity_id, "consumes_artifact", str(artifact), path)
        if entity_id.startswith("slice."):
            add_trace(projection, entity_id, "artifacts", artifact)
        elif is_id(item.get("active_slice")):
            add_trace(projection, str(item["active_slice"]), "artifacts", artifact)

    refs_by_type = {
        "system": "participates_in",
        "program": "participates_in",
        "domain": "participates_in",
        "service": "requires",
        "workstream": "impacted_by",
        "outcome": "serves",
        "journey": "realized_by",
        "slice": "decomposed_into",
        "active_slice": "planned_by",
        "raised_from": "impacted_by",
        "validates": "validated_by",
        "implemented_by_story": "implemented_by_story",
    }
    for key, rel_type in refs_by_type.items():
        for target in as_list(item.get(key)):
            add_relationship(projection, entity_id, rel_type, str(target), path, evidence=key)

    for target in as_list(item.get("capabilities")) + as_list(item.get("required_capabilities")):
        add_relationship(projection, entity_id, "requires", str(target), path, evidence="capability")

    optional = item.get("optional_context")
    if isinstance(optional, dict):
        for key, trace_key in [
            ("system", "systems"),
            ("outcome", "outcomes"),
            ("journey", "journeys"),
            ("capabilities", "capabilities"),
        ]:
            value = optional.get(key)
            for target in as_list(value):
                if target:
                    add_trace(projection, entity_id, trace_key, target)

    if entity_id.startswith("slice."):
        add_trace(projection, entity_id, "systems", item.get("system"))
        add_trace(projection, entity_id, "outcomes", item.get("outcome"))
        add_trace(projection, entity_id, "journeys", item.get("journey"))
        add_trace(projection, entity_id, "capabilities", item.get("capabilities"))
        add_trace(projection, entity_id, "capabilities", item.get("required_capabilities"))
        add_trace(projection, entity_id, "bmad_artifacts", item.get("bmad_packet_refs"))

    active_slice = item.get("active_slice") or item.get("slice")
    if is_id(active_slice):
        if entity_id.startswith("bmad_packet."):
            add_trace(projection, str(active_slice), "bmad_artifacts", entity_id)
        if entity_id.startswith("story."):
            add_trace(projection, str(active_slice), "stories", entity_id)
        if entity_id.startswith("validation."):
            add_trace(projection, str(active_slice), "validation_results", entity_id)

    validates = item.get("validates")
    if is_id(validates) and entity_id.startswith("validation."):
        add_trace(projection, str(validates), "validation_results", entity_id)

    if entity_id.startswith("salmon."):
        for target in as_list(item.get("impacted_nodes")):
            add_relationship(projection, entity_id, "impacted_by", str(target), path, evidence="salmon")
            if is_id(target) and str(target).startswith("slice."):
                add_trace(projection, str(target), "salmon_signals", entity_id)

    candidate = item.get("candidate")
    promoted_from = as_list(item.get("promoted_from"))
    if is_id(candidate):
        for source in promoted_from:
            add_relationship(projection, str(source), "promotes_to", str(candidate), path, evidence="promotion_gate")


def collect_freshness(projection: Projection, item: dict[str, Any], path: Path) -> None:
    entity_id = str(item.get("id", "")).strip()
    if not is_id(entity_id):
        return
    validity = item.get("validity")
    updated_at = item.get("updated_at")
    signals: list[str] = []
    if validity in {"stale", "needs_review"}:
        signals.append(str(validity))
    if updated_at:
        try:
            parsed = dt.datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            age_days = (dt.datetime.now(dt.timezone.utc) - parsed).days
            if age_days > STALE_DAYS:
                signals.append(f"older_than_{STALE_DAYS}_days")
        except ValueError:
            signals.append("invalid_updated_at")
    projection.freshness.append(
        {
            "id": entity_id,
            "kind": entity_kind(None, item),
            "validity": validity or "unknown",
            "updated_at": updated_at,
            "signals": signals,
            "source_path": str(path),
        }
    )


def build_projection(project_root: Path) -> Projection:
    projection = Projection()
    for path in source_files(project_root):
        data = load_structured_file(path)
        for parent_key, item in iter_dicts(data):
            add_node(projection, item, path, parent_key)
        for parent_key, item in iter_dicts(data):
            collect_relationships(projection, item, path, parent_key)
            collect_freshness(projection, item, path)
    add_warnings(projection, project_root)
    projection.relationships = dedupe_dicts(projection.relationships)
    for key, record in projection.traceability.items():
        for field_name, value in record.items():
            if isinstance(value, list):
                record[field_name] = sorted(set(value))
    return projection


def dedupe_dicts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result = []
    for item in items:
        marker = json.dumps(item, sort_keys=True)
        if marker not in seen:
            seen.add(marker)
            result.append(item)
    return result


def relationship_refs(projection: Projection) -> set[str]:
    refs: set[str] = set()
    for rel in projection.relationships:
        refs.add(str(rel["from"]))
        refs.add(str(rel["to"]))
    for record in projection.traceability.values():
        for key, value in record.items():
            if isinstance(value, list):
                refs.update(str(v) for v in value if is_id(v))
            elif is_id(value):
                refs.add(str(value))
    return refs


def add_warning(projection: Projection, severity: str, warning_type: str, **fields: Any) -> None:
    warning = {"severity": severity, "type": warning_type}
    warning.update(fields)
    projection.warnings.append(warning)


def add_warnings(projection: Projection, project_root: Path) -> None:
    root = lens_root(project_root)
    known_ids = set(projection.id_to_node)
    for entity_id, paths in projection.duplicate_ids.items():
        add_warning(projection, "high", "duplicate_id", id=entity_id, paths=paths)

    for ref in sorted(relationship_refs(projection)):
        if is_id(ref) and ref not in known_ids:
            add_warning(projection, "high", "orphan_ref", ref=ref)

    for rel in projection.relationships:
        target = str(rel.get("to", ""))
        if target.startswith(("capability.", "domain.", "service.", "system.", "program.")) and target not in known_ids:
            add_warning(projection, "medium", "unresolved_promoted_ref", ref=target, source_path=rel.get("source_path"))

    for rel in LEDGER_DIRS:
        if not (root / rel).exists():
            add_warning(projection, "high", "missing_ledger_dir", path=str(root / rel))

    for fresh in projection.freshness:
        if fresh["signals"]:
            add_warning(projection, "medium", "stale_or_needs_review", id=fresh["id"], signals=fresh["signals"], source_path=fresh["source_path"])

    for node in projection.nodes:
        if node["kind"] == "story" or node["id"].startswith("story."):
            traced = any(node["id"] in record.get("stories", []) for record in projection.traceability.values())
            has_rel = any(node["id"] in {rel["from"], rel["to"]} for rel in projection.relationships)
            if not traced and not has_rel:
                add_warning(projection, "high", "untraced_story", id=node["id"], source_path=node["source_path"])


def init(args) -> int:
    root = lens_root(Path(args.project_root))
    for rel in DIRS:
        (root / rel).mkdir(parents=True, exist_ok=True)
    sources = root / "archive" / "capture" / "sources.yaml"
    if not sources.exists():
        write_text(sources, "sources: []\n")
    project_context = Path(args.project_root) / "_bmad-output" / "project-context.md"
    if not project_context.exists():
        write_text(project_context, "# Project Context for AI Agents\n\nThis project uses LENS for slice traceability and validation.\n")
    print(json.dumps({"status": "ok", "lens_root": str(root), "directories": len(DIRS)}, indent=2))
    return 0


def graph_payload(projection: Projection, project_root: Path) -> dict[str, Any]:
    return {
        "generated_at": now(),
        "source_truth": False,
        "source_roots": [str(lens_root(project_root)), str(fixtures_root(project_root))],
        "nodes": projection.nodes,
        "relationships": projection.relationships,
        "warnings": projection.warnings,
    }


def map_rebuild(args) -> int:
    project_root = Path(args.project_root)
    root = lens_root(project_root)
    graph = root / "graph"
    graph.mkdir(parents=True, exist_ok=True)
    projection = build_projection(project_root)
    payload = graph_payload(projection, project_root)
    write_text(graph / "derived-map.json", json.dumps(payload, indent=2) + "\n")
    write_yaml(graph / "derived-map.yaml", payload)
    write_yaml(graph / "relationship-index.yaml", {"relationships": projection.relationships})
    write_yaml(graph / "traceability-index.yaml", {"traceability": list(projection.traceability.values())})
    write_yaml(
        graph / "freshness-index.yaml",
        {
            "generated_at": payload["generated_at"],
            "stale_after_days": STALE_DAYS,
            "files_indexed": len(source_files(project_root)),
            "items": projection.freshness,
        },
    )
    write_yaml(graph / "warnings.yaml", {"warnings": projection.warnings})
    print(
        json.dumps(
            {
                "status": "ok",
                "nodes": len(projection.nodes),
                "relationships": len(projection.relationships),
                "traceability": len(projection.traceability),
                "warnings": len(projection.warnings),
            },
            indent=2,
        )
    )
    return 0


def doctor(args) -> int:
    project_root = Path(args.project_root)
    root = lens_root(project_root)
    graph = root / "graph"
    graph.mkdir(parents=True, exist_ok=True)
    projection = build_projection(project_root)
    write_yaml(graph / "warnings.yaml", {"warnings": projection.warnings})
    by_type: dict[str, int] = {}
    for warning in projection.warnings:
        by_type[warning["type"]] = by_type.get(warning["type"], 0) + 1
    report = [
        "# LENS Doctor Report",
        "",
        f"Generated: {now()}",
        "",
        f"Nodes indexed: {len(projection.nodes)}",
        f"Relationships indexed: {len(projection.relationships)}",
        f"Traceability records: {len(projection.traceability)}",
        f"Warnings: {len(projection.warnings)}",
        "",
        "## Findings By Type",
        "",
    ]
    for warning_type, count in sorted(by_type.items()):
        report.append(f"- {warning_type}: {count}")
    report.extend(["", "## Findings", ""])
    for warning in projection.warnings:
        report.append(f"- {warning['severity']}: {warning['type']} {warning.get('id', warning.get('ref', warning.get('path', '')))}")
    write_text(graph / "doctor-report.md", "\n".join(report) + "\n")
    print(json.dumps({"status": "ok", "warnings": len(projection.warnings), "by_type": by_type}, indent=2))
    return 0


def active_nodes(projection: Projection, *kinds: str) -> list[dict[str, Any]]:
    wanted = set(kinds)
    return [
        node
        for node in projection.nodes
        if node.get("kind") in wanted and node.get("status") not in {"archived", "superseded"}
    ]


def auspex(args) -> int:
    project_root = Path(args.project_root)
    root = lens_root(project_root)
    projection = build_projection(project_root)
    status = {
        "generated_at": now(),
        "source_truth": False,
        "derived_map": str(root / "graph" / "derived-map.json"),
        "node_count": len(projection.nodes),
        "relationship_count": len(projection.relationships),
        "warning_count": len(projection.warnings),
        "active_outcomes": active_nodes(projection, "outcome"),
        "active_journeys": active_nodes(projection, "journey"),
        "active_slices": active_nodes(projection, "slice"),
        "open_decisions": active_nodes(projection, "decision"),
        "risks": active_nodes(projection, "risk"),
        "blockers": [w for w in projection.warnings if w.get("severity") in {"high", "critical"}],
        "bmad_progress": [
            node for node in projection.nodes if node.get("kind") in {"bmad_packet", "story", "implementation_evidence"}
        ],
        "validation_evidence": active_nodes(projection, "validation_result"),
        "salmon_signals": active_nodes(projection, "salmon_signal"),
        "traceability": list(projection.traceability.values()),
    }
    out = root / "auspex"
    write_text(out / "status.json", json.dumps(status, indent=2) + "\n")
    write_yaml(out / "status.yaml", {"auspex_status": status})
    summary = [
        "# Auspex Stakeholder Summary",
        "",
        "Auspex is read-only and generated from the Derived Map and source ledgers.",
        "",
        f"- Nodes indexed: {status['node_count']}",
        f"- Relationships indexed: {status['relationship_count']}",
        f"- Active outcomes: {len(status['active_outcomes'])}",
        f"- Active journeys: {len(status['active_journeys'])}",
        f"- Active slices: {len(status['active_slices'])}",
        f"- Open decisions: {len(status['open_decisions'])}",
        f"- Risks: {len(status['risks'])}",
        f"- Blockers: {len(status['blockers'])}",
        f"- BMAD progress items: {len(status['bmad_progress'])}",
        f"- Validation evidence items: {len(status['validation_evidence'])}",
        f"- Salmon signals: {len(status['salmon_signals'])}",
        "",
    ]
    write_text(out / "stakeholder-summary.md", "\n".join(summary))
    print(json.dumps({"status": "ok", "output": str(out), "active_slices": len(status["active_slices"])}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init", "map-rebuild", "doctor", "auspex"])
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    return globals()[args.command.replace("-", "_")](args)


if __name__ == "__main__":
    raise SystemExit(main())
