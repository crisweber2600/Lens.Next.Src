from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
import sys
import types

import pytest


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "doctor_checks.py"
SPEC = importlib.util.spec_from_file_location("nextlens_doctor_checks", SCRIPT_PATH)
DOCTOR_CHECKS = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = DOCTOR_CHECKS
SPEC.loader.exec_module(DOCTOR_CHECKS)

DERIVED_GRAPH_PATH = Path(__file__).resolve().parent.parent / "derived_graph.py"
DERIVED_GRAPH_SPEC = importlib.util.spec_from_file_location("nextlens_derived_graph", DERIVED_GRAPH_PATH)
DERIVED_GRAPH = importlib.util.module_from_spec(DERIVED_GRAPH_SPEC)
assert DERIVED_GRAPH_SPEC is not None and DERIVED_GRAPH_SPEC.loader is not None
sys.modules[DERIVED_GRAPH_SPEC.name] = DERIVED_GRAPH
DERIVED_GRAPH_SPEC.loader.exec_module(DERIVED_GRAPH)

LANDSCAPE_STORE_PATH = Path(__file__).resolve().parent.parent / "landscape_store.py"
LANDSCAPE_STORE_SPEC = importlib.util.spec_from_file_location("nextlens_landscape_store", LANDSCAPE_STORE_PATH)
LANDSCAPE_STORE = importlib.util.module_from_spec(LANDSCAPE_STORE_SPEC)
assert LANDSCAPE_STORE_SPEC is not None and LANDSCAPE_STORE_SPEC.loader is not None
sys.modules[LANDSCAPE_STORE_SPEC.name] = LANDSCAPE_STORE
LANDSCAPE_STORE_SPEC.loader.exec_module(LANDSCAPE_STORE)


@dataclass(frozen=True)
class _SchemaEntity:
    entity_type: str
    semantic_id: str
    opaque_id: str
    name: str
    metadata: dict[str, object] = field(default_factory=dict)
    source_path: Path | None = None
    resolved_relationships: dict[str, object] = field(default_factory=dict)


def _build_landscape_state(
    entities_by_id: dict[str, object],
    *,
    warnings: tuple[str, ...] = (),
) -> SimpleNamespace:
    return SimpleNamespace(
        entities_by_id=entities_by_id,
        warnings=warnings,
        load_sequence=tuple(entities_by_id.keys()),
    )


def _reconstructed_connected_state(tmp_path: Path):
    system = LANDSCAPE_STORE.ReconstructedLandscapeEntity(
        entity_type="system",
        semantic_id="system-main",
        opaque_id="opaque-system-main",
        name="NextLens System",
        snapshot={},
        relationships={},
        metadata={},
        source_path=tmp_path / "system.yaml",
        resolved_relationships={},
    )
    role = LANDSCAPE_STORE.ReconstructedLandscapeEntity(
        entity_type="role",
        semantic_id="role-operator",
        opaque_id="opaque-role-operator",
        name="Operator",
        snapshot={},
        relationships={},
        metadata={},
        source_path=tmp_path / "role.yaml",
        resolved_relationships={},
    )
    outcome = LANDSCAPE_STORE.ReconstructedLandscapeEntity(
        entity_type="outcome",
        semantic_id="outcome-reduce-ambiguity",
        opaque_id="opaque-outcome-reduce-ambiguity",
        name="Reduce ambiguity",
        snapshot={},
        relationships={},
        metadata={},
        source_path=tmp_path / "outcome.yaml",
        resolved_relationships={},
    )
    journey = LANDSCAPE_STORE.ReconstructedLandscapeEntity(
        entity_type="journey",
        semantic_id="journey-onboard",
        opaque_id="opaque-journey-onboard",
        name="Onboard",
        snapshot={},
        relationships={},
        metadata={},
        source_path=tmp_path / "journey.yaml",
        resolved_relationships={},
    )
    system.resolved_relationships = {
        "roles": (
            LANDSCAPE_STORE.LandscapeRelationship("roles", role.semantic_id, role, {}),
        )
    }
    role.resolved_relationships = {
        "outcomes": (
            LANDSCAPE_STORE.LandscapeRelationship("outcomes", outcome.semantic_id, outcome, {}),
        )
    }
    outcome.resolved_relationships = {
        "journeys": (
            LANDSCAPE_STORE.LandscapeRelationship("journeys", journey.semantic_id, journey, {}),
        )
    }
    return _build_landscape_state(
        {
            system.semantic_id: system,
            role.semantic_id: role,
            outcome.semantic_id: outcome,
            journey.semantic_id: journey,
        }
    )


def _base_packet_payload() -> dict[str, object]:
    return {
        "trace": {
            "systemId": "system-main",
            "roleIds": ["role-operator"],
            "outcomeIds": ["outcome-reduce-ambiguity"],
            "journeyIds": ["journey-onboard"],
        },
        "selectionRationale": "selected by operator for this release",
        "bmadConsumerHints": {
            "prdInput": "product input",
            "uxInput": "ux input",
            "architectureInput": "architecture input",
        },
        "system": {
            "thesis": "Increase planning signal quality through deterministic selection",
        },
        "roles": [{"id": "role-operator"}],
        "outcomes": [{"id": "outcome-reduce-ambiguity"}],
        "journeys": [{"id": "journey-onboard"}],
        "openQuestions": ["What is success?"],
        "risks": ["Missing context"],
    }


def _base_selected_feature() -> dict[str, object]:
    return {
        "includedScope": [
            "system-main",
        ],
        "explicitOutOfScope": ["adjacent roadmap"],
    }


def _build_ok_context(tmp_path: Path) -> DOCTOR_CHECKS.DoctorCheckContext:
    state = _reconstructed_connected_state(tmp_path)
    graph_payload = DERIVED_GRAPH.rebuild_derived_graph(state).to_payload(
        source_state_ref="reconstruction:test"
    )
    return DOCTOR_CHECKS.DoctorCheckContext(
        landscape_state=state,
        derived_graph=graph_payload,
        packet_candidate=_base_packet_payload(),
        selected_feature=_base_selected_feature(),
        docs_path=tmp_path,
    )


def test_registry_contains_required_ep7_doctor_checks() -> None:
    check_ids = sorted(check.check_id for check in DOCTOR_CHECKS.build_default_doctor_check_registry().list_checks())

    assert check_ids == [
        "context-readiness",
        "feature-scope",
        "graph-consistency",
        "schema-validity",
        "traceability",
        "write-boundary",
    ]


def test_schema_validity_passes_for_well_formed_landscape() -> None:
    context = DOCTOR_CHECKS.DoctorCheckContext(
        landscape_state=_build_landscape_state(
            {
                "system-main": _SchemaEntity(
                    entity_type="system",
                    semantic_id="system-main",
                    opaque_id="opaque-system-main",
                    name="NextLens System",
                ),
                "role-operator": _SchemaEntity(
                    entity_type="role",
                    semantic_id="role-operator",
                    opaque_id="opaque-role-operator",
                    name="Operator",
                ),
            }
        ),
        derived_graph={},
    )
    result = DOCTOR_CHECKS._check_schema_validity(context)

    assert result.status == "pass"
    assert result.severity == "blocking"
    assert result.message == "All landscape entities pass schema checks."


def test_schema_validity_fails_for_incomplete_entity() -> None:
    context = DOCTOR_CHECKS.DoctorCheckContext(
        landscape_state=_build_landscape_state(
            {
                "broken": _SchemaEntity(
                    entity_type="system",
                    semantic_id="broken",
                    opaque_id="",
                    name="",
                ),
            }
        ),
        derived_graph={},
    )
    result = DOCTOR_CHECKS._check_schema_validity(context)

    assert result.status == "fail"
    assert result.severity == "blocking"
    assert "missing 'name'" in result.message or result.references


def test_feature_scope_rejects_adjacent_or_future_scope_entries() -> None:
    state = _reconstructed_connected_state(Path("."))
    context = DOCTOR_CHECKS.DoctorCheckContext(
        landscape_state=state,
        derived_graph={},
        selected_feature={
            "includedScope": ["adjacent journey map", "future feature draft"],
            "explicitOutOfScope": ["feature-other"],
        },
    )
    result = DOCTOR_CHECKS._check_feature_scope(context)

    assert result.status == "fail"
    assert result.severity == "blocking"
    assert "adjacent journey" in result.references[0]

    context = DOCTOR_CHECKS.DoctorCheckContext(
        landscape_state=state,
        derived_graph={},
        selected_feature={
            "includedScope": ["system-main"],
            "explicitOutOfScope": ["future-platform"],
        },
    )
    result = DOCTOR_CHECKS._check_feature_scope(context)
    assert result.status == "pass"
    assert result.severity == "blocking"


def test_traceability_identifies_unresolved_references(tmp_path: Path) -> None:
    context = _build_ok_context(tmp_path)
    packet = _base_packet_payload()
    packet["trace"] = {
        "systemId": "system-missing",
        "roleIds": ["role-missing"],
        "outcomeIds": ["outcome-missing"],
        "journeyIds": [],
    }
    context = DOCTOR_CHECKS.DoctorCheckContext(
        landscape_state=context.landscape_state,
        derived_graph=context.derived_graph,
        packet_candidate=packet,
        selected_feature=_base_selected_feature(),
    )
    result = DOCTOR_CHECKS._check_traceability(context)

    assert result.status == "warning"
    assert result.severity == "advisory"
    assert "does not resolve" in result.message


def test_context_readiness_requires_required_inputs(tmp_path: Path) -> None:
    context = _build_ok_context(tmp_path)
    packet = _base_packet_payload()
    packet.pop("bmadConsumerHints")
    packet["roles"] = []
    context = DOCTOR_CHECKS.DoctorCheckContext(
        landscape_state=context.landscape_state,
        derived_graph=context.derived_graph,
        packet_candidate=packet,
        selected_feature=_base_selected_feature(),
    )
    result = DOCTOR_CHECKS._check_context_readiness(context)

    assert result.status == "warning"
    assert result.severity == "advisory"
    assert "prdInput" in result.references[0]


def test_write_boundary_blocks_non_contained_targets(tmp_path: Path) -> None:
    state = _build_landscape_state({}, warnings=())
    context = DOCTOR_CHECKS.DoctorCheckContext(
        landscape_state=state,
        derived_graph={},
        docs_path=tmp_path,
        write_targets=["../outside/file.yaml", "release/notes.md"],
    )
    result = DOCTOR_CHECKS._check_write_boundary(context)

    assert result.status == "fail"
    assert result.severity == "blocking"
    assert "outside docs path" in result.references[0]


def test_graph_consistency_warns_when_validation_raises(monkeypatch) -> None:
    state = _reconstructed_connected_state(Path("."))
    context = DOCTOR_CHECKS.DoctorCheckContext(
        landscape_state=state,
        derived_graph={"nodes": [], "edges": []},
    )
    fake_issue = SimpleNamespace(message="unexpected graph error")
    fake_module = types.SimpleNamespace(
        validate_graph_consistency=lambda *_: SimpleNamespace(
            status="fail", issues=(fake_issue,)
        )
    )
    monkeypatch.setattr(DOCTOR_CHECKS, "_load_runtime_module", lambda *args: fake_module)
    result = DOCTOR_CHECKS._check_graph_consistency(context)
    assert result.status == "warning"
    assert result.severity == "advisory"
    assert "unexpected graph error" in result.references


def test_graph_consistency_passes_for_connected_graph(tmp_path: Path) -> None:
    state = _reconstructed_connected_state(tmp_path)
    graph_payload = DERIVED_GRAPH.rebuild_derived_graph(state).to_payload(source_state_ref="reconstruction:test")
    context = DOCTOR_CHECKS.DoctorCheckContext(landscape_state=state, derived_graph=graph_payload)

    result = DOCTOR_CHECKS._check_graph_consistency(context)

    assert result.status == "pass"
    assert result.severity == "advisory"


def test_write_doctor_jsonl_report_and_summary(tmp_path: Path) -> None:
    context = _build_ok_context(tmp_path)
    run_result = DOCTOR_CHECKS.build_default_doctor_check_registry().run_all(context)
    report_path = DOCTOR_CHECKS.write_doctor_jsonl_report(run_result, tmp_path)

    lines = [json.loads(line) for line in report_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == len(run_result.results) + 1
    assert lines[0]["check_id"] == "context-readiness"
    summary = lines[-1]
    assert summary["checks_run"] == 6
    assert summary["passed"] == 6
    assert summary["overall_status"] == "pass"


def test_run_preflight_doctor_checks_blocks_on_blocking_findings(tmp_path: Path) -> None:
    context = _build_ok_context(tmp_path)
    context = DOCTOR_CHECKS.DoctorCheckContext(
        landscape_state=context.landscape_state,
        derived_graph=context.derived_graph,
        packet_candidate=context.packet_candidate,
        selected_feature={"includedScope": []},
        docs_path=context.docs_path,
    )
    result = DOCTOR_CHECKS.run_preflight_doctor_checks(context)

    assert result.status == "blocked"
    assert result.allow_emission is False
    assert result.operation_blocked is True
    assert result.operator_prompted is False
    assert result.report_path is not None
    assert result.report_path.exists()


def test_run_preflight_doctor_checks_prompts_for_advisory_and_uses_operator_response(
    tmp_path: Path,
) -> None:
    context = _build_ok_context(tmp_path)
    packet = _base_packet_payload()
    packet["trace"]["systemId"] = "system-missing"
    context = DOCTOR_CHECKS.DoctorCheckContext(
        landscape_state=context.landscape_state,
        derived_graph=context.derived_graph,
        packet_candidate=packet,
        selected_feature=_base_selected_feature(),
        docs_path=context.docs_path,
        write_targets=[".nextlens/state.yaml"],
    )
    declined = DOCTOR_CHECKS.run_preflight_doctor_checks(
        context,
        prompt_fn=lambda prompt: "n",
    )
    assert declined.status == "blocked"
    assert declined.allow_emission is False
    assert declined.operation_blocked is True
    assert declined.operator_prompted is True
    assert declined.operator_response == "n"

    allowed = DOCTOR_CHECKS.run_preflight_doctor_checks(
        context,
        prompt_fn=lambda prompt: "yes",
        run_id="approved-run",
    )
    assert allowed.status == "warning"
    assert allowed.allow_emission is True
    assert allowed.operation_blocked is False
    assert allowed.operator_prompted is True
    assert allowed.operator_response == "yes"
