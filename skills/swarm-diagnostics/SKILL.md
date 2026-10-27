---
name: swarm-diagnostics
description: "Use when an Antigravity agent or swarm session went wrong and the cause is needed: repeated work, an ignored plan, endless fix loops, a skill that never fired, stalled subagents, or unexpectedly high time or token cost."
disable-model-invocation: false
triggers: [user, model]
---

# Evidence-Cited Session & Swarm Diagnostics (`/swarm-diagnostics`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

## Overview

Pin down what happened in a current or past Antigravity conversation and its child subagents by running `scripts/swarm_diagnostics.py` against `~/.gemini/antigravity/brain/<conversation-id>/.system_generated/logs/transcript.jsonl` and the workspace `.swarm/` directory (`goal_loop.json`, `ledger.md`, `deferred_minor_ledger.md`, `immortal_state.json`).

> [!IMPORTANT]
> ## The Iron Law
> ```
> EVERY FINDING CITES path:line OR step_index — NO CITATION, NO FINDING
> ```
> Every count, duration, tool error, and loop escalation MUST come from `scripts/swarm_diagnostics.py` or a verified line in `transcript.jsonl` / `.swarm/`, never from memory or speculation. Never open raw multi-megabyte `transcript.jsonl` files directly in LLM context before running `swarm_diagnostics.py`.

---

## 1. Quick Triage Reference (Complaint $\rightarrow$ Lead Dimension)

All 7 diagnostic dimensions run automatically in `swarm_diagnostics.py`. Lead your verdict with the dimension matching the user's symptom:

| User Complaint / Symptom | Lead Dimension(s) to Inspect First |
| :--- | :--- |
| `"It took too long"` / `"Where did the time go?"` | `7. cost-and-time`, `5. stumbles` |
| `"Why did it do this extra/repeated work?"` | `4. repeated-work`, `3. plan-adherence` |
| `"Why is the context so bloated / expensive?"` | `7. cost-and-time` (Top 5 Largest Transcript Lines), `2. subagent-spawns` |
| `"What are the subagents doing right now?"` | `2. subagent-spawns`, `1. skill-timeline` |
| `"It ignored the plan or skipped tasks"` | `3. plan-adherence` (`.swarm/goal_loop.json` vs actual edits) |
| `"Skill X never fired"` | `1. skill-timeline` (`SKILL.md` `view_file` events) |
| `"Why did the worker keep looping or halt?"` | `6. loop-rulings` (Round 4–5 escalations & Round 5 `Ruling:` breakers in `.swarm/ledger.md`) |

---

## 2. Running the Deterministic Diagnostic Engine (`swarm_diagnostics.py`)

Always invoke `swarm_diagnostics.py` through `python3` to stream `transcript.jsonl` safely outside the LLM context window:

```bash
# 1. Diagnose the most recent conversation in ~/.gemini/antigravity/brain/ and write markdown report:
python3 "$AGENT_SWARM_HOME/scripts/swarm_diagnostics.py" \
  --project-dir . \
  --out .swarm/diagnostics_report.md

# 2. Diagnose a specific conversation ID (e.g. parent orchestrator or a specific subagent):
python3 "$AGENT_SWARM_HOME/scripts/swarm_diagnostics.py" \
  --conversation-id "<conversation-id>" \
  --project-dir . \
  --out .swarm/diagnostics_report.md

# 3. Emit machine-readable JSON for programmatic inspection:
python3 "$AGENT_SWARM_HOME/scripts/swarm_diagnostics.py" \
  --conversation-id "<conversation-id>" \
  --project-dir . \
  --json
```

---

## 3. The 7 Superpowers Diagnostic Dimensions

`scripts/swarm_diagnostics.py` computes and cites (`transcript.jsonl:<line>` and `step_index=<N>`) these 7 dimensions in order:

1. **`skill-timeline`:** Every `view_file` call targeting a `SKILL.md` or `/skills/` path, recording `skill_name`, `transcript.jsonl:<line>`, `step_index`, and ISO-8601 timestamp. Proves whether required skills were actually read before execution.
2. **`subagent-spawns`:** Every `invoke_subagent` batch (`transcript.jsonl:<line>`, `step_index`), matched against the spawned `conversationId` and child `transcript.jsonl`. Reports child line count, whether the subagent called `send_message` back to the parent (with `child/transcript.jsonl:<line>` citation), and live state (`COMPLETED_REPORTED`, `ACTIVE_OR_IDLE_NO_REPORT`, `ERRORED`).
3. **`plan-adherence`:** Cross-references `.swarm/goal_loop.json` (`overall_goal`, `--outcome-cmd`, and tasks `T1..Tn`) against actual `write_to_file` / `replace_file_content` / `multi_replace_file_content` edits in the transcript and verifies whether `--outcome-cmd` was executed.
4. **`repeated-work`:** Flags any file edited $\ge 3$ times, any file viewed $\ge 3$ times, and any identical shell command executed $\ge 2$ times, listing every `transcript.jsonl:<line> (step_index=<N>)` occurrence.
5. **`stumbles`:** Extracts every step with `status == "ERROR"` or `The command exited with code <non-zero>`, citing the exact `transcript.jsonl:<line>`, `step_index`, preceding tool call citation, exit code, and 1-line error summary.
6. **`loop-rulings`:** Scans `.swarm/ledger.md`, `.swarm/deferred_minor_ledger.md`, and `.swarm/immortal_state.json` for Round 4–5 fresh-subagent escalations, Round 5 `Ruling:` circuit breakers (citing `.swarm/ledger.md:<line>`), subagent revivals, and deferred minor findings.
7. **`cost-and-time`:** Computes total transcript lines and byte volume, tool call distribution, total wall-clock span vs. active turn compute time (excluding user wait gaps $> 60\text{s}$), the **Top 5 Active Compute Bottlenecks** (`from_line` $\rightarrow$ `to_line`), and the **Top 5 Largest Transcript Lines** (context-bloat audit).

---

## 4. Hard Rules

- **Context Safety:** A single line in `transcript.jsonl` or `transcript_full.jsonl` can exceed 1 MB. Always run `python3 "$AGENT_SWARM_HOME/scripts/swarm_diagnostics.py"` first; never dump raw JSONL files into the prompt.
- **Read-Only Session Files:** Never modify, truncate, or delete any file under `~/.gemini/antigravity/brain/`.
- **Discard Uncited Claims:** If a hypothesized cause cannot be backed by a `transcript.jsonl:<line>` or `.swarm/<file>:<line>` citation, discard it.

---

## 5. Red Flags — STOP and Follow Process

If you catch yourself thinking any of these, **STOP immediately** and run `swarm_diagnostics.py`:
- *"I remember what happened earlier in this session, so I can summarize why it failed without running `swarm_diagnostics.py`."*
- *"I'll run `view_file` directly on `transcript_full.jsonl` to browse what happened."*
- *"The subagent probably timed out; I'll state that without checking the child's `transcript.jsonl` line count and last status."*
- *"I'll estimate the wall-clock time and number of edits instead of quoting the exact numbers."*

---

## 6. Common Rationalizations

| Excuse | Reality |
| :--- | :--- |
| `"I was in this session, I already know what went wrong"` | In-context memory misses exact step timestamps, child subagent transcripts, and silent non-zero exit codes. Run the script. |
| `"Reading transcript.jsonl with view_file is quicker"` | A single large tool result line blows out the context window. `swarm_diagnostics.py` streams lines safely in $< 0.2\text{s}$. |
| `"Approximate counts ('around 5 edits') are good enough"` | Uncited approximations hide the actual loop trigger. Cite every edit's `transcript.jsonl:<line>` (`step_index=<N>`). |
| `"Subagent went idle so it must have finished"` | Subagents that go idle without calling `send_message` never delivered their result (`ACTIVE_OR_IDLE_NO_REPORT`). Check Dimension 2. |

---

## 7. Zero-Context-Bloat Subagent Return Contract (`< 15 Lines`)

Write the complete 7-dimension report to `.swarm/diagnostics_report.md` and return ONLY this `< 15 lines` summary to the caller:

```markdown
Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
Artifact: .swarm/diagnostics_report.md (Conversation: <conversation-id>)
Session Metrics: <N> lines (<B> bytes) | Wall-Clock: <W>s (Active Compute: <A>s)
1. Skill Timeline: <S> SKILL.md reads (<unique skill names>)
2. Subagents: <M> spawned across <B_cnt> batches (<completed>/<M> sent message)
3. Plan & Repeated Work: <E> files edited (<R_edit> edited >=3x, <R_cmd> cmds re-run >=2x)
4. Stumbles & Loop Rulings: <St> stumbles | <Rul> Round-5 Rulings | <Esc> Round 4-5 escalations
Top Cited Root Causes:
1. [<Dimension>] <transcript.jsonl:line (step_index=N)> — <1-line evidence-backed finding>
2. [<Dimension>] <transcript.jsonl:line (step_index=N)> — <1-line evidence-backed finding>
```
