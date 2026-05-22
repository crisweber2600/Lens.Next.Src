from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "bug_reporter_ops.py"


class BugReporterOpsTests(unittest.TestCase):
    def test_create_record_and_close_bug(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            feature = root / "docs" / "features" / "demo-feature"
            feature.mkdir(parents=True)
            (feature / "feature.yaml").write_text("feature_id: demo-feature\n", encoding="utf-8")

            create = subprocess.run(
                [
                    "python",
                    str(SCRIPT),
                    "create-bug",
                    "--project-root",
                    str(root),
                    "--feature-id",
                    "demo-feature",
                    "--slug",
                    "ui-crash",
                    "--title",
                    "UI crash",
                    "--what-happened",
                    "Crash happened",
                    "--what-should-have-happened",
                    "No crash",
                    "--chat-history",
                    "User said it crashes",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(create.returncode, 0, msg=create.stderr)
            create_payload = json.loads(create.stdout)
            self.assertTrue(Path(create_payload["path"]).exists())

            record = subprocess.run(
                [
                    "python",
                    str(SCRIPT),
                    "record-quickdev-pr",
                    "--project-root",
                    str(root),
                    "--slug",
                    "ui-crash",
                    "--pr-url",
                    "https://example.test/pr/1",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(record.returncode, 0, msg=record.stderr)

            close = subprocess.run(
                [
                    "python",
                    str(SCRIPT),
                    "close-quickdev-bug",
                    "--project-root",
                    str(root),
                    "--slug",
                    "ui-crash",
                    "--summary",
                    "Fixed click handler",
                    "--validation-summary",
                    "Added focused unit coverage",
                    "--doctor-status",
                    "deferred",
                    "--doctor-rationale",
                    "Doctor run deferred to post-merge",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(close.returncode, 0, msg=close.stderr)
            close_payload = json.loads(close.stdout)
            self.assertIn("/Fixed/", close_payload["path"])
            self.assertTrue(Path(close_payload["path"]).exists())

    def test_close_requires_doctor_evidence_when_passed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            feature = root / "docs" / "features" / "demo-feature"
            feature.mkdir(parents=True)
            (feature / "feature.yaml").write_text("feature_id: demo-feature\n", encoding="utf-8")

            subprocess.run(
                [
                    "python",
                    str(SCRIPT),
                    "create-bug",
                    "--project-root",
                    str(root),
                    "--feature-id",
                    "demo-feature",
                    "--slug",
                    "ui-crash",
                    "--title",
                    "UI crash",
                    "--what-happened",
                    "Crash happened",
                    "--what-should-have-happened",
                    "No crash",
                    "--chat-history",
                    "User said it crashes",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            close = subprocess.run(
                [
                    "python",
                    str(SCRIPT),
                    "close-quickdev-bug",
                    "--project-root",
                    str(root),
                    "--slug",
                    "ui-crash",
                    "--summary",
                    "Fixed",
                    "--validation-summary",
                    "Validated",
                    "--doctor-status",
                    "passed",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(close.returncode, 0)
            payload = json.loads(close.stdout)
            self.assertEqual(payload["error"], "missing_doctor_evidence")


if __name__ == "__main__":
    unittest.main()
