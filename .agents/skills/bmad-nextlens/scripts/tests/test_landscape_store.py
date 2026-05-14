from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys

import yaml


MODULE_PATH = Path(__file__).resolve().parent.parent / "landscape_store.py"
SPEC = importlib.util.spec_from_file_location("nextlens_landscape_store", MODULE_PATH)
LANDSCAPE_STORE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = LANDSCAPE_STORE
SPEC.loader.exec_module(LANDSCAPE_STORE)


def test_initialize_landscape_dirs_creates_expected_structure(tmp_path: Path) -> None:
    directories = LANDSCAPE_STORE.initialize_landscape_dirs(tmp_path)

    assert set(directories) == set(LANDSCAPE_STORE.LANDSCAPE_ENTITY_DIRECTORIES)
    for directory_name in LANDSCAPE_STORE.LANDSCAPE_ENTITY_DIRECTORIES:
        assert (tmp_path / "landscape" / directory_name).is_dir()


def test_persist_landscape_entity_writes_parseable_entity_file(tmp_path: Path) -> None:
    entity = _default_entity_record()

    result = LANDSCAPE_STORE.persist_landscape_entity(tmp_path, entity)

    assert result.status == "pass"
    assert result.path == tmp_path / "landscape" / "role" / "role-system-architect.yaml"
    assert result.path is not None and result.path.exists()
    payload = yaml.safe_load(result.path.read_text(encoding="utf-8"))
    assert payload["identity"]["semanticId"] == "role-system-architect"
    assert payload["identity"]["opaqueId"] == "opaque-role-system-architect"
    assert payload["snapshot"]["title"] == "System Architect"
    assert payload["relationships"]["systemId"] == "system-nextlens"
    assert os.access(result.path, os.R_OK)
    assert os.access(result.path, os.W_OK)


def test_persist_landscape_entity_uses_atomic_replace(tmp_path: Path, monkeypatch) -> None:
    entity = _default_entity_record()
    replace_calls: list[tuple[Path, Path]] = []
    original_replace = LANDSCAPE_STORE.os.replace

    def recording_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        replace_calls.append((Path(src), Path(dst)))
        original_replace(src, dst)

    monkeypatch.setattr(LANDSCAPE_STORE.os, "replace", recording_replace)

    result = LANDSCAPE_STORE.persist_landscape_entity(tmp_path, entity)

    assert result.status == "pass"
    assert any(src.suffix == ".tmp" and dst == result.path for src, dst in replace_calls)
    assert not any(path.suffix == ".tmp" for path in (tmp_path / "landscape" / "role").iterdir())


def test_persist_landscape_entity_rolls_back_on_write_failure(tmp_path: Path, monkeypatch) -> None:
    entity = _default_entity_record()
    existing_path = tmp_path / "landscape" / "role" / "role-system-architect.yaml"
    existing_path.parent.mkdir(parents=True, exist_ok=True)
    existing_path.write_text("original: true\n", encoding="utf-8")
    original_replace = LANDSCAPE_STORE.os.replace

    def failing_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        src_path = Path(src)
        dst_path = Path(dst)
        if src_path.suffix == ".tmp" and dst_path == existing_path:
            raise PermissionError("write blocked")
        original_replace(src, dst)

    monkeypatch.setattr(LANDSCAPE_STORE.os, "replace", failing_replace)

    result = LANDSCAPE_STORE.persist_landscape_entity(tmp_path, entity)

    assert result.status == "fail"
    assert result.blocks_packet_emission is True
    assert result.rollback_performed is True
    assert result.error == "write blocked"
    assert existing_path.read_text(encoding="utf-8") == "original: true\n"


def test_reconstruct_landscape_state_loads_entities_in_dependency_order(tmp_path: Path) -> None:
    _persist_entities(
        tmp_path,
        _entity_record(
            entity_type="system",
            semantic_id="system-nextlens",
            opaque_id="opaque-system-nextlens",
            name="NextLens",
        ),
        _entity_record(
            entity_type="role",
            semantic_id="role-system-architect",
            opaque_id="opaque-role-system-architect",
            name="System Architect",
            relationships={"systemId": "system-nextlens"},
        ),
        _entity_record(
            entity_type="outcome",
            semantic_id="outcome-reduce-ambiguity",
            opaque_id="opaque-outcome-reduce-ambiguity",
            name="Reduce Ambiguity",
            relationships={"systemId": "system-nextlens", "journeyIds": ["journey-intake"]},
        ),
        _entity_record(
            entity_type="journey",
            semantic_id="journey-intake",
            opaque_id="opaque-journey-intake",
            name="Intake",
            relationships={"outcomeId": "outcome-reduce-ambiguity"},
        ),
    )

    state = LANDSCAPE_STORE.reconstruct_landscape_state(tmp_path)

    assert state.load_sequence == (
        "system-nextlens",
        "role-system-architect",
        "outcome-reduce-ambiguity",
        "journey-intake",
    )
    assert state.get_by_id("journey-intake") is not None


def test_reconstruct_landscape_state_queries_without_additional_io(tmp_path: Path, monkeypatch) -> None:
    _persist_entities(tmp_path, _default_entity_record())
    state = LANDSCAPE_STORE.reconstruct_landscape_state(tmp_path)

    def fail_read_text(self: Path, *args: object, **kwargs: object) -> str:
        raise AssertionError("unexpected filesystem read")

    monkeypatch.setattr(Path, "read_text", fail_read_text)

    entity = state.get_by_id("role-system-architect")
    assert entity is not None
    assert entity.name == "System Architect"


def test_reconstruct_landscape_state_queries_by_type_in_deterministic_order(tmp_path: Path) -> None:
    _persist_entities(
        tmp_path,
        _entity_record(
            entity_type="outcome",
            semantic_id="outcome-zeta",
            opaque_id="opaque-outcome-zeta",
            name="Zeta",
        ),
        _entity_record(
            entity_type="outcome",
            semantic_id="outcome-alpha",
            opaque_id="opaque-outcome-alpha",
            name="Alpha",
        ),
    )

    state = LANDSCAPE_STORE.reconstruct_landscape_state(tmp_path)

    assert [entity.semantic_id for entity in state.get_by_type("outcome")] == [
        "outcome-alpha",
        "outcome-zeta",
    ]


def test_reconstruct_landscape_state_resolves_relationships_and_warns_on_breakage(tmp_path: Path) -> None:
    _persist_entities(
        tmp_path,
        _entity_record(
            entity_type="outcome",
            semantic_id="outcome-reduce-ambiguity",
            opaque_id="opaque-outcome-reduce-ambiguity",
            name="Reduce Ambiguity",
            relationships={"journeyIds": ["journey-intake", "journey-missing"]},
        ),
        _entity_record(
            entity_type="journey",
            semantic_id="journey-intake",
            opaque_id="opaque-journey-intake",
            name="Intake",
        ),
    )

    state = LANDSCAPE_STORE.reconstruct_landscape_state(tmp_path)

    related = state.get_related_entities(
        "outcome-reduce-ambiguity",
        relationship_name="journeyIds",
    )
    assert [edge.target_id for edge in related] == ["journey-intake", "journey-missing"]
    assert related[0].target_entity is not None
    assert related[1].target_entity is None
    assert any("journey-missing" in warning for warning in state.warnings)


def _default_entity_record() -> LANDSCAPE_STORE.LandscapeEntityRecord:
    return _entity_record(
        entity_type="role",
        semantic_id="role-system-architect",
        opaque_id="opaque-role-system-architect",
        name="System Architect",
        snapshot={"title": "System Architect", "status": "active"},
        relationships={"systemId": "system-nextlens"},
        metadata={"source": "context", "author": "operator"},
    )


def _entity_record(
    *,
    entity_type: str,
    semantic_id: str,
    opaque_id: str,
    name: str,
    snapshot: dict[str, object] | None = None,
    relationships: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
) -> LANDSCAPE_STORE.LandscapeEntityRecord:
    return LANDSCAPE_STORE.LandscapeEntityRecord(
        entity_type=entity_type,
        semantic_id=semantic_id,
        opaque_id=opaque_id,
        name=name,
        snapshot=snapshot or {"title": name, "status": "active"},
        relationships=relationships or {},
        metadata=metadata or {"source": "context", "author": "operator"},
    )


def _persist_entities(tmp_path: Path, *entities: LANDSCAPE_STORE.LandscapeEntityRecord) -> None:
    for entity in entities:
        result = LANDSCAPE_STORE.persist_landscape_entity(tmp_path, entity)
        assert result.status == "pass"