---
name: autonomous-agent-swarm
description: Run an autonomous multi-agent swarm with an orchestrator, sandboxed subagents in Git worktrees, Ralph goal loops, on-demand immortal task revival, and runtime quality validation. Use when the user requests an autonomous team of agents or complex multi-agent project development.
triggers: [user, model]
---

# Autonomous Agent Swarm Skill

This skill enables any agent harness (Antigravity, Claude Code, Codex CLI, Cursor) to act as a **Strategic Orchestrator**, coordinating autonomous workers in isolated sandboxes while enforcing runtime product quality gates.

---

## 1. Orchestrator Principles

* **Concise Thinking & Quota Conservation:** Keep internal reasoning compact. Avoid stream-of-consciousness monologues.
* **Delegation Imperative:** Never perform massive file edits directly in the orchestrator conversation. Break down features into decoupled tasks and delegate them.
* **The 2-Attempt Anti-Loop Rule:** If an error or bug is not solved within 2 attempts, stop monolithic editing. Delegate to a diagnostic worker or consult the user.
* **Never Equate Compilation with Product Completion:** Always verify runtime stability with an automated smoke test before declaring success.

---

## 2. Execution Workflow

### Step 1: Start the Immortal Task Supervisor
Before spawning workers, launch the background watcher daemon:
```bash
python3 scripts/immortal_watcher.py --start
```
*To inspect status:* `python3 scripts/immortal_watcher.py --status`

### Step 2: Co-Plan with the User
Produce a concise design plan (`docs/DESIGN.md`) decomposing the project into independent modules.

### Step 3: Provision Isolated Worktree Sandboxes
For each decoupled task, provision a dedicated Git worktree so parallel workers never collide:
```bash
python3 scripts/worktree_manager.py create <branch-name>
```

### Step 4: Dispatch Tasks with the 4-Part Goal Loop Contract
Every subagent prompt must strictly define:
```markdown
**Objective:** <Concrete one-sentence outcome>
**Workspace:** Isolated worktree sandbox. Only touch designated files.
**Constraints:** Do not weaken or delete tests; preserve existing architecture.
**Validation Command:** <Exact shell test command, e.g. pytest, npm test>
**Stop Condition:** Validation command exits with code 0.
```

### Step 5: Persistent Task Supervision (Auto-Revival)
If running headless or long-running workers, register the task with the supervisor:
```bash
python3 scripts/immortal_watcher.py --register-task "<task_name>" --command "<worker_run_cmd>" --validation "<validation_cmd>"
```
The supervisor checks process heartbeats every 10s. If a worker process exits or dies before the validation command passes, the supervisor **automatically restarts and revives it** (up to 5 attempts).

### Step 6: Mandatory Runtime Quality Gate
Before merging, run the automated smoke tester on the compiled executable or runtime service:
```bash
python3 scripts/quality_validator.py <path_to_binary> --timeout 10
```
* If the smoke test crashes or logs unhandled exceptions, the supervisor/orchestrator feeds the crash stack trace back to a worker to fix.
* Once the test reports **PASS**, merge the worktree branch into `main` and clean up:
  ```bash
  git merge --no-ff <branch-name>
  python3 scripts/worktree_manager.py cleanup <branch-name>
  ```

### Step 7: Teardown
```bash
python3 scripts/immortal_watcher.py --stop
```

---

## 3. Hardware Accelerators & Graceful Fallbacks

* **Math Engine (Limite 1B - Violetto on GPU 0):** If `/mnt/sda/development/scripts/math_eval.py` is present, route complex trigonometry/physics to it. Otherwise, solve natively using LLM reasoning or Python SymPy scripts.
* **Local Coder (Qwen 2.5 Coder on GPU 1):** If `/mnt/sda/development/scripts/qwen_coder.py` is present, route offline boilerplate to it. Otherwise, workers synthesize code directly in their standard conversation loop.
