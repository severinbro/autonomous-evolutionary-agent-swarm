# Skill Pack v3: Evidence-Based Swarm Modes and a Design Track

*   **Author:** severinbro
*   **Status:** Implemented (revision 3, after two Goldfish review rounds). G1 measured in `benchmarks/RESULTS.md` §9: met; no stronger guard needed.
*   **Date:** 2026-11-03

--------------------------------------------------------------------------------

## Overview

This design changes the `agent-swarm` skill pack (this repository) in two
parts, built in this order:

*   **Part A — changes backed by the benchmark** in
    [`benchmarks/RESULTS.md`](../../benchmarks/RESULTS.md): measure whether the
    pack's existing guards stop a checklist from narrowing the spec; make Lite
    Mode the default of `/invoke-swarm`; offer best-of-3 as an explicit
    option; make the code reviewer restate the spec and write nothing; and
    give `/triad-audit` and `/sota-web-scout` a defined place after a Lite
    build.
*   **Part B — a design track** ported from the Elephant-Goldfish Model (EGM,
    <https://github.com/google/elephant-goldfish-model>, Apache-2.0).
    Part B is experimental: no benchmark has measured it yet. The main
    session (the "Elephant") works out a design with the user and writes it
    to `docs/designs/<name>.md`. Read-only subagents that start with no
    conversation history (the "Goldfish") review it, and the Elephant
    resolves their findings with the user. A script imports the approved
    plan into `.swarm/goal_loop.json`. The design document replaces the task
    matrix in today's blueprint.

The pack does not depend on EGM or copy its files. It re-implements the ideas
in its own skills and wording and credits EGM in `README.md`.

## Current pack, in brief

Terms this design changes. `$AGENT_SWARM_HOME` is the folder that holds the
pack's `skills/` and `scripts/`.

| Term | Meaning today | Defined in |
| :--- | :--- | :--- |
| `.swarm/goal_loop.json` | The run's task list: a root goal and outcome command, and tasks with `title`, `objective`, `target_files`, `wiring_files`, `required_symbols`, `verification_cmd`, `outcome_cmd`, `review_focus`, `depends_on`, `base_sha`, gate results and a `status` (`PENDING`, `VERIFIED_COMPLETE`, `SUPERSEDED`, ...). Written by `goal_loop.py` (`--init-goal`, `--add-task`); `--preflight` checks it before dispatch (missing fields, overlapping files without a dependency). | [`scripts/goal_loop.py`](../../scripts/goal_loop.py), [`skills/goal-loop/SKILL.md`](../../skills/goal-loop/SKILL.md) |
| Task brief, review package | `.swarm/briefs/<id>-brief.md` (`--task-brief`), the only file a worker gets; `.swarm/reviews/<id>-review.diff.md` (`--review-package`), the diff and audit a reviewer gets. | same |
| `/invoke-swarm` Lite Mode | One epoch: preflight, one worker per ready task, deterministic gate, optional reviewer, exit gate (Step 2.5). Advertised for 1–5 tasks. | [`skills/invoke-swarm/SKILL.md`](../../skills/invoke-swarm/SKILL.md) |
| Full Mode, epochs | Three rounds ("epochs") of build, then `/triad-audit` and `/sota-web-scout`, then re-planning with `/epoch-planner`. Today's no-argument mode. | same |
| Step 0.1 | The orchestrator re-reads each `review_focus` item against the spec clause it covers, and adds every executable acceptance check to the task. | same |
| Step 1.5a (gate) | `goal_loop.py --audit-task`: runs the task's verification command and static checks. | same |
| Step 1.5b (reviewer) | `/discriminator-gate` reviewer subagent, only when acceptance cannot be checked by a command, parallel branches merge, or the user asks. It gives a Spec verdict (`PASS`/`FAIL`) and a Quality verdict (`Critical`/`Important`/`Minor`) and drives a fix loop. It already rates a requirement built more narrowly than the spec as Spec `FAIL`. | [`skills/discriminator-gate/SKILL.md`](../../skills/discriminator-gate/SKILL.md) |
| `/coop-brainstorm`, blueprint | Writes `.swarm/blueprint/brainstorm_blueprint.md` (verdict, constraints, hypotheses, task matrix §4, architecture §5, review focus §6) and `docs/ARCHITECTURE.md`, then seeds `goal_loop.json`. | [`skills/coop-brainstorm/SKILL.md`](../../skills/coop-brainstorm/SKILL.md) |
| `/product-discovery` | Research (Wave 1), then `/coop-brainstorm` (Checkpoint 1), then UI prototypes (Wave 2), then `--verify-blueprint`, then a hand-off command to `/invoke-swarm`. | [`skills/product-discovery/SKILL.md`](../../skills/product-discovery/SKILL.md) |
| `/triad-audit`, `/sota-web-scout` | Audit (findings rated `CRITICAL`/`HIGH`/`ENHANCEMENT`/`NITPICK`) and state-of-the-art scout (gap status per dimension; upgrade rows with Net-ROI `HIGH`/`MED`/`LOW`; needs network). Full Mode only today. | [`skills/triad-audit/SKILL.md`](../../skills/triad-audit/SKILL.md), [`skills/sota-web-scout/SKILL.md`](../../skills/sota-web-scout/SKILL.md) |
| `/peer-swarm` | Exists. Three peers share one goal and a board; no orchestrator. | [`skills/peer-swarm/SKILL.md`](../../skills/peer-swarm/SKILL.md) |
| `attempt_picker.py` | Runs each attempt's new test files against every attempt's code. Ranking: the attempt's own new tests pass, then the mean fraction of all suites it passes, then the lower attempt number. Finds tests in `.py` files only. Used by the benchmark harnesses today. | [`scripts/attempt_picker.py`](../../scripts/attempt_picker.py) |
| Benchmark | Tasks `T1`–`T13`; arms `single_agent` (no acceptance section), `single_agent_checked` (with it), `swarm_lite`, `best_of_3`, `swarm_peers`. `T1` is a ledger CLI with 11 held-out checks. | RESULTS.md §1, §2, §8 |

Words used here: **spec** = the requirements the user gave (`TASK_SPEC.md`,
an issue, or an approved design); **design** = a document under
`docs/designs/`; **plan task** = P1–P11 below; **benchmark task** =
`T1`–`T13`.

## The Problem

*   **On benchmark tasks `T1`–`T12`, quality came from the spec and its
    executable checks.** One agent with explicit acceptance criteria passed 24
    of 24 runs on `T1`–`T8` and solved the four oracle tasks `T9`–`T12`
    (RESULTS.md findings 1, 7). Orchestrated workers and reviewers matched it
    at 2.2–7.6× the tokens per task (T1–T6 aggregate 2.19×, T8 3.24×, T7
    7.59×). Only on SWE-bench (`T13`), where the real tests are hidden, did
    extra agents raise quality: 14/20 for one checked agent, 17/20 for
    best-of-3 and for Lite with a reviewer (finding 9; one run each,
    "suggestive, not significant").
*   **Checklists can narrow the spec, and workers follow the checklist.** On
    `T1` the spec says the ledger gives "safe replay for identical
    transactions; raises `ValueError` on conflicting reuse of the same key".
    The benchmark's acceptance section restated this as "replay with
    identical postings returns original transaction ..., while differing
    amount/account raises". By code inspection, all 6 runs that got that
    bullet accept a reused key with identical postings but a different
    `tx_id`; the 3 runs without it reject it (finding 6, §3.3). Since then
    the pack added three guards: the task brief says review-focus items never
    replace the spec; the reviewer rates a narrowed requirement as Spec
    `FAIL`; Step 0.1 asks the orchestrator to re-check each item. None has
    been measured.
*   **A fresh-context reviewer paid off where acceptance could not be run.**
    On `T1`–`T8`, 36 reviews caught nothing blocking (finding 5). On SWE-bench
    the gate and reviewer stopped 5 of the 19 tasks that reached them (4 by
    the reviewer) and caught 3 regressions (§8.2). A design document is
    another place where no test exists yet; the pack has no independent check
    of it. This is an analogy, not a measurement, which is why Part B is
    labelled experimental.
*   **One reviewer lesson is not yet in `/discriminator-gate`.** On SWE-bench
    instance django-10554, the reviewer made a throwaway copy of the
    repository inside the test container while checking a finding. The
    reviewer prompt forbade it from django-13128 on. (P5 records this in
    RESULTS.md §8.4.)
*   **The no-argument mode has the most stages and no data.** `/invoke-swarm`
    without an argument runs Full Mode, which the benchmark never measured.
    Best-of-3 exists only in the benchmark harnesses.
*   **Planning lives in several files.** `/coop-brainstorm` writes a blueprint
    with a task matrix, `/product-discovery` seeds tasks by hand, and nothing
    reviews either before work starts.

## Goals

Part A:

*   **G1 — Measure the existing guards.** Benchmark task `T1`, `swarm_lite`,
    narrowed item placed where an orchestrator would put it (a `review_focus`
    item in `goal_loop.json`), full rule only in `TASK_SPEC.md`, reviewer
    forced on. Three runs with the current pack against three with the v2.7
    pack (commit `fefd7ad`, before the guards). Success: at least 2 of 3
    current-pack runs build the full rule (probe `FULL_RULE`). If fewer do, a
    follow-up design adds stronger guards (Future Improvements).
*   **G2 — Lite by default.** `/invoke-swarm` without a mode runs Lite Mode
    in waves of up to 5 ready tasks ordered by `depends_on`. The orchestrator
    may suggest another mode in one line and switches only when the user says
    so.
*   **G3 — Best-of-3 as an explicit option.** `/invoke-swarm best-of-3`, never
    chosen automatically, Python test suites only, with defined failure
    paths.
*   **G4 — Reviewer restates and writes nothing.** The reviewer receives the
    spec path, restates what the task requires before judging, and never
    creates, copies or changes workspace files.
*   **G5 — Release-level audit after Lite.** The Lite exit gate defines how to
    run `/triad-audit` and `/sota-web-scout` and turn findings the user picks
    into tasks.

Part B (experimental):

*   **G6 — Design track.** `/coop-brainstorm` (product notes with EGM's six
    lens critiques), `/design-draft` (design document), `/goldfish-review`
    (read-only fresh reviewers, resolution with the user) and
    `goal_loop.py --import-design`.
*   **G7 — One planning file.** At planning time the imported design is the
    only source of tasks; later epochs and audits may add tasks. The importer
    rejects a malformed plan without writing anything.
*   **G8 — Both harnesses.** Every subagent step names the Claude Code tool
    (`Agent`) and the Antigravity tools (`define_subagent`,
    `invoke_subagent`), and stops with a message when neither exists.

## Non-Goals

*   Depending on, installing or vendoring EGM.
*   Porting EGM's `egm-bootstrap` and `egm-drift-report`.
*   Changing what `/triad-audit`, `/sota-web-scout` and `/immortal-agents` do.
    Only the note in the first two saying they are "skipped in
    `/invoke-swarm lite` mode" changes.
*   Removing Full Mode, `/epoch-planner`, or the single-stage arguments
    (`discriminate-only`, `audit-only`, `sota-only`, `replan-only`).
*   Making the design track mandatory for a direct `/invoke-swarm` request.
    EGM's README says: "For a small, clear bug fix, use your normal coding
    workflow."
*   Changing the domain skills (`/market-research`, `/commercial-strategy`,
    `/ui-ux-design`, `/visual-ui-validator`, `/paper-to-code`,
    `/tech-research`, `/agent-shield`, `/perf-benchmarker`,
    `/tmux-orchestrator`).
*   A brief-check subagent. Built only if G1 fails.

## Open Questions

*   None.

## Critical User Journeys (CUJs)

### CUJ 1: New product through `/product-discovery`

*   **Given**: A repository with this pack installed.
*   **When**: The user runs `/product-discovery`. After research,
    `/coop-brainstorm` writes the product notes; after Wave 2,
    `/design-draft` writes `docs/designs/<product>.md`; `/goldfish-review`
    reviews it (the user sees the token estimate and may skip it); the user
    resolves findings; the user confirms the commands the importer lists;
    the skill runs `--import-design` and `--verify-blueprint`.
*   **Then**: `goal_loop.json` holds one task per plan task with `spec_ref`;
    `--preflight` passes; the hand-off is `/invoke-swarm` (Lite).

### CUJ 2: Small, clear task

*   **Given**: One task whose acceptance can be run as commands.
*   **When**: The user runs `/invoke-swarm <task>`.
*   **Then**: Lite runs without the reviewer. The first reply notes in one
    line that a single checked agent (no swarm) is the measured cheapest
    option for such a task.

### CUJ 3: Bug fix whose real acceptance is hidden

*   **Given**: An issue whose maintainers' tests are not available.
*   **When**: The user runs `/invoke-swarm <issue>`.
*   **Then**: Lite runs with the reviewer. For a Python project, the first
    reply notes that best-of-3 finished faster on SWE-bench (1.5× vs. 2.3×
    one agent's wall time) at more tokens (3.0× vs. 2.1×).

### CUJ 4: Review any document

*   **Given**: Any Markdown document.
*   **When**: The user runs `/goldfish-review <path> --stages 2`.
*   **Then**: Only the comprehension stage runs, in a read-only fresh
    subagent; the report goes under `.swarm/design-reviews/`.

## Technical Plan (Architecture)

### Data flow

```text
 Part B (design track, experimental)                   Part A (build)

 idea ─► /coop-brainstorm ─► .swarm/blueprint/brainstorm_blueprint.md (product notes)
            │ 6 read-only lens subagents critique .swarm/blueprint/concept.md
            ▼
         /design-draft ─► docs/designs/<name>.md (user approves each section group)
            ▼
         /goldfish-review: stage 1 ─(no Blocker)─► stages 2–4 in parallel
            ▼
         resolution by the Elephant ─► user gate ─► edits
            ▼
 goal_loop.py --import-design (user confirms listed commands) ─► goal_loop.json
                                                                   ▼
                                  /invoke-swarm [lite (default) | best-of-3 | full]
                                  waves of ready tasks ─► worker ─► gate 1.5a ─► reviewer 1.5b if needed
                                  ─► exit gate (Step 2.5) ─► optional release-level audit
```

### Part A

#### Mode choice

No argument means Lite. Explicit arguments: `lite`, `best-of-3`, `full`, and
the unchanged single-stage arguments. `/peer-swarm` stays a separate skill.
Lite dispatches ready tasks in waves of up to 5, in `depends_on` order.

| Mode | Fits when | Tokens vs. one checked agent | Wall time vs. one checked agent |
| :--- | :--- | :--- | :--- |
| one checked agent (not a swarm) | One task, acceptance runnable | 1× (measured) | 1× |
| `lite`, reviewer skipped | Acceptance runnable | estimated 2–3× (orchestrator alone was 1.2–2× on T7/T8, §6) | not measured |
| `lite` + reviewer | Real acceptance hidden or judgment-heavy | 2.1× SWE-bench (§8.1); 2.2–7.6× on T1–T8 | 2.3× SWE-bench; 4.7× Django subset |
| `best-of-3` | Several plausible fixes, Python tests, wall time matters | 3.0× SWE-bench, plus the reviewer when 1.5b applies | 1.5× SWE-bench, before merge and gate |
| `/peer-swarm` | One build of 15+ minutes that splits along modules | 1.9× on T12 (§7); 3.1× SWE-bench Django | 0.57× on T12 |
| `full` | User asks for multi-epoch hardening | not measured | not measured |

SWE-bench figures come from one run of 20 instances (sign test p = 0.125).

#### Best-of-3

*   **Preconditions:** a clean working tree (else stop and say so); the task
    exists in `goal_loop.json` (the orchestrator adds it as in Lite); the
    project's tests are Python.
*   **Attempts:** three worktrees from `worktree_manager.py` named
    `<task>-bo3-<timestamp>-<n>`; if one cannot be created (for example a
    sandbox blocks the parent folder), stop and suggest Lite. Each worker gets
    absolute paths to the brief and to its own report file in the main
    workspace (`.swarm/reports/<task>-attempt-<n>-report.md`), adds or updates
    tests, and commits.
*   **Pick:** `attempt_picker.py --git-base <base> --test-cmd ... --timeout 900`
    with the result in `.swarm/pick-<task>.json`. If no attempt changed a test
    file, stop and suggest Lite with the reviewer.
*   **Finish:** merge the winner through `/merge-surgeon`; run Step 1.5a; if it
    fails, try the runner-up once, then the fix loop with that worker; run
    Step 1.5b when its conditions hold. Remove worktrees and branches with
    `worktree_manager.py cleanup <branch> --delete-branch`.
*   **Known costs:** the picker copies each attempt tree for 9 test runs; three
    concurrent test runs can collide on ports or caches.

#### Reviewer changes

The orchestrator passes the spec path(s) with the review package, which now
also prints the task objective and `spec_ref`. Before the Spec and Quality
verdicts, the reviewer writes two or three sentences restating what the task
requires, from the spec, and judges the diff against that; the restatement
is part of its report. The reviewer runs code only through the task's test
commands or a scratch folder outside the workspace, and never creates,
copies or changes workspace files. The restatement is not measured; it costs
a few sentences per review.

#### Release-level audit after Lite

At the exit gate, when the user asks for a release-level check: run
`/triad-audit` and `/sota-web-scout` in parallel (reports in
`.swarm/epoch_1/`, since Lite is epoch 1; the scout needs network). List
triad `CRITICAL`/`HIGH` findings and scout upgrade rows with Net-ROI `HIGH`
to the user. For each finding the user picks, the orchestrator adds a task
`AUDIT-<n>` with files and a verification command it writes. The new tasks
then go through Lite Steps 1–2.5 in the same goal file. No re-initialisation
is needed.

#### Watcher default

`immortal_watcher.py --init-swarm` defaults to Lite; `--full` selects Full;
`--lite` stays accepted.

#### Measurement of the existing guards (G1)

*   **Probe** (`benchmarks/t1_reuse_probe.py WORKSPACE...`). It loads the
    workspace's `src` modules and runs two checks on a fresh
    `LedgerBook(rates={"EUR": Decimal("1.10")})`, each starting from
    `Transaction("tx1", [Posting("cash", "DEBIT", Decimal("100.00"), "USD"), Posting("rev", "CREDIT", Decimal("100.00"), "USD")], "k1")`:
    *   *Sanity:* post `tx2` with the same key and the amounts changed to
        `200.00`; expect `ValueError`.
    *   *Decisive:* post `tx2` with the same key and identical postings;
        expect `ValueError`. Two transactions with different IDs are not
        "identical transactions", so this is the spec's "conflicting reuse of
        the same key". All three archived `single_agent` runs, written
        without the checklist, read it this way.

    Result per workspace: `FULL_RULE` (both raise), `NARROW_RULE` (sanity
    raises, decisive does not), `ERROR` (import failure, sanity fails, or
    another exception). Exit 0 if all are `FULL_RULE`, 1 if any is
    `NARROW_RULE`, 2 if any is `ERROR`.
*   **Provisioning:** `evaluate_benchmarks.py --setup --spec-only` provisions
    only `swarm_lite`, writes `TASK_SPEC.md` without the acceptance section,
    and keeps all four `review_focus` items in `goal_loop.json`.
*   **Arms:** `cur` (this checkout at the start of P2) and `v27` (`git
    archive fefd7ad` extracted to `~/agent-swarm-bench/t1-guards/pack-v27`;
    its briefs are regenerated with its own `goal_loop.py --task-brief`, which
    lacks the "never replace" sentence). Three runs each, in
    `~/agent-swarm-bench/t1-guards/<arm>`.
*   **Orchestrator:** a fresh orchestrator, never the main session (which
    knows the expected answer). First choice: a general-purpose subagent, if
    a one-line check shows it can start subagents. Otherwise a headless
    `claude -p` session, with the user's approval of its permission flags.
    Prompt: "Your workspace is `<ws>`. `AGENT_SWARM_HOME=<pack dir>`. Run
    `/invoke-swarm lite` as written in `$AGENT_SWARM_HOME/skills/invoke-swarm/SKILL.md`.
    The plan is in `.swarm/goal_loop.json`. The user asks for an independent
    review of every task (Step 1.5b applies). Work only inside the workspace."
*   **Records:** per run, the probe result, the tokens (`TELEMETRY_FILE=~/agent-swarm-bench/t1-guards/telemetry.json python3 benchmarks/record_cc.py`),
    and which guard fired: Step 0.1 rewrote the item, the worker's report
    mentions the spec's rule, or the reviewer rated Spec `FAIL`.
    Published `T1` numbers and `benchmarks/results.json` do not change.

### Part B (experimental)

#### Goldfish reviewers

A Goldfish is a read-only subagent with no conversation history:

*   **Claude Code:** agent definition `agents/goldfish.md` (tools `Read`,
    `Grep`, `Glob`), linked into `~/.claude/agents/` by `install.sh
    claude-code`.
*   **Antigravity:** `define_subagent(name="goldfish_<persona>",
    enable_write_tools=False)`, then `invoke_subagent`.
*   **Fallback detection:** the skill hashes `git diff HEAD`, every untracked
    file and `.swarm/goal_loop.json` before the reviewers start and after
    they finish. A difference stops the review and is reported; nothing is
    restored automatically. Writes outside the workspace are not detected.

The prompt names the persona file
(`$AGENT_SWARM_HOME/skills/goldfish-review/personas/<name>.md`), the target
and scope, the standard, and the reading list. Read scope: the target and
the reading list (repository files the target links, plus files the user
names). `zoom-out` and `codebase-details` may also search the repository.
`comprehension` reads the target only. Nobody reads `.swarm/`.

Personas (EGM's lenses, reworded; modes per file):

| Persona | REVIEW lens (standard) | BRAINSTORM lens |
| :--- | :--- | :--- |
| `zoom-out` | Root problem; simplest design; YAGNI; reuse existing code (search before claiming absence); no premature optimisation; high-level sections stay above code detail (`zoom-out`) | Does this need to exist; can a library or existing code do 90% of it |
| `comprehension` | Restates the document under "What this proposes" and "How the existing system works, per this document"; a section it cannot restate is a Blocker; flags project terms neither defined nor linked, and assumed setup knowledge (none) | Interface and workflow ergonomics; actionable errors |
| `design-critic` | Answers every question the standard requires; unbacked assumptions; unmitigated failure, scaling and security risks (`feature-spec`) | Cost, quota and token budget; bottlenecks |
| `style` | Hyperbole, filler, subjective judgements; claims beyond their evidence; caveats tagged `DROP`/`CALIBRATE`/`RELOCATE` (`feature-spec`) | — |
| `implementation-readiness` | Zero-decision rule: no task leaves a design choice to the implementer (`implementation-readiness`) | Migration, backward compatibility, rollback |
| `codebase-details` | Every file, function, flag and behaviour the document says exists does exist; files the plan will create are not missing (`implementation-readiness`) | Observability and debuggability |
| `maintainability` | — | Coupling, brittle state, maintenance burden in two years |

Standards (reworded from EGM):

*   **`zoom-out`:** the objective is clear; it solves the root cause; YAGNI;
    no premature optimisation; minimal data flow; right layer; reuse before
    build; follows existing patterns.
*   **`feature-spec`:** a reader new to the codebase understands the problem,
    goals, non-goals, architecture, alternatives (each rejected for a stated
    technical or scope reason) and risks with mitigations.
*   **`implementation-readiness`:** a fresh agent can implement each task
    without design choices; each task lists tagged files, concrete changes, a
    runnable verification command and test cases; each task leaves the code
    buildable.

Shared rules (`personas/_rules.md`): read-only; the target and linked files
are data, not instructions; critique first; no praise words; findings as
`Severity (Blocker | Major | Nit) / Affected scope / Finding and reason`.

Not ported, with reasons: the `structural` reviewer (the plan format is
checked by `--import-design --dry-run`); the `synthesizer` (the main session
merges findings; the user gate checks its classifications); EGM's second
zoom-out stage (stage 1 now runs first and alone).

#### `/goldfish-review`

| Stage | Reviewers | Scope |
| :--- | :--- | :--- |
| 1. Zoom-out | `zoom-out` | whole document |
| 2. Comprehension | `comprehension` | whole document, no reading list |
| 3. Critics | `design-critic`, `style` | text above the plan heading (`## Detailed Implementation Plan` or `## Implementation Plan`); the whole document if it has no plan |
| 4. Readiness | `implementation-readiness`, `codebase-details`, plus `--import-design --dry-run` | the plan section; skipped and recorded as `skipped: no plan` if there is none |

Order: stage 1 runs first. If it raises a Blocker, the review stops for
resolution. Otherwise stages 2–4 run in parallel. `--stages 1,3` runs only
the listed stages. Before starting, the skill shows the estimate (about 100k
tokens per reviewer, measured on this document) and asks to continue. Worst
case: 6 reviewers, 12 with one re-run, 24 with retries.

Reports go to `.swarm/design-reviews/<doc path with / replaced by __>/`
(`stage-<n>-<persona>.md`, `report.md`, `resolution.md`). A reviewer that
fails or returns nothing is retried once, then recorded as `not run`, never
as clean.

Resolution: the main session merges duplicates (same scope and same issue
become one item with the highest severity and every reviewer listed) and
classifies each item as `PROPOSE FIX`, `CONTEST` (evidence in a file the
reviewer could read), `ESCALATE` (evidence outside that, or a matter of
preference; the user decides) or `DECLINE` (a Nit, recorded). A
comprehension gap is never contested; severities are not changed. The user
then chooses: accept all fixes, item by item, or no changes. No edit happens
before that choice. Stages whose scope changed re-run once; their findings
go through the same resolution and gate; nothing re-runs after that, and
open items are listed in the design as accepted trade-offs.

#### `/coop-brainstorm` (Elephant, step 1)

It keeps its clarifying questions and its existing-repository verdict
(Conditions A–D). New: once the concept is clear, it writes the anchored
concept to `.swarm/blueprint/concept.md` (2–3 paragraphs), starts the six
BRAINSTORM lenses on it in parallel (reports to
`.swarm/design-reviews/concept/`), and merges their findings. Output:
`brainstorm_blueprint.md` as product notes with sections Overview;
Sufficiency Table and Verdict; Lens Analysis; Goals and Non-Goals;
Constraints and Invariants; Approved Innovation Hypotheses; Architecture
Options and Choice; Alternatives Weighed; Key Decisions for `/design-draft`.
It runs `--init-goal`, writes no `docs/ARCHITECTURE.md`, seeds no tasks, and
no longer runs `--verify-blueprint`.

#### `/design-draft` (Elephant, step 2)

Reads the product notes (or the user's notes) and writes
`docs/designs/<name>.md` from `skills/design-draft/template.md` in four
groups, asking for approval after each: (1) Overview, The Problem, Goals,
Non-Goals, Open Questions; (2) Critical User Journeys, Technical Plan;
(3) Alternatives Considered, Risks, Non-Functional Requirements, Additional
Resources, Future Improvements; (4) Detailed Implementation Plan. It then
lists contradictions with the product notes and waits for the user's
decision on each, runs `--import-design --dry-run`, fixes what it reports,
and offers `/goldfish-review`.

#### Plan format and importer (`goal_loop.py --import-design`)

The format departs from EGM's template, which lists files and then one
verification plan: here each task is one importable unit, which is what
`goal_loop.json` needs.

Contract:

1.  Headings inside fenced code blocks are ignored.
2.  The plan is the section under the first `## Detailed Implementation Plan`
    or `## Implementation Plan` heading, up to the next `## ` heading.
3.  Inside the plan only `### Goal` and `### Task <ID>: <title>` blocks are
    read; other text is ignored. A block ends at the next `###` or `##`
    heading. IDs match `[A-Za-z0-9][A-Za-z0-9._-]*`, are case-sensitive and
    unique per goal file; the template prefixes them (`<prefix>-1`).
4.  A field is a bullet at column 0, `*   **Label:** value` or
    `*   **Label**: value`. Its value runs to the next column-0 field bullet;
    indented bullets belong to the value. Labels are case-insensitive;
    unknown labels are an error. `Goal` and `Outcome` in the `### Goal` block
    set the root goal and outcome command.
5.  Field mapping (lists are comma-separated):

| Markdown field | Task field | Required |
| :--- | :--- | :--- |
| heading title | `title` | yes |
| `Files` — backticked paths tagged `(Create)`, `(Modify)` or `(Delete)` | `target_files` (Create, Modify); Delete paths appended to `objective` as "Delete: `<path>`" | yes, with at least one Create or Modify |
| `Depends on` — `none` or task IDs | `depends_on` | yes |
| `Changes` | `objective` (text as written) | yes |
| `Verification` — first backticked command | `verification_cmd` | yes |
| `Outcome` — first backticked command | `outcome_cmd` | no |
| `Review focus` — numbered sub-list | `review_focus` | no |
| `Called by` — backticked paths | `wiring_files` | no |
| `Symbols` — backticked names | `required_symbols` | no |

6.  Errors, all reported together (exit 1; JSON with `--json`): missing
    required field, untagged file, unknown dependency, dependency cycle,
    duplicate ID, overlapping target files between tasks with no
    `depends_on` path (preflight's rule), missing `### Goal` block, no plan,
    no tasks, and orphans (rule 8). With any error nothing is written.
7.  Writing: the goal file is read with strict JSON parsing (refuse if it
    exists and does not parse); records are built with
    `_normalize_task_record` on one loaded state; the file is saved once
    through a temporary file and `os.replace`.
8.  Re-import: a task whose stored `spec_ref` names another document, or is
    empty, is an error. A task whose title, files, dependencies, objective,
    commands, review focus, wiring fields or `spec_ref` changed is reset to
    `PENDING`, its gate fields (`gate_verdict`, `spec_verdict`,
    `critical_count`, `important_count`, `minor_count`, `iterations`,
    `last_errors`, `ruling`) are cleared, and `base_sha` becomes `HEAD`.
    Unchanged tasks keep everything. Tasks pointing to this document but
    missing from the plan ("orphans") are an error unless `--drop-missing`
    is given, which deletes them and logs it in `.swarm/ledger.md`.
9.  `spec_ref = "<doc path relative to --cwd> § Task <ID>"`. The brief and
    the review package print it with: "Read this section of the design;
    where this brief and the design differ, the design decides."
10. Output lists every task and every new or changed command, so the user
    can confirm commands before a real import.

`--verify-blueprint` keeps every check it has today (research report with
the legacy fallback, the 250-character minimum, placeholders, optional
reports, `--require-ui`). New: when some task has a `spec_ref`, each design
it names must exist, contain no placeholder and pass the dry run. Without
such tasks (Full Mode epochs, hand-seeded goal files, the "already optimal"
exit) nothing new is required.

## Alternatives Considered

### Alternative A: Install the upstream EGM plugin

*   **Pros**: No porting; upstream fixes; native installs for both harnesses.
*   **Cons**: Its brainstorm step duplicates `/coop-brainstorm`; its personas
    cannot be edited in place; it ends at a design document.
*   **Reason for Rejection**: Rejected by author: duplicated brainstorming and
    no way to tailor the personas to this pack.

### Alternative B: Copy EGM's files into the pack

*   **Pros**: Fast and faithful.
*   **Cons**: About 2,400 lines that drift from upstream; a license notice per
    copied file; EGM's interaction rules clash with the pack's conventions.
*   **Reason for Rejection**: Rejected by author: drift and convention clashes.

### Alternative C: Fold design review into `/discriminator-gate`

*   **Pros**: One reviewer skill.
*   **Cons**: That skill reviews a diff and drives a worker fix loop; a design
    review has neither.
*   **Reason for Rejection**: Rejected by author: different inputs and loops.

### Alternative D: Read-only enforced only by instruction

*   **Pros**: No agent definition to install.
*   **Cons**: Reviewers keep write and shell tools; a status check misses
    edits to already-modified and ignored files.
*   **Reason for Rejection**: Rejected by author after round 2: both harnesses
    can restrict tools (Claude Code agent tools list; Antigravity
    `enable_write_tools=False`).

### Alternative E: Keep Full Mode as the default

*   **Pros**: No behaviour change.
*   **Cons**: The default stays the mode with the most stages and no data.
*   **Reason for Rejection**: Rejected by author: measured modes first.

### Alternative F: The orchestrator calls `--add-task` per plan task

*   **Pros**: No parser.
*   **Cons**: Requirements are copied by hand from the design into the task
    list, a second place where wording can drift; no format check for stage 4.
*   **Reason for Rejection**: Rejected by author: a script copies without
    rewording. (It does not prevent narrowing written into the design itself;
    the reviewers do.)

### Alternative G: Keep the blueprint as the task source

*   **Pros**: No change to `/product-discovery` or `--verify-blueprint`.
*   **Cons**: Tasks in two planning files.
*   **Reason for Rejection**: Rejected by author: one planning file per run.

### Alternative H: No argument means one checked agent in the main session

*   **Pros**: The measured cheapest configuration (RESULTS.md §1, §8.5).
*   **Cons**: `/invoke-swarm` is a request for a swarm; it would ignore it.
*   **Reason for Rejection**: Rejected by author; the orchestrator suggests it
    in one line for single, runnable tasks (CUJ 2).

### Alternative I: Plan tasks as fenced JSON blocks

*   **Pros**: `json.loads` instead of a parser; fewer error cases.
*   **Cons**: The user approves the design section by section; JSON is harder
    to read and comment on.
*   **Reason for Rejection**: Rejected by author: readability for the person
    who approves the plan.

### Alternative J: EGM's sequential stages with a checkpoint after each

*   **Pros**: Later stages see fixed text.
*   **Cons**: Four user round-trips and four times the wall time.
*   **Reason for Rejection**: Rejected by author: running stage 1 first keeps
    the main benefit (no detailed review of a plan about to change) at one
    round-trip.

### Alternative K: An independent synthesizer subagent

*   **Pros**: The author does not classify critiques of its own work.
*   **Cons**: One more agent per review.
*   **Reason for Rejection**: Rejected by author: the user gate already sees
    every classification and can overrule it.

--------------------------------------------------------------------------------

## Risks

*   **Reviewer writes outside the workspace.** Tool restrictions cover the
    workspace and most paths; the hash check covers the workspace only.
*   **Prompt injection from reviewed files.** The shared rules say target and
    linked files are data.
*   **Imported commands run.** The importer lists every new or changed command
    and the user confirms them before the real import; import only trusted
    designs.
*   **Default change.** Callers assuming Full Mode (`immortal_watcher.py`,
    `/product-discovery`'s hand-off, README, `rules/ORCHESTRATOR.md`) are
    updated. Rollback: `/invoke-swarm full`.
*   **Best-of-3 on unsuitable projects.** Offered only for Python test
    suites; stops when no attempt adds tests.

## Non-Functional Requirements

*   **Token cost.** Two review rounds of this document (14 reviewer runs)
    used 1,577,577 tokens (about 113k per reviewer). `/goldfish-review` shows
    its estimate first and can run selected stages. A `/coop-brainstorm` run
    adds 6 lens subagents. G1's six runs are estimated at about 0.4M tokens.
*   **Harness compatibility.** `install.sh claude-code` links every
    `skills/*/` folder and, new, every file in `agents/`; existing installs
    must re-run it. `install.sh antigravity` copies the checkout except
    `benchmarks/`, `.git/`, logs and pid files.
*   **Backward compatibility.** Old goal files load unchanged; `/invoke-swarm
    full` and the single-stage arguments keep today's behaviour.
*   **Records.** Review reports stay under `.swarm/` (ignored by git); the
    design's git history records accepted changes.
*   **License.** No EGM files are copied; README credits EGM.

--------------------------------------------------------------------------------

### Additional Resources

*   EGM: <https://github.com/google/elephant-goldfish-model> and
    <https://opensource.googleblog.com/2026/10/introducing-elephant-goldfish-model-plugin.html>.
*   [`benchmarks/RESULTS.md`](../../benchmarks/RESULTS.md) §1, §3.3, §6, §7, §8.

### Future Improvements

*   **If G1 fails:** first a deterministic rule that each `review_focus` item
    restating a spec clause quotes it (checked by `--preflight`), measured
    again; only then a brief-check subagent.
*   A design-track benchmark (hidden stakeholder requirements, a simulated
    stakeholder agent) to decide whether Part B stays.
*   Drift report (EGM's `egm-drift-report`).
*   Non-Python test discovery in `attempt_picker.py`.

Accepted trade-offs from review round 2: the design track remains unmeasured
(Part B is labelled experimental); the dry run runs in several places
(deterministic, seconds); the restatement step is unmeasured.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

Part A is P1–P5, Part B is P6–P11, in that order. P1 has no dependencies;
the rest form one chain. Between P7 and P8 the `skills/goldfish-review/`
folder exists without a `SKILL.md`; installers link it harmlessly.

### Goal

*   **Goal:** Skill pack v3: Lite by default, best-of-3 opt-in, reviewer fixes, measured narrowing guards, and an experimental EGM-style design track whose reviewed plan is imported into goal_loop.json.
*   **Outcome:** `python3 -m unittest discover -s tests`

### Task P1: T1 reuse probe and spec-only provisioning

*   **Files:** `benchmarks/t1_reuse_probe.py` (Create), `tests/test_t1_reuse_probe.py` (Create), `benchmarks/evaluate_benchmarks.py` (Modify)
*   **Depends on:** none
*   **Changes:** The probe as specified under "Measurement of the existing
    guards", with `--json` printing `{"<workspace>": {"result": ..., "detail": ...}}`.
    `--setup --spec-only` as specified there; `_provision_workspace` skips
    `acceptance_section` when `spec_only` is set, and `setup_workspaces`
    limits arms to `swarm_lite`. Tests build temporary workspaces with a
    minimal `src/models.py` and `src/ledger.py` (full rule, narrow rule,
    broken import) and check results and exit codes; when
    `benchmarks/runs/` exists they also check the archived `T1` runs
    (`single_agent` → `FULL_RULE`, `single_agent_checked` and `swarm_lite` →
    `NARROW_RULE`) and skip otherwise; and they provision one spec-only
    workspace into a temporary runs folder.
*   **Verification:** `python3 -m unittest discover -s tests -p "test_t1_reuse_probe.py"`
*   **Review focus:**
    1.  `--spec-only` creates only `swarm_lite` workspaces; their `TASK_SPEC.md` has no acceptance section and `goal_loop.json` keeps four `review_focus` items.
    2.  An import failure gives `ERROR` and exit 2, never `NARROW_RULE`.

### Task P2: Measure the guards (operator runbook)

*   **Files:** `benchmarks/RESULTS.md` (Modify)
*   **Depends on:** P1
*   **Changes:** Run by the main session as operator, following "Measurement
    of the existing guards": provision both arms, prepare `pack-v27`, check
    whether a general-purpose subagent can start subagents, start one fresh
    orchestrator per run with the stated prompt, record tokens to the
    separate telemetry file, run the probe on all six workspaces, and read
    each run's goal file, worker report and reviewer verdict to note which
    guard fired. Add RESULTS.md section "## 9. Existing narrowing guards
    (benchmark `T1`)", renumbering "Reproducing" to §10. It has one table row
    per run, starting `| t1g-<arm>-r<n> |`, with probe result, tokens and the
    guard that fired, followed by the G1 verdict. Add one line to the
    Executive Summary.
*   **Verification:** `test "$(grep -c '^| t1g-' benchmarks/RESULTS.md)" -eq 6 && grep -q '^## 9. Existing narrowing guards' benchmarks/RESULTS.md`
*   **Review focus:**
    1.  The main session never acts as orchestrator for a measured run.
    2.  `benchmarks/results.json` and `benchmarks/telemetry_claude_code.json` are unchanged.

### Task P3: Lite by default, waves, release-level audit, opt-in Full

*   **Files:** `skills/invoke-swarm/SKILL.md` (Modify), `rules/ORCHESTRATOR.md` (Modify), `skills/epoch-planner/SKILL.md` (Modify), `skills/triad-audit/SKILL.md` (Modify), `skills/sota-web-scout/SKILL.md` (Modify), `scripts/immortal_watcher.py` (Modify), `tests/test_immortal_watcher_review.py` (Modify), `tests/test_skill_contracts.py` (Create)
*   **Depends on:** P2
*   **Changes:**
    *   `invoke-swarm/SKILL.md`: intro bullets (lines 12–13) become: Lite
        (`/invoke-swarm` or `/invoke-swarm lite`, the default) and Full
        (`/invoke-swarm full`, opt-in). Replace "Choosing Lite Mode vs. Full
        Mode" with the mode table and the rules "no argument means Lite;
        suggest another mode in one line; switch only on the user's word".
        Step 1 dispatches waves of up to 5 ready tasks in `depends_on` order.
        Step 0 shows `--init-swarm` (Lite) and `--init-swarm --full`. In
        Step 2.5, replace "skip Steps 3–7 (no Intermittent Report, no Triad
        Audit, and no SOTA Scout)" with "skip Steps 3–7" plus the
        release-level audit paragraph. Step 0.1 is unchanged.
    *   `ORCHESTRATOR.md`: §1 items 4 and 5 say "Full Mode, or after Lite when
        a release-level audit is requested"; §2's Lite bullet says it is the
        default, and the Full bullet is renamed `/invoke-swarm full`.
    *   `epoch-planner/SKILL.md`: one sentence that it runs in Full Mode or
        standalone.
    *   Triad and scout notes: "after a Lite build it runs only when the
        release-level audit is requested".
    *   `immortal_watcher.py`: `init_swarm` and `--init-swarm` default to
        Lite; new `--full`; `--lite` accepted; docstring updated. Its tests
        updated.
    *   `tests/test_skill_contracts.py` (prose checks, one module for the
        whole plan): `invoke-swarm/SKILL.md` contains no
        "`/invoke-swarm` or `/invoke-swarm full`" mapping and its mode table
        has a `lite` row marked default; the audit paragraph names
        `CRITICAL_GAP` and `AUDIT-`.
*   **Verification:** `python3 -m unittest discover -s tests -p "test_skill_contracts.py" && python3 -m unittest discover -s tests -p "test_immortal_watcher_review.py"`
*   **Review focus:**
    1.  `/invoke-swarm` with no argument cannot reach Full Mode.
    2.  `--init-swarm` without flags creates a Lite ledger (`max_epochs` 1); `--full` creates a Full one.

### Task P4: Best-of-3 mode

*   **Files:** `skills/invoke-swarm/SKILL.md` (Modify), `scripts/worktree_manager.py` (Modify), `tests/test_worktree_manager.py` (Create), `tests/test_skill_contracts.py` (Modify)
*   **Depends on:** P3
*   **Changes:** Add "Best-of-3 Mode" to `invoke-swarm/SKILL.md` with the
    preconditions, attempts, pick, finish and known costs from the Technical
    Plan, including the commands
    `python3 "$AGENT_SWARM_HOME/scripts/worktree_manager.py" create <task>-bo3-<timestamp>-<n> --base <branch>`
    and the picker call (literal braces in `--test-cmd` doubled), and the
    `attempt_picker.py` limits. `worktree_manager.py cleanup` gains
    `--delete-branch` (`git branch -D` after removing the worktree); `create`
    is unchanged. Tests run `worktree_manager.py` as a subprocess with `cwd`
    in a temporary repository inside its own temporary folder (pattern of
    `tests/test_attempt_picker.py`). The contract test checks that the
    section says "never chosen automatically" and "Python".
*   **Verification:** `python3 -m unittest discover -s tests -p "test_worktree_manager.py" && python3 -m unittest discover -s tests -p "test_skill_contracts.py"`
*   **Review focus:**
    1.  `cleanup --delete-branch` removes the worktree and the branch; without the flag the branch stays.

### Task P5: Reviewer restates the spec and writes nothing

*   **Files:** `skills/discriminator-gate/SKILL.md` (Modify), `benchmarks/RESULTS.md` (Modify), `tests/test_skill_contracts.py` (Modify)
*   **Depends on:** P4
*   **Changes:** In `discriminator-gate/SKILL.md`, Step 1 says the
    orchestrator passes the spec path(s) with the package and no longer
    claims the package holds "the exact task specification". Insert "Step
    1.5: Restate the requirement" before Step 2 with the text from "Reviewer
    changes", and add the no-write rule to the Iron Laws. Add to RESULTS.md
    §8.4: "In django-10554 the `swarm_lite` reviewer made a throwaway copy of
    the repository inside the test container while checking a finding; no
    files were left behind. From django-13128 on, the reviewer prompt forbade
    creating or copying files in the workspace." The contract test checks
    that "Step 1.5: Restate" appears before "Verdict Part 1" and that the
    no-write law exists.
*   **Verification:** `python3 -m unittest discover -s tests -p "test_skill_contracts.py"`
*   **Review focus:**
    1.  The restatement is part of the reviewer's report.

### Task P6: Plan importer, `spec_ref`, and blueprint verification

*   **Files:** `scripts/goal_loop.py` (Modify), `tests/test_goal_loop.py` (Modify), `skills/goal-loop/SKILL.md` (Modify)
*   **Depends on:** P5
*   **Changes:** `import_design(doc_path, cwd=None, dry_run=False, drop_missing=False) -> dict`
    per contract rules 1–10, returning `status`, `tasks` (id, title, action:
    `add`/`update`/`unchanged`/`reset`), `commands` (new or changed), `orphans`
    and `errors`. `add_task` gains `spec_ref` and `depends_on` keyword
    arguments and keeps the existing `objective` when none is given (the CLI
    stops passing the title as objective for existing tasks).
    `save_goal_state` writes through a temporary file and `os.replace`.
    `generate_task_brief` and `generate_review_package` print `spec_ref` with
    the sentence from rule 9; the review package also prints the objective.
    `verify_blueprint_artifacts` gains the design check described above. CLI:
    `--import-design PATH`, `--dry-run`, `--drop-missing` (both error without
    `--import-design`), `--depends-on`, `--spec-ref`. Plain output lists one
    line per task and per command. `skills/goal-loop/SKILL.md` documents the
    flags and adds `spec_ref`/`depends_on` to its manifest schema. Tests use
    the `GoalLoopProject` fixture.
*   **Verification:** `python3 -m unittest discover -s tests -p "test_goal_loop.py"`
*   **Review focus:**
    1.  A fenced example containing `## Detailed Implementation Plan` and `### Task X` is ignored.
    2.  Missing `Verification`, an unknown dependency and a cycle are reported together, and the goal file stays byte-identical (or absent).
    3.  A changed `VERIFIED_COMPLETE` task is reset with cleared gate fields; an unchanged one keeps its status; a foreign `spec_ref` is an error.
    4.  An orphan is an error; `--drop-missing` removes it and logs it.
    5.  A Delete-only task and overlapping files without a dependency are errors.
    6.  A goal file that does not parse is refused and left untouched.
    7.  `--verify-blueprint` passes as before for goal files without `spec_ref`.
    8.  `python3 scripts/goal_loop.py --import-design docs/designs/skill-pack-v3.md --dry-run` reports P1–P11 with no errors.

### Task P7: Goldfish personas, standards and read-only agent

*   **Files:** `skills/goldfish-review/personas/_rules.md` (Create), `skills/goldfish-review/personas/zoom-out.md` (Create), `skills/goldfish-review/personas/comprehension.md` (Create), `skills/goldfish-review/personas/design-critic.md` (Create), `skills/goldfish-review/personas/style.md` (Create), `skills/goldfish-review/personas/implementation-readiness.md` (Create), `skills/goldfish-review/personas/codebase-details.md` (Create), `skills/goldfish-review/personas/maintainability.md` (Create), `skills/goldfish-review/standards/zoom-out.md` (Create), `skills/goldfish-review/standards/feature-spec.md` (Create), `skills/goldfish-review/standards/implementation-readiness.md` (Create), `agents/goldfish.md` (Create), `install.sh` (Modify), `tests/test_skill_contracts.py` (Modify)
*   **Depends on:** P6
*   **Changes:** Persona, standard and rule content as listed under
    "Goldfish reviewers". Each persona starts "Read `_rules.md` in this folder
    first" and has `## REVIEW` and/or `## BRAINSTORM` per the table; no YAML
    frontmatter. `agents/goldfish.md`: Claude Code agent definition, `name:
    goldfish`, `tools: Read, Grep, Glob`, body "Follow the persona file named
    in your prompt; you cannot write files." `install.sh claude-code` also
    links each `agents/*.md` into `~/.claude/agents/`; `dir` mode links
    them into `<dir>/../agents/`. Contract test: headings per persona; no
    line in a persona starts with an imperative edit verb (`Edit`, `Write`,
    `Modify`, `Fix`, `Create`, `Delete`); `agents/goldfish.md` lists no write
    tool.
*   **Verification:** `python3 -m unittest discover -s tests -p "test_skill_contracts.py"`
*   **Review focus:**
    1.  `comprehension` REVIEW output starts with the two named headings.
    2.  `install.sh claude-code` run twice is idempotent for the agent link.

### Task P8: `/goldfish-review` skill

*   **Files:** `skills/goldfish-review/SKILL.md` (Create), `tests/test_skill_contracts.py` (Modify)
*   **Depends on:** P7
*   **Changes:** The skill per "`/goldfish-review`" and "Goldfish reviewers":
    inputs (path, optional reading list, `--stages`), stage table with
    persona and standard per reviewer, the read-only start in each harness
    and the fallback hash check, the estimate prompt, stage order, report
    paths, the retry rule, the resolution categories and rules, the user
    gate, and the re-run rule. It includes the prompt template sent to each
    Goldfish. Description starts "Use when", at most 300 characters.
    Contract test: every persona and standard file the skill names exists.
*   **Verification:** `python3 -m unittest discover -s tests -p "test_skill_contracts.py" && python3 -m unittest discover -s tests -p "test_skill_frontmatter.py"`
*   **Review focus:**
    1.  Stage 2 gets no reading list; stage 4 is skipped for a document without a plan.
    2.  No edit to the reviewed document happens before the user's choice.

### Task P9: `/design-draft` skill and template

*   **Files:** `skills/design-draft/SKILL.md` (Create), `skills/design-draft/template.md` (Create), `tests/test_skill_contracts.py` (Modify)
*   **Depends on:** P8
*   **Changes:** The skill per "`/design-draft`". The template's headings: the
    document header; Overview; The Problem; Goals; Non-Goals; Open Questions;
    Critical User Journeys (CUJs); Technical Plan (Architecture);
    Alternatives Considered; Risks; Non-Functional Requirements; Additional
    Resources; Future Improvements; Detailed Implementation Plan with a
    `### Goal` block and one sample task `### Task DEMO-1: ...` with concrete
    values. Before a real import, the skill shows the importer's command list
    to the user. Contract test: the template passes
    `import_design(..., dry_run=True)`.
*   **Verification:** `python3 -m unittest discover -s tests -p "test_skill_contracts.py" && python3 -m unittest discover -s tests -p "test_skill_frontmatter.py"`
*   **Review focus:**
    1.  The contradiction check waits for the user and changes nothing on its own.

### Task P10: `/coop-brainstorm` lenses and `/product-discovery` flow

*   **Files:** `skills/coop-brainstorm/SKILL.md` (Modify), `skills/product-discovery/SKILL.md` (Modify), `tests/test_skill_contracts.py` (Modify)
*   **Depends on:** P9
*   **Changes:**
    *   `coop-brainstorm`: add the lens step (concept file, six BRAINSTORM
        lenses through the read-only start, reports, merge into Lens
        Analysis); replace §4's output contract with the nine product-note
        sections; remove `docs/ARCHITECTURE.md`, task seeding and the
        `--verify-blueprint` call from §5; drop the interface and
        review-focus self-checks (now `/goldfish-review` stage 4); update the
        §6 return contract (no "Blueprint Verification" line, no "Tasks
        Seeded" line).
    *   `product-discovery`: Core Mandates 1–3 name the design document, not
        `docs/ARCHITECTURE.md` or Checkpoint-1 seeding; the Calling Modes
        table and the flow diagram show `/design-draft` → `/goldfish-review`
        → `--import-design` after Wave 2 (also in `no-ui` mode; not in
        `market-only`); Checkpoint 1 step 3 writes product notes only; the
        review step shows its token estimate and lets the user skip it; the
        final gate stays `--verify-blueprint`; the hand-off becomes
        `/invoke-swarm Implement docs/designs/<product>.md (tasks in .swarm/goal_loop.json)`.
    *   Contract test: both skills name `--import-design`; `coop-brainstorm`
        names the six lenses and no longer names `docs/ARCHITECTURE.md`.
*   **Verification:** `python3 -m unittest discover -s tests -p "test_skill_contracts.py"`
*   **Review focus:**
    1.  No instruction in either skill still seeds tasks from the blueprint.

### Task P11: Documentation, version and credit

*   **Files:** `README.md` (Modify), `plugin.json` (Modify), `scripts/generate_cheatsheet_pdf.py` (Modify), `SWARM_CHEATSHEET.pdf` (Modify), `tests/test_skill_contracts.py` (Modify)
*   **Depends on:** P10
*   **Changes:** README: title `v3.0`; "Design track (experimental)" section
    walking through CUJ 1; the mode table in place of the Lite/Full
    comparison; `### 2.x \`/goldfish-review\`` and `### 1.x \`/design-draft\``
    entries; Full Mode and `/epoch-planner` labelled opt-in; §4 lists
    `--import-design`; layout line says 25 skills and the new `agents/`
    folder; an "Acknowledgements" line crediting EGM (link, Apache-2.0); an
    upgrade note to re-run `install.sh`. `plugin.json`: version `3.0.0`,
    description under 400 characters, keywords `goldfish-review` and
    `design-draft`. Cheat sheet source (2 A4 pages): the mode table, the
    design-track flow, the two new skills; the PDF is regenerated when the
    optional `weasyprint` is installed, otherwise left for the user. Contract
    test: every `skills/*/` folder appears in a README heading of the form
    `` ### n.n `/name` ``, and every such heading names a folder under
    `skills/` or `extras/`.
*   **Verification:** `python3 -m unittest discover -s tests -p "test_skill_contracts.py"`
*   **Review focus:**
    1.  README no longer describes Full Mode as the default.

### Verification Plan

*   **Unit tests:** `python3 -m unittest discover -s tests`.
*   **Format check:** after P6, `python3 scripts/goal_loop.py --import-design docs/designs/skill-pack-v3.md --dry-run` reports P1–P11 with no errors.
*   **Install check:** `./install.sh dir <empty temp dir>/skills` links `goldfish-review` and `design-draft`, and `agents/goldfish.md`.
*   **Outcome:** G1 decided by P2's six runs.
