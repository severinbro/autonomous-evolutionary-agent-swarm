---
name: epoch-planner
description: "Use when an epoch of a swarm run has finished and needs its intermittent report, or when audit and state-of-the-art findings must become the next epoch's tasks in .swarm/goal_loop.json."
---

# Epoch Planner & Intermittent Report Generator (`/epoch-planner`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

When the user invokes `/epoch-planner`, or when `/invoke-swarm` reaches **Step 3 (Intermittent Epoch Report)** or **Step 7 (Next-Epoch Adjusted Implementation Plan)**, execute this skill.

Rather than relying on vague instructions ("write a thorough plan"), `/epoch-planner` enforces a **Positive Output Contract ("Match the Form to the Failure")**: every report and plan must contain exact, verifiable sections in strict order, and every planned task must populate `review_focus` (implied failure modes pinned to tests) and `base_sha` in `.swarm/goal_loop.json`.

---

## The Iron Laws of `/epoch-planner`

```
1. MATCH THE FORM TO THE FAILURE — FOLLOW THE POSITIVE OUTPUT CONTRACT SECTIONS IN EXACT ORDER.
2. EVERY PLANNED TASK MUST INCLUDE `review_focus` (TOP IMPLIED FAILURE MODES PINNED TO CONCRETE TESTS).
3. EVERY PLANNED TASK MUST DECLARE `wiring_contract` (`must_be_called_by` + `exported_symbols`) AND `base_sha`.
4. EPOCH 3 MUST EXPLICITLY SWEEP `.swarm/deferred_minor_ledger.md` AND AUDIT `.swarm/ledger.md` BREAKER RULINGS.
```

---

## Deliverable 1: Intermittent Epoch Report (Step 3 of `/invoke-swarm`)

Write `.swarm/reports/epoch_<N>_intermittent_report.md` using these exact 5 sections in order:

```markdown
# Epoch <N> Intermittent Report

## 1. Deterministic Convergence Snapshot
- **Epoch Gate Status:** `CONVERGED | INCOMPLETE` (`CONVERGED` when every Epoch <N> task is `VERIFIED_COMPLETE`, `COMPLETED_WITH_RULING`, or `SUPERSEDED` by finished tasks in `goal_loop.py --status`)
- **Base -> Head Commit Range:** `<EPOCH_START_SHA>..<HEAD_SHA>`
- **Task Hard-Cap Ledger:**
  | Task ID | Title | Spec Verdict | Blocking Fails | Critical / Important / Minor | Hard-Cap Score | Fix Rounds Used |
  | :--- | :--- | :---: | :---: | :---: | :---: | :---: |

## 2. AST & Runtime Wiring Matrix
| Module (`target_files`) | Exported Symbols | Verified Caller (`must_be_called_by`) | Call Site (`file:line`) | Outcome Command Exit Code |
| :--- | :--- | :--- | :--- | :---: |

## 3. Breaker Rulings & Escalations Recorded (`.swarm/ledger.md`)
- List every Round 4 fresh-worker escalation and Round 5 Breaker `Ruling:` (with its `OVERRIDE` / `SPLIT_TASK` / `RE_ARCHITECT_CONTRACT` / `ESCALATE_TO_USER` type) recorded during Epoch <N>, or `"None — all tasks converged within Rounds 1–3."`

## 4. Deferred Minor Ledger Delta (`.swarm/deferred_minor_ledger.md`)
- Count and bullet summary of `Minor` findings deferred during Epoch <N> for the Epoch 3 polish sweep.

## 5. Open Risks Entering Triad Audit (Steps 4–6)
- Top 3 concrete technical, concurrency, security, or performance hypotheses for `rigor_auditor`, `safety_auditor`, and `innovation_auditor` to stress-test next.
```

---

## Deliverable 2: Next-Epoch Adjusted Implementation Plan (Step 7 of `/invoke-swarm`)

After Triad Audit (`/triad-audit`) and SOTA Web Scout (`/sota-web-scout`) complete, write `.swarm/plans/epoch_<N+1>_plan.md` using these exact 6 sections in order, and synchronize the new tasks into `.swarm/goal_loop.json`:

```markdown
# Epoch <N+1> Adjusted Implementation Plan

## 1. Funnel Stage & Scope Gate
- **Current Funnel Stage:**
  - `Epoch 1 (Broad Exploration & Vertical Architecture)`
  - `Epoch 2 (Deepening, Edge Cases & High-ROI SOTA Integration)`
  - `Epoch 3 (Convergence, Regression Lock & Deferred Minor Sweep)`
  - `Epoch 4+ (Targeted Goal-Loop Remediation)`
- **Explicit Out-of-Scope (YAGNI Guardrails):** Bullet list of low-ROI or speculative features explicitly rejected for this epoch.

## 2. Triad & SOTA Findings Disposition Table
| Source (`Rigor` / `Safety` / `Innovation` / `SOTA` / `Minor Ledger`) | Finding Summary | Severity (`Critical` / `Important` / `High-ROI` / `Minor`) | Assigned Task ID in Epoch <N+1> |
| :--- | :--- | :---: | :---: |

## 3. Review Focus (Top 5 Implied Failure Modes)
Identify the **top 5 most likely failure modes** implied by the changes in Epoch <N+1> (e.g., partial write under crash, stale cache after config reload, race condition on concurrent cancel, off-by-one window boundary, unhandled non-zero subprocess exit) and pin each one to a specific task test:
1. **Failure Mode 1:** `<description>` -> **Pinned Task & Test:** `<TASK_ID>` (`<exact test command / test name>`)
2. **Failure Mode 2:** `<description>` -> **Pinned Task & Test:** `<TASK_ID>` (`<exact test command / test name>`)
3. **Failure Mode 3:** `<description>` -> **Pinned Task & Test:** `<TASK_ID>` (`<exact test command / test name>`)
4. **Failure Mode 4:** `<description>` -> **Pinned Task & Test:** `<TASK_ID>` (`<exact test command / test name>`)
5. **Failure Mode 5:** `<description>` -> **Pinned Task & Test:** `<TASK_ID>` (`<exact test command / test name>`)

## 4. Task Specifications & Wiring Contracts
For each task (`TASK-00X`), specify:
- **Title & Objective**
- **`base_sha`:** Current `HEAD` commit SHA (`git rev-parse HEAD`).
- **`target_files`:** Exact files to create/modify (verified disjoint across parallel tasks via `goal_loop.py --preflight`).
- **`wiring_contract`:** `must_be_called_by` entrypoint files + `exported_symbols`.
- **`review_focus`:** Failure modes from Section 3 assigned to this task.
- **`verification_commands`:** Exact shell commands that exit `0` only when the behavior and failure modes are proven.

## 5. Dependency DAG & Parallel Dispatch Waves
- **Wave 1 (Parallel):** Disjoint tasks with zero file overlap (`goal_loop.py --preflight` clean).
- **Wave 2 (Dependent / Integration):** Tasks that depend on Wave 1 outputs.

## 6. Preflight & Blueprint Verification Stamp
- Output of `python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd <WORKSPACE_DIR> --preflight`
- Output of `python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd <WORKSPACE_DIR> --verify-blueprint`
```

---

## Synchronizing Tasks into `.swarm/goal_loop.json`

Every task added to `.swarm/goal_loop.json` for Epoch `<N+1>` must include `base_sha` and `review_focus` so `goal_loop.py --task-brief <TASK_ID>` and `goal_loop.py --review-package <TASK_ID>` surface them automatically to workers and reviewers:

```json
{
  "id": "TASK-004",
  "title": "Harden retry backoff and sweep deferred minor ledger",
  "description": "Resolve Safety Auditor timeout edge case and clean up deferred minor items.",
  "epoch": 2,
  "status": "PENDING",
  "depends_on": ["TASK-001"],
  "base_sha": "HEAD",
  "review_focus": [
    "Verify jittered backoff caps at max_delay_ms and never blocks event loop on cancellation",
    "Ensure zero unused imports remain after refactoring retry helper"
  ],
  "target_files": ["src/retry.py"],
  "wiring_contract": {
    "must_be_called_by": ["src/main.py"],
    "exported_symbols": ["execute_with_retry"]
  },
  "verification_commands": ["pytest -q tests/test_retry.py"]
}
```

Always run `--preflight` and `--verify-blueprint` immediately after updating `.swarm/goal_loop.json`.

---

## Red Flag Thought-Catchers (STOP Immediately If You Think Any of These)

- *"I'll write a free-form narrative plan instead of filling out the 6 Positive Output Contract sections."* -> **STOP.** Free-form plans omit failure modes, wiring callers, and file overlap checks. Follow the exact 6-section template.
- *"I'll leave `review_focus` empty and let the reviewer figure out what edge cases matter."* -> **STOP.** Every planned task must include concrete `review_focus` failure modes pinned to tests.
- *"It's Epoch 3, so I'll add 4 brand-new experimental architecture rewrites."* -> **STOP.** Respect the 3-Epoch Funnel: Epoch 3 is strictly for convergence, regression locking, and sweeping `.swarm/deferred_minor_ledger.md`.

---

## Rationalization Excuse / Reality Table

| Common Planner Excuse | Reality & Mandatory Action |
| :--- | :--- |
| *"Triad Audit found an `Important` race condition, but I'll just mention it in prose instead of creating a task in `goal_loop.json`."* | Anything not tracked as a task with a `verification_command` in `.swarm/goal_loop.json` will be ignored by workers. Map every `Critical` / `Important` Triad finding in the Section 2 Disposition Table to a task ID. |
| *"Two tasks in Wave 1 both edit `src/server.py`, but they edit different functions so it's fine."* | Concurrent edits to the same file in shared workspaces cause lost writes. Run `goal_loop.py --preflight` and either serialize them (`depends_on`) or mandate worktree isolation. |
| *"We can ignore `.swarm/deferred_minor_ledger.md` in Epoch 3."* | Deferred `Minor` items are a promise made during Epochs 1–2 to protect velocity without sacrificing final polish. Sweep them explicitly in an Epoch 3 task. |
