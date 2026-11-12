---
name: goal-loop
description: "Use when work must continue until a stated goal is verifiably met: defining the goal, tasks, and sub-tasks in .swarm/goal_loop.json, auditing a task's wiring and stubs, recording review verdicts, or checking whether the goal is reached."
---

# Goal-Loop Engine (`/goal-loop`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

When the user invokes `/goal-loop` (or `/goal`), or when `/invoke-swarm` / `/discriminator-gate` executes task-level and goal-level verification, use `"$AGENT_SWARM_HOME/scripts/goal_loop.py"` to enforce hierarchical goal decomposition, context-slimmed file handoffs, AST-verified entrypoint wiring, and deterministic categorical gating (`PASS`/`FAIL`) until the desired outcome is reached.

---

## The Iron Laws of `/goal-loop`

```
1. NO COMPLETION WITHOUT DETERMINISTIC INVARIANT PASS + TWO-VERDICT GATE PASS.
2. CATEGORIES AND COUNTS DECIDE THE OUTCOME — NO REDUNDANT DECIMAL SCORES.
3. AN IMPORT WITHOUT AN AST CALL/ATTRIBUTE/NAME USAGE IS UNWIRED DEAD CODE (`BLOCKING_FAIL`).
4. SUBAGENTS READ FILES FROM DISK (`--task-brief` / `--review-package`) — NEVER PASTE WALLS OF TEXT INTO PROMPTS.
```

---

## Core Architecture: Deterministic Invariants + Categorical Gate

The `/goal-loop` engine eliminates fragile point-deduction arithmetic and redundant decimal scores, evaluating tasks directly through **Deterministic Invariants (`BLOCKING_FAIL` vs. `ADVISORY_WARN`)** and **Categorical Verdicts (`PASS` vs. `FAIL`)**:

### 1. Deterministic Invariants (`BLOCKING_FAIL` vs. `ADVISORY_WARN`)
Every automated scan in `goal_loop.py` classifies findings into two strict tiers:

- **`BLOCKING_FAIL` (Immediate `FAIL` Verdict, Status: `NEEDS_ITERATION`):**
  1. **Missing Target Files** or empty (`0-byte`) target files.
  2. **AST / Regex Wiring Violation (`wiring_contract`):** Target module is never imported by its declared caller (`must_be_called_by`), or is imported only at top-level without any active AST `Call`, `Attribute`, or `Name` reference outside the import node (`unused_import`), or fails to define its `exported_symbols`.
  3. **Outcome Command Failure:** Any `verification_commands` or `outcome_verification_cmds` exits with a non-zero code or times out.
  4. **Code & Test Authenticity Violation:**
     - Unconditional `NotImplementedError`, stub-only functions (`pass` / `...`), `TODO` / `FIXME` / `PLACEHOLDER` markers, mock-framework imports, or literal dummy/mock/placeholder return values in production code.
     - **Constant return next to a fake/stub comment** (`CONSTANT_RETURN_WITH_FAKE_COMMENT`, e.g., `return 1.25  # fake` or `# fake value for now\nreturn 42`).
     - **Mock-only test file** (`MOCK_ONLY_TEST_FILE`, test files that only assert on `MagicMock`/`AsyncMock`/`patch`/`.assert_called*` without asserting on real production outputs) or **vacuous test file** (`VACUOUS_TEST_FILE`, e.g., `assert True`).
     - Interfaces (`Protocol`, `@abstractmethod`, `src/contracts/`) are exempt from stub checks.

- **`ADVISORY_WARN` (Reported for Review, Does Not Block Alone):**
  1. Broad `except Exception:` blocks or `: any` / `as any` type annotations in production files.

### 2. Categorical Gate Evaluation (`evaluate_gate`)
When `goal_loop.py --audit-task <TASK_ID>` or `goal_loop.py --record-task <TASK_ID>` evaluates a task, the category and counts directly determine the verdict:

| Condition | Gate Verdict | Task Status |
| :--- | :---: | :--- |
| Any `BLOCKING_FAIL` invariant (`blocking_fails > 0`), `spec_verdict != "PASS"`, `critical_count > 0`, or `important_count > 0` | **`FAIL`** | **`NEEDS_ITERATION`** |
| `blocking_fails == 0` AND `spec_verdict == "PASS"` AND `critical_count == 0` AND `important_count == 0` | **`PASS`** | **`VERIFIED_COMPLETE`** |

### 3. Completion, Review & Rulings
- **The reviewer can only add failures.** `--record-task` records the reviewer verdict on top of the latest `--audit-task` (and runs the audit itself if the task was never audited). A `PASS` verdict never clears a `BLOCKING_FAIL`; only re-running `--audit-task` on fixed code does.
- **A task is finished only with both:** zero `BLOCKING_FAIL`s in a fresh audit, and a passing review (`PASS`, 0 Critical, 0 Important) or an `OVERRIDE` ruling. A task that passes the audit without a recorded review is `AWAITING_REVIEW`.
- **`--verify-goal` re-audits every task, including finished ones**, so a later change that breaks a finished task's wiring or tests reopens the goal. Its result lists every ruling under `rulings`.
- **Round 5 rulings need `--ruling-type`:** `OVERRIDE` (completes the task; rejected while any `BLOCKING_FAIL` remains), `SPLIT_TASK` (task becomes `SUPERSEDED`, finished when every task in `--superseded-by` is), `RE_ARCHITECT_CONTRACT` or `ESCALATE_TO_USER` (task is `BLOCKED_BY_RULING` until a new verdict is recorded). See `/discriminator-gate`.

---

## Context-Slimming File Handoffs (`superpowers` Pattern)

To prevent orchestrator context window bloat, `goal_loop.py` generates self-contained artifacts on disk in `.swarm/briefs/` and `.swarm/reviews/` so worker and reviewer subagents read from disk instead of receiving multi-thousand-line prompt pastes:

1. **Pre-Dispatch Conflict Scan (`--preflight`):**
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd <WORKSPACE_DIR> --preflight
   ```
   Scans `.swarm/goal_loop.json` before subagent dispatch and exits `1` on any failure:
   - **Fails:** shared `target_files` between tasks that can run in parallel, meaning both unfinished, same epoch, and neither in the other's `depends_on` chain (`OVERLAPPING_TARGET_FILES`; serialize with `depends_on` or move the shared code into a contract/foundation task); missing `target_files` or `verification_commands` (`MISSING_VERIFICATION_CMD`); `depends_on` naming an unknown task (`UNRESOLVED_DEPENDENCY`).
   - **Warns:** `wiring_contract.must_be_called_by` caller files not on disk yet (`MISSING_CALLER_FILE`); missing `review_focus`.

2. **Focused Worker Task Brief (`--task-brief <TASK_ID>`):**
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd <WORKSPACE_DIR> --task-brief TASK-001
   ```
   Writes `.swarm/briefs/<TASK_ID>-brief.md` containing **only** that task's objective, sub-tasks, `target_files`, `wiring_contract`, `review_focus` failure modes, `verification_commands`, and goal `non_negotiables`.

3. **Deterministic Diff Review Package (`--review-package <TASK_ID> [--base-sha <SHA>]`):**
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd <WORKSPACE_DIR> --review-package TASK-001 --base-sha <BASE_SHA>
   ```
   Writes `.swarm/reviews/<TASK_ID>-review.diff.md` containing:
   - The task's title, objective, `spec_ref` (when set), `wiring_contract`, and `review_focus` items (not the spec itself; pass the spec path to the reviewer separately).
   - `git log --oneline <BASE_SHA>..HEAD` and `git diff --stat <BASE_SHA>..HEAD`.
   - Full unified diff (`git diff <BASE_SHA>..HEAD`) plus untracked target file previews.
   - Pre-computed automated invariant summary (`BLOCKING_FAIL` vs. `ADVISORY_WARN`).

---

## Manifest Schema (`.swarm/goal_loop.json`)

Initialize a new manifest via `--init` (or `--init-goal "<Goal>"`):
```bash
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd <WORKSPACE_DIR> --init
```

Each task in `.swarm/goal_loop.json` includes:
- `id`: Unique task ID (e.g., `"TASK-001"`).
- `title` & `description`: Concrete engineering deliverable.
- `epoch`: Target epoch (`1`, `2`, `3`, or `4+` for remediation).
- `base_sha`: Git commit SHA captured when the task starts so `--review-package` diffs accurately.
- `review_focus`: Array of top implied failure modes that tests must explicitly verify. Workers treat it as their acceptance checklist, so each item must keep the full condition of the spec clause it covers (quote the clause when in doubt); a narrower item makes every worker implement the narrow version.
- `target_files`: Exact files the task creates or modifies.
- `wiring_contract`:
  - `must_be_called_by`: Entrypoint/orchestrator files that must import and actively invoke this module in their AST.
  - `exported_symbols`: Symbols that must be defined in `target_files` and invoked by callers.
- `verification_commands`: Shell commands that must exit `0`.
- `depends_on`: Task IDs that must finish first; `/invoke-swarm` dispatches in waves by it, and `--preflight` uses it to tell serialized from parallel tasks.
- `spec_ref`: For tasks imported from a design, `"<design path> § Task <ID>"`. Briefs and review packages print it; where they differ from the design, the design decides.
- `subtasks`: Atomic checklist items (`id`, `title`, `status`, `verification_cmd`).

**Importing a design (`--import-design <doc> [--dry-run] [--drop-missing]`):** reads the `### Goal` block and every `### Task <ID>: <title>` block under the design's `## Detailed Implementation Plan` (headings inside code fences are ignored) and writes them as tasks with `spec_ref`. Fields are column-0 bullets: `Files` (backticked paths tagged `(Create)`/`(Modify)`/`(Delete)`), `Depends on`, `Changes`, `Verification` (backticked command) are required; `Outcome`, `Review focus` (numbered list), `Called by` and `Symbols` are optional. All errors are reported together and nothing is written while any exists: missing fields, untagged files, non-fenced `Open Questions` headings or unresolved `[?]` question markers (Elephant questions belong in live harness polls via `ask_question` / `AskUserQuestion` / `request_user_input`, never inside plan/design files), unknown or cyclic dependencies, duplicate IDs, files shared by tasks with no dependency path, task IDs owned by another design, and tasks dropped from the plan (unless `--drop-missing`). A re-imported task whose fields changed goes back to `PENDING` with its gate results cleared. The output lists every new or changed command; confirm them with the user via the harness polling tool before a real import, because the gate will run them.

**Checking spec-to-code drift (`--drift-report [<doc> ...] [--run-checks]`):** compares non-draft designs under `docs/designs/*.md` (and `spec_ref` targets) against the live codebase and `.swarm/goal_loop.json`, flagging `MISSING_TARGET_FILE`, `LINGERING_DELETED_FILE`, `MISSING_EXPORTED_SYMBOL`, `BROKEN_CALLER_WIRING`, `GOAL_LOOP_OUT_OF_SYNC`, and (with `--run-checks`) failing `Verification`/`Outcome` commands. See `/drift-report`.

---

## CLI Reference (`scripts/goal_loop.py`)

```bash
# 1. Initialize or inspect the manifest
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd . --init
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd . --status

# 1b. Import a reviewed design's plan (dry run first; it lists every command the gate will run)
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd . --import-design docs/designs/<name>.md --dry-run
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd . --import-design docs/designs/<name>.md

# 1c. Add a single task by hand (an existing task keeps its objective when --objective is omitted)
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd . --add-task --task-id T2 --title "<title>" \
  --target-files src/a.py --validation-cmd "<cmd>" --depends-on T1

# 2. Run preflight conflict & dependency check before dispatching workers
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd . --preflight

# 3. Generate context-slimmed worker task brief (.swarm/reviews/TASK-001-brief.md)
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd . --task-brief TASK-001

# 4. Generate deterministic diff review package (.swarm/reviews/TASK-001-review.diff.md)
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd . --review-package TASK-001 --base-sha HEAD

# 5. Run deterministic invariant audit (AST wiring + authenticity + commands + Hard Cap score)
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd . --audit-task TASK-001

# 6. Record Two-Verdict Gate result, severity counts, or Round 5 Breaker Ruling
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd . \
  --record-task TASK-001 \
  --spec-verdict PASS \
  --critical-count 0 \
  --important-count 0 \
  --minor-count 1 \
  --notes "Minor naming suggestion deferred to ledger"

# 7. Record a Round 5 Breaker Ruling to .swarm/ledger.md (keep the reviewer's real open counts)
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd . \
  --record-task TASK-001 \
  --spec-verdict PASS \
  --critical-count 0 \
  --important-count 1 \
  --ruling-type OVERRIDE \
  --ruling "Accepted current retry backoff — matches RFC — costs 50ms extra on cold start if wrong"

# 8. Verify end-to-end goal convergence (every task, repo authenticity, and the root outcome command)
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd . --verify-goal

# 9. Check spec-to-code drift across docs/designs/*.md (add --run-checks to execute Verification/Outcome commands)
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd . --drift-report --run-checks
```

---

## Red Flag Thought-Catchers (STOP Immediately If You Think Any of These)

- *"The module is imported at the top of `main.py`, so it's wired."* -> **STOP.** `goal_loop.py` parses the caller's Python AST (`ast.parse`). If an imported symbol is never referenced in an `ast.Call`, `ast.Attribute`, or `ast.Name` node outside the import statement, it triggers `BLOCKING_FAIL` (`unused_import`) and fails the gate.
- *"There is one failing test, but the rest of the code looks clean, so I'll mark it complete."* -> **STOP.** Any `BLOCKING_FAIL` or `spec_verdict != PASS` immediately fails the categorical gate (`FAIL`).
- *"I'll paste the entire `.swarm/goal_loop.json` and 5 source files into the worker subagent prompt so it has full context."* -> **STOP.** Generate `.swarm/briefs/<TASK_ID>-brief.md` via `--task-brief <TASK_ID>` and pass the file path.

---

## Rationalization Excuse / Reality Table

| Common Agent Excuse | Reality & Mandatory Action |
| :--- | :--- |
| *"The helper function is tested in `test_helper.py`, so it participates in the outcome."* | Unit testing an isolated file is **0% outcome participation** if no runtime entrypoint calls it. Wire it into `must_be_called_by` and re-run `--audit-task`. |
| *"The `NotImplementedError` is only in an edge-case branch we don't hit yet."* | Unconditional `NotImplementedError` in production code is a `BLOCKING_FAIL`. Implement the branch or remove dead surface area (YAGNI). |
| *"Running `--preflight` is unnecessary for 3 small tasks."* | Overlapping `target_files` across parallel workers cause silent merge overwrites. Always run `--preflight` before dispatching workers. |
| *"The reviewer says PASS, so recording it will clear the audit's `BLOCKING_FAIL`s."* | The reviewer can only add failures. Fix the code, re-run `--audit-task`, then record the verdict. |
| *"I'll manually edit `.swarm/goal_loop.json` to set `status: VERIFIED`."* | Never hand-edit task statuses to bypass verification. Always run `--audit-task` and `--record-task` so deterministic invariants and ledgers stay synchronized. |
