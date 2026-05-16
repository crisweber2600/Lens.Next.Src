"""Generate durable NextLens evidence bundle YAML from collector manifests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Callable, Mapping

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover
    yaml = None
    _YAML_IMPORT_ERROR = exc
else:
    _YAML_IMPORT_ERROR = None


NEXTLENS_EVIDENCE_BUNDLE_SCHEMA_VERSION = "nextlens.evidence-bundle.v1"

NEXTLENS_STAGE_OUTCOME_DEFAULTS = {
    "intake": "pass",
    "extracted_concepts": "skipped",
    "context_sufficiency": "pass",
    "ranking": "pass",
    "confirmation": "pass",
    "authoritative_write": "pass",
    "derived_graph_rebuild": "pass",
    "doctor": "pass",
    "packet_emission": "pass",
    "bmad_handoff": "pending",
    "bmad_artifacts": "pending",
    "stories": "pending",
    "implementation_evidence": "pending",
    "validation": "pending",
    "salmon": "none",
    "landscape_update": "pending",
    "derived_graph_refresh": "pending",
}


@dataclass(frozen=True)
class EvidenceBundleResult:
    status: str
    path: Path | None = None
    bundle: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def generate_nextlens_evidence_bundle(
    docs_path: str | Path,
    *,
    packet: Mapping[str, Any],
    artifact_refs: Mapping[str, Any] | None = None,
    stage_outcomes: Mapping[str, str] | None = None,
    now_factory: Callable[[], datetime] | None = None,
    replace_fn: Callable[[str, str], None] | None = None,
) -> EvidenceBundleResult:
    try:
        yaml_module = _require_yaml()
        bundle = build_nextlens_evidence_bundle(
            packet=packet,
            artifact_refs=artifact_refs,
            stage_outcomes=stage_outcomes,
            now_factory=now_factory,
        )
        output_path = Path(str(packet.get("evidenceBundleRef") or "")).expanduser()
        if not output_path.is_absolute():
            output_path = Path(docs_path) / output_path
        _atomic_write_yaml(output_path, bundle, yaml_module, replace_fn=replace_fn)
        return EvidenceBundleResult(status="pass", path=output_path, bundle=bundle)
    except Exception as exc:
        return EvidenceBundleResult(status="fail", error=str(exc))


def build_nextlens_evidence_bundle(
    *,
    packet: Mapping[str, Any],
    artifact_refs: Mapping[str, Any] | None = None,
    stage_outcomes: Mapping[str, str] | None = None,
    now_factory: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    refs = dict(artifact_refs or {})
    outcomes = dict(NEXTLENS_STAGE_OUTCOME_DEFAULTS)
    outcomes.update({str(key): str(value) for key, value in dict(stage_outcomes or {}).items()})
    packet_id = str(packet.get("packetId") or "")
    feature_id = str(packet.get("featureId") or "")
    derived_graph_ref = refs.get("derivedGraphRef") or packet.get("derivedGraphRef")
    return {
        "evidence_bundle": {
            "schemaVersion": NEXTLENS_EVIDENCE_BUNDLE_SCHEMA_VERSION,
            "runId": str(refs.get("runId") or "run.001"),
            "packetId": packet_id,
            "featureId": feature_id,
            "inputAnalysisRef": str(refs.get("inputAnalysisRef") or "artifacts/input-analysis.json"),
            "extractedConceptsRef": str(refs.get("extractedConceptsRef") or "artifacts/extracted-concepts.json"),
            "topDownContextRef": str(refs.get("topDownContextRef") or "artifacts/top-down-context.yaml"),
            "contextSufficiencyRef": str(refs.get("contextSufficiencyRef") or "artifacts/context-sufficiency.json"),
            "rankingTraceRef": str(refs.get("rankingTraceRef") or "artifacts/ranking-trace.json"),
            "doctorReportRef": str(refs.get("doctorReportRef") or "artifacts/doctor-report.jsonl"),
            "salmonRoutingRef": str(refs.get("salmonRoutingRef") or "artifacts/salmon-routing.json"),
            "idempotencyDecisionRef": str(refs.get("idempotencyDecisionRef") or "artifacts/idempotency.json"),
            "bmadHandoffRefs": _string_mapping(refs.get("bmadHandoffRefs")),
            "bmadArtifactBundleRef": _string_or_none(refs.get("bmadArtifactBundleRef")),
            "implementationEvidenceRef": _string_or_none(refs.get("implementationEvidenceRef")),
            "validationResultRef": _string_or_none(refs.get("validationResultRef")),
            "salmonSignalRefs": _string_list(refs.get("salmonSignalRefs")),
            "landscapeUpdateRef": _string_or_none(refs.get("landscapeUpdateRef")),
            "derivedGraphRef": _string_or_none(derived_graph_ref),
            "stageOutcomes": outcomes,
            "createdAt": _utc_timestamp(now_factory),
        }
    }


def evidence_bundle_path(docs_path: str | Path, *, run_id: str, packet_id: str | None = None) -> Path:
    identifier = str(packet_id or run_id or "").strip()
    if not identifier:
        raise ValueError("packet_id or run_id is required to determine evidence bundle path.")
    return Path(docs_path) / ".nextlens" / f"evidence-{identifier}.yaml"


def generate_evidence_bundle(
    docs_path: str | Path,
    manifest: Mapping[str, Any],
    *,
    packet_id: str | None = None,
    artifact_refs: Mapping[str, Any] | None = None,
    now_factory: Callable[[], datetime] | None = None,
    replace_fn: Callable[[str, str], None] | None = None,
) -> EvidenceBundleResult:
    try:
        yaml_module = _require_yaml()
        run_id = str(manifest.get("run_id") or "").strip()
        output_path = evidence_bundle_path(docs_path, run_id=run_id, packet_id=packet_id)
        bundle = build_evidence_bundle(
            docs_path,
            manifest,
            packet_id=packet_id,
            artifact_refs=artifact_refs,
            evidence_bundle_ref=str(output_path),
            now_factory=now_factory,
        )
        _atomic_write_yaml(output_path, bundle, yaml_module, replace_fn=replace_fn)
        return EvidenceBundleResult(status="pass", path=output_path, bundle=bundle)
    except Exception as exc:
        return EvidenceBundleResult(status="fail", error=str(exc))


def build_evidence_bundle(
    docs_path: str | Path,
    manifest: Mapping[str, Any],
    *,
    packet_id: str | None = None,
    artifact_refs: Mapping[str, Any] | None = None,
    evidence_bundle_ref: str | None = None,
    now_factory: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    docs_root = Path(docs_path)
    collection_points = _mapping(manifest.get("collection_points"))
    run_id = str(manifest.get("run_id") or "")
    completed_at = str(manifest.get("completed_at") or _utc_timestamp(now_factory))
    started_at = str(manifest.get("started_at") or completed_at)
    return {
        "run": {
            "run_id": run_id,
            "packet_id": packet_id,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_seconds": manifest.get("duration_seconds", _duration_seconds(started_at, completed_at)),
        },
        "stage_records": list(_sequence(manifest.get("stage_records"))),
        "records": {
            "context_intake": _latest_payload(collection_points, "context_intake_and_parsing"),
            "context_sufficiency": _latest_payload(collection_points, "context_sufficiency_check"),
            "landscape_state": _latest_payload(collection_points, "landscape_state_reconstruction"),
            "feature_ranking": _latest_payload(collection_points, "feature_ranking_and_tie_break"),
            "doctor_validation": _latest_payload(collection_points, "doctor_validation_results"),
            "graph_consistency": _latest_payload(collection_points, "graph_consistency_check"),
            "packet_emission": _latest_payload(collection_points, "packet_emission_result"),
            "salmon_routing": _latest_payload(collection_points, "salmon_routing_results"),
        },
        "artifacts": _artifact_payload(
            docs_root,
            packet_id=packet_id,
            artifact_refs=artifact_refs or {},
            evidence_bundle_ref=evidence_bundle_ref,
        ),
        "operator_confirmations": [
            dict(record.get("payload") or {})
            for record in _sequence(collection_points.get("operator_confirmations"))
        ],
        "errors_and_warnings": {
            "errors": list(_sequence(manifest.get("errors"))),
            "warnings": list(_sequence(manifest.get("warnings"))),
            "exception_traces": [
                dict(record.get("payload") or {})
                for record in _sequence(collection_points.get("errors_and_exceptions"))
            ],
        },
        "manifest": {
            "stage_count": manifest.get("stage_count", len(_sequence(manifest.get("stage_records")))),
            "status_counts": dict(_mapping(manifest.get("status_counts"))),
            "collection_points_present": list(_sequence(manifest.get("collection_points_present"))),
        },
    }


def _artifact_payload(
    docs_root: Path,
    *,
    packet_id: str | None,
    artifact_refs: Mapping[str, Any],
    evidence_bundle_ref: str | None,
) -> dict[str, str | None]:
    packet_path = artifact_refs.get("packet_json") or artifact_refs.get("packet_path")
    if packet_path is None and packet_id:
        packet_path = docs_root / ".nextlens" / f"packet-{packet_id}.json"
    return {
        "packet_json": _string_or_none(packet_path),
        "doctor_report_jsonl": _string_or_none(artifact_refs.get("doctor_report_jsonl") or artifact_refs.get("doctor_report_path")),
        "evidence_bundle_yaml": evidence_bundle_ref,
        "salmon_events_directory": _string_or_none(artifact_refs.get("salmon_events_directory") or docs_root / ".nextlens" / "salmon"),
        "landscape_state_directory": _string_or_none(artifact_refs.get("landscape_state_directory") or docs_root / "landscape"),
        "derived_graph_json": _string_or_none(artifact_refs.get("derived_graph_json") or docs_root / "derived" / "graph.json"),
    }


def _latest_payload(collection_points: Mapping[str, Any], name: str) -> dict[str, Any]:
    records = _sequence(collection_points.get(name))
    if not records:
        return {}
    latest = records[-1]
    if isinstance(latest, Mapping):
        payload = latest.get("payload", latest)
        if isinstance(payload, Mapping):
            return dict(payload)
    return {}


def _atomic_write_yaml(
    path: Path,
    payload: Mapping[str, Any],
    yaml_module: Any,
    *,
    replace_fn: Callable[[str, str], None] | None = None,
) -> None:
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


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [str(item) for item in value.values() if str(item).strip()]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _string_mapping(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(item) for key, item in value.items() if item is not None}


def _require_yaml():
    if yaml is None:
        raise RuntimeError("PyYAML is required for evidence bundle generation.") from _YAML_IMPORT_ERROR
    return yaml


def _utc_timestamp(now_factory: Callable[[], datetime] | None) -> str:
    now = now_factory() if now_factory else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _duration_seconds(started_at: str, completed_at: str) -> float:
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return max((end - start).total_seconds(), 0.0)
