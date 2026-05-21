from __future__ import annotations

import argparse
import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "ausx_projection.py"
SPEC = importlib.util.spec_from_file_location("ausx_projection", SCRIPT_PATH)
ausx_projection = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ausx_projection)


class AusxProjectionTests(unittest.TestCase):
    def test_doctor_blocks_missing_parent_and_reports_unpromoted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            feature_dir = docs / "features" / "feat-one"
            feature_dir.mkdir(parents=True)
            feature_dir.joinpath("feature.md").write_text(
                "---\n"
                "stable_id: feature:one\n"
                "entity_type: feature\n"
                "title: Feature One\n"
                "status: completed\n"
                "publication_state: published\n"
                "belongs_to: service:missing\n"
                "promotion_status: pending\n"
                "updated_at: 2026-05-21\n"
                "---\n"
                "# Feature One\n",
                encoding="utf-8",
            )
            args = argparse.Namespace(
                project_root=root,
                work_intake_path="docs/features",
                feature_archive_path="docs/features",
                landscape_root="docs",
                reporting_output_path="_bmad-output/auspex",
                include_drafts=False,
                verbose=False,
            )
            result = ausx_projection.run_doctor(args)
            codes = {finding["code"] for finding in result["findings"]}
            self.assertEqual(result["status"], "blocked")
            self.assertIn("missing_parent_entity", codes)
            self.assertIn("completed_unpromoted", codes)

    def test_rebuild_writes_generated_outputs_when_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service_dir = root / "docs" / "program" / "domain" / "service" / "ledger"
            service_dir.mkdir(parents=True)
            root.joinpath("docs/program/ledger").mkdir(parents=True)
            root.joinpath("docs/program/ledger/program.md").write_text(
                "---\n"
                "stable_id: program:alpha\n"
                "entity_type: program\n"
                "title: Alpha\n"
                "status: active\n"
                "publication_state: published\n"
                "updated_at: 2026-05-21\n"
                "---\n",
                encoding="utf-8",
            )
            root.joinpath("docs/program/domain/ledger").mkdir(parents=True)
            root.joinpath("docs/program/domain/ledger/domain.md").write_text(
                "---\n"
                "stable_id: domain:identity\n"
                "entity_type: domain\n"
                "title: Identity\n"
                "status: active\n"
                "publication_state: published\n"
                "belongs_to: program:alpha\n"
                "updated_at: 2026-05-21\n"
                "---\n",
                encoding="utf-8",
            )
            service_dir.joinpath("service.md").write_text(
                "---\n"
                "stable_id: service:attendance\n"
                "entity_type: service\n"
                "title: Attendance\n"
                "status: active\n"
                "publication_state: published\n"
                "belongs_to: domain:identity\n"
                "updated_at: 2026-05-21\n"
                "---\n",
                encoding="utf-8",
            )
            args = argparse.Namespace(
                project_root=root,
                work_intake_path="docs/features",
                feature_archive_path="docs/features",
                landscape_root="docs",
                reporting_output_path="_bmad-output/auspex",
                include_drafts=False,
                verbose=False,
                force=False,
            )
            exit_code, result = ausx_projection.run_rebuild(args)
            self.assertEqual(exit_code, 0)
            self.assertEqual(result["status"], "complete")
            self.assertTrue(Path(result["json_path"]).exists())
            self.assertTrue(Path(result["markdown_path"]).exists())


if __name__ == "__main__":
    unittest.main()