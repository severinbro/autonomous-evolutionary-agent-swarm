---
name: coop-brainstorm
description: "Use when planning features, architecture, or a product together with the user before code is written, including turning research reports into agreed product notes that /design-draft turns into a design. Runs standalone or as Checkpoint 1 of /product-discovery."
disable-model-invocation: false
triggers: [user, model]
---

# Cooperative Brainstorming & Product Notes (`/coop-brainstorm`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

## Overview

You are the **Elephant**: the session that holds the project context. Together with the user you turn an idea (and any research reports) into agreed **product notes**: what to build, for whom, why, under which constraints, and with which architecture. Before the user commits, six fresh read-only reviewers (the **Goldfish lenses**, ported from the Elephant-Goldfish Model) critique the concept from different angles. The notes are the input to `/design-draft`, which writes the design whose implementation plan becomes the task list. This skill writes no tasks.

**Core principle:** read the code and the reports before asking; ask one question at a time; let fresh reviewers attack the concept before the user locks it.

---

## 1. Look Before You Ask & Single-Question Clarification

1. **Read context first.** Inspect the repository (`src/`, tests, manifests, `docs/`) and any discovery reports before your first message:
   - `.swarm/blueprint/tech_research_report.md` & `.swarm/sota/sota_knowledge_base.md`
   - `.swarm/blueprint/market_research_report.md`
   - `.swarm/blueprint/commercial_strategy_report.md`
2. **One question at a time.**
   - **If a critical requirement is unsettled** (who uses it, where it runs, a hard constraint, how success is measured, what is out of scope): echo back what you understand in at most 150 words, cite relevant code (`path:line`), and end with **one** open question saying what the answer changes about what gets built. Keep asking across turns until the problem, users, constraints and boundaries are clear.
   - **Once the concept is clear:** summarise it in 2–3 sentences and ask whether to send it to the lens review or keep clarifying.

---

## 2. Existing-Repository Verdict (Conditions A–D)

Evaluate the workspace across 4 Sufficiency Dimensions (`Technical & SOTA Parity`, `Market & Switch-Trigger Coverage`, `Architecture & Open-Core Boundary Cleanliness`, `UI/UX Quality`) and follow the matching branch:

| Observable Condition | Required Action & Recommendation |
| :--- | :--- |
| **Condition A: Existing Repo with all 4 dimensions `OPTIMAL` AND zero candidate features with `HIGH` Net-ROI** | Declare **`VERDICT: PROJECT ALREADY OPTIMAL (NO CODE CHANGES REQUIRED)`** and offer *"Keep project as-is"* as the first option. Skip the lens review and `/design-draft`. |
| **Condition B: Existing Repo with `Option 0 (Existing Architecture)` rated `OPTIMAL`** | Recommend **`Option 0: Keep Existing Architecture`** and fit approved `HIGH` Net-ROI features into existing module boundaries. |
| **Condition C: Greenfield Repo OR `Option 0` rated `UPGRADE_NEEDED`** | Lay out **2–3 competing architectures** with explicit trade-offs, recommend the strongest fit, and let the user confirm. |
| **Condition D: Non-differentiating commodity subsystem needed** (CLI parsing, auth, charting, serialization, transport) | Run **Search-First Build-vs-Adopt** (`Fit: HIGH/MED/LOW`, `Maintenance: ACTIVE/STALE`, `License`) and tag `[ADOPT AS-IS: <pkg>]` or `[WRAP / EXTEND: <pkg>]`. Reserve `[BUILD CUSTOM]` for domain-differentiating kernels. |

---

## 3. Lens Review (six Goldfish, in parallel)

1. Write the clarified concept to `.swarm/blueprint/concept.md` (2–3 paragraphs: problem, users, proposed approach, constraints, non-goals). This file is all the lenses see.
2. Start six read-only reviewers in parallel, one per lens, exactly as `/goldfish-review` starts them (Claude Code: `Agent` with `subagent_type: "goldfish"`; Antigravity: `define_subagent(..., enable_write_tools=False)` then `invoke_subagent`; take the snapshot fingerprint before and after; no subagent tool → tell the user and stop the lens step). Prompt each with `Mode: BRAINSTORM`, `Target: .swarm/blueprint/concept.md`, its persona file `$AGENT_SWARM_HOME/skills/goldfish-review/personas/<persona>.md`, and the reading list (the discovery reports, if any):

   | Persona | Lens |
   | :--- | :--- |
   | `zoom-out` | Does this need to exist? Can existing code or a library cover most of it? |
   | `comprehension` | Interface and workflow ergonomics; actionable errors |
   | `design-critic` | Cost, quota and token budget; bottlenecks |
   | `implementation-readiness` | Migration, backward compatibility, rollback |
   | `codebase-details` | Observability and debuggability |
   | `maintainability` | Coupling and long-term maintenance |

3. Save each reply to `.swarm/design-reviews/concept/<persona>.md`. Merge the findings (duplicates become one item) into the **Lens Analysis** section of the product notes.
4. Tell the user the 2–3 strongest objections and ask how to address them (narrow scope, change approach, add a constraint, or accept the risk). Repeat clarification and the lens review if the concept changes substantially.

---

## 4. Checkpoint 1 Confirmation

Present a concise synthesis and let the user choose, one decision per question:
1. **Innovation hypotheses** to include (top `HIGH` Net-ROI items first, or *"Keep project as-is"* under Condition A).
2. **Scope:** goals and non-goals.
3. **Architecture:** `Option 0` versus the alternatives.
4. **UI prototypes:** whether `/product-discovery` should run `/ui-ux-design` next.

---

## 5. Output Contract: Product Notes (`.swarm/blueprint/brainstorm_blueprint.md`)

Write the confirmed notes in exactly these sections, in this order, with no placeholders:

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
<Merged findings of the six lenses, each with the user's decision: addressed how, or accepted as a risk.>

## Goals and Non-Goals
- **Goals:** <checkable outcomes>
- **Non-Goals:** <deliberately excluded scope and anti-goals, with the reason>

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
<Each rejected option with its technical or scope reason ("Rejected by author: ..."). `/design-draft` copies these into the design.>

## Key Decisions for /design-draft
<Decisions the design must carry forward, and the end-to-end outcome command that will prove the product works.>
```

Then initialise the root goal (no tasks; `/design-draft` and `goal_loop.py --import-design` create them):

```bash
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" \
  --init-goal "<Agreed Overall Goal>" \
  --outcome-cmd "<End-to-End Verification Command>" \
  --entrypoints <entrypoint_files>
```

---

## 6. Self-Review Checklist

Before finishing:
1. **No placeholders:** the notes contain no `TBD`, `TODO`, "handle edge cases" or unnamed files.
2. **Every goal is checkable** by a command or an observation.
3. **Every lens finding has a decision** (addressed, or accepted as a risk) in Lens Analysis.
4. **Alternatives Weighed** names a reason for each rejection.

Interfaces, task lists and per-task failure modes belong in the design; `/goldfish-review` stage 4 checks them there.

---

## 7. Subagent Return Contract (`< 15 Lines`)

When invoked as a subagent, write the notes and return only:

```markdown
Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
Artifacts: .swarm/blueprint/brainstorm_blueprint.md, .swarm/blueprint/concept.md, .swarm/design-reviews/concept/
Sufficiency Verdict: <PROJECT ALREADY OPTIMAL | PLAN AGREED>
Selected Architecture: <Option 0 | Option A/B>
Lens Review: <6/6 completed | n not run> — <top objection and its decision>
Root Goal: initialised with outcome command `<cmd>`
Next Step: /design-draft (or none if already optimal)
Concerns / Blockers: None (or 1-line description)
```
