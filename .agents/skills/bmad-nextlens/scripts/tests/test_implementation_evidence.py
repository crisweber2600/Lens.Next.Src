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


DOWNSTREAM = _load_module("nextlens_downstream_hierarchy_evidence", "downstream_hierarchy.py")


def test_validate_implementation_evidence_passes_required_story() -> None:
    evidence = _valid_evidence()

    result = DOWNSTREAM.validate_implementation_evidence(
        evidence,
        expected_packet_id="packet-1",
        expected_feature_id="feature-1",
        required_story_ids=["story-1"],
    )

    assert result.is_valid
    assert result.status == "pass"


def test_validate_implementation_evidence_accepts_completed_story_lineage() -> None:
    evidence = _valid_evidence()

    result = DOWNSTREAM.validate_implementation_evidence(
        evidence,
        expected_packet_id="packet-1",
        expected_feature_id="feature-1",
        packet_trace={"outcomeIds": ["outcome-1"], "journeyIds": ["journey-1"]},
    )

    assert result.is_valid


def test_validate_implementation_evidence_requires_completed_story_outcome() -> None:
    evidence = _valid_evidence()
    evidence["stories"][0]["tracesTo"]["outcomeIds"] = []

    result = DOWNSTREAM.validate_implementation_evidence(
        evidence,
        expected_packet_id="packet-1",
        expected_feature_id="feature-1",
        packet_trace={"outcomeIds": ["outcome-1"], "journeyIds": ["journey-1"]},
    )

    assert _error_by_field(result, "stories[0].tracesTo.outcomeIds").expected_type == "at least one outcome id"


def test_validate_implementation_evidence_requires_completed_story_journey() -> None:
    evidence = _valid_evidence()
    evidence["stories"][0]["tracesTo"]["journeyIds"] = []

    result = DOWNSTREAM.validate_implementation_evidence(
        evidence,
        expected_packet_id="packet-1",
        expected_feature_id="feature-1",
        packet_trace={"outcomeIds": ["outcome-1"], "journeyIds": ["journey-1"]},
    )

    assert _error_by_field(result, "stories[0].tracesTo.journeyIds").expected_type == "at least one journey id"


def test_validate_implementation_evidence_rejects_unresolved_outcome() -> None:
    evidence = _valid_evidence()
    evidence["stories"][0]["tracesTo"]["outcomeIds"] = ["outcome-missing"]

    result = DOWNSTREAM.validate_implementation_evidence(
        evidence,
        expected_packet_id="packet-1",
        expected_feature_id="feature-1",
        packet_trace={"outcomeIds": ["outcome-1"], "journeyIds": ["journey-1"]},
    )

    assert _error_by_field(result, "stories[0].tracesTo.outcomeIds").expected_type == "known packet trace outcome ids"


def test_validate_implementation_evidence_rejects_unresolved_journey() -> None:
    evidence = _valid_evidence()
    evidence["stories"][0]["tracesTo"]["journeyIds"] = ["journey-missing"]

    result = DOWNSTREAM.validate_implementation_evidence(
        evidence,
        expected_packet_id="packet-1",
        expected_feature_id="feature-1",
        packet_trace={"outcomeIds": ["outcome-1"], "journeyIds": ["journey-1"]},
    )

    assert _error_by_field(result, "stories[0].tracesTo.journeyIds").expected_type == "known packet trace journey ids"


def test_validate_implementation_evidence_keeps_legacy_list_trace_compatible() -> None:
    evidence = _valid_evidence()
    evidence["stories"][0]["tracesTo"] = ["feature-1"]

    result = DOWNSTREAM.validate_implementation_evidence(
        evidence,
        expected_packet_id="packet-1",
        expected_feature_id="feature-1",
        packet_trace={"outcomeIds": ["outcome-1"], "journeyIds": ["journey-1"]},
    )

    assert result.is_valid


def test_validate_implementation_evidence_reports_missing_and_optional_stories() -> None:
    evidence = _valid_evidence()

    result = DOWNSTREAM.validate_implementation_evidence(
        evidence,
        required_story_ids=["story-2"],
        optional_story_ids=["story-3"],
    )

    assert not result.is_valid
    assert _error_by_field(result, "stories.missing").expected_type == "story evidence for required stories"
    assert _warning_by_field(result, "stories.optional").expected_type == "story evidence for optional stories"


def test_validate_implementation_evidence_flags_mismatched_ids_and_traces() -> None:
    evidence = _valid_evidence()
    evidence["packetId"] = "packet-x"
    evidence["featureId"] = "feature-x"
    evidence["stories"][0]["tracesTo"] = ["artifact-1"]

    result = DOWNSTREAM.validate_implementation_evidence(
        evidence,
        expected_packet_id="packet-1",
        expected_feature_id="feature-1",
    )

    assert _error_by_field(result, "packetId").expected_type == "string 'packet-1'"
    assert _error_by_field(result, "featureId").expected_type == "string 'feature-1'"
    assert _error_by_field(result, "stories[0].tracesTo").expected_type == "include feature 'feature-1'"


def _valid_evidence() -> dict[str, object]:
    return DOWNSTREAM.build_implementation_evidence(
        packet_id="packet-1",
        feature_id="feature-1",
        source_type="manual",
        bmad_artifact_bundle_ref="docs/.nextlens/bundle.yaml",
        stories=[
            {
                "id": "story-1",
                "status": "done",
                "tracesTo": {
                    "packetId": "packet-1",
                    "featureId": "feature-1",
                    "outcomeIds": ["outcome-1"],
                    "journeyIds": ["journey-1"],
                },
                "evidenceRefs": ["commit-123"],
            }
        ],
        scope_observations=[],
        goal_evidence=["goal-1"],
        outcome_evidence=["outcome-1"],
        journey_evidence=["journey-1"],
        now_factory=lambda: datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc),
    )


def _error_by_field(result: object, field_name: str) -> object:
    for error in result.errors:
        if error.field == field_name:
            return error
    raise AssertionError(f"expected validation error for {field_name}")


def _warning_by_field(result: object, field_name: str) -> object:
    for warning in result.warnings:
        if warning.field == field_name:
            return warning
    raise AssertionError(f"expected validation warning for {field_name}")
