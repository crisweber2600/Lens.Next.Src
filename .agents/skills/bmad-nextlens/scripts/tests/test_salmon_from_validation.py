from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).resolve().parent.parent / "downstream_salmon_landscape.py"
SPEC = importlib.util.spec_from_file_location("nextlens_downstream_salmon_landscape", MODULE_PATH)
DOWNSTREAM = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = DOWNSTREAM
SPEC.loader.exec_module(DOWNSTREAM)


def test_generate_salmon_signals_from_validation_creates_routed_deduped_event(tmp_path: Path) -> None:
    validation = {
        "status": "pass",
        "salmonRequired": True,
        "featureId": "feature-password-recovery",
        "packetId": "packet-123",
        "validationId": "validation-001",
        "findings": [
            {
                "impactLevel": "journey_assumption_change",
                "issueDescription": "Journey assumption no longer holds for the selected feature.",
                "impactedNodes": {
                    "features": ["feature-password-recovery"],
                    "journeys": ["journey-onboard"],
                    "outcomes": [],
                    "roles": [],
                    "operatingLoops": [],
                    "capabilities": [],
                    "bmadArtifacts": [],
                },
                "severity": "advisory",
            }
        ],
    }

    result = DOWNSTREAM.generate_salmon_signals_from_validation(
        validation,
        tmp_path,
        now_factory=lambda: datetime(2026, 5, 14, 12, 34, 56, tzinfo=timezone.utc),
    )

    assert result.status == "pass"
    assert len(result.events) == 1
    event = result.events[0]
    assert event["schemaVersion"] == "nextlens.salmon-signal.v1"
    assert event["source"]["type"] == "validation"
    assert event["discovery"]["impactLevel"] == "journey_assumption_change"
    assert event["routingResult"]["targetRef"].replace("\\", "/").endswith(
        "landscape/journey/journey-onboard.yaml"
    )
    assert event["recommendedAction"]["type"] == "landscape_update"
    assert len(event["dedupFingerprint"]) == 64
    assert event["createdAt"] == "2026-05-14T12:34:56Z"


def test_generate_salmon_signals_from_validation_skips_without_salmon_required(tmp_path: Path) -> None:
    validation = {
        "status": "pass",
        "salmonRequired": False,
        "findings": [],
    }

    result = DOWNSTREAM.generate_salmon_signals_from_validation(validation, tmp_path)

    assert result.status == "skipped"
    assert result.events == ()


def test_validation_findings_without_impact_level_are_enriched(tmp_path: Path) -> None:
    validation = {
        "status": "salmon_required",
        "salmonRequired": True,
        "featureId": "feature-password-recovery",
        "validationId": "validation-impact-mapping",
        "findings": [
            {
                "category": "scope",
                "type": "scope_leak",
                "message": "Implementation touched explicitOutOfScope admin controls.",
                "impactedFeature": "feature-password-recovery",
            },
            {
                "category": "journey",
                "message": "Missing required journey evidence for journey-account-recovery.",
                "journeyId": "journey-account-recovery",
            },
            {
                "category": "outcome",
                "message": "Implemented value differs from promised outcome.",
                "outcomeId": "outcome-reduced-ambiguity",
            },
            {
                "category": "role",
                "message": "Stakeholder evidence mismatch for support agent.",
                "stakeholderId": "role-support-agent",
            },
            {
                "category": "operating_loop",
                "message": "Operating loop mismatch in planning loop.",
                "operatingLoopId": "loop-planning",
            },
            {
                "category": "durable_truth",
                "message": "Current landscape correction needed for routing capability.",
                "capabilityId": "capability-routing",
            },
            {
                "category": "architecture",
                "message": "Architecture assumption invalidated by implementation evidence.",
                "architectureRef": "architecture.md",
            },
            {
                "category": "implementation",
                "type": "minor_implementation_note",
                "message": "Minor implementation note only.",
            },
        ],
    }

    result = DOWNSTREAM.generate_salmon_signals_from_validation(validation, tmp_path)

    assert result.status == "pass"
    assert [event["discovery"]["impactLevel"] for event in result.events] == [
        "feature_scope_change",
        "journey_assumption_change",
        "outcome_reframe",
        "role_or_stakeholder_change",
        "operating_loop_change",
        "capability_or_landscape_update",
        "bmad_correct_course_required",
        "local_feature_note",
    ]
    by_impact = {event["discovery"]["impactLevel"]: event for event in result.events}
    assert by_impact["feature_scope_change"]["impactedNodes"]["features"] == ["feature-password-recovery"]
    assert by_impact["journey_assumption_change"]["impactedNodes"]["journeys"] == ["journey-account-recovery"]
    assert by_impact["outcome_reframe"]["impactedNodes"]["outcomes"] == ["outcome-reduced-ambiguity"]
    assert by_impact["role_or_stakeholder_change"]["impactedNodes"]["roles"] == ["role-support-agent"]
    assert by_impact["operating_loop_change"]["impactedNodes"]["operatingLoops"] == ["loop-planning"]
    assert by_impact["capability_or_landscape_update"]["impactedNodes"]["capabilities"] == ["capability-routing"]
    assert by_impact["bmad_correct_course_required"]["impactedNodes"]["bmadArtifacts"] == ["architecture.md"]
    assert by_impact["bmad_correct_course_required"]["recommendedAction"] == {
        "type": "correct_course",
        "details": "Run BMAD correct-course to revisit invalidated PRD, architecture, or story assumptions.",
    }
