from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import uuid


MODULE_PATH = Path(__file__).resolve().parent.parent / "stable_ids.py"
SPEC = importlib.util.spec_from_file_location("nextlens_stable_ids", MODULE_PATH)
STABLE_IDS = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = STABLE_IDS
SPEC.loader.exec_module(STABLE_IDS)


def test_generate_semantic_id_is_normalized_and_readable() -> None:
    semantic_id = STABLE_IDS.generate_semantic_id("role", "System Architect")

    assert semantic_id == "role-system-architect"


def test_generate_opaque_id_is_deterministic_uuid() -> None:
    first = STABLE_IDS.generate_opaque_id("role-system-architect")
    second = STABLE_IDS.generate_opaque_id("role-system-architect")

    assert first == second
    assert str(uuid.UUID(first)) == first


def test_assign_stable_entity_id_reuses_existing_identifier() -> None:
    existing = STABLE_IDS.StableEntityId(
        entity_type="role",
        name="System Architect",
        semantic_id="role-system-architect",
        opaque_id=STABLE_IDS.generate_opaque_id("role-system-architect"),
    )

    assigned = STABLE_IDS.assign_stable_entity_id(
        "role",
        "System Architect",
        existing=existing,
    )

    assert assigned == existing


def test_assign_stable_entity_id_disambiguates_collisions() -> None:
    assigned = STABLE_IDS.assign_stable_entity_id(
        "role",
        "System Architect",
        used_semantic_ids={"role-system-architect"},
    )

    assert assigned.semantic_id == "role-system-architect-2"
    assert assigned.opaque_id == STABLE_IDS.generate_opaque_id("role-system-architect-2")


def test_generate_semantic_id_enforces_format_and_length() -> None:
    semantic_id = STABLE_IDS.generate_semantic_id(
        "Operating Loop",
        "Weekly Planning Review And Cross Team Coordination Ceremony",
    )

    assert semantic_id == semantic_id.lower()
    assert "_" not in semantic_id
    assert len(semantic_id) <= 50
    assert semantic_id.startswith("operating-loop-")


def test_validate_stable_id_immutability_reports_rename_events() -> None:
    previous = STABLE_IDS.StableEntityId(
        entity_type="role",
        name="System Architect",
        semantic_id="role-system-architect",
        opaque_id=STABLE_IDS.generate_opaque_id("role-system-architect"),
    )
    current = STABLE_IDS.StableEntityId(
        entity_type="role",
        name="System Architect",
        semantic_id="role-solution-architect",
        opaque_id=STABLE_IDS.generate_opaque_id("role-solution-architect"),
    )

    validation = STABLE_IDS.validate_stable_id_immutability(previous, current)

    assert len(validation.warnings) == 1
    assert "Stable ID changed for role 'System Architect'" in validation.warnings[0]
    assert len(validation.rename_events) == 1
    event = validation.rename_events[0]
    assert event.previous_semantic_id == "role-system-architect"
    assert event.current_semantic_id == "role-solution-architect"