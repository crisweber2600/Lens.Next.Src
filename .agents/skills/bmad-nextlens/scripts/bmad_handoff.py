"""Generate BMAD handoff artifacts for a selected NextLens Feature packet."""

from __future__ import annotations

from dataclasses import dataclass, field
import copy
from pathlib import Path
from typing import Any, Mapping


HANDOFF_DIRNAME = "bmad-handoff"
HANDOFF_FILE_MAP = {
    "prdInput": "prd-input.md",
    "uxInput": "ux-input.md",
    "architectureInput": "architecture-input.md",
    "epicStoryInput": "epic-story-input.md",
    "readinessInput": "readiness-input.md",
}
DEFAULT_SCOPE_CONTAINMENT_WARNING = (
    "This packet represents one selected Feature from top-down discovery. "
    "Do not expand into adjacent journeys, future Features, platform architecture, "
    "or unrelated outcomes unless Salmon or correct-course signals scope change."
)
BMAD_EXPANSION_BOUNDARY = (
    "Build only this selected Feature.",
    "Do not expand into adjacent journeys.",
    "Do not implement future Features.",
    "Do not promote to capability/domain/system.",
    "Do not rewrite system architecture unless explicitly in scope.",
)


@dataclass(frozen=True)
class BmadHandoffResult:
    status: str
    handoff_dir: Path | None = None
    artifact_paths: dict[str, str] = field(default_factory=dict)
    packet: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def generate_bmad_handoff_artifacts(
    docs_path: str | Path,
    packet: Mapping[str, Any],
    *,
    update_packet: bool = True,
) -> BmadHandoffResult:
    try:
        prepared = _prepare_handoff_payload(packet)
        output_dir = _handoff_output_dir(docs_path, prepared["packet_id"])
        output_dir.mkdir(parents=True, exist_ok=True)

        artifact_paths: dict[str, str] = {}
        for hint_key, filename in HANDOFF_FILE_MAP.items():
            content = _render_handoff_markdown(
                hint_key,
                filename,
                prepared,
                seed_input=prepared["seed_inputs"].get(hint_key),
            )
            path = output_dir / filename
            path.write_text(content, encoding="utf-8", newline="\n")
            artifact_paths[hint_key] = str(path)

        updated_packet = _apply_handoff_hints(packet, artifact_paths) if update_packet else dict(packet)
        return BmadHandoffResult(
            status="pass",
            handoff_dir=output_dir,
            artifact_paths=artifact_paths,
            packet=updated_packet,
        )
    except Exception as exc:
        return BmadHandoffResult(status="fail", error=str(exc))


def _handoff_output_dir(docs_path: str | Path, packet_id: str) -> Path:
    if not packet_id:
        raise ValueError("packetId is required to generate BMAD handoff artifacts.")
    return Path(docs_path) / ".nextlens" / HANDOFF_DIRNAME / f"packet-{packet_id}"


def _prepare_handoff_payload(packet: Mapping[str, Any]) -> dict[str, Any]:
    packet_id = str(packet.get("packetId") or "").strip()
    feature_id = str(packet.get("featureId") or "").strip()
    if not packet_id or not feature_id:
        raise ValueError("packetId and featureId are required for BMAD handoff generation.")

    selected_feature = _as_mapping(packet.get("selectedFeature"))
    trace = _as_mapping(packet.get("trace"))
    hints = _as_mapping(packet.get("bmadConsumerHints"))

    return {
        "packet_id": packet_id,
        "feature_id": feature_id,
        "feature_name": str(selected_feature.get("name") or feature_id),
        "feature_goal": str(selected_feature.get("goal") or ""),
        "source_mode": str(packet.get("sourceMode") or "unknown"),
        "system_trace": str(trace.get("systemId") or "unknown"),
        "outcome_trace": _string_list(trace.get("outcomeIds")),
        "journey_trace": _string_list(trace.get("journeyIds")),
        "included_scope": _string_list(selected_feature.get("includedScope")),
        "explicit_out_of_scope": _string_list(selected_feature.get("explicitOutOfScope")),
        "scope_warning": str(
            hints.get("scopeContainmentWarning") or DEFAULT_SCOPE_CONTAINMENT_WARNING
        ),
        "evidence_bundle_ref": str(packet.get("evidenceBundleRef") or ""),
        "seed_inputs": {
            key: str(hints.get(key) or "").strip()
            for key in HANDOFF_FILE_MAP
            if _is_meaningful(hints.get(key))
        },
    }


def _apply_handoff_hints(packet: Mapping[str, Any], artifact_paths: Mapping[str, str]) -> dict[str, Any]:
    updated = copy.deepcopy(dict(packet))
    hints = dict(_as_mapping(updated.get("bmadConsumerHints")))
    for hint_key, path in artifact_paths.items():
        hints[hint_key] = str(path)
    updated["bmadConsumerHints"] = hints
    return updated


def _render_handoff_markdown(
    hint_key: str,
    filename: str,
    payload: Mapping[str, Any],
    *,
    seed_input: str | None = None,
) -> str:
    title = filename.replace("-", " ").replace(".md", "").title()
    lines = [
        f"# BMAD Handoff: {title}",
        "",
        "## Packet Metadata",
        f"- packetId: {payload['packet_id']}",
        f"- featureId: {payload['feature_id']}",
        f"- selectedFeature: {payload['feature_name']}",
        f"- selectedFeatureGoal: {payload['feature_goal']}",
        f"- sourceMode: {payload['source_mode']}",
        "",
        "## Traceability",
        f"- system trace: {payload['system_trace']}",
        f"- outcome trace: {_format_list(payload['outcome_trace'])}",
        f"- journey trace: {_format_list(payload['journey_trace'])}",
        "",
        "## Scope",
        "### Included Scope",
        *_bullet_lines(payload["included_scope"]),
        "",
        "### Explicit Out Of Scope",
        *_bullet_lines(payload["explicit_out_of_scope"]),
        "",
        "## Scope Containment Warning",
        payload["scope_warning"],
        "",
        "## BMAD Expansion Boundary",
        *_bullet_lines(BMAD_EXPANSION_BOUNDARY),
        "",
    ]

    if seed_input:
        lines.extend(
            [
                "## Seed Input",
                seed_input,
                "",
            ]
        )

    lines.extend(
        [
            "## Evidence Bundle",
            f"- evidenceBundleRef: {payload['evidence_bundle_ref']}",
            "",
        ]
    )
    return "\n".join(lines)


def _format_list(values: list[str]) -> str:
    return ", ".join(values) if values else "none"


def _bullet_lines(values: list[str] | tuple[str, ...]) -> list[str]:
    items = [item for item in values if str(item).strip()]
    if not items:
        return ["- none"]
    return [f"- {item}" for item in items]


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _is_meaningful(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_is_meaningful(item) for item in value)
    if isinstance(value, Mapping):
        return bool(value)
    return True
