from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import yaml


MODULE_PATH = Path(__file__).resolve().parent.parent / "downstream_salmon_landscape.py"
SPEC = importlib.util.spec_from_file_location("nextlens_downstream_salmon_landscape", MODULE_PATH)
DOWNSTREAM = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = DOWNSTREAM
SPEC.loader.exec_module(DOWNSTREAM)


def test_build_landscape_update_proposal_includes_required_fields() -> None:
    proposal = DOWNSTREAM.build_landscape_update_proposal(
        source_refs={"packetRef": "packet-123", "validationRef": "validation-001"},
        updates=[
            {
                "target": "landscape/feature/feature-password-recovery.yaml",
                "changeType": "status",
                "rationale": "Validation confirms current truth needs to be updated.",
                "authority": "validation",
            }
        ],
        update_id="update-001",
    )

    assert proposal["schemaVersion"] == "nextlens.landscape-update.v1"
    assert proposal["updateId"] == "update-001"
    assert proposal["status"] == "proposed"
    assert proposal["sourceRefs"]["packetRef"] == "packet-123"
    assert proposal["sourceRefs"]["evidenceRef"] is None
    assert proposal["sourceRefs"]["validationRef"] == "validation-001"
    assert proposal["sourceRefs"]["salmonRef"] is None
    assert proposal["authority"]["livingLandscape"] == "authoritative"
    assert proposal["authority"]["derivedGraph"] == "non_authoritative"
    assert proposal["authority"]["derivedGraphAuthoritative"] is False
    assert proposal["updates"][0]["target"] == "landscape/feature/feature-password-recovery.yaml"


def test_apply_landscape_update_writes_payload_and_marks_applied(tmp_path: Path) -> None:
    proposal = DOWNSTREAM.build_landscape_update_proposal(
        source_refs={"salmonRef": "salmon-001"},
        updates=[
            {
                "target": "landscape/role/role-operator.yaml",
                "changeType": "update",
                "rationale": "Correct role metadata from Salmon signal.",
                "authority": "salmon",
                "payload": {
                    "entityType": "role",
                    "identity": {
                        "semanticId": "role-operator",
                        "opaqueId": "opaque-role-operator",
                        "name": "Operator",
                    },
                    "snapshot": {"title": "Operator"},
                    "relationships": {},
                    "metadata": {"source": "salmon", "author": "nextlens"},
                },
            }
        ],
        update_id="update-apply-001",
    )

    result = DOWNSTREAM.apply_landscape_update(tmp_path, proposal)

    assert result.status == "pass"
    assert result.derived_graph_ref == (tmp_path / "derived" / "graph.json").as_posix()
    assert result.derived_graph_authoritative is False
    target_path = tmp_path / "landscape" / "role" / "role-operator.yaml"
    assert target_path.exists()
    payload = yaml.safe_load(target_path.read_text(encoding="utf-8"))
    assert payload["identity"]["semanticId"] == "role-operator"
    update_path = tmp_path / ".nextlens" / "landscape-updates" / "update-update-apply-001.yaml"
    assert update_path.exists()
    stored_update = yaml.safe_load(update_path.read_text(encoding="utf-8"))
    assert stored_update["status"] == "applied"
    assert (tmp_path / "derived" / "graph.json").exists()


def test_apply_landscape_update_rejects_disallowed_target(tmp_path: Path) -> None:
    proposal = DOWNSTREAM.build_landscape_update_proposal(
        source_refs={"packetRef": "packet-123"},
        updates=[
            {
                "target": "../secrets.yaml",
                "changeType": "update",
                "rationale": "Should not write outside landscape.",
                "authority": "validation",
                "payload": {"value": "nope"},
            }
        ],
        update_id="update-unsafe",
    )

    result = DOWNSTREAM.apply_landscape_update(tmp_path, proposal)

    assert result.status == "fail"
    assert "landscape" in (result.error or "")
