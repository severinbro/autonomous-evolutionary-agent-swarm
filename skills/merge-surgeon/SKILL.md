---
name: merge-surgeon
description: "Use when merging several parallel worker branches or worktrees, when a merge conflicts or tests fail after a merge, or when integration attempts keep failing and the conflict may be architectural."
disable-model-invocation: false
triggers: [user, model]
---

# Git Worktree Merge Surgeon (`/merge-surgeon`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

## Overview

Integrate approved parallel worker branches in dependency order while preserving locked contracts (`src/contracts/`), both workers' tested behaviors, and clean base-branch test health.

> [!IMPORTANT]
> ## The Iron Law
> ```
> NO BRANCH MERGE WITHOUT A PRE-MERGE SNAPSHOT, 4-PHASE ROOT-CAUSE CONFLICT INVESTIGATION, AND A FRESH POST-MERGE TEST SUITE PASS
> ```
> Never guess at conflict resolutions, delete one worker's feature to make tests pass, or leave the base branch in a failing state. If **3 merge/integration fix attempts fail** on a branch, restore the snapshot and escalate the architectural conflict immediately.

---

## 1. Sub-Agent Definition (`merge_surgeon`)

When multiple worker branches touch shared manifests (`package.json`, `Cargo.toml`, `pyproject.toml`), routers, or registries, the Orchestrator spawns `merge_surgeon` via `invoke_subagent`:
- `name`: `"merge_surgeon"`
- `description`: `"Git worktree integration specialist that merges approved worker branches in dependency order, resolves semantic and manifest conflicts via 4-phase root-cause analysis while preserving locked contracts, and verifies the integrated test suite."`
- `enable_write_tools`: `true`
- `enable_subagent_tools`: `false`

---

## 2. Deterministic Merge & Snapshot Rollback Protocol

1. **Create Epoch Pre-Merge Git Snapshot:**
   Before merging any branch in Epoch `<N>`, record an epoch-level rollback checkpoint:
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" \
     --snapshot-create "pre-merge-epoch-<N>"
   ```
2. **Order Branches by Dependency:**
   Merge foundational/data-model branches first, core domain logic second, and UI/entrypoint integration branches last.
3. **Pre-Merge Diff & Contract Verification:**
   Inspect each branch (`git diff main...<branch>`) and verify its task is `VERIFIED_COMPLETE` or `COMPLETED_WITH_RULING` in `goal_loop.py --status` and respects frozen signatures in `src/contracts/`.
4. **Per-Branch Snapshot & `--no-ff` Merge:**
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" \
     --snapshot-create "pre-merge-<branch>"
   git merge --no-ff <branch> -m "merge(swarm): integrate <branch> into Epoch <N>"
   ```
   - **Dependency Manifests (`package.json`, `pyproject.toml`, `Cargo.toml`):** Union dependencies from both branches cleanly and verify lockfile/environment consistency.
   - **Barrel / Export Files (`__init__.py`, `index.ts`, `mod.rs`):** Export symbols from both worker branches without shadowing.
   - **Semantic / Logic Conflicts or Post-Merge Test Failures:** Execute the **4-Phase Root-Cause Conflict Resolution Protocol** below.
5. **Immediate Post-Merge Test & Outcome Gate (Per Branch):**
   Run the full integrated test suite AND the project `--outcome-cmd` after **each** branch merge before moving to the next branch.
6. **Tag Milestone & Clean Up Worktrees:**
   ```bash
   git tag -f swarm-epoch-<N>
   python3 "$AGENT_SWARM_HOME/scripts/worktree_manager.py" cleanup <branch>
   ```

---

## 3. The 4-Phase Root-Cause Conflict Resolution Protocol (`systematic-debugging` Pattern)

Whenever a git merge conflict or a post-merge test failure occurs, you MUST complete Phases 1–4 in order:

### Phase 1: Root Cause & Provenance Investigation
1. **Read Complete Diffs & Stack Traces:** Run `git status`, `git diff --merge`, and `git log --merge -p <conflicted_file>`. When a post-merge test fails, read the entire traceback and exact line numbers (`path:line`).
2. **Trace Data Flow & Symbol Origin:** Identify what Worker A produced, what Worker B consumed, and how each interacts with `src/contracts/` and `.swarm/blueprint/behavioral_specs.md`.

### Phase 2: Contract & Pattern Analysis
1. **Compare Against Locked Contracts:** Check `src/contracts/` to determine which branch adheres to the locked signature and whether an adapter or union is required.
2. **List All Semantic Differences:** Enumerate state mutations, initialization order, config keys, and return types across both branches.

### Phase 3: Single Hypothesis & Minimal Integration Fix
1. **State Hypothesis Explicitly:** Record in `.swarm/epoch_<N>/merge_report.md`: *"Conflict/failure in `<file:line>` is caused by `<exact mismatch>`; adapting `<integration_point>` preserves both Worker A's `<feature_A>` and Worker B's `<feature_B>`."*
2. **Test Minimally:** Apply one targeted integration change at a time. Never delete a worker's feature or weaken/skip a test assertion.

### Phase 4: Verification & The 3-Fix Architectural Escalation Breaker
1. **Run Fresh Verification:** Execute the full test suite and `--outcome-cmd`.
2. **Count Fix Attempts (`Attempt 1..3`):**
   - **If Attempt `< 3` fails:** Return to Phase 1 using the new failure output.
   - **If `>= 3` Fix Attempts Fail (Architectural Escalation Breaker):**
     **STOP IMMEDIATELY.** Do NOT attempt Fix #4. Three failed integration fixes prove the two branches have an incompatible architectural assumption.
     1. Restore the clean pre-merge snapshot immediately:
        ```bash
        python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" \
          --snapshot-restore "pre-merge-<branch>"
        ```
     2. Record an explicit `Ruling: ARCHITECTURAL_MERGE_CONFLICT` in `.swarm/ledger.md` and `.swarm/epoch_<N>/merge_report.md` detailing the exact interface collision (`path:line`).
     3. Return `Status: BLOCKED` to the Orchestrator so `/contract-lock` can revise the shared interface before re-running the affected worker.

---

## 4. Red Flags — STOP and Follow Process

If you catch yourself thinking any of these, **STOP immediately** and return to Phase 1:
- *"I'll just take `--ours` or `--theirs` on this file to get the merge done quickly."*
- *"One worker's test is failing after merge; I'll relax or `@skip` that test assertion."*
- *"Fix #3 didn't work, let me just try one more quick tweak (Fix #4) in the shared module."*
- *"I'll merge all 4 branches first and run the test suite once at the very end."*
- *"I don't need a pre-merge snapshot for this branch; the diff looks tiny."*

---

## 5. Common Rationalizations

| Excuse | Reality |
| :--- | :--- |
| `"Batch-merging all branches before testing is faster"` | When 4 branches are merged at once and 12 tests break, you cannot isolate which branch caused the regression. Test after every single branch. |
| `"Accepting --theirs on the shared router is fine"` | `--theirs` silently deletes the earlier worker's routes/wiring, causing an `ORPHAN_UNWIRED_MODULE` failure in Triad Audit. |
| `"One more fix attempt (Attempt #4) will solve it"` | 3+ failed integration fixes indicate an architectural/contract mismatch. Restore the snapshot and escalate to the Orchestrator. |
| `"Relaxing the test threshold fixes the post-merge failure"` | Weakening a test hides a real behavioral regression. Fix the integration glue at the root cause or escalate. |
| `"Snapshots are overkill for a clean git merge"` | Semantic conflicts pass `git merge` cleanly with zero conflict markers while breaking runtime behavior. Always snapshot first. |

---

## 6. Zero-Context-Bloat Subagent Return Contract (`< 15 Lines`)

Write full merge diagnostics, conflict resolutions, and test logs to `.swarm/epoch_<N>/merge_report.md`, and return ONLY this `< 15 lines` summary to the Orchestrator:

```markdown
Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
Artifact: .swarm/epoch_<N>/merge_report.md | Milestone Tag: swarm-epoch-<N>
Branches Integrated (<K>/<Total>):
1. <branch-1> -> MERGED (commit <sha>, Conflicts: <0 or resolved at path:line>, Fix Attempts: <0-3>/3)
2. <branch-2> -> MERGED (commit <sha>, Conflicts: <0 or resolved at path:line>, Fix Attempts: <0-3>/3)
Post-Merge Verification: `<test_cmd>` -> PASS (<N> passed, 0 failed) | `<outcome_cmd>` -> PASS (exit 0)
Snapshots & Worktrees: Pre-merge snapshots verified; merged worktrees cleaned up
Escalations / Rulings: None (or `Ruling: ARCHITECTURAL_MERGE_CONFLICT` on <branch> restored to pre-merge-<branch>)
```
