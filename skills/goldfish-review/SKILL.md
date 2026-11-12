---
name: goldfish-review
description: "Use when a design document, plan, README or other Markdown document needs an independent review by fresh read-only reviewers before work starts, or when only one review stage (such as the comprehension test) should run on a document."
---

# Goldfish Review (`/goldfish-review`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

You are the **Elephant**: the session that knows the project and usually wrote the document. Because you share your own draft's blind spots, you hand it to **Goldfish**: fresh read-only subagents with zero conversation history that see only the document and named files. You then resolve their findings with the user. Ported from Google's Elephant-Goldfish Model (EGM, <https://github.com/google/elephant-goldfish-model>).

**Harness Polling Rule (`$AGENT_SWARM_HOME/references/harness-polling.md`):** Every Elephant prompt to the user (stage confirmation, `ESCALATE` items, and resolution gate) **MUST** use the **active harness's native polling tool** (`ask_question` in Antigravity, `AskUserQuestion` in Claude Code, `request_user_input` in Codex CLI; structured fallback elsewhere) with `(Recommended)` first—never questions written inside the target document or `plan.md`.

---

## Inputs

- **Target:** path to the Markdown document.
- **Reading list (optional):** repository files reviewers may read for context. Linked repo files are added automatically; files under `.swarm/` never are.
- **`--stages <list>` (optional):** comma-separated stage numbers (for example `--stages 2` or `--stages 1,3`). Default: all four.

---

## Step 1: Estimate and Poll Confirmation

Count the reviewers the requested stages need (six for a full review) and state the token estimate (~100k tokens per reviewer, measured on this pack's own design reviews). Poll the user via the **harness polling tool** (`ask_question` / `AskUserQuestion` / `request_user_input`):
- `(Recommended) Run requested stages (<N> reviewers, ~<N*100>k tokens)`
- `Run Stage 1 (Zoom-out) + Stage 2 (Comprehension) only (2 reviewers)`
- `Run Stage 4 (Implementation Readiness) only`
- `Skip Goldfish review`

Do not start reviewers before the user's answer.

---

## Step 2: Start Read-Only Reviewers

Every reviewer is a fresh subagent with zero conversation history and no file-write tools:

- **Claude Code:** `Agent` tool with `subagent_type: "goldfish"` (`agents/goldfish.md`, linked by `./install.sh claude-code`). If not installed, use a general-purpose subagent and rely on the snapshot check below.
- **Antigravity:** `define_subagent(name="goldfish_<persona>", enable_write_tools=False)`, then `invoke_subagent`.
- **Codex CLI:** `spawn_agent` in read-only sandbox (`sandbox_mode: "read-only"`).
- **No subagent tool:** stop and notify the user via the harness polling tool. A review in the same context is not a Goldfish review.

**Snapshot check.** Before the first reviewer starts and after the last one finishes, hash the workspace:

```bash
( git diff HEAD; git ls-files -o --exclude-standard -z | xargs -0 -r sha256sum; sha256sum .swarm/goal_loop.json 2>/dev/null ) | sha256sum
```

If the two hashes differ, stop the review and tell the user what changed without restoring files yourself.

**Prompt for each reviewer** (fill angle brackets only):

```text
You are a Goldfish reviewer. Read $AGENT_SWARM_HOME/skills/goldfish-review/personas/<persona>.md and follow it.
Mode: REVIEW
Target: <absolute path to the document>
Scope: <whole document | lines <a>-<b> (<section>)>
Standard: $AGENT_SWARM_HOME/skills/goldfish-review/standards/<standard>.md   (omit for comprehension)
Reading list: <absolute paths, or "none">
Do not read anything under .swarm/. Do not create, change or delete files. Reply with your findings only.
```

Retry a failed or empty reviewer once; if it fails again, record `not run` (never count it as clean).

---

## Step 3: Run the Stages

| Stage | Reviewers (persona → standard) | Scope |
| :--- | :--- | :--- |
| 1. Zoom-out | `zoom-out` → `zoom-out` | whole document |
| 2. Comprehension | `comprehension` → none | whole document; **no reading list** |
| 3. Critics | `design-critic` → `feature-spec`; `style` → `feature-spec` | everything above `## Detailed Implementation Plan` or `## Implementation Plan` (whole document if no plan) |
| 4. Readiness | `implementation-readiness` → `implementation-readiness`; `codebase-details` → `implementation-readiness`; plus `python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd <workspace> --import-design <target> --dry-run` | the plan section; if the document has no plan, record the stage as `skipped: no plan` |

**Order.** Stage 1 runs first and alone. If it reports a `Blocker`, stop and resolve it with the user (Step 5) before spending tokens on later stages. Otherwise run stages 2, 3, and 4 in parallel.

Save each reply to `.swarm/design-reviews/<target path with / replaced by __>/stage-<n>-<persona>.md` (plus `stage-4-import.md` for stage 4). Always preserve Stage 2's restatement so the user can check whether a newcomer understood the spec.

---

## Step 4: Consolidate

Write `report.md` in the same folder: (1) reviewer status table (`completed`, `not run`, `skipped`); (2) merged findings (same scope + same issue = highest severity, all raising reviewers listed); (3) ordered `Blocker` → `Major` → `Nit`.

---

## Step 5: Resolve With the User (Harness Poll)

Classify every item in `resolution.md`:

| Category | Use when | Action |
| :--- | :--- | :--- |
| `PROPOSE FIX` | The finding is valid. | Give the exact edit. |
| `CONTEST` | The finding is wrong, with checkable evidence in a file the reviewer could read. | Cite `file:symbol` or exact document lines. |
| `ESCALATE` | Needs product/author judgment or evidence outside what the reviewer could read. | Poll the user via the harness polling tool; do not guess. |
| `DECLINE` | A `Nit` not worth changing. | Record it. |

Rules:
- Comprehension gaps are never contested: if a fresh reader missed it, context is missing.
- `"This was intentional"` is not evidence; use `PROPOSE FIX` or `ESCALATE`.
- Never downgrade a severity; contest with evidence if you disagree.

Link `resolution.md`, poll each `ESCALATE` question via the **harness polling tool** (`ask_question` / `AskUserQuestion` / `request_user_input`) with `(Recommended)` first, and poll the overall resolution gate: `(Recommended) Accept all proposed fixes`, `Review item by item`, or `Apply no changes`. No edit to the document happens before that answer.

---

## Step 6: Apply and Re-Run Once

Apply accepted edits (recording settled `ESCALATE` choices in `## Resolved Decisions`, never as `## Open Questions`). Re-run, once, each stage whose scope changed, and run Steps 4–5 once more. Record any remaining open items as accepted trade-offs in the document and close the review (reporting counts to `/design-draft` or `/product-discovery` when called by them).

---

## Red Flags

- *"I'll review it myself in this session; it's faster."* → **STOP.** Same-context review shares the Elephant's blind spots.
- *"I'll park `ESCALATE` questions inside the design's `Open Questions` section."* → **STOP.** Poll via the harness polling tool and write only settled decisions.
- *"I'll fix the obvious items before polling."* → **STOP.** No edit before the user's Step 5 answer.
- *"One more round will make it perfect."* → **STOP.** One re-run per changed stage, then close.
