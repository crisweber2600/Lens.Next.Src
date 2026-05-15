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


def test_tie_break_prefers_highest_outcome_alignment(monkeypatch: pytest.MonkeyPatch) -> None:
    ranked = _rank_with_mocked_scores(
        monkeypatch,
        _scored_candidate("feature-alpha", outcome_alignment=82.0),
        _scored_candidate("feature-beta", outcome_alignment=91.0),
    )

    assert [candidate.candidate_id for candidate in ranked] == ["feature-beta", "feature-alpha"]


def test_tie_break_prefers_highest_journey_criticality_after_outcome_alignment(monkeypatch: pytest.MonkeyPatch) -> None:
    ranked = _rank_with_mocked_scores(
        monkeypatch,
        _scored_candidate("feature-alpha", outcome_alignment=90.0, journey_criticality=70.0),
        _scored_candidate("feature-beta", outcome_alignment=90.0, journey_criticality=88.0),
    )

    assert [candidate.candidate_id for candidate in ranked] == ["feature-beta", "feature-alpha"]


def test_tie_break_prefers_fewer_unresolved_blockers(monkeypatch: pytest.MonkeyPatch) -> None:
    ranked = _rank_with_mocked_scores(
        monkeypatch,
        _scored_candidate(
            "feature-alpha",
            outcome_alignment=90.0,
            journey_criticality=88.0,
            unresolved_blockers=2,
        ),
        _scored_candidate(
            "feature-beta",
            outcome_alignment=90.0,
            journey_criticality=88.0,
            unresolved_blockers=1,
        ),
    )

    assert [candidate.candidate_id for candidate in ranked] == ["feature-beta", "feature-alpha"]


def test_tie_break_prefers_highest_evidence_clarity(monkeypatch: pytest.MonkeyPatch) -> None:
    ranked = _rank_with_mocked_scores(
        monkeypatch,
        _scored_candidate(
            "feature-alpha",
            outcome_alignment=90.0,
            journey_criticality=88.0,
            unresolved_blockers=1,
            evidence_clarity=74.0,
        ),
        _scored_candidate(
            "feature-beta",
            outcome_alignment=90.0,
            journey_criticality=88.0,
            unresolved_blockers=1,
            evidence_clarity=92.0,
        ),
    )

    assert [candidate.candidate_id for candidate in ranked] == ["feature-beta", "feature-alpha"]


def test_tie_break_prefers_earliest_candidate_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    ranked = _rank_with_mocked_scores(
        monkeypatch,
        _scored_candidate(
            "feature-alpha",
            outcome_alignment=90.0,
            journey_criticality=88.0,
            unresolved_blockers=1,
            evidence_clarity=92.0,
            stable_candidate_timestamp="2026-05-02T12:00:00Z",
        ),
        _scored_candidate(
            "feature-beta",
            outcome_alignment=90.0,
            journey_criticality=88.0,
            unresolved_blockers=1,
            evidence_clarity=92.0,
            stable_candidate_timestamp="2026-05-01T12:00:00Z",
        ),
    )

    assert [candidate.candidate_id for candidate in ranked] == ["feature-beta", "feature-alpha"]


def test_tie_break_falls_back_to_lexical_order(monkeypatch: pytest.MonkeyPatch) -> None:
    ranked = _rank_with_mocked_scores(
        monkeypatch,
        _scored_candidate(
            "feature-zeta",
            outcome_alignment=90.0,
            journey_criticality=88.0,
            unresolved_blockers=1,
            evidence_clarity=92.0,
            stable_candidate_timestamp="2026-05-01T12:00:00Z",
        ),
        _scored_candidate(
            "feature-alpha",
            outcome_alignment=90.0,
            journey_criticality=88.0,
            unresolved_blockers=1,
            evidence_clarity=92.0,
            stable_candidate_timestamp="2026-05-01T12:00:00Z",
        ),
    )

    assert [candidate.candidate_id for candidate in ranked] == ["feature-alpha", "feature-zeta"]


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


def _rank_with_mocked_scores(
    monkeypatch: pytest.MonkeyPatch,
    *scored_candidates: FEATURE_SCORING.ScoredCandidate,
) -> tuple[FEATURE_SCORING.ScoredCandidate, ...]:
    score_map = {candidate.candidate_id: candidate for candidate in scored_candidates}

    monkeypatch.setattr(
        FEATURE_SCORING,
        "score_candidate_feature",
        lambda candidate, context: score_map[candidate["id"]],
    )

    return FEATURE_SCORING.rank_candidate_features(
        {"candidateFeatures": [{"id": candidate.candidate_id} for candidate in reversed(scored_candidates)]}
    )


def _scored_candidate(
    candidate_id: str,
    *,
    composite_score: float = 80.0,
    unresolved_blockers: int = 0,
    stable_candidate_timestamp: str | None = None,
    outcome_alignment: float = 80.0,
    journey_criticality: float = 80.0,
    evidence_clarity: float = 80.0,
) -> FEATURE_SCORING.ScoredCandidate:
    factor_overrides = {
        "outcome_alignment": outcome_alignment,
        "journey_criticality": journey_criticality,
        "evidence_clarity": evidence_clarity,
    }
    factor_scores = tuple(
        FEATURE_SCORING.FactorScore(
            name=name,
            score=factor_overrides.get(name, 80.0),
            detail=name,
        )
        for name in FEATURE_SCORING.FACTOR_ORDER
    )
    return FEATURE_SCORING.ScoredCandidate(
        candidate_id=candidate_id,
        candidate_name=candidate_id,
        factor_scores=factor_scores,
        composite_score=composite_score,
        unresolved_blockers=unresolved_blockers,
        stable_candidate_timestamp=stable_candidate_timestamp,
    )