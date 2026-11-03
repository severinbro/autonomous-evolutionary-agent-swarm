#!/usr/bin/env python3
"""Probe benchmark task T1 workspaces for the idempotency rule a checklist once narrowed (RESULTS.md §3.3).

The T1 spec: "safe replay for identical transactions; raises `ValueError` on conflicting reuse of the same key".
The benchmark's acceptance bullet restated it as "replay with identical postings returns original transaction ...,
while differing amount/account raises", and the runs that received it accept a reused key with identical postings
but a different `tx_id`. Two transactions with different IDs are not identical, so the spec rejects that reuse.

Each workspace gets two checks on a fresh `LedgerBook`, both starting from `tx1` posted under key `k1`:
  - sanity:   `tx2` reuses `k1` with different amounts            -> must raise ValueError
  - decisive: `tx2` reuses `k1` with postings identical to `tx1`  -> must raise ValueError

Result per workspace: FULL_RULE (both raise), NARROW_RULE (only the sanity check raises), ERROR (anything else).
Exit code: 0 if every workspace is FULL_RULE, 1 if any is NARROW_RULE (and none is ERROR), 2 if any is ERROR.

Usage: t1_reuse_probe.py WORKSPACE [WORKSPACE ...] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_benchmarks import _load_task_modules  # noqa: E402


def _reuse_raises(mods: dict[str, Any], second_amount: str) -> bool:
    """Post tx1 under key k1, then tx2 under k1; True if tx2 raises ValueError."""
    Posting, Transaction, LedgerBook = mods["Posting"], mods["Transaction"], mods["LedgerBook"]

    def postings(amount: str) -> list[Any]:
        return [
            Posting("cash", "DEBIT", Decimal(amount), "USD"),
            Posting("rev", "CREDIT", Decimal(amount), "USD"),
        ]

    book = LedgerBook(rates={"EUR": Decimal("1.10")})
    book.post_transaction(Transaction("tx1", postings("100.00"), "k1"))
    try:
        book.post_transaction(Transaction("tx2", postings(second_amount), "k1"))
    except ValueError:
        return True
    return False


def probe(ws: Path) -> dict[str, str]:
    _load_task_modules(ws)
    try:
        from src.ledger import LedgerBook
        from src.models import Posting, Transaction
    except Exception as exc:
        return {"result": "ERROR", "detail": f"import failure: {exc!r}"}
    mods = {"Posting": Posting, "Transaction": Transaction, "LedgerBook": LedgerBook}
    try:
        if not _reuse_raises(mods, "200.00"):
            return {"result": "ERROR", "detail": "sanity check failed: reused key with different amounts was accepted"}
        if _reuse_raises(mods, "100.00"):
            return {"result": "FULL_RULE", "detail": "reused key with a different tx_id is rejected"}
        return {"result": "NARROW_RULE", "detail": "reused key with identical postings but a different tx_id is accepted"}
    except Exception as exc:
        return {"result": "ERROR", "detail": f"unexpected exception: {exc!r}"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("workspaces", nargs="+", help="T1 workspace folders (each with src/ledger.py and src/models.py)")
    ap.add_argument("--json", action="store_true", help="Print one JSON object keyed by workspace")
    args = ap.parse_args()

    results = {ws: probe(Path(ws)) for ws in args.workspaces}
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for ws, res in results.items():
            print(f"{res['result']:<12} {ws}  ({res['detail']})")
    found = {r["result"] for r in results.values()}
    sys.exit(2 if "ERROR" in found else 1 if "NARROW_RULE" in found else 0)


if __name__ == "__main__":
    main()
