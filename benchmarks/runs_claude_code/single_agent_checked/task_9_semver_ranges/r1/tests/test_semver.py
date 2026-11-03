"""Tests for the node-semver 7.x compatible implementation (default options).

Expected values are derived from the semver 2.0.0 spec and the documented
node-semver range grammar/desugaring rules.
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
from src.ranges import Range, max_satisfying, satisfies  # noqa: E402
from src.version import compare, valid  # noqa: E402


class TestValid(unittest.TestCase):
    def test_valid_versions(self):
        cases = {
            "1.2.3": "1.2.3",
            "0.0.0": "0.0.0",
            " 1.2.3 ": "1.2.3",
            "\t1.2.3\n": "1.2.3",
            " 1.2.3﻿": "1.2.3",
            "v1.2.3": "1.2.3",
            "1.2.3-alpha": "1.2.3-alpha",
            "1.2.3-alpha.1": "1.2.3-alpha.1",
            "1.2.3-0a": "1.2.3-0a",
            "1.2.3--": "1.2.3--",
            "1.2.3-alpha+build.5": "1.2.3-alpha",
            "1.2.3+001": "1.2.3",
            "1.2.3+build-meta.01": "1.2.3",
            "10.20.30": "10.20.30",
            "9007199254740991.0.0": "9007199254740991.0.0",
            "1.2.3-9007199254740991": "1.2.3-9007199254740991",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(valid(text), expected)

    def test_invalid_versions(self):
        for text in ["", "1", "1.2", "1.2.3.4", "01.2.3", "1.02.3", "1.2.03",
                     "1.2.3-01", "1.2.3-", "1.2.3+", "1.2.3-a..b", "1.2.3-a_b",
                     "=1.2.3", "V1.2.3", "vv1.2.3", "v 1.2.3", "a.b.c", "1.2.3beta",
                     "1.2.3 4", "1.2.3\x85", "1.2.-3", "-1.2.3", "1.2.x", "~1.2.3",
                     "9007199254740992.0.0", "1.9007199254740992.0",
                     "1.2.٣", "1.2.3-é",
                     "1.2.3-" + "a" * 251]:
            with self.subTest(text=text):
                self.assertIsNone(valid(text))

    def test_max_length(self):
        ok = "1.2.3-" + "a" * 250
        self.assertEqual(len(ok), 256)
        self.assertEqual(valid(ok), ok)
        self.assertIsNone(valid(" " + ok))  # untrimmed length is checked


class TestCompare(unittest.TestCase):
    GREATER = [
        ("0.0.0", "0.0.0-foo"), ("0.0.1", "0.0.0"), ("1.0.0", "0.9.9"),
        ("0.10.0", "0.9.0"), ("0.99.0", "0.10.0"), ("2.0.0", "1.2.3"),
        ("v0.0.0", "0.0.0-foo"), ("v0.0.1", "0.0.0"), ("1.2.3", "1.2.3-asdf"),
        ("1.2.3", "1.2.3-4"), ("1.2.3", "1.2.3-4-foo"), ("1.2.3-5-foo", "1.2.3-5"),
        ("1.2.3-5", "1.2.3-4"), ("1.2.3-5-foo", "1.2.3-5-Foo"),
        ("3.0.0", "2.7.2+asdf"), ("1.2.3-a.10", "1.2.3-a.5"),
        ("1.2.3-a.b", "1.2.3-a.5"), ("1.2.3-a.b", "1.2.3-a"),
        ("1.2.3-a.b.c.10.d.5", "1.2.3-a.b.c.5.d.100"),
        ("1.2.3-r2", "1.2.3-r100"), ("1.2.3-r100", "1.2.3-R2"),
        ("1.0.0-alpha.1", "1.0.0-alpha"), ("1.0.0-alpha.beta", "1.0.0-alpha.1"),
        ("1.0.0-beta", "1.0.0-alpha.beta"), ("1.0.0-beta.2", "1.0.0-beta"),
        ("1.0.0-beta.11", "1.0.0-beta.2"), ("1.0.0-rc.1", "1.0.0-beta.11"),
        ("1.0.0", "1.0.0-rc.1"), ("1.0.0-a", "1.0.0-999"),
    ]
    EQUAL = [
        ("1.2.3", "v1.2.3"), ("1.2.3", " 1.2.3 "), ("1.2.3-beta+build", "1.2.3-beta+otherbuild"),
        ("1.2.3+build", "1.2.3+otherbuild"), ("1.2.3-beta.4", "v1.2.3-beta.4"),
    ]

    def test_ordering(self):
        for a, b in self.GREATER:
            with self.subTest(a=a, b=b):
                self.assertEqual(compare(a, b), 1)
                self.assertEqual(compare(b, a), -1)

    def test_equality(self):
        for a, b in self.EQUAL:
            with self.subTest(a=a, b=b):
                self.assertEqual(compare(a, b), 0)
                self.assertEqual(compare(b, a), 0)

    def test_huge_numeric_prerelease_compares_as_doubles(self):
        # Both identifiers exceed MAX_SAFE_INTEGER and round to the same double.
        self.assertEqual(compare("1.0.0-9007199254740993", "1.0.0-9007199254740992"), 0)

    def test_invalid_raises(self):
        for a, b in [("1.2", "1.2.3"), ("1.2.3", "nope"), ("", "1.0.0"), ("=1.0.0", "1.0.0")]:
            with self.subTest(a=a, b=b):
                with self.assertRaises(ValueError):
                    compare(a, b)


INCLUDE = [
    ("1.0.0 - 2.0.0", "1.2.3"), ("^1.2.3+build", "1.2.3"), ("^1.2.3+build", "1.3.0"),
    ("1.2.3-pre+asdf - 2.4.3-pre+asdf", "1.2.3"),
    ("1.2.3-pre+asdf - 2.4.3-pre+asdf", "1.2.3-pre.2"),
    ("1.2.3-pre+asdf - 2.4.3-pre+asdf", "2.4.3-alpha"),
    ("1.2.3+asdf - 2.4.3+asdf", "1.2.3"), ("1.0.0", "1.0.0"), (">=*", "0.2.4"),
    ("", "1.0.0"), ("*", "1.2.3"), ("*", "v1.2.3"), (">=1.0.0", "1.0.0"),
    (">=1.0.0", "1.0.1"), (">=1.0.0", "1.1.0"), (">1.0.0", "1.0.1"), (">1.0.0", "1.1.0"),
    ("<=2.0.0", "2.0.0"), ("<=2.0.0", "1.9999.9999"), ("<=2.0.0", "0.2.9"),
    ("<2.0.0", "1.9999.9999"), ("<2.0.0", "0.2.9"), (">= 1.0.0", "1.0.0"),
    (">=  1.0.0", "1.0.1"), (">=   1.0.0", "1.1.0"), ("> 1.0.0", "1.0.1"),
    (">  1.0.0", "1.1.0"), ("<=   2.0.0", "2.0.0"), ("<= 2.0.0", "1.9999.9999"),
    ("<=  2.0.0", "0.2.9"), ("<    2.0.0", "1.9999.9999"), ("<\t2.0.0", "0.2.9"),
    (">=0.1.97", "v0.1.97"), (">=0.1.97", "0.1.97"), ("0.1.20 || 1.2.4", "1.2.4"),
    (">=0.2.3 || <0.0.1", "0.0.0"), (">=0.2.3 || <0.0.1", "0.2.3"),
    (">=0.2.3 || <0.0.1", "0.2.4"), ("||", "1.3.4"), ("2.x.x", "2.1.3"),
    ("1.2.x", "1.2.3"), ("1.2.x || 2.x", "2.1.3"), ("1.2.x || 2.x", "1.2.3"),
    ("x", "1.2.3"), ("2.*.*", "2.1.3"), ("1.2.*", "1.2.3"), ("1.2.* || 2.*", "2.1.3"),
    ("1.2.* || 2.*", "1.2.3"), ("2", "2.1.2"), ("2.3", "2.3.1"), ("~0.0.1", "0.0.1"),
    ("~0.0.1", "0.0.2"), ("~x", "0.0.9"), ("~2", "2.0.9"), ("~2.4", "2.4.0"),
    ("~2.4", "2.4.5"), ("~>3.2.1", "3.2.2"), ("~1", "1.2.3"), ("~>1", "1.2.3"),
    ("~> 1", "1.2.3"), ("~1.0", "1.0.2"), ("~ 1.0", "1.0.2"), ("~ 1.0.3", "1.0.12"),
    (">=1", "1.0.0"), (">= 1", "1.0.0"), ("<1.2", "1.1.1"), ("< 1.2", "1.1.1"),
    ("~v0.5.4-pre", "0.5.5"), ("~v0.5.4-pre", "0.5.4"), ("=0.7.x", "0.7.2"),
    ("<=0.7.x", "0.7.2"), (">=0.7.x", "0.7.2"), ("<=0.7.x", "0.6.2"),
    ("~1.2.1 >=1.2.3", "1.2.3"), ("~1.2.1 =1.2.3", "1.2.3"), ("~1.2.1 1.2.3", "1.2.3"),
    ("~1.2.1 >=1.2.3 1.2.3", "1.2.3"), ("~1.2.1 1.2.3 >=1.2.3", "1.2.3"),
    (">=1.2.1 1.2.3", "1.2.3"), ("1.2.3 >=1.2.1", "1.2.3"), (">=1.2.3 >=1.2.1", "1.2.3"),
    (">=1.2.1 >=1.2.3", "1.2.3"), (">=1.2", "1.2.8"), ("^1.2.3", "1.8.1"),
    ("^0.1.2", "0.1.2"), ("^0.1", "0.1.2"), ("^0.0.1", "0.0.1"), ("^1.2", "1.4.2"),
    ("^1.2 ^1", "1.4.2"), ("^1.2.3-alpha", "1.2.3-pre"), ("^1.2.0-alpha", "1.2.0-pre"),
    ("^0.0.1-alpha", "0.0.1-beta"), ("^0.0.1-alpha", "0.0.1"),
    ("^0.1.1-alpha", "0.1.1-beta"), ("^x", "1.2.3"), ("x - 1.0.0", "0.9.7"),
    ("x - 1.x", "0.9.7"), ("1.0.0 - x", "1.9.7"), ("1.x - x", "1.9.7"),
    ("<=7.x", "7.9.9"), ("^ 1.2.3", "1.9.0"), ("~> 1.2", "1.2.9"),
    ("1.2.3 - 2", "2.9.9"), ("1.2 - 2.3", "2.3.99"), ("v1.2.3", "1.2.3"),
    ("=1.2.3", "1.2.3"), ("1.2.3+build", "1.2.3"), ("*", "0.0.0"),
    (">=0.0.0", "0.0.0"), ("1.x || >=2.5.0 || 5.0.0 - 7.2.3", "6.1.0"),
    ("^0.0.0", "0.0.0"), ("^0.0", "0.0.9"), ("^0", "0.9.9"), ("~0", "0.9.9"),
    ("1.2.3-alpha.1 - 1.2.3-alpha.5", "1.2.3-alpha.3"),
    (">1.2.3-alpha.3", "1.2.3-alpha.7"), (">1.2.3-alpha.3", "3.4.5"),
    ("~1.2.3-beta.2", "1.2.3-beta.4"), ("~1.2.3-beta.2", "1.2.9"),
    ("^1.2.3-beta.2", "1.2.3-beta.4"), ("1.2.3 || 1.2.4-rc.1", "1.2.4-rc.1"),
    ("~1.2+build", "1.2.5"), (" ^1.2.3　", "1.5.0"),
]

EXCLUDE = [
    ("1.0.0 - 2.0.0", "2.2.3"), ("1.2.3+asdf - 2.4.3+asdf", "1.2.3-pre.2"),
    ("1.2.3+asdf - 2.4.3+asdf", "2.4.3-alpha"), ("^1.2.3+build", "2.0.0"),
    ("^1.2.3+build", "1.2.0"), ("^1.2.3", "1.2.3-pre"), ("^1.2", "1.2.0-pre"),
    (">1.2", "1.3.0-beta"), ("<=1.2.3", "1.2.3-beta"), ("^1.2.3", "1.2.3-beta"),
    ("=0.7.x", "0.7.0-asdf"), (">=0.7.x", "0.7.0-asdf"), ("<=0.7.x", "0.7.0-asdf"),
    ("1.0.0", "1.0.1"), (">=1.0.0", "0.0.0"), (">=1.0.0", "0.0.1"), (">=1.0.0", "0.1.0"),
    (">1.0.0", "0.0.1"), (">1.0.0", "0.1.0"), ("<=2.0.0", "3.0.0"),
    ("<=2.0.0", "2.9999.9999"), ("<=2.0.0", "2.2.9"), ("<2.0.0", "2.9999.9999"),
    ("<2.0.0", "2.2.9"), (">=0.1.97", "v0.1.93"), (">=0.1.97", "0.1.93"),
    ("0.1.20 || 1.2.4", "1.2.3"), (">=0.2.3 || <0.0.1", "0.0.3"),
    (">=0.2.3 || <0.0.1", "0.2.2"), ("2.x.x", "1.1.3"), ("2.x.x", "3.1.3"),
    ("1.2.x", "1.3.3"), ("1.2.x || 2.x", "3.1.3"), ("1.2.x || 2.x", "1.1.3"),
    ("2.*.*", "1.1.3"), ("2.*.*", "3.1.3"), ("1.2.*", "1.3.3"), ("1.2.* || 2.*", "3.1.3"),
    ("1.2.* || 2.*", "1.1.3"), ("2", "1.1.2"), ("2.3", "2.4.1"), ("~0.0.1", "0.1.0-alpha"),
    ("~0.0.1", "0.1.0"), ("~2.4", "2.5.0"), ("~2.4", "2.3.9"), ("~>3.2.1", "3.3.2"),
    ("~>3.2.1", "3.2.0"), ("~1", "0.2.3"), ("~>1", "2.2.3"), ("~1.0", "1.1.0"),
    ("<1", "1.0.0"), (">=1.2", "1.1.1"), ("~v0.5.4-beta", "0.5.4-alpha"),
    ("=0.7.x", "0.8.2"), (">=0.7.x", "0.6.2"), ("<0.7.x", "0.7.2"),
    ("<1.2.3", "1.2.3-beta"), ("=1.2.3", "1.2.3-beta"), (">1.2", "1.2.8"),
    ("^0.0.1", "0.0.2-alpha"), ("^0.0.1", "0.0.2"), ("^1.2.3", "2.0.0-alpha"),
    ("^1.2.3", "1.2.2"), ("^1.2", "1.1.9"), ("*", "v1.2.3-foo"), ("^1.0.0", "2.0.0-rc1"),
    ("1 - 2", "2.0.0-pre"), ("1 - 2", "1.0.0-pre"), ("1.0 - 2", "1.0.0-pre"),
    ("1.1.x", "1.0.0-a"), ("1.1.x", "1.1.0-a"), ("1.1.x", "1.2.0-a"), ("1.x", "1.0.0-a"),
    ("1.x", "1.1.0-a"), ("1.x", "1.2.0-a"), (">=1.0.0 <1.1.0", "1.1.0"),
    (">=1.0.0 <1.1.0", "1.1.0-pre"), (">=1.0.0 <1.1.0-pre", "1.1.0-pre"),
    ("^0.1.2", "0.2.0"), ("^0.0.3", "0.0.4"), ("^0", "1.0.0"), ("^0.0", "0.1.0"),
    (">1.2.3-alpha.3", "1.2.3-alpha.2"), (">1.2.3-alpha.3", "3.4.5-alpha.9"),
    ("~1.2.3-beta.2", "1.2.4-beta.2"), ("1.2.3 - 2", "3.0.0"), ("1.2 - 2.3", "2.4.0"),
    (">*", "1.0.0"), ("<*", "1.0.0"), (">x", "0.0.0"), ("<0.0.0-0", "0.0.0"),
    (">1 || <x", "1.5.0"), ("", "1.0.0-beta"), ("x", "1.0.0-beta"),
    ("1.2.3 - 1.2.4", "1.2.4-0"), ("1.2.3 || 1.2.4-rc.1", "1.2.4-rc.2"),
]

INVALID_RANGES = [
    "blerg", "git+https://user:password0123@github.com/foo", ">=", "1.2.3 - ",
    "1.2.3 ||| 2.0.0", ">==1.2.3", "~01.2.3", "^1.2.3.4", "1.2.3-01", ">=1.2.3 foo",
    ">1.2.3 <", "1.2.3 - =2.0.0", "> = 1.2.3", "^9007199254740991",
    "<9007199254740992.x", ">9007199254740991.x", "99999999999999999999999.x", "1.2.3 - 99999999999999999999",
    "~1.2.3.4", "1.2.3beta", "a || 1.2.3", "!1.2.3", "*.*.*.*",
]


class TestSatisfies(unittest.TestCase):
    def test_include(self):
        for rng, ver in INCLUDE:
            with self.subTest(range=rng, version=ver):
                self.assertTrue(satisfies(ver, rng))

    def test_exclude(self):
        for rng, ver in EXCLUDE:
            with self.subTest(range=rng, version=ver):
                self.assertFalse(satisfies(ver, rng))

    def test_invalid_range_is_false(self):
        for rng in INVALID_RANGES:
            with self.subTest(range=rng):
                with self.assertRaises(ValueError):
                    Range(rng)
                self.assertFalse(satisfies("1.2.3", rng))

    def test_invalid_version_is_false(self):
        for ver in ["", "1.2", "not a version", "=1.2.3", "1.2.3.4", "01.2.3"]:
            with self.subTest(version=ver):
                self.assertFalse(satisfies(ver, "*"))
                self.assertFalse(satisfies(ver, ""))

    def test_desugaring(self):
        cases = {
            "1.2.3 - 2.3.4": [[">=1.2.3", "<=2.3.4"]],
            "1.2 - 2.3.4": [[">=1.2.0", "<=2.3.4"]],
            "1.2.3 - 2.3": [[">=1.2.3", "<2.4.0-0"]],
            "1.2.3 - 2": [[">=1.2.3", "<3.0.0-0"]],
            "*": [[""]], "": [[""]], "1.x": [[">=1.0.0", "<2.0.0-0"]],
            "1.2.x": [[">=1.2.0", "<1.3.0-0"]],
            "~1.2.3": [[">=1.2.3", "<1.3.0-0"]], "~1.2": [[">=1.2.0", "<1.3.0-0"]],
            "~1": [[">=1.0.0", "<2.0.0-0"]], "~0.2.3": [[">=0.2.3", "<0.3.0-0"]],
            "~1.2.3-beta.2": [[">=1.2.3-beta.2", "<1.3.0-0"]],
            "^1.2.3": [[">=1.2.3", "<2.0.0-0"]], "^0.2.3": [[">=0.2.3", "<0.3.0-0"]],
            "^0.0.3": [[">=0.0.3", "<0.0.4-0"]],
            "^1.2.3-beta.2": [[">=1.2.3-beta.2", "<2.0.0-0"]],
            "^0.0.3-beta": [[">=0.0.3-beta", "<0.0.4-0"]],
            "^1.2.x": [[">=1.2.0", "<2.0.0-0"]], "^0.0.x": [["<0.1.0-0"]],
            "^0.0": [["<0.1.0-0"]], "^1.x": [[">=1.0.0", "<2.0.0-0"]],
            "^0.x": [["<1.0.0-0"]], ">1": [[">=2.0.0"]], ">1.2": [[">=1.3.0"]],
            "<1.2": [["<1.2.0-0"]], "<=1.2": [["<1.3.0-0"]], "<=1": [["<2.0.0-0"]],
            ">=1.2": [[">=1.2.0"]], ">*": [["<0.0.0-0"]], "<x": [["<0.0.0-0"]],
            ">=0.0.0": [[""]], "=1.2.3": [["1.2.3"]], "v1.2.3": [["1.2.3"]],
            "1.2.3 1.2.3": [["1.2.3"]], "* >=1.2.3": [[">=1.2.3"]],
            ">=1.2.3 <0.0.0-0 <2": [["<0.0.0-0"]],
            "<0.0.0-0 || 1.x": [[">=1.0.0", "<2.0.0-0"]],
            "<0.0.0-0 || >*": [["<0.0.0-0"]],
            "1.x || * || 2.x": [[""]],
            "<9007199254740991.x": [["<9007199254740991.0.0-0"]],
            "> 1.2.3   <  1.2.5": [[">1.2.3", "<1.2.5"]],
        }
        for rng, expected in cases.items():
            with self.subTest(range=rng):
                got = [[c.value for c in s] for s in Range(rng).set]
                self.assertEqual(got, expected)


class TestMaxSatisfying(unittest.TestCase):
    def test_cases(self):
        cases = [
            (["1.2.3", "1.2.4"], "1.2", "1.2.4"),
            (["1.2.4", "1.2.3"], "1.2", "1.2.4"),
            (["1.2.3", "1.2.4", "1.2.5", "1.2.6"], "~1.2.3", "1.2.6"),
            (["1.1.0", "1.2.0", "1.2.1", "1.3.0", "2.0.0b1", "2.0.0b2", "2.0.0b3",
              "2.0.0", "2.1.0"], "~2.0.0", "2.0.0"),
            (["1.2.3", "1.4.0", "2.0.0"], "~1.2", "1.2.3"),
            (["v1.2.3", "1.2.3"], "1.2.3", "v1.2.3"),
            (["1.2.3", "v1.2.3"], "1.2.3", "1.2.3"),
            ([" 1.5.0 ", "1.4.0"], "^1", " 1.5.0 "),
            (["1.0.0-beta", "0.9.0"], "*", "0.9.0"),
            (["1.0.0-beta.2", "1.0.0-beta.10", "1.0.0"], ">=1.0.0-beta <1.0.0", "1.0.0-beta.10"),
            (["2.0.0", "3.0.0"], "^1", None),
            ([], "*", None),
            (["1.2.3", "1.2.4"], "not a range", None),
            (["junk", "", "1.0.0"], "*", "1.0.0"),
        ]
        for versions, rng, expected in cases:
            with self.subTest(versions=versions, range=rng):
                self.assertEqual(max_satisfying(versions, rng), expected)


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(list(args))
        return code, buf.getvalue().strip()

    def test_satisfies_command(self):
        self.assertEqual(self.run_cli("satisfies", "1.2.5", "^1.2.3"), (0, "true"))
        self.assertEqual(self.run_cli("satisfies", "2.0.0", "^1.2.3"), (0, "false"))

    def test_max_command(self):
        self.assertEqual(self.run_cli("max", "~1.2", "1.2.3", "1.4.0", "2.0.0"), (0, "1.2.3"))
        self.assertEqual(self.run_cli("max", "^3", "1.2.3"), (0, "null"))
        self.assertEqual(self.run_cli("max", "*"), (0, "null"))

    def test_cli_delegates_to_library(self):
        with mock.patch.object(cli, "satisfies", return_value=True) as sat:
            self.assertEqual(self.run_cli("satisfies", "x", "y"), (0, "true"))
            sat.assert_called_once_with("x", "y")
        with mock.patch.object(cli, "max_satisfying", return_value="9.9.9") as mx:
            self.assertEqual(self.run_cli("max", "r", "a", "b"), (0, "9.9.9"))
            mx.assert_called_once_with(["a", "b"], "r")

    def test_usage_error(self):
        with redirect_stdout(io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
            self.assertEqual(cli.main([]), 2)
            self.assertEqual(cli.main(["satisfies", "1.0.0"]), 2)

    def test_module_entrypoint(self):
        out = subprocess.run(
            [sys.executable, "-m", "src.cli", "satisfies", "1.2.5", "^1.2.3"],
            cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.strip(), "true")
        out = subprocess.run(
            [sys.executable, "-m", "src.cli", "max", "~1.2", "1.2.3", "1.4.0"],
            cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.strip(), "1.2.3")


if __name__ == "__main__":
    unittest.main()
