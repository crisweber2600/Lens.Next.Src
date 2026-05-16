from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import sys


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
                "tracesTo": ["artifact-1"],
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
    assert result.stage_outcomes["validation"] == "salmon_required"
    assert result.stage_outcomes["salmon"] == "created"
    assert result.stage_outcomes["landscape_update"] == "proposed"
    assert result.stage_outcomes["derived_graph_refresh"] == "pending"

    assert result.validation_path is not None
    assert result.validation_path.exists()
    assert result.refs["bmadArtifactBundleRef"] == str(bundle_path)
    assert result.refs["implementationEvidenceRef"] == str(evidence_path)
    assert result.refs["validationResultRef"] == str(result.validation_path)
    assert result.refs["salmonSignalRefs"]
    assert result.refs["landscapeUpdateRef"]
    assert result.refs["derivedGraphRef"] == packet["derivedGraphRef"]


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
