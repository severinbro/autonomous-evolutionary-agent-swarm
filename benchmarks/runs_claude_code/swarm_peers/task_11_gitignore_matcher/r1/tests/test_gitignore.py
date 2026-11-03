"""Unit tests for the gitignore matcher (gitignore(5) semantics).

Expected values are derived from the gitignore(5) documentation, not from
running any other implementation.
"""
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.matcher import GitIgnore  # noqa: E402
import src.cli  # noqa: E402


class Base(unittest.TestCase):
    def check(self, text, ignored=(), kept=()):
        g = GitIgnore(text)
        for p in ignored:
            self.assertTrue(g.is_ignored(p), "%r should be ignored by %r" % (p, text))
        for p in kept:
            self.assertFalse(g.is_ignored(p), "%r should NOT be ignored by %r" % (p, text))


class TestBlankAndComments(Base):
    def test_empty_text(self):
        self.check("", kept=["a", "a/b", ".gitignore"])

    def test_blank_lines(self):
        self.check("\n\n\n", kept=["a", "b/c"])

    def test_whitespace_only_line_is_blank(self):
        self.check("   \n", kept=["a", " ", "b/c"])

    def test_comment(self):
        self.check("# a comment\n#foo\n", kept=["# a comment", "#foo", "foo"])

    def test_escaped_hash(self):
        self.check("\\#foo\n", ignored=["#foo", "d/#foo"], kept=["foo", "\\#foo"])

    def test_hash_in_middle_is_literal(self):
        self.check("a#b\n", ignored=["a#b"], kept=["a", "ab"])

    def test_leading_space_is_significant(self):
        self.check(" a\n", ignored=[" a"], kept=["a"])

    def test_no_trailing_newline(self):
        self.check("foo", ignored=["foo", "x/foo"])

    def test_lf_lines(self):
        self.check("a\nb\n", ignored=["a", "b"], kept=["c"])

    def test_crlf_line_endings(self):
        self.check("a\r\n*.log\r\nbuild/\r\n", ignored=["a", "x.log", "build/y"], kept=["a\r", "c"])

    def test_trailing_backslash_never_matches(self):
        self.check("foo\\\n", kept=["foo", "foo\\", "d/foo"])

    def test_utf8_bom_skipped(self):
        self.check("\ufefffoo\n", ignored=["foo"], kept=["\ufefffoo2"])


class TestTrailingSpaces(Base):
    def test_trailing_spaces_trimmed(self):
        self.check("foo   \n", ignored=["foo", "a/foo"], kept=["foo   ", "foo "])

    def test_escaped_trailing_space_kept(self):
        self.check("foo\\ \n", ignored=["foo "], kept=["foo"])

    def test_escaped_space_then_trimmed(self):
        self.check("foo\\    \n", ignored=["foo "], kept=["foo", "foo    "])


class TestNegation(Base):
    def test_negation_reincludes(self):
        self.check("*.txt\n!keep.txt\n", ignored=["a.txt", "d/b.txt"], kept=["keep.txt", "d/keep.txt"])

    def test_last_match_wins(self):
        self.check("*.txt\n!a.txt\na.txt\n", ignored=["a.txt"])
        self.check("a.txt\n!*.txt\n", kept=["a.txt", "b.txt"])

    def test_negation_alone_does_nothing(self):
        self.check("!foo\n", kept=["foo", "bar"])

    def test_escaped_bang(self):
        self.check("\\!important\n", ignored=["!important", "d/!important"], kept=["important"])

    def test_cannot_reinclude_when_parent_dir_excluded(self):
        self.check("dir/\n!dir/a\n", ignored=["dir/a", "dir/b"])
        self.check("logs\n!logs/keep\n", ignored=["logs/keep", "logs/x"])

    def test_reinclude_with_star_contents(self):
        self.check("dir/*\n!dir/a\n", ignored=["dir/b", "dir/sub/c"], kept=["dir/a"])

    def test_negated_dir_unignores(self):
        self.check("build/\n!build/\n", kept=["build/x", "a/build/y"])

    def test_documented_foo_bar_example(self):
        text = "/*\n!/foo\n/foo/*\n!/foo/bar\n"
        self.check(
            text,
            ignored=["a", "x/y", "foo/baz", "foo/qux/z", ".hidden"],
            kept=["foo/bar", "foo/bar/x", "foo/bar/deep/y"],
        )

    def test_whitelist_everything_but_txt(self):
        text = "*\n!*/\n!*.txt\n"
        self.check(text, ignored=["a.c", "d/b.c", "d/e/f"], kept=["a.txt", "d/b.txt", "d/e/c.txt"])

    def test_reinclude_directory(self):
        self.check("/*\n!/keep/\n", ignored=["a", "other/x"], kept=["keep/x", "keep/y/z"])

    def test_negation_cannot_reinclude_under_dir_ignored_by_glob(self):
        self.check("foo/*\n!foo/bar/a\n", ignored=["foo/bar/a", "foo/x"])


class TestDirectoryOnly(Base):
    def test_trailing_slash_matches_only_dirs(self):
        self.check("build/\n", ignored=["build/a", "build/x/y", "src/build/z"], kept=["build", "src/build"])

    def test_anchored_trailing_slash(self):
        self.check("/build/\n", ignored=["build/a"], kept=["src/build/a", "build"])

    def test_doc_frotz_dir(self):
        self.check("doc/frotz/\n", ignored=["doc/frotz/a", "doc/frotz/b/c"], kept=["a/doc/frotz/b", "doc/frotz"])

    def test_frotz_dir_any_level(self):
        self.check("frotz/\n", ignored=["frotz/a", "a/frotz/b", "x/y/frotz/z"], kept=["frotz", "a/frotz"])

    def test_star_slash(self):
        self.check("*/\n", ignored=["a/b", "c/d/e"], kept=["a", "b.txt"])

    def test_dir_wildcard(self):
        self.check("tmp*/\n", ignored=["tmp1/x", "a/tmpdir/y"], kept=["tmp1", "a/tmpdir"])


class TestAnchoring(Base):
    def test_no_slash_matches_any_level(self):
        self.check("foo\n", ignored=["foo", "a/foo", "a/b/foo", "foo/bar", "a/foo/bar"], kept=["foobar", "afoo"])

    def test_leading_slash_anchors(self):
        self.check("/foo\n", ignored=["foo", "foo/x"], kept=["a/foo", "a/foo/x"])

    def test_middle_slash_anchors(self):
        self.check("doc/frotz\n", ignored=["doc/frotz", "doc/frotz/x"], kept=["a/doc/frotz", "doc/frotzz"])

    def test_leading_slash_star_c(self):
        self.check("/*.c\n", ignored=["cat-file.c"], kept=["mozilla-sha1/sha1.c"])

    def test_glob_with_slash_is_anchored(self):
        self.check("a/*.c\n", ignored=["a/x.c"], kept=["b/a/x.c", "a/b/x.c"])

    def test_star_log_any_depth(self):
        self.check("*.log\n", ignored=["x.log", "a/b.log", "a/b/c.log", "logs.log/x"], kept=["a/b.txt", "x.log.txt"])

    def test_anchored_dir_path_ignores_contents(self):
        self.check("a/b\n", ignored=["a/b", "a/b/c.txt", "a/b/d/e"], kept=["x/a/b", "a/bc"])


class TestWildcards(Base):
    def test_star_does_not_cross_slash(self):
        self.check("foo/*\n", ignored=["foo/test.json", "foo/bar/hello.c"], kept=["foo", "a/foo/x"])
        self.check("a*c\n", ignored=["abc", "ac", "x/abbbc"], kept=["ab/c"])

    def test_star_matches_dotfiles(self):
        self.check("*\n", ignored=[".hidden", "a", "a/.b", ".git/x"])
        self.check(".*\n", ignored=[".env", "a/.env", ".d/x"], kept=["a.b", "env"])

    def test_question_mark(self):
        self.check("?.txt\n", ignored=["a.txt", "d/b.txt"], kept=["ab.txt", ".txt"])
        self.check("a?b\n", ignored=["axb"], kept=["a/b", "ab"])

    def test_bracket_range(self):
        self.check("file[0-9].txt\n", ignored=["file1.txt", "d/file9.txt"], kept=["filea.txt", "file10.txt"])

    def test_bracket_set(self):
        self.check("[abc].md\n", ignored=["a.md", "c.md"], kept=["d.md", "ab.md"])

    def test_bracket_negation(self):
        self.check("x[!0-9]\n", ignored=["xa"], kept=["x1", "x"])
        self.check("x[^0-9]\n", ignored=["xa"], kept=["x1"])

    def test_bracket_does_not_match_slash(self):
        self.check("a[/]b\n", kept=["a/b", "ab"])
        self.check("a[!x]b\n", kept=["a/b"], ignored=["ayb"])

    def test_bracket_close_first(self):
        self.check("[]]x\n", ignored=["]x"], kept=["x", "[]]x"])

    def test_bracket_char_class(self):
        self.check("v[[:digit:]]\n", ignored=["v1", "d/v7"], kept=["va", "v"])
        self.check("[[:upper:]]*\n", ignored=["Readme", "d/Abc"], kept=["readme"])

    def test_escaped_metachars(self):
        self.check("\\*.txt\n", ignored=["*.txt"], kept=["a.txt"])
        self.check("a\\?\n", ignored=["a?"], kept=["ab"])
        self.check("\\[ab]\n", ignored=["[ab]"], kept=["a", "b"])
        self.check("fo\\o\n", ignored=["foo"], kept=["fo\\o"])

    def test_case_sensitive(self):
        self.check("*.LOG\n", ignored=["a.LOG"], kept=["a.log"])
        self.check("Foo\n", ignored=["Foo"], kept=["foo", "FOO"])


class TestDoubleAsterisk(Base):
    def test_leading_double_star(self):
        self.check("**/foo\n", ignored=["foo", "a/foo", "a/b/foo", "a/foo/x"], kept=["afoo", "foox"])

    def test_leading_double_star_with_path(self):
        self.check("**/foo/bar\n", ignored=["foo/bar", "a/foo/bar", "x/y/foo/bar/z"], kept=["foo/x/bar", "bar"])

    def test_trailing_double_star(self):
        self.check("abc/**\n", ignored=["abc/x", "abc/x/y/z"], kept=["abc", "x/abc/y"])

    def test_middle_double_star(self):
        self.check(
            "a/**/b\n",
            ignored=["a/b", "a/x/b", "a/x/y/b", "a/x/b/c"],
            kept=["ab", "a/xb", "x/a/b", "a/bx"],
        )

    def test_double_star_alone(self):
        self.check("**\n", ignored=["a", "a/b", ".x"])

    def test_double_star_not_at_boundary_is_single_star(self):
        self.check("a**b\n", ignored=["ab", "axyzb", "d/axb"], kept=["ax/yb"])
        self.check("foo/**bar\n", ignored=["foo/xbar"], kept=["foo/x/bar"])

    def test_double_star_dir_only(self):
        self.check("**/cache/\n", ignored=["cache/x", "a/cache/x"], kept=["cache", "a/cache"])

    def test_double_star_extension(self):
        self.check("src/**/*.pyc\n", ignored=["src/a.pyc", "src/x/y/a.pyc"], kept=["a.pyc", "lib/a.pyc"])


class TestIgnoredFiles(Base):
    def test_sorted_output(self):
        g = GitIgnore("*.log\nbuild/\n")
        paths = ["z.log", "src/main.c", "build/out.o", "a.log", "a/b.log"]
        self.assertEqual(g.ignored_files(paths), ["a.log", "a/b.log", "build/out.o", "z.log"])

    def test_empty(self):
        self.assertEqual(GitIgnore("*.log\n").ignored_files([]), [])

    def test_returns_list(self):
        res = GitIgnore("x\n").ignored_files(["x", "y"])
        self.assertIsInstance(res, list)
        self.assertEqual(res, ["x"])

    def test_outcome_example(self):
        g = GitIgnore("*.log\n")
        self.assertTrue(g.is_ignored("a/b.log"))
        self.assertFalse(g.is_ignored("a/b.txt"))


class TestCLI(unittest.TestCase):
    def _write(self, text):
        fd, path = tempfile.mkstemp(suffix=".gitignore")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        self.addCleanup(os.remove, path)
        return path

    def test_cli_subprocess(self):
        path = self._write("*.log\n!keep.log\nbuild/\n")
        out = subprocess.run(
            [sys.executable, "-m", "src.cli", path, "z.log", "keep.log", "build/a", "src/x.c", "a/b.log"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.splitlines(), ["a/b.log", "build/a", "z.log"])

    def test_cli_no_matches(self):
        path = self._write("*.log\n")
        out = subprocess.run(
            [sys.executable, "-m", "src.cli", path, "a.txt"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout, "")

    def test_cli_calls_gitignore(self):
        path = self._write("*.log\n")
        with mock.patch.object(src.cli, "GitIgnore", wraps=GitIgnore) as spy:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = src.cli.main([path, "a.log", "b.txt"])
        self.assertIn(rc, (0, None))
        self.assertEqual(spy.call_count, 1)
        args, kwargs = spy.call_args
        passed = args[0] if args else next(iter(kwargs.values()))
        self.assertIn("*.log", passed)
        self.assertEqual(buf.getvalue().splitlines(), ["a.log"])


if __name__ == "__main__":
    unittest.main()
