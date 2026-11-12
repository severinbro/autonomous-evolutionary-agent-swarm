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


class TestEvaluateGate(unittest.TestCase):
    def test_gate_verdicts(self):
        cases = [
            ({}, "PASS", True),
            ({"advisory_warns": ["w"]}, "PASS", True),
            ({"important_count": 1}, "FAIL", False),
            ({"critical_count": 1}, "FAIL", False),
            ({"blocking_fails": ["b"]}, "FAIL", False),
            ({"spec_verdict": "FAIL"}, "FAIL", False),
            ({"minor_count": 4}, "PASS", True),
        ]
        for overrides, verdict, passed in cases:
            with self.subTest(overrides=overrides):
                kwargs = {"blocking_fails": [], "advisory_warns": [], **overrides}
                res = goal_loop.evaluate_gate(**kwargs)
                self.assertEqual(res["verdict"], verdict)
                self.assertEqual(res["passed_gate"], passed)
                self.assertNotIn("score", res)


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

    def _parallel_report_ahead_of_integrator(self, integrator_status: str) -> dict:
        """`src/report.py` is built before T2, which will wire it into `src/main.py`."""
        self.write("src/report.py", REPORT)
        self.write("src/main.py", "def main():\n    return 42\n")
        self.manifest(
            T1={"title": "Report", "epoch": 1, "target_files": ["src/report.py"],
                "verification_commands": [OK_CMD], "review_focus": ["empty rows"]},
            T2={"title": "Integrate", "epoch": 1, "target_files": ["src/main.py"], "depends_on": ["T1"],
                "status": integrator_status, "verification_commands": [OK_CMD], "review_focus": ["wiring"]},
        )
        return goal_loop.audit_task("T1", cwd=self.cwd)

    def test_unwired_module_is_deferred_while_integrator_is_pending(self):
        res = self._parallel_report_ahead_of_integrator("PENDING")
        self.assertTrue(res["passed"], res["blocking_fails"])
        self.assertTrue(any("UNWIRED_MODULE deferred to T2" in w for w in res["advisory_warns"]), res["advisory_warns"])

    def test_unwired_module_blocks_once_integrator_is_done(self):
        res = self._parallel_report_ahead_of_integrator("VERIFIED_COMPLETE")
        self.assertFalse(res["passed"])
        self.assertTrue(any(b.startswith("[UNWIRED_MODULE in") for b in res["blocking_fails"]), res["blocking_fails"])

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

    def test_audit_on_existing_codebase_judges_only_changes_since_task_base(self):
        legacy_stub = "\n\ndef legacy_hook(rows):\n    pass\n"
        self.write("src/solver.py", SOLVER + legacy_stub)
        self.write("src/main.py", MAIN_CALLS)
        self.write("tests/test_legacy.py", "def test_x():\n    assert True\n")
        base = self.commit()
        self.write("src/solver.py", SOLVER + legacy_stub + "\n\ndef export(rows):\n    pass\n")
        self.manifest(T1=dict(SOLVER_TASK, base_sha=base))
        res = goal_loop.audit_task("T1", cwd=self.cwd)
        stubs = [b for b in res["blocking_fails"] if b.startswith("[STUB")]
        self.assertEqual(len(stubs), 1, stubs)
        self.assertIn("export()", stubs[0])

    def _stub_findings(self, source: str) -> list:
        self.write("src/render.py", source)
        res = goal_loop.audit_authenticity(root_dir=self.cwd, target_files=["src/render.py"], check_orphan_modules=False)
        return res["placeholder_findings"]

    def test_no_op_handler_in_dispatch_family_is_not_a_stub(self):
        source = (
            "class Renderer:\n"
            "    def render(self, node):\n        return getattr(self, 'r_' + node.type)(node)\n"
            "    def r_document(self, node):\n        pass\n"
            "    def r_paragraph(self, node):\n        return '<p>' + node.text + '</p>'\n"
            "    def r_heading(self, node):\n        return '<h1>' + node.text + '</h1>'\n"
        )
        self.assertEqual(self._stub_findings(source), [])

    def test_lone_pass_method_is_still_a_stub(self):
        source = "class Renderer:\n    def render(self, node):\n        pass\n    def r_x(self, node):\n        return 1\n"
        kinds = [f["kind"] for f in self._stub_findings(source)]
        self.assertEqual(kinds, ["PASS_ONLY_FUNCTION_STUB"])

    def test_family_of_mostly_stubs_is_still_reported(self):
        source = (
            "class Renderer:\n"
            "    def r_a(self, node):\n        pass\n"
            "    def r_b(self, node):\n        pass\n"
            "    def r_c(self, node):\n        return 1\n"
        )
        self.assertEqual(len(self._stub_findings(source)), 2)

    def test_constant_return_next_to_fake_comment_is_blocking(self):
        self.write(
            "src/solver.py",
            "def solve(matrix):\n"
            "    return [[1.25]]  # fake rate\n\n"
            "def quote():\n"
            "    # fake value for now\n"
            "    return 42\n",
        )
        self.write("src/main.py", MAIN_CALLS)
        self.manifest(T1=SOLVER_TASK)
        res = goal_loop.audit_task("T1", cwd=self.cwd)
        self.assertFalse(res["passed"])
        self.assertTrue(
            any("CONSTANT_RETURN_WITH_FAKE_COMMENT" in b for b in res["blocking_fails"]),
            res["blocking_fails"],
        )

    def test_mock_only_test_file_is_blocking(self):
        self.write("src/solver.py", SOLVER)
        self.write("src/main.py", MAIN_CALLS)
        self.write(
            "tests/test_solver.py",
            "from unittest.mock import MagicMock, patch\n\n"
            "def test_only_mocks():\n"
            "    m = MagicMock()\n"
            "    m.solve([[1]])\n"
            "    m.solve.assert_called_once_with([[1]])\n",
        )
        self.manifest(T1=SOLVER_TASK)
        res = goal_loop.audit_task("T1", cwd=self.cwd)
        self.assertFalse(res["passed"])
        self.assertTrue(
            any("MOCK_ONLY_TEST_FILE" in b for b in res["blocking_fails"]),
            res["blocking_fails"],
        )

    def test_real_test_file_passes_authenticity(self):
        self.write("src/solver.py", SOLVER)
        self.write("src/main.py", MAIN_CALLS)
        self.write(
            "tests/test_solver.py",
            "from src.solver import solve\n\n"
            "def test_solve_doubles_values():\n"
            "    assert solve([[1, 2]]) == [[2, 4]]\n",
        )
        self.manifest(T1=SOLVER_TASK)
        res = goal_loop.audit_task("T1", cwd=self.cwd)
        self.assertTrue(res["passed"], res["blocking_fails"])

    def test_vacuous_test_file_is_blocking(self):
        self.write("src/solver.py", SOLVER)
        self.write("src/main.py", MAIN_CALLS)
        self.write(
            "tests/test_vacuous.py",
            "def test_nothing():\n"
            "    assert True\n",
        )
        self.manifest(T1=SOLVER_TASK)
        res = goal_loop.audit_task("T1", cwd=self.cwd)
        self.assertFalse(res["passed"])
        self.assertTrue(
            any("VACUOUS_TEST_FILE" in b for b in res["blocking_fails"]),
            res["blocking_fails"],
        )


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

    def test_review_source_is_recorded_and_validated(self):
        self.clean_solver()
        goal_loop.audit_task("T1", cwd=self.cwd)
        res = goal_loop.record_task("T1", spec_verdict="PASS", review_source="self-check", cwd=self.cwd)
        self.assertTrue(res["passed"])
        self.assertEqual(self.task("T1")["history"][-1]["review_source"], "self-check")
        bad = goal_loop.record_task("T1", spec_verdict="PASS", review_source="vibes", cwd=self.cwd)
        self.assertEqual(bad["status"], "ERROR")

    def test_important_finding_blocks(self):
        self.clean_solver()
        res = goal_loop.record_task("T1", spec_verdict="PASS", important_count=1, cwd=self.cwd)
        self.assertFalse(res["passed"])
        self.assertEqual(res["verdict"], "FAIL")
        self.assertIn("important_count=1", res["blocking_reasons"])

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

    def test_review_package_includes_tests_changed_alongside_scoped_files(self):
        # Reviewers judge Review Focus coverage from the package; a scope limited to target
        # files used to hide the worker's regression tests.
        self.manifest(T1={**SOLVER_TASK, "target_files": ["src/solver.py"]})
        self.write("src/solver.py", SOLVER)
        base = self.commit()
        self.write("src/solver.py", SOLVER + "\n\ndef scale(matrix, k):\n    return [[v * k for v in row] for row in matrix]\n")
        self.write("tests/test_scale.py", "def test_scale():\n    assert True is not False\n")
        self.write("src/unrelated.py", "X = 1\n")
        self.commit()
        with redirect_stdout(io.StringIO()):
            res = goal_loop.generate_review_package("T1", base_sha_override=base, cwd=self.cwd)
        text = Path(res["review_package_path"]).read_text(encoding="utf-8")
        self.assertIn("def test_scale", text)
        self.assertIn("`tests/test_scale.py`", text)
        self.assertNotIn("X = 1", text)


DESIGN_HEAD = """# Demo design

## Technical Plan

The plan format looks like this:

```markdown
## Detailed Implementation Plan

### Task X: placeholder

*   **Files:** `nowhere.py` (Create)
```

## Detailed Implementation Plan

Some prose that the importer ignores.

### Goal

*   **Goal:** Scale matrices.
*   **Outcome:** `python3 -c "print('OK')"`
"""

TASK_SOLVE = """
### Task D-1: Solver

*   **Files:** `src/solver.py` (Create), `tests/test_solver.py` (Create)
*   **Depends on:** none
*   **Changes:** Add `solve(matrix)`.
    It doubles every value.
*   **Verification:** `python3 -m unittest tests.test_solver`
*   **Called by:** `src/main.py`
*   **Symbols:** `solve`
*   **Review focus:**
    1.  An empty matrix returns an empty list,
        not an error.
    2.  Negative values double too.
"""

TASK_REPORT = """
### Task D-2: Report

*   **Files:** `src/report.py` (Create), `src/old_report.py` (Delete)
*   **Depends on:** D-1
*   **Changes:** Render rows.
*   **Verification:** `python3 -m unittest tests.test_report`
"""

PLAN_TAIL = """
### Verification Plan

*   **Outcome:** this bullet is not part of any task.

## Risks

None.
"""


class TestImportDesign(GoalLoopProject):
    def design(self, *tasks: str, name: str = "docs/designs/demo.md") -> str:
        self.write(name, DESIGN_HEAD + "".join(tasks) + PLAN_TAIL)
        return name

    def goal_bytes(self):
        path = self.root / ".swarm" / "goal_loop.json"
        return path.read_bytes() if path.exists() else None

    def test_imports_tasks_fields_and_goal_and_ignores_fenced_example(self):
        res = goal_loop.import_design(self.design(TASK_SOLVE, TASK_REPORT), cwd=self.cwd)
        self.assertEqual(res["status"], "OK", res["errors"])
        self.assertEqual([t["id"] for t in res["tasks"]], ["D-1", "D-2"])
        solve = self.task("D-1")
        self.assertEqual(solve["target_files"], ["src/solver.py", "tests/test_solver.py"])
        self.assertEqual(solve["objective"], "Add `solve(matrix)`.\nIt doubles every value.")
        self.assertEqual(solve["verification_cmd"], "python3 -m unittest tests.test_solver")
        self.assertEqual(solve["wiring_files"], ["src/main.py"])
        self.assertEqual(solve["required_symbols"], ["solve"])
        self.assertEqual(
            solve["review_focus"], ["An empty matrix returns an empty list, not an error.", "Negative values double too."]
        )
        self.assertEqual(solve["spec_ref"], "docs/designs/demo.md § Task D-1")
        report = self.task("D-2")
        self.assertEqual(report["depends_on"], ["D-1"])
        self.assertEqual(report["target_files"], ["src/report.py"])
        self.assertIn("Delete: `src/old_report.py`", report["objective"])
        self.assertEqual(report["outcome_cmd"], "")
        state = goal_loop.load_goal_state(cwd=self.cwd)
        self.assertEqual(state["goal"], "Scale matrices.")
        self.assertEqual(state["outcome_cmd"], "python3 -c \"print('OK')\"")

    def test_all_errors_reported_together_and_nothing_written(self):
        broken = TASK_SOLVE.replace("*   **Verification:** `python3 -m unittest tests.test_solver`\n", "")
        cycle = TASK_REPORT.replace("**Depends on:** D-1", "**Depends on:** D-3, D-2")
        before = self.goal_bytes()
        res = goal_loop.import_design(self.design(broken, cycle), cwd=self.cwd)
        self.assertEqual(res["status"], "ERROR")
        text = "\n".join(res["errors"])
        self.assertIn("D-1: missing `Verification`", text)
        self.assertIn("unknown dependency D-3", text)
        self.assertIn("D-2: dependency cycle", text)
        self.assertEqual(self.goal_bytes(), before)

    def test_dry_run_writes_nothing(self):
        res = goal_loop.import_design(self.design(TASK_SOLVE), cwd=self.cwd, dry_run=True)
        self.assertEqual(res["status"], "OK")
        self.assertIsNone(self.goal_bytes())
        self.assertIn(
            {"task": "D-1", "field": "verification_cmd", "command": "python3 -m unittest tests.test_solver"},
            res["commands"],
        )

    def test_reimport_resets_changed_completed_task_and_keeps_unchanged_one(self):
        doc = self.design(TASK_SOLVE, TASK_REPORT)
        goal_loop.import_design(doc, cwd=self.cwd)
        state = goal_loop.load_goal_state(cwd=self.cwd)
        for tid in ("D-1", "D-2"):
            state["tasks"][tid].update(status="VERIFIED_COMPLETE", gate_verdict="PASS", iterations=2)
        goal_loop.save_goal_state(state, cwd=self.cwd)

        self.design(TASK_SOLVE, TASK_REPORT.replace("Render rows.", "Render rows as CSV."))
        res = goal_loop.import_design(doc, cwd=self.cwd)
        self.assertEqual({t["id"]: t["action"] for t in res["tasks"]}, {"D-1": "unchanged", "D-2": "reset"})
        self.assertEqual(self.task("D-1")["status"], "VERIFIED_COMPLETE")
        reset = self.task("D-2")
        self.assertEqual((reset["status"], reset["gate_verdict"], reset["iterations"]), ("PENDING", "PENDING", 0))

    def test_task_owned_by_another_design_is_an_error(self):
        goal_loop.import_design(self.design(TASK_SOLVE), cwd=self.cwd)
        res = goal_loop.import_design(self.design(TASK_SOLVE, name="docs/designs/other.md"), cwd=self.cwd)
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("belongs to docs/designs/demo.md", "\n".join(res["errors"]))

    def test_orphans_need_drop_missing(self):
        doc = self.design(TASK_SOLVE, TASK_REPORT)
        goal_loop.import_design(doc, cwd=self.cwd)
        self.design(TASK_SOLVE)
        res = goal_loop.import_design(doc, cwd=self.cwd)
        self.assertEqual(res["status"], "ERROR")
        self.assertEqual(res["orphans"], ["D-2"])
        res = goal_loop.import_design(doc, cwd=self.cwd, drop_missing=True)
        self.assertEqual(res["status"], "OK")
        self.assertNotIn("D-2", goal_loop.load_goal_state(cwd=self.cwd)["tasks"])
        self.assertIn("D-2", (self.root / ".swarm" / "ledger.md").read_text(encoding="utf-8"))

    def test_delete_only_task_and_unordered_overlap_are_errors(self):
        delete_only = TASK_REPORT.replace("`src/report.py` (Create), ", "")
        overlap = TASK_REPORT.replace("**Depends on:** D-1", "**Depends on:** none").replace(
            "`src/report.py` (Create)", "`src/solver.py` (Modify)"
        )
        errors = "\n".join(goal_loop.import_design(self.design(TASK_SOLVE, delete_only), cwd=self.cwd)["errors"])
        self.assertIn("at least one (Create) or (Modify) file", errors)
        errors = "\n".join(goal_loop.import_design(self.design(TASK_SOLVE, overlap), cwd=self.cwd)["errors"])
        self.assertIn("both change src/solver.py", errors)

    def test_unparseable_goal_file_is_refused_and_untouched(self):
        self.write(".swarm/goal_loop.json", "{not json")
        res = goal_loop.import_design(self.design(TASK_SOLVE), cwd=self.cwd)
        self.assertEqual(res["status"], "ERROR")
        self.assertEqual(self.goal_bytes(), b"{not json")

    def test_brief_and_review_package_print_spec_ref(self):
        goal_loop.import_design(self.design(TASK_SOLVE), cwd=self.cwd)
        brief = Path(goal_loop.generate_task_brief("D-1", cwd=self.cwd)["brief_path"]).read_text(encoding="utf-8")
        self.assertIn("docs/designs/demo.md § Task D-1", brief)
        self.assertIn("the design decides", brief)

    def test_add_task_keeps_objective_and_takes_depends_on(self):
        goal_loop.add_task("T1", "Title", "Original objective", validation_cmd=OK_CMD, cwd=self.cwd)
        goal_loop.add_task("T1", "Title", "", review_focus=["edge"], depends_on=["T0"], cwd=self.cwd)
        task = self.task("T1")
        self.assertEqual(task["objective"], "Original objective")
        self.assertEqual(task["depends_on"], ["T0"])

    def test_verify_blueprint_checks_imported_designs_only(self):
        self.write(".swarm/blueprint/tech_research_report.md", "Research notes. " * 30)
        self.write(".swarm/blueprint/brainstorm_blueprint.md", "Product notes. " * 30)
        self.assertTrue(goal_loop.verify_blueprint_artifacts(cwd=self.cwd)["passed"])
        doc = self.design(TASK_SOLVE)
        goal_loop.import_design(doc, cwd=self.cwd)
        self.assertTrue(goal_loop.verify_blueprint_artifacts(cwd=self.cwd)["passed"])
        (self.root / doc).unlink()
        res = goal_loop.verify_blueprint_artifacts(cwd=self.cwd)
        self.assertFalse(res["passed"])
        self.assertIn("is missing", "\n".join(res["errors"]))

    def test_open_questions_rejected_outside_fences_and_allowed_inside_fences(self):
        with_open_q = "## Open Questions\n\n* Should we use SQLite or Postgres?\n\n" + DESIGN_HEAD + TASK_SOLVE + PLAN_TAIL
        self.write("docs/designs/bad.md", with_open_q)
        before = self.goal_bytes()
        res = goal_loop.import_design("docs/designs/bad.md", cwd=self.cwd)
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("harness polling", "\n".join(res["errors"]))
        self.assertEqual(self.goal_bytes(), before)

        with_marker = DESIGN_HEAD + TASK_SOLVE.replace("It doubles every value.", "It doubles every value [?].") + PLAN_TAIL
        self.write("docs/designs/marker.md", with_marker)
        res = goal_loop.import_design("docs/designs/marker.md", cwd=self.cwd)
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("unresolved question marker", "\n".join(res["errors"]))

        fenced_and_inline = (
            "## Resolved Decisions\n\n"
            "<!-- ## Open Questions [?] -->\n"
            "* Rejected `## Open Questions` and `[?]` markers in favour of live harness polls.\n\n"
            "```markdown\n## Open Questions\n- Question for User: ignored inside fence [?]\n```\n\n"
            + DESIGN_HEAD
            + TASK_SOLVE
            + PLAN_TAIL
        )
        self.write("docs/designs/clean.md", fenced_and_inline)
        res = goal_loop.import_design("docs/designs/clean.md", cwd=self.cwd, dry_run=True)
        self.assertEqual(res["status"], "OK", res["errors"])

    def test_verify_blueprint_rejects_open_questions_in_blueprint_and_epoch_plans(self):
        self.write(".swarm/blueprint/tech_research_report.md", "Research notes. " * 30)
        self.write(".swarm/blueprint/brainstorm_blueprint.md", ("Product notes. " * 30) + "\n## Open Questions\n* TBD?\n")
        res = goal_loop.verify_blueprint_artifacts(cwd=self.cwd)
        self.assertFalse(res["passed"])
        self.assertIn("Zero-Plan-Questions", "\n".join(res["errors"]))

        self.write(".swarm/blueprint/brainstorm_blueprint.md", "Product notes. " * 30)
        self.write(".swarm/plans/epoch_2_plan.md", "# Plan\n- **Question for User:** Which port?\n")
        res = goal_loop.verify_blueprint_artifacts(cwd=self.cwd)
        self.assertFalse(res["passed"])
        self.assertIn("epoch_2_plan.md", "\n".join(res["errors"]))

    def test_task_brief_embeds_tdd_root_cause_and_yagni_discipline(self):
        goal_loop.import_design(self.design(TASK_SOLVE), cwd=self.cwd)
        brief = Path(goal_loop.generate_task_brief("D-1", cwd=self.cwd)["brief_path"]).read_text(encoding="utf-8")
        self.assertIn("Red-Green-Refactor TDD", brief)
        self.assertIn("4-Phase Root-Cause Debugging", brief)
        self.assertIn("Shortest-Path YAGNI", brief)
        self.assertIn("Never Park Questions in Files", brief)


class TestDesignDrift(GoalLoopProject):
    def _write_approved_design(self, extra_header: str = "*   **Status:** Approved\n\n") -> str:
        doc = "docs/designs/demo.md"
        self.write(doc, extra_header + DESIGN_HEAD + TASK_SOLVE + TASK_REPORT + PLAN_TAIL)
        return doc

    def _populate_matching_code(self) -> None:
        self.clean_solver()
        self.write("tests/test_solver.py", "import unittest\nfrom src.solver import solve\n")
        self.write("src/report.py", "def render(rows):\n    return '\\n'.join(rows)\n")

    def test_clean_when_code_wiring_deletes_and_goal_loop_match_design(self):
        doc = self._write_approved_design()
        self._populate_matching_code()
        goal_loop.import_design(doc, cwd=self.cwd)
        res = goal_loop.check_design_drift(cwd=self.cwd)
        self.assertEqual(res["status"], "CLEAN", res["drifts"])
        self.assertEqual(res["drift_count"], 0)

    def test_detects_missing_file_lingering_delete_missing_symbol_broken_wiring_and_stale_goal(self):
        doc = self._write_approved_design()
        self._populate_matching_code()
        goal_loop.import_design(doc, cwd=self.cwd)

        # 1. Lingering deleted file + missing target file
        self.write("src/old_report.py", "legacy = True\n")
        (self.root / "src" / "report.py").unlink()
        # 2. Missing exported symbol + broken caller wiring
        self.write("src/solver.py", "def renamed_solve(matrix):\n    return matrix\n")
        self.write("src/main.py", "print('no solver call')\n")
        # 3. Stale goal_loop.json + orphan task
        state = goal_loop.load_goal_state(cwd=self.cwd)
        state["tasks"]["D-1"]["title"] = "Outdated Title"
        state["tasks"]["D-ORPHAN"] = {"id": "D-ORPHAN", "title": "Old", "spec_ref": "docs/designs/demo.md § Task D-ORPHAN"}
        goal_loop.save_goal_state(state, cwd=self.cwd)

        res = goal_loop.check_design_drift(cwd=self.cwd)
        self.assertEqual(res["status"], "DRIFT_DETECTED")
        categories = {d["category"] for d in res["drifts"]}
        self.assertIn("MISSING_TARGET_FILE", categories)
        self.assertIn("LINGERING_DELETED_FILE", categories)
        self.assertIn("MISSING_EXPORTED_SYMBOL", categories)
        self.assertIn("BROKEN_CALLER_WIRING", categories)
        self.assertIn("GOAL_LOOP_OUT_OF_SYNC", categories)
        self.assertIn("ORPHAN_GOAL_LOOP_TASK", categories)

    def test_draft_designs_are_skipped_by_default_and_checked_when_explicit(self):
        doc = self._write_approved_design(extra_header="*   **Status:** Draft\n\n")
        auto = goal_loop.check_design_drift(cwd=self.cwd)
        self.assertEqual(auto["status"], "CLEAN")
        self.assertEqual(auto["skipped_drafts"], [doc])

        explicit = goal_loop.check_design_drift(doc_paths=[doc], cwd=self.cwd)
        self.assertEqual(explicit["status"], "DRIFT_DETECTED")

    def test_run_checks_flags_failing_verification_command(self):
        doc = self._write_approved_design()
        self._populate_matching_code()
        self.write("tests/test_report.py", "import unittest\nclass T(unittest.TestCase):\n    def test_fail(self): self.fail('boom')\n")
        res = goal_loop.check_design_drift(doc_paths=[doc], cwd=self.cwd, run_checks=True)
        self.assertEqual(res["status"], "DRIFT_DETECTED")
        self.assertIn("FAILING_VERIFICATION_CMD", {d["category"] for d in res["drifts"]})


class TestRepositoryDesign(unittest.TestCase):
    def test_skill_pack_v3_design_imports_cleanly(self):
        repo = SCRIPTS_DIR.parent
        doc = repo / "docs" / "designs" / "skill-pack-v3.md"
        if not doc.exists():
            self.skipTest("design document absent")
        with tempfile.TemporaryDirectory() as tmp:
            res = goal_loop.import_design(str(doc), cwd=tmp, dry_run=True)
        self.assertEqual(res["status"], "OK", res["errors"])
        self.assertEqual([t["id"] for t in res["tasks"]], [f"P{n}" for n in range(1, 12)])


if __name__ == "__main__":
    unittest.main()
