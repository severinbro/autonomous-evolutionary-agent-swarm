"""Range desugaring table (expected values hand-derived from node-semver 7.x rules)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ranges import Range, max_satisfying, satisfies  # noqa: E402


def desugar(text):
    return " || ".join(" ".join(c.value for c in s) for s in Range(text).set)


class TestDesugar(unittest.TestCase):
    CASES = [
        # hyphen ranges
        ("1.0.0 - 2.0.0", ">=1.0.0 <=2.0.0"),
        ("1.2.3 - 2.3", ">=1.2.3 <2.4.0-0"),
        ("1.2.3 - 2", ">=1.2.3 <3.0.0-0"),
        ("1.2 - 2.3.4", ">=1.2.0 <=2.3.4"),
        ("1.2.3-pre - 2.0.0-rc.1", ">=1.2.3-pre <=2.0.0-rc.1"),
        ("x - 1.0.0", "<=1.0.0"),
        ("1.0.0 - x", ">=1.0.0"),
        ("1.2.3\t-\t2.0.0", ">=1.2.3 <=2.0.0"),
        # caret
        ("^1.2.3", ">=1.2.3 <2.0.0-0"),
        ("^0.2.3", ">=0.2.3 <0.3.0-0"),
        ("^0.0.3", ">=0.0.3 <0.0.4-0"),
        ("^1.2.3-beta.2", ">=1.2.3-beta.2 <2.0.0-0"),
        ("^0.0.3-beta", ">=0.0.3-beta <0.0.4-0"),
        ("^1.2.x", ">=1.2.0 <2.0.0-0"),
        ("^0.0.x", "<0.1.0-0"),
        ("^0.0", "<0.1.0-0"),
        ("^1.x", ">=1.0.0 <2.0.0-0"),
        ("^0.x", "<1.0.0-0"),
        ("^ 1.2", ">=1.2.0 <2.0.0-0"),
        ("^1.2.3+build", ">=1.2.3 <2.0.0-0"),
        # tilde
        ("~1.2.3", ">=1.2.3 <1.3.0-0"),
        ("~1.2", ">=1.2.0 <1.3.0-0"),
        ("~1", ">=1.0.0 <2.0.0-0"),
        ("~> 1.2.3", ">=1.2.3 <1.3.0-0"),
        ("~ 1.2", ">=1.2.0 <1.3.0-0"),
        ("~1.2.3-beta.2", ">=1.2.3-beta.2 <1.3.0-0"),
        ("~v0.5.4-pre", ">=0.5.4-pre <0.6.0-0"),
        # x-ranges and primitives
        (">1", ">=2.0.0"),
        (">1.2", ">=1.3.0"),
        (">=1.2", ">=1.2.0"),
        ("<1.2", "<1.2.0-0"),
        ("<=1.2", "<1.3.0-0"),
        ("<=1", "<2.0.0-0"),
        ("=1.2.x", ">=1.2.0 <1.3.0-0"),
        ("1.2", ">=1.2.0 <1.3.0-0"),
        ("2.*.*", ">=2.0.0 <3.0.0-0"),
        ("*", ""),
        ("", ""),
        ("x", ""),
        (">=*", ""),
        ("<*", "<0.0.0-0"),
        (">*", "<0.0.0-0"),
        (">=0.0.0", ""),
        ("v1.2.3", "1.2.3"),
        ("=1.2.3", "1.2.3"),
        (">=v1.2.3", ">=1.2.3"),
        ("1.2.3+build", "1.2.3"),
        (">= 1.2.3 < 2", ">=1.2.3 <2.0.0-0"),
        # set collapsing
        ("1.2.3 || 2.x", "1.2.3 || >=2.0.0 <3.0.0-0"),
        ("<0.0.0-0 || 1.x", ">=1.0.0 <2.0.0-0"),
        ("1.x || *", ""),
        ("||", ""),
        ("1.2.3 1.2.3", "1.2.3"),
        ("* >=1.0.0", ">=1.0.0"),
        ("<* >=1.0.0", "<0.0.0-0"),
    ]

    def test_desugar(self):
        for text, expected in self.CASES:
            with self.subTest(range=text):
                self.assertEqual(desugar(text), expected)

    INVALID = [
        "blerg", ">=", "a.b.c", "1.2.3.4", ">01.2.3", "~1.2.3 - 2",
        "1.2.3 - 2 - 3", "**", ">=1.2.3 garbage", "1.2.3 -", "01.2.3",
        "^1.2.3.4", "~a", "1.2.3-01", "> = 1.2.3",
        ">9007199254740991", "9007199254740992.0.0",
    ]

    def test_invalid(self):
        for text in self.INVALID:
            with self.subTest(range=text):
                with self.assertRaises((ValueError, TypeError)):
                    Range(text)
                self.assertFalse(satisfies("1.2.3", text))
                self.assertIsNone(max_satisfying(["1.2.3"], text))

    def test_non_string_range(self):
        self.assertFalse(satisfies("1.2.3", None))
        self.assertIsNone(max_satisfying(["1.2.3"], 123))

    def test_max_satisfying_rules(self):
        # returned exactly as given; first of equal-precedence versions wins
        self.assertEqual(max_satisfying(["v1.2.3", "1.2.3+b"], "1.x"), "v1.2.3")
        self.assertEqual(max_satisfying(["1.2.3", "bogus", "1.2.4"], "~1.2"), "1.2.4")
        self.assertIsNone(max_satisfying([], "*"))
        self.assertIsNone(max_satisfying(["1.3.0-beta"], "^1.2.0"))
        self.assertEqual(max_satisfying(["1.2.3-beta.1", "1.2.3-beta.2"], "^1.2.3-beta.0"),
                         "1.2.3-beta.2")

    def test_prerelease_tuple_rule(self):
        self.assertTrue(satisfies("1.2.3-beta.3", "^1.2.3-beta.2"))
        self.assertFalse(satisfies("1.2.4-beta", "^1.2.3-beta.2"))
        self.assertTrue(satisfies("1.2.4-beta", ">1.2.3 || >=1.2.4-alpha"))
        self.assertFalse(satisfies("1.2.4-beta", ">1.2.3"))
        self.assertFalse(satisfies("1.0.0-rc.1", "*"))
        self.assertFalse(satisfies("1.0.0-rc.1", ""))


if __name__ == "__main__":
    unittest.main()
