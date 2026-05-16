from __future__ import annotations

from pathlib import Path


def test_new_skill_requires_candidate_breakdown_before_packet_emission() -> None:
    skills_root = Path(__file__).resolve().parents[3]
    skill_text = (skills_root / "bmad-nextlens-new" / "SKILL.md").read_text(encoding="utf-8")

    assert "## Candidate Breakdown Gate" in skill_text
    assert "before any Feature packet is composed or emitted" in skill_text
    assert "Bottom-Up LENS descriptions must be analyzed into candidate Feature slices" in skill_text
    assert "The operator must be able to choose a rank or candidate id" in skill_text
    assert "vscode_askQuestions" in skill_text
    assert "render the numbered candidate menu" in skill_text
    assert "Do not infer confirmation from silence" in skill_text
    assert skill_text.index("## Candidate Breakdown Gate") < skill_text.index("## Action Contract")


def test_new_skill_requires_explicit_curation_and_forbids_inline_runtime_repair() -> None:
    skills_root = Path(__file__).resolve().parents[3]
    skill_text = (skills_root / "bmad-nextlens-new" / "SKILL.md").read_text(encoding="utf-8")

    assert "use the shared extracted-concepts stage first" in skill_text
    assert "authoritative curated `top_down_context` artifact" in skill_text
    assert "Raw prose or extracted concepts alone must not be emitted directly as a Feature packet." in skill_text
    assert "## Runtime Defect Boundary" in skill_text
    assert "Do not patch `.agents/skills/bmad-nextlens/scripts/**`" in skill_text
    assert "route it through `/lens-nextlens-bugfix`, `bmad-nextlens-doctor`, or Salmon" in skill_text
    assert skill_text.index("## Runtime Defect Boundary") < skill_text.index("## Action Contract")