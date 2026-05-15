"""Deterministic Salmon correction-event fingerprinting and deduplication."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping


SALMON_DIR = ".nextlens/salmon"
FINGERPRINT_INDEX_NAME = "fingerprints.json"


@dataclass(frozen=True)
class SalmonFingerprint:
    normalized_issue_class: str
    target_stable_id: str
    canonical_path: str
    message_hash: str
    fingerprint: str


@dataclass(frozen=True)
class SalmonDeduplicationResult:
    status: str
    fingerprint: str
    event_path: Path | None = None
    event: dict[str, Any] = field(default_factory=dict)
    evidence_event: dict[str, Any] = field(default_factory=dict)


def generate_salmon_fingerprint(
    *,
    issue_class: str,
    target_stable_id: str,
    canonical_path: str,
    issue_description: str,
) -> SalmonFingerprint:
    normalized_issue_class = _normalize_token(issue_class)
    normalized_target_id = _normalize_token(target_stable_id)
    normalized_path = _normalize_path(canonical_path)
    normalized_description = _normalize_message(issue_description)
    message_hash = _sha256(normalized_description)
    fingerprint = _sha256("|".join((normalized_issue_class, normalized_target_id, normalized_path, message_hash)))
    return SalmonFingerprint(
        normalized_issue_class=normalized_issue_class,
        target_stable_id=normalized_target_id,
        canonical_path=normalized_path,
        message_hash=message_hash,
        fingerprint=fingerprint,
    )


def deduplicate_salmon_event(
    docs_path: str | Path,
    event: Mapping[str, Any],
    *,
    now_factory: Any = None,
) -> SalmonDeduplicationResult:
    docs_root = Path(docs_path)
    salmon_root = docs_root / SALMON_DIR
    event_root = salmon_root / "events"
    salmon_root.mkdir(parents=True, exist_ok=True)
    event_root.mkdir(parents=True, exist_ok=True)
    index_path = salmon_root / FINGERPRINT_INDEX_NAME
    index = _load_index(index_path)
    fingerprint = _event_fingerprint(event)
    source_key = _source_key(event)
    created_at = _utc_timestamp(now_factory)

    if fingerprint not in index["fingerprints"]:
        event_payload = dict(event)
        event_payload["dedupFingerprint"] = fingerprint
        event_payload.setdefault("sources", [_source_payload(event)])
        event_payload["routingResult"] = _routing_result(event, "created")
        event_path = event_root / f"{event_payload['id']}.json"
        _write_json(event_path, event_payload)
        index["fingerprints"][fingerprint] = {
            "eventId": event_payload["id"],
            "eventPath": str(event_path),
            "sources": [source_key],
            "createdAt": created_at,
            "updatedAt": created_at,
        }
        _write_json(index_path, index)
        return SalmonDeduplicationResult(
            status="new",
            fingerprint=fingerprint,
            event_path=event_path,
            event=event_payload,
            evidence_event=_evidence("new", fingerprint, event_payload["id"], source_key, created_at),
        )

    entry = index["fingerprints"][fingerprint]
    event_path = Path(entry["eventPath"])
    existing_event = _load_event(event_path)
    sources = list(entry.get("sources", []))
    if source_key in sources:
        return SalmonDeduplicationResult(
            status="duplicate_ignored",
            fingerprint=fingerprint,
            event_path=event_path,
            event=existing_event,
            evidence_event=_evidence("duplicate_ignored", fingerprint, entry["eventId"], source_key, created_at),
        )

    sources.append(source_key)
    existing_event["sources"] = list(existing_event.get("sources", [])) + [_source_payload(event)]
    existing_event["routingResult"] = _routing_result(existing_event, "merged")
    entry["sources"] = sources
    entry["updatedAt"] = created_at
    _write_json(event_path, existing_event)
    _write_json(index_path, index)
    return SalmonDeduplicationResult(
        status="merged",
        fingerprint=fingerprint,
        event_path=event_path,
        event=existing_event,
        evidence_event=_evidence("merged", fingerprint, entry["eventId"], source_key, created_at),
    )


def fingerprint_index_path(docs_path: str | Path) -> Path:
    return Path(docs_path) / SALMON_DIR / FINGERPRINT_INDEX_NAME


def _event_fingerprint(event: Mapping[str, Any]) -> str:
    if isinstance(event.get("dedupFingerprint"), str) and event["dedupFingerprint"]:
        return str(event["dedupFingerprint"])
    discovery = _mapping(event.get("discovery"))
    fingerprint = generate_salmon_fingerprint(
        issue_class=str(discovery.get("issueClass") or discovery.get("impactLevel") or event.get("severity") or "unknown"),
        target_stable_id=str(discovery.get("impactedFeature") or _first_feature(event) or "unknown"),
        canonical_path=str(discovery.get("canonicalPath") or _routing_result(event, "created").get("targetRef") or "unknown"),
        issue_description=str(discovery.get("issueDescription") or ""),
    )
    return fingerprint.fingerprint


def _load_index(index_path: Path) -> dict[str, Any]:
    if not index_path.exists():
        return {"fingerprints": {}}
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"fingerprints": {}}
    fingerprints = payload.get("fingerprints")
    if not isinstance(fingerprints, dict):
        payload["fingerprints"] = {}
    return payload


def _load_event(event_path: Path) -> dict[str, Any]:
    payload = json.loads(event_path.read_text(encoding="utf-8"))
    return dict(payload) if isinstance(payload, Mapping) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f"{path.stem}-", suffix=".tmp")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(dict(payload), handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp_path, path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def _routing_result(event: Mapping[str, Any], status: str) -> dict[str, Any]:
    routing = dict(_mapping(event.get("routingResult")))
    routing["status"] = status
    routing.setdefault("targetRef", "salmon:event")
    return routing


def _source_payload(event: Mapping[str, Any]) -> dict[str, Any]:
    return dict(_mapping(event.get("source")))


def _source_key(event: Mapping[str, Any]) -> str:
    source = _source_payload(event)
    return f"{source.get('type', 'unknown')}:{source.get('sourceId', 'unknown')}"


def _first_feature(event: Mapping[str, Any]) -> str | None:
    impacted_nodes = _mapping(event.get("impactedNodes"))
    features = impacted_nodes.get("features")
    if isinstance(features, list) and features:
        return str(features[0])
    return None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _evidence(status: str, fingerprint: str, event_id: str, source_key: str, timestamp: str) -> dict[str, Any]:
    return {
        "stage": "salmon-deduplication",
        "status": status,
        "fingerprint": fingerprint,
        "eventId": event_id,
        "source": source_key,
        "recordedAt": timestamp,
    }


def _normalize_token(value: str) -> str:
    return "-".join(str(value).strip().lower().replace("_", "-").split())


def _normalize_path(value: str) -> str:
    return str(value).strip().replace("\\", "/").strip("/").lower()


def _normalize_message(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc_timestamp(now_factory: Any) -> str:
    now = now_factory() if now_factory else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")