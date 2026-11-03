---
name: invoke-swarm
description: "Use when the user asks for a multi-agent swarm, an autonomous team of agents, or a large build that should run in parallel and keep iterating until verified results match the goal, or wants to run a single stage of that loop."
---

# Invoke Evolutionary Agent Swarm (`/invoke-swarm`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

When the user invokes `/invoke-swarm` (or asks to build, upgrade, or verify a system using the multi-agent swarm), you act as the **Swarm Orchestrator**. You can run `/invoke-swarm` in these modes:

- **Lite Mode (`/invoke-swarm` or `/invoke-swarm lite`) — the default:** Runs **1 Epoch** with Pre-Flight (`--preflight`), Worker Dispatch (`--task-brief`) in waves of ready tasks, workers that run their own acceptance checks and validators, the **deterministic gate** (`--audit-task`, `--record-task`), and the **Validator** (test suite, `web_ui_validator.py`, `goal_loop.py --verify-goal`). A separate reviewer subagent (`/discriminator-gate`) runs only when Step 1.5b calls for one. `/triad-audit` and `/sota-web-scout` run only when the user asks for the release-level audit at the exit gate (Step 2.5).
- **Full Mode (`/invoke-swarm full`) — opt-in Multi-Epoch Evolutionary Funnel:** Coordinates specialized subagents across the **3-Epoch Funnel** (including parallel Triad Audit and SOTA Web Scout between epochs, plus automatic Goal-Loop Remediation Epochs if needed) until every deterministic invariant, AST wiring contract, and end-to-end outcome check passes. It runs only when the user asks for it.
- **Best-of-3 (`/invoke-swarm best-of-3`) — opt-in:** three independent workers, a cross-testing picker, then the Lite gate (see "Best-of-3 Mode").
- **Single stages** (`discriminate-only`, `audit-only`, `sota-only`, `replan-only`) work as before.

---

## Choosing a Mode

No argument means Lite. When another mode fits the request better, say so in one line with the figures below, and switch only when the user says so.

| Mode | Fits when | Tokens vs. one checked agent | Wall time vs. one checked agent |
| :--- | :--- | :--- | :--- |
| one checked agent (not a swarm) | One task whose acceptance runs as commands | 1× (measured) | 1× |
| **`lite` (default)**, reviewer skipped | Acceptance runnable as commands | estimated 2–3× (the orchestrator alone cost 1.2–2× on T7/T8) | not measured |
| `lite` + reviewer (Step 1.5b) | Real acceptance hidden or judgment-heavy | 2.1× on SWE-bench; 2.2–7.6× on T1–T8 | 2.3× on SWE-bench; 4.7× on its Django subset |
| `best-of-3` (opt-in) | Several plausible fixes, Python tests, wall time matters | 3.0× on SWE-bench, plus the reviewer when Step 1.5b applies | 1.5× on SWE-bench, before merge and gate |
| `/peer-swarm` (separate skill) | One build of 15+ minutes that splits along modules | 1.9× on T12; 3.1× on SWE-bench Django | 0.57× on T12 |
| `full` (opt-in) | The user asks for multi-epoch hardening | not measured | not measured |

Figures come from `benchmarks/RESULTS.md`; the SWE-bench ones from one run of 20 instances (suggestive, not significant).

---

## Best-of-3 Mode (`/invoke-swarm best-of-3`)

Three independent workers attempt the same task; a script picks the attempt whose code passes the most of all attempts' new tests. It is never chosen automatically, and it is offered only for projects whose tests are Python files.

1. **Preconditions.** The working tree is clean (otherwise stop and say so: uncommitted work would be missing from every attempt). The task exists in `.swarm/goal_loop.json` (add it as in Lite Step 0). Record the base commit `B`.
2. **Attempts.** For n = 1..3 create a worktree; it is placed next to the repository at `../<repo>-<branch>`:
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/worktree_manager.py" create <task>-bo3-<timestamp>-<n> --base <current branch>
   ```
   If a worktree cannot be created (for example because a sandbox blocks the parent folder), stop and suggest Lite. Dispatch three workers in parallel, one per worktree. Give each the absolute path of the task brief in the main workspace and its own report path there, `.swarm/reports/<task>-attempt-<n>-report.md` (worktrees have no `.swarm/`). Each worker adds or updates tests for the change and commits.
3. **Pick.** Literal braces in the test command must be doubled; `{tests}` is replaced by the test files to run:
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/attempt_picker.py" \
     --attempts <worktree 1> <worktree 2> <worktree 3> \
     --git-base B --test-cmd "<test command with {tests}>" --timeout 900 --json > .swarm/pick-<task>.json
   ```
   The picker ranks attempts by: own new tests pass, then the mean fraction of all attempts' new test files passed, then the lower attempt number. If no attempt changed a test file, every attempt scores 0: stop and suggest Lite with the reviewer.
4. **Finish.** Merge the winning attempt's branch (the worktree path ends in its name) through `/merge-surgeon`. Run Step 1.5a on the result; if it fails, try the runner-up once, then run the fix loop with that worker. Run Step 1.5b when its conditions hold. Remove all three worktrees and branches with `worktree_manager.py cleanup <branch> --delete-branch`.

Known costs and limits: the picker copies each attempt for 9 test runs; three concurrent workers can collide on ports or caches; when a test file already fails at `B`, attempts tie and attempt 1 wins.

---

## The Iron Laws of `/invoke-swarm`

```
1. NEVER DISPATCH PARALLEL WORKERS WITHOUT RUNNING `goal_loop.py --preflight` FIRST.
2. NEVER PASTE MULTI-FILE SPECS OR DIFFS INTO SUBAGENT PROMPTS — USE `--task-brief` AND `--review-package` FILE PATHS.
3. SUBAGENTS MUST RETURN CONCISE (`< 15 LINES`) STRUCTURED STATUS REPORTS TO PRESERVE ORCHESTRATOR CONTEXT.
4. NO TASK MERGES TO MAIN WITHOUT PASSING THE DETERMINISTIC GATE (`--audit-task`: 0 BLOCKING_FAIL; VERIFICATION, OUTCOME AND UI VALIDATOR COMMANDS EXIT 0), PLUS THE REVIEWER VERDICT WHEN STEP 1.5b REQUIRES ONE.
5. DEFERRED MINOR FINDINGS ARE SWEPT IN EPOCH 3 POLISH (OR REPORTED AT EXIT IN LITE MODE) — THEY NEVER DERAIL BUILD VELOCITY.
```

---

## The Evolutionary Swarm Lifecycle (Step-by-Step)

### Step 0: Blueprint & Goal-Loop Manifest Initialization
1. Ensure `.swarm/goal_loop.json` exists and defines the `overall_goal`, `non_negotiables`, `outcome_verification_cmds`, and epoch tasks (`id`, `title`, `epoch`, `base_sha`, `review_focus`, `target_files`, `wiring_contract`, `verification_commands`, `subtasks`).
2. Initialize the immortal supervisor state (Lite is the default; add `--full` for Full Mode):
   ```bash
   # Lite Mode (1 Epoch — gate + Validator):
   python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" \
     --init-swarm --project-goal "<Overall Project Goal>"

   # Full Mode (3-Epoch Funnel), only on /invoke-swarm full:
   python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" \
     --init-swarm --full --project-goal "<Overall Project Goal>"
   ```

### Step 0.1: Check Each Task's `review_focus` Against the Spec
`review_focus` items reach the worker as an acceptance checklist, and workers follow the checklist over the spec. For every item, re-read the spec clause it covers and confirm the item keeps the clause's full condition. Example: the spec says "raise on conflicting reuse of the same key"; an item saying "identical postings replay, differing amounts raise" drops the other ways a reuse can conflict. Fix the item, or quote the spec clause in it. Also add every executable acceptance check (outcome command, `web_ui_validator.py` for HTML) to the task, because workers that run these themselves catch the defects a later reviewer would.

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
Dispatch in waves: a task is ready when every task in its `depends_on` is finished. Start up to 5 ready tasks at once; when a wave's tasks pass the gate, start the next wave. For each ready task in the current wave:
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
     - `DONE` or `DONE_WITH_CONCERNS`: Proceed to Step 1.5.

### Step 1.5a: Deterministic Gate (Always)
Run `goal_loop.py --cwd <WORKSPACE_DIR> --audit-task <TASK_ID>`, which also runs the task's verification command. Run the outcome command and, for HTML, `web_ui_validator.py`. Read any `DONE_WITH_CONCERNS` concern. If no reviewer subagent is required (Step 1.5b), record the result yourself:
```bash
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd <WORKSPACE_DIR> \
  --record-task <TASK_ID> --review-source self-check \
  --spec-verdict <PASS|FAIL> --critical-count <N> --important-count <M>
```
A failing check sends the task back to the same worker with the failing output (Rounds 1–3 of the fix loop below).

### Step 1.5b: Reviewer Subagent (`/discriminator-gate`) — Only When Needed
Spawn the separate reviewer only when at least one of these holds:
- Part of the acceptance cannot be checked by a command (judgment-heavy requirements, security-sensitive changes, ambiguous specs).
- Several parallel workers' branches will be merged against a shared contract.
- The user asked for an independent review.

Otherwise skip it. In the repo's benchmark (`benchmarks/RESULTS.md`, 18 single-worker runs with executable acceptance checks) the reviewer passed every task on round 1 and changed no shipped code, at about 2.2× the token cost of the worker alone.

When the reviewer runs:
1. Generate the deterministic diff review package on disk:
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" \
     --cwd <WORKSPACE_DIR> --review-package <TASK_ID> --base-sha <BASE_SHA>
   ```
2. Start the reviewer with two paths: the review package and the spec it judges against (`TASK_SPEC.md`, the issue text, or the design section in the task's `spec_ref`). The reviewer restates the requirement first (`/discriminator-gate` Step 1.5) and never writes to the workspace. It runs deterministic invariant verification (`--audit-task <TASK_ID>`) and evaluates `.swarm/reviews/<TASK_ID>-review.diff.md` across:
   - **Part 1 — Spec & Outcome Compliance:** `PASS | FAIL | UNVERIFIABLE` (checks `Missing`, `Extra / YAGNI`, `Misunderstood`, and `review_focus` test coverage).
   - **Part 2 — Code Quality Severity Buckets:** `Critical` (`critical_count > 0` blocks task), `Important` (`important_count > 0` blocks task), `Minor` (logged to `.swarm/deferred_minor_ledger.md`, never blocks).
3. Record the verdict with `goal_loop.py --record-task --review-source reviewer` (your verdict can only add failures; `BLOCKING_FAIL`s from the audit always count). If the task did not pass, execute the **5-Round Escalating Fix Loop**:
   - **Rounds 1–3:** Resume the **same worker** with only open `Critical` and `Important` findings; re-review strictly `FIX_BASE..HEAD` (`ADDRESSED | NOT ADDRESSED` + `New Breakage in the Fix Diff`).
   - **Rounds 4–5:** Retire the stalled worker and spawn a **fresh worker subagent** (`"A prior implementer attempted this task 3 times; these findings remain open. You own it now."`).
   - **Round 5 Breaker (`Ruling:`):** Stop at Round 5. Pick one `--ruling-type` (`OVERRIDE`, `SPLIT_TASK`, `RE_ARCHITECT_CONTRACT`, `ESCALATE_TO_USER`) and record `Ruling: <what you decided> — <why> — <what it costs if wrong>` via `goal_loop.py --record-task <TASK_ID> --ruling-type <TYPE> --ruling "..."`. Only `OVERRIDE` completes the task, and only with zero `BLOCKING_FAIL`s (see `/discriminator-gate`).

### Step 2: Git Worktree Merge Surgery (`/merge-surgeon`)
If workers ran in isolated branches/worktrees, merge verified branches cleanly while honoring `/contract-lock` interfaces and re-verifying post-merge tests.

### Step 2.5 (Lite Mode Exit Gate): Validator & Goal Verification (`--lite`)
When running in **Lite Mode**, skip Steps 3–7. Run the project's full test suite, then the Validator and Goal-Loop verification:
```bash
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd <WORKSPACE_DIR> --verify-goal
python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" --check-convergence --lite
```
If HTML/UI files exist, also run `scripts/web_ui_validator.py`. If the deliverable is a game or app binary, also run `scripts/quality_validator.py <binary> --timeout 10` (it smoke-tests binaries only). Once `--verify-goal` and `--check-convergence --lite` return `CONVERGED_NO_IMPROVEMENTS_NEEDED`, deliver the final summary.

**Release-level audit (when the user asks for one):** run `/triad-audit` and `/sota-web-scout` in parallel (reports go to `.swarm/epoch_1/`, since Lite is epoch 1; the scout needs network access). List every triad `CRITICAL` or `HIGH` finding, every scout `CRITICAL_GAP`, and every scout upgrade row with Net-ROI `HIGH` to the user. For each finding the user picks, add a task `AUDIT-<n>` with `goal_loop.py --add-task`, giving it the files and a verification command you write. The new tasks then go through Steps 1–2.5 in the same goal file; no re-initialisation is needed.

### Step 3 (Full Mode): Intermittent Epoch Report (`/epoch-planner`)
Confirm every Epoch <N> task is `VERIFIED_COMPLETE`, `COMPLETED_WITH_RULING`, or `SUPERSEDED` by finished tasks in `goal_loop.py --status` (tasks that are `BLOCKED_BY_RULING` go to the user), then generate `.swarm/reports/epoch_<N>_intermittent_report.md`.

### Steps 4–6 (Full Mode): Parallel Triad Audit (`/triad-audit`) + SOTA Web Scout (`/sota-web-scout`)
Spawn `rigor_auditor`, `safety_auditor`, `innovation_auditor`, and `sota_web_scout` in parallel to stress-test edge cases, security/resource safety, performance baselines (`/perf-benchmarker`), and external SOTA parity.

### Step 7 (Full Mode): Next-Epoch Adjusted Plan (`/epoch-planner`) & The 3-Epoch Funnel
Synthesize Triad Audit and SOTA findings into the next epoch's tasks in `.swarm/goal_loop.json` (including `review_focus` and `base_sha`):
- **Epoch 1 (Broad Exploration & Core Architecture):** End-to-end working vertical slice with verified AST wiring.
- **Epoch 2 (Deepening, Edge Cases & SOTA Parity):** Resolving Triad Audit findings, concurrency/error recovery, and high-ROI SOTA features.
- **Epoch 3 (Convergence, Polish & Deferred Minor Ledger Sweep):** Sweeping `.swarm/deferred_minor_ledger.md`, zeroing regressions, and running `/quality-validator` + `goal_loop.py --verify-goal`.
- **Epoch 4+ (Automatic Remediation Epochs):** Triggered automatically if `goal_loop.py --verify-goal` or `immortal_watcher.py --check-convergence` reports unfinished invariants.

---

## Red Flag Thought-Catchers (STOP Immediately If You Think Any of These)

- *"I'll spawn 4 workers right now without running `--preflight` because their task titles sound different."* -> **STOP.** Different task titles routinely touch the same `main.py`, `router.ts`, or `config.py`. Run `--preflight` first.
- *"I'll ask each worker to return a full 300-line walkthrough of its changes in its final message."* -> **STOP.** Multi-hundred-line subagent replies overflow the orchestrator context window by Epoch 2. Enforce the `< 15 lines` return contract and rely on `--review-package` on disk.
- *"A worker returned `DONE_WITH_CONCERNS`, so I'll just mark it `VERIFIED` without reading the concern."* -> **STOP.** Inspect the concern; if it cannot be settled by running a check, spawn the reviewer (Step 1.5b) before recording the task verdict.
- *"I'll spawn a reviewer for every task to be safe."* -> **STOP.** For single-worker tasks with executable acceptance checks the reviewer doubles cost and has not caught anything in testing. Spend the effort on better acceptance checks (Step 0.1) instead.
- *"The `review_focus` list covers the spec, so the worker can skip the spec."* -> **STOP.** Checklists that restate a spec clause narrowly make every worker implement the narrow version. Check each item against its clause (Step 0.1).

---

## Rationalization Excuse / Reality Table

| Common Orchestrator Excuse | Reality & Mandatory Action |
| :--- | :--- |
| *"We're in a hurry, so I'll skip the deterministic gate for Epoch 1 and audit everything in Epoch 3."* | Unwired modules and broken assumptions in Epoch 1 compound exponentially in Epoch 2. Every task must pass `--audit-task` and `--record-task` in its own epoch. |
| *"The reviewer found 3 Minor style issues, so I'll run a fix round now."* | Minor issues are logged to `.swarm/deferred_minor_ledger.md` and swept in Epoch 3. Never burn fix-loop rounds on Minor items in Epochs 1–2. |
| *"All 3 Epochs ran, so the swarm is done even though `--verify-goal` has 1 failing command."* | The 3-Epoch Funnel is a structure, not a permission slip to ship broken software. Spawn Remediation Epoch 4 until `--verify-goal` exits `0`. |
