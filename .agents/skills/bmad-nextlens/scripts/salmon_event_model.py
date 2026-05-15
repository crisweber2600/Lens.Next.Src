"""Canonical Salmon correction event schema and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Any, Mapping
import uuid


SALMON_EVENT_SCHEMA_VERSION = "1.0"
SALMON_SOURCE_TYPES = frozenset({"human", "doctor", "review", "implementation"})
SALMON_SEVERITIES = frozenset({"blocking", "advisory", "informational"})
SALMON_ACTION_TYPES = frozenset({"local_note", "landscape_update", "block_packet", "correct_course"})
SALMON_ROUTING_STATUSES = frozenset({"created", "merged", "duplicate_ignored"})
SALMON_IMPACT_LEVELS = frozenset(
    {
        "local_feature_note",
        "feature_scope_change",
        "journey_assumption_change",
        "outcome_reframe",
        "role_or_stakeholder_change",
        "operating_loop_change",
        "capability_or_landscape_update",
        "bmad_correct_course_required",
    }
)
SALMON_IMPACTED_NODE_FIELDS = (
    "features",
    "journeys",
    "outcomes",
    "roles",
    "operatingLoops",
    "capabilities",
    "bmadArtifacts",
)
SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SalmonEventValidationError:
    field: str
    expected: str
    actual_value: Any = None
    message: str = ""


@dataclass(frozen=True)
class SalmonEventValidationResult:
    status: str
    errors: tuple[SalmonEventValidationError, ...] = field(default_factory=tuple)

    @property
    def is_valid(self) -> bool:
        return self.status == "pass" and not self.errors


def build_salmon_event_schema() -> dict[str, Any]:
    return {
        "schemaVersion": SALMON_EVENT_SCHEMA_VERSION,
        "required": [
            "schemaVersion",
            "id",
            "raisedFrom",
            "source",
            "discovery",
            "impactedNodes",
            "severity",
            "recommendedAction",
            "dedupFingerprint",
            "createdAt",
            "routingResult",
        ],
        "sourceTypes": sorted(SALMON_SOURCE_TYPES),
        "severities": sorted(SALMON_SEVERITIES),
        "impactLevels": sorted(SALMON_IMPACT_LEVELS),
        "actionTypes": sorted(SALMON_ACTION_TYPES),
        "routingStatuses": sorted(SALMON_ROUTING_STATUSES),
        "impactedNodeFields": list(SALMON_IMPACTED_NODE_FIELDS),
    }


def validate_salmon_event(event: Mapping[str, Any]) -> SalmonEventValidationResult:
    errors: list[SalmonEventValidationError] = []
    if not isinstance(event, Mapping):
        return SalmonEventValidationResult(
            status="fail",
            errors=(SalmonEventValidationError("event", "object", event, "Salmon event must be an object."),),
        )

    _require_string(event, "schemaVersion", errors, expected_value=SALMON_EVENT_SCHEMA_VERSION)
    _require_uuid(event, "id", errors)
    _require_string(event, "raisedFrom", errors)
    _require_enum(event, "severity", SALMON_SEVERITIES, errors)
    _require_sha256(event, "dedupFingerprint", errors)
    _require_timestamp(event, "createdAt", errors)

    source = _require_object(event, "source", errors)
    _require_enum(source, "source.type", SALMON_SOURCE_TYPES, errors)
    _require_string(source, "source.sourceId", errors)

    discovery = _require_object(event, "discovery", errors)
    _require_string(discovery, "discovery.issueDescription", errors, max_length=None)
    _require_string(discovery, "discovery.impactedFeature", errors)
    _require_enum(discovery, "discovery.impactLevel", SALMON_IMPACT_LEVELS, errors)

    impacted_nodes = _require_object(event, "impactedNodes", errors)
    for field_name in SALMON_IMPACTED_NODE_FIELDS:
        _require_array(impacted_nodes, f"impactedNodes.{field_name}", errors)

    action = _require_object(event, "recommendedAction", errors)
    _require_enum(action, "recommendedAction.type", SALMON_ACTION_TYPES, errors)
    _require_string(action, "recommendedAction.details", errors)

    routing = _require_object(event, "routingResult", errors)
    _require_enum(routing, "routingResult.status", SALMON_ROUTING_STATUSES, errors)
    _require_string(routing, "routingResult.targetRef", errors)

    return SalmonEventValidationResult(
        status="fail" if errors else "pass",
        errors=tuple(errors),
    )


def _require_object(payload: Mapping[str, Any], field_name: str, errors: list[SalmonEventValidationError]) -> Mapping[str, Any]:
    value = payload.get(_leaf_name(field_name))
    if isinstance(value, Mapping):
        return value
    _append_error(payload, field_name, "object", errors)
    return {}


def _require_string(
    payload: Mapping[str, Any],
    field_name: str,
    errors: list[SalmonEventValidationError],
    *,
    expected_value: str | None = None,
    max_length: int | None = 1000,
) -> None:
    value = payload.get(_leaf_name(field_name))
    if not isinstance(value, str) or not value.strip():
        _append_error(payload, field_name, "string", errors)
        return
    if max_length is not None and len(value) > max_length:
        errors.append(
            SalmonEventValidationError(
                field=field_name,
                expected=f"string <= {max_length} chars",
                actual_value=value,
                message=f"{field_name} exceeds {max_length} characters.",
            )
        )
    if expected_value is not None and value != expected_value:
        errors.append(
            SalmonEventValidationError(
                field=field_name,
                expected=f"string '{expected_value}'",
                actual_value=value,
                message=f"{field_name} must equal '{expected_value}'.",
            )
        )


def _require_enum(
    payload: Mapping[str, Any],
    field_name: str,
    allowed_values: frozenset[str],
    errors: list[SalmonEventValidationError],
) -> None:
    value = payload.get(_leaf_name(field_name))
    if not isinstance(value, str) or value not in allowed_values:
        errors.append(
            SalmonEventValidationError(
                field=field_name,
                expected="one of " + ", ".join(sorted(allowed_values)),
                actual_value=value,
                message=f"{field_name} must be one of: {', '.join(sorted(allowed_values))}.",
            )
        )


def _require_array(payload: Mapping[str, Any], field_name: str, errors: list[SalmonEventValidationError]) -> None:
    value = payload.get(_leaf_name(field_name))
    if not isinstance(value, list):
        _append_error(payload, field_name, "array", errors)


def _require_uuid(payload: Mapping[str, Any], field_name: str, errors: list[SalmonEventValidationError]) -> None:
    value = payload.get(_leaf_name(field_name))
    if not isinstance(value, str):
        _append_error(payload, field_name, "UUID string", errors)
        return
    try:
        uuid.UUID(value)
    except ValueError:
        errors.append(
            SalmonEventValidationError(field_name, "UUID string", value, f"{field_name} must be a valid UUID string.")
        )


def _require_timestamp(payload: Mapping[str, Any], field_name: str, errors: list[SalmonEventValidationError]) -> None:
    value = payload.get(_leaf_name(field_name))
    if not isinstance(value, str):
        _append_error(payload, field_name, "ISO 8601 timestamp string", errors)
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(
            SalmonEventValidationError(
                field_name,
                "ISO 8601 timestamp string",
                value,
                f"{field_name} must be a valid ISO 8601 timestamp string.",
            )
        )


def _require_sha256(payload: Mapping[str, Any], field_name: str, errors: list[SalmonEventValidationError]) -> None:
    value = payload.get(_leaf_name(field_name))
    if not isinstance(value, str) or SHA256_HEX_PATTERN.fullmatch(value) is None:
        errors.append(
            SalmonEventValidationError(
                field_name,
                "SHA256 hex string",
                value,
                f"{field_name} must be a 64-character lowercase SHA256 hex string.",
            )
        )


def _append_error(
    payload: Mapping[str, Any],
    field_name: str,
    expected: str,
    errors: list[SalmonEventValidationError],
) -> None:
    leaf_name = _leaf_name(field_name)
    actual_value = payload.get(leaf_name)
    message = f"{field_name} is required and must be {expected}." if leaf_name not in payload else f"{field_name} must be {expected}."
    errors.append(SalmonEventValidationError(field_name, expected, actual_value, message))


def _leaf_name(field_name: str) -> str:
    return field_name.rsplit(".", 1)[-1]