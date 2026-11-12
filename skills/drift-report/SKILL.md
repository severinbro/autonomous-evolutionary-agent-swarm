---
name: drift-report
description: "Use when checking whether design documents under docs/designs/ and the live codebase have diverged after implementation, refactors, or PRs, or when reconciling outdated specs with current code."
---

# Spec-to-Code Drift Report (`/drift-report`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

You are the **Elephant** reconciling written design specifications (`docs/designs/*.md`) with the live repository. Ported from the Elephant-Goldfish Model's drift maintenance workflow (EGM, <https://github.com/google/elephant-goldfish-model>), paired with deterministic AST/file checks in `scripts/goal_loop.py` and harness-native polling (`$AGENT_SWARM_HOME/references/harness-polling.md`).

Never silently overwrite either the code or the design, and never write unresolved questions into a design or `plan.md`.

---

## Step 1: Run the Deterministic Structural Drift Scan

Scan all non-draft designs under `docs/designs/*.md` (and any design referenced by `.swarm/goal_loop.json`), or pass specific design paths:

```bash
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd <workspace> --drift-report
# Add --run-checks to also execute each design's Verification and Outcome commands:
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd <workspace> --drift-report --run-checks
```

The deterministic scan checks six drift categories:
- `MISSING_TARGET_FILE`: a `(Create)` or `(Modify)` file in `Files` is missing on disk.
- `LINGERING_DELETED_FILE`: a `(Delete)` file in `Files` still exists on disk.
- `MISSING_EXPORTED_SYMBOL`: a symbol in `Symbols` is missing from the target module's AST.
- `BROKEN_CALLER_WIRING`: a file in `Called by` no longer imports and invokes the module/symbol.
- `GOAL_LOOP_OUT_OF_SYNC` / `ORPHAN_GOAL_LOOP_TASK`: the design's tasks diverged from `.swarm/goal_loop.json`.
- `FAILING_VERIFICATION_CMD` / `FAILING_OUTCOME_CMD` (with `--run-checks`): a design check no longer passes.

---

## Step 2: Optional Semantic Drift Pass (Read-Only Goldfish)

When the structural scan is `CLEAN` or the user asks for a deeper architectural check, spawn one fresh read-only `codebase-details` Goldfish reviewer (Claude Code: `Agent` with `subagent_type: "goldfish"`; Antigravity: `define_subagent(..., enable_write_tools=False)` then `invoke_subagent`; Codex CLI: `spawn_agent` read-only; take the workspace SHA-256 snapshot before and after per `/goldfish-review`). Ask it to compare the design's `Technical Plan` prose and interfaces against the current files and report concrete divergences (`Severity / Affected scope / Finding and reason`). Save its report to `.swarm/design-reviews/<design>-drift.md`.

---

## Step 3: Poll the User via the Harness Polling Tool

If both Step 1 and Step 2 find zero drift, report `CLEAN` in two lines (noting whether `--run-checks` or the semantic Goldfish pass was skipped).

Otherwise, group related drift items and prompt the user **live** using the **active harness's native polling tool** (`ask_question` in Antigravity, `AskUserQuestion` in Claude Code, `request_user_input` in Codex CLI; see `$AGENT_SWARM_HOME/references/harness-polling.md`), placing `(Recommended)` first based on git history and test health:

1. **`Update design spec to match code`:** Code evolved intentionally and tests pass; reconcile `docs/designs/<name>.md` and record why under `## Resolved Decisions`.
2. **`Add remediation task to goal_loop.json`:** Code regressed or skipped a spec requirement; add a `DRIFT-<n>` task with a failing-first verification command and hand off to `/invoke-swarm`.
3. **`Re-import plan into goal_loop.json`:** Only `.swarm/goal_loop.json` is stale; show the `--import-design --dry-run` command list first and confirm via the harness polling tool before importing.

---

## Step 4: Re-Verify & Disclose Trade-Offs

Apply only the user-approved updates, re-run `goal_loop.py --drift-report` until `CLEAN` (when reconciling specs), and state explicitly in your summary what was checked, what was skipped (for example `--run-checks` or Draft designs), and any accepted trade-offs.

---

## Red Flags

- *"Code looks newer, so I'll update `docs/designs/foo.md` without asking."* → **STOP.** Only the user knows whether divergence was intentional evolution or an accidental regression. Poll via the harness polling tool first.
- *"I'll add an `## Open Questions` section to the design listing the drift."* → **STOP.** Never park questions in design or plan files; `--import-design` and `--drift-report` reject them.
