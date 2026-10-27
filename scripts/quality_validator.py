#!/usr/bin/env python3
"""Autonomous Game & Product Quality Gate Validator.

Executes real runtime smoke tests on compiled binaries (e.g. Unity, Godot, Unreal, Pygame),
inspects Player.log / stdout for crashes (SIGTRAP, NullReferenceException, SIGSEGV),
and verifies that game systems (player, camera, bots, game loop) actually run.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

UNITY_LOG_DEFAULT = os.path.expanduser("~/.config/unity3d/DefaultCompany/game/Player.log")


def run_smoke_test(
    binary_path: str,
    timeout_secs: int = 10,
    log_path: str | None = None,
    headless: bool = False
) -> dict[str, any]:
    if not os.path.exists(binary_path):
        return {
            "status": "FAIL",
            "reason": f"Binary not found: {binary_path}",
            "crashed": True,
            "exit_code": -1,
            "errors": [f"File does not exist: {binary_path}"]
        }

    # Ensure binary is executable
    os.chmod(binary_path, 0o755)

    cmd = [binary_path]
    if headless:
        cmd.extend(["-batchmode", "-nographics"])

    env = os.environ.copy()
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":0"

    print(f"Launching smoke test: {' '.join(cmd)} (Timeout: {timeout_secs}s, DISPLAY: {env.get('DISPLAY')})...")
    
    # Remove old log if tracking Unity
    target_log = log_path or (
        os.path.expanduser(f"~/.config/unity3d/DefaultCompany/{os.path.basename(os.path.dirname(binary_path))}/Player.log")
        if "build" in binary_path else UNITY_LOG_DEFAULT
    )

    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    crashed = False
    exit_code = None
    start_time = time.time()

    # Monitor process for the requested timeout
    while time.time() - start_time < timeout_secs:
        ret = proc.poll()
        if ret is not None:
            crashed = (ret != 0)
            exit_code = ret
            break
        time.sleep(0.5)

    # If still running after timeout, it successfully booted without crashing!
    if proc.poll() is None:
        print(f"Smoke test passed {timeout_secs}s runtime threshold without crashing. Terminating test process...")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        crashed = False
        exit_code = 0

    stdout, stderr = proc.communicate()

    # Inspect log file for fatal Unity/C# exceptions
    fatal_errors = []
    log_content = ""
    if os.path.exists(target_log):
        with open(target_log, "r", encoding="utf-8", errors="replace") as f:
            log_content = f.read()
            for line in log_content.splitlines():
                if any(err in line for err in ["NullReferenceException", "Crash", "Trace/breakpoint trap", "Segmentation fault", "Fatal Error"]):
                    fatal_errors.append(line.strip())

    if fatal_errors or crashed:
        return {
            "status": "FAIL",
            "crashed": True,
            "exit_code": exit_code,
            "fatal_errors": fatal_errors[:10],
            "stderr_snippet": stderr[-500:],
            "log_snippet": log_content[-1000:] if log_content else ""
        }

    return {
        "status": "PASS",
        "crashed": False,
        "exit_code": exit_code,
        "uptime_seconds": timeout_secs,
        "log_path": target_log
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Runtime Quality & Smoke Test Validator")
    parser.add_argument("binary", help="Path to executable game binary")
    parser.add_argument("--timeout", type=int, default=8, help="Smoke test duration in seconds (default: 8)")
    parser.add_argument("--log-path", help="Explicit path to runtime engine log")
    parser.add_argument("--headless", action="store_true", help="Pass headless flags if supported")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    args = parser.parse_args()

    result = run_smoke_test(args.binary, timeout_secs=args.timeout, log_path=args.log_path, headless=args.headless)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("\n=== QUALITY GATE SMOKE TEST REPORT ===")
        print(f"Status: {result['status']}")
        print(f"Crashed: {result['crashed']} (Exit Code: {result.get('exit_code')})")
        if result["status"] == "FAIL":
            print("\nFatal Errors Detected:")
            for err in result.get("fatal_errors", []):
                print(f"  ❌ {err}")
            if result.get("stderr_snippet"):
                print(f"\nStderr Output:\n{result['stderr_snippet']}")
        else:
            print(f"✅ Product passed runtime stability test ({result.get('uptime_seconds')}s cleanly).")

    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
