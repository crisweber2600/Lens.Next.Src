"""Structured run evidence collection for NextLens command execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from typing import Any, Callable, Mapping, Sequence


VALID_STAGE_STATUSES = {"pass", "warning", "fail"}

EVIDENCE_COLLECTION_POINTS = (
    "command_arguments_and_config",
    "context_intake_and_parsing",
    "context_sufficiency_check",
    "landscape_state_reconstruction",
    "feature_ranking_and_tie_break",
    "operator_confirmations",
    "doctor_validation_results",
    "graph_consistency_check",
    "packet_emission_result",
    "salmon_routing_results",
    "errors_and_exceptions",
)


@dataclass
class EvidenceCollector:
    command_arguments: Mapping[str, Any] | None = None
    config: Mapping[str, Any] | None = None
    run_id: str | None = None
    now_factory: Callable[[], datetime] | None = None
    uuid_factory: Callable[[], uuid.UUID | str] | None = None
    started_at: str = field(init=False)
    stage_records: list[dict[str, Any]] = field(default_factory=list, init=False)
    collection_points: dict[str, list[dict[str, Any]]] = field(default_factory=dict, init=False)
    warnings: list[str] = field(default_factory=list, init=False)
    errors: list[dict[str, Any]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        if self.run_id is None:
            generator = self.uuid_factory or uuid.uuid4
            self.run_id = str(generator())
        self.started_at = _utc_timestamp(self.now_factory)
        self.collection_points = {point: [] for point in EVIDENCE_COLLECTION_POINTS}
        self.record_collection_point(
            "command_arguments_and_config",
            {
                "command_arguments": dict(self.command_arguments or {}),
                "config": dict(self.config or {}),
            },
        )

    def run_record(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "stage_records": list(self.stage_records),
        }

    def record_stage(
        self,
        stage_name: str,
        *,
        status: str,
        input_summary: Mapping[str, Any] | None = None,
        output_summary: Mapping[str, Any] | None = None,
        warnings: Sequence[str] = (),
        diagnostics: Sequence[str] = (),
        started_at: datetime | str | None = None,
        ended_at: datetime | str | None = None,
        collection_point: str | None = None,
    ) -> dict[str, Any]:
        normalized_status = status.strip().lower()
        if normalized_status not in VALID_STAGE_STATUSES:
            raise ValueError(f"invalid evidence status '{status}'")

        stage_started_at = _timestamp_value(started_at, self.now_factory)
        stage_ended_at = _timestamp_value(ended_at, self.now_factory)
        record = {
            "stage_name": stage_name,
            "started_at": stage_started_at,
            "ended_at": stage_ended_at,
            "status": normalized_status,
            "input_summary": dict(input_summary or {}),
            "output_summary": dict(output_summary or {}),
            "duration_seconds": _duration_seconds(stage_started_at, stage_ended_at),
            "warnings": list(warnings),
            "diagnostics": list(diagnostics),
        }
        self.stage_records.append(record)
        self.warnings.extend(str(warning) for warning in warnings)
        if collection_point:
            self.record_collection_point(collection_point, record)
        return record

    def record_collection_point(self, name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if name not in self.collection_points:
            raise ValueError(f"unknown evidence collection point '{name}'")
        record = {
            "timestamp": _utc_timestamp(self.now_factory),
            "payload": dict(payload),
        }
        self.collection_points[name].append(record)
        return record

    def record_error(
        self,
        error: BaseException | str,
        *,
        stage_name: str | None = None,
        diagnostics: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        error_record = {
            "timestamp": _utc_timestamp(self.now_factory),
            "stage_name": stage_name,
            "error_type": type(error).__name__ if isinstance(error, BaseException) else "Error",
            "message": str(error),
            "diagnostics": dict(diagnostics or {}),
        }
        self.errors.append(error_record)
        self.record_collection_point("errors_and_exceptions", error_record)
        return error_record

    def build_manifest(self, *, completed_at: datetime | str | None = None) -> dict[str, Any]:
        completed_timestamp = _timestamp_value(completed_at, self.now_factory)
        status_counts = {status: 0 for status in sorted(VALID_STAGE_STATUSES)}
        for record in self.stage_records:
            status_counts[record["status"]] += 1
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": completed_timestamp,
            "duration_seconds": _duration_seconds(self.started_at, completed_timestamp),
            "stage_count": len(self.stage_records),
            "stage_records": list(self.stage_records),
            "status_counts": status_counts,
            "collection_points": dict(self.collection_points),
            "collection_points_present": [
                name for name, records in self.collection_points.items() if records
            ],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "available_for_bundle_assembly": True,
        }


def _timestamp_value(value: datetime | str | None, now_factory: Callable[[], datetime] | None) -> str:
    if value is None:
        return _utc_timestamp(now_factory)
    if isinstance(value, datetime):
        return _format_timestamp(value)
    return str(value)


def _utc_timestamp(now_factory: Callable[[], datetime] | None) -> str:
    now = now_factory() if now_factory else datetime.now(timezone.utc)
    return _format_timestamp(now)


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _duration_seconds(started_at: str, ended_at: str) -> float:
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return max((end - start).total_seconds(), 0.0)