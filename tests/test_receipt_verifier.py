from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPTS = REPO_ROOT / "skills" / "bul-verify-receipt" / "scripts"
if str(VERIFY_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(VERIFY_SCRIPTS))

from verify_receipt import verify_receipt, write_report_atomic


def load_json(relative: str) -> dict:
    return json.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))


def test_valid_receipt_passes_with_non_effects_label() -> None:
    result = verify_receipt(
        load_json("evals/bul-verify-receipt/files/valid-receipt.json"),
        load_json("evals/bul-verify-receipt/files/run-metadata.json"),
    )
    assert result["status"] == "pass"
    assert result["runValid"] is True
    assert result["label"] == "Non-effects verified"
    assert result["checkedFiles"]["count"] == 3


def test_false_graph_receipt_fails_with_evidence() -> None:
    result = verify_receipt(
        load_json("evals/bul-verify-receipt/files/false-graph-receipt.json"),
        load_json("evals/bul-verify-receipt/files/false-graph-run-metadata.json"),
    )
    assert result["status"] == "fail"
    assert result["runValid"] is False
    assert result["label"] == "Receipt mismatch detected"
    assert any(error.get("evidence", {}).get("category") == "graph" for error in result["hardBlockers"])
    assert any(error["code"] == "falseReceiptClaim" for error in result["hardBlockers"])


def test_forbidden_written_files_are_checked_even_with_benign_changed_files() -> None:
    receipt = load_json("evals/bul-verify-receipt/files/valid-receipt.json")
    metadata = load_json("evals/bul-verify-receipt/files/run-metadata.json")
    metadata["writtenFiles"] = [{"path": "docs/derived-graph/graph.json", "kind": "file"}]
    metadata["changedFiles"] = [{"path": "docs/bottom-up-lens/benign.json", "kind": "file"}]
    receipt["writtenFiles"] = metadata["writtenFiles"]
    receipt["changedFiles"] = metadata["changedFiles"]
    result = verify_receipt(receipt, metadata)
    assert result["status"] == "fail"
    assert any(error["code"] == "forbiddenChangedFile" for error in result["hardBlockers"])


def test_non_effect_claims_must_all_be_present_and_false() -> None:
    receipt = load_json("evals/bul-verify-receipt/files/valid-receipt.json")
    metadata = load_json("evals/bul-verify-receipt/files/run-metadata.json")
    receipt["nonEffects"]["governancePublished"] = True
    del receipt["nonEffects"]["releaseCloneWritten"]
    result = verify_receipt(receipt, metadata)
    assert result["status"] == "fail"
    assert any(error["code"] == "forbiddenNonEffectClaim" for error in result["hardBlockers"])
    assert any(error["code"] == "missingNonEffectClaim" for error in result["hardBlockers"])


def test_missing_metadata_fails_closed() -> None:
    result = verify_receipt(
        load_json("evals/bul-verify-receipt/files/valid-receipt.json"),
        load_json("evals/bul-verify-receipt/files/missing-metadata.json"),
    )
    assert result["status"] == "fail"
    assert any(error["code"] == "missingChangedFileManifest" for error in result["hardBlockers"])


def test_verifier_does_not_mutate_inputs_and_report_guard(tmp_path: Path) -> None:
    receipt_path = REPO_ROOT / "evals" / "bul-verify-receipt" / "files" / "valid-receipt.json"
    metadata_path = REPO_ROOT / "evals" / "bul-verify-receipt" / "files" / "run-metadata.json"
    before = hashlib.sha256(receipt_path.read_bytes() + metadata_path.read_bytes()).hexdigest()
    result = verify_receipt(load_json("evals/bul-verify-receipt/files/valid-receipt.json"), load_json("evals/bul-verify-receipt/files/run-metadata.json"))
    after = hashlib.sha256(receipt_path.read_bytes() + metadata_path.read_bytes()).hexdigest()
    assert result["status"] == "pass"
    assert before == after

    reports_root = tmp_path / "reports"
    report_path = reports_root / "receipt-report.json"
    assert write_report_atomic(result, report_path, reports_root) == report_path
    assert report_path.exists()

    outside_report = tmp_path / "outside" / "receipt-report.json"
    try:
        write_report_atomic(result, outside_report, reports_root)
    except ValueError as exc:
        assert "outside configured" in str(exc) or "outside" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("report guard should reject outside report paths")
