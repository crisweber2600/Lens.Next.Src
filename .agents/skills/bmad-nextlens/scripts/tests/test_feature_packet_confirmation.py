from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).resolve().parent.parent / "feature_packet_confirmation.py"
SPEC = importlib.util.spec_from_file_location("nextlens_feature_packet_confirmation", MODULE_PATH)
FEATURE_PACKET_CONFIRMATION = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = FEATURE_PACKET_CONFIRMATION
SPEC.loader.exec_module(FEATURE_PACKET_CONFIRMATION)


def test_render_final_confirmation_displays_packet_review_prompt() -> None:
    lines = FEATURE_PACKET_CONFIRMATION.render_final_confirmation(_packet())

    assert lines == (
        "[stage:final-confirmation]",
        "About to emit Feature packet:",
        "- Packet ID: packet-123",
        "- Feature: Password Recovery",
        "- Goal: Restore account access.",
        "- Scope: password reset, self-service recovery",
        "- Out of Scope: admin triage, platform architecture",
        "- Evidence: system=system-nextlens; roles=1; outcomes=1; journeys=1; relationships=1",
        "- Doctor Status: advisory",
        "Emit packet? [Y/n]",
    )


def test_confirm_response_records_evidence_and_proceeds_to_emission() -> None:
    result = FEATURE_PACKET_CONFIRMATION.handle_final_confirmation_response(
        _packet(),
        "Y",
        now_factory=lambda: datetime(2026, 5, 14, 12, 34, 56, tzinfo=timezone.utc),
    )

    assert result.status == "confirmed"
    assert result.proceed_to_emission is True
    assert result.write_permitted is True
    assert result.packet_emitted is False
    assert result.next_action == "continue_to_emission"
    assert result.evidence_event == {
        "stage": "final-confirmation",
        "status": "confirmed",
        "packetId": "packet-123",
        "featureId": "feature-password-recovery",
        "confirmedAt": "2026-05-14T12:34:56Z",
    }


def test_cancel_response_stops_without_writes_or_packet_emission_and_preserves_context() -> None:
    result = FEATURE_PACKET_CONFIRMATION.handle_final_confirmation_response(
        _packet(),
        "n",
        now_factory=lambda: datetime(2026, 5, 14, 12, 34, 56, tzinfo=timezone.utc),
    )

    assert result.status == "cancelled"
    assert result.proceed_to_emission is False
    assert result.write_permitted is False
    assert result.packet_emitted is False
    assert result.next_action == "stop_no_writes"
    assert result.diagnostic_context == {
        "stage": "final-confirmation",
        "packetId": "packet-123",
        "featureId": "feature-password-recovery",
        "reason": "operator_cancelled",
        "resumeFrom": "final-confirmation",
    }


def test_invalid_response_reprompts_without_writes() -> None:
    result = FEATURE_PACKET_CONFIRMATION.handle_final_confirmation_response(_packet(), "maybe")

    assert result.status == "invalid_response"
    assert result.output_lines == ("Please enter Y or n:",)
    assert result.proceed_to_emission is False
    assert result.write_permitted is False
    assert result.next_action == "prompt_again"


def _packet() -> dict[str, object]:
    return {
        "packetId": "packet-123",
        "featureId": "feature-password-recovery",
        "selectedFeature": {
            "name": "Password Recovery",
            "goal": "Restore account access.",
            "includedScope": ["password reset", "self-service recovery"],
            "explicitOutOfScope": ["admin triage", "platform architecture"],
        },
        "trace": {
            "systemId": "system-nextlens",
            "roleIds": ["role-operator"],
            "outcomeIds": ["outcome-reduced-ambiguity"],
            "journeyIds": ["journey-account-recovery"],
            "relationshipRefs": ["system-nextlens->role-operator"],
        },
        "doctorSummary": {"status": "advisory"},
    }