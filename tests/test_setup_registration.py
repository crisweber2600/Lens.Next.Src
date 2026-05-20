from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_merge_config_registers_defaults_idempotently(tmp_path: Path) -> None:
    merge_config = load_module(REPO_ROOT / "skills" / "bul-setup" / "scripts" / "merge-config.py")
    module_yaml = yaml.safe_load((REPO_ROOT / "skills" / "bul-setup" / "assets" / "module.yaml").read_text(encoding="utf-8"))
    existing = {"output_folder": "docs", "bul": {"zombie": True}}
    answers = {"core": {}, "module": {}}

    once = merge_config.merge_config(existing, module_yaml, answers)
    twice = merge_config.merge_config(once, module_yaml, answers)

    assert once == twice
    assert once["bul"]["packet_output_path"] == "{project-root}/docs/bottom-up-lens"
    assert once["bul"]["reports_output_path"] == "{project-root}/_bmad-output/bottom-up-lens"
    assert once["bul"]["default_packet_schema_version"] == "bul.feature-packet.v1"
    assert "zombie" not in once["bul"]


def test_merge_help_csv_replaces_zombie_rows(tmp_path: Path) -> None:
    merge_help = load_module(REPO_ROOT / "skills" / "bul-setup" / "scripts" / "merge-help-csv.py")
    target = tmp_path / "module-help.csv"
    source = REPO_ROOT / "skills" / "bul-setup" / "assets" / "module-help.csv"
    stale_rows = [
        merge_help.HEADER,
        ["Bottom-Up LENS", "bul-create-packet", "Old", "BC", "old", "create-packet", "", "anytime", "", "", "false", "", ""],
        ["Other", "other-skill", "Other", "OT", "other", "run", "", "anytime", "", "", "false", "", ""],
    ]
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(stale_rows)

    merge_help.main.__globals__["parse_args"] = lambda: type("Args", (), {"target": str(target), "source": str(source), "legacy_dir": None, "module_code": "bul", "verbose": False})()
    assert merge_help.main() == 0
    first = target.read_text(encoding="utf-8")
    merge_help.main()
    second = target.read_text(encoding="utf-8")

    rows = list(csv.DictReader(target.open(newline="", encoding="utf-8")))
    assert first == second
    assert [row["skill"] for row in rows].count("bul-create-packet") == 1
    assert any(row["skill"] == "other-skill" for row in rows)
    assert {row["action"] for row in rows if row["module"] == "Bottom-Up LENS"} == {"configure", "create-packet", "validate-packet", "verify-receipt"}


def test_setup_assets_do_not_target_forbidden_surfaces() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            REPO_ROOT / "skills" / "bul-setup" / "assets" / "module.yaml",
            REPO_ROOT / "skills" / "bul-setup" / "assets" / "module-help.csv",
        ]
    ).lower()
    forbidden_runtime_targets = ["lens.core.governance", "release/", "feature-yaml-ops", "lens-work", "bmad-nextlens"]
    for marker in forbidden_runtime_targets:
        assert marker not in text
