---
name: discriminator-gate
description: "Use when a worker agent reports a task done and its diff must be reviewed before it counts as complete, when deciding whether review findings block, or when a fix loop is stuck and needs escalation or a Round 5 ruling."
---

# Discriminator Gate & 5-Round Escalating Fix Loop (`/discriminator-gate`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

When the user invokes `/discriminator-gate`, or when `/invoke-swarm` reaches **Step 1.5** after a worker subagent completes a task, execute this skill to audit the implementation. The Discriminator Gate operates on a **Hybrid Two-Verdict Categorical Gate + Hard-Cap Rubric** paired with a **5-Round Escalating Fix Loop**.

---

## The Iron Laws of `/discriminator-gate`

```
1. NEVER TRUST THE WORKER'S SELF-REPORT — INSPECT THE DIFF PACKAGE AND RUN THE AUDIT.
2. TWO INDEPENDENT VERDICTS: SPEC COMPLIANCE (`PASS` ONLY) AND CODE QUALITY (`Critical=0, Important=0`).
3. MINOR FINDINGS NEVER BLOCK A TASK OR TRIGGER A FIX ROUND — DEFER THEM TO `.swarm/deferred_minor_ledger.md`.
4. SCOPED RE-REVIEW (`FIX_BASE..HEAD`) MAY ONLY CHECK PRIOR OPEN FINDINGS AND NEW BREAKAGE IN THE FIX DIFF — NO MOVING GOALPOSTS.
5. ROUND 4 ESCALATES TO A FRESH WORKER; ROUND 5 TRIGGERS AN ORCHESTRATOR BREAKER `Ruling:` IN `.swarm/ledger.md`.
```

---

## Step 1: Generate the Deterministic Review Package (Zero Prompt Bloat)

Before spawning or running the `discriminator` reviewer, generate the deterministic review artifact on disk:

```bash
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" \
  --cwd <WORKSPACE_DIR> \
  --review-package <TASK_ID> \
  --base-sha <BASE_SHA>
```

This creates `.swarm/reviews/<TASK_ID>-review.diff.md` containing:
- The exact task specification, `wiring_contract`, and `review_focus` failure modes from `.swarm/goal_loop.json`.
- `git log --oneline <BASE_SHA>..HEAD` and `git diff --stat <BASE_SHA>..HEAD`.
- The full unified diff (`git diff <BASE_SHA>..HEAD`) and untracked file previews.
- The pre-computed **Deterministic Invariant Audit** (`BLOCKING_FAIL` vs. `ADVISORY_WARN`).

Pass **only the path** `.swarm/reviews/<TASK_ID>-review.diff.md` to the `discriminator` subagent—never paste raw diffs into the prompt.

---

## Step 2: Two-Verdict Categorical Evaluation + Hard-Cap Rubric

The `discriminator` evaluates `.swarm/reviews/<TASK_ID>-review.diff.md` and live execution using two independent verdicts:

### Verdict Part 1: Spec & Outcome Compliance (`PASS` | `FAIL` | `UNVERIFIABLE`)
Checks whether the code built what was requested—nothing less, nothing extra:
- **Missing Requirements:** Did the worker skip any requirement, sub-task, or `wiring_contract` caller integration?
- **Extra / Unrequested Scope (YAGNI Violation):** Did the worker build unrequested abstractions, unused config flags, or speculative features outside the task brief?
- **Misunderstood Requirement:** Did the worker solve the wrong problem or wire into the wrong entrypoint?
- **Review Focus Proof:** For every item in the task's `review_focus` list, is there a concrete, passing automated test that would fail if that failure mode regressed?

### Verdict Part 2: Code Quality Severity Buckets (`Approved` | `Needs Fixes`)
Every code quality, security, concurrency, or resource-lifecycle issue must be categorized into one of three strict severity buckets with `file:line` citations:

| Severity Bucket | Definition | Hard-Cap & Loop Impact |
| :--- | :--- | :--- |
| **`Critical` (Must Fix)** | Any `BLOCKING_FAIL` invariant (missing/empty files, broken AST wiring / `unused_import`, failing verification command, stub/TODO/`NotImplementedError`), data corruption, security flaw, crash, or race condition. | **Hard-caps score at `<= 6.0`**. Blocks task immediately (`NEEDS_ITERATION`). |
| **`Important` (Should Fix)** | Architectural boundary violation, missing error recovery on I/O boundaries, resource leak, or unverified `review_focus` edge case. | **Hard-caps score at `<= 7.0`**. Blocks task until fixed (`NEEDS_ITERATION`). |
| **`Minor` (Deferred to Ledger)** | Naming polish, docstring tweaks, minor stylistic cleanup, or micro-optimizations. | **Does NOT block.** Appended to `.swarm/deferred_minor_ledger.md` for Epoch 3 polish. **Forbidden from triggering a fix loop.** |

### Recording the Verdict
Record the evaluation deterministically via `goal_loop.py --record-task`:
```bash
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" \
  --cwd <WORKSPACE_DIR> \
  --record-task <TASK_ID> \
  --spec-verdict <PASS|FAIL|UNVERIFIABLE> \
  --critical-count <N> \
  --important-count <M> \
  --minor-count <K> \
  --notes "<concise summary of open Critical/Important items or deferred Minor items>"
```
`--record-task` runs the deterministic audit itself if the task was never audited. Your verdict can only add failures: `BLOCKING_FAIL`s from the latest `--audit-task` always count, a `PASS` cannot clear them, and only re-running `--audit-task` on fixed code does.

Then update the worker's round counter in `immortal_watcher.py`. It applies the same gate and tracks rounds only: record Minor findings and rulings with `goal_loop.py` alone, or they are logged twice:
```bash
python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" \
  --record-review <WORKER_ID> \
  --impl-score <HARD_CAP_SCORE> --goal-score <HARD_CAP_SCORE> \
  --spec-verdict <PASS|FAIL|UNVERIFIABLE> \
  --critical-flaws <N> --important-flaws <M>
```

---

## Step 3: The 5-Round Escalating Fix Loop & Scoped Re-Review

When the gate fails (any `BLOCKING_FAIL`, `spec_verdict != PASS`, `Critical > 0`, or `Important > 0`), execute the **5-Round Escalating Fix Loop**:

### Rounds 1–3: Same Worker Subagent + Scoped Re-Review (`FIX_BASE..HEAD`)
1. Record the pre-fix commit SHA as `FIX_BASE=$(git rev-parse HEAD)`.
2. Send a targeted fix prompt to the **same worker subagent** listing **only** the open `Critical` and `Important` findings (with `file:line` and concrete verification criteria). Never include `Minor` findings.
3. **Scoped Re-Review Contract (`FIX_BASE..HEAD`):**
   When the worker returns, the `discriminator` inspects **only** `git diff $FIX_BASE..HEAD` and answers strictly two questions:
   - **1. Prior Open Issues (`ADDRESSED` | `NOT ADDRESSED`):** For each numbered `Critical` / `Important` finding from the previous round, did the fix diff actually resolve it?
   - **2. New Breakage in the Fix Diff:** Did the changes in `FIX_BASE..HEAD` introduce a new bug, regression, or broken caller in the touched lines?
   - **Anti-Goalpost-Moving Rule:** The reviewer is **strictly forbidden** from inventing brand-new style critiques or complaining about pre-existing code outside `FIX_BASE..HEAD` that it failed to flag in Round 1.

### Rounds 4–5: Escalation to a Fresh Worker Subagent
If any `Critical` or `Important` finding remains open after **Round 3**:
1. The original worker subagent's context is either polluted or stuck in a local minimum. **Retire the original worker.**
2. Spawn a **fresh worker subagent** with a clean context window, passing `.swarm/briefs/<TASK_ID>-brief.md` and the exact remaining open findings:
   > *"A prior implementer attempted this task 3 times; these specific Critical/Important findings remain open. Inspect the current state of the target files, resolve these exact findings without breaking existing passing tests, and verify. You own it now."*
3. Run Scoped Re-Review (`FIX_BASE..HEAD`) for Round 4 and (if needed) Round 5.

### Round 5 Breaker (`Ruling:` in `.swarm/ledger.md`)
If the task still has not converged after **Round 5**:
1. **STOP LOOPING.** Do not run a 6th round.
2. Inspect the disputed findings yourself and pick exactly one ruling type. A ruling settles a disagreement between agents; it never overturns the deterministic audit:

   | `--ruling-type` | Use When | Effect |
   | :--- | :--- | :--- |
   | `OVERRIDE` | The open Critical/Important findings are reviewer overreach or false positives, and `--audit-task` reports zero `BLOCKING_FAIL`s. | Task becomes `COMPLETED_WITH_RULING` and is listed in the `--verify-goal` result. Rejected while any `BLOCKING_FAIL` remains. |
   | `SPLIT_TASK` | The task is too large to converge. Add the smaller tasks to `.swarm/goal_loop.json` first. | Task becomes `SUPERSEDED` and counts as finished once every task in `--superseded-by` is finished. |
   | `RE_ARCHITECT_CONTRACT` | The findings trace back to a flawed interface or contract. | Task is `BLOCKED_BY_RULING` until `/contract-lock` revises the contract and a new verdict is recorded. |
   | `ESCALATE_TO_USER` | The dispute needs a product decision. | Task is `BLOCKED_BY_RULING` until the user decides and a new verdict is recorded. |

3. Record the ruling with the reviewer's actual open counts; never rewrite them to `0`:
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" \
     --cwd <WORKSPACE_DIR> \
     --record-task <TASK_ID> \
     --spec-verdict <PASS|FAIL|UNVERIFIABLE> \
     --critical-count <N> \
     --important-count <M> \
     --ruling-type <OVERRIDE|SPLIT_TASK|RE_ARCHITECT_CONTRACT|ESCALATE_TO_USER> \
     --ruling "Ruling: <what you decided> — <why> — <what it costs if wrong>"
   # SPLIT_TASK also needs: --superseded-by TASK-004,TASK-005
   ```

---

## Red Flag Thought-Catchers (STOP Immediately If You Think Any of These)

- *"Round 1 passed Critical and Important, let me send the worker back just to clean up these 2 Minor naming issues."* -> **STOP.** `Minor` findings NEVER trigger a fix round. Record them with `--minor-count` so they are logged to `.swarm/deferred_minor_ledger.md`.
- *"While re-reviewing Round 2's fix diff, I noticed another function 200 lines away that could be refactored."* -> **STOP.** Scoped Re-Review (`FIX_BASE..HEAD`) forbids moving the goalposts onto untouched lines.
- *"The worker failed 3 times, let me send it a 4th message with more exclamation marks."* -> **STOP.** Round 4 MUST escalate to a **fresh worker subagent** with clean context.
- *"We're on Round 6 and the reviewer and worker still disagree on an edge case."* -> **STOP.** Never exceed 5 rounds. Invoke the Round 5 Breaker and write a `Ruling:` to `.swarm/ledger.md`.

---

## Rationalization Excuse / Reality Table

| Common Reviewer / Orchestrator Excuse | Reality & Mandatory Action |
| :--- | :--- |
| *"The worker reported `Status: DONE` and said all tests pass, so I can skip `--review-package`."* | Workers frequently miss unwired callers (`unused_import`) or stub branches. Always generate `--review-package` and run `--audit-task`. |
| *"The code has an `Important` resource leak, but overall it's really solid so I'll give it an 8.2."* | Any `Important` finding hard-caps the score at `<= 7.0`. Either it is genuinely `Important` (cap at `7.0` and fix it) or it is `Minor` (defer to `.swarm/deferred_minor_ledger.md`). |
| *"The worker added a cool extra plugin loader nobody asked for—bonus points!"* | Unrequested features violate `Part 1: Spec Compliance` (Extra / YAGNI Violation) and add untested attack surface. Flag as `Important` or `FAIL` Spec Compliance. |
| *"I'll keep looping the same subagent for 8 rounds until it gets it right."* | After 3 rounds, context pollution degrades subagent reasoning. Escalate to a fresh worker at Round 4 and enforce the Breaker `Ruling:` at Round 5. |
