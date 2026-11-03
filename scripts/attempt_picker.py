#!/usr/bin/env python3
"""Pick the best of several independent attempts at one task by cross-testing them (no LLM judge).

Each attempt is a workspace with its implementation and a `tests/` folder written by the same agent.
Every attempt's test suite runs against every attempt's implementation. Independent attempts tend to make
different mistakes, so a test one agent wrote often catches a bug another agent made; the implementation
that passes the largest share of all suites wins.

Ranking, in order:
  1. `--check-cmd` passes in the attempt (e.g. the task's outcome command), if given;
  2. the attempt's own test suite passes;
  3. cross-test score: mean over all suites of the fraction of that suite's tests the implementation passes;
  4. lower attempt index (deterministic tie-break).

Git mode (`--git-base`) is for attempts that are checkouts of one existing repository, where tests live in
the project's own suite instead of a top-level `tests/` folder. Each attempt's suite is the set of test files it
added or changed relative to the base commit; each of those files runs against every attempt's code through
`--test-cmd` (a template with `{tests}`, run from the attempt's folder), and a file counts as passed when the
command exits 0.

Usage:
  python3 scripts/attempt_picker.py --attempts A1 A2 A3 [--check-cmd "<cmd>"] [--install-into DEST] [--json]
  python3 scripts/attempt_picker.py --attempts A1 A2 A3 --git-base <commit> --test-cmd "./run_tests.sh pytest {tests}" \
      [--label-style path|dotted --label-root tests] [--install-into DEST] [--json]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# Runs unittest discovery on `tests/` and prints {test_id: passed} as JSON on the last line.
_RUNNER = r"""
import json, sys, unittest
sys.path.insert(0, ".")
results = {}

class Collect(unittest.TestResult):
    def addSuccess(self, test):
        results[test.id()] = True
    def addFailure(self, test, err):
        results[test.id()] = False
    def addError(self, test, err):
        results[test.id()] = False
    def addUnexpectedSuccess(self, test):
        results[test.id()] = False
    def addExpectedFailure(self, test, err):
        results[test.id()] = True

suite = unittest.TestLoader().discover("tests")
suite.run(Collect())
print(json.dumps(results))
"""

IGNORED = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".swarm")
TEST_DIRS = {"tests", "testing"}


def is_test_path(rel: str) -> bool:
    """Python test files by the common layouts: under `tests/` or `testing/`, or named `test_*.py` / `*_test(s).py`."""
    parts = rel.split("/")
    name = parts[-1]
    if not name.endswith(".py"):
        return False
    return (
        any(p in TEST_DIRS for p in parts[:-1])
        or name.startswith("test_")
        or name in ("tests.py", "test.py")
        or name.endswith(("_test.py", "_tests.py"))
    )


def to_label(rel: str, style: str = "path", root: str = "") -> str:
    """`path` keeps the file path; `dotted` turns `tests/app/test_x.py` into `app.test_x` (Django-style labels)."""
    if style == "path":
        return rel
    if root and rel.startswith(root.rstrip("/") + "/"):
        rel = rel[len(root.rstrip("/")) + 1:]
    return rel[:-3].replace("/", ".") if rel.endswith(".py") else rel.replace("/", ".")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


def changed_test_files(repo: Path, base: str) -> list[str]:
    """Test files the attempt added or changed relative to `base` (committed, staged, unstaged or untracked)."""
    changed = set(_git(repo, "diff", "--name-only", base).split())
    changed |= set(_git(repo, "ls-files", "--others", "--exclude-standard").split())
    return sorted(f for f in changed if is_test_path(f) and (repo / f).is_file())


def run_suite(impl: Path, tests: Path, timeout: float) -> dict[str, bool]:
    """Run the test suite in `tests` against the implementation in `impl`; returns {test_id: passed}."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "ws"
        shutil.copytree(impl, work, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".swarm", "tests"))
        shutil.copytree(tests, work / "tests", ignore=IGNORED)
        try:
            proc = subprocess.run(
                [sys.executable, "-c", _RUNNER], cwd=work, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            return {"<timeout>": False}
        lines = [l for l in proc.stdout.splitlines() if l.strip()]
        try:
            return json.loads(lines[-1]) if lines else {"<no output>": False}
        except json.JSONDecodeError:
            return {"<unparseable output>": False}


def run_cmd(cmd: str, cwd: Path, timeout: float) -> bool:
    try:
        return subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, timeout=timeout).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def pick(attempts: list[Path], check_cmd: str = "", timeout: float = 120.0) -> dict[str, Any]:
    suites = {a: a / "tests" for a in attempts if (a / "tests").is_dir()}
    report: list[dict[str, Any]] = []
    for idx, impl in enumerate(attempts):
        per_suite: dict[str, dict[str, int]] = {}
        fractions: list[float] = []
        own_pass = False
        for owner, tests in suites.items():
            res = run_suite(impl, tests, timeout)
            passed = sum(1 for ok in res.values() if ok)
            total = len(res)
            per_suite[owner.name] = {"passed": passed, "total": total}
            if total:
                fractions.append(passed / total)
            if owner == impl:
                own_pass = total > 0 and passed == total
        report.append({
            "attempt": str(impl),
            "index": idx,
            "check_cmd_passed": run_cmd(check_cmd, impl, timeout) if check_cmd else None,
            "own_tests_passed": own_pass,
            "cross_test_score": round(sum(fractions) / len(fractions), 4) if fractions else 0.0,
            "per_suite": per_suite,
        })

    def rank(r: dict[str, Any]) -> tuple:
        return (r["check_cmd_passed"] is not False, r["own_tests_passed"], r["cross_test_score"], -r["index"])

    winner = max(report, key=rank)
    return {"winner": winner["attempt"], "attempts": report}


def pick_git(
    attempts: list[Path], base: str, test_cmd: str, label_style: str = "path", label_root: str = "",
    timeout: float = 900.0,
) -> dict[str, Any]:
    """Cross-test checkouts of one repository; see the module docstring (git mode)."""
    suites = {a: changed_test_files(a, base) for a in attempts}
    report: list[dict[str, Any]] = []
    for idx, impl in enumerate(attempts):
        per_suite: dict[str, dict[str, Any]] = {}
        fractions: list[float] = []
        own_pass = False
        for owner, files in suites.items():
            if not files:
                continue
            passed: list[str] = []
            with tempfile.TemporaryDirectory() as tmp:
                work = Path(tmp) / "ws"
                shutil.copytree(impl, work, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                for f in files:
                    (work / f).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(owner / f, work / f)
                for f in files:
                    if run_cmd(test_cmd.format(tests=to_label(f, label_style, label_root)), work, timeout):
                        passed.append(f)
            per_suite[owner.name] = {"passed": len(passed), "total": len(files), "files": files}
            fractions.append(len(passed) / len(files))
            if owner == impl:
                own_pass = len(passed) == len(files)
        report.append({
            "attempt": str(impl),
            "index": idx,
            "check_cmd_passed": None,
            "own_tests_passed": own_pass,
            "cross_test_score": round(sum(fractions) / len(fractions), 4) if fractions else 0.0,
            "per_suite": per_suite,
        })
    winner = max(report, key=lambda r: (r["own_tests_passed"], r["cross_test_score"], -r["index"]))
    return {"winner": winner["attempt"], "attempts": report}


def install(winner: Path, dest: Path) -> None:
    """Copy the winning attempt's files into `dest`, replacing what is there except `.git` and `.swarm`."""
    dest.mkdir(parents=True, exist_ok=True)
    for item in winner.iterdir():
        if item.name in (".git", "__pycache__"):
            continue
        target = dest / item.name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        if item.is_dir():
            shutil.copytree(item, target, ignore=IGNORED)
        else:
            shutil.copy2(item, target)


def main() -> None:
    ap = argparse.ArgumentParser(description="Pick the best of several attempts by cross-testing them")
    ap.add_argument("--attempts", nargs="+", required=True, help="Attempt workspace folders, each with tests/")
    ap.add_argument("--check-cmd", default="", help="Command that must pass in an attempt (e.g. the outcome command)")
    ap.add_argument("--install-into", default="", help="Copy the winning attempt's files into this folder")
    ap.add_argument("--timeout", type=float, default=120.0, help="Seconds per test-suite run")
    ap.add_argument("--git-base", default="", help="Git mode: commit the attempts started from")
    ap.add_argument("--test-cmd", default="", help="Git mode: command template with {tests}, run in each attempt folder")
    ap.add_argument("--label-style", choices=("path", "dotted"), default="path", help="Git mode: how {tests} is written")
    ap.add_argument("--label-root", default="", help="Git mode: folder stripped before dotted labels (e.g. tests)")
    ap.add_argument("--json", action="store_true", help="Print the full report as JSON")
    args = ap.parse_args()

    attempts = [Path(a).resolve() for a in args.attempts]
    missing = [str(a) for a in attempts if not a.is_dir()]
    if missing:
        sys.exit(f"Attempt folder(s) not found: {', '.join(missing)}")
    if args.git_base:
        if not args.test_cmd:
            sys.exit("--git-base needs --test-cmd")
        res = pick_git(attempts, args.git_base, args.test_cmd, args.label_style, args.label_root, args.timeout)
    else:
        res = pick(attempts, check_cmd=args.check_cmd, timeout=args.timeout)
    if args.install_into:
        install(Path(res["winner"]), Path(args.install_into).resolve())
        res["installed_into"] = str(Path(args.install_into).resolve())
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        for r in res["attempts"]:
            mark = "*" if r["attempt"] == res["winner"] else " "
            print(f"{mark} {r['attempt']}: check={r['check_cmd_passed']} own_tests={r['own_tests_passed']} "
                  f"cross_test_score={r['cross_test_score']}")
        print(f"winner: {res['winner']}")


if __name__ == "__main__":
    main()
