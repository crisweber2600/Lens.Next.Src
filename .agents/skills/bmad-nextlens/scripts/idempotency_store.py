"""Idempotency token generation and storage for NextLens mutating operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
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


def generate_idempotency_token() -> str:
    return str(uuid.uuid4())


def build_request_digest(operation_type: str, parameters: Mapping[str, Any]) -> str:
    payload = {
        "operationType": operation_type,
        "parameters": _json_safe(parameters),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def issue_idempotency_token(
    docs_path: str | Path,
    operation_type: str,
    parameters: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> IdempotencyTokenRecord:
    created_at = _timestamp(now)
    token = generate_idempotency_token()
    record = IdempotencyTokenRecord(
        token=token,
        operation_type=operation_type,
        created_at=created_at,
        request_digest=build_request_digest(operation_type, parameters),
        status="pending",
        ttl_hours=TOKEN_TTL_HOURS,
        expires_at=_timestamp_after(created_at, hours=TOKEN_TTL_HOURS),
    )
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
    path = _tokens_dir(docs_path) / f"{token}.yaml"
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