---
name: invoke-swarm
description: "Use when the user asks for a multi-agent swarm, an autonomous team of agents, or a large build that should run in parallel and keep iterating until verified results match the goal, or wants to run a single stage of that loop."
---

# Invoke Evolutionary Agent Swarm (`/invoke-swarm`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

When the user invokes `/invoke-swarm` (or asks to build, upgrade, or verify a complex system using the multi-agent swarm), you act as the **Swarm Orchestrator**. You coordinate specialized subagents across an evolutionary **3-Epoch Funnel** (plus automatic Goal-Loop Remediation Epochs if needed) until every deterministic invariant, AST wiring contract, and end-to-end outcome check passes.

---

## The Iron Laws of `/invoke-swarm`

```
1. NEVER DISPATCH PARALLEL WORKERS WITHOUT RUNNING `goal_loop.py --preflight` FIRST.
2. NEVER PASTE MULTI-FILE SPECS OR DIFFS INTO SUBAGENT PROMPTS — USE `--task-brief` AND `--review-package` FILE PATHS.
3. SUBAGENTS MUST RETURN CONCISE (`< 15 LINES`) STRUCTURED STATUS REPORTS TO PRESERVE ORCHESTRATOR CONTEXT.
4. NO TASK MERGES TO MAIN WITHOUT PASSING THE TWO-VERDICT DISCRIMINATOR GATE (0 BLOCKING_FAIL, SPEC PASS, 0 CRITICAL, 0 IMPORTANT).
5. DEFERRED MINOR FINDINGS ARE SWEPT IN EPOCH 3 POLISH — THEY NEVER DERAIL EPOCH 1 OR EPOCH 2 VELOCITY.
```

---

## The Evolutionary Swarm Lifecycle (Step-by-Step)

### Step 0: Blueprint & Goal-Loop Manifest Initialization
1. Ensure `.swarm/goal_loop.json` exists and defines the `overall_goal`, `non_negotiables`, `outcome_verification_cmds`, and epoch tasks (`id`, `title`, `epoch`, `base_sha`, `review_focus`, `target_files`, `wiring_contract`, `verification_commands`, `subtasks`).
2. Initialize the immortal supervisor state:
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" \
     --init-swarm --project-goal "<Overall Project Goal>"
   ```

### Step 0.25: Pre-Dispatch Conflict Scan (`--preflight`)
Before spawning any worker subagents for the current epoch, run the deterministic preflight check:
```bash
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" \
  --cwd <WORKSPACE_DIR> --preflight
```
- `--preflight` exits `1` until every failure is fixed. Do not dispatch while it fails.
- `OVERLAPPING_TARGET_FILES` (two parallel tasks modify the same file): **serialize** them with `depends_on`, or move the shared code into a contract/foundation task (`/contract-lock`).
- `MISSING_VERIFICATION_CMD`: add concrete shell test commands to the task's `verification_commands`.
- `UNRESOLVED_DEPENDENCY`: fix the `depends_on` task ID.

### Step 0.5: Pre-Spawn Interface & Type Contract Lock (`/contract-lock`)
Freeze shared cross-module interfaces, schemas, and entrypoint signatures on the base branch before parallel workers branch off, recording the commit SHA in each task's `base_sha`.

### Step 1: Context-Slimmed Worker Dispatch (`--task-brief <TASK_ID>`)
For each ready task in the current epoch:
1. Generate its self-contained task brief on disk:
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" \
     --cwd <WORKSPACE_DIR> --task-brief <TASK_ID>
   ```
2. Invoke the worker subagent, passing **only the path** `.swarm/briefs/<TASK_ID>-brief.md` and enforcing the **Structured Subagent Return Contract (`< 15 lines`)**:
   ```markdown
   Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
   Task: <TASK_ID>
   Files Modified: <comma-separated paths>
   Verification Run: <exact command(s) + exit code>
   Wiring Proof: <caller_file:line -> exported_symbol()>
   Concerns / Notes: <1-3 bullet points max, or "None">
   ```
   - Handle `Status` immediately:
     - `BLOCKED` or `NEEDS_CONTEXT`: Resolve the missing dependency or ambiguity before running the reviewer.
     - `DONE` or `DONE_WITH_CONCERNS`: Proceed to Step 1.5 (`/discriminator-gate`).

### Step 1.5: Two-Verdict Discriminator Gate & 5-Round Escalating Fix Loop (`/discriminator-gate`)
1. Generate the deterministic diff review package on disk:
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" \
     --cwd <WORKSPACE_DIR> --review-package <TASK_ID> --base-sha <BASE_SHA>
   ```
2. Run deterministic invariant verification (`--audit-task <TASK_ID>`) and evaluate `.swarm/reviews/<TASK_ID>-review.diff.md` across:
   - **Part 1 — Spec & Outcome Compliance:** `PASS | FAIL | UNVERIFIABLE` (checks `Missing`, `Extra / YAGNI`, `Misunderstood`, and `review_focus` test coverage).
   - **Part 2 — Code Quality Severity Buckets:** `Critical` (hard-caps at `<= 6.0`), `Important` (hard-caps at `<= 7.0`), `Minor` (logged to `.swarm/deferred_minor_ledger.md`, never blocks).
3. Record the verdict with `goal_loop.py --record-task` (your verdict can only add failures; `BLOCKING_FAIL`s from the audit always count). If the task did not pass, execute the **5-Round Escalating Fix Loop**:
   - **Rounds 1–3:** Resume the **same worker** with only open `Critical` and `Important` findings; re-review strictly `FIX_BASE..HEAD` (`ADDRESSED | NOT ADDRESSED` + `New Breakage in the Fix Diff`).
   - **Rounds 4–5:** Retire the stalled worker and spawn a **fresh worker subagent** (`"A prior implementer attempted this task 3 times; these findings remain open. You own it now."`).
   - **Round 5 Breaker (`Ruling:`):** Stop at Round 5. Pick one `--ruling-type` (`OVERRIDE`, `SPLIT_TASK`, `RE_ARCHITECT_CONTRACT`, `ESCALATE_TO_USER`) and record `Ruling: <what you decided> — <why> — <what it costs if wrong>` via `goal_loop.py --record-task <TASK_ID> --ruling-type <TYPE> --ruling "..."`. Only `OVERRIDE` completes the task, and only with zero `BLOCKING_FAIL`s (see `/discriminator-gate`).

### Step 2: Git Worktree Merge Surgery (`/merge-surgeon`)
If workers ran in isolated branches/worktrees, merge verified branches cleanly while honoring `/contract-lock` interfaces and re-verifying post-merge tests.

### Step 3: Intermittent Epoch Report (`/epoch-planner`)
Confirm every Epoch <N> task is `VERIFIED_COMPLETE`, `COMPLETED_WITH_RULING`, or `SUPERSEDED` by finished tasks in `goal_loop.py --status` (tasks that are `BLOCKED_BY_RULING` go to the user), then generate `.swarm/reports/epoch_<N>_intermittent_report.md`.

### Steps 4–6: Parallel Triad Audit (`/triad-audit`) + SOTA Web Scout (`/sota-web-scout`)
Spawn `rigor_auditor`, `safety_auditor`, `innovation_auditor`, and `sota_web_scout` in parallel to stress-test edge cases, security/resource safety, performance baselines (`/perf-benchmarker`), and external SOTA parity.

### Step 7: Next-Epoch Adjusted Plan (`/epoch-planner`) & The 3-Epoch Funnel
Synthesize Triad Audit and SOTA findings into the next epoch's tasks in `.swarm/goal_loop.json` (including `review_focus` and `base_sha`):
- **Epoch 1 (Broad Exploration & Core Architecture):** End-to-end working vertical slice with 100% AST wiring.
- **Epoch 2 (Deepening, Edge Cases & SOTA Parity):** Resolving Triad Audit findings, concurrency/error recovery, and high-ROI SOTA features.
- **Epoch 3 (Convergence, Polish & Deferred Minor Ledger Sweep):** Sweeping `.swarm/deferred_minor_ledger.md`, zeroing regressions, and running `/quality-validator` + `goal_loop.py --verify-goal`.
- **Epoch 4+ (Automatic Remediation Epochs):** Triggered automatically if `goal_loop.py --verify-goal` or `immortal_watcher.py --check-convergence` reports unfinished invariants.

---

## Red Flag Thought-Catchers (STOP Immediately If You Think Any of These)

- *"I'll spawn 4 workers right now without running `--preflight` because their task titles sound different."* -> **STOP.** Different task titles routinely touch the same `main.py`, `router.ts`, or `config.py`. Run `--preflight` first.
- *"I'll ask each worker to return a full 300-line walkthrough of its changes in its final message."* -> **STOP.** Multi-hundred-line subagent replies overflow the orchestrator context window by Epoch 2. Enforce the `< 15 lines` return contract and rely on `--review-package` on disk.
- *"A worker returned `DONE_WITH_CONCERNS`, so I'll just mark it `VERIFIED` without reading the concern."* -> **STOP.** Inspect the concern and pass it to `/discriminator-gate` before recording the task verdict.

---

## Rationalization Excuse / Reality Table

| Common Orchestrator Excuse | Reality & Mandatory Action |
| :--- | :--- |
| *"We're in a hurry, so I'll skip the Discriminator Gate for Epoch 1 and audit everything in Epoch 3."* | Unwired modules and broken assumptions in Epoch 1 compound exponentially in Epoch 2. Every task must pass `--audit-task` and `--record-task` in its own epoch. |
| *"The reviewer found 3 Minor style issues, so I'll run a fix round now."* | Minor issues are logged to `.swarm/deferred_minor_ledger.md` and swept in Epoch 3. Never burn fix-loop rounds on Minor items in Epochs 1–2. |
| *"All 3 Epochs ran, so the swarm is done even though `--verify-goal` has 1 failing command."* | The 3-Epoch Funnel is a structure, not a permission slip to ship broken software. Spawn Remediation Epoch 4 until `--verify-goal` exits `0`. |
