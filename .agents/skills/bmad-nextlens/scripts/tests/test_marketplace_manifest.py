from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
MANIFEST_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"


def test_marketplace_manifest_has_required_distribution_metadata() -> None:
    manifest = _manifest()

    assert manifest["name"] == "NextLens Top-Down Bridge"
    assert manifest["license"] == "MIT"
    assert manifest["owner"]["name"] == "NextLens Team"
    assert manifest["homepage"].startswith("https://github.com/")
    assert manifest["repository"].startswith("https://github.com/")
    assert set(manifest["keywords"]) >= {"nextlens", "top-down", "feature-packet", "bmad-module"}


def test_marketplace_manifest_declares_one_installable_plugin() -> None:
    plugins = _manifest()["plugins"]

    assert len(plugins) == 1
    plugin = plugins[0]
    assert plugin["name"] == "nxl"
    assert plugin["source"] == "./"
    assert plugin["description"] == "Deterministic top-down feature packet bridge with doctor validation and salmon correction routing."
    assert plugin["version"] == "1.0.0"
    assert plugin["author"]["name"] == "NextLens Team"


def test_marketplace_manifest_skill_paths_are_repo_relative_and_exist() -> None:
    expected_skill_paths = [
        ".agents/skills/bmad-nextlens-setup",
        ".agents/skills/bmad-nextlens-new",
        ".agents/skills/bmad-nextlens-doctor",
        ".agents/skills/bmad-nextlens-salmon",
    ]

    plugin = _manifest()["plugins"][0]
    assert plugin["skills"] == expected_skill_paths
    for skill_path in plugin["skills"]:
        assert not Path(skill_path).is_absolute()
        assert ".." not in Path(skill_path).parts
        assert (REPO_ROOT / skill_path).is_dir()
        assert (REPO_ROOT / skill_path / "SKILL.md").is_file()


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
