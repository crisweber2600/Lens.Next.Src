from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).resolve().parent.parent / "feature_packet_schema.py"
SPEC = importlib.util.spec_from_file_location("nextlens_feature_packet_schema", MODULE_PATH)
FEATURE_PACKET_SCHEMA = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = FEATURE_PACKET_SCHEMA
SPEC.loader.exec_module(FEATURE_PACKET_SCHEMA)


def test_valid_feature_packet_passes_schema_validation() -> None:
    packet = _valid_packet()

    result = FEATURE_PACKET_SCHEMA.validate_feature_packet_schema(
        packet,
        selected_candidate_id="feature-password-recovery",
    )

    assert result.is_valid
    assert result.status == "pass"
    assert result.errors == ()


def test_missing_required_field_reports_field_expected_type_and_message() -> None:
    packet = _valid_packet()
    packet.pop("derivedGraphRef")

    result = FEATURE_PACKET_SCHEMA.validate_feature_packet_schema(packet)

    assert not result.is_valid
    error = _error_by_field(result, "derivedGraphRef")
    assert error.expected_type == "string"
    assert error.actual_value is None
    assert "derivedGraphRef is required" in error.message


def test_wrong_types_report_actual_values_for_top_level_and_nested_fields() -> None:
    packet = _valid_packet()
    packet["sourceContextRefs"] = "docs/context.yaml"
    packet["selectedFeature"]["name"] = 42

    result = FEATURE_PACKET_SCHEMA.validate_feature_packet_schema(packet)

    source_refs_error = _error_by_field(result, "sourceContextRefs")
    nested_error = _error_by_field(result, "selectedFeature.name")
    assert source_refs_error.expected_type == "array"
    assert source_refs_error.actual_value == "docs/context.yaml"
    assert nested_error.expected_type == "string"
    assert nested_error.actual_value == 42


def test_schema_version_source_mode_uuid_timestamp_and_selected_candidate_are_enforced() -> None:
    packet = _valid_packet()
    packet["schemaVersion"] = "nextlens.feature-packet.v2"
    packet["sourceMode"] = "bottom_up"
    packet["packetId"] = "packet-123"
    packet["createdAt"] = "not-a-date"
    packet["featureId"] = "feature-other"

    result = FEATURE_PACKET_SCHEMA.validate_feature_packet_schema(
        packet,
        selected_candidate_id="feature-password-recovery",
        expected_source_mode="top_down",
    )

    assert _error_by_field(result, "schemaVersion").expected_type == "string 'nextlens.feature-packet.v1'"
    assert _error_by_field(result, "sourceMode").expected_type == "string 'top_down'"
    assert _error_by_field(result, "packetId").expected_type == "UUID string"
    assert _error_by_field(result, "createdAt").expected_type == "ISO 8601 timestamp string"
    assert _error_by_field(result, "featureId").expected_type == "selected candidate id 'feature-password-recovery'"


def test_schema_accepts_bottom_up_when_expected_source_mode_matches() -> None:
    packet = _valid_packet()
    packet["sourceMode"] = "bottom_up"

    result = FEATURE_PACKET_SCHEMA.validate_feature_packet_schema(
        packet,
        selected_candidate_id="feature-password-recovery",
        expected_source_mode="bottom_up",
    )

    assert result.is_valid
    assert result.status == "pass"


def test_nested_required_trace_rationale_and_bmad_hint_fields_are_validated() -> None:
    packet = _valid_packet()
    packet["trace"].pop("relationshipRefs")
    packet["selectionRationale"].pop("tieBreakEvidence")
    packet["bmadConsumerHints"].pop("readinessInput")

    result = FEATURE_PACKET_SCHEMA.validate_feature_packet_schema(packet)

    assert _error_by_field(result, "trace.relationshipRefs").expected_type == "array"
    assert _error_by_field(result, "selectionRationale.tieBreakEvidence").expected_type == "object"
    assert _error_by_field(result, "bmadConsumerHints.readinessInput").expected_type == "string"


def _error_by_field(result: object, field_name: str) -> object:
    for error in result.errors:
        if error.field == field_name:
            return error
    raise AssertionError(f"expected validation error for {field_name}")


def _valid_packet() -> dict[str, object]:
    return {
        "schemaVersion": "nextlens.feature-packet.v1",
        "packetId": "550e8400-e29b-41d4-a716-446655440000",
        "featureId": "feature-password-recovery",
        "sourceMode": "top_down",
        "selectedFeature": {
            "id": "feature-password-recovery",
            "name": "Password Recovery",
            "goal": "Restore account access without expanding scope.",
            "includedScope": ["password-reset"],
            "explicitOutOfScope": ["admin-triage", "future-auth-platform"],
        },
        "trace": {
            "systemId": "system-nextlens",
            "discoveryEpochId": "epoch-2026-05-14",
            "roleIds": ["role-operator"],
            "outcomeIds": ["outcome-reduced-ambiguity"],
            "journeyIds": ["journey-account-recovery"],
            "operatingLoopIds": ["loop-planning"],
            "relationshipRefs": ["system-nextlens->role-operator"],
        },
        "selectionRationale": {
            "score": 88.5,
            "tieBreakEvidence": {"applied": ["outcome_alignment"]},
            "whyThisFeature": "Highest outcome alignment and readiness.",
            "whyNow": "Unblocks implementation planning.",
            "rejectedAlternates": ["feature-admin-triage"],
        },
        "sourceContextRefs": ["docs/context/topdown.yaml"],
        "authoritativeStateRef": "docs/.nextlens/state/feature-password-recovery.yaml",
        "derivedGraphRef": "docs/.nextlens/derived/graph.json",
        "doctorSummary": {"status": "pass"},
        "salmonRoutingSummary": {"status": "not_required"},
        "bmadConsumerHints": {
            "prdInput": "Product planning context.",
            "uxInput": "UX planning context.",
            "architectureInput": "Architecture planning context.",
            "epicStoryInput": "Epic and story planning context.",
            "readinessInput": "Implementation readiness context.",
        },
        "evidenceBundleRef": "docs/.nextlens/evidence/feature-password-recovery.json",
        "createdAt": "2026-05-14T12:34:56Z",
    }