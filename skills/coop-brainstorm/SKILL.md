---
name: coop-brainstorm
description: "Use when planning features, architecture, or a product together with the user before code is written, including turning research reports into agreed product notes that /design-draft turns into a design. Runs standalone or as Checkpoint 1 of /product-discovery."
disable-model-invocation: false
triggers: [user, model]
---

# Cooperative Brainstorming & Product Notes (`/coop-brainstorm`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

## Overview

You are the **Elephant**: the session that holds project context. Together with the user you turn an idea (and any discovery reports) into agreed **product notes**: what to build, for whom, why, under which constraints, and with which architecture. Before the user commits, six fresh read-only reviewers (**Goldfish lenses**, ported from Google's Elephant-Goldfish Model) critique the concept from independent angles. The notes feed `/design-draft`, whose implementation plan `goal_loop.py --import-design` turns into tasks. This skill writes no tasks.

**Harness Polling Rule (`$AGENT_SWARM_HOME/references/harness-polling.md`):** Prompt every Elephant question, branch choice, objection resolution, and Checkpoint 1 decision using the **active harness's native polling tool** (`ask_question` in Antigravity, `AskUserQuestion` in Claude Code, `request_user_input` in Codex CLI; structured fallback elsewhere) with `(Recommended)` first. **Never write `## Open Questions` or `[?]` markers into `.swarm/blueprint/*.md` or any `plan.md`.**

---

## 1. Code-First Lookup, Framing Challenge & Decision-Tree Grilling

Synthesizing EGM, `mattpocock/skills` (`/grill-me`), `garrytan/gstack` (`/office-hours`), `addyosmani/agent-skills`, and `DietrichGebert/ponytail`:

1. **Code Before Poll:** Inspect the repository (`src/`, tests, manifests, `docs/`) and any discovery reports before your first message:
   - `.swarm/blueprint/tech_research_report.md` & `.swarm/sota/sota_knowledge_base.md`
   - `.swarm/blueprint/market_research_report.md`
   - `.swarm/blueprint/commercial_strategy_report.md`
   Never poll the user for a fact that `Read`, `Grep`, or `Glob` can establish (`path:line`).
2. **Framing & Radical YAGNI Challenge:** Check whether the request solves a symptom rather than the root problem, and whether existing code or the standard library already covers 90% of it.
3. **Decision-Tree Grilling via Harness Polling Tool:**
   - Echo back verified repository facts in at most 120 words (`path:line`), then walk unsettled branches of the decision tree (users, constraints, failure semantics, scope boundaries, build-vs-adopt) using the **harness polling tool** (`ask_question` / `AskUserQuestion` / `request_user_input`).
   - Put `(Recommended)` first on every question and state in one sentence what each option changes in the build.
   - Once all branches are settled, summarise the concept in 2–3 sentences and poll whether to run the 6-lens Goldfish critique or refine further.

---

## 2. Existing-Repository Verdict (Conditions A–D)

Evaluate the workspace across 4 Sufficiency Dimensions (`Technical & SOTA Parity`, `Market & Switch-Trigger Coverage`, `Architecture & Open-Core Boundary Cleanliness`, `UI/UX Quality`):

| Observable Condition | Required Action & Recommendation |
| :--- | :--- |
| **Condition A: Existing Repo with all 4 dimensions `OPTIMAL` AND zero candidate features with `HIGH` Net-ROI** | Declare **`VERDICT: PROJECT ALREADY OPTIMAL (NO CODE CHANGES REQUIRED)`** and place `(Recommended) Keep project as-is` first in the harness poll. Skip the lens review and `/design-draft`. |
| **Condition B: Existing Repo with `Option 0 (Existing Architecture)` rated `OPTIMAL`** | Recommend **`Option 0: Keep Existing Architecture`** and fit approved `HIGH` Net-ROI features into existing module boundaries. |
| **Condition C: Greenfield Repo OR `Option 0` rated `UPGRADE_NEEDED`** | Present **2–3 competing architectures** with explicit trade-offs, mark the strongest fit `(Recommended)`, and poll the user via the harness tool. |
| **Condition D: Non-differentiating commodity subsystem needed** (CLI parsing, auth, charting, serialization, transport) | Run **Search-First Build-vs-Adopt** (stdlib first, then `Fit: HIGH/MED/LOW`, `Maintenance: ACTIVE/STALE`, `License`) and tag `[ADOPT AS-IS: <pkg>]` or `[WRAP / EXTEND: <pkg>]`. Reserve `[BUILD CUSTOM]` for domain-differentiating kernels. |

---

## 3. Lens Review (Six Read-Only Goldfish, in Parallel)

1. Write the clarified concept to `.swarm/blueprint/concept.md` (2–3 paragraphs: problem, users, proposed approach, constraints, non-goals, zero open questions).
2. Start six read-only reviewers in parallel, exactly as `/goldfish-review` starts them (Claude Code: `Agent` with `subagent_type: "goldfish"`; Antigravity: `define_subagent(..., enable_write_tools=False)` then `invoke_subagent`; Codex CLI: `spawn_agent` read-only; take the workspace SHA-256 snapshot before and after; no subagent tool → notify via the harness polling tool and stop the lens step). Pass `Mode: BRAINSTORM`, `Target: .swarm/blueprint/concept.md`, persona `$AGENT_SWARM_HOME/skills/goldfish-review/personas/<persona>.md`, and the discovery reports as reading list:

   | Persona | Lens |
   | :--- | :--- |
   | `zoom-out` | Does this need to exist? Can stdlib, existing code, or a library cover most of it? |
   | `comprehension` | Interface and workflow ergonomics; actionable errors |
   | `design-critic` | Cost, quota and token budget; bottlenecks |
   | `implementation-readiness` | Migration, backward compatibility, rollback |
   | `codebase-details` | Observability and debuggability |
   | `maintainability` | Coupling and long-term maintenance |

3. Save each reply to `.swarm/design-reviews/concept/<persona>.md` and merge duplicates into **Lens Analysis**.
4. Surface the 2–3 strongest objections and **poll the user via the harness polling tool** on how to resolve each (narrow scope, adjust approach, add a constraint, or accept as a documented trade-off).

---

## 4. Checkpoint 1 Confirmation (Harness Poll)

Synthesize the concept and poll the user via `ask_question` / `AskUserQuestion` / `request_user_input` (with `(Recommended)` first):
1. **Innovation hypotheses** (`HIGH` Net-ROI items, or `Keep project as-is` under Condition A).
2. **Scope:** checkable goals and YAGNI non-goals.
3. **Architecture:** `Option 0` versus alternatives.
4. **UI prototypes:** whether `/product-discovery` should run `/ui-ux-design` next.

---

## 5. Output Contract: Product Notes (`.swarm/blueprint/brainstorm_blueprint.md`)

Write the confirmed notes in these exact sections, with zero placeholders and zero open questions:

```markdown
# Product Notes: <Project Name>

**Author:** <git config user.name> · **Date:** <YYYY-MM-DD>
**Discovery reports:** <links to the reports used, or "none">

## Overview
<What is being built, for whom, and the core value, in plain language.>

## Sufficiency Table and Verdict
| Dimension | Evidence (`path:line` or Greenfield) | Status (`OPTIMAL` / `UPGRADE_TARGET`) |
| :--- | :--- | :--- |
| Technical & SOTA Parity | ... | ... |
| Market & Switch-Trigger Coverage | ... | ... |
| Architecture & Open-Core Cleanliness | ... | ... |
| UI/UX Quality (`web_ui_validator`) | ... | ... |
- **Verdict:** `PROJECT ALREADY OPTIMAL (NO CODE CHANGES REQUIRED)` | `PLAN AGREED — CONTINUE WITH /design-draft`

## Lens Analysis
<Merged findings of the six lenses, each with the user's polled decision: addressed how, or accepted as a risk.>

## Goals and Non-Goals
- **Goals:** <checkable outcomes>
- **Non-Goals:** <deliberately excluded scope and anti-goals, with the YAGNI reason>

## Constraints and Invariants
- **Runtime & version floors:** ...
- **License & dependency policy:** ...
- **Preserved behaviour (`WHEN -> THEN` / `ALWAYS TRUE`):** ... (`path:line`)

## Approved Innovation Hypotheses
| ID | Hypothesis & mechanism (source) | Value | Effort | Net-ROI | Decision |
| :--- | :--- | :--- | :--- | :--- | :--- |

## Architecture Options and Choice
- **Options:** `Option 0 (existing)`, `Option A`, `Option B`, each with trade-offs.
- **Chosen:** <option> — <why>
- **Build vs adopt:** <tags from Condition D>

## Alternatives Weighed
<Each rejected option with its technical or scope reason ("Rejected by author: ..."), plus what was intentionally skipped.>

## Key Decisions for /design-draft
<Settled decisions `/design-draft` carries forward, and the end-to-end outcome command.>
```

Then initialise the root goal (no tasks; `/design-draft` and `goal_loop.py --import-design` create them):

```bash
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" \
  --init-goal "<Agreed Overall Goal>" \
  --outcome-cmd "<End-to-End Verification Command>" \
  --entrypoints <entrypoint_files>
```

---

## 6. Red Flags & Subagent Return Contract (`< 15 Lines`)

- *"I'll ask the user which framework this repo uses."* → **STOP.** Read `package.json`/`pyproject.toml` first; never poll what code answers.
- *"I'll put unresolved questions in `brainstorm_blueprint.md` for later."* → **STOP.** Poll via the harness polling tool now; `goal_loop.py` rejects open questions in blueprint and plan files.

When invoked as a subagent, return only:
```markdown
Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
Artifacts: .swarm/blueprint/brainstorm_blueprint.md, .swarm/blueprint/concept.md, .swarm/design-reviews/concept/
Sufficiency Verdict: <PROJECT ALREADY OPTIMAL | PLAN AGREED>
Selected Architecture: <Option 0 | Option A/B>
Lens Review: <6/6 completed | n not run> — <top objection and its decision>
Root Goal: initialised with outcome command `<cmd>`
Next Step: /design-draft (or none if already optimal)
Concerns / Skipped: None (or explicit skipped checks / accepted risks)
```
