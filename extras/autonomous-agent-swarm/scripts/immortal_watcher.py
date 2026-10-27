#!/usr/bin/env python3
"""Immortal Agents Watcher & Task Revival Supervisor for Ubuntu / Linux.

Monitors internet connectivity, process heartbeats, and swarm worker tasks.
If an agent or worker process dies before fulfilling its verifiable validation condition,
the supervisor automatically restarts and revives it until the task is complete.
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

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(PLUGIN_DIR, "scripts", "immortal_watcher.log")
PID_FILE = os.path.join(PLUGIN_DIR, "scripts", "immortal_watcher.pid")
TASKS_FILE = os.path.join(PLUGIN_DIR, "scripts", "swarm_tasks.json")
PROBE_URL = "http://captive.apple.com/hotspot-detect.html"
PROBE_TIMEOUT = 5
CHECK_INTERVAL = 10
MAX_REVIVE_ATTEMPTS = 5


def log(msg: str) -> None:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    entry = f"[{now}] {msg}"
    print(entry)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


def load_tasks() -> dict[str, dict]:
    if not os.path.exists(TASKS_FILE):
        return {}
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_tasks(tasks: dict[str, dict]) -> None:
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)


def check_internet() -> bool:
    try:
        req = urllib.request.Request(PROBE_URL, headers={"User-Agent": "ImmortalWatcher/1.0"})
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
        res = subprocess.run(validation_cmd, shell=True, cwd=cwd, capture_output=True, text=True, check=False)
        return res.returncode == 0
    except Exception:
        return False


def spawn_task_process(task_name: str, cmd: str, cwd: str | None = None) -> int:
    task_log = os.path.join(PLUGIN_DIR, "scripts", f"task_{task_name}.log")
    with open(task_log, "a", encoding="utf-8") as out:
        out.write(f"\n--- [SPAWN {datetime.datetime.now().isoformat()}] {cmd} ---\n")
        proc = subprocess.Popen(
            cmd,
            shell=True,
            cwd=cwd,
            stdout=out,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid
        )
    return proc.pid


def register_task(name: str, command: str, validation_cmd: str, cwd: str | None = None) -> None:
    tasks = load_tasks()
    pid = spawn_task_process(name, command, cwd=cwd)
    tasks[name] = {
        "command": command,
        "validation_cmd": validation_cmd,
        "cwd": cwd or os.getcwd(),
        "pid": pid,
        "status": "RUNNING",
        "attempts": 1,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "last_revived": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    save_tasks(tasks)
    log(f"Registered persistent task '{name}' (PID: {pid}). Validation: {validation_cmd}")


def supervise_tasks() -> None:
    tasks = load_tasks()
    modified = False

    for name, task in list(tasks.items()):
        if task.get("status") == "COMPLETED":
            continue

        pid = task.get("pid")
        cwd = task.get("cwd")
        v_cmd = task.get("validation_cmd")
        attempts = task.get("attempts", 1)

        # 1. Check if the validation condition has already been fulfilled
        if validate_task_done(v_cmd, cwd=cwd):
            log(f"✅ TASK FULFILLED: Task '{name}' passed validation condition!")
            task["status"] = "COMPLETED"
            modified = True
            continue

        # 2. Check if process is still running
        running = pid and is_running(pid)

        # 3. If process died and validation NOT met -> REVIVE IT!
        if not running:
            if attempts >= MAX_REVIVE_ATTEMPTS:
                log(f"❌ TASK EXHAUSTED: Task '{name}' died after {attempts} attempts without passing validation.")
                task["status"] = "FAILED"
                modified = True
                continue

            attempts += 1
            log(f"⚠️ WORKER DIED: Task '{name}' died before validation met. Auto-reviving (Attempt {attempts}/{MAX_REVIVE_ATTEMPTS})...")
            new_pid = spawn_task_process(name, task["command"], cwd=cwd)
            task["pid"] = new_pid
            task["attempts"] = attempts
            task["last_revived"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            task["status"] = "RUNNING"
            modified = True

    if modified:
        save_tasks(tasks)


def run_loop(single_run: bool = False) -> None:
    log("Immortal Watcher started. Monitoring connectivity and persistent tasks.")
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

        # Supervise registered agent tasks & revive any that died
        supervise_tasks()

        tasks = load_tasks()
        active = sum(1 for t in tasks.values() if t.get("status") == "RUNNING")
        completed = sum(1 for t in tasks.values() if t.get("status") == "COMPLETED")
        log(f"HEALTH CHECK OK | Online: {online} | Active Tasks: {active} | Completed Tasks: {completed}")

        if single_run:
            log("Test run completed successfully.")
            break

        time.sleep(CHECK_INTERVAL)


def start_daemon() -> None:
    if os.path.exists(PID_FILE):
        with open(PID_FILE, "r") as f:
            try:
                pid = int(f.read().strip())
                if is_running(pid):
                    print(f"Immortal Watcher is already running (PID: {pid}).")
                    return
            except ValueError:
                pass

    pid = os.fork()
    if pid > 0:
        with open(PID_FILE, "w") as f:
            f.write(str(pid))
        print(f"Immortal Watcher daemon launched (PID: {pid}). Logs at {LOG_FILE}")
        sys.exit(0)

    # In child process
    os.setsid()
    with open(os.devnull, "r") as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())

    run_loop(single_run=False)


def stop_daemon() -> None:
    if not os.path.exists(PID_FILE):
        print("No PID file found. Immortal Watcher does not appear to be running.")
        return

    with open(PID_FILE, "r") as f:
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
        with open(PID_FILE, "r") as f:
            try:
                pid = int(f.read().strip())
                running = is_running(pid)
            except ValueError:
                pass

    status_str = f"ACTIVE (PID: {pid})" if running else "INACTIVE"
    print(f"Immortal Watcher: {status_str}")

    tasks = load_tasks()
    if tasks:
        print("\nManaged Swarm Tasks:")
        for name, t in tasks.items():
            print(f"  - [{t.get('status')}] {name} (PID: {t.get('pid')}, Attempts: {t.get('attempts')}/{MAX_REVIVE_ATTEMPTS})")
            print(f"    Validation: {t.get('validation_cmd')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Immortal Agents Supervisor & Task Revival Watcher")
    parser.add_argument("--start", action="store_true", help="Start supervisor in background")
    parser.add_argument("--stop", action="store_true", help="Stop background supervisor")
    parser.add_argument("--status", action="store_true", help="Check supervisor and task running status")
    parser.add_argument("--logs", action="store_true", help="Print recent supervisor logs")
    parser.add_argument("--test-run", action="store_true", help="Run a single diagnostic check cycle")
    parser.add_argument("--register-task", help="Register a persistent task: <task_name>")
    parser.add_argument("--command", help="Execution command for the task")
    parser.add_argument("--validation", help="Verification command proving task is done")
    parser.add_argument("--cwd", help="Working directory for task")
    args = parser.parse_args()

    if args.register_task:
        if not args.command or not args.validation:
            print("Error: --register-task requires --command and --validation arguments.")
            sys.exit(1)
        register_task(args.register_task, args.command, args.validation, cwd=args.cwd)
    elif args.start:
        start_daemon()
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
        run_loop(single_run=True)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
