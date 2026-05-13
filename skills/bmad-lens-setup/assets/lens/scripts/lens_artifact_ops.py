#!/usr/bin/env python3
"""Small deterministic helpers for LENS archive/landscape/graph artifacts.

The scripts are intentionally conservative: they create directories and derived
status projections, but they do not decide product truth. LENS skills and humans
own the source artifacts.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

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
    "salmon/signals",
    "salmon/propagation",
    "salmon/decisions",
    "auspex",
    "gates",
]

ID_RE = re.compile(r"^\s*id:\s*['\"]?([^'\"#\n]+)", re.MULTILINE)
KIND_RE = re.compile(r"^\s*kind:\s*['\"]?([^'\"#\n]+)", re.MULTILINE)
REL_RE = re.compile(r"^\s*-?\s*(?:relationship|rel|id):\s*['\"]?([^'\"#\n]+)", re.MULTILINE)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def lens_root(project_root: Path) -> Path:
    return project_root / "_bmad-output" / "lens"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def as_yaml(data, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(data, dict):
        lines = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{pad}{key}:")
                lines.append(as_yaml(value, indent + 1))
            else:
                lines.append(f"{pad}{key}: {json.dumps(value) if isinstance(value, str) else value}")
        return "\n".join(lines)
    if isinstance(data, list):
        lines = []
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}-")
                lines.append(as_yaml(item, indent + 1))
            else:
                lines.append(f"{pad}- {json.dumps(item) if isinstance(item, str) else item}")
        return "\n".join(lines)
    return f"{pad}{data}"


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


def scan_nodes(root: Path):
    nodes = []
    duplicate_ids = {}
    seen = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".yaml", ".yml", ".md"} and "/graph/" not in str(path):
            text = path.read_text(encoding="utf-8", errors="ignore")
            ids = [m.group(1).strip() for m in ID_RE.finditer(text)]
            kind_match = KIND_RE.search(text)
            kind = kind_match.group(1).strip() if kind_match else "unknown"
            for entity_id in ids:
                node = {"id": entity_id, "kind": kind, "path": str(path)}
                nodes.append(node)
                if entity_id in seen:
                    duplicate_ids.setdefault(entity_id, [seen[entity_id]]).append(str(path))
                else:
                    seen[entity_id] = str(path)
    return nodes, duplicate_ids


def map_rebuild(args) -> int:
    root = lens_root(Path(args.project_root))
    graph = root / "graph"
    graph.mkdir(parents=True, exist_ok=True)
    nodes, duplicate_ids = scan_nodes(root)
    data = {
        "generated_at": now(),
        "source_truth": False,
        "source_roots": [str(root / "archive"), str(root / "landscape")],
        "nodes": nodes,
        "relationships": [],
        "warnings": [{"type": "duplicate_id", "id": k, "paths": v} for k, v in duplicate_ids.items()],
    }
    write_text(graph / "derived-map.json", json.dumps(data, indent=2) + "\n")
    write_text(graph / "derived-map.yaml", as_yaml(data) + "\n")
    write_text(graph / "relationship-index.yaml", "relationships: []\n")
    write_text(graph / "traceability-index.yaml", "traceability: []\n")
    write_text(graph / "freshness-index.yaml", as_yaml({"generated_at": data["generated_at"], "files_indexed": len(nodes)}) + "\n")
    write_text(graph / "warnings.yaml", as_yaml({"warnings": data["warnings"]}) + "\n")
    print(json.dumps({"status": "ok", "nodes": len(nodes), "warnings": len(data["warnings"])}, indent=2))
    return 0


def doctor(args) -> int:
    root = lens_root(Path(args.project_root))
    graph = root / "graph"
    graph.mkdir(parents=True, exist_ok=True)
    nodes, duplicate_ids = scan_nodes(root)
    warnings = []
    for entity_id, paths in duplicate_ids.items():
        warnings.append({"severity": "high", "type": "duplicate_id", "id": entity_id, "paths": paths})
    required = [root / "archive", root / "landscape", root / "graph"]
    for path in required:
        if not path.exists():
            warnings.append({"severity": "high", "type": "missing_required_tree", "path": str(path)})
    write_text(graph / "warnings.yaml", as_yaml({"warnings": warnings}) + "\n")
    report = ["# LENS Doctor Report", "", f"Generated: {now()}", "", f"Nodes indexed: {len(nodes)}", f"Warnings: {len(warnings)}", ""]
    for warning in warnings:
        report.append(f"- {warning['severity']}: {warning['type']} {warning.get('id', warning.get('path', ''))}")
    write_text(graph / "doctor-report.md", "\n".join(report) + "\n")
    print(json.dumps({"status": "ok", "warnings": len(warnings)}, indent=2))
    return 0


def auspex(args) -> int:
    root = lens_root(Path(args.project_root))
    graph_json = root / "graph" / "derived-map.json"
    data = {"nodes": [], "warnings": []}
    if graph_json.exists():
        data = json.loads(graph_json.read_text(encoding="utf-8"))
    status = {
        "generated_at": now(),
        "source_truth": False,
        "derived_map": str(graph_json),
        "node_count": len(data.get("nodes", [])),
        "warning_count": len(data.get("warnings", [])),
        "active_slices": [n for n in data.get("nodes", []) if n.get("kind") == "slice"],
        "risks": [],
        "blockers": [],
        "salmon_signals": [n for n in data.get("nodes", []) if n.get("kind") == "salmon_signal"],
    }
    out = root / "auspex"
    write_text(out / "status.json", json.dumps(status, indent=2) + "\n")
    write_text(out / "status.yaml", as_yaml({"auspex_status": status}) + "\n")
    summary = "# Auspex Stakeholder Summary\n\nAuspex is read-only and generated from the Derived Map.\n\n"
    summary += f"- Nodes indexed: {status['node_count']}\n- Warnings: {status['warning_count']}\n- Active slices: {len(status['active_slices'])}\n- Salmon signals: {len(status['salmon_signals'])}\n"
    write_text(out / "stakeholder-summary.md", summary)
    print(json.dumps({"status": "ok", "output": str(out)}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init", "map-rebuild", "doctor", "auspex"])
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    return globals()[args.command.replace("-", "_")](args)


if __name__ == "__main__":
    raise SystemExit(main())
