# SWE-bench Benchmark (T13) in Antigravity with Gemini 4 Argon

This run tests the skill pack on real bugs in real repositories, where a single agent is expected to fail sometimes, so multi-agent designs finally have something to fix. Tasks T1–T12 could not show a quality difference because a single checked agent solved all of them.

- **Tasks:** 20 SWE-bench Verified instances rated "1–4 hours" or harder (12 Django, 5 SymPy, 3 pytest), listed in [`instances.json`](instances.json). Each is a real GitHub issue; the fix is graded by the issue's own hidden tests using the official SWE-bench harness.
- **Arms:** `single_agent_checked`, `best_of_3`, `swarm_peers`, `swarm_lite`, one run per instance each. With 20 instances, each arm gets 20 graded attempts.
- **Model:** Gemini 4 Argon, in the Antigravity **desktop app or CLI**. Argon is not available in the Antigravity IDE.

---

## 1. Session budget and order (Argon has a weekly quota)

| Arm | Conversations per instance | For 20 instances |
| :--- | :---: | :---: |
| `single_agent_checked` | 1 | 20 |
| `best_of_3` | 3 (independent) | 60 |
| `swarm_peers` | 3 (started together) | 60 |
| `swarm_lite` | 1 orchestrator + its worker and reviewer subagents | 20 (+ subagents) |

Run in this order and stop early if a phase answers the question:

1. **`single_agent_checked` on all 20.** If it resolves 18 or more, there is too little headroom for the other arms to show anything; stop and report.
2. **`best_of_3` on all 20.** The arm most likely to raise the resolve rate.
3. **`swarm_lite`, then `swarm_peers`.** Peers are designed for large builds that split into parts; a bug fix rarely splits, so expect them mainly to cost more.

Within a phase, work through the instances in the order of `instances.json`, so a partial week still covers whole repositories.

## 2. One-time setup

```bash
cd /path/to/autonomous-evolutionary-agent-swarm
./install.sh antigravity                      # plugin must include /peer-swarm and the updated goal_loop.py
python3 -m venv benchmarks/swe/.venv && benchmarks/swe/.venv/bin/pip install swebench==5.0.2   # skip if it exists
benchmarks/swe/.venv/bin/python benchmarks/swe/swe_bench.py pull            # ~45 GB of images, shared layers
benchmarks/swe/.venv/bin/python benchmarks/swe/swe_bench.py setup --runs-dir ~/agent-swarm-bench/swe/antigravity_argon
```

`setup` creates one workspace per arm and instance under `~/agent-swarm-bench/swe/antigravity_argon/<arm>/<instance>/r1/` (for `best_of_3`, also `r1_attempt_1..3/`). Each workspace is a full checkout of the repository with:

- `TASK_SPEC.md`: the issue text, how to run tests, acceptance criteria and rules;
- `run_tests.sh`: runs any command inside the instance's Docker image with the checkout mounted (no network inside the container).

Antigravity needs Docker access (your user must be able to run `docker` without `sudo`).

## 3. Rules for every run

- **One new top-level conversation per agent,** opened on that workspace folder only. Never open the repository root or `~/agent-swarm-bench` itself.
- **Keep the hidden tests hidden.** Agents must not read `~/.cache/huggingface`, the `benchmarks/` folder, other workspaces, or the internet. The prompts say so; if an agent does it anyway, note the run as contaminated.
- **Don't intervene.** If an agent asks a question, answer only: `Decide using TASK_SPEC.md and continue.`
- **Time cap: 60 minutes per run.** Stop it there; whatever is on disk is graded.
- **Don't re-run failures.** A wrong fix is data. Redo a run only if it could not start (tool outage), and note why.
- **Model check:** confirm Gemini 4 Argon is selected before each conversation.

**Known environment issues** (seen in the Claude Code run; they affect every arm equally):

- **SymPy:** whole test files often error before any change, because `bin/test` turns SymPy's Python 3.9 `DeprecationWarning`s into errors (35 errors in `sympy/stats/tests/test_continuous_rv.py`, 16 across `sympy/printing`). Broad sweeps such as `bin/test sympy/core sympy/assumptions ...` can run past 30 minutes; sympy-16597 hit the 60-minute cap in every arm that tried such a sweep.
- **pytest:** `testing/test_junitxml.py` and `testing/python/metafunc.py` cannot be collected (no `xmlschema`/`hypothesis`), and a few tests in `testing/python/collect.py`, `fixtures.py`, `acceptance_test.py` and `test_terminal.py` fail at the base commit.
- **Peers share one working tree:** a peer running `git stash` removes the other peers' uncommitted edits until it pops. Nothing was lost in the Claude Code run, but treat it as a coordination hazard when reading peer transcripts.

## 4. Prompts

Replace `<WS>` with the workspace's absolute path.

### `single_agent_checked`, and each `best_of_3` attempt (`r1_attempt_1`, `_2`, `_3`)

```text
Your workspace is <WS>, a checkout of an open-source repository. Work only inside it: do not read or list files outside it, and do not use the network.

Resolve the issue described in TASK_SPEC.md by changing the repository's source code. Follow its "Acceptance Criteria & Self-Checks" section, and run tests only through ./run_tests.sh as the spec explains. Do not edit run_tests.sh or TASK_SPEC.md, and do not use subagents.

When you are done, reply with at most 5 lines: status, files changed, and the test commands you ran with their results.
```

For `best_of_3`, run the three attempts as three separate conversations (they may run at the same time), then pick the winner:

```bash
benchmarks/swe/.venv/bin/python benchmarks/swe/swe_bench.py pick \
  --runs-dir ~/agent-swarm-bench/swe/antigravity_argon --instance <instance_id> --run r1
```

`pick` runs each attempt's new tests against every attempt's code and copies the attempt that passes the most of them into `r1/` (no model involved). Wall time for the arm = from the first attempt's start to the end of `pick`.

### `swarm_peers` (start three conversations at the same time)

```text
You are peer-<N>, one of 3 peers (peer-1, peer-2, peer-3) working at the same time in the workspace <WS>, a checkout of an open-source repository. Work only inside it: do not read or list files outside it, and do not use the network.

All three of you share one goal: resolve the issue described in TASK_SPEC.md by changing the repository's source code, following its "Acceptance Criteria & Self-Checks" section. Run tests only through ./run_tests.sh as the spec explains. There is no leader and no reviewer; you organise yourselves.

Coordinate only through .swarm/board.md:
- Read it first. Claim an item before working on it by editing the Items section (for example: reproduce the bug, find the cause, write the regression test, implement the fix, run the related test modules).
- Record decisions other peers depend on (the root cause, which files change) under Decisions before relying on them.
- The others edit files concurrently: re-read the board and a file right before you change it, and do not overwrite another peer's claimed file.
- Mark items done; check others' work when yours is done.

Do not edit run_tests.sh or TASK_SPEC.md, and do not use subagents. When you believe the issue is resolved and the related tests pass, append "peer-<N>: FINISHED" under Finished and stop. Reply with at most 5 lines: what you did and the test commands you ran with their results.
```

### `swarm_lite` (one orchestrator conversation)

```text
Your workspace is <WS>, a checkout of an open-source repository. You and every subagent you start must work only inside it: do not read or list files outside it, and do not use the network.

Run /invoke-swarm lite on this workspace to resolve the issue in TASK_SPEC.md. The plan is already in .swarm/goal_loop.json (one task, FIX) with its brief in .swarm/briefs/FIX-brief.md. Follow the skill as written, with these settings:
- Before dispatching, record the start commit: `git rev-parse HEAD`.
- Dispatch one worker subagent with the brief and TASK_SPEC.md. Workers run tests only through ./run_tests.sh and must not edit run_tests.sh or TASK_SPEC.md.
- When the worker reports, record what it changed: `python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd <WS> --add-task --task-id FIX --title "Resolve <instance>" --target-files <changed source files, comma-separated> --validation-cmd "./run_tests.sh <the test command the worker ran>"`. Then run `--audit-task FIX`. If the validation command fails only because of failures that also occur at the start commit (the worker reports these), narrow it to the worker's new tests (for SymPy `bin/test -k <test name> <file>`); if it fails on the worker's own tests, send the failing output back to the worker as a fix round.
- Step 1.5b applies (the issue's own tests are hidden, so acceptance cannot be fully checked by a command): generate `--review-package FIX --base-sha <start commit>`, run a reviewer subagent on it, and record its verdict with `--review-source reviewer`. Follow the fix loop as written.

Reply with at most 10 lines: final task status, fix rounds used, reviewer findings, and the files changed.
```

## 5. Record telemetry after each run

Add an entry to `benchmarks/swe/telemetry_antigravity_argon.json` under `arm → instance_id → "r1"`:

```json
{
  "best_of_3": {
    "django__django-13344": {
      "r1": {"conversation_ids": ["<attempt 1>", "<attempt 2>", "<attempt 3>"], "wall_seconds": 1234.0}
    }
  }
}
```

- `conversation_ids`: every conversation that worked on the run (all three attempts or peers; the orchestrator plus its subagents for `swarm_lite`), as named under `~/.gemini/antigravity/brain/`.
- `wall_seconds`: from sending the first prompt to the last reply (plus `pick` for `best_of_3`).

## 6. Grade

```bash
benchmarks/swe/.venv/bin/python benchmarks/swe/swe_bench.py evaluate \
  --runs-dir ~/agent-swarm-bench/swe/antigravity_argon --harness antigravity_argon \
  --telemetry-file benchmarks/swe/telemetry_antigravity_argon.json \
  --results-file benchmarks/swe/results_antigravity_argon.json
```

Each workspace's change (source files only; test files and the benchmark helpers are left out because the grader applies the issue's own tests) is graded in the instance's Docker image by the official harness, about 1–2 minutes per instance, 4 at a time. A workspace is graded only once its telemetry entry exists, so record telemetry when a run ends; a workspace without one (not started, or still running) is skipped as pending, not counted as a failure.

## 7. How to read the results

With 20 instances per arm, a difference of 1–2 resolved instances is noise; look for differences of about 4 or more, and at which instances flip.

| If you see | It means |
| :--- | :--- |
| `best_of_3` resolves clearly more than `single_agent_checked` | Independent attempts plus cross-testing raise quality on hard bugs; worth ~3× tokens when correctness matters. Check whether the picker chose the resolved attempt when one existed (`.swarm/pick.json`). |
| `swarm_lite`'s reviewer fails rounds and those instances end resolved | The reviewer finally catches something; keep Step 1.5b for hidden-test work. |
| `swarm_peers` resolves no more than the single agent at ~3× tokens | Consistent with T9/T11: peers pay off only on large builds that split. |
| Every arm resolves about the same | More agents do not help on these bugs with this model; prefer one checked agent. |

Compare with the Claude Code results (`results_claude_code.json`) arm by arm to see whether a finding holds across models.
