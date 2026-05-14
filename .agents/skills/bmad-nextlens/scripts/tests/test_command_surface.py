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


def test_help_action_returns_help_mode() -> None:
    parsed = COMMAND_SURFACE.parse_story_command("nextlens --help")

    assert parsed.mode == "help"
    help_text = COMMAND_SURFACE.build_help_text()
    assert "NextLens BMAD module actions:" in help_text
    assert "nextlens new --context path/to/context.yaml" in help_text


def test_invalid_arguments_include_help_text() -> None:
    with pytest.raises(COMMAND_SURFACE.CommandSurfaceError) as exc_info:
        COMMAND_SURFACE.parse_story_command("nextlens new --docs-path /custom/path")

    assert "Missing required argument 'context_source'" in str(exc_info.value)
    assert "nextlens new --context path/to/context.yaml" in exc_info.value.help_text


def test_module_help_registers_nextlens_actions() -> None:
    module_help = Path(__file__).resolve().parents[2] / "assets" / "module-help.csv"
    text = module_help.read_text(encoding="utf-8")

    assert "NextLens,bmad-nextlens,Create Feature Packet,NN" in text
    assert "NextLens,bmad-nextlens,Run Doctor Checks,ND" in text
    assert "NextLens,bmad-nextlens,Route Salmon Findings,NS" in text
    assert "NextLens,bmad-nextlens,Show NextLens Help,NH" in text