"""Idempotency token generation and storage for NextLens mutating operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Mapping
import uuid

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - exercised in runtime environments
    yaml = None
    _YAML_IMPORT_ERROR = exc
else:
    _YAML_IMPORT_ERROR = None


TOKEN_TTL_HOURS = 24
TOKEN_STATUS_VALUES = {"pending", "completed", "failed"}
DEDUPLICATION_DISPOSITIONS = {"new", "replay", "pending", "failed"}
DEFAULT_PENDING_RETRY_AFTER_SECONDS = 5


@dataclass(frozen=True)
class IdempotencyTokenRecord:
    token: str
    operation_type: str
    created_at: str
    request_digest: str
    status: str = "pending"
    completed_at: str | None = None
    result: Mapping[str, Any] | None = None
    ttl_hours: int = TOKEN_TTL_HOURS
    expires_at: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "operationType": self.operation_type,
            "createdAt": self.created_at,
            "requestDigest": self.request_digest,
            "status": self.status,
            "completedAt": self.completed_at,
            "result": dict(self.result) if isinstance(self.result, Mapping) else self.result,
            "ttlHours": self.ttl_hours,
            "expiresAt": self.expires_at or _timestamp_after(self.created_at, hours=self.ttl_hours),
        }


@dataclass(frozen=True)
class DeduplicationDecision:
    disposition: str
    token: str
    record: IdempotencyTokenRecord | None = None
    result: Any = None
    retry_after_seconds: int | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        if self.disposition not in DEDUPLICATION_DISPOSITIONS:
            raise ValueError(f"Unsupported deduplication disposition '{self.disposition}'.")


def generate_idempotency_token() -> str:
    return str(uuid.uuid4())


def build_request_digest(operation_type: str, parameters: Mapping[str, Any]) -> str:
    payload = {
        "operationType": operation_type,
        "parameters": _json_safe(parameters),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def deduplicate_request(
    docs_path: str | Path,
    token: str,
    operation_type: str,
    parameters: Mapping[str, Any],
    *,
    now: datetime | None = None,
    timeout_seconds: float = 0.0,
    poll_interval_seconds: float = 0.05,
    sleep_fn: callable | None = None,
) -> DeduplicationDecision:
    path = token_record_path(docs_path, token)
    if not path.exists():
        record = _build_token_record(token, operation_type, parameters, now=now)
        persist_token_record(docs_path, record)
        return DeduplicationDecision(
            disposition="new",
            token=token,
            record=record,
            message="No existing idempotency record was found. Operation may proceed.",
        )

    return _resolve_existing_request(
        docs_path,
        token,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        sleep_fn=sleep_fn,
    )


def issue_idempotency_token(
    docs_path: str | Path,
    operation_type: str,
    parameters: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> IdempotencyTokenRecord:
    token = generate_idempotency_token()
    record = _build_token_record(token, operation_type, parameters, now=now)
    persist_token_record(docs_path, record)
    return record


def persist_token_record(docs_path: str | Path, record: IdempotencyTokenRecord) -> Path:
    yaml_module = _require_yaml_support()
    tokens_dir = _tokens_dir(docs_path)
    tokens_dir.mkdir(parents=True, exist_ok=True)
    final_path = tokens_dir / f"{record.token}.yaml"

    fd, temp_name = tempfile.mkstemp(dir=str(tokens_dir), prefix=f"{record.token}-", suffix=".tmp")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            yaml_module.safe_dump(record.to_payload(), handle, sort_keys=False)
        os.replace(temp_path, final_path)
        temp_path = None
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

    return final_path


def load_token_record(docs_path: str | Path, token: str) -> IdempotencyTokenRecord:
    yaml_module = _require_yaml_support()
    path = token_record_path(docs_path, token)
    payload = yaml_module.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Token record '{path}' must contain a mapping.")
    return IdempotencyTokenRecord(
        token=str(payload.get("token") or token),
        operation_type=str(payload.get("operationType") or ""),
        created_at=str(payload.get("createdAt") or ""),
        request_digest=str(payload.get("requestDigest") or ""),
        status=str(payload.get("status") or "pending"),
        completed_at=_optional_string(payload.get("completedAt")),
        result=payload.get("result") if isinstance(payload.get("result"), Mapping) else payload.get("result"),
        ttl_hours=int(payload.get("ttlHours") or TOKEN_TTL_HOURS),
        expires_at=_optional_string(payload.get("expiresAt")),
    )


def complete_token_record(
    docs_path: str | Path,
    token: str,
    result: Mapping[str, Any],
    *,
    now: datetime | None = None,
    status: str = "completed",
) -> IdempotencyTokenRecord:
    if status not in TOKEN_STATUS_VALUES:
        raise ValueError(f"Unsupported token status '{status}'.")

    existing = load_token_record(docs_path, token)
    updated = IdempotencyTokenRecord(
        token=existing.token,
        operation_type=existing.operation_type,
        created_at=existing.created_at,
        request_digest=existing.request_digest,
        status=status,
        completed_at=_timestamp(now),
        result=dict(result),
        ttl_hours=existing.ttl_hours,
        expires_at=existing.expires_at or _timestamp_after(existing.created_at, hours=existing.ttl_hours),
    )
    persist_token_record(docs_path, updated)
    return updated


def token_record_path(docs_path: str | Path, token: str) -> Path:
    return _tokens_dir(docs_path) / f"{token}.yaml"


def archive_expired_tokens(docs_path: str | Path, *, now: datetime | None = None) -> list[Path]:
    current = now or datetime.now(timezone.utc)
    archive_dir = _archive_dir(docs_path)
    archive_dir.mkdir(parents=True, exist_ok=True)
    archived_paths: list[Path] = []

    for path in sorted(_tokens_dir(docs_path).glob("*.yaml")):
        record = load_token_record(docs_path, path.stem)
        expires_at = _parse_timestamp(record.expires_at or _timestamp_after(record.created_at, hours=record.ttl_hours))
        if expires_at <= current:
            archived_path = archive_dir / path.name
            os.replace(path, archived_path)
            archived_paths.append(archived_path)

    return archived_paths


def _require_yaml_support():
    if yaml is None:
        raise RuntimeError(
            "PyYAML is required to persist idempotency tokens. Install PyYAML before running the token store."
        ) from _YAML_IMPORT_ERROR
    return yaml


def _tokens_dir(docs_path: str | Path) -> Path:
    return Path(docs_path) / ".idempotency" / "tokens"


def _archive_dir(docs_path: str | Path) -> Path:
    return Path(docs_path) / ".idempotency" / "archive"


def _build_token_record(
    token: str,
    operation_type: str,
    parameters: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> IdempotencyTokenRecord:
    created_at = _timestamp(now)
    return IdempotencyTokenRecord(
        token=token,
        operation_type=operation_type,
        created_at=created_at,
        request_digest=build_request_digest(operation_type, parameters),
        status="pending",
        ttl_hours=TOKEN_TTL_HOURS,
        expires_at=_timestamp_after(created_at, hours=TOKEN_TTL_HOURS),
    )


def _resolve_existing_request(
    docs_path: str | Path,
    token: str,
    *,
    timeout_seconds: float,
    poll_interval_seconds: float,
    sleep_fn: callable | None,
) -> DeduplicationDecision:
    sleeper = sleep_fn or time.sleep
    deadline = time.monotonic() + timeout_seconds if timeout_seconds > 0 else None

    while True:
        record = load_token_record(docs_path, token)
        if record.status == "completed":
            return DeduplicationDecision(
                disposition="replay",
                token=token,
                record=record,
                result=record.result,
                message="Existing completed request found. Returning the original result without re-running side effects.",
            )
        if record.status == "failed":
            return DeduplicationDecision(
                disposition="failed",
                token=token,
                record=record,
                result=record.result,
                message="Existing request already failed. Contact support or perform manual recovery before retrying.",
            )
        if record.status != "pending":
            raise ValueError(f"Unsupported token status '{record.status}'.")

        if deadline is None:
            return _pending_decision(token, record, timeout_seconds)

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return _pending_decision(token, record, timeout_seconds)

        sleeper(min(poll_interval_seconds, remaining))


def _pending_decision(
    token: str,
    record: IdempotencyTokenRecord,
    timeout_seconds: float,
) -> DeduplicationDecision:
    retry_after_seconds = max(
        1,
        DEFAULT_PENDING_RETRY_AFTER_SECONDS if timeout_seconds <= 0 else math.ceil(timeout_seconds),
    )
    return DeduplicationDecision(
        disposition="pending",
        token=token,
        record=record,
        retry_after_seconds=retry_after_seconds,
        message=(
            "Existing request is still pending. "
            f"Retry after {retry_after_seconds} seconds or wait for completion before retrying."
        ),
    )


def _timestamp(now: datetime | None = None) -> str:
    normalized = now or datetime.now(timezone.utc)
    return normalized.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _timestamp_after(base_timestamp: str, *, hours: int) -> str:
    return _timestamp(_parse_timestamp(base_timestamp) + timedelta(hours=hours))


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return _timestamp(value)
    return value