# Harness-Native Elephant Polling & Read-Only Goldfish Reference

Every interactive **Elephant** skill (`/coop-brainstorm`, `/design-draft`, `/goldfish-review`, `/drift-report`, `/product-discovery`, `/ui-ux-design`, and `/discriminator-gate` escalations) follows this cross-harness interaction contract.

---

## 1. The Zero-Plan-Questions Iron Law

1. **Never park questions inside plan or design files.** Do not write `## Open Questions`, `[?]`, `TODO: ask`, or `Question for User:` blocks into `plan.md`, `docs/designs/<name>.md`, `.swarm/plans/*.md`, or `.swarm/blueprint/*.md`.
2. **Poll live, write decisions.** Prompt every clarification, trade-off, section-group approval, contradiction check, Goldfish review gate, and drift reconciliation **live** using the active harness's native polling tool (Section 2), then record only the **settled choice** under `## Resolved Decisions` (or the relevant spec section).
3. **Deterministic gate enforcement.** `scripts/goal_loop.py --import-design` and `scripts/goal_loop.py --verify-blueprint` fail deterministically if any non-fenced `Open Questions` heading or unresolved question marker appears in a design or blueprint document.

---

## 2. Harness-Specific Interactive Polling Tool Matrix

Always invoke the structured polling tool provided by the current harness rather than dumping open-ended questions into Markdown files or unstructured prose walls:

| Harness | Native Polling Tool | Invocation Rules & Option Conventions |
| :--- | :--- | :--- |
| **Antigravity** | `ask_question` | Pass `questions=[{"question": "...", "options": ["(Recommended) ...", "..."], "is_multi_select": False}]`. Keep options unnumbered and omit `"Other"` (the UI adds both). Place the recommended choice first, prefixed with `(Recommended)`. |
| **Claude Code** | `AskUserQuestion` | Pass `questions=[{"question": "...", "header": "<1-2 word chip>", "options": [{"label": "... (Recommended)", "description": "<what this changes>"}], "multiSelect": False}]` (1–4 questions per call; UI provides `"Other"` automatically). |
| **Codex CLI** | `request_user_input` | Pass `questions=[{"id": "<slug>", "header": "<short title>", "question": "...", "options": [{"label": "... (Recommended)", "description": "<what this changes>"}]}]`. |
| **Cursor / Other** | `ask_question` / `ask_followup_question` | Use the harness's structured multiple-choice tool with `(Recommended)` first. Fall back to a single concise numbered poll in chat **only** when the runtime exposes no structured polling tool, and wait for the reply before editing the plan. |

---

## 3. Code-First Decision-Tree Grilling Protocol

Synthesized from Google's **Elephant-Goldfish Model (EGM)**, **`mattpocock/skills` (`/grill-me`)**, **`garrytan/gstack` (`/office-hours`)**, **`addyosmani/agent-skills`**, and **`DietrichGebert/ponytail`**:

1. **Code Before Poll (Epistemic Lookup):** Inspect the repository (`Read`, `Grep`, `Glob`) and discovery artifacts first. **Never poll the user for a fact the codebase already answers**—cite `path:line` and move to real design choices.
2. **Framing & Radical YAGNI Challenge:** Before polling implementation details, verify whether the request addresses the root problem rather than a symptom, and check whether existing code or the standard library already covers it (`Condition A: PROJECT ALREADY OPTIMAL` or shortest-path reuse).
3. **Decision-Impact Options:** Every option in a poll states what changes in the architecture, behavior, or scope if chosen, with `(Recommended)` first and backed by codebase or benchmark evidence.
4. **Branch-by-Branch Closure:** Walk unsettled branches of the decision tree via the polling tool (1–4 tightly scoped questions per round) until zero ambiguities remain before writing tasks.

---

## 4. Read-Only Goldfish Subagent Spawning Matrix

Goldfish reviewers (`/goldfish-review`, `/coop-brainstorm` lenses, `/drift-report` semantic check) must start with **zero conversation history** and **no file-write tools**:

| Harness | Read-Only Subagent Invocation |
| :--- | :--- |
| **Antigravity** | `define_subagent(Name="goldfish_<persona>", EnableWriteTools=False, ...)` followed by `invoke_subagent(...)`. |
| **Claude Code** | `Agent` tool with `subagent_type: "goldfish"` (`agents/goldfish.md`, restricted to `tools: Read, Grep, Glob`). |
| **Codex CLI** | `spawn_agent` in read-only sandbox (`sandbox_mode: "read-only"`). |
| **No subagent tool** | **Stop** and notify the user via the harness polling tool. Never substitute a same-context self-review for a Goldfish review. |

Always record the workspace SHA-256 snapshot before the first Goldfish starts and verify it is unchanged after the last one finishes.
