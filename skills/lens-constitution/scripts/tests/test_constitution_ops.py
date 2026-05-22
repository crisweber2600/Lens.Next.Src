from __future__ import annotations

import argparse
import importlib.util
import shlex
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "constitution_ops.py"
SPEC = importlib.util.spec_from_file_location("constitution_ops", SCRIPT_PATH)
constitution_ops = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(constitution_ops)


def write_constitution(path: Path, data: dict, prose: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + constitution_ops.yaml.safe_dump(data, sort_keys=True) + "---\n" + prose,
        encoding="utf-8",
    )


def write_frontmatter(path: Path, metadata: dict, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + constitution_ops.yaml.safe_dump(metadata, sort_keys=True) + "---\n" + body,
        encoding="utf-8",
    )


def write_feature_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(constitution_ops.yaml.safe_dump(data, sort_keys=True), encoding="utf-8")


class ConstitutionOpsTests(unittest.TestCase):
    def test_resolve_reports_recovery_when_constitution_root_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_feature_yaml(
                root / "docs" / "features" / "rollcall" / "feature.yaml",
                {
                    "feature_id": "rollcall",
                    "stable_id": "feature:rollcall",
                    "entity_type": "feature",
                    "track": "full",
                    "phase": "preplan",
                    "belongs_to": "domain:identity",
                },
            )

            args = argparse.Namespace(
                project_root=root,
                constitution_root=None,
                feature_id="rollcall",
                feature_path=None,
                domain=None,
                service=None,
                repo=None,
                phase=None,
                track=None,
                dry_run=False,
            )

            result, code = constitution_ops.cmd_resolve(args)

            self.assertEqual(code, 1)
            self.assertEqual(result["error"], "constitution_root_not_found")
            self.assertEqual(result["recovery"]["action"], "bootstrap_constitution")
            self.assertIn("bootstrap", result["recovery"]["suggested_command"])
            command_parts = shlex.split(result["recovery"]["suggested_command"])
            self.assertEqual(
                command_parts[-2:],
                ["--constitution-root", str((root / ".lens" / ".constitution").resolve())],
            )

    def test_resolve_reports_recovery_when_org_constitution_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            constitution_root = root / ".lens" / ".constitution"
            constitution_root.mkdir(parents=True, exist_ok=True)

            write_feature_yaml(
                root / "docs" / "features" / "rollcall" / "feature.yaml",
                {
                    "feature_id": "rollcall",
                    "stable_id": "feature:rollcall",
                    "entity_type": "feature",
                    "track": "full",
                    "phase": "preplan",
                    "belongs_to": "domain:identity",
                },
            )

            args = argparse.Namespace(
                project_root=root,
                constitution_root=None,
                feature_id="rollcall",
                feature_path=None,
                domain=None,
                service=None,
                repo=None,
                phase=None,
                track=None,
                dry_run=False,
            )

            result, code = constitution_ops.cmd_resolve(args)

            self.assertEqual(code, 1)
            self.assertEqual(result["error"], "org_constitution_missing")
            self.assertEqual(result["recovery"]["action"], "bootstrap_constitution")
            self.assertIn("bootstrap", result["recovery"]["suggested_command"])
            command_parts = shlex.split(result["recovery"]["suggested_command"])
            self.assertEqual(
                command_parts[-2:],
                ["--constitution-root", str(constitution_root.resolve())],
            )

    def test_bootstrap_creates_org_constitution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            args = argparse.Namespace(
                project_root=root,
                constitution_root=None,
                dry_run=False,
            )
            result, code = constitution_ops.cmd_bootstrap(args)

            self.assertEqual(code, 0)
            self.assertEqual(result["status"], "created")

            org_path = Path(result["org_constitution"])
            self.assertTrue(org_path.exists())
            content = org_path.read_text(encoding="utf-8")
            self.assertIn("permitted_tracks", content)
            self.assertIn("gate_mode", content)

    def test_resolve_uses_local_feature_lineage_and_combines_prose(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            constitution_root = root / ".lens" / ".constitution"
            write_constitution(
                constitution_root / "org" / "constitution.md",
                {"permitted_tracks": ["full", "express"], "gate_mode": "informational"},
                "Org article one.",
            )
            write_constitution(
                constitution_root / "identity" / "constitution.md",
                {"additional_review_participants": ["security"]},
                "Domain article two.",
            )
            write_constitution(
                constitution_root / "identity" / "attendance" / "constitution.md",
                {"gate_mode": "hard", "enforce_review": True},
                "Service article three.",
            )

            write_frontmatter(
                root / "docs" / "program" / "ledger" / "program.md",
                {
                    "stable_id": "program:alpha",
                    "entity_type": "program",
                    "title": "Alpha",
                    "status": "active",
                    "publication_state": "published",
                    "updated_at": "2026-05-21",
                },
            )
            write_frontmatter(
                root / "docs" / "program" / "identity" / "ledger" / "domain.md",
                {
                    "stable_id": "domain:identity",
                    "entity_type": "domain",
                    "title": "Identity",
                    "status": "active",
                    "publication_state": "published",
                    "belongs_to": "program:alpha",
                    "updated_at": "2026-05-21",
                },
            )
            write_frontmatter(
                root / "docs" / "program" / "identity" / "attendance" / "ledger" / "service.md",
                {
                    "stable_id": "service:attendance",
                    "entity_type": "service",
                    "title": "Attendance",
                    "status": "active",
                    "publication_state": "published",
                    "belongs_to": "domain:identity",
                    "updated_at": "2026-05-21",
                },
            )
            write_feature_yaml(
                root / "docs" / "features" / "rollcall" / "feature.yaml",
                {
                    "feature_id": "rollcall",
                    "stable_id": "feature:rollcall",
                    "entity_type": "feature",
                    "track": "full",
                    "phase": "preplan",
                    "belongs_to": "service:attendance",
                    "docs_path": "docs/features/rollcall",
                },
            )

            args = argparse.Namespace(
                project_root=root,
                constitution_root=None,
                feature_id="rollcall",
                feature_path=None,
                domain=None,
                service=None,
                repo=None,
                phase=None,
                track=None,
                dry_run=False,
            )

            result, code = constitution_ops.cmd_resolve(args)

            self.assertEqual(code, 0)
            self.assertEqual(result["scope"]["domain"], "identity")
            self.assertEqual(result["scope"]["service"], "attendance")
            self.assertEqual(result["constitution_root"], str(constitution_root.resolve()))
            self.assertEqual(result["levels_loaded"], ["org", "domain", "service"])
            self.assertEqual(result["resolved_constitution"]["gate_mode"], "hard")
            self.assertIn("Org article one.", result["combined_prose"])
            self.assertIn("Domain article two.", result["combined_prose"])
            self.assertIn("Service article three.", result["combined_prose"])

    def test_progressive_display_maps_local_phase_and_track(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            constitution_root = root / ".lens" / ".constitution"
            write_constitution(
                constitution_root / "org" / "constitution.md",
                {
                    "permitted_tracks": ["express", "full"],
                    "required_artifacts": {"planning": ["security-review"]},
                },
                "Org guidance.",
            )
            write_frontmatter(
                root / "docs" / "program" / "identity" / "ledger" / "domain.md",
                {
                    "stable_id": "domain:identity",
                    "entity_type": "domain",
                    "title": "Identity",
                    "status": "active",
                    "publication_state": "published",
                    "belongs_to": "program:alpha",
                    "updated_at": "2026-05-21",
                },
            )
            write_feature_yaml(
                root / "docs" / "features" / "mini" / "feature.yaml",
                {
                    "feature_id": "mini",
                    "stable_id": "feature:mini",
                    "entity_type": "feature",
                    "track": "express",
                    "phase": "expressplan",
                    "belongs_to": "domain:identity",
                },
            )

            args = argparse.Namespace(
                project_root=root,
                constitution_root=None,
                feature_id="mini",
                feature_path=None,
                domain=None,
                service=None,
                repo=None,
                phase=None,
                track=None,
                dry_run=False,
            )

            result, code = constitution_ops.cmd_progressive_display(args)

            self.assertEqual(code, 0)
            self.assertEqual(result["local_phase"], "expressplan")
            self.assertEqual(result["constitution_phase"], "planning")
            self.assertEqual(result["required_artifacts_for_phase"], ["security-review"])
            self.assertTrue(result["track_permitted"])

    def test_check_compliance_uses_local_artifact_aliases_for_full_track(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            constitution_root = root / ".lens" / ".constitution"
            write_constitution(
                constitution_root / "org" / "constitution.md",
                {
                    "permitted_tracks": ["full"],
                    "required_artifacts": {"planning": ["business-plan", "tech-plan"]},
                    "gate_mode": "hard",
                },
                "Org guidance.",
            )
            write_frontmatter(
                root / "docs" / "program" / "identity" / "attendance" / "ledger" / "service.md",
                {
                    "stable_id": "service:attendance",
                    "entity_type": "service",
                    "title": "Attendance",
                    "status": "active",
                    "publication_state": "published",
                    "belongs_to": "domain:identity",
                    "updated_at": "2026-05-21",
                },
            )
            write_frontmatter(
                root / "docs" / "program" / "identity" / "ledger" / "domain.md",
                {
                    "stable_id": "domain:identity",
                    "entity_type": "domain",
                    "title": "Identity",
                    "status": "active",
                    "publication_state": "published",
                    "belongs_to": "program:alpha",
                    "updated_at": "2026-05-21",
                },
            )
            feature_dir = root / "docs" / "features" / "ledger-fix"
            write_feature_yaml(
                feature_dir / "feature.yaml",
                {
                    "feature_id": "ledger-fix",
                    "stable_id": "feature:ledger-fix",
                    "entity_type": "feature",
                    "track": "full",
                    "phase": "techplan",
                    "belongs_to": "service:attendance",
                },
            )
            feature_dir.joinpath("product-brief.md").write_text("# brief\n", encoding="utf-8")
            feature_dir.joinpath("architecture.md").write_text("# architecture\n", encoding="utf-8")

            args = argparse.Namespace(
                project_root=root,
                constitution_root=None,
                feature_id="ledger-fix",
                feature_path=None,
                domain=None,
                service=None,
                repo=None,
                phase=None,
                track=None,
                artifacts_path=None,
                dry_run=False,
            )

            result, code = constitution_ops.cmd_check_compliance(args)

            self.assertEqual(code, 0)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["constitution_phase"], "planning")

    def test_check_compliance_blocks_when_alias_equivalent_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            constitution_root = root / ".lens" / ".constitution"
            write_constitution(
                constitution_root / "org" / "constitution.md",
                {
                    "permitted_tracks": ["full"],
                    "required_artifacts": {"planning": ["tech-plan"]},
                    "gate_mode": "hard",
                },
                "Org guidance.",
            )
            write_frontmatter(
                root / "docs" / "program" / "identity" / "ledger" / "domain.md",
                {
                    "stable_id": "domain:identity",
                    "entity_type": "domain",
                    "title": "Identity",
                    "status": "active",
                    "publication_state": "published",
                    "belongs_to": "program:alpha",
                    "updated_at": "2026-05-21",
                },
            )
            write_feature_yaml(
                root / "docs" / "features" / "missing-tech" / "feature.yaml",
                {
                    "feature_id": "missing-tech",
                    "stable_id": "feature:missing-tech",
                    "entity_type": "feature",
                    "track": "full",
                    "phase": "businessplan",
                    "belongs_to": "domain:identity",
                },
            )
            args = argparse.Namespace(
                project_root=root,
                constitution_root=None,
                feature_id="missing-tech",
                feature_path=None,
                domain=None,
                service=None,
                repo=None,
                phase=None,
                track=None,
                artifacts_path=None,
                dry_run=False,
            )

            result, code = constitution_ops.cmd_check_compliance(args)

            self.assertEqual(code, 2)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(result["hard_gate_failures"])


if __name__ == "__main__":
    unittest.main()