from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


MODULE_PATH = Path(__file__).resolve().parent.parent / "feature_scoring.py"
SPEC = importlib.util.spec_from_file_location("nextlens_feature_scoring", MODULE_PATH)
FEATURE_SCORING = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = FEATURE_SCORING
SPEC.loader.exec_module(FEATURE_SCORING)


def test_score_candidate_feature_calculates_all_factor_scores_and_composite() -> None:
    context = _base_context()
    candidate = context["candidateFeatures"][0]

    scored = FEATURE_SCORING.score_candidate_feature(candidate, context)
    factor_map = scored.factor_map()

    assert [factor.name for factor in scored.factor_scores] == list(FEATURE_SCORING.FACTOR_ORDER)
    assert factor_map["outcome_alignment"].score == pytest.approx(66.6667)
    assert factor_map["journey_criticality"].score == pytest.approx(66.6667)
    assert factor_map["role_value"].score == pytest.approx(83.3333)
    assert factor_map["risk_reduction"].score == pytest.approx(90.0)
    assert factor_map["dependency_readiness"].score == pytest.approx(50.0)
    assert factor_map["implementation_boundedness"].score == pytest.approx(100.0)
    assert factor_map["bmad_readiness"].score == pytest.approx(66.6667)
    assert factor_map["evidence_clarity"].score == pytest.approx(100.0)
    assert factor_map["open_question_severity"].score == pytest.approx(90.0)
    assert scored.composite_score == pytest.approx(79.2593)


def test_risk_reduction_defaults_to_100_when_context_has_no_risks() -> None:
    context = _base_context()
    context["risks"] = []

    scored = FEATURE_SCORING.score_candidate_feature(context["candidateFeatures"][0], context)

    assert scored.factor_map()["risk_reduction"].score == 100.0


def test_implementation_boundedness_penalizes_missing_scope_and_spillage() -> None:
    context = _base_context()
    candidate = dict(context["candidateFeatures"][0])
    candidate.pop("scope")
    candidate.pop("summary", None)
    candidate.pop("description", None)
    candidate["outOfScope"] = []
    candidate["spillageDetected"] = True
    candidate["adjacentJourneyRefs"] = ["journey-payments"]
    candidate["futureFeatureRefs"] = ["feature-billing-2"]

    scored = FEATURE_SCORING.score_candidate_feature(candidate, context)

    assert scored.factor_map()["implementation_boundedness"].score == 0.0


def test_rank_candidate_features_is_deterministic_and_applies_tie_breakers() -> None:
    context = _base_context()
    context["candidateFeatures"] = [
        _candidate(
            candidate_id="feature-later",
            stable_timestamp="2026-05-10T12:00:00Z",
            dependency_statuses=(True,),
            open_questions=[{"id": "question-advisory", "severity": "advisory"}],
        ),
        _candidate(
            candidate_id="feature-earlier",
            stable_timestamp="2026-05-01T12:00:00Z",
            dependency_statuses=(True,),
            open_questions=[{"id": "question-advisory", "severity": "advisory"}],
        ),
    ]

    first_run = FEATURE_SCORING.rank_candidate_features(context)
    second_run = FEATURE_SCORING.rank_candidate_features(context)

    assert [candidate.candidate_id for candidate in first_run] == [
        "feature-earlier",
        "feature-later",
    ]
    assert [candidate.candidate_id for candidate in second_run] == [
        "feature-earlier",
        "feature-later",
    ]
    assert [candidate.composite_score for candidate in first_run] == [
        candidate.composite_score for candidate in second_run
    ]


def _base_context() -> dict[str, object]:
    return {
        "outcomes": [
            {"id": "outcome-1", "criticality": "high"},
            {"id": "outcome-2", "criticality": "medium"},
            {"id": "outcome-3", "criticality": "low"},
        ],
        "journeys": [
            {"id": "journey-1", "roleDependencyWeight": 4},
            {"id": "journey-2", "roleDependencyWeight": 2},
        ],
        "roles": [
            {"id": "role-1", "stakeholderImportance": 5},
            {"id": "role-2", "stakeholderImportance": 1},
        ],
        "risks": [
            {"id": "risk-1", "severity": "blocking"},
            {"id": "risk-2", "severity": "advisory"},
            {"id": "risk-3", "severity": "informational"},
        ],
        "openQuestions": [
            {"id": "question-advisory", "severity": "advisory"},
        ],
        "candidateFeatures": [
            _candidate(),
        ],
    }


def _candidate(
    *,
    candidate_id: str = "feature-auth-recovery",
    stable_timestamp: str = "2026-05-04T12:00:00Z",
    dependency_statuses: tuple[bool, ...] = (True, False),
    open_questions: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "id": candidate_id,
        "name": "Auth Recovery",
        "outcomeIds": ["outcome-1", "outcome-3"],
        "journeyIds": ["journey-1"],
        "roleIds": ["role-1"],
        "riskIds": ["risk-1", "risk-2"],
        "dependencies": [
            {"id": f"dep-{index + 1}", "satisfied": status}
            for index, status in enumerate(dependency_statuses)
        ],
        "scope": {
            "summary": "Bound password recovery to sign-in journeys only",
            "outOfScope": ["account provisioning", "admin tooling"],
        },
        "bmadArtifacts": {
            "prd": True,
            "ux": True,
            "architecture": False,
        },
        "trace": {
            "systemId": "system-nextlens",
            "roleIds": ["role-1"],
            "outcomeIds": ["outcome-1", "outcome-3"],
            "journeyIds": ["journey-1"],
            "featureId": candidate_id,
        },
        "openQuestions": open_questions or [
            {"id": "question-advisory", "severity": "advisory"},
        ],
        "stableCandidateTimestamp": stable_timestamp,
    }