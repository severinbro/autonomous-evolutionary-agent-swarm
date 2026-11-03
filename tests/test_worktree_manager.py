"""Tests for scripts/worktree_manager.py create/cleanup (used by /invoke-swarm best-of-3)."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "worktree_manager.py"


class WorktreeCleanupTest(unittest.TestCase):
    def setUp(self):
        # Worktrees are created next to the repository, so the repository gets its own temporary parent.
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "proj"
        self.repo.mkdir()
        (self.repo / "a.txt").write_text("a\n")
        self._git("init", "-q", "-b", "main")
        self._git("add", "-A")
        self._git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")

    def tearDown(self):
        self._tmp.cleanup()

    def _git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True, text=True).stdout

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args], cwd=self.repo, capture_output=True, text=True, check=False
        )

    def _branches(self):
        return self._git("branch", "--format=%(refname:short)").split()

    def test_create_places_worktree_next_to_repo(self):
        res = self._run("create", "t1-bo3-1", "--base", "main")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue((self.repo.parent / "proj-t1-bo3-1" / "a.txt").is_file())
        self.assertIn("t1-bo3-1", self._branches())

    def test_cleanup_keeps_branch_without_flag(self):
        self._run("create", "t1-bo3-1", "--base", "main")
        res = self._run("cleanup", "t1-bo3-1")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertFalse((self.repo.parent / "proj-t1-bo3-1").exists())
        self.assertIn("t1-bo3-1", self._branches())

    def test_cleanup_delete_branch_removes_worktree_and_branch(self):
        self._run("create", "t1-bo3-2", "--base", "main")
        res = self._run("cleanup", "t1-bo3-2", "--delete-branch")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertFalse((self.repo.parent / "proj-t1-bo3-2").exists())
        self.assertNotIn("t1-bo3-2", self._branches())


if __name__ == "__main__":
    unittest.main()
