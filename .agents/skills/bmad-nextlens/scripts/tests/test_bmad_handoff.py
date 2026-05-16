from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).resolve().parent.parent / "bmad_handoff.py"
SPEC = importlib.util.spec_from_file_location("nextlens_bmad_handoff", MODULE_PATH)
BMAD_HANDOFF = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = BMAD_HANDOFF
SPEC.loader.exec_module(BMAD_HANDOFF)


def test_generate_bmad_handoff_artifacts_writes_all_inputs_and_updates_packet(tmp_path: Path) -> None:
    packet = _packet(tmp_path)

    result = BMAD_HANDOFF.generate_bmad_handoff_artifacts(tmp_path, packet, update_packet=True)

    assert result.status == "pass"
    expected_dir = tmp_path / ".nextlens" / "bmad-handoff" / "packet-550e8400-e29b-41d4-a716-446655440000"
    assert result.handoff_dir == expected_dir
    assert expected_dir.exists()

    expected_paths = {
        "prdInput": expected_dir / "prd-input.md",
        "uxInput": expected_dir / "ux-input.md",
        "architectureInput": expected_dir / "architecture-input.md",
        "epicStoryInput": expected_dir / "epic-story-input.md",
        "readinessInput": expected_dir / "readiness-input.md",
    }
    assert result.artifact_paths == {key: str(path) for key, path in expected_paths.items()}

    updated_hints = result.packet["bmadConsumerHints"]
    for hint_key, path in expected_paths.items():
        assert updated_hints[hint_key] == str(path)

    for path in expected_paths.values():
        content = path.read_text(encoding="utf-8")
        assert "packetId: 550e8400-e29b-41d4-a716-446655440000" in content
        assert "featureId: feature-password-recovery" in content
        assert "selectedFeature: Password Recovery" in content
        assert "selectedFeatureGoal: Restore account access without widening scope." in content
        assert "sourceMode: top_down" in content
        assert "system trace: system-nextlens" in content
        assert "outcome trace: outcome-reduced-ambiguity" in content
        assert "journey trace: journey-account-recovery" in content
        assert "- password reset" in content
        assert "- self-service recovery" in content
        assert "- admin triage" in content
        assert "Scope Containment Warning" in content
        assert "Keep scope contained to the selected Feature." in content
        assert "BMAD Expansion Boundary" in content
        assert "Build only this selected Feature." in content
        assert "evidenceBundleRef: docs/.nextlens/evidence-550e8400-e29b-41d4-a716-446655440000.yaml" in content


def _packet(tmp_path: Path) -> dict[str, object]:
    return {
        "packetId": "550e8400-e29b-41d4-a716-446655440000",
        "featureId": "feature-password-recovery",
        "sourceMode": "top_down",
        "selectedFeature": {
            "id": "feature-password-recovery",
            "name": "Password Recovery",
            "goal": "Restore account access without widening scope.",
            "includedScope": ["password reset", "self-service recovery"],
            "explicitOutOfScope": ["admin triage"],
        },
        "trace": {
            "systemId": "system-nextlens",
            "outcomeIds": ["outcome-reduced-ambiguity"],
            "journeyIds": ["journey-account-recovery"],
        },
        "bmadConsumerHints": {
            "scopeContainmentWarning": "Keep scope contained to the selected Feature.",
            "prdInput": "PRD goal and key requirements.",
            "uxInput": "UX patterns and key flows.",
            "architectureInput": "Architecture decisions affecting this Feature.",
            "epicStoryInput": "Epic and story outline.",
            "readinessInput": "Implementation readiness is green.",
        },
        "evidenceBundleRef": "docs/.nextlens/evidence-550e8400-e29b-41d4-a716-446655440000.yaml",
    }
