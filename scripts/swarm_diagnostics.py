#!/usr/bin/env python3
"""
swarm_diagnostics.py — Evidence-Cited Session & Swarm Diagnostics Engine

Inspired by obra/superpowers `diagnosing-superpowers` and `systematic-debugging`.
Safely streams Antigravity conversation transcripts (`transcript.jsonl`) and
`.swarm/` state (`goal_loop.json`, `ledger.md`, `deferred_minor_ledger.md`,
`immortal_state.json`) to produce deterministic, `path:line` and `step_index`
cited diagnostics across the 7 Superpowers Diagnostic Dimensions:

  1. skill-timeline   — Which SKILL.md files were viewed and at which step_index/line
  2. subagent-spawns  — invoke_subagent calls, roles, child transcripts & completion status
  3. plan-adherence   — Tasks in .swarm/goal_loop.json vs actual file edits & outcome runs
  5. repeated-work    — Files edited >= 3 times, viewed >= 3 times, or commands re-run
  5. stumbles         — Steps with status == "ERROR" or non-zero command exit codes
  6. loop-rulings     — Tasks hitting Round 4-5 escalation or Round 5 `Ruling:` breakers
  7. cost-and-time    — Step counts, tool breakdown, wall-clock duration, & top bottlenecks

Core Principle: Every finding cites `path:line` and `step_index`. No citation, no finding.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


DEFAULT_BRAIN_DIR = Path.home() / ".gemini" / "antigravity" / "brain"

EXIT_CODE_RE = re.compile(r"The command exited with code (\d+)\.")
SUBAGENT_BLOCK_RE = re.compile(
    r'\{\s*"conversationId"\s*:\s*"([^"]+)"\s*,\s*"logAbsoluteUri"\s*:\s*"([^"]+)"',
    re.MULTILINE,
)


def parse_iso_timestamp(ts: str | None) -> datetime | None:
    if not ts or not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def safe_json_val(val: Any) -> Any:
    """Decode nested JSON-encoded string values inside Antigravity tool_calls['args']."""
    if not isinstance(val, str):
        return val
    stripped = val.strip()
    if (
        (stripped.startswith('"') and stripped.endswith('"'))
        or (stripped.startswith("[") and stripped.endswith("]"))
        or (stripped.startswith("{") and stripped.endswith("}"))
    ):
        try:
            return json.loads(stripped)
        except Exception:
            if stripped.startswith('"') and stripped.endswith('"') and len(stripped) >= 2:
                return stripped[1:-1]
    return val


def read_specific_line(filepath: Path, target_line_no: int) -> dict[str, Any] | None:
    """Read a single 1-indexed line from transcript_full.jsonl when truncated_fields is present."""
    if not filepath.is_file():
        return None
    try:
        with filepath.open("r", encoding="utf-8", errors="replace") as f:
            for idx, raw in enumerate(f, 1):
                if idx == target_line_no:
                    return json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        _ = str(exc)
    return None


def discover_conversation(brain_dir: Path, conversation_id: str | None) -> tuple[str, Path]:
    if conversation_id:
        candidate = brain_dir / conversation_id / ".system_generated" / "logs" / "transcript.jsonl"
        if candidate.is_file():
            return conversation_id, candidate
        # Allow passing a direct path to transcript.jsonl or conversation folder
        direct = Path(conversation_id)
        if direct.is_file():
            return direct.parent.parent.parent.name, direct
        if (direct / ".system_generated" / "logs" / "transcript.jsonl").is_file():
            return direct.name, direct / ".system_generated" / "logs" / "transcript.jsonl"
        raise FileNotFoundError(
            f"Transcript not found for conversation '{conversation_id}' under {brain_dir}"
        )

    candidates: list[tuple[float, str, Path]] = []
    if brain_dir.is_dir():
        for child in brain_dir.iterdir():
            if not child.is_dir():
                continue
            tpath = child / ".system_generated" / "logs" / "transcript.jsonl"
            if tpath.is_file():
                try:
                    mtime = tpath.stat().st_mtime
                    candidates.append((mtime, child.name, tpath))
                except OSError:
                    continue

    if not candidates:
        raise FileNotFoundError(f"No conversation transcripts found under {brain_dir}")
    candidates.sort(key=lambda x: x[0], reverse=True)
    _, cid, path = candidates[0]
    return cid, path


def inspect_child_transcript(transcript_path: Path) -> dict[str, Any]:
    """Stream a spawned subagent's transcript.jsonl safely to summarize its execution."""
    info: dict[str, Any] = {
        "transcript_path": str(transcript_path),
        "exists": transcript_path.is_file(),
        "total_lines": 0,
        "last_step_index": None,
        "last_status": None,
        "last_type": None,
        "sent_message": False,
        "send_message_citations": [],
        "error_citations": [],
        "files_edited": [],
        "state": "MISSING_TRANSCRIPT",
    }
    if not transcript_path.is_file():
        return info

    edited_set: list[str] = []
    try:
        with transcript_path.open("r", encoding="utf-8", errors="replace") as f:
            for line_no, raw in enumerate(f, 1):
                raw = raw.strip()
                if not raw:
                    continue
                info["total_lines"] = line_no
                try:
                    obj = json.loads(raw)
                except Exception:
                    continue
                step_idx = obj.get("step_index")
                status = obj.get("status")
                stype = obj.get("type")
                info["last_step_index"] = step_idx
                info["last_status"] = status
                info["last_type"] = stype

                if status == "ERROR":
                    info["error_citations"].append(
                        f"{transcript_path}:{line_no} (step_index={step_idx})"
                    )

                tcs = obj.get("tool_calls") or []
                if isinstance(tcs, list):
                    for tc in tcs:
                        if not isinstance(tc, dict):
                            continue
                        tname = tc.get("name") or ""
                        args = tc.get("args") or tc.get("arguments") or {}
                        if isinstance(args, str):
                            args = safe_json_val(args)
                        if not isinstance(args, dict):
                            args = {}
                        if tname == "send_message":
                            info["sent_message"] = True
                            info["send_message_citations"].append(
                                f"{transcript_path}:{line_no} (step_index={step_idx})"
                            )
                        elif tname in (
                            "write_to_file",
                            "replace_file_content",
                            "multi_replace_file_content",
                        ):
                            target = safe_json_val(
                                args.get("TargetFile") or args.get("AbsolutePath") or ""
                            )
                            if isinstance(target, str) and target and target not in edited_set:
                                edited_set.append(target)
    except Exception as exc:
        info["state"] = f"READ_ERROR ({exc})"
        return info

    info["files_edited"] = edited_set
    if info["sent_message"]:
        info["state"] = "COMPLETED_REPORTED"
    elif info["last_status"] == "ERROR":
        info["state"] = "ERRORED"
    elif info["total_lines"] > 0:
        info["state"] = "ACTIVE_OR_IDLE_NO_REPORT"
    else:
        info["state"] = "EMPTY"
    return info


def analyze_transcript_and_swarm(
    conversation_id: str,
    transcript_path: Path,
    project_dir: Path,
) -> dict[str, Any]:
    full_transcript_path = transcript_path.parent / "transcript_full.jsonl"
    short_tname = transcript_path.name  # transcript.jsonl

    skill_timeline: list[dict[str, Any]] = []
    subagent_spawns: list[dict[str, Any]] = []
    file_edits: dict[str, list[dict[str, Any]]] = defaultdict(list)
    file_views: dict[str, list[dict[str, Any]]] = defaultdict(list)
    commands_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stumbles: list[dict[str, Any]] = []

    step_records: list[dict[str, Any]] = []
    tool_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()

    pending_subagent_batches: list[dict[str, Any]] = []
    last_planner_tools_by_step: dict[int, list[dict[str, Any]]] = {}
    most_recent_planner_step: dict[str, Any] | None = None

    total_bytes = 0
    total_lines = 0

    with transcript_path.open("r", encoding="utf-8", errors="replace") as f:
        for line_no, raw_line in enumerate(f, 1):
            total_lines = line_no
            line_bytes = len(raw_line.encode("utf-8", errors="replace"))
            total_bytes += line_bytes
            raw_stripped = raw_line.strip()
            if not raw_stripped:
                continue

            try:
                obj = json.loads(raw_stripped)
            except Exception as exc:
                stumbles.append(
                    {
                        "citation": f"{transcript_path}:{line_no}",
                        "short_citation": f"{short_tname}:{line_no}",
                        "line_number": line_no,
                        "step_index": None,
                        "created_at": None,
                        "kind": "JSON_PARSE_ERROR",
                        "tool": None,
                        "summary": f"Malformed JSON line: {exc}",
                    }
                )
                continue

            step_idx = obj.get("step_index")
            stype = str(obj.get("type") or "UNKNOWN")
            status = str(obj.get("status") or "UNKNOWN")
            created_at = obj.get("created_at")
            truncated_fields = obj.get("truncated_fields") or []

            type_counts[stype] += 1
            status_counts[status] += 1

            step_records.append(
                {
                    "line_number": line_no,
                    "step_index": step_idx,
                    "type": stype,
                    "status": status,
                    "created_at": created_at,
                    "byte_size": line_bytes,
                    "tools": [],
                }
            )

            tcs = obj.get("tool_calls") or []
            # If tool_calls was truncated on an invoke_subagent or edit step, read full line
            if (
                "tool_calls" in truncated_fields
                and isinstance(tcs, list)
                and any(
                    isinstance(tc, dict)
                    and tc.get("name")
                    in (
                        "invoke_subagent",
                        "write_to_file",
                        "replace_file_content",
                        "multi_replace_file_content",
                    )
                    for tc in tcs
                )
            ):
                full_obj = read_specific_line(full_transcript_path, line_no)
                if full_obj and isinstance(full_obj.get("tool_calls"), list):
                    tcs = full_obj["tool_calls"]

            parsed_tools_for_step: list[dict[str, Any]] = []
            if isinstance(tcs, list):
                for tc in tcs:
                    if not isinstance(tc, dict):
                        continue
                    tname = str(tc.get("name") or "unknown_tool")
                    tool_counts[tname] += 1
                    step_records[-1]["tools"].append(tname)

                    raw_args = tc.get("args") or tc.get("arguments") or {}
                    if isinstance(raw_args, str):
                        raw_args = safe_json_val(raw_args)
                    if not isinstance(raw_args, dict):
                        raw_args = {}
                    args = {k: safe_json_val(v) for k, v in raw_args.items()}

                    parsed_tools_for_step.append(
                        {
                            "name": tname,
                            "args": args,
                            "line_number": line_no,
                            "step_index": step_idx,
                        }
                    )

                    # Dimension 1: skill-timeline & Dimension 4: file views
                    if tname == "view_file":
                        apath = str(args.get("AbsolutePath") or "")
                        if apath:
                            file_views[apath].append(
                                {
                                    "line_number": line_no,
                                    "step_index": step_idx,
                                    "created_at": created_at,
                                    "citation": f"{transcript_path}:{line_no}",
                                    "short_citation": f"{short_tname}:{line_no}",
                                }
                            )
                            if apath.endswith("SKILL.md") or "/skills/" in apath:
                                parts = Path(apath).parts
                                skill_name = Path(apath).parent.name if apath.endswith("SKILL.md") else Path(apath).name
                                if "skills" in parts:
                                    sidx = parts.index("skills")
                                    if sidx + 1 < len(parts):
                                        skill_name = parts[sidx + 1]
                                skill_timeline.append(
                                    {
                                        "skill_name": skill_name,
                                        "skill_path": apath,
                                        "line_number": line_no,
                                        "step_index": step_idx,
                                        "created_at": created_at,
                                        "citation": f"{transcript_path}:{line_no}",
                                        "short_citation": f"{short_tname}:{line_no}",
                                    }
                                )

                    # Dimension 3 & 4: file edits
                    elif tname in (
                        "write_to_file",
                        "replace_file_content",
                        "multi_replace_file_content",
                    ):
                        tfile = str(args.get("TargetFile") or args.get("AbsolutePath") or "")
                        if tfile:
                            file_edits[tfile].append(
                                {
                                    "tool": tname,
                                    "line_number": line_no,
                                    "step_index": step_idx,
                                    "created_at": created_at,
                                    "citation": f"{transcript_path}:{line_no}",
                                    "short_citation": f"{short_tname}:{line_no}",
                                }
                            )

                    # Dimension 4: repeated commands
                    elif tname == "run_command":
                        cmdline = str(args.get("CommandLine") or "").strip()
                        if cmdline:
                            commands_run[cmdline].append(
                                {
                                    "line_number": line_no,
                                    "step_index": step_idx,
                                    "created_at": created_at,
                                    "citation": f"{transcript_path}:{line_no}",
                                    "short_citation": f"{short_tname}:{line_no}",
                                }
                            )

                    # Dimension 2: subagent-spawns
                    elif tname == "invoke_subagent":
                        sub_list = args.get("Subagents")
                        if isinstance(sub_list, str):
                            sub_list = safe_json_val(sub_list)
                        entries: list[dict[str, Any]] = []
                        if isinstance(sub_list, list):
                            for item in sub_list:
                                if isinstance(item, dict):
                                    entries.append(
                                        {
                                            "role": item.get("Role") or "unknown",
                                            "type_name": item.get("TypeName") or "self",
                                            "workspace": item.get("Workspace") or "inherit",
                                            "model": item.get("Model") or "inherit",
                                            "prompt_chars": len(str(item.get("Prompt") or "")),
                                        }
                                    )
                        batch_record = {
                            "invoke_line_number": line_no,
                            "invoke_step_index": step_idx,
                            "created_at": created_at,
                            "citation": f"{transcript_path}:{line_no}",
                            "short_citation": f"{short_tname}:{line_no}",
                            "requested_subagents": entries,
                            "spawned_instances": [],
                        }
                        subagent_spawns.append(batch_record)
                        pending_subagent_batches.append(batch_record)

            if parsed_tools_for_step:
                if isinstance(step_idx, int):
                    last_planner_tools_by_step[step_idx] = parsed_tools_for_step
                most_recent_planner_step = {
                    "line_number": line_no,
                    "step_index": step_idx,
                    "tools": parsed_tools_for_step,
                }

            # Match subagent creation output in GENERIC steps
            content_str = str(obj.get("content") or "")
            if "Created the following subagents:" in content_str:
                if "content" in truncated_fields:
                    full_obj = read_specific_line(full_transcript_path, line_no)
                    if full_obj and isinstance(full_obj.get("content"), str):
                        content_str = full_obj["content"]
                matches = SUBAGENT_BLOCK_RE.findall(content_str)
                target_batch = pending_subagent_batches.pop(0) if pending_subagent_batches else None
                for idx, (cid, log_uri) in enumerate(matches):
                    log_path_str = log_uri.replace("file://", "")
                    child_info = inspect_child_transcript(Path(log_path_str))
                    req_meta = (
                        target_batch["requested_subagents"][idx]
                        if target_batch and idx < len(target_batch["requested_subagents"])
                        else {}
                    )
                    instance = {
                        "conversation_id": cid,
                        "role": req_meta.get("role", f"subagent_{idx+1}"),
                        "type_name": req_meta.get("type_name", "unknown"),
                        "workspace": req_meta.get("workspace", "inherit"),
                        "result_line_number": line_no,
                        "result_step_index": step_idx,
                        "result_citation": f"{transcript_path}:{line_no}",
                        "child_summary": child_info,
                    }
                    if target_batch is not None:
                        target_batch["spawned_instances"].append(instance)
                    else:
                        subagent_spawns.append(
                            {
                                "invoke_line_number": line_no,
                                "invoke_step_index": step_idx,
                                "created_at": created_at,
                                "citation": f"{transcript_path}:{line_no}",
                                "short_citation": f"{short_tname}:{line_no}",
                                "requested_subagents": [req_meta] if req_meta else [],
                                "spawned_instances": [instance],
                            }
                        )

            # Dimension 5: stumbles (status == "ERROR" or non-zero command exit code)
            if status == "ERROR":
                snippet = content_str.strip().splitlines()[0][:160] if content_str.strip() else "Step status == ERROR"
                stumbles.append(
                    {
                        "citation": f"{transcript_path}:{line_no}",
                        "short_citation": f"{short_tname}:{line_no}",
                        "line_number": line_no,
                        "step_index": step_idx,
                        "created_at": created_at,
                        "kind": "STEP_STATUS_ERROR",
                        "exit_code": None,
                        "preceding_tool": (
                            most_recent_planner_step["tools"][0]["name"]
                            if most_recent_planner_step and most_recent_planner_step.get("tools")
                            else None
                        ),
                        "preceding_citation": (
                            f"{short_tname}:{most_recent_planner_step['line_number']} (step_index={most_recent_planner_step['step_index']})"
                            if most_recent_planner_step
                            else None
                        ),
                        "summary": snippet,
                    }
                )
            elif stype == "GENERIC" and content_str:
                m_exit = EXIT_CODE_RE.search(content_str)
                if m_exit and int(m_exit.group(1)) != 0:
                    exit_code = int(m_exit.group(1))
                    # Extract first error line after "Output:"
                    out_idx = content_str.find("Output:")
                    err_preview = ""
                    if out_idx != -1:
                        err_lines = [
                            ln.strip()
                            for ln in content_str[out_idx + 7 :].splitlines()
                            if ln.strip()
                        ]
                        err_preview = " | ".join(err_lines[:2])[:180]
                    preceding = None
                    if isinstance(step_idx, int) and (step_idx - 1) in last_planner_tools_by_step:
                        ptools = last_planner_tools_by_step[step_idx - 1]
                        preceding = ptools[0] if ptools else None
                    elif most_recent_planner_step and most_recent_planner_step.get("tools"):
                        preceding = most_recent_planner_step["tools"][0]

                    stumbles.append(
                        {
                            "citation": f"{transcript_path}:{line_no}",
                            "short_citation": f"{short_tname}:{line_no}",
                            "line_number": line_no,
                            "step_index": step_idx,
                            "created_at": created_at,
                            "kind": "NON_ZERO_EXIT_CODE",
                            "exit_code": exit_code,
                            "preceding_tool": preceding["name"] if preceding else "run_command",
                            "preceding_citation": (
                                f"{short_tname}:{preceding['line_number']} (step_index={preceding['step_index']})"
                                if preceding
                                else None
                            ),
                            "summary": err_preview or f"Command exited with code {exit_code}",
                        }
                    )

    # Dimension 3: plan-adherence (.swarm/goal_loop.json vs actual edits)
    swarm_dir = project_dir / ".swarm"
    goal_loop_path = swarm_dir / "goal_loop.json"
    plan_adherence: dict[str, Any] = {
        "goal_loop_path": str(goal_loop_path),
        "goal_loop_exists": goal_loop_path.is_file(),
        "overall_goal": None,
        "outcome_cmd": None,
        "outcome_cmd_executed": False,
        "outcome_cmd_citations": [],
        "tasks_total": 0,
        "tasks_by_status": {},
        "task_details": [],
        "edited_files_count": len(file_edits),
        "edited_files": [
            {
                "file": fpath,
                "edit_count": len(edits),
                "citations": [e["short_citation"] + f" (step {e['step_index']})" for e in edits],
            }
            for fpath, edits in sorted(file_edits.items(), key=lambda x: (-len(x[1]), x[0]))
        ],
    }

    if goal_loop_path.is_file():
        try:
            gdata = json.loads(goal_loop_path.read_text(encoding="utf-8", errors="replace"))
            plan_adherence["overall_goal"] = gdata.get("overall_goal") or gdata.get("goal")
            outcome_cmd = gdata.get("outcome_cmd") or gdata.get("outcome_command")
            plan_adherence["outcome_cmd"] = outcome_cmd
            if outcome_cmd and isinstance(outcome_cmd, str):
                for cmd_str, runs in commands_run.items():
                    if outcome_cmd in cmd_str:
                        plan_adherence["outcome_cmd_executed"] = True
                        plan_adherence["outcome_cmd_citations"].extend(
                            [r["short_citation"] + f" (step {r['step_index']})" for r in runs]
                        )
            tasks = gdata.get("tasks") or []
            status_counter: Counter[str] = Counter()
            if isinstance(tasks, list):
                plan_adherence["tasks_total"] = len(tasks)
                for t in tasks:
                    if not isinstance(t, dict):
                        continue
                    tstatus = str(t.get("status") or "unknown")
                    status_counter[tstatus] += 1
                    plan_adherence["task_details"].append(
                        {
                            "id": t.get("id") or t.get("task_id"),
                            "title": t.get("title") or t.get("name"),
                            "status": tstatus,
                            "rounds": t.get("rounds") or t.get("attempts") or 0,
                        }
                    )
            plan_adherence["tasks_by_status"] = dict(status_counter)
        except Exception as exc:
            plan_adherence["parse_error"] = str(exc)

    # Dimension 4: repeated-work (files edited >= 3 times, viewed >= 3 times, commands >= 2 times)
    repeated_edits = [
        {
            "file": fpath,
            "count": len(edits),
            "citations": [f"{e['short_citation']} (step_index={e['step_index']})" for e in edits],
        }
        for fpath, edits in sorted(file_edits.items(), key=lambda x: (-len(x[1]), x[0]))
        if len(edits) >= 3
    ]
    repeated_views = [
        {
            "file": fpath,
            "count": len(views),
            "citations": [f"{v['short_citation']} (step_index={v['step_index']})" for v in views],
        }
        for fpath, views in sorted(file_views.items(), key=lambda x: (-len(x[1]), x[0]))
        if len(views) >= 3
    ]
    repeated_commands = [
        {
            "command": cmd[:140],
            "count": len(runs),
            "citations": [f"{r['short_citation']} (step_index={r['step_index']})" for r in runs],
        }
        for cmd, runs in sorted(commands_run.items(), key=lambda x: (-len(x[1]), x[0]))
        if len(runs) >= 2
    ]

    # Dimension 6: loop-rulings (.swarm/ledger.md, deferred_minor_ledger.md, immortal_state.json)
    ledger_path = swarm_dir / "ledger.md"
    deferred_path = swarm_dir / "deferred_minor_ledger.md"
    immortal_path = swarm_dir / "immortal_state.json"

    rulings_found: list[dict[str, Any]] = []
    escalated_rounds: list[dict[str, Any]] = []
    deferred_findings: list[dict[str, Any]] = []

    if ledger_path.is_file():
        try:
            for lno, line in enumerate(
                ledger_path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if "Ruling:" in line or "[Round 5 Breaker]" in line:
                    rulings_found.append(
                        {
                            "citation": f"{ledger_path}:{lno}",
                            "line_number": lno,
                            "content": line.strip(),
                        }
                    )
                elif re.search(r"Round\s+[45]\b|ESCALAT", line, re.IGNORECASE):
                    escalated_rounds.append(
                        {
                            "citation": f"{ledger_path}:{lno}",
                            "line_number": lno,
                            "content": line.strip(),
                        }
                    )
        except OSError as exc:
            rulings.append({"citation": str(ledger_path), "line_number": 0, "content": f"Read error: {exc}"})

    if deferred_path.is_file():
        try:
            for lno, line in enumerate(
                deferred_path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                stripped = line.strip()
                if stripped.startswith("- ") or stripped.startswith("|"):
                    deferred_findings.append(
                        {
                            "citation": f"{deferred_path}:{lno}",
                            "line_number": lno,
                            "content": stripped[:160],
                        }
                    )
        except OSError as exc:
            deferred_findings.append({"citation": str(deferred_path), "line_number": 0, "content": f"Read error: {exc}"})

    immortal_summary: dict[str, Any] = {"exists": immortal_path.is_file()}
    if immortal_path.is_file():
        try:
            idata = json.loads(immortal_path.read_text(encoding="utf-8", errors="replace"))
            subagents_map = idata.get("subagents") or {}
            revivals_total = 0
            high_round_agents: list[dict[str, Any]] = []
            if isinstance(subagents_map, dict):
                for cid, srec in subagents_map.items():
                    if not isinstance(srec, dict):
                        continue
                    rev = int(srec.get("revivals") or 0)
                    revivals_total += rev
                    reviews = srec.get("reviews") or []
                    rcount = len(reviews) if isinstance(reviews, list) else int(srec.get("round") or 0)
                    if rcount >= 4:
                        high_round_agents.append(
                            {
                                "conversation_id": cid,
                                "role": srec.get("role"),
                                "rounds": rcount,
                                "revivals": rev,
                            }
                        )
            immortal_summary.update(
                {
                    "registered_subagents": len(subagents_map) if isinstance(subagents_map, dict) else 0,
                    "total_revivals": revivals_total,
                    "round_4_5_escalated_agents": high_round_agents,
                }
            )
        except Exception as exc:
            immortal_summary["parse_error"] = str(exc)

    # Dimension 7: cost-and-time (step counts, wall-clock duration, top bottlenecks)
    timestamps_with_rec: list[tuple[datetime, dict[str, Any]]] = []
    for rec in step_records:
        dt = parse_iso_timestamp(rec.get("created_at"))
        if dt is not None:
            timestamps_with_rec.append((dt, rec))

    wall_clock_total_sec = 0.0
    active_compute_sec = 0.0
    bottlenecks: list[dict[str, Any]] = []

    if len(timestamps_with_rec) >= 2:
        first_dt = timestamps_with_rec[0][0]
        last_dt = timestamps_with_rec[-1][0]
        wall_clock_total_sec = max(0.0, (last_dt - first_dt).total_seconds())

        for idx in range(1, len(timestamps_with_rec)):
            prev_dt, prev_rec = timestamps_with_rec[idx - 1]
            curr_dt, curr_rec = timestamps_with_rec[idx]
            delta = (curr_dt - prev_dt).total_seconds()
            if delta < 0:
                continue
            is_user_idle_gap = curr_rec["type"] == "USER_INPUT" and delta > 60.0
            if not is_user_idle_gap:
                active_compute_sec += delta
            bottlenecks.append(
                {
                    "duration_seconds": round(delta, 2),
                    "is_user_idle_gap": is_user_idle_gap,
                    "from_citation": f"{short_tname}:{prev_rec['line_number']} (step_index={prev_rec['step_index']}, type={prev_rec['type']})",
                    "to_citation": f"{short_tname}:{curr_rec['line_number']} (step_index={curr_rec['step_index']}, type={curr_rec['type']})",
                    "tools_in_window": prev_rec["tools"] or curr_rec["tools"],
                }
            )

    tool_bottlenecks = [b for b in bottlenecks if not b["is_user_idle_gap"]]
    tool_bottlenecks.sort(key=lambda x: x["duration_seconds"], reverse=True)
    all_bottlenecks_sorted = sorted(bottlenecks, key=lambda x: x["duration_seconds"], reverse=True)

    largest_lines = sorted(step_records, key=lambda r: r["byte_size"], reverse=True)[:5]

    return {
        "conversation_id": conversation_id,
        "transcript_path": str(transcript_path),
        "project_dir": str(project_dir.resolve()),
        "generated_at": datetime.now().astimezone().isoformat(),
        "dimensions": {
            "1_skill_timeline": {
                "skills_viewed_count": len(skill_timeline),
                "unique_skills": sorted({s["skill_name"] for s in skill_timeline}),
                "events": skill_timeline,
            },
            "2_subagent_spawns": {
                "invoke_batches_count": len(subagent_spawns),
                "total_subagents_spawned": sum(
                    len(b["spawned_instances"]) or len(b["requested_subagents"])
                    for b in subagent_spawns
                ),
                "batches": subagent_spawns,
            },
            "3_plan_adherence": plan_adherence,
            "4_repeated_work": {
                "files_edited_3plus_count": len(repeated_edits),
                "files_edited_3plus": repeated_edits,
                "files_viewed_3plus_count": len(repeated_views),
                "files_viewed_3plus": repeated_views,
                "commands_rerun_2plus_count": len(repeated_commands),
                "commands_rerun_2plus": repeated_commands,
            },
            "5_stumbles": {
                "stumble_count": len(stumbles),
                "events": stumbles,
            },
            "6_loop_rulings": {
                "ledger_path": str(ledger_path),
                "ledger_exists": ledger_path.is_file(),
                "ruling_breakers_count": len(rulings_found),
                "ruling_breakers": rulings_found,
                "round_4_5_escalations_count": len(escalated_rounds),
                "round_4_5_escalations": escalated_rounds,
                "deferred_minor_count": len(deferred_findings),
                "deferred_minor_items": deferred_findings[:15],
                "immortal_state": immortal_summary,
            },
            "7_cost_and_time": {
                "total_transcript_lines": total_lines,
                "total_transcript_bytes": total_bytes,
                "step_types": dict(type_counts),
                "step_statuses": dict(status_counts),
                "tool_call_counts": dict(tool_counts.most_common()),
                "wall_clock_total_seconds": round(wall_clock_total_sec, 2),
                "active_turn_compute_seconds": round(active_compute_sec, 2),
                "top_active_bottlenecks": tool_bottlenecks[:5],
                "top_overall_gaps": all_bottlenecks_sorted[:5],
                "largest_transcript_lines": [
                    {
                        "citation": f"{short_tname}:{r['line_number']} (step_index={r['step_index']})",
                        "type": r["type"],
                        "byte_size": r["byte_size"],
                        "tools": r["tools"],
                    }
                    for r in largest_lines
                ],
            },
        },
    }


def render_markdown_report(data: dict[str, Any]) -> str:
    dims = data["dimensions"]
    d1 = dims["1_skill_timeline"]
    d2 = dims["2_subagent_spawns"]
    d3 = dims["3_plan_adherence"]
    d4 = dims["4_repeated_work"]
    d5 = dims["5_stumbles"]
    d6 = dims["6_loop_rulings"]
    d7 = dims["7_cost_and_time"]

    lines: list[str] = [
        f"# Swarm Session Diagnostic Report (`{data['conversation_id']}`)",
        "",
        f"- **Transcript Path:** `{data['transcript_path']}`",
        f"- **Project Directory:** `{data['project_dir']}`",
        f"- **Generated At:** `{data['generated_at']}`",
        f"- **Evidence Standard:** Every finding cites `transcript.jsonl:<line>` (`step_index=<N>`) or `.swarm/<file>:<line>`.",
        "",
        "---",
        "",
        "## 1. Skill Timeline (`skill-timeline`)",
        f"- **Total `SKILL.md` Reads:** `{d1['skills_viewed_count']}` across `{len(d1['unique_skills'])}` unique skills",
        "",
    ]

    if d1["events"]:
        lines.append("| # | Skill Name | Citation (`path:line`) | `step_index` | Timestamp | Full Path |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for i, ev in enumerate(d1["events"], 1):
            lines.append(
                f"| {i} | `{ev['skill_name']}` | `{ev['short_citation']}` | `{ev['step_index']}` | `{ev['created_at']}` | `{ev['skill_path']}` |"
            )
    else:
        lines.append("- *No `SKILL.md` view_file calls recorded in this transcript.*")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 2. Subagent Spawns (`subagent-spawns`)",
            f"- **Invoke Batches:** `{d2['invoke_batches_count']}` | **Total Subagents Spawned:** `{d2['total_subagents_spawned']}`",
            "",
        ]
    )

    if d2["batches"]:
        lines.append(
            "| Batch | Invoke Citation | Role | Workspace | Child Conversation ID | Child Lines | Sent Message (`send_message`) | State |"
        )
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for b_idx, batch in enumerate(d2["batches"], 1):
            cite = f"{batch['short_citation']} (step {batch['invoke_step_index']})"
            if batch["spawned_instances"]:
                for inst in batch["spawned_instances"]:
                    csum = inst["child_summary"]
                    sm_cite = (
                        ", ".join(csum["send_message_citations"])
                        if csum["send_message_citations"]
                        else "No"
                    )
                    lines.append(
                        f"| {b_idx} | `{cite}` | `{inst['role']}` | `{inst['workspace']}` | `{inst['conversation_id']}` | `{csum['total_lines']}` | `{sm_cite}` | `{csum['state']}` |"
                    )
            else:
                for req in batch["requested_subagents"]:
                    lines.append(
                        f"| {b_idx} | `{cite}` | `{req.get('role')}` | `{req.get('workspace')}` | *(pending/unmatched)* | `0` | `No` | `SPAWN_REQUESTED` |"
                    )
    else:
        lines.append("- *No `invoke_subagent` calls recorded in this transcript.*")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 3. Plan Adherence (`plan-adherence`)",
            f"- **`.swarm/goal_loop.json` Present:** `{d3['goal_loop_exists']}` (`{d3['goal_loop_path']}`)",
            f"- **Overall Goal:** `{d3['overall_goal'] or 'N/A'}`",
            f"- **Outcome Command (`--outcome-cmd`):** `{d3['outcome_cmd'] or 'N/A'}` (Executed: `{d3['outcome_cmd_executed']}`)",
            f"- **Files Edited in Transcript:** `{d3['edited_files_count']}`",
            "",
        ]
    )

    if d3["edited_files"]:
        lines.append("| File Path | Edit Count | Citations (`transcript.jsonl:<line>`) |")
        lines.append("| :--- | :--- | :--- |")
        for ef in d3["edited_files"][:20]:
            lines.append(f"| `{ef['file']}` | `{ef['edit_count']}` | {', '.join(f'`{c}`' for c in ef['citations'])} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 4. Repeated Work (`repeated-work`)",
            f"- **Files Edited $\\ge 3$ Times:** `{d4['files_edited_3plus_count']}`",
            f"- **Files Viewed $\\ge 3$ Times:** `{d4['files_viewed_3plus_count']}`",
            f"- **Commands Re-Run $\\ge 2$ Times:** `{d4['commands_rerun_2plus_count']}`",
            "",
        ]
    )

    if d4["files_edited_3plus"]:
        lines.append("### Files Edited $\\ge 3$ Times")
        for item in d4["files_edited_3plus"]:
            lines.append(f"- `{item['file']}` (**{item['count']}x**): {', '.join(f'`{c}`' for c in item['citations'])}")
    if d4["files_viewed_3plus"]:
        lines.append("### Files Viewed $\\ge 3$ Times")
        for item in d4["files_viewed_3plus"][:10]:
            lines.append(f"- `{item['file']}` (**{item['count']}x**): {', '.join(f'`{c}`' for c in item['citations'])}")
    if d4["commands_rerun_2plus"]:
        lines.append("### Commands Executed $\\ge 2$ Times")
        for item in d4["commands_rerun_2plus"][:10]:
            lines.append(f"- `{item['command']}` (**{item['count']}x**): {', '.join(f'`{c}`' for c in item['citations'])}")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 5. Stumbles & Tool Errors (`stumbles`)",
            f"- **Total Stumbles (`status == ERROR` or Non-Zero Exit Code):** `{d5['stumble_count']}`",
            "",
        ]
    )

    if d5["events"]:
        lines.append("| # | Citation (`path:line`) | `step_index` | Kind | Preceding Tool | Exit Code | Error Summary |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for idx, st in enumerate(d5["events"], 1):
            lines.append(
                f"| {idx} | `{st['short_citation']}` | `{st['step_index']}` | `{st['kind']}` | `{st.get('preceding_tool') or 'N/A'}` (`{st.get('preceding_citation') or 'N/A'}`) | `{st.get('exit_code') if st.get('exit_code') is not None else 'N/A'}` | {st['summary'].replace('|', '/')} |"
            )
    else:
        lines.append("- *Zero stumbles or non-zero exit codes detected.*")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 6. Loop Escalations & Rulings (`loop-rulings`)",
            f"- **`.swarm/ledger.md` Present:** `{d6['ledger_exists']}` | **Round 5 `Ruling:` Breakers:** `{d6['ruling_breakers_count']}` | **Round 4–5 Escalations:** `{d6['round_4_5_escalations_count']}`",
            f"- **Deferred Minor Ledger Entries:** `{d6['deferred_minor_count']}`",
            "",
        ]
    )

    if d6["ruling_breakers"]:
        for r in d6["ruling_breakers"]:
            lines.append(f"- **Breaker Cited (`{r['citation']}`):** `{r['content']}`")
    if d6["round_4_5_escalations"]:
        for esc in d6["round_4_5_escalations"]:
            lines.append(f"- **Escalation Cited (`{esc['citation']}`):** `{esc['content']}`")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 7. Cost, Step Counts & Bottlenecks (`cost-and-time`)",
            f"- **Total Transcript Lines / Steps:** `{d7['total_transcript_lines']}` (`{d7['total_transcript_bytes']:,}` bytes)",
            f"- **Step Types:** `{json.dumps(d7['step_types'])}`",
            f"- **Step Statuses:** `{json.dumps(d7['step_statuses'])}`",
            f"- **Tool Call Counts:** `{json.dumps(d7['tool_call_counts'])}`",
            f"- **Total Wall-Clock Session Span:** `{d7['wall_clock_total_seconds']}s` | **Active Compute Time (Excl. User Wait > 60s):** `{d7['active_turn_compute_seconds']}s`",
            "",
            "### Top 5 Active Compute / Tool Bottlenecks",
            "| Rank | Duration (`s`) | From (`path:line`) | To (`path:line`) | Tools Involved |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
    )

    for rank, b in enumerate(d7["top_active_bottlenecks"], 1):
        tlist = ", ".join(b["tools_in_window"]) if b["tools_in_window"] else "model_thinking / stream"
        lines.append(
            f"| {rank} | `{b['duration_seconds']}s` | `{b['from_citation']}` | `{b['to_citation']}` | `{tlist}` |"
        )

    lines.extend(
        [
            "",
            "### Top 5 Largest Transcript Lines (Context-Bloat Audit)",
            "| Rank | Citation (`path:line`) | Step Type | Size (Bytes) | Tools |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for rank, lrec in enumerate(d7["largest_transcript_lines"], 1):
        lines.append(
            f"| {rank} | `{lrec['citation']}` | `{lrec['type']}` | `{lrec['byte_size']:,}` | `{', '.join(lrec['tools']) or 'N/A'}` |"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evidence-cited Antigravity conversation & .swarm/ session diagnostics across 7 dimensions."
    )
    parser.add_argument(
        "--conversation-id",
        default=None,
        help="Conversation ID or path to transcript.jsonl (defaults to most recent conversation in --brain-dir).",
    )
    parser.add_argument(
        "--brain-dir",
        default=str(DEFAULT_BRAIN_DIR),
        help=f"Antigravity brain directory (default: {DEFAULT_BRAIN_DIR}).",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="Project workspace directory containing .swarm/ state (default: .).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional output path for the Markdown diagnostic report (e.g. .swarm/diagnostics_report.md).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit full diagnostic metrics as JSON to stdout.",
    )
    args = parser.parse_args()

    try:
        cid, transcript_path = discover_conversation(Path(args.brain_dir), args.conversation_id)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    report_data = analyze_transcript_and_swarm(
        conversation_id=cid,
        transcript_path=transcript_path,
        project_dir=Path(args.project_dir),
    )

    md_report = render_markdown_report(report_data)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md_report, encoding="utf-8")

    if args.json:
        print(json.dumps(report_data, indent=2))
    else:
        print(md_report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
