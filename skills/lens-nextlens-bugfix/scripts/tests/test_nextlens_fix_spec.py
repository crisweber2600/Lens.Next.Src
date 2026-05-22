from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "nextlens_fix_spec.py"


class NextLensFixSpecTests(unittest.TestCase):
    def test_generates_expected_branch_and_slug(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "TargetProjects" / "lens.next.src").mkdir(parents=True)
            feature_dir = root / "docs" / "features" / "demo-feature"
            feature_dir.mkdir(parents=True)
            (feature_dir / "feature.yaml").write_text("feature_id: demo-feature\n", encoding="utf-8")

            result = subprocess.run(
                [
                    "python",
                    str(SCRIPT),
                    "--project-root",
                    str(root),
                    "--what-happened",
                    "Button click crashes settings page",
                    "--what-should-have-happened",
                    "Settings should save",
                    "--chat-history",
                    "User reported crash",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["bug_slug"], "button-click-crashes-settings-page")
            self.assertEqual(
                payload["bugfix_working_branch"],
                "feature/nextlens-bugfix-button-click-crashes-settings-page",
            )
            self.assertFalse(payload["delegation_blocked"])

    def test_blocks_when_write_root_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            feature_dir = root / "docs" / "features" / "demo-feature"
            feature_dir.mkdir(parents=True)
            (feature_dir / "feature.yaml").write_text("feature_id: demo-feature\n", encoding="utf-8")

            result = subprocess.run(
                [
                    "python",
                    str(SCRIPT),
                    "--project-root",
                    str(root),
                    "--what-happened",
                    "Anything",
                    "--what-should-have-happened",
                    "Anything else",
                    "--chat-history",
                    "Some chat",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertIn("allowed_write_root_missing", payload["delegation_blockers"])


if __name__ == "__main__":
    unittest.main()
