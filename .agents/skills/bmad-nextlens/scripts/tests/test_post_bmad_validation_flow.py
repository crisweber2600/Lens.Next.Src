from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

import yaml


SCRIPTS_DIR = Path(__file__).resolve().parent.parent


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


POST_BMAD = _load_module("nextlens_post_bmad_validation", "post_bmad_validation.py")
DOWNSTREAM = _load_module("nextlens_downstream_post_bmad", "downstream_hierarchy.py")
DOCTOR = _load_module("nextlens_doctor_post_bmad", "doctor_checks.py")
HANDOFF = _load_module("nextlens_bmad_handoff_post_bmad", "bmad_handoff.py")
COMMAND_SURFACE = _load_module("nextlens_command_surface_post_bmad", "command_surface.py")


def test_ensure_salmon_findings_maps_categories_and_enriches_packet_nodes() -> None:
    validation = {
        "status": "salmon_required",
        "salmonRequired": True,
        "validationId": "validation-mapping",
        "findings": [
            {"category": "journey_evidence", "message": "Journey evidence changed."},
            {"type": "value_mismatch", "message": "Outcome value changed."},
            {"category": "review_owner", "reviewOwnerId": "role-reviewer"},
            {"category": "operating_loop", "loopId": "loop-planning"},
            {"category": "story", "storyRef": "stories/story-1.md"},
            {"category": "local", "message": "Local note only."},
            {"category": "unknown", "message": "Conservative fallback."},
        ],
    }
    packet = {
        "featureId": "feature-from-packet",
        "trace": {"journeyIds": ["journey-from-packet"], "outcomeIds": ["outcome-from-packet"]},
    }

    stitched = POST_BMAD._ensure_salmon_findings(validation, packet=packet)

    assert stitched is not None
    findings = stitched["findings"]
    assert [finding["impactLevel"] for finding in findings] == [
        "journey_assumption_change",
        "outcome_reframe",
        "role_or_stakeholder_change",
        "operating_loop_change",
        "bmad_correct_course_required",
        "local_feature_note",
        "feature_scope_change",
    ]
    assert all(finding["impactedNodes"]["features"] == ["feature-from-packet"] for finding in findings)
    assert findings[0]["impactedNodes"]["journeys"] == ["journey-from-packet"]
    assert findings[1]["impactedNodes"]["outcomes"] == ["outcome-from-packet"]
    assert findings[2]["impactedNodes"]["roles"] == ["role-reviewer"]
    assert findings[3]["impactedNodes"]["operatingLoops"] == ["loop-planning"]
    assert findings[4]["impactedNodes"]["bmadArtifacts"] == ["stories/story-1.md"]


def test_post_bmad_validation_flow_emits_validation_and_salmon(tmp_path: Path) -> None:
    packet = {
        "packetId": "packet-1",
        "featureId": "feature-1",
        "trace": {"outcomeIds": ["outcome-1"], "journeyIds": ["journey-1"]},
        "derivedGraphRef": str(tmp_path / "derived" / "graph.json"),
        "evidenceBundleRef": str(tmp_path / ".nextlens" / "evidence-packet-1.yaml"),
    }
    story_trace = _story_trace("packet-1", "feature-1", ["artifact-1"], ["outcome-1"], ["journey-1"])

    bundle = DOWNSTREAM.build_bmad_artifact_bundle(
        packet_id="packet-1",
        feature_id="feature-1",
        artifacts=[{"id": "artifact-1", "type": "prd", "path": "bmad/prd.md", "status": "ready"}],
        stories=[
            {
                "id": "story-1",
                "title": "First story",
                "status": "ready",
                "tracesTo": story_trace,
                "createdAt": "2026-05-14T10:00:00Z",
            }
        ],
        now_factory=lambda: datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc),
    )
    bundle_path = tmp_path / ".nextlens" / "bmad-bundle.json"
    _write_json(bundle_path, bundle)

    evidence = DOWNSTREAM.build_implementation_evidence(
        packet_id="packet-1",
        feature_id="feature-1",
        source_type="manual",
        bmad_artifact_bundle_ref=str(bundle_path),
        stories=[
            {
                "id": "story-1",
                "status": "done",
                "tracesTo": story_trace,
                "evidenceRefs": ["commit-123"],
            }
        ],
        scope_observations=[{"type": "upstream_assumption_change"}],
        goal_evidence=["goal-1"],
        outcome_evidence=["outcome-1"],
        journey_evidence=["journey-1"],
        now_factory=lambda: datetime(2026, 5, 14, 10, 5, 0, tzinfo=timezone.utc),
    )
    evidence_path = tmp_path / ".nextlens" / "implementation-evidence.json"
    _write_json(evidence_path, evidence)

    result = POST_BMAD.run_post_bmad_validation_flow(
        packet=packet,
        docs_path=tmp_path,
        bmad_artifact_bundle=str(bundle_path),
        implementation_evidence=str(evidence_path),
        landscape_updates=[
            {
                "target": "landscape/feature/feature-1.yaml",
                "changeType": "status",
                "rationale": "Validation requires a truth update.",
                "authority": "validation",
            }
        ],
        now_factory=lambda: datetime(2026, 5, 14, 10, 6, 0, tzinfo=timezone.utc),
    )

    assert result.status == "pass"
    assert result.stage_outcomes["bmad_artifacts"] == "pass"
    assert result.stage_outcomes["stories"] == "pass"
    assert result.stage_outcomes["implementation_evidence"] == "pass"
    assert result.validation_result["status"] == "salmon_required"
    assert result.stage_outcomes["validation"] == "salmon_required"
    assert result.stage_outcomes["salmon"] == "created"
    assert result.stage_outcomes["landscape_update"] == "proposed"
    assert result.stage_outcomes["derived_graph_refresh"] == "pending"

    assert result.validation_path is not None
    assert result.validation_path.exists()
    assert result.evidence_bundle_ref == packet["evidenceBundleRef"]
    assert result.refs["evidenceBundleRef"] == packet["evidenceBundleRef"]
    assert result.refs["bmadArtifactBundleRef"] == str(bundle_path)
    assert result.refs["implementationEvidenceRef"] == str(evidence_path)
    assert result.refs["validationResultRef"] == str(result.validation_path)
    assert result.refs["salmonSignalRefs"]
    assert result.refs["landscapeUpdateRef"]
    assert result.refs["derivedGraphRef"] == packet["derivedGraphRef"]
    source_refs = result.landscape_result.update["sourceRefs"]
    assert source_refs["packetRef"] == "packet-1"
    assert source_refs["evidenceBundleRef"] == packet["evidenceBundleRef"]
    assert source_refs["evidenceRef"] == packet["evidenceBundleRef"]
    assert source_refs["implementationEvidenceRef"] == str(evidence_path)
    assert source_refs["validationRef"] == str(result.validation_path)
    assert source_refs["salmonRef"] == result.refs["salmonSignalRefs"][0]

    evidence_bundle_path = Path(result.evidence_bundle_ref)
    assert evidence_bundle_path.exists()
    evidence_bundle = yaml.safe_load(evidence_bundle_path.read_text(encoding="utf-8"))["evidence_bundle"]
    assert evidence_bundle["bmadArtifactBundleRef"] == str(bundle_path)
    assert evidence_bundle["implementationEvidenceRef"] == str(evidence_path)
    assert evidence_bundle["validationResultRef"] == str(result.validation_path)
    assert evidence_bundle["salmonSignalRefs"] == result.refs["salmonSignalRefs"]
    assert evidence_bundle["landscapeUpdateRef"] == result.refs["landscapeUpdateRef"]
    assert evidence_bundle["derivedGraphRef"] == packet["derivedGraphRef"]
    assert evidence_bundle["sourceRefs"] == source_refs
    assert evidence_bundle["stageOutcomes"]["validation"] == "salmon_required"
    assert evidence_bundle["stageOutcomes"]["salmon"] == "created"


def test_post_bmad_validation_default_proposes_feature_update_without_apply(tmp_path: Path) -> None:
    packet = {
        "packetId": "packet-pass",
        "featureId": "feature-pass",
        "trace": {"outcomeIds": ["outcome-pass"], "journeyIds": ["journey-pass"]},
        "derivedGraphRef": "derived/graph.json",
        "evidenceBundleRef": str(tmp_path / ".nextlens" / "evidence-packet-pass.yaml"),
    }
    story_trace = _story_trace(
        "packet-pass",
        "feature-pass",
        ["artifact-pass"],
        ["outcome-pass"],
        ["journey-pass"],
    )
    bundle = DOWNSTREAM.build_bmad_artifact_bundle(
        packet_id="packet-pass",
        feature_id="feature-pass",
        artifacts=[{"id": "artifact-pass", "type": "prd", "path": "bmad/prd.md", "status": "ready"}],
        stories=[
            {
                "id": "story-pass",
                "title": "Pass story",
                "status": "ready",
                "tracesTo": story_trace,
                "createdAt": "2026-05-14T10:00:00Z",
            }
        ],
        now_factory=lambda: datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc),
    )
    bundle_path = tmp_path / ".nextlens" / "bmad-bundle-pass.json"
    _write_json(bundle_path, bundle)
    evidence = DOWNSTREAM.build_implementation_evidence(
        packet_id="packet-pass",
        feature_id="feature-pass",
        source_type="manual",
        bmad_artifact_bundle_ref=str(bundle_path),
        stories=[
            {
                "id": "story-pass",
                "status": "done",
                "tracesTo": story_trace,
                "evidenceRefs": ["commit-pass"],
            }
        ],
        goal_evidence=["goal-pass"],
        outcome_evidence=["outcome-pass"],
        journey_evidence=["journey-pass"],
        now_factory=lambda: datetime(2026, 5, 14, 10, 5, 0, tzinfo=timezone.utc),
    )
    evidence_path = tmp_path / ".nextlens" / "implementation-evidence-pass.json"
    _write_json(evidence_path, evidence)

    result = POST_BMAD.run_post_bmad_validation_flow(
        packet=packet,
        docs_path=tmp_path,
        bmad_artifact_bundle=str(bundle_path),
        implementation_evidence=str(evidence_path),
        now_factory=lambda: datetime(2026, 5, 14, 10, 6, 0, tzinfo=timezone.utc),
    )

    assert result.status == "pass"
    assert result.validation_result["status"] == "pass"
    assert result.stage_outcomes["salmon"] == "none"
    assert result.stage_outcomes["landscape_update"] == "proposed"
    assert result.stage_outcomes["derived_graph_refresh"] == "pending"
    assert result.landscape_result.update["authority"]["livingLandscapeAuthoritative"] is True
    assert result.landscape_result.update["authority"]["derivedGraphAuthoritative"] is False
    assert result.landscape_result.update["sourceRefs"]["packetRef"] == "packet-pass"
    assert result.landscape_result.update["sourceRefs"]["evidenceBundleRef"] == packet["evidenceBundleRef"]
    assert result.landscape_result.update["sourceRefs"]["evidenceRef"] == packet["evidenceBundleRef"]
    assert result.landscape_result.update["sourceRefs"]["implementationEvidenceRef"] == str(evidence_path)
    assert result.landscape_result.update["sourceRefs"]["validationRef"] == str(result.validation_path)
    assert result.landscape_result.update["sourceRefs"]["salmonRef"] is None
    assert result.landscape_result.update["updates"][0]["target"] == "landscape/feature/feature-pass.yaml"
    assert not (tmp_path / "landscape" / "feature" / "feature-pass.yaml").exists()


def test_post_bmad_validation_apply_mode_applies_and_refreshes_graph(tmp_path: Path) -> None:
    packet = {
        "packetId": "packet-apply",
        "featureId": "feature-apply",
        "trace": {"outcomeIds": ["outcome-apply"], "journeyIds": ["journey-apply"]},
        "derivedGraphRef": "derived/graph-old.json",
        "evidenceBundleRef": str(tmp_path / ".nextlens" / "evidence-packet-apply.yaml"),
    }
    story_trace = _story_trace(
        "packet-apply",
        "feature-apply",
        ["artifact-apply"],
        ["outcome-apply"],
        ["journey-apply"],
    )
    bundle = DOWNSTREAM.build_bmad_artifact_bundle(
        packet_id="packet-apply",
        feature_id="feature-apply",
        artifacts=[{"id": "artifact-apply", "type": "prd", "path": "bmad/prd.md", "status": "ready"}],
        stories=[
            {
                "id": "story-apply",
                "title": "Apply story",
                "status": "ready",
                "tracesTo": story_trace,
                "createdAt": "2026-05-14T10:00:00Z",
            }
        ],
    )
    bundle_path = tmp_path / ".nextlens" / "bmad-bundle-apply.json"
    _write_json(bundle_path, bundle)
    evidence = DOWNSTREAM.build_implementation_evidence(
        packet_id="packet-apply",
        feature_id="feature-apply",
        source_type="manual",
        bmad_artifact_bundle_ref=str(bundle_path),
        stories=[
            {
                "id": "story-apply",
                "status": "done",
                "tracesTo": story_trace,
                "evidenceRefs": ["commit-apply"],
            }
        ],
        goal_evidence=["goal-apply"],
        outcome_evidence=["outcome-apply"],
        journey_evidence=["journey-apply"],
    )
    evidence_path = tmp_path / ".nextlens" / "implementation-evidence-apply.json"
    _write_json(evidence_path, evidence)

    result = POST_BMAD.run_post_bmad_validation_flow(
        packet=packet,
        docs_path=tmp_path,
        bmad_artifact_bundle=str(bundle_path),
        implementation_evidence=str(evidence_path),
        apply_landscape_updates=True,
    )

    assert result.status == "pass"
    assert result.stage_outcomes["landscape_update"] == "applied"
    assert result.stage_outcomes["derived_graph_refresh"] == "pass"
    assert result.refs["derivedGraphRef"] == (tmp_path / "derived" / "graph.json").as_posix()
    assert result.refs["derivedGraphAuthoritative"] is False
    assert (tmp_path / "landscape" / "feature" / "feature-apply.yaml").exists()
    assert (tmp_path / "derived" / "graph.json").exists()


def test_post_bmad_validation_uses_packet_trace_for_story_lineage(tmp_path: Path) -> None:
    packet = {
        "packetId": "packet-lineage",
        "featureId": "feature-lineage",
        "trace": {"outcomeIds": ["outcome-known"], "journeyIds": ["journey-known"]},
        "derivedGraphRef": "derived/graph.json",
        "evidenceBundleRef": str(tmp_path / ".nextlens" / "evidence-packet-lineage.yaml"),
    }
    bundle = DOWNSTREAM.build_bmad_artifact_bundle(
        packet_id="packet-lineage",
        feature_id="feature-lineage",
        artifacts=[{"id": "artifact-lineage", "type": "prd", "path": "bmad/prd.md", "status": "ready"}],
        stories=[
            {
                "id": "story-lineage",
                "title": "Lineage story",
                "status": "ready",
                "tracesTo": _story_trace(
                    "packet-lineage",
                    "feature-lineage",
                    ["artifact-lineage"],
                    ["outcome-missing"],
                    ["journey-known"],
                ),
                "createdAt": "2026-05-14T10:00:00Z",
            }
        ],
    )

    result = POST_BMAD.run_post_bmad_validation_flow(
        packet=packet,
        docs_path=tmp_path,
        bmad_artifact_bundle=bundle,
        create_salmon=False,
    )

    assert result.status == "pass"
    assert result.stage_outcomes["bmad_artifacts"] == "failed"
    assert result.stage_outcomes["stories"] == "failed"


def test_validate_post_bmad_proposal_lifecycle_generates_downstream_refs_without_apply(
    tmp_path: Path,
    monkeypatch,
) -> None:
    packet, bundle_path, evidence_path = _write_ready_post_bmad_inputs(
        tmp_path,
        packet_id="packet-e2e-propose",
        feature_id="feature-e2e-propose",
        outcome_id="outcome-e2e-propose",
        journey_id="journey-e2e-propose",
        story_id="story-e2e-propose",
    )

    parsed = COMMAND_SURFACE.parse_story_command(
        "nextlens validate --packet packet.json "
        f"--bmad-artifacts {bundle_path} "
        f"--implementation-evidence {evidence_path} "
        "--landscape-update-mode propose"
    )
    assert parsed.mode == "validate"
    assert parsed.landscape_update_mode == "propose"

    deterministic_ids = _install_deterministic_uuid(monkeypatch, "101")
    result = POST_BMAD.run_post_bmad_validation_flow(
        packet=packet,
        docs_path=tmp_path,
        bmad_artifact_bundle=str(bundle_path),
        implementation_evidence=str(evidence_path),
        now_factory=lambda: datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert result.status == "pass"
    assert result.validation_path is not None and result.validation_path.exists()
    assert result.validation_path.name == f"validation-{deterministic_ids[0]}.json"
    assert result.validation_result["status"] == "salmon_required"
    assert result.refs["salmonSignalRefs"]
    assert result.refs["landscapeUpdateRef"]
    assert result.refs["derivedGraphAuthoritative"] is False
    assert result.stage_outcomes == {
        "bmad_artifacts": "pass",
        "stories": "pass",
        "implementation_evidence": "pass",
        "validation": "salmon_required",
        "salmon": "created",
        "landscape_update": "proposed",
        "derived_graph_refresh": "pending",
    }

    proposal = result.landscape_result.update
    assert proposal["updateId"] == deterministic_ids[2]
    assert proposal["status"] == "proposed"
    assert proposal["authority"]["livingLandscapeAuthoritative"] is True
    assert proposal["authority"]["derivedGraphAuthoritative"] is False
    assert proposal["updates"][0]["target"] == "landscape/feature/feature-e2e-propose.yaml"
    assert proposal["updates"][0]["authority"] == "salmon"
    assert not (tmp_path / "landscape" / "feature" / "feature-e2e-propose.yaml").exists()
    assert not (tmp_path / "derived" / "graph.json").exists()

    evidence_bundle = yaml.safe_load(Path(result.evidence_bundle_ref).read_text(encoding="utf-8"))[
        "evidence_bundle"
    ]
    assert evidence_bundle["bmadArtifactBundleRef"] == str(bundle_path)
    assert evidence_bundle["implementationEvidenceRef"] == str(evidence_path)
    assert evidence_bundle["validationResultRef"] == str(result.validation_path)
    assert evidence_bundle["salmonSignalRefs"] == result.refs["salmonSignalRefs"]
    assert evidence_bundle["landscapeUpdateRef"] == result.refs["landscapeUpdateRef"]
    assert evidence_bundle["derivedGraphRef"] == packet["derivedGraphRef"]
    for stage, outcome in result.stage_outcomes.items():
        assert evidence_bundle["stageOutcomes"][stage] == outcome

    doctor_packet = _packet_with_downstream_artifacts(packet, result)
    assert _doctor_downstream_statuses(doctor_packet, tmp_path) == {
        "handoff-artifacts-required": "pass",
        "handoff-artifacts-optional": "pass",
        "handoff-scope": "pass",
        "bmad-artifact-bundle": "pass",
        "bmad-story-trace": "pass",
        "implementation-evidence-schema": "pass",
        "implementation-evidence-identity": "pass",
        "validation-result-schema": "pass",
        "salmon-signal-schema": "pass",
        "landscape-update-schema": "pass",
        "derived-graph-authority": "pass",
    }


def test_validate_post_bmad_apply_lifecycle_applies_landscape_and_refreshes_graph(
    tmp_path: Path,
    monkeypatch,
) -> None:
    packet, bundle_path, evidence_path = _write_ready_post_bmad_inputs(
        tmp_path,
        packet_id="packet-e2e-apply",
        feature_id="feature-e2e-apply",
        outcome_id="outcome-e2e-apply",
        journey_id="journey-e2e-apply",
        story_id="story-e2e-apply",
    )

    parsed = COMMAND_SURFACE.parse_story_command(
        "nextlens validate --packet packet.json "
        f"--bmad-artifacts {bundle_path} "
        f"--implementation-evidence {evidence_path} "
        "--landscape-update-mode apply"
    )
    assert parsed.mode == "validate"
    assert parsed.landscape_update_mode == "apply"

    deterministic_ids = _install_deterministic_uuid(monkeypatch, "201")
    result = POST_BMAD.run_post_bmad_validation_flow(
        packet=packet,
        docs_path=tmp_path,
        bmad_artifact_bundle=str(bundle_path),
        implementation_evidence=str(evidence_path),
        apply_landscape_updates=True,
        now_factory=lambda: datetime(2026, 5, 14, 12, 30, 0, tzinfo=timezone.utc),
    )

    assert result.status == "pass"
    assert result.validation_path.name == f"validation-{deterministic_ids[0]}.json"
    assert result.landscape_result.update["updateId"] == deterministic_ids[2]
    assert result.stage_outcomes["landscape_update"] == "applied"
    assert result.stage_outcomes["derived_graph_refresh"] == "pass"
    assert result.refs["derivedGraphAuthoritative"] is False
    assert result.landscape_result.derived_graph_authoritative is False
    assert result.refs["derivedGraphRef"] == (tmp_path / "derived" / "graph.json").as_posix()
    assert (tmp_path / "landscape" / "feature" / "feature-e2e-apply.yaml").exists()
    derived_graph = json.loads((tmp_path / "derived" / "graph.json").read_text(encoding="utf-8"))
    assert derived_graph["metadata"].get("authoritative", False) is False
    assert not (tmp_path / "landscape" / "capability" / "feature-e2e-apply.yaml").exists()
    assert not (tmp_path / "landscape" / "domain" / "feature-e2e-apply.yaml").exists()
    assert not (tmp_path / "landscape" / "system" / "feature-e2e-apply.yaml").exists()


def test_validate_action_runner_loads_packet_and_evidence_files_and_returns_refs(tmp_path: Path) -> None:
    packet, bundle_path, evidence_path = _write_ready_post_bmad_inputs(
        tmp_path,
        packet_id="packet-runner",
        feature_id="feature-runner",
        outcome_id="outcome-runner",
        journey_id="journey-runner",
        story_id="story-runner",
    )
    packet_path = tmp_path / ".nextlens" / "packet-runner.json"
    _write_json(packet_path, packet)

    result = POST_BMAD.run_validate_action(
        str(packet_path),
        str(evidence_path),
        bmad_artifacts_source=str(bundle_path),
        docs_path=tmp_path,
    )

    assert result["status"] == "pass"
    assert result["validationResultRef"]
    assert Path(result["validationResultRef"]).exists()
    assert result["evidenceBundleRef"] == packet["evidenceBundleRef"]
    assert result["salmonSignalRefs"]
    assert result["landscapeUpdateRef"]
    assert result["derivedGraphRef"] == packet["derivedGraphRef"]
    assert result["stageOutcomes"]["implementation_evidence"] == "pass"
    assert result["nextAction"]


def test_validate_action_runner_missing_packet_fails(tmp_path: Path) -> None:
    _, _, evidence_path = _write_ready_post_bmad_inputs(
        tmp_path,
        packet_id="packet-missing-packet",
        feature_id="feature-missing-packet",
        outcome_id="outcome-missing-packet",
        journey_id="journey-missing-packet",
        story_id="story-missing-packet",
    )

    result = POST_BMAD.run_validate_action(
        str(tmp_path / ".nextlens" / "does-not-exist.json"),
        str(evidence_path),
        docs_path=tmp_path,
    )

    assert result["status"] == "fail"
    assert "packet source could not be loaded" in result["error"]
    assert result["validationResultRef"] is None


def test_validate_action_runner_missing_implementation_evidence_fails(tmp_path: Path) -> None:
    packet, _, _ = _write_ready_post_bmad_inputs(
        tmp_path,
        packet_id="packet-missing-evidence",
        feature_id="feature-missing-evidence",
        outcome_id="outcome-missing-evidence",
        journey_id="journey-missing-evidence",
        story_id="story-missing-evidence",
    )
    packet_path = tmp_path / ".nextlens" / "packet-missing-evidence.json"
    _write_json(packet_path, packet)

    result = POST_BMAD.run_validate_action(
        str(packet_path),
        str(tmp_path / ".nextlens" / "missing-evidence.json"),
        docs_path=tmp_path,
    )

    assert result["status"] == "fail"
    assert "implementation evidence source could not be loaded" in result["error"]
    assert result["evidenceBundleRef"] is None


def test_validate_action_runner_invalid_landscape_update_mode_fails_before_writes(tmp_path: Path) -> None:
    packet, bundle_path, evidence_path = _write_ready_post_bmad_inputs(
        tmp_path,
        packet_id="packet-invalid-mode",
        feature_id="feature-invalid-mode",
        outcome_id="outcome-invalid-mode",
        journey_id="journey-invalid-mode",
        story_id="story-invalid-mode",
    )
    packet_path = tmp_path / ".nextlens" / "packet-invalid-mode.json"
    _write_json(packet_path, packet)

    result = POST_BMAD.run_validate_action(
        str(packet_path),
        str(evidence_path),
        bmad_artifacts_source=str(bundle_path),
        docs_path=tmp_path,
        landscape_update_mode="promote",
    )

    assert result["status"] == "fail"
    assert "Invalid landscape_update_mode" in result["error"]
    assert not (tmp_path / ".nextlens" / "validation").exists()
    assert not (tmp_path / ".nextlens" / "landscape-updates").exists()


def test_validate_action_runner_propose_mode_does_not_apply_landscape_update(tmp_path: Path) -> None:
    packet, bundle_path, evidence_path = _write_ready_post_bmad_inputs(
        tmp_path,
        packet_id="packet-runner-propose",
        feature_id="feature-runner-propose",
        outcome_id="outcome-runner-propose",
        journey_id="journey-runner-propose",
        story_id="story-runner-propose",
    )
    packet_path = tmp_path / ".nextlens" / "packet-runner-propose.json"
    _write_json(packet_path, packet)

    result = POST_BMAD.run_validate_action(
        str(packet_path),
        str(evidence_path),
        bmad_artifacts_source=str(bundle_path),
        docs_path=tmp_path,
        landscape_update_mode="proposal",
    )

    assert result["status"] == "pass"
    assert result["stageOutcomes"]["landscape_update"] == "proposed"
    assert result["stageOutcomes"]["derived_graph_refresh"] == "pending"
    assert not (tmp_path / "landscape" / "feature" / "feature-runner-propose.yaml").exists()
    assert not (tmp_path / "derived" / "graph.json").exists()


def test_validate_action_runner_apply_mode_applies_and_refreshes_derived_graph(tmp_path: Path) -> None:
    packet, bundle_path, evidence_path = _write_ready_post_bmad_inputs(
        tmp_path,
        packet_id="packet-runner-apply",
        feature_id="feature-runner-apply",
        outcome_id="outcome-runner-apply",
        journey_id="journey-runner-apply",
        story_id="story-runner-apply",
    )
    packet_path = tmp_path / ".nextlens" / "packet-runner-apply.json"
    _write_json(packet_path, packet)

    result = POST_BMAD.run_validate_action(
        str(packet_path),
        str(evidence_path),
        bmad_artifacts_source=str(bundle_path),
        docs_path=tmp_path,
        landscape_update_mode="apply",
    )

    assert result["status"] == "pass"
    assert result["stageOutcomes"]["landscape_update"] == "applied"
    assert result["stageOutcomes"]["derived_graph_refresh"] == "pass"
    assert result["derivedGraphRef"] == (tmp_path / "derived" / "graph.json").as_posix()
    assert (tmp_path / "landscape" / "feature" / "feature-runner-apply.yaml").exists()
    assert (tmp_path / "derived" / "graph.json").exists()


def test_validate_action_runner_updates_evidence_bundle(tmp_path: Path) -> None:
    packet, bundle_path, evidence_path = _write_ready_post_bmad_inputs(
        tmp_path,
        packet_id="packet-runner-bundle",
        feature_id="feature-runner-bundle",
        outcome_id="outcome-runner-bundle",
        journey_id="journey-runner-bundle",
        story_id="story-runner-bundle",
    )
    packet_path = tmp_path / ".nextlens" / "packet-runner-bundle.json"
    _write_json(packet_path, packet)

    result = POST_BMAD.run_validate_action(
        str(packet_path),
        str(evidence_path),
        bmad_artifacts_source=str(bundle_path),
        docs_path=tmp_path,
    )

    bundle = yaml.safe_load(Path(result["evidenceBundleRef"]).read_text(encoding="utf-8"))[
        "evidence_bundle"
    ]
    assert bundle["validationResultRef"] == result["validationResultRef"]
    assert bundle["landscapeUpdateRef"] == result["landscapeUpdateRef"]
    assert bundle["stageOutcomes"]["landscape_update"] == result["stageOutcomes"]["landscape_update"]


def test_validate_action_e2e_propose_via_command_surface_uses_real_files(tmp_path: Path) -> None:
    packet, bundle_path, evidence_path = _write_ready_post_bmad_inputs(
        tmp_path,
        packet_id="packet-action-e2e-propose",
        feature_id="feature-action-e2e-propose",
        outcome_id="outcome-action-e2e-propose",
        journey_id="journey-action-e2e-propose",
        story_id="story-action-e2e-propose",
    )
    packet_path = tmp_path / ".nextlens" / "packet-action-e2e-propose.json"
    _write_json(packet_path, packet)

    parsed = COMMAND_SURFACE.parse_story_command(
        f"nextlens validate --packet {packet_path} "
        f"--implementation-evidence {evidence_path} "
        f"--bmad-artifacts {bundle_path} "
        f"--docs-path {tmp_path} "
        "--landscape-update-mode propose"
    )

    result = _run_validate_action_from_parsed(parsed)

    assert result["status"] == "pass"
    assert Path(result["validationResultRef"]).exists()
    assert result["evidenceBundleRef"] == packet["evidenceBundleRef"]
    assert result["salmonSignalRefs"]
    assert Path(result["landscapeUpdateRef"]).exists()
    assert result["derivedGraphAuthoritative"] is False
    assert result["stageOutcomes"] == {
        "bmad_artifacts": "pass",
        "stories": "pass",
        "implementation_evidence": "pass",
        "validation": "salmon_required",
        "salmon": "created",
        "landscape_update": "proposed",
        "derived_graph_refresh": "pending",
    }
    validation = json.loads(Path(result["validationResultRef"]).read_text(encoding="utf-8"))
    assert validation["status"] == "salmon_required"

    proposal = yaml.safe_load(Path(result["landscapeUpdateRef"]).read_text(encoding="utf-8"))
    assert proposal["status"] == "proposed"
    assert proposal["authority"]["derivedGraphAuthoritative"] is False
    source_refs = proposal["sourceRefs"]
    assert source_refs["evidenceBundleRef"] == packet["evidenceBundleRef"]
    assert source_refs["implementationEvidenceRef"] == str(evidence_path)
    assert source_refs["evidenceBundleRef"] != source_refs["implementationEvidenceRef"]

    evidence_bundle = yaml.safe_load(Path(result["evidenceBundleRef"]).read_text(encoding="utf-8"))[
        "evidence_bundle"
    ]
    assert evidence_bundle["sourceRefs"] == source_refs
    assert evidence_bundle["landscapeUpdateRef"] == result["landscapeUpdateRef"]
    assert evidence_bundle["salmonSignalRefs"] == result["salmonSignalRefs"]
    for stage, outcome in result["stageOutcomes"].items():
        assert evidence_bundle["stageOutcomes"][stage] == outcome

    bmad_bundle = json.loads(Path(parsed.bmad_artifacts_source).read_text(encoding="utf-8"))
    implementation_evidence = json.loads(
        Path(parsed.implementation_evidence_source).read_text(encoding="utf-8")
    )
    for story in (bmad_bundle["stories"][0], implementation_evidence["stories"][0]):
        assert story["tracesTo"]["featureId"] == "feature-action-e2e-propose"
        assert story["tracesTo"]["outcomeIds"] == ["outcome-action-e2e-propose"]
        assert story["tracesTo"]["journeyIds"] == ["journey-action-e2e-propose"]

    assert not (tmp_path / "landscape" / "feature" / "feature-action-e2e-propose.yaml").exists()
    assert not (tmp_path / "derived" / "graph.json").exists()
    assert not (tmp_path / "landscape" / "capability" / "feature-action-e2e-propose.yaml").exists()
    assert not (tmp_path / "landscape" / "domain" / "feature-action-e2e-propose.yaml").exists()
    assert not (tmp_path / "landscape" / "system" / "feature-action-e2e-propose.yaml").exists()


def test_validate_action_e2e_apply_via_command_surface_applies_and_refreshes(tmp_path: Path) -> None:
    packet, bundle_path, evidence_path = _write_ready_post_bmad_inputs(
        tmp_path,
        packet_id="packet-action-e2e-apply",
        feature_id="feature-action-e2e-apply",
        outcome_id="outcome-action-e2e-apply",
        journey_id="journey-action-e2e-apply",
        story_id="story-action-e2e-apply",
    )
    packet_path = tmp_path / ".nextlens" / "packet-action-e2e-apply.json"
    _write_json(packet_path, packet)

    parsed = COMMAND_SURFACE.parse_story_command(
        f"nextlens validate --packet {packet_path} "
        f"--implementation-evidence {evidence_path} "
        f"--bmad-artifacts {bundle_path} "
        f"--docs-path {tmp_path} "
        "--landscape-update-mode apply"
    )

    result = _run_validate_action_from_parsed(parsed)

    assert result["status"] == "pass"
    assert result["derivedGraphAuthoritative"] is False
    assert result["stageOutcomes"]["validation"] == "salmon_required"
    assert result["stageOutcomes"]["salmon"] == "created"
    assert result["stageOutcomes"]["landscape_update"] == "applied"
    assert result["stageOutcomes"]["derived_graph_refresh"] == "pass"
    assert (tmp_path / "landscape" / "feature" / "feature-action-e2e-apply.yaml").exists()
    assert Path(result["derivedGraphRef"]).exists()

    applied_update = yaml.safe_load(Path(result["landscapeUpdateRef"]).read_text(encoding="utf-8"))
    assert applied_update["status"] == "applied"
    source_refs = applied_update["sourceRefs"]
    assert source_refs["evidenceBundleRef"] == packet["evidenceBundleRef"]
    assert source_refs["implementationEvidenceRef"] == str(evidence_path)
    assert source_refs["evidenceBundleRef"] != source_refs["implementationEvidenceRef"]

    evidence_bundle = yaml.safe_load(Path(result["evidenceBundleRef"]).read_text(encoding="utf-8"))[
        "evidence_bundle"
    ]
    assert evidence_bundle["sourceRefs"] == source_refs
    assert evidence_bundle["stageOutcomes"]["landscape_update"] == "applied"
    assert evidence_bundle["stageOutcomes"]["derived_graph_refresh"] == "pass"

    derived_graph = json.loads(Path(result["derivedGraphRef"]).read_text(encoding="utf-8"))
    assert derived_graph["metadata"].get("authoritative", False) is False
    assert not (tmp_path / "landscape" / "capability" / "feature-action-e2e-apply.yaml").exists()
    assert not (tmp_path / "landscape" / "domain" / "feature-action-e2e-apply.yaml").exists()
    assert not (tmp_path / "landscape" / "system" / "feature-action-e2e-apply.yaml").exists()


def test_validate_action_with_landscape_update_source_proposal_mode(tmp_path: Path) -> None:
    packet, bundle_path, evidence_path = _write_ready_post_bmad_inputs(
        tmp_path,
        packet_id="packet-source-propose",
        feature_id="feature-source-propose",
        outcome_id="outcome-source-propose",
        journey_id="journey-source-propose",
        story_id="story-source-propose",
    )
    packet_path = tmp_path / ".nextlens" / "packet-source-propose.json"
    updates_path = tmp_path / ".nextlens" / "updates-source-propose.yaml"
    _write_json(packet_path, packet)
    updates_path.write_text(
        yaml.safe_dump(
            {
                "updates": [
                    _landscape_update("feature-source-propose", status="validated_from_source")
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = POST_BMAD.run_validate_action(
        str(packet_path),
        str(evidence_path),
        bmad_artifacts_source=str(bundle_path),
        docs_path=tmp_path,
        landscape_update_source=str(updates_path),
        landscape_update_mode="propose",
    )

    assert result["status"] == "pass"
    assert result["stageOutcomes"]["landscape_update"] == "proposed"
    assert not (tmp_path / "landscape" / "feature" / "feature-source-propose.yaml").exists()


def test_validate_action_with_landscape_update_source_apply_mode(tmp_path: Path) -> None:
    packet, bundle_path, evidence_path = _write_ready_post_bmad_inputs(
        tmp_path,
        packet_id="packet-source-apply",
        feature_id="feature-source-apply",
        outcome_id="outcome-source-apply",
        journey_id="journey-source-apply",
        story_id="story-source-apply",
    )
    packet_path = tmp_path / ".nextlens" / "packet-source-apply.json"
    updates_path = tmp_path / ".nextlens" / "updates-source-apply.json"
    _write_json(packet_path, packet)
    _write_json(updates_path, _landscape_update("feature-source-apply", status="validated_from_source"))

    result = POST_BMAD.run_validate_action(
        str(packet_path),
        str(evidence_path),
        bmad_artifacts_source=str(bundle_path),
        docs_path=tmp_path,
        landscape_update_source=str(updates_path),
        landscape_update_mode="apply",
    )

    assert result["status"] == "pass"
    assert result["stageOutcomes"]["landscape_update"] == "applied"
    assert result["stageOutcomes"]["derived_graph_refresh"] == "pass"
    assert (tmp_path / "landscape" / "feature" / "feature-source-apply.yaml").exists()
    assert (tmp_path / "derived" / "graph.json").exists()


def test_validate_action_runner_invalid_landscape_update_source_fails(tmp_path: Path) -> None:
    packet, bundle_path, evidence_path = _write_ready_post_bmad_inputs(
        tmp_path,
        packet_id="packet-invalid-source",
        feature_id="feature-invalid-source",
        outcome_id="outcome-invalid-source",
        journey_id="journey-invalid-source",
        story_id="story-invalid-source",
    )
    packet_path = tmp_path / ".nextlens" / "packet-invalid-source.json"
    updates_path = tmp_path / ".nextlens" / "updates-invalid-source.json"
    _write_json(packet_path, packet)
    _write_json(updates_path, {"updates": [{"target": "landscape/feature/feature-invalid-source.yaml"}]})

    result = POST_BMAD.run_validate_action(
        str(packet_path),
        str(evidence_path),
        bmad_artifacts_source=str(bundle_path),
        docs_path=tmp_path,
        landscape_update_source=str(updates_path),
    )

    assert result["status"] == "fail"
    assert "missing required field" in result["error"]
    assert result["validationResultRef"] is None


def test_validate_action_apply_mode_cannot_write_outside_docs_landscape(tmp_path: Path) -> None:
    packet, bundle_path, evidence_path = _write_ready_post_bmad_inputs(
        tmp_path,
        packet_id="packet-outside-target",
        feature_id="feature-outside-target",
        outcome_id="outcome-outside-target",
        journey_id="journey-outside-target",
        story_id="story-outside-target",
    )
    packet_path = tmp_path / ".nextlens" / "packet-outside-target.json"
    updates_path = tmp_path / ".nextlens" / "updates-outside-target.json"
    _write_json(packet_path, packet)
    outside_target = tmp_path / "outside-landscape.yaml"
    update = _landscape_update("feature-outside-target", target="../outside-landscape.yaml")
    _write_json(updates_path, update)

    result = POST_BMAD.run_validate_action(
        str(packet_path),
        str(evidence_path),
        bmad_artifacts_source=str(bundle_path),
        docs_path=tmp_path,
        landscape_update_source=str(updates_path),
        landscape_update_mode="apply",
    )

    assert result["status"] == "fail"
    assert "must remain under" in result["error"]
    assert result["stageOutcomes"]["landscape_update"] == "blocked"
    assert not outside_target.exists()


def test_post_bmad_validation_marks_deduped_salmon_outcome(
    tmp_path: Path,
    monkeypatch,
) -> None:
    packet, bundle_path, evidence_path = _write_ready_post_bmad_inputs(
        tmp_path,
        packet_id="packet-e2e-deduped",
        feature_id="feature-e2e-deduped",
        outcome_id="outcome-e2e-deduped",
        journey_id="journey-e2e-deduped",
        story_id="story-e2e-deduped",
    )
    _install_deterministic_uuid(monkeypatch, "301")

    first = POST_BMAD.run_post_bmad_validation_flow(
        packet=packet,
        docs_path=tmp_path,
        bmad_artifact_bundle=str(bundle_path),
        implementation_evidence=str(evidence_path),
    )
    second = POST_BMAD.run_post_bmad_validation_flow(
        packet=packet,
        docs_path=tmp_path,
        bmad_artifact_bundle=str(bundle_path),
        implementation_evidence=str(evidence_path),
    )

    assert first.status == "pass"
    assert first.stage_outcomes["salmon"] == "created"
    assert second.status == "pass"
    assert second.stage_outcomes["salmon"] == "deduped"


def test_post_bmad_validation_failed_insufficient_evidence_does_not_propose(tmp_path: Path) -> None:
    packet = {
        "packetId": "packet-fail",
        "featureId": "feature-fail",
        "trace": {"outcomeIds": ["outcome-required"], "journeyIds": ["journey-required"]},
        "derivedGraphRef": "derived/graph.json",
        "evidenceBundleRef": str(tmp_path / ".nextlens" / "evidence-packet-fail.yaml"),
    }
    evidence = DOWNSTREAM.build_implementation_evidence(
        packet_id="packet-fail",
        feature_id="feature-fail",
        source_type="manual",
        bmad_artifact_bundle_ref="bundle.json",
        stories=[],
        goal_evidence=[],
        outcome_evidence=[],
        journey_evidence=[],
    )
    evidence_path = tmp_path / ".nextlens" / "implementation-evidence-fail.json"
    _write_json(evidence_path, evidence)

    result = POST_BMAD.run_post_bmad_validation_flow(
        packet=packet,
        docs_path=tmp_path,
        implementation_evidence=str(evidence_path),
    )

    assert result.status == "pass"
    assert result.validation_result["status"] == "failed"
    assert result.stage_outcomes["validation"] == "failed"
    assert result.stage_outcomes["landscape_update"] == "pending"
    assert result.refs["landscapeUpdateRef"] is None
    assert result.landscape_result is None


def test_post_bmad_validation_preserves_existing_bundle_and_uses_atomic_replace(tmp_path: Path) -> None:
    evidence_bundle_ref = tmp_path / ".nextlens" / "evidence-packet-existing.yaml"
    packet = {
        "packetId": "packet-existing",
        "featureId": "feature-existing",
        "derivedGraphRef": "derived/graph-existing.json",
        "evidenceBundleRef": str(evidence_bundle_ref),
    }
    evidence_bundle_ref.parent.mkdir(parents=True, exist_ok=True)
    evidence_bundle_ref.write_text(
        yaml.safe_dump(
            {
                "evidence_bundle": {
                    "schemaVersion": "nextlens.evidence-bundle.v1",
                    "runId": "run.existing",
                    "packetId": "packet-existing",
                    "featureId": "feature-existing",
                    "inputAnalysisRef": "artifacts/input-analysis-existing.json",
                    "rankingTraceRef": "artifacts/ranking-trace-existing.json",
                    "doctorReportRef": "artifacts/doctor-existing.jsonl",
                    "stageOutcomes": {
                        "intake": "pass",
                        "ranking": "pass",
                        "doctor": "pass",
                    },
                    "createdAt": "2026-05-14T09:00:00Z",
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    replacements: list[tuple[str, str]] = []

    def replace_fn(src: str, dst: str) -> None:
        replacements.append((src, dst))
        Path(src).replace(dst)

    result = POST_BMAD.run_post_bmad_validation_flow(
        packet=packet,
        docs_path=tmp_path,
        bmad_artifact_bundle_ref="artifacts/bmad-bundle-existing.json",
        implementation_evidence_ref="artifacts/implementation-existing.json",
        create_salmon=False,
        now_factory=lambda: datetime(2026, 5, 14, 10, 8, 0, tzinfo=timezone.utc),
        replace_fn=replace_fn,
    )

    assert result.status == "pass"
    assert replacements
    assert replacements[-1][1] == str(evidence_bundle_ref)
    assert Path(replacements[-1][0]).parent == evidence_bundle_ref.parent
    assert not Path(replacements[-1][0]).exists()
    bundle = yaml.safe_load(evidence_bundle_ref.read_text(encoding="utf-8"))["evidence_bundle"]
    assert bundle["inputAnalysisRef"] == "artifacts/input-analysis-existing.json"
    assert bundle["rankingTraceRef"] == "artifacts/ranking-trace-existing.json"
    assert bundle["doctorReportRef"] == "artifacts/doctor-existing.jsonl"
    assert bundle["bmadArtifactBundleRef"] == "artifacts/bmad-bundle-existing.json"
    assert bundle["implementationEvidenceRef"] == "artifacts/implementation-existing.json"
    assert bundle["derivedGraphRef"] == "derived/graph-existing.json"
    assert bundle["stageOutcomes"]["intake"] == "pass"
    assert bundle["stageOutcomes"]["ranking"] == "pass"
    assert bundle["stageOutcomes"]["doctor"] == "pass"
    for key in (
        "bmad_artifacts",
        "stories",
        "implementation_evidence",
        "validation",
        "salmon",
        "landscape_update",
        "derived_graph_refresh",
    ):
        assert key in bundle["stageOutcomes"]


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_ready_post_bmad_inputs(
    tmp_path: Path,
    *,
    packet_id: str,
    feature_id: str,
    outcome_id: str,
    journey_id: str,
    story_id: str,
) -> tuple[dict[str, object], Path, Path]:
    packet = {
        "packetId": packet_id,
        "featureId": feature_id,
        "featureName": f"Feature {feature_id}",
        "sourceMode": "top_down",
        "trace": {
            "systemId": "system-e2e",
            "discoveryEpochId": "epoch-e2e",
            "roleIds": ["role-e2e"],
            "outcomeIds": [outcome_id],
            "journeyIds": [journey_id],
        },
        "selectionRationale": "Selected for deterministic post-BMAD validation coverage.",
        "selectedFeature": {
            "name": f"Feature {feature_id}",
            "goal": "Validate post-BMAD downstream lifecycle.",
            "includedScope": [feature_id],
            "explicitOutOfScope": ["adjacent journeys", "future features", "capability promotion"],
        },
        "system": {"thesis": "Post-BMAD validation keeps landscape truth governed."},
        "roles": [{"id": "role-e2e"}],
        "outcomes": [{"id": outcome_id}],
        "journeys": [{"id": journey_id}],
        "openQuestions": ["Which Salmon finding should be reviewed first?"],
        "risks": ["Applying landscape updates without operator intent."],
        "derivedGraphRef": str(tmp_path / "derived" / "graph-source.json"),
        "evidenceBundleRef": str(tmp_path / ".nextlens" / f"evidence-{packet_id}.yaml"),
    }
    handoff = HANDOFF.generate_bmad_handoff_artifacts(tmp_path, packet)
    assert handoff.status == "pass"
    packet = handoff.packet

    trace = _story_trace(
        packet_id,
        feature_id,
        ["prd-e2e", "architecture-e2e"],
        [outcome_id],
        [journey_id],
    )
    bundle = DOWNSTREAM.build_bmad_artifact_bundle(
        packet_id=packet_id,
        feature_id=feature_id,
        artifacts=[
            {"id": "prd-e2e", "type": "prd", "path": "bmad/prd.md", "status": "ready"},
            {
                "id": "architecture-e2e",
                "type": "architecture",
                "path": "bmad/architecture.md",
                "status": "ready",
            },
        ],
        stories=[
            {
                "id": story_id,
                "title": "Complete post-BMAD validation lifecycle",
                "status": "ready",
                "tracesTo": trace,
                "createdAt": "2026-05-14T11:00:00Z",
            }
        ],
        bundle_id=f"bundle-{packet_id}",
        now_factory=lambda: datetime(2026, 5, 14, 11, 0, 0, tzinfo=timezone.utc),
    )
    bundle_path = tmp_path / ".nextlens" / f"bmad-bundle-{packet_id}.json"
    _write_json(bundle_path, bundle)

    evidence = DOWNSTREAM.build_implementation_evidence(
        packet_id=packet_id,
        feature_id=feature_id,
        source_type="manual",
        bmad_artifact_bundle_ref=str(bundle_path),
        stories=[
            {
                "id": story_id,
                "status": "done",
                "tracesTo": trace,
                "evidenceRefs": ["commit-e2e", "test-e2e"],
            }
        ],
        scope_observations=[
            {
                "type": "upstream_assumption_change",
                "description": "Implemented evidence changed a durable journey assumption.",
                "requiresSalmon": True,
            }
        ],
        evidence_id=f"evidence-{packet_id}",
        goal_evidence=[feature_id],
        outcome_evidence=[outcome_id],
        journey_evidence=[journey_id],
        now_factory=lambda: datetime(2026, 5, 14, 11, 30, 0, tzinfo=timezone.utc),
    )
    evidence_path = tmp_path / ".nextlens" / f"implementation-evidence-{packet_id}.json"
    _write_json(evidence_path, evidence)

    return dict(packet), bundle_path, evidence_path


def _run_validate_action_from_parsed(parsed) -> dict[str, object]:
    assert parsed.mode == "validate"
    return POST_BMAD.run_validate_action(
        parsed.packet_source,
        parsed.implementation_evidence_source,
        bmad_artifacts_source=parsed.bmad_artifacts_source,
        docs_path=parsed.overrides.get("docs_path"),
        landscape_update_source=parsed.landscape_update_source,
        landscape_update_mode=parsed.landscape_update_mode,
    )


def _story_trace(
    packet_id: str,
    feature_id: str,
    artifact_ids: list[str],
    outcome_ids: list[str],
    journey_ids: list[str],
) -> dict[str, object]:
    return {
        "packetId": packet_id,
        "featureId": feature_id,
        "artifactIds": artifact_ids,
        "outcomeIds": outcome_ids,
        "journeyIds": journey_ids,
    }


def _landscape_update(
    feature_id: str,
    *,
    target: str | None = None,
    status: str = "validated",
) -> dict[str, object]:
    return {
        "target": target or f"landscape/feature/{feature_id}.yaml",
        "changeType": "status",
        "rationale": "Validate action supplied an operator-approved Landscape update.",
        "authority": "validation",
        "payload": {
            "entityType": "feature",
            "identity": {
                "semanticId": feature_id,
                "opaqueId": f"opaque-{feature_id}",
                "name": f"Feature {feature_id}",
            },
            "snapshot": {
                "status": status,
                "currentTruth": "Validate action source update.",
                "validationStatus": status,
                "notes": ["Validate action source update."],
                "salmonSignalRefs": [],
            },
            "relationships": {},
            "metadata": {
                "source": "validate-action",
                "author": "nextlens",
                "updatedAt": "2026-05-14T12:45:00Z",
                "derivedGraphAuthoritative": False,
            },
        },
    }


def _install_deterministic_uuid(monkeypatch, suffix_start: str) -> list[str]:
    base = int(suffix_start)
    values = [
        f"00000000-0000-4000-8000-{base + offset:012d}"
        for offset in range(10)
    ]
    iterator = iter(values)
    monkeypatch.setattr(POST_BMAD.uuid, "uuid4", lambda: next(iterator))
    return values


def _packet_with_downstream_artifacts(
    packet: dict[str, object],
    result: POST_BMAD.PostBmadValidationResult,
) -> dict[str, object]:
    enriched = dict(packet)
    enriched["validationRequested"] = True
    enriched["derivedGraphAuthoritative"] = False
    enriched["downstreamArtifacts"] = {
        "bmadArtifactBundleRef": result.refs["bmadArtifactBundleRef"],
        "implementationEvidenceRef": result.refs["implementationEvidenceRef"],
        "validationResultRef": result.refs["validationResultRef"],
        "salmonSignals": list(result.salmon_result.events),
        "landscapeUpdate": result.landscape_result.update,
    }
    return enriched


def _doctor_downstream_statuses(
    packet: dict[str, object],
    docs_path: Path,
) -> dict[str, str]:
    context = DOCTOR.DoctorCheckContext(
        landscape_state=None,
        derived_graph={},
        packet_candidate=packet,
        docs_path=docs_path,
    )
    checks = (
        DOCTOR._check_handoff_artifacts_required,
        DOCTOR._check_handoff_artifacts_optional,
        DOCTOR._check_handoff_scope,
        DOCTOR._check_bmad_artifact_bundle,
        DOCTOR._check_bmad_story_trace,
        DOCTOR._check_implementation_evidence_schema,
        DOCTOR._check_implementation_evidence_identity,
        DOCTOR._check_validation_result_schema,
        DOCTOR._check_salmon_signal_schema,
        DOCTOR._check_landscape_update_schema,
        DOCTOR._check_derived_graph_authority,
    )
    return {result.check_id: result.status for result in (check(context) for check in checks)}
