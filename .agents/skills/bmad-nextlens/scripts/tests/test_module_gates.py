from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys


MODULE_PATH = Path(__file__).resolve().parent.parent / "module_gates.py"
SPEC = importlib.util.spec_from_file_location("nextlens_module_gates", MODULE_PATH)
MODULE_GATES = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE_GATES
SPEC.loader.exec_module(MODULE_GATES)


def test_create_module_package_regenerates_manifests_and_checksum_report(tmp_path: Path) -> None:
    repo_root = _repo_fixture(tmp_path)

    result = MODULE_GATES.create_module_package(
        repo_root,
        now_factory=lambda: datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert result.status == "pass"
    assert result.approved_for_distribution is True
    assert (repo_root / ".agents" / "skills" / "bmad-nextlens-setup" / "assets" / "module.yaml").is_file()
    assert (repo_root / "skills" / "module.yaml").is_file()
    assert (repo_root / ".agents" / "skills" / "bmad-nextlens-setup" / "assets" / "module-help.csv").is_file()
    assert (repo_root / ".claude-plugin" / "marketplace.json").is_file()
    assert result.report_path == repo_root / ".claude-plugin" / "module-gates.json"
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert report["status"] == "pass"
    assert report["generated_at"] == "2026-05-14T12:00:00Z"
    assert {item["path"] for item in report["generated_files"]} == {
        ".agents/skills/bmad-nextlens-setup/assets/module.yaml",
        "skills/module.yaml",
        ".agents/skills/bmad-nextlens-setup/assets/module-help.csv",
        ".claude-plugin/marketplace.json",
    }
    assert all(len(item["checksum"]) == 64 for item in report["generated_files"])


def test_validate_module_package_passes_for_generated_package(tmp_path: Path) -> None:
    repo_root = _repo_fixture(tmp_path)
    MODULE_GATES.create_module_package(repo_root)

    result = MODULE_GATES.validate_module_package(repo_root)

    assert result.status == "pass"
    assert result.approved_for_distribution is True
    assert result.findings == ()
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert report["approved_for_distribution"] is True


def test_validate_module_package_reports_missing_manifest_skill_with_remediation(tmp_path: Path) -> None:
    repo_root = _repo_fixture(tmp_path)
    MODULE_GATES.create_module_package(repo_root)
    (repo_root / ".agents" / "skills" / "bmad-nextlens-new" / "SKILL.md").unlink()

    result = MODULE_GATES.validate_module_package(repo_root)

    assert result.status == "fail"
    assert result.approved_for_distribution is False
    assert any(finding.check_id == "marketplace-skill-missing" for finding in result.findings)
    assert any("Create the skill file" in finding.remediation for finding in result.findings)


def test_validate_module_package_blocks_inconsistent_capability_sets(tmp_path: Path) -> None:
    repo_root = _repo_fixture(tmp_path)
    MODULE_GATES.create_module_package(repo_root)
    module_help = repo_root / ".agents" / "skills" / "bmad-nextlens-setup" / "assets" / "module-help.csv"
    module_help.write_text(
        module_help.read_text(encoding="utf-8").replace(",salmon,", ",missing,"),
        encoding="utf-8",
    )

    result = MODULE_GATES.validate_module_package(repo_root)

    assert result.status == "fail"
    assert any(finding.check_id == "module-help-action-set" for finding in result.findings)
    assert any(finding.check_id == "manifest-command-consistency" for finding in result.findings)


def test_validate_module_package_requires_config_discovery_manifest_to_mirror_setup_manifest(tmp_path: Path) -> None:
    repo_root = _repo_fixture(tmp_path)
    MODULE_GATES.create_module_package(repo_root)
    config_discovery_module = repo_root / "skills" / "module.yaml"
    config_discovery_module.write_text(
        config_discovery_module.read_text(encoding="utf-8").replace("code: nxl", "code: stale"),
        encoding="utf-8",
    )

    result = MODULE_GATES.validate_module_package(repo_root)

    assert result.status == "fail"
    assert any(finding.check_id == "config-discovery-module-yaml" for finding in result.findings)


def test_validate_module_package_requires_marketplace_owner_name(tmp_path: Path) -> None:
    repo_root = _repo_fixture(tmp_path)
    MODULE_GATES.create_module_package(repo_root)
    marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"
    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    marketplace["owner"] = {}
    marketplace_path.write_text(json.dumps(marketplace), encoding="utf-8")

    result = MODULE_GATES.validate_module_package(repo_root)

    assert result.status == "fail"
    assert any(finding.check_id == "marketplace-owner" for finding in result.findings)


def test_validate_module_package_requires_marketplace_plugin_author_name(tmp_path: Path) -> None:
    repo_root = _repo_fixture(tmp_path)
    MODULE_GATES.create_module_package(repo_root)
    marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"
    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    marketplace["plugins"][0]["author"] = {}
    marketplace_path.write_text(json.dumps(marketplace), encoding="utf-8")

    result = MODULE_GATES.validate_module_package(repo_root)

    assert result.status == "fail"
    assert any(finding.check_id == "marketplace-author" for finding in result.findings)


def test_validate_current_repository_package_passes() -> None:
    repo_root = Path(__file__).resolve().parents[5]

    result = MODULE_GATES.validate_module_package(repo_root)

    assert result.status == "pass"
    assert result.approved_for_distribution is True


def _repo_fixture(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[5]
    repo_root = tmp_path / "NextLens"
    shared_skill_path = repo_root / ".agents" / "skills" / "bmad-nextlens" / "SKILL.md"
    shared_skill_path.parent.mkdir(parents=True, exist_ok=True)
    source_shared_skill = source_root / ".agents" / "skills" / "bmad-nextlens" / "SKILL.md"
    if source_shared_skill.exists():
        shutil.copyfile(source_shared_skill, shared_skill_path)
    else:
        shared_skill_path.write_text("# bmad-nextlens\n", encoding="utf-8")
    for skill_name in (
        "bmad-nextlens-setup",
        "bmad-nextlens-new",
        "bmad-nextlens-doctor",
        "bmad-nextlens-salmon",
    ):
        skill_path = repo_root / ".agents" / "skills" / skill_name / "SKILL.md"
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        source_skill = source_root / ".agents" / "skills" / skill_name / "SKILL.md"
        if source_skill.exists():
            shutil.copyfile(source_skill, skill_path)
        else:
            skill_path.write_text(f"# {skill_name}\n", encoding="utf-8")

    for relative_path in (
        ".agents/skills/bmad-nextlens-setup/assets/module.yaml",
        "skills/module.yaml",
        ".agents/skills/bmad-nextlens-setup/assets/module-help.csv",
        ".claude-plugin/marketplace.json",
    ):
        source_path = source_root / relative_path
        target_path = repo_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.exists():
            shutil.copyfile(source_path, target_path)
    return repo_root
