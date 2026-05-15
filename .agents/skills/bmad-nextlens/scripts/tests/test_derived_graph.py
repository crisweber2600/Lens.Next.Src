from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).resolve().parent.parent / "derived_graph.py"
SPEC = importlib.util.spec_from_file_location("nextlens_derived_graph", MODULE_PATH)
DERIVED_GRAPH = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = DERIVED_GRAPH
SPEC.loader.exec_module(DERIVED_GRAPH)


def test_build_graph_schema_exposes_required_node_types_and_properties() -> None:
    schema = DERIVED_GRAPH.build_graph_schema().to_payload()

    assert schema["version"] == "1.0"
    assert set(
        [
            "system",
            "role",
            "outcome",
            "journey",
            "operating_loop",
            "capability",
            "decision",
            "risk",
        ]
    ).issubset(set(schema["nodes"]["types"]))
    assert schema["nodes"]["properties"] == ["id", "type", "label", "metadata"]


def test_build_graph_schema_exposes_required_edge_types_and_properties() -> None:
    schema = DERIVED_GRAPH.build_graph_schema().to_payload()
    edge_types = {item["type"]: item for item in schema["edges"]["types"]}

    assert edge_types["system_role"] == {
        "type": "system_role",
        "source_type": "system",
        "target_type": "role",
        "label": "system requires role participation",
    }
    assert edge_types["role_outcome"]["target_type"] == "outcome"
    assert edge_types["outcome_journey"]["target_type"] == "journey"
    assert edge_types["journey_operating_loop"]["target_type"] == "operating_loop"
    assert edge_types["operating_loop_capability"]["target_type"] == "capability"
    assert edge_types["capability_decision"]["target_type"] == "decision"
    assert edge_types["feature_journey"]["target_type"] == "journey"
    assert edge_types["feature_outcome"]["target_type"] == "outcome"
    assert schema["edges"]["properties"] == ["source", "target", "type", "label", "metadata"]


def test_make_graph_node_returns_required_node_shape() -> None:
    node = DERIVED_GRAPH.make_graph_node(
        "role-system-architect",
        "role",
        "System Architect",
        {"source": "landscape", "status": "active"},
    )

    assert node.to_payload() == {
        "id": "role-system-architect",
        "type": "role",
        "label": "System Architect",
        "metadata": {"source": "landscape", "status": "active"},
    }


def test_make_graph_edge_returns_required_edge_shape() -> None:
    edge = DERIVED_GRAPH.make_graph_edge(
        "system-nextlens",
        "role-system-architect",
        "system_role",
        {"source_relationship": "systemId"},
    )

    assert edge.to_payload() == {
        "source": "system-nextlens",
        "target": "role-system-architect",
        "type": "system_role",
        "label": "system requires role participation",
        "metadata": {"source_relationship": "systemId"},
    }


def test_make_graph_node_rejects_unknown_node_type() -> None:
    try:
        DERIVED_GRAPH.make_graph_node("unknown-1", "unknown", "Unknown")
    except ValueError as exc:
        assert "Unsupported derived graph node type" in str(exc)
    else:  # pragma: no cover - defensive check in direct module test
        raise AssertionError("expected ValueError for unsupported node type")


def test_make_graph_edge_rejects_unknown_edge_type() -> None:
    try:
        DERIVED_GRAPH.make_graph_edge("source", "target", "unknown_edge")
    except ValueError as exc:
        assert "Unsupported derived graph edge type" in str(exc)
    else:  # pragma: no cover - defensive check in direct module test
        raise AssertionError("expected ValueError for unsupported edge type")


def test_rebuild_derived_graph_resolves_edges_and_reports_quality() -> None:
    state = _landscape_state(
        _entity("system", "system-nextlens", "NextLens"),
        _entity("role", "role-architect", "Architect", {"systemId": "system-nextlens", "outcomeIds": ["outcome-clarity"]}),
        _entity("outcome", "outcome-clarity", "Clarity", {"journeyIds": ["journey-intake", "journey-missing"]}),
        _entity("journey", "journey-intake", "Intake"),
        _entity("risk", "risk-unused", "Unused Risk"),
    )

    result = DERIVED_GRAPH.rebuild_derived_graph(state)
    edge_ids = {(edge.source, edge.target, edge.type) for edge in result.edges}

    assert ("system-nextlens", "role-architect", "system_role") in edge_ids
    assert ("role-architect", "outcome-clarity", "role_outcome") in edge_ids
    assert ("outcome-clarity", "journey-intake", "outcome_journey") in edge_ids
    assert "risk-unused" in result.orphaned_node_ids
    assert any("journey-missing" in warning for warning in result.warnings)
    assert result.checksum == DERIVED_GRAPH.generate_consistency_checksum(result.nodes, result.edges)


def test_write_derived_graph_persists_required_graph_shape(tmp_path: Path) -> None:
    state = _landscape_state(
        _entity("system", "system-nextlens", "NextLens"),
        _entity("role", "role-architect", "Architect", {"systemId": "system-nextlens"}),
    )

    output_path = DERIVED_GRAPH.write_derived_graph(tmp_path, state, source_state_ref="state-1")

    import json

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert output_path == tmp_path / "derived" / "graph.json"
    assert [node["id"] for node in payload["nodes"]] == ["role-architect", "system-nextlens"]
    assert payload["edges"][0]["type"] == "system_role"
    assert payload["metadata"]["sourceStateRef"] == "state-1"
    assert payload["metadata"]["consistencyChecksum"]


def test_validate_graph_consistency_passes_current_graph() -> None:
    state = _landscape_state(
        _entity("system", "system-nextlens", "NextLens"),
        _entity("role", "role-architect", "Architect", {"systemId": "system-nextlens"}),
    )
    graph = DERIVED_GRAPH.rebuild_derived_graph(state).to_payload(source_state_ref="state-1")

    result = DERIVED_GRAPH.validate_graph_consistency(graph, state)

    assert result.status == "pass"
    assert result.blocks_packet_emission is False
    assert result.issues == ()


def test_validate_graph_consistency_fails_for_stale_or_corrupt_graph() -> None:
    state = _landscape_state(
        _entity("system", "system-nextlens", "NextLens"),
        _entity("role", "role-architect", "Architect", {"systemId": "system-nextlens"}),
    )
    graph = DERIVED_GRAPH.rebuild_derived_graph(state).to_payload(source_state_ref="state-1")
    graph["nodes"] = graph["nodes"][:-1]
    graph["edges"].append({"source": "system-nextlens", "target": "missing-role", "type": "system_role"})
    graph["metadata"]["consistencyChecksum"] = "stale"

    result = DERIVED_GRAPH.validate_graph_consistency(graph, state)
    codes = {issue.code for issue in result.issues}

    assert result.status == "fail"
    assert result.blocks_packet_emission is True
    assert "landscape_entity_missing_from_graph" in codes
    assert "graph_edge_references_missing_node" in codes
    assert "graph_checksum_stale" in codes
    assert all(issue.recovery for issue in result.issues)


def test_validate_graph_consistency_reports_advisory_orphans_without_blocking() -> None:
    state = _landscape_state(_entity("risk", "risk-unused", "Unused Risk"))
    graph = DERIVED_GRAPH.rebuild_derived_graph(state).to_payload(source_state_ref="state-1")

    result = DERIVED_GRAPH.validate_graph_consistency(graph, state)

    assert result.status == "advisory"
    assert result.blocks_packet_emission is False
    assert any(issue.code == "orphaned_graph_node" for issue in result.issues)


class _Relationship:
    def __init__(self, relationship_name: str, target_id: str, target_entity: object | None) -> None:
        self.relationship_name = relationship_name
        self.target_id = target_id
        self.target_entity = target_entity
        self.metadata = {}


class _Entity:
    def __init__(self, entity_type: str, semantic_id: str, name: str, relationships: dict[str, object] | None = None) -> None:
        self.entity_type = entity_type
        self.semantic_id = semantic_id
        self.opaque_id = f"opaque-{semantic_id}"
        self.name = name
        self.metadata = {}
        self.source_path = Path(f"{semantic_id}.yaml")
        self.raw_relationships = relationships or {}
        self.resolved_relationships: dict[str, tuple[_Relationship, ...]] = {}


class _State:
    def __init__(self, entities: list[_Entity], warnings: tuple[str, ...]) -> None:
        self.entities_by_id = {entity.semantic_id: entity for entity in entities}
        self.load_sequence = tuple(entity.semantic_id for entity in entities)
        self.warnings = warnings


def _entity(entity_type: str, semantic_id: str, name: str, relationships: dict[str, object] | None = None) -> _Entity:
    return _Entity(entity_type, semantic_id, name, relationships)


def _landscape_state(*entities: _Entity) -> _State:
    state = _State(list(entities), ())
    warnings: list[str] = []
    for entity in entities:
        resolved: dict[str, list[_Relationship]] = {}
        for name, raw_value in entity.raw_relationships.items():
            values = raw_value if isinstance(raw_value, list) else [raw_value]
            for target_id in values:
                target = state.entities_by_id.get(str(target_id))
                if target is None:
                    warnings.append(f"Broken relationship '{name}' from '{entity.semantic_id}' to '{target_id}'.")
                resolved.setdefault(name, []).append(_Relationship(name, str(target_id), target))
        entity.resolved_relationships = {name: tuple(items) for name, items in resolved.items()}
    state.warnings = tuple(warnings)
    return state
