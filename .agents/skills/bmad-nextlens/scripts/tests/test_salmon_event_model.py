from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).resolve().parent.parent / "salmon_event_model.py"
SPEC = importlib.util.spec_from_file_location("nextlens_salmon_event_model", MODULE_PATH)
SALMON_EVENT_MODEL = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = SALMON_EVENT_MODEL
SPEC.loader.exec_module(SALMON_EVENT_MODEL)


def test_build_salmon_event_schema_declares_version_required_fields_and_enums() -> None:
    schema = SALMON_EVENT_MODEL.build_salmon_event_schema()

    assert schema["schemaVersion"] == "1.0"
    assert "dedupFingerprint" in schema["required"]
    assert schema["sourceTypes"] == ["doctor", "human", "implementation", "review"]
    assert schema["severities"] == ["advisory", "blocking", "informational"]
    assert "bmadArtifacts" in schema["impactedNodeFields"]


def test_validate_salmon_event_accepts_canonical_event() -> None:
    result = SALMON_EVENT_MODEL.validate_salmon_event(_event())

    assert result.is_valid
    assert result.status == "pass"
    assert result.errors == ()


def test_validate_salmon_event_reports_missing_required_fields_and_wrong_types() -> None:
    event = _event()
    event.pop("dedupFingerprint")
    event["impactedNodes"]["journeys"] = "journey-1"
    event["source"]["type"] = "bot"

    result = SALMON_EVENT_MODEL.validate_salmon_event(event)

    assert _error_by_field(result, "dedupFingerprint").expected == "SHA256 hex string"
    assert _error_by_field(result, "impactedNodes.journeys").expected == "array"
    assert "doctor" in _error_by_field(result, "source.type").expected


def test_validate_salmon_event_enforces_uuid_timestamp_sha_and_string_lengths() -> None:
    event = _event()
    event["id"] = "event-1"
    event["createdAt"] = "not-a-date"
    event["dedupFingerprint"] = "abc"
    event["raisedFrom"] = "x" * 1001
    event["discovery"]["issueDescription"] = "x" * 5000

    result = SALMON_EVENT_MODEL.validate_salmon_event(event)

    assert _error_by_field(result, "id").expected == "UUID string"
    assert _error_by_field(result, "createdAt").expected == "ISO 8601 timestamp string"
    assert _error_by_field(result, "dedupFingerprint").expected == "SHA256 hex string"
    assert _error_by_field(result, "raisedFrom").expected == "string <= 1000 chars"
    assert all(error.field != "discovery.issueDescription" for error in result.errors)


def _error_by_field(result: object, field_name: str) -> object:
    for error in result.errors:
        if error.field == field_name:
            return error
    raise AssertionError(f"expected validation error for {field_name}")


def _event() -> dict[str, object]:
    return {
        "schemaVersion": "1.0",
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "raisedFrom": "doctor-check",
        "source": {"type": "doctor", "sourceId": "feature-scope"},
        "discovery": {
            "issueDescription": "Selected Feature scope includes an adjacent journey.",
            "impactedFeature": "feature-password-recovery",
            "impactLevel": "feature_scope_change",
        },
        "impactedNodes": {
            "features": ["feature-password-recovery"],
            "journeys": ["journey-account-recovery"],
            "outcomes": ["outcome-reduced-ambiguity"],
            "roles": ["role-operator"],
            "operatingLoops": ["loop-planning"],
            "capabilities": [],
            "bmadArtifacts": ["prd.md"],
        },
        "severity": "blocking",
        "recommendedAction": {"type": "block_packet", "details": "Remove adjacent journey from scope."},
        "dedupFingerprint": "0" * 64,
        "createdAt": "2026-05-14T12:34:56Z",
        "routingResult": {"status": "created", "targetRef": "docs/.nextlens/salmon/events/event.yaml"},
    }