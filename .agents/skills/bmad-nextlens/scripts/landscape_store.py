"""Persist NextLens landscape state in the control-repo docs tree."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Mapping

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - exercised in runtime environments
    yaml = None
    _YAML_IMPORT_ERROR = exc
else:
    _YAML_IMPORT_ERROR = None


LANDSCAPE_ENTITY_DIRECTORIES = (
    "system",
    "role",
    "outcome",
    "journey",
    "operating_loop",
    "capability",
    "decision",
    "risk",
    "feature",
)


@dataclass(frozen=True)
class LandscapeEntityRecord:
    entity_type: str
    semantic_id: str
    opaque_id: str
    name: str
    snapshot: Mapping[str, Any]
    relationships: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LandscapePersistenceResult:
    status: str
    path: Path | None = None
    error: str | None = None
    rollback_performed: bool = False
    blocks_packet_emission: bool = False


@dataclass(frozen=True)
class LandscapeRelationship:
    relationship_name: str
    target_id: str
    target_entity: "ReconstructedLandscapeEntity | None"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class ReconstructedLandscapeEntity:
    entity_type: str
    semantic_id: str
    opaque_id: str
    name: str
    snapshot: dict[str, Any]
    relationships: dict[str, Any]
    metadata: dict[str, Any]
    source_path: Path
    resolved_relationships: dict[str, tuple[LandscapeRelationship, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class LandscapeState:
    entities_by_id: Mapping[str, ReconstructedLandscapeEntity]
    entities_by_type: Mapping[str, tuple[ReconstructedLandscapeEntity, ...]]
    warnings: tuple[str, ...] = field(default_factory=tuple)
    load_sequence: tuple[str, ...] = field(default_factory=tuple)

    def get_by_id(self, semantic_id: str) -> ReconstructedLandscapeEntity | None:
        return self.entities_by_id.get(semantic_id)

    def get_by_type(self, entity_type: str) -> tuple[ReconstructedLandscapeEntity, ...]:
        return self.entities_by_type.get(_entity_directory_name(entity_type), ())

    def get_related_entities(
        self,
        semantic_id: str,
        *,
        relationship_name: str | None = None,
    ) -> tuple[LandscapeRelationship, ...]:
        entity = self.entities_by_id.get(semantic_id)
        if entity is None:
            return ()

        if relationship_name is not None:
            return entity.resolved_relationships.get(relationship_name, ())

        flattened: list[LandscapeRelationship] = []
        for name in sorted(entity.resolved_relationships):
            flattened.extend(entity.resolved_relationships[name])
        return tuple(flattened)


def initialize_landscape_dirs(docs_path: str | Path) -> dict[str, Path]:
    docs_root = Path(docs_path)
    landscape_root = docs_root / "landscape"
    landscape_root.mkdir(parents=True, exist_ok=True)

    directories: dict[str, Path] = {}
    for directory_name in LANDSCAPE_ENTITY_DIRECTORIES:
        directory_path = landscape_root / directory_name
        directory_path.mkdir(parents=True, exist_ok=True)
        directories[directory_name] = directory_path

    return directories


def persist_landscape_entity(
    docs_path: str | Path,
    entity: LandscapeEntityRecord,
) -> LandscapePersistenceResult:
    yaml_module = _require_yaml_support()

    try:
        directories = initialize_landscape_dirs(docs_path)
        entity_directory = _entity_directory_name(entity.entity_type)
        if entity_directory not in directories:
            raise ValueError(
                f"Unsupported landscape entity type '{entity.entity_type}'."
            )

        final_path = directories[entity_directory] / f"{entity.semantic_id}.yaml"
        payload = _build_payload(entity, entity_directory)
        existed_before = final_path.exists()
        backup_path = final_path.with_suffix(final_path.suffix + ".bak")
        temp_path: Path | None = None
        rollback_performed = False

        try:
            fd, temp_name = tempfile.mkstemp(
                dir=str(final_path.parent),
                prefix=f"{entity.semantic_id}-",
                suffix=".tmp",
            )
            temp_path = Path(temp_name)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                yaml_module.safe_dump(payload, handle, sort_keys=False)

            if existed_before:
                os.replace(final_path, backup_path)

            os.replace(temp_path, final_path)
            temp_path = None
            _set_read_write_permissions(final_path)
            _validate_written_payload(final_path, payload, yaml_module)

            if backup_path.exists():
                backup_path.unlink()

            _rebuild_derived_graph(docs_path)

            return LandscapePersistenceResult(status="pass", path=final_path)
        except Exception as exc:  # pragma: no cover - exercised via tests through failure simulation
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()

            if existed_before and backup_path.exists():
                if final_path.exists():
                    final_path.unlink()
                os.replace(backup_path, final_path)
                rollback_performed = True
            elif final_path.exists():
                final_path.unlink()
                rollback_performed = True

            return LandscapePersistenceResult(
                status="fail",
                path=final_path,
                error=str(exc),
                rollback_performed=rollback_performed,
                blocks_packet_emission=True,
            )
    except Exception as exc:
        return LandscapePersistenceResult(
            status="fail",
            error=str(exc),
            rollback_performed=False,
            blocks_packet_emission=True,
        )


def reconstruct_landscape_state(docs_path: str | Path) -> LandscapeState:
    yaml_module = _require_yaml_support()
    directories = initialize_landscape_dirs(docs_path)
    warnings: list[str] = []
    entities_by_id: dict[str, ReconstructedLandscapeEntity] = {}
    entities_by_type: dict[str, list[ReconstructedLandscapeEntity]] = {
        entity_type: [] for entity_type in LANDSCAPE_ENTITY_DIRECTORIES
    }
    load_sequence: list[str] = []

    for entity_type in LANDSCAPE_ENTITY_DIRECTORIES:
        for file_path in sorted(directories[entity_type].glob("*.yaml")):
            try:
                payload = yaml_module.safe_load(file_path.read_text(encoding="utf-8"))
                entity = _parse_reconstructed_entity(payload, entity_type, file_path)
            except Exception as exc:
                warnings.append(str(exc))
                continue

            if entity.semantic_id in entities_by_id:
                warnings.append(
                    f"Duplicate semanticId '{entity.semantic_id}' detected at '{file_path}'."
                )
                continue

            entities_by_id[entity.semantic_id] = entity
            entities_by_type[entity_type].append(entity)
            load_sequence.append(entity.semantic_id)

    for entity in entities_by_id.values():
        entity.resolved_relationships = _resolve_relationships(
            entity.relationships,
            entities_by_id,
            warnings,
            entity.semantic_id,
        )

    return LandscapeState(
        entities_by_id=entities_by_id,
        entities_by_type={
            entity_type: tuple(sorted(items, key=lambda item: item.semantic_id))
            for entity_type, items in entities_by_type.items()
        },
        warnings=tuple(warnings),
        load_sequence=tuple(load_sequence),
    )


def _require_yaml_support():
    if yaml is None:
        raise RuntimeError(
            "PyYAML is required to persist landscape state. Install PyYAML before running the landscape store."
        ) from _YAML_IMPORT_ERROR
    return yaml


def _entity_directory_name(entity_type: str) -> str:
    return str(entity_type).strip().lower().replace("-", "_").replace(" ", "_")


def _parse_reconstructed_entity(
    payload: Any,
    entity_type: str,
    file_path: Path,
) -> ReconstructedLandscapeEntity:
    if not isinstance(payload, Mapping):
        raise ValueError(f"Landscape file '{file_path}' must contain a mapping.")

    identity = payload.get("identity")
    if not isinstance(identity, Mapping):
        raise ValueError(f"Landscape file '{file_path}' is missing identity data.")

    semantic_id = str(identity.get("semanticId") or "").strip()
    opaque_id = str(identity.get("opaqueId") or "").strip()
    name = str(identity.get("name") or "").strip()
    if not semantic_id or not opaque_id or not name:
        raise ValueError(f"Landscape file '{file_path}' has incomplete identity data.")

    snapshot = payload.get("snapshot") or {}
    relationships = payload.get("relationships") or {}
    metadata = payload.get("metadata") or {}
    if not isinstance(relationships, Mapping):
        raise ValueError(f"Landscape file '{file_path}' has invalid relationships data.")

    return ReconstructedLandscapeEntity(
        entity_type=entity_type,
        semantic_id=semantic_id,
        opaque_id=opaque_id,
        name=name,
        snapshot=dict(snapshot) if isinstance(snapshot, Mapping) else {"value": snapshot},
        relationships=dict(relationships),
        metadata=dict(metadata) if isinstance(metadata, Mapping) else {"value": metadata},
        source_path=file_path,
    )


def _build_payload(entity: LandscapeEntityRecord, entity_directory: str) -> dict[str, Any]:
    timestamp = _utc_timestamp()
    metadata = dict(entity.metadata)
    metadata.setdefault("createdAt", timestamp)
    metadata.setdefault("updatedAt", timestamp)
    metadata.setdefault("source", "nextlens")
    metadata.setdefault("author", "nextlens")

    return {
        "entityType": entity_directory,
        "identity": {
            "semanticId": entity.semantic_id,
            "opaqueId": entity.opaque_id,
            "name": entity.name,
        },
        "snapshot": dict(entity.snapshot),
        "relationships": dict(entity.relationships),
        "metadata": metadata,
    }


def _validate_written_payload(path: Path, expected_payload: Mapping[str, Any], yaml_module: Any) -> None:
    loaded = yaml_module.safe_load(path.read_text(encoding="utf-8"))
    if loaded != dict(expected_payload):
        raise ValueError(f"Persisted landscape payload validation failed for '{path}'.")


def _set_read_write_permissions(path: Path) -> None:
    path.chmod(
        stat.S_IRUSR
        | stat.S_IWUSR
        | stat.S_IRGRP
        | stat.S_IWGRP
        | stat.S_IROTH
    )


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rebuild_derived_graph(docs_path: str | Path) -> None:
    import importlib.util
    import sys

    module_path = Path(__file__).resolve().parent / "derived_graph.py"
    spec = importlib.util.spec_from_file_location("nextlens_derived_graph_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load derived graph runtime.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    state = reconstruct_landscape_state(docs_path)
    module.write_derived_graph(docs_path, state)


def _resolve_relationships(
    relationships: Mapping[str, Any],
    entities_by_id: Mapping[str, ReconstructedLandscapeEntity],
    warnings: list[str],
    source_id: str,
) -> dict[str, tuple[LandscapeRelationship, ...]]:
    resolved: dict[str, tuple[LandscapeRelationship, ...]] = {}

    for relationship_name, raw_value in relationships.items():
        edges: list[LandscapeRelationship] = []
        for target_id, metadata in _coerce_relationship_targets(raw_value):
            target_entity = entities_by_id.get(target_id)
            if target_entity is None:
                warnings.append(
                    f"Broken relationship '{relationship_name}' from '{source_id}' to '{target_id}'."
                )
            edges.append(
                LandscapeRelationship(
                    relationship_name=relationship_name,
                    target_id=target_id,
                    target_entity=target_entity,
                    metadata=metadata,
                )
            )

        if edges:
            resolved[relationship_name] = tuple(edges)

    return resolved


def _coerce_relationship_targets(raw_value: Any) -> list[tuple[str, dict[str, Any]]]:
    if isinstance(raw_value, str):
        return [(raw_value, {})]

    if isinstance(raw_value, Mapping):
        target_id = str(raw_value.get("id") or raw_value.get("semanticId") or "").strip()
        if target_id:
            metadata = {
                key: value
                for key, value in raw_value.items()
                if key not in {"id", "semanticId"}
            }
            return [(target_id, metadata)]
        return []

    if isinstance(raw_value, list):
        edges: list[tuple[str, dict[str, Any]]] = []
        for item in raw_value:
            edges.extend(_coerce_relationship_targets(item))
        return edges

    return []
