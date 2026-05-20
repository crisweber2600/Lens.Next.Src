from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SCAFFOLD_PATHS = [
    ".claude-plugin/marketplace.json",
    "README.md",
    "LICENSE",
    "skills/bul-setup/SKILL.md",
    "skills/bul-setup/assets/module.yaml",
    "skills/bul-setup/assets/module-help.csv",
    "skills/bul-setup/scripts/merge-config.py",
    "skills/bul-setup/scripts/merge-help-csv.py",
    "skills/bul-setup/scripts/cleanup-legacy.py",
    "skills/bul-create-packet/SKILL.md",
    "skills/bul-create-packet/scripts/validate_scaffold.py",
    "skills/bul-validate-packet/SKILL.md",
    "skills/bul-verify-receipt/SKILL.md",
    "evals/bul-create-packet/evals.json",
    "evals/bul-create-packet/triggers.json",
    "evals/bul-validate-packet/evals.json",
    "evals/bul-verify-receipt/evals.json",
]


FORBIDDEN_RUNTIME_DEPENDENCIES = [
    "lens.core/_bmad/lens-work",
    "feature-yaml-ops.py",
    "publish-to-governance",
    "lens-git-orchestration",
    "lens-constitution",
    "bmad-nextlens/scripts",
]


EXPECTED_SKILLS = [
    "bul-setup",
    "bul-create-packet",
    "bul-validate-packet",
    "bul-verify-receipt",
]


def test_bottom_up_lens_required_scaffold_paths_exist() -> None:
    for relative_path in REQUIRED_SCAFFOLD_PATHS:
        assert (REPO_ROOT / relative_path).exists(), relative_path


def test_bottom_up_lens_marketplace_plugin_lists_existing_skill_paths() -> None:
    manifest = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    plugins = {plugin["name"]: plugin for plugin in manifest["plugins"]}

    assert "nxl" in plugins, "existing top-down plugin must remain registered"
    assert manifest["plugins"] == [plugins["nxl"]], "E1-S4 owns final Bottom-Up LENS marketplace registration"
    for skill in EXPECTED_SKILLS:
        assert (REPO_ROOT / "skills" / skill / "SKILL.md").is_file()


def test_bottom_up_lens_module_yaml_registers_configuration_and_capabilities() -> None:
    module_yaml = yaml.safe_load((REPO_ROOT / "skills" / "bul-setup" / "assets" / "module.yaml").read_text(encoding="utf-8"))

    assert module_yaml["code"] == "bul"
    assert module_yaml["name"] == "Bottom-Up LENS"
    assert module_yaml["module_version"] == "1.0.0"
    assert module_yaml["packet_output_path"]["default"] == "{project-root}/docs/bottom-up-lens"
    assert module_yaml["reports_output_path"]["default"] == "{project-root}/_bmad-output/bottom-up-lens"
    assert module_yaml["default_packet_schema_version"]["default"] == "bul.feature-packet.v1"
    assert [capability["skill"] for capability in module_yaml["capabilities"]] == EXPECTED_SKILLS


def test_bottom_up_lens_module_help_entries_are_complete_and_ordered() -> None:
    with (REPO_ROOT / "skills" / "bul-setup" / "assets" / "module-help.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert [row["skill"] for row in rows] == EXPECTED_SKILLS
    assert [row["action"] for row in rows] == ["configure", "create-packet", "validate-packet", "verify-receipt"]
    assert {row["menu-code"] for row in rows} == {"BU", "BC", "BV", "BR"}
    refs = {f"{row['skill']}:{row['action']}" for row in rows}
    for row in rows:
        for field in ("after", "before"):
            if row[field]:
                assert row[field] in refs


def test_bottom_up_lens_readme_and_skills_state_standalone_boundary() -> None:
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    skill_text = "\n".join((REPO_ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8") for skill in EXPECTED_SKILLS)

    assert "standalone BMad module" in text
    assert "not Lens governance behavior" in text
    assert "packet_output_path" in text
    assert "reports_output_path" in text
    assert "feature.yaml" in text
    assert "governance publish" in text
    assert "release clones" in text
    assert "Landscape" in text
    assert "Derived Graph" in text
    assert "Salmon" in text
    assert "promotion" in text
    assert "adjacency" in text
    assert "pressure" in text
    assert "roadmap" in text
    for forbidden in FORBIDDEN_RUNTIME_DEPENDENCIES:
        assert forbidden not in skill_text
