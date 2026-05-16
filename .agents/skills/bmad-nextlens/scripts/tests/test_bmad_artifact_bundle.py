from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parent.parent


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


DOWNSTREAM = _load_module("nextlens_downstream_hierarchy_bundle", "downstream_hierarchy.py")


def test_build_bundle_normalizes_paths_and_validates() -> None:
    bundle = DOWNSTREAM.build_bmad_artifact_bundle(
        packet_id="packet-1",
        feature_id="feature-1",
        artifacts=[
            {"id": "prd", "type": "prd", "path": "docs/./prd.md", "status": "complete"}
        ],
        stories=[
            {
                "id": "story-1",
                "title": "Story One",
                "status": "ready",
                "tracesTo": ["prd", "feature-1"],
                "createdAt": "2026-05-14T10:00:00Z",
            }
        ],
        now_factory=lambda: datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc),
    )

    assert bundle["artifacts"][0]["path"] == "docs/prd.md"
    result = DOWNSTREAM.validate_bmad_artifact_bundle(bundle)
    assert result.is_valid
    assert result.status == "pass"


def test_bundle_validation_flags_bad_path_and_trace() -> None:
    bundle = {
        "schemaVersion": "nextlens.bmad-artifact-bundle.v1",
        "packetId": "packet-1",
        "featureId": "feature-1",
        "artifacts": [
            {"id": "prd", "type": "prd", "path": "docs\\prd.md", "status": "complete"}
        ],
        "stories": [
            {
                "id": "story-1",
                "title": "Story One",
                "status": "ready",
                "tracesTo": ["unknown-artifact"],
                "createdAt": "2026-05-14T10:00:00Z",
            }
        ],
        "createdAt": "2026-05-14T10:00:00Z",
    }

    result = DOWNSTREAM.validate_bmad_artifact_bundle(bundle)

    assert not result.is_valid
    assert "normalized path" in _error_by_field(result, "artifacts[0].path").expected_type
    assert _error_by_field(result, "stories[0].tracesTo").expected_type == "known artifact or feature reference"


def _error_by_field(result: object, field_name: str) -> object:
    for error in result.errors:
        if error.field == field_name:
            return error
    raise AssertionError(f"expected validation error for {field_name}")
