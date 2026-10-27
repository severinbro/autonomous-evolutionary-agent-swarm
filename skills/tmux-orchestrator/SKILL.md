---
name: tmux-orchestrator
description: "Use when running, monitoring, or messaging background agents, CLI tools, or build processes in Linux tmux sessions and panes."
disable-model-invocation: true
triggers: [user, model]
---

# Linux Tmux Agent Orchestrator

This skill provides a reliable CLI runbook for running, monitoring, and communicating with background agents, CLI tools (like Codex CLI, Cursor CLI, Claude Code), and headless processes on Ubuntu using `tmux`.

---

## 1. Quick Reference Commands

### Start a Dedicated Agent Session (in a specific Worktree)
```bash
tmux new-session -d -s swarm-worker-1 -c /path/to/worktree
```

### Send Command or Instruction (Non-blocking)
```bash
# Send command and press enter:
tmux send-keys -t swarm-worker-1 "npm test" C-m

# For interactive agent prompts:
tmux send-keys -t swarm-worker-1 "Fix the failing tests in src/player.ts" C-m
```

### Inspect Output (Capture Pane)
```bash
# Read the last 150 lines from the pane:
tmux capture-pane -pt swarm-worker-1 -S -150
```

### Check Process & Pane Status
```bash
# Returns 1 if process died, 0 if still active:
tmux list-panes -t swarm-worker-1 -F "#{pane_dead} #{pane_current_command}"
```

### Terminate / Clean Up Session
```bash
tmux kill-session -t swarm-worker-1
```

---

## 2. Multi-Worker Layout (Split Panes)

To monitor multiple workers side-by-side in a single tmux window:

```bash
# Create base session:
tmux new-session -d -s swarm -n workers -c /path/to/repo

# Split horizontally for Worker 2:
tmux split-window -t swarm:workers -h -c /path/to/worktree-2

# Split vertically for Worker 3:
tmux split-window -t swarm:workers.0 -v -c /path/to/worktree-3

# Send tasks to specific panes:
tmux send-keys -t swarm:workers.0 "task 1 command" C-m
tmux send-keys -t swarm:workers.1 "task 2 command" C-m
tmux send-keys -t swarm:workers.2 "task 3 command" C-m
```
