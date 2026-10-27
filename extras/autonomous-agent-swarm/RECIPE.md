# Cooking Recipe: Autonomous Agent Swarm with Sandboxed Subagents & Goal Loops

## Overview

This recipe sets up a production-grade **Autonomous Agent Swarm** for Antigravity on Linux. It implements a hierarchical multi-agent architecture where:
* A **Smart Orchestrator** (Claude Opus with Gemini Pro fallback) maintains architectural oversight, plans with the user, and keeps internal thinking compact to conserve token quota.
* **Fast Subagents** (Gemini 3.8 Flash) execute concrete implementation tasks inside their **own isolated Git worktree sandboxes** and dedicated conversation contexts.
* **Ralph Goal Loops** enforce autonomous self-testing (`plan → act → test → review → iterate`) until code passes verifiable criteria without premature stopping.
* An **On-Demand Immortal Watcher Daemon** monitors internet connectivity and session health, automatically recovering stalled tasks.
* **Local GPU Accelerators** (Limite 1B - Violetto for math on GPU 0, Qwen 2.5 Coder 7B on GPU 1) are supported as **optional accelerators** with automatic graceful fallbacks to cloud models on machines without dedicated GPUs.

---

## 1. System Requirements & Portability Matrix

| Feature | Standard Machine / Laptop / Cloud VM | Dedicated Workstation (Dual RTX 3060) |
| :--- | :--- | :--- |
| **Orchestrator** | Claude Opus (preferred) / Gemini Pro | Claude Opus / Gemini Pro |
| **Worker Subagents** | Gemini 3.8 Flash (`Model: "flash"`) | Gemini 3.8 Flash (`Model: "flash"`) |
| **Sandbox Isolation** | Git Worktrees via `Workspace: "share"` | Git Worktrees via `Workspace: "share"` |
| **Math Reasoning** | Native LLM reasoning + Python/SymPy | **Limite 1B - Violetto (GPU 0)** |
| **Offline Boilerplate** | Native Flash synthesis in conversation | **Qwen 2.5 Coder 7B AWQ (GPU 1)** |
| **Session Multiplexing** | Linux `tmux` (or native background tasks) | Linux `tmux` |

*The entire swarm runs cleanly on any machine with Git and Python 3.10+. If local GPU scripts are not found, the system automatically falls back to native cloud LLMs without errors.*

---

## 2. Directory Structure & File Manifest

The swarm is packaged as an Antigravity plugin located at `~/.gemini/config/plugins/agent-swarm`:

```text
~/.gemini/config/plugins/agent-swarm/
├── plugin.json
├── rules/
│   └── ORCHESTRATOR.md               # Quota conservation, delegation, and sandbox governance
├── skills/
│   ├── invoke-swarm/SKILL.md         # On-demand /invoke-swarm entry point
│   ├── goal-loop/SKILL.md            # 4-part Ralph loop autonomous execution contract
│   ├── quality-validator/SKILL.md    # Product runtime smoke testing and quality gate
│   ├── immortal-agents/SKILL.md      # Supervisor reference and failure recovery
│   ├── tmux-orchestrator/SKILL.md    # Headless session and terminal management
│   └── math-reasoning/SKILL.md       # Math engine instructions with non-GPU fallbacks
└── scripts/
    ├── immortal_watcher.py           # Background connectivity and task-revival supervisor
    ├── quality_validator.py          # Automated runtime smoke tester and crash auditor
    └── worktree_manager.py           # Git worktree sandbox provisioning and diff manager
```

---

## 3. Installation & Setup

### Step 1: Create the Plugin Directories
```bash
mkdir -p ~/.gemini/config/plugins/agent-swarm/rules \
         ~/.gemini/config/plugins/agent-swarm/skills/invoke-swarm \
         ~/.gemini/config/plugins/agent-swarm/skills/goal-loop \
         ~/.gemini/config/plugins/agent-swarm/skills/immortal-agents \
         ~/.gemini/config/plugins/agent-swarm/skills/tmux-orchestrator \
         ~/.gemini/config/plugins/agent-swarm/skills/math-reasoning \
         ~/.gemini/config/plugins/agent-swarm/scripts
```

### Step 2: Create `plugin.json`
Save to `~/.gemini/config/plugins/agent-swarm/plugin.json`:
```json
{
  "name": "agent-swarm",
  "displayName": "Autonomous Agent Swarm Toolkit",
  "version": "1.0.0",
  "description": "Multi-agent autonomous swarm architecture: orchestrator governance, sandboxed subagents in Git worktrees, Ralph goal loops, on-demand immortal-agents supervisor daemon, and GPU-accelerated local math/coding models.",
  "author": { "name": "Antigravity Swarm Architecture" },
  "keywords": ["multi-agent", "orchestrator", "subagents", "sandboxing", "git-worktree", "goal-loop", "immortal-agents"]
}
```

### Step 3: Create Orchestrator Governance Rules
Save to `~/.gemini/config/plugins/agent-swarm/rules/ORCHESTRATOR.md`:
* Specifies Claude Opus as primary orchestrator with Gemini Pro fallback.
* Enforces concise thinking to conserve tokens.
* Enforces subagent delegation with `Workspace: "share"` (Git worktree sandboxes).
* Restricts live editor MCP tools (Unity/Blender) to single sequential execution to prevent scene corruption.
* Configures local GPU models (Limite / Qwen) as optional accelerators with cloud fallbacks.

### Step 4: Install Scripts and Set Permissions
Ensure the helper scripts are executable:
```bash
chmod +x ~/.gemini/config/plugins/agent-swarm/scripts/immortal_watcher.py
chmod +x ~/.gemini/config/plugins/agent-swarm/scripts/worktree_manager.py
```

### Step 5: Verify the Setup
Run a diagnostic health check:
```bash
python3 ~/.gemini/config/plugins/agent-swarm/scripts/immortal_watcher.py --test-run
```
Expected output:
```text
Immortal Watcher started. Monitoring connectivity and swarm sessions.
HEALTH CHECK OK | Online: True | Active Swarm Tmux Sessions: 0 []
Test run completed successfully.
```

---

## 4. How to Use the Swarm (`/invoke-swarm`)

### Triggering the Swarm
Whenever you want to build a major feature, game system, or application, simply type:
```text
/invoke-swarm
```
*(Or say: "Start an autonomous swarm to build [feature]...")*

### The Execution Workflow

1. **On-Demand Supervisor Launch:**
   `/invoke-swarm` starts `immortal_watcher.py` in the background to monitor network connectivity and agent heartbeats.
2. **Co-Planning:**
   The Orchestrator clarifies requirements with you, writes a concise architecture/design document (`docs/DESIGN.md`), and decomposes the work into decoupled subtasks.
3. **Spawning Sandboxed Subagents:**
   The Orchestrator calls `invoke_subagent` with:
   * `Workspace: "share"`: Provisions an isolated Git worktree branch for each subagent.
   * `Model: "flash"`: Fast Gemini 3.8 Flash worker.
   * **The 4-Part Goal Loop Contract:**
     ```markdown
     **Objective:** <Concrete one-sentence outcome>
     **Constraints:** <Files allowed to touch, libraries, APIs to avoid>
     **Validation Command:** <Exact command, e.g. pytest tests/test_movement.py>
     **Stop Condition:** <Validation command exits with code 0>
     ```
4. **Autonomous Iteration:**
   Subagents iterate in their worktree (`edit → test → fix`) until their tests pass.
5. **Merge & Teardown:**
   The Orchestrator inspects the worktree diff, runs integrated tests on `main`, merges the branch, cleans up the worktree, and stops the supervisor daemon.

---

## 5. Optional Local GPU Engines Configuration

### Limite 1B - Violetto (Math Reasoning on GPU 0)
* **Location:** `/mnt/sda/development/scripts/math_eval.py`
* **Port:** Served via vLLM on `http://127.0.0.1:8000/v1`
* **Trigger:** Complex trigonometry, collision formulas, coordinate math, or algorithmic proofs.
* **Fallback:** On machines without this script or GPU, the orchestrator/subagent solves math natively or runs `python3 -c "import math, sympy; ..."`.

### Qwen 2.5 Coder 7B AWQ (Offline Boilerplate on GPU 1)
* **Location:** `/mnt/sda/development/scripts/qwen_coder.py`
* **Port:** Served via vLLM on `http://127.0.0.1:8001/v1`
* **Trigger:** Standalone, repetitive boilerplate code where zero API token consumption is desired.
* **Fallback:** On standard machines, workers write code directly in their standard conversation turn.

---

## 6. Operational Cheat Sheet

### Worktree Sandbox Management
```bash
# List all active worktree sandboxes:
python3 ~/.gemini/config/plugins/agent-swarm/scripts/worktree_manager.py list

# View diff of a worker's branch against main:
python3 ~/.gemini/config/plugins/agent-swarm/scripts/worktree_manager.py diff feat/player-movement

# Clean up and prune a merged worktree:
python3 ~/.gemini/config/plugins/agent-swarm/scripts/worktree_manager.py cleanup feat/player-movement
```

### Immortal Watcher Supervisor Controls
```bash
# Check if supervisor is running:
python3 ~/.gemini/config/plugins/agent-swarm/scripts/immortal_watcher.py --status

# View recent supervisor logs:
python3 ~/.gemini/config/plugins/agent-swarm/scripts/immortal_watcher.py --logs

# Manually stop supervisor:
python3 ~/.gemini/config/plugins/agent-swarm/scripts/immortal_watcher.py --stop
```

### Headless Tmux Worker Inspection (Ubuntu)
```bash
# View output of a headless tmux worker:
tmux capture-pane -pt swarm-worker-1 -S -100

# Kill a stalled tmux session:
tmux kill-session -t swarm-worker-1
```

---

## 7. Product Quality Gate Validation

Never consider a build or game finished based on compiler success alone.
```bash
# Run the automated smoke tester on the built binary:
python3 ~/.gemini/config/plugins/agent-swarm/scripts/quality_validator.py /path/to/game.x86_64 --timeout 10
```
* **PASS:** Game binary booted, attached to `:0`, initialized physics/input, and ran for 10s with zero crashes or fatal exceptions.
* **FAIL:** Binary crashed (e.g. `SIGTRAP` / `Trace/breakpoint trap` core dump, `NullReferenceException`). Automatically outputs crash trace to feed back into the swarm for auto-repair.

---

## 8. Root Cause Analysis: Why Earlier Runs Failed & How This Fixes It

1. **Why Claude Opus Wasn't Used:**
   * In Antigravity, the Orchestrator model is governed strictly by the **top-level chat UI Model Selection dropdown**.
   * If the UI is set to `Gemini 3.8 Flash (High)`, the orchestrator runs on Flash.
   * **Fix:** Manually switch the UI dropdown to **Claude 3.5 / 3.7 / Opus** in Antigravity before typing `/invoke-swarm`.

2. **Why Separate Chat Tabs Weren't Seen:**
   * Antigravity subagents run as headless background worker tasks that report to the parent via background RPC. They do not open separate browser/chat UI tabs.
   * After the initial 4 subagents finished, the agent mistakenly entered a monolithic 700-step loop trying to debug Unity alone.
   * **Fix:** `ORCHESTRATOR.md` now enforces the **2-Attempt Limit**—the orchestrator is strictly forbidden from trying to fix errors itself in a monolithic loop, forcing it to delegate to diagnostic subagents.

3. **Why the Game Crashed & Iterated Aimlessly:**
   * Unity compiled cleanly, so the agent assumed it worked. But upon spawning the player at `(-465.00, 7.50, -30.00)`, an unhandled runtime exception triggered a `Trace/breakpoint trap (core dumped)`.
   * **Fix:** The `quality-validator` skill and `quality_validator.py` script now enforce an automated runtime smoke test on the real binary before declaring any task done.

