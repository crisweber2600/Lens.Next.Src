from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).resolve().parent.parent / "salmon_deduplication.py"
SPEC = importlib.util.spec_from_file_location("nextlens_salmon_deduplication", MODULE_PATH)
SALMON_DEDUPLICATION = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = SALMON_DEDUPLICATION
SPEC.loader.exec_module(SALMON_DEDUPLICATION)


def test_generate_salmon_fingerprint_is_deterministic_and_normalized() -> None:
    first = SALMON_DEDUPLICATION.generate_salmon_fingerprint(
        issue_class="Feature Scope Change",
        target_stable_id="Feature-Password-Recovery",
        canonical_path="Docs\\Feature\\Packet.JSON",
        issue_description="  Adjacent journey included.  ",
    )
    second = SALMON_DEDUPLICATION.generate_salmon_fingerprint(
        issue_class="feature_scope_change",
        target_stable_id="feature-password-recovery",
        canonical_path="docs/feature/packet.json",
        issue_description="adjacent   journey included.",
    )

    assert first.fingerprint == second.fingerprint
    assert first.message_hash == second.message_hash
    assert len(first.fingerprint) == 64
    assert first.canonical_path == "docs/feature/packet.json"


def test_deduplicate_salmon_event_persists_new_event_and_index(tmp_path: Path) -> None:
    event = _event(source_id="feature-scope")

    result = SALMON_DEDUPLICATION.deduplicate_salmon_event(
        tmp_path,
        event,
        now_factory=lambda: datetime(2026, 5, 14, 12, 34, 56, tzinfo=timezone.utc),
    )

    index_path = tmp_path / ".nextlens" / "salmon" / "fingerprints.json"
    assert result.status == "new"
    assert result.event["routingResult"]["status"] == "created"
    assert result.event_path.exists()
    assert index_path.exists()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["fingerprints"][result.fingerprint]["eventId"] == event["id"]
    assert index["fingerprints"][result.fingerprint]["sources"] == ["doctor:feature-scope"]


def test_deduplicate_salmon_event_ignores_same_source_duplicate(tmp_path: Path) -> None:
    event = _event(source_id="feature-scope")
    first = SALMON_DEDUPLICATION.deduplicate_salmon_event(tmp_path, event)

    duplicate = SALMON_DEDUPLICATION.deduplicate_salmon_event(tmp_path, dict(event))

    assert duplicate.status == "duplicate_ignored"
    assert duplicate.fingerprint == first.fingerprint
    assert duplicate.event_path == first.event_path
    assert duplicate.evidence_event["status"] == "duplicate_ignored"


def test_deduplicate_salmon_event_merges_new_source_into_existing_event(tmp_path: Path) -> None:
    first = SALMON_DEDUPLICATION.deduplicate_salmon_event(tmp_path, _event(source_id="feature-scope"))
    second_event = _event(event_id="550e8400-e29b-41d4-a716-446655440001", source_id="reviewer-a")
    second_event["source"] = {"type": "review", "sourceId": "reviewer-a"}

    merged = SALMON_DEDUPLICATION.deduplicate_salmon_event(tmp_path, second_event)

    assert merged.status == "merged"
    assert merged.event_path == first.event_path
    assert merged.event["routingResult"]["status"] == "merged"
    assert merged.event["sources"] == [
        {"type": "doctor", "sourceId": "feature-scope"},
        {"type": "review", "sourceId": "reviewer-a"},
    ]
    index = json.loads(SALMON_DEDUPLICATION.fingerprint_index_path(tmp_path).read_text(encoding="utf-8"))
    assert index["fingerprints"][merged.fingerprint]["sources"] == [
        "doctor:feature-scope",
        "review:reviewer-a",
    ]


def _event(*, event_id: str = "550e8400-e29b-41d4-a716-446655440000", source_id: str) -> dict[str, object]:
    return {
        "schemaVersion": "1.0",
        "id": event_id,
        "raisedFrom": "doctor-check",
        "source": {"type": "doctor", "sourceId": source_id},
        "discovery": {
            "issueClass": "feature_scope_change",
            "canonicalPath": "docs/feature/packet.json",
            "issueDescription": "Selected Feature scope includes an adjacent journey.",
            "impactedFeature": "feature-password-recovery",
            "impactLevel": "feature_scope_change",
        },
        "impactedNodes": {
            "features": ["feature-password-recovery"],
            "journeys": ["journey-account-recovery"],
            "outcomes": ["outcome-reduced-ambiguity"],
            "roles": ["role-operator"],
            "operatingLoops": [],
            "capabilities": [],
            "bmadArtifacts": ["prd.md"],
        },
        "severity": "blocking",
        "recommendedAction": {"type": "block_packet", "details": "Remove adjacent journey from scope."},
        "createdAt": "2026-05-14T12:34:56Z",
        "routingResult": {"status": "created", "targetRef": "docs/.nextlens/salmon/events/event.json"},
    }