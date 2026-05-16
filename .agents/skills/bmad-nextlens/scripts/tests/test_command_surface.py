from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "command_surface.py"
SPEC = importlib.util.spec_from_file_location("bmad_nextlens_command_surface", SCRIPT_PATH)
COMMAND_SURFACE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = COMMAND_SURFACE
SPEC.loader.exec_module(COMMAND_SURFACE)


def test_parse_new_action_from_module_options() -> None:
    parsed = COMMAND_SURFACE.parse_module_action(
        "new",
        {
            "context_source": "path/to/context.yaml",
            "docs_path": "/custom/path",
        },
    )

    assert parsed.mode == "new"
    assert parsed.context_source == "path/to/context.yaml"
    assert parsed.packet_source is None
    assert parsed.findings_source is None
    assert parsed.overrides == {"docs_path": "/custom/path"}


def test_parse_doctor_action_from_story_command() -> None:
    parsed = COMMAND_SURFACE.parse_story_command("nextlens doctor --packet path/to/packet.json")

    assert parsed.mode == "doctor"
    assert parsed.packet_source == "path/to/packet.json"
    assert parsed.context_source is None
    assert parsed.findings_source is None


def test_parse_salmon_action_from_story_command() -> None:
    parsed = COMMAND_SURFACE.parse_story_command("nextlens salmon --findings path/to/findings.jsonl")

    assert parsed.mode == "salmon"
    assert parsed.findings_source == "path/to/findings.jsonl"
    assert parsed.context_source is None
    assert parsed.packet_source is None


def test_parse_validate_action_from_story_command_with_required_args() -> None:
    parsed = COMMAND_SURFACE.parse_story_command(
        "nextlens validate --packet path/to/packet.json "
        "--bmad-artifacts path/to/bmad-bundle.json "
        "--implementation-evidence path/to/evidence.json"
    )

    assert parsed.mode == "validate"
    assert parsed.packet_source == "path/to/packet.json"
    assert parsed.bmad_artifacts_source == "path/to/bmad-bundle.json"
    assert parsed.implementation_evidence_source == "path/to/evidence.json"
    assert parsed.findings_source is None


def test_parse_validate_action_accepts_docs_path_and_landscape_options() -> None:
    parsed = COMMAND_SURFACE.parse_story_command(
        "nextlens validate --packet packet.json "
        "--implementation-evidence evidence.json "
        "--docs-path docs "
        "--landscape-update-source landscape-updates.json "
        "--landscape-update-mode propose"
    )

    assert parsed.mode == "validate"
    assert parsed.packet_source == "packet.json"
    assert parsed.implementation_evidence_source == "evidence.json"
    assert parsed.landscape_update_source == "landscape-updates.json"
    assert parsed.landscape_update_mode == "propose"
    assert parsed.overrides == {"docs_path": "docs"}


def test_help_action_returns_help_mode() -> None:
    parsed = COMMAND_SURFACE.parse_story_command("nextlens --help")

    assert parsed.mode == "help"
    help_text = COMMAND_SURFACE.build_help_text()
    assert "NextLens BMAD module actions:" in help_text
    assert "nextlens setup" in help_text
    assert "nextlens new --context path/to/context.yaml" in help_text
    assert "validate --packet <path> --implementation-evidence <path>" in help_text
    assert "--landscape-update-mode propose|apply" in help_text
    assert "proposal-only by default" in help_text
    assert "post-BMAD validation" in help_text
    assert "not Doctor" in help_text


def test_setup_action_returns_setup_mode() -> None:
    assert COMMAND_SURFACE.parse_module_action("configure").mode == "setup"
    assert COMMAND_SURFACE.parse_story_command("nextlens setup").mode == "setup"


def test_invalid_arguments_include_help_text() -> None:
    with pytest.raises(COMMAND_SURFACE.CommandSurfaceError) as exc_info:
        COMMAND_SURFACE.parse_story_command("nextlens new --docs-path /custom/path")

    assert "Missing required argument 'context_source'" in str(exc_info.value)
    assert "nextlens new --context path/to/context.yaml" in exc_info.value.help_text


def test_validate_action_rejects_missing_packet() -> None:
    with pytest.raises(COMMAND_SURFACE.CommandSurfaceError) as exc_info:
        COMMAND_SURFACE.parse_story_command(
            "nextlens validate --implementation-evidence path/to/evidence.json"
        )

    assert "Missing required argument 'packet_source'" in str(exc_info.value)
    assert "--packet and --implementation-evidence" in str(exc_info.value)


def test_validate_action_rejects_missing_implementation_evidence() -> None:
    with pytest.raises(COMMAND_SURFACE.CommandSurfaceError) as exc_info:
        COMMAND_SURFACE.parse_story_command("nextlens validate --packet path/to/packet.json")

    assert "Missing required argument 'implementation_evidence_source'" in str(exc_info.value)
    assert "--packet and --implementation-evidence" in str(exc_info.value)


def test_module_help_registers_nextlens_actions() -> None:
    module_help = Path(__file__).resolve().parents[3] / "bmad-nextlens-setup" / "assets" / "module-help.csv"
    text = module_help.read_text(encoding="utf-8")

    assert "module,skill,display-name,menu-code,description,action,args,phase,after,before,required,output-location,outputs" in text
    assert "Setup NextLens,SN" in text
    assert "Create Feature Packet,NF" in text
    assert "Run Doctor Checks,ND" in text
    assert "Route Salmon Findings,NS" in text
    assert "Run Post-BMAD Validation,NV" in text
    assert "post-BMAD validation" in text