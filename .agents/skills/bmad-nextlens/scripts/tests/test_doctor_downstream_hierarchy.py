from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parent.parent


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


DOCTOR = _load_module("nextlens_doctor_downstream", "doctor_checks.py")
DOWNSTREAM = _load_module("nextlens_downstream_hierarchy_doctor", "downstream_hierarchy.py")
DERIVED_GRAPH = _load_module("nextlens_derived_graph_doctor", "derived_graph.py")
LANDSCAPE_STORE = _load_module("nextlens_landscape_store_doctor", "landscape_store.py")


def _base_packet() -> dict[str, object]:
    return {
        "packetId": "packet-1",
        "featureId": "feature-1",
        "bmadConsumerHints": {
            "prdInput": "product input",
            "uxInput": "ux input",
            "architectureInput": "architecture input",
            "epicStoryInput": "epic input",
            "readinessInput": "readiness input",
        },
    }


def _build_state(tmp_path: Path):
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
    system.resolved_relationships = {
        "roles": (
            LANDSCAPE_STORE.LandscapeRelationship("roles", role.semantic_id, role, {}),
        )
    }
    return type(
        "State",
        (),
        {
            "entities_by_id": {system.semantic_id: system, role.semantic_id: role},
            "warnings": (),
            "load_sequence": (system.semantic_id, role.semantic_id),
        },
    )()


def test_handoff_missing_required_artifact_blocks(tmp_path: Path) -> None:
    packet = _base_packet()
    packet["bmadConsumerHints"]["prdInput"] = "handoff/prd-input.md"
    context = DOCTOR.DoctorCheckContext(
        landscape_state=None,
        derived_graph={},
        packet_candidate=packet,
        docs_path=tmp_path,
    )
    result = DOCTOR._check_handoff_artifacts_required(context)
    assert result.status == "fail"
    assert result.severity == "blocking"


def test_handoff_missing_optional_artifact_warns(tmp_path: Path) -> None:
    packet = _base_packet()
    packet["bmadConsumerHints"]["epicStoryInput"] = "handoff/epic-input.md"
    context = DOCTOR.DoctorCheckContext(
        landscape_state=None,
        derived_graph={},
        packet_candidate=packet,
        docs_path=tmp_path,
    )
    result = DOCTOR._check_handoff_artifacts_optional(context)
    assert result.status == "warning"
    assert result.severity == "advisory"


def test_handoff_scope_boundary_blocks_on_expansion(tmp_path: Path) -> None:
    handoff_path = tmp_path / "handoff" / "prd-input.md"
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_path.write_text(
        "Please build adjacent journeys and future features for full coverage.\n",
        encoding="utf-8",
    )
    packet = _base_packet()
    packet["bmadConsumerHints"]["prdInput"] = str(handoff_path)
    context = DOCTOR.DoctorCheckContext(
        landscape_state=None,
        derived_graph={},
        packet_candidate=packet,
        docs_path=tmp_path,
    )
    result = DOCTOR._check_handoff_scope(context)
    assert result.status == "fail"
    assert result.severity == "blocking"


def test_bmad_artifact_bundle_schema_blocks() -> None:
    packet = _base_packet()
    packet["downstreamArtifacts"] = {"bmadArtifactBundle": {"packetId": "packet-1"}}
    context = DOCTOR.DoctorCheckContext(landscape_state=None, derived_graph={}, packet_candidate=packet)
    result = DOCTOR._check_bmad_artifact_bundle(context)
    assert result.status == "fail"
    assert result.severity == "blocking"


def test_bmad_story_trace_blocks() -> None:
    bundle = DOWNSTREAM.build_bmad_artifact_bundle(
        packet_id="packet-1",
        feature_id="feature-1",
        artifacts=[{"id": "prd", "type": "prd", "path": "docs/prd.md", "status": "complete"}],
        stories=[
            {
                "id": "story-1",
                "title": "Story One",
                "status": "ready",
                "tracesTo": ["unknown-artifact"],
                "createdAt": "2026-05-14T10:00:00Z",
            }
        ],
    )
    packet = _base_packet()
    packet["downstreamArtifacts"] = {"bmadArtifactBundle": bundle}
    context = DOCTOR.DoctorCheckContext(landscape_state=None, derived_graph={}, packet_candidate=packet)
    result = DOCTOR._check_bmad_story_trace(context)
    assert result.status == "fail"
    assert result.severity == "blocking"


def test_implementation_evidence_schema_blocks_when_requested() -> None:
    packet = _base_packet()
    packet["validationRequested"] = True
    packet["downstreamArtifacts"] = {"implementationEvidence": {"packetId": "packet-1"}}
    context = DOCTOR.DoctorCheckContext(landscape_state=None, derived_graph={}, packet_candidate=packet)
    result = DOCTOR._check_implementation_evidence_schema(context)
    assert result.status == "fail"
    assert result.severity == "blocking"


def test_implementation_evidence_identity_blocks_on_mismatch() -> None:
    evidence = DOWNSTREAM.build_implementation_evidence(
        packet_id="packet-2",
        feature_id="feature-2",
        source_type="manual",
        bmad_artifact_bundle_ref="bundle.yaml",
        stories=[{"id": "story-1", "status": "done", "tracesTo": ["feature-2"], "evidenceRefs": []}],
        scope_observations=[],
        goal_evidence=["goal-1"],
        outcome_evidence=["outcome-1"],
        journey_evidence=["journey-1"],
        now_factory=lambda: datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc),
    )
    packet = _base_packet()
    packet["downstreamArtifacts"] = {"implementationEvidence": evidence}
    context = DOCTOR.DoctorCheckContext(landscape_state=None, derived_graph={}, packet_candidate=packet)
    result = DOCTOR._check_implementation_evidence_identity(context)
    assert result.status == "fail"
    assert result.severity == "blocking"


def test_validation_result_schema_blocks() -> None:
    packet = _base_packet()
    packet["downstreamArtifacts"] = {"validationResult": {"schemaVersion": "invalid"}}
    context = DOCTOR.DoctorCheckContext(landscape_state=None, derived_graph={}, packet_candidate=packet)
    result = DOCTOR._check_validation_result_schema(context)
    assert result.status == "fail"
    assert result.severity == "blocking"


def test_salmon_signal_schema_blocks() -> None:
    packet = _base_packet()
    packet["downstreamArtifacts"] = {
        "salmonSignals": [
            {
                "schemaVersion": "nextlens.salmon-signal.v1",
                "id": "not-a-uuid",
            }
        ]
    }
    context = DOCTOR.DoctorCheckContext(landscape_state=None, derived_graph={}, packet_candidate=packet)
    result = DOCTOR._check_salmon_signal_schema(context)
    assert result.status == "fail"
    assert result.severity == "blocking"


def test_landscape_update_schema_blocks() -> None:
    packet = _base_packet()
    packet["downstreamArtifacts"] = {
        "landscapeUpdate": {"schemaVersion": "nextlens.landscape-update.v1"}
    }
    context = DOCTOR.DoctorCheckContext(landscape_state=None, derived_graph={}, packet_candidate=packet)
    result = DOCTOR._check_landscape_update_schema(context)
    assert result.status == "fail"
    assert result.severity == "blocking"


def test_derived_graph_authority_blocks() -> None:
    packet = _base_packet()
    packet["derivedGraphAuthoritative"] = True
    context = DOCTOR.DoctorCheckContext(landscape_state=None, derived_graph={}, packet_candidate=packet)
    result = DOCTOR._check_derived_graph_authority(context)
    assert result.status == "fail"
    assert result.severity == "blocking"


def test_derived_graph_stale_warns(tmp_path: Path) -> None:
    state = _build_state(tmp_path)
    graph_payload = DERIVED_GRAPH.rebuild_derived_graph(state).to_payload(source_state_ref="ref")
    graph_payload["metadata"]["consistencyChecksum"] = "stale"
    context = DOCTOR.DoctorCheckContext(
        landscape_state=state,
        derived_graph=graph_payload,
        packet_candidate=_base_packet(),
    )
    result = DOCTOR._check_derived_graph_stale(context)
    assert result.status == "warning"
    assert result.severity == "advisory"


def test_optional_review_evidence_warns_when_missing() -> None:
    evidence = DOWNSTREAM.build_implementation_evidence(
        packet_id="packet-1",
        feature_id="feature-1",
        source_type="manual",
        bmad_artifact_bundle_ref="bundle.yaml",
        stories=[{"id": "story-1", "status": "done", "tracesTo": ["feature-1"], "evidenceRefs": []}],
        scope_observations=[],
        goal_evidence=[],
        outcome_evidence=[],
        journey_evidence=[],
        now_factory=lambda: datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc),
    )
    packet = _base_packet()
    packet["downstreamArtifacts"] = {"implementationEvidence": evidence}
    context = DOCTOR.DoctorCheckContext(landscape_state=None, derived_graph={}, packet_candidate=packet)
    result = DOCTOR._check_review_evidence(context)
    assert result.status == "warning"
    assert result.severity == "advisory"
