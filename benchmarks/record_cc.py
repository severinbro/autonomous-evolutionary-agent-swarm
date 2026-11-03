#!/usr/bin/env python3
"""Append one Claude Code run's telemetry (from Agent completion notices) to telemetry_claude_code.json.

Usage: record_cc.py <arm> <task_key> <run_id> <wall_seconds> <tokens> <tool_calls> [<tokens> <tool_calls> ...]
Each <tokens> <tool_calls> pair is one subagent; totals are summed. Set TELEMETRY_FILE to write elsewhere. Wall time is measured by the caller
(for parallel arms: from the first launch to the last completion, plus any deterministic step).
"""
import json
import os
import sys
from pathlib import Path

path = Path(os.environ.get("TELEMETRY_FILE", Path(__file__).resolve().parent / "telemetry_claude_code.json"))
arm, task, run, wall, *pairs = sys.argv[1:]
nums = [int(x) for x in pairs]
agents = [{"tokens": nums[i], "tool_calls": nums[i + 1]} for i in range(0, len(nums), 2)]
data = json.loads(path.read_text()) if path.exists() else {}
data.setdefault(arm, {}).setdefault(task, {})[run] = {
    "wall_seconds": float(wall),
    "reported_tokens": sum(a["tokens"] for a in agents),
    "reported_tool_calls": sum(a["tool_calls"] for a in agents),
    "agents": agents,
}
path.write_text(json.dumps(data, indent=2) + "\n")
print(f"recorded {arm}/{task}/{run}: {len(agents)} agent(s), {sum(a['tokens'] for a in agents)} tokens, {wall}s")
