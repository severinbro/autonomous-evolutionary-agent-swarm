---
name: design-draft
description: "Use when a feature or product needs a written design before implementation: turning product notes from /coop-brainstorm, or the user's own notes, into a design document under docs/designs/ whose implementation plan can be imported into .swarm/goal_loop.json."
---

# Design Draft (`/design-draft`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

You are the **Elephant**: the session that holds the project context. Together with the user you write the design document section by section, writing no production code here. `goal_loop.py --import-design` turns its implementation plan into tasks. Ported from Google's Elephant-Goldfish Model (`https://github.com/google/elephant-goldfish-model`) and enriched with vertical-slice planning (`mattpocock/skills`), Red-Green-Refactor readiness (`obra/superpowers`), and shortest-path YAGNI (`DietrichGebert/ponytail`).

**Harness Polling Rule (`$AGENT_SWARM_HOME/references/harness-polling.md`):** Every ambiguity, trade-off, section approval, contradiction decision, and import confirmation **MUST** be prompted live using the **corresponding harness's native polling tool** (`ask_question` in Antigravity, `AskUserQuestion` in Claude Code, `request_user_input` in Codex CLI; structured fallback elsewhere) with `(Recommended)` first. **Never write `## Open Questions` or `[?]` markers inside `docs/designs/<name>.md` or any `plan.md`.**

Use `/design-draft` when a feature has real design decisions. For a small, clear fix, go straight to `/invoke-swarm`.

---

## Step 1: Gather Context & Poll Unsettled Branches

1. Read `.swarm/blueprint/brainstorm_blueprint.md` if it exists (from `/coop-brainstorm`); otherwise ask the user via the harness polling tool or a concise prompt for the problem statement.
2. **Code Before Poll:** Read the code the feature touches (`Read`, `Grep`, `Glob`) so file paths, symbols, and existing helpers are verified facts (`path:line`). Never poll the user for something the repository already answers.
3. If code inspection reveals an unsettled architectural or behavioral branch, **poll the user immediately via the harness polling tool** (`ask_question` / `AskUserQuestion` / `request_user_input`) with `(Recommended)` first, and record each settled choice for `## Resolved Decisions`.
4. Copy `$AGENT_SWARM_HOME/skills/design-draft/template.md` to `docs/designs/<short-name>.md`, fill in the header (`git config user.name`, date, `Status: Draft`), and state in one line what you are drafting and from which input.

---

## Step 2: Draft in Four Groups (Polled Section Gates)

Write each group into `docs/designs/<name>.md`, summarise in chat in 2–4 lines what you wrote and the main decisions (with a clickable link to the file; never paste the draft into chat), and **poll the user via the harness polling tool** (`(Recommended) Approve section group and continue`, `Revise this section group`). Do not advance without approval.

1. **Overview, The Problem, Goals, Non-Goals, Resolved Decisions.** Focus on root cause (`gstack`) and checkable goals; aggressively exclude speculative bloat in Non-Goals (`ponytail` YAGNI). Record every polled choice in `Resolved Decisions`—never leave open questions in the file.
2. **Critical User Journeys, Technical Plan.** Components, data flow, interfaces, and reuse of stdlib/existing code before adding new modules or dependencies.
3. **Alternatives Considered, Risks, Non-Functional Requirements, Additional Resources, Future Improvements.** Carry alternatives from product notes' "Alternatives Weighed" (poll via the harness tool if absent). Every rejection states its technical or scope reason (`"Rejected by author: ..."`). Note any intentionally skipped scope or unchecked risk in `Future Improvements`.
4. **Detailed Implementation Plan.** Decompose into **vertical slices ("tracer bullets")** rather than horizontal unintegrated layers, using the import contract:
   - one `### Goal` block with `Goal` and the end-to-end backticked `Outcome` command;
   - one `### Task <PREFIX>-<n>: <title>` block per slice, with `Files` (`(Create)`/`(Modify)`/`(Delete)`), `Depends on`, `Changes`, `Verification` (a backticked test command that **fails before the change** for Red-Green-Refactor TDD), plus `Called by`, `Symbols`, and `Review focus` where wiring and edge cases matter.

   Leave zero design decisions to the implementer: name functions, fields, error behaviour, and test cases. Tasks touching the same file must have a `Depends on` path between them. Write signatures and schemas only, not implementation bodies.

---

## Step 3: Check Against the Product Notes

Re-read the Step 1 input and compare it with the draft. List, one line each, quoting both texts:
- **Contradictions:** the notes decided something and the draft decides it differently.
- **Additions** that change the architecture, an external interface, or a dependency.

If any exist, **poll the user on each item via the harness polling tool** (`ask_question` / `AskUserQuestion` / `request_user_input`) with `(Recommended)` first. Change nothing on your own. If nothing differs, say so in one line.

---

## Step 4: Validate Plan Format & Zero-Plan-Questions Gate

```bash
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd <workspace> --import-design docs/designs/<name>.md --dry-run
```

Fix every reported error (missing fields, untagged files, open-question headings/markers, unknown or cyclic dependencies, overlapping files without `Depends on`) and re-run until `OK`. Set `Status: In Review`.

---

## Step 5: Goldfish Review and Confirmed Import

1. Poll the user via the harness polling tool to run `/goldfish-review docs/designs/<name>.md` (stating its ~100k-tokens-per-reviewer estimate; the user may run all stages, pick stages, or skip).
2. After the review closes, run `--import-design ... --dry-run` again, display the exact commands the gate will execute, and **poll the user via the harness polling tool to confirm them**.
3. On confirmation, run `--import-design` without `--dry-run`, set `Status: Approved`, and hand off to `/invoke-swarm`.

---

## Red Flags

- *"I'll park this unsettled edge case under `## Open Questions` inside `docs/designs/<name>.md`."* → **STOP.** Plans hold resolved decisions, never questions. Poll live with the harness polling tool (`ask_question` / `AskUserQuestion` / `request_user_input`) first.
- *"I'll write the whole design at once and ask at the end."* → **STOP.** Draft one group at a time and poll approval after each.
- *"The implementer can decide the error handling."* → **STOP.** Undecided choices become inconsistent code. Decide it in the plan.
- *"The notes said X but Y is cleaner, so I changed it silently."* → **STOP.** Surface contradictions in Step 3 and poll the user.
- *"I'll import before the user sees the commands."* → **STOP.** Imported commands execute in the gate; show and confirm them first.
