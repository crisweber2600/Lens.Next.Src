"""Generate Salmon signals from validation and curate landscape update proposals."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping, Sequence
import uuid

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover
    yaml = None
    _YAML_IMPORT_ERROR = exc
else:
    _YAML_IMPORT_ERROR = None


def _load_runtime_module(module_name: str, file_name: str):
    module_path = Path(__file__).resolve().parent / file_name
    spec = importlib.util.spec_from_file_location(f"nextlens_{module_name}_runtime", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load {module_name} module from '{module_path}'.")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


SALMON_EVENT_MODEL = _load_runtime_module("salmon_event_model", "salmon_event_model.py")
SALMON_DEDUPLICATION = _load_runtime_module("salmon_deduplication", "salmon_deduplication.py")
SALMON_ROUTING = _load_runtime_module("salmon_routing", "salmon_routing.py")
LANDSCAPE_STORE = _load_runtime_module("landscape_store", "landscape_store.py")
DERIVED_GRAPH = _load_runtime_module("derived_graph", "derived_graph.py")


LANDSCAPE_UPDATE_SCHEMA_VERSION = "nextlens.landscape-update.v1"
LANDSCAPE_UPDATE_STATUSES = frozenset({"proposed", "applied", "rejected"})
LANDSCAPE_UPDATE_CHANGE_TYPES = frozenset({"create", "update", "delete", "status", "current_truth"})
LANDSCAPE_ALLOWED_DIRECTORIES = tuple(LANDSCAPE_STORE.LANDSCAPE_ENTITY_DIRECTORIES) + ("feature",)


@dataclass(frozen=True)
class SalmonSignalBatchResult:
    status: str
    events: tuple[dict[str, Any], ...] = ()
    routing_decisions: tuple[Any, ...] = ()
    dedup_results: tuple[Any, ...] = ()
    evidence_event: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class LandscapeUpdateProposalResult:
    status: str
    path: Path | None = None
    update: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class LandscapeUpdateApplyResult:
    status: str
    update_path: Path | None = None
    update: dict[str, Any] = field(default_factory=dict)
    applied_targets: tuple[str, ...] = ()
    skipped_targets: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    derived_graph_ref: str | None = None
    derived_graph_authoritative: bool = False
    error: str | None = None


def generate_salmon_signals_from_validation(
    validation_result: Mapping[str, Any],
    docs_path: str | Path,
    *,
    now_factory: Any = None,
) -> SalmonSignalBatchResult:
    findings = [
        _enrich_validation_finding(finding, validation_result)
        for finding in _sequence(validation_result.get("findings"))
        if isinstance(finding, Mapping)
    ]
    if not _salmon_required(validation_result, findings):
        return SalmonSignalBatchResult(
            status="skipped",
            evidence_event={
                "stage": "salmon-signal-generation",
                "status": "skipped",
                "eventCount": 0,
            },
        )

    events: list[dict[str, Any]] = []
    routing_decisions: list[Any] = []
    dedup_results: list[Any] = []
    try:
        for finding in findings:
            if not _finding_requires_salmon(validation_result, finding):
                continue
            event = _build_salmon_signal(validation_result, finding, now_factory=now_factory)
            decision = SALMON_ROUTING.route_salmon_event(event, docs_path, now_factory=now_factory)
            routed_event = SALMON_ROUTING.apply_routing_result(event, decision)
            dedup_result = SALMON_DEDUPLICATION.deduplicate_salmon_event(
                docs_path,
                routed_event,
                now_factory=now_factory,
            )
            events.append(dedup_result.event)
            routing_decisions.append(decision)
            dedup_results.append(dedup_result)
    except Exception as exc:
        return SalmonSignalBatchResult(
            status="fail",
            events=tuple(events),
            routing_decisions=tuple(routing_decisions),
            dedup_results=tuple(dedup_results),
            evidence_event={
                "stage": "salmon-signal-generation",
                "status": "fail",
                "eventCount": len(events),
                "error": str(exc),
            },
            error=str(exc),
        )

    status = "pass" if events else "skipped"
    return SalmonSignalBatchResult(
        status=status,
        events=tuple(events),
        routing_decisions=tuple(routing_decisions),
        dedup_results=tuple(dedup_results),
        evidence_event={
            "stage": "salmon-signal-generation",
            "status": status,
            "eventCount": len(events),
        },
    )


def build_landscape_update_proposal(
    *,
    source_refs: Mapping[str, Any] | None,
    updates: Sequence[Mapping[str, Any]],
    update_id: str | None = None,
    status: str = "proposed",
    now_factory: Any = None,
) -> dict[str, Any]:
    if status not in LANDSCAPE_UPDATE_STATUSES:
        raise ValueError(f"Unsupported landscape update status '{status}'.")
    proposal_id = update_id or str(uuid.uuid4())
    normalized_updates = [_normalize_update(update) for update in updates]
    return {
        "schemaVersion": LANDSCAPE_UPDATE_SCHEMA_VERSION,
        "updateId": proposal_id,
        "status": status,
        "sourceRefs": _normalize_source_refs(source_refs or {}),
        "authority": {
            "livingLandscape": "authoritative",
            "derivedGraph": "non_authoritative",
            "livingLandscapeAuthoritative": True,
            "derivedGraphAuthoritative": False,
        },
        "updates": normalized_updates,
        "proposedAt": _utc_timestamp(now_factory),
    }


def persist_landscape_update(
    docs_path: str | Path,
    update: Mapping[str, Any],
    *,
    replace_fn: Any = None,
) -> LandscapeUpdateProposalResult:
    try:
        yaml_module = _require_yaml()
        output_path = _landscape_update_path(docs_path, update)
        _atomic_write_yaml(output_path, update, yaml_module, replace_fn=replace_fn)
        return LandscapeUpdateProposalResult(status="pass", path=output_path, update=dict(update))
    except Exception as exc:
        return LandscapeUpdateProposalResult(status="fail", error=str(exc), update=dict(update))


def apply_landscape_update(
    docs_path: str | Path,
    update: Mapping[str, Any],
    *,
    now_factory: Any = None,
    replace_fn: Any = None,
) -> LandscapeUpdateApplyResult:
    docs_root = Path(docs_path)
    try:
        yaml_module = _require_yaml()
        status = str(update.get("status") or "").strip().lower()
        if status != "proposed":
            raise ValueError("Landscape update must be in proposed status before applying.")
        if str(update.get("schemaVersion") or "") != LANDSCAPE_UPDATE_SCHEMA_VERSION:
            raise ValueError("Landscape update schemaVersion mismatch.")

        applied: list[str] = []
        skipped: list[str] = []
        warnings: list[str] = []
        for change in _sequence(update.get("updates")):
            target_path = _validated_update_target(docs_root, change)
            change_type = str(change.get("changeType") or "").strip().lower()
            if change_type not in LANDSCAPE_UPDATE_CHANGE_TYPES:
                raise ValueError(f"Unsupported landscape changeType '{change_type}'.")
            if change_type == "delete":
                if target_path.exists():
                    target_path.unlink()
                applied.append(target_path.as_posix())
                continue
            payload = change.get("payload")
            if not isinstance(payload, Mapping):
                raise ValueError(f"Landscape update payload missing for {target_path}.")
            _atomic_write_yaml(target_path, payload, yaml_module, replace_fn=replace_fn)
            applied.append(target_path.as_posix())

        derived_graph_ref = None
        try:
            state = LANDSCAPE_STORE.reconstruct_landscape_state(docs_root)
            graph_path = DERIVED_GRAPH.write_derived_graph(docs_root, state)
            derived_graph_ref = graph_path.as_posix()
        except Exception as exc:  # pragma: no cover - best effort rebuild
            warnings.append(f"Derived graph refresh failed: {exc}")

        applied_update = dict(update)
        applied_update["status"] = "applied"
        applied_update["appliedAt"] = _utc_timestamp(now_factory)
        output_path = _landscape_update_path(docs_root, applied_update)
        _atomic_write_yaml(output_path, applied_update, yaml_module, replace_fn=replace_fn)

        return LandscapeUpdateApplyResult(
            status="pass",
            update_path=output_path,
            update=applied_update,
            applied_targets=tuple(applied),
            skipped_targets=tuple(skipped),
            warnings=tuple(warnings),
            derived_graph_ref=derived_graph_ref,
            derived_graph_authoritative=False,
        )
    except Exception as exc:
        return LandscapeUpdateApplyResult(status="fail", error=str(exc), update=dict(update))


def _salmon_required(validation_result: Mapping[str, Any], findings: Sequence[Mapping[str, Any]]) -> bool:
    if bool(validation_result.get("salmonRequired")):
        return True
    return any(bool(finding.get("salmonRequired") or finding.get("upstreamTruthChanged")) for finding in findings)


def _finding_requires_salmon(validation_result: Mapping[str, Any], finding: Mapping[str, Any]) -> bool:
    if bool(validation_result.get("salmonRequired")):
        return True
    return bool(finding.get("salmonRequired") or finding.get("upstreamTruthChanged"))


def _build_salmon_signal(
    validation_result: Mapping[str, Any],
    finding: Mapping[str, Any],
    *,
    now_factory: Any = None,
) -> dict[str, Any]:
    impact_level = str(finding.get("impactLevel") or "").strip()
    if impact_level not in SALMON_EVENT_MODEL.SALMON_IMPACT_LEVELS:
        raise ValueError(f"Unsupported Salmon impact level '{impact_level}'.")

    validation_id = str(
        finding.get("validationId")
        or validation_result.get("validationId")
        or validation_result.get("validation_id")
        or "validation"
    )
    feature_id = str(
        finding.get("impactedFeature")
        or validation_result.get("featureId")
        or validation_result.get("feature_id")
        or "feature"
    )
    packet_id = str(validation_result.get("packetId") or validation_result.get("packet_id") or "")
    issue_description = str(
        finding.get("issueDescription")
        or finding.get("summary")
        or "Validation indicated upstream truth changed."
    )
    issue_class = str(finding.get("issueClass") or impact_level)
    canonical_path = str(finding.get("canonicalPath") or _packet_path(packet_id))
    dedup = SALMON_DEDUPLICATION.generate_salmon_fingerprint(
        issue_class=issue_class,
        target_stable_id=feature_id,
        canonical_path=canonical_path,
        issue_description=issue_description,
    )
    recommended_action = _recommended_action(finding, impact_level)
    impacted_nodes = _coerce_impacted_nodes(finding, feature_id, validation_result)
    created_at = _utc_timestamp(now_factory)
    event_id = str(
        finding.get("eventId")
        or finding.get("salmonSignalId")
        or finding.get("salmonSignalID")
        or uuid.uuid4()
    )

    return {
        "schemaVersion": SALMON_EVENT_MODEL.SALMON_EVENT_SCHEMA_VERSION,
        "id": event_id,
        "raisedFrom": f"validation:{validation_id}",
        "source": {"type": "validation", "sourceId": validation_id},
        "discovery": {
            "issueClass": issue_class,
            "canonicalPath": canonical_path,
            "issueDescription": issue_description,
            "impactedFeature": feature_id,
            "impactLevel": impact_level,
            "findingId": finding.get("findingId") or finding.get("id"),
        },
        "impactedNodes": impacted_nodes,
        "severity": _normalize_severity(finding.get("severity")),
        "recommendedAction": recommended_action,
        "dedupFingerprint": dedup.fingerprint,
        "createdAt": created_at,
        "routingResult": {
            "status": "created",
            "targetRef": "pending",
        },
    }


def _enrich_validation_finding(
    finding: Mapping[str, Any],
    validation_result: Mapping[str, Any],
) -> dict[str, Any]:
    enriched = dict(finding)
    impact_level = str(enriched.get("impactLevel") or "").strip()
    if impact_level not in SALMON_EVENT_MODEL.SALMON_IMPACT_LEVELS:
        enriched["impactLevel"] = _mapped_impact_level(enriched)
        impact_level = str(enriched["impactLevel"])
    feature_id = str(
        enriched.get("impactedFeature")
        or validation_result.get("featureId")
        or validation_result.get("feature_id")
        or "feature"
    )
    enriched["impactedNodes"] = _coerce_impacted_nodes(enriched, feature_id, validation_result)
    if impact_level == "bmad_correct_course_required" and not isinstance(enriched.get("recommendedAction"), Mapping):
        enriched["recommendedActionDetails"] = (
            "Run BMAD correct-course to revisit invalidated PRD, architecture, or story assumptions."
        )
    return enriched


def _mapped_impact_level(finding: Mapping[str, Any]) -> str:
    tokens = _finding_tokens(finding)
    if _has_any(tokens, ("note_only", "implementation_note", "local_note")) or (
        "minor" in tokens and "note" in tokens and "implementation" in tokens
    ):
        return "local_feature_note"
    if _has_any(tokens, ("prd", "architecture", "architectural", "story")) and _has_any(
        tokens, ("invalid", "invalidated", "invalidation", "assumption", "assumptions")
    ):
        return "bmad_correct_course_required"
    if _has_any(tokens, ("operating_loop", "operatingloop", "loop")) and _has_any(
        tokens, ("mismatch", "differs", "invalid", "invalidated")
    ):
        return "operating_loop_change"
    if _has_any(tokens, ("role", "stakeholder")) and _has_any(
        tokens, ("mismatch", "differs", "invalid", "invalidated", "evidence")
    ):
        return "role_or_stakeholder_change"
    if _has_any(tokens, ("outcome", "value")) and _has_any(
        tokens, ("missing", "differs", "different", "mismatch", "implemented_value", "implemented")
    ):
        return "outcome_reframe"
    if _has_any(tokens, ("journey", "path")) and _has_any(
        tokens, ("missing", "invalid", "invalidated", "evidence")
    ):
        return "journey_assumption_change"
    if _has_any(tokens, ("durable_truth", "durable", "current_landscape", "currentlandscape", "correction", "truth")):
        return "capability_or_landscape_update"
    if _has_any(tokens, ("scope_leak", "scopeleak", "explicitoutofscope", "out_of_scope", "outofscope")):
        return "feature_scope_change"
    return "feature_scope_change"


def _finding_tokens(finding: Mapping[str, Any]) -> set[str]:
    token_text_parts: list[str] = []
    for key in (
        "category",
        "type",
        "findingType",
        "issueClass",
        "reference",
        "field",
        "path",
        "canonicalPath",
        "message",
        "summary",
        "issueDescription",
        "description",
    ):
        value = finding.get(key)
        if isinstance(value, (str, int, float, bool)):
            if key in {"category", "type", "findingType", "issueClass", "reference", "field", "path"}:
                token_text_parts.append(key)
            token_text_parts.append(str(value))
    text = " ".join(token_text_parts).lower()
    normalized = text.replace("-", "_").replace(".", "_").replace("/", "_").replace(" ", "_")
    raw_parts = text.replace("-", " ").replace("_", " ").replace(".", " ").replace("/", " ").split()
    tokens = {part.strip() for part in raw_parts if part.strip()}
    tokens.update(part.strip() for part in normalized.split("_") if part.strip())
    if "operating" in tokens and "loop" in tokens:
        tokens.add("operating_loop")
    if "explicitoutofscope" in normalized:
        tokens.add("explicitoutofscope")
    if "out_of_scope" in normalized:
        tokens.add("out_of_scope")
    if "scope_leak" in normalized or "scopeleak" in normalized:
        tokens.add("scope_leak")
    if "durable_truth" in normalized:
        tokens.add("durable_truth")
    if "current_landscape" in normalized:
        tokens.add("current_landscape")
    if "currentlandscape" in normalized:
        tokens.add("currentlandscape")
    if "implemented_value" in normalized:
        tokens.add("implemented_value")
    if "note_only" in normalized:
        tokens.add("note_only")
    return tokens


def _has_any(tokens: set[str], candidates: Sequence[str]) -> bool:
    return any(candidate in tokens for candidate in candidates)


def _recommended_action(finding: Mapping[str, Any], impact_level: str) -> dict[str, Any]:
    action_payload = finding.get("recommendedAction")
    if isinstance(action_payload, Mapping):
        return {
            "type": str(action_payload.get("type") or "").strip() or _default_action_type(impact_level),
            "details": str(action_payload.get("details") or "Manual review required."),
        }

    return {
        "type": _default_action_type(impact_level),
        "details": str(
            finding.get("recommendedActionDetails")
            or "Manual review required before updating authoritative landscape."
        ),
    }


def _default_action_type(impact_level: str) -> str:
    if impact_level == "bmad_correct_course_required":
        return "correct_course"
    if impact_level == "local_feature_note":
        return "local_note"
    return "landscape_update"


def _normalize_severity(value: Any) -> str:
    severity = str(value or "advisory").strip().lower()
    if severity not in SALMON_EVENT_MODEL.SALMON_SEVERITIES:
        return "advisory"
    return severity


def _coerce_impacted_nodes(
    finding: Mapping[str, Any],
    feature_id: str,
    validation_result: Mapping[str, Any],
) -> dict[str, list[str]]:
    impacted_nodes = dict(_mapping(finding.get("impactedNodes")))
    for field_name in SALMON_EVENT_MODEL.SALMON_IMPACTED_NODE_FIELDS:
        values = _sequence(impacted_nodes.get(field_name))
        if not values and field_name == "features":
            values = _node_values(finding, "features", "featureIds", "featureId", "impactedFeature")
            values = values or _node_values(validation_result, "features", "featureIds", "featureId", "feature_id")
            if not values and feature_id:
                values = [feature_id]
        if not values:
            values = (
                _node_values(finding, field_name, *_node_aliases(field_name))
                or _node_values(validation_result, field_name, *_node_aliases(field_name))
            )
        impacted_nodes[field_name] = [str(value) for value in values if str(value).strip()]
    return impacted_nodes


def _node_aliases(field_name: str) -> tuple[str, ...]:
    return {
        "journeys": ("journeyIds", "journeyId", "impactedJourney", "journeyPath"),
        "outcomes": ("outcomeIds", "outcomeId", "impactedOutcome"),
        "roles": ("roleIds", "roleId", "stakeholderIds", "stakeholderId", "impactedRole", "impactedStakeholder"),
        "operatingLoops": ("operatingLoopIds", "operatingLoopId", "loopIds", "loopId", "impactedOperatingLoop"),
        "capabilities": ("capabilityIds", "capabilityId", "landscapeNodeIds", "landscapeNodeId", "impactedCapability"),
        "bmadArtifacts": (
            "bmadArtifactIds",
            "bmadArtifactId",
            "bmadArtifacts",
            "bmadArtifact",
            "prdRef",
            "architectureRef",
            "storyRef",
        ),
    }.get(field_name, ())


def _node_values(payload: Mapping[str, Any], *keys: str) -> list[Any]:
    values: list[Any] = []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            values.extend(value)
        elif value is not None and str(value).strip():
            values.append(value)
    return values


def _packet_path(packet_id: str) -> str:
    if not packet_id:
        return "unknown"
    return f".nextlens/packet-{packet_id}.json"


def _normalize_update(update: Mapping[str, Any]) -> dict[str, Any]:
    target = str(update.get("target") or "").strip()
    if not target:
        raise ValueError("Landscape update target is required.")
    change_type = str(update.get("changeType") or "").strip()
    if not change_type:
        raise ValueError(f"Landscape update changeType is required for {target}.")
    rationale = str(update.get("rationale") or "").strip()
    if not rationale:
        raise ValueError(f"Landscape update rationale is required for {target}.")
    authority = str(update.get("authority") or "").strip()
    if not authority:
        raise ValueError(f"Landscape update authority is required for {target}.")
    payload = update.get("payload")
    normalized = {
        "target": target,
        "changeType": change_type,
        "rationale": rationale,
        "authority": authority,
    }
    if payload is not None:
        normalized["payload"] = payload
    return normalized


def _normalize_source_refs(source_refs: Mapping[str, Any]) -> dict[str, Any]:
    source_map = {str(key): value for key, value in source_refs.items()}
    normalized = {
        "packetRef": source_map.get("packetRef") or source_map.get("packet"),
        "evidenceRef": source_map.get("evidenceRef") or source_map.get("evidence"),
        "validationRef": source_map.get("validationRef") or source_map.get("validation"),
        "salmonRef": source_map.get("salmonRef") or source_map.get("salmon"),
    }
    return {key: (str(value) if value is not None else None) for key, value in normalized.items()}


def _landscape_update_path(docs_path: str | Path, update: Mapping[str, Any]) -> Path:
    update_id = str(update.get("updateId") or "").strip()
    if not update_id:
        raise ValueError("Landscape update requires updateId.")
    return Path(docs_path) / ".nextlens" / "landscape-updates" / f"update-{update_id}.yaml"


def _validated_update_target(docs_root: Path, update: Mapping[str, Any]) -> Path:
    target = str(update.get("target") or "").strip()
    if not target:
        raise ValueError("Landscape update target is required.")
    target_path = Path(target)
    if not target_path.is_absolute():
        target_path = docs_root / target_path
    target_path = target_path.resolve()
    landscape_root = (docs_root / "landscape").resolve()
    try:
        relative = target_path.relative_to(landscape_root)
    except ValueError:
        raise ValueError(f"Landscape update target must remain under {landscape_root}.") from None
    if not relative.parts:
        raise ValueError("Landscape update target must point to a specific entity file.")
    if relative.parts[0] not in LANDSCAPE_ALLOWED_DIRECTORIES:
        raise ValueError(f"Landscape update target directory '{relative.parts[0]}' is not allowed.")
    if target_path.suffix not in {".yaml", ".yml"}:
        raise ValueError("Landscape update target must be a YAML file.")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    return target_path


def _require_yaml():
    if yaml is None:
        raise RuntimeError("PyYAML is required for landscape update persistence.") from _YAML_IMPORT_ERROR
    return yaml


def _atomic_write_yaml(path: Path, payload: Mapping[str, Any], yaml_module: Any, *, replace_fn: Any = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f"{path.stem}-", suffix=".tmp")
    temp_path = Path(temp_name)
    active_replace = replace_fn or os.replace
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            yaml_module.safe_dump(dict(payload), handle, sort_keys=False)
        active_replace(str(temp_path), str(path))
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _utc_timestamp(now_factory: Any) -> str:
    now = now_factory() if now_factory else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
