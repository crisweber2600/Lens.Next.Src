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


def test_post_bmad_validation_flow_emits_validation_and_salmon(tmp_path: Path) -> None:
    packet = {
        "packetId": "packet-1",
        "featureId": "feature-1",
        "trace": {"outcomeIds": ["outcome-1"], "journeyIds": ["journey-1"]},
        "derivedGraphRef": str(tmp_path / "derived" / "graph.json"),
        "evidenceBundleRef": str(tmp_path / ".nextlens" / "evidence-packet-1.yaml"),
    }

    bundle = DOWNSTREAM.build_bmad_artifact_bundle(
        packet_id="packet-1",
        feature_id="feature-1",
        artifacts=[{"id": "artifact-1", "type": "prd", "path": "bmad/prd.md", "status": "ready"}],
        stories=[
            {
                "id": "story-1",
                "title": "First story",
                "status": "ready",
                "tracesTo": ["artifact-1", "feature-1"],
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
                "tracesTo": ["feature-1"],
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
    assert result.stage_outcomes["validation"] == "warn"
    assert result.stage_outcomes["salmon"] == "pass"
    assert result.stage_outcomes["landscape_update"] == "pass"
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

    evidence_bundle_path = Path(result.evidence_bundle_ref)
    assert evidence_bundle_path.exists()
    evidence_bundle = yaml.safe_load(evidence_bundle_path.read_text(encoding="utf-8"))["evidence_bundle"]
    assert evidence_bundle["bmadArtifactBundleRef"] == str(bundle_path)
    assert evidence_bundle["implementationEvidenceRef"] == str(evidence_path)
    assert evidence_bundle["validationResultRef"] == str(result.validation_path)
    assert evidence_bundle["salmonSignalRefs"] == result.refs["salmonSignalRefs"]
    assert evidence_bundle["landscapeUpdateRef"] == result.refs["landscapeUpdateRef"]
    assert evidence_bundle["derivedGraphRef"] == packet["derivedGraphRef"]
    assert evidence_bundle["stageOutcomes"]["validation"] == "warn"
    assert evidence_bundle["stageOutcomes"]["salmon"] == "pass"


def test_post_bmad_validation_default_proposes_feature_update_without_apply(tmp_path: Path) -> None:
    packet = {
        "packetId": "packet-pass",
        "featureId": "feature-pass",
        "trace": {"outcomeIds": ["outcome-pass"], "journeyIds": ["journey-pass"]},
        "derivedGraphRef": "derived/graph.json",
        "evidenceBundleRef": str(tmp_path / ".nextlens" / "evidence-packet-pass.yaml"),
    }
    bundle = DOWNSTREAM.build_bmad_artifact_bundle(
        packet_id="packet-pass",
        feature_id="feature-pass",
        artifacts=[{"id": "artifact-pass", "type": "prd", "path": "bmad/prd.md", "status": "ready"}],
        stories=[
            {
                "id": "story-pass",
                "title": "Pass story",
                "status": "ready",
                "tracesTo": ["artifact-pass", "feature-pass"],
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
                "tracesTo": ["feature-pass", "outcome-pass", "journey-pass"],
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
    assert result.stage_outcomes["landscape_update"] == "pass"
    assert result.stage_outcomes["derived_graph_refresh"] == "pending"
    assert result.landscape_result.update["authority"]["livingLandscapeAuthoritative"] is True
    assert result.landscape_result.update["authority"]["derivedGraphAuthoritative"] is False
    assert result.landscape_result.update["sourceRefs"]["packetRef"] == "packet-pass"
    assert result.landscape_result.update["sourceRefs"]["evidenceRef"] == str(evidence_path)
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
    bundle = DOWNSTREAM.build_bmad_artifact_bundle(
        packet_id="packet-apply",
        feature_id="feature-apply",
        artifacts=[{"id": "artifact-apply", "type": "prd", "path": "bmad/prd.md", "status": "ready"}],
        stories=[
            {
                "id": "story-apply",
                "title": "Apply story",
                "status": "ready",
                "tracesTo": ["artifact-apply", "feature-apply"],
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
                "tracesTo": ["feature-apply", "outcome-apply", "journey-apply"],
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
        "validation": "warn",
        "salmon": "pass",
        "landscape_update": "pass",
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

    trace = {
        "featureId": feature_id,
        "artifactIds": ["prd-e2e", "architecture-e2e"],
        "outcomeIds": [outcome_id],
        "journeyIds": [journey_id],
    }
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
