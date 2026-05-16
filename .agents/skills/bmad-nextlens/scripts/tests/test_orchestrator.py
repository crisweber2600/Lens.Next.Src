from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from textwrap import dedent

import yaml


MODULE_PATH = Path(__file__).resolve().parent.parent / "orchestrator.py"
SPEC = importlib.util.spec_from_file_location("nextlens_orchestrator", MODULE_PATH)
ORCHESTRATOR = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = ORCHESTRATOR
SPEC.loader.exec_module(ORCHESTRATOR)


def test_run_new_action_pipeline_blocks_on_raw_prose_without_top_down_context(tmp_path: Path) -> None:
    result = ORCHESTRATOR.run_new_action_pipeline(
        "Start with one useful Feature. Do not assume a system exists.",
        docs_path=tmp_path,
    )

    assert result["status"] == "blocked"
    assert result["current_stage"] == "sufficiency"
    assert result["completed_stages"] == ["intake", "extract"]
    assert "top_down_context" in result["output"]
    concepts = json.loads((tmp_path / ".nextlens" / "artifacts" / "extracted-concepts.json").read_text(encoding="utf-8"))
    assert concepts["decision"] == "captured"
    assert concepts["possibleOpenQuestions"]


def test_run_new_action_pipeline_consumes_extracted_concepts_before_requiring_context(tmp_path: Path) -> None:
    concepts_path = tmp_path / "extracted-concepts.yaml"
    concepts_path.write_text(_extracted_concepts_yaml(), encoding="utf-8")

    result = ORCHESTRATOR.run_new_action_pipeline(
        str(concepts_path),
        docs_path=tmp_path,
    )

    assert result["status"] == "blocked"
    assert result["completed_stages"] == ["intake", "extract"]
    artifact = json.loads((tmp_path / ".nextlens" / "artifacts" / "extracted-concepts.json").read_text(encoding="utf-8"))
    assert artifact["decision"] == "consumed"
    assert artifact["possibleCandidateFeatures"][0]["id"] == "feature-context-gate"


def test_run_new_action_pipeline_blocks_when_context_sufficiency_fails(tmp_path: Path) -> None:
    context_path = tmp_path / "blocked-context.yaml"
    context_path.write_text(_blocked_context_yaml(), encoding="utf-8")

    result = ORCHESTRATOR.run_new_action_pipeline(
        str(context_path),
        docs_path=tmp_path,
    )

    assert result["status"] == "blocked"
    assert result["current_stage"] == "sufficiency"
    assert "write" not in result["completed_stages"]
    assert "return_to_discovery" in result["output"]


def test_run_new_action_pipeline_emits_packet_after_explicit_confirmation(tmp_path: Path) -> None:
    context_path = tmp_path / "ready-context.yaml"
    context_path.write_text(_ready_context_yaml(), encoding="utf-8")

    result = ORCHESTRATOR.run_new_action_pipeline(
        str(context_path),
        docs_path=tmp_path,
        resume_state={
            "context": {
                "selected_candidate_id": "feature-context-gate",
                "confirmation_response": "yes",
            }
        },
    )

    assert result["status"] == "complete"
    packet_paths = sorted((tmp_path / ".nextlens").glob("packet-*.json"))
    assert len(packet_paths) == 1
    packet = json.loads(packet_paths[0].read_text(encoding="utf-8"))
    assert packet["featureId"] == "feature-context-gate"
    assert packet["system"]["thesis"] == "Improve planning fidelity"
    assert packet["doctorSummary"]["status"] == "pass"
    final_doctor_report = Path(packet["doctorSummary"]["reportPath"])
    assert final_doctor_report.exists()
    assert Path(packet["evidenceBundleRef"]).exists()
    bundle = yaml.safe_load(Path(packet["evidenceBundleRef"]).read_text(encoding="utf-8"))["evidence_bundle"]
    assert bundle["schemaVersion"] == "nextlens.evidence-bundle.v1"
    assert bundle["packetId"] == packet["packetId"]
    assert bundle["featureId"] == "feature-context-gate"
    assert bundle["doctorReportRef"] == final_doctor_report.relative_to(tmp_path / ".nextlens").as_posix()
    assert bundle["extractedConceptsRef"] == "artifacts/extracted-concepts.json"
    assert bundle["stageOutcomes"]["extracted_concepts"] == "skipped"
    assert bundle["stageOutcomes"]["doctor"] == "pass"
    assert set(bundle["bmadHandoffRefs"]) == {
        "prdInput",
        "uxInput",
        "architectureInput",
        "epicStoryInput",
        "readinessInput",
    }
    skipped = json.loads((tmp_path / ".nextlens" / "artifacts" / "extracted-concepts.json").read_text(encoding="utf-8"))
    assert skipped["decision"] == "already_curated"
    doctor_reports = sorted((tmp_path / ".nextlens").glob("doctor-*.jsonl"))
    assert len(doctor_reports) == 2
    assert final_doctor_report in doctor_reports
    final_lines = [
        json.loads(line)
        for line in final_doctor_report.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(
        line.get("check_id") == "handoff-artifacts-required" and line.get("status") == "pass"
        for line in final_lines
    )
    assert any(
        line.get("check_id") == "handoff-scope" and line.get("status") == "pass"
        for line in final_lines
    )


def test_run_new_action_pipeline_blocks_when_final_handoff_artifact_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    context_path = tmp_path / "ready-context.yaml"
    context_path.write_text(_ready_context_yaml(), encoding="utf-8")
    original_generate = ORCHESTRATOR.BMAD_HANDOFF.generate_bmad_handoff_artifacts

    def generate_then_remove_required_artifact(*args, **kwargs):
        result = original_generate(*args, **kwargs)
        Path(result.artifact_paths["prdInput"]).unlink()
        return result

    monkeypatch.setattr(
        ORCHESTRATOR.BMAD_HANDOFF,
        "generate_bmad_handoff_artifacts",
        generate_then_remove_required_artifact,
    )

    result = ORCHESTRATOR.run_new_action_pipeline(
        str(context_path),
        docs_path=tmp_path,
        resume_state={
            "context": {
                "selected_candidate_id": "feature-context-gate",
                "confirmation_response": "yes",
            }
        },
    )

    assert result["status"] == "blocked"
    assert result["current_stage"] == "emit"
    assert "doctor_status=blocked" in result["output"]
    assert not list((tmp_path / ".nextlens").glob("packet-*.json"))
    assert _any_doctor_line(
        tmp_path,
        check_id="handoff-artifacts-required",
        status="fail",
    )


def test_run_new_action_pipeline_blocks_when_final_handoff_boundary_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    context_path = tmp_path / "ready-context.yaml"
    context_path.write_text(_ready_context_yaml(), encoding="utf-8")
    original_generate = ORCHESTRATOR.BMAD_HANDOFF.generate_bmad_handoff_artifacts

    def generate_then_remove_scope_boundary(*args, **kwargs):
        result = original_generate(*args, **kwargs)
        prd_path = Path(result.artifact_paths["prdInput"])
        content = prd_path.read_text(encoding="utf-8")
        content = content.replace("## Scope Containment Warning\n", "")
        content = content.replace(
            "This packet represents one selected Feature from top-down discovery. "
            "Do not expand into adjacent journeys, future Features, platform architecture, "
            "or unrelated outcomes unless Salmon or correct-course signals scope change.",
            "",
        )
        content = content.replace("## BMAD Expansion Boundary\n", "")
        for boundary_line in ORCHESTRATOR.BMAD_HANDOFF.BMAD_EXPANSION_BOUNDARY:
            content = content.replace(f"- {boundary_line}\n", "")
        prd_path.write_text(content, encoding="utf-8")
        return result

    monkeypatch.setattr(
        ORCHESTRATOR.BMAD_HANDOFF,
        "generate_bmad_handoff_artifacts",
        generate_then_remove_scope_boundary,
    )

    result = ORCHESTRATOR.run_new_action_pipeline(
        str(context_path),
        docs_path=tmp_path,
        resume_state={
            "context": {
                "selected_candidate_id": "feature-context-gate",
                "confirmation_response": "yes",
            }
        },
    )

    assert result["status"] == "blocked"
    assert result["current_stage"] == "emit"
    assert "doctor_status=blocked" in result["output"]
    assert not list((tmp_path / ".nextlens").glob("packet-*.json"))
    assert _any_doctor_line(
        tmp_path,
        check_id="handoff-scope",
        status="fail",
    )


def test_run_new_action_pipeline_preserves_bottom_up_source_mode_and_structured_open_questions(tmp_path: Path) -> None:
    context_path = tmp_path / "bottom-up-context.yaml"
    context_path.write_text(_bottom_up_ready_context_yaml(), encoding="utf-8")

    result = ORCHESTRATOR.run_new_action_pipeline(
        str(context_path),
        docs_path=tmp_path,
        resume_state={
            "context": {
                "selected_candidate_id": "feature-context-gate",
                "confirmation_response": "yes",
            }
        },
    )

    assert result["status"] == "complete"
    packet_path = next((tmp_path / ".nextlens").glob("packet-*.json"))
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    assert packet["sourceMode"] == "bottom_up"
    assert packet["openQuestions"] == [
        {
            "id": "question-bottom-up-proof",
            "text": "What evidence proves this bottom-up slice is ready?",
            "severity": "medium",
        }
    ]


def _blocked_context_yaml() -> str:
    return dedent(
        """
top_down_context:
  schemaVersion: lens.topdown-context.v1
  system:
    id: nextlens
    name: NextLens
    thesis: Improve planning fidelity
    status: active
    confidence: high
  discoveryEpoch:
    id: epoch-2026-05-14
    status: synthesized
    sourceRefs:
      - docs/discovery.md
  roles:
    - id: role-operator
      name: Operator
  outcomes:
    - id: outcome-reduce-ambiguity
      name: Reduce ambiguity
  journeys:
    - id: journey-intake
      name: Intake
  candidateFeatures:
    - id: feature-context-gate
      name: Context sufficiency gate
  stakeholders: []
  operatingLoops: []
  openQuestions:
    - Which top-down fields are mandatory?
    - How should ranking be explained?
    - What proves readiness?
  risks:
    - risk-one
    - risk-two
    - risk-three
  decisions: []
  relationshipRefs: []
"""
    ).strip()


def _any_doctor_line(tmp_path: Path, *, check_id: str, status: str) -> bool:
    for report in (tmp_path / ".nextlens").glob("doctor-*.jsonl"):
        for raw_line in report.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            line = json.loads(raw_line)
            if line.get("check_id") == check_id and line.get("status") == status:
                return True
    return False


def _extracted_concepts_yaml() -> str:
    return dedent(
        """
extracted_concepts:
  schemaVersion: nextlens.extracted-concepts.v1
  possibleRoles:
    - id: role-operator
      name: Operator
  possibleStakeholders:
    - id: stakeholder-reviewer
      name: Reviewer
  possibleOutcomes:
    - id: outcome-reduce-ambiguity
      name: Reduce ambiguity
  possibleOperatingLoops:
    - id: loop-planning
      name: Planning loop
  possibleJourneys:
    - id: journey-intake
      name: Intake
  possibleCandidateFeatures:
    - id: feature-context-gate
      name: Context sufficiency gate
  possibleRisks:
    - id: risk-raw-prose
      name: Raw prose bypass
  possibleOpenQuestions:
    - What top-down context is authoritative?
  possibleRelationshipRefs:
    - nextlens->role-operator
"""
    ).strip()


def _ready_context_yaml() -> str:
    return dedent(
        """
top_down_context:
  schemaVersion: lens.topdown-context.v1
  system:
    id: nextlens
    name: NextLens
    thesis: Improve planning fidelity
    status: active
    confidence: high
  discoveryEpoch:
    id: epoch-2026-05-14
    status: synthesized
    sourceRefs:
      - docs/discovery.md
  roles:
    - id: role-operator
      name: Operator
  stakeholders: []
  outcomes:
    - id: outcome-reduce-ambiguity
      name: Reduce ambiguity
  operatingLoops:
    - id: loop-planning
      name: Planning loop
  journeys:
    - id: journey-intake
      name: Intake
  candidateFeatures:
    - id: feature-context-gate
      name: Context sufficiency gate
      goal: Block packet emission until top-down context is complete.
      outOfScope:
        - adjacent journeys
      roleIds:
        - role-operator
      outcomeIds:
        - outcome-reduce-ambiguity
      journeyIds:
        - journey-intake
      operatingLoopIds:
        - loop-planning
      relationshipRefs:
        - nextlens->role-operator
      selectionRationale: Highest outcome alignment and bounded implementation scope.
      whyNow: Prevents invalid packet emission from raw prose.
      bmadConsumerHints:
        prdInput: PRD guardrail input.
        uxInput: UX implications for the sufficiency gate.
        architectureInput: Architecture impact of requiring top-down context.
        epicStoryInput: Epic and story outline.
        readinessInput: Ready for implementation.
  openQuestions:
    - Which contexts may remain advisory?
    - How should warning confirmations be surfaced?
    - What evidence proves ranking integrity?
  risks:
    - id: risk-fallback-doctor
      name: Fallback doctor pass
      severity: high
  decisions:
    - id: decision-require-top-down-context
      name: Require top-down context before emission
  relationshipRefs:
    - nextlens->role-operator
  bmadConsumerContext:
    planningMode: feature-packet
    consumer: bmad
"""
    ).strip()


def _bottom_up_ready_context_yaml() -> str:
    return dedent(
        """
top_down_context:
  schemaVersion: lens.topdown-context.v1
  sourceMode: bottom_up
  system:
    id: nextlens
    name: NextLens
    thesis: Improve planning fidelity
    status: active
    confidence: high
  discoveryEpoch:
    id: epoch-2026-05-14
    status: synthesized
    sourceRefs:
      - docs/discovery.md
  roles:
    - id: role-operator
      name: Operator
  stakeholders: []
  outcomes:
    - id: outcome-reduce-ambiguity
      name: Reduce ambiguity
  operatingLoops:
    - id: loop-planning
      name: Planning loop
  journeys:
    - id: journey-intake
      name: Intake
  candidateFeatures:
    - id: feature-context-gate
      name: Context sufficiency gate
      goal: Block packet emission until top-down context is complete.
      outOfScope:
        - adjacent journeys
      roleIds:
        - role-operator
      outcomeIds:
        - outcome-reduce-ambiguity
      journeyIds:
        - journey-intake
      operatingLoopIds:
        - loop-planning
      relationshipRefs:
        - nextlens->role-operator
      selectionRationale: Highest outcome alignment and bounded implementation scope.
      whyNow: Prevents invalid packet emission from raw prose.
      bmadConsumerHints:
        prdInput: PRD guardrail input.
        uxInput: UX implications for the sufficiency gate.
        architectureInput: Architecture impact of requiring top-down context.
        epicStoryInput: Epic and story outline.
        readinessInput: Ready for implementation.
  openQuestions:
    - id: question-bottom-up-proof
      text: What evidence proves this bottom-up slice is ready?
      severity: medium
  risks:
    - id: risk-fallback-doctor
      name: Fallback doctor pass
      severity: high
  decisions:
    - id: decision-require-top-down-context
      name: Require top-down context before emission
  relationshipRefs:
    - nextlens->role-operator
  bmadConsumerContext:
    planningMode: feature-packet
    consumer: bmad
"""
    ).strip()
