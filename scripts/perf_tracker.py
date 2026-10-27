#!/usr/bin/env python3
"""Quantitative Performance & Memory Benchmark Tracker across Swarm Epochs.

Executes a target benchmark command over N iterations, measures wall-clock latency
(mean, median, min, max) and peak RSS memory usage, stores the results in
`.swarm/benchmarks.json`, and computes percentage deltas against previous epochs
so `rigor_auditor` and the Orchestrator can detect performance regressions.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import statistics
import subprocess
import sys
import time
from typing import Any

DEFAULT_BENCH_FILE = ".swarm/benchmarks.json"


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load_benchmarks(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return {"benchmarks": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"benchmarks": {}}


def save_benchmarks(path: str, data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def run_single_iteration(cmd: str, cwd: str | None = None) -> tuple[int, float, int]:
    """Run command and return (exit_code, elapsed_ms, peak_rss_kb)."""
    use_gnu_time = os.path.exists("/usr/bin/time")
    start = time.perf_counter()
    peak_kb = 0

    if use_gnu_time:
        wrapped_cmd = f'/usr/bin/time -f "__MEM_KB__:%M" bash -c {json.dumps(cmd)}'
        res = subprocess.run(wrapped_cmd, shell=True, cwd=cwd, capture_output=True, text=True, check=False)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        for line in (res.stderr or "").splitlines():
            if line.startswith("__MEM_KB__:"):
                try:
                    peak_kb = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
        return res.returncode, elapsed_ms, peak_kb

    res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, check=False)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return res.returncode, elapsed_ms, peak_kb


def run_benchmark(
    name: str,
    cmd: str,
    epoch: int = 1,
    runs: int = 3,
    max_regression_pct: float = 15.0,
    bench_file: str = DEFAULT_BENCH_FILE,
    cwd: str | None = None,
) -> dict[str, Any]:
    latencies_ms: list[float] = []
    peak_kbs: list[int] = []
    passed_runs = 0
    failed_run_details: list[str] = []

    for i in range(runs):
        code, elapsed_ms, peak_kb = run_single_iteration(cmd, cwd=cwd)
        if code != 0:
            failed_run_details.append(f"run {i + 1} exited with code {code}")
        else:
            passed_runs += 1
            latencies_ms.append(round(elapsed_ms, 2))
            peak_kbs.append(peak_kb)

    pass_at_k = passed_runs >= 1
    pass_hat_k = passed_runs == runs
    pass_rate = round(passed_runs / max(1, runs), 3)

    if not pass_hat_k:
        return {
            "name": name,
            "epoch": epoch,
            "runs": runs,
            "passed_runs": passed_runs,
            "pass_at_k": pass_at_k,
            "pass_hat_k": pass_hat_k,
            "pass_rate": pass_rate,
            "status": "FAIL",
            "reason": f"pass^{runs} reliability gate failed ({passed_runs}/{runs} passed): {'; '.join(failed_run_details)}",
        }

    mean_ms = round(statistics.mean(latencies_ms), 2)
    median_ms = round(statistics.median(latencies_ms), 2)
    min_ms = round(min(latencies_ms), 2)
    max_ms = round(max(latencies_ms), 2)
    max_rss_kb = max(peak_kbs) if peak_kbs else 0

    store = load_benchmarks(bench_file)
    history: list[dict[str, Any]] = store.setdefault("benchmarks", {}).setdefault(name, [])

    baseline = history[0] if history else None
    previous = history[-1] if history else None

    delta_vs_prev_pct = None
    delta_vs_base_pct = None
    regressed = False

    if previous and previous.get("median_ms", 0) > 0:
        delta_vs_prev_pct = round(((median_ms - previous["median_ms"]) / previous["median_ms"]) * 100.0, 2)
        if delta_vs_prev_pct > max_regression_pct:
            regressed = True

    if baseline and baseline.get("median_ms", 0) > 0:
        delta_vs_base_pct = round(((median_ms - baseline["median_ms"]) / baseline["median_ms"]) * 100.0, 2)

    record = {
        "name": name,
        "epoch": epoch,
        "timestamp": now_iso(),
        "command": cmd,
        "runs": runs,
        "passed_runs": passed_runs,
        "pass_at_k": pass_at_k,
        "pass_hat_k": pass_hat_k,
        "pass_rate": pass_rate,
        "mean_ms": mean_ms,
        "median_ms": median_ms,
        "min_ms": min_ms,
        "max_ms": max_ms,
        "peak_rss_kb": max_rss_kb,
        "delta_vs_previous_pct": delta_vs_prev_pct,
        "delta_vs_baseline_pct": delta_vs_base_pct,
        "status": "REGRESSION" if regressed else "PASS",
    }
    history.append(record)
    save_benchmarks(bench_file, store)
    return record


def main() -> None:
    ap = argparse.ArgumentParser(description="Quantitative Performance & Memory Tracker across Swarm Epochs")
    ap.add_argument("--name", required=True, help="Benchmark identifier (e.g. core_simulation, api_throughput)")
    ap.add_argument("--command", required=True, help="Shell command to benchmark")
    ap.add_argument("--epoch", type=int, default=1, help="Current Macro-Loop Epoch (1..3)")
    ap.add_argument("--runs", type=int, default=3, help="Number of iterations (default: 3)")
    ap.add_argument("--max-regression-pct", type=float, default=15.0, help="Allowed latency regression percentage")
    ap.add_argument("--file", default=DEFAULT_BENCH_FILE, help="Path to benchmarks JSON file")
    ap.add_argument("--cwd", help="Working directory for the benchmark command")
    args = ap.parse_args()

    result = run_benchmark(
        name=args.name,
        cmd=args.command,
        epoch=args.epoch,
        runs=args.runs,
        max_regression_pct=args.max_regression_pct,
        bench_file=args.file,
        cwd=args.cwd,
    )
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("status") == "PASS" else 1)


if __name__ == "__main__":
    main()
