from __future__ import annotations

import argparse
import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "lens_preflight.py"
SPEC = importlib.util.spec_from_file_location("lens_preflight", SCRIPT_PATH)
lens_preflight = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(lens_preflight)


def make_args(root: Path, **overrides) -> argparse.Namespace:
    values = {
        "project_root": root,
        "work_intake_path": "docs/features",
        "feature_archive_path": "docs/features",
        "landscape_root": "docs",
        "reporting_output_path": "_bmad-output/lens",
        "lens_enabled": False,
        "lens_governance_repo_path": "",
        "lens_lifecycle_contract": "",
        "lens_context_path": "",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def write_schema(root: Path) -> None:
    schema = root / "skills" / "lens-setup" / "assets" / "metadata-schema.md"
    schema.parent.mkdir(parents=True)
    schema.write_text("# Lens Metadata Contract\n", encoding="utf-8")


class LensPreflightTests(unittest.TestCase):
    def test_standalone_preflight_passes_without_lens(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "docs" / "features").mkdir(parents=True)
            (root / "_bmad-output" / "lens").mkdir(parents=True)
            write_schema(root)

            result = lens_preflight.run_preflight(make_args(root))

            self.assertEqual(result["status"], "pass")
            self.assertFalse(result["lens"]["detected"])
            self.assertEqual(result["blocking_count"], 0)

    def test_lens_context_is_discovered_without_calling_lens_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "docs" / "features" / "feature-one").mkdir(parents=True)
            (root / "_bmad-output" / "lens").mkdir(parents=True)
            (root / "lens.core" / "_bmad" / "lens-work").mkdir(parents=True)
            (root / "lens.core" / "_bmad" / "lens-work" / "lifecycle.yaml").write_text(
                "phase_order:\n  - preplan\n",
                encoding="utf-8",
            )
            (root / "lens.core").mkdir(exist_ok=True)
            (root / "lens.core" / "AGENTS.md").write_text("# Lens\n", encoding="utf-8")
            (root / "governance").mkdir()
            (root / ".lens" / "personal").mkdir(parents=True)
            (root / ".lens" / "governance-setup.yaml").write_text(
                "governance_repo_path: governance\n",
                encoding="utf-8",
            )
            (root / ".lens" / "personal" / "context.yaml").write_text(
                "feature_id: feature-one\ntrack: full\nphase: preplan\ndocs_path: docs/features/feature-one\n",
                encoding="utf-8",
            )
            write_schema(root)

            result = lens_preflight.run_preflight(make_args(root, lens_enabled=True))

            self.assertEqual(result["status"], "pass")
            self.assertTrue(result["lens"]["detected"])
            self.assertEqual(result["lens"]["feature_id"], "feature-one")
            self.assertEqual(result["lens"]["track"], "full")
            self.assertTrue(result["lens"]["governance_repo_ready"])

    def test_lens_mode_blocks_when_governance_repo_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "docs" / "features").mkdir(parents=True)
            (root / "_bmad-output" / "lens").mkdir(parents=True)
            (root / "lens.core" / "_bmad" / "lens-work").mkdir(parents=True)
            (root / "lens.core" / "_bmad" / "lens-work" / "lifecycle.yaml").write_text(
                "phase_order:\n  - preplan\n",
                encoding="utf-8",
            )
            write_schema(root)

            result = lens_preflight.run_preflight(make_args(root, lens_enabled=True))
            codes = {finding["code"] for finding in result["blocking"]}

            self.assertEqual(result["status"], "blocked")
            self.assertIn("lens_governance_repo_unavailable", codes)


if __name__ == "__main__":
    unittest.main()