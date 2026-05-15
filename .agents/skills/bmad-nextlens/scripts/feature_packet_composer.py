"""Compose canonical NextLens Feature packets from selected ranking context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, Sequence
import uuid


SOURCE_CONTEXT_REFS = (
    "product-brief.md",
    "prd.md",
    "ux-design.md",
    "architecture.md",
    "research.md",
    "brainstorm.md",
)
DEFAULT_SCOPE_CONTAINMENT_WARNING = (
    "BMAD must stay within selectedFeature.includedScope and must not expand into "
    "adjacent journeys, future Features, full platform architecture, or unrelated outcomes."
)
DEFAULT_EXPLICIT_OUT_OF_SCOPE = (
    "adjacent journeys",
    "future Features",
    "platform architecture",
    "unrelated outcomes",
)


@dataclass(frozen=True)
class FeaturePacketCompositionResult:
    status: str
    packet: dict[str, Any]
    validation: Any


def compose_feature_packet(
    selected_candidate: Any,
    ranked_candidates: Sequence[Any],
    context: Mapping[str, Any],
    *,
    docs_path: str | Path,
    authoritative_state_ref: str | Path | None = None,
    derived_graph_ref: str | Path | None = None,
    doctor_summary: Mapping[str, Any] | None = None,
    salmon_routing_summary: Mapping[str, Any] | None = None,
    packet_id_factory: Callable[[], str] | None = None,
    now_factory: Callable[[], datetime] | None = None,
    source_context_refs: Sequence[str] | None = None,
) -> FeaturePacketCompositionResult:
    schema_module = _load_schema_module()
    docs_root = Path(docs_path)
    selected_candidate_id = _candidate_id(selected_candidate)
    candidate_definition = _candidate_definition(context, selected_candidate_id)
    created_at = _utc_timestamp(now_factory)
    packet_id = (packet_id_factory or _uuid4)()

    packet = {
        "schemaVersion": schema_module.FEATURE_PACKET_SCHEMA_VERSION,
        "packetId": packet_id,
        "featureId": selected_candidate_id,
        "sourceMode": schema_module.FEATURE_PACKET_SOURCE_MODE,
        "selectedFeature": _selected_feature_payload(selected_candidate, candidate_definition),
        "trace": _trace_payload(candidate_definition, context),
        "selectionRationale": _selection_rationale_payload(
            selected_candidate,
            ranked_candidates,
            candidate_definition,
        ),
        "sourceContextRefs": list(source_context_refs or SOURCE_CONTEXT_REFS),
        "authoritativeStateRef": str(authoritative_state_ref or docs_root / "landscape"),
        "derivedGraphRef": str(derived_graph_ref or docs_root / "derived" / "graph.json"),
        "doctorSummary": _doctor_summary_payload(doctor_summary),
        "salmonRoutingSummary": dict(salmon_routing_summary or {"status": "not_required"}),
        "bmadConsumerHints": _bmad_consumer_hints(context, candidate_definition),
        "evidenceBundleRef": str(docs_root / ".nextlens" / "evidence" / f"{selected_candidate_id}.json"),
        "createdAt": created_at,
    }
    validation = schema_module.validate_feature_packet_schema(
        packet,
        selected_candidate_id=selected_candidate_id,
    )
    return FeaturePacketCompositionResult(
        status="pass" if validation.is_valid else "fail",
        packet=packet,
        validation=validation,
    )


def _selected_feature_payload(selected_candidate: Any, candidate: Mapping[str, Any]) -> dict[str, Any]:
    candidate_id = _candidate_id(selected_candidate)
    scope = _mapping_value(candidate, "scope")
    included_scope = _first_list(
        candidate,
        scope,
        keys=("includedScope", "included_scope", "scopeItems", "items"),
    )
    if not included_scope:
        summary = str(scope.get("summary") or candidate.get("summary") or candidate.get("description") or "").strip()
        included_scope = [summary] if summary else [candidate_id]

    explicit_out_of_scope = _first_list(
        candidate,
        scope,
        keys=("explicitOutOfScope", "outOfScope", "out_of_scope"),
    )
    explicit_out_of_scope = _append_missing(explicit_out_of_scope, DEFAULT_EXPLICIT_OUT_OF_SCOPE)

    return {
        "id": candidate_id,
        "name": str(candidate.get("name") or getattr(selected_candidate, "candidate_name", candidate_id)),
        "goal": str(candidate.get("goal") or candidate.get("summary") or candidate.get("description") or "Selected Feature"),
        "includedScope": included_scope,
        "explicitOutOfScope": explicit_out_of_scope,
    }


def _trace_payload(candidate: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
    system = _mapping_value(context, "system")
    discovery_epoch = _mapping_value(context, "discoveryEpoch")
    return {
        "systemId": _first_id(system, context, keys=("systemId", "id", "semanticId")),
        "discoveryEpochId": _first_id(discovery_epoch, context, keys=("discoveryEpochId", "id", "epochId")),
        "roleIds": _ids_for(candidate, context, "role", context_key="roles"),
        "outcomeIds": _ids_for(candidate, context, "outcome", context_key="outcomes"),
        "journeyIds": _ids_for(candidate, context, "journey", context_key="journeys"),
        "operatingLoopIds": _ids_for(candidate, context, "operatingLoop", context_key="operatingLoops"),
        "relationshipRefs": _relationship_refs(candidate, context),
    }


def _selection_rationale_payload(
    selected_candidate: Any,
    ranked_candidates: Sequence[Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    factor_map = selected_candidate.factor_map() if hasattr(selected_candidate, "factor_map") else {}
    rejected = []
    for ranked in ranked_candidates:
        if _candidate_id(ranked) == _candidate_id(selected_candidate):
            continue
        rejected.append(
            {
                "id": _candidate_id(ranked),
                "name": str(getattr(ranked, "candidate_name", _candidate_id(ranked))),
                "score": float(getattr(ranked, "composite_score", 0.0)),
            }
        )
        if len(rejected) == 2:
            break

    return {
        "score": float(getattr(selected_candidate, "composite_score", candidate.get("score", 0.0))),
        "tieBreakEvidence": {
            name: {"score": factor.score, "detail": factor.detail}
            for name, factor in factor_map.items()
        },
        "whyThisFeature": str(
            candidate.get("selectionRationale")
            or candidate.get("rationale")
            or "Selected as the highest-ranked Feature candidate."
        ),
        "whyNow": str(
            candidate.get("whyNow")
            or candidate.get("timingRationale")
            or "Candidate is ready for downstream BMAD planning."
        ),
        "rejectedAlternates": rejected,
    }


def _doctor_summary_payload(summary: Mapping[str, Any] | None) -> dict[str, Any]:
    if summary is None:
        return {
            "status": "not_run",
            "blocking_count": 0,
            "advisory_count": 0,
            "informational_count": 0,
        }
    return {
        "status": str(summary.get("status") or summary.get("overall_status") or "unknown"),
        "blocking_count": int(summary.get("blocking_count") or summary.get("blocked") or 0),
        "advisory_count": int(summary.get("advisory_count") or summary.get("advisory") or 0),
        "informational_count": int(summary.get("informational_count") or summary.get("informational") or 0),
    }


def _bmad_consumer_hints(context: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, str]:
    hints = _mapping_value(candidate, "bmadConsumerHints") or _mapping_value(context, "bmadConsumerHints")
    return {
        "scopeContainmentWarning": str(hints.get("scopeContainmentWarning") or DEFAULT_SCOPE_CONTAINMENT_WARNING),
        "prdInput": _hint_value(hints, context, "prdInput", "prd", "PRD goal and key requirements unavailable."),
        "uxInput": _hint_value(hints, context, "uxInput", "ux", "UX patterns and key flows unavailable."),
        "architectureInput": _hint_value(
            hints,
            context,
            "architectureInput",
            "architecture",
            "Architecture decisions affecting this Feature unavailable.",
        ),
        "epicStoryInput": _hint_value(
            hints,
            context,
            "epicStoryInput",
            "epics",
            "Estimated epic/story breakdown unavailable.",
        ),
        "readinessInput": _hint_value(
            hints,
            context,
            "readinessInput",
            "readiness",
            "Implementation readiness status unavailable.",
        ),
    }


def _hint_value(
    hints: Mapping[str, Any],
    context: Mapping[str, Any],
    hint_key: str,
    context_key: str,
    fallback: str,
) -> str:
    value = hints.get(hint_key)
    if value:
        return str(value)
    context_value = context.get(context_key)
    if isinstance(context_value, Mapping):
        for key in ("summary", "goal", "description", "status"):
            if context_value.get(key):
                return str(context_value[key])
    if context_value:
        return str(context_value)
    return fallback


def _candidate_definition(context: Mapping[str, Any], candidate_id: str) -> Mapping[str, Any]:
    for candidate in _mapping_items(context.get("candidateFeatures")):
        if _mapping_id(candidate) == candidate_id:
            return candidate
    return {}


def _candidate_id(candidate: Any) -> str:
    if isinstance(candidate, Mapping):
        return _mapping_id(candidate)
    return str(getattr(candidate, "candidate_id", getattr(candidate, "id", ""))).strip()


def _mapping_id(value: Mapping[str, Any]) -> str:
    return str(
        value.get("id")
        or value.get("candidateId")
        or value.get("featureId")
        or value.get("semanticId")
        or ""
    ).strip()


def _mapping_value(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if isinstance(value, Mapping):
        return value
    return {}


def _first_id(*payloads: Mapping[str, Any], keys: Sequence[str]) -> str:
    for payload in payloads:
        for key in keys:
            value = payload.get(key)
            if value:
                return str(value)
    return "unknown"


def _ids_for(candidate: Mapping[str, Any], context: Mapping[str, Any], singular: str, *, context_key: str) -> list[str]:
    candidate_ids = _first_list(
        candidate,
        keys=(
            f"{singular}Ids",
            f"{singular}_ids",
            f"{singular}Refs",
            f"{singular}_refs",
            context_key,
        ),
    )
    if candidate_ids:
        return _normalize_ids(candidate_ids)
    return _normalize_ids(_mapping_items(context.get(context_key)))


def _relationship_refs(candidate: Mapping[str, Any], context: Mapping[str, Any]) -> list[str]:
    refs = _first_list(candidate, context, keys=("relationshipRefs", "relationships"))
    return [str(item) for item in refs]


def _first_list(*payloads: Mapping[str, Any], keys: Sequence[str]) -> list[Any]:
    for payload in payloads:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return list(value)
            if isinstance(value, tuple):
                return list(value)
    return []


def _normalize_ids(values: Sequence[Any]) -> list[str]:
    ids: list[str] = []
    for value in values:
        if isinstance(value, Mapping):
            item = _mapping_id(value)
        else:
            item = str(value).strip()
        if item:
            ids.append(item)
    return list(dict.fromkeys(ids))


def _mapping_items(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [item for item in value if isinstance(item, Mapping)]
    return []


def _append_missing(values: Sequence[Any], required_values: Sequence[str]) -> list[str]:
    normalized = [str(value) for value in values if str(value).strip()]
    lower_values = {value.lower() for value in normalized}
    for required in required_values:
        if required.lower() not in lower_values:
            normalized.append(required)
    return normalized


def _uuid4() -> str:
    return str(uuid.uuid4())


def _utc_timestamp(now_factory: Callable[[], datetime] | None) -> str:
    now = now_factory() if now_factory else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_schema_module():
    module_path = Path(__file__).resolve().parent / "feature_packet_schema.py"
    spec = importlib.util.spec_from_file_location("nextlens_feature_packet_schema_runtime", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("Unable to load feature_packet_schema module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module