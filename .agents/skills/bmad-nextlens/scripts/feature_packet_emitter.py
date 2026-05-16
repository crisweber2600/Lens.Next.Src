"""Atomic Feature packet emission for NextLens."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Callable, Mapping


PACKET_OUTPUT_DIR = ".nextlens"
PACKET_NAME_TEMPLATE = "packet-{packet_id}.json"
PACKET_FILE_MODE = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP


@dataclass(frozen=True)
class FeaturePacketEmissionResult:
    status: str
    packet_path: Path | None = None
    output_lines: tuple[str, ...] = field(default_factory=tuple)
    evidence_event: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    rollback_guidance: str | None = None
    packet_emitted: bool = False


def packet_output_path(docs_path: str | Path, packet_id: str) -> Path:
    if not str(packet_id or "").strip():
        raise ValueError("packetId is required to determine packet output path.")
    return Path(docs_path) / PACKET_OUTPUT_DIR / PACKET_NAME_TEMPLATE.format(packet_id=packet_id)


def emit_feature_packet(
    packet: Mapping[str, Any],
    docs_path: str | Path,
    *,
    now_factory: Callable[[], datetime] | None = None,
    replace_fn: Callable[[str, str], None] | None = None,
) -> FeaturePacketEmissionResult:
    """Emit Feature packet to configured output location.
    
    After successful emission, the next steps are:
    1. Optionally run NextLens Doctor for non-mutating packet health validation
    2. Delegate Feature development to normal top-down BMAD planning and implementation:
       - Clarify feature intent and boundaries
       - Create PRD-level specifications
       - Define architectural implications
       - Generate stories and acceptance criteria
       - Prepare execution handoff
       - Capture implementation evidence
    3. After BMAD implementation evidence exists, run NextLens Validate to generate
       validation results, route Salmon when needed, prepare Landscape proposal/apply
       output, and update the evidence-bundle.
    
    This stage does NOT complete the planning flow. It is the beginning of
    the Feature packet lifecycle, not the end.
    """
    packet_id = str(packet.get("packetId") or "").strip()
    try:
        output_path = packet_output_path(docs_path, packet_id)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = _write_temp_packet(output_path.parent, packet_id, packet)
        active_replace = replace_fn or os.replace
        try:
            active_replace(str(temp_path), str(output_path))
            os.chmod(output_path, PACKET_FILE_MODE)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

        written_at = _utc_timestamp(now_factory)
        return FeaturePacketEmissionResult(
            status="pass",
            packet_path=output_path,
            output_lines=(
                f"Packet emitted to: {output_path}",
                "Next steps:",
                "1. Optional health check: run /bmad-nextlens-doctor for non-mutating packet validation.",
                "2. Delegate Feature development to BMAD planning/implementation.",
                "3. After BMAD implementation evidence exists, run /bmad-nextlens-validate.",
                "4. Validate creates a validation result, routes Salmon if needed, prepares Landscape proposal/apply output, and updates the evidence-bundle.",
            ),
            evidence_event={
                "stage": "emit-packet",
                "status": "pass",
                "packetId": packet_id,
                "packetPath": str(output_path),
                "writtenAt": written_at,
            },
            packet_emitted=True,
        )
    except Exception as exc:
        return FeaturePacketEmissionResult(
            status="fail",
            packet_path=None,
            output_lines=(
                f"Packet emission failed: {exc}",
                "Rollback guidance: remove any packet temp files in .nextlens and rerun emission after fixing the write error.",
            ),
            evidence_event={
                "stage": "emit-packet",
                "status": "fail",
                "packetId": packet_id or None,
                "error": str(exc),
                "failedAt": _utc_timestamp(now_factory),
            },
            error=str(exc),
            rollback_guidance="Remove packet temp files in .nextlens, verify permissions, and retry emission.",
            packet_emitted=False,
        )


def _write_temp_packet(output_dir: Path, packet_id: str, packet: Mapping[str, Any]) -> Path:
    fd, temp_name = tempfile.mkstemp(
        dir=str(output_dir),
        prefix=f"packet-{packet_id}-",
        suffix=".tmp",
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(dict(packet), handle, indent=2, sort_keys=True)
            handle.write("\n")
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
    return temp_path


def _utc_timestamp(now_factory: Callable[[], datetime] | None) -> str:
    now = now_factory() if now_factory else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")