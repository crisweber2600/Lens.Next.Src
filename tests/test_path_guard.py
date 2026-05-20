from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CREATE_SCRIPTS = REPO_ROOT / "skills" / "bul-create-packet" / "scripts"
if str(CREATE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(CREATE_SCRIPTS))

from path_guard import DENIED_CATEGORIES, guard_path, guard_write_plan


def test_path_guard_allows_configured_output_roots(tmp_path: Path) -> None:
    packet_root = tmp_path / "docs" / "bottom-up-lens"
    report_root = tmp_path / "_bmad-output" / "bottom-up-lens"
    target = packet_root / "packet.json"
    result = guard_path(target, [packet_root, report_root], "packetPath")
    assert result["status"] == "pass"
    assert result["matchedRoot"] == str(packet_root.resolve())
    assert result["normalizedPath"] == str(target.resolve())


def test_path_guard_blocks_traversal_outside_allowed_roots(tmp_path: Path) -> None:
    packet_root = tmp_path / "docs" / "bottom-up-lens"
    target = packet_root / ".." / "outside.json"
    result = guard_path(target, [packet_root], "packetPath")
    assert result["status"] == "fail"
    assert result["pathGuard"]["category"] == "outside-allowed-roots"


def test_path_guard_blocks_forbidden_fixture_categories(tmp_path: Path) -> None:
    allowed = tmp_path / "docs" / "bottom-up-lens"
    fixtures = json.loads((REPO_ROOT / "evals" / "forbidden-write-fixtures.json").read_text(encoding="utf-8"))["fixtures"]
    categories_seen = set()
    for fixture in fixtures:
        result = guard_path(tmp_path / fixture["path"], [allowed], "plannedWrites")
        assert result["status"] == "fail", fixture
        assert result["pathGuard"]["category"] == fixture["category"], fixture
        categories_seen.add(fixture["category"])
    assert categories_seen >= set(DENIED_CATEGORIES) - {"control-github"}


def test_path_guard_allows_harmless_substrings_under_output_root(tmp_path: Path) -> None:
    allowed = tmp_path / "docs" / "bottom-up-lens"
    for relative in ("my-graphical-ui/packet.json", "release-notes/packet.json", "team-services-output/packet.json"):
        result = guard_path(allowed / relative, [allowed], "packetPath")
        assert result["status"] == "pass", relative


def test_write_plan_uses_guard_for_all_paths(tmp_path: Path) -> None:
    allowed = tmp_path / "docs" / "bottom-up-lens"
    result = guard_write_plan([allowed / "packet.json", tmp_path / "docs" / "derived-graph" / "graph.json"], [allowed])
    assert result["status"] == "fail"
    assert result["failures"][0]["pathGuard"]["category"] == "graph"
