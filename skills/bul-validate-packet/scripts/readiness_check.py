#!/usr/bin/env python3
"""BMAD readiness checks for Bottom-Up LENS packets.

Readiness is intentionally separate from packet validity.  A packet can be valid
archive evidence while still not ready for BMAD execution.
"""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover - import fallback for direct script execution
    from validation_contract import BMAD_NOT_READY_LABEL, BMAD_READY_LABEL, make_error
except ImportError:  # pragma: no cover
    from .validation_contract import BMAD_NOT_READY_LABEL, BMAD_READY_LABEL, make_error

READINESS_RULES = [
    "acceptance-criteria-quality",
    "constraints-quality",
    "actor-clarity",
    "provenance-sufficiency",
    "anti-inference-handoff",
    "handoff-context",
]


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and any(item not in (None, "", [], {}) for item in value)


def _acceptance_text(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        if _non_empty_string(item.get("text")):
            return item["text"]
        given = item.get("given") or item.get("Given")
        when = item.get("when") or item.get("When")
        then = item.get("then") or item.get("Then")
        return " ".join(str(part) for part in (given, when, then) if part)
    return str(item)


def _has_gwt(text: str) -> bool:
    lowered = text.lower()
    return "given" in lowered and "when" in lowered and "then" in lowered


def _reason(code: str, field: str, message: str, recommendation: str) -> dict[str, str]:
    return make_error(code, field, message, recommendation)


def check_bmad_readiness(packet: dict[str, Any]) -> dict[str, Any]:
    reasons: list[dict[str, str]] = []

    acceptance = packet.get("acceptanceCriteria")
    if not _non_empty_list(acceptance):
        reasons.append(
            _reason(
                "readinessMissingAcceptanceCriteria",
                "acceptanceCriteria",
                "BMAD readiness requires acceptance criteria.",
                "Add concrete Given/When/Then acceptance criteria before BMAD handoff.",
            )
        )
    else:
        weak_indices = [index for index, item in enumerate(acceptance) if not _has_gwt(_acceptance_text(item))]
        if weak_indices:
            reasons.append(
                _reason(
                    "readinessWeakAcceptanceCriteria",
                    "acceptanceCriteria",
                    "Every acceptance criterion should be expressed with Given/When/Then behavior.",
                    "Rewrite weak acceptance criteria into Given/When/Then statements before BMAD handoff.",
                )
            )

    constraints = packet.get("constraints")
    if not _non_empty_list(constraints) or len(constraints) < 2:
        reasons.append(
            _reason(
                "readinessWeakConstraints",
                "constraints",
                "BMAD readiness needs enough implementation constraints to prevent overreach.",
                "Provide concrete constraints plus anti-inference handoff instructions.",
            )
        )

    identity = packet.get("identity") if isinstance(packet.get("identity"), dict) else {}
    if not _non_empty_string(identity.get("actor")):
        reasons.append(
            _reason(
                "readinessActorMissing",
                "identity.actor",
                "Actor clarity is required for BMAD handoff.",
                "Name the actor or user role that receives the useful outcome.",
            )
        )

    handoff = packet.get("handoff") if isinstance(packet.get("handoff"), dict) else {}
    if not _non_empty_string(handoff.get("implementationContext")):
        reasons.append(
            _reason(
                "readinessMissingHandoffContext",
                "handoff.implementationContext",
                "Implementation handoff context is missing.",
                "Summarize the implementation context, target surfaces, and known exclusions for BMAD.",
            )
        )

    provenance = packet.get("provenance") if isinstance(packet.get("provenance"), dict) else {}
    if not _non_empty_list(provenance.get("inputRefs")) or provenance.get("explicitInputsOnly") is not True:
        reasons.append(
            _reason(
                "readinessWeakProvenance",
                "provenance",
                "Provenance is insufficient for BMAD handoff.",
                "Record explicit local context references and avoid ambient inference.",
            )
        )

    joined_handoff = "\n".join(str(value).lower() for value in [handoff.get("antiInferenceInstructions"), *(constraints or [])])
    if not ("branch" in joined_handoff and "editor" in joined_handoff and ("cwd" in joined_handoff or "current working directory" in joined_handoff)):
        reasons.append(
            _reason(
                "readinessMissingAntiInferenceHandoff",
                "handoff.antiInferenceInstructions",
                "BMAD handoff must explicitly reject branch, editor, and cwd inference.",
                "Add handoff instructions that tell downstream agents to use only packet fields and explicit inputs.",
            )
        )

    status = "pass" if not reasons else "fail"
    return {
        "status": status,
        "label": BMAD_READY_LABEL if status == "pass" else BMAD_NOT_READY_LABEL,
        "rulesEvaluated": READINESS_RULES,
        "reasons": reasons,
    }
