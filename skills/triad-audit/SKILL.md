---
name: triad-audit
description: "Use when a codebase needs an independent deep audit of correctness, security, and innovation, for example after an epoch of a swarm run or before a release."
disable-model-invocation: false
triggers: [user, model]
---

# Triad Audit Swarm: Rigor, Safety & Innovation (`/triad-audit`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

## Overview

Execute an adversarial 3-pillar audit of the codebase across **Rigor** (`rigor_auditor`), **Safety** (`safety_auditor`), and **Innovation** (`innovation_auditor`), writing evidence-cited reports to `.swarm/epoch_<N>/audit_<rigor|safety|innovation>.md` and recording scores in the swarm ledger.

> [!IMPORTANT]
> ## The Iron Law
> ```
> NO TRIAD AUDIT WITHOUT UNANCHORED PARALLEL ISOLATION, SEMANTIC-BEFORE-DETECTOR ORDERING, AND 6.0 HARD-CAP ENFORCEMENT
> ```
> Every auditor (`rigor_auditor`, `safety_auditor`, `innovation_auditor`) MUST run in its own isolated subagent context without reading peer audit reports, MUST complete its semantic code inspection and adversarial tests *before* running deterministic scanners, and MUST cap its score (and the Epoch convergence score) at **`6.0 / 10.0`** if any `CRITICAL` Safety or Rigor defect exists.

---

## 1. Unanchored Parallel Isolation & Hard-Cap Protocol (`impeccable` Pattern)

1. **Cross-Auditor Isolation:**
   - Spawn `rigor_auditor`, `safety_auditor`, and `innovation_auditor` concurrently via `invoke_subagent` (`Workspace: "share"`).
   - No auditor may read `.swarm/epoch_<N>/audit_*.md` written by another auditor during the same epoch.
2. **Semantic Assessment BEFORE Deterministic Detectors (Anti-Anchoring Rule):**
   - **Step A (Semantic & Adversarial First):** Each auditor inspects the source code (`path:line`), writes and executes its own adversarial edge-case/security/outcome tests, and drafts its semantic defect list and preliminary score.
   - **Step B (Deterministic Scanners Second):** Only *after* Step A is recorded does the auditor execute `goal_loop.py --scan-authenticity`, `perf_tracker.py`, or `agent_shield.py` to merge automated detector findings. A `0-finding` regex scan never overrides a semantic defect found in Step A.
3. **Mandatory Provenance Header in Every Report:**
   Every `.swarm/epoch_<N>/audit_<type>.md` report and unified summary MUST begin with:
   - `Method: triad-isolated (independent subagent contexts, semantic-before-detector)` when all 3 auditors ran in isolated subagent contexts; OR
   - `Method: ⚠️ DEGRADED: single-context` if single-aspect or single-agent fallback execution was used.
4. **The `6.0 / 10.0` Hard Cap Rule:**
   - If `rigor_auditor` or `safety_auditor` identifies **$\ge 1$ unresolved `CRITICAL` defect**—including any failing test, crash, `placeholder_findings > 0`, `synthetic_findings > 0`, `unwired_findings > 0` (`ORPHAN_UNWIRED_MODULE`), `pass_hat_k: false` flakiness, command/SQL/prompt injection, exposed credential, silent exception swallowing on a critical path, or AgentShield grade `D`/`F`—then:
     $$\text{Auditor Score} = \min(\text{Raw Score}, 6.0), \quad \text{Epoch Convergence Score} = \min(\text{Epoch Average}, 6.0)$$
   - Record `Hard Cap Triggered: YES (6.0 ceiling due to CRITICAL defect at <path:line>)` in the report header.

---

## 2. The Three Specialized Audit Sub-Agents

Register all three auditors via `define_subagent` and spawn them in parallel via `invoke_subagent` (`Workspace: "share"`), registering each with `immortal_watcher.py --register-subagent <conv_id> --agent-kind auditor`:

### 1. `rigor_auditor` (Mathematical, Algorithmic, Performance & `pass^k` Reliability Rigor)
- **Step A — Semantic & Adversarial Edge-Case Testing:**
  - Inspect algorithms, numerical stability, concurrency locks, and state transitions (`path:line`).
  - Write and execute **adversarial edge-case or property tests** (boundary inputs, empty/huge payloads, NaN/Inf, race conditions). Record any failing test command as a mandatory `Validation Command` for the next epoch.
  - Cross-verify non-trivial mathematical formulas symbolically (SymPy, or the optional `math-reasoning` extra if installed) when applicable.
- **Step B — Quantitative Benchmarking & Authenticity Scanners:**
  - Run `perf_tracker.py` with `--runs 3` (or `--runs 5`) to verify `pass_hat_k: true` ($K/K$ consecutive passes with zero flakiness) and check for latency/memory regressions (`> 15%`):
    ```bash
    python3 "$AGENT_SWARM_HOME/scripts/perf_tracker.py" \
      --name "core_workload" --command "<benchmark_cmd>" --epoch <N> --runs 3
    ```
  - Run the authenticity & wiring scanner and classify any `placeholder_findings`, `synthetic_findings`, or `unwired_findings` (`ORPHAN_UNWIRED_MODULE`) as **`CRITICAL`** (triggering the `6.0` Hard Cap):
    ```bash
    python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --scan-authenticity --path .
    ```

### 2. `safety_auditor` (Security, `/agent-shield`, Silent-Failure & Untrusted-Data Boundary Auditor)
- **Step A — Semantic Threat Modeling & Negative-Input Testing:**
  - Inspect all external input boundaries, file/path handlers, subprocess calls, auth/license guards, and exception blocks (`path:line`).
  - Execute malformed/negative-input tests to verify the system fails loudly with typed errors rather than crashing, leaking secrets, or silently swallowing exceptions (`except Exception: pass`).
  - Verify that any web/repo/LLM ingestion treats external text strictly as untrusted inert data.
- **Step B — Automated `/agent-shield` 5-Category Scan:**
  ```bash
  python3 "$AGENT_SWARM_HOME/scripts/agent_shield.py" \
    --path . --report ".swarm/epoch_<N>/security_shield_report.md"
  ```
  Merge the `0–100` AgentShield score (`A–F` grade) and findings into `.swarm/epoch_<N>/audit_safety.md`. Any `CRITICAL` security finding or grade `D`/`F` triggers the **`6.0` Hard Cap**.

### 3. `innovation_auditor` (Novelty, 100% Outcome Participation, Architecture & UX)
- **Step A — Semantic Outcome-Participation & UX Inspection:**
  - Trace every feature and UI control from entrypoint to output (`path:line`) to verify **100% outcome participation** (zero decorative/ornamental dead controls).
  - Compare architectural elegance, visualizations, and user ergonomics against the **Overall Project Goal** and `.swarm/sota/sota_knowledge_base.md`.
- **Step B — Headless UI & Blueprint Verification (when web UI exists):**
  - Run `web_ui_validator.py` on HTML/web entrypoints and incorporate any DOM/Canvas/console findings.

---

## 3. Report Schema & Swarm Ledger Recording

Each auditor writes `.swarm/epoch_<N>/audit_<rigor|safety|innovation>.md` using this header and severity table (`CRITICAL`, `HIGH`, `ENHANCEMENT`, `NITPICK`):

```markdown
# Triad Audit Report: <RIGOR | SAFETY | INNOVATION> (Epoch <N>)
- **Method:** `triad-isolated (independent subagent contexts, semantic-before-detector)` | `⚠️ DEGRADED: single-context`
- **Raw Semantic Score:** `<X.X>/10.0`
- **Hard Cap Triggered (`<= 6.0` on CRITICAL):** `NO` | `YES — Capped at 6.0 due to CRITICAL defect at <path:line>`
- **Final Recorded Score:** `<Y.Y>/10.0`
- **Finding Counts:** `CRITICAL: <c> | HIGH: <h> | ENHANCEMENT: <e> | NITPICK: <n>`
```

Each auditor records its final score in the swarm ledger before returning:

```bash
python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" \
  --record-audit <rigor|safety|innovation> \
  --audit-score <1.0-10.0> \
  --critical-count <int> \
  --high-count <int> \
  --enhancement-count <int> \
  --report-path ".swarm/epoch_<N>/audit_<type>.md" \
  --notes "<Top 3 actionable findings with path:line>"
```

---

## 4. Red Flags — STOP and Follow Process

If you catch yourself thinking any of these, **STOP immediately** and follow the Triad Audit protocol:
- *"I'll run `agent_shield.py` and `goal_loop.py --scan-authenticity` first, and since they passed, I'll give a `9.2/10` without writing adversarial tests."*
- *"To save time, I'll simulate all 3 auditors myself in one turn instead of spawning 3 isolated subagents."* (If single-context is forced by user instruction, you MUST mark `Method: ⚠️ DEGRADED: single-context`).
- *"There is 1 `CRITICAL` unwired module or security bug, but the rest of the code is great so I'll score it `8.1/10`."* (Violates the **`6.0` Hard Cap**).
- *"Reading the code is enough; I don't need to execute an adversarial edge-case test."*

---

## 5. Common Rationalizations

| Excuse | Reality |
| :--- | :--- |
| `"Automated scanner returned 0 findings, so Rigor/Safety is 9.5/10"` | Regex scanners only catch surface syntax. Running scanners first anchors you into skipping semantic and adversarial testing. |
| `"Running all 3 audits in one context is just as good"` | Single-context auditing suffers from self-confirmation bias. True Triad Audit requires 3 isolated subagent contexts (`Method: triad-isolated`). |
| `"A 7.8 or 8.2 is fair despite one CRITICAL bug"` | A critical correctness or security failure means the software is broken. The `6.0` Hard Cap is non-negotiable. |
| `"Writing a new adversarial test takes too long"` | Passive code reading misses boundary crashes, race conditions, and NaN propagation. Execute at least one adversarial test per audit. |

---

## 6. Zero-Context-Bloat Subagent Return Contract (`< 15 Lines`)

Each auditor writes its full report to `.swarm/epoch_<N>/audit_<type>.md`, runs `immortal_watcher.py --record-audit`, and returns ONLY this `< 15 lines` summary to the Orchestrator (`AUDIT FINISHED`):

```markdown
Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
Marker: AUDIT FINISHED (<rigor | safety | innovation>)
Method: triad-isolated | ⚠️ DEGRADED: single-context
Artifact: .swarm/epoch_<N>/audit_<type>.md
Final Score: <Y.Y>/10.0 (Raw Semantic: <X.X>/10.0 | Hard Cap 6.0 Triggered: <YES/NO>)
Findings: CRITICAL=<c>, HIGH=<h>, ENHANCEMENT=<e>, NITPICK=<n>
Adversarial & Detector Evidence: `<test_cmd>` -> <PASS/FAIL> | Scanner -> <summary>
Top 3 Cited Findings:
1. [<SEVERITY>] <path:line> — <1-line defect & validation command>
2. [<SEVERITY>] <path:line> — <1-line defect & validation command>
3. [<SEVERITY>] <path:line> — <1-line defect & validation command>
```
