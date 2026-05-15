from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import sys
from uuid import UUID


MODULE_PATH = Path(__file__).resolve().parent.parent / "evidence_collector.py"
SPEC = importlib.util.spec_from_file_location("nextlens_evidence_collector", MODULE_PATH)
EVIDENCE_COLLECTOR = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = EVIDENCE_COLLECTOR
SPEC.loader.exec_module(EVIDENCE_COLLECTOR)


def test_collector_initializes_run_record_with_empty_stage_records() -> None:
    collector = EVIDENCE_COLLECTOR.EvidenceCollector(
        command_arguments={"mode": "new", "context": "context.yaml"},
        config={"docs_path": "docs/feature"},
        uuid_factory=lambda: UUID("00000000-0000-4000-8000-000000000001"),
        now_factory=lambda: datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc),
    )

    assert collector.run_record() == {
        "run_id": "00000000-0000-4000-8000-000000000001",
        "started_at": "2026-05-14T10:00:00Z",
        "stage_records": [],
    }
    command_point = collector.collection_points["command_arguments_and_config"][0]
    assert command_point["payload"]["command_arguments"]["mode"] == "new"
    assert command_point["payload"]["config"]["docs_path"] == "docs/feature"


def test_record_stage_captures_summaries_duration_warnings_and_diagnostics() -> None:
    collector = EVIDENCE_COLLECTOR.EvidenceCollector(
        run_id="run-1",
        now_factory=lambda: datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc),
    )

    record = collector.record_stage(
        "context-sufficiency",
        status="warning",
        input_summary={"items_processed": 8, "context_source": "context.yaml"},
        output_summary={"decision": "ready_with_warnings", "blocks": 0},
        warnings=["risks are sparse"],
        diagnostics=["gate risks_captured returned advisory"],
        started_at=datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 5, 14, 10, 0, 3, tzinfo=timezone.utc),
        collection_point="context_sufficiency_check",
    )

    assert record["stage_name"] == "context-sufficiency"
    assert record["status"] == "warning"
    assert record["input_summary"]["items_processed"] == 8
    assert record["output_summary"]["decision"] == "ready_with_warnings"
    assert record["duration_seconds"] == 3.0
    assert record["warnings"] == ["risks are sparse"]
    assert record["diagnostics"] == ["gate risks_captured returned advisory"]
    assert collector.collection_points["context_sufficiency_check"][0]["payload"] == record


def test_manifest_exposes_all_required_collection_points_for_bundle_assembly() -> None:
    collector = EVIDENCE_COLLECTOR.EvidenceCollector(run_id="run-1")
    collector.record_collection_point("context_intake_and_parsing", {"entities_loaded": 12})
    collector.record_collection_point("landscape_state_reconstruction", {"entities_loaded": {"role": 2}})
    collector.record_collection_point("feature_ranking_and_tie_break", {"candidates_evaluated": 3})
    collector.record_collection_point("operator_confirmations", {"confirmed": True})
    collector.record_collection_point("doctor_validation_results", {"checks_run": 7})
    collector.record_collection_point("packet_emission_result", {"packet_emitted": True})
    collector.record_collection_point("salmon_routing_results", {"events_created": 1})

    manifest = collector.build_manifest(completed_at="2026-05-14T10:00:10Z")

    assert set(manifest["collection_points"]) == set(EVIDENCE_COLLECTOR.EVIDENCE_COLLECTION_POINTS)
    assert "packet_emission_result" in manifest["collection_points_present"]
    assert "salmon_routing_results" in manifest["collection_points_present"]
    assert manifest["available_for_bundle_assembly"] is True


def test_record_error_adds_exception_collection_point() -> None:
    collector = EVIDENCE_COLLECTOR.EvidenceCollector(run_id="run-1")

    record = collector.record_error(ValueError("bad packet"), stage_name="emit", diagnostics={"packet_id": "p1"})

    assert record["stage_name"] == "emit"
    assert record["error_type"] == "ValueError"
    assert record["message"] == "bad packet"
    assert record["diagnostics"] == {"packet_id": "p1"}
    assert collector.collection_points["errors_and_exceptions"][0]["payload"] == record


def test_invalid_status_and_unknown_collection_point_fail_clearly() -> None:
    collector = EVIDENCE_COLLECTOR.EvidenceCollector(run_id="run-1")

    try:
        collector.record_stage("context-intake", status="blocked")
    except ValueError as exc:
        assert "invalid evidence status" in str(exc)
    else:
        raise AssertionError("invalid stage status should fail")

    try:
        collector.record_collection_point("unknown", {})
    except ValueError as exc:
        assert "unknown evidence collection point" in str(exc)
    else:
        raise AssertionError("unknown collection point should fail")