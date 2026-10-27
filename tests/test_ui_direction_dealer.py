#!/usr/bin/env python3
"""Contract tests for ui_direction_dealer.py: dealt directions are distinct, complete, and slop-free."""

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import ui_direction_dealer as dealer  # noqa: E402

# The default indigo/violet that web_ui_validator.py flags as `slop-ai-palette`.
AI_DEFAULT_HEXES = {"#6366f1", "#8b5cf6", "#a855f7"}
MODES = ("persuade", "operate", "read", "experience")


class TestDealing(unittest.TestCase):
    def test_deals_three_distinct_complete_directions(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                dealt = dealer.score_and_deal_directions(mode, "river gauge telemetry", deal_count=3)
                ids = [d["id"] for d in dealt]
                self.assertEqual(len(set(ids)), 3, ids)
                for direction in dealt:
                    for key in ("hero_blueprint", "section_blueprints", "typography_system", "color_system"):
                        self.assertTrue(direction.get(key), f"{direction['id']} has no {key}")

    def test_dealing_is_deterministic_for_a_seed(self):
        first = [d["id"] for d in dealer.score_and_deal_directions("persuade", "ai code studio", 3, seed=7)]
        second = [d["id"] for d in dealer.score_and_deal_directions("persuade", "ai code studio", 3, seed=7)]
        self.assertEqual(first, second)

    def test_forced_direction_is_returned_alone(self):
        target = dealer.DIRECTIONS_LIBRARY[0]["id"]
        dealt = dealer.score_and_deal_directions("persuade", "", 3, forced_direction_id=target)
        self.assertEqual([d["id"] for d in dealt], [target])

    def test_library_avoids_the_ai_default_palette(self):
        for direction in dealer.DIRECTIONS_LIBRARY:
            with self.subTest(direction=direction["id"]):
                hexes = {h.lower() for h in re.findall(r"#[0-9a-fA-F]{6}\b", json.dumps(direction["color_system"]))}
                self.assertFalse(hexes & AI_DEFAULT_HEXES)


class TestPersist(unittest.TestCase):
    def test_persist_writes_design_and_surface_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                [
                    sys.executable, str(SCRIPTS_DIR / "ui_direction_dealer.py"),
                    "--mode", "operate", "--query", "ops console", "--persist",
                    "--output-dir", tmp, "-p", "Ops Console", "--page", "dashboard",
                ],
                check=True,
                capture_output=True,
            )
            design = Path(tmp) / "DESIGN.md"
            self.assertTrue(design.is_file())
            self.assertIn("Ops Console", design.read_text(encoding="utf-8"))
            self.assertTrue((Path(tmp) / ".swarm" / "surfaces" / "dashboard.md").is_file())


if __name__ == "__main__":
    unittest.main()
