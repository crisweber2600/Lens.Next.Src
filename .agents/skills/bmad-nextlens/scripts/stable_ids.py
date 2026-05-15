"""Deterministic stable ID helpers for NextLens landscape entities."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import unicodedata
import uuid
from typing import Iterable


MAX_SEMANTIC_ID_LENGTH = 50
OPAQUE_ID_NAMESPACE = uuid.UUID("4d1e49f6-2f63-5ec5-9643-7c6d15fd9980")


@dataclass(frozen=True)
class StableEntityId:
    entity_type: str
    name: str
    semantic_id: str
    opaque_id: str


@dataclass(frozen=True)
class StableIdRenameEvent:
    entity_type: str
    name: str
    previous_semantic_id: str
    current_semantic_id: str
    previous_opaque_id: str
    current_opaque_id: str


@dataclass(frozen=True)
class StableIdValidationResult:
    warnings: tuple[str, ...] = field(default_factory=tuple)
    rename_events: tuple[StableIdRenameEvent, ...] = field(default_factory=tuple)


def generate_semantic_id(
    entity_type: str,
    name: str,
    *,
    max_length: int = MAX_SEMANTIC_ID_LENGTH,
) -> str:
    normalized_type = _normalize_fragment(entity_type) or "entity"
    normalized_name = _normalize_fragment(name) or normalized_type
    semantic_id = f"{normalized_type}-{normalized_name}"
    return _truncate_identifier(semantic_id, max_length=max_length)


def generate_opaque_id(semantic_id: str) -> str:
    return str(uuid.uuid5(OPAQUE_ID_NAMESPACE, semantic_id))


def assign_stable_entity_id(
    entity_type: str,
    name: str,
    *,
    used_semantic_ids: Iterable[str] = (),
    existing: StableEntityId | None = None,
    max_length: int = MAX_SEMANTIC_ID_LENGTH,
) -> StableEntityId:
    if existing is not None:
        return existing

    base_semantic_id = generate_semantic_id(entity_type, name, max_length=max_length)
    semantic_id = disambiguate_semantic_id(
        base_semantic_id,
        used_semantic_ids,
        max_length=max_length,
    )
    return StableEntityId(
        entity_type=entity_type,
        name=name,
        semantic_id=semantic_id,
        opaque_id=generate_opaque_id(semantic_id),
    )


def disambiguate_semantic_id(
    base_semantic_id: str,
    used_semantic_ids: Iterable[str],
    *,
    max_length: int = MAX_SEMANTIC_ID_LENGTH,
) -> str:
    normalized_used = set(used_semantic_ids)
    if base_semantic_id not in normalized_used:
        return base_semantic_id

    suffix_index = 2
    while True:
        candidate = _append_suffix(base_semantic_id, suffix_index, max_length=max_length)
        if candidate not in normalized_used:
            return candidate
        suffix_index += 1


def validate_stable_id_immutability(
    previous: StableEntityId,
    current: StableEntityId,
) -> StableIdValidationResult:
    if (
        previous.semantic_id == current.semantic_id
        and previous.opaque_id == current.opaque_id
    ):
        return StableIdValidationResult()

    warning = (
        f"Stable ID changed for {current.entity_type} '{current.name}': "
        f"semantic_id {previous.semantic_id} -> {current.semantic_id}; "
        f"opaque_id {previous.opaque_id} -> {current.opaque_id}."
    )
    rename_event = StableIdRenameEvent(
        entity_type=current.entity_type,
        name=current.name,
        previous_semantic_id=previous.semantic_id,
        current_semantic_id=current.semantic_id,
        previous_opaque_id=previous.opaque_id,
        current_opaque_id=current.opaque_id,
    )
    return StableIdValidationResult(
        warnings=(warning,),
        rename_events=(rename_event,),
    )


def _normalize_fragment(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_text.lower()
    compact = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    compact = re.sub(r"-{2,}", "-", compact)
    return compact


def _truncate_identifier(value: str, *, max_length: int) -> str:
    trimmed = value[:max_length].strip("-")
    return trimmed or value[:max_length]


def _append_suffix(base_semantic_id: str, suffix_index: int, *, max_length: int) -> str:
    suffix = f"-{suffix_index}"
    trimmed_base = base_semantic_id[: max_length - len(suffix)].rstrip("-")
    return f"{trimmed_base}{suffix}"