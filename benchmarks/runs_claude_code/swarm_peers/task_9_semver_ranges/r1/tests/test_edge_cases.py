"""Edge cases for node-semver 7.x (default options) compatibility.

All expected values were derived by hand from the node-semver algorithm
(regex grammar, range desugaring rules, prerelease exclusion rule); no other
semver implementation was run or consulted.
"""

import unittest

from src.version import compare, valid
from src.ranges import max_satisfying, satisfies


class VersionValidityEdgeCases(unittest.TestCase):
    def test_valid_forms(self):
        cases = {
            "1.2.3": "1.2.3",
            "v1.2.3": "1.2.3",
            " v1.2.3 ": "1.2.3",
            "\t1.2.3\n": "1.2.3",
            "﻿1.2.3 ": "1.2.3",  # BOM / NBSP are JS whitespace
            "0.0.0": "0.0.0",
            "1.2.3-0": "1.2.3-0",
            "1.2.3-0a": "1.2.3-0a",
            "1.2.3--": "1.2.3--",
            "1.2.3-alpha.1+build.01": "1.2.3-alpha.1",
            "1.2.3+01": "1.2.3",
            "1.2.3+-": "1.2.3",
            "1.2.3-x.7.z.92": "1.2.3-x.7.z.92",
            "9007199254740991.0.0": "9007199254740991.0.0",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(valid(text), expected)

    def test_invalid_forms(self):
        for text in [
            "", "1", "1.2", "1.2.3.4", "=1.2.3", "V1.2.3", "vv1.2.3", "v 1.2.3",
            "1 .2.3", "01.2.3", "1.02.3", "1.2.03", "1.2.3-01", "1.2.3-alpha.01",
            "1.2.3-", "1.2.3+", "1.2.3-a..b", "1.2.3+a..b", "1.2.3-a_b",
            "1.2.3beta", "-1.2.3", "9007199254740992.0.0", "1.9007199254740992.0",
            "1.2.3\x1c", "1.2.3\x85", "1.2.3-١", "١.2.3", "x.2.3",
            "1.2.*", "NOT VALID",
        ]:
            with self.subTest(text=text):
                self.assertIsNone(valid(text))

    def test_non_strings(self):
        self.assertIsNone(valid(None))
        self.assertIsNone(valid(123))

    def test_max_length(self):
        self.assertEqual(valid("1.2.3-" + "a" * 250), "1.2.3-" + "a" * 250)
        self.assertIsNone(valid("1.2.3-" + "a" * 251))
        # Length is checked before trimming.
        self.assertIsNone(valid("1.2.3-" + "a" * 250 + " "))
        self.assertEqual(valid("1.2.3-" + "a" * 249 + " "), "1.2.3-" + "a" * 249)


class CompareEdgeCases(unittest.TestCase):
    def test_greater(self):
        for a, b in [
            ("0.0.0", "0.0.0-foo"), ("0.0.1", "0.0.0"), ("1.0.0", "0.9.9"),
            ("0.10.0", "0.9.0"), ("0.99.0", "0.10.0"), ("2.0.0", "1.2.3"),
            ("v0.0.0", "0.0.0-foo"), ("1.2.3", "1.2.3-asdf"), ("1.2.3", "1.2.3-4"),
            ("1.2.3", "1.2.3-4-foo"), ("1.2.3-5-foo", "1.2.3-5"), ("1.2.3-5", "1.2.3-4"),
            ("1.2.3-5-foo", "1.2.3-5-Foo"), ("3.0.0", "2.7.2+asdf"),
            ("1.2.3-a.10", "1.2.3-a.5"), ("1.2.3-a.b", "1.2.3-a.5"), ("1.2.3-a.b", "1.2.3-a"),
            ("1.2.3-a.b.c.10.d.5", "1.2.3-a.b.c.5.d.100"), ("1.2.3-r2", "1.2.3-r100"),
            ("1.2.3-r100", "1.2.3-R2"), ("1.0.0-alpha.beta", "1.0.0-alpha.1"),
            ("1.0.0-beta.11", "1.0.0-beta.2"), ("1.0.0-rc.1", "1.0.0-beta.11"),
        ]:
            with self.subTest(a=a, b=b):
                self.assertEqual(compare(a, b), 1)
                self.assertEqual(compare(b, a), -1)

    def test_equal(self):
        for a, b in [
            ("1.2.3", "v1.2.3"), ("1.2.3-beta+build", "1.2.3-beta+otherbuild"),
            ("1.2.3+build", "1.2.3+otherbuild"), (" v1.2.3+build ", "1.2.3+otherbuild"),
            # Huge numeric prerelease ids are compared as JS doubles.
            ("1.0.0-9007199254740993", "1.0.0-9007199254740992"),
        ]:
            with self.subTest(a=a, b=b):
                self.assertEqual(compare(a, b), 0)

    def test_invalid_raises(self):
        for a, b in [("1.2", "1.2.3"), ("1.2.3", "=1.2.3"), ("1.2.3", None), ("x", "y")]:
            with self.subTest(a=a, b=b):
                with self.assertRaises(ValueError):
                    compare(a, b)


class RangeEdgeCases(unittest.TestCase):
    INCLUDED = [
        ("1.0.0 - 2.0.0", "1.2.3"), ("^1.2.3+build", "1.2.3"), ("^1.2.3+build", "1.3.0"),
        ("1.2.3-pre+asdf - 2.4.3-pre+asdf", "1.2.3"),
        ("1.2.3-pre+asdf - 2.4.3-pre+asdf", "1.2.3-pre.2"),
        ("1.2.3-pre+asdf - 2.4.3-pre+asdf", "2.4.3-alpha"),
        ("1.2.3+asdf - 2.4.3+asdf", "1.2.3"), ("1.0.0", "1.0.0"), (">=*", "0.2.4"),
        ("", "1.0.0"), ("*", "1.2.3"), (">=1.0.0", "1.0.0"), (">1.0.0", "1.0.1"),
        ("<=2.0.0", "2.0.0"), ("<2.0.0", "1.9999.9999"), (">= 1.0.0", "1.0.0"),
        (">=  1.0.0", "1.0.1"), ("<=   2.0.0", "2.0.0"), ("0.1.20 || 1.2.4", "1.2.4"),
        (">=0.2.3 || <0.0.1", "0.0.0"), (">=0.2.3 || <0.0.1", "0.2.3"), ("||", "1.3.4"),
        ("2.x.x", "2.1.3"), ("1.2.x || 2.x", "2.1.3"), ("x", "1.2.3"), ("2.*.*", "2.1.3"),
        ("2", "2.1.2"), ("2.3", "2.3.1"), ("~0.0.1", "0.0.2"), ("~x", "0.0.9"),
        ("~2.4", "2.4.5"), ("~>3.2.1", "3.2.2"), ("~> 1", "1.2.3"), ("~ 1.0", "1.0.2"),
        (">= 1", "1.0.0"), ("< 1.2", "1.1.1"), ("~v0.5.4-pre", "0.5.5"),
        ("~v0.5.4-pre", "0.5.4"), ("=0.7.x", "0.7.2"), ("<=0.7.x", "0.7.2"),
        ("~1.2.1 >=1.2.3", "1.2.3"), ("~1.2.1 =1.2.3", "1.2.3"), ("~1.2.1 1.2.3", "1.2.3"),
        ("^1.2.3", "1.8.1"), ("^0.1.2", "0.1.2"), ("^0.1", "0.1.2"), ("^0.0.1", "0.0.1"),
        ("^1.2 ^1", "1.4.2"), ("^1.2.3-alpha", "1.2.3-pre"), ("^0.0.1-alpha", "0.0.1-beta"),
        ("^0.0.1-alpha", "0.0.1"), ("^x", "1.2.3"), ("x - 1.0.0", "0.9.7"),
        ("x - 1.x", "0.9.7"), ("1.0.0 - x", "1.9.7"), ("1.x - x", "1.9.7"), ("<=7.x", "7.9.9"),
        ("^ 1.2.3", "1.5.0"), (">=v1.2.3", "1.2.3"), (">= v1.2.3", "1.2.3"),
        ("=v1.2.3", "1.2.3"), ("v1.2.3 - v2.0.0", "1.5.0"), ("1.2.3 - 2.3", "2.3.9"),
        ("1.2.3 - 2", "2.9.9"), ("1.2 - 2.3.4", "1.2.0"), (">1", "2.0.0"), (">1.2", "1.3.0"),
        ("<=1.2", "1.2.9"), ("1.x.3", "1.5.0"), ("1.X", "1.9.0"), ("X", "0.0.1"),
        ("^0.0", "0.0.5"), ("^0", "0.9.9"), ("^0.0.0", "0.0.0"), ("^1.x", "1.0.0"),
        ("^1.2.x", "1.9.9"), ("^0.2.x", "0.2.9"), ("~1.2.3-beta.2", "1.2.3-beta.4"),
        ("~1.2.3-beta.2", "1.2.3-beta.10"), ("1.2.3-beta", "1.2.3-beta+b"),
        (">=1.2.3-beta", "1.2.3-gamma"), (">1.2.3-0", "1.2.3"),
        (">=1.0.0-rc.1 <2 || 3", "1.0.0-rc.2"), ("^1.2.3 ~1.2.4", "1.2.5"),
        ("1 - 2 || 4 - 5", "4.5.0"), (">=1.2.3\t<2", "1.5.0"),
        (">=1.2.3 <2.0.0", "1.5.0"), (" 1.2.3 ", "1.2.3"), ("1.2.3", " v1.2.3 "),
        ("9007199254740991.0.0", "9007199254740991.0.0"),
    ]

    EXCLUDED = [
        ("1.0.0 - 2.0.0", "2.2.3"), ("1.2.3+asdf - 2.4.3+asdf", "1.2.3-pre.2"),
        ("^1.2.3+build", "2.0.0"), ("^1.2.3+build", "1.2.0"), ("^1.2.3", "1.2.3-pre"),
        ("^1.2", "1.2.0-pre"), (">1.2", "1.3.0-beta"), ("<=1.2.3", "1.2.3-beta"),
        ("=0.7.x", "0.7.0-asdf"), (">=0.7.x", "0.7.0-asdf"), ("1.0.0", "1.0.1"),
        (">=1.0.0", "0.0.0"), ("<=2.0.0", "2.2.9"), (">=0.1.97", "v0.1.93"),
        ("0.1.20 || 1.2.4", "1.2.3"), (">=0.2.3 || <0.0.1", "0.0.3"), ("2.x.x", "3.1.3"),
        ("1.2.* || 2.*", "1.1.3"), ("2", "1.1.2"), ("2.3", "2.4.1"), ("~0.0.1", "0.1.0-alpha"),
        ("~0.0.1", "0.1.0"), ("~2.4", "2.5.0"), ("~>3.2.1", "3.3.2"), ("~1", "0.2.3"),
        ("~1.0", "1.1.0"), ("<1", "1.0.0"), (">=1.2", "1.1.1"), ("~v0.5.4-beta", "0.5.4-alpha"),
        ("<0.7.x", "0.7.2"), ("<1.2.3", "1.2.3-beta"), ("=1.2.3", "1.2.3-beta"),
        (">1.2", "1.2.8"), ("^0.0.1", "0.0.2-alpha"), ("^0.0.1", "0.0.2"),
        ("^1.2.3", "2.0.0-alpha"), ("^1.2.3", "1.2.2"), ("^1.2", "1.1.9"), ("*", "v1.2.3-foo"),
        ("", "1.0.0-beta"), ("^1.0.0", "2.0.0-rc1"), ("^1.0.0", "1.0.0-rc1"),
        ("1 - 2", "2.0.0-pre"), ("1 - 2", "1.0.0-pre"), ("1.0 - 2", "1.0.0-pre"),
        ("1.1.x", "1.1.0-a"), ("1.x", "1.2.0-a"), (">=1.0.0 <1.1.0", "1.1.0"),
        (">=1.0.0 <1.1.0", "1.1.0-pre"), (">=1.0.0 <1.1.0-pre", "1.1.0-pre"),
        ("1.2.3 - 2.3", "2.4.0"), ("1.2.3 - 2.3", "2.4.0-0"), ("1.2.3 - 2", "3.0.0"),
        ("<=1.2", "1.3.0-0"), ("<=1.2", "1.2.5-beta"), ("<1.3", "1.3.0-beta"),
        ("^1.2.3-alpha", "1.2.4-alpha"), ("~1.2.3-beta.2", "1.2.4-beta.2"),
        ("~1.2.3-beta.2", "1.2.3-beta.1"), ("^0.0", "0.1.0"), ("^0.0.0", "0.0.1"),
        (">=1.2.3-beta", "1.3.0-beta"), ("<2.0.0-0", "1.5.0-beta"), ("<2.0.0", "2.0.0-beta"),
        ("^1.2.3 ~1.2.4", "1.3.0"), (">*", "1.0.0"), ("<*", "0.0.0"), (">x", "1.0.0"),
        ("1.2.3", "1.2"), ("1.2.3", "=1.2.3"), ("1.2.3", ""),
    ]

    INVALID_RANGES = [
        "blerg", "==1.2.3", "v=1.2.3", ">>1.2.3", "1.2.3.4", "01.2.3", "1.02", "1.2.3-01",
        "1.2.3 ||| 2", "1.0.0 - 2.0.0 >1.5.0", "1.2.3- 2.0.0", "=1.2.3 - 2.0.0",
        "1.2.3 - =2.0.0", "1.2.3\x1c", "^1.2.3.4", "~1.2.3-", ">=1.2.3 junk",
        "^9007199254740991.0.0", "~1.9007199254740991.0", ">=1.2.3-" + "a" * 260,
        # node's safeRe caps identifier lengths (250 letters / 256 digits).
        "1.2.3+" + "a" * 300, "x.1.1-" + "a" * 300, "x." + "1" * 300,
    ]

    def test_long_build_within_cap(self):
        self.assertTrue(satisfies("1.2.3", "1.2.3+" + "a" * 250))

    def test_included(self):
        for rng, ver in self.INCLUDED:
            with self.subTest(range=rng, version=ver):
                self.assertTrue(satisfies(ver, rng))

    def test_excluded(self):
        for rng, ver in self.EXCLUDED:
            with self.subTest(range=rng, version=ver):
                self.assertFalse(satisfies(ver, rng))

    def test_invalid_ranges_never_satisfied(self):
        for rng in self.INVALID_RANGES:
            for ver in ["0.0.0", "1.2.3", "1.5.0", "2.0.0", "9007199254740991.0.0", "1.9007199254740991.0"]:
                with self.subTest(range=rng, version=ver):
                    self.assertFalse(satisfies(ver, rng))
            with self.subTest(range=rng, fn="max_satisfying"):
                self.assertIsNone(max_satisfying(["1.2.3", "1.5.0", "2.0.0"], rng))


class MaxSatisfyingEdgeCases(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(max_satisfying(["1.2.3", "1.2.4"], "1.2"), "1.2.4")
        self.assertEqual(max_satisfying(["1.2.4", "1.2.3"], "1.2"), "1.2.4")
        self.assertEqual(max_satisfying(["1.2.3", "1.2.4", "1.2.5", "1.2.6"], "~1.2.3"), "1.2.6")
        self.assertEqual(
            max_satisfying(["1.1.0", "1.2.0", "1.2.1", "1.3.0", "2.0.0b1", "2.0.0b2",
                            "2.0.0b3", "2.0.0", "2.1.0"], "~2.0.0"),
            "2.0.0",
        )

    def test_returns_input_string_verbatim(self):
        self.assertEqual(max_satisfying(["v1.2.3", "1.2.4+build"], "^1"), "1.2.4+build")
        self.assertEqual(max_satisfying([" v1.9.0 ", "1.2.4"], "^1"), " v1.9.0 ")

    def test_first_of_equal_precedence_wins(self):
        self.assertEqual(max_satisfying(["1.2.3+a", "v1.2.3", "1.2.3+b"], "1.2.3"), "1.2.3+a")

    def test_skips_invalid_and_prereleases(self):
        self.assertEqual(max_satisfying(["junk", "1.0.0", "", "1.1.0-beta"], "*"), "1.0.0")
        self.assertEqual(max_satisfying(["1.2.3-beta.1", "1.2.3-beta.3", "1.2.4-beta"],
                                        ">=1.2.3-beta.0"), "1.2.3-beta.3")

    def test_none_results(self):
        self.assertIsNone(max_satisfying([], "*"))
        self.assertIsNone(max_satisfying(["1.0.0", "2.0.0"], "^3"))
        self.assertIsNone(max_satisfying(["1.2.3", "1.2.4"], "not a range"))


if __name__ == "__main__":
    unittest.main()
