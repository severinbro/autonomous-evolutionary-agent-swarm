"""Unit tests for the gitignore matcher (expected values from gitignore(5))."""

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

from src import cli  # noqa: E402
from src.matcher import GitIgnore  # noqa: E402
from src.patterns import parse_gitignore, parse_line, wildmatch  # noqa: E402


class Base(unittest.TestCase):
    def check(self, text, ignored=(), kept=()):
        g = GitIgnore(text)
        for p in ignored:
            self.assertTrue(g.is_ignored(p), f"{text!r} should ignore {p!r}")
        for p in kept:
            self.assertFalse(g.is_ignored(p), f"{text!r} should not ignore {p!r}")


class TestParsing(Base):
    def test_blank_and_comment_lines(self):
        self.assertIsNone(parse_line(""))
        self.assertIsNone(parse_line("   "))
        self.assertIsNone(parse_line("# comment"))
        self.assertEqual(parse_gitignore("\n\n# c\n*.o\n\n"), [parse_line("*.o")])

    def test_comment_only_at_line_start(self):
        self.check(" #foo", ignored=[" #foo"], kept=["#foo"])

    def test_escaped_hash(self):
        self.check("\\#foo\n", ignored=["#foo", "d/#foo"], kept=["foo"])
        self.check("#foo\n", kept=["#foo"])

    def test_trailing_spaces_trimmed(self):
        self.check("foo   \n", ignored=["foo"], kept=["foo   ", "foo "])

    def test_escaped_trailing_space_kept(self):
        self.check("foo\\ \n", ignored=["foo "], kept=["foo"])
        self.check("foo\\  \n", ignored=["foo "], kept=["foo", "foo  "])

    def test_trailing_tab_not_trimmed(self):
        self.check("foo\t\n", ignored=["foo\t"], kept=["foo"])

    def test_crlf_line_endings(self):
        self.check("*.log\r\nbuild/\r\n", ignored=["a.log", "build/x"], kept=["a.txt"])

    def test_no_final_newline(self):
        self.check("*.log", ignored=["x.log"])

    def test_utf8_bom_skipped(self):
        self.check("\ufeff*.log\n", ignored=["x.log"])

    def test_flags(self):
        p = parse_line("!/a/b/")
        self.assertTrue(p.negative)
        self.assertTrue(p.must_be_dir)
        self.assertFalse(p.no_dir)
        q = parse_line("foo")
        self.assertTrue(q.no_dir)
        self.assertFalse(q.negative or q.must_be_dir)

    def test_empty_patterns_match_nothing(self):
        self.check("!\n/\n", kept=["a", "a/b"])


class TestBasenamePatterns(Base):
    def test_no_slash_matches_any_level(self):
        self.check("foo\n", ignored=["foo", "a/foo", "a/b/foo", "foo/bar"],
                   kept=["foobar", "afoo", "a/foox"])

    def test_star_extension(self):
        self.check("*.log\n", ignored=["a.log", "a/b.log", ".log", "x/y/z.log"],
                   kept=["a.txt", "a.log.txt", "alog"])

    def test_log_directory_contents(self):
        # a directory named like the pattern hides everything below it
        self.check("*.log\n", ignored=["dir.log/inner.txt"])

    def test_question_mark(self):
        self.check("?.c\n", ignored=["a.c", "d/b.c"], kept=["ab.c", ".c"])

    def test_brackets(self):
        self.check("[abc].txt\n", ignored=["a.txt", "c.txt"], kept=["d.txt", "ab.txt"])
        self.check("file[0-9]\n", ignored=["file0", "file9"], kept=["filea", "file10"])
        self.check("x[!0-9]\n", ignored=["xa"], kept=["x1"])
        self.check("x[^0-9]\n", ignored=["xa"], kept=["x1"])
        self.check("[]]\n", ignored=["]"], kept=["a"])
        self.check("[!]]\n", ignored=["a"], kept=["]"])
        self.check("a[-z]\n", ignored=["a-", "az"], kept=["ab"])
        self.check("a[z-]\n", ignored=["a-", "az"], kept=["ab"])

    def test_bracket_char_classes(self):
        self.check("[[:digit:]]*\n", ignored=["1abc"], kept=["abc"])
        self.check("x[[:upper:]]\n", ignored=["xA"], kept=["xa"])
        self.check("x[[:space:][:alpha:]]\n", ignored=["x ", "xq"], kept=["x1"])

    def test_unterminated_bracket_never_matches(self):
        self.check("a[b\n", kept=["a[b", "ab"])

    def test_star_is_greedy_within_name(self):
        self.check("a*b*c\n", ignored=["abc", "axxbyyc", "d/abbc"], kept=["acb"])

    def test_double_star_without_slash_is_plain_star(self):
        self.check("a**b\n", ignored=["ab", "axyzb", "d/axb"], kept=["ax/yb"])

    def test_case_sensitive(self):
        self.check("*.LOG\nREADME\n", ignored=["x.LOG", "README"],
                   kept=["x.log", "readme", "Readme"])

    def test_escaped_wildcards(self):
        self.check("\\*.txt\n", ignored=["*.txt"], kept=["a.txt"])
        self.check("a\\?\n", ignored=["a?"], kept=["ab"])
        self.check("\\[x]\n", ignored=["[x]"], kept=["x"])

    def test_trailing_backslash_matches_nothing(self):
        self.check("foo\\\n", kept=["foo", "foo\\"])


class TestAnchoredPatterns(Base):
    def test_leading_slash(self):
        self.check("/foo\n", ignored=["foo", "foo/x"], kept=["a/foo", "a/foo/x"])

    def test_leading_slash_with_glob(self):
        self.check("/*.c\n", ignored=["cat-file.c"], kept=["mozilla-sha1/sha1.c"])

    def test_middle_slash_is_anchored(self):
        self.check("doc/frotz\n", ignored=["doc/frotz", "doc/frotz/x"],
                   kept=["a/doc/frotz", "frotz"])
        self.check("doc/frotz/\n", ignored=["doc/frotz/x"],
                   kept=["a/doc/frotz/x", "doc/frotz"])

    def test_star_does_not_cross_slash(self):
        self.check("Documentation/*.html\n",
                   ignored=["Documentation/git.html"],
                   kept=["Documentation/ppc/ppc.html", "tools/perf/Documentation/perf.html"])

    def test_single_star_segment(self):
        self.check("a/*/b\n", ignored=["a/x/b", "a/x/b/c"], kept=["a/b", "a/x/y/b"])

    def test_question_does_not_match_slash(self):
        self.check("a?b\n", kept=["a/b"])
        self.check("x/a?b\n", ignored=["x/a-b"], kept=["x/a/b"])

    def test_bracket_does_not_match_slash(self):
        self.check("x/a[/]b\n", kept=["x/a/b"])
        self.check("x/a[!a]b\n", ignored=["x/acb"], kept=["x/a/b"])


class TestDirectoryOnly(Base):
    def test_trailing_slash_matches_directories_only(self):
        self.check("frotz/\n", ignored=["frotz/a", "a/frotz/b", "x/frotz/y/z"],
                   kept=["frotz", "a/frotz"])

    def test_glob_directory(self):
        self.check("build*/\n", ignored=["build/a", "build-1/x/y", "s/buildx/f"],
                   kept=["build", "buildfile"])


class TestDoubleStar(Base):
    def test_leading_double_star(self):
        self.check("**/foo\n", ignored=["foo", "a/foo", "a/b/foo", "foo/x"],
                   kept=["afoo", "a/xfoo"])
        self.check("**/foo/bar\n", ignored=["foo/bar", "a/foo/bar", "x/y/foo/bar/z"],
                   kept=["foo/x/bar", "bar"])

    def test_trailing_double_star(self):
        self.check("abc/**\n", ignored=["abc/x", "abc/x/y/z"], kept=["abc", "xabc/x", "a/abc/x"])

    def test_middle_double_star(self):
        self.check("a/**/b\n", ignored=["a/b", "a/x/b", "a/x/y/b", "a/x/b/c"],
                   kept=["a/xb", "b", "x/a/b"])

    def test_lone_double_star(self):
        self.check("**\n", ignored=["a", "a/b/c"])

    def test_double_star_dir_only(self):
        self.check("**/tmp/\n", ignored=["tmp/x", "a/tmp/x"], kept=["tmp", "a/tmp"])

    def test_other_consecutive_stars_are_regular(self):
        self.check("x/a**b\n", ignored=["x/ab", "x/aqqb"], kept=["x/a/b", "x/aq/qb"])
        self.check("x/**b\n", ignored=["x/b", "x/qb"], kept=["x/q/b"])
        self.check("x/b**\n", ignored=["x/b", "x/bq", "x/bq/r"], kept=["x/q/b"])


class TestNegationAndOrder(Base):
    def test_negation(self):
        self.check("*.log\n!keep.log\n", ignored=["a.log", "d/x.log"],
                   kept=["keep.log", "d/keep.log"])

    def test_last_match_wins(self):
        self.check("!keep.log\n*.log\n", ignored=["keep.log"])

    def test_escaped_bang(self):
        self.check("\\!important\n", ignored=["!important"], kept=["important"])

    def test_cannot_reinclude_inside_excluded_dir(self):
        self.check("build/\n!build/keep.txt\n", ignored=["build/keep.txt", "build/a"])
        self.check("logs\n!logs/x\n", ignored=["logs/x"])

    def test_reinclude_with_star_contents(self):
        self.check("build/*\n!build/keep.txt\n", ignored=["build/a", "build/sub/x"],
                   kept=["build/keep.txt"])

    def test_doc_example_only_foo_bar(self):
        text = "/*\n!/foo\n/foo/*\n!/foo/bar\n"
        self.check(text, ignored=["a", "x/y", "foo/a", "foo/baz/x"],
                   kept=["foo/bar", "foo/bar/deep/file"])

    def test_negated_directory_reincluded(self):
        self.check("/*/\n!/src/\n", ignored=["lib/a"], kept=["src/a", "top"])

    def test_negated_dir_only_pattern_does_not_apply_to_files(self):
        self.check("*.d\n!*.d/\n", ignored=["x.d"], kept=["x.d/file"])


class TestApi(Base):
    def test_outcome_example(self):
        g = GitIgnore("*.log\n")
        self.assertTrue(g.is_ignored("a/b.log"))
        self.assertFalse(g.is_ignored("a/b.txt"))

    def test_ignored_files_sorted(self):
        g = GitIgnore("*.o\n/tmp\n")
        paths = ["z.o", "src/main.c", "tmp/x", "a/b.o", "src/tmp/y"]
        self.assertEqual(g.ignored_files(paths), ["a/b.o", "tmp/x", "z.o"])

    def test_empty_gitignore(self):
        self.assertEqual(GitIgnore("").ignored_files(["a", "b/c"]), [])

    def test_wildmatch_helper(self):
        self.assertTrue(wildmatch("a/**/c", "a/b/c"))
        self.assertFalse(wildmatch("a/*", "a/b/c"))
        self.assertTrue(wildmatch("a*", "a/b", pathname=False))


class TestCli(unittest.TestCase):
    def _write(self, text):
        fd, path = tempfile.mkstemp(suffix=".gitignore")
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        self.addCleanup(os.remove, path)
        return path

    def test_cli_subprocess(self):
        path = self._write("*.log\n!keep.log\nbuild/\n")
        out = subprocess.run(
            [sys.executable, "-m", "src.cli", path, "z.log", "keep.log", "build/a", "a.txt"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
        self.assertEqual(out.splitlines(), ["build/a", "z.log"])

    def test_cli_calls_gitignore(self):
        path = self._write("*.tmp\n")
        with mock.patch.object(cli, "GitIgnore", wraps=GitIgnore) as spy:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cli.main([path, "a.tmp", "b.txt"])
        self.assertEqual(rc, 0)
        spy.assert_called_once_with("*.tmp\n")
        self.assertEqual(buf.getvalue(), "a.tmp\n")

    def test_cli_missing_file(self):
        with redirect_stdout(io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
            self.assertEqual(cli.main(["/nonexistent/.gitignore", "a"]), 2)


if __name__ == "__main__":
    unittest.main()
