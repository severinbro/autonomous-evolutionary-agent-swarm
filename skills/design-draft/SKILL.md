---
name: design-draft
description: "Use when a feature or product needs a written design before implementation: turning product notes from /coop-brainstorm, or the user's own notes, into a design document under docs/designs/ whose implementation plan can be imported into .swarm/goal_loop.json."
---

# Design Draft (`/design-draft`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

You are the **Elephant**: the session that holds the project context. Together with the user you write the design document section by section. You write no code here. The design becomes the single planning file of the build: `goal_loop.py --import-design` turns its implementation plan into tasks. Ported from the Elephant-Goldfish Model's drafting step (EGM, <https://github.com/google/elephant-goldfish-model>); experimental.

Use it when a feature has real design decisions. For a small, clear fix, go straight to `/invoke-swarm`.

---

## Step 1: Gather the Input

1. Read the product notes `.swarm/blueprint/brainstorm_blueprint.md` if they exist (written by `/coop-brainstorm`); otherwise ask the user for their notes or a problem statement.
2. Read the code the feature touches, so the Technical Plan and the file lists are real.
3. Choose the file: `docs/designs/<short-name>.md`. Copy `skills/design-draft/template.md` there and fill in the header (author from `git config user.name`, today's date, `Status: Draft`).
4. Confirm with the user in one message what you are drafting and from which input.

---

## Step 2: Draft in Four Groups

Write each group into the file, then summarise in chat in 2–4 lines what you wrote and the main decisions, link the file, and ask one question: **approve and continue**, or **revise** (with what to change). Do not paste the draft into chat. Do not move on without approval.

1. **Overview, The Problem, Goals, Non-Goals, Open Questions.** Focus on why. Goals must be checkable.
2. **Critical User Journeys, Technical Plan.** Components, data flow, interfaces, and how they fit the existing code.
3. **Alternatives Considered, Risks, Non-Functional Requirements, Additional Resources, Future Improvements.** Take the alternatives from the product notes' "Alternatives Weighed" (ask the user if absent). Every rejection names the deciding technical or scope reason ("Rejected by author: ...").
4. **Detailed Implementation Plan.** In the import format (see the template's comment):
   - one `### Goal` block with the goal sentence and the end-to-end `Outcome` command;
   - one `### Task <PREFIX>-<n>: <title>` block per task, with `Files`, `Depends on`, `Changes`, `Verification`, and `Review focus` where failure modes matter.

   Leave no design decision to the implementer: name functions, fields, error behaviour and test cases. Every `Verification` command must fail without the change. Tasks that change the same file need a `Depends on` path between them. Write no code; signatures and schemas are fine.

---

## Step 3: Check Against the Product Notes

Re-read the input from Step 1 and compare it with the draft. The draft may be right where it differs, because drafting read code that brainstorming did not. So list, one line each, quoting both texts:

- **Contradictions:** the notes decided something and the draft decides it differently.
- **Additions** that change the architecture, an external interface, or a dependency.

Ask the user to decide each one. Change nothing on your own. If nothing differs, say so in one line.

---

## Step 4: Validate the Plan Format

```bash
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd <workspace> --import-design docs/designs/<name>.md --dry-run
```

Fix every reported error (missing fields, untagged files, unknown or cyclic dependencies, overlapping files without a dependency) and run it again until it passes. Set `Status: In Review`.

---

## Step 5: Review and Import

1. Offer `/goldfish-review docs/designs/<name>.md` (it states its token estimate first; the user may skip it).
2. After the review closes, run the dry run again and show the user the list of commands it prints. The gate will execute these, so ask the user to confirm them.
3. On confirmation, import for real (same command without `--dry-run`), set `Status: Approved`, and hand off to `/invoke-swarm`.

---

## Red Flags

- *"I'll write the whole design at once and ask at the end."* → **STOP.** One group at a time, approved each time.
- *"The implementer can decide the error handling."* → **STOP.** Undecided choices become inconsistent code. Decide it in the plan.
- *"The notes said X but I think Y is better, so I changed it."* → **STOP.** List it as a contradiction and let the user decide.
- *"I'll import before the user sees the commands."* → **STOP.** Imported commands run in the gate. Show them first.
