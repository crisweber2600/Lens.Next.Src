from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CREATE_SCRIPTS = REPO_ROOT / "skills" / "bul-create-packet" / "scripts"
if str(CREATE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(CREATE_SCRIPTS))

from create_packet import (
    CONFIRMATION_TOKEN,
    STAGE_LABELS,
    cancel_result,
    compose_packet_from_json,
    confirmation_allows_write,
    display_context,
    ensure_no_duplicate,
    render_preview,
    resume_run_state,
    save_run_state,
    select_candidate,
    write_accepted_packet,
)


def load_input() -> dict:
    return json.loads((REPO_ROOT / "evals" / "bul-create-packet" / "files" / "headless-valid-input.json").read_text(encoding="utf-8"))


def test_stage_labels_and_context_display_block_ambient_inference(tmp_path: Path) -> None:
    assert STAGE_LABELS == [
        "context-intake",
        "candidate-selection",
        "local-sufficiency",
        "scope-boundary",
        "preview",
        "confirmation",
        "write",
        "receipt",
    ]
    context = {"contextSource": "operator-paste", "operatorIntent": "Start from one feature"}
    result = display_context(context, tmp_path / "packets", tmp_path / "reports")
    assert result["status"] == "pass"
    assert "packetOutputPath" in result
    blocked = display_context({"contextSource": "", "operatorIntent": "", "inferredFromBranch": True}, tmp_path / "packets", tmp_path / "reports")
    assert blocked["status"] == "fail"
    assert blocked["blockedInferenceSources"] == ["branch"]


def test_candidate_selection_requires_exactly_one_and_defers_unranked_notes() -> None:
    candidates = [{"id": "a", "title": "A"}, {"id": "b", "title": "B", "rank": 1}]
    selected, errors = select_candidate(candidates, "a")
    assert not errors
    assert [item["selected"] for item in selected] == [True, False]
    assert "rank" not in selected[1]
    assert "unranked" in selected[1]["deferredNote"]
    _, missing_errors = select_candidate(candidates, "missing")
    assert missing_errors[0]["code"] == "candidateSelectionRequired"


def test_preview_confirmation_and_no_write_paths(tmp_path: Path) -> None:
    packet = compose_packet_from_json(load_input())
    preview = render_preview(packet, tmp_path / "packets", tmp_path / "reports")
    assert "Selected feature: Safe local export" in preview
    assert "Confirmation token: CREATE PACKET" in preview
    assert "Will not write:" in preview
    assert confirmation_allows_write(interactive_token=CONFIRMATION_TOKEN)
    assert not confirmation_allows_write(interactive_token="")
    assert not confirmation_allows_write(interactive_token="CREATE  PACKET")
    assert not confirmation_allows_write(headless=True, confirm_flag=False)
    assert confirmation_allows_write(headless=True, confirm_flag=True)
    cancelled = cancel_result("operator cancelled")
    assert cancelled["acceptedPacketWritten"] is False
    assert "No packet" in cancelled["message"]


def test_atomic_write_and_receipt_verification(tmp_path: Path) -> None:
    packet = compose_packet_from_json(load_input())
    result = write_accepted_packet(packet, tmp_path / "packets")
    assert result["status"] == "pass"
    assert result["acceptedPacketWritten"] is True
    for key in ("packetPath", "runMetadataPath", "receiptPath"):
        path = Path(result[key])
        assert path.exists()
        assert path.is_relative_to((tmp_path / "packets").resolve())
    receipt = json.loads(Path(result["receiptPath"]).read_text(encoding="utf-8"))
    assert receipt["status"] == "verified"
    assert result["verification"]["status"] == "pass"


def test_duplicate_requires_explicit_resolution(tmp_path: Path) -> None:
    packet = compose_packet_from_json(load_input())
    first = write_accepted_packet(packet, tmp_path / "packets")
    assert first["status"] == "pass"
    duplicate = ensure_no_duplicate(tmp_path / "packets", packet)
    assert duplicate["status"] == "fail"
    assert "Duplicate packet attempt" in duplicate["message"]
    original_packet_id = packet["packetId"]
    resolved = ensure_no_duplicate(tmp_path / "packets", packet, resolution="new-packet")
    assert resolved["status"] == "pass"
    assert packet["packetId"] != original_packet_id


def test_run_state_cache_is_safe_and_resume_revalidates(tmp_path: Path) -> None:
    run_state_path = tmp_path / "packets" / "run-state.json"
    result = save_run_state(run_state_path, {"stage": "write", "packetId": "p1", "selectedCandidateId": "c1"}, [tmp_path / "packets"])
    assert result["status"] == "pass"
    data = json.loads(run_state_path.read_text(encoding="utf-8"))
    assert data["cacheOnly"] is True
    assert data["notTopologyTruth"] is True
    resumed = resume_run_state(run_state_path)
    assert resumed["status"] == "pass"
    assert resumed["resumeStage"] == "preview"
    assert resumed["requiresRevalidationBeforeWrite"] is True

    secret_result = save_run_state(tmp_path / "packets" / "bad-state.json", {"stage": "preview", "token": "abc"}, [tmp_path / "packets"])
    assert secret_result["status"] == "fail"
    assert secret_result["pathGuard"]["category"] == "secret-scan"
