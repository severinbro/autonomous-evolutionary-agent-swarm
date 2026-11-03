---
name: goldfish-review
description: "Use when a design document, plan, README or other Markdown document needs an independent review by fresh read-only reviewers before work starts, or when only one review stage (such as the comprehension test) should run on a document."
---

# Goldfish Review (`/goldfish-review`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

You are the **Elephant**: the session that knows the project and usually wrote the document. You cannot review your own document objectively, so you hand it to **Goldfish**: read-only reviewers that start with no conversation history and see only the document and the files it names. You then resolve their findings with the user. This is a port of the Elephant-Goldfish Model (EGM, <https://github.com/google/elephant-goldfish-model>). It is experimental: no benchmark in this repository has measured it yet.

A review does not replace tests or the user's judgement.

---

## Inputs

- **Target:** path to the Markdown document.
- **Reading list (optional):** files the reviewers may read for context. The repository files the target links are added automatically; files under `.swarm/` never are.
- **`--stages <list>` (optional):** comma-separated stage numbers, for example `--stages 2` or `--stages 1,3`. Default: all four.

---

## Step 1: Estimate and Confirm

Count the reviewers the requested stages need (table below; six for a full review). Tell the user the estimate: about 100k tokens per reviewer, measured on this pack's own design reviews. Ask one question: continue, or choose fewer stages. Do not start reviewers before the answer.

---

## Step 2: Start Read-Only Reviewers

Every reviewer is a fresh subagent that cannot write files:

- **Claude Code:** the `Agent` tool with `subagent_type: "goldfish"` (the read-only agent in `agents/goldfish.md`, linked by `./install.sh claude-code`). If that type is not installed, use a general-purpose subagent and rely on the snapshot check below.
- **Antigravity:** `define_subagent(name="goldfish_<persona>", enable_write_tools=False)`, then `invoke_subagent`.
- **No subagent tool:** stop and tell the user. A review in the same context is not a Goldfish review.

**Snapshot check.** Before the first reviewer starts and after the last one finishes, record a fingerprint of the workspace:

```bash
( git diff HEAD; git ls-files -o --exclude-standard -z | xargs -0 -r sha256sum; sha256sum .swarm/goal_loop.json 2>/dev/null ) | sha256sum
```

If the two fingerprints differ, stop the review and tell the user what changed. Do not restore anything yourself. Writes outside the workspace are not detected.

**Prompt for each reviewer** (fill in the angle brackets; nothing else):

```text
You are a Goldfish reviewer. Read $AGENT_SWARM_HOME/skills/goldfish-review/personas/<persona>.md and follow it.
Mode: REVIEW
Target: <absolute path to the document>
Scope: <whole document | lines <a>-<b> (<section>)>
Standard: $AGENT_SWARM_HOME/skills/goldfish-review/standards/<standard>.md   (omit for comprehension)
Reading list: <absolute paths, or "none">
Do not read anything under .swarm/. Do not create, change or delete files. Reply with your findings only.
```

A reviewer that fails or returns nothing is retried once. If it fails again, record it as `not run`. Never count it as a reviewer with no findings.

---

## Step 3: Run the Stages

| Stage | Reviewers (persona → standard) | Scope |
| :--- | :--- | :--- |
| 1. Zoom-out | `zoom-out` → `zoom-out` | whole document |
| 2. Comprehension | `comprehension` → none | whole document; **no reading list** |
| 3. Critics | `design-critic` → `feature-spec`; `style` → `feature-spec` | everything above the plan heading (`## Detailed Implementation Plan` or `## Implementation Plan`); the whole document if there is no plan |
| 4. Readiness | `implementation-readiness` → `implementation-readiness`; `codebase-details` → `implementation-readiness`; plus `python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd <workspace> --import-design <target> --dry-run` | the plan section; if the document has no plan, record the stage as `skipped: no plan` |

**Order.** Stage 1 runs first and alone. If it reports a Blocker, stop: resolve it with the user (Step 5) before spending tokens on detailed review of text that is about to change. Otherwise start stages 2, 3 and 4 in parallel.

Write each reviewer's complete reply to `.swarm/design-reviews/<target path with / replaced by __>/stage-<n>-<persona>.md`. For stage 4, also save the dry-run output as `stage-4-import.md`. For stage 2, keep the restatement even when there are no findings: the user checks it against what they meant.

---

## Step 4: Consolidate

Write `report.md` in the same folder:

1. A status table: each reviewer with `completed`, `not run`, or `skipped`.
2. The findings, merged: the same scope and the same issue become one item with the highest severity and every reviewer that raised it. Keep each item's reviewer, severity, scope and text.
3. Order: Blocker, then Major, then Nit.

---

## Step 5: Resolve With the User

Classify every item in `resolution.md`:

| Category | Use when | Action |
| :--- | :--- | :--- |
| `PROPOSE FIX` | The finding is valid. | Give the exact edit. |
| `CONTEST` | The finding is wrong, and the evidence is in a file the reviewer could read. | Cite the file and symbol, or the document's own text. |
| `ESCALATE` | The finding is wrong or a matter of preference, and the evidence is outside what the reviewer could read (a verbal decision, a team convention). | Ask the user; do not edit. |
| `DECLINE` | A Nit not worth changing. | Record it. (A Nit may also get a `PROPOSE FIX`.) |

Rules:
- A comprehension gap is never contested: if a fresh reader could not follow the text, it lacks context.
- "This was intentional" is not evidence. Without checkable evidence, use `PROPOSE FIX` or `ESCALATE`.
- Do not change a severity. If you think a Blocker is a Nit, contest it and say why.
- Add context when a human reader needs it, not only to satisfy a reviewer.
- You wrote the document. Wanting to contest a finding is not evidence that the reviewer is wrong.

Tell the user where `resolution.md` is, list `ESCALATE` items first (they need the user's knowledge), and ask one question: **accept all fixes**, **go item by item**, or **no changes**. No edit to the document happens before that answer.

---

## Step 6: Apply and Re-Run Once

Apply the accepted edits. Re-run, once, each stage whose scope the edits changed. Their findings go through Steps 4–5 again, into the same `resolution.md` and the same user question. Nothing re-runs after that. List any open items in the document as accepted trade-offs, then tell the user the review is closed.

When `/design-draft` or `/product-discovery` called this skill, return to it with the counts: fixes applied, contested, escalated, declined, still open.

---

## Brainstorm Mode (used by `/coop-brainstorm`)

`/coop-brainstorm` sends the same personas in `Mode: BRAINSTORM` on a short concept file (`.swarm/blueprint/concept.md`). Six lenses run in parallel: `zoom-out` (does it need to exist), `comprehension` (ergonomics), `design-critic` (cost and token budget), `implementation-readiness` (migration), `codebase-details` (observability), `maintainability` (long-term maintenance). The same read-only start and snapshot check apply; reports go to `.swarm/design-reviews/concept/`. No standard is passed.

---

## Red Flags

- *"I'll review it myself in this session; it's faster."* → **STOP.** Same-context review shares the author's assumptions. Use subagents, or tell the user you cannot.
- *"The reviewer is wrong; I'll just skip that finding."* → **STOP.** Classify it. Contest with evidence or escalate to the user.
- *"I'll fix the obvious items before asking."* → **STOP.** No edit before the user's answer in Step 5.
- *"One more round will make it perfect."* → **STOP.** Fresh reviewers always find something new. One re-run per changed stage, then close.
