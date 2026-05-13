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
TEMPLATES = REPO_ROOT / "skills/bmad-lens-setup/assets/lens/templates"


def prepare_project(tmp_path: Path) -> Path:
    target = tmp_path / "skills/bmad-lens-setup/assets/lens/fixtures"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(FIXTURES, target)
    shutil.copytree(TEMPLATES, tmp_path / "skills/bmad-lens-setup/assets/lens/templates")
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
    relationship_contract = yaml.safe_load(
        (REPO_ROOT / "skills/bmad-lens-setup/assets/lens/schemas/relationship-types.yaml").read_text(encoding="utf-8")
    )
    allowed_types = set(relationship_contract["relationship_types"])

    assert any(rel["from"] == "slice.evidence_visible_to_teacher" for rel in relationships)
    assert {rel["type"] for rel in relationships} <= allowed_types
    assert any(rel["type"] == "possibly_conflicts_with" for rel in relationships)
    assert any(rel["type"] == "touches_file" for rel in relationships)
    assert any(row["slice"] == "slice.evidence_visible_to_teacher" for row in traceability)
    top_down_trace = next(row for row in traceability if row["slice"] == "slice.evidence_visible_to_teacher")
    assert top_down_trace["impacted_workstreams"]
    assert top_down_trace["shared_contracts"]
    assert any(item["id"] == "slice.download_model_images" for item in freshness)
    assert any(warning["type"] == "workstream_impact_gate" for warning in warnings)


def test_doctor_and_auspex_emit_richer_status(tmp_path: Path) -> None:
    project = prepare_project(tmp_path)
    run_cmd(project, "init")
    run_cmd(project, "map-rebuild")
    doctor = json.loads(run_cmd(project, "doctor").stdout)
    assert doctor["warnings"] > 0
    assert "orphan_ref" in doctor["by_type"]
    assert "workstream_impact_gate" in doctor["by_type"]
    assert "unresolved_decision" in doctor["by_type"]

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


def test_init_writes_rich_project_context_when_absent(tmp_path: Path) -> None:
    project = prepare_project(tmp_path)
    run_cmd(project, "init")
    context = (project / "_bmad-output/project-context.md").read_text(encoding="utf-8")
    assert "Traceability Rule" in context
    assert "Scope Rule" in context
    assert "Architecture Rule" in context
    assert "Upstream Change Rule" in context
    assert "Source Truth Rule" in context


def test_bmad_packet_yaml_fixture_is_valid_and_aligned() -> None:
    packet = yaml.safe_load(
        (FIXTURES / "top-down/evidence-visible-to-teacher/bmad-packet.yaml").read_text(encoding="utf-8")
    )["bmad_packet"]
    packet_md = (FIXTURES / "top-down/evidence-visible-to-teacher/bmad-packet.md").read_text(encoding="utf-8")
    assert packet["active_slice"] == "slice.evidence_visible_to_teacher"
    for key in ["included_scope", "explicit_exclusions", "active_slice", "required_capabilities", "recommended_bmad_next_step"]:
        assert key in packet
    assert "slice.evidence_visible_to_teacher" in packet_md
    assert "Required Capabilities" in packet_md


def test_doctor_flags_semantic_anomalies_from_source_truth(tmp_path: Path) -> None:
    project = prepare_project(tmp_path)
    anomaly = project / "skills/bmad-lens-setup/assets/lens/fixtures/doctor/anomaly.yaml"
    anomaly.parent.mkdir(parents=True, exist_ok=True)
    anomaly.write_text(
        """
items:
  - id: story.untraced
    kind: story
    name: Untraced Story
    status: planned
    confidence: low
    created_at: "2026-05-13"
    updated_at: "2026-05-13"
    source_refs: []
    relationships: []
    open_questions: []
  - id: bmad_packet.unsynced
    kind: bmad_packet
    name: Unsynced Packet
    status: draft
    validity: needs_review
    confidence: low
    created_at: "2026-05-13"
    updated_at: "2026-05-13"
    source_refs: []
    relationships: []
    open_questions: []
  - id: rel.self_loop
    kind: relationship
    name: Self Loop
    status: hypothesized
    confidence: low
    created_at: "2026-05-13"
    updated_at: "2026-05-13"
    source_refs: []
    relationships: []
    open_questions: []
    from: slice.download_model_images
    to: slice.download_model_images
""",
        encoding="utf-8",
    )

    run_cmd(project, "init")
    doctor = json.loads(run_cmd(project, "doctor").stdout)
    assert "missing_source_refs" in doctor["by_type"]
    assert "stale_or_needs_review" in doctor["by_type"]
    assert "untraced_story" in doctor["by_type"]
    assert "bmad_sync_gap" in doctor["by_type"]
    assert "relationship_self_loop" in doctor["by_type"]
    assert "relationship_missing_type" in doctor["by_type"]
