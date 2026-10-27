#!/usr/bin/env python3
"""Immortal Agents Watcher, Subagent Revival & Multi-Epoch Evolutionary Swarm Ledger.

Supports both the full 3-Epoch `/invoke-swarm` Macro-Loop and standalone execution
of individual loop stages (`/discriminator-gate`, `/triad-audit`, `/sota-web-scout`,
`/epoch-planner`, `/immortal-agents`):
  - Step 0.25: Pre-Flight Conflict & Dependency Scan (`goal_loop.py --preflight`)
  - Step 1: Parallel Implementation Subagents (`--task-brief <ID>`) + `immortal_watcher` revival
  - Step 1.5: `discriminator` Two-Verdict Categorical Gate + Hard-Cap Rubric & 5-Round Escalating Fix Loop:
      * Rounds 1-3: Resume the SAME worker subagent (scoped re-review `FIX_BASE..HEAD`)
      * Rounds 4-5: Spawn a FRESH escalated worker subagent
      * Round 5 Breaker: Orchestrator records `Ruling: <what> — <why> — <cost if wrong>` in `.swarm/ledger.md`
      * Minor findings: Logged to `.swarm/deferred_minor_ledger.md` (never block task completion)
  - Step 2-3: Orchestrator merge & Intermittent Report tracking
  - Step 4-5: Triad Audit Agents (`rigor`, `safety`, `innovation`) 1-10 scoring & findings
  - Step 6: Parallel `sota_web_scout` continuous SOTA benchmarking & 1-10 scoring
  - Step 7: Deterministic Convergence Check (`.swarm/goal_loop.json`, `.swarm/ledger.md`, `.swarm/deferred_minor_ledger.md`)
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(PLUGIN_DIR, "scripts", "immortal_watcher.log")
PID_FILE = os.path.join(PLUGIN_DIR, "scripts", "immortal_watcher.pid")
GLOBAL_TASKS_FILE = os.path.join(PLUGIN_DIR, "scripts", "swarm_tasks.json")
BRAIN_DIR = os.path.expanduser("~/.gemini/antigravity/brain")

PROBE_URL = "http://captive.apple.com/hotspot-detect.html"
PROBE_TIMEOUT = 5
CHECK_INTERVAL = 10
MAX_REVIVE_ATTEMPTS = 5
MAX_DISCRIMINATOR_LOOPS = 5
ESCALATION_FRESH_WORKER_ROUND = 4
BREAKER_RULING_ROUND = 5
MAX_MACRO_EPOCHS = 3
HARD_MAX_REMEDIATION_EPOCHS = 10
PASSING_SCORE_THRESHOLD = 8.0
HARD_CAP_BLOCKING = 6.0
HARD_CAP_IMPORTANT = 7.0
BASELINE_UNPROBED_CEILING = 8.5
ADVERSARIAL_LOOP1_CEILING = 9.5
ADVERSARIAL_REFINED_CEILING = 9.8
CONVERGENCE_RIGOR_THRESHOLD = 9.0
CONVERGENCE_SAFETY_THRESHOLD = 9.0
CONVERGENCE_INNOVATION_THRESHOLD = 8.5
DEFAULT_STALL_SECONDS = 180


def resolve_tasks_file(create_local_dir: bool = False) -> str:
    """Resolve per-workspace .swarm/swarm_tasks.json first, falling back to global plugin state."""
    env_override = os.environ.get("SWARM_TASKS_FILE")
    if env_override:
        return os.path.abspath(env_override)

    curr = os.path.abspath(os.getcwd())
    while True:
        candidate_dir = os.path.join(curr, ".swarm")
        if os.path.isdir(candidate_dir):
            return os.path.join(candidate_dir, "swarm_tasks.json")
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent

    if create_local_dir and os.path.abspath(os.getcwd()) != PLUGIN_DIR:
        local_swarm = os.path.join(os.path.abspath(os.getcwd()), ".swarm")
        os.makedirs(local_swarm, exist_ok=True)
        return os.path.join(local_swarm, "swarm_tasks.json")

    return GLOBAL_TASKS_FILE


def inspect_swarm_ledgers(cwd: str | None = None) -> dict[str, Any]:
    """Inspect `.swarm/goal_loop.json`, `.swarm/ledger.md`, and `.swarm/deferred_minor_ledger.md`."""
    base = os.path.abspath(cwd or os.getcwd())
    swarm_dir = os.path.join(base, ".swarm")
    goal_json_path = os.path.join(swarm_dir, "goal_loop.json")
    ledger_md_path = os.path.join(swarm_dir, "ledger.md")
    minor_md_path = os.path.join(swarm_dir, "deferred_minor_ledger.md")

    rulings_count = 0
    rulings_list: list[str] = []
    ledger_entries = 0
    if os.path.isfile(ledger_md_path):
        try:
            for ln in Path(ledger_md_path).read_text(encoding="utf-8", errors="replace").splitlines():
                if ln.strip().startswith("- "):
                    ledger_entries += 1
                if "Ruling:" in ln:
                    rulings_count += 1
                    rulings_list.append(ln.strip())
        except Exception:
            pass

    deferred_minor_count = 0
    deferred_minor_items: list[str] = []
    if os.path.isfile(minor_md_path):
        try:
            for ln in Path(minor_md_path).read_text(encoding="utf-8", errors="replace").splitlines():
                if ln.strip().startswith("- "):
                    deferred_minor_count += 1
                    deferred_minor_items.append(ln.strip())
        except Exception:
            pass

    goal_tasks_total = 0
    goal_tasks_done = 0
    goal_tasks_ruled = 0
    if os.path.isfile(goal_json_path):
        try:
            gdata = json.loads(Path(goal_json_path).read_text(encoding="utf-8", errors="replace"))
            gtasks = gdata.get("tasks", {})
            if isinstance(gtasks, dict):
                goal_tasks_total = len(gtasks)
                for t in gtasks.values():
                    if isinstance(t, dict):
                        if t.get("status") in ("VERIFIED_COMPLETE", "COMPLETED", "COMPLETED_WITH_RULING"):
                            goal_tasks_done += 1
                        if t.get("status") == "COMPLETED_WITH_RULING" or t.get("ruling"):
                            goal_tasks_ruled += 1
        except Exception:
            pass

    return {
        "goal_loop_exists": os.path.isfile(goal_json_path),
        "goal_tasks_total": goal_tasks_total,
        "goal_tasks_done": goal_tasks_done,
        "goal_tasks_ruled": goal_tasks_ruled,
        "ledger_exists": os.path.isfile(ledger_md_path),
        "ledger_entries": ledger_entries,
        "rulings_count": rulings_count,
        "rulings": rulings_list[-10:],
        "deferred_minor_ledger_exists": os.path.isfile(minor_md_path),
        "deferred_minor_count": deferred_minor_count,
        "deferred_minor_items": deferred_minor_items[-10:],
    }


EPOCH_FUNNEL_FOCUS = {
    1: "Epoch 1 (Foundation, Core Architecture & End-to-End Entrypoint Wiring): Build core system, modular boundaries, real AST entrypoint wiring, and baseline test suite.",
    2: "Epoch 2 (SOTA Feature Injection & Architectural Elevation): Inject highest-ROI SOTA visualizations/features from Web Scout and fix Epoch 1 Rigor/Safety defects.",
    3: "Epoch 3 (Hardening, Deferred-Minor Polish & Zero-Defect Outcome Convergence): Freeze core architecture. Sweep `.swarm/deferred_minor_ledger.md`, verify `.swarm/ledger.md` rulings, and focus strictly on algorithmic rigor, performance optimization, edge-case coverage, visual polish, and security closure.",
}


def get_epoch_focus(epoch_num: int) -> str:
    if epoch_num in EPOCH_FUNNEL_FOCUS:
        return EPOCH_FUNNEL_FOCUS[epoch_num]
    return (
        f"Epoch {epoch_num} (Goal-Loop Outcome & Authenticity Remediation): "
        "Eliminate all remaining synthetic/placeholder/unwired implementations, resolve Critical/Important "
        "defects, and iterate until end-to-end output ACTUALLY matches the desired product outcome."
    )


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def log(msg: str) -> None:
    entry = f"[{now_iso()}] {msg}"
    print(entry)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


def default_epoch_record(epoch_num: int) -> dict[str, Any]:
    return {
        "epoch": epoch_num,
        "focus": get_epoch_focus(epoch_num),
        "started_at": now_iso(),
        "intermittent_report": None,
        "audits": {
            "rigor": None,
            "safety": None,
            "innovation": None,
        },
        "sota_evaluation": None,
        "adjusted_plan": None,
        "convergence": None,
    }


def load_state() -> dict[str, Any]:
    tasks_file = resolve_tasks_file(create_local_dir=False)
    if not os.path.exists(tasks_file):
        return {
            "current_epoch": 1,
            "max_epochs": MAX_MACRO_EPOCHS,
            "project_goal": "",
            "tasks": {},
            "subagents": {},
            "epochs": {"1": default_epoch_record(1)},
            "sota_history": [],
            "overall_evaluation": None,
        }
    try:
        with open(tasks_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "tasks" not in data and "subagents" not in data:
                return {
                    "current_epoch": 1,
                    "max_epochs": MAX_MACRO_EPOCHS,
                    "project_goal": "",
                    "tasks": data,
                    "subagents": {},
                    "epochs": {"1": default_epoch_record(1)},
                    "sota_history": [],
                    "overall_evaluation": None,
                }
            data.setdefault("current_epoch", 1)
            data.setdefault("max_epochs", MAX_MACRO_EPOCHS)
            data.setdefault("project_goal", "")
            data.setdefault("tasks", {})
            data.setdefault("subagents", {})
            data.setdefault("epochs", {"1": default_epoch_record(1)})
            data.setdefault("sota_history", [])
            data.setdefault("overall_evaluation", None)
            return data
    except Exception:
        return {
            "current_epoch": 1,
            "max_epochs": MAX_MACRO_EPOCHS,
            "project_goal": "",
            "tasks": {},
            "subagents": {},
            "epochs": {"1": default_epoch_record(1)},
            "sota_history": [],
            "overall_evaluation": None,
        }


def save_state(state: dict[str, Any], create_local_dir: bool = False) -> None:
    tasks_file = resolve_tasks_file(create_local_dir=create_local_dir)
    os.makedirs(os.path.dirname(os.path.abspath(tasks_file)), exist_ok=True)
    with open(tasks_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    # Mirror to global tasks file so background daemon / status checks outside repo still see latest state
    if os.path.abspath(tasks_file) != os.path.abspath(GLOBAL_TASKS_FILE):
        try:
            with open(GLOBAL_TASKS_FILE, "w", encoding="utf-8") as gf:
                json.dump(state, gf, indent=2)
        except Exception:
            pass


def ensure_epoch(state: dict[str, Any], epoch_num: int | None = None) -> dict[str, Any]:
    ep = epoch_num or state.get("current_epoch", 1)
    ep_key = str(ep)
    if ep_key not in state["epochs"]:
        state["epochs"][ep_key] = default_epoch_record(ep)
    return state["epochs"][ep_key]


def init_swarm(project_goal: str = "") -> None:
    state = {
        "initialized_at": now_iso(),
        "current_epoch": 1,
        "max_epochs": MAX_MACRO_EPOCHS,
        "project_goal": project_goal,
        "tasks": {},
        "subagents": {},
        "epochs": {"1": default_epoch_record(1)},
        "sota_history": [],
        "overall_evaluation": None,
    }
    save_state(state, create_local_dir=True)
    log(f"Initialized new evolutionary swarm ledger (Epoch 1/{MAX_MACRO_EPOCHS}). Goal: {project_goal or 'N/A'}")


def start_epoch(epoch_num: int) -> dict[str, Any]:
    if epoch_num < 1 or epoch_num > HARD_MAX_REMEDIATION_EPOCHS:
        print(f"Error: Epoch must be between 1 and {HARD_MAX_REMEDIATION_EPOCHS}.")
        sys.exit(1)
    state = load_state()
    state["current_epoch"] = epoch_num
    if epoch_num > state.get("max_epochs", MAX_MACRO_EPOCHS):
        state["max_epochs"] = epoch_num
    ep_rec = ensure_epoch(state, epoch_num)
    ep_rec["started_at"] = now_iso()
    save_state(state)
    log(f"🚀 STARTED MACRO-LOOP EPOCH {epoch_num}/{state['max_epochs']}: {ep_rec['focus']}")
    print(json.dumps(ep_rec, indent=2))
    return ep_rec


def check_internet() -> bool:
    try:
        req = urllib.request.Request(PROBE_URL, headers={"User-Agent": "ImmortalWatcher/3.0"})
        with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT) as response:
            return response.status == 200
    except Exception:
        try:
            with urllib.request.urlopen("https://1.1.1.1", timeout=PROBE_TIMEOUT) as r:
                return r.status in (200, 301, 302)
        except Exception:
            return False


def is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def validate_task_done(validation_cmd: str, cwd: str | None = None) -> bool:
    if not validation_cmd:
        return True
    try:
        res = subprocess.run(
            validation_cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def spawn_task_process(task_name: str, cmd: str, cwd: str | None = None) -> int:
    task_log = os.path.join(PLUGIN_DIR, "scripts", f"task_{task_name}.log")
    with open(task_log, "a", encoding="utf-8") as out:
        out.write(f"\n--- [SPAWN {now_iso()}] {cmd} ---\n")
        proc = subprocess.Popen(
            cmd,
            shell=True,
            cwd=cwd,
            stdout=out,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )
    return proc.pid


def register_task(name: str, command: str, validation_cmd: str, cwd: str | None = None) -> None:
    state = load_state()
    tasks = state["tasks"]
    pid = spawn_task_process(name, command, cwd=cwd)
    tasks[name] = {
        "command": command,
        "validation_cmd": validation_cmd,
        "cwd": cwd or os.getcwd(),
        "pid": pid,
        "status": "RUNNING",
        "attempts": 1,
        "created_at": now_iso(),
        "last_revived": now_iso(),
    }
    save_state(state)
    log(f"Registered persistent OS task '{name}' (PID: {pid}). Validation: {validation_cmd}")


def get_transcript_path(conv_id: str) -> str:
    return os.path.join(BRAIN_DIR, conv_id, ".system_generated", "logs", "transcript.jsonl")


def register_subagent(
    conv_id: str,
    role: str,
    branch: str = "",
    worktree: str = "",
    implementation_goal: str = "",
    agent_kind: str = "worker",
) -> None:
    state = load_state()
    subagents = state["subagents"]
    epoch = state.get("current_epoch", 1)
    subagents[conv_id] = {
        "conversation_id": conv_id,
        "role": role,
        "agent_kind": agent_kind,
        "epoch": epoch,
        "branch": branch,
        "worktree": worktree,
        "implementation_goal": implementation_goal,
        "transcript_path": get_transcript_path(conv_id),
        "status": "RUNNING",
        "revive_attempts": 0,
        "max_revive_attempts": MAX_REVIVE_ATTEMPTS,
        "loop_count": 0,
        "max_loops": MAX_DISCRIMINATOR_LOOPS,
        "impl_score": None,
        "goal_score": None,
        "effective_score": None,
        "review_history": [],
        "registered_at": now_iso(),
        "last_checked": now_iso(),
        "last_revived": None,
    }
    save_state(state)
    log(f"Registered {agent_kind} subagent '{role}' (ID: {conv_id}, Epoch: {epoch}, branch: {branch or 'N/A'}).")


def inspect_subagent_transcript(conv_id: str, stall_seconds: int = DEFAULT_STALL_SECONDS) -> dict[str, Any]:
    """Inspect a subagent's transcript.jsonl for errors, stream interruptions, or stalls."""
    t_path = get_transcript_path(conv_id)
    if not os.path.exists(t_path):
        return {
            "exists": False,
            "stalled": False,
            "interrupted": False,
            "reason": "Transcript not created yet",
            "idle_seconds": 0.0,
        }

    try:
        mtime = os.path.getmtime(t_path)
        idle_secs = max(0.0, time.time() - mtime)
        last_step: dict[str, Any] = {}
        with open(t_path, "r", encoding="utf-8", errors="replace") as f:
            lines = [line.strip() for line in f if line.strip()]
            if lines:
                last_step = json.loads(lines[-1])

        step_status = str(last_step.get("status", "")).upper()
        step_content = str(last_step.get("content", ""))
        interrupted = (
            step_status == "ERROR"
            or "stream was interrupted" in step_content.lower()
            or ("network" in step_content.lower() and step_status == "ERROR")
        )
        finished_reported = any(
            marker in step_content.lower()
            for marker in ("task finished", "audit finished", "sota report finished")
        )
        stalled = (not finished_reported) and (idle_secs >= stall_seconds)

        reason = "OK"
        if interrupted:
            reason = f"Last transcript step ended in ERROR / stream interruption (status={step_status})"
        elif stalled:
            reason = f"No transcript activity for {int(idle_secs)}s (threshold={stall_seconds}s)"

        return {
            "exists": True,
            "stalled": stalled,
            "interrupted": interrupted,
            "finished_reported": finished_reported,
            "last_step_status": step_status,
            "idle_seconds": round(idle_secs, 1),
            "reason": reason,
        }
    except Exception as exc:
        return {
            "exists": True,
            "stalled": False,
            "interrupted": False,
            "reason": f"Failed to inspect transcript: {exc}",
            "idle_seconds": 0.0,
        }


def check_subagents(stall_seconds: int = DEFAULT_STALL_SECONDS, as_json: bool = False) -> list[dict[str, Any]]:
    state = load_state()
    subagents = state.get("subagents", {})
    needs_revival: list[dict[str, Any]] = []
    modified = False

    for conv_id, info in subagents.items():
        current_status = info.get("status", "RUNNING")
        if current_status in (
            "APPROVED",
            "APPROVED_WITH_RULING",
            "COMPLETED_WITH_RULING",
            "MERGED",
            "ESCALATED",
            "BREAKER_ADJUDICATION_REQUIRED",
            "FAILED",
            "COMPLETED",
        ):
            continue

        agent_kind = info.get("agent_kind", "worker")
        diag = inspect_subagent_transcript(conv_id, stall_seconds=stall_seconds)
        info["last_checked"] = now_iso()
        modified = True

        # Event-driven gate agents (discriminator, watcher) legitimately sit idle waiting
        # for workers to finish; only flag them if their last step crashed with ERROR/interruption.
        is_idle_gate = agent_kind in ("discriminator", "watcher") and not diag.get("interrupted")
        if is_idle_gate:
            continue

        if diag.get("interrupted") or diag.get("stalled"):
            revives = info.get("revive_attempts", 0)
            if revives >= MAX_REVIVE_ATTEMPTS:
                info["status"] = "FAILED"
                log(f"❌ SUBAGENT EXHAUSTED: '{info.get('role')}' ({conv_id}) reached max revives ({revives}).")
            else:
                info["status"] = "INTERRUPTED" if diag.get("interrupted") else "STALLED"
                alert = {
                    "conversation_id": conv_id,
                    "role": info.get("role"),
                    "agent_kind": agent_kind,
                    "epoch": info.get("epoch", 1),
                    "branch": info.get("branch"),
                    "status": info["status"],
                    "reason": diag.get("reason"),
                    "idle_seconds": diag.get("idle_seconds"),
                    "revive_attempts": revives,
                    "max_revive_attempts": MAX_REVIVE_ATTEMPTS,
                    "recommended_action": (
                        f"Call send_message(Recipient='{conv_id}', Message='IMMORTAL WATCHER REVIVAL: "
                        f"Your session stalled or was interrupted ({diag.get('reason')}). "
                        f"Check your current worktree/task state and continue executing your assignment "
                        f"until completion.')"
                    ),
                }
                needs_revival.append(alert)
                log(f"⚠️ SUBAGENT {info['status']}: '{info.get('role')}' ({conv_id}) - {diag.get('reason')}")

    if modified:
        save_state(state)

    if as_json:
        print(json.dumps({"needs_revival": needs_revival, "subagents": subagents}, indent=2))
    else:
        if not needs_revival:
            print("All active subagents are healthy (no stalls or interruptions detected).")
        else:
            print(f"⚠️ Detected {len(needs_revival)} subagent(s) requiring revival:")
            for item in needs_revival:
                print(f"  - [{item['status']}] {item['role']} ({item['conversation_id']}): {item['reason']}")
                print(f"    Action: {item['recommended_action']}")

    return needs_revival


def mark_revived(conv_id: str) -> None:
    state = load_state()
    subagents = state.get("subagents", {})
    if conv_id not in subagents:
        print(f"Error: Subagent {conv_id} is not registered.")
        sys.exit(1)

    info = subagents[conv_id]
    info["revive_attempts"] = info.get("revive_attempts", 0) + 1
    info["last_revived"] = now_iso()
    info["status"] = "RUNNING"
    save_state(state)
    log(
        f"🔄 SUBAGENT REVIVED: '{info.get('role')}' ({conv_id}) "
        f"(Attempt {info['revive_attempts']}/{MAX_REVIVE_ATTEMPTS})"
    )


PROTECTED_CONFIG_BASENAMES = {
    ".eslintrc",
    ".eslintrc.js",
    ".eslintrc.json",
    ".eslintrc.cjs",
    "eslint.config.js",
    "eslint.config.mjs",
    "biome.json",
    ".flake8",
    ".pylintrc",
    "mypy.ini",
    "pytest.ini",
}


def audit_worktree_diff(worktree: str, branch: str = "", allow_config_edits: bool = False) -> dict[str, Any]:
    """Perform objective static hygiene, silent-failure, config-tampering, and authenticity/wiring checks on worker diff."""
    result: dict[str, Any] = {
        "checked": False,
        "todo_count": 0,
        "any_cast_count": 0,
        "silent_failure_count": 0,
        "synthetic_count": 0,
        "half_baked_count": 0,
        "unwired_modules": [],
        "config_tampering_files": [],
        "prod_lines_added": 0,
        "test_files_touched": 0,
        "reasons": [],
    }
    if not worktree or not os.path.isdir(worktree):
        return result

    diff_target = f"main...{branch}" if branch else "HEAD~1"
    try:
        proc = subprocess.run(
            ["git", "diff", "--unified=0", diff_target],
            cwd=worktree,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            proc = subprocess.run(
                ["git", "diff", "--unified=0", "HEAD"],
                cwd=worktree,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        if proc.returncode != 0 or not proc.stdout.strip():
            return result
    except Exception:
        return result

    result["checked"] = True
    current_file = ""
    is_test_file = False
    prev_was_except = False
    test_files: set[str] = set()
    prod_files_touched: set[str] = set()
    tampered_files: set[str] = set()

    for line in proc.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            lower_f = current_file.lower()
            base_f = os.path.basename(lower_f)
            is_test_file = any(tok in lower_f for tok in ("test", "spec", "__tests__", "bench"))
            prev_was_except = False
            if is_test_file:
                test_files.add(current_file)
            elif current_file.endswith((".ts", ".tsx", ".js", ".jsx", ".py", ".rs", ".go", ".c", ".cpp", ".cs")):
                prod_files_touched.add(current_file)
            if not allow_config_edits:
                if (
                    base_f in PROTECTED_CONFIG_BASENAMES
                    or lower_f.startswith((".git/hooks/", ".gemini/", ".claude/", "src/contracts/"))
                    or "/src/contracts/" in f"/{lower_f}"
                ):
                    tampered_files.add(current_file)
            continue
        if not line.startswith("+") or line.startswith("+++"):
            prev_was_except = False
            continue

        added_code = line[1:]
        stripped = added_code.strip()

        # Check config weakening in pyproject.toml or tsconfig.json
        if not allow_config_edits and os.path.basename(current_file.lower()) in {"pyproject.toml", "tsconfig.json"}:
            if any(
                weak in stripped
                for weak in (
                    '"strict": false',
                    '"noImplicitAny": false',
                    "ignore_errors = true",
                    "disable_error_code",
                    'select = []',
                )
            ):
                tampered_files.add(current_file)

        if not is_test_file:
            if current_file.endswith((".ts", ".tsx", ".js", ".jsx", ".py", ".rs", ".go", ".c", ".cpp", ".cs")):
                result["prod_lines_added"] += 1
                for marker in ("TODO:", "FIXME:", "HACK:", "XXX:", "PLACEHOLDER:", "TBD:"):
                    if marker in added_code:
                        result["todo_count"] += 1
                if current_file.endswith((".ts", ".tsx")) and (" as any" in added_code or ": any" in added_code):
                    result["any_cast_count"] += 1
                elif current_file.endswith(".py") and stripped.startswith("except:"):
                    result["any_cast_count"] += 1

                # Silent Failure Hunter checks
                if current_file.endswith(".py"):
                    if (
                        stripped in {"except: pass", "except Exception: pass", "except BaseException: pass"}
                        or stripped.startswith("except Exception: return ")
                        or stripped.startswith("except: return ")
                    ):
                        result["silent_failure_count"] += 1
                        prev_was_except = False
                    elif prev_was_except and stripped in {"pass", "return None", "return []", "return {}", "return False"}:
                        result["silent_failure_count"] += 1
                        prev_was_except = False
                    else:
                        prev_was_except = stripped in {"except:", "except Exception:", "except BaseException:"} or (
                            stripped.startswith("except Exception as ") and stripped.endswith(":")
                        )
                elif current_file.endswith((".ts", ".tsx", ".js", ".jsx")):
                    if (
                        ".catch(() => {})" in stripped
                        or ".catch(() => [])" in stripped
                        or ".catch(() => null)" in stripped
                        or "catch {}" in stripped
                        or "catch (e) {}" in stripped
                        or "catch (_)" in stripped and "{}" in stripped
                    ):
                        result["silent_failure_count"] += 1

    # Run deep AST/authenticity & cross-file wiring check via goal_loop on touched production files
    if prod_files_touched:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import goal_loop
            auth = goal_loop.audit_authenticity(
                root_dir=worktree,
                target_files=sorted(prod_files_touched),
                check_orphan_modules=True,
            )
            non_todo_placeholders = [
                f for f in auth.get("placeholder_findings", []) if f.get("kind") != "TODO_OR_PLACEHOLDER_COMMENT"
            ]
            result["half_baked_count"] = len(non_todo_placeholders)
            result["synthetic_count"] = len(auth.get("synthetic_findings", []))
            result["unwired_modules"] = [f.get("file", "") for f in auth.get("unwired_findings", [])]
        except Exception:
            pass

    result["test_files_touched"] = len(test_files)
    result["config_tampering_files"] = sorted(tampered_files)
    # Reasons are labelled with the tier `record_review` applies: BLOCKING_FAIL hard-caps at 6.0, ADVISORY_WARN never blocks.
    if result["todo_count"] > 0:
        result["reasons"].append(f"[BLOCKING_FAIL] Found {result['todo_count']} TODO/FIXME/HACK/PLACEHOLDER stub(s) in production diff")
    if result["half_baked_count"] > 0:
        result["reasons"].append(
            f"[BLOCKING_FAIL] Anti-Half-Baked Gate: Found {result['half_baked_count']} unimplemented stub function(s) or half-baked placeholder comment(s)"
        )
    if result["synthetic_count"] > 0:
        result["reasons"].append(
            f"[BLOCKING_FAIL] Anti-Synthetic Gate: Found {result['synthetic_count']} mock framework import(s) or hardcoded synthetic/dummy return(s) in production code"
        )
    if result["unwired_modules"]:
        result["reasons"].append(
            f"[BLOCKING_FAIL] Outcome Participation Gate: Unwired conceptual module(s) {result['unwired_modules']} are never imported or invoked by any production entrypoint/pipeline"
        )
    if result["any_cast_count"] > 0:
        result["reasons"].append(
            f"[ADVISORY_WARN] Found {result['any_cast_count']} unguarded 'any' / bare 'except:' escape(s) in production diff"
        )
    if result["silent_failure_count"] > 0:
        result["reasons"].append(
            f"[ADVISORY_WARN] Silent-Failure Hunter: Found {result['silent_failure_count']} swallowed exception/fallback pattern(s) in diff"
        )
    if result["config_tampering_files"]:
        result["reasons"].append(
            f"[BLOCKING_FAIL] Config/Contract Protection: Worker modified protected config or locked contract file(s) {result['config_tampering_files']}"
        )
    if result["prod_lines_added"] >= 15 and result["test_files_touched"] == 0:
        result["reasons"].append(
            f"[INFO] Modified {result['prod_lines_added']} production lines with 0 test files updated"
        )
    return result


def write_lesson_to_markdown(epoch: int, category: str, lesson: str, lessons_file: str = ".swarm/lessons_learned.md") -> None:
    try:
        os.makedirs(os.path.dirname(os.path.abspath(lessons_file)), exist_ok=True)
        header_needed = not os.path.exists(lessons_file)
        with open(lessons_file, "a", encoding="utf-8") as f:
            if header_needed:
                f.write("# Cross-Epoch Negative Memory & Anti-Regression Ledger\n\n")
                f.write("All sub-agents must read and respect these invariants across epochs:\n\n")
            f.write(f"- **[Epoch {epoch} | {category}]** ({now_iso()[:19]}Z): {lesson}\n")
    except Exception:
        pass


def _record_instinct_safe(rule: str, category: str, confidence: float = 0.75, cwd: str | None = None) -> None:
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import instinct_manager
        instinct_manager.record_instinct(
            rule=rule,
            category=category,
            initial_confidence=confidence,
            cwd=cwd,
        )
    except Exception:
        pass


def create_git_snapshot(label: str, cwd: str | None = None) -> dict[str, Any]:
    """Record current HEAD SHA so a failed merge or verification step can roll back cleanly."""
    target_dir = os.path.abspath(cwd or os.getcwd())
    res = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=target_dir,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if res.returncode != 0:
        print(f"Error: Unable to read git HEAD in {target_dir}")
        sys.exit(1)
    sha = res.stdout.strip()
    state = load_state()
    snap = {
        "label": label,
        "sha": sha,
        "cwd": target_dir,
        "timestamp": now_iso(),
    }
    state.setdefault("snapshots", {})[label] = snap
    save_state(state)
    log(f"📸 GIT SNAPSHOT CREATED [{label}]: {sha[:12]} in {target_dir}")
    print(json.dumps(snap, indent=2))
    return snap


def restore_git_snapshot(label: str, cwd: str | None = None) -> dict[str, Any]:
    """Restore repository worktree to a previously saved snapshot SHA."""
    state = load_state()
    snaps = state.get("snapshots", {})
    if label not in snaps:
        print(f"Error: Snapshot '{label}' not found.")
        sys.exit(1)
    snap = snaps[label]
    target_dir = os.path.abspath(cwd or snap.get("cwd") or os.getcwd())
    sha = snap["sha"]
    res = subprocess.run(
        ["git", "reset", "--hard", sha],
        cwd=target_dir,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    ok = res.returncode == 0
    out = {
        "label": label,
        "restored_sha": sha,
        "cwd": target_dir,
        "status": "RESTORED" if ok else "ERROR",
        "timestamp": now_iso(),
    }
    log(f"⏪ GIT SNAPSHOT RESTORED [{label}] -> {sha[:12]} ({out['status']})")
    print(json.dumps(out, indent=2))
    return out


def record_review(
    conv_id: str,
    impl_score: float,
    goal_score: float,
    notes: str = "",
    critical_flaws: int = 0,
    major_flaws: int = 0,
    minor_flaws: int = 0,
    spec_verdict: str = "PASS",
    ruling: str = "",
    adversarial_cmd: str = "",
    outcome_cmd: str = "",
    expect_output: str = "",
    worktree_override: str = "",
    branch_override: str = "",
    uncalibrated: bool = False,
    pass_hat_k: int = 1,
    allow_config_edits: bool = False,
) -> dict[str, Any]:
    state = load_state()
    subagents = state.get("subagents", {})
    if conv_id not in subagents:
        subagents[conv_id] = {
            "conversation_id": conv_id,
            "role": "Worker",
            "agent_kind": "worker",
            "epoch": state.get("current_epoch", 1),
            "branch": branch_override,
            "worktree": worktree_override,
            "status": "RUNNING",
            "revive_attempts": 0,
            "max_revive_attempts": MAX_REVIVE_ATTEMPTS,
            "loop_count": 0,
            "max_loops": MAX_DISCRIMINATOR_LOOPS,
            "review_history": [],
            "registered_at": now_iso(),
        }

    info = subagents[conv_id]
    if worktree_override:
        info["worktree"] = worktree_override
    if branch_override:
        info["branch"] = branch_override

    loop_count = info.get("loop_count", 0) + 1
    raw_impl_score = float(impl_score)
    raw_goal_score = float(goal_score)
    norm_spec_verdict = (spec_verdict or "PASS").upper().strip()
    calibration_reasons: list[str] = []
    blocking_fails: list[str] = []
    advisory_warns: list[str] = []

    worktree_dir = info.get("worktree") or ""
    branch_name = info.get("branch") or ""
    probe_cwd = worktree_dir if (worktree_dir and os.path.isdir(worktree_dir)) else os.getcwd()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import goal_loop

    # 1. Execute independent adversarial probe (with optional pass^k consecutive runs) if supplied
    adversarial_passed = False
    k_runs = max(1, int(pass_hat_k))
    passed_k_runs = 0
    if adversarial_cmd:
        fail_tail = ""
        try:
            for trial in range(k_runs):
                probe_res = subprocess.run(
                    adversarial_cmd,
                    shell=True,
                    cwd=probe_cwd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                if probe_res.returncode == 0:
                    passed_k_runs += 1
                else:
                    snippet = (probe_res.stderr or probe_res.stdout or "").strip().splitlines()[-1:]
                    fail_tail = snippet[0][:160] if snippet else f"exit code {probe_res.returncode}"
            if passed_k_runs == k_runs:
                adversarial_passed = True
                k_label = f" (pass^{k_runs}: {passed_k_runs}/{k_runs} trials)" if k_runs > 1 else ""
                calibration_reasons.append(f"Independent adversarial probe passed{k_label}: `{adversarial_cmd}`")
            else:
                msg = f"Independent adversarial probe FAILED pass^{k_runs} gate ({passed_k_runs}/{k_runs} passed: `{adversarial_cmd}` -> {fail_tail})"
                blocking_fails.append(msg)
                calibration_reasons.append(f"[BLOCKING_FAIL] {msg}")
        except Exception as exc:
            msg = f"Independent adversarial probe errored ({exc})"
            blocking_fails.append(msg)
            calibration_reasons.append(f"[BLOCKING_FAIL] {msg}")

    # 1b. Execute End-to-End Outcome Command if supplied (--outcome-cmd)
    outcome_verified = True
    if outcome_cmd:
        try:
            out_gate = goal_loop.run_command_gate(
                outcome_cmd,
                cwd=probe_cwd,
                expect_output=expect_output,
                pass_hat_k=1,
            )
            if out_gate["passed"]:
                calibration_reasons.append(f"End-to-end outcome verification passed: `{outcome_cmd}`")
            else:
                outcome_verified = False
                msg = f"End-to-end outcome verification FAILED (`{outcome_cmd}`): {'; '.join(out_gate['errors'][:2])}"
                blocking_fails.append(msg)
                calibration_reasons.append(f"[BLOCKING_FAIL] {msg}")
        except Exception as exc:
            outcome_verified = False
            msg = f"End-to-end outcome verification errored ({exc})"
            blocking_fails.append(msg)
            calibration_reasons.append(f"[BLOCKING_FAIL] {msg}")

    # 2. Run objective git-diff hygiene, silent-failure, authenticity/wiring, and config-tampering check
    diff_audit = (
        audit_worktree_diff(worktree_dir, branch_name, allow_config_edits=allow_config_edits)
        if (worktree_dir or branch_name)
        else {
            "checked": False,
            "reasons": [],
        }
    )
    if diff_audit.get("todo_count", 0) > 0:
        blocking_fails.append(f"Found {diff_audit['todo_count']} TODO/FIXME/PLACEHOLDER stub(s) in production diff")
    if diff_audit.get("half_baked_count", 0) > 0:
        blocking_fails.append(f"Found {diff_audit['half_baked_count']} unimplemented stub function(s) or half-baked placeholder(s)")
    if diff_audit.get("synthetic_count", 0) > 0:
        blocking_fails.append(f"Found {diff_audit['synthetic_count']} mock framework import(s) or synthetic return(s) in production")
    if diff_audit.get("unwired_modules"):
        blocking_fails.append(f"Unwired production module(s): {diff_audit['unwired_modules']}")
    if diff_audit.get("config_tampering_files"):
        blocking_fails.append(f"Unauthorized config/contract tampering: {diff_audit['config_tampering_files']}")
    if diff_audit.get("silent_failure_count", 0) > 0:
        advisory_warns.append(f"Broad/swallowed exception handler(s) ({diff_audit['silent_failure_count']}) — Defend in 1 sentence or fix")
    if diff_audit.get("any_cast_count", 0) > 0:
        advisory_warns.append(f"Type escape `: any` / `as any` ({diff_audit['any_cast_count']}) — Defend in 1 sentence or fix")
    calibration_reasons.extend(diff_audit.get("reasons", []))

    # 3. Apply Hard-Cap Scoring Rule (replacing arbitrary point-deduction math)
    #    - Any BLOCKING_FAIL, spec_verdict != PASS, or critical_flaws > 0 -> Hard-capped at 6.0
    #    - Any major_flaws (Important) > 0 -> Hard-capped at 7.0
    #    - Minor flaws NEVER block or deduct; deferred to .swarm/deferred_minor_ledger.md
    hard_cap: float | None = None
    if len(blocking_fails) > 0 or norm_spec_verdict != "PASS" or critical_flaws > 0 or not outcome_verified:
        hard_cap = HARD_CAP_BLOCKING
        calibration_reasons.append(
            f"Hard Cap {HARD_CAP_BLOCKING}/10 applied (blocking_fails={len(blocking_fails)}, "
            f"spec_verdict={norm_spec_verdict}, critical_flaws={critical_flaws})"
        )
    elif major_flaws > 0:
        hard_cap = HARD_CAP_IMPORTANT
        calibration_reasons.append(f"Hard Cap {HARD_CAP_IMPORTANT}/10 applied (important/major_flaws={major_flaws})")

    if minor_flaws > 0:
        goal_loop.append_deferred_minor(
            task_id=branch_name or conv_id,
            count=minor_flaws,
            notes=notes,
            cwd=probe_cwd,
        )
        calibration_reasons.append(
            f"Deferred {minor_flaws} Minor finding(s) to `.swarm/deferred_minor_ledger.md` (non-blocking)"
        )

    if not uncalibrated:
        if hard_cap is not None:
            impl_score = round(min(raw_impl_score, hard_cap), 1)
            goal_score = round(min(raw_goal_score, hard_cap), 1)
        else:
            default_clean = 9.2 if len(advisory_warns) == 0 else 8.5
            ceiling = ADVERSARIAL_LOOP1_CEILING if (adversarial_passed and loop_count == 1) else (
                ADVERSARIAL_REFINED_CEILING if adversarial_passed else default_clean
            )
            impl_score = round(max(8.5, min(raw_impl_score, ceiling)), 1)
            goal_score = round(max(8.5, min(raw_goal_score, ceiling)), 1)
    else:
        impl_score = round(raw_impl_score, 1)
        goal_score = round(raw_goal_score, 1)

    effective_score = min(impl_score, goal_score)
    ruling_clean = ruling.strip()
    # The gate is categorical and shared with `goal_loop.py --record-task`; the scores above are telemetry only.
    gate = goal_loop.compute_hard_cap_score(
        blocking_fails=blocking_fails,
        advisory_warns=advisory_warns,
        spec_verdict=norm_spec_verdict,
        critical_count=critical_flaws,
        important_count=major_flaws,
        minor_count=minor_flaws,
    )
    passed = gate["passed_gate"] and outcome_verified
    if ruling_clean and blocking_fails:
        calibration_reasons.append("[BLOCKING_FAIL] Ruling ignored: a ruling cannot override deterministic BLOCKING_FAILs")

    # 4. 5-Round Escalating Fix Loop & Round 5 Breaker Ruling
    fix_loop_action = "Task approved."
    if ruling_clean and not blocking_fails:
        formatted_ruling = ruling_clean if ruling_clean.startswith("Ruling:") else f"Ruling: {ruling_clean}"
        verdict = "COMPLETED_WITH_RULING"
        info["status"] = "APPROVED_WITH_RULING"
        info["ruling"] = ruling_clean
        passed = True
        fix_loop_action = f"Round 5 Breaker Adjudicated — recorded `{formatted_ruling}` in `.swarm/ledger.md`."
        goal_loop.append_ledger_entry(
            f"Subagent `{info.get('role')}` ({conv_id}, branch `{branch_name or 'N/A'}`): "
            f"COMPLETED_WITH_RULING at Round {loop_count}/{MAX_DISCRIMINATOR_LOOPS} — {formatted_ruling}",
            cwd=probe_cwd,
        )
    elif passed:
        verdict = "PASS"
        info["status"] = "APPROVED"
        goal_loop.append_ledger_entry(
            f"Subagent `{info.get('role')}` ({conv_id}, branch `{branch_name or 'N/A'}`): "
            f"PASS at Round {loop_count}/{MAX_DISCRIMINATOR_LOOPS} (score={effective_score}/10, "
            f"minor_deferred={minor_flaws})",
            cwd=probe_cwd,
        )
    elif loop_count >= BREAKER_RULING_ROUND:
        verdict = "ROUND_5_BREAKER_TRIPPED"
        info["status"] = "BREAKER_ADJUDICATION_REQUIRED"
        fix_loop_action = (
            "Round 5 Breaker tripped: STOP looping. Orchestrator must adjudicate remaining findings and record "
            "`Ruling: <what you decided> — <why> — <what it costs if wrong>` via "
            "`goal_loop.py --record-task <ID> --ruling \"...\"` or `immortal_watcher.py --record-review <ID> --ruling \"...\"`."
        )
        goal_loop.append_ledger_entry(
            f"Subagent `{info.get('role')}` ({conv_id}): Round 5/5 Breaker tripped — awaiting Orchestrator `Ruling:`.",
            cwd=probe_cwd,
        )
    elif loop_count >= ESCALATION_FRESH_WORKER_ROUND:
        verdict = "ESCALATE_FRESH_WORKER"
        info["status"] = "ESCALATED_FRESH_WORKER"
        fix_loop_action = (
            f"Round {loop_count}/{MAX_DISCRIMINATOR_LOOPS} Escalation: Spawn a FRESH worker subagent on a higher-tier model "
            "with framing: 'A prior implementer attempted this task 3 times; these findings remain open. You own it now.'"
        )
        goal_loop.append_ledger_entry(
            f"Subagent `{info.get('role')}` ({conv_id}): fix round {loop_count}/5 -> ESCALATE_FRESH_WORKER "
            f"(critical={critical_flaws}, important={major_flaws}, blocking={len(blocking_fails)})",
            cwd=probe_cwd,
        )
    else:
        verdict = "REFINE"
        info["status"] = "REFINING"
        fix_loop_action = (
            f"Round {loop_count}/{MAX_DISCRIMINATOR_LOOPS}: Resume the SAME worker subagent with only open "
            "Critical/Important findings. Scoped re-review must check ONLY `FIX_BASE..HEAD`."
        )
        goal_loop.append_ledger_entry(
            f"Subagent `{info.get('role')}` ({conv_id}): fix round {loop_count}/5 -> REFINE same worker "
            f"(critical={critical_flaws}, important={major_flaws}, blocking={len(blocking_fails)})",
            cwd=probe_cwd,
        )

    info["loop_count"] = loop_count
    info["impl_score"] = impl_score
    info["goal_score"] = goal_score
    info["effective_score"] = effective_score
    info["hard_cap"] = hard_cap
    info["spec_verdict"] = norm_spec_verdict
    info["last_checked"] = now_iso()

    entry = {
        "epoch": info.get("epoch", state.get("current_epoch", 1)),
        "loop": loop_count,
        "max_loops": MAX_DISCRIMINATOR_LOOPS,
        "timestamp": now_iso(),
        "spec_verdict": norm_spec_verdict,
        "raw_impl_score": raw_impl_score,
        "raw_goal_score": raw_goal_score,
        "impl_score": impl_score,
        "goal_score": goal_score,
        "effective_score": effective_score,
        "hard_cap": hard_cap,
        "blocking_fails": blocking_fails,
        "advisory_warns": advisory_warns,
        "adversarial_verified": adversarial_passed,
        "outcome_verified": outcome_verified,
        "pass_hat_k": {"k": k_runs, "passed_runs": passed_k_runs} if adversarial_cmd else None,
        "flaws": {
            "critical": critical_flaws,
            "important": major_flaws,
            "major": major_flaws,
            "minor_deferred": minor_flaws,
        },
        "ruling": info.get("ruling"),
        "fix_loop_action": fix_loop_action,
        "calibration_reasons": calibration_reasons,
        "verdict": verdict,
        "notes": notes,
    }
    info.setdefault("review_history", []).append(entry)
    if not passed:
        lesson_text = notes or "; ".join(calibration_reasons) or f"Discriminator hard-capped at {hard_cap}"
        cat = f"discriminator:{info.get('role', conv_id)}"
        state.setdefault("lessons", []).append({
            "timestamp": now_iso(),
            "epoch": entry["epoch"],
            "category": cat,
            "lesson": lesson_text,
        })
        write_lesson_to_markdown(entry["epoch"], cat, lesson_text)
        instinct_cat = (
            "unwired-conceptual-code" if diff_audit.get("unwired_modules") else (
                "synthetic-or-placeholder" if (diff_audit.get("synthetic_count") or diff_audit.get("half_baked_count")) else (
                    "silent-failure" if diff_audit.get("silent_failure_count") else (
                        "config-tampering" if diff_audit.get("config_tampering_files") else cat
                    )
                )
            )
        )
        _record_instinct_safe(
            rule=lesson_text,
            category=instinct_cat,
            confidence=0.75,
            cwd=worktree_dir or os.getcwd(),
        )
    save_state(state)

    cal_note = f" (Hard Cap: {hard_cap})" if hard_cap is not None else ""
    log(
        f"🎯 DISCRIMINATOR REVIEW [{verdict}]: Subagent '{info.get('role')}' ({conv_id}) | "
        f"Epoch {entry['epoch']} | Round {loop_count}/{MAX_DISCRIMINATOR_LOOPS} | "
        f"Spec: {norm_spec_verdict} | Score: {effective_score}/10{cal_note}"
    )
    print(json.dumps(entry, indent=2))
    return entry


def add_lesson(
    lesson: str,
    category: str = "architecture",
    lessons_file: str = ".swarm/lessons_learned.md",
) -> dict[str, Any]:
    """Record a cross-epoch negative memory / anti-regression invariant and sync to Instincts Engine."""
    state = load_state()
    epoch = state.get("current_epoch", 1)
    entry = {
        "timestamp": now_iso(),
        "epoch": epoch,
        "category": category,
        "lesson": lesson,
    }
    state.setdefault("lessons", []).append(entry)
    save_state(state)
    write_lesson_to_markdown(epoch, category, lesson, lessons_file=lessons_file)
    _record_instinct_safe(rule=lesson, category=category, confidence=0.72)

    log(f"🧠 NEGATIVE MEMORY & INSTINCT RECORDED (Epoch {epoch} | {category}): {lesson}")
    print(json.dumps(entry, indent=2))
    return entry


def list_lessons(as_json: bool = False) -> list[dict[str, Any]]:
    state = load_state()
    lessons = state.get("lessons", [])
    if as_json:
        print(json.dumps(lessons, indent=2))
    else:
        if not lessons:
            print("No cross-epoch negative memory invariants recorded yet.")
        else:
            print("=== CROSS-EPOCH NEGATIVE MEMORY (LESSONS LEARNED) ===")
            for item in lessons:
                print(f"  - [Epoch {item.get('epoch', 1)} | {item.get('category', 'general')}] {item.get('lesson')}")
    return lessons



def record_intermittent_report(report_path: str, summary: str = "", epoch_num: int | None = None) -> dict[str, Any]:
    state = load_state()
    ep_rec = ensure_epoch(state, epoch_num)
    entry = {
        "timestamp": now_iso(),
        "report_path": report_path,
        "summary": summary,
    }
    ep_rec["intermittent_report"] = entry
    save_state(state)
    log(f"📋 INTERMITTENT REPORT RECORDED (Epoch {ep_rec['epoch']}): {report_path}")
    print(json.dumps(entry, indent=2))
    return entry


def record_audit(
    auditor: str,
    score: float,
    critical_count: int = 0,
    high_count: int = 0,
    enhancement_count: int = 0,
    report_path: str = "",
    notes: str = "",
    epoch_num: int | None = None,
) -> dict[str, Any]:
    auditor_key = auditor.lower().strip()
    if auditor_key not in ("rigor", "safety", "innovation"):
        print("Error: --auditor must be one of: rigor, safety, innovation")
        sys.exit(1)

    state = load_state()
    ep_rec = ensure_epoch(state, epoch_num)
    entry = {
        "auditor": auditor_key,
        "epoch": ep_rec["epoch"],
        "timestamp": now_iso(),
        "score": score,
        "critical_count": critical_count,
        "high_count": high_count,
        "enhancement_count": enhancement_count,
        "report_path": report_path,
        "notes": notes,
    }
    ep_rec["audits"][auditor_key] = entry
    save_state(state)
    log(
        f"🔍 TRIAD AUDIT [{auditor_key.upper()}] (Epoch {ep_rec['epoch']}): "
        f"Score={score}/10 | Critical={critical_count} | High={high_count} | Enhancements={enhancement_count}"
    )
    print(json.dumps(entry, indent=2))
    return entry


def record_sota(
    innovation_score: float,
    sota_impl_score: float,
    benchmark_path: str = "",
    top_gaps: str = "",
    epoch_num: int | None = None,
) -> dict[str, Any]:
    state = load_state()
    ep_rec = ensure_epoch(state, epoch_num)
    entry = {
        "epoch": ep_rec["epoch"],
        "timestamp": now_iso(),
        "innovation_vs_sota_score": innovation_score,
        "implementation_vs_sota_score": sota_impl_score,
        "benchmark_path": benchmark_path,
        "top_gaps": top_gaps,
    }
    ep_rec["sota_evaluation"] = entry
    state.setdefault("sota_history", []).append(entry)
    save_state(state)
    log(
        f"🌐 SOTA WEB SCOUT REPORT (Epoch {ep_rec['epoch']}): "
        f"Innovation vs SOTA={innovation_score}/10 | Implementation vs SOTA={sota_impl_score}/10"
    )
    print(json.dumps(entry, indent=2))
    return entry


def check_convergence(
    plan_path: str = "",
    epoch_num: int | None = None,
    outcome_cmd: str = "",
    expect_output: str = "",
    allow_stop_unconverged: bool = False,
) -> dict[str, Any]:
    """Evaluate Step 7 Macro-Loop Convergence or Next-Epoch Transition UNTIL desired outcome is met."""
    state = load_state()
    ep_rec = ensure_epoch(state, epoch_num)
    current_ep = ep_rec["epoch"]
    audits = ep_rec.get("audits", {})
    sota = ep_rec.get("sota_evaluation") or {}

    rigor = audits.get("rigor") or {}
    safety = audits.get("safety") or {}
    innovation = audits.get("innovation") or {}

    r_score = float(rigor.get("score") or 0.0)
    s_score = float(safety.get("score") or 0.0)
    i_score = float(innovation.get("score") or 0.0)
    sota_innov = float(sota.get("innovation_vs_sota_score") or 0.0)
    sota_impl = float(sota.get("implementation_vs_sota_score") or 0.0)

    total_critical = sum(int((audits.get(k) or {}).get("critical_count", 0)) for k in ("rigor", "safety", "innovation"))
    total_high = sum(int((audits.get(k) or {}).get("high_count", 0)) for k in ("rigor", "safety", "innovation"))
    total_enhancements = sum(
        int((audits.get(k) or {}).get("enhancement_count", 0)) for k in ("rigor", "safety", "innovation")
    )

    # Verify codebase authenticity (no synthetic, no half-baked/placeholder, no unwired conceptual code)
    # and verify Goal-Loop tasks/subtasks + outcome_cmd if configured
    authenticity_passed = True
    authenticity_counts: dict[str, int] = {
        "placeholder_or_half_baked": 0,
        "synthetic_or_mock": 0,
        "unwired_conceptual_modules": 0,
        "total_violations": 0,
    }
    goal_outcome_passed = True
    goal_errors: list[str] = []

    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import goal_loop
        cwd = os.getcwd()
        goal_file = goal_loop.resolve_goal_file(cwd=cwd, create_dir=False)
        if os.path.exists(goal_file) or outcome_cmd:
            g_res = goal_loop.verify_goal_state(
                cwd=cwd,
                outcome_cmd_override=outcome_cmd,
                expect_output_override=expect_output,
            )
            goal_outcome_passed = bool(g_res.get("goal_reached", False))
            authenticity_counts = g_res.get("authenticity", authenticity_counts)
            authenticity_passed = authenticity_counts.get("total_violations", 0) == 0
            goal_errors = g_res.get("errors", [])
        elif os.path.abspath(cwd) != os.path.abspath(PLUGIN_DIR):
            auth_res = goal_loop.audit_authenticity(root_dir=cwd, check_orphan_modules=True)
            authenticity_passed = bool(auth_res.get("passed", True))
            authenticity_counts = auth_res.get("counts", authenticity_counts)
    except Exception:
        pass

    scores_converged = (
        r_score >= CONVERGENCE_RIGOR_THRESHOLD
        and s_score >= CONVERGENCE_SAFETY_THRESHOLD
        and i_score >= CONVERGENCE_INNOVATION_THRESHOLD
        and sota_innov >= CONVERGENCE_INNOVATION_THRESHOLD
        and sota_impl >= CONVERGENCE_INNOVATION_THRESHOLD
    )
    no_blocking_findings = (total_critical == 0) and (total_high == 0) and (total_enhancements == 0)
    truly_converged = scores_converged and no_blocking_findings and authenticity_passed and goal_outcome_passed

    if truly_converged:
        decision = "CONVERGED_NO_IMPROVEMENTS_NEEDED"
        next_epoch = None
        next_focus = (
            "All Rigor, Safety, Innovation, SOTA benchmarks, Authenticity (0 synthetic/placeholder/unwired), "
            "and End-to-End Outcome checks verified. Proceed to Final Report."
        )
    elif current_ep < MAX_MACRO_EPOCHS:
        decision = "CONTINUE_NEXT_EPOCH"
        next_epoch = current_ep + 1
        next_focus = get_epoch_focus(next_epoch)
    elif not allow_stop_unconverged and current_ep < HARD_MAX_REMEDIATION_EPOCHS:
        decision = "CONTINUE_UNTIL_GOAL_MET"
        next_epoch = current_ep + 1
        state["max_epochs"] = max(state.get("max_epochs", MAX_MACRO_EPOCHS), next_epoch)
        next_focus = get_epoch_focus(next_epoch)
    else:
        decision = "MAX_EPOCHS_REACHED"
        next_epoch = None
        next_focus = f"Reached hard safety epoch cap ({current_ep}). Escalate remaining gaps in Final Report."

    if plan_path:
        ep_rec["adjusted_plan"] = plan_path

    ledger_summary = inspect_swarm_ledgers(cwd=os.getcwd())

    result = {
        "evaluated_epoch": current_ep,
        "max_epochs": state.get("max_epochs", MAX_MACRO_EPOCHS),
        "timestamp": now_iso(),
        "scores": {
            "rigor": r_score,
            "safety": s_score,
            "innovation": i_score,
            "sota_innovation": sota_innov,
            "sota_implementation": sota_impl,
        },
        "findings_Remaining": {
            "critical": total_critical,
            "high": total_high,
            "enhancements": total_enhancements,
        },
        "authenticity_verified": authenticity_passed,
        "authenticity_counts": authenticity_counts,
        "outcome_verified": goal_outcome_passed,
        "goal_errors": goal_errors[:8],
        "ledgers": ledger_summary,
        "decision": decision,
        "next_epoch": next_epoch,
        "next_epoch_focus": next_focus,
        "adjusted_plan_path": plan_path or None,
    }
    ep_rec["convergence"] = result
    save_state(state)

    log(
        f"🔄 MACRO-LOOP CONVERGENCE GATE (Epoch {current_ep}/{state.get('max_epochs', MAX_MACRO_EPOCHS)}) -> [{decision}] | "
        f"Rigor={r_score}, Safety={s_score}, Innov={i_score}, SOTA=({sota_innov}/{sota_impl}) | "
        f"Crit={total_critical}, High={total_high} | Auth={authenticity_passed} | Outcome={goal_outcome_passed} | "
        f"Rulings={ledger_summary['rulings_count']} | DeferredMinors={ledger_summary['deferred_minor_count']}"
    )
    print(json.dumps(result, indent=2))
    return result


def record_overall_evaluation(score: float, tests_passed: bool, security_passed: bool, notes: str = "") -> None:
    state = load_state()
    approved = (score >= PASSING_SCORE_THRESHOLD) and tests_passed and security_passed
    evaluation = {
        "timestamp": now_iso(),
        "final_epoch": state.get("current_epoch", 1),
        "overall_goal_score": score,
        "tests_passed": tests_passed,
        "security_passed": security_passed,
        "status": "SUCCESS" if approved else "NEEDS_REMEDIATION",
        "notes": notes,
    }
    state["overall_evaluation"] = evaluation
    save_state(state)
    log(
        f"🏁 FINAL ORCHESTRATOR EVALUATION [{evaluation['status']}]: "
        f"Epoch {evaluation['final_epoch']}/{state.get('max_epochs', MAX_MACRO_EPOCHS)} | "
        f"Overall Score: {score}/10 | Tests: {tests_passed} | Security: {security_passed}"
    )
    print(json.dumps(evaluation, indent=2))


def supervise_tasks() -> None:
    state = load_state()
    tasks = state.get("tasks", {})
    modified = False

    for name, task in list(tasks.items()):
        if task.get("status") == "COMPLETED":
            continue

        pid = task.get("pid")
        cwd = task.get("cwd")
        v_cmd = task.get("validation_cmd")
        attempts = task.get("attempts", 1)

        if validate_task_done(v_cmd, cwd=cwd):
            log(f"✅ TASK FULFILLED: Task '{name}' passed validation condition!")
            task["status"] = "COMPLETED"
            modified = True
            continue

        running = pid and is_running(pid)

        if not running:
            if attempts >= MAX_REVIVE_ATTEMPTS:
                log(f"❌ TASK EXHAUSTED: Task '{name}' died after {attempts} attempts without passing validation.")
                task["status"] = "FAILED"
                modified = True
                continue

            attempts += 1
            log(
                f"⚠️ WORKER DIED: Task '{name}' died before validation met. "
                f"Auto-reviving (Attempt {attempts}/{MAX_REVIVE_ATTEMPTS})..."
            )
            new_pid = spawn_task_process(name, task["command"], cwd=cwd)
            task["pid"] = new_pid
            task["attempts"] = attempts
            task["last_revived"] = now_iso()
            task["status"] = "RUNNING"
            modified = True

    if modified:
        save_state(state)


def run_loop(single_run: bool = False, stall_seconds: int = DEFAULT_STALL_SECONDS) -> None:
    log("Immortal Watcher started. Monitoring connectivity, OS tasks, subagent transcripts, and .swarm ledgers.")
    consecutive_outages = 0

    while True:
        online = check_internet()
        if not online:
            consecutive_outages += 1
            log(f"WARNING: Network probe failed (Outage count: {consecutive_outages}). Swarm paused.")
        else:
            if consecutive_outages > 0:
                log(f"RECOVERY: Network connectivity restored after {consecutive_outages} cycles.")
                consecutive_outages = 0

        supervise_tasks()
        check_subagents(stall_seconds=stall_seconds, as_json=False)

        state = load_state()
        tasks = state.get("tasks", {})
        subagents = state.get("subagents", {})
        active_tasks = sum(1 for t in tasks.values() if t.get("status") == "RUNNING")
        active_subs = sum(
            1
            for s in subagents.values()
            if s.get("status") in ("RUNNING", "REFINING", "ESCALATED_FRESH_WORKER", "STALLED", "INTERRUPTED")
        )
        approved_subs = sum(
            1 for s in subagents.values() if s.get("status") in ("APPROVED", "APPROVED_WITH_RULING", "MERGED")
        )
        ledger_info = inspect_swarm_ledgers(cwd=os.getcwd())
        log(
            f"HEALTH CHECK OK | Epoch: {state.get('current_epoch', 1)}/{MAX_MACRO_EPOCHS} | Online: {online} | "
            f"Active Subagents: {active_subs} | Approved Subagents: {approved_subs} | Active OS Tasks: {active_tasks} | "
            f"Goal Tasks: {ledger_info['goal_tasks_done']}/{ledger_info['goal_tasks_total']} | "
            f"Rulings: {ledger_info['rulings_count']} | Deferred Minors: {ledger_info['deferred_minor_count']}"
        )

        if single_run:
            log("Test run completed successfully.")
            break

        time.sleep(CHECK_INTERVAL)


def start_daemon(stall_seconds: int = DEFAULT_STALL_SECONDS) -> None:
    if os.path.exists(PID_FILE):
        with open(PID_FILE, "r", encoding="utf-8") as f:
            try:
                pid = int(f.read().strip())
                if is_running(pid):
                    print(f"Immortal Watcher is already running (PID: {pid}).")
                    return
            except ValueError:
                pass

    pid = os.fork()
    if pid > 0:
        with open(PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(pid))
        print(f"Immortal Watcher daemon launched (PID: {pid}). Logs at {LOG_FILE}")
        sys.exit(0)

    os.setsid()
    with open(os.devnull, "r", encoding="utf-8") as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())

    run_loop(single_run=False, stall_seconds=stall_seconds)


def stop_daemon() -> None:
    if not os.path.exists(PID_FILE):
        print("No PID file found. Immortal Watcher does not appear to be running.")
        return

    with open(PID_FILE, "r", encoding="utf-8") as f:
        try:
            pid = int(f.read().strip())
        except ValueError:
            pid = None

    if pid and is_running(pid):
        os.kill(pid, signal.SIGTERM)
        print(f"Terminated Immortal Watcher process {pid}.")
    else:
        print(f"Process {pid} was not running.")

    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)


def status_daemon() -> None:
    running = False
    pid = None
    if os.path.exists(PID_FILE):
        with open(PID_FILE, "r", encoding="utf-8") as f:
            try:
                pid = int(f.read().strip())
                running = is_running(pid)
            except ValueError:
                pass

    status_str = f"ACTIVE (PID: {pid})" if running else "INACTIVE"
    print(f"Immortal Watcher Daemon: {status_str}")

    state = load_state()
    curr_ep = state.get("current_epoch", 1)
    print(f"Macro-Loop Epoch: {curr_ep}/{state.get('max_epochs', MAX_MACRO_EPOCHS)}")
    if state.get("project_goal"):
        print(f"Project Goal: {state['project_goal']}")

    ledger_info = inspect_swarm_ledgers(cwd=os.getcwd())
    print(
        f"Goal-Loop & Ledgers: Tasks={ledger_info['goal_tasks_done']}/{ledger_info['goal_tasks_total']} "
        f"(Ruled: {ledger_info['goal_tasks_ruled']}) | "
        f"`.swarm/ledger.md` Entries={ledger_info['ledger_entries']} (Rulings: {ledger_info['rulings_count']}) | "
        f"`.swarm/deferred_minor_ledger.md` Items={ledger_info['deferred_minor_count']}"
    )

    subagents = state.get("subagents", {})
    if subagents:
        print("\nManaged Swarm Subagents (5-Round Escalating Fix Loop: 1-3 Same Worker, 4-5 Fresh Worker, 5 Breaker):")
        for conv_id, s in subagents.items():
            impl_s = s.get("impl_score")
            goal_s = s.get("goal_score")
            cap_s = f", HardCap={s.get('hard_cap')}" if s.get("hard_cap") is not None else ""
            score_str = f"Impl={impl_s}/10, Goal={goal_s}/10{cap_s}" if impl_s is not None else "Unscored"
            ruling_s = f" | Ruling: {s.get('ruling')}" if s.get("ruling") else ""
            print(
                f"  - [{s.get('status')}] (Epoch {s.get('epoch', 1)}) {s.get('role')} "
                f"[kind={s.get('agent_kind', 'worker')}] (ID: {conv_id}, Branch: {s.get('branch') or 'N/A'}) | "
                f"Fix Rounds: {s.get('loop_count', 0)}/{MAX_DISCRIMINATOR_LOOPS} ({score_str}) | "
                f"Revives: {s.get('revive_attempts', 0)}/{MAX_REVIVE_ATTEMPTS}{ruling_s}"
            )

    epochs = state.get("epochs", {})
    if epochs:
        print("\nEpoch Audit & SOTA Summary:")
        for ep_k, ep_v in sorted(epochs.items(), key=lambda x: int(x[0])):
            auds = ep_v.get("audits", {})
            r_s = (auds.get("rigor") or {}).get("score", "-")
            s_s = (auds.get("safety") or {}).get("score", "-")
            i_s = (auds.get("innovation") or {}).get("score", "-")
            sota_ev = ep_v.get("sota_evaluation") or {}
            sota_str = (
                f"Innov={sota_ev.get('innovation_vs_sota_score')}/10, "
                f"Impl={sota_ev.get('implementation_vs_sota_score')}/10"
                if sota_ev
                else "Pending"
            )
            conv_decision = (ep_v.get("convergence") or {}).get("decision", "IN_PROGRESS")
            print(
                f"  - Epoch {ep_k}: Rigor={r_s}/10 | Safety={s_s}/10 | Innovation={i_s}/10 | "
                f"SOTA=({sota_str}) | Gate: {conv_decision}"
            )

    tasks = state.get("tasks", {})
    if tasks:
        print("\nManaged OS Tasks:")
        for name, t in tasks.items():
            print(
                f"  - [{t.get('status')}] {name} (PID: {t.get('pid')}, "
                f"Attempts: {t.get('attempts')}/{MAX_REVIVE_ATTEMPTS})"
            )

    if state.get("overall_evaluation"):
        ov = state["overall_evaluation"]
        print(
            f"\nOverall Project Evaluation: [{ov.get('status')}] "
            f"(Epoch {ov.get('final_epoch', curr_ep)}) "
            f"Score={ov.get('overall_goal_score')}/10 | Tests={ov.get('tests_passed')} | "
            f"Security={ov.get('security_passed')}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Immortal Agents Supervisor, Subagent Revival & 3-Epoch Evolutionary Swarm Ledger"
    )
    parser.add_argument("--start", action="store_true", help="Start supervisor daemon in background")
    parser.add_argument("--stop", action="store_true", help="Stop background supervisor daemon")
    parser.add_argument("--status", action="store_true", help="Check supervisor, subagent, audit, and epoch status")
    parser.add_argument("--logs", action="store_true", help="Print recent supervisor logs")
    parser.add_argument("--test-run", action="store_true", help="Run a single diagnostic check cycle")
    parser.add_argument("--init-swarm", action="store_true", help="Reset and initialize swarm ledger for a new run")
    parser.add_argument("--project-goal", default="", help="Overall project goal description (used with --init-swarm)")
    parser.add_argument("--start-epoch", type=int, metavar="N", help="Advance/start Macro-Loop Epoch N (1..3)")

    # Subagent management & revival flags
    parser.add_argument("--register-subagent", metavar="CONV_ID", help="Register a spawned subagent conversation ID")
    parser.add_argument("--role", default="Swarm Worker", help="Role title for the registered subagent")
    parser.add_argument(
        "--agent-kind",
        default="worker",
        choices=["worker", "discriminator", "auditor", "sota_scout", "watcher"],
        help="Category of subagent",
    )
    parser.add_argument("--branch", default="", help="Git worktree branch for the subagent")
    parser.add_argument("--worktree", default="", help="Worktree directory path for the subagent")
    parser.add_argument("--impl-goal", default="", help="Specific implementation goal for the subagent")
    parser.add_argument("--check-subagents", action="store_true", help="Check all registered subagents for stalls/errors")
    parser.add_argument("--stall-seconds", type=int, default=DEFAULT_STALL_SECONDS, help="Inactivity threshold in seconds")
    parser.add_argument("--mark-revived", metavar="CONV_ID", help="Record that a stalled/interrupted subagent was revived")
    parser.add_argument("--json", action="store_true", help="Format check output as JSON")

    # Step 1.5 Discriminator Two-Verdict + Hard-Cap review & 5-Round Escalating Loop flags
    parser.add_argument("--record-review", metavar="CONV_ID", help="Record a Discriminator Two-Verdict + Hard-Cap assessment")
    parser.add_argument("--impl-score", type=float, default=9.2, help="Implementation goal score (1.0 - 10.0, default 9.2)")
    parser.add_argument("--goal-score", type=float, default=9.2, help="Overall project goal score (1.0 - 10.0, default 9.2)")
    parser.add_argument(
        "--spec-verdict",
        choices=["PASS", "FAIL", "UNVERIFIABLE"],
        default="PASS",
        help="Part 1 Spec Compliance Verdict (PASS, FAIL, UNVERIFIABLE; non-PASS hard-caps score at 6.0)",
    )
    parser.add_argument("--critical-flaws", type=int, default=0, help="Count of Critical findings (hard-caps score at 6.0)")
    parser.add_argument(
        "--major-flaws",
        "--important-flaws",
        dest="major_flaws",
        type=int,
        default=0,
        help="Count of Important/Major findings (hard-caps score at 7.0)",
    )
    parser.add_argument(
        "--minor-flaws",
        type=int,
        default=0,
        help="Count of Minor findings (deferred to `.swarm/deferred_minor_ledger.md`, NEVER blocks completion)",
    )
    parser.add_argument(
        "--ruling",
        default="",
        help="Round 5 Breaker adjudication (`Ruling: <what> — <why> — <cost if wrong>`) recorded in `.swarm/ledger.md`",
    )
    parser.add_argument(
        "--adversarial-cmd",
        default="",
        help="Independent adversarial/boundary verification command executed by Discriminator",
    )
    parser.add_argument(
        "--outcome-cmd",
        default="",
        help="End-to-end command verifying that the implementation actually produces the desired product output",
    )
    parser.add_argument(
        "--expect-output",
        default="",
        help="Regex or substring that must appear in --outcome-cmd stdout",
    )
    parser.add_argument(
        "--pass-hat-k",
        type=int,
        default=1,
        help="Number of consecutive trials --adversarial-cmd must pass (pass^k flakiness gate, default: 1)",
    )
    parser.add_argument(
        "--allow-config-edits",
        action="store_true",
        help="Allow worker diff to modify linter/config/contract files without config-tampering block",
    )
    parser.add_argument(
        "--uncalibrated",
        action="store_true",
        help="Bypass Hard-Cap enforcement (not recommended; for internal testing only)",
    )
    parser.add_argument("--notes", default="", help="Critique, summary, or notes")

    # Git Snapshot Rollback flags
    parser.add_argument("--snapshot-create", metavar="LABEL", help="Save current git HEAD SHA snapshot before merge/refactor")
    parser.add_argument("--snapshot-restore", metavar="LABEL", help="Restore worktree to a saved git HEAD SHA snapshot")

    # Step 3 Intermittent Report flag
    parser.add_argument("--record-intermittent", metavar="REPORT_PATH", help="Record Step 3 Intermittent Report path")

    # Step 4-5 Triad Audit flags
    parser.add_argument(
        "--record-audit",
        choices=["rigor", "safety", "innovation"],
        help="Record a Step 4-5 Triad Audit score (rigor, safety, or innovation)",
    )
    parser.add_argument("--audit-score", type=float, help="Auditor score (1.0 - 10.0)")
    parser.add_argument("--critical-count", type=int, default=0, help="Number of CRITICAL findings")
    parser.add_argument("--high-count", type=int, default=0, help="Number of HIGH severity findings")
    parser.add_argument("--enhancement-count", type=int, default=0, help="Number of ENHANCEMENT findings")
    parser.add_argument("--report-path", default="", help="Path to detailed markdown/json report")

    # Step 6 SOTA Web Scout flags
    parser.add_argument("--record-sota", action="store_true", help="Record Step 6 SOTA Web Scout continuous evaluation")
    parser.add_argument("--sota-innovation-score", type=float, help="Project innovation vs SOTA score (1.0 - 10.0)")
    parser.add_argument("--sota-impl-score", type=float, help="Project implementation vs SOTA score (1.0 - 10.0)")
    parser.add_argument("--benchmark-path", default="", help="Path to SOTA benchmark markdown file")

    # Step 7 Convergence & Re-Plan check
    parser.add_argument(
        "--check-convergence",
        action="store_true",
        help="Evaluate Step 7 convergence across Triad Audits, SOTA Scout, Authenticity & Desired Outcome",
    )
    parser.add_argument("--plan-path", default="", help="Path to adjusted implementation plan for next epoch")
    parser.add_argument(
        "--allow-stop-unconverged",
        action="store_true",
        help="Allow stopping at Epoch 3 even if outcome/convergence is not yet reached (default: false — runs until goal met)",
    )

    # Final Orchestrator holistic evaluation flags
    parser.add_argument("--record-overall", action="store_true", help="Record final Orchestrator whole-project evaluation")
    parser.add_argument("--overall-score", type=float, help="Final whole-project goal score (1.0 - 10.0)")
    parser.add_argument("--tests-passed", action="store_true", help="Flag indicating full integrated tests passed")
    parser.add_argument("--security-passed", action="store_true", help="Flag indicating security audit passed")

    # Cross-epoch negative memory, instincts & dashboard flags
    parser.add_argument("--add-lesson", metavar="TEXT", help="Record a cross-epoch anti-regression lesson/invariant")
    parser.add_argument("--lesson-category", default="architecture", help="Category for --add-lesson")
    parser.add_argument("--lessons-file", default=".swarm/lessons_learned.md", help="Markdown path for lessons learned")
    parser.add_argument("--list-lessons", action="store_true", help="List all recorded cross-epoch lessons")
    parser.add_argument("--inject-instincts", action="store_true", help="Output Top-K context-budgeted instincts for current repo")
    parser.add_argument("--promote-instincts", action="store_true", help="Promote qualifying project instincts to global memory")
    parser.add_argument("--generate-dashboard", action="store_true", help="Generate .swarm/dashboard.html telemetry UI")
    parser.add_argument("--dashboard-out", default=".swarm/dashboard.html", help="Output path for dashboard HTML")

    # Persistent OS task flags
    parser.add_argument("--register-task", help="Register a persistent OS task: <task_name>")
    parser.add_argument("--command", help="Execution command for the OS task")
    parser.add_argument("--validation", help="Verification command proving OS task is done")
    parser.add_argument("--cwd", help="Working directory for the OS task")

    args = parser.parse_args()

    if args.init_swarm:
        init_swarm(project_goal=args.project_goal)
    elif args.start_epoch is not None:
        start_epoch(args.start_epoch)
    elif args.snapshot_create:
        create_git_snapshot(label=args.snapshot_create, cwd=args.cwd)
    elif args.snapshot_restore:
        restore_git_snapshot(label=args.snapshot_restore, cwd=args.cwd)
    elif args.add_lesson:
        add_lesson(lesson=args.add_lesson, category=args.lesson_category, lessons_file=args.lessons_file)
    elif args.list_lessons:
        list_lessons(as_json=args.json)
    elif args.inject_instincts:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import instinct_manager
        if args.json:
            print(json.dumps(instinct_manager.get_ranked_instincts(cwd=args.cwd), indent=2))
        else:
            print(instinct_manager.format_injection_block(cwd=args.cwd))
    elif args.promote_instincts:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import instinct_manager
        promoted = instinct_manager.promote_qualifying_instincts(cwd=args.cwd)
        print(json.dumps({"promoted_count": len(promoted), "promoted": promoted}, indent=2))
    elif args.generate_dashboard:
        import swarm_dashboard
        swarm_dashboard.generate_dashboard(out_file=args.dashboard_out)
    elif args.register_subagent:
        register_subagent(
            conv_id=args.register_subagent,
            role=args.role,
            branch=args.branch,
            worktree=args.worktree,
            implementation_goal=args.impl_goal,
            agent_kind=args.agent_kind,
        )
    elif args.check_subagents:
        check_subagents(stall_seconds=args.stall_seconds, as_json=args.json)
    elif args.mark_revived:
        mark_revived(args.mark_revived)
    elif args.record_review:
        record_review(
            conv_id=args.record_review,
            impl_score=args.impl_score,
            goal_score=args.goal_score,
            notes=args.notes,
            critical_flaws=args.critical_flaws,
            major_flaws=args.major_flaws,
            minor_flaws=args.minor_flaws,
            spec_verdict=args.spec_verdict,
            ruling=args.ruling,
            adversarial_cmd=args.adversarial_cmd,
            outcome_cmd=args.outcome_cmd,
            expect_output=args.expect_output,
            worktree_override=args.worktree,
            branch_override=args.branch,
            uncalibrated=args.uncalibrated,
            pass_hat_k=args.pass_hat_k,
            allow_config_edits=args.allow_config_edits,
        )
    elif args.record_intermittent:
        record_intermittent_report(report_path=args.record_intermittent, summary=args.notes)
    elif args.record_audit:
        if args.audit_score is None:
            print("Error: --record-audit requires --audit-score (1-10).")
            sys.exit(1)
        record_audit(
            auditor=args.record_audit,
            score=args.audit_score,
            critical_count=args.critical_count,
            high_count=args.high_count,
            enhancement_count=args.enhancement_count,
            report_path=args.report_path,
            notes=args.notes,
        )
    elif args.record_sota:
        if args.sota_innovation_score is None or args.sota_impl_score is None:
            print("Error: --record-sota requires --sota-innovation-score and --sota-impl-score (1-10).")
            sys.exit(1)
        record_sota(
            innovation_score=args.sota_innovation_score,
            sota_impl_score=args.sota_impl_score,
            benchmark_path=args.benchmark_path,
            top_gaps=args.notes,
        )
    elif args.check_convergence:
        check_convergence(
            plan_path=args.plan_path,
            outcome_cmd=args.outcome_cmd,
            expect_output=args.expect_output,
            allow_stop_unconverged=args.allow_stop_unconverged,
        )
    elif args.record_overall:
        if args.overall_score is None:
            print("Error: --record-overall requires --overall-score (1-10).")
            sys.exit(1)
        record_overall_evaluation(
            score=args.overall_score,
            tests_passed=args.tests_passed,
            security_passed=args.security_passed,
            notes=args.notes,
        )
    elif args.register_task:
        if not args.command or not args.validation:
            print("Error: --register-task requires --command and --validation arguments.")
            sys.exit(1)
        register_task(args.register_task, args.command, args.validation, cwd=args.cwd)
    elif args.start:
        start_daemon(stall_seconds=args.stall_seconds)
    elif args.stop:
        stop_daemon()
    elif args.status:
        status_daemon()
    elif args.logs:
        if os.path.exists(LOG_FILE):
            subprocess.run(["tail", "-n", "30", LOG_FILE], check=False)
        else:
            print("No log file found.")
    elif args.test_run:
        run_loop(single_run=True, stall_seconds=args.stall_seconds)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
