#!/usr/bin/env python3
"""Hierarchical Goal-Loop Execution, Deterministic Invariant Audit & Two-Verdict Gate Engine.

Powers `/goal-loop`, `/discriminator-gate`, `/invoke-swarm`, `/epoch-planner`, and `/product-discovery`
to run tasks and sub-tasks iteratively until their `/goal` and verification commands pass, checking AST
call-site wiring, stub/placeholder patterns, constant returns next to fake/stub comments, and mock-only tests.

Core Capabilities:
  1. Hierarchical Goal -> Tasks -> Sub-Tasks ledger (`.swarm/goal_loop.json`, `.swarm/goal_progress.md`,
     `.swarm/ledger.md`, and `.swarm/deferred_minor_ledger.md`).
  2. Deterministic Invariants (`BLOCKING_FAIL` vs `ADVISORY_WARN`) + Two-Verdict Categorical Gate:
     - `BLOCKING_FAIL`:
       1) `verification_cmd` failed (`exit_code != 0`).
       2) Unresolved stubs/placeholders/synthetic returns (`NotImplementedError`, `TODO`, `FIXME`,
          stub `pass`/`...` bodies, mock imports in production paths, constant returns adjacent to
          fake/stub/hardcoded comments, and test files that only assert on mocks or tautologies).
       3) Broken AST/call-site wiring (`must_be_called_by` / `wiring_files` not actually called/referenced
          in executable AST nodes outside imports, or flagged as `unused_import`).
       4) Missing `target_files`.
     - `ADVISORY_WARN` ("Defend in 1 sentence or fix"):
       1) Broad `except Exception:` / bare `except:` without re-raise or structured error handling.
       2) Excessive `: any` / `as any` type annotations.
     - Categorical Gate Verdict (`PASS` vs `FAIL` — decided directly by categories and counts):
       - Any `BLOCKING_FAIL` OR `spec_verdict != "PASS"` OR `critical_count > 0` OR `important_count > 0` -> `FAIL`.
       - Clean Pass (`blocking_fails == 0`, `spec_verdict == "PASS"`, `critical_count == 0`, `important_count == 0`) -> `PASS`.
       - `minor_count > 0` is logged to `.swarm/deferred_minor_ledger.md` and NEVER blocks task completion.
       - Round 5 Breaker rulings (`--ruling "<what> — <why> — <cost if wrong>"`) are recorded in
         `.swarm/ledger.md` and allow completion as `COMPLETED_WITH_RULING` when `blocking_fails == 0`.
  3. Context-Hygiene Subcommands (`obra/superpowers` architecture):
     - `--preflight`: Pre-Flight Conflict & Dependency Table across all tasks.
     - `--task-brief <TASK_ID>`: Self-contained markdown brief at `.swarm/briefs/<TASK_ID>-brief.md`.
     - `--review-package <TASK_ID> [--base-sha <SHA>]`: Bundles `git log`, `git diff --stat`,
       `git diff -U10`, and deterministic `audit_task` invariant report into
       `.swarm/reviews/<TASK_ID>-review.diff.md`.
"""

from __future__ import annotations

import argparse
import ast
import copy
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SKIP_DIRS = {
    ".git",
    ".swarm",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    "target",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".next",
    "coverage",
}

PROD_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go", ".c", ".cpp", ".cs"}

DEFAULT_ENTRYPOINT_PATTERNS = {
    "main.py",
    "app.py",
    "cli.py",
    "server.py",
    "wsgi.py",
    "asgi.py",
    "manage.py",
    "__main__.py",
    "__init__.py",
    "conftest.py",
    "setup.py",
    "index.html",
    "index.ts",
    "index.tsx",
    "index.js",
    "index.jsx",
    "main.ts",
    "main.tsx",
    "main.js",
    "app.ts",
    "app.tsx",
    "server.ts",
    "server.js",
    "main.rs",
    "lib.rs",
    "mod.rs",
    "main.go",
    "program.cs",
}

STUB_COMMENT_RE = re.compile(
    r"(?:#|//|/\*)\s*(?:TODO|FIXME|HACK|XXX|PLACEHOLDER|TBD)\b[:\s]*(.*)",
    re.IGNORECASE,
)

HALF_BAKED_COMMENT_RE = re.compile(
    r"(?:#|//|/\*)\s*(?:"
    r"in a real implementation|"
    r"in production this would|"
    r"simplified for (?:now|prototype|demo|brevity)|"
    r"mock(?:ed)? (?:implementation|for now|response|data)|"
    r"placeholder (?:implementation|for|logic)|"
    r"synthetic (?:fallback|implementation|data|response)|"
    r"stub(?:bed)? (?:out|implementation|for now)|"
    r"not yet wired|"
    r"conceptual implementation"
    r")\b",
    re.IGNORECASE,
)

NOT_IMPLEMENTED_RE = re.compile(
    r"(?:"
    r"\braise\s+NotImplementedError\b|"
    r"\breturn\s+NotImplemented\b|"
    r"\btodo!\s*\(|"
    r"\bunimplemented!\s*\(|"
    r"\bthrow\s+new\s+Error\(\s*['\"](?:not\s+implemented|todo|placeholder|unimplemented)"
    r")",
    re.IGNORECASE,
)

SYNTHETIC_IMPORT_RE = re.compile(
    r"(?:"
    r"^\s*(?:from\s+unittest\s+import\s+mock|import\s+unittest\.mock|from\s+unittest\.mock\s+import)\b|"
    r"\b(?:MagicMock|AsyncMock)\s*\(|"
    r"\b(?:jest\.fn|vi\.fn|sinon\.stub|sinon\.spy)\s*\("
    r")",
    re.MULTILINE,
)

SYNTHETIC_RETURN_RE = re.compile(
    r"\breturn\s+(?:['\"](?:dummy|mock|placeholder|synthetic|fake|todo|coming\s+soon)[_:\s'\"]|"
    r"\{\s*['\"](?:mock|dummy|synthetic|placeholder)['\"]\s*:)",
    re.IGNORECASE,
)

FAKE_RETURN_COMMENT_RE = re.compile(
    r"(?:#|//|/\*)\s*(?:.*?\b(?:"
    r"fake|faked|hardcoded|hard-coded|canned|stub|stubbed|dummy|mock|mocked|"
    r"pretend|placeholder|synthetic|for\s+now|temp(?:orary)?\s+return|"
    r"fixed\s+value|static\s+return|always\s+returns?"
    r")\b.*)",
    re.IGNORECASE,
)

NON_PY_CONST_RETURN_RE = re.compile(
    r"^\s*return\s+(?:"
    r"true|false|null|undefined|"
    r"-?\d+(?:\.\d+)?|"
    r"['\"][^'\"]*['\"]|"
    r"\[\s*\]|\{\s*\}"
    r")\s*;?\s*(?:(?://|/\*).*$|$)",
    re.IGNORECASE,
)

ANY_ANNOTATION_RE = re.compile(
    r"(?:\bas\s+any\b|:\s*any\b|:\s*list\[any\]|:\s*dict\[[^,\]]+,\s*any\])",
    re.IGNORECASE,
)

BLUEPRINT_PLACEHOLDER_RE = re.compile(
    r"(?:\bLorem\s+ipsum\b|\[\s*TBD\s*\]|\[\s*TODO\s*\]|\bINSERT_\w+\b|<TODO[^>]*>)",
    re.IGNORECASE,
)

# Statuses that mark a task as finished. `--verify-goal` still re-audits every finished task.
DONE_TASK_STATUSES = {"VERIFIED_COMPLETE", "COMPLETED", "COMPLETED_WITH_RULING"}

# Round 5 Breaker ruling types. A ruling settles a disagreement between agents; it never overturns a
# deterministic audit result. Only OVERRIDE completes a task, and only when the audit has no BLOCKING_FAIL.
RULING_TYPES = ("OVERRIDE", "SPLIT_TASK", "RE_ARCHITECT_CONTRACT", "ESCALATE_TO_USER")
# Who produced the verdict: a separate reviewer subagent, or the orchestrator from the worker's self-checks.
REVIEW_SOURCES = ("reviewer", "self-check")

# Printed next to `spec_ref` in task briefs and review packages.
SPEC_REF_NOTE = "read this section of the design; where this brief and the design differ, the design decides."

# Design-plan import (`--import-design`): headings, field bullets and the fields a plan task may carry.
PLAN_HEADING_RE = re.compile(r"^## (?:Detailed Implementation Plan|Implementation Plan)\s*$")
PLAN_TASK_RE = re.compile(r"^### Task ([A-Za-z0-9][A-Za-z0-9._-]*):\s*(.+?)\s*$")
PLAN_FIELD_RE = re.compile(r"^[*-]\s+\*\*([^*]+?)(?::\*\*|\*\*:)\s*(.*)$")
PLAN_FILE_RE = re.compile(r"`([^`]+)`\s*\((Create|Modify|Delete)\)")
PLAN_TASK_FIELDS = ("files", "depends on", "changes", "verification", "outcome", "review focus", "called by", "symbols")
PLAN_GOAL_FIELDS = ("goal", "outcome")
# Fields whose change resets an imported task to PENDING, and the gate results such a reset clears.
IMPORT_COMPARED_FIELDS = (
    "title", "target_files", "depends_on", "objective", "verification_cmd", "outcome_cmd",
    "review_focus", "wiring_files", "required_symbols", "spec_ref",
)
GATE_RESET_FIELDS = {
    "gate_verdict": "PENDING", "spec_verdict": "UNVERIFIABLE", "critical_count": 0, "important_count": 0,
    "minor_count": 0, "iterations": 0, "last_errors": [], "ruling": None, "blocking_fails": [], "advisory_warns": [],
}


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _detect_git_head(cwd: str | None = None) -> str:
    target = os.path.abspath(cwd or os.getcwd())
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=target,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        _ = str(exc)
    return "HEAD"


DEFAULT_MANIFEST: dict[str, Any] = {
    "initialized_at": "",
    "updated_at": "",
    "goal": "Deliver verified, production-wired software that passes all task and outcome checks",
    "outcome_cmd": "",
    "expect_output": "",
    "pass_hat_k": 1,
    "entrypoints": ["src/main.py"],
    "non_negotiables": [
        "No unimplemented stubs (TODO/FIXME/NotImplementedError/pass/...) or mock imports in production files",
        "No constant returns next to fake/stub/hardcoded comments or test files that only assert on mocks",
        "AST-verified call-site wiring into active entrypoints",
        "All Review Focus failure modes covered by automated tests",
    ],
    "status": "IN_PROGRESS",
    "can_emit_goal_complete": False,
    "tasks": {
        "TASK-001": {
            "id": "TASK-001",
            "task_id": "TASK-001",
            "title": "Core Feature Implementation & Entrypoint Wiring",
            "description": "Implement core module logic and wire it into the main application execution path.",
            "objective": "Implement core module logic and wire it into the main application execution path.",
            "status": "PENDING",
            "base_sha": "HEAD",
            "target_files": ["src/core.py"],
            "wiring_files": ["src/main.py"],
            "required_symbols": ["run_core"],
            "wiring_contract": {
                "must_be_called_by": ["src/main.py"],
                "exported_symbols": ["run_core"],
            },
            "verification_cmd": "python3 -m unittest discover -s tests -q",
            "validation_cmd": "python3 -m unittest discover -s tests -q",
            "outcome_cmd": "",
            "expect_output": "",
            "review_focus": [
                "Degenerate, empty, or malformed input handling without silent failure",
                "Boundary and scale conditions verified with concrete assertions",
                "Active AST call-site invocation from src/main.py (not unused import)",
            ],
            "blocking_fails": [],
            "advisory_warns": [],
            "spec_verdict": "UNVERIFIABLE",
            "gate_verdict": "PENDING",
            "critical_count": 0,
            "important_count": 0,
            "minor_count": 0,
            "ruling": None,
            "iterations": 0,
            "last_errors": [],
            "subtasks": {},
            "history": [],
        }
    },
    "verification_history": [],
}


def resolve_goal_file(cwd: str | None = None, create_dir: bool = False) -> str:
    env_override = os.environ.get("SWARM_GOAL_FILE")
    if env_override:
        return os.path.abspath(env_override)
    base = os.path.abspath(cwd or os.getcwd())
    swarm_dir = os.path.join(base, ".swarm")
    if create_dir:
        os.makedirs(swarm_dir, exist_ok=True)
    return os.path.join(swarm_dir, "goal_loop.json")


def resolve_progress_md(cwd: str | None = None) -> str:
    base = os.path.abspath(cwd or os.getcwd())
    return os.path.join(base, ".swarm", "goal_progress.md")


def resolve_ledger_md(cwd: str | None = None, create_dir: bool = False) -> str:
    base = os.path.abspath(cwd or os.getcwd())
    swarm_dir = os.path.join(base, ".swarm")
    if create_dir:
        os.makedirs(swarm_dir, exist_ok=True)
    return os.path.join(swarm_dir, "ledger.md")


def resolve_deferred_minor_ledger_md(cwd: str | None = None, create_dir: bool = False) -> str:
    base = os.path.abspath(cwd or os.getcwd())
    swarm_dir = os.path.join(base, ".swarm")
    if create_dir:
        os.makedirs(swarm_dir, exist_ok=True)
    return os.path.join(swarm_dir, "deferred_minor_ledger.md")


def ensure_ledger_files(cwd: str | None = None) -> None:
    ledger_path = resolve_ledger_md(cwd=cwd, create_dir=True)
    if not os.path.exists(ledger_path):
        with open(ledger_path, "w", encoding="utf-8") as f:
            f.write("# Swarm Execution, Pre-Flight & Rulings Ledger\n\n")
    minor_path = resolve_deferred_minor_ledger_md(cwd=cwd, create_dir=True)
    if not os.path.exists(minor_path):
        with open(minor_path, "w", encoding="utf-8") as f:
            f.write("# Deferred Minor Findings Ledger (Non-Blocking — Sweep in Final Polish)\n\n")


def append_ledger_entry(line: str, cwd: str | None = None) -> str:
    ensure_ledger_files(cwd=cwd)
    ledger_path = resolve_ledger_md(cwd=cwd, create_dir=True)
    with open(ledger_path, "a", encoding="utf-8") as f:
        f.write(f"- [{now_iso()[:19]}Z] {line}\n")
    return ledger_path


def append_deferred_minor(task_id: str, count: int, notes: str = "", cwd: str | None = None) -> str:
    ensure_ledger_files(cwd=cwd)
    minor_path = resolve_deferred_minor_ledger_md(cwd=cwd, create_dir=True)
    detail = notes.strip() or f"{count} minor polish item(s) deferred during review"
    with open(minor_path, "a", encoding="utf-8") as f:
        f.write(f"- [{now_iso()[:19]}Z] **Task `{task_id}`** (minor x{count}, deferred): {detail}\n")
    return minor_path


def _normalize_task_record(tid: str, raw: dict[str, Any], default_base_sha: str = "HEAD") -> dict[str, Any]:
    t = dict(raw)
    tid_str = str(t.get("task_id") or t.get("id") or tid)
    t["id"] = tid_str
    t["task_id"] = tid_str
    t.setdefault("title", f"Task {tid_str}")
    desc = t.get("description") or t.get("objective") or t["title"]
    t["description"] = desc
    t["objective"] = t.get("objective") or desc
    t.setdefault("status", "PENDING")
    t.setdefault("base_sha", default_base_sha)

    # Synchronize wiring_contract <-> wiring_files / required_symbols
    wc = t.get("wiring_contract")
    if not isinstance(wc, dict):
        wc = {}
    wiring_files = list(t.get("wiring_files") or wc.get("must_be_called_by") or [])
    req_symbols = list(t.get("required_symbols") or wc.get("exported_symbols") or [])
    t["wiring_files"] = [str(x).strip() for x in wiring_files if str(x).strip()]
    t["required_symbols"] = [str(x).strip() for x in req_symbols if str(x).strip()]
    t["wiring_contract"] = {
        "must_be_called_by": list(t["wiring_files"]),
        "exported_symbols": list(t["required_symbols"]),
    }

    target_files = list(t.get("target_files") or [])
    t["target_files"] = [str(x).strip() for x in target_files if str(x).strip()]

    # `verification_commands` (list) is the documented manifest key; `verification_cmd` is what audits run.
    v_cmds = t.get("verification_commands") or []
    if isinstance(v_cmds, str):
        v_cmds = [v_cmds]
    v_cmds = [str(c).strip() for c in v_cmds if str(c).strip()]
    v_cmd = t.get("verification_cmd") or t.get("validation_cmd") or " && ".join(v_cmds)
    t["verification_commands"] = v_cmds or ([v_cmd] if v_cmd else [])
    t["verification_cmd"] = v_cmd
    t["validation_cmd"] = t.get("validation_cmd") or v_cmd
    t.setdefault("outcome_cmd", "")
    t.setdefault("expect_output", "")
    t.setdefault("wiring_target", "")

    rf = t.get("review_focus")
    if isinstance(rf, str):
        rf = [x.strip() for x in rf.split(";") if x.strip()] if ";" in rf else ([rf.strip()] if rf.strip() else [])
    elif not isinstance(rf, list):
        rf = []
    t["review_focus"] = rf

    t.setdefault("blocking_fails", [])
    t.setdefault("advisory_warns", [])
    t.setdefault("spec_verdict", "UNVERIFIABLE")
    t.setdefault("gate_verdict", "PENDING")
    t.setdefault("critical_count", 0)
    t.setdefault("important_count", 0)
    t.setdefault("minor_count", 0)
    t.pop("score", None)
    t.pop("hard_cap", None)
    t.setdefault("ruling", None)
    t.setdefault("iterations", 0)
    t.setdefault("last_errors", [])
    t.setdefault("subtasks", {})
    t.setdefault("history", [])
    return t


def load_goal_state(cwd: str | None = None) -> dict[str, Any]:
    path = resolve_goal_file(cwd=cwd, create_dir=False)
    default_sha = _detect_git_head(cwd=cwd)
    if not os.path.exists(path):
        return {
            "initialized_at": now_iso(),
            "updated_at": now_iso(),
            "goal": "",
            "outcome_cmd": "",
            "expect_output": "",
            "pass_hat_k": 1,
            "entrypoints": [],
            "non_negotiables": list(DEFAULT_MANIFEST["non_negotiables"]),
            "status": "IN_PROGRESS",
            "can_emit_goal_complete": False,
            "tasks": {},
            "verification_history": [],
        }
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("goal", "")
            data.setdefault("outcome_cmd", "")
            data.setdefault("expect_output", "")
            data.setdefault("pass_hat_k", 1)
            data.setdefault("entrypoints", [])
            data.setdefault("non_negotiables", list(DEFAULT_MANIFEST["non_negotiables"]))
            data.setdefault("status", "IN_PROGRESS")
            data.setdefault("can_emit_goal_complete", False)
            raw_tasks = data.get("tasks", {})
            norm_tasks: dict[str, Any] = {}
            if isinstance(raw_tasks, list):
                for idx, item in enumerate(raw_tasks, start=1):
                    if isinstance(item, dict):
                        tid = str(item.get("task_id") or item.get("id") or f"TASK-{idx:03d}")
                        norm_tasks[tid] = _normalize_task_record(tid, item, default_base_sha=default_sha)
            elif isinstance(raw_tasks, dict):
                for tid, item in raw_tasks.items():
                    if isinstance(item, dict):
                        norm_tasks[str(tid)] = _normalize_task_record(str(tid), item, default_base_sha=default_sha)
            data["tasks"] = norm_tasks
            data.setdefault("verification_history", [])
            return data
    except Exception:
        return {
            "initialized_at": now_iso(),
            "updated_at": now_iso(),
            "goal": "",
            "outcome_cmd": "",
            "expect_output": "",
            "pass_hat_k": 1,
            "entrypoints": [],
            "non_negotiables": list(DEFAULT_MANIFEST["non_negotiables"]),
            "status": "IN_PROGRESS",
            "can_emit_goal_complete": False,
            "tasks": {},
            "verification_history": [],
        }


def save_goal_state(state: dict[str, Any], cwd: str | None = None) -> None:
    state["updated_at"] = now_iso()
    path = resolve_goal_file(cwd=cwd, create_dir=True)
    # Write to a temporary file first so a crash never leaves a truncated goal file.
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp_path, path)
    render_goal_progress_md(state, cwd=cwd)


def render_goal_progress_md(state: dict[str, Any], cwd: str | None = None) -> str:
    md_path = resolve_progress_md(cwd=cwd)
    os.makedirs(os.path.dirname(md_path), exist_ok=True)
    lines = [
        "# Autonomous Goal-Loop, Categorical Gate & Outcome Participation Ledger",
        "",
        f"- **Root Desired Outcome (`/goal`):** {state.get('goal') or 'N/A'}",
        f"- **Root Outcome Verification Command:** `{state.get('outcome_cmd') or 'N/A'}`",
        f"- **Expected Outcome Pattern:** `{state.get('expect_output') or '(exit code 0)'}`",
        f"- **Registered Product Entrypoints:** `{', '.join(state.get('entrypoints', [])) or 'Auto-detected'}`",
        f"- **Overall Goal Status:** **`{state.get('status', 'IN_PROGRESS')}`** "
        f"(Can Emit `<!-- GOAL_COMPLETE -->`: `{state.get('can_emit_goal_complete', False)}`)",
        f"- **Last Updated:** `{state.get('updated_at', '')}`",
        "",
        "## Hierarchical Tasks & Sub-Tasks",
        "",
    ]
    tasks = state.get("tasks", {})
    if not tasks:
        lines.append("_No tasks registered yet. Run `goal_loop.py --init` or `goal_loop.py --add-task`._")
    else:
        for tid, task in tasks.items():
            t_status = task.get("status", "PENDING")
            if t_status in DONE_TASK_STATUSES:
                icon = "✅"
            elif t_status in ("BLOCKED_BY_RULING", "SUPERSEDED"):
                icon = "⛔" if t_status == "BLOCKED_BY_RULING" else "↪️"
            else:
                icon = "🔄" if t_status in ("IN_PROGRESS", "NEEDS_ITERATION", "AWAITING_REVIEW") else "⏳"
            gate_v = task.get("gate_verdict")
            verdict_str = f" | Gate: `{gate_v}`" if gate_v and gate_v != "PENDING" else ""
            lines.append(f"### {icon} Task `{tid}`: {task.get('title', tid)} [`{t_status}`{verdict_str}]")
            lines.append(f"- **Objective:** {task.get('objective', '')}")
            if task.get("base_sha"):
                lines.append(f"- **Base SHA:** `{task.get('base_sha')}`")
            if task.get("target_files"):
                lines.append(f"- **Target Files:** `{', '.join(task['target_files'])}`")
            if task.get("wiring_files"):
                lines.append(
                    f"- **Must Be Called By (AST Wiring):** `{', '.join(task['wiring_files'])}` "
                    f"(Symbols: `{', '.join(task.get('required_symbols', [])) or 'module import'}`)"
                )
            if task.get("verification_cmd") or task.get("validation_cmd"):
                lines.append(f"- **Verification Command:** `{task.get('verification_cmd') or task.get('validation_cmd')}`")
            if task.get("review_focus"):
                lines.append(f"- **Review Focus:** {'; '.join(task['review_focus'])}")
            if task.get("ruling"):
                lines.append(
                    f"- **⚖️ Orchestrator Ruling ({task.get('ruling_type') or 'untyped'}):** `Ruling: {task['ruling']}`"
                )
            if task.get("superseded_by"):
                lines.append(f"- **Superseded By:** `{', '.join(task['superseded_by'])}`")
            if task.get("blocking_fails"):
                for bf in task["blocking_fails"][:5]:
                    lines.append(f"- ❌ **BLOCKING_FAIL:** {bf}")
            if task.get("advisory_warns"):
                for aw in task["advisory_warns"][:5]:
                    lines.append(f"- ⚠️ **ADVISORY_WARN:** {aw}")

            subtasks = task.get("subtasks", {})
            if subtasks:
                lines.append("- **Sub-Tasks:**")
                for sid, sub in subtasks.items():
                    s_status = sub.get("status", "PENDING")
                    s_icon = "✅" if s_status in DONE_TASK_STATUSES else ("❌" if s_status == "NEEDS_ITERATION" else "⏳")
                    iters = sub.get("iterations", 0)
                    lines.append(
                        f"  - {s_icon} **`{sid}`** ({sub.get('title', sid)}) — `{s_status}` "
                        f"[Iterations: {iters}]"
                    )
                    lines.append(f"    - *Objective:* {sub.get('objective', '')}")
                    if sub.get("target_files"):
                        lines.append(f"    - *Target Files:* `{', '.join(sub['target_files'])}`")
                    if sub.get("wiring_files"):
                        lines.append(
                            f"    - *Entrypoint/Pipeline Wiring:* `{', '.join(sub['wiring_files'])}` "
                            f"(Required Symbols: `{', '.join(sub.get('required_symbols', [])) or 'module import'}`)"
                        )
                    if sub.get("validation_cmd"):
                        lines.append(f"    - *Validation:* `{sub.get('validation_cmd')}`")
                    if sub.get("outcome_cmd"):
                        lines.append(f"    - *Outcome Probe:* `{sub.get('outcome_cmd')}`")
                    if sub.get("last_errors"):
                        for err in sub["last_errors"]:
                            lines.append(f"    - ⚠️ *Unresolved Defect:* {err}")
            lines.append("")

    content = "\n".join(lines) + "\n"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)
    return md_path


def is_test_file(rel_path: str) -> bool:
    norm = rel_path.replace("\\", "/").lower()
    base = os.path.basename(norm)
    if "/benchmarks/" in f"/{norm}" or "/bench/" in f"/{norm}":
        return False
    return (
        base.startswith("test_")
        or base.endswith(("_test.py", ".test.ts", ".test.tsx", ".test.js", ".spec.ts", ".spec.tsx", ".spec.js"))
        or "/tests/" in f"/{norm}"
        or "/test/" in f"/{norm}"
        or "/__tests__/" in f"/{norm}"
    )


def is_test_or_tooling_file(rel_path: str) -> bool:
    norm = rel_path.replace("\\", "/").lower()
    base = os.path.basename(norm)
    return (
        is_test_file(rel_path)
        or "/benchmarks/" in f"/{norm}"
        or "/bench/" in f"/{norm}"
        or "/contracts/" in f"/{norm}"
        or base in {"agent_shield.py", "immortal_watcher.py", "goal_loop.py", "web_ui_validator.py"}
    )


def is_contract_or_interface_file(rel_path: str) -> bool:
    norm = rel_path.replace("\\", "/").lower()
    base = os.path.basename(norm)
    return (
        "/contracts/" in f"/{norm}"
        or base.startswith(("contract", "interface", "types", "schema", "protocol"))
        or base.endswith((".d.ts", "_types.py", "_schema.py", "_contracts.py"))
    )


def _is_ast_constant_expr(node: ast.AST | None) -> bool:
    """Return True if `node` is a constant literal or a container/unary op composed solely of constants."""
    if node is None:
        return False
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Not, ast.Invert)):
        return _is_ast_constant_expr(node.operand)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_is_ast_constant_expr(elt) for elt in node.elts)
    if isinstance(node, ast.Dict):
        return all(
            (k is None or _is_ast_constant_expr(k)) and _is_ast_constant_expr(v)
            for k, v in zip(node.keys, node.values)
        )
    return False


def _find_fake_comment_near_lines(
    source_lines: list[str],
    start_line: int,
    end_line: int,
) -> str | None:
    """Return the matching comment snippet if any line in [start_line, end_line] (1-based) has a fake/stub comment."""
    lo = max(1, start_line)
    hi = min(len(source_lines), end_line)
    for idx in range(lo - 1, hi):
        m = FAKE_RETURN_COMMENT_RE.search(source_lines[idx])
        if m:
            return m.group(0).strip()[:120]
    return None


def _is_trivial_body(fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True for bodies that are only a docstring, `pass`, `...`, or `raise NotImplementedError`."""
    body = list(fn_node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    if not body:
        return True
    if len(body) != 1:
        return False
    stmt = body[0]
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is Ellipsis:
        return True
    return isinstance(stmt, ast.Raise) and "NotImplementedError" in (ast.unparse(stmt) if hasattr(ast, "unparse") else "")


def _dispatch_no_op_handlers(methods: list[ast.FunctionDef | ast.AsyncFunctionDef]) -> set[str]:
    """`pass`-only methods that belong to a dispatch family (visitor/renderer/event handlers).

    A family is 3+ methods in one class sharing a prefix such as `visit_`, `r_` or `on_`, at least half of
    which have real bodies. Code like `getattr(self, "visit_" + node.type)` needs a handler for every
    type, and some handlers rightly do nothing; a lone `pass` method is still reported as a stub.
    """
    families: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = {}
    for m in methods:
        if m.name.startswith("_") or "_" not in m.name:
            continue
        families.setdefault(m.name.split("_")[0], []).append(m)
    allowed: set[str] = set()
    for members in families.values():
        if len(members) < 3:
            continue
        real = [m for m in members if not _is_trivial_body(m)]
        if len(real) * 2 < len(members):
            continue
        for m in members:
            body = [b for b in m.body if not (isinstance(b, ast.Expr) and isinstance(getattr(b, "value", None), ast.Constant)
                                              and isinstance(b.value.value, str))]
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                allowed.add(m.name)
    return allowed


def _check_python_ast_authenticity(source: str, rel_path: str) -> dict[str, list[dict[str, Any]]]:
    """Use Python AST to detect empty/stubbed functions, constant returns next to fake comments, and broad excepts."""
    stubs: list[dict[str, Any]] = []
    synthetics: list[dict[str, Any]] = []
    advisory_warns: list[dict[str, Any]] = []
    imports: set[str] = set()
    called_names: set[str] = set()
    defined_symbols: set[str] = set()
    has_main_guard = False

    if is_contract_or_interface_file(rel_path):
        return {
            "stubs": stubs,
            "synthetics": synthetics,
            "advisory_warns": advisory_warns,
            "imports": list(imports),
            "called_names": list(called_names),
            "defined_symbols": list(defined_symbols),
            "has_main_guard": True,
        }

    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError as exc:
        stubs.append(
            {
                "file": rel_path,
                "line": exc.lineno or 1,
                "kind": "SYNTAX_ERROR",
                "detail": f"Python SyntaxError: {exc.msg}",
            }
        )
        return {
            "stubs": stubs,
            "synthetics": synthetics,
            "advisory_warns": advisory_warns,
            "imports": [],
            "called_names": [],
            "defined_symbols": [],
            "has_main_guard": False,
        }

    source_lines = source.splitlines()
    abstract_class_nodes: set[ast.AST] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            defined_symbols.add(node.name)
            for base in node.bases:
                base_str = ast.unparse(base) if hasattr(ast, "unparse") else ""
                if any(tok in base_str for tok in ("Protocol", "ABC", "Interface", "Base", "Exception", "Error")):
                    abstract_class_nodes.add(node)
        elif isinstance(node, ast.If):
            cond_dump = ast.dump(node.test)
            if "__name__" in cond_dump and "__main__" in cond_dump:
                has_main_guard = True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
                imports.add(alias.name.split(".")[0])
                if alias.asname:
                    called_names.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
                imports.add(node.module.split(".")[0])
                for part in node.module.split("."):
                    imports.add(part)
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr)
                if isinstance(node.func.value, ast.Name):
                    called_names.add(f"{node.func.value.id}.{node.func.attr}")
        elif isinstance(node, ast.Name):
            called_names.add(node.id)
        elif isinstance(node, ast.ExceptHandler):
            is_broad = node.type is None or (
                isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException")
            )
            if is_broad:
                has_reraise = any(isinstance(sub, ast.Raise) for sub in ast.walk(node))
                body_dump = ast.dump(node)
                has_structured_log = any(
                    tok in body_dump for tok in ("logger", "logging", "stderr", "record_error", "handle_error")
                )
                if not has_reraise and not has_structured_log:
                    advisory_warns.append(
                        {
                            "file": rel_path,
                            "line": node.lineno or 1,
                            "kind": "BROAD_EXCEPT_WITHOUT_RERAISE",
                            "detail": (
                                f"Broad `except Exception:` / bare `except:` at `{rel_path}:{node.lineno}` "
                                "without re-raise or structured error handling (Defend in 1 sentence or fix)."
                            ),
                        }
                    )

    def _iter_direct_func_nodes(root_stmt_list: list[ast.stmt]) -> list[ast.AST]:
        collected: list[ast.AST] = []
        stack = list(root_stmt_list)
        while stack:
            cur = stack.pop(0)
            if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            collected.append(cur)
            for child in ast.iter_child_nodes(cur):
                if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    stack.append(child)
        return collected

    def _inspect_func(fn_node: ast.FunctionDef | ast.AsyncFunctionDef, in_abstract_class: bool) -> None:
        defined_symbols.add(fn_node.name)
        if fn_node.name.startswith("__") and fn_node.name.endswith("__"):
            return
        for dec in fn_node.decorator_list:
            dec_str = ast.unparse(dec) if hasattr(ast, "unparse") else ""
            if any(d in dec_str for d in ("abstractmethod", "overload", "property")):
                return
        if in_abstract_class:
            return

        body = fn_node.body
        effective_body = body
        docstring_text = ""
        if (
            effective_body
            and isinstance(effective_body[0], ast.Expr)
            and isinstance(effective_body[0].value, ast.Constant)
            and isinstance(effective_body[0].value.value, str)
        ):
            docstring_text = effective_body[0].value.value
            effective_body = effective_body[1:]

        if not effective_body:
            stubs.append(
                {
                    "file": rel_path,
                    "line": fn_node.lineno,
                    "kind": "EMPTY_FUNCTION_STUB",
                    "detail": f"Function `{fn_node.name}()` has only a docstring and no implementation body.",
                }
            )
            return

        if len(effective_body) == 1:
            stmt = effective_body[0]
            if isinstance(stmt, ast.Pass):
                stubs.append(
                    {
                        "file": rel_path,
                        "line": fn_node.lineno,
                        "kind": "PASS_ONLY_FUNCTION_STUB",
                        "detail": f"Function `{fn_node.name}()` is an unimplemented `pass` stub.",
                    }
                )
                return
            elif (
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and stmt.value.value is Ellipsis
            ):
                stubs.append(
                    {
                        "file": rel_path,
                        "line": fn_node.lineno,
                        "kind": "ELLIPSIS_FUNCTION_STUB",
                        "detail": f"Function `{fn_node.name}()` is an unimplemented `...` stub.",
                    }
                )
                return
            elif isinstance(stmt, ast.Raise):
                exc_str = ast.unparse(stmt) if hasattr(ast, "unparse") else ""
                if "NotImplementedError" in exc_str:
                    stubs.append(
                        {
                            "file": rel_path,
                            "line": fn_node.lineno,
                            "kind": "NOT_IMPLEMENTED_STUB",
                            "detail": f"Function `{fn_node.name}()` raises `NotImplementedError`.",
                        }
                    )
                    return

        # Check for constant returns adjacent to fake/stub/hardcoded comments
        fn_end_line = getattr(fn_node, "end_lineno", fn_node.lineno) or fn_node.lineno
        for sub_node in _iter_direct_func_nodes(effective_body):
            if isinstance(sub_node, ast.Return) and _is_ast_constant_expr(sub_node.value):
                ret_line = sub_node.lineno or fn_node.lineno
                ret_end = getattr(sub_node, "end_lineno", ret_line) or ret_line
                window_start = fn_node.lineno if len(effective_body) <= 2 else max(fn_node.lineno, ret_line - 2)
                window_end = fn_end_line if len(effective_body) <= 2 else min(fn_end_line, ret_end + 1)
                comment_hit = _find_fake_comment_near_lines(source_lines, window_start, window_end)
                if not comment_hit and len(effective_body) == 1 and docstring_text:
                    doc_m = FAKE_RETURN_COMMENT_RE.search(f"# {docstring_text}")
                    if doc_m:
                        comment_hit = docstring_text.strip().splitlines()[0][:120]
                if comment_hit:
                    val_str = ast.unparse(sub_node.value) if hasattr(ast, "unparse") and sub_node.value else "constant"
                    synthetics.append(
                        {
                            "file": rel_path,
                            "line": ret_line,
                            "kind": "CONSTANT_RETURN_WITH_FAKE_COMMENT",
                            "detail": (
                                f"Function `{fn_node.name}()` returns constant `{val_str[:60]}` "
                                f"next to fake/stub comment (`{comment_hit}`)."
                            ),
                        }
                    )

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _inspect_func(node, in_abstract_class=False)
        elif isinstance(node, ast.ClassDef):
            is_abs = node in abstract_class_nodes
            methods = [i for i in node.body if isinstance(i, (ast.FunctionDef, ast.AsyncFunctionDef))]
            no_op_handlers = _dispatch_no_op_handlers(methods)
            for item in methods:
                if item.name in no_op_handlers:
                    defined_symbols.add(item.name)
                    advisory_warns.append(
                        {
                            "file": rel_path,
                            "line": item.lineno,
                            "kind": "NO_OP_DISPATCH_HANDLER",
                            "detail": (
                                f"`{item.name}()` is a `pass`-only member of a handler family "
                                f"(`{item.name.split('_')[0]}_*`); treated as a deliberate no-op, not a stub."
                            ),
                        }
                    )
                    continue
                _inspect_func(item, in_abstract_class=is_abs)

    return {
        "stubs": stubs,
        "synthetics": synthetics,
        "advisory_warns": advisory_warns,
        "imports": list(imports),
        "called_names": list(called_names),
        "defined_symbols": list(defined_symbols),
        "has_main_guard": has_main_guard,
    }


_MOCK_CONSTRUCTOR_NAMES = {
    "MagicMock",
    "AsyncMock",
    "Mock",
    "NonCallableMock",
    "NonCallableMagicMock",
    "PropertyMock",
    "patch",
    "create_autospec",
    "spy",
}

_MOCK_ASSERT_METHODS = {
    "assert_called",
    "assert_called_once",
    "assert_called_with",
    "assert_called_once_with",
    "assert_any_call",
    "assert_has_calls",
    "assert_not_called",
}

_MOCK_ONLY_ATTRS = {
    "called",
    "call_count",
    "call_args",
    "call_args_list",
    "mock_calls",
    "method_calls",
    "return_value",
    "side_effect",
}

_PY_BUILTIN_NAMES = {
    "True",
    "False",
    "None",
    "len",
    "int",
    "float",
    "str",
    "bool",
    "list",
    "dict",
    "set",
    "tuple",
    "any",
    "all",
    "isinstance",
    "issubclass",
    "type",
    "abs",
    "min",
    "max",
    "sum",
    "sorted",
    "range",
    "enumerate",
    "zip",
    "Exception",
    "ValueError",
    "TypeError",
    "KeyError",
    "RuntimeError",
}


def _extract_root_name(node: ast.AST | None) -> str | None:
    cur = node
    while isinstance(cur, (ast.Attribute, ast.Subscript, ast.Call)):
        if isinstance(cur, ast.Attribute):
            cur = cur.value
        elif isinstance(cur, ast.Subscript):
            cur = cur.value
        elif isinstance(cur, ast.Call):
            cur = cur.func
    if isinstance(cur, ast.Name):
        return cur.id
    return None


def _is_mock_constructor_call(node: ast.AST | None) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id in _MOCK_CONSTRUCTOR_NAMES:
        return True
    if isinstance(func, ast.Attribute):
        if func.attr in _MOCK_CONSTRUCTOR_NAMES or func.attr == "object":
            root = _extract_root_name(func.value)
            if func.attr in _MOCK_CONSTRUCTOR_NAMES or root in ("patch", "mock", "mocker", "unittest"):
                return True
    return False


def _expr_references_only_mocks(expr: ast.AST, mock_vars: set[str]) -> bool:
    """Return True if an assertion expression only inspects mock objects/attributes and no real variables."""
    names: set[str] = set()
    has_mock_attr = False
    for sub in ast.walk(expr):
        if isinstance(sub, ast.Attribute) and sub.attr in _MOCK_ONLY_ATTRS:
            has_mock_attr = True
        elif isinstance(sub, ast.Name) and sub.id not in _PY_BUILTIN_NAMES and sub.id != "self":
            names.add(sub.id)
    if has_mock_attr and (not names or names.issubset(mock_vars)):
        return True
    if names and names.issubset(mock_vars):
        return True
    return False


def _check_python_test_file_authenticity(source: str, rel_path: str) -> dict[str, list[dict[str, Any]]]:
    """Detect Python test files that only assert on mocks (`MOCK_ONLY_TEST_FILE`) or have vacuous assertions."""
    stubs: list[dict[str, Any]] = []
    synthetics: list[dict[str, Any]] = []

    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError:
        return {"stubs": stubs, "synthetics": synthetics}

    test_funcs: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            test_funcs.append(node)

    if not test_funcs:
        return {"stubs": stubs, "synthetics": synthetics}

    total_real_assertions = 0
    total_mock_assertions = 0
    total_tautologies = 0

    for fn in test_funcs:
        mock_vars: set[str] = set()
        patch_decorator_count = 0
        for dec in fn.decorator_list:
            dec_str = ast.unparse(dec) if hasattr(ast, "unparse") else ""
            if "patch" in dec_str:
                patch_decorator_count += 1

        non_self_args = [a.arg for a in fn.args.args if a.arg not in ("self", "cls")]
        for arg_name in non_self_args:
            low = arg_name.lower()
            if low.startswith("mock") or low.endswith("mock") or low in ("mocker", "monkeypatch"):
                mock_vars.add(arg_name)
        if patch_decorator_count > 0 and non_self_args:
            for injected in non_self_args[-patch_decorator_count:]:
                mock_vars.add(injected)

        # First pass inside test function: collect mock variables and mock-derived variables
        for sub in ast.walk(fn):
            if isinstance(sub, ast.With):
                for item in sub.items:
                    ctx_str = ast.unparse(item.context_expr) if hasattr(ast, "unparse") else ""
                    if "patch" in ctx_str or _is_mock_constructor_call(item.context_expr):
                        if isinstance(item.optional_vars, ast.Name):
                            mock_vars.add(item.optional_vars.id)
            elif isinstance(sub, ast.Assign):
                target_names = [t.id for t in sub.targets if isinstance(t, ast.Name)]
                for tname in target_names:
                    if tname.lower().startswith("mock") or tname.lower().endswith("mock"):
                        mock_vars.add(tname)
                if _is_mock_constructor_call(sub.value):
                    for tname in target_names:
                        mock_vars.add(tname)
                else:
                    val_root = _extract_root_name(sub.value)
                    if val_root and val_root in mock_vars:
                        for tname in target_names:
                            mock_vars.add(tname)

        # Second pass: classify assertions in this test function
        for sub in ast.walk(fn):
            if isinstance(sub, ast.Assert):
                if _is_ast_constant_expr(sub.test):
                    total_tautologies += 1
                elif _expr_references_only_mocks(sub.test, mock_vars):
                    total_mock_assertions += 1
                else:
                    total_real_assertions += 1
            elif isinstance(sub, ast.With):
                for item in sub.items:
                    ctx_str = ast.unparse(item.context_expr) if hasattr(ast, "unparse") else ""
                    if "Raises" in ctx_str or "raises" in ctx_str:
                        total_real_assertions += 1
            elif isinstance(sub, ast.Call):
                if isinstance(sub.func, ast.Attribute):
                    attr = sub.func.attr
                    if attr in _MOCK_ASSERT_METHODS or attr.startswith("assert_called"):
                        total_mock_assertions += 1
                    elif attr in ("assertRaises", "assertRaisesRegex"):
                        total_real_assertions += 1
                    elif attr.startswith("assert"):
                        non_const_args = [a for a in sub.args if not _is_ast_constant_expr(a)]
                        if not non_const_args:
                            total_tautologies += 1
                        elif all(_expr_references_only_mocks(a, mock_vars) for a in non_const_args):
                            total_mock_assertions += 1
                        else:
                            total_real_assertions += 1

    if total_mock_assertions > 0 and total_real_assertions == 0:
        synthetics.append(
            {
                "file": rel_path,
                "line": test_funcs[0].lineno,
                "kind": "MOCK_ONLY_TEST_FILE",
                "detail": (
                    f"Test file `{rel_path}` only asserts on mocks ({total_mock_assertions} mock assertion(s), "
                    "0 assertions on real production outputs or state)."
                ),
            }
        )
    elif total_real_assertions == 0 and total_tautologies > 0 and total_mock_assertions == 0:
        stubs.append(
            {
                "file": rel_path,
                "line": test_funcs[0].lineno,
                "kind": "VACUOUS_TEST_FILE",
                "detail": (
                    f"Test file `{rel_path}` contains only constant/tautological assertions "
                    f"({total_tautologies} tautologies, 0 real assertions)."
                ),
            }
        )

    return {"stubs": stubs, "synthetics": synthetics}


def _check_js_test_file_authenticity(source: str, rel_path: str) -> dict[str, list[dict[str, Any]]]:
    """Detect JS/TS test files that only assert on mocks (`toHaveBeenCalled*` / `sinon.assert.called*`)."""
    stubs: list[dict[str, Any]] = []
    synthetics: list[dict[str, Any]] = []

    expect_matches = list(
        re.finditer(r"\bexpect\s*\(([^)]+)\)\s*\.\s*(?:not\s*\.\s*)?([A-Za-z0-9_]+)", source)
    )
    sinon_mock_asserts = len(re.findall(r"\bsinon\.assert\.called\w*\b", source))
    mock_vars = set(
        re.findall(
            r"\b(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:jest\.fn|vi\.fn|sinon\.(?:stub|spy|mock))\b",
            source,
        )
    )

    mock_assertions = sinon_mock_asserts
    real_assertions = 0
    for m in expect_matches:
        subj = m.group(1).strip()
        matcher = m.group(2).strip()
        if matcher.startswith("toHaveBeenCalled") or matcher.startswith("toBeCalled"):
            mock_assertions += 1
        elif subj in mock_vars or subj.lower().startswith("mock"):
            mock_assertions += 1
        else:
            real_assertions += 1

    if mock_assertions > 0 and real_assertions == 0:
        synthetics.append(
            {
                "file": rel_path,
                "line": 1,
                "kind": "MOCK_ONLY_TEST_FILE",
                "detail": (
                    f"Test file `{rel_path}` only asserts on mocks ({mock_assertions} mock assertion(s), "
                    "0 assertions on real production outputs or state)."
                ),
            }
        )
    return {"stubs": stubs, "synthetics": synthetics}


def audit_authenticity(
    root_dir: str = ".",
    target_files: list[str] | None = None,
    entrypoints: list[str] | None = None,
    check_orphan_modules: bool = True,
) -> dict[str, Any]:
    """Scan production code for placeholders/stubs, fake constant returns, unwired modules, and mock-only tests."""
    root = os.path.abspath(root_dir)
    explicit_entrypoints = {os.path.normpath(p) for p in (entrypoints or []) if p}

    prod_files: list[str] = []
    test_files: list[str] = []
    if target_files:
        for tf in target_files:
            abs_tf = tf if os.path.isabs(tf) else os.path.join(root, tf)
            if os.path.isfile(abs_tf):
                rel = os.path.relpath(abs_tf, root)
                if is_test_file(rel):
                    test_files.append(rel)
                elif not is_test_or_tooling_file(rel):
                    prod_files.append(rel)
        # Also include repo test files so mock-only test files in `tests/` are caught during task audits
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".worktree")]
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in PROD_EXTENSIONS:
                    continue
                abs_p = os.path.join(dirpath, fn)
                rel_p = os.path.relpath(abs_p, root)
                if is_test_file(rel_p) and rel_p not in test_files:
                    test_files.append(rel_p)
    else:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".worktree")]
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in PROD_EXTENSIONS:
                    continue
                abs_p = os.path.join(dirpath, fn)
                rel_p = os.path.relpath(abs_p, root)
                if is_test_file(rel_p):
                    test_files.append(rel_p)
                elif not is_test_or_tooling_file(rel_p):
                    prod_files.append(rel_p)

    all_repo_prod_files: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".worktree")]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in PROD_EXTENSIONS:
                abs_p = os.path.join(dirpath, fn)
                rel_p = os.path.relpath(abs_p, root)
                if not is_test_or_tooling_file(rel_p):
                    p_obj = Path(abs_p)
                    if p_obj.is_file():
                        try:
                            all_repo_prod_files[rel_p] = p_obj.read_text(encoding="utf-8", errors="replace")
                        except OSError as exc:
                            all_repo_prod_files[rel_p] = f"# unreadable: {exc}"

    placeholder_findings: list[dict[str, Any]] = []
    synthetic_findings: list[dict[str, Any]] = []
    unwired_findings: list[dict[str, Any]] = []
    advisory_findings: list[dict[str, Any]] = []
    file_ast_info: dict[str, dict[str, Any]] = {}

    for rel_p in sorted(prod_files):
        abs_p = os.path.join(root, rel_p)
        p_obj = Path(abs_p)
        if not p_obj.is_file():
            continue
        content = all_repo_prod_files.get(rel_p)
        if content is None:
            content = p_obj.read_text(encoding="utf-8", errors="replace")

        ext = os.path.splitext(rel_p)[1].lower()
        if ext == ".py":
            ast_res = _check_python_ast_authenticity(content, rel_p)
            file_ast_info[rel_p] = ast_res
            placeholder_findings.extend(ast_res["stubs"])
            synthetic_findings.extend(ast_res["synthetics"])
            advisory_findings.extend(ast_res["advisory_warns"])

        lines_list = content.splitlines()
        for lineno, line in enumerate(lines_list, start=1):
            if STUB_COMMENT_RE.search(line):
                placeholder_findings.append(
                    {
                        "file": rel_p,
                        "line": lineno,
                        "kind": "TODO_OR_PLACEHOLDER_COMMENT",
                        "detail": line.strip()[:160],
                    }
                )
            if HALF_BAKED_COMMENT_RE.search(line):
                placeholder_findings.append(
                    {
                        "file": rel_p,
                        "line": lineno,
                        "kind": "HALF_BAKED_IMPLEMENTATION_COMMENT",
                        "detail": line.strip()[:160],
                    }
                )
            if ext != ".py" and NOT_IMPLEMENTED_RE.search(line):
                placeholder_findings.append(
                    {
                        "file": rel_p,
                        "line": lineno,
                        "kind": "NOT_IMPLEMENTED_STUB",
                        "detail": line.strip()[:160],
                    }
                )
            if ext != ".py" and NON_PY_CONST_RETURN_RE.search(line):
                comment_hit = _find_fake_comment_near_lines(lines_list, lineno - 1, lineno + 1)
                if comment_hit:
                    synthetic_findings.append(
                        {
                            "file": rel_p,
                            "line": lineno,
                            "kind": "CONSTANT_RETURN_WITH_FAKE_COMMENT",
                            "detail": (
                                f"Constant return `{line.strip()[:80]}` next to fake/stub comment (`{comment_hit}`)."
                            ),
                        }
                    )
            if SYNTHETIC_IMPORT_RE.search(line):
                synthetic_findings.append(
                    {
                        "file": rel_p,
                        "line": lineno,
                        "kind": "MOCK_FRAMEWORK_IN_PRODUCTION",
                        "detail": f"Test/mock framework used inside production file: `{line.strip()[:140]}`",
                    }
                )
            if SYNTHETIC_RETURN_RE.search(line):
                synthetic_findings.append(
                    {
                        "file": rel_p,
                        "line": lineno,
                        "kind": "HARDCODED_SYNTHETIC_RETURN",
                        "detail": f"Hardcoded dummy/mock/synthetic return value: `{line.strip()[:140]}`",
                    }
                )
            if not line.strip().startswith(("#", "//", "/*")) and ANY_ANNOTATION_RE.search(line):
                advisory_findings.append(
                    {
                        "file": rel_p,
                        "line": lineno,
                        "kind": "EXCESSIVE_ANY_ANNOTATION",
                        "detail": (
                            f"Type annotation `: any` / `as any` at `{rel_p}:{lineno}` "
                            f"(Defend in 1 sentence or fix): `{line.strip()[:120]}`"
                        ),
                    }
                )

    for rel_test in sorted(test_files):
        abs_t = os.path.join(root, rel_test)
        p_t = Path(abs_t)
        if not p_t.is_file():
            continue
        try:
            test_src = p_t.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        ext_t = os.path.splitext(rel_test)[1].lower()
        if ext_t == ".py":
            t_res = _check_python_test_file_authenticity(test_src, rel_test)
            placeholder_findings.extend(t_res["stubs"])
            synthetic_findings.extend(t_res["synthetics"])
        elif ext_t in (".ts", ".tsx", ".js", ".jsx"):
            t_res = _check_js_test_file_authenticity(test_src, rel_test)
            placeholder_findings.extend(t_res["stubs"])
            synthetic_findings.extend(t_res["synthetics"])

    if check_orphan_modules and len(all_repo_prod_files) >= 2:
        for rel_p in sorted(prod_files):
            norm_p = os.path.normpath(rel_p)
            base_name = os.path.basename(norm_p).lower()
            stem = os.path.splitext(os.path.basename(norm_p))[0]

            if (
                norm_p in explicit_entrypoints
                or base_name in DEFAULT_ENTRYPOINT_PATTERNS
                or is_contract_or_interface_file(rel_p)
                or file_ast_info.get(rel_p, {}).get("has_main_guard", False)
            ):
                continue

            referenced_in_prod = False
            mod_dotted = os.path.splitext(norm_p)[0].replace(os.sep, ".")
            for other_p, other_content in all_repo_prod_files.items():
                if other_p == rel_p:
                    continue
                if stem in other_content or mod_dotted in other_content:
                    referenced_in_prod = True
                    break

            if not referenced_in_prod:
                unwired_findings.append(
                    {
                        "file": rel_p,
                        "line": 1,
                        "kind": "ORPHAN_UNWIRED_MODULE",
                        "detail": (
                            f"Production module `{rel_p}` (`{stem}`) is never imported or referenced by any "
                            f"other non-test production file or entrypoint. Conceptually present code must be "
                            f"wired into the product's active execution pipeline."
                        ),
                    }
                )

    total_violations = len(placeholder_findings) + len(synthetic_findings) + len(unwired_findings)
    passed = total_violations == 0
    return {
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "scanned_files_count": len(prod_files),
        "scanned_test_files_count": len(test_files),
        "counts": {
            "placeholder_or_half_baked": len(placeholder_findings),
            "synthetic_or_mock": len(synthetic_findings),
            "unwired_conceptual_modules": len(unwired_findings),
            "advisory_warns": len(advisory_findings),
            "total_violations": total_violations,
        },
        "placeholder_findings": placeholder_findings,
        "synthetic_findings": synthetic_findings,
        "unwired_findings": unwired_findings,
        "advisory_findings": advisory_findings,
    }


def _git_changes(root: str, base: str | None) -> dict[str, set[int] | None] | None:
    """Files changed since `base` in the working tree: {path: added line numbers, or None for new files}.

    Returns None when there is no usable base (not a git repository, no commits, or the literal "HEAD"),
    which callers treat as "judge the whole tree", the behaviour for new projects.
    """
    if not base or base == "HEAD":
        return None
    try:
        ok = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"], cwd=root,
                            capture_output=True, text=True, timeout=10)
        if ok.returncode != 0:
            return None
        diff = subprocess.run(["git", "diff", "-U0", "--no-color", "--no-renames", base], cwd=root,
                              capture_output=True, text=True, timeout=60, check=True).stdout
        untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=root,
                                   capture_output=True, text=True, timeout=60, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    changes: dict[str, set[int] | None] = {}
    current: str | None = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = None if line[4:] == "/dev/null" else line[4:].removeprefix("b/")
            if current is not None:
                changes.setdefault(current, set())
        elif line.startswith("@@") and current is not None:
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                start, count = int(m.group(1)), int(m.group(2) or "1")
                lines = changes[current]
                if lines is not None:
                    lines.update(range(start, start + count))
        elif line.startswith("--- /dev/null"):
            pass
    for rel in untracked.splitlines():
        if rel:
            changes[rel] = None
    return changes


def restrict_to_changes(auth_res: dict[str, Any], changes: dict[str, set[int] | None]) -> dict[str, Any]:
    """Keep only findings the change introduced: in new files, or on (or right after) an added line.

    On an existing codebase this stops a task audit from failing on code the task never touched (old test
    files, pre-existing no-op methods). Modules count as unwired only if the task added or edited them.
    """
    def touched(item: dict[str, Any]) -> bool:
        rel = os.path.normpath(item.get("file", ""))
        if rel not in changes:
            return False
        lines = changes[rel]
        line = item.get("line")
        # A finding points at a `def` (or a single statement); count it if that line or the next one changed.
        return lines is None or line is None or any(n in lines for n in (int(line), int(line) + 1))

    out = dict(auth_res)
    for key in ("placeholder_findings", "synthetic_findings", "advisory_findings"):
        out[key] = [f for f in auth_res.get(key, []) if touched(f)]
    out["unwired_findings"] = [f for f in auth_res.get("unwired_findings", [])
                               if os.path.normpath(f.get("file", "")) in changes]
    total = len(out["placeholder_findings"]) + len(out["synthetic_findings"]) + len(out["unwired_findings"])
    out["passed"] = total == 0
    out["status"] = "PASS" if out["passed"] else "FAIL"
    out["counts"] = {
        "placeholder_or_half_baked": len(out["placeholder_findings"]),
        "synthetic_or_mock": len(out["synthetic_findings"]),
        "unwired_conceptual_modules": len(out["unwired_findings"]),
        "advisory_warns": len(out["advisory_findings"]),
        "total_violations": total,
    }
    out["restricted_to_changes"] = True
    return out


def _inspect_python_caller_ast(source: str, rel_path: str) -> dict[str, Any]:
    """Parse Python caller file with `ast.parse()` and separate imports from active AST expression/statement usage."""
    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError as exc:
        return {
            "valid_syntax": False,
            "syntax_error": f"SyntaxError in `{rel_path}` at line {exc.lineno}: {exc.msg}",
            "imported_symbol_map": {},
            "imported_modules": set(),
            "used_names": set(),
            "called_names": set(),
        }

    imported_symbol_map: dict[str, str] = {}
    imported_modules: set[str] = set()
    used_names: set[str] = set()
    called_names: set[str] = set()

    def _walk_non_import(node: ast.AST) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
                for part in alias.name.split("."):
                    imported_modules.add(part)
                bound = alias.asname or alias.name.split(".")[0]
                imported_symbol_map[alias.name] = bound
                imported_symbol_map[alias.name.split(".")[-1]] = bound
            return
        if isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module)
                for part in node.module.split("."):
                    imported_modules.add(part)
            for alias in node.names:
                bound = alias.asname or alias.name
                imported_symbol_map[alias.name] = bound
            return

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
                used_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr)
                used_names.add(node.func.attr)
                if isinstance(node.func.value, ast.Name):
                    qual = f"{node.func.value.id}.{node.func.attr}"
                    called_names.add(qual)
                    used_names.add(qual)
                    used_names.add(node.func.value.id)
        elif isinstance(node, ast.Attribute):
            used_names.add(node.attr)
            if isinstance(node.value, ast.Name):
                used_names.add(node.value.id)
                used_names.add(f"{node.value.id}.{node.attr}")
        elif isinstance(node, ast.Name):
            used_names.add(node.id)

        for child in ast.iter_child_nodes(node):
            _walk_non_import(child)

    _walk_non_import(tree)
    return {
        "valid_syntax": True,
        "syntax_error": None,
        "imported_symbol_map": imported_symbol_map,
        "imported_modules": imported_modules,
        "used_names": used_names,
        "called_names": called_names,
    }


def _inspect_non_python_caller_regex(source: str, rel_path: str) -> dict[str, Any]:
    """Inspect .ts/.js/.rs/.go/.cs caller file using comment-stripped regex call/reference patterns."""
    no_block_comments = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    import_lines: list[str] = []
    exec_lines: list[str] = []
    for raw_line in no_block_comments.splitlines():
        line = re.sub(r"//.*$", "", raw_line).strip()
        if not line:
            continue
        if line.startswith(("import ", "from ", "export type ", "type ", "use ", "package ")):
            import_lines.append(line)
        else:
            exec_lines.append(line)
    return {
        "import_blob": "\n".join(import_lines),
        "exec_blob": "\n".join(exec_lines),
    }


def verify_wiring(
    root_dir: str,
    target_files: list[str],
    wiring_files: list[str],
    required_symbols: list[str],
) -> dict[str, Any]:
    """Verify `target_files` exist and `wiring_files` actively invoke/reference `required_symbols` via AST/call checks."""
    root = os.path.abspath(root_dir)
    errors: list[str] = []
    missing_target_files: list[str] = []
    unused_imports: list[str] = []

    for tf in target_files:
        abs_tf = tf if os.path.isabs(tf) else os.path.join(root, tf)
        if not os.path.isfile(abs_tf):
            missing_target_files.append(tf)
            errors.append(f"Target implementation file does not exist: `{tf}`")

    if not wiring_files:
        return {
            "passed": len(errors) == 0,
            "missing_target_files": missing_target_files,
            "unused_imports": unused_imports,
            "errors": errors,
        }

    py_callers: dict[str, dict[str, Any]] = {}
    other_callers: dict[str, dict[str, Any]] = {}

    for wf in wiring_files:
        abs_wf = wf if os.path.isabs(wf) else os.path.join(root, wf)
        if not os.path.isfile(abs_wf):
            errors.append(f"Wiring/entrypoint file does not exist: `{wf}`")
            continue
        try:
            src = Path(abs_wf).read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            errors.append(f"Unable to read wiring file `{wf}`: {exc}")
            continue

        ext = os.path.splitext(wf)[1].lower()
        if ext == ".py":
            info = _inspect_python_caller_ast(src, wf)
            if not info["valid_syntax"]:
                errors.append(info["syntax_error"])
            else:
                py_callers[wf] = info
        else:
            other_callers[wf] = _inspect_non_python_caller_regex(src, wf)

    if not py_callers and not other_callers:
        return {
            "passed": len(errors) == 0,
            "missing_target_files": missing_target_files,
            "unused_imports": unused_imports,
            "errors": errors,
        }

    # 1. Check target module stems are wired when no explicit symbols or alongside symbols
    for tf in target_files:
        stem = os.path.splitext(os.path.basename(tf))[0]
        if stem in ("__init__", "index", "main", "app", "cli", "server"):
            continue
        stem_imported = False
        stem_used = False
        for info in py_callers.values():
            bound = info["imported_symbol_map"].get(stem, stem)
            if stem in info["imported_modules"] or stem in info["imported_symbol_map"]:
                stem_imported = True
            if (
                stem in info["used_names"]
                or bound in info["used_names"]
                or any(s in info["used_names"] or info["imported_symbol_map"].get(s, s) in info["used_names"] for s in required_symbols)
            ):
                stem_used = True
        for oinfo in other_callers.values():
            if re.search(rf"\b{re.escape(stem)}\b", oinfo["import_blob"]):
                stem_imported = True
            if re.search(rf"\b{re.escape(stem)}\b", oinfo["exec_blob"]) or any(
                re.search(rf"\b{re.escape(s)}\b", oinfo["exec_blob"]) for s in required_symbols
            ):
                stem_used = True

        if not stem_imported and not stem_used:
            errors.append(
                f"Target module `{tf}` (`{stem}`) is not imported or referenced in AST/call expressions of wiring file(s) "
                f"`{', '.join(wiring_files)}`."
            )
        elif stem_imported and not stem_used and not required_symbols:
            unused_imports.append(stem)
            errors.append(
                f"unused_import: Target module `{tf}` (`{stem}`) is imported in `{', '.join(wiring_files)}` "
                f"but never used in any executable AST expression/statement."
            )

    # 2. Check each required symbol via AST (for .py) and regex call-patterns (for .ts/.js/.rs/.go/.cs)
    for sym in required_symbols:
        sym_imported_in: list[str] = []
        sym_used_in: list[str] = []

        for wf, info in py_callers.items():
            bound = info["imported_symbol_map"].get(sym, sym)
            if sym in info["imported_symbol_map"] or sym in info["imported_modules"]:
                sym_imported_in.append(wf)
            if sym in info["used_names"] or bound in info["used_names"] or sym in info["called_names"] or bound in info["called_names"]:
                sym_used_in.append(wf)

        for wf, oinfo in other_callers.items():
            if re.search(rf"\b{re.escape(sym)}\b", oinfo["import_blob"]):
                sym_imported_in.append(wf)
            call_or_ref_re = re.compile(rf"\b{re.escape(sym)}\s*(?:\(|\.|<|\[|,|\)|;|:|=)|\bnew\s+{re.escape(sym)}\b")
            if call_or_ref_re.search(oinfo["exec_blob"]) or re.search(rf"\b{re.escape(sym)}\b", oinfo["exec_blob"]):
                sym_used_in.append(wf)

        if not sym_used_in:
            if sym_imported_in:
                unused_imports.append(sym)
                errors.append(
                    f"unused_import: Symbol `{sym}` is imported in `{', '.join(sym_imported_in)}` "
                    f"but NEVER invoked, instantiated, or referenced in any executable AST node outside imports."
                )
            else:
                errors.append(
                    f"Broken AST/call-site wiring: Required symbol `{sym}` is neither imported nor used in "
                    f"wiring file(s) `{', '.join(wiring_files)}`."
                )

    return {
        "passed": len(errors) == 0,
        "missing_target_files": missing_target_files,
        "unused_imports": unused_imports,
        "errors": errors,
    }


def run_command_gate(
    cmd: str,
    cwd: str,
    expect_output: str = "",
    pass_hat_k: int = 1,
    timeout: int = 120,
) -> dict[str, Any]:
    if not cmd.strip():
        return {"passed": True, "runs": 0, "passed_runs": 0, "exit_code": 0, "errors": []}

    k = max(1, int(pass_hat_k))
    passed_runs = 0
    errors: list[str] = []
    last_stdout = ""
    last_stderr = ""
    last_code = 0

    for trial in range(1, k + 1):
        try:
            res = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            last_code = res.returncode
            last_stdout = (res.stdout or "").strip()
            last_stderr = (res.stderr or "").strip()
            combined = f"{last_stdout}\n{last_stderr}"

            if res.returncode != 0:
                tail = (last_stderr or last_stdout).splitlines()[-1:]
                snippet = tail[0][:200] if tail else f"exit code {res.returncode}"
                errors.append(f"Trial {trial}/{k} of `{cmd}` failed (exit {res.returncode}): {snippet}")
                continue

            if expect_output:
                if not re.search(expect_output, combined, re.MULTILINE):
                    errors.append(
                        f"Trial {trial}/{k} of `{cmd}` exited 0, but output did NOT match expected pattern "
                        f"`{expect_output}`. Actual stdout snippet: `{last_stdout[:200]}`"
                    )
                    continue

            passed_runs += 1
        except subprocess.TimeoutExpired:
            last_code = 124
            errors.append(f"Trial {trial}/{k} of `{cmd}` timed out after {timeout}s.")
        except Exception as exc:
            last_code = 1
            errors.append(f"Trial {trial}/{k} of `{cmd}` errored: {exc}")

    return {
        "passed": passed_runs == k,
        "runs": k,
        "passed_runs": passed_runs,
        "exit_code": 0 if passed_runs == k else (last_code or 1),
        "stdout_snippet": last_stdout[-400:],
        "stderr_snippet": last_stderr[-400:],
        "errors": errors,
    }


def evaluate_gate(
    blocking_fails: list[str],
    advisory_warns: list[str] | None = None,
    spec_verdict: str = "PASS",
    critical_count: int = 0,
    important_count: int = 0,
    minor_count: int = 0,
) -> dict[str, Any]:
    """Evaluate the Two-Verdict categorical gate directly from categories and defect counts."""
    advisory_list = list(advisory_warns or [])
    norm_verdict = (spec_verdict or "PASS").upper().strip()
    blocking_reasons: list[str] = []

    if len(blocking_fails) > 0:
        blocking_reasons.append(f"blocking_fails={len(blocking_fails)}")
    if norm_verdict != "PASS":
        blocking_reasons.append(f"spec_verdict={norm_verdict}")
    if critical_count > 0:
        blocking_reasons.append(f"critical_count={critical_count}")
    if important_count > 0:
        blocking_reasons.append(f"important_count={important_count}")

    passed_gate = len(blocking_reasons) == 0
    verdict = "PASS" if passed_gate else "FAIL"
    return {
        "verdict": verdict,
        "passed_gate": passed_gate,
        "spec_verdict": norm_verdict,
        "blocking_reasons": blocking_reasons,
        "counts": {
            "blocking_fails": len(blocking_fails),
            "advisory_warns": len(advisory_list),
            "critical": int(critical_count),
            "important": int(important_count),
            "minor": int(minor_count),
        },
        "minor_deferred_count": int(minor_count),
    }


compute_hard_cap_score = evaluate_gate


def init_manifest(
    goal: str = "",
    outcome_cmd: str = "",
    expect_output: str = "",
    entrypoints: list[str] | None = None,
    pass_hat_k: int = 1,
    seed_default_tasks: bool = True,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Initialize `.swarm/goal_loop.json`, `.swarm/ledger.md`, and `.swarm/deferred_minor_ledger.md`."""
    ensure_ledger_files(cwd=cwd)
    state = load_goal_state(cwd=cwd)
    base_sha = _detect_git_head(cwd=cwd)
    # Starting point for `--verify-goal`: on an existing codebase only what changed since here is judged.
    state.setdefault("base_sha", base_sha)

    if goal and goal != "DEFAULT":
        state["goal"] = goal
    elif not state.get("goal"):
        state["goal"] = DEFAULT_MANIFEST["goal"]

    if outcome_cmd:
        state["outcome_cmd"] = outcome_cmd
    if expect_output:
        state["expect_output"] = expect_output
    if entrypoints is not None and len(entrypoints) > 0:
        state["entrypoints"] = [e.strip() for e in entrypoints if e.strip()]
    elif not state.get("entrypoints"):
        state["entrypoints"] = list(DEFAULT_MANIFEST["entrypoints"])

    state["pass_hat_k"] = max(1, int(pass_hat_k))
    state.setdefault("non_negotiables", list(DEFAULT_MANIFEST["non_negotiables"]))
    state["status"] = "IN_PROGRESS"
    state["can_emit_goal_complete"] = False

    if seed_default_tasks and not state.get("tasks"):
        default_tasks = copy.deepcopy(DEFAULT_MANIFEST["tasks"])
        for tid, tdata in default_tasks.items():
            tdata["base_sha"] = base_sha
            tdata["created_at"] = now_iso()
            state["tasks"][tid] = _normalize_task_record(tid, tdata, default_base_sha=base_sha)

    save_goal_state(state, cwd=cwd)
    append_ledger_entry(f"Initialized Goal-Loop manifest (`base_sha={base_sha[:12]}`). Goal: {state['goal']}", cwd=cwd)
    return state


def init_goal(
    goal: str,
    outcome_cmd: str = "",
    expect_output: str = "",
    entrypoints: list[str] | None = None,
    pass_hat_k: int = 1,
    cwd: str | None = None,
) -> dict[str, Any]:
    return init_manifest(
        goal=goal,
        outcome_cmd=outcome_cmd,
        expect_output=expect_output,
        entrypoints=entrypoints,
        pass_hat_k=pass_hat_k,
        seed_default_tasks=False,
        cwd=cwd,
    )


def add_task(
    task_id: str,
    title: str,
    objective: str,
    validation_cmd: str = "",
    outcome_cmd: str = "",
    expect_output: str = "",
    wiring_target: str = "",
    target_files: list[str] | None = None,
    wiring_files: list[str] | None = None,
    required_symbols: list[str] | None = None,
    review_focus: list[str] | None = None,
    base_sha: str = "",
    depends_on: list[str] | None = None,
    spec_ref: str = "",
    cwd: str | None = None,
) -> dict[str, Any]:
    state = load_goal_state(cwd=cwd)
    tasks = state.setdefault("tasks", {})
    existing = tasks.get(task_id, {})
    # An existing task keeps its objective unless a new one is given.
    objective = objective or existing.get("objective") or title
    detected_sha = base_sha or existing.get("base_sha") or _detect_git_head(cwd=cwd)
    t_files = [f.strip() for f in (target_files or existing.get("target_files") or []) if f.strip()]
    w_files = [f.strip() for f in (wiring_files or existing.get("wiring_files") or []) if f.strip()]
    r_syms = [s.strip() for s in (required_symbols or existing.get("required_symbols") or []) if s.strip()]
    r_focus = review_focus if review_focus is not None else existing.get("review_focus", [])

    raw = {
        **existing,
        "id": task_id,
        "task_id": task_id,
        "title": title,
        "description": objective,
        "objective": objective,
        "base_sha": detected_sha,
        "target_files": t_files,
        "wiring_files": w_files,
        "required_symbols": r_syms,
        "wiring_contract": {
            "must_be_called_by": w_files,
            "exported_symbols": r_syms,
        },
        "verification_cmd": validation_cmd or existing.get("verification_cmd", ""),
        "validation_cmd": validation_cmd or existing.get("validation_cmd", ""),
        "outcome_cmd": outcome_cmd or existing.get("outcome_cmd", ""),
        "expect_output": expect_output or existing.get("expect_output", ""),
        "wiring_target": wiring_target or existing.get("wiring_target", ""),
        "review_focus": r_focus,
        "depends_on": list(depends_on) if depends_on is not None else existing.get("depends_on", []),
        "spec_ref": spec_ref or existing.get("spec_ref", ""),
        "status": existing.get("status", "PENDING"),
        "created_at": existing.get("created_at", now_iso()),
        "subtasks": existing.get("subtasks", {}),
    }
    tasks[task_id] = _normalize_task_record(task_id, raw, default_base_sha=detected_sha)
    state["status"] = "IN_PROGRESS"
    state["can_emit_goal_complete"] = False
    save_goal_state(state, cwd=cwd)
    return tasks[task_id]


def add_subtask(
    task_id: str,
    subtask_id: str,
    title: str,
    objective: str,
    target_files: list[str] | None = None,
    wiring_files: list[str] | None = None,
    required_symbols: list[str] | None = None,
    validation_cmd: str = "",
    outcome_cmd: str = "",
    expect_output: str = "",
    review_focus: list[str] | None = None,
    cwd: str | None = None,
) -> dict[str, Any]:
    state = load_goal_state(cwd=cwd)
    tasks = state.setdefault("tasks", {})
    if task_id not in tasks:
        tasks[task_id] = _normalize_task_record(
            task_id,
            {
                "task_id": task_id,
                "title": f"Task {task_id}",
                "objective": objective,
                "status": "IN_PROGRESS",
                "created_at": now_iso(),
                "subtasks": {},
            },
            default_base_sha=_detect_git_head(cwd=cwd),
        )
    subtasks = tasks[task_id].setdefault("subtasks", {})
    existing = subtasks.get(subtask_id, {})
    subtasks[subtask_id] = {
        "subtask_id": subtask_id,
        "task_id": task_id,
        "title": title,
        "objective": objective,
        "target_files": [f.strip() for f in (target_files or []) if f.strip()],
        "wiring_files": [f.strip() for f in (wiring_files or []) if f.strip()],
        "required_symbols": [s.strip() for s in (required_symbols or []) if s.strip()],
        "validation_cmd": validation_cmd,
        "outcome_cmd": outcome_cmd,
        "expect_output": expect_output,
        "review_focus": review_focus or existing.get("review_focus", []),
        "status": existing.get("status", "PENDING"),
        "iterations": existing.get("iterations", 0),
        "last_errors": existing.get("last_errors", []),
        "verified_at": existing.get("verified_at"),
    }
    state["status"] = "IN_PROGRESS"
    state["can_emit_goal_complete"] = False
    save_goal_state(state, cwd=cwd)
    return subtasks[subtask_id]


def _pending_dependents(tasks: dict[str, Any], task_id: str) -> list[str]:
    """Unfinished tasks that depend on `task_id`, directly or transitively."""
    found: set[str] = set()
    frontier = {task_id}
    while frontier:
        nxt = {
            tid
            for tid, t in tasks.items()
            if tid not in found and frontier & {str(d) for d in (t.get("depends_on") or [])}
        }
        found |= nxt
        frontier = nxt
    return sorted(
        tid for tid in found if tasks[tid].get("status") not in DONE_TASK_STATUSES | {"SUPERSEDED"}
    )


def audit_task(
    task_id: str,
    cwd: str | None = None,
    run_cmd: bool = True,
) -> dict[str, Any]:
    """Run deterministic invariant checks on a Task (`BLOCKING_FAIL` vs `ADVISORY_WARN`) and evaluate categorical gate."""
    root = os.path.abspath(cwd or os.getcwd())
    state = load_goal_state(cwd=root)
    tasks = state.get("tasks", {})
    if task_id not in tasks:
        return {
            "task_id": task_id,
            "status": "ERROR",
            "verdict": "FAIL",
            "passed": False,
            "blocking_fails": [f"Task `{task_id}` not found in `.swarm/goal_loop.json`."],
            "advisory_warns": [],
        }

    task = tasks[task_id]
    blocking_fails: list[str] = []
    advisory_warns: list[str] = []

    target_files = list(task.get("target_files", []))
    wiring_files = list(task.get("wiring_files") or task.get("wiring_contract", {}).get("must_be_called_by", []))
    required_symbols = list(
        task.get("required_symbols") or task.get("wiring_contract", {}).get("exported_symbols", [])
    )

    # Also aggregate from subtasks if parent task delegates files to subtasks
    for sub in task.get("subtasks", {}).values():
        for tf in sub.get("target_files", []):
            if tf not in target_files:
                target_files.append(tf)
        for wf in sub.get("wiring_files", []):
            if wf not in wiring_files:
                wiring_files.append(wf)
        for rs in sub.get("required_symbols", []):
            if rs not in required_symbols:
                required_symbols.append(rs)

    # 1. Check Missing Target Files + AST/Call-Site Wiring
    wiring_res = verify_wiring(
        root_dir=root,
        target_files=target_files,
        wiring_files=wiring_files,
        required_symbols=required_symbols,
    )
    if not wiring_res["passed"]:
        for err in wiring_res["errors"]:
            blocking_fails.append(f"[WIRING/TARGET] {err}")

    # 2. Check Stubs/Placeholders/Synthetic Returns (`BLOCKING_FAIL`) & Broad Except / `any` (`ADVISORY_WARN`)
    scan_targets = list(dict.fromkeys(target_files + wiring_files))
    existing_scan_targets = [
        tf for tf in scan_targets if os.path.isfile(tf if os.path.isabs(tf) else os.path.join(root, tf))
    ]
    auth_res = audit_authenticity(
        root_dir=root,
        target_files=existing_scan_targets if existing_scan_targets else None,
        entrypoints=state.get("entrypoints", []),
        check_orphan_modules=bool(existing_scan_targets),
    )
    changes = _git_changes(root, task.get("base_sha"))
    if changes is not None:
        auth_res = restrict_to_changes(auth_res, changes)
    for item in auth_res.get("placeholder_findings", []):
        blocking_fails.append(f"[STUB/PLACEHOLDER:{item['kind']} in {item['file']}:{item['line']}] {item['detail']}")
    for item in auth_res.get("synthetic_findings", []):
        blocking_fails.append(f"[SYNTHETIC/MOCK:{item['kind']} in {item['file']}:{item['line']}] {item['detail']}")
    # A module built ahead of the task that integrates it (parallel workers on a locked contract) is
    # not wired yet by design. Defer the finding to the dependent tasks; their audits and the final
    # `--verify-goal` orphan scan still enforce the wiring.
    integrators = _pending_dependents(tasks, task_id)
    for item in auth_res.get("unwired_findings", []):
        if integrators:
            advisory_warns.append(
                f"[UNWIRED_MODULE deferred to {', '.join(integrators)} in {item['file']}] {item['detail']}"
            )
        else:
            blocking_fails.append(f"[UNWIRED_MODULE in {item['file']}] {item['detail']}")
    for item in auth_res.get("advisory_findings", []):
        advisory_warns.append(f"[ADVISORY_WARN in {item['file']}:{item['line']}] {item['detail']}")

    # 3. Run verification_cmd (`exit_code != 0` -> `BLOCKING_FAIL`)
    v_cmd = task.get("verification_cmd") or task.get("validation_cmd") or ""
    cmd_res: dict[str, Any] = {"passed": True, "exit_code": 0, "errors": []}
    if run_cmd and v_cmd:
        cmd_res = run_command_gate(v_cmd, cwd=root)
        if not cmd_res["passed"]:
            for err in cmd_res["errors"]:
                blocking_fails.append(f"[VERIFICATION_CMD_FAILED] {err}")

    # 4. Run task outcome_cmd if configured
    out_cmd = task.get("outcome_cmd") or ""
    if run_cmd and out_cmd:
        out_res = run_command_gate(out_cmd, cwd=root, expect_output=task.get("expect_output", ""))
        if not out_res["passed"]:
            for err in out_res["errors"]:
                blocking_fails.append(f"[OUTCOME_CMD_FAILED] {err}")

    inferred_spec_verdict = "PASS" if len(blocking_fails) == 0 else "FAIL"
    gate = evaluate_gate(
        blocking_fails=blocking_fails,
        advisory_warns=advisory_warns,
        spec_verdict=inferred_spec_verdict,
        critical_count=int(task.get("critical_count") or 0),
        important_count=int(task.get("important_count") or 0),
        minor_count=int(task.get("minor_count") or 0),
    )

    task["blocking_fails"] = blocking_fails
    task["advisory_warns"] = advisory_warns
    task["last_errors"] = blocking_fails
    task["gate_verdict"] = gate["verdict"]
    task["audited_at"] = now_iso()
    save_goal_state(state, cwd=root)

    return {
        "task_id": task_id,
        "title": task.get("title", task_id),
        "verdict": gate["verdict"],
        "passed": gate["passed_gate"],
        "spec_verdict": gate["spec_verdict"],
        "blocking_reasons": gate["blocking_reasons"],
        "blocking_fails": blocking_fails,
        "advisory_warns": advisory_warns,
        "wiring": wiring_res,
        "authenticity": auth_res["counts"],
        "verification_cmd": v_cmd or None,
        "verification_exit_code": cmd_res.get("exit_code", 0),
    }


def _record_error(task_id: str, message: str) -> dict[str, Any]:
    return {"task_id": task_id, "status": "ERROR", "passed": False, "errors": [message]}


def _review_passed(task: dict[str, Any]) -> bool:
    """True when the reviewer verdict passed (PASS, 0 Critical, 0 Important) or an OVERRIDE ruling settled it."""
    if "review_passed" in task:
        return bool(task["review_passed"])
    # Manifests recorded before `review_passed` existed: derive it from the recorded verdict.
    if task.get("status") == "COMPLETED_WITH_RULING" and task.get("ruling"):
        return True
    return (
        str(task.get("spec_verdict", "")).upper() == "PASS"
        and int(task.get("critical_count") or 0) == 0
        and int(task.get("important_count") or 0) == 0
    )


def record_task(
    task_id: str,
    spec_verdict: str | None = None,
    critical_count: int = 0,
    important_count: int = 0,
    minor_count: int = 0,
    ruling: str = "",
    notes: str = "",
    cwd: str | None = None,
    run_audit: bool = False,
    ruling_type: str = "",
    superseded_by: list[str] | None = None,
    review_source: str = "reviewer",
) -> dict[str, Any]:
    """Record the reviewer's Two-Verdict result (and optional Round 5 Breaker ruling) on top of the audit.

    The reviewer verdict can only add failures: BLOCKING_FAILs from the latest `audit_task` always count, and
    only a fresh audit of fixed code clears them. The audit runs here if the task was never audited.
    `review_source` records whether a separate reviewer subagent or the orchestrator's self-check produced it.
    """
    if review_source not in REVIEW_SOURCES:
        return _record_error(task_id, f"review_source must be one of {', '.join(REVIEW_SOURCES)}")
    root = os.path.abspath(cwd or os.getcwd())
    ensure_ledger_files(cwd=root)
    state = load_goal_state(cwd=root)
    tasks = state.get("tasks", {})
    if task_id not in tasks:
        return _record_error(task_id, f"Task `{task_id}` not found in `.swarm/goal_loop.json`.")

    ruling_clean = ruling.strip()
    ruling_kind = (ruling_type or "").strip().upper()
    successors = [str(s).strip() for s in (superseded_by or []) if str(s).strip()]
    if ruling_clean and ruling_kind not in RULING_TYPES:
        return _record_error(task_id, f"`--ruling` needs `--ruling-type` ({', '.join(RULING_TYPES)}).")
    if ruling_kind and not ruling_clean:
        return _record_error(task_id, "`--ruling-type` needs `--ruling \"<decision> — <why> — <cost if wrong>\"`.")
    if ruling_kind == "SPLIT_TASK":
        unknown = [s for s in successors if s not in tasks or s == task_id]
        if not successors or unknown:
            detail = f" (unknown: {', '.join(unknown)})" if unknown else ""
            return _record_error(task_id, f"SPLIT_TASK needs `--superseded-by` naming other existing task IDs{detail}.")

    if run_audit or not tasks[task_id].get("audited_at"):
        audit_task(task_id, cwd=root, run_cmd=True)
        state = load_goal_state(cwd=root)
    task = state["tasks"][task_id]
    blocking_fails = list(task.get("blocking_fails", []))
    advisory_warns = list(task.get("advisory_warns", []))

    if ruling_kind == "OVERRIDE" and blocking_fails:
        return _record_error(
            task_id,
            "Rulings cannot override deterministic BLOCKING_FAILs; fix the code and re-run `--audit-task`: "
            + "; ".join(blocking_fails[:3]),
        )

    effective_spec_verdict = spec_verdict.upper().strip() if spec_verdict else "UNVERIFIABLE"
    gate = evaluate_gate(
        blocking_fails=blocking_fails,
        advisory_warns=advisory_warns,
        spec_verdict=effective_spec_verdict,
        critical_count=critical_count,
        important_count=important_count,
        minor_count=minor_count,
    )
    review_passed = effective_spec_verdict == "PASS" and critical_count == 0 and important_count == 0

    task["iterations"] = int(task.get("iterations", 0)) + 1
    task["spec_verdict"] = effective_spec_verdict
    task["critical_count"] = int(critical_count)
    task["important_count"] = int(important_count)
    task["minor_count"] = int(minor_count)
    task["gate_verdict"] = gate["verdict"]
    task["review_passed"] = review_passed

    minor_ledger_path = None
    if minor_count > 0:
        minor_ledger_path = append_deferred_minor(
            task_id=task_id,
            count=minor_count,
            notes=notes,
            cwd=root,
        )

    ledger_path = resolve_ledger_md(cwd=root, create_dir=True)
    verdict_summary = (
        f"spec_verdict={effective_spec_verdict}, critical={critical_count}, important={important_count}, "
        f"blocking_fails={len(blocking_fails)}, gate={gate['verdict']}, review_source={review_source}"
    )
    if ruling_kind:
        formatted_ruling = ruling_clean if ruling_clean.startswith("Ruling:") else f"Ruling: {ruling_clean}"
        task["ruling"] = ruling_clean
        task["ruling_type"] = ruling_kind
        if ruling_kind == "OVERRIDE":
            task["status"] = "COMPLETED_WITH_RULING"
            task["review_passed"] = True
            task["gate_verdict"] = "PASS"
            task["verified_at"] = now_iso()
            passed = True
        elif ruling_kind == "SPLIT_TASK":
            task["status"] = "SUPERSEDED"
            task["superseded_by"] = successors
            passed = False
        else:
            task["status"] = "BLOCKED_BY_RULING"
            passed = False
        successor_note = f" (superseded by {', '.join(successors)})" if successors else ""
        append_ledger_entry(
            f"Task `{task_id}`: {ruling_kind} ruling -> {task['status']}{successor_note} — {formatted_ruling} "
            f"[{verdict_summary}]",
            cwd=root,
        )
    else:
        task["ruling"] = None
        task["ruling_type"] = None
        task.pop("superseded_by", None)
        if gate["passed_gate"]:
            task["status"] = "VERIFIED_COMPLETE"
            task["verified_at"] = now_iso()
            passed = True
            append_ledger_entry(
                f"Task `{task_id}`: complete ({verdict_summary}, minor_deferred={minor_count})",
                cwd=root,
            )
        else:
            task["status"] = "NEEDS_ITERATION"
            passed = False
            append_ledger_entry(
                f"Task `{task_id}`: fix round {task['iterations']}/5 required "
                f"({verdict_summary}, reasons={', '.join(gate['blocking_reasons'])})",
                cwd=root,
            )

    entry = {
        "timestamp": now_iso(),
        "task_id": task_id,
        "iteration": task["iterations"],
        "status": task["status"],
        "verdict": task["gate_verdict"],
        "passed": passed,
        "spec_verdict": effective_spec_verdict,
        "review_passed": task["review_passed"],
        "critical_count": int(critical_count),
        "important_count": int(important_count),
        "minor_count": int(minor_count),
        "minor_deferred_to": minor_ledger_path,
        "blocking_reasons": gate["blocking_reasons"],
        "blocking_fails": blocking_fails,
        "advisory_warns": advisory_warns,
        "ruling": task.get("ruling"),
        "ruling_type": task.get("ruling_type"),
        "superseded_by": task.get("superseded_by"),
        "ledger_path": ledger_path,
        "review_source": review_source,
        "notes": notes,
    }
    task.setdefault("history", []).append(entry)
    save_goal_state(state, cwd=root)
    return entry


def run_preflight(cwd: str | None = None, as_json: bool = False) -> dict[str, Any]:
    """Scan all tasks in `.swarm/goal_loop.json` and output a Pre-Flight Conflict & Dependency Table.

    Fails on missing `target_files` / verification commands, `UNRESOLVED_DEPENDENCY`, and
    `OVERLAPPING_TARGET_FILES` between tasks that can run in parallel (both unfinished, same epoch,
    neither depending on the other). Overlaps between serialized tasks are reported but do not fail.
    """
    root = os.path.abspath(cwd or os.getcwd())
    ensure_ledger_files(cwd=root)
    state = load_goal_state(cwd=root)
    tasks = state.get("tasks", {})
    task_ids = list(tasks.keys())
    inactive_statuses = DONE_TASK_STATUSES | {"SUPERSEDED"}

    overlaps: list[dict[str, Any]] = []
    task_checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    failures: list[str] = []

    def dependencies(tid: str) -> set[str]:
        """Transitive `depends_on` closure of a task."""
        seen: set[str] = set()
        stack = [str(d) for d in (tasks.get(tid, {}).get("depends_on") or [])]
        while stack:
            dep = stack.pop()
            if dep in seen or dep not in tasks:
                continue
            seen.add(dep)
            stack.extend(str(d) for d in (tasks[dep].get("depends_on") or []))
        return seen

    def can_run_in_parallel(tid_a: str, tid_b: str) -> bool:
        ta, tb = tasks[tid_a], tasks[tid_b]
        if ta.get("status") in inactive_statuses or tb.get("status") in inactive_statuses:
            return False
        if str(ta.get("epoch", 1)) != str(tb.get("epoch", 1)):
            return False
        return tid_a not in dependencies(tid_b) and tid_b not in dependencies(tid_a)

    for tid in task_ids:
        t = tasks[tid]
        t_files = list(t.get("target_files", []))
        w_files = list(t.get("wiring_files") or t.get("wiring_contract", {}).get("must_be_called_by", []))
        v_cmd = t.get("verification_cmd") or t.get("validation_cmd") or ""
        r_focus = t.get("review_focus") or []
        unknown_deps = [str(d) for d in (t.get("depends_on") or []) if str(d) not in tasks]
        missing_callers = [w for w in w_files if not os.path.isfile(w if os.path.isabs(w) else os.path.join(root, w))]

        row_issues: list[str] = []
        if not t_files:
            row_issues.append("MISSING `target_files`")
            failures.append(f"Task `{tid}` is missing `target_files`.")
        if not v_cmd:
            row_issues.append("MISSING_VERIFICATION_CMD")
            failures.append(f"Task `{tid}` is missing `verification_commands`.")
        if unknown_deps:
            row_issues.append(f"UNRESOLVED_DEPENDENCY: {', '.join(unknown_deps)}")
            failures.append(f"Task `{tid}` depends on unknown task(s): {', '.join(unknown_deps)}.")
        if missing_callers:
            row_issues.append(f"WARN: MISSING_CALLER_FILE: {', '.join(missing_callers)}")
            warnings.append(f"Task `{tid}` caller file(s) not on disk yet: {', '.join(missing_callers)}.")
        if not r_focus:
            row_issues.append("WARN: missing `review_focus`")
            warnings.append(f"Task `{tid}` is missing `review_focus` (implied failure modes to prove in tests).")

        task_checks.append(
            {
                "task_id": tid,
                "title": t.get("title", tid),
                "target_files": t_files,
                "must_be_called_by": w_files,
                "verification_cmd": v_cmd or None,
                "review_focus_count": len(r_focus),
                "status": "OK" if not row_issues else "; ".join(row_issues),
            }
        )

    for i in range(len(task_ids)):
        for j in range(i + 1, len(task_ids)):
            tid_a, tid_b = task_ids[i], task_ids[j]
            ta, tb = tasks[tid_a], tasks[tid_b]
            a_targets = set(ta.get("target_files", []))
            b_targets = set(tb.get("target_files", []))
            a_callers = set(ta.get("wiring_files") or ta.get("wiring_contract", {}).get("must_be_called_by", []))
            b_callers = set(tb.get("wiring_files") or tb.get("wiring_contract", {}).get("must_be_called_by", []))

            shared_targets = sorted(a_targets & b_targets)
            shared_callers = sorted(a_callers & b_callers)
            cross_touch = sorted((a_targets & b_callers) | (b_targets & a_callers))

            if shared_targets or shared_callers or cross_touch:
                parallel = can_run_in_parallel(tid_a, tid_b)
                blocking = bool(shared_targets) and parallel
                if blocking:
                    recommendation = (
                        "OVERLAPPING_TARGET_FILES: serialize with `depends_on`, or move the shared code into a "
                        "contract/foundation task before parallel dispatch"
                    )
                    failures.append(
                        f"Parallel tasks `{tid_a}` and `{tid_b}` both modify {', '.join(shared_targets)}."
                    )
                elif shared_targets:
                    recommendation = "Serialized by `depends_on`, epoch, or status; no action needed"
                else:
                    recommendation = "Coordinate entrypoint merge via `/merge-surgeon`"
                overlaps.append(
                    {
                        "task_pair": f"{tid_a} <-> {tid_b}",
                        "parallel": parallel,
                        "blocking": blocking,
                        "shared_target_files": shared_targets,
                        "shared_caller_files": shared_callers,
                        "producer_consumer_files": cross_touch,
                        "recommendation": recommendation,
                    }
                )

    md_lines = [
        "# Pre-Flight Conflict & Dependency Scan",
        "",
        "## 1. Per-Task Readiness & Review-Focus Table",
        "",
        "| Task ID | Title | Target Files | Must Be Called By | Verification Cmd | Review Focus Items | Pre-Flight Check |",
        "| :--- | :--- | :--- | :--- | :--- | :---: | :--- |",
    ]
    for tc in task_checks:
        tf_str = ", ".join(f"`{x}`" for x in tc["target_files"]) or "_None_"
        wf_str = ", ".join(f"`{x}`" for x in tc["must_be_called_by"]) or "_None_"
        vc_str = f"`{tc['verification_cmd']}`" if tc["verification_cmd"] else "_MISSING_"
        md_lines.append(
            f"| `{tc['task_id']}` | {tc['title']} | {tf_str} | {wf_str} | {vc_str} | "
            f"{tc['review_focus_count']} | {tc['status']} |"
        )

    md_lines.extend(
        [
            "",
            "## 2. Pairwise File & Interface Overlap Table",
            "",
            "| Task Pair | Overlapping Target Files | Shared Caller Files | Producer/Consumer Link | Orchestrator Action |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    if not overlaps:
        md_lines.append("| _All Task Pairs_ | _None_ | _None_ | _None_ | Clean — safe for isolated dispatch |")
    else:
        for ov in overlaps:
            st_s = ", ".join(f"`{x}`" for x in ov["shared_target_files"]) or "_None_"
            sc_s = ", ".join(f"`{x}`" for x in ov["shared_caller_files"]) or "_None_"
            pc_s = ", ".join(f"`{x}`" for x in ov["producer_consumer_files"]) or "_None_"
            md_lines.append(f"| `{ov['task_pair']}` | {st_s} | {sc_s} | {pc_s} | {ov['recommendation']} |")

    if failures:
        md_lines.extend(["", "## 3. Pre-Flight Failures (Fix Before Dispatch)", ""])
        md_lines.extend(f"- ❌ {f}" for f in failures)

    markdown_table = "\n".join(md_lines) + "\n"
    preflight_path = os.path.join(root, ".swarm", "preflight.md")
    with open(preflight_path, "w", encoding="utf-8") as f:
        f.write(markdown_table)
    append_ledger_entry(
        f"Pre-flight scan completed ({len(task_checks)} task(s), {len(overlaps)} overlap pair(s), "
        f"{len(failures)} failure(s), {len(warnings)} warning(s)). Table written to `.swarm/preflight.md`.",
        cwd=root,
    )

    return {
        "passed": not failures,
        "task_count": len(task_checks),
        "overlap_count": len(overlaps),
        "blocking_overlap_count": sum(1 for ov in overlaps if ov["blocking"]),
        "failures": failures,
        "warnings": warnings,
        "task_checks": task_checks,
        "overlaps": overlaps,
        "preflight_file": preflight_path,
        "markdown": markdown_table,
    }


def generate_task_brief(task_id: str, cwd: str | None = None) -> dict[str, Any]:
    """Extract a self-contained markdown brief to `.swarm/briefs/<TASK_ID>-brief.md` and print its path."""
    root = os.path.abspath(cwd or os.getcwd())
    state = load_goal_state(cwd=root)
    tasks = state.get("tasks", {})
    if task_id not in tasks:
        return {
            "status": "ERROR",
            "errors": [f"Task `{task_id}` not found in `.swarm/goal_loop.json`."],
        }

    task = tasks[task_id]
    briefs_dir = os.path.join(root, ".swarm", "briefs")
    reports_dir = os.path.join(root, ".swarm", "reports")
    os.makedirs(briefs_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)

    brief_path = os.path.join(briefs_dir, f"{task_id}-brief.md")
    report_path = os.path.join(reports_dir, f"{task_id}-report.md")

    target_files = task.get("target_files", [])
    wiring_files = task.get("wiring_files") or task.get("wiring_contract", {}).get("must_be_called_by", [])
    req_symbols = task.get("required_symbols") or task.get("wiring_contract", {}).get("exported_symbols", [])
    review_focus = task.get("review_focus", [])
    non_negotiables = state.get("non_negotiables") or DEFAULT_MANIFEST["non_negotiables"]

    lines = [
        f"# Task Brief: `{task_id}` — {task.get('title', task_id)}",
        "",
        "## 1. Task Description & Objective",
        f"{task.get('description') or task.get('objective') or task.get('title', '')}",
        "",
        f"- **Parent Project Goal:** {state.get('goal') or 'N/A'}",
        f"- **Recorded Base SHA (`base_sha`):** `{task.get('base_sha') or _detect_git_head(cwd=root)}`",
        f"- **Worker Detailed Report Output Path:** `{report_path}`",
    ]
    if task.get("spec_ref"):
        lines.append(f"- **Source Design (`spec_ref`):** `{task['spec_ref']}` — {SPEC_REF_NOTE}")
    lines += [
        "",
        "## 2. Target Files & AST Wiring Contract",
        f"- **Target Implementation Files (`target_files`):** {', '.join(f'`{x}`' for x in target_files) or '_None specified_'}",
        f"- **Must Be Called By (`wiring_contract.must_be_called_by`):** {', '.join(f'`{x}`' for x in wiring_files) or '_None specified_'}",
        f"- **Exported / Required Symbols (`wiring_contract.exported_symbols`):** {', '.join(f'`{x}`' for x in req_symbols) or '_Module-level wiring_'}",
        "",
        "## 3. Verification & Outcome Commands",
        f"- **Task Verification Command (`verification_cmd`):** `{task.get('verification_cmd') or task.get('validation_cmd') or 'N/A'}`",
    ]
    if task.get("outcome_cmd"):
        lines.append(f"- **Task Outcome Command (`outcome_cmd`):** `{task.get('outcome_cmd')}`")
    if task.get("expect_output"):
        lines.append(f"- **Expected Output Pattern:** `{task.get('expect_output')}`")

    lines.extend(
        [
            "",
            "## 4. Review Focus (Implied Failure Modes Your Tests MUST Prove)",
            "These items add to the specification; they never replace it. Where an item states a condition more "
            "narrowly than the spec, implement the spec's full condition.",
        ]
    )
    if review_focus:
        for idx, rf in enumerate(review_focus, start=1):
            lines.append(f"{idx}. {rf}")
    else:
        lines.append("1. Verify happy-path, boundary/degenerate inputs, and negative error handling with real assertions.")

    lines.extend(
        [
            "",
            "## 5. Global Non-Negotiables",
        ]
    )
    for nn in non_negotiables:
        lines.append(f"- {nn}")

    lines.extend(
        [
            "",
            "## 6. Subagent Return Contract (`< 15 lines` in chat)",
            f"Write your full implementation notes and test output to `{report_path}`, and return ONLY:",
            "- `Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT`",
            "- `Commits: <base_sha>..<head_sha>`",
            "- `Tests: <1-line verification command summary>`",
            "- `Concerns: <none or bulleted concerns>`",
            "",
        ]
    )

    with open(brief_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return {
        "status": "OK",
        "task_id": task_id,
        "brief_path": brief_path,
        "report_path": report_path,
    }


def generate_review_package(
    task_id: str,
    base_sha_override: str = "",
    cwd: str | None = None,
) -> dict[str, Any]:
    """Bundle `git log`, `git diff --stat`, `git diff -U10` (`<base>..HEAD`), and deterministic `audit_task` report."""
    root = os.path.abspath(cwd or os.getcwd())
    state = load_goal_state(cwd=root)
    tasks = state.get("tasks", {})
    if task_id not in tasks:
        return {
            "status": "ERROR",
            "errors": [f"Task `{task_id}` not found in `.swarm/goal_loop.json`."],
        }

    task = tasks[task_id]
    base_sha = base_sha_override or task.get("base_sha") or "HEAD"
    reviews_dir = os.path.join(root, ".swarm", "reviews")
    os.makedirs(reviews_dir, exist_ok=True)
    review_path = os.path.join(reviews_dir, f"{task_id}-review.diff.md")

    scoped_files = list(
        dict.fromkeys(
            list(task.get("target_files", []))
            + list(task.get("wiring_files") or task.get("wiring_contract", {}).get("must_be_called_by", []))
        )
    )
    existing_scoped = [f for f in scoped_files if os.path.exists(f if os.path.isabs(f) else os.path.join(root, f))]

    def _run_git(args_list: list[str]) -> tuple[int, str]:
        try:
            r = subprocess.run(
                ["git"] + args_list,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            return r.returncode, (r.stdout or "").strip()
        except Exception as exc:
            return 1, f"git execution error: {exc}"

    _, head_sha = _run_git(["rev-parse", "HEAD"])
    head_sha = head_sha or "HEAD"

    # Determine effective git range
    range_spec = f"{base_sha}..HEAD"

    # Tests the worker changed are the evidence for the Review Focus items, so a scoped
    # package includes them even though they are not target files.
    changed_tests: list[str] = []
    if existing_scoped:
        _, committed = _run_git(["diff", "--name-only", range_spec])
        _, uncommitted = _run_git(["diff", "--name-only", "HEAD"])
        _, untracked = _run_git(["ls-files", "--others", "--exclude-standard"])
        for name in dict.fromkeys((committed + "\n" + uncommitted + "\n" + untracked).splitlines()):
            if name and is_test_file(name) and name not in existing_scoped and os.path.exists(os.path.join(root, name)):
                changed_tests.append(name)
        existing_scoped = existing_scoped + changed_tests
    code_log, git_log_out = _run_git(["log", "--oneline", range_spec])
    if code_log != 0 or not git_log_out:
        _, git_log_out = _run_git(["log", "--oneline", "-n", "5"])

    path_args = ["--"] + existing_scoped if existing_scoped else []
    code_stat, diff_stat_out = _run_git(["diff", "--stat", range_spec] + path_args)
    if code_stat != 0 or not diff_stat_out:
        _, diff_stat_out = _run_git(["diff", "--stat", "HEAD"] + path_args)
        if not diff_stat_out:
            _, diff_stat_out = _run_git(["status", "--short"])

    code_diff, diff_u10_out = _run_git(["diff", "-U10", range_spec] + path_args)
    if code_diff != 0 or not diff_u10_out:
        _, diff_u10_out = _run_git(["diff", "-U10", "HEAD"] + path_args)

    # Run deterministic invariant audit for the review package
    invariant_report = audit_task(task_id, cwd=root, run_cmd=True)

    lines = [
        f"# Deterministic Review Package: `{task_id}` — {task.get('title', task_id)}",
        "",
        f"- **Base SHA:** `{base_sha}`",
        f"- **Head SHA:** `{head_sha}`",
        f"- **Scoped Files:** {', '.join(f'`{x}`' for x in scoped_files) or '_Full Repository_'}",
        f"- **Changed Test Files (included):** {', '.join(f'`{x}`' for x in changed_tests) or '_None_'}",
        f"- **Generated At:** `{now_iso()}`",
        f"- **Task Objective:** {task.get('objective') or task.get('title', task_id)}",
    ]
    if task.get("spec_ref"):
        lines.append(f"- **Source Design (`spec_ref`):** `{task['spec_ref']}` — {SPEC_REF_NOTE}")
    lines += [
        "",
        "## 1. Deterministic `audit_task` Invariant Report",
        f"- **Inferred Spec Verdict:** `{invariant_report['spec_verdict']}`",
        f"- **Deterministic Audit Gate Verdict:** `{invariant_report['verdict']}` "
        f"(Blocking reasons: `{', '.join(invariant_report.get('blocking_reasons', [])) or 'none'}`)",
        f"- **Verification Command (`{invariant_report['verification_cmd'] or 'N/A'}`):** "
        f"exit code `{invariant_report['verification_exit_code']}`",
        "",
        "### Blocking Fails (`BLOCKING_FAIL` -> Blocks Gate Completion)",
    ]
    if invariant_report["blocking_fails"]:
        for bf in invariant_report["blocking_fails"]:
            lines.append(f"- ❌ {bf}")
    else:
        lines.append("- ✅ None (`0` blocking fails)")

    lines.extend(
        [
            "",
            "### Advisory Warnings (`ADVISORY_WARN` -> Defend in 1 sentence or fix)",
        ]
    )
    if invariant_report["advisory_warns"]:
        for aw in invariant_report["advisory_warns"]:
            lines.append(f"- ⚠️ {aw}")
    else:
        lines.append("- ✅ None (`0` advisory warnings)")

    lines.extend(
        [
            "",
            "### Review Focus Checklist (Tests Must Prove)",
        ]
    )
    for rf in task.get("review_focus", []):
        lines.append(f"- [ ] {rf}")
    if not task.get("review_focus"):
        lines.append("- [ ] Verify edge cases and real pipeline wiring.")

    lines.extend(
        [
            "",
            f"## 2. Commits (`git log --oneline {base_sha}..HEAD`)",
            "```text",
            git_log_out or "(no commits in range)",
            "```",
            "",
            f"## 3. Diff Stat (`git diff --stat {base_sha}..HEAD`)",
            "```text",
            diff_stat_out or "(no diff stat changes)",
            "```",
            "",
            f"## 4. Full Contextual Diff (`git diff -U10 {base_sha}..HEAD`)",
            "```diff",
            diff_u10_out or "(no tracked diff against base_sha)",
            "```",
            "",
        ]
    )

    with open(review_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return {
        "status": "OK",
        "task_id": task_id,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "review_package_path": review_path,
        "invariant_report": invariant_report,
    }


def verify_subtask(subtask_id: str, cwd: str | None = None) -> dict[str, Any]:
    root = os.path.abspath(cwd or os.getcwd())
    state = load_goal_state(cwd=root)
    tasks = state.get("tasks", {})

    found_task: dict[str, Any] | None = None
    found_sub: dict[str, Any] | None = None
    for t in tasks.values():
        if subtask_id in t.get("subtasks", {}):
            found_task = t
            found_sub = t["subtasks"][subtask_id]
            break

    if not found_sub or not found_task:
        return {
            "status": "ERROR",
            "passed": False,
            "errors": [f"Sub-task `{subtask_id}` not found in `.swarm/goal_loop.json`."],
        }

    found_sub["iterations"] = found_sub.get("iterations", 0) + 1
    errors: list[str] = []

    target_files = found_sub.get("target_files", [])
    wiring_files = found_sub.get("wiring_files", [])
    required_symbols = found_sub.get("required_symbols", [])

    # 1. AST & Call-Site Wiring Check
    wiring_res = verify_wiring(
        root_dir=root,
        target_files=target_files,
        wiring_files=wiring_files,
        required_symbols=required_symbols,
    )
    if not wiring_res["passed"]:
        errors.extend(wiring_res["errors"])

    # 2. Authenticity Check on target_files + wiring_files
    scan_targets = list(dict.fromkeys(target_files + wiring_files))
    auth_res = audit_authenticity(
        root_dir=root,
        target_files=scan_targets if scan_targets else None,
        entrypoints=state.get("entrypoints", []),
        check_orphan_modules=bool(scan_targets),
    )
    if not auth_res["passed"]:
        for item in auth_res["placeholder_findings"][:5]:
            errors.append(f"[Placeholder/Stub in {item['file']}:{item['line']}] {item['detail']}")
        for item in auth_res["synthetic_findings"][:5]:
            errors.append(f"[Synthetic/Mock in {item['file']}:{item['line']}] {item['detail']}")
        for item in auth_res["unwired_findings"][:5]:
            errors.append(f"[Unwired Conceptual Code in {item['file']}] {item['detail']}")

    # 3. Sub-task Validation Command
    val_cmd = found_sub.get("validation_cmd", "")
    if val_cmd:
        val_res = run_command_gate(val_cmd, cwd=root)
        if not val_res["passed"]:
            errors.extend(val_res["errors"])

    # 4. Sub-task Outcome Command
    out_cmd = found_sub.get("outcome_cmd", "")
    if out_cmd:
        out_res = run_command_gate(
            out_cmd,
            cwd=root,
            expect_output=found_sub.get("expect_output", ""),
        )
        if not out_res["passed"]:
            errors.extend(out_res["errors"])

    passed = len(errors) == 0
    found_sub["status"] = "VERIFIED_COMPLETE" if passed else "NEEDS_ITERATION"
    found_sub["last_errors"] = errors
    if passed:
        found_sub["verified_at"] = now_iso()

    all_subs = list(found_task.get("subtasks", {}).values())
    if found_task.get("status") in ("BLOCKED_BY_RULING", "SUPERSEDED"):
        pass  # a ruling owns the parent status until the next `--record-task`
    elif all_subs and all(s.get("status") == "VERIFIED_COMPLETE" for s in all_subs):
        parent_errors: list[str] = []
        if found_task.get("validation_cmd"):
            p_val = run_command_gate(found_task["validation_cmd"], cwd=root)
            if not p_val["passed"]:
                parent_errors.extend(p_val["errors"])
        if found_task.get("outcome_cmd"):
            p_out = run_command_gate(
                found_task["outcome_cmd"],
                cwd=root,
                expect_output=found_task.get("expect_output", ""),
            )
            if not p_out["passed"]:
                parent_errors.extend(p_out["errors"])
        # Finished sub-tasks never complete the parent on their own: it still needs a clean audit and a review.
        if parent_errors:
            found_task["status"] = "NEEDS_ITERATION"
        elif _review_passed(found_task) and not found_task.get("blocking_fails"):
            found_task["status"] = "VERIFIED_COMPLETE"
        else:
            found_task["status"] = "AWAITING_REVIEW"
    else:
        found_task["status"] = "IN_PROGRESS"

    save_goal_state(state, cwd=root)
    return {
        "subtask_id": subtask_id,
        "task_id": found_task["task_id"],
        "status": found_sub["status"],
        "passed": passed,
        "iterations": found_sub["iterations"],
        "errors": errors,
        "next_action": (
            f"Sub-task `{subtask_id}` VERIFIED_COMPLETE. Proceed to next sub-task (`goal_loop.py --next`)."
            if passed
            else f"ITERATE on `{subtask_id}`: Fix the {len(errors)} defect(s) above and re-run `goal_loop.py --verify-subtask {subtask_id}`."
        ),
    }


def verify_task(task_id: str, cwd: str | None = None) -> dict[str, Any]:
    """Re-audit a task. It is complete only with zero BLOCKING_FAILs and a passed (or OVERRIDE-ruled) review."""
    root = os.path.abspath(cwd or os.getcwd())
    state = load_goal_state(cwd=root)
    tasks = state.get("tasks", {})
    if task_id not in tasks:
        return {"status": "ERROR", "passed": False, "errors": [f"Task `{task_id}` not found."]}

    task = tasks[task_id]
    if task.get("status") == "BLOCKED_BY_RULING":
        return {
            "task_id": task_id,
            "status": "BLOCKED_BY_RULING",
            "passed": False,
            "ruling": task.get("ruling"),
            "errors": [f"Task `{task_id}` is blocked by a {task.get('ruling_type')} ruling: {task.get('ruling')}"],
        }
    if task.get("status") == "SUPERSEDED":
        successors = ", ".join(task.get("superseded_by") or [])
        return {
            "task_id": task_id,
            "status": "SUPERSEDED",
            "passed": False,
            "errors": [f"Task `{task_id}` is superseded by {successors}; verify those tasks instead."],
        }

    errors: list[str] = []
    for sid in task.get("subtasks", {}):
        sub_res = verify_subtask(sid, cwd=root)
        if not sub_res["passed"]:
            errors.append(f"Sub-task `{sid}` failed verification: {'; '.join(sub_res['errors'])}")

    audit_res = audit_task(task_id, cwd=root, run_cmd=True)
    errors.extend(audit_res["blocking_fails"])

    state = load_goal_state(cwd=root)
    task = state["tasks"][task_id]
    review_ok = _review_passed(task)
    if errors:
        task["status"] = "NEEDS_ITERATION"
    elif not review_ok:
        task["status"] = "AWAITING_REVIEW"
        errors.append(
            f"Task `{task_id}` passes the audit but has no passing review; record the reviewer verdict with "
            "`--record-task`."
        )
    else:
        task["review_passed"] = True
        task["status"] = "COMPLETED_WITH_RULING" if task.get("ruling") else "VERIFIED_COMPLETE"
    passed = len(errors) == 0
    task["gate_verdict"] = "PASS" if passed else "FAIL"
    save_goal_state(state, cwd=root)
    return {
        "task_id": task_id,
        "status": task["status"],
        "verdict": task["gate_verdict"],
        "passed": passed,
        "blocking_fails": audit_res["blocking_fails"],
        "advisory_warns": audit_res["advisory_warns"],
        "errors": errors,
    }


def _superseded_task_done(
    task_id: str,
    tasks: dict[str, Any],
    task_results: dict[str, bool],
    seen: set[str] | None = None,
) -> bool:
    """A SUPERSEDED task is done once every task that replaced it is done."""
    seen = seen if seen is not None else set()
    if task_id in seen:
        return False
    seen.add(task_id)
    successors = tasks.get(task_id, {}).get("superseded_by") or []
    if not successors:
        return False
    for sid in successors:
        if sid not in tasks:
            return False
        if tasks[sid].get("status") == "SUPERSEDED":
            if not _superseded_task_done(sid, tasks, task_results, seen):
                return False
        elif not task_results.get(sid, False):
            return False
    return True


def verify_goal_state(
    cwd: str | None = None,
    outcome_cmd_override: str = "",
    expect_output_override: str = "",
    pass_hat_k_override: int | None = None,
) -> dict[str, Any]:
    """Verify the entire Root Goal: every task re-audited and reviewed + repo authenticity + end-to-end outcome."""
    root = os.path.abspath(cwd or os.getcwd())
    state = load_goal_state(cwd=root)

    if outcome_cmd_override:
        state["outcome_cmd"] = outcome_cmd_override
    if expect_output_override:
        state["expect_output"] = expect_output_override
    if pass_hat_k_override is not None:
        state["pass_hat_k"] = max(1, int(pass_hat_k_override))

    errors: list[str] = []
    unfinished_subtasks: list[str] = []
    unfinished_tasks: list[str] = []
    task_results: dict[str, bool] = {}

    tasks = state.get("tasks", {})
    for tid, task in tasks.items():
        if task.get("status") == "SUPERSEDED":
            continue
        for sid, sub in task.get("subtasks", {}).items():
            if sub.get("status") not in DONE_TASK_STATUSES:
                res = verify_subtask(sid, cwd=root)
                if not res["passed"]:
                    unfinished_subtasks.append(sid)
                    errors.append(f"Unfinished sub-task `{sid}` ({sub.get('title')}): {'; '.join(res['errors'][:2])}")
        # Finished tasks are re-audited too: later changes can break wiring or tests they relied on.
        t_res = verify_task(tid, cwd=root)
        task_results[tid] = t_res["passed"]
        if not t_res["passed"]:
            unfinished_tasks.append(tid)
            errors.extend(t_res["errors"][:2])

    state = load_goal_state(cwd=root)
    tasks = state.get("tasks", {})
    for tid, task in tasks.items():
        if task.get("status") == "SUPERSEDED" and not _superseded_task_done(tid, tasks, task_results):
            unfinished_tasks.append(tid)
            errors.append(
                f"Task `{tid}` is superseded by {', '.join(task.get('superseded_by') or [])}, which are not all finished."
            )
    rulings = [
        {"task_id": tid, "ruling_type": t.get("ruling_type") or "untyped", "ruling": t.get("ruling"), "status": t.get("status")}
        for tid, t in tasks.items()
        if t.get("ruling")
    ]

    auth_res = audit_authenticity(
        root_dir=root,
        entrypoints=state.get("entrypoints", []),
        check_orphan_modules=True,
    )
    changes = _git_changes(root, state.get("base_sha"))
    if changes is not None:
        auth_res = restrict_to_changes(auth_res, changes)
    if not auth_res["passed"]:
        for item in auth_res["placeholder_findings"][:5]:
            errors.append(f"[Placeholder/Half-Baked in {item['file']}:{item['line']}] {item['detail']}")
        for item in auth_res["synthetic_findings"][:5]:
            errors.append(f"[Synthetic/Mock in {item['file']}:{item['line']}] {item['detail']}")
        for item in auth_res["unwired_findings"][:5]:
            errors.append(f"[Unwired Conceptual Module: {item['file']}] {item['detail']}")

    outcome_cmd = outcome_cmd_override or state.get("outcome_cmd", "")
    expect_output = expect_output_override or state.get("expect_output", "")
    k_runs = pass_hat_k_override or state.get("pass_hat_k", 1)

    outcome_res: dict[str, Any] = {"passed": True, "runs": 0, "passed_runs": 0, "errors": []}
    if outcome_cmd:
        outcome_res = run_command_gate(
            outcome_cmd,
            cwd=root,
            expect_output=expect_output,
            pass_hat_k=k_runs,
        )
        if not outcome_res["passed"]:
            errors.extend(outcome_res["errors"])

    goal_reached = len(errors) == 0
    state["status"] = "GOAL_REACHED" if goal_reached else "CONTINUE_GOAL_LOOP"
    state["can_emit_goal_complete"] = goal_reached

    record = {
        "timestamp": now_iso(),
        "status": state["status"],
        "passed": goal_reached,
        "goal_reached": goal_reached,
        "can_emit_goal_complete": goal_reached,
        "authenticity": auth_res["counts"],
        "outcome_verification": {
            "command": outcome_cmd or None,
            "passed": outcome_res["passed"],
            "passed_runs": outcome_res["passed_runs"],
            "runs": outcome_res["runs"],
        },
        "unfinished_tasks": unfinished_tasks,
        "unfinished_subtasks": unfinished_subtasks,
        "rulings": rulings,
        "errors": errors,
    }
    state.setdefault("verification_history", []).append(record)
    save_goal_state(state, cwd=root)
    return record


verify_goal = verify_goal_state


def _plan_blocks(text: str) -> tuple[list[tuple[str, list[str]]] | None, bool]:
    """Split a design's plan section into `(heading, lines)` blocks.

    Headings inside fenced code blocks are ignored. Returns `(None, False)` when the document has no plan
    heading; the bool says whether a `### Goal` block exists.
    """
    lines = text.splitlines()
    fenced: list[bool] = []
    in_fence = False
    for line in lines:
        if line.lstrip().startswith(("```", "~~~")):
            fenced.append(True)
            in_fence = not in_fence
        else:
            fenced.append(in_fence)

    start = next((i for i, line in enumerate(lines) if not fenced[i] and PLAN_HEADING_RE.match(line)), None)
    if start is None:
        return None, False
    end = next((i for i in range(start + 1, len(lines)) if not fenced[i] and lines[i].startswith("## ")), len(lines))

    blocks: list[tuple[str, list[str]]] = []
    for i in range(start + 1, end):
        if not fenced[i] and lines[i].startswith("### "):
            blocks.append((lines[i], []))
        elif blocks:
            blocks[-1][1].append(lines[i])
    return blocks, any(heading.strip() == "### Goal" for heading, _ in blocks)


def _plan_fields(body: list[str]) -> tuple[dict[str, str], list[str]]:
    """Read column-0 `*   **Label:** value` bullets; a value runs until the next such bullet."""
    fields: dict[str, list[str]] = {}
    errors: list[str] = []
    current: str | None = None
    for line in body:
        m = PLAN_FIELD_RE.match(line)
        if m:
            current = m.group(1).strip().lower()
            if current in fields:
                errors.append(f"duplicate field `{m.group(1).strip()}`")
            fields[current] = [m.group(2)]
        elif current is not None:
            fields[current].append(line)
    return {k: "\n".join(v).strip() for k, v in fields.items()}, errors


def _first_command(value: str) -> str:
    m = re.search(r"`([^`]+)`", value)
    return m.group(1).strip() if m else ""


def _plan_text(value: str) -> str:
    return "\n".join(line.strip() for line in value.splitlines()).strip()


def _plan_list_items(value: str) -> list[str]:
    items: list[str] = []
    for line in value.splitlines():
        stripped = line.strip()
        m = re.match(r"^\d+\.\s+(.*)$", stripped)
        if m:
            items.append(m.group(1).strip())
        elif stripped and items:
            items[-1] = f"{items[-1]} {stripped}"
    return items


def _parse_design_plan(text: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Parse the goal block and task blocks of a design; return `(goal, tasks, errors)`."""
    errors: list[str] = []
    blocks, has_goal = _plan_blocks(text)
    if blocks is None:
        return {}, [], ["No `## Detailed Implementation Plan` (or `## Implementation Plan`) section."]

    goal: dict[str, Any] = {}
    tasks: list[dict[str, Any]] = []
    for heading, body in blocks:
        if heading.strip() == "### Goal":
            fields, field_errors = _plan_fields(body)
            errors += [f"Goal block: {e}" for e in field_errors]
            errors += [f"Goal block: unknown field `{k}`" for k in fields if k not in PLAN_GOAL_FIELDS]
            goal = {"goal": _plan_text(fields.get("goal", "")), "outcome_cmd": _first_command(fields.get("outcome", ""))}
            if not goal["goal"]:
                errors.append("Goal block: missing `Goal`.")
            if not goal["outcome_cmd"]:
                errors.append("Goal block: missing a backticked `Outcome` command.")
            continue
        m = PLAN_TASK_RE.match(heading)
        if not m:
            continue
        tid, title = m.group(1), m.group(2)
        fields, field_errors = _plan_fields(body)
        errors += [f"Task {tid}: {e}" for e in field_errors]
        errors += [f"Task {tid}: unknown field `{k}`" for k in fields if k not in PLAN_TASK_FIELDS]
        for required in ("files", "depends on", "changes", "verification"):
            if not fields.get(required):
                errors.append(f"Task {tid}: missing `{required.capitalize()}`.")

        files_value = fields.get("files", "")
        tagged = PLAN_FILE_RE.findall(files_value)
        if len(re.findall(r"`[^`]+`", files_value)) != len(tagged):
            errors.append(f"Task {tid}: every file needs a (Create), (Modify) or (Delete) tag.")
        target_files = [path for path, action in tagged if action != "Delete"]
        deleted = [path for path, action in tagged if action == "Delete"]
        if files_value and not target_files:
            errors.append(f"Task {tid}: needs at least one (Create) or (Modify) file.")

        deps_value = fields.get("depends on", "")
        depends_on = (
            [] if deps_value.strip().lower() == "none"
            else [d.strip().strip("`") for d in deps_value.split(",") if d.strip()]
        )
        verification = _first_command(fields.get("verification", ""))
        if fields.get("verification") and not verification:
            errors.append(f"Task {tid}: `Verification` has no backticked command.")
        outcome = _first_command(fields.get("outcome", ""))
        if fields.get("outcome") and not outcome:
            errors.append(f"Task {tid}: `Outcome` has no backticked command.")

        objective = _plan_text(fields.get("changes", ""))
        if deleted:
            objective += "\n\n" + "\n".join(f"Delete: `{path}`" for path in deleted)
        tasks.append(
            {
                "id": tid,
                "title": title,
                "target_files": target_files,
                "depends_on": depends_on,
                "objective": objective,
                "verification_cmd": verification,
                "outcome_cmd": outcome,
                "review_focus": _plan_list_items(fields.get("review focus", "")),
                "wiring_files": re.findall(r"`([^`]+)`", fields.get("called by", "")),
                "required_symbols": re.findall(r"`([^`]+)`", fields.get("symbols", "")),
            }
        )

    if not has_goal:
        errors.append("Missing `### Goal` block in the plan.")
    if not tasks:
        errors.append("The plan has no `### Task <ID>: <title>` blocks.")

    ids = [t["id"] for t in tasks]
    errors += [f"Duplicate task ID `{tid}`." for tid in sorted({i for i in ids if ids.count(i) > 1})]
    known = set(ids)
    for t in tasks:
        unknown = [d for d in t["depends_on"] if d not in known]
        if unknown:
            errors.append(f"Task {t['id']}: unknown dependency {', '.join(unknown)}.")

    deps = {t["id"]: [d for d in t["depends_on"] if d in known] for t in tasks}

    def closure(tid: str) -> set[str]:
        seen: set[str] = set()
        stack = list(deps.get(tid, []))
        while stack:
            d = stack.pop()
            if d not in seen:
                seen.add(d)
                stack.extend(deps.get(d, []))
        return seen

    closures = {tid: closure(tid) for tid in deps}
    for tid, reach in closures.items():
        if tid in reach:
            errors.append(f"Task {tid}: dependency cycle.")
    for i, a in enumerate(tasks):
        for b in tasks[i + 1:]:
            shared = sorted(set(a["target_files"]) & set(b["target_files"]))
            if shared and a["id"] not in closures.get(b["id"], set()) and b["id"] not in closures.get(a["id"], set()):
                errors.append(
                    f"Tasks {a['id']} and {b['id']} both change {', '.join(shared)} with no `Depends on` path between them."
                )
    return goal, tasks, errors


def import_design(
    doc_path: str, cwd: str | None = None, dry_run: bool = False, drop_missing: bool = False
) -> dict[str, Any]:
    """Import a design's implementation plan into `.swarm/goal_loop.json` (validate everything, then write once)."""
    root = os.path.abspath(cwd or os.getcwd())
    abs_doc = doc_path if os.path.isabs(doc_path) else os.path.join(root, doc_path)
    rel_doc = os.path.relpath(abs_doc, root)
    result: dict[str, Any] = {"status": "ERROR", "doc": rel_doc, "tasks": [], "commands": [], "orphans": [], "errors": []}
    if not os.path.isfile(abs_doc):
        result["errors"].append(f"Design not found: `{rel_doc}`.")
        return result

    goal, plan_tasks, errors = _parse_design_plan(Path(abs_doc).read_text(encoding="utf-8"))

    goal_path = resolve_goal_file(cwd=root, create_dir=False)
    if os.path.exists(goal_path):
        try:
            with open(goal_path, "r", encoding="utf-8") as f:
                json.load(f)
        except (OSError, ValueError) as exc:
            errors.append(f"Goal file `{os.path.relpath(goal_path, root)}` does not parse ({exc}); not importing.")
            result["errors"] = errors
            return result
    state = load_goal_state(cwd=root)
    tasks = state.setdefault("tasks", {})

    def ref_doc(task: dict[str, Any]) -> str:
        return str(task.get("spec_ref") or "").split(" § ")[0]

    plan_ids = {t["id"] for t in plan_tasks}
    for t in plan_tasks:
        existing = tasks.get(t["id"])
        if existing is not None and ref_doc(existing) != rel_doc:
            owner = ref_doc(existing) or "no design"
            errors.append(f"Task ID `{t['id']}` already exists in the goal file and belongs to {owner}.")
    orphans = sorted(tid for tid, task in tasks.items() if ref_doc(task) == rel_doc and tid not in plan_ids)
    result["orphans"] = orphans
    if orphans and not drop_missing:
        errors.append(
            f"Tasks from this design are missing from its plan: {', '.join(orphans)}. "
            "Re-run with --drop-missing to delete them."
        )
    if errors:
        result["errors"] = errors
        return result

    head = _detect_git_head(cwd=root)
    for t in plan_tasks:
        record = {**t, "spec_ref": f"{rel_doc} § Task {t['id']}"}
        existing = tasks.get(t["id"])
        changed_cmds = [
            (field, record[field]) for field in ("verification_cmd", "outcome_cmd")
            if record[field] and (existing is None or existing.get(field) != record[field])
        ]
        result["commands"] += [{"task": t["id"], "field": f, "command": c} for f, c in changed_cmds]
        if existing is None:
            action = "add"
            merged = {**record, "status": "PENDING", "base_sha": head, "created_at": now_iso()}
        elif all(existing.get(f) == record[f] for f in IMPORT_COMPARED_FIELDS):
            action = "unchanged"
            merged = existing
        else:
            action = "update" if existing.get("status", "PENDING") == "PENDING" else "reset"
            merged = {**existing, **record, **copy.deepcopy(GATE_RESET_FIELDS), "status": "PENDING", "base_sha": head}
        merged["verification_commands"] = [record["verification_cmd"]]
        merged["validation_cmd"] = record["verification_cmd"]
        merged["wiring_contract"] = {
            "must_be_called_by": list(record["wiring_files"]),
            "exported_symbols": list(record["required_symbols"]),
        }
        result["tasks"].append({"id": t["id"], "title": t["title"], "action": action})
        tasks[t["id"]] = _normalize_task_record(t["id"], merged, default_base_sha=head)

    if goal.get("outcome_cmd") and not state.get("outcome_cmd"):
        result["commands"].append({"task": "(goal)", "field": "outcome_cmd", "command": goal["outcome_cmd"]})
        state["outcome_cmd"] = goal["outcome_cmd"]
    if goal.get("goal") and not state.get("goal"):
        state["goal"] = goal["goal"]
    result["status"] = "OK"
    if dry_run:
        return result

    for tid in orphans:
        tasks.pop(tid, None)
        append_ledger_entry(f"- Dropped task `{tid}`: no longer in the plan of `{rel_doc}` (--drop-missing).", cwd=root)
    state["status"] = "IN_PROGRESS"
    state["can_emit_goal_complete"] = False
    save_goal_state(state, cwd=root)
    return result


def verify_blueprint_artifacts(cwd: str | None = None, require_ui: bool = False) -> dict[str, Any]:
    """Verify `/product-discovery` Phase A outputs have no unresolved placeholders, real evidence, and wired UI prototypes."""
    root = os.path.abspath(cwd or os.getcwd())
    bp_dir = os.path.join(root, ".swarm", "blueprint")
    errors: list[str] = []
    checked_files: list[str] = []

    tech_report = os.path.join(bp_dir, "tech_research_report.md")
    legacy_report = os.path.join(bp_dir, "deep_research_report.md")
    research_report = tech_report if (os.path.exists(tech_report) or not os.path.exists(legacy_report)) else legacy_report

    expected_reports = [
        research_report,
        os.path.join(bp_dir, "brainstorm_blueprint.md"),
    ]
    optional_reports = [
        os.path.join(bp_dir, "market_research_report.md"),
        os.path.join(bp_dir, "commercial_strategy_report.md"),
        os.path.join(root, "docs", "ARCHITECTURE.md"),
    ]

    for r_path in expected_reports + [p for p in optional_reports if os.path.exists(p)]:
        rel = os.path.relpath(r_path, root)
        if not os.path.isfile(r_path):
            errors.append(f"Missing required blueprint artifact: `{rel}`")
            continue
        checked_files.append(rel)
        text = Path(r_path).read_text(encoding="utf-8", errors="replace")
        if len(text.strip()) < 250:
            errors.append(f"Blueprint artifact `{rel}` is half-baked / too short ({len(text.strip())} chars).")
        for m in BLUEPRINT_PLACEHOLDER_RE.finditer(text):
            errors.append(f"Blueprint artifact `{rel}` contains unfulfilled placeholder `{m.group(0)}`.")

    if require_ui:
        ui_dir = os.path.join(bp_dir, "ui_proposals")
        templates = sorted(Path(ui_dir).glob("template_*.html")) if os.path.isdir(ui_dir) else []
        if len(templates) < 3:
            errors.append(
                f"Expected 3 single-file HTML templates in `.swarm/blueprint/ui_proposals/`, found {len(templates)}."
            )
        else:
            validator_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_ui_validator.py")
            cmd = [sys.executable, validator_script] + [str(t) for t in templates]
            res = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False)
            if res.returncode != 0:
                errors.append(
                    f"`web_ui_validator.py` failed on blueprint UI templates: {(res.stdout or res.stderr).strip()[:300]}"
                )

    # Designs that tasks were imported from must still exist and still import cleanly.
    design_docs = sorted(
        {
            str(t.get("spec_ref")).split(" § ")[0]
            for t in load_goal_state(cwd=root).get("tasks", {}).values()
            if t.get("spec_ref")
        }
    )
    for rel in design_docs:
        doc = os.path.join(root, rel)
        if not os.path.isfile(doc):
            errors.append(f"Design `{rel}` named by a task's `spec_ref` is missing.")
            continue
        checked_files.append(rel)
        for m in BLUEPRINT_PLACEHOLDER_RE.finditer(Path(doc).read_text(encoding="utf-8", errors="replace")):
            errors.append(f"Design `{rel}` contains unfulfilled placeholder `{m.group(0)}`.")
        dry = import_design(rel, cwd=root, dry_run=True)
        errors += [f"Design `{rel}` does not import cleanly: {e}" for e in dry["errors"]]

    passed = len(errors) == 0
    return {
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "checked_files": checked_files,
        "errors": errors,
    }


def get_next_action(cwd: str | None = None) -> dict[str, Any]:
    """Return the next unfinished Sub-Task or Task in the Goal-Loop queue."""
    root = os.path.abspath(cwd or os.getcwd())
    state = load_goal_state(cwd=root)
    for tid, task in state.get("tasks", {}).items():
        if task.get("status") == "SUPERSEDED":
            continue
        for sid, sub in task.get("subtasks", {}).items():
            if sub.get("status") not in DONE_TASK_STATUSES:
                return {
                    "has_next": True,
                    "kind": "subtask",
                    "task_id": tid,
                    "subtask_id": sid,
                    "title": sub.get("title"),
                    "objective": sub.get("objective"),
                    "target_files": sub.get("target_files", []),
                    "wiring_files": sub.get("wiring_files", []),
                    "required_symbols": sub.get("required_symbols", []),
                    "validation_cmd": sub.get("validation_cmd", ""),
                    "outcome_cmd": sub.get("outcome_cmd", ""),
                    "last_errors": sub.get("last_errors", []),
                }
        if task.get("status") not in DONE_TASK_STATUSES:
            return {
                "has_next": True,
                "kind": "task",
                "task_id": tid,
                "status": task.get("status"),
                "ruling": task.get("ruling"),
                "title": task.get("title"),
                "objective": task.get("objective"),
                "target_files": task.get("target_files", []),
                "wiring_files": task.get("wiring_files", []),
                "required_symbols": task.get("required_symbols", []),
                "verification_cmd": task.get("verification_cmd") or task.get("validation_cmd", ""),
                "validation_cmd": task.get("validation_cmd", ""),
                "outcome_cmd": task.get("outcome_cmd", ""),
                "review_focus": task.get("review_focus", []),
            }

    return {
        "has_next": False,
        "kind": "goal_verification",
        "message": "All registered tasks and sub-tasks are marked complete. Run `goal_loop.py --verify-goal` to verify final outcome!",
    }


def get_summary(cwd: str | None = None) -> dict[str, Any]:
    root = os.path.abspath(cwd or os.getcwd())
    state = load_goal_state(cwd=root)
    tasks = state.get("tasks", {})
    completed = [tid for tid, t in tasks.items() if t.get("status") in DONE_TASK_STATUSES]
    ruled = [tid for tid, t in tasks.items() if t.get("ruling")]
    pending = [tid for tid, t in tasks.items() if t.get("status") not in DONE_TASK_STATUSES | {"SUPERSEDED"}]

    minor_path = resolve_deferred_minor_ledger_md(cwd=root, create_dir=False)
    deferred_minor_lines = 0
    if os.path.isfile(minor_path):
        deferred_minor_lines = sum(
            1 for ln in Path(minor_path).read_text(encoding="utf-8", errors="replace").splitlines() if ln.startswith("- ")
        )

    return {
        "goal": state.get("goal", ""),
        "status": state.get("status", "IN_PROGRESS"),
        "can_emit_goal_complete": state.get("can_emit_goal_complete", False),
        "total_tasks": len(tasks),
        "completed_tasks": completed,
        "ruled_tasks": ruled,
        "pending_tasks": pending,
        "deferred_minor_entries": deferred_minor_lines,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Hierarchical Goal-Loop, Deterministic Invariants (`BLOCKING_FAIL` vs `ADVISORY_WARN`) & Categorical Gate Engine"
    )
    ap.add_argument("--cwd", "--path", dest="cwd", default=None, help="Target workspace directory")
    ap.add_argument(
        "--init",
        nargs="?",
        const="DEFAULT",
        metavar="GOAL_TEXT",
        help="Initialize `.swarm/goal_loop.json` with DEFAULT_MANIFEST (including TASK-001, review_focus, base_sha)",
    )
    ap.add_argument("--init-goal", metavar="GOAL_TEXT", help="Initialize root `/goal` and desired product outcome")
    ap.add_argument("--outcome-cmd", default="", help="End-to-end command that verifies the desired outcome")
    ap.add_argument("--expect-output", default="", help="Regex or substring that must appear in outcome command stdout")
    ap.add_argument("--entrypoints", default="", help="Comma-separated list of product entrypoint files")
    ap.add_argument("--pass-hat-k", type=int, default=1, help="Consecutive passes required for outcome command")

    ap.add_argument("--add-task", action="store_true", help="Add or update a parent Task in the goal loop")
    ap.add_argument("--add-subtask", action="store_true", help="Add or update a Sub-Task under --task-id")
    ap.add_argument("--task-id", "--parent-task", dest="task_id", default="", help="Task ID (e.g. TASK-001 or T1)")
    ap.add_argument("--subtask-id", default="", help="Sub-Task ID (e.g. T1.1)")
    ap.add_argument("--title", default="", help="Short title for the task or sub-task")
    ap.add_argument("--objective", "--outcome", dest="objective", default="", help="Concrete deliverable objective")
    ap.add_argument("--target-files", default="", help="Comma-separated implementation files for the task/sub-task")
    ap.add_argument(
        "--wiring-files",
        "--must-be-called-by",
        dest="wiring_files",
        default="",
        help="Comma-separated entrypoint/caller files that must call/reference this task in AST",
    )
    ap.add_argument(
        "--required-symbols",
        "--exported-symbols",
        dest="required_symbols",
        default="",
        help="Comma-separated symbols that must be imported & actively used in wiring-files",
    )
    ap.add_argument("--wiring-target", default="", help="Description of how the task commits to the product outcome")
    ap.add_argument(
        "--validation-cmd",
        "--verification-cmd",
        dest="validation_cmd",
        default="",
        help="Unit/component verification command",
    )
    ap.add_argument(
        "--review-focus",
        default="",
        help="Semicolon-separated list of implied failure modes/inputs that tests must prove",
    )
    ap.add_argument("--base-sha", default="", help="Git base commit SHA for task diff and review package")
    ap.add_argument("--depends-on", default="", help="Comma-separated task IDs this task depends on (with --add-task)")
    ap.add_argument("--spec-ref", default="", help="Design section the task implements, `<doc> § Task <ID>` (with --add-task)")
    ap.add_argument(
        "--import-design",
        metavar="PATH",
        help="Import the `## Detailed Implementation Plan` of a design document into `.swarm/goal_loop.json`",
    )
    ap.add_argument("--dry-run", action="store_true", help="With --import-design: validate and report, write nothing")
    ap.add_argument(
        "--drop-missing",
        action="store_true",
        help="With --import-design: delete tasks from this design that are no longer in its plan",
    )

    # Context-hygiene subcommands (superpowers integration)
    ap.add_argument(
        "--preflight",
        action="store_true",
        help="Scan all tasks in `.swarm/goal_loop.json` and output a Pre-Flight Conflict & Dependency Table",
    )
    ap.add_argument(
        "--task-brief",
        nargs="?",
        const="__USE_TASK_ID__",
        metavar="TASK_ID",
        help="Extract a clean, self-contained markdown brief to `.swarm/briefs/<TASK_ID>-brief.md` and print its path",
    )
    ap.add_argument(
        "--review-package",
        nargs="?",
        const="__USE_TASK_ID__",
        metavar="TASK_ID",
        help="Bundle git log, git diff --stat, git diff -U10, and deterministic `audit_task` report to `.swarm/reviews/<TASK_ID>-review.diff.md`",
    )

    # Verification, Audit & Two-Verdict Hard-Cap Recording
    ap.add_argument("--verify-subtask", metavar="SUBTASK_ID", help="Run 4-stage verification gate on a sub-task")
    ap.add_argument(
        "--verify-task",
        nargs="?",
        const="__USE_TASK_ID__",
        metavar="TASK_ID",
        help="Verify all subtasks, AST wiring, authenticity, and verification_cmd for a task",
    )
    ap.add_argument(
        "--audit-task",
        nargs="?",
        const="__USE_TASK_ID__",
        metavar="TASK_ID",
        help="Run deterministic invariant check (`BLOCKING_FAIL` vs `ADVISORY_WARN`) and evaluate categorical gate",
    )
    ap.add_argument(
        "--record-task",
        nargs="?",
        const="__USE_TASK_ID__",
        metavar="TASK_ID",
        help="Record Two-Verdict Categorical Gate (`--spec-verdict`, `--critical-count`, `--important-count`, `--minor-count`, `--ruling`)",
    )
    ap.add_argument(
        "--spec-verdict",
        choices=["PASS", "FAIL", "UNVERIFIABLE"],
        default=None,
        help="Part 1 Spec Compliance Verdict from Discriminator (default inferred from blocking_fails)",
    )
    ap.add_argument("--critical-count", type=int, default=0, help="Count of Critical findings (blocks gate completion)")
    ap.add_argument("--important-count", type=int, default=0, help="Count of Important findings (blocks gate completion)")
    ap.add_argument(
        "--minor-count",
        type=int,
        default=0,
        help="Count of Minor findings (deferred to `.swarm/deferred_minor_ledger.md`, NEVER blocks completion)",
    )
    ap.add_argument(
        "--ruling",
        default="",
        help="Round 5 Breaker adjudication (`Ruling: <what> — <why> — <cost if wrong>`) recorded in `.swarm/ledger.md`",
    )
    ap.add_argument(
        "--ruling-type",
        choices=RULING_TYPES,
        default="",
        help="Required with --ruling. Only OVERRIDE completes the task, and only when the audit has no BLOCKING_FAIL",
    )
    ap.add_argument(
        "--superseded-by",
        default="",
        help="Comma-separated existing task IDs that replace this task (required with --ruling-type SPLIT_TASK)",
    )
    ap.add_argument("--notes", default="", help="Optional review or minor-finding notes")
    ap.add_argument(
        "--review-source",
        choices=REVIEW_SOURCES,
        default="reviewer",
        help="`reviewer` if a separate reviewer subagent produced the verdict, `self-check` if the orchestrator "
        "recorded it from the worker's own checks (Lite Mode default)",
    )
    ap.add_argument("--run-audit", action="store_true", help="Re-run deterministic `audit_task` inside `--record-task`")

    ap.add_argument("--verify-goal", "--verify-epoch", dest="verify_goal", action="store_true", help="Verify all tasks, repo authenticity, and root outcome")
    ap.add_argument("--verify-blueprint", action="store_true", help="Verify `/product-discovery` blueprint artifacts have zero placeholders")
    ap.add_argument("--require-ui", action="store_true", help="Require 3 validated HTML UI templates in --verify-blueprint")
    ap.add_argument("--scan-authenticity", action="store_true", help="Scan codebase for stubs, synthetic mocks, and unwired modules")
    ap.add_argument("--no-orphan-check", action="store_true", help="Skip cross-file orphan module check during --scan-authenticity")
    ap.add_argument("--emit-completion", action="store_true", help="Emit `<!-- GOAL_COMPLETE -->` if and only if goal verification passes")
    ap.add_argument("--summary", action="store_true", help="Print concise Goal-Loop & ledger summary")
    ap.add_argument("--next", action="store_true", help="Get the next unfinished sub-task or task to work on")
    ap.add_argument("--status", action="store_true", help="Print current Goal-Loop status")
    ap.add_argument("--json", action="store_true", help="Format output as JSON")

    args = ap.parse_args()
    cwd = args.cwd or os.getcwd()
    if (args.dry_run or args.drop_missing) and not args.import_design:
        ap.error("--dry-run and --drop-missing require --import-design")

    def _resolve_tid(val: str | None) -> str:
        if val and val != "__USE_TASK_ID__":
            return val
        if args.task_id:
            return args.task_id
        return "TASK-001"

    if args.init is not None:
        ep_list = [x.strip() for x in args.entrypoints.split(",") if x.strip()] if args.entrypoints else None
        st = init_manifest(
            goal=args.init,
            outcome_cmd=args.outcome_cmd,
            expect_output=args.expect_output,
            entrypoints=ep_list,
            pass_hat_k=args.pass_hat_k,
            seed_default_tasks=True,
            cwd=cwd,
        )
        print(json.dumps(st, indent=2))
    elif args.init_goal:
        ep_list = [x.strip() for x in args.entrypoints.split(",") if x.strip()] if args.entrypoints else []
        st = init_goal(
            goal=args.init_goal,
            outcome_cmd=args.outcome_cmd,
            expect_output=args.expect_output,
            entrypoints=ep_list,
            pass_hat_k=args.pass_hat_k,
            cwd=cwd,
        )
        print(json.dumps(st, indent=2))
    elif args.import_design:
        res = import_design(args.import_design, cwd=cwd, dry_run=args.dry_run, drop_missing=args.drop_missing)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            label = "Dry run" if args.dry_run else "Import"
            print(f"{label} of `{res['doc']}`: {res['status']}")
            for t in res["tasks"]:
                print(f"  {t['action']:<9} {t['id']}  {t['title']}")
            for c in res["commands"]:
                print(f"  command   {c['task']} {c['field']}: {c['command']}")
            for o in res["orphans"]:
                print(f"  orphan    {o}")
            for e in res["errors"]:
                print(f"  error     {e}")
        sys.exit(0 if res["status"] == "OK" else 1)
    elif args.add_task:
        if not args.task_id or not args.title:
            print("Error: --add-task requires --task-id and --title", file=sys.stderr)
            sys.exit(1)
        t_files = [x.strip() for x in args.target_files.split(",") if x.strip()]
        w_files = [x.strip() for x in args.wiring_files.split(",") if x.strip()]
        req_syms = [x.strip() for x in args.required_symbols.split(",") if x.strip()]
        r_focus = [x.strip() for x in args.review_focus.split(";") if x.strip()] if args.review_focus else None
        res = add_task(
            task_id=args.task_id,
            title=args.title,
            objective=args.objective,
            validation_cmd=args.validation_cmd,
            outcome_cmd=args.outcome_cmd,
            expect_output=args.expect_output,
            wiring_target=args.wiring_target,
            target_files=t_files,
            wiring_files=w_files,
            required_symbols=req_syms,
            review_focus=r_focus,
            base_sha=args.base_sha,
            depends_on=[x.strip() for x in args.depends_on.split(",") if x.strip()] if args.depends_on else None,
            spec_ref=args.spec_ref,
            cwd=cwd,
        )
        print(json.dumps(res, indent=2))
    elif args.add_subtask:
        if not args.task_id or not args.subtask_id or not args.title:
            print("Error: --add-subtask requires --task-id, --subtask-id, and --title", file=sys.stderr)
            sys.exit(1)
        t_files = [x.strip() for x in args.target_files.split(",") if x.strip()]
        w_files = [x.strip() for x in args.wiring_files.split(",") if x.strip()]
        req_syms = [x.strip() for x in args.required_symbols.split(",") if x.strip()]
        r_focus = [x.strip() for x in args.review_focus.split(";") if x.strip()] if args.review_focus else None
        res = add_subtask(
            task_id=args.task_id,
            subtask_id=args.subtask_id,
            title=args.title,
            objective=args.objective or args.title,
            target_files=t_files,
            wiring_files=w_files,
            required_symbols=req_syms,
            validation_cmd=args.validation_cmd,
            outcome_cmd=args.outcome_cmd,
            expect_output=args.expect_output,
            review_focus=r_focus,
            cwd=cwd,
        )
        print(json.dumps(res, indent=2))
    elif args.preflight:
        res = run_preflight(cwd=cwd, as_json=args.json)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(res["markdown"])
            if res["warnings"]:
                print("Warnings:")
                for w in res["warnings"]:
                    print(f"  - {w}")
        sys.exit(0 if res["passed"] else 1)
    elif args.task_brief is not None:
        tid = _resolve_tid(args.task_brief)
        res = generate_task_brief(tid, cwd=cwd)
        if res.get("status") != "OK":
            print(json.dumps(res, indent=2), file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(res["brief_path"])
    elif args.review_package is not None:
        tid = _resolve_tid(args.review_package)
        res = generate_review_package(tid, base_sha_override=args.base_sha, cwd=cwd)
        if res.get("status") != "OK":
            print(json.dumps(res, indent=2), file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(res["review_package_path"])
    elif args.audit_task is not None:
        tid = _resolve_tid(args.audit_task)
        res = audit_task(tid, cwd=cwd, run_cmd=True)
        print(json.dumps(res, indent=2))
    elif args.record_task is not None:
        tid = _resolve_tid(args.record_task)
        res = record_task(
            task_id=tid,
            spec_verdict=args.spec_verdict,
            critical_count=args.critical_count,
            important_count=args.important_count,
            minor_count=args.minor_count,
            ruling=args.ruling,
            notes=args.notes,
            cwd=cwd,
            run_audit=args.run_audit,
            ruling_type=args.ruling_type,
            superseded_by=[s for s in args.superseded_by.split(",") if s.strip()],
            review_source=args.review_source,
        )
        print(json.dumps(res, indent=2))
        if res.get("status") == "ERROR":
            sys.exit(1)
    elif args.verify_subtask:
        res = verify_subtask(args.verify_subtask, cwd=cwd)
        print(json.dumps(res, indent=2))
        sys.exit(0 if res["passed"] else 1)
    elif args.verify_task is not None:
        tid = _resolve_tid(args.verify_task)
        res = verify_task(tid, cwd=cwd)
        print(json.dumps(res, indent=2))
        sys.exit(0 if res["passed"] else 1)
    elif args.verify_goal:
        res = verify_goal_state(
            cwd=cwd,
            outcome_cmd_override=args.outcome_cmd,
            expect_output_override=args.expect_output,
            pass_hat_k_override=args.pass_hat_k if args.pass_hat_k > 1 else None,
        )
        print(json.dumps(res, indent=2))
        sys.exit(0 if res["goal_reached"] else 1)
    elif args.emit_completion:
        res = verify_goal_state(cwd=cwd)
        if res.get("can_emit_goal_complete"):
            print("<!-- GOAL_COMPLETE -->")
            sys.exit(0)
        else:
            print(json.dumps(res, indent=2), file=sys.stderr)
            sys.exit(1)
    elif args.verify_blueprint:
        res = verify_blueprint_artifacts(cwd=cwd, require_ui=args.require_ui)
        print(json.dumps(res, indent=2))
        sys.exit(0 if res["passed"] else 1)
    elif args.scan_authenticity:
        t_files = [x.strip() for x in args.target_files.split(",") if x.strip()] if args.target_files else None
        ep_list = [x.strip() for x in args.entrypoints.split(",") if x.strip()] if args.entrypoints else None
        res = audit_authenticity(
            root_dir=cwd,
            target_files=t_files,
            entrypoints=ep_list,
            check_orphan_modules=not args.no_orphan_check,
        )
        print(json.dumps(res, indent=2))
        sys.exit(0 if res["passed"] else 1)
    elif args.summary:
        res = get_summary(cwd=cwd)
        print(json.dumps(res, indent=2))
    elif args.next:
        res = get_next_action(cwd=cwd)
        print(json.dumps(res, indent=2))
    elif args.status:
        st = load_goal_state(cwd=cwd)
        if args.json:
            print(json.dumps(st, indent=2))
        else:
            md_path = render_goal_progress_md(st, cwd=cwd)
            print(Path(md_path).read_text(encoding="utf-8"))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
