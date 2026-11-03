"""Tests for scripts/attempt_picker.py (cross-testing selection among independent attempts)."""

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import attempt_picker  # noqa: E402

CORRECT = "def clamp(x, lo, hi):\n    return max(lo, min(x, hi))\n"
# Each buggy attempt is wrong on a different edge, and its own tests miss that edge.
BUG_UPPER = "def clamp(x, lo, hi):\n    return max(lo, x)\n"
BUG_LOWER = "def clamp(x, lo, hi):\n    return min(x, hi)\n"

TESTS_CORRECT = (
    "import unittest\nfrom src.calc import clamp\n\n"
    "class T(unittest.TestCase):\n"
    "    def test_inside(self):\n        self.assertEqual(clamp(5, 0, 10), 5)\n"
    "    def test_upper(self):\n        self.assertEqual(clamp(15, 0, 10), 10)\n"
    "    def test_lower(self):\n        self.assertEqual(clamp(-5, 0, 10), 0)\n"
)
TESTS_LOWER_ONLY = (
    "import unittest\nfrom src.calc import clamp\n\n"
    "class T(unittest.TestCase):\n"
    "    def test_lower(self):\n        self.assertEqual(clamp(-1, 0, 3), 0)\n"
)
TESTS_UPPER_ONLY = (
    "import unittest\nfrom src.calc import clamp\n\n"
    "class T(unittest.TestCase):\n"
    "    def test_upper(self):\n        self.assertEqual(clamp(9, 0, 3), 3)\n"
)


class AttemptPickerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def attempt(self, name: str, impl: str, tests: str) -> Path:
        ws = self.root / name
        (ws / "src").mkdir(parents=True)
        (ws / "tests").mkdir()
        (ws / "src" / "__init__.py").write_text("")
        (ws / "src" / "calc.py").write_text(impl)
        (ws / "tests" / "test_calc.py").write_text(tests)
        return ws

    def test_cross_testing_beats_self_reported_success(self):
        # Both buggy attempts pass their own tests; only cross-testing exposes them.
        a1 = self.attempt("a1", BUG_UPPER, TESTS_LOWER_ONLY)
        a2 = self.attempt("a2", BUG_LOWER, TESTS_UPPER_ONLY)
        a3 = self.attempt("a3", CORRECT, TESTS_CORRECT)
        res = attempt_picker.pick([a1, a2, a3])
        self.assertEqual(res["winner"], str(a3))
        scores = {Path(r["attempt"]).name: r for r in res["attempts"]}
        self.assertTrue(scores["a1"]["own_tests_passed"])
        self.assertLess(scores["a1"]["cross_test_score"], scores["a3"]["cross_test_score"])

    def test_check_cmd_failure_outranks_score(self):
        a1 = self.attempt("a1", CORRECT, TESTS_CORRECT)
        a2 = self.attempt("a2", CORRECT, TESTS_CORRECT)
        (a1 / "MARK").write_text("broken")
        res = attempt_picker.pick([a1, a2], check_cmd=f'"{sys.executable}" -c "import os,sys; sys.exit(os.path.exists(\'MARK\'))"')
        self.assertEqual(res["winner"], str(a2))

    def test_install_copies_winner_and_keeps_nothing_stale(self):
        a1 = self.attempt("a1", CORRECT, TESTS_CORRECT)
        dest = self.root / "r1"
        (dest / "src").mkdir(parents=True)
        (dest / "src" / "stale.py").write_text("x = 1\n")
        (dest / "TASK_SPEC.md").write_text("spec")
        attempt_picker.install(a1, dest)
        self.assertEqual((dest / "src" / "calc.py").read_text(), CORRECT)
        self.assertFalse((dest / "src" / "stale.py").exists())
        self.assertTrue((dest / "TASK_SPEC.md").exists())

    def test_tests_that_cannot_import_count_as_failures(self):
        a1 = self.attempt("a1", CORRECT, TESTS_CORRECT)
        a2 = self.attempt("a2", "def other():\n    return 1\n", TESTS_CORRECT)
        res = attempt_picker.pick([a1, a2])
        self.assertEqual(res["winner"], str(a1))
        a2_report = [r for r in res["attempts"] if r["attempt"] == str(a2)][0]
        self.assertEqual(a2_report["cross_test_score"], 0.0)


GIT_BASE_CODE = "def clamp(x, lo, hi):\n    return x\n"
GIT_TEST = (
    "import sys, unittest\nsys.path.insert(0, '.')\nfrom pkg.calc import clamp\n\n"
    "class T(unittest.TestCase):\n    def test_it(self):\n        self.assertEqual({call}, {want})\n\n"
    "if __name__ == '__main__':\n    unittest.main()\n"
)


class GitModeTest(unittest.TestCase):
    """Attempts are checkouts of one repository; tests live in the project's own suite."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.base_repo = self.root / "base"
        (self.base_repo / "pkg").mkdir(parents=True)
        (self.base_repo / "pkg" / "__init__.py").write_text("")
        (self.base_repo / "pkg" / "calc.py").write_text(GIT_BASE_CODE)
        self._git(self.base_repo, "init", "-q")
        self._git(self.base_repo, "add", "-A")
        self._git(self.base_repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
        self.base = self._git(self.base_repo, "rev-parse", "HEAD").strip()

    def tearDown(self):
        self._tmp.cleanup()

    @staticmethod
    def _git(repo, *args):
        import subprocess
        return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout

    def attempt(self, name: str, impl: str, test_name: str, call: str, want: str) -> Path:
        import shutil
        ws = self.root / name
        shutil.copytree(self.base_repo, ws, symlinks=True)
        (ws / "pkg" / "calc.py").write_text(impl)
        (ws / "pkg" / "tests").mkdir()
        (ws / "pkg" / "tests" / test_name).write_text(GIT_TEST.format(call=call, want=want))
        return ws

    def test_cross_testing_picks_the_attempt_that_passes_everyone_s_tests(self):
        a1 = self.attempt("a1", BUG_UPPER, "test_lower.py", "clamp(-1, 0, 3)", "0")
        a2 = self.attempt("a2", BUG_LOWER, "test_upper.py", "clamp(9, 0, 3)", "3")
        a3 = self.attempt("a3", CORRECT, "test_both.py", "(clamp(9, 0, 3), clamp(-1, 0, 3))", "(3, 0)")
        res = attempt_picker.pick_git([a1, a2, a3], self.base, f'"{sys.executable}" {{tests}}')
        self.assertEqual(res["winner"], str(a3))
        by_name = {Path(r["attempt"]).name: r for r in res["attempts"]}
        self.assertTrue(by_name["a1"]["own_tests_passed"])
        self.assertEqual(by_name["a3"]["cross_test_score"], 1.0)
        self.assertEqual(by_name["a1"]["per_suite"]["a1"]["files"], ["pkg/tests/test_lower.py"])

    def test_test_file_detection_and_dotted_labels(self):
        self.assertTrue(attempt_picker.is_test_path("tests/admin_views/tests.py"))
        self.assertTrue(attempt_picker.is_test_path("sympy/core/tests/test_basic.py"))
        self.assertTrue(attempt_picker.is_test_path("testing/test_mark.py"))
        self.assertFalse(attempt_picker.is_test_path("django/test/utils.py"))
        self.assertFalse(attempt_picker.is_test_path("src/_pytest/mark/structures.py"))
        self.assertEqual(attempt_picker.to_label("tests/admin_views/test_forms.py", "dotted", "tests"),
                         "admin_views.test_forms")


if __name__ == "__main__":
    unittest.main()
