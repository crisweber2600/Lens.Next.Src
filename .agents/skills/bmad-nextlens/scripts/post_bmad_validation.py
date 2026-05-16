"""Post-BMAD validation flow for implementation evidence and downstream updates."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Callable, Mapping, Sequence
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


DOWNSTREAM = _load_runtime_module("downstream_hierarchy", "downstream_hierarchy.py")
SALMON_LANDSCAPE = _load_runtime_module("downstream_salmon_landscape", "downstream_salmon_landscape.py")
EVIDENCE_BUNDLE = _load_runtime_module("evidence_bundle", "evidence_bundle.py")


@dataclass(frozen=True)
class PostBmadValidationResult:
    status: str
    validation_result: dict[str, Any] = field(default_factory=dict)
    validation_path: Path | None = None
    evidence_bundle_ref: str | None = None
    salmon_result: Any | None = None
    landscape_result: Any | None = None
    stage_outcomes: dict[str, str] = field(default_factory=dict)
    refs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def run_validate_action(
    packet_source: str,
    implementation_evidence_source: str,
    *,
    bmad_artifacts_source: str | None = None,
    docs_path: str | Path | None = None,
    landscape_update_source: str | None = None,
    landscape_update_mode: str | None = None,
) -> dict[str, Any]:
    """Deterministic action runner for governed post-BMAD validation."""
    try:
        apply_landscape_updates = _validate_action_apply_mode(landscape_update_mode)
        packet = _load_required_mapping_source(packet_source, label="packet")
        implementation_evidence = _load_required_mapping_source(
            implementation_evidence_source,
            label="implementation evidence",
        )
        bmad_artifacts = (
            _load_required_mapping_source(bmad_artifacts_source, label="BMAD artifacts")
            if bmad_artifacts_source is not None
            else None
        )
        landscape_updates = (
            _load_landscape_update_source(
                landscape_update_source,
                apply_landscape_updates=apply_landscape_updates,
            )
            if landscape_update_source is not None
            else None
        )
    except Exception as exc:
        return _validate_action_failure(str(exc))

    result = run_post_bmad_validation_flow(
        packet=packet,
        docs_path=Path(docs_path) if docs_path is not None else Path.cwd(),
        bmad_artifact_bundle=bmad_artifacts,
        implementation_evidence=implementation_evidence,
        bmad_artifact_bundle_ref=bmad_artifacts_source,
        implementation_evidence_ref=implementation_evidence_source,
        landscape_updates=landscape_updates,
        apply_landscape_updates=apply_landscape_updates,
    )
    return _validate_action_result(result)


def run_post_bmad_validation_flow(
    *,
    packet: Mapping[str, Any],
    docs_path: str | Path,
    bmad_artifact_bundle: Mapping[str, Any] | str | Path | None = None,
    implementation_evidence: Mapping[str, Any] | str | Path | None = None,
    bmad_artifact_bundle_ref: str | None = None,
    implementation_evidence_ref: str | None = None,
    required_story_ids: Sequence[str] | None = None,
    optional_story_ids: Sequence[str] | None = None,
    required_outcome_ids: Sequence[str] | None = None,
    optional_outcome_ids: Sequence[str] | None = None,
    required_journey_ids: Sequence[str] | None = None,
    optional_journey_ids: Sequence[str] | None = None,
    create_salmon: bool = True,
    landscape_updates: Sequence[Mapping[str, Any]] | None = None,
    apply_landscape_updates: bool = False,
    now_factory: Callable[[], datetime] | None = None,
    replace_fn: Callable[[str, str], None] | None = None,
) -> PostBmadValidationResult:
    docs_root = Path(docs_path)
    packet_id = str(packet.get("packetId") or "")
    feature_id = str(packet.get("featureId") or "")
    evidence_bundle_ref = str(packet.get("evidenceBundleRef") or "").strip()

    try:
        if not evidence_bundle_ref:
            raise ValueError("packet.evidenceBundleRef is required for post-BMAD validation.")
        bundle_payload, bundle_ref = _resolve_payload(bmad_artifact_bundle, label="BMAD artifact bundle")
        if bmad_artifact_bundle_ref:
            bundle_ref = bmad_artifact_bundle_ref
        evidence_payload, evidence_ref = _resolve_payload(
            implementation_evidence,
            label="implementation evidence",
        )
        if implementation_evidence_ref:
            evidence_ref = implementation_evidence_ref

        bmad_artifacts_outcome, stories_outcome, story_ids, optional_story_ids_resolved = _bundle_outcomes(
            bundle_payload,
            packet_trace=_mapping(packet.get("trace")),
            required_story_ids=required_story_ids,
            optional_story_ids=optional_story_ids,
        )

        implementation_outcome = "pending"
        evidence_validation = None
        if evidence_payload is not None:
            evidence_validation = DOWNSTREAM.validate_implementation_evidence(
                evidence_payload,
                expected_packet_id=packet_id or None,
                expected_feature_id=feature_id or None,
                required_story_ids=story_ids,
                optional_story_ids=optional_story_ids_resolved,
                packet_trace=_mapping(packet.get("trace")),
            )
            implementation_outcome = _implementation_outcome(evidence_validation)

        validation_result: dict[str, Any] = {}
        validation_path = None
        validation_outcome = "pending"
        if evidence_payload is not None:
            validation_result = DOWNSTREAM.build_validation_result(
                evidence_payload,
                expected_packet_id=packet_id or None,
                expected_feature_id=feature_id or None,
                required_story_ids=story_ids,
                optional_story_ids=optional_story_ids_resolved,
                required_outcome_ids=_resolve_required_ids(
                    required_outcome_ids, _sequence(_mapping(packet.get("trace")).get("outcomeIds"))
                ),
                optional_outcome_ids=optional_outcome_ids,
                required_journey_ids=_resolve_required_ids(
                    required_journey_ids, _sequence(_mapping(packet.get("trace")).get("journeyIds"))
                ),
                optional_journey_ids=optional_journey_ids,
                packet_trace=_mapping(packet.get("trace")),
                now_factory=now_factory,
            )
            validation_result, validation_path = _persist_validation_result(
                docs_root,
                validation_result,
                now_factory=now_factory,
                replace_fn=replace_fn,
            )
            validation_outcome = _validation_outcome(validation_result)

        salmon_result = None
        salmon_outcome = "none"
        salmon_refs: list[str] = []
        if not create_salmon and validation_result:
            salmon_outcome = "skipped"
        elif create_salmon and validation_result:
            salmon_validation = _ensure_salmon_findings(validation_result, packet=packet)
            if salmon_validation:
                salmon_result = SALMON_LANDSCAPE.generate_salmon_signals_from_validation(
                    salmon_validation,
                    docs_root,
                    now_factory=now_factory,
                )
                salmon_outcome, salmon_refs = _salmon_outcome(salmon_result)
            else:
                salmon_outcome = "none"

        landscape_result = None
        landscape_outcome = "pending"
        derived_graph_outcome = "pending"
        landscape_ref: str | None = None
        derived_graph_ref: str | None = str(packet.get("derivedGraphRef") or "") or None
        resolved_landscape_updates = list(landscape_updates or [])
        if not resolved_landscape_updates and validation_result:
            resolved_landscape_updates = _default_landscape_updates(
                packet=packet,
                validation_result=validation_result,
                salmon_result=salmon_result,
                now_factory=now_factory,
            )
        if resolved_landscape_updates:
            landscape_source_refs = _landscape_source_refs(
                packet_id=packet_id,
                evidence_bundle_ref=evidence_bundle_ref,
                implementation_evidence_ref=evidence_ref,
                validation_path=validation_path,
                salmon_refs=salmon_refs,
            )
            proposal = SALMON_LANDSCAPE.build_landscape_update_proposal(
                source_refs=landscape_source_refs,
                updates=resolved_landscape_updates,
                now_factory=now_factory,
            )
            proposal_result = SALMON_LANDSCAPE.persist_landscape_update(
                docs_root,
                proposal,
                replace_fn=replace_fn,
            )
            landscape_result = proposal_result
            if proposal_result.status == "pass":
                landscape_outcome = _landscape_proposal_outcome(proposal_result)
                landscape_ref = str(proposal_result.path) if proposal_result.path else None
                if apply_landscape_updates:
                    landscape_result = SALMON_LANDSCAPE.apply_landscape_update(
                        docs_root,
                        proposal_result.update,
                        now_factory=now_factory,
                        replace_fn=replace_fn,
                    )
                    if landscape_result.status == "pass":
                        landscape_outcome = "applied"
                        landscape_ref = (
                            str(landscape_result.update_path)
                            if landscape_result.update_path
                            else landscape_ref
                        )
                        derived_graph_ref = landscape_result.derived_graph_ref or derived_graph_ref
                        derived_graph_outcome = _derived_graph_refresh_outcome(landscape_result)
                    else:
                        landscape_outcome = "blocked"
                        derived_graph_outcome = "blocked"
            else:
                landscape_outcome = _landscape_proposal_outcome(proposal_result)
                if apply_landscape_updates:
                    derived_graph_outcome = "blocked"

        stage_outcomes = {
            "bmad_artifacts": bmad_artifacts_outcome,
            "stories": stories_outcome,
            "implementation_evidence": implementation_outcome,
            "validation": validation_outcome,
            "salmon": salmon_outcome,
            "landscape_update": landscape_outcome,
            "derived_graph_refresh": derived_graph_outcome,
        }
        refs = {
            "evidenceBundleRef": evidence_bundle_ref,
            "bmadArtifactBundleRef": bundle_ref,
            "implementationEvidenceRef": evidence_ref,
            "validationResultRef": str(validation_path) if validation_path else None,
            "salmonSignalRefs": salmon_refs,
            "landscapeUpdateRef": landscape_ref,
            "derivedGraphRef": derived_graph_ref,
            "derivedGraphAuthoritative": False,
        }
        if landscape_result is not None:
            refs["sourceRefs"] = dict(landscape_result.update.get("sourceRefs") or {})
        evidence_result = EVIDENCE_BUNDLE.merge_nextlens_evidence_bundle(
            docs_root,
            packet=packet,
            artifact_refs=refs,
            stage_outcomes=stage_outcomes,
            now_factory=now_factory,
            replace_fn=replace_fn,
        )
        if evidence_result.status != "pass":
            raise RuntimeError(evidence_result.error or "Evidence bundle update failed.")

        return PostBmadValidationResult(
            status="pass",
            validation_result=validation_result,
            validation_path=validation_path,
            evidence_bundle_ref=str(evidence_result.path) if evidence_result.path else evidence_bundle_ref,
            salmon_result=salmon_result,
            landscape_result=landscape_result,
            stage_outcomes=stage_outcomes,
            refs=refs,
        )
    except Exception as exc:  # pragma: no cover - surfaced in caller
        return PostBmadValidationResult(status="fail", error=str(exc))


def validation_result_path(docs_path: str | Path, validation_id: str) -> Path:
    if not validation_id:
        raise ValueError("validation_id is required for validation result path.")
    return Path(docs_path) / ".nextlens" / "validation" / f"validation-{validation_id}.json"


def _validate_action_apply_mode(mode: str | None) -> bool:
    normalized = str(mode or "propose").strip().lower()
    if normalized in {"", "propose", "proposal"}:
        return False
    if normalized == "apply":
        return True
    raise ValueError(
        "Invalid landscape_update_mode "
        f"'{mode}'. Expected one of: propose, proposal, apply."
    )


def _load_required_mapping_source(source: str | None, *, label: str) -> dict[str, Any]:
    if source is None or not str(source).strip():
        raise ValueError(f"{label} source is required.")
    path = Path(str(source))
    if not path.exists():
        raise ValueError(f"{label} source could not be loaded: {source}")
    try:
        payload = _load_payload_file(path)
    except Exception as exc:
        raise ValueError(f"{label} source could not be loaded: {source}: {exc}") from exc
    return dict(payload)


def _load_landscape_update_source(
    source: str,
    *,
    apply_landscape_updates: bool,
) -> list[dict[str, Any]]:
    path = Path(str(source))
    if not path.exists():
        raise ValueError(f"landscape update source could not be loaded: {source}")
    try:
        payload = _load_data_file(path)
    except Exception as exc:
        raise ValueError(f"landscape update source could not be loaded: {source}: {exc}") from exc

    if isinstance(payload, Mapping) and isinstance(payload.get("updates"), list):
        raw_updates = payload.get("updates")
    elif isinstance(payload, Mapping):
        raw_updates = [payload]
    elif isinstance(payload, list):
        raw_updates = payload
    else:
        raise ValueError("landscape update source must be an object, list, or object with updates.")

    updates: list[dict[str, Any]] = []
    for index, raw_update in enumerate(raw_updates or []):
        if not isinstance(raw_update, Mapping):
            raise ValueError(f"landscape update at index {index} must be an object.")
        updates.append(
            _validate_action_landscape_update(
                raw_update,
                index=index,
                apply_landscape_updates=apply_landscape_updates,
            )
        )
    if not updates:
        raise ValueError("landscape update source must contain at least one update.")
    return updates


def _validate_action_landscape_update(
    update: Mapping[str, Any],
    *,
    index: int,
    apply_landscape_updates: bool,
) -> dict[str, Any]:
    target = str(update.get("target") or "").strip()
    change_type = str(update.get("changeType") or "").strip()
    rationale = str(update.get("rationale") or "").strip()
    authority = str(update.get("authority") or "").strip()
    missing = [
        name
        for name, value in (
            ("target", target),
            ("changeType", change_type),
            ("rationale", rationale),
            ("authority", authority),
        )
        if not value
    ]
    if missing:
        raise ValueError(
            f"landscape update at index {index} missing required field(s): {', '.join(missing)}."
        )
    if change_type.lower() not in SALMON_LANDSCAPE.LANDSCAPE_UPDATE_CHANGE_TYPES:
        raise ValueError(
            f"landscape update at index {index} has unsupported changeType '{change_type}'."
        )
    payload = update.get("payload")
    if payload is not None and not isinstance(payload, Mapping):
        raise ValueError(f"landscape update at index {index} payload must be an object.")
    if apply_landscape_updates and change_type.lower() != "delete" and payload is None:
        raise ValueError(
            f"landscape update at index {index} payload is required when apply mode writes a target."
        )
    try:
        return SALMON_LANDSCAPE._normalize_update(update)
    except Exception as exc:
        raise ValueError(f"landscape update at index {index} is invalid: {exc}") from exc


def _validate_action_failure(error: str) -> dict[str, Any]:
    return {
        "status": "fail",
        "validationResultRef": None,
        "evidenceBundleRef": None,
        "salmonSignalRefs": [],
        "landscapeUpdateRef": None,
        "derivedGraphRef": None,
        "derivedGraphAuthoritative": None,
        "stageOutcomes": {},
        "nextAction": "Fix Validate action input and rerun validation.",
        "error": error,
    }


def _validate_action_result(result: PostBmadValidationResult) -> dict[str, Any]:
    refs = result.refs or {}
    stage_outcomes = dict(result.stage_outcomes or {})
    status = result.status
    error = result.error
    if result.status == "pass" and (
        stage_outcomes.get("landscape_update") == "blocked"
        or stage_outcomes.get("derived_graph_refresh") == "blocked"
    ):
        status = "fail"
        error = str(getattr(result.landscape_result, "error", "") or "Landscape update was blocked.")
    payload = {
        "status": status,
        "validationResultRef": refs.get("validationResultRef"),
        "evidenceBundleRef": result.evidence_bundle_ref or refs.get("evidenceBundleRef"),
        "salmonSignalRefs": list(refs.get("salmonSignalRefs") or []),
        "landscapeUpdateRef": refs.get("landscapeUpdateRef"),
        "derivedGraphRef": refs.get("derivedGraphRef"),
        "derivedGraphAuthoritative": refs.get("derivedGraphAuthoritative"),
        "stageOutcomes": stage_outcomes,
        "nextAction": _validate_action_next_action(result, status=status),
        "error": error,
    }
    return payload


def _validate_action_next_action(result: PostBmadValidationResult, *, status: str | None = None) -> str:
    if (status or result.status) != "pass":
        return "Fix post-BMAD validation errors and rerun Validate."
    landscape_outcome = str((result.stage_outcomes or {}).get("landscape_update") or "")
    if landscape_outcome == "applied":
        return "Review the applied Landscape update and refreshed non-authoritative Derived Graph."
    if landscape_outcome == "proposed":
        return "Review the proposed Landscape update; rerun Validate in apply mode to apply it."
    if (result.refs or {}).get("salmonSignalRefs"):
        return "Review Salmon signals before updating the Living Landscape."
    return "Review validation outputs and continue BMAD handoff."


def _landscape_source_refs(
    *,
    packet_id: str,
    evidence_bundle_ref: str,
    implementation_evidence_ref: str | None,
    validation_path: Path | None,
    salmon_refs: Sequence[str],
) -> dict[str, Any]:
    refs: dict[str, Any] = {
        "packetRef": packet_id or None,
        "validationRef": str(validation_path) if validation_path else None,
        "salmonRef": salmon_refs[0] if salmon_refs else None,
    }
    if evidence_bundle_ref:
        refs["evidenceBundleRef"] = evidence_bundle_ref
        refs["evidenceRef"] = evidence_bundle_ref
    if implementation_evidence_ref:
        refs["implementationEvidenceRef"] = implementation_evidence_ref
    return refs


def _persist_validation_result(
    docs_root: Path,
    result: Mapping[str, Any],
    *,
    now_factory: Callable[[], datetime] | None,
    replace_fn: Callable[[str, str], None] | None,
) -> tuple[dict[str, Any], Path]:
    validation_id = str(
        result.get("validationId") or result.get("validation_id") or uuid.uuid4()
    )
    payload = dict(result)
    payload["validationId"] = validation_id
    payload.setdefault("createdAt", _utc_timestamp(now_factory))
    path = validation_result_path(docs_root, validation_id)
    _atomic_write_json(path, payload, replace_fn=replace_fn)
    return payload, path


def _bundle_outcomes(
    bundle_payload: Mapping[str, Any] | None,
    *,
    required_story_ids: Sequence[str] | None,
    optional_story_ids: Sequence[str] | None,
    packet_trace: Mapping[str, Any] | None = None,
) -> tuple[str, str, list[str], list[str]]:
    if bundle_payload is None:
        return "pending", "pending", list(required_story_ids or []), list(optional_story_ids or [])

    validation = DOWNSTREAM.validate_bmad_artifact_bundle(
        bundle_payload,
        packet_trace=packet_trace,
    )
    bmad_outcome = _validation_status_to_stage(validation.status)
    stories = _mapping_sequence(bundle_payload.get("stories"))
    required_from_bundle, optional_from_bundle = _split_story_ids(stories)
    required_ids = list(required_story_ids) if required_story_ids is not None else required_from_bundle
    optional_ids = list(optional_story_ids) if optional_story_ids is not None else optional_from_bundle
    if not stories and not required_ids and not optional_ids:
        stories_outcome = "pending"
    else:
        stories_outcome = _validation_status_to_stage(validation.status)
    return bmad_outcome, stories_outcome, required_ids, optional_ids


def _split_story_ids(stories: Sequence[Mapping[str, Any]]) -> tuple[list[str], list[str]]:
    required: list[str] = []
    optional: list[str] = []
    for story in stories:
        story_id = str(story.get("id") or "").strip()
        if not story_id:
            continue
        status = str(story.get("status") or "").strip().lower()
        if status in {"optional", "backlog", "deferred"}:
            optional.append(story_id)
        else:
            required.append(story_id)
    return required, optional


def _implementation_outcome(result: Any) -> str:
    status = str(getattr(result, "status", "") or "").lower()
    if status == "pass":
        return "pass"
    if status == "pass_with_warnings":
        return "pass_with_warnings"
    if status in {"fail", "failed"}:
        return "failed"
    return "pending"


def _validation_outcome(result: Mapping[str, Any]) -> str:
    status = str(result.get("status") or "").lower()
    if status in {"pass", "pass_with_warnings", "failed", "salmon_required"}:
        return status
    return "pending"


def _salmon_outcome(result: Any) -> tuple[str, list[str]]:
    status = str(getattr(result, "status", "") or "").lower()
    if status == "fail":
        return "blocked", []
    if status == "skipped":
        return "skipped", []
    dedup_results = list(getattr(result, "dedup_results", ()) or ())
    refs = [
        str(item.event_path)
        for item in dedup_results
        if getattr(item, "event_path", None) is not None
    ]
    dedup_statuses = {str(getattr(item, "status", "") or "").lower() for item in dedup_results}
    if dedup_statuses and not (dedup_statuses - {"duplicate_ignored", "merged"}):
        return "deduped", refs
    if "new" in dedup_statuses or refs:
        return "created", refs
    return "none", refs


def _validation_status_to_stage(status: str) -> str:
    normalized = str(status or "").lower()
    if normalized == "pass":
        return "pass"
    if normalized == "pass_with_warnings":
        return "pass_with_warnings"
    if normalized in {"fail", "failed"}:
        return "failed"
    return "pending"


def _landscape_proposal_outcome(result: Any) -> str:
    update_status = str(_mapping(getattr(result, "update", {})).get("status") or "").lower()
    if update_status in {"proposed", "applied", "rejected", "blocked"}:
        return update_status
    if str(getattr(result, "status", "") or "").lower() == "pass":
        return "proposed"
    return "blocked"


def _ensure_salmon_findings(
    result: Mapping[str, Any],
    *,
    packet: Mapping[str, Any] | None = None,
) -> Mapping[str, Any] | None:
    findings = _mapping_sequence(result.get("findings"))
    allowed_levels = SALMON_LANDSCAPE.SALMON_EVENT_MODEL.SALMON_IMPACT_LEVELS
    if not bool(result.get("salmonRequired")):
        if any(str(finding.get("impactLevel") or "").strip() in allowed_levels for finding in findings):
            return result
        return None
    packet = _mapping(packet)
    feature_id = str(result.get("featureId") or packet.get("featureId") or "feature")
    salmon_findings = []
    for finding in findings:
        impact_level = str(finding.get("impactLevel") or "").strip()
        if impact_level not in allowed_levels:
            impact_level = _mapped_salmon_impact_level(finding)
        salmon_findings.append(
            {
                **dict(finding),
                "impactLevel": impact_level,
                "issueDescription": str(
                    finding.get("issueDescription")
                    or finding.get("message")
                    or "Validation indicated upstream truth changed."
                ),
                "severity": str(finding.get("severity") or "advisory"),
                "impactedNodes": _enriched_impacted_nodes(finding, impact_level, feature_id, result, packet),
            }
        )
    if not salmon_findings:
        salmon_findings.append(
            {
                "impactLevel": "feature_scope_change",
                "issueDescription": "Validation indicated upstream truth changed.",
                "severity": "advisory",
                "impactedNodes": _enriched_impacted_nodes({}, "feature_scope_change", feature_id, result, packet),
            }
        )
    stitched = dict(result)
    stitched["findings"] = salmon_findings
    return stitched


def _mapped_salmon_impact_level(finding: Mapping[str, Any]) -> str:
    text = _finding_match_text(finding)
    ordered_mappings = (
        (("scope", "scope_leak", "explicit_out_of_scope", "explicitoutofscope"), "feature_scope_change"),
        (("journey", "journey_evidence", "journey_path"), "journey_assumption_change"),
        (("outcome", "outcome_evidence", "value_mismatch"), "outcome_reframe"),
        (("role", "stakeholder", "review_owner"), "role_or_stakeholder_change"),
        (("operating_loop", "operatingloop", "loop"), "operating_loop_change"),
        (("landscape", "current_truth", "currenttruth", "capability"), "capability_or_landscape_update"),
        (("bmad", "prd", "architecture", "epic", "story"), "bmad_correct_course_required"),
        (("note", "local"), "local_feature_note"),
    )
    for needles, impact_level in ordered_mappings:
        if any(needle in text for needle in needles):
            return impact_level
    return "feature_scope_change"


def _finding_match_text(finding: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "category",
        "type",
        "findingType",
        "issueClass",
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
            parts.append(str(value))
    text = " ".join(parts).lower()
    return text.replace("-", "_").replace(".", "_").replace("/", "_").replace(" ", "_")


def _enriched_impacted_nodes(
    finding: Mapping[str, Any],
    impact_level: str,
    feature_id: str,
    validation_result: Mapping[str, Any],
    packet: Mapping[str, Any],
) -> dict[str, list[str]]:
    impacted_nodes = _fallback_impacted_nodes(feature_id)
    existing_nodes = _mapping(finding.get("impactedNodes"))
    for field_name in impacted_nodes:
        impacted_nodes[field_name] = _unique_strings(_sequence(existing_nodes.get(field_name)))

    impacted_nodes["features"] = _unique_strings(
        impacted_nodes["features"]
        + _node_values(finding, "features", "featureIds", "featureId", "impactedFeature")
        + _node_values(validation_result, "features", "featureIds", "featureId", "feature_id")
        + _node_values(packet, "features", "featureIds", "featureId")
        + ([feature_id] if feature_id else [])
    )

    trace = _mapping(packet.get("trace"))
    if impact_level == "journey_assumption_change":
        impacted_nodes["journeys"] = _unique_strings(
            impacted_nodes["journeys"]
            + _node_values(finding, "journeys", "journeyIds", "journeyId", "impactedJourney", "journeyPath")
            + _node_values(validation_result, "journeys", "journeyIds", "journeyId")
            + _node_values(trace, "journeyIds", "journeyId")
        )
    if impact_level == "outcome_reframe":
        impacted_nodes["outcomes"] = _unique_strings(
            impacted_nodes["outcomes"]
            + _node_values(finding, "outcomes", "outcomeIds", "outcomeId", "impactedOutcome")
            + _node_values(validation_result, "outcomes", "outcomeIds", "outcomeId")
            + _node_values(trace, "outcomeIds", "outcomeId")
        )
    if impact_level == "role_or_stakeholder_change":
        impacted_nodes["roles"] = _unique_strings(
            impacted_nodes["roles"]
            + _node_values(
                finding,
                "roles",
                "roleIds",
                "roleId",
                "stakeholderIds",
                "stakeholderId",
                "impactedRole",
                "impactedStakeholder",
                "reviewOwner",
                "reviewOwnerId",
            )
        )
    if impact_level == "operating_loop_change":
        impacted_nodes["operatingLoops"] = _unique_strings(
            impacted_nodes["operatingLoops"]
            + _node_values(
                finding,
                "operatingLoops",
                "operatingLoopIds",
                "operatingLoopId",
                "loopIds",
                "loopId",
                "impactedOperatingLoop",
            )
        )
    if impact_level == "capability_or_landscape_update":
        impacted_nodes["capabilities"] = _unique_strings(
            impacted_nodes["capabilities"]
            + _node_values(
                finding,
                "capabilities",
                "capabilityIds",
                "capabilityId",
                "landscapeNodeIds",
                "landscapeNodeId",
                "impactedCapability",
            )
        )
    if impact_level == "bmad_correct_course_required":
        impacted_nodes["bmadArtifacts"] = _unique_strings(
            impacted_nodes["bmadArtifacts"]
            + _node_values(
                finding,
                "bmadArtifacts",
                "bmadArtifactIds",
                "bmadArtifactId",
                "bmadArtifact",
                "prdRef",
                "architectureRef",
                "epicRef",
                "storyRef",
                "storyId",
                "storyIds",
            )
            + _node_values(validation_result, "bmadArtifacts", "bmadArtifactIds", "bmadArtifactId")
        )
    return impacted_nodes


def _fallback_impacted_nodes(feature_id: str) -> dict[str, list[str]]:
    return {
        "features": [feature_id] if feature_id else [],
        "journeys": [],
        "outcomes": [],
        "roles": [],
        "operatingLoops": [],
        "capabilities": [],
        "bmadArtifacts": [],
    }


def _node_values(payload: Mapping[str, Any], *keys: str) -> list[Any]:
    values: list[Any] = []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            values.extend(value)
        elif value is not None and str(value).strip():
            values.append(value)
    return values


def _unique_strings(values: Sequence[Any]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def _default_landscape_updates(
    *,
    packet: Mapping[str, Any],
    validation_result: Mapping[str, Any],
    salmon_result: Any | None,
    now_factory: Callable[[], datetime] | None,
) -> list[dict[str, Any]]:
    status = str(validation_result.get("status") or "").strip().lower()
    salmon_events = list(getattr(salmon_result, "events", ()) or ())
    if status == "pass":
        return [
            _feature_validation_update(
                packet,
                validation_result,
                status="validated",
                change_type="current_truth",
                now_factory=now_factory,
            )
        ]
    if status == "pass_with_warnings":
        return [
            _feature_validation_update(
                packet,
                validation_result,
                status="validated_with_warnings",
                change_type="status",
                now_factory=now_factory,
            )
        ]
    if status == "salmon_required" or salmon_events:
        return _salmon_landscape_updates(packet, validation_result, salmon_events, now_factory=now_factory)
    return []


def _feature_validation_update(
    packet: Mapping[str, Any],
    validation_result: Mapping[str, Any],
    *,
    status: str,
    change_type: str,
    now_factory: Callable[[], datetime] | None,
) -> dict[str, Any]:
    feature_id = _feature_id(packet, validation_result)
    findings = _serializable_findings(validation_result)
    rationale = "BMAD validation passed and confirmed Feature current truth."
    if findings:
        rationale = "BMAD validation completed with warnings that should be retained on the Feature."
    return {
        "target": _feature_target(feature_id),
        "changeType": change_type,
        "rationale": rationale,
        "authority": "living_landscape",
        "payload": _feature_payload(
            feature_id,
            packet=packet,
            validation_result=validation_result,
            status=status,
            notes=[_finding_note(finding) for finding in findings],
            now_factory=now_factory,
        ),
    }


def _salmon_landscape_updates(
    packet: Mapping[str, Any],
    validation_result: Mapping[str, Any],
    salmon_events: Sequence[Mapping[str, Any]],
    *,
    now_factory: Callable[[], datetime] | None,
) -> list[dict[str, Any]]:
    updates: list[dict[str, Any]] = []
    if not salmon_events:
        updates.append(
            _feature_validation_update(
                packet,
                validation_result,
                status="salmon_review_required",
                change_type="status",
                now_factory=now_factory,
            )
        )
        return updates

    for event in salmon_events:
        if not isinstance(event, Mapping):
            continue
        feature_id = _salmon_feature_id(event, packet, validation_result)
        discovery = _mapping(event.get("discovery"))
        notes = [
            str(discovery.get("issueDescription") or "Salmon signal indicates upstream truth changed.")
        ]
        updates.append(
            {
                "target": _feature_target(feature_id),
                "changeType": "status",
                "rationale": "Salmon signal requires a Living Landscape Feature update.",
                "authority": "salmon",
                "payload": _feature_payload(
                    feature_id,
                    packet=packet,
                    validation_result=validation_result,
                    status="salmon_review_required",
                    notes=notes,
                    salmon_event=event,
                    now_factory=now_factory,
                ),
            }
        )
    return updates


def _feature_payload(
    feature_id: str,
    *,
    packet: Mapping[str, Any],
    validation_result: Mapping[str, Any],
    status: str,
    notes: Sequence[str],
    salmon_event: Mapping[str, Any] | None = None,
    now_factory: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    timestamp = _utc_timestamp(now_factory)
    salmon_refs = [str(salmon_event.get("id"))] if isinstance(salmon_event, Mapping) and salmon_event.get("id") else []
    return {
        "entityType": "feature",
        "identity": {
            "semanticId": feature_id,
            "opaqueId": f"opaque-{feature_id}",
            "name": str(packet.get("featureName") or validation_result.get("featureName") or feature_id),
        },
        "snapshot": {
            "status": status,
            "currentTruth": _current_truth(status),
            "validationStatus": str(validation_result.get("status") or ""),
            "notes": list(notes),
            "salmonSignalRefs": salmon_refs,
        },
        "relationships": {},
        "metadata": {
            "source": "post-bmad-validation",
            "author": "nextlens",
            "updatedAt": timestamp,
            "derivedGraphAuthoritative": False,
        },
    }


def _current_truth(status: str) -> str:
    if status == "validated":
        return "BMAD validation passed for this Feature."
    if status == "validated_with_warnings":
        return "BMAD validation passed with warning findings for this Feature."
    return "BMAD validation produced Salmon signals requiring Living Landscape review."


def _serializable_findings(validation_result: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [finding for finding in _mapping_sequence(validation_result.get("findings"))]


def _finding_note(finding: Mapping[str, Any]) -> str:
    severity = str(finding.get("severity") or "warning")
    message = str(finding.get("message") or finding.get("issueDescription") or "Validation warning.")
    return f"{severity}: {message}"


def _salmon_feature_id(
    event: Mapping[str, Any],
    packet: Mapping[str, Any],
    validation_result: Mapping[str, Any],
) -> str:
    impacted_nodes = _mapping(event.get("impactedNodes"))
    features = _sequence(impacted_nodes.get("features"))
    if features:
        return str(features[0])
    discovery = _mapping(event.get("discovery"))
    if discovery.get("impactedFeature"):
        return str(discovery.get("impactedFeature"))
    return _feature_id(packet, validation_result)


def _feature_id(packet: Mapping[str, Any], validation_result: Mapping[str, Any]) -> str:
    return str(packet.get("featureId") or validation_result.get("featureId") or "feature").strip() or "feature"


def _feature_target(feature_id: str) -> str:
    return f"landscape/feature/{feature_id}.yaml"


def _derived_graph_refresh_outcome(result: Any) -> str:
    if str(getattr(result, "status", "") or "").lower() != "pass":
        return "blocked"
    if not getattr(result, "derived_graph_ref", None):
        return "blocked"
    if getattr(result, "warnings", None):
        return "stale"
    return "pass"


def _resolve_payload(source: Any, *, label: str) -> tuple[Mapping[str, Any] | None, str | None]:
    if source is None:
        return None, None
    if isinstance(source, Mapping):
        return dict(source), None
    path = Path(str(source))
    if path.exists():
        return _load_payload_file(path), str(path)
    raise ValueError(f"{label} source could not be loaded: {source}")


def _load_payload_file(path: Path) -> Mapping[str, Any]:
    payload = _load_data_file(path)
    if not isinstance(payload, Mapping):
        raise ValueError(f"Payload at {path} must be a mapping.")
    return dict(payload)


def _load_data_file(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        yaml_module = _require_yaml()
        payload = yaml_module.safe_load(text)
    else:
        payload = json.loads(text)
    return payload


def _atomic_write_json(
    path: Path,
    payload: Mapping[str, Any],
    *,
    replace_fn: Callable[[str, str], None] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f"{path.stem}-", suffix=".tmp")
    temp_path = Path(temp_name)
    active_replace = replace_fn or os.replace
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(dict(payload), handle, indent=2, sort_keys=True)
            handle.write("\n")
        active_replace(str(temp_path), str(path))
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def _require_yaml():
    if yaml is None:
        raise RuntimeError("PyYAML is required to load YAML payloads.") from _YAML_IMPORT_ERROR
    return yaml


def _resolve_required_ids(explicit: Sequence[str] | None, fallback: Sequence[str]) -> list[str]:
    if explicit is not None:
        return [str(item) for item in explicit if str(item).strip()]
    return [str(item) for item in fallback if str(item).strip()]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return []


def _mapping_sequence(value: Any) -> list[Mapping[str, Any]]:
    return [item for item in _sequence(value) if isinstance(item, Mapping)]


def _utc_timestamp(now_factory: Callable[[], datetime] | None) -> str:
    now = now_factory() if now_factory else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
