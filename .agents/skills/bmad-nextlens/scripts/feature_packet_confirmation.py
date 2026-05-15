"""Final operator confirmation gate before Feature packet emission."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


CONFIRMATION_PROMPT = "Emit packet? [Y/n]"
INVALID_CONFIRMATION_PROMPT = "Please enter Y or n:"


@dataclass(frozen=True)
class FeaturePacketConfirmationResult:
    status: str
    proceed_to_emission: bool
    write_permitted: bool
    packet_emitted: bool
    output_lines: tuple[str, ...] = field(default_factory=tuple)
    evidence_event: dict[str, Any] = field(default_factory=dict)
    diagnostic_context: dict[str, Any] = field(default_factory=dict)
    next_action: str | None = None


def render_final_confirmation(packet: Mapping[str, Any]) -> tuple[str, ...]:
    selected_feature = _mapping(packet.get("selectedFeature"))
    doctor_summary = _mapping(packet.get("doctorSummary"))
    trace = _mapping(packet.get("trace"))
    return (
        "[stage:final-confirmation]",
        "About to emit Feature packet:",
        f"- Packet ID: {packet.get('packetId', 'unknown')}",
        f"- Feature: {selected_feature.get('name', 'unknown')}",
        f"- Goal: {selected_feature.get('goal', 'unknown')}",
        f"- Scope: {_summarize_list(selected_feature.get('includedScope'))}",
        f"- Out of Scope: {_summarize_list(selected_feature.get('explicitOutOfScope'))}",
        f"- Evidence: {_traceability_summary(trace)}",
        f"- Doctor Status: {doctor_summary.get('status', 'unknown')}",
        CONFIRMATION_PROMPT,
    )


def handle_final_confirmation_response(
    packet: Mapping[str, Any],
    response: str,
    *,
    now_factory: Any = None,
) -> FeaturePacketConfirmationResult:
    normalized = (response or "").strip().lower()
    if normalized in {"", "y", "yes"}:
        return FeaturePacketConfirmationResult(
            status="confirmed",
            proceed_to_emission=True,
            write_permitted=True,
            packet_emitted=False,
            output_lines=("final_confirmation: confirmed",),
            evidence_event={
                "stage": "final-confirmation",
                "status": "confirmed",
                "packetId": packet.get("packetId"),
                "featureId": packet.get("featureId"),
                "confirmedAt": _utc_timestamp(now_factory),
            },
            next_action="emit_packet",
        )

    if normalized in {"n", "no"}:
        return FeaturePacketConfirmationResult(
            status="cancelled",
            proceed_to_emission=False,
            write_permitted=False,
            packet_emitted=False,
            output_lines=("final_confirmation: cancelled",),
            evidence_event={
                "stage": "final-confirmation",
                "status": "cancelled",
                "packetId": packet.get("packetId"),
                "featureId": packet.get("featureId"),
                "cancelledAt": _utc_timestamp(now_factory),
            },
            diagnostic_context={
                "stage": "final-confirmation",
                "packetId": packet.get("packetId"),
                "featureId": packet.get("featureId"),
                "reason": "operator_cancelled",
                "resumeFrom": "final-confirmation",
            },
            next_action="stop_no_writes",
        )

    return FeaturePacketConfirmationResult(
        status="invalid_response",
        proceed_to_emission=False,
        write_permitted=False,
        packet_emitted=False,
        output_lines=(INVALID_CONFIRMATION_PROMPT,),
        diagnostic_context={
            "stage": "final-confirmation",
            "packetId": packet.get("packetId"),
            "featureId": packet.get("featureId"),
            "reason": "invalid_input",
        },
        next_action="prompt_again",
    )


def _summarize_list(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "none"
    return str(value or "none")


def _traceability_summary(trace: Mapping[str, Any]) -> str:
    return "; ".join(
        (
            f"system={trace.get('systemId', 'unknown')}",
            f"roles={len(_list_value(trace.get('roleIds')))}",
            f"outcomes={len(_list_value(trace.get('outcomeIds')))}",
            f"journeys={len(_list_value(trace.get('journeyIds')))}",
            f"relationships={len(_list_value(trace.get('relationshipRefs')))}",
        )
    )


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _utc_timestamp(now_factory: Any) -> str:
    now = now_factory() if now_factory else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")