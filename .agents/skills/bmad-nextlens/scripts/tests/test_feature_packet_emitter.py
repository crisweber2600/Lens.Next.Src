from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import stat
import sys


MODULE_PATH = Path(__file__).resolve().parent.parent / "feature_packet_emitter.py"
SPEC = importlib.util.spec_from_file_location("nextlens_feature_packet_emitter", MODULE_PATH)
FEATURE_PACKET_EMITTER = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = FEATURE_PACKET_EMITTER
SPEC.loader.exec_module(FEATURE_PACKET_EMITTER)


def test_emit_feature_packet_creates_nextlens_dir_and_writes_indented_json(tmp_path: Path) -> None:
    packet = _packet()

    result = FEATURE_PACKET_EMITTER.emit_feature_packet(
        packet,
        tmp_path,
        now_factory=lambda: datetime(2026, 5, 14, 12, 34, 56, tzinfo=timezone.utc),
    )

    expected_path = tmp_path / ".nextlens" / "packet-550e8400-e29b-41d4-a716-446655440000.json"
    assert result.status == "pass"
    assert result.packet_emitted is True
    assert result.packet_path == expected_path
    assert result.output_lines == (
        f"Packet emitted to: {expected_path}",
        "Next steps:",
        "1. Optional health check: run /bmad-nextlens-doctor for non-mutating packet validation.",
        "2. Delegate Feature development to BMAD planning/implementation.",
        "3. After BMAD implementation evidence exists, run /bmad-nextlens-validate.",
        "4. Validate creates a validation result, routes Salmon if needed, prepares Landscape proposal/apply output, and updates the evidence-bundle.",
    )
    output = "\n".join(result.output_lines)
    assert "/bmad-nextlens-doctor" in output
    assert "non-mutating packet validation" in output
    assert "/bmad-nextlens-validate" in output
    assert "After BMAD implementation evidence exists" in output
    assert "Landscape proposal/apply output" in output
    assert "evidence-bundle" in output
    assert "auto-promotion" not in output
    assert expected_path.exists()
    assert json.loads(expected_path.read_text(encoding="utf-8")) == packet
    assert expected_path.read_text(encoding="utf-8").startswith("{\n  ")
    assert result.evidence_event == {
        "stage": "emit-packet",
        "status": "pass",
        "packetId": "550e8400-e29b-41d4-a716-446655440000",
        "packetPath": str(expected_path),
        "writtenAt": "2026-05-14T12:34:56Z",
    }


def test_packet_output_path_uses_deterministic_packet_filename(tmp_path: Path) -> None:
    path = FEATURE_PACKET_EMITTER.packet_output_path(
        tmp_path,
        "550e8400-e29b-41d4-a716-446655440000",
    )

    assert path == tmp_path / ".nextlens" / "packet-550e8400-e29b-41d4-a716-446655440000.json"


def test_emit_feature_packet_cleans_temp_file_when_atomic_replace_fails(tmp_path: Path) -> None:
    def fail_replace(source: str, target: str) -> None:
        raise PermissionError(f"cannot replace {target}")

    result = FEATURE_PACKET_EMITTER.emit_feature_packet(
        _packet(),
        tmp_path,
        replace_fn=fail_replace,
    )

    assert result.status == "fail"
    assert result.packet_emitted is False
    assert "cannot replace" in result.error
    assert "Rollback guidance" in result.output_lines[1]
    assert not (tmp_path / ".nextlens" / "packet-550e8400-e29b-41d4-a716-446655440000.json").exists()
    assert list((tmp_path / ".nextlens").glob("*.tmp")) == []


def test_emit_feature_packet_sets_member_read_write_permissions(tmp_path: Path) -> None:
    result = FEATURE_PACKET_EMITTER.emit_feature_packet(_packet(), tmp_path)

    mode = result.packet_path.stat().st_mode
    assert mode & stat.S_IRUSR
    assert mode & stat.S_IWUSR
    assert mode & stat.S_IRGRP
    assert mode & stat.S_IWGRP


def _packet() -> dict[str, object]:
    return {
        "packetId": "550e8400-e29b-41d4-a716-446655440000",
        "featureId": "feature-password-recovery",
        "schemaVersion": "nextlens.feature-packet.v1",
        "sourceMode": "top_down",
    }