"""Deterministic candidate feature scoring for NextLens."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


FACTOR_ORDER = (
    "outcome_alignment",
    "journey_criticality",
    "role_value",
    "risk_reduction",
    "dependency_readiness",
    "implementation_boundedness",
    "bmad_readiness",
    "evidence_clarity",
    "open_question_severity",
)

CRITICALITY_WEIGHTS = {
    "critical": 5.0,
    "high": 4.0,
    "medium": 2.5,
    "low": 1.0,
}
ROLE_IMPORTANCE_WEIGHTS = {
    "critical": 5.0,
    "high": 4.0,
    "medium": 2.5,
    "low": 1.0,
}
SEVERITY_WEIGHTS = {
    "blocking": 35.0,
    "critical": 30.0,
    "high": 25.0,
    "major": 20.0,
    "medium": 15.0,
    "advisory": 10.0,
    "low": 8.0,
    "informational": 5.0,
}
BMAD_ARTIFACT_KEYS = ("prd", "ux", "architecture")


@dataclass(frozen=True)
class FactorScore:
    name: str
    score: float
    detail: str


@dataclass(frozen=True)
class ScoredCandidate:
    candidate_id: str
    candidate_name: str
    factor_scores: tuple[FactorScore, ...]
    composite_score: float
    unresolved_blockers: int
    stable_candidate_timestamp: str | None

    def factor_map(self) -> dict[str, FactorScore]:
        return {factor.name: factor for factor in self.factor_scores}


def score_candidate_feature(
    candidate: Mapping[str, Any],
    context: Mapping[str, Any],
) -> ScoredCandidate:
    candidate_id = _candidate_id(candidate)
    candidate_name = str(candidate.get("name") or candidate_id)

    factor_scores = (
        _score_outcome_alignment(candidate, context),
        _score_journey_criticality(candidate, context),
        _score_role_value(candidate, context),
        _score_risk_reduction(candidate, context),
        _score_dependency_readiness(candidate),
        _score_implementation_boundedness(candidate),
        _score_bmad_readiness(candidate),
        _score_evidence_clarity(candidate),
        _score_open_question_severity(candidate, context),
    )
    composite_score = _round_score(
        sum(factor.score for factor in factor_scores) / len(factor_scores)
    )

    return ScoredCandidate(
        candidate_id=candidate_id,
        candidate_name=candidate_name,
        factor_scores=factor_scores,
        composite_score=composite_score,
        unresolved_blockers=_unresolved_blocker_count(candidate, context),
        stable_candidate_timestamp=_stable_candidate_timestamp(candidate),
    )


def rank_candidate_features(context: Mapping[str, Any]) -> tuple[ScoredCandidate, ...]:
    candidates = [
        score_candidate_feature(candidate, context)
        for candidate in _iter_mapping_list(context.get("candidateFeatures"))
    ]
    return tuple(sorted(candidates, key=_ranking_key))


def _score_outcome_alignment(
    candidate: Mapping[str, Any],
    context: Mapping[str, Any],
) -> FactorScore:
    covered_ids = _candidate_reference_ids(candidate, "outcome")
    outcomes = _iter_mapping_list(context.get("outcomes"))
    covered_weight = _weighted_matches(
        outcomes,
        covered_ids,
        weight_keys=("criticalityWeight", "criticality", "weight", "priority"),
        weight_lookup=CRITICALITY_WEIGHTS,
    )
    total_weight = _weighted_total(
        outcomes,
        weight_keys=("criticalityWeight", "criticality", "weight", "priority"),
        weight_lookup=CRITICALITY_WEIGHTS,
    )
    score = _percentage(covered_weight, total_weight)
    return FactorScore(
        name="outcome_alignment",
        score=score,
        detail=f"{len(covered_ids)} covered outcomes across {len(outcomes)} total outcomes",
    )


def _score_journey_criticality(
    candidate: Mapping[str, Any],
    context: Mapping[str, Any],
) -> FactorScore:
    covered_ids = _candidate_reference_ids(candidate, "journey")
    journeys = _iter_mapping_list(context.get("journeys"))
    covered_weight = _weighted_matches(
        journeys,
        covered_ids,
        weight_keys=("roleDependencyWeight", "roleDependency", "dependencyWeight"),
    )
    total_weight = _weighted_total(
        journeys,
        weight_keys=("roleDependencyWeight", "roleDependency", "dependencyWeight"),
        fallback_from_lists=("roleIds", "role_refs", "dependentRoles"),
    )
    score = _percentage(covered_weight, total_weight)
    return FactorScore(
        name="journey_criticality",
        score=score,
        detail=f"{len(covered_ids)} covered journeys across {len(journeys)} total journeys",
    )


def _score_role_value(
    candidate: Mapping[str, Any],
    context: Mapping[str, Any],
) -> FactorScore:
    covered_ids = _candidate_reference_ids(candidate, "role")
    roles = _iter_mapping_list(context.get("roles"))
    covered_weight = _weighted_matches(
        roles,
        covered_ids,
        weight_keys=("stakeholderImportance", "importanceWeight", "importance", "priority"),
        weight_lookup=ROLE_IMPORTANCE_WEIGHTS,
    )
    total_weight = _weighted_total(
        roles,
        weight_keys=("stakeholderImportance", "importanceWeight", "importance", "priority"),
        weight_lookup=ROLE_IMPORTANCE_WEIGHTS,
    )
    score = _percentage(covered_weight, total_weight)
    return FactorScore(
        name="role_value",
        score=score,
        detail=f"{len(covered_ids)} impacted roles across {len(roles)} total roles",
    )


def _score_risk_reduction(
    candidate: Mapping[str, Any],
    context: Mapping[str, Any],
) -> FactorScore:
    mitigated_ids = _candidate_reference_ids(candidate, "risk")
    risks = _iter_mapping_list(context.get("risks"))
    if not risks:
        return FactorScore(
            name="risk_reduction",
            score=100.0,
            detail="no risks present; defaulting to 100",
        )

    mitigated_weight = _weighted_matches(
        risks,
        mitigated_ids,
        weight_keys=("severityWeight", "severity", "priority"),
        weight_lookup=SEVERITY_WEIGHTS,
    )
    total_weight = _weighted_total(
        risks,
        weight_keys=("severityWeight", "severity", "priority"),
        weight_lookup=SEVERITY_WEIGHTS,
    )
    score = _percentage(mitigated_weight, total_weight)
    return FactorScore(
        name="risk_reduction",
        score=score,
        detail=f"{len(mitigated_ids)} mitigated risks across {len(risks)} total risks",
    )


def _score_dependency_readiness(candidate: Mapping[str, Any]) -> FactorScore:
    dependencies = _iter_mapping_list(candidate.get("dependencies"))
    if not dependencies:
        return FactorScore(
            name="dependency_readiness",
            score=100.0,
            detail="no upstream dependencies",
        )

    satisfied = sum(1 for dependency in dependencies if _dependency_is_satisfied(dependency))
    score = _percentage(float(satisfied), float(len(dependencies)))
    return FactorScore(
        name="dependency_readiness",
        score=score,
        detail=f"{satisfied} satisfied dependencies across {len(dependencies)} total dependencies",
    )


def _score_implementation_boundedness(candidate: Mapping[str, Any]) -> FactorScore:
    scope = candidate.get("scope") if isinstance(candidate.get("scope"), Mapping) else {}
    summary = str(
        scope.get("summary")
        or candidate.get("summary")
        or candidate.get("description")
        or ""
    ).strip()
    out_of_scope = _iter_any_list(scope.get("outOfScope") or candidate.get("outOfScope"))
    penalties = 0.0
    detail_parts: list[str] = []

    if summary:
        detail_parts.append("scope summary present")
    else:
        penalties += 35.0
        detail_parts.append("scope summary missing")

    if out_of_scope:
        detail_parts.append("explicit out-of-scope list present")
    else:
        penalties += 20.0
        detail_parts.append("out-of-scope list missing")

    if _truthy(scope.get("spillageDetected") or candidate.get("spillageDetected") or candidate.get("scopeSpillage")):
        penalties += 35.0
        detail_parts.append("scope spillage detected")

    adjacent_refs = _iter_any_list(candidate.get("adjacentJourneyRefs"))
    future_refs = _iter_any_list(candidate.get("futureFeatureRefs"))
    if adjacent_refs:
        penalties += 5.0 * len(adjacent_refs)
        detail_parts.append(f"{len(adjacent_refs)} adjacent journey references")
    if future_refs:
        penalties += 7.5 * len(future_refs)
        detail_parts.append(f"{len(future_refs)} future feature references")

    score = _round_score(_clamp_score(100.0 - penalties))
    return FactorScore(
        name="implementation_boundedness",
        score=score,
        detail="; ".join(detail_parts),
    )


def _score_bmad_readiness(candidate: Mapping[str, Any]) -> FactorScore:
    artifacts = _collect_bmad_artifacts(candidate)
    ready_count = sum(1 for artifact in BMAD_ARTIFACT_KEYS if artifacts.get(artifact, False))
    score = _percentage(float(ready_count), float(len(BMAD_ARTIFACT_KEYS)))
    return FactorScore(
        name="bmad_readiness",
        score=score,
        detail=f"{ready_count} of {len(BMAD_ARTIFACT_KEYS)} BMAD inputs available",
    )


def _score_evidence_clarity(candidate: Mapping[str, Any]) -> FactorScore:
    trace = candidate.get("trace") if isinstance(candidate.get("trace"), Mapping) else {}
    completeness = 0
    if _has_value(trace.get("systemId") or candidate.get("systemId")):
        completeness += 1
    if _iter_any_list(trace.get("roleIds") or candidate.get("roleIds")):
        completeness += 1
    if _iter_any_list(trace.get("outcomeIds") or candidate.get("outcomeIds")):
        completeness += 1
    if _iter_any_list(trace.get("journeyIds") or candidate.get("journeyIds")):
        completeness += 1
    if _has_value(trace.get("featureId") or candidate.get("featureId") or candidate.get("semanticId") or candidate.get("id")):
        completeness += 1

    score = _percentage(float(completeness), 5.0)
    return FactorScore(
        name="evidence_clarity",
        score=score,
        detail=f"{completeness} of 5 traceability links present",
    )


def _score_open_question_severity(
    candidate: Mapping[str, Any],
    context: Mapping[str, Any],
) -> FactorScore:
    questions = _candidate_open_questions(candidate, context)
    penalty = 0.0
    for question in questions:
        penalty += _resolve_weight(
            question,
            weight_keys=("severityWeight", "severity", "priority"),
            weight_lookup=SEVERITY_WEIGHTS,
            default=10.0,
        )
    score = _round_score(_clamp_score(100.0 - penalty))
    return FactorScore(
        name="open_question_severity",
        score=score,
        detail=f"{len(questions)} unresolved questions",
    )


def _weighted_matches(
    items: Sequence[Mapping[str, Any]],
    matched_ids: set[str],
    *,
    weight_keys: Sequence[str],
    weight_lookup: Mapping[str, float] | None = None,
) -> float:
    total = 0.0
    for item in items:
        if _entity_id(item) in matched_ids:
            total += _resolve_weight(item, weight_keys=weight_keys, weight_lookup=weight_lookup)
    return total


def _weighted_total(
    items: Sequence[Mapping[str, Any]],
    *,
    weight_keys: Sequence[str],
    weight_lookup: Mapping[str, float] | None = None,
    fallback_from_lists: Sequence[str] = (),
) -> float:
    total = 0.0
    for item in items:
        total += _resolve_weight(
            item,
            weight_keys=weight_keys,
            weight_lookup=weight_lookup,
            fallback_from_lists=fallback_from_lists,
        )
    return total


def _resolve_weight(
    item: Mapping[str, Any],
    *,
    weight_keys: Sequence[str],
    weight_lookup: Mapping[str, float] | None = None,
    fallback_from_lists: Sequence[str] = (),
    default: float = 1.0,
) -> float:
    for key in weight_keys:
        value = item.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered and weight_lookup and lowered in weight_lookup:
                return weight_lookup[lowered]

    for key in fallback_from_lists:
        value = item.get(key)
        if isinstance(value, list) and value:
            return float(len(value))

    return default


def _candidate_reference_ids(candidate: Mapping[str, Any], entity: str) -> set[str]:
    singular = entity
    plural = f"{entity}s"
    candidates = [
        candidate.get(f"{singular}Id"),
        candidate.get(f"{singular}Ids"),
        candidate.get(plural),
        candidate.get(f"{entity}Refs"),
        candidate.get("trace", {}).get(f"{singular}Id") if isinstance(candidate.get("trace"), Mapping) else None,
        candidate.get("trace", {}).get(f"{singular}Ids") if isinstance(candidate.get("trace"), Mapping) else None,
    ]
    identifiers: set[str] = set()
    for value in candidates:
        identifiers.update(_coerce_ids(value))
    return identifiers


def _candidate_open_questions(
    candidate: Mapping[str, Any],
    context: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    raw_questions = candidate.get("openQuestions")
    if isinstance(raw_questions, list) and raw_questions:
        if all(isinstance(item, Mapping) for item in raw_questions):
            return list(raw_questions)

    question_ids = _coerce_ids(candidate.get("openQuestionIds"))
    if not question_ids:
        question_ids = _coerce_ids(candidate.get("openQuestions"))
    context_questions = {
        _entity_id(question): question
        for question in _iter_mapping_list(context.get("openQuestions"))
    }
    return [context_questions[question_id] for question_id in question_ids if question_id in context_questions]


def _dependency_is_satisfied(dependency: Mapping[str, Any]) -> bool:
    status = str(dependency.get("status") or "").strip().lower()
    if status in {"ready", "done", "complete", "satisfied"}:
        return True
    if status in {"blocked", "pending", "missing", "failed"}:
        return False
    return _truthy(dependency.get("satisfied") or dependency.get("ready") or dependency.get("complete"))


def _collect_bmad_artifacts(candidate: Mapping[str, Any]) -> dict[str, bool]:
    artifacts = {key: False for key in BMAD_ARTIFACT_KEYS}
    raw_artifacts = candidate.get("bmadArtifacts")
    if isinstance(raw_artifacts, Mapping):
        for key in BMAD_ARTIFACT_KEYS:
            artifacts[key] = _truthy(raw_artifacts.get(key))
        return artifacts

    if isinstance(raw_artifacts, list):
        present = {str(item).strip().lower() for item in raw_artifacts}
        for key in BMAD_ARTIFACT_KEYS:
            artifacts[key] = key in present
        return artifacts

    raw_inputs = candidate.get("bmadInputs")
    if isinstance(raw_inputs, Mapping):
        for key in BMAD_ARTIFACT_KEYS:
            artifacts[key] = _truthy(raw_inputs.get(key))
    return artifacts


def _unresolved_blocker_count(
    candidate: Mapping[str, Any],
    context: Mapping[str, Any],
) -> int:
    unsatisfied_dependencies = sum(
        1 for dependency in _iter_mapping_list(candidate.get("dependencies")) if not _dependency_is_satisfied(dependency)
    )
    blocking_questions = 0
    for question in _candidate_open_questions(candidate, context):
        severity = str(question.get("severity") or question.get("priority") or "").strip().lower()
        if severity in {"blocking", "critical", "high"}:
            blocking_questions += 1
    return unsatisfied_dependencies + blocking_questions


def _stable_candidate_timestamp(candidate: Mapping[str, Any]) -> str | None:
    metadata = candidate.get("metadata") if isinstance(candidate.get("metadata"), Mapping) else {}
    for value in (
        candidate.get("stableCandidateTimestamp"),
        candidate.get("createdAt"),
        metadata.get("createdAt"),
        candidate.get("timestamp"),
    ):
        if _has_value(value):
            return str(value)
    return None


def _ranking_key(candidate: ScoredCandidate) -> tuple[Any, ...]:
    factors = candidate.factor_map()
    return (
        -candidate.composite_score,
        -factors["outcome_alignment"].score,
        -factors["journey_criticality"].score,
        candidate.unresolved_blockers,
        -factors["evidence_clarity"].score,
        _timestamp_sort_key(candidate.stable_candidate_timestamp),
        candidate.candidate_id,
    )


def _timestamp_sort_key(value: str | None) -> tuple[int, datetime, str]:
    if value is None:
        return (1, datetime.max.replace(tzinfo=timezone.utc), "")
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (0, parsed.astimezone(timezone.utc), value)
    except ValueError:
        return (1, datetime.max.replace(tzinfo=timezone.utc), value)


def _candidate_id(candidate: Mapping[str, Any]) -> str:
    for key in ("semanticId", "id", "featureId"):
        value = candidate.get(key)
        if _has_value(value):
            return str(value)
    return str(candidate.get("name") or "candidate")


def _entity_id(entity: Mapping[str, Any]) -> str:
    for key in ("semanticId", "id", "featureId"):
        value = entity.get(key)
        if _has_value(value):
            return str(value)
    return ""


def _coerce_ids(value: Any) -> set[str]:
    identifiers: set[str] = set()
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            identifiers.add(stripped)
    elif isinstance(value, Mapping):
        entity_id = _entity_id(value)
        if entity_id:
            identifiers.add(entity_id)
    elif isinstance(value, list):
        for item in value:
            identifiers.update(_coerce_ids(item))
    return identifiers


def _iter_mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, Mapping)]
    return []


def _iter_any_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _percentage(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return _round_score(_clamp_score((numerator / denominator) * 100.0))


def _round_score(value: float) -> float:
    return round(value, 4)


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "present", "ready", "complete"}
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, Mapping):
        return bool(value)
    return True