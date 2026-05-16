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
    assert Path(packet["evidenceBundleRef"]).exists()
    bundle = yaml.safe_load(Path(packet["evidenceBundleRef"]).read_text(encoding="utf-8"))["evidence_bundle"]
    assert bundle["schemaVersion"] == "nextlens.evidence-bundle.v1"
    assert bundle["packetId"] == packet["packetId"]
    assert bundle["featureId"] == "feature-context-gate"
    assert bundle["extractedConceptsRef"] == "artifacts/extracted-concepts.json"
    assert bundle["stageOutcomes"]["extracted_concepts"] == "skipped"
    skipped = json.loads((tmp_path / ".nextlens" / "artifacts" / "extracted-concepts.json").read_text(encoding="utf-8"))
    assert skipped["decision"] == "already_curated"
    assert any((tmp_path / ".nextlens").glob("doctor-*.jsonl"))


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
