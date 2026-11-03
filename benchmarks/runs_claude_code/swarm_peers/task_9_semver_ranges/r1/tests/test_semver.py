"""Unit tests for the node-semver 7.x compatible implementation.

Expected values are derived by hand from node-semver's documented and
specified behaviour (default options: not loose, includePrerelease off).
"""

import io
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import cli  # noqa: E402
from src.ranges import max_satisfying, satisfies  # noqa: E402
from src.version import compare, valid  # noqa: E402


class TestValid(unittest.TestCase):
    def test_valid_versions(self):
        cases = [
            ("1.2.3", "1.2.3"),
            ("0.0.0", "0.0.0"),
            ("v1.2.3", "1.2.3"),
            (" 1.2.3 ", "1.2.3"),
            ("\t1.2.3\n", "1.2.3"),
            ("1.2.3-alpha", "1.2.3-alpha"),
            ("1.2.3-alpha.1", "1.2.3-alpha.1"),
            ("1.2.3-0", "1.2.3-0"),
            ("1.2.3-0a", "1.2.3-0a"),
            ("1.2.3--", "1.2.3--"),
            ("1.2.3-x-y-z.-", "1.2.3-x-y-z.-"),
            ("1.2.3+build", "1.2.3"),
            ("1.2.3+build.01", "1.2.3"),
            ("1.2.3-beta.2+exp.sha.5114f85", "1.2.3-beta.2"),
            ("10.20.30", "10.20.30"),
            ("9007199254740991.0.0", "9007199254740991.0.0"),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(valid(text), expected)

    def test_invalid_versions(self):
        cases = [
            "",
            "   ",
            "1",
            "1.2",
            "1.2.3.4",
            "a.b.c",
            "01.2.3",
            "1.02.3",
            "1.2.03",
            "1.2.3-",
            "1.2.3+",
            "1.2.3-01",
            "1.2.3-00",
            "1.2.3-a..b",
            "1.2.3-alpha_beta",
            "1.2.3+a+b",
            "=1.2.3",
            "vv1.2.3",
            "V1.2.3",
            "v 1.2.3",
            "1.2.3 4",
            ">1.2.3",
            "~1.2.3",
            "1.2.x",
            "-1.2.3",
            "9007199254740992.0.0",
            "1.9007199254740992.0",
            "1.2.3-" + "a" * 300,
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertIsNone(valid(text))


class TestCompare(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(compare("1.2.3", "1.2.3"), 0)
        self.assertEqual(compare("1.2.3", "1.2.4"), -1)
        self.assertEqual(compare("1.2.4", "1.2.3"), 1)
        self.assertEqual(compare("1.10.0", "1.9.0"), 1)
        self.assertEqual(compare("2.0.0", "10.0.0"), -1)
        self.assertEqual(compare("1.0.0", "0.99.99"), 1)

    def test_build_and_prefix_ignored(self):
        self.assertEqual(compare("1.2.3+a", "1.2.3+b"), 0)
        self.assertEqual(compare("v1.2.3", "1.2.3"), 0)
        self.assertEqual(compare(" 1.2.3", "1.2.3+build"), 0)
        self.assertEqual(compare("1.2.3-beta+x", "1.2.3-beta"), 0)

    def test_semver_spec_precedence_chain(self):
        chain = [
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-alpha.beta",
            "1.0.0-beta",
            "1.0.0-beta.2",
            "1.0.0-beta.11",
            "1.0.0-rc.1",
            "1.0.0",
            "1.0.1-0",
            "1.0.1",
        ]
        for i, a in enumerate(chain):
            for j, b in enumerate(chain):
                expected = (i > j) - (i < j)
                with self.subTest(a=a, b=b):
                    self.assertEqual(compare(a, b), expected)

    def test_prerelease_identifier_rules(self):
        # numeric identifiers compare numerically
        self.assertEqual(compare("1.0.0-2", "1.0.0-10"), -1)
        # numeric identifiers sort before alphanumeric ones
        self.assertEqual(compare("1.0.0-9", "1.0.0-a"), -1)
        self.assertEqual(compare("1.0.0-alpha", "1.0.0-1"), 1)
        # alphanumeric identifiers compare in ASCII order
        self.assertEqual(compare("1.0.0-Alpha", "1.0.0-alpha"), -1)
        self.assertEqual(compare("1.0.0-a10", "1.0.0-a9"), -1)
        self.assertEqual(compare("1.0.0-0a", "1.0.0-1"), 1)
        # a longer prerelease wins when all preceding identifiers are equal
        self.assertEqual(compare("1.0.0-a.b", "1.0.0-a"), 1)
        # prerelease is lower than the release
        self.assertEqual(compare("1.0.0-rc.1", "1.0.0"), -1)
        self.assertEqual(compare("1.0.0", "1.0.0-rc.1"), 1)

    def test_invalid_raises_value_error(self):
        for a, b in [("1.2", "1.2.3"), ("1.2.3", "nope"), ("", ""), ("=1.2.3", "1.2.3")]:
            with self.subTest(a=a, b=b):
                with self.assertRaises(ValueError):
                    compare(a, b)


SATISFIES_TRUE = [
    # exact / primitive comparators
    ("1.2.3", "1.2.3"),
    ("1.2.3", "=1.2.3"),
    ("1.2.3", "v1.2.3"),
    ("1.2.3", "=v1.2.3"),
    ("v1.2.3", "1.2.3"),
    (" 1.2.3 ", "1.2.3"),
    ("1.2.3", "  1.2.3  "),
    ("1.2.3", ">=1.2.3"),
    ("1.2.4", ">1.2.3"),
    ("1.2.2", "<1.2.3"),
    ("1.2.3", "<=1.2.3"),
    ("1.2.3", "1.2.3+build"),
    ("1.2.3+build", "1.2.3"),
    ("1.2.4", ">1.2.3 <1.2.5"),
    ("1.2.4", "> 1.2.3 < 1.2.5"),
    ("1.2.4", ">=   1.2.3"),
    ("1.2.4", ">=1.2.3\t<2"),
    # x-ranges / partial versions
    ("1.2.3", "*"),
    ("1.2.3", ""),
    ("1.2.3", "x"),
    ("1.2.3", "X"),
    ("0.0.0", "*"),
    ("1.2.3", "1"),
    ("1.2.3", "1.x"),
    ("1.2.3", "1.X"),
    ("1.2.3", "1.*"),
    ("1.2.3", "1.2"),
    ("1.2.3", "1.2.x"),
    ("1.2.3", "1.2.*"),
    ("1.2.3", "=1.2"),
    ("1.2.3", ">=*"),
    ("1.2.3", "<=*"),
    ("2.0.0", ">1"),
    ("1.3.0", ">1.2"),
    ("1.2.0", ">=1.2"),
    ("1.1.9", "<1.2"),
    ("1.2.9", "<=1.2"),
    ("1.9.9", "<=1"),
    ("1.2.0", "1.2 1.2.0"),
    # tilde
    ("1.2.3", "~1.2.3"),
    ("1.2.9", "~1.2.3"),
    ("1.2.3", "~1.2"),
    ("1.2.0", "~1.2"),
    ("1.9.9", "~1"),
    ("1.0.0", "~1"),
    ("0.2.5", "~0.2.3"),
    ("1.2.3", "~>1.2.3"),
    ("1.2.4", "~ 1.2.3"),
    ("1.2.3", "~*"),
    ("1.2.3-beta.4", "~1.2.3-beta.2"),
    ("1.2.3", "~1.2.3-beta.2"),
    ("1.2.5", "~1.2.3-beta.2"),
    # caret
    ("1.2.3", "^1.2.3"),
    ("1.9.9", "^1.2.3"),
    ("1.2.4", "^ 1.2.3"),
    ("0.2.3", "^0.2.3"),
    ("0.2.9", "^0.2.3"),
    ("0.0.3", "^0.0.3"),
    ("1.2.0", "^1.2.x"),
    ("1.9.0", "^1.2.x"),
    ("0.0.9", "^0.0.x"),
    ("0.0.9", "^0.0"),
    ("1.0.0", "^1.x"),
    ("1.9.9", "^1"),
    ("0.9.9", "^0.x"),
    ("0.9.9", "^0"),
    ("1.2.3", "^*"),
    ("1.2.3-beta.4", "^1.2.3-beta.2"),
    ("1.2.3", "^1.2.3-beta.2"),
    ("1.5.0", "^1.2.3-beta.2"),
    ("0.0.3-beta.4", "^0.0.3-beta"),
    ("0.1.5", "^0.1.2-rc.1"),
    ("1.2.3", "^1.2.3+build"),
    # hyphen ranges
    ("1.2.3", "1.2.3 - 2.3.4"),
    ("1.5.0", "1.2.3 - 2.3.4"),
    ("2.3.4", "1.2.3 - 2.3.4"),
    ("1.2.0", "1.2 - 2.3.4"),
    ("2.3.9", "1.2.3 - 2.3"),
    ("2.9.9", "1.2.3 - 2"),
    ("2.9.9", "1.x - 2.x"),
    ("9.9.9", "1.2.3 - *"),
    ("0.0.1", "* - 2.0.0"),
    ("1.2.3-pre", "1.2.3-pre - 2.0.0"),
    ("2.0.0-pre", "1.2.3 - 2.0.0-pre"),
    ("1.2.3", "v1.2.3 - v2.0.0"),
    # unions
    ("3.0.0", "1.2.3 || >=3"),
    ("1.2.3", "1.2.3 || >=3"),
    ("1.2.3", "~1.2.3 || ^2"),
    ("2.5.0", "~1.2.3 || ^2"),
    ("1.2.3", "||"),
    ("1.2.3", "<1.0.0 || >=1.2.0 <1.3.0"),
    ("1.2.3", ">*  || 1.2.3"),
    # prerelease rule
    ("1.2.3-beta", ">=1.2.3-alpha"),
    ("1.2.3-beta", "1.2.3-beta"),
    ("1.2.3-alpha.7", ">1.2.3-alpha.3"),
    ("3.4.5", ">1.2.3-alpha.3"),
    ("1.2.3-beta", "<1.2.3 >=1.2.3-alpha"),
    ("1.2.3-beta", "1.0.0 || >=1.2.3-alpha <2"),
]

SATISFIES_FALSE = [
    ("1.2.4", "1.2.3"),
    ("1.2.3", ">1.2.3"),
    ("1.2.3", "<1.2.3"),
    ("1.2.4", "<=1.2.3"),
    ("1.2.2", ">=1.2.3"),
    ("1.2.5", ">1.2.3 <1.2.5"),
    ("1.2.3", ">=1.2.3 <1.2.3"),
    ("2.0.0", "1.x"),
    ("0.9.9", "1"),
    ("1.3.0", "1.2"),
    ("1.3.0", "1.2.x"),
    ("1.9.9", ">1"),
    ("1.2.9", ">1.2"),
    ("1.1.9", ">=1.2"),
    ("1.2.0", "<1.2"),
    ("1.3.0", "<=1.2"),
    ("2.0.0", "<=1"),
    ("1.2.3", ">*"),
    ("1.2.3", "<*"),
    ("0.0.0", "<0.0.0"),
    # tilde
    ("1.3.0", "~1.2.3"),
    ("1.2.2", "~1.2.3"),
    ("1.3.0", "~1.2"),
    ("2.0.0", "~1"),
    ("0.3.0", "~0.2.3"),
    ("1.2.4-beta.2", "~1.2.3-beta.2"),
    ("1.2.3-beta.1", "~1.2.3-beta.2"),
    ("1.3.0-0", "~1.2.3"),
    # caret
    ("2.0.0", "^1.2.3"),
    ("1.2.2", "^1.2.3"),
    ("0.3.0", "^0.2.3"),
    ("0.2.2", "^0.2.3"),
    ("0.0.4", "^0.0.3"),
    ("0.0.2", "^0.0.3"),
    ("0.1.0", "^0.0.x"),
    ("0.1.0", "^0.0"),
    ("1.0.0", "^0.x"),
    ("1.0.0", "^0"),
    ("2.0.0", "^1.x"),
    ("1.2.4-beta", "^1.2.3"),
    ("2.0.0-beta", "^1.2.3"),
    ("2.0.0-0", "^1.2.3"),
    ("1.2.4-beta.4", "^1.2.3-beta.2"),
    ("0.0.4", "^0.0.3-beta"),
    ("0.2.0", "^0.1.2-rc.1"),
    # hyphen ranges
    ("1.2.2", "1.2.3 - 2.3.4"),
    ("2.3.5", "1.2.3 - 2.3.4"),
    ("1.1.9", "1.2 - 2.3.4"),
    ("2.4.0", "1.2.3 - 2.3"),
    ("2.4.0-0", "1.2.3 - 2.3"),
    ("3.0.0", "1.2.3 - 2"),
    ("3.0.0", "1.x - 2.x"),
    ("2.0.0", "1.2.3 - 2.0.0-pre"),
    # prerelease versions need a comparator with a prerelease on the same tuple
    ("1.0.0-beta", "*"),
    ("1.0.0-beta", ""),
    ("1.0.0-beta", "x"),
    ("1.0.0-beta", ">=0.0.0"),
    ("1.2.3-alpha", "1.2.3"),
    ("1.2.3-alpha", "1.2"),
    ("1.2.3-beta", "~1.2.2"),
    ("2.0.0-0", "<2.0.0"),
    ("1.2.4-beta", ">=1.2.3-alpha"),
    ("3.4.5-alpha.9", ">1.2.3-alpha.3"),
    ("1.2.3-alpha.1", ">1.2.3-alpha.3"),
    ("1.2.3-beta", "1.0.0 || >=1.2.2 <2"),
    # invalid versions
    ("1.2", "1.2"),
    ("not.a.version", "*"),
    ("=1.2.3", "1.2.3"),
    ("", "*"),
    ("1.2.3.4", "*"),
    ("01.2.3", "*"),
    # invalid ranges
    ("1.2.3", "garbage"),
    ("1.2.3", "not a range"),
    ("1.2.3", "1.2.3 || garbage"),
    ("1.2.3", "1.2-beta"),
    ("1.2.3", ">=1.2.3 foo"),
    ("1.2.3", "01.2.3"),
    ("1.2.3", "^1.2.3.4"),
    ("1.2.3", "~a"),
    ("1.2.3", "=>1.2.3"),
    ("1.2.3", "!1.2.3"),
]


class TestSatisfies(unittest.TestCase):
    def test_true(self):
        for version, rng in SATISFIES_TRUE:
            with self.subTest(version=version, range=rng):
                self.assertIs(satisfies(version, rng), True)

    def test_false(self):
        for version, rng in SATISFIES_FALSE:
            with self.subTest(version=version, range=rng):
                self.assertIs(satisfies(version, rng), False)

    def test_outcome_examples(self):
        self.assertTrue(satisfies("1.2.5", "^1.2.3"))
        self.assertFalse(satisfies("2.0.0", "^1.2.3"))


class TestMaxSatisfying(unittest.TestCase):
    def test_cases(self):
        cases = [
            (["1.2.3", "1.4.0", "2.0.0"], "~1.2", "1.2.3"),
            (["1.2.3", "1.2.4"], "1.2", "1.2.4"),
            (["1.2.4", "1.2.3"], "1.2", "1.2.4"),
            (["1.2.3", "1.2.4", "1.2.5", "1.2.6"], "~1.2.3", "1.2.6"),
            (
                ["1.1.0", "1.2.0", "1.2.1", "1.3.0", "2.0.0b1", "2.0.0b2",
                 "2.0.0b3", "2.0.0", "2.1.0"],
                "~2.0.0",
                "2.0.0",
            ),
            (["1.1.0", "1.2.0"], "2.x", None),
            (["1.2.3"], "garbage", None),
            ([], "*", None),
            (["not-a-version", "1.2"], "*", None),
            (["v1.2.3", "1.2.2"], "*", "v1.2.3"),
            ([" 1.2.3 ", "1.2.2"], "*", " 1.2.3 "),
            (["1.2.3+a", "1.2.3+b"], "1.2.3", "1.2.3+a"),
            (["1.2.3+b", "1.2.3+a"], "1.2.3", "1.2.3+b"),
            (["1.2.3-beta", "1.2.2"], "^1.2.0", "1.2.2"),
            (["1.2.3-beta", "1.2.2"], "^1.2.3-alpha", "1.2.3-beta"),
            (["1.2.3-beta", "1.2.3"], "^1.2.3-alpha", "1.2.3"),
            (["1.10.0", "1.9.0", "1.2.0"], "^1", "1.10.0"),
            (["0.1.0", "0.2.0", "1.0.0"], "1.0.0 || 0.1.x", "1.0.0"),
            (["2.0.0", "3.0.0"], ">*", None),
        ]
        for versions, rng, expected in cases:
            with self.subTest(versions=versions, range=rng):
                self.assertEqual(max_satisfying(versions, rng), expected)


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        proc = subprocess.run(
            [sys.executable, "-m", "src.cli", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return proc

    def test_satisfies_subprocess(self):
        proc = self.run_cli("satisfies", "1.2.5", "^1.2.3")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "true")
        proc = self.run_cli("satisfies", "2.0.0", "^1.2.3")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "false")
        proc = self.run_cli("satisfies", "1.5.0", "1.2.3 - 2.3.4")
        self.assertEqual(proc.stdout.strip(), "true")

    def test_max_subprocess(self):
        proc = self.run_cli("max", "~1.2", "1.2.3", "1.4.0", "2.0.0")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "1.2.3")
        proc = self.run_cli("max", "^3", "1.2.3", "2.0.0")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "null")
        proc = self.run_cli("max", "*")
        self.assertEqual(proc.stdout.strip(), "null")

    def test_usage_error(self):
        self.assertNotEqual(self.run_cli().returncode, 0)
        self.assertNotEqual(self.run_cli("bogus").returncode, 0)
        self.assertNotEqual(self.run_cli("satisfies", "1.2.3").returncode, 0)

    def test_cli_calls_satisfies(self):
        with mock.patch.object(cli, "satisfies", return_value=True) as m:
            out = io.StringIO()
            with redirect_stdout(out):
                code = cli.main(["satisfies", "1.0.0", "^2"])
        m.assert_called_once_with("1.0.0", "^2")
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue().strip(), "true")

    def test_cli_calls_max_satisfying(self):
        with mock.patch.object(cli, "max_satisfying", return_value="9.9.9") as m:
            out = io.StringIO()
            with redirect_stdout(out):
                code = cli.main(["max", "^1", "1.0.0", "1.1.0"])
        m.assert_called_once_with(["1.0.0", "1.1.0"], "^1")
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue().strip(), "9.9.9")

    def test_cli_uses_ranges_functions(self):
        import src.ranges as ranges
        self.assertIs(cli.satisfies, ranges.satisfies)
        self.assertIs(cli.max_satisfying, ranges.max_satisfying)


if __name__ == "__main__":
    unittest.main()
