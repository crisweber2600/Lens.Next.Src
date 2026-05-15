from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sys
import time

import yaml


MODULE_PATH = Path(__file__).resolve().parent.parent / "idempotency_store.py"
SPEC = importlib.util.spec_from_file_location("nextlens_idempotency_store", MODULE_PATH)
IDEMPOTENCY_STORE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = IDEMPOTENCY_STORE
SPEC.loader.exec_module(IDEMPOTENCY_STORE)


def _make_record(
    token: str,
    operation_type: str,
    parameters: dict[str, object],
    *,
    status: str = "pending",
    result: dict[str, object] | None = None,
    completed_at: str | None = None,
) -> object:
    return IDEMPOTENCY_STORE.IdempotencyTokenRecord(
        token=token,
        operation_type=operation_type,
        created_at="2026-05-14T23:00:00Z",
        request_digest=IDEMPOTENCY_STORE.build_request_digest(operation_type, parameters),
        status=status,
        completed_at=completed_at,
        result=result,
        expires_at="2026-05-15T23:00:00Z",
    )


def test_generate_idempotency_token_returns_uuid_v4_format() -> None:
    token = IDEMPOTENCY_STORE.generate_idempotency_token()

    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        token,
    )


def test_issue_idempotency_token_persists_record_with_metadata(tmp_path: Path) -> None:
    record = IDEMPOTENCY_STORE.issue_idempotency_token(
        tmp_path,
        "write-landscape",
        {"entity": "role-system-architect", "scope": "landscape"},
        now=datetime(2026, 5, 14, 23, 0, tzinfo=timezone.utc),
    )

    stored_path = tmp_path / ".idempotency" / "tokens" / f"{record.token}.yaml"
    assert stored_path.exists()
    payload = yaml.safe_load(stored_path.read_text(encoding="utf-8"))
    assert payload["token"] == record.token
    assert payload["operationType"] == "write-landscape"
    assert payload["status"] == "pending"
    assert payload["createdAt"] == "2026-05-14T23:00:00Z"
    assert payload["expiresAt"] == "2026-05-15T23:00:00Z"
    assert payload["requestDigest"] == IDEMPOTENCY_STORE.build_request_digest(
        "write-landscape",
        {"entity": "role-system-architect", "scope": "landscape"},
    )


def test_complete_token_record_updates_status_and_result(tmp_path: Path) -> None:
    issued = IDEMPOTENCY_STORE.issue_idempotency_token(
        tmp_path,
        "emit-packet",
        {"candidate": "feature-password-recovery"},
        now=datetime(2026, 5, 14, 23, 0, tzinfo=timezone.utc),
    )

    completed = IDEMPOTENCY_STORE.complete_token_record(
        tmp_path,
        issued.token,
        {"packetId": "packet-123", "status": "ok"},
        now=datetime(2026, 5, 14, 23, 5, tzinfo=timezone.utc),
    )

    assert completed.status == "completed"
    assert completed.completed_at == "2026-05-14T23:05:00Z"
    reloaded = IDEMPOTENCY_STORE.load_token_record(tmp_path, issued.token)
    assert reloaded.status == "completed"
    assert reloaded.result == {"packetId": "packet-123", "status": "ok"}


def test_archive_expired_tokens_moves_records_older_than_ttl(tmp_path: Path) -> None:
    issued = IDEMPOTENCY_STORE.issue_idempotency_token(
        tmp_path,
        "route-correction",
        {"salmonId": "salmon-1"},
        now=datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc),
    )

    archived = IDEMPOTENCY_STORE.archive_expired_tokens(
        tmp_path,
        now=datetime(2026, 5, 14, 11, 0, tzinfo=timezone.utc),
    )

    expected_path = tmp_path / ".idempotency" / "archive" / f"{issued.token}.yaml"
    assert archived == [expected_path]
    assert expected_path.exists()
    assert not (tmp_path / ".idempotency" / "tokens" / f"{issued.token}.yaml").exists()


def test_issue_idempotency_token_generates_unique_values_across_multiple_operations(tmp_path: Path) -> None:
    tokens = {
        IDEMPOTENCY_STORE.issue_idempotency_token(
            tmp_path,
            "write-landscape",
            {"sequence": index},
            now=datetime(2026, 5, 14, 23, 0, tzinfo=timezone.utc) + timedelta(seconds=index),
        ).token
        for index in range(20)
    }

    assert len(tokens) == 20


def test_deduplicate_request_marks_new_request_and_persists_provided_token(tmp_path: Path) -> None:
    token = "550e8400-e29b-41d4-a716-446655440000"
    parameters = {"candidate": "feature-password-recovery"}

    decision = IDEMPOTENCY_STORE.deduplicate_request(
        tmp_path,
        token,
        "emit-packet",
        parameters,
        now=datetime(2026, 5, 14, 23, 0, tzinfo=timezone.utc),
    )

    assert decision.disposition == "new"
    assert decision.record is not None
    assert decision.record.token == token
    assert IDEMPOTENCY_STORE.token_record_path(tmp_path, token).exists()
    stored = IDEMPOTENCY_STORE.load_token_record(tmp_path, token)
    assert stored.status == "pending"


def test_deduplicate_request_replays_completed_result_after_initial_issue(tmp_path: Path) -> None:
    token = "550e8400-e29b-41d4-a716-446655440001"
    parameters = {"candidate": "feature-password-recovery"}

    first = IDEMPOTENCY_STORE.deduplicate_request(
        tmp_path,
        token,
        "emit-packet",
        parameters,
        now=datetime(2026, 5, 14, 23, 0, tzinfo=timezone.utc),
    )
    assert first.disposition == "new"

    IDEMPOTENCY_STORE.complete_token_record(
        tmp_path,
        token,
        {"packetId": "packet-123", "status": "ok"},
        now=datetime(2026, 5, 14, 23, 5, tzinfo=timezone.utc),
    )

    replay = IDEMPOTENCY_STORE.deduplicate_request(
        tmp_path,
        token,
        "emit-packet",
        parameters,
    )

    assert replay.disposition == "replay"
    assert replay.result == {"packetId": "packet-123", "status": "ok"}


def test_deduplicate_request_waits_for_pending_completion_then_replays(tmp_path: Path) -> None:
    token = "550e8400-e29b-41d4-a716-446655440002"
    parameters = {"candidate": "feature-password-recovery"}
    IDEMPOTENCY_STORE.persist_token_record(tmp_path, _make_record(token, "emit-packet", parameters))
    sleep_calls: list[float] = []

    def _sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        IDEMPOTENCY_STORE.complete_token_record(
            tmp_path,
            token,
            {"packetId": "packet-456", "status": "ok"},
            now=datetime(2026, 5, 14, 23, 1, tzinfo=timezone.utc),
        )

    decision = IDEMPOTENCY_STORE.deduplicate_request(
        tmp_path,
        token,
        "emit-packet",
        parameters,
        timeout_seconds=1,
        poll_interval_seconds=0.01,
        sleep_fn=_sleep,
    )

    assert sleep_calls
    assert decision.disposition == "replay"
    assert decision.result == {"packetId": "packet-456", "status": "ok"}


def test_deduplicate_request_returns_retry_after_for_pending_token(tmp_path: Path) -> None:
    token = "550e8400-e29b-41d4-a716-446655440003"
    parameters = {"candidate": "feature-password-recovery"}
    IDEMPOTENCY_STORE.persist_token_record(tmp_path, _make_record(token, "emit-packet", parameters))

    decision = IDEMPOTENCY_STORE.deduplicate_request(
        tmp_path,
        token,
        "emit-packet",
        parameters,
        timeout_seconds=0,
    )

    assert decision.disposition == "pending"
    assert decision.retry_after_seconds == IDEMPOTENCY_STORE.DEFAULT_PENDING_RETRY_AFTER_SECONDS
    assert decision.message is not None
    assert "retry after" in decision.message.lower()


def test_deduplicate_request_returns_failure_for_failed_token(tmp_path: Path) -> None:
    token = "550e8400-e29b-41d4-a716-446655440004"
    parameters = {"candidate": "feature-password-recovery"}
    IDEMPOTENCY_STORE.persist_token_record(
        tmp_path,
        _make_record(
            token,
            "emit-packet",
            parameters,
            status="failed",
            result={"error": "writer conflict"},
            completed_at="2026-05-14T23:02:00Z",
        ),
    )

    decision = IDEMPOTENCY_STORE.deduplicate_request(
        tmp_path,
        token,
        "emit-packet",
        parameters,
    )

    assert decision.disposition == "failed"
    assert decision.message is not None
    assert "contact support" in decision.message.lower()


def test_deduplicate_request_lookup_completes_within_100ms(tmp_path: Path) -> None:
    token = "550e8400-e29b-41d4-a716-446655440005"
    parameters = {"candidate": "feature-password-recovery"}
    IDEMPOTENCY_STORE.persist_token_record(
        tmp_path,
        _make_record(
            token,
            "emit-packet",
            parameters,
            status="completed",
            result={"packetId": "packet-789", "status": "ok"},
            completed_at="2026-05-14T23:03:00Z",
        ),
    )

    started = time.perf_counter()
    decision = IDEMPOTENCY_STORE.deduplicate_request(
        tmp_path,
        token,
        "emit-packet",
        parameters,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert decision.disposition == "replay"
    assert elapsed_ms < 100