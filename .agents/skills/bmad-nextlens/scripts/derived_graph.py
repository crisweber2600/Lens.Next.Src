"""Canonical derived graph schema for NextLens landscape projections."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


DERIVED_GRAPH_SCHEMA_VERSION = "1.0"
DERIVED_GRAPH_NODE_TYPES = (
    "system",
    "role",
    "outcome",
    "journey",
    "operating_loop",
    "capability",
    "decision",
    "risk",
    "feature",
)
DERIVED_GRAPH_NODE_PROPERTIES = ("id", "type", "label", "metadata")
DERIVED_GRAPH_EDGE_PROPERTIES = ("source", "target", "type", "label", "metadata")


@dataclass(frozen=True)
class DerivedGraphEdgeType:
    type: str
    source_type: str
    target_type: str
    label: str

    def to_payload(self) -> dict[str, str]:
        return {
            "type": self.type,
            "source_type": self.source_type,
            "target_type": self.target_type,
            "label": self.label,
        }


DERIVED_GRAPH_EDGE_TYPES = (
    DerivedGraphEdgeType(
        type="system_role",
        source_type="system",
        target_type="role",
        label="system requires role participation",
    ),
    DerivedGraphEdgeType(
        type="role_outcome",
        source_type="role",
        target_type="outcome",
        label="role achieves outcome",
    ),
    DerivedGraphEdgeType(
        type="outcome_journey",
        source_type="outcome",
        target_type="journey",
        label="outcome fulfilled by journey",
    ),
    DerivedGraphEdgeType(
        type="journey_operating_loop",
        source_type="journey",
        target_type="operating_loop",
        label="journey contains operating loop",
    ),
    DerivedGraphEdgeType(
        type="operating_loop_capability",
        source_type="operating_loop",
        target_type="capability",
        label="operating loop uses capability",
    ),
    DerivedGraphEdgeType(
        type="capability_decision",
        source_type="capability",
        target_type="decision",
        label="decision governs capability",
    ),
    DerivedGraphEdgeType(
        type="feature_journey",
        source_type="feature",
        target_type="journey",
        label="feature proves journey",
    ),
    DerivedGraphEdgeType(
        type="feature_outcome",
        source_type="feature",
        target_type="outcome",
        label="feature proves outcome",
    ),
)


@dataclass(frozen=True)
class DerivedGraphNode:
    id: str
    type: str
    label: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DerivedGraphEdge:
    source: str
    target: str
    type: str
    label: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "type": self.type,
            "label": self.label,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DerivedGraphSchema:
    version: str = DERIVED_GRAPH_SCHEMA_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "nodes": {
                "types": list(DERIVED_GRAPH_NODE_TYPES),
                "properties": list(DERIVED_GRAPH_NODE_PROPERTIES),
            },
            "edges": {
                "types": [edge_type.to_payload() for edge_type in DERIVED_GRAPH_EDGE_TYPES],
                "properties": list(DERIVED_GRAPH_EDGE_PROPERTIES),
            },
        }


def build_graph_schema() -> DerivedGraphSchema:
    return DerivedGraphSchema()


def make_graph_node(
    node_id: str,
    node_type: str,
    label: str,
    metadata: Mapping[str, Any] | None = None,
) -> DerivedGraphNode:
    if node_type not in DERIVED_GRAPH_NODE_TYPES:
        raise ValueError(f"Unsupported derived graph node type '{node_type}'.")
    return DerivedGraphNode(id=node_id, type=node_type, label=label, metadata=metadata or {})


def make_graph_edge(
    source: str,
    target: str,
    edge_type: str,
    metadata: Mapping[str, Any] | None = None,
) -> DerivedGraphEdge:
    edge_definition = next((item for item in DERIVED_GRAPH_EDGE_TYPES if item.type == edge_type), None)
    if edge_definition is None:
        raise ValueError(f"Unsupported derived graph edge type '{edge_type}'.")
    return DerivedGraphEdge(
        source=source,
        target=target,
        type=edge_definition.type,
        label=edge_definition.label,
        metadata=metadata or {},
    )


@dataclass(frozen=True)
class DerivedGraphBuildResult:
    nodes: tuple[DerivedGraphNode, ...]
    edges: tuple[DerivedGraphEdge, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)
    orphaned_node_ids: tuple[str, ...] = field(default_factory=tuple)
    unreachable_node_ids: tuple[str, ...] = field(default_factory=tuple)
    checksum: str = ""

    def to_payload(self, *, source_state_ref: str, generated_at: str | None = None) -> dict[str, Any]:
        return {
            "nodes": [node.to_payload() for node in self.nodes],
            "edges": [edge.to_payload() for edge in self.edges],
            "metadata": {
                "generatedAt": generated_at or _utc_timestamp(),
                "sourceStateRef": source_state_ref,
                "consistencyChecksum": self.checksum,
                "warnings": list(self.warnings),
                "orphanedNodeIds": list(self.orphaned_node_ids),
                "unreachableNodeIds": list(self.unreachable_node_ids),
            },
        }


@dataclass(frozen=True)
class GraphConsistencyIssue:
    severity: str
    code: str
    message: str
    recovery: str

    def to_payload(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "recovery": self.recovery,
        }


@dataclass(frozen=True)
class GraphConsistencyResult:
    status: str
    blocks_packet_emission: bool
    issues: tuple[GraphConsistencyIssue, ...] = field(default_factory=tuple)

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "blocksPacketEmission": self.blocks_packet_emission,
            "issues": [issue.to_payload() for issue in self.issues],
        }


def rebuild_derived_graph(landscape_state: Any) -> DerivedGraphBuildResult:
    nodes = _build_nodes(landscape_state)
    edges, warnings = _build_edges(landscape_state)
    orphaned_node_ids = _find_orphaned_node_ids(nodes, edges)
    unreachable_node_ids = _find_unreachable_node_ids(nodes, edges)
    checksum = generate_consistency_checksum(nodes, edges)
    return DerivedGraphBuildResult(
        nodes=tuple(sorted(nodes, key=lambda node: node.id)),
        edges=tuple(sorted(edges, key=lambda edge: _edge_id(edge))),
        warnings=tuple(warnings),
        orphaned_node_ids=tuple(orphaned_node_ids),
        unreachable_node_ids=tuple(unreachable_node_ids),
        checksum=checksum,
    )


def write_derived_graph(
    docs_path: str | Path,
    landscape_state: Any,
    *,
    source_state_ref: str | None = None,
) -> Path:
    docs_root = Path(docs_path)
    graph = rebuild_derived_graph(landscape_state)
    output_path = docs_root / "derived" / "graph.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = graph.to_payload(source_state_ref=source_state_ref or _source_state_ref(landscape_state))
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def generate_consistency_checksum(
    nodes: tuple[DerivedGraphNode, ...] | list[DerivedGraphNode],
    edges: tuple[DerivedGraphEdge, ...] | list[DerivedGraphEdge],
) -> str:
    node_ids = sorted(node.id for node in nodes)
    edge_ids = sorted(_edge_id(edge) for edge in edges)
    return hashlib.sha256("|".join([*node_ids, *edge_ids]).encode("utf-8")).hexdigest()


def validate_graph_consistency(
    graph_payload: Mapping[str, Any],
    landscape_state: Any,
) -> GraphConsistencyResult:
    graph_nodes = _payload_items(graph_payload, "nodes")
    graph_edges = _payload_items(graph_payload, "edges")
    metadata = graph_payload.get("metadata") if isinstance(graph_payload, Mapping) else {}
    metadata = metadata if isinstance(metadata, Mapping) else {}
    landscape_ids = set(getattr(landscape_state, "entities_by_id", {}).keys())
    node_ids = {str(node.get("id")) for node in graph_nodes if isinstance(node, Mapping) and node.get("id")}
    issues: list[GraphConsistencyIssue] = []

    for node_id in sorted(node_ids - landscape_ids):
        issues.append(
            GraphConsistencyIssue(
                severity="fail",
                code="graph_node_missing_from_landscape",
                message=f"Graph node '{node_id}' does not exist in authoritative landscape state.",
                recovery="Rebuild graph from current landscape state or restore the missing landscape entity.",
            )
        )

    for landscape_id in sorted(landscape_ids - node_ids):
        issues.append(
            GraphConsistencyIssue(
                severity="fail",
                code="landscape_entity_missing_from_graph",
                message=f"Landscape entity '{landscape_id}' is absent from derived graph.",
                recovery="Rebuild graph before packet emission.",
            )
        )

    for edge in graph_edges:
        if not isinstance(edge, Mapping):
            continue
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source not in node_ids or target not in node_ids:
            issues.append(
                GraphConsistencyIssue(
                    severity="fail",
                    code="graph_edge_references_missing_node",
                    message=f"Graph edge '{source}->{target}' references a non-existent graph node.",
                    recovery="Rebuild graph and fix any broken landscape relationships.",
                )
            )

    current_graph = rebuild_derived_graph(landscape_state)
    actual_checksum = str(metadata.get("consistencyChecksum") or "")
    if actual_checksum != current_graph.checksum:
        issues.append(
            GraphConsistencyIssue(
                severity="fail",
                code="graph_checksum_stale",
                message="Graph consistency checksum does not match current authoritative state.",
                recovery="Rebuild graph from current landscape state before packet emission.",
            )
        )

    for warning in current_graph.warnings:
        issues.append(
            GraphConsistencyIssue(
                severity="advisory",
                code="broken_landscape_reference",
                message=warning,
                recovery="Fix the referenced landscape relationship or accept advisory packet emission.",
            )
        )

    for node_id in current_graph.orphaned_node_ids:
        issues.append(
            GraphConsistencyIssue(
                severity="advisory",
                code="orphaned_graph_node",
                message=f"Graph node '{node_id}' has no incoming or outgoing edges.",
                recovery="Connect the entity through landscape relationships or accept advisory packet emission.",
            )
        )

    has_fail = any(issue.severity == "fail" for issue in issues)
    if has_fail:
        return GraphConsistencyResult(status="fail", blocks_packet_emission=True, issues=tuple(issues))
    if issues:
        return GraphConsistencyResult(status="advisory", blocks_packet_emission=False, issues=tuple(issues))
    return GraphConsistencyResult(status="pass", blocks_packet_emission=False, issues=())


def _build_nodes(landscape_state: Any) -> list[DerivedGraphNode]:
    nodes: list[DerivedGraphNode] = []
    entities_by_id = getattr(landscape_state, "entities_by_id", {})
    for entity in entities_by_id.values():
        nodes.append(
            make_graph_node(
                entity.semantic_id,
                entity.entity_type,
                entity.name,
                {
                    "opaqueId": entity.opaque_id,
                    "sourcePath": str(entity.source_path),
                    **dict(entity.metadata),
                },
            )
        )
    return nodes


def _payload_items(payload: Mapping[str, Any], key: str) -> list[Any]:
    value = payload.get(key) if isinstance(payload, Mapping) else []
    return list(value) if isinstance(value, list) else []


def _build_edges(landscape_state: Any) -> tuple[list[DerivedGraphEdge], list[str]]:
    edges: list[DerivedGraphEdge] = []
    warnings = list(getattr(landscape_state, "warnings", ()))
    entities_by_id = getattr(landscape_state, "entities_by_id", {})

    for entity in entities_by_id.values():
        for relationship_name, relationships in sorted(entity.resolved_relationships.items()):
            for relationship in relationships:
                if relationship.target_entity is None:
                    warnings.append(
                        f"Broken graph reference '{relationship_name}' from '{entity.semantic_id}' to '{relationship.target_id}'."
                    )
                    continue

                edge_type = _edge_type_for(entity.entity_type, relationship.target_entity.entity_type)
                source = entity.semantic_id
                target = relationship.target_id

                if edge_type is None:
                    reverse_edge_type = _edge_type_for(relationship.target_entity.entity_type, entity.entity_type)
                    if reverse_edge_type is None:
                        continue
                    edge_type = reverse_edge_type
                    source = relationship.target_id
                    target = entity.semantic_id

                edges.append(
                    make_graph_edge(
                        source,
                        target,
                        edge_type,
                        {
                            "source_relationship": relationship_name,
                            **dict(relationship.metadata),
                        },
                    )
                )

    return _dedupe_edges(edges), warnings


def _edge_type_for(source_type: str, target_type: str) -> str | None:
    for edge_type in DERIVED_GRAPH_EDGE_TYPES:
        if edge_type.source_type == source_type and edge_type.target_type == target_type:
            return edge_type.type
    return None


def _dedupe_edges(edges: list[DerivedGraphEdge]) -> list[DerivedGraphEdge]:
    deduped: dict[str, DerivedGraphEdge] = {}
    for edge in edges:
        deduped[_edge_id(edge)] = edge
    return list(deduped.values())


def _find_orphaned_node_ids(nodes: list[DerivedGraphNode], edges: list[DerivedGraphEdge]) -> list[str]:
    connected = {edge.source for edge in edges} | {edge.target for edge in edges}
    return sorted(node.id for node in nodes if node.id not in connected)


def _find_unreachable_node_ids(nodes: list[DerivedGraphNode], edges: list[DerivedGraphEdge]) -> list[str]:
    system_roots = sorted(node.id for node in nodes if node.type == "system")
    if not system_roots:
        return sorted(node.id for node in nodes)

    adjacency: dict[str, set[str]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source, set()).add(edge.target)

    reachable: set[str] = set()
    pending = list(system_roots)
    while pending:
        node_id = pending.pop()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        pending.extend(sorted(adjacency.get(node_id, ())))

    return sorted(node.id for node in nodes if node.id not in reachable)


def _edge_id(edge: DerivedGraphEdge) -> str:
    return f"{edge.source}->{edge.target}:{edge.type}"


def _source_state_ref(landscape_state: Any) -> str:
    load_sequence = sorted(getattr(landscape_state, "load_sequence", ()))
    return hashlib.sha256("|".join(load_sequence).encode("utf-8")).hexdigest()


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
