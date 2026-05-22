from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "ensure_bmad_installer_updated.py"
SPEC = importlib.util.spec_from_file_location("ensure_bmad_installer_updated", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class StrictValidationTests(unittest.TestCase):
    def _write_csv(self, path: Path, header: list[str], rows: list[list[str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)

    def _build_repo(self, *, bad_hash: bool = False, omit_skill_manifest_row: bool = False) -> Path:
        root = Path(tempfile.mkdtemp(prefix="bmad-installer-test-"))
        skill_path = root / "skills/lens-sample/SKILL.md"
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        skill_path.write_text("---\nname: lens-sample\n---\n", encoding="utf-8")

        skill_manifest_rows = []
        if not omit_skill_manifest_row:
            skill_manifest_rows.append(
                [
                    "lens-sample",
                    "lens-sample",
                    "sample",
                    "lens",
                    "skills/lens-sample/SKILL.md",
                ]
            )

        self._write_csv(
            root / "_bmad/_config/skill-manifest.csv",
            ["canonicalId", "name", "description", "module", "path"],
            skill_manifest_rows,
        )

        skill_hash = MODULE.sha256(skill_path)
        if bad_hash:
            skill_hash = "0" * 64

        self._write_csv(
            root / "_bmad/_config/files-manifest.csv",
            ["type", "name", "module", "path", "hash"],
            [["md", "SKILL", "lens", "skills/lens-sample/SKILL.md", skill_hash]],
        )

        return root

    def test_strict_validation_passes_when_manifests_match_disk(self) -> None:
        repo_root = self._build_repo()
        status = MODULE.validate_strict(repo_root)
        self.assertEqual(status, 0)

    def test_strict_validation_fails_when_skill_manifest_missing_entry(self) -> None:
        repo_root = self._build_repo(omit_skill_manifest_row=True)
        status = MODULE.validate_strict(repo_root)
        self.assertEqual(status, 1)

    def test_strict_validation_fails_when_hash_mismatch(self) -> None:
        repo_root = self._build_repo(bad_hash=True)
        status = MODULE.validate_strict(repo_root)
        self.assertEqual(status, 1)


if __name__ == "__main__":
    unittest.main()
