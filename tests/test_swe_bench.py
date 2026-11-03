"""Tests for benchmarks/swe/swe_bench.py patch extraction (what the SWE-bench grader receives)."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SWE_DIR = Path(__file__).resolve().parent.parent / "benchmarks" / "swe"
sys.path.insert(0, str(SWE_DIR))

import swe_bench  # noqa: E402


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


class ExtractPatchTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        (self.ws / "pkg").mkdir()
        (self.ws / "pkg" / "core.py").write_text("X = 1\n")
        (self.ws / "tests").mkdir()
        (self.ws / "tests" / "test_core.py").write_text("def test():\n    pass\n")
        git(self.ws, "init", "-q")
        git(self.ws, "add", "-A")
        git(self.ws, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
        self.start = git(self.ws, "rev-parse", "HEAD").strip()
        (self.ws / ".git" / "info" / "exclude").write_text("TASK_SPEC.md\nrun_tests.sh\n.swarm/\n")

    def tearDown(self):
        self._tmp.cleanup()

    def test_keeps_source_changes_and_new_files_but_drops_tests_and_helpers(self):
        (self.ws / "pkg" / "core.py").write_text("X = 2\n")
        (self.ws / "pkg" / "new_module.py").write_text("Y = 3\n")
        (self.ws / "tests" / "test_core.py").write_text("def test():\n    assert True\n")
        (self.ws / "pkg" / "test_new.py").write_text("def test_new():\n    pass\n")
        (self.ws / "TASK_SPEC.md").write_text("spec\n")
        (self.ws / "run_tests.sh").write_text("#!/bin/sh\n")
        (self.ws / ".swarm").mkdir()
        (self.ws / ".swarm" / "board.md").write_text("board\n")
        patch = swe_bench.extract_patch(self.ws, self.start)
        self.assertIn("pkg/core.py", patch)
        self.assertIn("pkg/new_module.py", patch)
        for absent in ("tests/test_core.py", "pkg/test_new.py", "TASK_SPEC.md", "run_tests.sh", ".swarm"):
            self.assertNotIn(absent, patch)
        self.assertEqual(git(self.ws, "status", "--short", "--", "pkg/new_module.py").strip(), "?? pkg/new_module.py",
                         "extraction must not touch the workspace's own index")

    def test_committed_changes_are_included_and_untouched_tree_gives_empty_patch(self):
        self.assertEqual(swe_bench.extract_patch(self.ws, self.start), "")
        (self.ws / "pkg" / "core.py").write_text("X = 5\n")
        git(self.ws, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "agent commit")
        self.assertIn("+X = 5", swe_bench.extract_patch(self.ws, self.start))


if __name__ == "__main__":
    unittest.main()
