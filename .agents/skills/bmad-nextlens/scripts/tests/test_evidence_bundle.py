from __future__ import annotations

import importlib.util
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


EVIDENCE_COLLECTOR = _load_module("nextlens_evidence_collector_for_bundle_tests", "evidence_collector.py")
EVIDENCE_BUNDLE = _load_module("nextlens_evidence_bundle", "evidence_bundle.py")


def test_generate_evidence_bundle_uses_packet_id_filename_and_writes_valid_yaml(tmp_path: Path) -> None:
    result = EVIDENCE_BUNDLE.generate_evidence_bundle(
        tmp_path,
        _manifest(),
        packet_id="packet-123",
    )

    assert result.status == "pass"
    assert result.path == tmp_path / ".nextlens" / "evidence-packet-123.yaml"
    assert yaml.safe_load(result.path.read_text(encoding="utf-8")) == result.bundle


def test_generate_evidence_bundle_falls_back_to_run_id_when_packet_missing(tmp_path: Path) -> None:
    result = EVIDENCE_BUNDLE.generate_evidence_bundle(tmp_path, _manifest())

    assert result.status == "pass"
    assert result.path == tmp_path / ".nextlens" / "evidence-run-1.yaml"
    assert result.bundle["run"]["packet_id"] is None


def test_build_evidence_bundle_populates_required_audit_sections(tmp_path: Path) -> None:
    manifest = _manifest()

    bundle = EVIDENCE_BUNDLE.build_evidence_bundle(tmp_path, manifest, packet_id="packet-123")

    assert bundle["run"] == {
        "run_id": "run-1",
        "packet_id": "packet-123",
        "started_at": "2026-05-14T10:00:00Z",
        "completed_at": "2026-05-14T10:00:05Z",
        "duration_seconds": 5.0,
    }
    records = bundle["records"]
    assert records["context_intake"]["context_loaded_from"] == "context.yaml"
    assert records["context_sufficiency"]["status"] == "ready_with_warnings"
    assert records["landscape_state"]["write_status"] == "success"
    assert records["feature_ranking"]["top_candidate_selected"]["id"] == "feature-1"
    assert records["doctor_validation"]["checks_run"] == 7
    assert records["graph_consistency"]["nodes_validated"] == 12
    assert records["packet_emission"]["idempotency_decision"] == "new"
    assert records["salmon_routing"]["events_created"] == 1
    assert bundle["operator_confirmations"] == [
        {"stage_name": "final-confirmation", "confirmation": "yes", "timestamp": "2026-05-14T10:00:03Z"}
    ]
    assert bundle["stage_records"][0]["stage_name"] == "context-intake"


def test_artifacts_include_self_reference_and_default_paths(tmp_path: Path) -> None:
    result = EVIDENCE_BUNDLE.generate_evidence_bundle(
        tmp_path,
        _manifest(),
        packet_id="packet-123",
        artifact_refs={"doctor_report_jsonl": "docs/.nextlens/doctor-run-1.jsonl"},
    )

    artifacts = result.bundle["artifacts"]
    assert artifacts["packet_json"] == str(tmp_path / ".nextlens" / "packet-packet-123.json")
    assert artifacts["doctor_report_jsonl"] == "docs/.nextlens/doctor-run-1.jsonl"
    assert artifacts["evidence_bundle_yaml"] == str(tmp_path / ".nextlens" / "evidence-packet-123.yaml")
    assert artifacts["salmon_events_directory"] == str(tmp_path / ".nextlens" / "salmon")
    assert artifacts["landscape_state_directory"] == str(tmp_path / "landscape")
    assert artifacts["derived_graph_json"] == str(tmp_path / "derived" / "graph.json")


def test_errors_and_warnings_are_preserved() -> None:
    bundle = EVIDENCE_BUNDLE.build_evidence_bundle(Path("docs/feature"), _manifest())

    assert bundle["errors_and_warnings"]["warnings"] == ["advisory finding"]
    assert bundle["errors_and_warnings"]["errors"][0]["message"] == "bad packet"
    assert bundle["errors_and_warnings"]["exception_traces"][0]["message"] == "bad packet"


def _manifest() -> dict[str, object]:
    collector = EVIDENCE_COLLECTOR.EvidenceCollector(
        run_id="run-1",
        now_factory=lambda: datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc),
    )
    collector.record_stage(
        "context-intake",
        status="pass",
        input_summary={"items_processed": 1},
        output_summary={"loaded": True},
        started_at="2026-05-14T10:00:00Z",
        ended_at="2026-05-14T10:00:01Z",
    )
    collector.record_collection_point(
        "context_intake_and_parsing",
        {
            "status": "pass",
            "context_loaded_from": "context.yaml",
            "schema_version_detected": "lens.topdown-context.v1",
            "context_entity_counts": {"systems": 1, "roles": 2, "outcomes": 3, "journeys": 4},
        },
    )
    collector.record_collection_point(
        "context_sufficiency_check",
        {
            "status": "ready_with_warnings",
            "gate_results": [{"gate_name": "risks_captured", "status": "warning", "value_if_applicable": 1}],
            "warnings": ["advisory finding"],
            "recommendation": "ask_for_confirmation",
        },
    )
    collector.record_collection_point(
        "landscape_state_reconstruction",
        {
            "status": "pass",
            "entities_loaded": {"system": 1, "role": 2},
            "write_attempted": "yes",
            "write_status": "success",
            "write_path": "docs/feature/landscape/system/system-1.yaml",
        },
    )
    collector.record_collection_point(
        "feature_ranking_and_tie_break",
        {
            "status": "pass",
            "candidates_evaluated": 3,
            "top_candidate_selected": {"id": "feature-1", "name": "Feature 1", "score": 94},
            "tie_break_applied": "yes",
            "tie_break_sequence": ["outcome_alignment"],
            "confirmation_given": "yes",
        },
    )
    collector.record_collection_point(
        "doctor_validation_results",
        {
            "status": "pass",
            "checks_run": 7,
            "blocking_findings": 0,
            "advisory_findings": 1,
            "informational_findings": 2,
            "doctor_report_path": "docs/.nextlens/doctor-run-1.jsonl",
        },
    )
    collector.record_collection_point(
        "graph_consistency_check",
        {
            "status": "pass",
            "consistency_checksum": "a" * 64,
            "nodes_validated": 12,
            "edges_validated": 18,
        },
    )
    collector.record_collection_point(
        "packet_emission_result",
        {
            "status": "success",
            "packet_id": "packet-123",
            "packet_path": "docs/.nextlens/packet-packet-123.json",
            "idempotency_token": "token-1",
            "idempotency_decision": "new",
        },
    )
    collector.record_collection_point(
        "salmon_routing_results",
        {
            "events_created": 1,
            "events_merged": 2,
            "duplicates_ignored": 3,
            "event_summary_path": "docs/.nextlens/salmon-summary-packet-123.yaml",
        },
    )
    collector.record_collection_point(
        "operator_confirmations",
        {"stage_name": "final-confirmation", "confirmation": "yes", "timestamp": "2026-05-14T10:00:03Z"},
    )
    collector.warnings.append("advisory finding")
    collector.record_error("bad packet", stage_name="emit")
    return collector.build_manifest(completed_at="2026-05-14T10:00:05Z")