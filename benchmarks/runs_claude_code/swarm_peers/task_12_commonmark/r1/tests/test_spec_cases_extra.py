"""Additional hand-written CommonMark 0.31.2 spec-example cases (peer-1)."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.render import render  # noqa: E402
import peer1_spec_cases  # noqa: E402


class TestExtraSpecCases(unittest.TestCase):
    maxDiff = None

    def _run(self, cases):
        for i, (md, expected) in enumerate(cases):
            with self.subTest(case=i, markdown=md):
                self.assertEqual(render(md), expected)

    def test_block_cases(self):
        self._run(peer1_spec_cases.BLOCK_CASES)

    def test_inline_cases(self):
        self._run(peer1_spec_cases.INLINE_CASES)

    def test_deep_nesting(self):
        self.assertEqual(render(">" * 3000 + "a\n").count("<blockquote>"), 3000)
        self.assertIn("<li>", render("- " * 1500 + "a\n"))
        self.assertTrue(render("*" * 3000 + "a" + "*" * 3000 + "\n").startswith("<p>"))


if __name__ == "__main__":
    unittest.main()
