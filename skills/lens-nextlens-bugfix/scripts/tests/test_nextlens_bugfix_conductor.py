from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "nextlens_bugfix_conductor.py"


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def init_repo(path: Path) -> None:
    run(["git", "init"], cwd=path)
    run(["git", "config", "user.email", "test@example.com"], cwd=path)
    run(["git", "config", "user.name", "Test User"], cwd=path)
    (path / "README.md").write_text("init\n", encoding="utf-8")
    run(["git", "add", "README.md"], cwd=path)
    run(["git", "commit", "-m", "init"], cwd=path)


class NextLensBugfixConductorTests(unittest.TestCase):
    def make_project(self) -> tuple[Path, Path]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        project_root = Path(temp_dir.name)

        repo = project_root / "TargetProjects" / "lens.next.src"
        repo.mkdir(parents=True)
        init_repo(repo)

        feature = project_root / "docs" / "features" / "demo-feature"
        feature.mkdir(parents=True)
        (feature / "feature.yaml").write_text("feature_id: demo-feature\n", encoding="utf-8")

        skills_root = project_root / "skills" / "lens-nextlens-bugfix" / "scripts"
        skills_root.mkdir(parents=True)
        for name in ("nextlens_fix_spec.py", "bug_reporter_ops.py"):
            source = Path(__file__).resolve().parents[1] / name
            (skills_root / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

        return project_root, repo

    def test_prepare_returns_contract_fields(self) -> None:
        project_root, _repo = self.make_project()

        result = run(
            [
                "python",
                str(SCRIPT),
                "prepare",
                "--project-root",
                str(project_root),
                "--feature-id",
                "demo-feature",
                "--what-happened",
                "settings save crashes",
                "--what-should-have-happened",
                "settings should save",
                "--chat-history",
                "user report",
            ]
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        for key in ("bug_slug", "working_branch", "base_branch", "starting_head", "allowed_write_root"):
            self.assertTrue(payload.get(key), msg=f"missing {key}")

    def test_prepare_blocks_dirty_working_tree(self) -> None:
        project_root, repo = self.make_project()
        (repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")

        result = run(
            [
                "python",
                str(SCRIPT),
                "prepare",
                "--project-root",
                str(project_root),
                "--feature-id",
                "demo-feature",
                "--what-happened",
                "settings save crashes",
                "--what-should-have-happened",
                "settings should save",
                "--chat-history",
                "user report",
            ]
        )

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["code"], "dirty_working_tree")

    def test_close_blocks_bugfix_no_changes(self) -> None:
        project_root, _repo = self.make_project()

        prep = run(
            [
                "python",
                str(SCRIPT),
                "prepare",
                "--project-root",
                str(project_root),
                "--feature-id",
                "demo-feature",
                "--what-happened",
                "settings save crashes",
                "--what-should-have-happened",
                "settings should save",
                "--chat-history",
                "user report",
            ]
        )
        payload = json.loads(prep.stdout)

        close = run(
            [
                "python",
                str(SCRIPT),
                "close",
                "--project-root",
                str(project_root),
                "--bug-slug",
                payload["bug_slug"],
                "--working-branch",
                payload["working_branch"],
                "--base-branch",
                payload["base_branch"],
                "--starting-head",
                payload["starting_head"],
                "--allowed-write-root",
                payload["allowed_write_root"],
                "--summary",
                "no-op",
                "--validation-summary",
                "none",
                "--doctor-status",
                "deferred",
                "--doctor-rationale",
                "doctor deferred",
                "--skip-push",
                "--pr-url",
                "https://example.test/pr/1",
            ]
        )

        self.assertNotEqual(close.returncode, 0)
        close_payload = json.loads(close.stdout)
        self.assertEqual(close_payload["code"], "bugfix_no_changes")

    def test_close_success_outputs_contract_fields(self) -> None:
        project_root, repo = self.make_project()

        prep = run(
            [
                "python",
                str(SCRIPT),
                "prepare",
                "--project-root",
                str(project_root),
                "--feature-id",
                "demo-feature",
                "--what-happened",
                "settings save crashes",
                "--what-should-have-happened",
                "settings should save",
                "--chat-history",
                "user report",
            ]
        )
        payload = json.loads(prep.stdout)

        (repo / "fix.txt").write_text("fixed\n", encoding="utf-8")
        run(["git", "add", "fix.txt"], cwd=repo)
        run(["git", "commit", "-m", "fix"], cwd=repo)

        close = run(
            [
                "python",
                str(SCRIPT),
                "close",
                "--project-root",
                str(project_root),
                "--bug-slug",
                payload["bug_slug"],
                "--working-branch",
                payload["working_branch"],
                "--base-branch",
                payload["base_branch"],
                "--starting-head",
                payload["starting_head"],
                "--allowed-write-root",
                payload["allowed_write_root"],
                "--summary",
                "fixed bug",
                "--validation-summary",
                "focused tests",
                "--doctor-status",
                "deferred",
                "--doctor-rationale",
                "doctor deferred",
                "--skip-push",
                "--pr-url",
                "https://example.test/pr/1",
            ]
        )

        self.assertEqual(close.returncode, 0, msg=close.stderr)
        close_payload = json.loads(close.stdout)
        for key in ("working_branch", "commit_hash", "PR URL", "bug_artifact_path"):
            self.assertTrue(close_payload.get(key), msg=f"missing {key}")


if __name__ == "__main__":
    unittest.main()
