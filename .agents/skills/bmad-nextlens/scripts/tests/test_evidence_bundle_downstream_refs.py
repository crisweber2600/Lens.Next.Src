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


EVIDENCE_BUNDLE = _load_module("nextlens_evidence_bundle_refs", "evidence_bundle.py")
BMAD_HANDOFF = _load_module("nextlens_bmad_handoff_refs", "bmad_handoff.py")
DOWNSTREAM = _load_module("nextlens_downstream_refs", "downstream_hierarchy.py")
POST_BMAD = _load_module("nextlens_post_bmad_refs", "post_bmad_validation.py")


def test_evidence_bundle_downstream_refs_stay_consistent(tmp_path: Path) -> None:
    packet = {
        "packetId": "packet-900",
        "featureId": "feature-900",
        "trace": {"outcomeIds": ["outcome-900"], "journeyIds": ["journey-900"]},
        "derivedGraphRef": str(tmp_path / "derived" / "graph.json"),
        "evidenceBundleRef": str(tmp_path / ".nextlens" / "evidence-packet-900.yaml"),
        "selectedFeature": {"id": "feature-900", "name": "Evidence Flow"},
        "bmadConsumerHints": {},
    }

    handoff = BMAD_HANDOFF.generate_bmad_handoff_artifacts(tmp_path, packet, update_packet=True)
    assert handoff.status == "pass"
    packet = handoff.packet
    initial_bundle = EVIDENCE_BUNDLE.generate_nextlens_evidence_bundle(
        tmp_path,
        packet=packet,
        artifact_refs={
            "runId": "run.900",
            "bmadHandoffRefs": handoff.artifact_paths,
            "inputAnalysisRef": "artifacts/input-analysis-900.json",
            "rankingTraceRef": "artifacts/ranking-trace-900.json",
            "doctorReportRef": "artifacts/doctor-report-900.jsonl",
        },
        stage_outcomes={"bmad_handoff": "pass"},
        now_factory=lambda: datetime(2026, 5, 14, 9, 59, 0, tzinfo=timezone.utc),
    )
    assert initial_bundle.status == "pass"

    bundle = DOWNSTREAM.build_bmad_artifact_bundle(
        packet_id="packet-900",
        feature_id="feature-900",
        artifacts=[{"id": "artifact-900", "type": "prd", "path": "bmad/prd.md", "status": "ready"}],
        stories=[
            {
                "id": "story-900",
                "title": "Story 900",
                "status": "ready",
                "tracesTo": ["artifact-900", "feature-900"],
                "createdAt": "2026-05-14T10:00:00Z",
            }
        ],
        now_factory=lambda: datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc),
    )
    bundle_path = tmp_path / ".nextlens" / "bmad-bundle-900.json"
    _write_json(bundle_path, bundle)

    evidence = DOWNSTREAM.build_implementation_evidence(
        packet_id="packet-900",
        feature_id="feature-900",
        source_type="manual",
        bmad_artifact_bundle_ref=str(bundle_path),
        stories=[
            {
                "id": "story-900",
                "status": "done",
                "tracesTo": ["feature-900"],
                "evidenceRefs": ["commit-900"],
            }
        ],
        scope_observations=[{"type": "upstream_assumption_change"}],
        goal_evidence=["goal-900"],
        outcome_evidence=["outcome-900"],
        journey_evidence=["journey-900"],
        now_factory=lambda: datetime(2026, 5, 14, 10, 5, 0, tzinfo=timezone.utc),
    )
    evidence_path = tmp_path / ".nextlens" / "implementation-evidence-900.json"
    _write_json(evidence_path, evidence)

    post_result = POST_BMAD.run_post_bmad_validation_flow(
        packet=packet,
        docs_path=tmp_path,
        bmad_artifact_bundle=str(bundle_path),
        implementation_evidence=str(evidence_path),
        landscape_updates=[
            {
                "target": "landscape/feature/feature-900.yaml",
                "changeType": "status",
                "rationale": "Validation confirmed scope change.",
                "authority": "validation",
            }
        ],
        now_factory=lambda: datetime(2026, 5, 14, 10, 6, 0, tzinfo=timezone.utc),
    )

    assert post_result.status == "pass"

    bundle_payload = yaml.safe_load(Path(post_result.evidence_bundle_ref).read_text(encoding="utf-8"))["evidence_bundle"]
    assert bundle_payload["bmadHandoffRefs"] == handoff.artifact_paths
    assert bundle_payload["inputAnalysisRef"] == "artifacts/input-analysis-900.json"
    assert bundle_payload["rankingTraceRef"] == "artifacts/ranking-trace-900.json"
    assert bundle_payload["doctorReportRef"] == "artifacts/doctor-report-900.jsonl"
    assert bundle_payload["bmadArtifactBundleRef"] == str(bundle_path)
    assert bundle_payload["implementationEvidenceRef"] == str(evidence_path)
    assert bundle_payload["validationResultRef"] == post_result.refs["validationResultRef"]
    assert bundle_payload["salmonSignalRefs"] == post_result.refs["salmonSignalRefs"]
    assert bundle_payload["landscapeUpdateRef"] == post_result.refs["landscapeUpdateRef"]
    assert bundle_payload["derivedGraphRef"] == packet["derivedGraphRef"]
    assert bundle_payload["stageOutcomes"]["bmad_handoff"] == "pass"
    assert bundle_payload["stageOutcomes"]["validation"] == "warn"
    assert bundle_payload["stageOutcomes"]["landscape_update"] == "pass"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
