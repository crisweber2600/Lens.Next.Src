"""Persist routed Salmon correction events and run summaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Mapping, Sequence

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover
    yaml = None
    _YAML_IMPORT_ERROR = exc
else:
    _YAML_IMPORT_ERROR = None


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
class SalmonPersistenceResult:
    status: str
    path: Path | None = None
    event: dict[str, Any] = field(default_factory=dict)
    evidence_event: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def persist_salmon_event(
    docs_path: str | Path,
    event: Mapping[str, Any],
    *,
    packet_id: str,
    persisted_by: str = "nextlens",
    now_factory: Callable[[], datetime] | None = None,
    replace_fn: Callable[[str, str], None] | None = None,
) -> SalmonPersistenceResult:
    try:
        yaml_module = _require_yaml()
        fingerprint = str(event.get("dedupFingerprint") or "").strip()
        if not fingerprint:
            raise ValueError("dedupFingerprint is required for Salmon event persistence.")
        output_path = salmon_event_path(docs_path, packet_id, fingerprint)
        persisted_at = _utc_timestamp(now_factory)
        payload = dict(event)
        metadata = {
            "persistedAt": persisted_at,
            "persistedBy": persisted_by,
        }
        metadata["fileChecksum"] = _payload_checksum({**payload, "_metadata": metadata})
        payload["_metadata"] = metadata
        _atomic_write_yaml(output_path, payload, yaml_module, replace_fn=replace_fn)
        return SalmonPersistenceResult(
            status="pass",
            path=output_path,
            event=payload,
            evidence_event={
                "stage": "salmon-persistence",
                "status": "pass",
                "eventCount": 1,
                "routingDecisions": [dict(_mapping(payload.get("routingResult")))],
                "warnings": [],
                "persistedAt": persisted_at,
            },
        )
    except Exception as exc:
        return SalmonPersistenceResult(
            status="fail",
            error=str(exc),
            evidence_event={
                "stage": "salmon-persistence",
                "status": "fail",
                "eventCount": 0,
                "routingDecisions": [],
                "warnings": [str(exc)],
            },
        )


def write_salmon_summary(
    docs_path: str | Path,
    *,
    packet_id: str,
    run_id: str,
    events: Sequence[Mapping[str, Any]],
    replace_fn: Callable[[str, str], None] | None = None,
) -> Path:
    yaml_module = _require_yaml()
    summary = build_salmon_summary(packet_id=packet_id, run_id=run_id, events=events)
    output_path = Path(docs_path) / ".nextlens" / f"salmon-summary-{packet_id}.yaml"
    _atomic_write_yaml(output_path, summary, yaml_module, replace_fn=replace_fn)
    return output_path


def build_salmon_summary(*, packet_id: str, run_id: str, events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    impact_distribution = {impact_level: 0 for impact_level in IMPACT_LEVELS}
    routing_results = {"created": 0, "merged": 0, "ignored": 0}
    for event in events:
        impact_level = str(_mapping(event.get("discovery")).get("impactLevel") or "")
        if impact_level in impact_distribution:
            impact_distribution[impact_level] += 1
        status = str(_mapping(event.get("routingResult")).get("status") or "")
        if status == "duplicate_ignored":
            routing_results["ignored"] += 1
        elif status in routing_results:
            routing_results[status] += 1

    return {
        "run_id": run_id,
        "packet_id": packet_id,
        "events_created": routing_results["created"],
        "events_merged": routing_results["merged"],
        "duplicates_ignored": routing_results["ignored"],
        "impact_distribution": impact_distribution,
        "routing_results": routing_results,
    }


def salmon_event_path(docs_path: str | Path, packet_id: str, fingerprint: str) -> Path:
    return Path(docs_path) / ".nextlens" / "salmon" / packet_id / f"{fingerprint}.yaml"


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


def _payload_checksum(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(dict(payload), sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _require_yaml():
    if yaml is None:
        raise RuntimeError("PyYAML is required for Salmon event persistence.") from _YAML_IMPORT_ERROR
    return yaml


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _utc_timestamp(now_factory: Callable[[], datetime] | None) -> str:
    now = now_factory() if now_factory else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")