from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CREATE_SCRIPTS = REPO_ROOT / "skills" / "bul-create-packet" / "scripts"
VALIDATE_SCRIPTS = REPO_ROOT / "skills" / "bul-validate-packet" / "scripts"
for path in (CREATE_SCRIPTS, VALIDATE_SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from read_only_consumer import consume_packet_state
from validate_module import validate_module
from validate_packet import validate_packet


def load_json(relative: str) -> dict:
    return json.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))


def test_marketplace_metadata_is_bottom_up_lens_only() -> None:
    manifest = load_json(".claude-plugin/marketplace.json")
    assert manifest["name"] == "Bottom-Up LENS"
    assert manifest["owner"]["name"] == "NextLens Maintainers"
    assert manifest["license"] == "MIT"
    assert "bottom-up-lens" in manifest["keywords"]
    plugin = manifest["plugins"][0]
    assert plugin["name"] == "bul"
    assert plugin["displayName"] == "Bottom-Up LENS"
    assert plugin["version"] == "1.0.0"
    assert plugin["module"] == {"name": "Bottom-Up LENS", "code": "bul", "moduleVersion": "1.0.0"}
    assert set(plugin["skills"]) == {"skills/bul-setup", "skills/bul-create-packet", "skills/bul-validate-packet", "skills/bul-verify-receipt"}
    text = json.dumps(manifest).lower()
    forbidden = ["top-down bridge", "doctor-validation", "salmon-routing", "governance installation", "branch topology"]
    for marker in forbidden:
        assert marker not in text


def test_readme_and_command_docs_include_required_labels_and_boundaries() -> None:
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8") + "\n" + (REPO_ROOT / "docs" / "commands.md").read_text(encoding="utf-8")
    for required in [
        "Start from one feature",
        "bul-setup",
        "bul-create-packet",
        "bul-validate-packet",
        "bul-verify-receipt",
        "packet_output_path",
        "reports_output_path",
        "Feature packet is valid",
        "Feature packet is not ready yet",
        "Ready for BMAD: not yet",
        "Ready for BMAD: ready",
        "Non-effects verified",
        "Receipt mismatch detected",
        "CREATE PACKET",
        "--confirm",
    ]:
        assert required in text
    assert "does not publish governance" in text
    assert "depend on current NextLens top-down runtime" in text


def test_eval_definitions_are_parseable_and_have_assertions() -> None:
    eval_files = [
        "evals/bul-create-packet/evals.json",
        "evals/bul-validate-packet/evals.json",
        "evals/bul-verify-receipt/evals.json",
    ]
    for relative in eval_files:
        data = load_json(relative)
        assert data["schemaVersion"] == "bul.eval-suite.v1"
        assert data["evals"], relative
        for eval_case in data["evals"]:
            assert eval_case["assertions"], eval_case
    triggers = load_json("evals/bul-create-packet/triggers.json")
    assert any("Start from one feature" in item["query"] for item in triggers["positive"])
    negative_queries = "\n".join(item["query"] for item in triggers["negative"])
    for marker in ["feature.yaml", "governance", "constitution", "branch topology", "top-down doctor"]:
        assert marker in negative_queries


def test_golden_examples_synchronize_with_validator_and_verifier_keys() -> None:
    valid = validate_packet(load_json("evals/bul-validate-packet/files/valid-packet.json"))
    not_ready = validate_packet(load_json("evals/bul-validate-packet/files/valid-not-bmad-ready.json"))
    assert set(valid) >= {"packetValid", "bmadReady", "hardBlockers", "advisories"}
    assert valid["packetValid"]["status"] == "pass"
    assert not_ready["packetValid"]["status"] == "pass"
    assert not_ready["bmadReady"]["status"] == "fail"


def test_read_only_consumer_contract_does_not_mutate_or_promote() -> None:
    packet = load_json("evals/bul-validate-packet/files/valid-packet.json")
    validation = validate_packet(packet)
    state = consume_packet_state(packet, validation)
    assert state["readOnly"] is True
    assert state["mutatesPacketState"] is False
    assert state["promotesTopology"] is False
    assert state["packetValid"]["status"] == "pass"
    assert state["bmadReady"]["status"] == "pass"


def test_release_traceability_and_module_validation_contract() -> None:
    release = (REPO_ROOT / "docs" / "release-readiness.md").read_text(encoding="utf-8")
    assert "product brief, research, brainstorm, PRD, and UX artifacts together satisfy the business-plan equivalent" in release
    assert "architecture.md` satisfies the tech-plan equivalent" in release
    result = validate_module(REPO_ROOT, run_tests=False, run_evals=True)
    assert result["status"] == "pass", result["errors"]
    assert result["evals"]["executed"] >= 8
    assert "Marketplace metadata complete" in result["releaseChecklist"]
