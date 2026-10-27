---
name: contract-lock
description: "Use before dispatching parallel worker agents that share interfaces, schemas, or files, when their plan needs a preflight conflict check and frozen cross-module contracts, or when an existing codebase's behavior must be captured before changes."
disable-model-invocation: false
triggers: [user, model]
---

# Pre-Spawn Interface & Type Contract Lock (`/contract-lock`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

## Overview

Eliminate multi-agent integration collisions before parallel worktrees branch by running a deterministic pre-flight dependency check, extracting brownfield behavioral invariants, and freezing machine-checkable interface contracts (`src/contracts/`) and contract tests (`tests/test_contracts*`) on the base branch.

> [!IMPORTANT]
> ## The Iron Law
> ```
> NO PARALLEL WORKER SPAWNS WITHOUT LOCKED CONTRACTS AND A PASSING PRE-FLIGHT DEPENDENCY CHECK ON THE BASE BRANCH FIRST
> ```
> Spawning parallel worktree agents before running `goal_loop.py --preflight` and committing `src/contracts/` guarantees Step 3 signature collisions. Complete all steps below before calling `invoke_subagent` for implementation workers.

---

## 1. Pre-Flight Shared-File & Interface Dependency Check (`--preflight`)

Before extracting or freezing contracts, verify that planned parallel tasks in `.swarm/goal_loop.json` (or `PLAN.md`) have clean file ownership boundaries and explicit cross-task interface declarations:

```bash
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --preflight
```

| Observable `--preflight` Outcome | Required Action Before Proceeding |
| :--- | :--- |
| **`PASS` (exit `0`)** | Proceed to Step 2 (`spec-miner` & Contract File creation). |
| **`FAIL: OVERLAPPING_TARGET_FILES` between parallel tasks** | Extract shared types/registries into `src/contracts/` or assign the shared file to a single foundational task before parallel branching. |
| **Manual check (not automated): dependent tasks lack exact `Consumes` / `Produces` signatures** | Define exact function names, parameter types, and return types in `src/contracts/` and update `.swarm/goal_loop.json` before spawning workers. |

---

## 2. Contract Lock, Brownfield Spec-Mining & Search-First Workflow

1. **Brownfield `spec-miner` Behavioral Extraction (Existing Repositories Only):**
   When running on an existing codebase that lacks formal behavioral specs, extract a flat ledger of existing behavioral assertions using the token-budgeted **Sample $\rightarrow$ Expand $\rightarrow$ Defer** strategy:
   - **Sample (Entrypoints First):** Read routers, controllers, CLI entrypoints, and public facades (where ~70% of behavioral assertions live). Record every **Requirement (`WHEN <trigger> -> THEN <outcome>`)** and **Invariant (`ALWAYS TRUE: <property>`)** with `path:line` citations in `.swarm/blueprint/behavioral_specs.md`.
   - **Expand (1-Level Call Chain, Max 15 Files):** Trace 1 level down the call chain to verify critical invariants; stop after 3 consecutive files yield no new invariants or at 15 files per capability.
   - **Defer:** List any remaining unread files in `<!-- deferred: file1, file2 -->` at the bottom of `.swarm/blueprint/behavioral_specs.md`.
2. **`/search-first` Build-vs-Adopt Package Check:**
   Before specifying custom utility or infrastructure interfaces in `src/contracts/`, check whether the language standard library or a well-maintained, permissive (`MIT` / `Apache-2.0`) package on PyPI/npm/crates.io already solves the problem:
   - **Adopt As-Is:** Exact match, well-maintained, permissive license $\rightarrow$ use directly instead of writing custom code.
   - **Extend / Wrap:** Partial match $\rightarrow$ wrap behind a thin typed interface in `src/contracts/`.
   - **Build Custom:** Core domain differentiator or no clean package exists $\rightarrow$ define custom contract and implement module.
3. **Identify Cross-Module Boundaries:**
   Inspect the current epoch's implementation plan (`PLAN.md`, `.swarm/goal_loop.json`, or `.swarm/epoch_<N>/adjusted_plan.md`) and list every data structure, function signature, event payload, IPC message, or REST/GraphQL/WebSocket schema shared between two or more worker tasks.
4. **Write Machine-Checkable Contract Files:**
   Create or update the shared contract module in the repository before branching:
   - **Python:** `src/contracts/` (using `typing.Protocol`, `@dataclass(frozen=True)`, or `pydantic.BaseModel` with explicit field types—never untyped `dict` or `Any`).
   - **TypeScript / JavaScript:** `src/contracts/index.ts` (exported `interface` and `type` definitions, or JSON Schema / Zod schemas).
   - **Rust / C++ / C#:** Shared trait/header/interface files (`src/contracts.rs`, `include/contracts.hpp`, `Contracts/ISubsystem.cs`).
5. **Write & Run a Fast Contract & Behavioral Invariant Test:**
   Create and execute a fast contract test (`pytest tests/test_contracts.py` or `npm run typecheck`) that verifies type/schema conformance and brownfield `WHEN -> THEN` invariants before committing.
6. **Commit & Freeze on the Base Branch:**
   ```bash
   git add src/contracts* tests/test_contracts* .swarm/blueprint/behavioral_specs.md
   git commit -m "chore(contracts): lock Epoch <N> cross-module interfaces"
   ```

---

## 3. Enforcement Rule for Worker Sub-Agents & Discriminator

* **Worker Dispatch Mandate:** Every worker prompt must include:
  > *"Shared interfaces in `src/contracts/` are FROZEN. Import and implement against these exact types. Do not rename, remove, or alter shared contract signatures without explicit Orchestrator approval."*
* **Automated Discriminator Config/Contract Protection:** During Step 1.5 (`/discriminator-gate`), `immortal_watcher.py --record-review` automatically scans `git diff main...<worker-branch>` for unauthorized edits to `src/contracts/` or linter/typechecker configs and records a **`BLOCKING_FAIL`** (task hard-capped at `6.0`) unless `--allow-config-edits` was explicitly granted.

---

## 4. Red Flags — STOP and Follow Process

If you catch yourself thinking any of these, **STOP immediately** and complete the Contract Lock workflow:
- *"There are only 2 or 3 workers, we can reconcile field names during the Step 3 merge."*
- *"I'll skip `goal_loop.py --preflight` because the task descriptions already look separate."*
- *"I'll put `data: dict[str, Any]` in `src/contracts/` for now so workers have flexibility."*
- *"Committing contract tests before spawning workers takes too much setup time."*
- *"A worker needs a different signature; I'll let the worker edit `src/contracts/` directly on its branch."*

---

## 5. Common Rationalizations

| Excuse | Reality |
| :--- | :--- |
| `"Workers can align interfaces during Step 3 merge"` | Uncoordinated workers invent incompatible field names (`user_id: int` vs `userId: str`), turning Step 3 into a full rewrite. Lock first. |
| `"Using dict[str, Any] in contracts is faster"` | Untyped dicts hide signature mismatches until runtime integration fails. Explicit fields and return types are mandatory. |
| `"Skipping --preflight saves 30 seconds"` | Silent file-ownership collisions cause git merge conflicts across worktrees that cost 20+ minutes to untangle. |
| `"Brownfield spec-mining isn't needed for a small feature"` | Without locked `WHEN -> THEN` behavioral specs, parallel workers silently break existing CLI/API invariants. |
| `"Just let Worker B tweak src/contracts/ in its worktree"` | Branch-local contract edits break Worker A on merge and trigger an automatic `BLOCKING_FAIL` for contract tampering. |

---

## 6. Zero-Context-Bloat Subagent Return Contract (`< 15 Lines`)

Write full behavioral specs to `.swarm/blueprint/behavioral_specs.md` and contract code to `src/contracts/`, then return ONLY this `< 15 lines` summary to the Orchestrator:

```markdown
Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
Pre-Flight Check: goal_loop.py --preflight -> PASS (0 file ownership collisions)
Locked Contract Files: <src/contracts/...> (commit <short-sha>)
Contract Verification: <pytest tests/test_contracts.py | npm run typecheck> -> PASS (<N> assertions)
Brownfield Invariants Mined: <M> WHEN->THEN rules in .swarm/blueprint/behavioral_specs.md
Exported Interfaces Locked:
1. `<InterfaceOrClass1>: <method_signature>`
2. `<InterfaceOrClass2>: <method_signature>`
Concerns / Blockers: None (or 1-line description)
```
