"""Classify Salmon corrections and route them to the intended NextLens target."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


IMPACT_LEVELS = (
    "local_feature_note",
    "feature_scope_change",
    "journey_assumption_change",
    "outcome_reframe",
    "role_or_stakeholder_change",
    "operating_loop_change",
    "capability_or_landscape_update",
    "bmad_correct_course_required",
)


@dataclass(frozen=True)
class SalmonRoutingDecision:
    impact_level: str
    target_ref: str
    action: str
    state_change: bool
    notification_targets: tuple[str, ...] = field(default_factory=tuple)
    requires_bmad_correct_course: bool = False
    creates_tracking_record: bool = False
    creates_missing_entities: bool = False
    routing_result: dict[str, Any] = field(default_factory=dict)


def classify_salmon_impact(event: Mapping[str, Any]) -> str:
    discovery = _mapping(event.get("discovery"))
    impact_level = str(discovery.get("impactLevel") or "").strip()
    if impact_level not in IMPACT_LEVELS:
        raise ValueError(f"Unsupported Salmon impact level '{impact_level}'.")
    return impact_level


def route_salmon_event(
    event: Mapping[str, Any],
    docs_path: str | Path,
    *,
    status: str = "created",
    now_factory: Any = None,
) -> SalmonRoutingDecision:
    impact_level = classify_salmon_impact(event)
    impacted_nodes = _mapping(event.get("impactedNodes"))
    feature_id = _first(impacted_nodes, "features") or _mapping(event.get("discovery")).get("impactedFeature") or "feature"
    docs_root = Path(docs_path)
    routed_at = _utc_timestamp(now_factory)
    target_ref, action, state_change = _target_for_impact(impact_level, docs_root, impacted_nodes, str(feature_id))
    notifications = _notification_targets(impact_level, impacted_nodes)
    routing_result = {
        "status": status,
        "targetRef": target_ref,
        "timestamp": routed_at,
    }
    return SalmonRoutingDecision(
        impact_level=impact_level,
        target_ref=target_ref,
        action=action,
        state_change=state_change,
        notification_targets=tuple(notifications),
        requires_bmad_correct_course=impact_level == "bmad_correct_course_required",
        creates_tracking_record=impact_level == "bmad_correct_course_required",
        creates_missing_entities=impact_level == "capability_or_landscape_update",
        routing_result=routing_result,
    )


def apply_routing_result(event: Mapping[str, Any], decision: SalmonRoutingDecision) -> dict[str, Any]:
    routed_event = dict(event)
    routed_event["routingResult"] = dict(decision.routing_result)
    return routed_event


def _target_for_impact(
    impact_level: str,
    docs_root: Path,
    impacted_nodes: Mapping[str, Any],
    feature_id: str,
) -> tuple[str, str, bool]:
    if impact_level == "local_feature_note":
        return (str(docs_root / ".nextlens" / "salmon" / "feature-notes" / f"{feature_id}.md"), "append_feature_note", False)
    if impact_level == "feature_scope_change":
        return (str(docs_root / "landscape" / "feature" / f"{feature_id}.yaml"), "update_feature_scope", True)
    if impact_level == "journey_assumption_change":
        return (str(docs_root / "landscape" / "journey" / f"{_first(impacted_nodes, 'journeys') or 'journey'}.yaml"), "update_journey_assumption", True)
    if impact_level == "outcome_reframe":
        return (str(docs_root / "landscape" / "outcome" / f"{_first(impacted_nodes, 'outcomes') or 'outcome'}.yaml"), "update_outcome_frame", True)
    if impact_level == "role_or_stakeholder_change":
        return (str(docs_root / "landscape" / "role" / f"{_first(impacted_nodes, 'roles') or 'role'}.yaml"), "update_role_or_stakeholder", True)
    if impact_level == "operating_loop_change":
        return (str(docs_root / "landscape" / "operating_loop" / f"{_first(impacted_nodes, 'operatingLoops') or 'operating-loop'}.yaml"), "update_operating_loop", True)
    if impact_level == "capability_or_landscape_update":
        return (str(docs_root / "landscape" / "capability" / f"{_first(impacted_nodes, 'capabilities') or feature_id}.yaml"), "upsert_capability_or_landscape", True)
    if impact_level == "bmad_correct_course_required":
        return (str(docs_root / ".nextlens" / "salmon" / "correct-course" / f"{feature_id}.json"), "create_bmad_correct_course_record", True)
    raise ValueError(f"Unsupported Salmon impact level '{impact_level}'.")


def _notification_targets(impact_level: str, impacted_nodes: Mapping[str, Any]) -> list[str]:
    if impact_level == "journey_assumption_change":
        return _prefix("bmad", _values(impacted_nodes, "bmadArtifacts"))
    if impact_level == "outcome_reframe":
        return _prefix("feature", _values(impacted_nodes, "features")) + _prefix("journey", _values(impacted_nodes, "journeys"))
    if impact_level == "role_or_stakeholder_change":
        return (
            _prefix("feature", _values(impacted_nodes, "features"))
            + _prefix("journey", _values(impacted_nodes, "journeys"))
            + _prefix("outcome", _values(impacted_nodes, "outcomes"))
        )
    if impact_level == "operating_loop_change":
        return _prefix("journey", _values(impacted_nodes, "journeys"))
    if impact_level == "bmad_correct_course_required":
        return _prefix("bmad", _values(impacted_nodes, "bmadArtifacts"))
    return []


def _prefix(prefix: str, values: list[str]) -> list[str]:
    return [f"{prefix}:{value}" for value in values]


def _first(payload: Mapping[str, Any], key: str) -> str | None:
    values = _values(payload, key)
    return values[0] if values else None


def _values(payload: Mapping[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _utc_timestamp(now_factory: Any) -> str:
    now = now_factory() if now_factory else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")