from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
MANIFEST_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"


def test_marketplace_manifest_has_required_distribution_metadata() -> None:
    manifest = _manifest()

    assert manifest["name"] == "NextLens Top-Down Bridge"
    assert manifest["version"] == "1.0.0"
    assert manifest["description"] == "Deterministic v1 top-down Feature packet bridge with validation and correction routing"
    assert manifest["author"] == "NextLens Team"
    assert manifest["repository"].startswith("https://github.com/")
    assert manifest["license"] == "MIT"
    assert set(manifest["keywords"]) >= {"nextlens", "top-down", "feature-packet", "bmad-module"}


def test_marketplace_manifest_declares_expected_plugins() -> None:
    plugins = {plugin["id"]: plugin for plugin in _manifest()["plugins"]}

    assert set(plugins) == {"nextlens-setup", "nextlens-new", "nextlens-doctor", "nextlens-salmon"}
    assert plugins["nextlens-setup"]["name"] == "NextLens Setup"
    assert plugins["nextlens-new"]["name"] == "NextLens New Packet"
    assert plugins["nextlens-doctor"]["name"] == "NextLens Doctor"
    assert plugins["nextlens-salmon"]["name"] == "NextLens Salmon"
    assert plugins["nextlens-setup"]["description"] == "Register or refresh the NextLens BMad module in this project."
    assert plugins["nextlens-new"]["description"] == "Create one Feature packet from top-down discovery context."
    assert plugins["nextlens-doctor"]["description"] == "Run non-mutating validation checks on a Feature packet or landscape."
    assert plugins["nextlens-salmon"]["description"] == "Route correction findings through deduplication and impact classification."


def test_marketplace_manifest_skill_paths_are_repo_relative_and_exist() -> None:
    expected_skill_paths = {
        "nextlens-setup": ".agents/skills/bmad-nextlens-setup/SKILL.md",
        "nextlens-new": ".agents/skills/bmad-nextlens-new/SKILL.md",
        "nextlens-doctor": ".agents/skills/bmad-nextlens-doctor/SKILL.md",
        "nextlens-salmon": ".agents/skills/bmad-nextlens-salmon/SKILL.md",
    }

    for plugin in _manifest()["plugins"]:
        assert plugin["skills"] == [expected_skill_paths[plugin["id"]]]
        for skill_path in plugin["skills"]:
            assert not Path(skill_path).is_absolute()
            assert ".." not in Path(skill_path).parts
            assert (REPO_ROOT / skill_path).is_file()


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))