"""Present ranked candidates and manage deterministic operator selection flow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class CandidateSelectionState:
    ranked_candidate_ids: tuple[str, ...]
    selected_candidate_id: str
    mode: str = "awaiting_confirmation"


@dataclass(frozen=True)
class CandidateSelectionResult:
    status: str
    state: CandidateSelectionState
    locked_selection: str | None = None
    next_action: str | None = None
    output_lines: tuple[str, ...] = ()


def initialize_candidate_selection(ranked_candidates: Sequence[Any]) -> CandidateSelectionState:
    if not ranked_candidates:
        raise ValueError("At least one ranked candidate is required.")
    candidate_ids = tuple(candidate.candidate_id for candidate in ranked_candidates)
    return CandidateSelectionState(
        ranked_candidate_ids=candidate_ids,
        selected_candidate_id=candidate_ids[0],
    )


def render_candidate_selection(
    ranked_candidates: Sequence[Any],
    candidates_by_id: Mapping[str, Mapping[str, Any]],
    *,
    selected_candidate_id: str | None = None,
) -> list[str]:
    if not ranked_candidates:
        raise ValueError("At least one ranked candidate is required.")

    ranked_lookup = {candidate.candidate_id: candidate for candidate in ranked_candidates}
    ordered_ids = [candidate.candidate_id for candidate in ranked_candidates]
    active_selected_id = selected_candidate_id or ordered_ids[0]
    if active_selected_id not in ranked_lookup:
        raise ValueError(f"Selected candidate '{active_selected_id}' is not present in the ranked candidates.")

    lines = ["[stage:candidate-selection]"]
    selected_candidate = ranked_lookup[active_selected_id]
    selected_payload = candidates_by_id.get(active_selected_id, {})
    selected_rank = ordered_ids.index(active_selected_id) + 1
    lines.extend(_render_selected_candidate(selected_candidate, selected_payload, selected_rank))

    alternative_rank = 2
    for candidate_id in ordered_ids:
        if candidate_id == active_selected_id:
            continue
        if alternative_rank > 3:
            break
        alternative_candidate = ranked_lookup[candidate_id]
        alternative_payload = candidates_by_id.get(candidate_id, {})
        lines.extend(
            _render_alternative_candidate(
                selected_candidate,
                alternative_candidate,
                alternative_payload,
                alternative_rank,
            )
        )
        alternative_rank += 1

    lines.append("Confirm selection? [Y/n]")
    return lines


def handle_candidate_selection_response(
    state: CandidateSelectionState,
    response: str,
    ranked_candidates: Sequence[Any],
    candidates_by_id: Mapping[str, Mapping[str, Any]],
) -> CandidateSelectionResult:
    ranked_lookup = {candidate.candidate_id: candidate for candidate in ranked_candidates}
    normalized = (response or "").strip().lower()

    if state.mode == "awaiting_confirmation":
        if normalized in {"", "y", "yes"}:
            return CandidateSelectionResult(
                status="confirmed",
                state=state,
                locked_selection=state.selected_candidate_id,
                next_action="confirmation_gate",
                output_lines=(f"selection_locked: {state.selected_candidate_id}",),
            )
        if normalized in {"n", "no"}:
            next_state = CandidateSelectionState(
                ranked_candidate_ids=state.ranked_candidate_ids,
                selected_candidate_id=state.selected_candidate_id,
                mode="awaiting_decline_action",
            )
            return CandidateSelectionResult(
                status="declined",
                state=next_state,
                output_lines=(
                    "Selection declined.",
                    "1. select different candidate",
                    "2. cancel flow with no writes",
                    "3. return to context with modifications",
                ),
            )
        return CandidateSelectionResult(
            status="invalid_response",
            state=state,
            output_lines=("Invalid response. Confirm selection? [Y/n]",),
        )

    if state.mode == "awaiting_decline_action":
        if normalized == "1":
            next_state = CandidateSelectionState(
                ranked_candidate_ids=state.ranked_candidate_ids,
                selected_candidate_id=state.selected_candidate_id,
                mode="awaiting_alternative_choice",
            )
            return CandidateSelectionResult(
                status="select_alternative",
                state=next_state,
                output_lines=tuple(_render_alternative_choice_menu(state, ranked_lookup, candidates_by_id)),
            )
        if normalized == "2":
            return CandidateSelectionResult(
                status="cancelled",
                state=state,
                next_action="cancel_no_writes",
                output_lines=("Selection cancelled. No writes performed.",),
            )
        if normalized == "3":
            return CandidateSelectionResult(
                status="return_to_context",
                state=state,
                next_action="return_to_context",
                output_lines=("Return to context with modifications requested.",),
            )
        return CandidateSelectionResult(
            status="invalid_response",
            state=state,
            output_lines=("Invalid option. Choose 1, 2, or 3.",),
        )

    if state.mode == "awaiting_alternative_choice":
        selected_candidate_id = _resolve_alternative_choice(state, normalized, ranked_lookup)
        if selected_candidate_id is None:
            return CandidateSelectionResult(
                status="invalid_response",
                state=state,
                output_lines=("Invalid candidate choice. Select rank 2, rank 3, or a candidate id.",),
            )
        next_state = CandidateSelectionState(
            ranked_candidate_ids=state.ranked_candidate_ids,
            selected_candidate_id=selected_candidate_id,
            mode="awaiting_confirmation",
        )
        return CandidateSelectionResult(
            status="alternative_selected",
            state=next_state,
            output_lines=tuple(
                render_candidate_selection(
                    ranked_candidates,
                    candidates_by_id,
                    selected_candidate_id=selected_candidate_id,
                )
            ),
        )

    raise ValueError(f"Unsupported candidate selection mode '{state.mode}'.")


def _render_selected_candidate(candidate: Any, payload: Mapping[str, Any], rank: int) -> list[str]:
    factors = candidate.factor_map()
    lines = [f"Selected Candidate (Rank {rank}):"]
    lines.append(f"name: {_candidate_name(candidate, payload)}")
    lines.append(f"goal: {_candidate_goal(payload)}")
    lines.append(f"score: {candidate.composite_score:.2f}")
    lines.append(
        "rationale: "
        + ", ".join(
            [
                f"outcome alignment {factors['outcome_alignment'].score:.2f}",
                f"journey criticality {factors['journey_criticality'].score:.2f}",
                f"role value {factors['role_value'].score:.2f}",
                f"risk reduction {factors['risk_reduction'].score:.2f}",
                f"evidence {factors['evidence_clarity'].score:.2f}",
            ]
        )
    )
    return lines


def _render_alternative_candidate(
    selected_candidate: Any,
    candidate: Any,
    payload: Mapping[str, Any],
    rank: int,
) -> list[str]:
    lines = [f"Alternative (Rank {rank}):"]
    lines.append(f"name: {_candidate_name(candidate, payload)}")
    lines.append(f"score: {candidate.composite_score:.2f}")
    lines.append(f"reason_not_selected: {_alternative_reason(selected_candidate, candidate)}")
    return lines


def _render_alternative_choice_menu(
    state: CandidateSelectionState,
    ranked_lookup: Mapping[str, Any],
    candidates_by_id: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    lines = ["Select alternative candidate:"]
    for rank, candidate_id in enumerate(state.ranked_candidate_ids, start=1):
        if candidate_id == state.selected_candidate_id or rank > 3:
            continue
        candidate = ranked_lookup[candidate_id]
        payload = candidates_by_id.get(candidate_id, {})
        lines.append(
            f"{rank}. {_candidate_name(candidate, payload)} ({candidate.candidate_id})"
        )
    return lines


def _resolve_alternative_choice(
    state: CandidateSelectionState,
    response: str,
    ranked_lookup: Mapping[str, Any],
) -> str | None:
    if response in {"2", "3"}:
        rank = int(response)
        if rank <= len(state.ranked_candidate_ids):
            candidate_id = state.ranked_candidate_ids[rank - 1]
            if candidate_id != state.selected_candidate_id:
                return candidate_id

    for candidate_id in state.ranked_candidate_ids:
        if response == candidate_id.lower() and candidate_id != state.selected_candidate_id:
            return candidate_id
        candidate = ranked_lookup[candidate_id]
        if response == getattr(candidate, "candidate_name", "").lower() and candidate_id != state.selected_candidate_id:
            return candidate_id
    return None


def _candidate_name(candidate: Any, payload: Mapping[str, Any]) -> str:
    return str(payload.get("name") or getattr(candidate, "candidate_name", getattr(candidate, "candidate_id", "candidate")))


def _candidate_goal(payload: Mapping[str, Any]) -> str:
    return str(
        payload.get("goal")
        or payload.get("summary")
        or payload.get("description")
        or "goal unavailable"
    )


def _alternative_reason(selected_candidate: Any, alternative_candidate: Any) -> str:
    selected_factors = selected_candidate.factor_map()
    alternative_factors = alternative_candidate.factor_map()
    score_delta = round(selected_candidate.composite_score - alternative_candidate.composite_score, 2)

    weaker_factors = []
    for factor_name in (
        "outcome_alignment",
        "journey_criticality",
        "role_value",
        "risk_reduction",
        "evidence_clarity",
    ):
        if alternative_factors[factor_name].score < selected_factors[factor_name].score:
            weaker_factors.append(factor_name.replace("_", " "))

    if weaker_factors:
        return f"score delta {score_delta:.2f}; weaker {', '.join(weaker_factors)}"
    return f"score delta {score_delta:.2f}; selected candidate wins on deterministic tie-breaks"