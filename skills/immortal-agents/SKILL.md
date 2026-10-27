---
name: immortal-agents
description: "Use when long-running worker agents stall, lose their connection, or need reviving, when background tasks must restart automatically, or when tracking which fix round a worker is in."
disable-model-invocation: false
triggers: [user, model]
---

# Immortal Watcher Supervisor, Sub-Agent Revival & 5-Round Escalation Guide (`/immortal-agents`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

## Overview

The **Immortal Agents** supervisor (`immortal_watcher` sub-agent + `immortal_watcher.py` daemon) provides fault tolerance against network/stream interruptions, automatic sub-agent revival, and strict enforcement of the **5-Round Escalating Fix Loop** so workers never thrash indefinitely on a failing task.

> [!IMPORTANT]
> ## The Iron Law
> ```
> NO INFINITE SAME-WORKER THRASHING AND NO UNLOGGED STALLS — ENFORCE THE 5-ROUND ESCALATING FIX LOOP AND ROUND 5 RULING BREAKER
> ```
> Never send a 4th refinement prompt to the same failing worker conversation, and never attempt a 6th fix round. Rounds 1–3 use the same worker; Rounds 4–5 MUST spawn a **fresh escalated subagent** with clean context; if Round 5 fails, record a binding **`Ruling:`** breaker in `.swarm/ledger.md` and halt automatic retries on that task.

---

## 1. Dual-Layer Resilience Architecture

1. **`immortal_watcher` Sub-Agent (Antigravity Agent Layer):**
   - Defined via `define_subagent(name="immortal_watcher", enable_write_tools=True, enable_subagent_tools=True)`.
   - Inspects active worker sub-agents via `manage_subagents(Action="list")` and `immortal_watcher.py --check-subagents --json` (which inspects each worker's `~/.gemini/antigravity/brain/<conv_id>/.system_generated/logs/transcript.jsonl`).
   - Distinguishes **Infrastructure Interruptions** (network drop, stream cut, `status == "ERROR"` mid-step) from **Refinement Loop Failures** (worker finished turn but failed the Discriminator gate or test suite).
2. **`immortal_watcher.py` Daemon (OS & Ledger Layer):**
   - Monitors internet connectivity probes (`captive.apple.com` / `1.1.1.1`), OS background processes, sub-agent transcript mtime/activity, `.swarm/immortal_state.json`, and the Discriminator evaluation ledger (`.swarm/ledger.md` / `swarm_tasks.json`).

---

## 2. The 5-Round Escalating Fix Loop & Round 5 `Ruling:` Breaker

Track every task's refinement round (`1..5`) deterministically across `.swarm/goal_loop.json`, `.swarm/immortal_state.json`, and `.swarm/ledger.md`:

| Refinement Round | Assigned Executor | Mandatory Supervisor Action |
| :--- | :--- | :--- |
| **Rounds 1–3: Same-Worker Micro-Refinement** | Original Worker (`<worker_conv_id_1>`) | Send targeted Discriminator defect list (`path:line` + failing test output) via `send_message` to the existing worker. (Infrastructure stream drops revive the same worker via `--mark-revived` without advancing the refinement round if no review occurred.) |
| **Rounds 4–5: Fresh Escalated Subagent (Context Reset)** | **New Escalated Subagent (`<worker_conv_id_2>`)** | **Retire `<worker_conv_id_1>`.** Spawn a fresh subagent on the branch via `invoke_subagent` with an escalated diagnostic prompt containing ONLY: (1) locked contract & task spec, (2) current `git diff`, (3) exact failing test traceback, and (4) a 3-bullet summary of approaches that failed in Rounds 1–3. |
| **After Round 5 Failure: Circuit Breaker (`Ruling:`)** | **HALTED (Orchestrator / Human Gate)** | **STOP all worker retries on this task.** Record a typed ruling with `goal_loop.py --record-task <TASK_ID> --ruling-type <OVERRIDE \| SPLIT_TASK \| RE_ARCHITECT_CONTRACT \| ESCALATE_TO_USER> --ruling "..."` (see `/discriminator-gate`), citing the exact `path:line` failure and root cause. `OVERRIDE` is rejected while the audit reports any `BLOCKING_FAIL`. |

### Required `.swarm/ledger.md` Round 5 Breaker Format:
```markdown
### [Round 5 Breaker] Task <Task_ID> (<branch>) — <ISO-8601 Timestamp>
- **Rounds 1–3 Worker:** `<conv_id_1>` (Best Score: `<X.X>/10`, Primary Failure: `<path:line>`)
- **Rounds 4–5 Escalated Worker:** `<conv_id_2>` (Best Score: `<Y.Y>/10`, Primary Failure: `<path:line>`)
- **Ruling:** `<OVERRIDE | SPLIT_TASK | RE_ARCHITECT_CONTRACT | ESCALATE_TO_USER>` — `Ruling: <what you decided> — <why> — <what it costs if wrong>`
```

---

## 3. CLI Reference (`immortal_watcher.py`)

```bash
# 1. Initialize swarm ledger for a new run:
python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" \
  --init-swarm --project-goal "<Overall Project Goal>"

# 2. Start the background supervisor daemon:
python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" --start

# 3. Register a spawned worker sub-agent (or Round 4-5 escalated sub-agent):
python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" \
  --register-subagent "<worker_conv_id>" \
  --role "<Role>" \
  --branch "<branch-name>" \
  --impl-goal "<Implementation Goal>"

# 4. Check all registered sub-agents for stalls, stream errors, or round limits:
python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" --check-subagents --json

# 5. Record an infrastructure sub-agent revival event:
python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" --mark-revived "<worker_conv_id>"

# 6. Record a Discriminator review for round tracking (pass/fail is the same categorical gate as goal_loop.py):
python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" \
  --record-review "<worker_conv_id>" \
  --impl-score 8.5 \
  --goal-score 9.0 \
  --notes "Passed all unit tests and architectural checks"

# 7. Record final Orchestrator whole-project evaluation:
python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" \
  --record-overall --overall-score 9.2 --tests-passed --security-passed \
  --notes "Merged all branches, integration & security suites passed"

# 8. Check status or stop daemon:
python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" --status
python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" --stop
```

---

## 4. Failure Mode & Revival Matrix

| Failure Mode | Observable Detection Signal | Automated Recovery Action |
| :--- | :--- | :--- |
| **Stream / Network Interruption** | Transcript last step `status == "ERROR"` or `"stream was interrupted"` | `immortal_watcher` sends revival prompt via `send_message` to `<worker_conv_id>` and runs `--mark-revived`. |
| **Stalled / Frozen Sub-Agent** | Transcript mtime idle `>= stall_seconds` without `"TASK FINISHED"` | `immortal_watcher` sends wakeup & checkpoint continuation prompt via `send_message`. |
| **Round 3 Gate Failure** | Worker's Round 3 review still fails the gate | Retire worker 1; spawn fresh escalated subagent for Round 4 with clean context and Round 1–3 failure summary. |
| **Round 5 Gate Failure** | Escalated subagent's Round 5 review still fails the gate | Stop retries; write `Ruling:` breaker entry to `.swarm/ledger.md`; escalate to Orchestrator. |
| **Wi-Fi / ISP Outage** | Probe fail on `captive.apple.com` and `1.1.1.1` | Pause worker queues; log outage start; trigger sub-agent revival checks once connectivity recovers. |
| **Crash of Background OS Task** | Process PID no longer alive before validation passes | `immortal_watcher.py` automatically respawns the task process (up to 5 attempts). |

---

## 5. Red Flags — STOP and Follow Process

If you catch yourself thinking any of these, **STOP immediately** and enforce the Immortal Agents protocol:
- *"The worker is at `7.5/10` after Round 3; I'll just message the same worker a 4th time since it already has the files in context."*
- *"Round 5 failed, but one more tweak in Round 6 will definitely get it through the gate."*
- *"I'll poll `manage_subagents(Action='list')` in a tight loop every 10 seconds instead of waiting for reactive wakeup or using `schedule`."*
- *"A worker stalled and went idle without `TASK FINISHED`; I'll just merge its partial branch as-is."*

---

## 6. Common Rationalizations

| Excuse | Reality |
| :--- | :--- |
| `"Keeping the same worker for Round 4 preserves context"` | After 3 failed rounds, the worker's context is polluted with failed hypotheses and sunk-cost bias. A fresh Round 4 subagent breaks the loop. |
| `"Round 6 is faster than writing a Ruling in .swarm/ledger.md"` | 5 failed rounds across 2 distinct agents prove the task spec or contract is flawed. Write the `Ruling:` breaker and fix the architecture. |
| `"Polling status in a loop ensures I catch completion fast"` | Antigravity wakes you reactively when a subagent messages or completes. Tight polling wastes tokens and bloats `transcript.jsonl`. |
| `"Stream error means the task is impossible"` | Stream/network errors are transient infrastructure drops. Revive via `send_message` + `--mark-revived`. |

---

## 7. Zero-Context-Bloat Subagent Return Contract (`< 15 Lines`)

When `immortal_watcher` reports status or completes a supervision cycle, write full state to `.swarm/immortal_state.json` and `.swarm/ledger.md` and return ONLY this `< 15 lines` summary to the Orchestrator:

```markdown
Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
Ledger State: .swarm/immortal_state.json, .swarm/ledger.md
Active / Completed Workers: <N completed>, <M running>, <K revived>, <E escalated (Rounds 4-5)>
Worker Round Summary:
- <Task/Role 1> (<conv_id>): Round <1-5>/5 | Score: <impl>/<goal> | State: <APPROVED | ESCALATED_R4 | RULING_BREAKER>
- <Task/Role 2> (<conv_id>): Round <1-5>/5 | Score: <impl>/<goal> | State: <APPROVED | ESCALATED_R4 | RULING_BREAKER>
Round 5 Rulings Triggered: None (or `Ruling: <TYPE>` on <Task_ID> — see .swarm/ledger.md:<line>)
Infrastructure Health: Network=<ONLINE/RECOVERED>, Revivals=<K>
```
