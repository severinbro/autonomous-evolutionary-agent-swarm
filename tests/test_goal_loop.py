#!/usr/bin/env python3
"""Contract tests for goal_loop.py: the gate rules that the skills promise."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import goal_loop  # noqa: E402

OK_CMD = f'"{sys.executable}" -c "raise SystemExit(0)"'
FAIL_CMD = f'"{sys.executable}" -c "raise SystemExit(3)"'

SOLVER = "def solve(matrix):\n    return [[value * 2 for value in row] for row in matrix]\n"
SOLVER_WITH_STUB = SOLVER + "\n\ndef export(result):\n    pass\n"
REPORT = "def render(rows):\n    return '\\n'.join(str(row) for row in rows)\n"
MAIN_CALLS = "from src.solver import solve\n\n\ndef main():\n    return solve([[1.0]])\n"
MAIN_IMPORT_ONLY = "from src import solver\n\n\ndef main():\n    return 42\n"
MAIN_CALLS_BOTH = (
    "from src.report import render\nfrom src.solver import solve\n\n\n"
    "def main():\n    return render(solve([[1.0]]))\n"
)

SOLVER_TASK = {
    "title": "Solver",
    "epoch": 1,
    "target_files": ["src/solver.py"],
    "wiring_contract": {"must_be_called_by": ["src/main.py"], "exported_symbols": ["solve"]},
    "verification_commands": [OK_CMD],
    "review_focus": ["empty matrix"],
}
REPORT_TASK = {
    "title": "Report",
    "epoch": 1,
    "target_files": ["src/report.py"],
    "wiring_contract": {"must_be_called_by": ["src/main.py"], "exported_symbols": ["render"]},
    "verification_commands": [OK_CMD],
    "review_focus": ["empty rows"],
}


class TestHardCapScore(unittest.TestCase):
    def test_score_table(self):
        cases = [
            ({}, 9.2, True),
            ({"advisory_warns": ["w"]}, 8.5, True),
            ({"important_count": 1}, 7.0, False),
            ({"critical_count": 1}, 6.0, False),
            ({"blocking_fails": ["b"]}, 6.0, False),
            ({"spec_verdict": "FAIL"}, 6.0, False),
            ({"minor_count": 4}, 9.2, True),
        ]
        for overrides, score, passed in cases:
            with self.subTest(overrides=overrides):
                kwargs = {"blocking_fails": [], "advisory_warns": [], **overrides}
                res = goal_loop.compute_hard_cap_score(**kwargs)
                self.assertEqual(res["score"], score)
                self.assertEqual(res["passed_gate"], passed)


class GoalLoopProject(unittest.TestCase):
    """A throwaway git repository with a `.swarm/goal_loop.json` manifest."""

    def setUp(self):
        os.environ.pop("SWARM_GOAL_FILE", None)
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.cwd = str(self.root)
        (self.root / "src").mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def manifest(self, **tasks) -> None:
        self.write(".swarm/goal_loop.json", json.dumps({"overall_goal": "demo", "tasks": tasks}))

    def task(self, tid: str) -> dict:
        return goal_loop.load_goal_state(cwd=self.cwd)["tasks"][tid]

    def clean_solver(self) -> None:
        self.write("src/solver.py", SOLVER)
        self.write("src/main.py", MAIN_CALLS)
        self.manifest(T1=SOLVER_TASK)

    def broken_solver(self) -> None:
        self.write("src/solver.py", SOLVER_WITH_STUB)
        self.write("src/main.py", MAIN_IMPORT_ONLY)
        self.manifest(T1=SOLVER_TASK)

    def commit(self) -> str:
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qm", "snapshot"],
            cwd=self.root,
            check=True,
        )
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.root, check=True, capture_output=True, text=True
        ).stdout.strip()


class TestAudit(GoalLoopProject):
    def test_called_symbol_passes(self):
        self.clean_solver()
        res = goal_loop.audit_task("T1", cwd=self.cwd)
        self.assertTrue(res["passed"], res["blocking_fails"])

    def test_import_without_call_is_blocking(self):
        self.write("src/solver.py", SOLVER)
        self.write("src/main.py", MAIN_IMPORT_ONLY)
        self.manifest(T1=SOLVER_TASK)
        res = goal_loop.audit_task("T1", cwd=self.cwd)
        self.assertFalse(res["passed"])
        self.assertTrue(any(b.startswith("[WIRING/TARGET]") for b in res["blocking_fails"]))

    def test_missing_target_file_is_blocking(self):
        self.write("src/main.py", MAIN_CALLS)
        self.manifest(T1=SOLVER_TASK)
        self.assertFalse(goal_loop.audit_task("T1", cwd=self.cwd)["passed"])

    def test_pass_stub_is_blocking(self):
        self.write("src/solver.py", SOLVER_WITH_STUB)
        self.write("src/main.py", MAIN_CALLS)
        self.manifest(T1=SOLVER_TASK)
        res = goal_loop.audit_task("T1", cwd=self.cwd)
        self.assertTrue(any(b.startswith("[STUB/PLACEHOLDER") for b in res["blocking_fails"]))

    def test_documented_verification_commands_are_run(self):
        self.write("src/solver.py", SOLVER)
        self.write("src/main.py", MAIN_CALLS)
        self.manifest(T1={**SOLVER_TASK, "verification_commands": [OK_CMD, FAIL_CMD]})
        res = goal_loop.audit_task("T1", cwd=self.cwd)
        self.assertFalse(res["passed"])
        self.assertTrue(any(b.startswith("[VERIFICATION_CMD_FAILED]") for b in res["blocking_fails"]))

    def test_interface_stubs_are_exempt(self):
        self.write(
            "src/contracts/api.py",
            "from typing import Protocol\n\n\nclass Solver(Protocol):\n    def solve(self, matrix: list) -> list:\n        ...\n",
        )
        self.write(
            "src/base.py",
            "from abc import ABC, abstractmethod\n\n\nclass Exporter(ABC):\n    @abstractmethod\n"
            "    def export(self, rows: list) -> str:\n        pass\n",
        )
        res = goal_loop.audit_authenticity(
            root_dir=self.cwd, target_files=["src/contracts/api.py", "src/base.py"], check_orphan_modules=False
        )
        self.assertEqual(res["placeholder_findings"], [])


class TestRecordTask(GoalLoopProject):
    def test_reviewer_pass_cannot_clear_audit_failures(self):
        self.broken_solver()
        goal_loop.audit_task("T1", cwd=self.cwd)
        res = goal_loop.record_task("T1", spec_verdict="PASS", cwd=self.cwd)
        self.assertFalse(res["passed"])
        self.assertEqual(self.task("T1")["status"], "NEEDS_ITERATION")
        self.assertTrue(res["blocking_fails"])

    def test_record_without_prior_audit_runs_the_audit(self):
        self.broken_solver()
        res = goal_loop.record_task("T1", spec_verdict="PASS", cwd=self.cwd)
        self.assertFalse(res["passed"])

    def test_clean_audit_and_passing_review_completes(self):
        self.clean_solver()
        goal_loop.audit_task("T1", cwd=self.cwd)
        res = goal_loop.record_task("T1", spec_verdict="PASS", minor_count=2, cwd=self.cwd)
        self.assertTrue(res["passed"])
        self.assertEqual(self.task("T1")["status"], "VERIFIED_COMPLETE")

    def test_important_finding_blocks(self):
        self.clean_solver()
        res = goal_loop.record_task("T1", spec_verdict="PASS", important_count=1, cwd=self.cwd)
        self.assertFalse(res["passed"])
        self.assertEqual(res["hard_cap"], 7.0)

    def test_ruling_requires_a_type(self):
        self.clean_solver()
        res = goal_loop.record_task("T1", spec_verdict="PASS", ruling="accept as is", cwd=self.cwd)
        self.assertEqual(res["status"], "ERROR")
        self.assertEqual(self.task("T1")["status"], "PENDING")

    def test_override_rejected_when_audit_fails(self):
        self.broken_solver()
        res = goal_loop.record_task(
            "T1", spec_verdict="PASS", important_count=1, ruling="reviewer is wrong", ruling_type="OVERRIDE",
            cwd=self.cwd,
        )
        self.assertEqual(res["status"], "ERROR")
        self.assertNotEqual(self.task("T1")["status"], "COMPLETED_WITH_RULING")

    def test_override_settles_a_reviewer_dispute(self):
        self.clean_solver()
        res = goal_loop.record_task(
            "T1", spec_verdict="PASS", important_count=1,
            ruling="Retry jitter is intended — matches the spec — costs 50 ms if wrong", ruling_type="OVERRIDE",
            cwd=self.cwd,
        )
        self.assertTrue(res["passed"])
        task = self.task("T1")
        self.assertEqual(task["status"], "COMPLETED_WITH_RULING")
        self.assertEqual(task["important_count"], 1)
        ledger = (self.root / ".swarm" / "ledger.md").read_text(encoding="utf-8")
        self.assertIn("OVERRIDE", ledger)

    def test_escalation_blocks_the_task(self):
        self.clean_solver()
        res = goal_loop.record_task(
            "T1", spec_verdict="FAIL", ruling="Needs a product decision", ruling_type="ESCALATE_TO_USER", cwd=self.cwd
        )
        self.assertFalse(res["passed"])
        self.assertEqual(self.task("T1")["status"], "BLOCKED_BY_RULING")

    def test_split_requires_existing_successors(self):
        self.clean_solver()
        res = goal_loop.record_task(
            "T1", spec_verdict="FAIL", ruling="Too big", ruling_type="SPLIT_TASK", superseded_by=["T9"], cwd=self.cwd
        )
        self.assertEqual(res["status"], "ERROR")


class TestVerifyGoal(GoalLoopProject):
    def test_goal_reached_when_audited_and_reviewed(self):
        self.clean_solver()
        goal_loop.record_task("T1", spec_verdict="PASS", cwd=self.cwd)
        res = goal_loop.verify_goal_state(cwd=self.cwd)
        self.assertTrue(res["goal_reached"], res["errors"])

    def test_completed_task_is_reaudited(self):
        self.clean_solver()
        goal_loop.record_task("T1", spec_verdict="PASS", cwd=self.cwd)
        self.write("src/main.py", MAIN_IMPORT_ONLY)  # later change breaks the wiring
        res = goal_loop.verify_goal_state(cwd=self.cwd)
        self.assertFalse(res["goal_reached"])
        self.assertIn("T1", res["unfinished_tasks"])

    def test_unreviewed_task_does_not_complete_the_goal(self):
        self.clean_solver()
        res = goal_loop.verify_goal_state(cwd=self.cwd)
        self.assertFalse(res["goal_reached"])
        self.assertEqual(self.task("T1")["status"], "AWAITING_REVIEW")

    def test_blocked_task_keeps_the_goal_open(self):
        self.clean_solver()
        goal_loop.record_task("T1", spec_verdict="FAIL", ruling="Ask user", ruling_type="ESCALATE_TO_USER", cwd=self.cwd)
        res = goal_loop.verify_goal_state(cwd=self.cwd)
        self.assertFalse(res["goal_reached"])
        self.assertIn("T1", res["unfinished_tasks"])

    def test_superseded_task_waits_for_its_successors(self):
        self.write("src/solver.py", SOLVER)
        self.write("src/report.py", REPORT)
        self.write("src/main.py", MAIN_CALLS_BOTH)
        self.manifest(T1=SOLVER_TASK, T2=REPORT_TASK)
        goal_loop.record_task("T1", spec_verdict="PASS", cwd=self.cwd)
        split = goal_loop.record_task(
            "T1", spec_verdict="FAIL", ruling="Split rendering out", ruling_type="SPLIT_TASK", superseded_by=["T2"],
            cwd=self.cwd,
        )
        self.assertEqual(split["status"], "SUPERSEDED")
        self.assertFalse(goal_loop.verify_goal_state(cwd=self.cwd)["goal_reached"])
        goal_loop.record_task("T2", spec_verdict="PASS", cwd=self.cwd)
        res = goal_loop.verify_goal_state(cwd=self.cwd)
        self.assertTrue(res["goal_reached"], res["errors"])


class TestPreflightAndHandoffs(GoalLoopProject):
    def preflight(self) -> dict:
        with redirect_stdout(io.StringIO()):
            return goal_loop.run_preflight(cwd=self.cwd, as_json=True)

    def test_parallel_tasks_sharing_a_target_fail(self):
        self.manifest(T1=SOLVER_TASK, T2={**REPORT_TASK, "target_files": ["src/solver.py"]})
        res = self.preflight()
        self.assertFalse(res["passed"])
        self.assertEqual(res["overlap_count"], 1)

    def test_serialized_tasks_sharing_a_target_pass(self):
        self.manifest(T1=SOLVER_TASK, T2={**REPORT_TASK, "target_files": ["src/solver.py"], "depends_on": ["T1"]})
        res = self.preflight()
        self.assertTrue(res["passed"], res)

    def test_unknown_dependency_fails(self):
        self.manifest(T1={**SOLVER_TASK, "depends_on": ["T7"]})
        self.assertFalse(self.preflight()["passed"])

    def test_task_brief_is_written_to_briefs_dir(self):
        self.manifest(T1=SOLVER_TASK)
        with redirect_stdout(io.StringIO()):
            res = goal_loop.generate_task_brief("T1", cwd=self.cwd)
        path = Path(res["brief_path"])
        self.assertEqual(path, self.root / ".swarm" / "briefs" / "T1-brief.md")
        self.assertIn("Solver", path.read_text(encoding="utf-8"))

    def test_review_package_is_written_to_reviews_dir(self):
        self.clean_solver()
        base = self.commit()
        self.write("src/solver.py", SOLVER + "\n\ndef scale(matrix, k):\n    return [[v * k for v in row] for row in matrix]\n")
        self.commit()
        with redirect_stdout(io.StringIO()):
            res = goal_loop.generate_review_package("T1", base_sha_override=base, cwd=self.cwd)
        self.assertEqual(res["status"], "OK")
        path = Path(res["review_package_path"])
        self.assertEqual(path, self.root / ".swarm" / "reviews" / "T1-review.diff.md")
        self.assertIn("def scale", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
