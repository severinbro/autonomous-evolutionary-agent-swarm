#!/usr/bin/env python3
"""SWE-bench Verified benchmark (T13): 20 hard instances, four arms, any harness.

Instances are the SWE-bench Verified tasks rated "1-4 hours" or harder from three pure-Python repositories
(12 Django, 5 SymPy, 3 pytest). Every workspace is a copy of the instance image's `/testbed` checkout, so the
agent starts from exactly the tree the official grader applies patches to. Agents run tests through
`./run_tests.sh`, which mounts the workspace into the instance's Docker image; the issue's own tests stay
hidden. Grading uses the official harness (`swebench.harness.run_evaluation`) on each workspace's diff.

Arms (workspaces under `<runs-dir>/<arm>/<instance>/r<N>/`):
  single_agent_checked  one agent with the issue, the test wrapper and acceptance criteria
  best_of_3             three independent single agents in `r<N>_attempt_{1,2,3}/`; `pick` installs the attempt
                        that passes the most of all attempts' new tests (scripts/attempt_picker.py, git mode)
  swarm_peers           three peers with one shared goal and `.swarm/board.md` (skills/peer-swarm)
  swarm_lite            `/invoke-swarm lite`: worker, deterministic gate, reviewer (`.swarm/goal_loop.json`)

Commands (run with benchmarks/swe/.venv/bin/python):
  select                                   write instances.json (agent-visible fields only)
  pull                                     docker pull the 20 instance images
  setup    --runs-dir D [--arms A ...] [--instances ID ...] [--runs N]
  pick     --runs-dir D --instance ID [--run r1]
  evaluate --runs-dir D --telemetry-file T --results-file R [--harness NAME] [--max-workers 4]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BENCH_DIR = HERE.parent
REPO_ROOT = BENCH_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(BENCH_DIR))

import attempt_picker  # noqa: E402
import goal_loop  # noqa: E402

DATASET = "SWE-bench/SWE-bench_Verified"
INSTANCES_FILE = HERE / "instances.json"
ARMS = ("single_agent_checked", "best_of_3", "swarm_peers", "swarm_lite")

# SWE-bench Verified, difficulty "1-4 hours" or ">4 hours", pure-Python repositories, spread across versions.
INSTANCE_IDS = [
    "django__django-10554", "django__django-11400", "django__django-12325", "django__django-13128",
    "django__django-13344", "django__django-13837", "django__django-14011", "django__django-15128",
    "django__django-15503", "django__django-15957", "django__django-16263", "django__django-16631",
    "sympy__sympy-12489", "sympy__sympy-13878", "sympy__sympy-14248", "sympy__sympy-16597", "sympy__sympy-18199",
    "pytest-dev__pytest-5787", "pytest-dev__pytest-6197", "pytest-dev__pytest-10356",
]

# Each repository's own test runner (from the dataset's eval scripts, without the hidden test names).
RUNNERS = {
    "django/django": {
        "runner": "./tests/runtests.py --verbosity 2 --settings=test_sqlite --parallel 1",
        "example": "admin_views",
        "labels": "test labels such as `admin_views` or `admin_views.test_forms` (folders under `tests/`)",
        "label_style": "dotted", "label_root": "tests",
    },
    "sympy/sympy": {
        "runner": "PYTHONWARNINGS='ignore::UserWarning,ignore::SyntaxWarning' bin/test -C --verbose",
        "example": "sympy/core/tests/test_basic.py",
        "labels": "test file paths such as `sympy/core/tests/test_basic.py`",
        "label_style": "path", "label_root": "",
    },
    "pytest-dev/pytest": {
        "runner": "pytest -rA",
        "example": "testing/test_mark.py",
        "labels": "test file paths such as `testing/test_mark.py`",
        "label_style": "path", "label_root": "",
    },
}

HELPER_FILES = ("TASK_SPEC.md", "run_tests.sh")

TASK_SPEC = """# Task: Resolve a {repo} issue ({instance_id})

This folder is a checkout of `{repo}` (version {version}). Resolve the issue below by changing the library's source code.

## Issue

{problem_statement}

## Running the tests

The project's environment (Python version and dependencies) lives in a Docker image. Run any command inside it with the wrapper, which mounts this checkout at `/testbed`:

    ./run_tests.sh <command>

The project's own test runner is `{runner}`, followed by {labels}. For example:

    ./run_tests.sh {runner} {example}

## Acceptance Criteria & Self-Checks

1. Add a regression test to the project's existing test suite that fails without your fix and passes with it.
2. Run the existing tests for every module you changed and make sure nothing that passed before now fails.
3. Keep the change focused on the issue: fix the library's code, and do not edit unrelated tests.

## Rules

- Work from the issue and this checkout only: no network access, and do not look up the upstream fix, the issue tracker, or other copies of this repository.
- Do not edit `run_tests.sh` or `TASK_SPEC.md`.
"""

RUN_TESTS = """#!/usr/bin/env bash
# Runs a command inside this task's SWE-bench environment, with this checkout mounted at /testbed.
set -euo pipefail
here="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd -P)"
if [ "$#" -eq 0 ]; then
  echo "usage: ./run_tests.sh <command> [args...]" >&2
  exit 2
fi
exec docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp -e LANG=C.UTF-8 -e LC_ALL=C.UTF-8 \\
  -v "$here":/testbed -w /testbed "{image}" \\
  bash -c 'cmd="$*"; set --; source /opt/miniconda3/bin/activate && conda activate testbed && eval "$cmd"' bash "$@"
"""


def _run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> str:
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True).stdout


def load_instances() -> dict[str, dict[str, Any]]:
    return {i["instance_id"]: i for i in json.loads(INSTANCES_FILE.read_text(encoding="utf-8"))}


# --------------------------------------------------------------------------- select / pull

def cmd_select() -> None:
    from datasets import load_dataset

    rows = {r["instance_id"]: r for r in load_dataset(DATASET, split="test") if r["instance_id"] in INSTANCE_IDS}
    missing = sorted(set(INSTANCE_IDS) - set(rows))
    if missing:
        sys.exit(f"Not in {DATASET}: {missing}")
    keep = ("instance_id", "repo", "version", "difficulty", "image", "problem_statement")
    out = [{k: rows[i][k] for k in keep} for i in INSTANCE_IDS]
    INSTANCES_FILE.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {INSTANCES_FILE} ({len(out)} instances; hidden tests and gold patches are not stored)")


def cmd_pull() -> None:
    for inst in load_instances().values():
        print("pulling", inst["image"], flush=True)
        subprocess.run(["docker", "pull", "-q", inst["image"]], check=True)


# --------------------------------------------------------------------------- setup

def cache_repo(runs_dir: Path, inst: dict[str, Any]) -> tuple[Path, str]:
    """Copy the image's /testbed once per instance; returns (repo copy, commit the checkout starts at)."""
    cache = runs_dir / "_cache" / inst["instance_id"]
    repo = cache / "repo"
    if not repo.is_dir():
        cache.mkdir(parents=True, exist_ok=True)
        cid = _run(["docker", "create", inst["image"]]).strip()
        try:
            _run(["docker", "cp", f"{cid}:/testbed", str(repo)])
        finally:
            _run(["docker", "rm", cid], check=False)
        (cache / "start_commit").write_text(_run(["git", "rev-parse", "HEAD"], cwd=repo).strip())
    return repo, (cache / "start_commit").read_text().strip()


def _write_helpers(ws: Path, inst: dict[str, Any]) -> None:
    r = RUNNERS[inst["repo"]]
    (ws / "TASK_SPEC.md").write_text(TASK_SPEC.format(
        repo=inst["repo"], instance_id=inst["instance_id"], version=inst["version"],
        problem_statement=inst["problem_statement"].strip(), runner=r["runner"], labels=r["labels"],
        example=r["example"]), encoding="utf-8")
    run_tests = ws / "run_tests.sh"
    run_tests.write_text(RUN_TESTS.format(image=inst["image"]), encoding="utf-8")
    run_tests.chmod(0o755)
    exclude = ws / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with exclude.open("a", encoding="utf-8") as f:
        f.write("\n# benchmark helpers\nTASK_SPEC.md\nrun_tests.sh\n.swarm/\n")


def _checkout(runs_dir: Path, inst: dict[str, Any], ws: Path) -> None:
    repo, _ = cache_repo(runs_dir, inst)
    shutil.copytree(repo, ws, symlinks=True)
    _write_helpers(ws, inst)


def provision(runs_dir: Path, arm: str, inst: dict[str, Any], ws: Path) -> None:
    if arm == "best_of_3":
        for i in (1, 2, 3):
            _checkout(runs_dir, inst, ws.parent / f"{ws.name}_attempt_{i}")
        ws.mkdir(parents=True)
        (ws / "PENDING_PICK").write_text("Run `swe_bench.py pick` after the three attempts finish.\n")
        return
    _checkout(runs_dir, inst, ws)
    if arm == "swarm_peers":
        (ws / ".swarm").mkdir()
        shutil.copy2(REPO_ROOT / "skills" / "peer-swarm" / "board_template.md", ws / ".swarm" / "board.md")
    if arm == "swarm_lite":
        # Target files and the verification command are not known before localisation; the orchestrator
        # records them with `goal_loop.py --add-task` once the worker reports which files it changed.
        goal_loop.init_manifest(goal=f"Resolve {inst['instance_id']} as described in TASK_SPEC.md",
                                seed_default_tasks=False, cwd=str(ws))
        goal_loop.add_task(
            task_id="FIX", title=f"Resolve {inst['instance_id']}", objective="Resolve the issue in TASK_SPEC.md",
            review_focus=[
                "The fix resolves the issue for every case the issue describes, not only its example",
                "No test that passed before the change fails after it",
            ],
            cwd=str(ws),
        )
        goal_loop.generate_task_brief("FIX", cwd=str(ws))


def cmd_setup(runs_dir: Path, arms: list[str], ids: list[str], runs: int) -> None:
    insts = load_instances()
    created = 0
    for arm in arms:
        for iid in ids:
            for n in range(1, runs + 1):
                ws = runs_dir / arm / iid / f"r{n}"
                if ws.exists():
                    continue
                provision(runs_dir, arm, insts[iid], ws)
                created += 1
                print("provisioned", ws.relative_to(runs_dir), flush=True)
    print(f"{created} workspace(s) created under {runs_dir}")


# --------------------------------------------------------------------------- patches

def extract_patch(ws: Path, start: str) -> str:
    """Working tree vs the start commit, without test files or benchmark helpers, via a throwaway index.

    Test files are dropped because the grader applies the instance's own test patch, and an agent's edits
    to the same files would make that patch fail to apply.
    """
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / "index"))
        subprocess.run(["git", "read-tree", start], cwd=ws, env=env, check=True)
        # Benchmark helpers are listed in .git/info/exclude, so `add -A` leaves them out.
        subprocess.run(["git", "add", "-A"], cwd=ws, env=env, check=True, capture_output=True)
        names = subprocess.run(["git", "diff", "--cached", "--name-only", start], cwd=ws, env=env, check=True,
                               capture_output=True, text=True).stdout.split()
        keep = [n for n in names if not attempt_picker.is_test_path(n)]
        if not keep:
            return ""
        return subprocess.run(["git", "diff", "--cached", start, "--", *keep], cwd=ws, env=env, check=True,
                              capture_output=True, text=True).stdout


# --------------------------------------------------------------------------- best_of_3 pick

def cmd_pick(runs_dir: Path, iid: str, run: str) -> None:
    inst = load_instances()[iid]
    ws = runs_dir / "best_of_3" / iid / run
    attempts = [ws.parent / f"{run}_attempt_{i}" for i in (1, 2, 3)]
    _, start = cache_repo(runs_dir, inst)
    r = RUNNERS[inst["repo"]]
    res = attempt_picker.pick_git(attempts, start, f"./run_tests.sh {r['runner']} {{tests}}",
                                  label_style=r["label_style"], label_root=r["label_root"])
    if ws.exists():
        shutil.rmtree(ws)
    shutil.copytree(res["winner"], ws, symlinks=True)
    (ws / ".swarm").mkdir(exist_ok=True)
    (ws / ".swarm" / "pick.json").write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"winner": Path(res["winner"]).name,
                      "scores": {Path(a["attempt"]).name: a["cross_test_score"] for a in res["attempts"]}}))


# --------------------------------------------------------------------------- evaluate

def _telemetry(meta: dict[str, Any], arm: str, iid: str, run: str) -> dict[str, Any]:
    entry = meta.get(arm, {}).get(iid, {}).get(run, {})
    out = {"wall_seconds": entry.get("wall_seconds"), "tokens": entry.get("reported_tokens")}
    if entry.get("conversation_ids"):
        import evaluate_benchmarks as eb  # Antigravity transcripts

        tel = [eb.inspect_subagent_transcript(c) for c in entry["conversation_ids"]]
        out["transcript_tokens_est"] = sum(t["transcript_tokens_est"] for t in tel)
        out["tool_calls"] = sum(t["tool_calls"] for t in tel)
    return out


def cmd_evaluate(runs_dir: Path, telemetry_file: Path, results_file: Path, harness: str, max_workers: int) -> None:
    insts = load_instances()
    meta = json.loads(telemetry_file.read_text()) if telemetry_file.exists() else {}
    eval_dir = runs_dir / "_eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {"dataset": DATASET, "harness": harness, "arms": {}, "summary": {}}
    for arm in ARMS:
        by_run: dict[str, list[tuple[str, Path]]] = {}
        for iid in INSTANCE_IDS:
            for ws in sorted((runs_dir / arm / iid).glob("r[0-9]*")):
                if ws.name[1:].isdigit() and not (ws / "PENDING_PICK").exists():
                    by_run.setdefault(ws.name, []).append((iid, ws))
        for run, items in sorted(by_run.items()):
            model = f"{harness}__{arm}__{run}"
            preds, rows = [], {}
            for iid, ws in items:
                _, start = cache_repo(runs_dir, insts[iid])
                patch = extract_patch(ws, start)
                tel = _telemetry(meta, arm, iid, run)
                if tel["wall_seconds"] is None:
                    # No telemetry yet: never worked on, or still running. Grading a half-done
                    # workspace would score a snapshot, so it stays pending until recorded.
                    if patch:
                        print(f"pending (changes on disk but no telemetry recorded): {arm}/{iid}/{run}")
                    continue
                preds.append({"instance_id": iid, "model_name_or_path": model, "model_patch": patch})
                rows[iid] = {"patch_lines": patch.count("\n"), **tel}
            if not preds:
                continue
            pred_file = eval_dir / f"{model}.jsonl"
            pred_file.write_text("".join(json.dumps(p) + "\n" for p in preds), encoding="utf-8")
            subprocess.run(
                [sys.executable, "-m", "swebench.harness.run_evaluation", "-d", DATASET, "-p", str(pred_file),
                 "-id", model, "--max_workers", str(max_workers), "-i", *rows],
                cwd=eval_dir, check=True,
            )
            report = json.loads((eval_dir / f"{model}.{model}.json").read_text())
            resolved = set(report.get("resolved_ids", []))
            for iid in rows:
                rows[iid]["resolved"] = iid in resolved
            results["arms"].setdefault(arm, {})[run] = rows
        if arm in results["arms"]:
            cells = [c for run in results["arms"][arm].values() for c in run.values()]
            toks = [c["tokens"] for c in cells if c.get("tokens")]
            walls = [c["wall_seconds"] for c in cells if c.get("wall_seconds")]
            results["summary"][arm] = {
                "resolved": f"{sum(c['resolved'] for c in cells)}/{len(cells)}",
                "mean_tokens": round(sum(toks) / len(toks)) if toks else None,
                "mean_wall_seconds": round(sum(walls) / len(walls), 1) if walls else None,
            }
    results_file.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results["summary"], indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description="SWE-bench Verified benchmark (T13)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("select")
    sub.add_parser("pull")
    s = sub.add_parser("setup")
    s.add_argument("--runs-dir", required=True)
    s.add_argument("--arms", nargs="+", default=list(ARMS), choices=ARMS)
    s.add_argument("--instances", nargs="+", default=INSTANCE_IDS)
    s.add_argument("--runs", type=int, default=1)
    p = sub.add_parser("pick")
    p.add_argument("--runs-dir", required=True)
    p.add_argument("--instance", required=True)
    p.add_argument("--run", default="r1")
    e = sub.add_parser("evaluate")
    e.add_argument("--runs-dir", required=True)
    e.add_argument("--telemetry-file", required=True)
    e.add_argument("--results-file", required=True)
    e.add_argument("--harness", default="run", help="Label for this harness/model, used in grader run IDs")
    e.add_argument("--max-workers", type=int, default=4)
    args = ap.parse_args()

    if args.cmd == "select":
        cmd_select()
    elif args.cmd == "pull":
        cmd_pull()
    elif args.cmd == "setup":
        cmd_setup(Path(args.runs_dir).resolve(), args.arms, args.instances, args.runs)
    elif args.cmd == "pick":
        cmd_pick(Path(args.runs_dir).resolve(), args.instance, args.run)
    elif args.cmd == "evaluate":
        cmd_evaluate(Path(args.runs_dir).resolve(), Path(args.telemetry_file).resolve(),
                     Path(args.results_file).resolve(), args.harness, args.max_workers)


if __name__ == "__main__":
    main()
