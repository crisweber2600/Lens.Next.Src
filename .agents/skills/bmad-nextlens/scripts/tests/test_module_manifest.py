from __future__ import annotations

from pathlib import Path

import yaml


MODULE_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = MODULE_ROOT.parent
MANIFEST_PATH = SKILLS_ROOT / "bmad-nextlens-setup" / "assets" / "module.yaml"
EXPECTED_COMMANDS = {"nextlens-setup", "nextlens-new", "nextlens-doctor", "nextlens-salmon"}
EXPECTED_ACTIONS = {"configure", "new", "doctor", "salmon"}
EXPECTED_SKILLS = {
    "nextlens-setup": "bmad-nextlens-setup",
    "nextlens-new": "bmad-nextlens-new",
    "nextlens-doctor": "bmad-nextlens-doctor",
    "nextlens-salmon": "bmad-nextlens-salmon",
}


def test_module_manifest_identity_fields_are_present() -> None:
    manifest = _manifest()

    assert manifest["code"] == "nxl"
    assert manifest["name"] == "NextLens Top-Down Bridge"
    assert manifest["module_version"] == "1.0.0"
    assert manifest["description"]
    assert manifest["default_selected"] is False
    assert "NextLens is ready" in manifest["module_greeting"]
    assert "separate parts" in manifest["module_greeting"]


def test_module_manifest_declares_expected_capabilities() -> None:
    manifest = _manifest()
    capabilities = {item["command"]: item for item in manifest["capabilities"]}

    assert set(capabilities) == EXPECTED_COMMANDS
    assert {item["action"] for item in capabilities.values()} == EXPECTED_ACTIONS
    assert capabilities["nextlens-setup"]["description"] == "Register or refresh the NextLens BMad module in this project."
    assert capabilities["nextlens-new"]["description"] == "Create one Feature packet from top-down discovery context."
    assert capabilities["nextlens-doctor"]["description"] == "Run non-mutating validation checks on a Feature packet or landscape."
    assert capabilities["nextlens-salmon"]["description"] == "Route correction findings through deduplication and impact classification."
    assert {command: item["skill"] for command, item in capabilities.items()} == EXPECTED_SKILLS
    assert {
        command: item["entry_point"]
        for command, item in capabilities.items()
    } == {
        command: f".agents/skills/{skill}/SKILL.md"
        for command, skill in EXPECTED_SKILLS.items()
    }
    assert all(item["skill_type"] == "workflow" for item in capabilities.values())


def test_module_manifest_declares_bmad_configuration_variables() -> None:
    manifest = _manifest()

    assert manifest["nextlens_docs_path"]["default"] == "{project-root}/docs"
    assert manifest["nextlens_landscape_store"]["default"] == "{project-root}/docs/landscape"
    assert manifest["nextlens_idempotency_ttl_hours"]["type"] == "number"
    assert manifest["nextlens_idempotency_ttl_hours"]["default"] == 24
    assert manifest["directories"] == ["{nextlens_docs_path}", "{nextlens_landscape_store}"]


def _manifest() -> dict[str, object]:
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
