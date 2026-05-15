from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import sys

import yaml


MODULE_PATH = Path(__file__).resolve().parent.parent / "salmon_persistence.py"
SPEC = importlib.util.spec_from_file_location("nextlens_salmon_persistence", MODULE_PATH)
SALMON_PERSISTENCE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = SALMON_PERSISTENCE
SPEC.loader.exec_module(SALMON_PERSISTENCE)


def test_persist_salmon_event_writes_event_yaml_with_metadata(tmp_path: Path) -> None:
    result = SALMON_PERSISTENCE.persist_salmon_event(
        tmp_path,
        _event("created", "feature_scope_change"),
        packet_id="packet-123",
        persisted_by="tester",
        now_factory=lambda: datetime(2026, 5, 14, 12, 34, 56, tzinfo=timezone.utc),
    )

    expected_path = tmp_path / ".nextlens" / "salmon" / "packet-123" / f"{'0' * 64}.yaml"
    assert result.status == "pass"
    assert result.path == expected_path
    assert expected_path.exists()
    payload = yaml.safe_load(expected_path.read_text(encoding="utf-8"))
    assert payload["_metadata"]["persistedAt"] == "2026-05-14T12:34:56Z"
    assert payload["_metadata"]["persistedBy"] == "tester"
    assert len(payload["_metadata"]["fileChecksum"]) == 64
    assert result.evidence_event["eventCount"] == 1
    assert result.evidence_event["routingDecisions"] == [{"status": "created", "targetRef": "target/ref"}]


def test_persist_salmon_event_cleans_temp_file_when_atomic_replace_fails(tmp_path: Path) -> None:
    def fail_replace(source: str, target: str) -> None:
        raise PermissionError(f"cannot replace {target}")

    result = SALMON_PERSISTENCE.persist_salmon_event(
        tmp_path,
        _event("created", "feature_scope_change"),
        packet_id="packet-123",
        replace_fn=fail_replace,
    )

    event_dir = tmp_path / ".nextlens" / "salmon" / "packet-123"
    assert result.status == "fail"
    assert "cannot replace" in result.error
    assert not (event_dir / f"{'0' * 64}.yaml").exists()
    assert list(event_dir.glob("*.tmp")) == []


def test_write_salmon_summary_counts_events_by_status_and_impact(tmp_path: Path) -> None:
    events = [
        _event("created", "feature_scope_change"),
        _event("merged", "feature_scope_change"),
        _event("duplicate_ignored", "bmad_correct_course_required"),
    ]

    path = SALMON_PERSISTENCE.write_salmon_summary(
        tmp_path,
        packet_id="packet-123",
        run_id="run-1",
        events=events,
    )

    summary = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert path == tmp_path / ".nextlens" / "salmon-summary-packet-123.yaml"
    assert summary["run_id"] == "run-1"
    assert summary["packet_id"] == "packet-123"
    assert summary["events_created"] == 1
    assert summary["events_merged"] == 1
    assert summary["duplicates_ignored"] == 1
    assert summary["impact_distribution"]["feature_scope_change"] == 2
    assert summary["impact_distribution"]["bmad_correct_course_required"] == 1
    assert summary["routing_results"] == {"created": 1, "merged": 1, "ignored": 1}


def test_build_salmon_summary_includes_all_impact_levels_even_when_zero() -> None:
    summary = SALMON_PERSISTENCE.build_salmon_summary(packet_id="packet-123", run_id="run-1", events=[])

    assert set(summary["impact_distribution"]) == set(SALMON_PERSISTENCE.IMPACT_LEVELS)
    assert all(value == 0 for value in summary["impact_distribution"].values())


def _event(status: str, impact_level: str) -> dict[str, object]:
    return {
        "id": "event-1",
        "dedupFingerprint": "0" * 64,
        "discovery": {"impactLevel": impact_level},
        "routingResult": {"status": status, "targetRef": "target/ref"},
    }