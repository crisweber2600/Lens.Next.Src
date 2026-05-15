from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).resolve().parent.parent / "traceability_index.py"
SPEC = importlib.util.spec_from_file_location("nextlens_traceability_index", MODULE_PATH)
TRACEABILITY_INDEX = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = TRACEABILITY_INDEX
SPEC.loader.exec_module(TRACEABILITY_INDEX)


def test_write_traceability_index_creates_markdown_file(tmp_path: Path) -> None:
    result = TRACEABILITY_INDEX.write_traceability_index(tmp_path, [_bundle("run-11111111", "packet-1")])

    assert result.status == "pass"
    assert result.path == tmp_path / ".nextlens" / "traceability-index.md"
    assert result.path.read_text(encoding="utf-8") == result.markdown
    assert result.markdown.startswith("# NextLens Traceability Index")


def test_recent_runs_table_contains_required_columns_and_links() -> None:
    markdown = TRACEABILITY_INDEX.render_traceability_index([_bundle("run-11111111", "packet-1")])

    assert "| Run ID | Timestamp | Feature Selected | Doctor Status | Result | Evidence | Packet |" in markdown
    assert "| run-1111 | 2026-05-14T10:00:00Z | feature-1: Feature One | pass | advisory |" in markdown
    assert "[evidence](docs/.nextlens/evidence-packet-1.yaml)" in markdown
    assert "[packet](docs/.nextlens/packet-packet-1.json)" in markdown


def test_quick_links_use_latest_run_when_index_is_updated() -> None:
    older = _bundle("run-11111111", "packet-1", completed_at="2026-05-14T10:00:00Z")
    newer = _bundle("run-22222222", "packet-2", completed_at="2026-05-14T11:00:00Z")

    markdown = TRACEABILITY_INDEX.render_traceability_index([older, newer])

    assert "| run-2222 | 2026-05-14T11:00:00Z |" in markdown
    assert "| run-1111 | 2026-05-14T10:00:00Z |" in markdown
    quick_links = markdown.split("## Quick Links", 1)[1].split("## Lineage", 1)[0]
    assert "evidence-packet-2.yaml" in quick_links
    assert "packet-packet-2.json" in quick_links
    assert "salmon-summary-packet-2.yaml" in quick_links


def test_lineage_section_displays_source_to_packet_tree() -> None:
    markdown = TRACEABILITY_INDEX.render_traceability_index([_bundle("run-11111111", "packet-1")])

    assert "System -> Roles -> Outcomes -> Journeys -> Feature -> Packet" in markdown
    assert "- system-1: System One" in markdown
    assert "  -> role-1: Role One" in markdown
    assert "    -> outcome-1: Outcome One" in markdown
    assert "      -> journey-1: Journey One" in markdown
    assert "        -> feature-1: Feature One" in markdown
    assert "          -> packet-1: docs/.nextlens/packet-packet-1.json" in markdown


def test_key_decisions_include_sufficiency_ranking_confirmations_and_doctor_summary() -> None:
    markdown = TRACEABILITY_INDEX.render_traceability_index([_bundle("run-11111111", "packet-1")])

    assert "- Context sufficiency: ready_with_warnings (ask_for_confirmation); warnings: risks are sparse" in markdown
    assert "- Ranking: selected feature-1 at score 91; tie break applied: yes" in markdown
    assert "- Operator confirmations: final-confirmation=yes" in markdown
    assert "- Doctor findings: status=pass, blocking=0, advisory=1, informational=2" in markdown


def test_blocked_result_when_errors_or_blocking_findings_are_present() -> None:
    bundle = _bundle("run-11111111", "packet-1")
    bundle["records"]["doctor_validation"]["blocking_findings"] = 1

    markdown = TRACEABILITY_INDEX.render_traceability_index([bundle])

    assert "| run-1111 | 2026-05-14T10:00:00Z | feature-1: Feature One | pass | blocked |" in markdown


def _bundle(run_id: str, packet_id: str, *, completed_at: str = "2026-05-14T10:00:00Z") -> dict[str, object]:
    return {
        "run": {
            "run_id": run_id,
            "packet_id": packet_id,
            "started_at": "2026-05-14T09:59:00Z",
            "completed_at": completed_at,
            "duration_seconds": 60.0,
        },
        "records": {
            "context_sufficiency": {
                "status": "ready_with_warnings",
                "recommendation": "ask_for_confirmation",
                "warnings": ["risks are sparse"],
            },
            "feature_ranking": {
                "top_candidate_selected": {"id": "feature-1", "name": "Feature One", "score": 91},
                "tie_break_applied": "yes",
            },
            "doctor_validation": {
                "status": "pass",
                "blocking_findings": 0,
                "advisory_findings": 1,
                "informational_findings": 2,
            },
            "salmon_routing": {
                "event_summary_path": f"docs/.nextlens/salmon-summary-{packet_id}.yaml",
            },
        },
        "artifacts": {
            "evidence_bundle_yaml": f"docs/.nextlens/evidence-{packet_id}.yaml",
            "packet_json": f"docs/.nextlens/packet-{packet_id}.json",
            "doctor_report_jsonl": "docs/.nextlens/doctor-run.jsonl",
        },
        "lineage": {
            "system": {"id": "system-1", "name": "System One"},
            "roles": [{"id": "role-1", "name": "Role One"}],
            "outcomes": [{"id": "outcome-1", "name": "Outcome One"}],
            "journeys": [{"id": "journey-1", "name": "Journey One"}],
        },
        "operator_confirmations": [
            {"stage_name": "final-confirmation", "confirmation": "yes", "timestamp": "2026-05-14T09:59:59Z"}
        ],
        "errors_and_warnings": {"errors": [], "warnings": []},
    }