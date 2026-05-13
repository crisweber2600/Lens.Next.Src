from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[6]
SCRIPT = REPO_ROOT / "skills/bmad-lens-setup/assets/lens/scripts/lens_artifact_ops.py"
FIXTURES = REPO_ROOT / "skills/bmad-lens-setup/assets/lens/fixtures"


def prepare_project(tmp_path: Path) -> Path:
    target = tmp_path / "skills/bmad-lens-setup/assets/lens/fixtures"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(FIXTURES, target)
    return tmp_path


def run_cmd(project_root: Path, command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), command, "--project-root", str(project_root)],
        check=True,
        text=True,
        capture_output=True,
    )


def test_map_rebuild_projects_relationship_traceability_freshness_and_warnings(tmp_path: Path) -> None:
    project = prepare_project(tmp_path)
    run_cmd(project, "init")
    result = run_cmd(project, "map-rebuild")

    payload = json.loads(result.stdout)
    assert payload["relationships"] > 0
    assert payload["traceability"] > 0

    graph = project / "_bmad-output/lens/graph"
    relationships = yaml.safe_load((graph / "relationship-index.yaml").read_text())["relationships"]
    traceability = yaml.safe_load((graph / "traceability-index.yaml").read_text())["traceability"]
    freshness = yaml.safe_load((graph / "freshness-index.yaml").read_text())["items"]
    warnings = yaml.safe_load((graph / "warnings.yaml").read_text())["warnings"]

    assert any(rel["from"] == "slice.evidence_visible_to_teacher" for rel in relationships)
    assert any(row["slice"] == "slice.evidence_visible_to_teacher" for row in traceability)
    assert any(item["id"] == "slice.download_model_images" for item in freshness)
    assert any(warning["type"] in {"orphan_ref", "unresolved_promoted_ref"} for warning in warnings)


def test_doctor_and_auspex_emit_richer_status(tmp_path: Path) -> None:
    project = prepare_project(tmp_path)
    run_cmd(project, "init")
    run_cmd(project, "map-rebuild")
    doctor = json.loads(run_cmd(project, "doctor").stdout)
    assert doctor["warnings"] > 0
    assert "orphan_ref" in doctor["by_type"]

    run_cmd(project, "auspex")
    status = json.loads((project / "_bmad-output/lens/auspex/status.json").read_text())
    assert status["relationship_count"] > 0
    assert status["active_slices"]
    assert status["active_journeys"]
    assert status["active_outcomes"]
    assert "open_decisions" in status
    assert status["bmad_progress"]
    assert status["validation_evidence"]
    assert status["salmon_signals"]
    assert status["blockers"]
