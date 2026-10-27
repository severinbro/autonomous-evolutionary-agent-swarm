---
name: quality-validator
description: "Use before claiming that a game, app, UI, or other deliverable works, is complete, or is ready to merge, and whenever a build compiles but has not actually been run."
disable-model-invocation: false
triggers: [user, model]
---

# Product Quality Gate & Runtime Smoke Validator (`/quality-validator`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

## Overview

Compilers and static typecheckers only verify syntax; they never prove runtime stability, responsive input loops, intact shaders/DOM containers, or end-to-end outcome execution. The **Quality Validator** enforces fresh runtime verification before any task, epoch, or project can claim completion.

> [!IMPORTANT]
> ## The Iron Law (`verification-before-completion`)
> ```
> NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE IN THIS MESSAGE
> ```
> If you have not run the verification command (`quality_validator.py`, `web_ui_validator.py`, test suite, and `--outcome-cmd`) in **this turn** after the final code edit and inspected its complete exit code and log output, you cannot claim the build passes, works, or is complete. Any runtime crash, unhandled exception, or missing fresh verification imposes an immediate **`6.0 / 10.0` Hard Cap** (`REJECTED`).

---

## 1. The 5-Step Verification Gate Function

Before claiming any deliverable is complete or ready for merge:

1. **IDENTIFY:** List the exact commands that prove runtime health and outcome completion:
   - Binary / Game / GUI App: `python3 "$AGENT_SWARM_HOME/scripts/quality_validator.py" /path/to/binary --timeout 10`
   - Web UI / HTML Dashboard: `python3 "$AGENT_SWARM_HOME/scripts/web_ui_validator.py" /path/to/index.html`
   - Project End-to-End Outcome: `<--outcome-cmd from .swarm/goal_loop.json>`
2. **RUN:** Execute each command fresh in the current turn (never rely on a run from before your last file edit).
3. **READ:** Inspect the complete stdout/stderr, exit code (`0` vs non-zero), runtime log (`Player.log`, console errors), and assertion counts.
4. **VERIFY & APPLY HARD CAP:**
   - **IF exit code $\neq 0$, OR any crash (`SIGSEGV`, `SIGTRAP`, `SIGABRT`), OR any unhandled exception (`NullReferenceException`, uncaught JS pageerror), OR any rubric check fails:**
     Apply the **`6.0 / 10.0` Hard Cap** immediately (`Verdict: REJECTED — HARD CAPPED AT 6.0`).
   - **IF all commands exit `0` with `0` runtime exceptions and all 4 rubric checks pass:**
     Record `Verdict: VERIFIED PASS`.
5. **CLAIM:** Write the full evidence log to `.swarm/epoch_<N>/quality_validation_report.md` and cite the exact command, exit code, and log line counts in your response.

---

## 2. Automated Runtime Smoke Testing (`quality_validator.py` & `web_ui_validator.py`)

```bash
# Game / Native / Desktop Binary Smoke Test:
python3 "$AGENT_SWARM_HOME/scripts/quality_validator.py" /path/to/game.x86_64 --timeout 10

# Web / Interactive HTML UI Smoke Test:
python3 "$AGENT_SWARM_HOME/scripts/web_ui_validator.py" /path/to/ui.html
```

### What `quality_validator.py` Validates:
1. **Zero-Crash Execution:** Launches the target binary, attaches to the display/window server, initializes physics/subsystems, and runs for the full timeout window without throwing `SIGTRAP`, `SIGSEGV`, `SIGABRT`, or exiting early.
2. **Log & Exception Auditing:** Scans runtime logs (`Player.log` for Unity, stdout/stderr for Godot/Pygame/Rust/C++) for fatal `NullReferenceException`, missing asset references, shader compilation errors, or unhandled panics/exceptions.
3. **Deterministic Exit Code:** Exits `0` on clean execution; exits `1` if any crash or fatal exception was caught (automatically triggering the **`6.0` Hard Cap**).

---

## 3. Product Quality Rubric & Hard-Cap Matrix (The 4 Checks)

Evaluate the deliverable against all 4 checks before closing any task or epoch:

| Check | Observable Verification Criterion | Score Impact on Failure | Required Remediation Action |
| :--- | :--- | :--- | :--- |
| **1. Runtime Stability** | Smoke test runs full window (`10s`) with exit `0` and `0` crashes/exceptions | **Hard Cap `6.0/10` (`REJECTED`)** | Relaunch worker with exact stack trace (`path:line`). |
| **2. Core Loop / Input Playability** | Entrypoint initializes, primary controls/CLI/UI respond to input, state updates | **Hard Cap `6.0/10` (`REJECTED`)** | Fix input bindings, controller wiring, or event listeners. |
| **3. Domain Systems & Mechanics** | Core mechanics (physics/combat/data pipeline/`--outcome-cmd`) produce verified output | **Hard Cap `6.0/10` (`REJECTED`)** | Delegate failing subsystem with concrete reproduction command. |
| **4. Visual, Shader & Asset Health** | Scene/UI renders with zero pink/missing shaders, zero `0x0` containers, zero broken assets | **Cap at `7.0/10` (`NEEDS_FIX`)** | Fix material/asset paths or CSS/Canvas layout dimensions. |

---

## 4. Targeted Failure Feedback Brief

When any check fails, extract the exact crash trace or failed rubric item (`path:line`) and dispatch a targeted remediation brief:

```markdown
**Objective:** Fix runtime failure in <Component/Method>
**Observed Defect (Cited):** <Log file:line> reports <Exact Exception / Error> during `<command>`
**Hard Cap Status:** Score capped at 6.0/10 until resolved
**Validation Command:** python3 "$AGENT_SWARM_HOME/scripts/quality_validator.py" ./build/app --timeout 10
**Stop Condition:** Validation command exits 0 in a fresh run with 0 exceptions in log.
```

---

## 5. Red Flags — STOP and Follow Process

If you catch yourself thinking any of these, **STOP immediately** and run the verification command fresh:
- *"The build compiled with 0 warnings, so it's ready to mark complete."*
- *"I only made a tiny 2-line fix after the last smoke test; I don't need to re-run `quality_validator.py`."*
- *"The smoke test crashed at 8 seconds, which is probably just a display environment quirk."*
- *"The tests passed earlier in this conversation, so I can report `Status: DONE` now."*
- *"Words like 'should work now', 'seems fixed', or 'likely passes' are in my draft response."*

---

## 6. Common Rationalizations

| Excuse | Reality |
| :--- | :--- |
| `"The compiler / linter succeeded with 0 errors"` | Compilers check syntax, not runtime null pointers, broken scene bindings, or missing shaders. Run the binary/UI validator. |
| `"It passed before my last minor cleanup edit"` | "Minor cleanup" edits routinely break imports or initialization order. Only a run executed *after* the final edit counts. |
| `"The exception in Player.log is non-fatal"` | Unhandled runtime exceptions corrupt downstream state and freeze game/UI loops. Fix it to `0` exceptions or cap at `6.0`. |
| `"I'm confident the fix works from reading the diff"` | Confidence is not evidence. Execute the command and cite the fresh exit code and stdout line count. |

---

## 7. Zero-Context-Bloat Subagent Return Contract (`< 15 Lines`)

Write full smoke-test logs and rubric details to `.swarm/epoch_<N>/quality_validation_report.md`, and return ONLY this `< 15 lines` summary to the Orchestrator:

```markdown
Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
Artifact: .swarm/epoch_<N>/quality_validation_report.md
Fresh Verification Run (This Turn):
- Smoke Validator: `<cmd>` -> Exit `<0|1>` (Runtime: `<Ns>`, Crashes: `<0|N>`, Exceptions: `<0|M>`)
- Outcome Command: `<outcome_cmd>` -> Exit `<0|1>`
Rubric Checks: 1. Stability=<PASS/FAIL> | 2. Core Loop=<PASS/FAIL> | 3. Systems=<PASS/FAIL> | 4. Visual/Assets=<PASS/FAIL>
Hard Cap (6.0) Triggered: <NO | YES — Capped at 6.0 due to <defect at path:line>>
Quality Score: <X.X>/10.0 (<VERIFIED PASS | REJECTED>)
Remediation Brief (if failed): None (or 1-line target `<path:line>` + validation command)
```
