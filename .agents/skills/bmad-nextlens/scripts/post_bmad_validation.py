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


@dataclass(frozen=True)
class PostBmadValidationResult:
    status: str
    validation_result: dict[str, Any] = field(default_factory=dict)
    validation_path: Path | None = None
    salmon_result: Any | None = None
    landscape_result: Any | None = None
    stage_outcomes: dict[str, str] = field(default_factory=dict)
    refs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


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
    now_factory: Callable[[], datetime] | None = None,
    replace_fn: Callable[[str, str], None] | None = None,
) -> PostBmadValidationResult:
    docs_root = Path(docs_path)
    packet_id = str(packet.get("packetId") or "")
    feature_id = str(packet.get("featureId") or "")

    try:
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
        if create_salmon and validation_result:
            salmon_validation = _ensure_salmon_findings(validation_result)
            if salmon_validation:
                salmon_result = SALMON_LANDSCAPE.generate_salmon_signals_from_validation(
                    salmon_validation,
                    docs_root,
                    now_factory=now_factory,
                )
                salmon_outcome, salmon_refs = _salmon_outcome(salmon_result)

        landscape_result = None
        landscape_outcome = "pending"
        landscape_ref: str | None = None
        if landscape_updates:
            proposal = SALMON_LANDSCAPE.build_landscape_update_proposal(
                source_refs={
                    "packetRef": packet_id or None,
                    "evidenceRef": packet.get("evidenceBundleRef"),
                    "validationRef": str(validation_path) if validation_path else None,
                    "salmonRef": salmon_refs[0] if salmon_refs else None,
                },
                updates=landscape_updates,
                now_factory=now_factory,
            )
            landscape_result = SALMON_LANDSCAPE.persist_landscape_update(
                docs_root,
                proposal,
                replace_fn=replace_fn,
            )
            if landscape_result.status == "pass":
                landscape_outcome = "proposed"
                landscape_ref = str(landscape_result.path) if landscape_result.path else None
            else:
                landscape_outcome = "rejected"

        stage_outcomes = {
            "bmad_artifacts": bmad_artifacts_outcome,
            "stories": stories_outcome,
            "implementation_evidence": implementation_outcome,
            "validation": validation_outcome,
            "salmon": salmon_outcome,
            "landscape_update": landscape_outcome,
            "derived_graph_refresh": "pending",
        }
        refs = {
            "bmadArtifactBundleRef": bundle_ref,
            "implementationEvidenceRef": evidence_ref,
            "validationResultRef": str(validation_path) if validation_path else None,
            "salmonSignalRefs": salmon_refs,
            "landscapeUpdateRef": landscape_ref,
            "derivedGraphRef": packet.get("derivedGraphRef"),
        }

        return PostBmadValidationResult(
            status="pass",
            validation_result=validation_result,
            validation_path=validation_path,
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
) -> tuple[str, str, list[str], list[str]]:
    if bundle_payload is None:
        return "pending", "pending", list(required_story_ids or []), list(optional_story_ids or [])

    validation = DOWNSTREAM.validate_bmad_artifact_bundle(bundle_payload)
    bmad_outcome = "pass" if validation.status == "pass" else "blocked"
    stories = _mapping_sequence(bundle_payload.get("stories"))
    required_from_bundle, optional_from_bundle = _split_story_ids(stories)
    required_ids = list(required_story_ids) if required_story_ids is not None else required_from_bundle
    optional_ids = list(optional_story_ids) if optional_story_ids is not None else optional_from_bundle
    if not stories and not required_ids and not optional_ids:
        stories_outcome = "pending"
    else:
        stories_outcome = "pass" if validation.status == "pass" else "blocked"
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
        return "pass"
    return "blocked"


def _validation_outcome(result: Mapping[str, Any]) -> str:
    status = str(result.get("status") or "").lower()
    if status == "pass":
        return "pass"
    if status == "pass_with_warnings":
        return "pass_with_warnings"
    if status == "salmon_required":
        return "salmon_required"
    if status == "failed":
        return "failed"
    return "pending"


def _salmon_outcome(result: Any) -> tuple[str, list[str]]:
    status = str(getattr(result, "status", "") or "").lower()
    if status == "fail":
        return "blocked", []
    if status == "skipped":
        return "none", []
    dedup_results = list(getattr(result, "dedup_results", ()) or ())
    dedup_statuses = {str(getattr(item, "status", "") or "") for item in dedup_results}
    if dedup_statuses & {"merged", "duplicate_ignored"}:
        outcome = "deduped"
    else:
        outcome = "created"
    refs = [
        str(item.event_path)
        for item in dedup_results
        if getattr(item, "event_path", None) is not None
    ]
    return outcome, refs


def _ensure_salmon_findings(result: Mapping[str, Any]) -> Mapping[str, Any] | None:
    findings = _mapping_sequence(result.get("findings"))
    allowed_levels = SALMON_LANDSCAPE.SALMON_EVENT_MODEL.SALMON_IMPACT_LEVELS
    if any(str(finding.get("impactLevel") or "").strip() in allowed_levels for finding in findings):
        return result
    if not bool(result.get("salmonRequired")):
        return None
    feature_id = str(result.get("featureId") or "feature")
    fallback_findings = []
    for finding in findings:
        if str(finding.get("category") or "") == "scope":
            fallback_findings.append(
                {
                    "impactLevel": "feature_scope_change",
                    "issueDescription": str(finding.get("message") or "Scope change detected."),
                    "severity": str(finding.get("severity") or "advisory"),
                    "impactedNodes": _fallback_impacted_nodes(feature_id),
                }
            )
    if not fallback_findings:
        fallback_findings.append(
            {
                "impactLevel": "feature_scope_change",
                "issueDescription": "Validation indicated upstream truth changed.",
                "severity": "advisory",
                "impactedNodes": _fallback_impacted_nodes(feature_id),
            }
        )
    stitched = dict(result)
    stitched["findings"] = fallback_findings
    return stitched


def _fallback_impacted_nodes(feature_id: str) -> dict[str, list[str]]:
    return {
        "features": [feature_id],
        "journeys": [],
        "outcomes": [],
        "roles": [],
        "operatingLoops": [],
        "capabilities": [],
        "bmadArtifacts": [],
    }


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
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        yaml_module = _require_yaml()
        payload = yaml_module.safe_load(text)
    else:
        payload = json.loads(text)
    if not isinstance(payload, Mapping):
        raise ValueError(f"Payload at {path} must be a mapping.")
    return dict(payload)


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
