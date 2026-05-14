from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sys

import yaml


MODULE_PATH = Path(__file__).resolve().parent.parent / "idempotency_store.py"
SPEC = importlib.util.spec_from_file_location("nextlens_idempotency_store", MODULE_PATH)
IDEMPOTENCY_STORE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = IDEMPOTENCY_STORE
SPEC.loader.exec_module(IDEMPOTENCY_STORE)


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