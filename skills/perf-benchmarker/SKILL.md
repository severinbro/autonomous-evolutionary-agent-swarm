---
name: perf-benchmarker
description: "Use when measuring the latency or peak memory of a command, recording a performance baseline, checking a change for performance regressions, or verifying that a test passes reliably across repeated runs."
disable-model-invocation: false
triggers: [user, model]
---

# Quantitative Performance & Memory Benchmarker (`/perf-benchmarker`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

Use this skill **standalone** or inside **`/triad-audit` (`rigor_auditor`)** to measure quantitative wall-clock latency (`mean`, `median`, `min`, `max` in ms) and peak RSS memory usage (`KB`) across Epochs 1 $\rightarrow$ 2 $\rightarrow$ 3.

---

## 1. CLI Usage (`scripts/perf_tracker.py`)

```bash
# Run a benchmark command across 5 iterations for Epoch N and compare against baseline:
python3 "$AGENT_SWARM_HOME/scripts/perf_tracker.py" \
  --name "core_pipeline" \
  --command "pytest tests/bench_pipeline.py -q" \
  --epoch <N> \
  --runs 5 \
  --max-regression-pct 15.0
```

---

## 2. How It Integrates with the 3-Epoch Loop

1. **Epoch 1 (Baseline Establishment):**
   - During Step 4–5 of Epoch 1, `rigor_auditor` runs `perf_tracker.py` on the core workload or benchmark test to record the **Epoch 1 Baseline** in `.swarm/benchmarks.json`.
2. **Epoch 2 & Epoch 3 (Regression Detection):**
   - `perf_tracker.py` automatically computes `delta_vs_previous_pct` and `delta_vs_baseline_pct`.
   - If median latency regresses by more than `--max-regression-pct` (default `15%`), the script outputs `"status": "REGRESSION"` and exits with code `1`.
   - `rigor_auditor` flags any `"REGRESSION"` as a `HIGH` severity finding for the next epoch's adjusted plan (and logs the cause in `.swarm/lessons_learned.md`).
3. **Dashboard Visualization:**
   - All recorded benchmarks in `.swarm/benchmarks.json` are automatically rendered in `.swarm/dashboard.html` when `immortal_watcher.py --generate-dashboard` is called.
