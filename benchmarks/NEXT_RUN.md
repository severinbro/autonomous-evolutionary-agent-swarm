# Next Benchmark Run: T7 and T8 in Antigravity

This run tests the two cases the T1–T6 results left open (see [`RESULTS.md`](RESULTS.md) §6):

- **T7, parallel modules on a shared contract:** do parallel workers save wall time without adding integration defects?
- **T8, invariants stated but edge cases not:** does an independent reviewer catch what a self-checking worker misses?

T1–T6 are not re-run. Each new task runs in two arms, 3 times each: **12 runs**, already provisioned under `benchmarks/runs/`.

| Arm | Workspace | What runs |
| :--- | :--- | :--- |
| `single_agent_checked` | `runs/single_agent_checked/<task>/r1..r3` | One agent with `TASK_SPEC.md` (spec + acceptance criteria). |
| `swarm_lite` | `runs/swarm_lite/<task>/r1..r3` | `/invoke-swarm lite` with the plan already in `.swarm/goal_loop.json`, followed as written. For T7 that is 5 sub-tasks, 3 of them in parallel. |

Expect roughly 3–4 hours of agent time in total if the runs take about as long as T4–T6 did.

---

## 1. Before the first run

1. **Reinstall the plugin so Antigravity uses the updated skills.** The `invoke-swarm`, `discriminator-gate`, `goal-loop` and `coop-brainstorm` skills and `goal_loop.py` changed. Antigravity runs a copy, not this checkout:
   ```bash
   cd /path/to/autonomous-evolutionary-agent-swarm
   ./install.sh antigravity
   ```
   Then restart Antigravity.
2. **Check that all 12 runs are pending:**
   ```bash
   python3 benchmarks/evaluate_benchmarks.py --evaluate | grep -A4 pending_runs
   ```
   Each arm should list `task_7_parallel_fulfilment/r1..r3` and `task_8_expense_ledger_traps/r1..r3`. This rewrites `results.json`; the T1–T6 numbers stay identical.
3. **Use the same model as before** (`inherit`).
4. **Playwright is not needed.** Neither task has a UI.

## 2. Rules for every run

These rules keep the arms comparable.

- **One new top-level conversation per run,** opened on that run's workspace folder only. Do not start runs as subagents of a driver conversation, and never open the `benchmarks/` folder or the repo root in a run.
- **The agent must not read `benchmarks/evaluate_benchmarks.py`.** It contains the held-out checks. The prompts below confine the agent to its workspace. If an agent opens a file outside its workspace anyway, note it and mark the run as contaminated in your notes.
- **Don't intervene.** If an agent asks a question, answer only: `Decide using TASK_SPEC.md and continue.` Note that it asked.
- **Time cap: 45 minutes per run.** If a run is still going, stop it and record it as it stands. The evaluator grades whatever is on disk.
- **Interleave the arms** so drift in time of day or service load hits both equally. Use this order:
  1. T7 r1 checked, T7 r1 swarm, T8 r1 checked, T8 r1 swarm
  2. the same four for r2
  3. the same four for r3
- **Don't re-run a failed run.** A crash or a wrong result is data. If a run cannot start at all (tool outage), redo it and note why.

## 3. Prompts

Replace `<WS>` with the run's absolute workspace path, for example:
`/path/to/autonomous-evolutionary-agent-swarm/benchmarks/runs/swarm_lite/task_7_parallel_fulfilment/r2`

### `single_agent_checked` (T7 and T8)

```text
Your workspace is <WS>. Work only inside it and do not read or list files outside it.

Implement the task described in <WS>/TASK_SPEC.md. Follow its "Acceptance Criteria & Self-Checks" section: run the verification command and the outcome command yourself and fix anything that fails before you finish.

Do not use subagents. When you are done, reply with at most 5 lines: status, files created, and the exit codes of the verification and outcome commands.
```

### `swarm_lite`, T7 (parallel plan)

```text
Your workspace is <WS>. You and every subagent you start must work only inside it and must not read or list files outside it.

Run /invoke-swarm lite on this workspace. The plan is already in <WS>/.swarm/goal_loop.json with briefs in <WS>/.swarm/briefs/: T7.0 (shared contract), then T7.A, T7.B and T7.C in parallel, then T7.D (integration). Do not change tasks, depends_on, or review_focus. Run --preflight first.

Follow the skill as written, with these settings:
- Dispatch T7.A, T7.B and T7.C as three concurrent worker subagents once T7.0 is recorded complete. Workers edit the workspace directly (no git worktrees); preflight guarantees their target files do not overlap.
- Step 1.5b applies (parallel work merging on a shared contract): run a reviewer subagent for each task and record its verdict with --review-source reviewer.
- Finish with goal_loop.py --verify-goal. Reply with at most 10 lines: final status of each task, fix rounds used, and the --verify-goal result.
```

### `swarm_lite`, T8 (single task)

```text
Your workspace is <WS>. You and every subagent you start must work only inside it and must not read or list files outside it.

Run /invoke-swarm lite on this workspace. The plan is already in <WS>/.swarm/goal_loop.json (one task, T8) with its brief in <WS>/.swarm/briefs/. Do not change the task or its review_focus.

Follow the skill as written, with this setting:
- Step 1.5b applies (the spec's invariants cannot be fully checked by a command): after the worker reports done, run a reviewer subagent and record its verdict with --review-source reviewer.
- Finish with goal_loop.py --verify-goal. Reply with at most 10 lines: final task status, fix rounds used, any findings, and the --verify-goal result.
```

## 4. Record telemetry after each run

Add an entry to `benchmarks/telemetry_meta.json` under `arm → task → run_id`. The shape matches the existing entries:

```json
"swarm_lite": {
  "task_7_parallel_fulfilment": {
    "r1": {
      "conversation_ids": ["<orchestrator id>", "<worker T7.0 id>", "<worker T7.A id>", "...", "<reviewer ids>"],
      "wall_seconds": 1234.0
    }
  }
}
```

- **`conversation_ids`:** every conversation that worked on the run. That is the single agent's own conversation for `single_agent_checked`, and the orchestrator plus every worker and reviewer subagent for `swarm_lite`. The IDs are the folder names under `~/.gemini/antigravity/brain/`.
- **`wall_seconds`:** from sending the prompt to the agent's final reply.
- **Note on comparing with T1–T6:** these runs count the swarm orchestrator's own conversation. If you drove T1–T6 from one parent conversation, its orchestration cost was not counted then, so compare T7–T8 swarm cost with T7–T8 checked cost, not with the T1–T6 ratios.

## 5. Evaluate

```bash
cd /path/to/autonomous-evolutionary-agent-swarm
python3 benchmarks/evaluate_benchmarks.py --evaluate
```

This grades every completed workspace and writes `benchmarks/results.json`. T7 and T8 appear under `summary.<arm>.per_task`. For `swarm_lite` the `gate_*` fields show review rounds, findings, and `review_sources` (the count of `reviewer` vs `self-check` verdicts; anything other than `reviewer` means the orchestrator did not follow the prompt).

## 6. How to read the results

With 3 runs per cell, treat each outcome as indicative, not proof.

**T7 (parallel workers):**

| If you see | It means |
| :--- | :--- |
| Swarm wall time clearly below checked (e.g. ≤ 0.75×) with no more defects | Parallel dispatch pays off on multi-module work. Keep it, and measure the token cost against the time saved. |
| Swarm not faster, or more held-out defects (integration seams) | Coordination overhead outweighs parallelism at this size. Recommend a single checked agent unless modules are much larger. |
| Reviewer `failed_rounds > 0` and those runs pass the held-out checks | The reviewer caught real integration problems. Note which checks. |

**T8 (unstated edge cases):**

| If you see | It means |
| :--- | :--- |
| Checked runs fail some of the 12 checks and swarm runs fail fewer, with `failed_rounds > 0` | The reviewer earns its cost when the spec states invariants rather than cases. Keep Step 1.5b's rule. |
| Both arms fail the same checks | The reviewer misses what the worker misses. Drop the reviewer for this case too. |
| Both arms pass everything | The traps are still too easy for this model; say so in RESULTS.md rather than drawing a conclusion. |

Then update RESULTS.md §6 with the numbers, and the summary if a conclusion changes.
