from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


SCORING_PATH = Path(__file__).resolve().parent.parent / "feature_scoring.py"
SCORING_SPEC = importlib.util.spec_from_file_location("nextlens_feature_scoring_for_selection", SCORING_PATH)
FEATURE_SCORING = importlib.util.module_from_spec(SCORING_SPEC)
assert SCORING_SPEC is not None and SCORING_SPEC.loader is not None
sys.modules[SCORING_SPEC.name] = FEATURE_SCORING
SCORING_SPEC.loader.exec_module(FEATURE_SCORING)

MODULE_PATH = Path(__file__).resolve().parent.parent / "candidate_selection.py"
SPEC = importlib.util.spec_from_file_location("nextlens_candidate_selection", MODULE_PATH)
CANDIDATE_SELECTION = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = CANDIDATE_SELECTION
SPEC.loader.exec_module(CANDIDATE_SELECTION)


def test_render_candidate_selection_displays_selected_and_two_alternatives() -> None:
    ranked = _ranked_candidates()
    candidates_by_id = _candidates_by_id()

    lines = CANDIDATE_SELECTION.render_candidate_selection(ranked, candidates_by_id)

    assert lines[0] == "[stage:candidate-selection]"
    assert "1. Selected Candidate (Rank 1):" in lines
    assert "2. Alternative (Rank 2):" in lines
    assert "3. Alternative (Rank 3):" in lines
    assert "Reply with a rank number or candidate id to inspect another candidate." in lines
    assert "Confirm highlighted selection? [y/N]" in lines
    assert lines[-1] == "No Feature packet is emitted from candidate selection."


def test_render_candidate_selection_includes_selected_details_and_alternative_reason() -> None:
    ranked = _ranked_candidates()
    candidates_by_id = _candidates_by_id()

    lines = CANDIDATE_SELECTION.render_candidate_selection(ranked, candidates_by_id)

    assert "name: Password Recovery" in lines
    assert "goal: Restore account access without widening scope" in lines
    assert any(line.startswith("score: 88.50") for line in lines)
    assert any("rationale: outcome alignment 94.00" in line for line in lines)
    assert any("reason_not_selected: score delta 6.50; weaker outcome alignment" in line for line in lines)


def test_handle_candidate_selection_response_confirms_selected_candidate() -> None:
    ranked = _ranked_candidates()
    state = CANDIDATE_SELECTION.initialize_candidate_selection(ranked)

    result = CANDIDATE_SELECTION.handle_candidate_selection_response(
        state,
        "Y",
        ranked,
        _candidates_by_id(),
    )

    assert result.status == "confirmed"
    assert result.locked_selection == "feature-password-recovery"
    assert result.next_action == "confirmation_gate"


def test_handle_candidate_selection_response_does_not_confirm_blank_response() -> None:
    ranked = _ranked_candidates()
    state = CANDIDATE_SELECTION.initialize_candidate_selection(ranked)

    result = CANDIDATE_SELECTION.handle_candidate_selection_response(
        state,
        "",
        ranked,
        _candidates_by_id(),
    )

    assert result.status == "invalid_response"
    assert result.locked_selection is None
    assert result.next_action is None
    assert "No Feature packet is emitted from candidate selection." in result.output_lines


def test_handle_candidate_selection_response_accepts_rank_for_deeper_candidate_inspection() -> None:
    ranked = _ranked_candidates()
    candidates_by_id = _candidates_by_id()
    state = CANDIDATE_SELECTION.initialize_candidate_selection(ranked)

    result = CANDIDATE_SELECTION.handle_candidate_selection_response(
        state,
        "2",
        ranked,
        candidates_by_id,
    )

    assert result.status == "candidate_selected"
    assert result.locked_selection is None
    assert result.state.selected_candidate_id == "feature-journey-health"
    assert "2. Selected Candidate (Rank 2):" in result.output_lines
    assert result.output_lines[-1] == "No Feature packet is emitted from candidate selection."


def test_handle_candidate_selection_response_decline_offers_next_actions() -> None:
    ranked = _ranked_candidates()
    state = CANDIDATE_SELECTION.initialize_candidate_selection(ranked)

    result = CANDIDATE_SELECTION.handle_candidate_selection_response(
        state,
        "n",
        ranked,
        _candidates_by_id(),
    )

    assert result.status == "declined"
    assert result.state.mode == "awaiting_decline_action"
    assert result.output_lines == (
        "Selection declined.",
        "1. select different candidate",
        "2. cancel flow with no writes",
        "3. return to context with modifications",
    )


def test_handle_candidate_selection_response_allows_alternative_selection() -> None:
    ranked = _ranked_candidates()
    candidates_by_id = _candidates_by_id()
    state = CANDIDATE_SELECTION.initialize_candidate_selection(ranked)
    declined = CANDIDATE_SELECTION.handle_candidate_selection_response(
        state,
        "n",
        ranked,
        candidates_by_id,
    )
    choose_other = CANDIDATE_SELECTION.handle_candidate_selection_response(
        declined.state,
        "1",
        ranked,
        candidates_by_id,
    )
    alternative = CANDIDATE_SELECTION.handle_candidate_selection_response(
        choose_other.state,
        "2",
        ranked,
        candidates_by_id,
    )

    assert choose_other.status == "select_alternative"
    assert "Select alternative candidate:" in choose_other.output_lines
    assert alternative.status == "alternative_selected"
    assert alternative.state.selected_candidate_id == "feature-journey-health"
    assert "2. Selected Candidate (Rank 2):" in alternative.output_lines
    assert alternative.output_lines[-1] == "No Feature packet is emitted from candidate selection."


def _ranked_candidates() -> tuple[FEATURE_SCORING.ScoredCandidate, ...]:
    return (
        _scored_candidate(
            "feature-password-recovery",
            composite_score=88.5,
            outcome_alignment=94.0,
            journey_criticality=91.0,
            role_value=86.0,
            risk_reduction=84.0,
            evidence_clarity=93.0,
        ),
        _scored_candidate(
            "feature-journey-health",
            composite_score=82.0,
            outcome_alignment=87.0,
            journey_criticality=88.0,
            role_value=79.0,
            risk_reduction=81.0,
            evidence_clarity=84.0,
        ),
        _scored_candidate(
            "feature-admin-triage",
            composite_score=78.25,
            outcome_alignment=74.0,
            journey_criticality=80.0,
            role_value=75.0,
            risk_reduction=76.0,
            evidence_clarity=80.0,
        ),
    )


def _candidates_by_id() -> dict[str, dict[str, str]]:
    return {
        "feature-password-recovery": {
            "name": "Password Recovery",
            "goal": "Restore account access without widening scope",
        },
        "feature-journey-health": {
            "name": "Journey Health Dashboard",
            "goal": "Track onboarding health signals for operators",
        },
        "feature-admin-triage": {
            "name": "Admin Triage Queue",
            "goal": "Reduce handoff delays for unresolved failures",
        },
    }


def _scored_candidate(
    candidate_id: str,
    *,
    composite_score: float,
    outcome_alignment: float,
    journey_criticality: float,
    role_value: float,
    risk_reduction: float,
    evidence_clarity: float,
) -> FEATURE_SCORING.ScoredCandidate:
    scores = {
        "outcome_alignment": outcome_alignment,
        "journey_criticality": journey_criticality,
        "role_value": role_value,
        "risk_reduction": risk_reduction,
        "dependency_readiness": 80.0,
        "implementation_boundedness": 85.0,
        "bmad_readiness": 75.0,
        "evidence_clarity": evidence_clarity,
        "open_question_severity": 90.0,
    }
    factor_scores = tuple(
        FEATURE_SCORING.FactorScore(name=name, score=scores[name], detail=name)
        for name in FEATURE_SCORING.FACTOR_ORDER
    )
    return FEATURE_SCORING.ScoredCandidate(
        candidate_id=candidate_id,
        candidate_name=candidate_id,
        factor_scores=factor_scores,
        composite_score=composite_score,
        unresolved_blockers=0,
        stable_candidate_timestamp="2026-05-01T12:00:00Z",
    )