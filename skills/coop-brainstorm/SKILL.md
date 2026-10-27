---
name: coop-brainstorm
description: "Use when planning features, architecture, or execution tasks together with the user before code is written, including turning research reports into a locked plan and a seeded .swarm/goal_loop.json. Runs standalone or as Checkpoint 1 of /product-discovery."
disable-model-invocation: false
triggers: [user, model]
---

# Cooperative Brainstorming & Product Architecture Ideation (`/coop-brainstorm`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

## Overview

Collaborate with your human partner to converge on high-ROI innovation hypotheses, a 3-Epoch feature matrix with explicit entrypoint wiring, a software architecture blueprint, and a 5-item `## Review Focus` failure-mode test plan before Epoch 1 implementation begins.

**Core principle:** Read existing code and discovery artifacts before asking; clarify open requirements one single-sentence question at a time; lock concrete interfaces, entrypoint wiring paths, and implied failure-mode tests with zero placeholders (`TBD`/`TODO`).

---

## 1. Look Before You Ask & Single-Question Clarification Protocol

1. **Read Context First:** Inspect the repository (`src/`, tests, manifests, `docs/`) and any existing discovery blueprints before your first message:
   - `.swarm/blueprint/deep_research_report.md` & `.swarm/sota/sota_knowledge_base.md`
   - `.swarm/blueprint/market_research_report.md`
   - `.swarm/blueprint/commercial_strategy_report.md`
2. **One Question at a Time (Socratic Clarification):**
   - **IF a critical requirement is unsettled** (target user workflow, deployment environment, or core constraint not answered by the repo or prior reports): echo back what you understand in $\le 150$ words, state any relevant codebase findings (`path:line`), and end with **one single-sentence question** stating what the answer changes about what gets built.
   - **IF the user's goal and discovery reports are already complete** (or once clarifying questions are answered): proceed directly to laying out the approaches and presenting the Checkpoint 1 selection modal via `ask_question`.

---

## 2. Observable Conditional Predicates (Existing-Repo Sufficiency & Architecture Gates)

Evaluate the workspace across 4 Sufficiency Dimensions (`Technical & SOTA Parity`, `Market & Switch-Trigger Coverage`, `Architecture & Open-Core Boundary Cleanliness`, `UI/UX Quality`) and follow the matching predicate branch:

| Observable Condition | Required Action & Recommendation |
| :--- | :--- |
| **Condition A: Existing Repo with all 4 Sufficiency Dimensions $\ge 8.5/10$ AND max candidate feature `Net-ROI < 8.0`** | Declare **`VERDICT: PROJECT ALREADY OPTIMAL (NO CODE CHANGES REQUIRED)`** in Section 1. Present *"Keep project as-is (Already Optimal — skip UI & Swarm)"* as the `(Recommended)` first option in `ask_question`. |
| **Condition B: Existing Repo with `Option 0 (Existing Architecture)` scoring $\ge 8.5/10$** | Recommend **`Option 0: KEEP EXISTING ARCHITECTURE (Zero Structural Rewrite)`** and attach any approved `Net-ROI >= 8.0` features into existing module boundaries. |
| **Condition C: Greenfield Repo OR `Option 0 (Existing Architecture)` scoring $< 8.5/10$** | Lay out **2–3 competing Software Architecture Blueprints** with explicit trade-offs, recommend the strongest fit, and ask the user to confirm in `ask_question`. |
| **Condition D: Non-differentiating commodity subsystem needed** (CLI parsing, auth, charting, serialization, transport) | Run **Search-First Build-vs-Adopt Evaluation** (`Fit 1-10`, `Maintenance 1-10`, `License MIT/Apache-2.0`) and tag as `[ADOPT AS-IS: <pkg>]` or `[WRAP / EXTEND: <pkg>]`. Reserve `[BUILD CUSTOM (Core Moat)]` strictly for domain-differentiating kernels. |

---

## 3. Interactive Checkpoint 1 Confirmation (`ask_question`)

Present a concise synthesis of the Sufficiency Scorecard, candidate Innovation Hypotheses (`Net-ROI >= 8.0`), 3-Epoch Feature Matrix, and Software Architecture options (`Option 0` vs. Alternatives), then call `ask_question` so the user selects:
1. **Innovation Hypotheses** to include (with `(Recommended)` prefix on top `Net-ROI >= 8.0` items, or *"Keep project as-is"* when Condition A holds).
2. **Feature Tier Scope & Build-vs-Adopt Decisions** across Epochs 1–3.
3. **Software Architecture Choice** (`Option 0` vs. Blueprint A / B / C).
4. **UI/UX Prototype Wave (`Wave 2`)**: whether to run `/ui-ux-design` or skip directly to `/invoke-swarm`.

---

## 4. Positive Structural Output Contract (`.swarm/blueprint/brainstorm_blueprint.md` & `docs/ARCHITECTURE.md`)

Write the confirmed blueprint to `.swarm/blueprint/brainstorm_blueprint.md` and `docs/ARCHITECTURE.md`. The document MUST contain these 6 sections in exact order:

```markdown
# Product & Architecture Blueprint: <Project Name>

**Goal:** <One sentence describing what this system builds and for whom>
**Architecture:** <2-3 sentences summarizing the selected architecture (`Option 0` or chosen Blueprint)>
**Tech Stack:** <Languages, core libraries, adopted packages, test runner>
**Discovery Specs:** `.swarm/blueprint/deep_research_report.md`, `.swarm/blueprint/market_research_report.md`, `.swarm/blueprint/commercial_strategy_report.md`

## 1. Sufficiency Scorecard & Executive Verdict
| Dimension | Current Score (`1.0-10.0` or `N/A`) | Cited Codebase Evidence (`path:line`) | Status (`OPTIMAL >= 8.5` / `UPGRADE TARGET`) |
| :--- | :--- | :--- | :--- |
| **1. Technical & SOTA Parity** | `<Score>` | `<path:line or Greenfield>` | `<Status>` |
| **2. Market & Switch-Trigger Coverage** | `<Score>` | `<path:line or Greenfield>` | `<Status>` |
| **3. Architecture & Open-Core Cleanliness** | `<Score>` | `<path:line or Greenfield>` | `<Status>` |
| **4. UI/UX Quality (`web_ui_validator`)** | `<Score>` | `<path:line or Greenfield>` | `<Status>` |

- **Overall Verdict:** `<VERDICT: PROJECT ALREADY OPTIMAL (NO CODE CHANGES REQUIRED) | VERDICT: HIGH-ROI PLAN LOCKED FOR EXECUTION>`

## 2. Global Constraints & Behavioral Invariants
- **Runtime & Version Floors:** `<Exact language/runtime versions and OS targets>`
- **License & Dependency Policy:** `<Permissive MIT/Apache-2.0 only; zero copyleft in core>`
- **Preserved Brownfield Invariants (`WHEN -> THEN` / `ALWAYS TRUE`):**
  1. `WHEN <trigger> -> THEN <exact observable outcome>` (`<path:line>`)
  2. `ALWAYS TRUE: <invariant property>` (`<path:line>`)

## 3. Approved Innovation Hypotheses (`Net-ROI >= 8.0`)
| ID | Hypothesis & Technical Mechanism | Novelty (`1-10`) | User / Switch Value (`1-10`) | Feasibility (`1-10`) | Net-ROI (`1-10`) | Decision (`APPROVED` / `ALREADY SOTA` / `REJECTED`) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `IH-1` | `<Mechanism + source paper/repo>` | `<X>` | `<Y>` | `<Z>` | `<ROI>` | `<Decision>` |

## 4. 3-Epoch Feature Matrix, Build-vs-Adopt & Entrypoint Wiring Contract
| Task ID | Epoch (`1` / `2` / `3`) | Feature / Capability | Build-vs-Adopt Tag (`[ADOPT AS-IS: pkg]` / `[WRAP: pkg]` / `[BUILD CUSTOM]`) | Commercial Tier (`[OSS Core]` / `[Pro]` / `[B2B Enterprise]`) | Entrypoint Wiring Path (`Entrypoint -> Controller -> Module -> Output`) | Verification Command (`--outcome-cmd`) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `T1` | `Epoch 1` | `<Feature>` | `<Tag>` | `<Tier>` | `<exact file/call chain>` | `<runnable command>` |

- **Explicit Anti-Goals (Rejected Scope):**
  1. `<Rejected Feature 1>` — **Reason:** `<Maintenance tax exceeds user/commercial value>`

## 5. Software Architecture & Cross-Module Interface Boundaries
- **Approaches Evaluated:**
  - `Option 0 (Existing Architecture)`: `<Trade-offs & score>`
  - `Option A (<Name>)`: `<Trade-offs & score>`
  - `Option B (<Name>)`: `<Trade-offs & score>`
- **Selected Architecture:** `<Option X>` — `<Why chosen>`
- **Task File & Interface Map:**
  | Task ID | Files to Create / Modify | Consumes (Exact Signatures) | Produces (Exact Signatures) |
  | :--- | :--- | :--- | :--- |
  | `T1` | `Create: src/...`, `Test: tests/...` | `<Imported types/functions>` | `<Exported functions(args) -> ReturnType>` |

## 6. Review Focus (Top 5 Implied Failure Modes & Edge-Case Inputs)
The five input classes or failure modes implied by this design that are most likely to bite a real user in production, and the owning task test that pins each behavior:

| # | Implied Failure Mode / Adversarial Input Class | Expected Resilient Behavior | Owning Task ID | Pinning Test File & Test Function Name |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `<e.g., Malformed/empty payload or zero-byte file at ingestion>` | `<Returns typed validation error without crash or partial state write>` | `T1` | `tests/test_<module>.py::test_<behavior>` |
| 2 | `<e.g., Concurrent write / race on shared state or worktree file>` | `<Atomic lock or deterministic serialization>` | `T2` | `tests/test_<module>.py::test_<behavior>` |
| 3 | `<e.g., Network/API timeout or offline Zotero/LLM fallback>` | `<Graceful local SQLite/cache fallback within timeout budget>` | `T2` | `tests/test_<module>.py::test_<behavior>` |
| 4 | `<e.g., Boundary numerical input (NaN, 0, huge array)>` | `<Clamped or rejected with explicit diagnostic message>` | `T3` | `tests/test_<module>.py::test_<behavior>` |
| 5 | `<e.g., Untrusted external string with prompt/shell injection tokens>` | `<Treated strictly as inert data; zero shell/eval execution>` | `T3` | `tests/test_<module>.py::test_<behavior>` |
```

---

## 5. Self-Review Checklist & `.swarm/goal_loop.json` Seeding

Before finishing `/coop-brainstorm`, run this 4-point self-check and seed `.swarm/goal_loop.json`:

1. **Zero-Placeholder Verification:** Scan `.swarm/blueprint/brainstorm_blueprint.md` and `docs/ARCHITECTURE.md` to confirm zero occurrences of `TBD`, `TODO`, `"handle edge cases"`, `"add appropriate validation"`, or unpinned file paths.
2. **Interface & Type Consistency:** Confirm every signature in a task's `Consumes` column matches the exact name and parameter/return types in an earlier task's `Produces` column.
3. **Review Focus Coverage:** Confirm all 5 rows in `## 6. Review Focus` name a concrete input/condition, expected behavior, owning `Task ID`, and test function name.
4. **Seed `.swarm/goal_loop.json` and Verify Blueprint:**
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" \
     --init-goal "<Locked Overall Project Goal>" \
     --outcome-cmd "<End-to-End Product Verification Command>" \
     --entrypoints <entrypoint_files>
   python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --verify-blueprint
   ```

---

## 6. Zero-Context-Bloat Subagent Return Contract (`< 15 Lines`)

When invoked as a subagent, write the complete blueprint to `.swarm/blueprint/brainstorm_blueprint.md` and `docs/ARCHITECTURE.md`, seed `.swarm/goal_loop.json`, and return ONLY this `< 15 lines` summary:

```markdown
Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
Artifacts: .swarm/blueprint/brainstorm_blueprint.md, docs/ARCHITECTURE.md, .swarm/goal_loop.json
Sufficiency Verdict: <PROJECT ALREADY OPTIMAL | HIGH-ROI PLAN LOCKED>
Selected Architecture: <Option 0 | Option A/B>
Tasks Seeded: <N> tasks (<T1..Tn>) across 3 Epochs | Outcome Cmd: `<cmd>`
Review Focus Pinned: 5/5 implied failure modes mapped to task tests
Blueprint Verification: goal_loop.py --verify-blueprint -> PASS (0 placeholders)
Concerns / Blockers: None (or 1-line description)
```
