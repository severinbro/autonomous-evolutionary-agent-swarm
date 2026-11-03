#!/usr/bin/env python3
"""Benchmark Suite Provisioner & Post-Hoc Defect/Cost/Time Evaluator (`benchmarks/evaluate_benchmarks.py`).

Provisions 11 build tasks, each in `runs/<arm>/<task>/r<N>/`. Tasks 1-6 run in the first three arms
below; a task's `arms` entry restricts it (Tasks 7-8: `single_agent_checked` and `swarm_lite`; the
oracle-graded Tasks 9-11 from `oracle_tasks.py`: `single_agent_checked` plus the three arms at the end):
  - `single_agent`:         `TASK_SPEC.md` only (no acceptance criteria, no swarm scripts/gates).
  - `single_agent_checked`: `TASK_SPEC.md` + the same Acceptance Criteria & Self-Checks section the
                            swarm worker receives (review focus, outcome command, UI validator
                            command), but no Discriminator Gate. Isolates the effect of the gate.
  - `swarm_lite`:           `TASK_SPEC.md` + the same Acceptance Criteria section, plus
                            `.swarm/goal_loop.json` configured for Lite Mode (1 Epoch: Pre-Flight +
                            Task Brief + Worker + Discriminator Gate + Validator). A task's
                            `swarm_tasks` plan (Task 7) provisions parallel sub-tasks with
                            `depends_on` instead of a single task.

  - `best_of_3`:            three independent `single_agent_checked` attempts in `r<N>_attempt_{1,2,3}/`;
                            `scripts/attempt_picker.py` installs the attempt that passes the most of
                            all attempts' tests into `r<N>/`.
  - `spec_tester`:          a worker in `r<N>/` plus a tester in `r<N>_tester/` that sees only the spec and
                            writes tests the worker must pass or dispute.
  - `swarm_peers`:          several peers share one goal in one workspace, coordinating only through
                            `.swarm/board.md` (no orchestrator, no reviewer).

`single_agent` vs `single_agent_checked` measures what the acceptance criteria and validator are
worth; `single_agent_checked` vs each later arm measures what that multi-agent design adds.

After execution, evaluates every run using:
  1. Held-out adversarial functional & edge-case tests (68 checks across 8 tasks: 11/6/8/6/8/6/11/12).
     Calls that could loop forever in agent code run in a child process with a timeout.
  2. AST Call-Site Wiring checks (`goal_loop.verify_wiring`).
  3. Code & Test Authenticity checks (`goal_loop.audit_authenticity`: stubs, constant returns next
     to fake comments, mock-only tests, vacuous tests, orphan modules).
  4. Real-browser 3-viewport UI validation (`web_ui_validator.validate_target`) on Task 4's
     `index.html`. Layout/runtime FAILs count as defects; `slop-*` style rules are reported
     separately as `ui_style_findings` and do not fail a run.
  5. Discriminator Gate activity for `swarm_lite` runs (review rounds, findings, and whether each
     verdict came from a reviewer subagent or a self-check, from `.swarm/goal_loop.json`).
  6. Subagent transcript telemetry (`transcript.jsonl` steps, tool calls, chars, and wall time).
     `transcript_tokens_est` is `chars / 4` of the transcript file: a proxy, not billed tokens
     (it includes JSON framing and excludes context re-read on every step).
"""

from __future__ import annotations

import argparse
import importlib
import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import goal_loop  # noqa: E402
import web_ui_validator  # noqa: E402

BENCH_DIR = REPO_ROOT / "benchmarks"
RUNS_DIR = BENCH_DIR / "runs"
BRAIN_DIR = Path(os.environ.get("ANTIGRAVITY_BRAIN_DIR", Path.home() / ".gemini" / "antigravity" / "brain"))

ARMS = ("single_agent", "single_agent_checked", "swarm_lite", "best_of_3", "spec_tester", "swarm_peers")
# Arms for tasks without their own `arms` entry (Tasks 1-6).
DEFAULT_ARMS = ("single_agent", "single_agent_checked", "swarm_lite")
# Arms whose TASK_SPEC.md carries the Acceptance Criteria & Self-Checks section.
ARMS_WITH_CRITERIA = ("single_agent_checked", "swarm_lite", "best_of_3", "spec_tester", "swarm_peers")

# Shared-goal peers coordinate only through this board (no orchestrator); same template as `/peer-swarm`.
PEER_BOARD = (REPO_ROOT / "skills" / "peer-swarm" / "board_template.md").read_text(encoding="utf-8")


TASKS: dict[str, dict[str, Any]] = {
    "task_1_ledger_cli": {
        "id": "T1",
        "title": "Multi-Currency Double-Entry Ledger & Reconciliation CLI",
        "spec_md": """# Build Task 1: Multi-Currency Double-Entry Ledger & Reconciliation CLI

Build a multi-module Python package under `src/` with unit tests under `tests/test_ledger.py`:

## Required Files & API Specification
1. `src/models.py`:
   - `Posting(account: str, side: str, amount: Decimal, currency: str = "USD")` where `side` is `"DEBIT"` or `"CREDIT"`.
   - `Transaction(tx_id: str, postings: list[Posting], idempotency_key: str, metadata: dict | None = None)`.
   - `ReconciliationReport(matched: list[str], missing_in_ledger: list[str], missing_in_bank: list[str], amount_mismatches: list[dict])`.
2. `src/fx_rates.py`:
   - `convert_to_usd(amount: Decimal, currency: str, rates: dict[str, Decimal]) -> Decimal`:
     - Converts `amount` from `currency` into `"USD"` using `rates` (where `rates[ccy]` is the USD value of 1 unit of `ccy`, e.g. `{"EUR": Decimal("1.10"), "GBP": Decimal("1.25")}`; `"USD"` is `1.00`).
     - Quantizes result to `Decimal("0.01")` using banker's rounding.
     - Raises `ValueError` for invalid inputs (unknown currency, non-positive amount, or non-positive rate).
3. `src/ledger.py`:
   - `LedgerBook(rates: dict[str, Decimal] | None = None, no_overdraft_accounts: set[str] | None = None)`:
     - `post_transaction(tx: Transaction) -> Transaction`:
       - Validates double-entry balance in USD (at least 2 postings; total USD debits must equal total USD credits, otherwise raises `ValueError`).
       - Enforces idempotency via `tx.idempotency_key` (safe replay for identical transactions; raises `ValueError` on conflicting reuse of the same key).
       - Enforces overdraft protection for accounts in `no_overdraft_accounts` (net balance is `debits - credits` in USD; raises `ValueError` if balance would drop below `0.00`).
     - `post_batch(transactions: list[Transaction]) -> list[Transaction]`:
       - Posts a list of transactions as an all-or-nothing atomic batch.
     - `get_balance(account: str) -> Decimal`: returns net USD balance (`debits - credits`, quantized to `0.01`).
     - `all_balances() -> dict[str, str]`: returns `{account: f"{balance:.2f}"}` sorted by account.
4. `src/reconciler.py`:
   - `reconcile_external(ledger: LedgerBook, bank_rows: list[dict]) -> ReconciliationReport`:
     - Compares committed ledger transactions against `bank_rows` (each `{"tx_id": str, "usd_total": str | float | Decimal}` where `usd_total` is the total USD debit of the transaction).
     - Populates `matched` (sorted `tx_id`s), `missing_in_ledger` (in `bank_rows` only), `missing_in_bank` (in `ledger` only), and `amount_mismatches` (`[{"tx_id": ..., "ledger_usd": str, "bank_usd": str}]`).
5. `src/cli.py`:
   - CLI entrypoint `python3 -m src.cli <subcommand> ...` supporting `balances <tx_jsonl_path>` and `reconcile <tx_jsonl_path> <bank_json_path>`.
6. `tests/test_ledger.py`:
   - Unit test suite runnable via `python3 -m unittest discover -s tests -v`.
""",
        "target_files": [
            "src/models.py",
            "src/fx_rates.py",
            "src/ledger.py",
            "src/reconciler.py",
            "src/cli.py",
        ],
        "wiring_files": ["src/ledger.py", "src/cli.py"],
        "required_symbols": ["convert_to_usd", "LedgerBook", "reconcile_external"],
        "verification_cmd": "python3 -m unittest discover -s tests -v",
        "outcome_cmd": (
            'python3 -c "from decimal import Decimal; from src.models import Posting, Transaction; '
            "from src.ledger import LedgerBook; from src.reconciler import reconcile_external; "
            "b = LedgerBook(rates={'EUR': Decimal('1.10')}, no_overdraft_accounts={'cash'}); "
            "t = Transaction('tx1', [Posting('cash', 'DEBIT', Decimal('100.00'), 'EUR'), Posting('rev', 'CREDIT', Decimal('110.00'), 'USD')], 'k1'); "
            "b.post_transaction(t); r = reconcile_external(b, [{'tx_id': 'tx1', 'usd_total': '110.00'}]); "
            "assert r.matched == ['tx1'] and b.get_balance('cash') == Decimal('110.00'); print('LEDGER_OK')\""
        ),
        "expect_output": "LEDGER_OK",
        "review_focus": [
            "Atomic rollback in post_batch when the 2nd or 3rd transaction triggers Overdraft or Unbalanced error (1st transaction must not remain committed)",
            "Idempotency key replay with identical postings returns original transaction without double-counting, while differing amount/account raises ValueError",
            "src/ledger.py must actively call convert_to_usd from src/fx_rates.py and src/cli.py must actively call reconcile_external from src/reconciler.py",
            "Tests in tests/test_ledger.py must assert on real LedgerBook and Reconciler outputs, not mocks",
        ],
    },
    "task_2_rate_limiter": {
        "id": "T2",
        "title": "Multi-Tenant Token-Bucket + Sliding-Window Rate Limiter & Dead-Letter Audit Router",
        "spec_md": """# Build Task 2: Multi-Tenant Token-Bucket + Sliding-Window Rate Limiter & Dead-Letter Audit Router

Build a multi-module Python rate limiter and request router under `src/` with unit tests under `tests/test_limiter.py`:

## Required Files & API Specification
1. `src/policies.py`:
   - `QuotaPolicy(tenant_id: str, capacity: int, refill_per_sec: float, window_seconds: int, max_window_requests: int)`
   - `Decision(allowed: bool, remaining_tokens: int, window_remaining: int, retry_after_ms: int, reason: str)`
2. `src/audit_log.py`:
   - `RejectionAuditLog`:
     - `record_rejection(tenant_id: str, route: str, timestamp_ms: int, reason: str, retry_after_ms: int) -> None`
     - `entries() -> list[dict]`
     - `summarize_by_tenant() -> dict[str, dict]`: returns `{tenant_id: {"rejected_count": int, "max_retry_after_ms": int, "reasons": list[str]}}`.
3. `src/limiter.py`:
   - `CompositeRateLimiter(policies: dict[str, QuotaPolicy])`:
     - `evaluate(tenant_id: str, cost: int = 1, timestamp_ms: int = 0) -> Decision`:
       - Enforces both a continuous token-bucket (`capacity`, `refill_per_sec`) and a sliding-window request log (`window_seconds`, `max_window_requests`) per `tenant_id`.
       - Returns `Decision(allowed, remaining_tokens, window_remaining, retry_after_ms, reason)` where `reason` is `"ALLOWED"`, `"TOKEN_BUCKET_EXHAUSTED"`, `"SLIDING_WINDOW_EXCEEDED"`, or `"BOTH_EXHAUSTED"`.
       - Raises `KeyError` or `ValueError` for unknown `tenant_id`.
4. `src/router.py`:
   - `RequestRouter(limiter: CompositeRateLimiter, audit_log: RejectionAuditLog)`:
     - `handle(tenant_id: str, route: str, cost: int, timestamp_ms: int) -> Decision`:
       - Evaluates the request against `limiter` and logs rejected requests to `audit_log`.
   - CLI entrypoint `python3 -m src.router --input <events_json_path>`.
5. `tests/test_limiter.py`:
   - Unit test suite runnable via `python3 -m unittest discover -s tests -v`.
""",
        "target_files": [
            "src/policies.py",
            "src/audit_log.py",
            "src/limiter.py",
            "src/router.py",
        ],
        "wiring_files": ["src/router.py"],
        "required_symbols": ["QuotaPolicy", "Decision", "RejectionAuditLog", "CompositeRateLimiter"],
        "verification_cmd": "python3 -m unittest discover -s tests -v",
        "outcome_cmd": (
            'python3 -c "from src.policies import QuotaPolicy; from src.audit_log import RejectionAuditLog; '
            "from src.limiter import CompositeRateLimiter; from src.router import RequestRouter; "
            "p = {'t1': QuotaPolicy('t1', capacity=5, refill_per_sec=1.0, window_seconds=10, max_window_requests=2)}; "
            "log = RejectionAuditLog(); r = RequestRouter(CompositeRateLimiter(p), log); "
            "d1 = r.handle('t1', '/a', 1, 1000); d2 = r.handle('t1', '/a', 1, 2000); d3 = r.handle('t1', '/a', 1, 3000); "
            "assert d1.allowed and d2.allowed and not d3.allowed and log.summarize_by_tenant()['t1']['rejected_count'] == 1; "
            "print('LIMITER_OK')\""
        ),
        "expect_output": "LIMITER_OK",
        "review_focus": [
            "When a request passes token bucket check but fails sliding window check, tokens must NOT be deducted",
            "Sliding window evicts timestamps at <= timestamp_ms - window_seconds * 1000",
            "RequestRouter.handle() must actively call RejectionAuditLog.record_rejection() on every rejected request",
            "Tests in tests/test_limiter.py must assert on real CompositeRateLimiter and RequestRouter state transitions, not mocks",
        ],
    },
    "task_3_dag_scheduler": {
        "id": "T3",
        "title": "Dependency DAG Workflow Runner with Retry Policy & Upstream Failure Propagation",
        "spec_md": """# Build Task 3: Dependency DAG Workflow Runner with Retry Policy & Upstream Failure Propagation

Build a multi-module Python DAG workflow scheduler under `src/` with unit tests under `tests/test_dag.py`:

## Required Files & API Specification
1. `src/graph.py`:
   - `TaskNode(node_id: str, deps: list[str], max_attempts: int = 1, base_delay_ms: int = 10, multiplier: float = 2.0, max_delay_ms: int = 1000)`
   - `WorkflowGraph`:
     - `add_node(node: TaskNode) -> None`
     - `find_cycle() -> list[str] | None`: returns `None` if acyclic, or a closed cycle path list `["A", ..., "A"]` if a cycle exists.
     - `topological_waves() -> list[list[str]]`: validates dependencies and acyclicity (raising `ValueError` on missing dependency or cycle) and returns sorted wave lists (`list[list[str]]`).
2. `src/retry.py`:
   - `RetryPolicy(max_attempts: int = 1, base_delay_ms: int = 10, multiplier: float = 2.0, max_delay_ms: int = 1000)`:
     - `delay_for_attempt(attempt_index: int) -> int`: returns exponential backoff delay in ms for retry `attempt_index >= 1`, capped at `max_delay_ms`.
   - `execute_with_retry(fn, policy: RetryPolicy) -> dict`:
     - Invokes `fn()` up to `policy.max_attempts` times and returns `{"succeeded": bool, "result": Any, "error": str | None, "attempts": int, "delays_ms": list[int]}`.
3. `src/executor.py`:
   - `WaveExecutor(graph: WorkflowGraph)`:
     - `run(callables: dict[str, Any]) -> dict`:
       - Executes nodes wave-by-wave using `RetryPolicy` and `execute_with_retry`.
       - Propagates upstream failures so dependent nodes are marked `"UPSTREAM_FAILED"` (`attempts=0`, `delays_ms=[]`) without invoking their callable, while independent branches continue executing.
       - Returns `{"waves": waves, "results": {node_id: {"status": str, "attempts": int, "delays_ms": list[int], "result": Any, "error": str | None}}}` where `status` is `"COMPLETED"`, `"FAILED"`, or `"UPSTREAM_FAILED"`.
4. `src/runner.py`:
   - CLI entrypoint `python3 -m src.runner --spec <spec_json_path>`.
5. `tests/test_dag.py`:
   - Unit test suite runnable via `python3 -m unittest discover -s tests -v`.
""",
        "target_files": [
            "src/graph.py",
            "src/retry.py",
            "src/executor.py",
            "src/runner.py",
        ],
        "wiring_files": ["src/executor.py", "src/runner.py"],
        "required_symbols": ["WorkflowGraph", "RetryPolicy", "execute_with_retry", "WaveExecutor"],
        "verification_cmd": "python3 -m unittest discover -s tests -v",
        "outcome_cmd": (
            'python3 -c "from src.graph import TaskNode, WorkflowGraph; from src.executor import WaveExecutor; '
            "g = WorkflowGraph(); g.add_node(TaskNode('A', [], max_attempts=2)); g.add_node(TaskNode('B', ['A'])); "
            "calls = []; "
            "fn_a = lambda: (calls.append(1), (_ for _ in ()).throw(RuntimeError('flaky')) if len(calls) == 1 else 10)[1]; "
            "res = WaveExecutor(g).run({'A': fn_a, 'B': lambda: 20}); "
            "assert res['results']['A']['status'] == 'COMPLETED' and res['results']['A']['attempts'] == 2; "
            "assert res['results']['B']['status'] == 'COMPLETED'; print('DAG_OK')\""
        ),
        "expect_output": "DAG_OK",
        "review_focus": [
            "Cycle detection on both multi-node cycles (A -> B -> C -> A) and self-loops (A -> A), raising ValueError in topological_waves()",
            "Transitive UPSTREAM_FAILED propagation: if A fails, B (depends on A) and C (depends on B) must both be UPSTREAM_FAILED with attempts=0, while independent node D still runs to COMPLETED",
            "src/executor.py must actively call execute_with_retry from src/retry.py",
            "Tests in tests/test_dag.py must execute real callables through WaveExecutor, not mock assertions",
        ],
    },
    "task_4_log_query_workbench": {
        "id": "T4",
        "title": "Structured Log Query Engine, Latency Spike Detector & Operational HTML Console",
        "spec_md": """# Build Task 4: Structured Log Query Engine, Latency Spike Detector & Operational HTML Console

Build a Python log analytics backend under `src/`, unit tests under `tests/test_log_engine.py`, and a single-file operational HTML/CSS/JS console at `index.html`:

## Required Files & API Specification
1. `src/log_engine.py`:
   - `LogRecord(timestamp_ms: int, service: str, level: str, status_code: int, latency_ms: float, message: str, trace_id: str = "")`
   - `compute_percentiles(values: list[float], percentiles: list[int] = [50, 95, 99]) -> dict[str, float]`:
     - Returns `{"p50": float, "p95": float, "p99": float}` using nearest-rank percentile calculation, or `0.0` when `values` is empty.
   - `LogStore`:
     - `load_jsonl(text_or_path: str) -> int`: parses JSONL lines (raising `ValueError` on malformed JSON or missing required fields).
     - `query(service: str | None = None, min_level: str | None = None, status_class: str | None = None, min_latency_ms: float | None = None, text_query: str | None = None) -> list[LogRecord]`:
       - Severity order: `DEBUG < INFO < WARN < ERROR < FATAL`.
       - `status_class`: `"2xx"`, `"4xx"`, `"5xx"`.
       - `text_query`: case-insensitive substring match against `message` or `trace_id`.
     - `summarize(records: list[LogRecord] | None = None) -> dict`:
       - Returns `{"count": int, "error_count": int, "error_rate": float, "percentiles": {"p50": float, "p95": float, "p99": float}}`.
2. `src/spike_detector.py`:
   - `detect_latency_spikes(records: list[LogRecord], baselines_ms: dict[str, float], min_samples: int = 3, threshold_ratio: float = 1.5) -> list[dict]`:
     - Groups `records` by `service` and identifies services with `>= min_samples` whose `p95` exceeds `baselines_ms[service] * threshold_ratio`.
     - Returns `[{"service": service, "sample_count": int, "p95_ms": float, "baseline_ms": float, "ratio": float}]` sorted by `ratio` descending.
3. `src/main.py`:
   - CLI entrypoint `python3 -m src.main --input <jsonl_path> [--service <svc>] [--min-level <lvl>] [--status-class <cls>]`.
4. `index.html`:
   - Single-file operational web console for inspecting log streams and latency spikes:
     - Interactive controls for filtering by service, severity level, and search text.
     - Displays `p50` / `p95` / `p99` KPI cards, latency spike alerts, and log records table, updating dynamically when filters are applied.
5. `tests/test_log_engine.py`:
   - Unit test suite runnable via `python3 -m unittest discover -s tests -v`.
""",
        "target_files": [
            "src/log_engine.py",
            "src/spike_detector.py",
            "src/main.py",
            "index.html",
        ],
        "wiring_files": ["src/spike_detector.py", "src/main.py"],
        "required_symbols": ["LogStore", "compute_percentiles", "detect_latency_spikes"],
        "verification_cmd": "python3 -m unittest discover -s tests -v",
        "outcome_cmd": (
            'python3 -c "from src.log_engine import LogRecord, LogStore; from src.spike_detector import detect_latency_spikes; '
            "s = LogStore(); "
            " recs = [LogRecord(1000+i, 'api', 'ERROR' if i==0 else 'INFO', 502 if i==0 else 200, float(v), f'msg {i}', f'tr-{i}') for i, v in enumerate([10, 20, 30, 250, 300])]; "
            "spikes = detect_latency_spikes(recs, {'api': 100.0}, min_samples=3); "
            "assert len(spikes) == 1 and spikes[0]['service'] == 'api'; print('LOG_ENGINE_OK')\""
        ),
        "expect_output": "LOG_ENGINE_OK",
        "review_focus": [
            "Nearest-rank percentile accuracy on empty list, single element, and skewed latency distributions",
            "LogStore.query filtering combinations (min_level severity ordering DEBUG < INFO < WARN < ERROR < FATAL + status_class 5xx + case-insensitive text_query)",
            "src/main.py must actively call detect_latency_spikes from src/spike_detector.py",
            "index.html must pass web_ui_validator.py --mode operate across 1440, 768, and 390px viewports with 0 FAIL findings",
        ],
    },
    "task_5_legacy_billing_refactor": {
        "id": "T5",
        "title": "Legacy Subscription Billing, Proration & Tax Engine Refactor",
        "seed_files": {
            "src/models.py": '''"""Legacy billing data models."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class LineItem:
    sku: str
    description: str
    amount_cents: int
    quantity: int = 1
    tax_exempt: bool = False


@dataclass
class Coupon:
    code: str
    kind: str  # "PERCENT" or "FIXED_CENTS"
    value: int | float
    exclusive: bool = False


@dataclass
class CustomerAccount:
    customer_id: str
    country: str
    vat_id: str | None = None
    credit_balance_cents: int = 0


@dataclass
class Invoice:
    invoice_id: str
    customer_id: str
    subtotal_cents: int
    discount_cents: int
    net_subtotal_cents: int
    tax_cents: int
    credit_applied_cents: int
    credit_generated_cents: int
    amount_due_cents: int
    reverse_charge: bool = False
    status: str = "FINALIZED"
    line_breakdown: list[dict] = field(default_factory=list)
''',
            "src/discounts.py": '''"""Legacy discount engine (contains known bugs to refactor)."""
from __future__ import annotations
from src.models import Coupon, LineItem


def apply_discounts(items: list[LineItem], coupons: list[Coupon] | None = None) -> tuple[list[dict], int]:
    """Apply coupons to line items and return (discounted_lines, total_discount_cents)."""
    coupons = coupons or []
    # BUG: mutates caller items in-place, ignores exclusive flag, applies fixed before percent
    total_discount = 0
    for c in coupons:
        if c.kind == "FIXED_CENTS":
            if items:
                items[0].amount_cents -= int(c.value)
                total_discount += int(c.value)
        elif c.kind == "PERCENT":
            for it in items:
                disc = int(round(it.amount_cents * it.quantity * (c.value / 100.0)))
                it.amount_cents -= disc
                total_discount += disc
    lines = []
    for it in items:
        gross = it.amount_cents * it.quantity
        lines.append({
            "sku": it.sku,
            "gross_cents": gross,
            "discount_cents": 0,
            "net_cents": gross,
            "tax_exempt": it.tax_exempt,
        })
    return lines, total_discount
''',
            "src/tax.py": '''"""Legacy regional tax engine (contains known bugs to refactor)."""
from __future__ import annotations
from decimal import Decimal

EU_COUNTRIES = {"DE", "FR", "NL", "ES", "IT", "AT", "BE", "IE", "PL", "SE"}
DEFAULT_TAX_RATES: dict[str, Decimal] = {
    "DE": Decimal("0.19"),
    "FR": Decimal("0.20"),
    "NL": Decimal("0.21"),
    "US": Decimal("0.00"),
}


def calculate_tax(
    discounted_lines: list[dict],
    buyer_country: str,
    seller_country: str = "DE",
    buyer_vat_id: str | None = None,
    tax_rates: dict[str, Decimal] | None = None,
) -> dict:
    rates = tax_rates if tax_rates is not None else DEFAULT_TAX_RATES
    # BUG: forgets buyer_country != seller_country for reverse charge and doesn't validate prefix
    if buyer_country in EU_COUNTRIES and buyer_vat_id:
        return {"tax_cents": 0, "reverse_charge": True, "rate": Decimal("0.00")}
    rate = float(rates.get(buyer_country, Decimal("0.00")))
    taxable = sum(line["net_cents"] for line in discounted_lines if not line.get("tax_exempt"))
    return {"tax_cents": int(round(taxable * rate)), "reverse_charge": False, "rate": Decimal(str(rate))}
''',
            "src/billing.py": '''"""Legacy subscription billing service (contains known bugs to refactor)."""
from __future__ import annotations
from decimal import Decimal
from src.discounts import apply_discounts
from src.models import Coupon, CustomerAccount, Invoice, LineItem
from src.tax import calculate_tax


class BillingEngine:
    def __init__(self, seller_country: str = "DE", tax_rates: dict[str, Decimal] | None = None) -> None:
        self.seller_country = seller_country
        self.tax_rates = tax_rates
        self._invoices: dict[str, Invoice] = {}
        self._idempotency: dict[str, str] = {}

    def create_invoice(
        self,
        invoice_id: str,
        customer: CustomerAccount,
        items: list[LineItem],
        coupons: list[Coupon] | None = None,
        idempotency_key: str | None = None,
        preview: bool = False,
    ) -> Invoice:
        lines, discount_cents = apply_discounts(items, coupons)
        subtotal_cents = sum(it.amount_cents * it.quantity for it in items)
        net_subtotal_cents = sum(l["net_cents"] for l in lines)
        tax_info = calculate_tax(
            lines,
            buyer_country=customer.country,
            seller_country=self.seller_country,
            buyer_vat_id=customer.vat_id,
            tax_rates=self.tax_rates,
        )
        tax_cents = tax_info["tax_cents"]
        gross_due = net_subtotal_cents + tax_cents
        credit_applied = min(customer.credit_balance_cents, max(0, gross_due))
        customer.credit_balance_cents -= credit_applied
        inv = Invoice(
            invoice_id=invoice_id,
            customer_id=customer.customer_id,
            subtotal_cents=subtotal_cents,
            discount_cents=discount_cents,
            net_subtotal_cents=net_subtotal_cents,
            tax_cents=tax_cents,
            credit_applied_cents=credit_applied,
            credit_generated_cents=0,
            amount_due_cents=gross_due - credit_applied,
            reverse_charge=tax_info["reverse_charge"],
            status="PREVIEW" if preview else "FINALIZED",
            line_breakdown=lines,
        )
        self._invoices[invoice_id] = inv
        return inv

    def void_invoice(self, invoice_id: str, customer: CustomerAccount) -> Invoice:
        inv = self._invoices[invoice_id]
        inv.status = "VOIDED"
        customer.credit_balance_cents += inv.credit_applied_cents
        return inv
''',
            "src/cli.py": '''"""Legacy CLI entrypoint."""
from __future__ import annotations
import sys


def main(argv: list[str] | None = None) -> int:
    return 0


if __name__ == "__main__":
    sys.exit(main())
''',
            "tests/test_billing.py": '''import unittest
from src.models import CustomerAccount, LineItem
from src.billing import BillingEngine


class TestBillingLegacy(unittest.TestCase):
    def test_basic_invoice(self) -> None:
        eng = BillingEngine()
        cust = CustomerAccount("c1", "US")
        inv = eng.create_invoice("inv1", cust, [LineItem("basic", "Basic", 1000, 1)])
        self.assertEqual(inv.amount_due_cents, 1000)


if __name__ == "__main__":
    unittest.main()
''',
        },
        "spec_md": """# Build Task 5: Legacy Subscription Billing, Proration & Tax Engine Refactor

This workspace contains a legacy multi-module billing codebase under `src/` with latent defects in discount allocation, tax rounding, reverse-charge VAT, credit carry-forward, preview side effects, and invoice voiding. Refactor the existing modules, extract `src/proration.py`, and expand `tests/test_billing.py`:

## Required Files & API Specification
1. `src/models.py`:
   - Preserve `LineItem(sku: str, description: str, amount_cents: int, quantity: int = 1, tax_exempt: bool = False)`, `Coupon(code: str, kind: str, value: int | float, exclusive: bool = False)`, `CustomerAccount(customer_id: str, country: str, vat_id: str | None = None, credit_balance_cents: int = 0)`, and `Invoice(...)`.
   - Validate that `LineItem.quantity >= 1`, `Coupon.kind` is `"PERCENT"` (`0 < value <= 100`) or `"FIXED_CENTS"` (`value > 0`), and `CustomerAccount.credit_balance_cents >= 0`.
2. `src/proration.py` (new module):
   - `prorate_subscription_change(old_plan_cents: int, new_plan_cents: int, cycle_start_day: int, cycle_end_day: int, change_day: int, old_quantity: int = 1, new_quantity: int | None = None, tax_exempt: bool = False) -> list[LineItem]`:
     - Validates `cycle_start_day <= change_day <= cycle_end_day`, `cycle_end_day > cycle_start_day`, and positive quantities/plan prices (raising `ValueError` otherwise).
     - Computes remaining cycle fraction `(cycle_end_day - change_day) / (cycle_end_day - cycle_start_day)`.
     - Returns two `LineItem` objects `[credit_item, charge_item]` with `quantity=1`:
       - `credit_item`: `sku="PRORATION_CREDIT"`, `amount_cents = -round_half_even(old_plan_cents * old_quantity * fraction)`
       - `charge_item`: `sku="PRORATION_CHARGE"`, `amount_cents = +round_half_even(new_plan_cents * effective_new_qty * fraction)`
       - Both rounded to integer cents via `Decimal` `ROUND_HALF_EVEN`.
3. `src/discounts.py`:
   - `apply_discounts(items: list[LineItem], coupons: list[Coupon] | None = None) -> tuple[list[dict], int]`:
     - Must NOT mutate caller `LineItem` objects in-place.
     - If any coupon has `exclusive=True` and `len(coupons) > 1`, or if duplicate coupon `code`s are provided, raise `ValueError`.
     - Discounts apply only to positive-gross line items (`gross_cents = amount_cents * quantity > 0`). Negative proration credit lines pass through unchanged (`discount_cents = 0`, `net_cents = gross_cents`).
     - Ordering:
       1. Apply all `"PERCENT"` coupons first (sorted by `code` ascending). Each percentage coupon reduces each positive line's current running net amount by `round_half_even(current_net * percent / 100)`.
       2. Apply `"FIXED_CENTS"` coupons next (sorted by `code` ascending). Sum fixed coupon values, cap total fixed discount at the sum of remaining positive line nets, and allocate proportionally across positive lines in proportion to their post-percent net amounts:
          - Each line gets `floor(fixed_total * line_net / total_positive_net)`, and the remaining integer cents are distributed 1 cent at a time to lines with the largest fractional remainder (ties broken by original line index `0, 1, ...`).
     - Returns `(lines, total_discount_cents)` where each entry in `lines` is `{"sku": str, "gross_cents": int, "discount_cents": int, "net_cents": int, "tax_exempt": bool}`.
4. `src/tax.py`:
   - `calculate_tax(discounted_lines: list[dict], buyer_country: str, seller_country: str = "DE", buyer_vat_id: str | None = None, tax_rates: dict[str, Decimal] | None = None) -> dict`:
     - EU cross-border B2B reverse charge applies if and only if `buyer_country in EU_COUNTRIES`, `seller_country in EU_COUNTRIES`, `buyer_country != seller_country`, and `buyer_vat_id` is a non-empty string starting with `buyer_country` followed by at least 2 alphanumeric characters. When active, `tax_cents = 0` and `reverse_charge = True`.
     - If the sum of `net_cents` across non-exempt (`tax_exempt=False`) lines is `<= 0`, `tax_cents = 0`.
     - Otherwise, compute tax on each non-exempt line (`round_half_even(line["net_cents"] * rate)`) and sum them (or if negative proration lines exist alongside positive taxable lines, compute `round_half_even(max(0, sum_taxable_net) * rate)` so credits reduce taxable base on the same invoice).
5. `src/billing.py`:
   - `BillingEngine.create_invoice(invoice_id, customer, items, coupons=None, idempotency_key=None, preview=False) -> Invoice`:
     - `subtotal_cents` is the sum of `amount_cents * quantity` across all `items`; `net_subtotal_cents = subtotal_cents - discount_cents`.
     - If `net_subtotal_cents < 0` (e.g. a net mid-cycle downgrade credit): `tax_cents = 0`, `credit_applied_cents = 0`, `credit_generated_cents = -net_subtotal_cents`, `amount_due_cents = 0`, and (when `preview=False`) `customer.credit_balance_cents` increases by `credit_generated_cents`.
     - If `net_subtotal_cents >= 0`: `gross_due = net_subtotal_cents + tax_cents`, `credit_applied_cents = min(customer.credit_balance_cents, gross_due)`, `credit_generated_cents = 0`, `amount_due_cents = gross_due - credit_applied_cents`, and (when `preview=False`) `customer.credit_balance_cents` decreases by `credit_applied_cents`.
     - When `preview=True`, no state may be mutated (`customer.credit_balance_cents`, `items`, stored invoices, and idempotency records must remain untouched).
     - Idempotency via `idempotency_key`: replaying the same key with identical `(customer_id, subtotal_cents, discount_cents)` returns the existing finalized `Invoice` without re-adjusting credits; conflicting reuse raises `ValueError`.
   - `BillingEngine.void_invoice(invoice_id, customer) -> Invoice`:
     - Raises `ValueError` if `invoice_id` is unknown, already `"VOIDED"`, or belongs to a different `customer_id`.
     - Restores `inv.credit_applied_cents` to `customer.credit_balance_cents` and deducts `inv.credit_generated_cents` (clamping or raising `ValueError` if customer already spent generated credit such that balance would drop below `0`).
6. `src/cli.py`:
   - CLI entrypoint `python3 -m src.cli <spec_json_path>` that wires `BillingEngine` and `prorate_subscription_change`.
""",
        "target_files": [
            "src/models.py",
            "src/proration.py",
            "src/discounts.py",
            "src/tax.py",
            "src/billing.py",
            "src/cli.py",
        ],
        "wiring_files": ["src/billing.py", "src/cli.py"],
        "required_symbols": ["prorate_subscription_change", "apply_discounts", "calculate_tax", "BillingEngine"],
        "verification_cmd": "python3 -m unittest discover -s tests -v",
        "outcome_cmd": (
            'python3 -c "from src.models import CustomerAccount, LineItem, Coupon; '
            "from src.proration import prorate_subscription_change; from src.billing import BillingEngine; "
            "eng = BillingEngine(); cust = CustomerAccount('c1', 'DE', vat_id='DE123456'); "
            "items = prorate_subscription_change(3000, 9000, 0, 30, 15); "
            "inv = eng.create_invoice('inv1', cust, items, coupons=[Coupon('P10', 'PERCENT', 10)]); "
            "assert inv.amount_due_cents > 0 and not inv.reverse_charge; print('BILLING_OK')\""
        ),
        "expect_output": "BILLING_OK",
        "review_focus": [
            "preview=True in BillingEngine.create_invoice and apply_discounts must never mutate LineItem.amount_cents or CustomerAccount.credit_balance_cents",
            "Coupon ordering (PERCENT before FIXED_CENTS), exclusive coupon conflict rejection, and largest-remainder proportional fixed-coupon allocation across taxable and tax_exempt lines",
            "EU reverse-charge VAT must only trigger when buyer_country != seller_country (domestic B2B with a valid local VAT ID is still taxed) and VAT ID starts with buyer_country",
            "Mid-cycle downgrade generating negative net_subtotal_cents must produce tax_cents=0, amount_due_cents=0, add credit_generated_cents to customer.credit_balance_cents, and void_invoice must reverse both credit_applied_cents and credit_generated_cents",
        ],
    },
    "task_6_mvcc_wal_store": {
        "id": "T6",
        "title": "Transactional MVCC Key-Value Store with Framed CRC32 WAL & Snapshot Compaction",
        "spec_md": """# Build Task 6: Transactional MVCC Key-Value Store with Framed CRC32 WAL & Snapshot Compaction

Build a multi-module transactional key-value storage engine implementing Snapshot Isolation (First-Committer-Wins), a CRC32-framed Write-Ahead Log with torn-write recovery, and snapshot-aware version compaction under `src/` with unit tests under `tests/test_mvcc.py`:

## Required Files & API Specification
1. `src/wal.py`:
   - `CorruptWALError(ValueError)`: exception raised on non-recoverable WAL corruption.
   - `WALRecord(lsn: int, tx_id: int, op: str, key: str | None = None, value: Any = None, commit_ts: int | None = None)` where `op` is `"BEGIN"`, `"PUT"`, `"DELETE"`, `"COMMIT"`, or `"ABORT"`.
   - `WriteAheadLog(path: str | Path)`:
     - Persists each record as a single line `<crc32_hex_8chars>\\t<compact_json>\\n`, where `crc32_hex_8chars` is lowercase 8-hex-digit `zlib.crc32` of the UTF-8 JSON payload bytes.
     - `append(record: WALRecord) -> int`: appends and flushes the framed record to disk.
     - `recover() -> list[WALRecord]`:
       - Reads the WAL file from disk.
       - **Torn-write vs corruption rule**: If the *final* line of the file is not terminated by `\\n` (indicating an incomplete append interrupted mid-write) and fails framing/CRC/JSON validation, `recover()` must ignore that trailing partial line and return all preceding valid records.
       - Any corruption (bad framing, CRC mismatch, or malformed JSON) on a newline-terminated line (`\\n`) or on any non-final line MUST raise `CorruptWALError`.
2. `src/mvcc.py`:
   - `WriteConflictError(ValueError)`: raised when a transaction violates First-Committer-Wins Snapshot Isolation.
   - `MVCCStore(wal_path: str | Path | None = None)`:
     - Maintains a monotonically increasing integer timestamp clock (`current_ts`, starting at `0` and incrementing by `1` on every `begin_tx()` and every successful `commit()`).
     - `begin_tx() -> int`: starts an active transaction with `start_ts = next_ts()`, appends `"BEGIN"` to WAL (if configured), and returns `tx_id`.
     - `get(tx_id: int, key: str) -> Any | None`:
       - Raises `ValueError` if `tx_id` is unknown, already committed, or aborted.
       - Returns `tx_id`'s own staged value if written in `tx_id` (returning `None` if `key` was deleted in `tx_id`, even when an older committed version exists).
       - Otherwise returns the latest committed version of `key` with `commit_ts <= tx.start_ts` (or `None` if that version is a delete tombstone or no version `<= tx.start_ts` exists).
     - `put(tx_id: int, key: str, value: Any) -> None` and `delete(tx_id: int, key: str) -> None`:
       - Stages a write or delete tombstone in `tx_id` and appends `"PUT"` / `"DELETE"` to WAL.
     - `scan(tx_id: int, prefix: str = "") -> dict[str, Any]`:
       - Returns `{key: value}` sorted by `key` for all visible non-deleted keys starting with `prefix` (merging the committed snapshot as of `tx.start_ts` with `tx_id`'s staged puts and deletes).
     - `commit(tx_id: int) -> int`:
       - **First-Committer-Wins check**: if any key in `tx_id`'s write set (`put` or `delete`) has a committed version with `commit_ts > tx.start_ts`, raises `WriteConflictError`, automatically aborts `tx_id` (discarding all its staged writes and appending `"ABORT"` to WAL), and leaves committed state unchanged.
       - Otherwise allocates `commit_ts = next_ts()`, appends `"COMMIT"` with `commit_ts` to WAL, publishes all staged puts/tombstones at `commit_ts`, and returns `commit_ts`.
     - `abort(tx_id: int) -> None`: discards staged writes, marks `tx_id` aborted, and appends `"ABORT"` to WAL.
     - `classmethod open(cls, wal_path: str | Path) -> MVCCStore`:
       - Reconstructs committed version chains by replaying `WriteAheadLog(wal_path).recover()`. Uncommitted or aborted transactions in the WAL must not appear in committed state, and `current_ts` / `tx_id` counters must advance past all recovered entries.
3. `src/compaction.py`:
   - `compact_store(store: MVCCStore) -> dict[str, int]`:
     - Computes `watermark_ts` as the minimum `start_ts` across all currently active transactions in `store`, or `store.current_ts` if no transactions are active.
     - For each key's committed version chain, identifies the latest version with `commit_ts <= watermark_ts` (the snapshot anchor):
       - Prunes all versions strictly older than that anchor (`commit_ts < anchor.commit_ts`).
       - If the anchor itself is a delete tombstone and no versions older than it remain, prunes the tombstone anchor as well.
       - Keeps all versions with `commit_ts > watermark_ts`.
     - Returns `{"versions_before": int, "versions_after": int, "pruned_count": int}`.
4. `src/cli.py`:
   - CLI entrypoint `python3 -m src.cli --wal <wal_path> --ops <ops_json_path>`.
5. `tests/test_mvcc.py`:
   - Unit test suite runnable via `python3 -m unittest discover -s tests -v`.
""",
        "target_files": [
            "src/wal.py",
            "src/mvcc.py",
            "src/compaction.py",
            "src/cli.py",
        ],
        "wiring_files": ["src/mvcc.py", "src/compaction.py", "src/cli.py"],
        "required_symbols": ["WriteAheadLog", "MVCCStore", "compact_store"],
        "verification_cmd": "python3 -m unittest discover -s tests -v",
        "outcome_cmd": (
            'python3 -c "import tempfile; from src.mvcc import MVCCStore, WriteConflictError; from src.compaction import compact_store; '
            "f = tempfile.NamedTemporaryFile(suffix='.wal', delete=False); f.close(); "
            "s = MVCCStore(f.name); t1 = s.begin_tx(); s.put(t1, 'k', 'v1'); s.commit(t1); "
            "t2 = s.begin_tx(); s.delete(t2, 'k'); assert s.get(t2, 'k') is None; s.commit(t2); "
            "s2 = MVCCStore.open(f.name); t3 = s2.begin_tx(); assert s2.get(t3, 'k') is None; "
            "compact_store(s2); print('MVCC_OK')\""
        ),
        "expect_output": "MVCC_OK",
        "review_focus": [
            "WriteAheadLog.recover() must ignore an incomplete trailing line without a newline (torn write at EOF) but raise CorruptWALError on any newline-terminated line with bad CRC/JSON or any mid-file corruption",
            "Staged delete(tx_id, key) must shadow earlier committed versions of key in both get(tx_id, key) and scan(tx_id, prefix)",
            "First-Committer-Wins conflict detection in commit() must abort the entire conflicting transaction atomically without leaking partial writes when one of multiple keys conflicts",
            "compact_store() must preserve the latest committed version <= oldest active transaction's start_ts while pruning older history and purging unreferenced tombstones when no older snapshot is active",
        ],
    },
    "task_7_parallel_fulfilment": {
        "id": "T7",
        "title": "Multi-Warehouse Order Fulfilment Service (Parallel Modules on a Shared Contract)",
        # Next-run tasks compare only the recommended default against the swarm.
        "arms": ("single_agent_checked", "swarm_lite"),
        "spec_md": """# Build Task 7: Multi-Warehouse Order Fulfilment Service

Build a Python order fulfilment service under `src/` with unit tests under `tests/` (one test file per module: `tests/test_catalog.py`, `tests/test_inventory.py`, `tests/test_shipping.py`, `tests/test_orders.py`). Modules 2-4 depend only on `src/contracts.py` and can be built independently; `src/orders.py` integrates them.

All money is integer cents, all weights are integer grams, and all times are integer milliseconds.

## Required Files & API Specification
1. `src/contracts.py` (shared types; no other module may redefine them):
   - `Clock(Protocol)` with `now_ms() -> int`, and `ManualClock(start_ms: int = 0)` with `now_ms()` and `advance(ms: int)`.
   - `@dataclass(frozen=True) Allocation(sku: str, warehouse_id: str, qty: int)`.
   - `@dataclass(frozen=True) Reservation(reservation_id: str, order_id: str, allocations: tuple[Allocation, ...], expires_at_ms: int)`.
   - `@dataclass(frozen=True) Product(sku: str, name: str, weight_g: int, price_tiers: tuple[tuple[int, int], ...], active: bool = True)` where `price_tiers` is `((min_qty, unit_price_cents), ...)`.
   - Exceptions: `UnknownSkuError(KeyError)`, `OutOfStockError(Exception)`, `ReservationExpiredError(Exception)`, `InvalidTransitionError(Exception)`.
2. `src/catalog.py`: `Catalog`:
   - `add_product(product: Product) -> None`: raises `ValueError` on a duplicate `sku`, on `price_tiers` without a `min_qty` of `1`, or on a non-positive `min_qty` or price.
   - `get(sku: str) -> Product`: raises `UnknownSkuError` for unknown or inactive SKUs.
   - `unit_price_cents(sku: str, qty: int) -> int`: the price of the tier with the largest `min_qty <= qty`.
   - `line_total_cents(sku: str, qty: int) -> int`: `unit_price_cents(sku, qty) * qty`.
3. `src/inventory.py`: `Inventory(clock: Clock)`:
   - `add_stock(warehouse_id: str, sku: str, qty: int) -> None` (`qty > 0`) and `on_hand(warehouse_id: str, sku: str) -> int`.
   - A reservation holds its allocations until it is released, committed, or expired. It is expired when `clock.now_ms() >= expires_at_ms`.
   - `available(sku: str) -> int`: on-hand quantity across all warehouses minus quantities held by unexpired reservations.
   - `reserve(order_id: str, lines: dict[str, int], ttl_ms: int) -> Reservation`: for each SKU in ascending SKU order, allocates from warehouses in ascending `warehouse_id` order, taking as much as each warehouse has available until the line is filled. All-or-nothing: if any line cannot be filled, raises `OutOfStockError` and holds nothing. `reservation_id` is `f"res-{order_id}"`, `expires_at_ms` is `now_ms() + ttl_ms`, and allocations are ordered by `(sku, warehouse_id)`.
   - `release(reservation_id: str) -> None`: drops the hold (no-op if it is already gone).
   - `commit(reservation_id: str) -> None`: deducts each allocation from its warehouse's on-hand stock and drops the hold. If the reservation has expired, drops the hold, leaves on-hand stock unchanged, and raises `ReservationExpiredError`.
   - `restock(allocations: Iterable[Allocation]) -> None`: adds each allocation's `qty` back to its own warehouse.
4. `src/shipping.py`:
   - `ZONE_BASE_FEE_CENTS = {"DOMESTIC": 499, "EU": 1299, "WORLD": 2499}` and `PER_KG_FEE_CENTS = {"DOMESTIC": 100, "EU": 250, "WORLD": 600}`.
   - `quote_shipping(allocations: Iterable[Allocation], weights_g: dict[str, int], zone: str) -> int`: one shipment per distinct `warehouse_id`; a shipment's weight is the sum of `weights_g[sku] * qty` over its allocations, and it costs `ZONE_BASE_FEE_CENTS[zone] + PER_KG_FEE_CENTS[zone] * ceil(weight_g / 1000)`. Returns the sum over shipments (`0` for no allocations). Raises `ValueError` for an unknown zone.
5. `src/orders.py`:
   - `@dataclass Order(order_id: str, zone: str, lines: dict[str, int], status: str, subtotal_cents: int, shipping_cents: int, total_cents: int, reservation: Reservation | None)`.
   - `OrderService(catalog: Catalog, inventory: Inventory, clock: Clock, reservation_ttl_ms: int = 900_000)`:
     - `create_order(order_id: str, zone: str, lines: dict[str, int]) -> Order`: before reserving anything, raises `ValueError` for a duplicate `order_id` or a non-positive quantity and `UnknownSkuError` for an unknown or inactive SKU. Then reserves stock, sets `subtotal_cents` to the sum of `catalog.line_total_cents`, `shipping_cents` to `quote_shipping` over the reservation's allocations, `total_cents` to their sum, and `status` to `"PENDING"`.
     - `get(order_id: str) -> Order`.
     - `pay(order_id: str) -> Order`: `PENDING` -> `PAID` by committing the reservation. If the reservation has expired, sets `status` to `"EXPIRED"` and raises `ReservationExpiredError`.
     - `cancel(order_id: str) -> Order`: `PENDING` -> `CANCELLED` (releases the reservation); `PAID` -> `CANCELLED` (restocks every allocation to its original warehouse).
     - Any other transition raises `InvalidTransitionError`.
6. `src/cli.py`: CLI entrypoint `python3 -m src.cli <scenario_json_path>` that builds the catalog and stock from the JSON file, applies its list of order operations in order, and prints the final orders as JSON.
""",
        "target_files": [
            "src/contracts.py",
            "src/catalog.py",
            "src/inventory.py",
            "src/shipping.py",
            "src/orders.py",
            "src/cli.py",
        ],
        "wiring_files": ["src/orders.py", "src/cli.py"],
        "required_symbols": ["Catalog", "Inventory", "quote_shipping", "OrderService"],
        "verification_cmd": "python3 -m unittest discover -s tests -v",
        "outcome_cmd": (
            'python3 -c "from src.contracts import ManualClock, Product; from src.catalog import Catalog; '
            "from src.inventory import Inventory; from src.orders import OrderService; "
            "c = ManualClock(0); cat = Catalog(); cat.add_product(Product('MUG', 'Mug', 600, ((1, 1000),))); "
            "inv = Inventory(c); inv.add_stock('WH-A', 'MUG', 1); inv.add_stock('WH-B', 'MUG', 1); "
            "s = OrderService(cat, inv, c); o = s.create_order('o1', 'DOMESTIC', {'MUG': 2}); "
            "assert o.shipping_cents == 2 * (499 + 100) and o.total_cents == 2000 + 1198; "
            "s.pay('o1'); print('FULFIL_OK')\""
        ),
        "expect_output": "FULFIL_OK",
        "review_focus": [
            "reserve() is all-or-nothing and allocates each SKU across warehouses in ascending warehouse_id order",
            "Expired reservations (now_ms >= expires_at_ms) stop counting against available() and cannot be committed; paying an expired order marks it EXPIRED",
            "Shipping charges one base fee per distinct warehouse in the reservation plus the per-kg fee on ceil(kg) of each shipment",
            "Cancelling a PAID order restocks every allocation to its original warehouse; any transition the spec does not list raises InvalidTransitionError",
            "src/orders.py must call Catalog, Inventory reserve/commit/release/restock, and quote_shipping",
        ],
        # Swarm plan: lock the contract, build catalog/inventory/shipping in parallel, then integrate.
        "swarm_tasks": [
            {
                "id": "T7.0",
                "title": "Shared contract types (src/contracts.py)",
                "target_files": ["src/contracts.py"],
                "required_symbols": ["ManualClock", "Allocation", "Reservation", "Product"],
                "verification_cmd": 'python3 -c "import src.contracts"',
                "review_focus": ["Types, fields, defaults, and exception base classes exactly as specified in TASK_SPEC.md section 1"],
                "depends_on": [],
            },
            {
                "id": "T7.A",
                "title": "Catalog with tier pricing (src/catalog.py)",
                "target_files": ["src/catalog.py", "tests/test_catalog.py"],
                "required_symbols": ["Catalog"],
                "verification_cmd": 'python3 -m unittest discover -s tests -p "test_catalog.py" -v',
                "review_focus": [
                    "unit_price_cents uses the tier with the largest min_qty <= qty",
                    "get() raises UnknownSkuError for unknown and inactive SKUs",
                ],
                "depends_on": ["T7.0"],
            },
            {
                "id": "T7.B",
                "title": "Multi-warehouse inventory with expiring reservations (src/inventory.py)",
                "target_files": ["src/inventory.py", "tests/test_inventory.py"],
                "required_symbols": ["Inventory"],
                "verification_cmd": 'python3 -m unittest discover -s tests -p "test_inventory.py" -v',
                "review_focus": [
                    "reserve() is all-or-nothing and allocates each SKU across warehouses in ascending warehouse_id order",
                    "Expired reservations (now_ms >= expires_at_ms) stop counting against available() and cannot be committed",
                    "restock() returns each allocation to its own warehouse",
                ],
                "depends_on": ["T7.0"],
            },
            {
                "id": "T7.C",
                "title": "Per-warehouse shipping quotes (src/shipping.py)",
                "target_files": ["src/shipping.py", "tests/test_shipping.py"],
                "required_symbols": ["quote_shipping"],
                "verification_cmd": 'python3 -m unittest discover -s tests -p "test_shipping.py" -v',
                "review_focus": [
                    "One base fee per distinct warehouse plus the per-kg fee on ceil(kg) of each shipment",
                ],
                "depends_on": ["T7.0"],
            },
            {
                "id": "T7.D",
                "title": "Order service and CLI integration (src/orders.py, src/cli.py)",
                "target_files": ["src/orders.py", "src/cli.py", "tests/test_orders.py"],
                "wiring_files": ["src/orders.py", "src/cli.py"],
                "required_symbols": ["Catalog", "Inventory", "quote_shipping", "OrderService"],
                "verification_cmd": "python3 -m unittest discover -s tests -v",
                "review_focus": [
                    "create_order validates every line before reserving anything",
                    "Paying an expired order marks it EXPIRED and frees its stock",
                    "Cancelling a PAID order restocks every allocation to its original warehouse; any transition the spec does not list raises InvalidTransitionError",
                ],
                "depends_on": ["T7.A", "T7.B", "T7.C"],
            },
        ],
    },
    "task_8_expense_ledger_traps": {
        "id": "T8",
        "title": "Shared-Expense Ledger & Debt Settlement (Invariants Stated, Edge Cases Not)",
        "arms": ("single_agent_checked", "swarm_lite"),
        "spec_md": """# Build Task 8: Shared-Expense Ledger & Debt Settlement

Build a Python shared-expense ledger under `src/` with unit tests under `tests/test_expenses.py`.

## Invariants (apply to every function below)
1. **Exact money:** amounts are integer cents internally; binary floating point is never used for money.
2. **Conservation:** each expense's shares sum exactly to its amount, and the sum of all member balances is always exactly `0`.
3. **Determinism:** identical inputs give identical outputs, regardless of the order in which members, weight entries, or balance entries are supplied.
4. **Validation without side effects:** invalid input, including input under which another invariant cannot hold, raises `ValueError` and leaves all state unchanged.

## Required Files & API Specification
1. `src/money.py`:
   - `parse_amount(text: str) -> int`: parses an amount string made of an optional leading `-`, one or more digits, and optionally `.` followed by one or two digits (`"12"`, `"12.5"`, `"-3.10"`) into integer cents. Any other string raises `ValueError`.
   - `format_amount(cents: int) -> str`: formats cents with two decimals (`1250` -> `"12.50"`, `-310` -> `"-3.10"`).
2. `src/group.py`: `Group()`:
   - `add_member(name: str) -> None`: raises `ValueError` for an empty or duplicate name.
   - `add_expense(expense_id: str, payer: str, amount: str, weights: dict[str, int]) -> dict[str, int]`: `payer` paid `amount` (a negative amount is a refund). The amount is split among the members in `weights` in proportion to their non-negative integer weights; a member with weight `0` owes nothing. Returns `{member: share_cents}` for the members in `weights`. `expense_id` must be unique, and `payer` and every member in `weights` must already be group members.
   - `balances() -> dict[str, int]`: for every member, total paid minus total owed (positive means the member is owed money).
   - `expenses() -> list[str]`: expense IDs in the order they were added.
3. `src/settle.py`:
   - `settle(balances: dict[str, int]) -> list[tuple[str, str, int]]`: returns transfers `(debtor, creditor, cents)` that bring every balance to `0`. Repeatedly pair the member with the largest debt with the member with the largest credit (ties broken by name, ascending) and transfer the smaller of the two absolute amounts.
4. `src/cli.py`: CLI entrypoint `python3 -m src.cli <expenses_json_path>` that prints balances (formatted with `format_amount`) and the settlement as JSON.
5. `tests/test_expenses.py`: unit test suite runnable via `python3 -m unittest discover -s tests -v`.
""",
        "target_files": ["src/money.py", "src/group.py", "src/settle.py", "src/cli.py"],
        "wiring_files": ["src/group.py", "src/cli.py"],
        "required_symbols": ["parse_amount", "Group", "settle"],
        "verification_cmd": "python3 -m unittest discover -s tests -v",
        "outcome_cmd": (
            'python3 -c "from src.group import Group; from src.settle import settle; g = Group(); '
            "g.add_member('ann'); g.add_member('bob'); "
            "g.add_expense('e1', 'ann', '10.00', {'ann': 1, 'bob': 1}); "
            "assert [tuple(t) for t in settle(g.balances())] == [('bob', 'ann', 500)]; print('EXPENSES_OK')\""
        ),
        "expect_output": "EXPENSES_OK",
        # Deliberately restates the spec's invariants only: the held-out checks test cases that follow
        # from them, and listing those cases here would turn the task back into spec-following.
        "review_focus": [
            "Exact money: no binary floating point anywhere amounts are parsed, split, formatted, or settled",
            "Conservation: every expense's shares sum exactly to its amount and member balances always sum to 0",
            "Determinism: outputs do not depend on the order of members, weight entries, or balance entries",
            "Invalid input, including input under which another invariant cannot hold, raises ValueError and leaves all state unchanged",
            "src/cli.py must call Group and settle",
        ],
    },
}


def acceptance_section(cfg: dict[str, Any]) -> str:
    """Acceptance Criteria & Self-Checks shared verbatim by every arm in `ARMS_WITH_CRITERIA`."""
    lines = [
        "",
        "## Acceptance Criteria & Self-Checks",
        "Before reporting the task done, make sure each of these holds and is covered by an automated test:",
    ]
    lines += [f"{i}. {item}" for i, item in enumerate(cfg["review_focus"], start=1)]
    lines += [
        "",
        f"- Verification command (must exit 0): `{cfg['verification_cmd']}`",
        f"- Outcome command (stdout must contain `{cfg['expect_output']}`): `{cfg['outcome_cmd']}`",
    ]
    if "index.html" in cfg["target_files"]:
        lines.append(
            f"- UI check (must report 0 FAIL findings): "
            f"`python3 {SCRIPTS_DIR / 'web_ui_validator.py'} index.html --mode operate`"
        )
    return "\n".join(lines) + "\n"


def run_dir(arm: str, task_key: str, run_id: str) -> Path:
    return RUNS_DIR / arm / task_key / run_id


def is_completed(ws: Path, task_key: str) -> bool:
    """A run counts once all of its task's target files exist; unrun or partially seeded workspaces are pending."""
    return all((ws / f).is_file() for f in TASKS[task_key]["target_files"])


def discover_runs(arm: str, task_key: str) -> list[tuple[str, Path]]:
    """Return `[(run_id, workspace)]` for every provisioned run of `arm`/`task_key`."""
    task_dir = RUNS_DIR / arm / task_key
    if not task_dir.is_dir():
        return []
    return [
        (p.name, p)
        for p in sorted(task_dir.iterdir(), key=lambda p: int(p.name[1:]) if p.name[1:].isdigit() else 0)
        if p.is_dir() and p.name.startswith("r") and p.name[1:].isdigit()
    ]


def migrate_legacy_layout() -> list[str]:
    """Move pre-repeat runs from `runs/<arm>/<task>/` into `runs/<arm>/<task>/r1/`."""
    moved: list[str] = []
    for arm in ARMS:
        for task_key in TASKS:
            task_dir = RUNS_DIR / arm / task_key
            if not (task_dir / "TASK_SPEC.md").is_file():
                continue
            target = task_dir / "r1"
            if target.exists():
                raise SystemExit(f"Cannot migrate {task_dir}: both a legacy run and {target} exist.")
            staging = RUNS_DIR / arm / f".{task_key}.migrating"
            task_dir.rename(staging)
            task_dir.mkdir()
            staging.rename(target)
            moved.append(str(target))
    return moved


def setup_workspaces(clean: bool = False, runs: int = 1, spec_only: bool = False) -> dict[str, Any]:
    """Create `benchmarks/runs/<arm>/<task>/r<N>` for every arm, task, and run index.

    Workspaces that already contain `TASK_SPEC.md` are left untouched, so re-running `--setup`
    never overwrites a completed run's code or `.swarm/` state (agents may delete `.git`, so its
    absence does not mean a workspace is unused).

    `spec_only` provisions `swarm_lite` alone, with the plain spec in `TASK_SPEC.md`: the acceptance
    criteria then reach the worker only as `review_focus` items in `.swarm/goal_loop.json`, where an
    orchestrator would have put them.
    """
    if clean and RUNS_DIR.exists():
        shutil.rmtree(RUNS_DIR)
    migrated = migrate_legacy_layout()

    arms = ("swarm_lite",) if spec_only else ARMS
    created: dict[str, list[str]] = {arm: [] for arm in arms}
    for arm in arms:
        for task_key, cfg in TASKS.items():
            if arm not in cfg.get("arms", DEFAULT_ARMS):
                continue
            for n in range(1, runs + 1):
                ws = run_dir(arm, task_key, f"r{n}")
                if (ws / "TASK_SPEC.md").exists():
                    continue
                _provision_workspace(arm, cfg, ws, spec_only=spec_only)
                created[arm].append(str(ws))
    return {"migrated": migrated, "created": created}


def sibling_dir(ws: Path, suffix: str) -> Path:
    """Helper workspaces (best-of-3 attempts, the spec tester's folder) sit next to `r<N>`, never inside it,
    so evaluation and authenticity scans of the run only ever see the final code."""
    return ws.parent / f"{ws.name}_{suffix}"


def _provision_workspace(arm: str, cfg: dict[str, Any], ws: Path, spec_only: bool = False) -> None:
    if arm == "best_of_3":
        # Three independent attempts; `scripts/attempt_picker.py --install-into r<N>` fills the run itself.
        for i in (1, 2, 3):
            _provision_workspace("single_agent_checked", cfg, sibling_dir(ws, f"attempt_{i}"))
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "TASK_SPEC.md").write_text(cfg["spec_md"] + acceptance_section(cfg), encoding="utf-8")
        return
    if arm == "spec_tester":
        # The tester sees only the spec, in its own folder, and writes tests the worker must face.
        tester = sibling_dir(ws, "tester")
        (tester / "tests").mkdir(parents=True, exist_ok=True)
        (tester / "TASK_SPEC.md").write_text(cfg["spec_md"] + acceptance_section(cfg), encoding="utf-8")
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "src").mkdir(exist_ok=True)
    (ws / "tests").mkdir(exist_ok=True)
    (ws / "src" / "__init__.py").write_text("", encoding="utf-8")
    for rel_path, content in cfg.get("seed_files", {}).items():
        dest = ws / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    spec = cfg["spec_md"]
    if arm in ARMS_WITH_CRITERIA and not spec_only:
        spec += acceptance_section(cfg)
    (ws / "TASK_SPEC.md").write_text(spec, encoding="utf-8")
    if arm == "swarm_peers":
        (ws / ".swarm").mkdir(exist_ok=True)
        (ws / ".swarm" / "board.md").write_text(PEER_BOARD, encoding="utf-8")

    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    subprocess.run(["git", "add", "-A"], cwd=ws, check=True)
    subprocess.run(
        ["git", "-c", "user.email=bench@swarm.local", "-c", "user.name=bench", "commit", "-qm", "init"],
        cwd=ws,
        check=True,
    )

    if arm == "swarm_lite":
        base_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ws, check=True, capture_output=True, text=True
        ).stdout.strip()
        goal_loop.init_manifest(
            goal=cfg["title"],
            outcome_cmd=cfg["outcome_cmd"],
            expect_output=cfg["expect_output"],
            entrypoints=cfg["wiring_files"],
            seed_default_tasks=False,
            cwd=str(ws),
        )
        # A task's `swarm_tasks` plan (parallel sub-tasks with `depends_on`) replaces the single task.
        plan = cfg.get("swarm_tasks") or [
            {
                "id": cfg["id"],
                "title": cfg["title"],
                "target_files": cfg["target_files"],
                "wiring_files": cfg["wiring_files"],
                "required_symbols": cfg["required_symbols"],
                "verification_cmd": cfg["verification_cmd"],
                "review_focus": cfg["review_focus"],
                "depends_on": [],
            }
        ]
        for sub in plan:
            goal_loop.add_task(
                task_id=sub["id"],
                title=sub["title"],
                objective=f"Implement {sub['title']} per TASK_SPEC.md",
                target_files=sub["target_files"],
                wiring_files=sub.get("wiring_files", []),
                required_symbols=sub["required_symbols"],
                validation_cmd=sub["verification_cmd"],
                outcome_cmd=cfg["outcome_cmd"] if sub is plan[-1] else "",
                expect_output=cfg["expect_output"] if sub is plan[-1] else "",
                review_focus=sub["review_focus"],
                base_sha=base_sha,
                cwd=str(ws),
            )
        state = goal_loop.load_goal_state(cwd=str(ws))
        for sub in plan:
            state["tasks"][sub["id"]]["depends_on"] = list(sub["depends_on"])
        goal_loop.save_goal_state(state, cwd=str(ws))
        goal_loop.run_preflight(cwd=str(ws), as_json=True)
        for sub in plan:
            goal_loop.generate_task_brief(sub["id"], cwd=str(ws))
        subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "immortal_watcher.py"),
                "--init-swarm",
                "--project-goal",
                cfg["title"],
                "--lite",
            ],
            cwd=ws,
            check=True,
            capture_output=True,
        )



def _load_task_modules(ws: Path) -> None:
    """Clear `src` from `sys.modules` and put `ws` at the front of `sys.path`."""
    for mod_name in list(sys.modules.keys()):
        if mod_name == "src" or mod_name.startswith("src."):
            sys.modules.pop(mod_name, None)
    ws_str = str(ws.resolve())
    if ws_str in sys.path:
        sys.path.remove(ws_str)
    sys.path.insert(0, ws_str)
    importlib.invalidate_caches()


def _eval_task_1(ws: Path) -> list[str]:
    """11 held-out adversarial checks for Task 1 (Ledger CLI)."""
    defects: list[str] = []
    _load_task_modules(ws)
    try:
        from src.models import Posting, Transaction
        from src.fx_rates import convert_to_usd
        from src.ledger import LedgerBook
        from src.reconciler import reconcile_external
    except Exception as exc:
        return [f"Import failure: {exc}"]

    # Check 1: Banker's rounding (ROUND_HALF_EVEN) on FX conversion
    try:
        val = convert_to_usd(Decimal("10.005"), "EUR", {"EUR": Decimal("1.00")})
        if val != Decimal("10.00"):
            defects.append(f"FX rounding failed ROUND_HALF_EVEN: expected 10.00, got {val}")
    except Exception as exc:
        defects.append(f"FX conversion raised unexpected error: {exc}")

    # Check 2: Negative or unknown currency rejected
    try:
        convert_to_usd(Decimal("10.00"), "CHF", {"EUR": Decimal("1.10")})
        defects.append("convert_to_usd failed to raise ValueError on unknown currency CHF")
    except ValueError:
        pass
    except Exception as exc:
        defects.append(f"convert_to_usd raised wrong exception type on unknown currency: {exc}")

    # Check 3: Unbalanced multi-currency transaction rejected
    try:
        book = LedgerBook(rates={"EUR": Decimal("1.10")}, no_overdraft_accounts={"cash"})
        bad_tx = Transaction(
            "tx_unbal",
            [
                Posting("cash", "DEBIT", Decimal("100.00"), "EUR"),
                Posting("rev", "CREDIT", Decimal("100.00"), "USD"),
            ],
            "idem-unbal",
        )
        book.post_transaction(bad_tx)
        defects.append("Unbalanced multi-currency transaction was accepted without raising ValueError")
    except ValueError:
        pass
    except Exception as exc:
        defects.append(f"Unbalanced transaction check failed with: {exc}")

    # Check 4: Idempotency replay returns existing without double counting; conflict raises ValueError
    try:
        book = LedgerBook(rates={"EUR": Decimal("1.10")}, no_overdraft_accounts={"cash"})
        tx1 = Transaction(
            "tx1",
            [
                Posting("cash", "DEBIT", Decimal("100.00"), "USD"),
                Posting("rev", "CREDIT", Decimal("100.00"), "USD"),
            ],
            "idem-1",
        )
        book.post_transaction(tx1)
        book.post_transaction(tx1)  # replay
        if book.get_balance("cash") != Decimal("100.00"):
            defects.append(f"Idempotent replay double-counted balance: {book.get_balance('cash')}")
        conflict_tx = Transaction(
            "tx1",
            [
                Posting("cash", "DEBIT", Decimal("200.00"), "USD"),
                Posting("rev", "CREDIT", Decimal("200.00"), "USD"),
            ],
            "idem-1",
        )
        try:
            book.post_transaction(conflict_tx)
            defects.append("Idempotency conflict (same key, different amount) did not raise ValueError")
        except ValueError:
            pass
    except Exception as exc:
        defects.append(f"Idempotency test failed: {exc}")

    # Check 5: Atomic batch rollback when 2nd transaction triggers overdraft
    try:
        book = LedgerBook(rates={"EUR": Decimal("1.10")}, no_overdraft_accounts={"cash"})
        seed = Transaction(
            "seed",
            [
                Posting("cash", "DEBIT", Decimal("50.00"), "USD"),
                Posting("equity", "CREDIT", Decimal("50.00"), "USD"),
            ],
            "k-seed",
        )
        book.post_transaction(seed)
        batch_ok = Transaction(
            "b1",
            [
                Posting("cash", "DEBIT", Decimal("30.00"), "USD"),
                Posting("rev", "CREDIT", Decimal("30.00"), "USD"),
            ],
            "k-b1",
        )
        batch_overdraft = Transaction(
            "b2",
            [
                Posting("expense", "DEBIT", Decimal("100.00"), "USD"),
                Posting("cash", "CREDIT", Decimal("100.00"), "USD"),
            ],
            "k-b2",
        )
        try:
            book.post_batch([batch_ok, batch_overdraft])
            defects.append("post_batch accepted batch with overdraft on no_overdraft_accounts={'cash'}")
        except ValueError:
            pass
        if book.get_balance("cash") != Decimal("50.00"):
            defects.append(
                f"post_batch failed atomic rollback: cash balance is {book.get_balance('cash')} instead of 50.00"
            )
    except Exception as exc:
        defects.append(f"Batch rollback test failed: {exc}")

    # Check 6: Reconciler detects matched, missing_in_ledger, missing_in_bank, and amount_mismatches
    try:
        book = LedgerBook()
        book.post_transaction(
            Transaction(
                "txA",
                [Posting("cash", "DEBIT", Decimal("75.00"), "USD"), Posting("rev", "CREDIT", Decimal("75.00"), "USD")],
                "k-a",
            )
        )
        book.post_transaction(
            Transaction(
                "txB",
                [Posting("cash", "DEBIT", Decimal("40.00"), "USD"), Posting("rev", "CREDIT", Decimal("40.00"), "USD")],
                "k-b",
            )
        )
        sticky = Transaction(
            "txOnlyLedger",
            [Posting("cash", "DEBIT", Decimal("15.00"), "USD"), Posting("rev", "CREDIT", Decimal("15.00"), "USD")],
            "k-c",
        )
        book.post_transaction(sticky)
        rep = reconcile_external(
            book,
            [
                {"tx_id": "txA", "usd_total": "75.00"},
                {"tx_id": "txB", "usd_total": "45.00"},
                {"tx_id": "txOnlyBank", "usd_total": "99.00"},
            ],
        )
        if rep.matched != ["txA"]:
            defects.append(f"Reconciler matched mismatch: {rep.matched}")
        if rep.missing_in_ledger != ["txOnlyBank"]:
            defects.append(f"Reconciler missing_in_ledger mismatch: {rep.missing_in_ledger}")
        if rep.missing_in_bank != ["txOnlyLedger"]:
            defects.append(f"Reconciler missing_in_bank mismatch: {rep.missing_in_bank}")
        if len(rep.amount_mismatches) != 1 or rep.amount_mismatches[0].get("tx_id") != "txB":
            defects.append(f"Reconciler amount_mismatches mismatch: {rep.amount_mismatches}")
    except Exception as exc:
        defects.append(f"Reconciler check failed: {exc}")

    return defects


def _eval_task_2(ws: Path) -> list[str]:
    """Held-out adversarial checks for Task 2 (Rate Limiter & Router)."""
    defects: list[str] = []
    _load_task_modules(ws)
    try:
        from src.policies import QuotaPolicy
        from src.audit_log import RejectionAuditLog
        from src.limiter import CompositeRateLimiter
        from src.router import RequestRouter
    except Exception as exc:
        return [f"Import failure: {exc}"]

    # Check 1: Non-mutation of tokens when sliding window rejects
    try:
        policy = QuotaPolicy("tenant_a", capacity=10, refill_per_sec=1.0, window_seconds=10, max_window_requests=2)
        limiter = CompositeRateLimiter({"tenant_a": policy})
        log = RejectionAuditLog()
        router = RequestRouter(limiter, log)

        d1 = router.handle("tenant_a", "/v1/pay", cost=2, timestamp_ms=1000)
        d2 = router.handle("tenant_a", "/v1/pay", cost=2, timestamp_ms=1000)
        # At t=1000, 6 tokens remain, but sliding window has 2/2 requests.
        # Next request with cost=3 at t=1000 must be rejected by sliding window WITHOUT deducting the 3 tokens!
        d3 = router.handle("tenant_a", "/v1/pay", cost=3, timestamp_ms=1000)
        if d3.allowed:
            defects.append("Sliding window failed to reject 3rd request when max_window_requests=2")
        # At t=11000 (window [1000, 11000] evicts t=1000), tokens should be refilled to 10 (or >= 6 without d3 deduction).
        # Specifically, if we test at t=11000 with refill_per_sec=0.0:
        policy_zero_refill = QuotaPolicy("t_zero", capacity=10, refill_per_sec=0.0001, window_seconds=5, max_window_requests=1)
        lim2 = CompositeRateLimiter({"t_zero": policy_zero_refill})
        r2 = RequestRouter(lim2, log)
        r2.handle("t_zero", "/x", cost=4, timestamp_ms=1000)  # allowed, 6 tokens left
        rej = r2.handle("t_zero", "/x", cost=4, timestamp_ms=2000)  # rejected by window (max_window_requests=1)
        if rej.allowed:
            defects.append("Second request in 5s window should be rejected when max_window_requests=1")
        # At t=6000 (1000 <= 6000 - 5000, so t=1000 is evicted!), a cost=6 request must succeed if rej didn't deduct 4 tokens!
        after_win = r2.handle("t_zero", "/x", cost=6, timestamp_ms=6000)
        if not after_win.allowed:
            defects.append(
                "Rejected sliding-window request erroneously mutated token bucket or failed boundary eviction at t - window"
            )
    except Exception as exc:
        defects.append(f"Sliding window / non-mutation check failed: {exc}")

    # Check 2: Non-mutation of sliding window when token bucket rejects
    try:
        p = QuotaPolicy("t_tok", capacity=3, refill_per_sec=1.0, window_seconds=10, max_window_requests=2)
        lim = CompositeRateLimiter({"t_tok": p})
        log = RejectionAuditLog()
        router = RequestRouter(lim, log)
        a1 = router.handle("t_tok", "/q", cost=3, timestamp_ms=1000)  # uses all 3 tokens, 1/2 window
        a2 = router.handle("t_tok", "/q", cost=2, timestamp_ms=1000)  # fails token bucket (0 tokens < 2)
        if a2.allowed or a2.retry_after_ms != 2000:
            defects.append(f"Token bucket rejection retry_after_ms expected 2000, got allowed={a2.allowed}, retry={a2.retry_after_ms}")
        # At t=3000, 2 tokens refilled; if a2 did NOT pollute the sliding window, window has 1/2 and this must succeed!
        a3 = router.handle("t_tok", "/q", cost=2, timestamp_ms=3000)
        if not a3.allowed:
            defects.append("Rejected token-bucket request erroneously recorded a hit in the sliding window")
    except Exception as exc:
        defects.append(f"Token-bucket non-mutation check failed: {exc}")

    # Check 3: Audit log summary & tenant isolation
    try:
        summary = log.summarize_by_tenant()
        if summary.get("t_tok", {}).get("rejected_count") != 1:
            defects.append(f"RejectionAuditLog not properly wired by RequestRouter: {summary}")
    except Exception as exc:
        defects.append(f"Audit log summary check failed: {exc}")

    return defects


def _eval_task_3(ws: Path) -> list[str]:
    """Held-out adversarial checks for Task 3 (DAG Scheduler)."""
    defects: list[str] = []
    _load_task_modules(ws)
    try:
        from src.graph import TaskNode, WorkflowGraph
        from src.executor import WaveExecutor
    except Exception as exc:
        return [f"Import failure: {exc}"]

    # Check 1: Cycle detection on 3-node cycle and self-loop
    try:
        g = WorkflowGraph()
        g.add_node(TaskNode("A", ["C"]))
        g.add_node(TaskNode("B", ["A"]))
        g.add_node(TaskNode("C", ["B"]))
        cyc = g.find_cycle()
        if not cyc or len(cyc) < 2 or cyc[0] != cyc[-1]:
            defects.append(f"find_cycle() failed to return closed cycle path on A->B->C->A: {cyc}")
        try:
            g.topological_waves()
            defects.append("topological_waves() failed to raise ValueError on cyclic graph")
        except ValueError:
            pass

        g_self = WorkflowGraph()
        g_self.add_node(TaskNode("X", ["X"]))
        if not g_self.find_cycle():
            defects.append("find_cycle() failed to detect self-loop X -> X")
    except Exception as exc:
        defects.append(f"Cycle detection check failed: {exc}")

    # Check 2: Transitive UPSTREAM_FAILED across 3 waves + sibling branch isolation + retry backoff
    try:
        g = WorkflowGraph()
        g.add_node(TaskNode("root_fail", [], max_attempts=3, base_delay_ms=10, multiplier=2.0, max_delay_ms=100))
        g.add_node(TaskNode("mid_dep", ["root_fail"], max_attempts=2))
        g.add_node(TaskNode("leaf_dep", ["mid_dep"], max_attempts=2))
        g.add_node(TaskNode("sibling_ok", [], max_attempts=2, base_delay_ms=15, multiplier=2.0))
        g.add_node(TaskNode("sibling_child", ["sibling_ok"], max_attempts=1))

        invocations = {"mid_dep": 0, "leaf_dep": 0, "sibling_ok": 0}

        def fail_always():
            raise RuntimeError("boom")

        def mid_fn():
            invocations["mid_dep"] += 1
            return "mid"

        def leaf_fn():
            invocations["leaf_dep"] += 1
            return "leaf"

        def sib_fn():
            invocations["sibling_ok"] += 1
            if invocations["sibling_ok"] == 1:
                raise RuntimeError("flaky once")
            return "sib_ok"

        res = WaveExecutor(g).run(
            {
                "root_fail": fail_always,
                "mid_dep": mid_fn,
                "leaf_dep": leaf_fn,
                "sibling_ok": sib_fn,
                "sibling_child": lambda: "child_ok",
            }
        )
        r = res["results"]
        if r["root_fail"]["status"] != "FAILED" or r["root_fail"]["attempts"] != 3:
            defects.append(f"root_fail expected FAILED after 3 attempts, got {r['root_fail']}")
        if r["root_fail"]["delays_ms"] != [10, 20]:
            defects.append(f"root_fail delays_ms expected [10, 20], got {r['root_fail']['delays_ms']}")
        if r["mid_dep"]["status"] != "UPSTREAM_FAILED" or invocations["mid_dep"] != 0:
            defects.append(f"mid_dep should be UPSTREAM_FAILED with 0 calls, got {r['mid_dep']}")
        if r["leaf_dep"]["status"] != "UPSTREAM_FAILED" or invocations["leaf_dep"] != 0:
            defects.append(f"Transitive leaf_dep should be UPSTREAM_FAILED with 0 calls, got {r['leaf_dep']}")
        if r["sibling_ok"]["status"] != "COMPLETED" or r["sibling_child"]["status"] != "COMPLETED":
            defects.append(f"Independent sibling branch failed to complete: {r['sibling_ok']}, {r['sibling_child']}")
    except Exception as exc:
        defects.append(f"WaveExecutor transitive failure / retry check failed: {exc}")

    return defects


def _eval_task_4(ws: Path) -> list[str]:
    """Held-out adversarial checks for Task 4 (Log Query Engine, Spike Detector & Operational UI)."""
    defects: list[str] = []
    _load_task_modules(ws)
    try:
        from src.log_engine import LogRecord, LogStore, compute_percentiles
        from src.spike_detector import detect_latency_spikes
    except Exception as exc:
        return [f"Import failure: {exc}"]

    # Check 1: Nearest-rank percentiles on empty, single, and 20-element list
    try:
        empty_p = compute_percentiles([])
        if empty_p.get("p50") != 0.0 or empty_p.get("p95") != 0.0 or empty_p.get("p99") != 0.0:
            defects.append(f"Empty percentile check failed: {empty_p}")
        twenty = [float(i * 10) for i in range(1, 21)]  # 10..200
        p20 = compute_percentiles(twenty)
        if p20.get("p50") != 100.0 or p20.get("p95") != 190.0 or p20.get("p99") != 200.0:
            defects.append(f"Nearest-rank percentiles on 10..200 expected p50=100, p95=190, p99=200, got {p20}")
    except Exception as exc:
        defects.append(f"Percentile check failed: {exc}")

    # Check 2: LogStore multi-criteria query & spike detector
    try:
        store = LogStore()
        jsonl_lines = "\n".join(
            [
                json.dumps({"timestamp_ms": 1000, "service": "auth", "level": "INFO", "status_code": 200, "latency_ms": 20.0, "message": "Login ok", "trace_id": "t-1"}),
                json.dumps({"timestamp_ms": 1010, "service": "auth", "level": "WARN", "status_code": 429, "latency_ms": 45.0, "message": "Rate throttled", "trace_id": "t-2"}),
                json.dumps({"timestamp_ms": 1020, "service": "auth", "level": "ERROR", "status_code": 503, "latency_ms": 310.0, "message": "DB timeout", "trace_id": "t-3"}),
                json.dumps({"timestamp_ms": 1030, "service": "billing", "level": "FATAL", "status_code": 500, "latency_ms": 500.0, "message": "Stripe webhook timeout", "trace_id": "t-4"}),
            ]
        )
        store.load_jsonl(jsonl_lines)
        q_warn = store.query(min_level="WARN")
        if len(q_warn) != 3:
            defects.append(f"min_level='WARN' expected 3 records (WARN, ERROR, FATAL), got {len(q_warn)}")
        q_5xx = store.query(status_class="5xx", text_query="timeout")
        if len(q_5xx) != 2:
            defects.append(f"status_class='5xx' + text_query='timeout' expected 2 records, got {len(q_5xx)}")
        spikes = detect_latency_spikes(store.query(service="auth"), {"auth": 100.0}, min_samples=3)
        if len(spikes) != 1 or spikes[0]["service"] != "auth":
            defects.append(f"detect_latency_spikes failed to detect auth spike: {spikes}")
    except Exception as exc:
        defects.append(f"LogStore / spike check failed: {exc}")

    # Check 3: Real-browser 3-viewport UI validation on index.html
    html_path = ws / "index.html"
    if not html_path.is_file():
        defects.append("index.html is missing")
    else:
        # Layout/runtime FAILs are defects; `slop-*` rules encode this pack's style preferences, so
        # they are tagged `[UI_STYLE]` and reported separately by `evaluate_workspace`.
        ui_res = web_ui_validator.validate_target(str(html_path), mode="operate")
        for f in ui_res.get("findings", []):
            if f["level"] != "FAIL":
                continue
            tag = "UI_STYLE" if f["id"].startswith("slop-") else "UI_FAIL"
            defects.append(f"[{tag}] [{f['id']} @{f['viewport']}px] {f['message']}")

    return defects


def _eval_task_5(ws: Path) -> list[str]:
    """Held-out adversarial checks for Task 5 (Legacy Subscription Billing, Proration & Tax Refactor)."""
    defects: list[str] = []
    _load_task_modules(ws)
    try:
        from src.models import Coupon, CustomerAccount, LineItem
        from src.proration import prorate_subscription_change
        from src.discounts import apply_discounts
        from src.tax import calculate_tax
        from src.billing import BillingEngine
    except Exception as exc:
        return [f"Import failure: {exc}"]

    # Check 1: Proration half-even rounding & quantity change
    try:
        p_items = prorate_subscription_change(
            old_plan_cents=3000,
            new_plan_cents=9000,
            cycle_start_day=0,
            cycle_end_day=30,
            change_day=10,
            old_quantity=2,
            new_quantity=3,
        )
        if len(p_items) != 2 or p_items[0].amount_cents != -4000 or p_items[1].amount_cents != 18000:
            defects.append(f"Proration quantity/fraction mismatch: got {p_items}")
        # Half-even check: 101 * (1/2) = 50.5 -> 50; 203 * (1/2) = 101.5 -> 102
        he_items = prorate_subscription_change(101, 203, 0, 2, 1)
        if he_items[0].amount_cents != -50 or he_items[1].amount_cents != 102:
            defects.append(
                f"Proration ROUND_HALF_EVEN failed: expected (-50, +102), got ({he_items[0].amount_cents}, {he_items[1].amount_cents})"
            )
    except Exception as exc:
        defects.append(f"Proration check failed: {exc}")

    # Check 2: Non-mutation of caller LineItem & CustomerAccount on preview=True
    try:
        eng = BillingEngine()
        cust = CustomerAccount("c_prev", "DE", vat_id="DE123456789", credit_balance_cents=2000)
        item = LineItem("pro", "Pro Plan", 10000, quantity=1, tax_exempt=False)
        eng.create_invoice(
            "inv_prev",
            cust,
            [item],
            coupons=[Coupon("SAVE10", "PERCENT", 10), Coupon("FIX500", "FIXED_CENTS", 500)],
            preview=True,
        )
        if item.amount_cents != 10000:
            defects.append(f"apply_discounts mutated LineItem.amount_cents in-place to {item.amount_cents}")
        if cust.credit_balance_cents != 2000:
            defects.append(f"create_invoice(preview=True) mutated CustomerAccount.credit_balance_cents to {cust.credit_balance_cents}")
    except Exception as exc:
        defects.append(f"Preview non-mutation check failed: {exc}")

    # Check 3: Exclusive coupon conflict rejection
    try:
        apply_discounts(
            [LineItem("a", "A", 1000, 1)],
            [Coupon("VIP", "PERCENT", 20, exclusive=True), Coupon("EXTRA", "FIXED_CENTS", 100, exclusive=False)],
        )
        defects.append("apply_discounts failed to raise ValueError when exclusive coupon combined with another coupon")
    except ValueError:
        pass
    except Exception as exc:
        defects.append(f"Exclusive coupon check raised wrong exception: {exc}")

    # Check 4: PERCENT before FIXED_CENTS + proportional largest-remainder allocation across taxable/exempt lines
    try:
        items_3 = [
            LineItem("tax_a", "A", 100, 1, tax_exempt=False),
            LineItem("tax_b", "B", 100, 1, tax_exempt=False),
            LineItem("ex_c", "C", 100, 1, tax_exempt=True),
        ]
        lines, tot_disc = apply_discounts(items_3, [Coupon("FIX100", "FIXED_CENTS", 100)])
        nets = [l["net_cents"] for l in lines]
        if tot_disc != 100 or nets != [66, 67, 67]:
            defects.append(f"Largest-remainder proportional allocation on [100,100,100] - 100 expected nets [66,67,67], got {nets}")
        # Ordering check: 1000 with 10% and 90 cents -> 1000 -> 900 -> 810 (total discount 190, not 181)
        ord_lines, ord_disc = apply_discounts(
            [LineItem("x", "X", 1000, 1)],
            [Coupon("C_FIX", "FIXED_CENTS", 90), Coupon("A_PCT", "PERCENT", 10)],
        )
        if ord_disc != 190 or ord_lines[0]["net_cents"] != 810:
            defects.append(f"Coupon ordering (PERCENT before FIXED_CENTS) failed: expected net 810, got {ord_lines}")
    except Exception as exc:
        defects.append(f"Proportional discount / ordering check failed: {exc}")

    # Check 5: EU cross-border B2B reverse charge vs domestic B2B vs invalid VAT prefix
    try:
        sample_lines = [{"sku": "s", "gross_cents": 10000, "discount_cents": 0, "net_cents": 10000, "tax_exempt": False}]
        # Cross-border DE -> FR with valid FR VAT ID -> reverse charge (0 tax)
        rc_ok = calculate_tax(sample_lines, buyer_country="FR", seller_country="DE", buyer_vat_id="FR12345678")
        if not rc_ok.get("reverse_charge") or rc_ok.get("tax_cents") != 0:
            defects.append(f"Cross-border EU B2B should trigger reverse_charge=True, tax=0: got {rc_ok}")
        # Domestic DE -> DE with DE VAT ID -> NOT reverse-charged (19% = 1900)
        dom = calculate_tax(sample_lines, buyer_country="DE", seller_country="DE", buyer_vat_id="DE12345678")
        if dom.get("reverse_charge") or dom.get("tax_cents") != 1900:
            defects.append(f"Domestic EU B2B (DE->DE) must NOT trigger reverse charge (expected tax 1900): got {dom}")
        # Mismatched VAT country prefix (buyer FR with DE VAT ID) -> NOT reverse-charged (20% = 2000)
        bad_vat = calculate_tax(sample_lines, buyer_country="FR", seller_country="DE", buyer_vat_id="DE12345678")
        if bad_vat.get("reverse_charge") or bad_vat.get("tax_cents") != 2000:
            defects.append(f"Mismatched VAT prefix (buyer FR, vat DE...) must NOT trigger reverse charge: got {bad_vat}")
    except Exception as exc:
        defects.append(f"EU reverse-charge tax check failed: {exc}")

    # Check 6: Downgrade credit carry-forward, next-invoice credit application, and void_invoice reversal
    try:
        eng = BillingEngine()
        cust = CustomerAccount("c_down", "DE", vat_id=None, credit_balance_cents=0)
        # Downgrade from 6000 to 2000 halfway through cycle -> -3000 + 1000 = -2000 net subtotal
        down_items = prorate_subscription_change(6000, 2000, 0, 30, 15)
        inv1 = eng.create_invoice("inv_down", cust, down_items)
        if inv1.tax_cents != 0 or inv1.amount_due_cents != 0 or inv1.credit_generated_cents != 2000:
            defects.append(f"Downgrade invoice expected tax=0, due=0, credit_generated=2000, got {inv1}")
        if cust.credit_balance_cents != 2000:
            defects.append(f"Customer credit_balance_cents after downgrade expected 2000, got {cust.credit_balance_cents}")

        # Next invoice: 5000 in DE (19% tax = 950 -> gross 5950) minus 2000 credit = 3950 due
        inv2 = eng.create_invoice("inv_next", cust, [LineItem("std", "Standard", 5000, 1)])
        if inv2.credit_applied_cents != 2000 or inv2.amount_due_cents != 3950 or cust.credit_balance_cents != 0:
            defects.append(f"Credit application on next invoice failed: inv2={inv2}, bal={cust.credit_balance_cents}")

        # Void inv2 -> restores 2000 credit
        eng.void_invoice("inv_next", cust)
        if cust.credit_balance_cents != 2000:
            defects.append(f"Voiding invoice failed to restore credit_applied_cents: bal={cust.credit_balance_cents}")
        # Double-void must raise ValueError
        try:
            eng.void_invoice("inv_next", cust)
            defects.append("Double void_invoice did not raise ValueError")
        except ValueError:
            pass
        # Void inv1 (downgrade invoice) -> claws back 2000 generated credit
        eng.void_invoice("inv_down", cust)
        if cust.credit_balance_cents != 0:
            defects.append(f"Voiding downgrade invoice failed to claw back credit_generated_cents: bal={cust.credit_balance_cents}")
    except Exception as exc:
        defects.append(f"Downgrade credit & void lifecycle check failed: {exc}")

    return defects


def _eval_task_6(ws: Path) -> list[str]:
    """Held-out adversarial checks for Task 6 (MVCC Key-Value Store + CRC32 WAL + Compaction)."""
    defects: list[str] = []
    _load_task_modules(ws)
    try:
        from src.wal import CorruptWALError, WALRecord, WriteAheadLog
        from src.mvcc import MVCCStore, WriteConflictError
        from src.compaction import compact_store
    except Exception as exc:
        return [f"Import failure: {exc}"]

    # Check 1: WAL torn trailing line (no newline) tolerated vs newline-terminated corrupt line & mid-file corruption rejected
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            wal_file = Path(tmpdir) / "test.wal"
            wal = WriteAheadLog(wal_file)
            wal.append(WALRecord(lsn=1, tx_id=1, op="BEGIN"))
            wal.append(WALRecord(lsn=2, tx_id=1, op="PUT", key="a", value=1))
            wal.append(WALRecord(lsn=3, tx_id=1, op="COMMIT", commit_ts=2))

            # Append torn trailing bytes WITHOUT newline
            with open(wal_file, "ab") as f:
                f.write(b"deadbeef\t{\"lsn\":4,\"tx_id\":2")
            rec_torn = wal.recover()
            if len(rec_torn) != 3:
                defects.append(f"WAL recover() failed to tolerate torn final line without newline: got {len(rec_torn)} records")

            # Now terminate the corrupt trailing line WITH newline -> must raise CorruptWALError
            with open(wal_file, "ab") as f:
                f.write(b"}\n")
            try:
                wal.recover()
                defects.append("WAL recover() failed to raise CorruptWALError on newline-terminated line with bad CRC")
            except CorruptWALError:
                pass
            except Exception as exc:
                defects.append(f"WAL recover() raised wrong exception on bad CRC line: {type(exc).__name__}: {exc}")

            # Mid-file corruption followed by valid line -> must raise CorruptWALError
            wal_file2 = Path(tmpdir) / "mid.wal"
            wal2 = WriteAheadLog(wal_file2)
            wal2.append(WALRecord(lsn=1, tx_id=1, op="BEGIN"))
            with open(wal_file2, "ab") as f:
                f.write(b"00000000\t{\"lsn\":2,\"tx_id\":1,\"op\":\"PUT\",\"key\":\"x\",\"value\":1}\n")
            wal2.append(WALRecord(lsn=3, tx_id=1, op="COMMIT", commit_ts=2))
            try:
                wal2.recover()
                defects.append("WAL recover() failed to raise CorruptWALError on mid-file CRC corruption")
            except CorruptWALError:
                pass
    except Exception as exc:
        defects.append(f"WAL framing/recovery check failed: {exc}")

    # Check 2: Staged delete tombstone shadows earlier committed value in get() and scan()
    try:
        store = MVCCStore()
        t1 = store.begin_tx()
        store.put(t1, "user:1", "Alice")
        store.put(t1, "user:2", "Bob")
        store.commit(t1)

        t2 = store.begin_tx()
        store.put(t2, "user:1", "Alicia")
        if store.get(t2, "user:1") != "Alicia":
            defects.append("Read-your-own-writes failed on uncommitted put")
        store.delete(t2, "user:1")
        if store.get(t2, "user:1") is not None:
            defects.append(f"Staged delete failed to shadow committed version in get(): got {store.get(t2, 'user:1')!r}")
        store.put(t2, "user:3", "Carol")
        scanned = store.scan(t2, prefix="user:")
        if scanned != {"user:2": "Bob", "user:3": "Carol"}:
            defects.append(f"scan() failed to merge snapshot with staged puts/deletes: got {scanned}")
        store.commit(t2)
    except Exception as exc:
        defects.append(f"Tombstone shadowing / scan check failed: {exc}")

    # Check 3: Snapshot isolation & First-Committer-Wins atomic conflict abort
    try:
        store = MVCCStore()
        t_init = store.begin_tx()
        store.put(t_init, "shared", "v0")
        store.put(t_init, "keep", "orig")
        store.commit(t_init)

        tx_a = store.begin_tx()
        tx_b = store.begin_tx()

        store.put(tx_a, "shared", "vA")
        store.put(tx_a, "only_a", 100)
        store.commit(tx_a)

        # tx_b started before tx_a committed; reading "shared" in tx_b must still see "v0"
        if store.get(tx_b, "shared") != "v0":
            defects.append(f"Snapshot isolation violated: tx_b saw {store.get(tx_b, 'shared')!r} instead of 'v0'")

        # Now tx_b writes both "only_b" and conflicting key "shared" -> commit must raise WriteConflictError and roll back "only_b"
        store.put(tx_b, "only_b", 200)
        store.put(tx_b, "shared", "vB")
        try:
            store.commit(tx_b)
            defects.append("First-Committer-Wins failed: concurrent write to 'shared' did not raise WriteConflictError")
        except WriteConflictError:
            pass

        tx_verify = store.begin_tx()
        if store.get(tx_verify, "shared") != "vA" or store.get(tx_verify, "only_b") is not None:
            defects.append(
                f"Conflicting transaction leaked partial writes or overwrote winner: shared={store.get(tx_verify, 'shared')}, only_b={store.get(tx_verify, 'only_b')}"
            )
        store.abort(tx_verify)
    except Exception as exc:
        defects.append(f"Snapshot isolation / conflict check failed: {exc}")

    # Check 4: WAL replay ignores uncommitted/aborted txs + Compaction respects active snapshot watermark
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            wal_path = Path(tmpdir) / "engine.wal"
            s1 = MVCCStore(wal_path)
            for i in range(1, 5):
                tx = s1.begin_tx()
                s1.put(tx, "k", f"v{i}")
                s1.commit(tx)
                if i == 2:
                    tx_pinned = s1.begin_tx()  # pinned at snapshot where k == "v2"

            # While tx_pinned is active after v2, compact_store must prune v1, keep v2 (anchor), and keep v3, v4 (> watermark)
            c_res1 = compact_store(s1)
            if s1.get(tx_pinned, "k") != "v2":
                defects.append(f"Compaction broke active snapshot read: expected 'v2', got {s1.get(tx_pinned, 'k')!r}")
            if c_res1.get("pruned_count", 0) < 1:
                defects.append(f"Compaction failed to prune obsolete version v1 behind watermark: {c_res1}")
            s1.abort(tx_pinned)

            # Delete 'k', commit, and leave an uncommitted dirty transaction in WAL
            tx_del = s1.begin_tx()
            s1.delete(tx_del, "k")
            s1.commit(tx_del)

            tx_dirty = s1.begin_tx()
            s1.put(tx_dirty, "k", "dirty_uncommitted")
            s1.put(tx_dirty, "ghost", "uncommitted")
            # Do not commit tx_dirty!

            # Compact with no active snapshots after reopening from WAL
            s2 = MVCCStore.open(wal_path)
            tx_check = s2.begin_tx()
            if s2.get(tx_check, "k") is not None or s2.get(tx_check, "ghost") is not None:
                defects.append(
                    f"MVCCStore.open() replayed uncommitted WAL records: k={s2.get(tx_check, 'k')}, ghost={s2.get(tx_check, 'ghost')}"
                )
            s2.abort(tx_check)
            c_res2 = compact_store(s2)
            if c_res2.get("versions_after") != 0:
                defects.append(f"Compaction with only tombstone anchor and no active tx expected versions_after=0, got {c_res2}")
    except Exception as exc:
        defects.append(f"Compaction / WAL replay check failed: {exc}")

    return defects


def _eval_task_7(ws: Path) -> list[str]:
    """11 held-out integration checks for Task 7 (Multi-Warehouse Order Fulfilment)."""
    defects: list[str] = []
    _load_task_modules(ws)
    try:
        from src.contracts import (
            InvalidTransitionError,
            ManualClock,
            OutOfStockError,
            Product,
            ReservationExpiredError,
            UnknownSkuError,
        )
        from src.catalog import Catalog
        from src.inventory import Inventory
        from src.shipping import quote_shipping
        from src.orders import OrderService
    except Exception as exc:
        return [f"Import failure: {exc}"]

    def world():
        clock = ManualClock(0)
        cat = Catalog()
        cat.add_product(Product("MUG", "Mug", 600, ((1, 1000), (10, 900), (50, 800))))
        cat.add_product(Product("CAP", "Cap", 150, ((1, 1500),)))
        cat.add_product(Product("OLD", "Retired", 100, ((1, 500),), active=False))
        inv = Inventory(clock)
        inv.add_stock("WH-B", "MUG", 3)
        inv.add_stock("WH-A", "MUG", 2)
        inv.add_stock("WH-A", "CAP", 5)
        return clock, cat, inv, OrderService(cat, inv, clock, reservation_ttl_ms=1000)

    # Check 1: Tier pricing picks the largest min_qty <= qty
    try:
        _, cat, _, _ = world()
        got = [cat.unit_price_cents("MUG", q) for q in (9, 10, 75)]
        if got != [1000, 900, 800]:
            defects.append(f"unit_price_cents tiers for qty 9/10/75 expected [1000, 900, 800], got {got}")
    except Exception as exc:
        defects.append(f"Tier pricing check failed: {exc!r}")

    # Check 2: Unknown and inactive SKUs raise UnknownSkuError
    try:
        _, cat, _, _ = world()
        for sku in ("NOPE", "OLD"):
            try:
                cat.get(sku)
                defects.append(f"Catalog.get({sku!r}) did not raise UnknownSkuError")
            except UnknownSkuError:
                pass
    except Exception as exc:
        defects.append(f"Unknown/inactive SKU check failed: {exc!r}")

    # Check 3: Reservation splits across warehouses in ascending warehouse_id order
    try:
        _, _, inv, _ = world()
        res = inv.reserve("o1", {"MUG": 4}, 1000)
        got = [(a.sku, a.warehouse_id, a.qty) for a in res.allocations]
        if got != [("MUG", "WH-A", 2), ("MUG", "WH-B", 2)]:
            defects.append(f"reserve split expected [(MUG, WH-A, 2), (MUG, WH-B, 2)], got {got}")
        if inv.available("MUG") != 1:
            defects.append(f"available(MUG) after reserving 4 of 5 expected 1, got {inv.available('MUG')}")
    except Exception as exc:
        defects.append(f"Warehouse split check failed: {exc!r}")

    # Check 4: reserve() is all-or-nothing
    try:
        _, _, inv, _ = world()
        try:
            inv.reserve("o2", {"CAP": 1, "MUG": 99}, 1000)
            defects.append("reserve() with an unfillable line did not raise OutOfStockError")
        except OutOfStockError:
            pass
        if inv.available("CAP") != 5:
            defects.append(f"Failed reserve() still holds stock: available(CAP)={inv.available('CAP')}, expected 5")
    except Exception as exc:
        defects.append(f"All-or-nothing reserve check failed: {exc!r}")

    # Check 5: Expired reservations stop holding stock and cannot be committed
    try:
        clock, _, inv, _ = world()
        res = inv.reserve("o3", {"CAP": 5}, 1000)
        clock.advance(1000)
        if inv.available("CAP") != 5:
            defects.append(f"Expired reservation still held: available(CAP)={inv.available('CAP')}, expected 5")
        try:
            inv.commit(res.reservation_id)
            defects.append("commit() of an expired reservation did not raise ReservationExpiredError")
        except ReservationExpiredError:
            pass
        if inv.on_hand("WH-A", "CAP") != 5:
            defects.append(f"Expired commit changed on_hand: {inv.on_hand('WH-A', 'CAP')}, expected 5")
    except Exception as exc:
        defects.append(f"Reservation expiry check failed: {exc!r}")

    # Check 6: One shipment per warehouse, per-kg fee on ceil(kg) of each shipment
    try:
        _, _, inv, _ = world()
        res = inv.reserve("o4", {"MUG": 4}, 1000)
        fee = quote_shipping(res.allocations, {"MUG": 600}, "DOMESTIC")
        if fee != 2 * (499 + 2 * 100):
            defects.append(f"Split shipment DOMESTIC fee expected 1398 (2 x (499 + 2kg x 100)), got {fee}")
        if quote_shipping([], {}, "EU") != 0:
            defects.append("quote_shipping([]) should be 0")
    except Exception as exc:
        defects.append(f"Shipping quote check failed: {exc!r}")

    # Check 7: Order totals integrate catalog tiers and the reservation's warehouse split
    try:
        _, _, _, svc = world()
        o = svc.create_order("o5", "EU", {"MUG": 4, "CAP": 1})
        # MUG 4 x 1000 + CAP 1 x 1500; WH-A ships MUG 2 + CAP 1 (1350 g -> 2 kg), WH-B ships MUG 2 (1200 g -> 2 kg)
        exp_ship = (1299 + 2 * 250) * 2
        if (o.subtotal_cents, o.shipping_cents, o.total_cents) != (5500, exp_ship, 5500 + exp_ship):
            defects.append(
                f"Order o5 (subtotal, shipping, total) expected (5500, {exp_ship}, {5500 + exp_ship}), "
                f"got ({o.subtotal_cents}, {o.shipping_cents}, {o.total_cents})"
            )
        if o.status != "PENDING":
            defects.append(f"New order status expected PENDING, got {o.status}")
    except Exception as exc:
        defects.append(f"Order totals check failed: {exc!r}")

    # Check 8: Paying after expiry marks the order EXPIRED and frees its stock
    try:
        clock, _, inv, svc = world()
        svc.create_order("o6", "DOMESTIC", {"CAP": 2})
        clock.advance(1000)
        try:
            svc.pay("o6")
            defects.append("pay() after reservation expiry did not raise ReservationExpiredError")
        except ReservationExpiredError:
            pass
        if svc.get("o6").status != "EXPIRED":
            defects.append(f"Order status after expired pay expected EXPIRED, got {svc.get('o6').status}")
        if inv.available("CAP") != 5 or inv.on_hand("WH-A", "CAP") != 5:
            defects.append("Expired order still holds or consumed CAP stock")
    except Exception as exc:
        defects.append(f"Expired payment check failed: {exc!r}")

    # Check 9: Cancelling a PAID order restocks each allocation to its original warehouse
    try:
        _, _, inv, svc = world()
        svc.create_order("o7", "DOMESTIC", {"MUG": 4})
        svc.pay("o7")
        if (inv.on_hand("WH-A", "MUG"), inv.on_hand("WH-B", "MUG")) != (0, 1):
            defects.append(
                f"After paying o7 on_hand (WH-A, WH-B) expected (0, 1), "
                f"got ({inv.on_hand('WH-A', 'MUG')}, {inv.on_hand('WH-B', 'MUG')})"
            )
        svc.cancel("o7")
        if (inv.on_hand("WH-A", "MUG"), inv.on_hand("WH-B", "MUG")) != (2, 3):
            defects.append(
                f"Cancelling PAID o7 should restock (WH-A, WH-B) to (2, 3), "
                f"got ({inv.on_hand('WH-A', 'MUG')}, {inv.on_hand('WH-B', 'MUG')})"
            )
    except Exception as exc:
        defects.append(f"Paid-cancel restock check failed: {exc!r}")

    # Check 10: Invalid transitions raise InvalidTransitionError
    try:
        _, _, _, svc = world()
        svc.create_order("o8", "DOMESTIC", {"CAP": 1})
        svc.cancel("o8")
        for op in (svc.cancel, svc.pay):
            try:
                op("o8")
                defects.append(f"{op.__name__}() on a CANCELLED order did not raise InvalidTransitionError")
            except InvalidTransitionError:
                pass
    except Exception as exc:
        defects.append(f"Invalid transition check failed: {exc!r}")

    # Check 11: Rejected orders reserve nothing; duplicate order IDs are rejected
    try:
        _, _, inv, svc = world()
        try:
            svc.create_order("o9", "DOMESTIC", {"CAP": 1, "NOPE": 1})
            defects.append("create_order() with an unknown SKU did not raise UnknownSkuError")
        except UnknownSkuError:
            pass
        if inv.available("CAP") != 5:
            defects.append(f"Rejected order still holds CAP stock: available={inv.available('CAP')}")
        svc.create_order("o10", "DOMESTIC", {"CAP": 1})
        try:
            svc.create_order("o10", "DOMESTIC", {"CAP": 1})
            defects.append("Duplicate order_id did not raise ValueError")
        except ValueError:
            pass
        if inv.available("CAP") != 4:
            defects.append(f"Duplicate order_id changed held stock: available(CAP)={inv.available('CAP')}, expected 4")
    except Exception as exc:
        defects.append(f"Order validation check failed: {exc!r}")

    return defects


def _call_with_timeout(fn: Any, *args: Any, timeout: float = 5.0) -> Any:
    """Run `fn(*args)` in a forked child so an endless loop in agent code cannot hang the evaluator."""
    ctx = multiprocessing.get_context("fork")
    queue = ctx.Queue()

    def target() -> None:
        try:
            queue.put(("ok", fn(*args)))
        except BaseException as exc:  # forwarded to the caller
            queue.put(("err", exc))

    proc = ctx.Process(target=target)
    proc.start()
    proc.join(timeout)
    if proc.is_alive():
        proc.kill()
        proc.join()
        raise TimeoutError(f"{getattr(fn, '__name__', fn)} did not return within {timeout}s")
    kind, value = queue.get(timeout=1)
    if kind == "err":
        raise value
    return value


def _eval_task_8(ws: Path) -> list[str]:
    """12 held-out checks for Task 8 (Shared-Expense Ledger). Each case follows from a stated invariant
    (exact money, conservation, determinism, side-effect-free validation) but is not spelled out in the spec."""
    defects: list[str] = []
    _load_task_modules(ws)
    try:
        from src.money import format_amount, parse_amount
        from src.group import Group
        from src.settle import settle
    except Exception as exc:
        return [f"Import failure: {exc}"]

    def group(*names):
        g = Group()
        for n in names:
            g.add_member(n)
        return g

    def snapshot(g):
        return (g.balances(), list(g.expenses()))

    # Check 1: Parsing is exact (no float round-trip) and rejects non-amount strings
    try:
        got = [parse_amount(t) for t in ("19.99", "0.07", "-3.1", "12", "4.35")]
        if got != [1999, 7, -310, 1200, 435]:
            defects.append(f"parse_amount of 19.99/0.07/-3.1/12/4.35 expected [1999, 7, -310, 1200, 435], got {got}")
        for bad in ("1.005", "abc", "", "1e3", "1.2.3", "nan"):
            try:
                parse_amount(bad)
                defects.append(f"parse_amount({bad!r}) did not raise ValueError")
            except ValueError:
                pass
    except Exception as exc:
        defects.append(f"parse_amount check failed: {exc!r}")

    # Check 2: Formatting small negative amounts keeps the sign on the whole value
    try:
        got = [format_amount(c) for c in (-5, -310, 0, 1999)]
        if got != ["-0.05", "-3.10", "0.00", "19.99"]:
            defects.append(f"format_amount of -5/-310/0/1999 expected ['-0.05', '-3.10', '0.00', '19.99'], got {got}")
    except Exception as exc:
        defects.append(f"format_amount check failed: {exc!r}")

    # Check 3: Uneven equal split conserves every cent and differs by at most 1 cent
    try:
        shares = group("ann", "bob", "cat").add_expense("e1", "ann", "1.00", {"ann": 1, "bob": 1, "cat": 1})
        vals = [shares[n] for n in ("ann", "bob", "cat")]
        if sum(vals) != 100 or max(vals) - min(vals) > 1:
            defects.append(f"Splitting 1.00 three ways must sum to 100 with spread <= 1, got {shares}")
    except Exception as exc:
        defects.append(f"Uneven split check failed: {exc!r}")

    # Check 4: Weighted split stays within 1 cent of the exact proportional share
    try:
        shares = group("ann", "bob").add_expense("e1", "ann", "1.00", {"ann": 2, "bob": 1})
        exact = {"ann": 200 / 3, "bob": 100 / 3}
        if sum(shares.values()) != 100 or any(abs(shares[n] - exact[n]) >= 1 for n in exact):
            defects.append(f"Weighted 2:1 split of 1.00 must sum to 100 within 1 cent of {{ann: 66.7, bob: 33.3}}, got {shares}")
    except Exception as exc:
        defects.append(f"Weighted split check failed: {exc!r}")

    # Check 5: Refunds (negative amounts) split with the same exactness
    try:
        shares = group("ann", "bob", "cat").add_expense("r1", "ann", "-1.00", {"ann": 1, "bob": 1, "cat": 1})
        vals = list(shares.values())
        if sum(vals) != -100 or max(vals) - min(vals) > 1:
            defects.append(f"Splitting a -1.00 refund three ways must sum to -100 with spread <= 1, got {shares}")
    except Exception as exc:
        defects.append(f"Refund split check failed: {exc!r}")

    # Check 6: Who receives the leftover cent does not depend on dict order
    try:
        a = group("ann", "bob", "cat").add_expense("e1", "ann", "1.00", {"ann": 1, "bob": 1, "cat": 1})
        b = group("cat", "bob", "ann").add_expense("e1", "ann", "1.00", {"cat": 1, "bob": 1, "ann": 1})
        if dict(sorted(a.items())) != dict(sorted(b.items())):
            defects.append(f"Same split in different member/weight order gave different shares: {a} vs {b}")
    except Exception as exc:
        defects.append(f"Split determinism check failed: {exc!r}")

    # Check 7: Invalid expenses raise ValueError and leave state unchanged
    try:
        g = group("ann", "bob")
        g.add_expense("e1", "ann", "10.00", {"ann": 1, "bob": 1})
        before = snapshot(g)
        bad_calls = {
            "all-zero weights": ("e2", "ann", "5.00", {"ann": 0, "bob": 0}),
            "negative weight": ("e3", "ann", "5.00", {"ann": 2, "bob": -1}),
            "non-member in weights": ("e4", "ann", "5.00", {"ann": 1, "zed": 1}),
            "non-member payer": ("e5", "zed", "5.00", {"ann": 1}),
            "duplicate expense_id": ("e1", "bob", "5.00", {"ann": 1}),
            "empty weights": ("e6", "ann", "5.00", {}),
            "bad amount": ("e7", "ann", "5.001", {"ann": 1}),
        }
        for label, args in bad_calls.items():
            try:
                g.add_expense(*args)
                defects.append(f"add_expense with {label} did not raise ValueError")
            except ValueError:
                pass
            if snapshot(g) != before:
                defects.append(f"add_expense with {label} changed state")
                before = snapshot(g)
    except Exception as exc:
        defects.append(f"Validation side-effect check failed: {exc!r}")

    # Check 8: Balances conserve money and include idle members
    try:
        g = group("ann", "bob", "cat", "dan")
        g.add_expense("e1", "ann", "10.00", {"ann": 1, "bob": 1, "cat": 1})
        g.add_expense("e2", "bob", "7.01", {"ann": 3, "cat": 4})
        g.add_expense("r1", "cat", "-2.00", {"ann": 1, "bob": 1, "cat": 1})
        bal = g.balances()
        if sum(bal.values()) != 0:
            defects.append(f"Balances must sum to 0, got {bal} (sum {sum(bal.values())})")
        if bal.get("dan") != 0:
            defects.append(f"Member with no expenses must appear with balance 0, got {bal.get('dan')!r}")
    except Exception as exc:
        defects.append(f"Balance conservation check failed: {exc!r}")

    # Check 9: Settlement zeroes every balance with positive, non-self transfers
    try:
        bal = {"ann": 1234, "bob": -999, "cat": -235, "dan": 500, "eve": -500}
        transfers = _call_with_timeout(settle, dict(bal))
        after = dict(bal)
        for frm, to, amt in transfers:
            if amt <= 0 or frm == to:
                defects.append(f"Invalid transfer {(frm, to, amt)}")
            after[frm] += amt
            after[to] -= amt
        if any(after.values()):
            defects.append(f"Applying settle() transfers left non-zero balances: {after}")
    except Exception as exc:
        defects.append(f"Settlement correctness check failed: {exc!r}")

    # Check 10: Settlement is deterministic under input order and needs no transfers when settled
    try:
        bal = {"ann": 300, "bob": -100, "cat": -100, "dan": -100}
        a = _call_with_timeout(settle, dict(bal))
        b = _call_with_timeout(settle, dict(reversed(list(bal.items()))))
        if [tuple(t) for t in a] != [tuple(t) for t in b]:
            defects.append(f"settle() depends on input order: {a} vs {b}")
        if _call_with_timeout(settle, {}) != [] or _call_with_timeout(settle, {"ann": 0, "bob": 0}) != []:
            defects.append("settle() of empty or all-zero balances must return []")
    except Exception as exc:
        defects.append(f"Settlement determinism check failed: {exc!r}")

    # Check 11: Settlement rejects balances that do not sum to 0
    try:
        _call_with_timeout(settle, {"ann": 100, "bob": -99})
        defects.append("settle() with balances summing to 1 did not raise ValueError")
    except ValueError:
        pass
    except Exception as exc:
        defects.append(f"Unbalanced settle check failed: {exc!r}")

    # Check 12: Many small expenses accumulate without drift
    try:
        g = group("ann", "bob", "cat")
        for i in range(100):
            g.add_expense(f"e{i}", "ann", "0.10", {"ann": 1, "bob": 1, "cat": 1})
        bal = g.balances()
        owed = {"ann": 1000 - bal["ann"], "bob": -bal["bob"], "cat": -bal["cat"]}
        if sum(bal.values()) != 0 or any(not 300 <= v <= 400 for v in owed.values()):
            defects.append(f"100 x 0.10 split three ways: each member must owe 300-400 cents and balances sum to 0, got {bal}")
    except Exception as exc:
        defects.append(f"Accumulation check failed: {exc!r}")

    return defects


EVALUATORS = {
    "task_1_ledger_cli": _eval_task_1,
    "task_2_rate_limiter": _eval_task_2,
    "task_3_dag_scheduler": _eval_task_3,
    "task_4_log_query_workbench": _eval_task_4,
    "task_5_legacy_billing_refactor": _eval_task_5,
    "task_6_mvcc_wal_store": _eval_task_6,
    "task_7_parallel_fulfilment": _eval_task_7,
    "task_8_expense_ledger_traps": _eval_task_8,
}

# Oracle-graded tasks T9-T11 (see `oracle_tasks.py`); their evaluators also return a score.
sys.path.insert(0, str(BENCH_DIR))
import oracle_tasks  # noqa: E402

for _key, _cfg in oracle_tasks.tasks().items():
    _fn = _cfg.pop("evaluator")
    TASKS[_key] = _cfg
    EVALUATORS[_key] = lambda ws, fn=_fn: fn(ws, _load_task_modules, _call_with_timeout)


def inspect_subagent_transcript(conv_id: str) -> dict[str, Any]:
    """Read `$ANTIGRAVITY_BRAIN_DIR/<conv_id>/.system_generated/logs/transcript.jsonl`."""
    t_path = BRAIN_DIR / conv_id / ".system_generated" / "logs" / "transcript.jsonl"
    if not t_path.is_file():
        return {"exists": False, "steps": 0, "tool_calls": 0, "chars": 0, "transcript_tokens_est": 0}

    steps = 0
    tool_calls = 0
    chars = 0
    with open(t_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line_s = line.strip()
            if not line_s:
                continue
            steps += 1
            chars += len(line_s)
            try:
                obj = json.loads(line_s)
                tcs = obj.get("tool_calls") or []
                if isinstance(tcs, list):
                    tool_calls += len(tcs)
            except Exception:
                pass
    return {
        "exists": True,
        "steps": steps,
        "tool_calls": tool_calls,
        "chars": chars,
        "transcript_tokens_est": round(chars / 4),
    }


def inspect_gate_activity(ws: Path) -> dict[str, Any] | None:
    """Summarize what the Discriminator Gate recorded in `.swarm/goal_loop.json`, or None if absent."""
    goal_file = ws / ".swarm" / "goal_loop.json"
    if not goal_file.is_file():
        return None
    state = json.loads(goal_file.read_text(encoding="utf-8"))
    rounds = 0
    failed_rounds = 0
    findings = {"critical": 0, "important": 0, "minor": 0, "blocking_fails": 0}
    review_sources: dict[str, int] = {}
    for task in state.get("tasks", {}).values():
        for entry in task.get("history", []):
            rounds += 1
            source = entry.get("review_source") or "unrecorded"
            review_sources[source] = review_sources.get(source, 0) + 1
            if not entry.get("passed"):
                failed_rounds += 1
            findings["critical"] += entry.get("critical_count") or 0
            findings["important"] += entry.get("important_count") or 0
            findings["minor"] += entry.get("minor_count") or 0
            findings["blocking_fails"] += len(entry.get("blocking_fails") or [])
    return {
        "tasks": len(state.get("tasks", {})),
        "review_rounds": rounds,
        "failed_rounds": failed_rounds,
        "findings": findings,
        "review_sources": review_sources,
    }


def evaluate_workspace(arm: str, task_key: str, ws: Path) -> dict[str, Any]:
    """Run held-out adversarial tests, AST wiring check, and authenticity scan on one run's workspace."""
    cfg = TASKS[task_key]

    held_out = EVALUATORS[task_key](ws)
    score = None
    if isinstance(held_out, tuple):
        held_out, score = held_out
    ui_style = [d for d in held_out if d.startswith("[UI_STYLE]")]
    ui_defects = [d for d in held_out if d.startswith("[UI_FAIL]")]
    held_out_defects = [d for d in held_out if d not in ui_style and d not in ui_defects]

    wiring_res = goal_loop.verify_wiring(
        root_dir=str(ws),
        target_files=cfg["target_files"],
        wiring_files=cfg["wiring_files"],
        required_symbols=cfg["required_symbols"],
    )
    wiring_defects = [f"[WIRING] {e}" for e in wiring_res.get("errors", [])]

    auth_res = goal_loop.audit_authenticity(
        root_dir=str(ws),
        target_files=cfg["target_files"] + cfg["wiring_files"],
        entrypoints=cfg["wiring_files"],
        check_orphan_modules=True,
    )
    auth_defects: list[str] = []
    for p in auth_res.get("placeholder_findings", []):
        auth_defects.append(f"[STUB:{p['kind']} {p['file']}:{p['line']}] {p['detail']}")
    for s in auth_res.get("synthetic_findings", []):
        auth_defects.append(f"[SYNTHETIC:{s['kind']} {s['file']}:{s['line']}] {s['detail']}")
    for u in auth_res.get("unwired_findings", []):
        auth_defects.append(f"[UNWIRED:{u['kind']} {u['file']}] {u['detail']}")

    unit_cmd = goal_loop.run_command_gate(cfg["verification_cmd"], cwd=str(ws))
    unit_defects = [] if unit_cmd["passed"] else [f"[UNIT_TEST_FAIL] {e}" for e in unit_cmd["errors"]]

    all_defects = held_out_defects + ui_defects + wiring_defects + auth_defects + unit_defects
    return {
        "arm": arm,
        "task": task_key,
        "workspace": str(ws),
        "passed_all": len(all_defects) == 0,
        "total_defects": len(all_defects),
        "held_out_defect_count": len(held_out_defects),
        "ui_defect_count": len(ui_defects),
        "wiring_defect_count": len(wiring_defects),
        "authenticity_defect_count": len(auth_defects),
        "unit_test_defect_count": len(unit_defects),
        "defects": all_defects,
        "oracle_score": None if score is None else round(score, 4),
        "ui_style_findings": ui_style,
        "gate": inspect_gate_activity(ws) if arm == "swarm_lite" else None,
    }


def _run_meta(meta: dict[str, Any], arm: str, task_key: str, run_id: str) -> dict[str, Any]:
    """Telemetry for one run: `meta[arm][task][run_id]`, or the legacy `meta[arm][task]` for `r1`."""
    t_meta = meta.get(arm, {}).get(task_key, {})
    if "conversation_ids" in t_meta:
        return t_meta if run_id == "r1" else {}
    return t_meta.get(run_id, {})


def _spread(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "min": 0.0, "max": 0.0}
    return {"mean": round(sum(values) / len(values), 1), "min": min(values), "max": max(values)}


def evaluate_all(meta: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "token_method": "transcript_tokens_est = chars / 4 of transcript.jsonl (proxy; excludes context re-reads)",
        "arms": {},
        "summary": {},
    }
    for arm in ARMS:
        arm_runs: dict[str, dict[str, Any]] = {}
        per_task: dict[str, Any] = {}
        pending: list[str] = []
        for task_key in TASKS:
            runs = []
            for run_id, ws in discover_runs(arm, task_key):
                if is_completed(ws, task_key):
                    runs.append((run_id, ws))
                else:
                    pending.append(f"{task_key}/{run_id}")
            if not runs:
                continue
            evs: dict[str, Any] = {}
            for run_id, ws in runs:
                ev = evaluate_workspace(arm, task_key, ws)
                r_meta = _run_meta(meta, arm, task_key, run_id)
                conv_ids = r_meta.get("conversation_ids", [])
                tel = [inspect_subagent_transcript(cid) for cid in conv_ids]
                # Harnesses without readable transcripts (Claude Code subagents) report tokens directly.
                ev["reported_tokens"] = r_meta.get("reported_tokens")
                ev["has_telemetry"] = bool(conv_ids) or ev["reported_tokens"] is not None
                ev["wall_seconds"] = round(float(r_meta.get("wall_seconds", 0.0)), 2)
                ev["conversation_ids"] = conv_ids
                ev["planner_steps"] = sum(t["steps"] for t in tel)
                ev["tool_calls"] = sum(t["tool_calls"] for t in tel)
                ev["transcript_chars"] = sum(t["chars"] for t in tel)
                ev["transcript_tokens_est"] = sum(t["transcript_tokens_est"] for t in tel)
                evs[run_id] = ev
            arm_runs[task_key] = evs

            with_tel = [e for e in evs.values() if e["has_telemetry"]]
            per_task[task_key] = {
                "runs": len(evs),
                "passed_runs": sum(1 for e in evs.values() if e["passed_all"]),
                "defects": _spread([e["total_defects"] for e in evs.values()]),
                "ui_style_findings": _spread([len(e["ui_style_findings"]) for e in evs.values()]),
                "wall_seconds": _spread([e["wall_seconds"] for e in with_tel]),
                "transcript_tokens_est": _spread([e["transcript_tokens_est"] for e in with_tel]),
                "tool_calls": _spread([e["tool_calls"] for e in with_tel]),
            }
            reported = [e["reported_tokens"] for e in with_tel if e["reported_tokens"] is not None]
            if reported:
                per_task[task_key]["reported_tokens"] = _spread(reported)
            scores = [e["oracle_score"] for e in evs.values() if e["oracle_score"] is not None]
            if scores:
                per_task[task_key]["oracle_score"] = _spread(scores)
            gates = [e["gate"] for e in evs.values() if e.get("gate")]
            if gates:
                per_task[task_key]["gate_failed_rounds"] = sum(g["failed_rounds"] for g in gates)
                per_task[task_key]["gate_findings"] = {
                    k: sum(g["findings"][k] for g in gates) for k in gates[0]["findings"]
                }

        if not arm_runs:
            if pending:
                report["summary"][arm] = {"runs_passed": "0/0", "pending_runs": pending}
            continue
        all_evs = [e for evs in arm_runs.values() for e in evs.values()]
        with_tel = [e for e in all_evs if e["has_telemetry"]]
        report["arms"][arm] = arm_runs
        report["summary"][arm] = {
            "runs_passed": f"{sum(1 for e in all_evs if e['passed_all'])}/{len(all_evs)}",
            "total_defects_found_afterwards": sum(e["total_defects"] for e in all_evs),
            "total_ui_style_findings": sum(len(e["ui_style_findings"]) for e in all_evs),
            "runs_with_telemetry": len(with_tel),
            "pending_runs": pending,
            "total_wall_seconds": round(sum(e["wall_seconds"] for e in with_tel), 2),
            "total_planner_steps": sum(e["planner_steps"] for e in with_tel),
            "total_tool_calls": sum(e["tool_calls"] for e in with_tel),
            "total_transcript_tokens_est": sum(e["transcript_tokens_est"] for e in with_tel),
            "total_reported_tokens": sum(e["reported_tokens"] or 0 for e in with_tel),
            "per_task": per_task,
        }
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="Benchmark Suite Provisioner & Post-Hoc Evaluator")
    ap.add_argument("--setup", action="store_true", help="Provision missing workspaces for every arm (existing runs are kept)")
    ap.add_argument("--runs", type=int, default=1, help="Runs per arm and task to provision with --setup (r1..rN)")
    ap.add_argument("--clean", action="store_true", help="Delete ALL existing benchmark runs before setup")
    ap.add_argument(
        "--spec-only",
        action="store_true",
        help="With --setup: provision swarm_lite only, without the acceptance section in TASK_SPEC.md",
    )
    ap.add_argument("--evaluate", action="store_true", help="Evaluate all completed runs in benchmarks/runs/")
    ap.add_argument("--telemetry-file", default=str(BENCH_DIR / "telemetry_meta.json"), help="JSON mapping arm -> task -> run_id -> {conversation_ids | reported_tokens, wall_seconds}")
    ap.add_argument("--runs-dir", default=os.environ.get("BENCH_RUNS_DIR", ""), help="Runs folder to use instead of benchmarks/runs (e.g. one per harness)")
    ap.add_argument("--tasks", default="", help="Comma-separated task keys or IDs (T9,T10) to restrict --setup and --evaluate to")
    ap.add_argument("--results-file", default=str(BENCH_DIR / "results.json"), help="Where --evaluate writes its report")
    args = ap.parse_args()

    global RUNS_DIR
    if args.runs_dir:
        RUNS_DIR = Path(args.runs_dir).resolve()
    if args.tasks:
        wanted = {t.strip() for t in args.tasks.split(",") if t.strip()}
        for key in [k for k, c in TASKS.items() if k not in wanted and c["id"] not in wanted]:
            TASKS.pop(key)

    if args.setup:
        res = setup_workspaces(clean=args.clean, runs=args.runs, spec_only=args.spec_only)
        print(json.dumps(res, indent=2))
        return

    if args.evaluate:
        meta: dict[str, Any] = {}
        if os.path.exists(args.telemetry_file):
            with open(args.telemetry_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
        report = evaluate_all(meta)
        out_json = Path(args.results_file)
        out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
