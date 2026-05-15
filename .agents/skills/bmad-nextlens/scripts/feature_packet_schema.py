"""Validation contract for canonical NextLens Feature packets."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence
import uuid


FEATURE_PACKET_SCHEMA_VERSION = "nextlens.feature-packet.v1"
FEATURE_PACKET_SOURCE_MODE = "top_down"


@dataclass(frozen=True)
class FeaturePacketValidationError:
    field: str
    expected_type: str
    actual_value: Any = None
    message: str = ""

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "field": self.field,
            "expectedType": self.expected_type,
            "message": self.message or f"{self.field} must be {self.expected_type}.",
        }
        if self.actual_value is not None:
            payload["actualValue"] = self.actual_value
        return payload


@dataclass(frozen=True)
class FeaturePacketValidationResult:
    status: str
    errors: tuple[FeaturePacketValidationError, ...] = field(default_factory=tuple)

    @property
    def is_valid(self) -> bool:
        return self.status == "pass" and not self.errors

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "errors": [error.to_payload() for error in self.errors],
        }


def validate_feature_packet_schema(
    packet: Mapping[str, Any],
    *,
    selected_candidate_id: str | None = None,
) -> FeaturePacketValidationResult:
    errors: list[FeaturePacketValidationError] = []
    if not isinstance(packet, Mapping):
        return FeaturePacketValidationResult(
            status="fail",
            errors=(
                FeaturePacketValidationError(
                    field="packet",
                    expected_type="object",
                    actual_value=packet,
                    message="Feature packet must be an object.",
                ),
            ),
        )

    _require_string(packet, "schemaVersion", errors, expected_value=FEATURE_PACKET_SCHEMA_VERSION)
    _require_uuid(packet, "packetId", errors)
    _require_string(packet, "featureId", errors)
    _require_string(packet, "sourceMode", errors, expected_value=FEATURE_PACKET_SOURCE_MODE)
    _require_object(packet, "selectedFeature", errors)
    _require_object(packet, "trace", errors)
    _require_object(packet, "selectionRationale", errors)
    _require_array(packet, "sourceContextRefs", errors)
    _require_string(packet, "authoritativeStateRef", errors)
    _require_string(packet, "derivedGraphRef", errors)
    _require_object(packet, "doctorSummary", errors)
    _require_object(packet, "salmonRoutingSummary", errors)
    _require_object(packet, "bmadConsumerHints", errors)
    _require_string(packet, "evidenceBundleRef", errors)
    _require_timestamp(packet, "createdAt", errors)

    if selected_candidate_id is not None and packet.get("featureId") != selected_candidate_id:
        errors.append(
            FeaturePacketValidationError(
                field="featureId",
                expected_type=f"selected candidate id '{selected_candidate_id}'",
                actual_value=packet.get("featureId"),
                message="featureId must reference exactly one selected candidate.",
            )
        )

    selected_feature = _mapping_value(packet, "selectedFeature")
    _require_string(selected_feature, "selectedFeature.id", errors)
    _require_string(selected_feature, "selectedFeature.name", errors)
    _require_string(selected_feature, "selectedFeature.goal", errors)
    _require_array(selected_feature, "selectedFeature.includedScope", errors)
    _require_array(selected_feature, "selectedFeature.explicitOutOfScope", errors)

    trace = _mapping_value(packet, "trace")
    _require_string(trace, "trace.systemId", errors)
    _require_string(trace, "trace.discoveryEpochId", errors)
    _require_array(trace, "trace.roleIds", errors)
    _require_array(trace, "trace.outcomeIds", errors)
    _require_array(trace, "trace.journeyIds", errors)
    _require_array(trace, "trace.operatingLoopIds", errors)
    _require_array(trace, "trace.relationshipRefs", errors)

    rationale = _mapping_value(packet, "selectionRationale")
    _require_number(rationale, "selectionRationale.score", errors)
    _require_object(rationale, "selectionRationale.tieBreakEvidence", errors)
    _require_string(rationale, "selectionRationale.whyThisFeature", errors)
    _require_string(rationale, "selectionRationale.whyNow", errors)
    _require_array(rationale, "selectionRationale.rejectedAlternates", errors)

    hints = _mapping_value(packet, "bmadConsumerHints")
    for hint_field in ("prdInput", "uxInput", "architectureInput", "epicStoryInput", "readinessInput"):
        _require_string(hints, f"bmadConsumerHints.{hint_field}", errors)

    return FeaturePacketValidationResult(
        status="fail" if errors else "pass",
        errors=tuple(errors),
    )


def _mapping_value(payload: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    value = payload.get(_leaf_name(field_name))
    if isinstance(value, Mapping):
        return value
    return {}


def _require_string(
    payload: Mapping[str, Any],
    field_name: str,
    errors: list[FeaturePacketValidationError],
    *,
    expected_value: str | None = None,
) -> None:
    value = payload.get(_leaf_name(field_name))
    if not isinstance(value, str) or not value.strip():
        _append_error(payload, field_name, "string", errors)
        return
    if expected_value is not None and value != expected_value:
        errors.append(
            FeaturePacketValidationError(
                field=field_name,
                expected_type=f"string '{expected_value}'",
                actual_value=value,
                message=f"{field_name} must equal '{expected_value}'.",
            )
        )


def _require_uuid(
    payload: Mapping[str, Any],
    field_name: str,
    errors: list[FeaturePacketValidationError],
) -> None:
    value = payload.get(_leaf_name(field_name))
    if not isinstance(value, str) or not value.strip():
        _append_error(payload, field_name, "UUID string", errors)
        return
    try:
        uuid.UUID(value)
    except ValueError:
        errors.append(
            FeaturePacketValidationError(
                field=field_name,
                expected_type="UUID string",
                actual_value=value,
                message=f"{field_name} must be a valid UUID string.",
            )
        )


def _require_timestamp(
    payload: Mapping[str, Any],
    field_name: str,
    errors: list[FeaturePacketValidationError],
) -> None:
    value = payload.get(_leaf_name(field_name))
    if not isinstance(value, str) or not value.strip():
        _append_error(payload, field_name, "ISO 8601 timestamp string", errors)
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(
            FeaturePacketValidationError(
                field=field_name,
                expected_type="ISO 8601 timestamp string",
                actual_value=value,
                message=f"{field_name} must be a valid ISO 8601 timestamp string.",
            )
        )


def _require_array(
    payload: Mapping[str, Any],
    field_name: str,
    errors: list[FeaturePacketValidationError],
) -> None:
    value = payload.get(_leaf_name(field_name))
    if not isinstance(value, list):
        _append_error(payload, field_name, "array", errors)


def _require_object(
    payload: Mapping[str, Any],
    field_name: str,
    errors: list[FeaturePacketValidationError],
) -> None:
    value = payload.get(_leaf_name(field_name))
    if not isinstance(value, Mapping):
        _append_error(payload, field_name, "object", errors)


def _require_number(
    payload: Mapping[str, Any],
    field_name: str,
    errors: list[FeaturePacketValidationError],
) -> None:
    value = payload.get(_leaf_name(field_name))
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        _append_error(payload, field_name, "number", errors)


def _append_error(
    payload: Mapping[str, Any],
    field_name: str,
    expected_type: str,
    errors: list[FeaturePacketValidationError],
) -> None:
    leaf_name = _leaf_name(field_name)
    actual_value = payload.get(leaf_name)
    if leaf_name not in payload:
        message = f"{field_name} is required and must be {expected_type}."
    else:
        message = f"{field_name} must be {expected_type}; got {type(actual_value).__name__}."
    errors.append(
        FeaturePacketValidationError(
            field=field_name,
            expected_type=expected_type,
            actual_value=actual_value,
            message=message,
        )
    )


def _leaf_name(field_name: str) -> str:
    return field_name.rsplit(".", 1)[-1]