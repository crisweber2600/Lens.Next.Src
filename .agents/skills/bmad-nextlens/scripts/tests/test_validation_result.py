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


DOWNSTREAM = _load_module("nextlens_downstream_hierarchy_validation", "downstream_hierarchy.py")


def test_validation_result_requires_evidence() -> None:
    result = DOWNSTREAM.build_validation_result(None)

    assert result["status"] == "failed"
    assert result["evidenceStatus"] == "missing"


def test_validation_result_marks_salmon_required_for_upstream_change() -> None:
    evidence = _valid_evidence(scope_observations=[{"type": "upstream_assumption_change"}])

    result = DOWNSTREAM.build_validation_result(evidence)

    assert result["status"] == "salmon_required"
    assert result["salmonRequired"] is True
    assert result["scopeStatus"] == "warning"


def test_validation_result_fails_when_journey_proof_missing() -> None:
    evidence = _valid_evidence(outcome_evidence=["outcome-1"], journey_evidence=[])

    result = DOWNSTREAM.build_validation_result(
        evidence,
        required_outcome_ids=["outcome-1"],
        required_journey_ids=["journey-1"],
    )

    assert result["outcomeStatus"] == "pass"
    assert result["journeyStatus"] == "fail"
    assert result["status"] == "failed"


def _valid_evidence(
    *,
    scope_observations: list[dict[str, object]] | None = None,
    outcome_evidence: list[str] | None = None,
    journey_evidence: list[str] | None = None,
) -> dict[str, object]:
    return DOWNSTREAM.build_implementation_evidence(
        packet_id="packet-1",
        feature_id="feature-1",
        source_type="manual",
        bmad_artifact_bundle_ref="docs/.nextlens/bundle.yaml",
        stories=[
            {
                "id": "story-1",
                "status": "done",
                "tracesTo": ["feature-1"],
                "evidenceRefs": ["commit-123"],
            }
        ],
        scope_observations=scope_observations or [],
        goal_evidence=["goal-1"],
        outcome_evidence=outcome_evidence or [],
        journey_evidence=journey_evidence or [],
        now_factory=lambda: datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc),
    )
