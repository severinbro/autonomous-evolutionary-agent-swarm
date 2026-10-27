#!/usr/bin/env python3
"""Tests that `immortal_watcher.py --record-review` applies the same categorical gate as goal_loop.py."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import immortal_watcher  # noqa: E402

FAIL_CMD = f'"{sys.executable}" -c "raise SystemExit(3)"'


class TestRecordReviewGate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self._orig = {
            "cwd": os.getcwd(),
            "env": os.environ.get("SWARM_TASKS_FILE"),
            "GLOBAL_TASKS_FILE": immortal_watcher.GLOBAL_TASKS_FILE,
            "LOG_FILE": immortal_watcher.LOG_FILE,
            "_record_instinct_safe": immortal_watcher._record_instinct_safe,
        }
        os.chdir(tmp)
        os.environ["SWARM_TASKS_FILE"] = str(tmp / "swarm_tasks.json")
        immortal_watcher.GLOBAL_TASKS_FILE = str(tmp / "global_tasks.json")
        immortal_watcher.LOG_FILE = str(tmp / "watcher.log")
        immortal_watcher._record_instinct_safe = lambda **kwargs: None  # keep the real instinct store untouched

    def tearDown(self):
        os.chdir(self._orig["cwd"])
        if self._orig["env"] is None:
            os.environ.pop("SWARM_TASKS_FILE", None)
        else:
            os.environ["SWARM_TASKS_FILE"] = self._orig["env"]
        immortal_watcher.GLOBAL_TASKS_FILE = self._orig["GLOBAL_TASKS_FILE"]
        immortal_watcher.LOG_FILE = self._orig["LOG_FILE"]
        immortal_watcher._record_instinct_safe = self._orig["_record_instinct_safe"]
        self._tmp.cleanup()

    def review(self, **kwargs):
        return immortal_watcher.record_review("worker-1", impl_score=9.0, goal_score=9.0, **kwargs)

    def test_clean_review_passes(self):
        self.assertEqual(self.review()["verdict"], "PASS")

    def test_important_finding_fails_regardless_of_scores(self):
        self.assertNotEqual(self.review(major_flaws=1)["verdict"], "PASS")

    def test_ruling_cannot_override_a_failed_outcome(self):
        res = self.review(outcome_cmd=FAIL_CMD, ruling="Accept anyway")
        self.assertNotIn(res["verdict"], ("PASS", "COMPLETED_WITH_RULING"))
        self.assertTrue(any("Ruling ignored" in r for r in res["calibration_reasons"]))

    def test_ruling_settles_a_reviewer_dispute(self):
        res = self.review(major_flaws=1, ruling="Reviewer overreach — matches spec — low cost if wrong")
        self.assertEqual(res["verdict"], "COMPLETED_WITH_RULING")


if __name__ == "__main__":
    unittest.main()
