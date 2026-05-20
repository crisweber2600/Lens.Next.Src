from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATE_SCRIPTS = REPO_ROOT / "skills" / "bul-validate-packet" / "scripts"
if str(VALIDATE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(VALIDATE_SCRIPTS))

from validation_contract import ERROR_SHAPE_KEYS, rule_inventory, validate_packet_dict
from validate_packet import validate_packet


def load_json(relative: str) -> dict:
    return json.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))


def test_rule_inventory_covers_required_categories_and_error_shape() -> None:
    categories = {rule["category"] for rule in rule_inventory()}
    assert {
        "schemaVersion",
        "sourceMode",
        "identity",
        "selectedFeature",
        "scope",
        "constraints",
        "assumptions",
        "provenance",
        "receiptReference",
        "topology",
        "nonEffects",
    } <= categories
    errors = validate_packet_dict({})
    assert errors
    for error in errors:
        assert tuple(error.keys()) == ERROR_SHAPE_KEYS


def test_no_jsonschema_dependency_or_import() -> None:
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "jsonschema" not in requirements
    for script in VALIDATE_SCRIPTS.glob("*.py"):
        text = script.read_text(encoding="utf-8").lower()
        assert "import jsonschema" not in text
        assert "from jsonschema" not in text
        assert "dependencies = [\"jsonschema" not in text


def test_valid_packet_passes_packet_and_bmad_readiness() -> None:
    result = validate_packet(load_json("evals/bul-validate-packet/files/valid-packet.json"))
    assert result["packetValid"]["status"] == "pass"
    assert result["packetValid"]["label"] == "Feature packet is valid"
    assert result["bmadReady"]["status"] == "pass"
    assert result["bmadReady"]["label"] == "Ready for BMAD: ready"


def test_valid_not_bmad_ready_keeps_packet_validity_separate() -> None:
    result = validate_packet(load_json("evals/bul-validate-packet/files/valid-not-bmad-ready.json"))
    assert result["packetValid"]["status"] == "pass"
    assert result["bmadReady"]["status"] == "fail"
    assert result["bmadReady"]["label"] == "Ready for BMAD: not yet"
    assert any(reason["code"] == "readinessWeakAcceptanceCriteria" for reason in result["bmadReady"]["reasons"])


def test_invalid_fixtures_fail_with_structured_errors() -> None:
    cases = {
        "evals/bul-validate-packet/files/invalid-multi-candidate.json": "invalidCandidateSelection",
        "evals/bul-validate-packet/files/invalid-missing-out-of-scope.json": "missingExplicitOutOfScope",
        "evals/bul-validate-packet/files/invalid-promoted-topology.json": "topologyNotUnpromoted",
        "evals/bul-validate-packet/files/invalid-inferred-context.json": "forbiddenContextInference",
    }
    for relative, expected_code in cases.items():
        result = validate_packet(load_json(relative))
        assert result["packetValid"]["status"] == "fail", relative
        codes = {error["code"] for error in result["hardBlockers"]}
        assert expected_code in codes
        for error in result["hardBlockers"]:
            assert set(error) == set(ERROR_SHAPE_KEYS)


def test_validate_packet_is_read_only(tmp_path: Path) -> None:
    source = REPO_ROOT / "evals" / "bul-validate-packet" / "files" / "valid-packet.json"
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    result = validate_packet(load_json("evals/bul-validate-packet/files/valid-packet.json"))
    after = hashlib.sha256(source.read_bytes()).hexdigest()
    assert result["packetValid"]["status"] == "pass"
    assert before == after
