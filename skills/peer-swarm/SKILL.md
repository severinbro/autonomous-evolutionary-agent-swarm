---
name: peer-swarm
description: "Use when one large build (roughly 15+ minutes for a single agent) splits along natural module boundaries and finishing sooner is worth about twice the tokens: several peer agents share one goal and coordinate through a board, with no orchestrator or reviewer."
---

# Peer Swarm: Shared Goal, Self-Organising Peers (`/peer-swarm`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

Several peer agents work at the same time in one workspace toward one shared goal. Nobody assigns work: the peers split it themselves on a shared board, negotiate the interfaces between their parts, test each other's work, and stop when the shared acceptance checks pass. You only set up the goal and the board, start the peers, and verify the result.

## When to use it, and when not

| Situation | Use |
| :--- | :--- |
| A single agent would need ~15+ minutes, the work splits into 2–4 parts (e.g. parser / renderer / tests), and wall time matters more than tokens | **`/peer-swarm`** |
| Smaller tasks, or tokens matter more than time | One agent with acceptance checks (see `/invoke-swarm` Lite Mode, Step 0.1 and 1.5a) |
| The work has a strict build order (contract → modules → integration) | One agent; a fixed dependency chain puts several agent start-ups in a row and cancels the parallel gain |

Evidence (`benchmarks/RESULTS.md` §7.2: a CommonMark renderer graded on the spec's 652 examples, 3 runs per arm, same model throughout): three peers matched a single checked agent's quality in every run (652/652) and finished in 0.57× the wall time (617 s vs 1,075 s), using 1.92× the tokens. The same peers on smaller tasks saved nothing: 1.24× the wall time on a task one agent finishes in ~3.5 minutes and 0.97× on a ~7-minute task, each at about 3× the tokens. Below roughly 10 minutes of single-agent work, use one agent.

## Procedure

### 1. Write the goal and its acceptance checks
Put the task in `TASK_SPEC.md` at the workspace root: what to build, the required files and API, and an *Acceptance Criteria & Self-Checks* section with the verification command, the outcome command, and any validator (for HTML, `web_ui_validator.py`). Every peer reads this file; it is the only definition of done. Check each acceptance item against the requirement it restates (see `/invoke-swarm` Step 0.1).

### 2. Create the board
```bash
mkdir -p .swarm && cp "$AGENT_SWARM_HOME/skills/peer-swarm/board_template.md" .swarm/board.md
```
Do not pre-fill the Items section. Letting the peers split the work themselves is the point; in testing they reliably found a sensible split (for a Markdown renderer: block parser / inline parser / wrapper, CLI and tests) and agreed interfaces before building on them.

### 3. Start the peers at the same time
Start 3 peers concurrently (3 is the only count tested). Give each the same prompt, changing only the peer name:

```text
You are peer-<N>, one of 3 peers (peer-1, peer-2, peer-3) working at the same time in the workspace <WS>. Work only inside it.

All three of you share one goal: implement TASK_SPEC.md in this workspace so that its verification and outcome commands pass and the implementation is correct per the spec. There is no leader and no reviewer; you organise yourselves.

Coordinate only through .swarm/board.md:
- Read it first. Claim an item before working on it by editing the Items section; split the work so peers can make progress in parallel.
- Record interface decisions other peers depend on (module boundaries, function signatures, data types) under Decisions before relying on them.
- The others edit files concurrently: re-read the board and a file right before you change it, and do not overwrite another peer's claimed file.
- Mark items done; help with remaining items or test others' work when yours are done.

When you believe the shared goal is met (verification and outcome commands both pass), append "peer-<N>: FINISHED" under Finished and stop. Do not use subagents. Reply with at most 5 lines: what you did and the final exit codes of both commands.
```

Harness tools: Antigravity `define_subagent` / `invoke_subagent`; Claude Code: the Agent tool with background runs.

### 4. Verify, then finish
When every peer has reported, check the result yourself instead of trusting the board:
```bash
<verification command> && <outcome command>
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd <WS> --scan-authenticity
```
If something fails, resume one peer with the failing output (or start one fresh peer with the board as context). Do not restart the whole swarm.

## What to watch for

- **Concurrent edits.** Peers claim files on the board; overlapping edits to one file are the main failure mode of peer setups. If the board shows two peers working in the same file, that is the first place to look when something breaks.
- **Premature FINISHED.** A peer may mark itself finished while others are still working; the swarm is done only when all peers have reported *and* your own check in step 4 passes.
- **Cost.** Expect roughly 2× the tokens of a single agent for about half the wall time. If time does not matter, use one agent.
