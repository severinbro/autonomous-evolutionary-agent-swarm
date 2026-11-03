"""Tests for the command-line entry point src/cli.py."""

import ast
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import src.cli as cli  # noqa: E402
from src.matcher import GitIgnore  # noqa: E402


class CLITestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write_gitignore(self, content, mode="w"):
        path = os.path.join(self.tmp.name, ".gitignore")
        if isinstance(content, bytes):
            with open(path, "wb") as fh:
                fh.write(content)
        else:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(content)
        return path

    def run_main(self, args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(args)
        return code, out.getvalue(), err.getvalue()


class TestCLIMain(CLITestBase):
    def test_prints_ignored_paths_sorted_one_per_line(self):
        gi = self.write_gitignore("*.log\nbuild/\n")
        code, out, _ = self.run_main(
            [gi, "z.log", "src/main.c", "build/out.o", "a/b.log", "README"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "a/b.log\nbuild/out.o\nz.log\n")

    def test_no_ignored_paths_prints_nothing(self):
        gi = self.write_gitignore("*.log\n")
        code, out, _ = self.run_main([gi, "a.txt", "b/c.txt"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_no_paths_given(self):
        gi = self.write_gitignore("*\n")
        code, out, _ = self.run_main([gi])
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_negation_through_cli(self):
        gi = self.write_gitignore("*.log\n!keep.log\n")
        code, out, _ = self.run_main([gi, "keep.log", "drop.log", "d/keep.log"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "drop.log\n")

    def test_crlf_gitignore(self):
        # Git strips a CR that directly precedes the LF of each line.
        gi = self.write_gitignore(b"*.log\r\n/build\r\n")
        code, out, _ = self.run_main([gi, "x.log", "build/a", "src/build/a", "y.txt"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "build/a\nx.log\n")

    def test_last_line_without_newline(self):
        gi = self.write_gitignore("*.o\n*.tmp")
        code, out, _ = self.run_main([gi, "a.o", "b.tmp", "c.c"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "a.o\nb.tmp\n")

    def test_utf8_bom_is_skipped(self):
        gi = self.write_gitignore(b"\xef\xbb\xbf*.log\n")
        code, out, _ = self.run_main([gi, "a.log", "b.txt"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "a.log\n")

    def test_missing_arguments_is_usage_error(self):
        code, out, err = self.run_main([])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("usage", err)

    def test_unreadable_gitignore_is_error(self):
        missing = os.path.join(self.tmp.name, "does-not-exist")
        code, out, err = self.run_main([missing, "a.log"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertTrue(err)


class TestCLICallsGitIgnore(CLITestBase):
    """Acceptance criterion: src/cli.py must call GitIgnore."""

    def test_main_constructs_gitignore_with_file_text(self):
        text = "*.log\n!keep.log\n"
        gi = self.write_gitignore(text)
        calls = []

        def spy(arg):
            calls.append(arg)
            return GitIgnore(arg)

        with mock.patch.object(cli, "GitIgnore", side_effect=spy) as fake:
            code, out, _ = self.run_main([gi, "a.log", "keep.log"])
        self.assertEqual(code, 0)
        fake.assert_called_once()
        self.assertEqual(calls, [text])
        self.assertEqual(out, "a.log\n")

    def test_output_comes_from_gitignore_object(self):
        gi = self.write_gitignore("anything\n")
        fake_instance = mock.Mock()
        fake_instance.ignored_files.return_value = ["p/q", "x"]
        with mock.patch.object(cli, "GitIgnore", return_value=fake_instance) as fake:
            code, out, _ = self.run_main([gi, "x", "p/q", "r"])
        self.assertEqual(code, 0)
        fake.assert_called_once_with("anything\n")
        fake_instance.ignored_files.assert_called_once_with(["x", "p/q", "r"])
        self.assertEqual(out, "p/q\nx\n")

    def test_source_references_gitignore_call(self):
        with open(os.path.join(ROOT, "src", "cli.py"), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        called = {
            node.func.id for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertIn("GitIgnore", called)


class TestCLISubprocess(CLITestBase):
    def test_module_invocation(self):
        gi = self.write_gitignore("# comment\n*.pyc\n/dist/\ndocs/**/*.tmp\n")
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", gi,
             "a.pyc", "pkg/b.pyc", "dist/x.whl", "pkg/dist/y", "docs/a/b/c.tmp",
             "docs/c.tmp", "main.py"],
            cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            ["a.pyc", "dist/x.whl", "docs/a/b/c.tmp", "docs/c.tmp", "pkg/b.pyc"])


if __name__ == "__main__":
    unittest.main()
