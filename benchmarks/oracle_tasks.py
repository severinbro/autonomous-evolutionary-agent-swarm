"""Oracle-graded tasks T9-T11 for `evaluate_benchmarks.py`.

Each task names a public standard instead of spelling out its rules, so a run can only pass by knowing
and applying the standard. Hidden checks compare the workspace's code against case files generated
from the reference implementation (`benchmarks/oracles/`):

  - T9  semver ranges   <- node `semver` 7.x (`npm`), default options
  - T10 cron schedules  <- `croniter`, standard 5-field syntax (cases where croniter departs from
                           crontab(5), such as `*/n` day fields, are left out)
  - T11 gitignore       <- `git ls-files --others --ignored --exclude-standard`

Evaluators return `(defects, score)`: `score` is the fraction of oracle cases answered correctly,
which separates runs even when none of them gets every case right.
"""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

ORACLE_DIR = Path(__file__).resolve().parent / "oracles"
ARMS_ORACLE = ("single_agent_checked", "best_of_3", "spec_tester", "swarm_peers")

NO_ORACLE_RULE = """
## Rules
- Python standard library only: no third-party packages.
- Work from your knowledge of the referenced standard. Do not run, import, or consult another implementation of it (for example Node's `semver`, the `git` binary, `croniter`, or any package) — neither at runtime nor to produce expected values for your tests.
"""


def _load(name: str) -> dict[str, Any]:
    return json.loads((ORACLE_DIR / name).read_text(encoding="utf-8"))


def _summarize(label: str, mismatches: list[str], total: int) -> list[str]:
    if not mismatches:
        return []
    shown = "; ".join(mismatches[:4])
    return [f"{label}: {len(mismatches)}/{total} cases wrong, e.g. {shown}"]


def _source_policy_defects(ws: Path, files: list[str]) -> list[str]:
    """Flag non-stdlib imports and subprocess use (calling git/node would bypass the task)."""
    defects: list[str] = []
    # The workspace's own modules (imported as `src.x` or, with a path tweak, as plain `x`) are local.
    local = {"src"} | {p.stem for p in (ws / "src").glob("*.py")}
    stdlib = set(sys.stdlib_module_names)
    for rel in files:
        path = ws / rel
        if not path.is_file():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module.split(".")[0]]
            for n in names:
                if n in local:
                    continue
                if n not in stdlib:
                    defects.append(f"[POLICY] {rel} imports non-stdlib module `{n}`")
                if n in ("subprocess",):
                    defects.append(f"[POLICY] {rel} imports `subprocess` (must not call other implementations)")
    return defects


def _map_cases(call_with_timeout: Callable[..., Any], fn: Callable[[Any], Any], cases: list[Any],
               timeout: float) -> list[Any]:
    """Apply `fn` to every case inside one child process; exceptions become `('EXC', name)` values."""

    def run_all() -> list[Any]:
        out = []
        for c in cases:
            try:
                out.append(fn(c))
            except Exception as exc:  # recorded as the case's output
                out.append(("EXC", type(exc).__name__))
        return out

    return call_with_timeout(run_all, timeout=timeout)


# --------------------------------------------------------------------------- T9 semver

T9_SPEC = """# Build Task 9: npm-Compatible Semantic Version Ranges

Implement Python modules under `src/` that reproduce the behaviour of the npm `semver` package (node-semver 7.x) with its default options (not loose, `includePrerelease` off), with unit tests under `tests/test_semver.py`.

## Required Files & API Specification
1. `src/version.py`:
   - `valid(text: str) -> str | None`: like `semver.valid(text)`: the normalized version string, or `None` if `text` is not a valid version.
   - `compare(a: str, b: str) -> int`: like `semver.compare(a, b)`: `-1`, `0` or `1` by version precedence. Raises `ValueError` for an invalid version.
2. `src/ranges.py`:
   - `satisfies(version: str, range_text: str) -> bool`: like `semver.satisfies(version, range_text)`, including returning `False` for an invalid version or range.
   - `max_satisfying(versions: list[str], range_text: str) -> str | None`: like `semver.maxSatisfying`: the highest version in `versions` that satisfies the range, returned exactly as given, or `None`.
   - Support every range syntax node-semver accepts in default mode.
3. `src/cli.py`: CLI entrypoint `python3 -m src.cli satisfies <version> <range>` (prints `true`/`false`) and `python3 -m src.cli max <range> <version>...` (prints the result or `null`).
4. `tests/test_semver.py`: unit test suite runnable via `python3 -m unittest discover -s tests -v`.
""" + NO_ORACLE_RULE


def eval_t9(ws: Path, load_modules: Callable[[Path], None], call_with_timeout: Callable[..., Any]):
    cases = _load("t9_semver_cases.json")
    load_modules(ws)
    try:
        from src.version import compare, valid  # type: ignore
        from src.ranges import max_satisfying, satisfies  # type: ignore
    except Exception as exc:
        return [f"Import failure: {exc!r}"], 0.0

    defects: list[str] = []
    correct = total = 0
    groups = [
        ("valid", cases["valid"], lambda c: valid(c[0]), lambda c: c[1]),
        ("compare", cases["compare"], lambda c: compare(c[0], c[1]), lambda c: c[2]),
        ("satisfies", cases["satisfies"], lambda c: satisfies(c[0], c[1]), lambda c: c[2]),
        ("max_satisfying", cases["max_satisfying"], lambda c: max_satisfying(list(c[0]), c[1]), lambda c: c[2]),
    ]
    for label, group, fn, expected in groups:
        try:
            got = _map_cases(call_with_timeout, fn, group, timeout=60)
        except Exception as exc:
            defects.append(f"{label}: evaluation failed ({exc!r})")
            total += len(group)
            continue
        wrong = []
        for c, g in zip(group, got):
            exp = expected(c)
            ok = g == exp and isinstance(g, bool) if label == "satisfies" else g == exp
            total += 1
            if ok:
                correct += 1
            else:
                wrong.append(f"{c[:-1]} -> {g!r} (expected {exp!r})")
        defects += _summarize(label, wrong, len(group))
    defects += _source_policy_defects(ws, ["src/version.py", "src/ranges.py", "src/cli.py"])
    return defects, (correct / total if total else 0.0)


# --------------------------------------------------------------------------- T10 cron

T10_SPEC = """# Build Task 10: Cron Schedule Calculator

Implement a cron expression parser and next-fire calculator under `src/` that follows standard cron semantics as documented in crontab(5) for Vixie cron / cronie, with unit tests under `tests/test_cron.py`.

## Required Files & API Specification
1. Expressions have the five standard time fields (minute, hour, day of month, month, day of week) with all the syntax crontab(5) defines for them, plus the `@yearly`, `@annually`, `@monthly`, `@weekly`, `@daily`, `@midnight` and `@hourly` shortcuts (`@reboot` is not supported).
2. `src/parser.py`: `parse(expr: str) -> Schedule`; raises `ValueError` for any expression crontab(5) does not accept.
3. `src/schedule.py`:
   - `next_fire(expr: str, after: datetime) -> datetime`: the first time strictly after `after` at which the schedule fires. Datetimes are naive (no time zones); results have `second == 0` and `microsecond == 0`.
   - `next_fires(expr: str, after: datetime, n: int) -> list[datetime]`: the next `n` fire times after `after`, in order.
4. `src/cli.py`: CLI entrypoint `python3 -m src.cli "<expr>" <iso-datetime> [n]` printing one ISO datetime per line.
5. `tests/test_cron.py`: unit test suite runnable via `python3 -m unittest discover -s tests -v`.
""" + NO_ORACLE_RULE


def eval_t10(ws: Path, load_modules: Callable[[Path], None], call_with_timeout: Callable[..., Any]):
    cases = _load("t10_cron_cases.json")
    load_modules(ws)
    try:
        from src.parser import parse  # type: ignore
        from src.schedule import next_fires  # type: ignore
    except Exception as exc:
        return [f"Import failure: {exc!r}"], 0.0

    defects: list[str] = []
    correct = total = 0
    fires = cases["next_fires"]

    def one(c):
        got = next_fires(c[0], datetime.fromisoformat(c[1]), 5)
        return [d.isoformat() for d in got]

    # One child per expression so a schedule that loops forever costs only its own cases.
    wrong = []
    by_expr: dict[str, list[Any]] = {}
    for c in fires:
        by_expr.setdefault(c[0], []).append(c)
    timeouts = 0
    for expr, group in by_expr.items():
        if timeouts >= 3:
            got = [("EXC", "skipped after repeated timeouts")] * len(group)
        else:
            try:
                got = _map_cases(call_with_timeout, one, group, timeout=10)
            except TimeoutError:
                timeouts += 1
                got = [("EXC", "TimeoutError")] * len(group)
        for c, g in zip(group, got):
            total += 1
            if g == c[2]:
                correct += 1
            else:
                wrong.append(f"{c[0]!r} after {c[1]} -> {g!r} (expected {c[2]!r})")
    defects += _summarize("next_fires", wrong, len(fires))

    def rejects(expr):
        try:
            parse(expr)
        except ValueError:
            return True
        return False

    invalid = cases["invalid"]
    try:
        got = _map_cases(call_with_timeout, rejects, invalid, timeout=20)
    except Exception as exc:
        got = [("EXC", repr(exc))] * len(invalid)
    wrong = []
    for e, g in zip(invalid, got):
        total += 1
        if g is True:
            correct += 1
        else:
            wrong.append(f"parse({e!r}) did not raise ValueError ({g!r})")
    defects += _summarize("invalid expressions", wrong, len(invalid))
    defects += _source_policy_defects(ws, ["src/parser.py", "src/schedule.py", "src/cli.py"])
    return defects, (correct / total if total else 0.0)


# --------------------------------------------------------------------------- T11 gitignore

T11_SPEC = """# Build Task 11: Gitignore Matcher

Implement under `src/` a matcher that decides which files Git ignores, given the contents of a single top-level `.gitignore`, exactly as Git does for untracked files (gitignore(5)), with unit tests under `tests/test_gitignore.py`.

## Required Files & API Specification
1. `src/patterns.py`: parsing of `.gitignore` lines into patterns.
2. `src/matcher.py`:
   - `GitIgnore(text: str)`: built from the full text of the `.gitignore` file.
   - `is_ignored(path: str) -> bool`: whether Git ignores the file at `path`, a path relative to the repository root with `/` separators. Paths always name files, never directories.
   - `ignored_files(paths: list[str]) -> list[str]`: the ignored paths, sorted.
3. `src/cli.py`: CLI entrypoint `python3 -m src.cli <gitignore_path> <path>...` printing each ignored path on its own line.
4. Scope: only the one `.gitignore` at the repository root applies (no nested `.gitignore` files, no `.git/info/exclude`, no global excludes file). Paths are case-sensitive.
5. `tests/test_gitignore.py`: unit test suite runnable via `python3 -m unittest discover -s tests -v`.
""" + NO_ORACLE_RULE


def eval_t11(ws: Path, load_modules: Callable[[Path], None], call_with_timeout: Callable[..., Any]):
    cases = _load("t11_gitignore_cases.json")
    load_modules(ws)
    try:
        from src.matcher import GitIgnore  # type: ignore
    except Exception as exc:
        return [f"Import failure: {exc!r}"], 0.0

    files = cases["files"]
    defects: list[str] = []
    correct = total = 0
    for sc in cases["scenarios"]:
        text = "\n".join(sc["gitignore"]) + "\n"
        expected = set(sc["ignored"])

        def run(_c, text=text):
            gi = GitIgnore(text)
            return [bool(gi.is_ignored(f)) for f in files] + [list(gi.ignored_files(list(files)))]

        try:
            got = _map_cases(call_with_timeout, run, [None], timeout=20)[0]
        except Exception as exc:
            got = ("EXC", repr(exc))
        label = f"gitignore {sc['gitignore']!r}"
        if isinstance(got, tuple):
            total += len(files) + 1
            defects.append(f"{label}: raised {got[1]}")
            continue
        wrong = [f"{f} -> {g}" for f, g in zip(files, got[:-1]) if g != (f in expected)]
        total += len(files) + 1
        correct += len(files) - len(wrong)
        if got[-1] == sorted(expected):
            correct += 1
        else:
            wrong.append(f"ignored_files -> {got[-1]!r}")
        defects += _summarize(label, wrong, len(files) + 1)
    defects += _source_policy_defects(ws, ["src/patterns.py", "src/matcher.py", "src/cli.py"])
    return defects, (correct / total if total else 0.0)


# --------------------------------------------------------------------------- T12 CommonMark

T12_SPEC = """# Build Task 12: CommonMark Markdown Renderer

Implement a Markdown-to-HTML renderer under `src/` that conforms to the CommonMark Spec, version 0.31.2, with unit tests under `tests/test_commonmark.py`.

## Required Files & API Specification
1. `src/blocks.py`: block-structure parsing (container and leaf blocks, link reference definitions).
2. `src/inlines.py`: inline parsing (code spans, emphasis and strong emphasis, links and images, autolinks, raw HTML, hard and soft line breaks, backslash escapes, entity and numeric character references).
3. `src/render.py`: `render(markdown: str) -> str` returning the HTML the CommonMark reference implementation produces for `markdown`, in the same form as the spec's examples (for example `"# Hi\\n"` renders as `"<h1>Hi</h1>\\n"`).
4. `src/cli.py`: CLI entrypoint `python3 -m src.cli` that reads Markdown from stdin and writes HTML to stdout.
5. `tests/test_commonmark.py`: unit test suite runnable via `python3 -m unittest discover -s tests -v`.
""" + NO_ORACLE_RULE + """- No network access: do not download the spec, its examples, or any other material.
"""


def _normalize_html(text: str) -> str:
    """Whitespace-insensitive comparison form, in the spirit of the spec's own test runner."""
    import re

    text = re.sub(r"\s+", " ", text)
    return re.sub(r"\s*(<[^>]+>)\s*", r"\1", text).strip()


def eval_t12(ws: Path, load_modules: Callable[[Path], None], call_with_timeout: Callable[..., Any]):
    examples = json.loads((ORACLE_DIR / "t12_commonmark_spec_0.31.2.json").read_text(encoding="utf-8"))
    load_modules(ws)
    try:
        from src.render import render  # type: ignore
    except Exception as exc:
        return [f"Import failure: {exc!r}"], 0.0

    by_section: dict[str, list[dict[str, Any]]] = {}
    for ex in examples:
        by_section.setdefault(ex["section"], []).append(ex)
    defects: list[str] = []
    correct = 0
    for section, group in by_section.items():
        try:
            got = _map_cases(call_with_timeout, lambda ex: render(ex["markdown"]), group, timeout=30)
        except Exception as exc:
            got = [("EXC", repr(exc))] * len(group)
        wrong = []
        for ex, g in zip(group, got):
            if isinstance(g, str) and _normalize_html(g) == _normalize_html(ex["html"]):
                correct += 1
            else:
                wrong.append(f"example {ex['example']}")
        defects += _summarize(f"section {section!r}", wrong, len(group))
    defects += _source_policy_defects(ws, ["src/blocks.py", "src/inlines.py", "src/render.py", "src/cli.py"])
    return defects, correct / len(examples)


# --------------------------------------------------------------------------- registration

def tasks() -> dict[str, dict[str, Any]]:
    common = {
        "arms": ARMS_ORACLE,
        "wiring_files": ["src/cli.py"],
        "verification_cmd": "python3 -m unittest discover -s tests -v",
    }
    return {
        "task_9_semver_ranges": {
            **common,
            "id": "T9",
            "title": "npm-Compatible Semantic Version Ranges (oracle: node-semver)",
            "spec_md": T9_SPEC,
            "target_files": ["src/version.py", "src/ranges.py", "src/cli.py"],
            "required_symbols": ["satisfies", "max_satisfying"],
            "outcome_cmd": (
                'python3 -c "from src.ranges import satisfies, max_satisfying; '
                "assert satisfies('1.2.5', '^1.2.3') and not satisfies('2.0.0', '^1.2.3'); "
                "assert max_satisfying(['1.2.3', '1.4.0', '2.0.0'], '~1.2') == '1.2.3'; print('SEMVER_OK')\""
            ),
            "expect_output": "SEMVER_OK",
            "review_focus": [
                "Every function behaves like node-semver 7.x with default options, for all inputs node-semver accepts or rejects",
                "src/cli.py must call satisfies and max_satisfying",
            ],
            "evaluator": eval_t9,
        },
        "task_10_cron_schedule": {
            **common,
            "id": "T10",
            "title": "Cron Schedule Calculator (oracle: croniter on crontab(5) syntax)",
            "spec_md": T10_SPEC,
            "target_files": ["src/parser.py", "src/schedule.py", "src/cli.py"],
            "required_symbols": ["next_fires"],
            "outcome_cmd": (
                'python3 -c "from datetime import datetime; from src.schedule import next_fire; '
                "assert next_fire('0 9 * * 1-5', datetime(2026, 11, 6, 10, 0)) == datetime(2026, 11, 9, 9, 0); "
                "print('CRON_OK')\""
            ),
            "expect_output": "CRON_OK",
            "review_focus": [
                "Every expression is interpreted exactly as crontab(5) (Vixie cron / cronie) defines, and anything it rejects raises ValueError",
                "src/cli.py must call next_fires",
            ],
            "evaluator": eval_t10,
        },
        "task_11_gitignore_matcher": {
            **common,
            "id": "T11",
            "title": "Gitignore Matcher (oracle: git ls-files --ignored)",
            "spec_md": T11_SPEC,
            "target_files": ["src/patterns.py", "src/matcher.py", "src/cli.py"],
            "required_symbols": ["GitIgnore"],
            "outcome_cmd": (
                'python3 -c "from src.matcher import GitIgnore; g = GitIgnore(\'*.log\\n\'); '
                "assert g.is_ignored('a/b.log') and not g.is_ignored('a/b.txt'); print('GITIGNORE_OK')\""
            ),
            "expect_output": "GITIGNORE_OK",
            "review_focus": [
                "is_ignored matches what Git itself reports for untracked files under the given .gitignore, for every pattern form gitignore(5) documents",
                "src/cli.py must call GitIgnore",
            ],
            "evaluator": eval_t11,
        },
        "task_12_commonmark": {
            **common,
            "id": "T12",
            "title": "CommonMark 0.31.2 Markdown Renderer (oracle: the spec's 652 examples)",
            "spec_md": T12_SPEC,
            "target_files": ["src/blocks.py", "src/inlines.py", "src/render.py", "src/cli.py"],
            "required_symbols": ["render"],
            "outcome_cmd": (
                'python3 -c "from src.render import render; '
                "assert render('# Hi\\\\n\\\\n*a* **b**\\\\n') == '<h1>Hi</h1>\\\\n<p><em>a</em> <strong>b</strong></p>\\\\n'; "
                "print('COMMONMARK_OK')\""
            ),
            "expect_output": "COMMONMARK_OK",
            "review_focus": [
                "render() output matches the CommonMark 0.31.2 reference implementation for every construct the spec defines",
                "src/cli.py must call render",
            ],
            "evaluator": eval_t12,
        },
    }
