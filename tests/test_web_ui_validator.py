#!/usr/bin/env python3
"""Tests for web_ui_validator.py failing closed when the headless browser cannot run."""

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import web_ui_validator  # noqa: E402

# Passes every static check (structure, single-file minimums, no placeholders, live handler),
# so the only possible FAIL is the missing browser.
PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
:root { color-scheme: light; } ::selection { background: #1d3557; color: #fff; }
body { font: 17px/1.5 Georgia, serif; margin: 0; } main { max-width: 60ch; margin: 0 auto; padding: 2rem; }
</style></head><body><main><h1>Rhine gauge readings</h1><p id="level">Kaub: 1.92 m</p>
<button id="refresh">Refresh</button></main><script>
document.getElementById("refresh").addEventListener("click", () => {
  document.getElementById("level").textContent = "Kaub: 1.94 m";
});
</script></body></html>
"""


class TestBrowserUnavailable(unittest.TestCase):
    def setUp(self):
        self._orig_inspect = web_ui_validator.run_playwright_multi_viewport_inspection
        web_ui_validator.run_playwright_multi_viewport_inspection = lambda **kwargs: {
            "ran": False,
            "reason": "simulated: playwright module not available",
            "findings": [],
            "viewports": [],
            "screenshots": [],
        }

    def tearDown(self):
        web_ui_validator.run_playwright_multi_viewport_inspection = self._orig_inspect

    def _validate(self, allow):
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "page.html"
            page.write_text(PAGE, encoding="utf-8")
            return web_ui_validator.validate_target(str(page), mode="read", allow=allow)

    def test_missing_browser_fails_closed(self):
        res = self._validate(set())
        self.assertEqual(res["status"], "FAIL")
        self.assertEqual(res["hard_cap_score"], 6.0)
        fail_ids = [f["id"] for f in res["findings"] if f["level"] == "FAIL"]
        self.assertEqual(fail_ids, ["browser-unavailable"])

    def test_explicit_allow_downgrades_to_warn(self):
        res = self._validate({"browser-unavailable"})
        self.assertEqual(res["status"], "PASS")
        warn_ids = [f["id"] for f in res["findings"] if f["level"] == "WARN"]
        self.assertIn("browser-unavailable", warn_ids)


if __name__ == "__main__":
    unittest.main()
