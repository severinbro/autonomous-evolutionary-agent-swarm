"""Tests for benchmarks/t1_reuse_probe.py and `evaluate_benchmarks.py --setup --spec-only`."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent.parent / "benchmarks"
PROBE = BENCH_DIR / "t1_reuse_probe.py"
ARCHIVE = BENCH_DIR / "runs"
sys.path.insert(0, str(BENCH_DIR))

import evaluate_benchmarks as eb  # noqa: E402

MODELS = (
    "from dataclasses import dataclass\n"
    "from decimal import Decimal\n\n"
    "@dataclass\nclass Posting:\n    account: str\n    side: str\n    amount: Decimal\n    currency: str\n\n"
    "@dataclass\nclass Transaction:\n    tx_id: str\n    postings: list\n    idempotency_key: str\n"
)

# Both ledgers reject a reused key with different postings; only the full one also rejects a new tx_id.
LEDGER = (
    "class LedgerBook:\n"
    "    def __init__(self, rates=None, no_overdraft_accounts=None):\n"
    "        self._by_key = {}\n\n"
    "    def post_transaction(self, tx):\n"
    "        existing = self._by_key.get(tx.idempotency_key)\n"
    "        if existing is not None:\n"
    "            if existing.postings != tx.postings{extra}:\n"
    "                raise ValueError('conflicting reuse')\n"
    "            return existing\n"
    "        self._by_key[tx.idempotency_key] = tx\n"
    "        return tx\n"
)
FULL_LEDGER = LEDGER.replace("{extra}", " or existing.tx_id != tx.tx_id")
NARROW_LEDGER = LEDGER.replace("{extra}", "")


def make_workspace(root: Path, name: str, ledger: str | None) -> Path:
    ws = root / name
    (ws / "src").mkdir(parents=True)
    (ws / "src" / "__init__.py").write_text("", encoding="utf-8")
    (ws / "src" / "models.py").write_text(MODELS, encoding="utf-8")
    (ws / "src" / "ledger.py").write_text(ledger if ledger is not None else "import missing_module\n", encoding="utf-8")
    return ws


def run_probe(*workspaces: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(PROBE), *map(str, workspaces), "--json"], capture_output=True, text=True, check=False
    )


class ProbeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_full_rule_passes(self):
        ws = make_workspace(self.root, "full", FULL_LEDGER)
        proc = run_probe(ws)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)[str(ws)]["result"], "FULL_RULE")

    def test_narrow_rule_fails(self):
        ws = make_workspace(self.root, "narrow", NARROW_LEDGER)
        proc = run_probe(ws)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)[str(ws)]["result"], "NARROW_RULE")

    def test_import_failure_is_error_not_narrow(self):
        ws = make_workspace(self.root, "broken", None)
        proc = run_probe(ws)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)[str(ws)]["result"], "ERROR")

    def test_error_outranks_narrow_in_exit_code(self):
        proc = run_probe(make_workspace(self.root, "narrow", NARROW_LEDGER), make_workspace(self.root, "broken", None))
        self.assertEqual(proc.returncode, 2, proc.stderr)

    @unittest.skipUnless((ARCHIVE / "single_agent" / "task_1_ledger_cli" / "r1").is_dir(), "archived T1 runs absent")
    def test_archived_runs_match_code_inspection(self):
        expected = {"single_agent": "FULL_RULE", "single_agent_checked": "NARROW_RULE", "swarm_lite": "NARROW_RULE"}
        for arm, result in expected.items():
            runs = [ARCHIVE / arm / "task_1_ledger_cli" / f"r{n}" for n in (1, 2, 3)]
            with self.subTest(arm=arm):
                found = {r["result"] for r in json.loads(run_probe(*runs).stdout).values()}
                self.assertEqual(found, {result})


class SpecOnlySetupTest(unittest.TestCase):
    def test_spec_only_provisions_swarm_lite_without_acceptance_section(self):
        saved_runs, saved_tasks = eb.RUNS_DIR, dict(eb.TASKS)
        with tempfile.TemporaryDirectory() as tmp:
            try:
                eb.RUNS_DIR = Path(tmp)
                for key in [k for k in eb.TASKS if k != "task_1_ledger_cli"]:
                    eb.TASKS.pop(key)
                res = eb.setup_workspaces(runs=1, spec_only=True)
            finally:
                eb.RUNS_DIR = saved_runs
                eb.TASKS.clear()
                eb.TASKS.update(saved_tasks)
            self.assertEqual(set(res["created"]), {"swarm_lite"})
            ws = Path(tmp) / "swarm_lite" / "task_1_ledger_cli" / "r1"
            spec = (ws / "TASK_SPEC.md").read_text(encoding="utf-8")
            cfg = saved_tasks["task_1_ledger_cli"]
            self.assertEqual(spec, cfg["spec_md"])
            goal = json.loads((ws / ".swarm" / "goal_loop.json").read_text(encoding="utf-8"))
            focus = [item for task in goal["tasks"].values() for item in task.get("review_focus", [])]
            self.assertEqual(focus, cfg["review_focus"])


if __name__ == "__main__":
    unittest.main()
