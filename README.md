# Autonomous Evolutionary Agent Swarm & Product Discovery Suite (`agent-swarm` v2.7)

A complete multi-agent orchestration plugin, initial web/literature/market opportunity scouting & product planning suite (`/product-discovery`), hierarchical Goal-Loop & AST Outcome-Authenticity engine (`/goal-loop` / `scripts/goal_loop.py`), Two-Verdict Categorical Discriminator Gate with Hard Caps & 5-Round Escalating Fix Loop (`/discriminator-gate`), empirical UI/UX Art Direction Dealer & 3-Viewport Real-Browser Inspector (`/ui-ux-design`, `scripts/ui_direction_dealer.py`, `scripts/web_ui_validator.py`), security & prompt-injection scanner (`/agent-shield`), evidence-cited session diagnostics (`/swarm-diagnostics`), and autonomous goal-driven evolutionary development loop (`/invoke-swarm`) that **runs UNTIL results ACTUALLY match the desired output with zero synthetic, half-baked, placeholder, or unwired code**.

> **Printable Desk Reference (2-Page A4 PDF):** A print-ready 2-page (front-and-back A4) PDF cheat sheet featuring a quick skill decision guide, vector SVG workflow graph, all skills, Two-Verdict + Hard-Cap evaluation rules, and `.swarm/` file mappings is included at [`SWARM_CHEATSHEET.pdf`](SWARM_CHEATSHEET.pdf) (regenerated via `scripts/generate_cheatsheet_pdf.py`).

---

## Installation

The skills work in any agent harness that loads `SKILL.md` folders. They were built for Google Antigravity, so they name Antigravity's tools (see [Harness compatibility](#harness-compatibility)).

```bash
git clone https://github.com/severinbro/autonomous-evolutionary-agent-swarm.git
cd autonomous-evolutionary-agent-swarm
./install.sh antigravity          # or: ./install.sh claude-code | ./install.sh dir <skills-dir>
agy plugin enable agent-swarm     # Antigravity only, once
export AGENT_SWARM_HOME="<path printed by install.sh>"   # add to your shell profile
pip install playwright && python3 -m playwright install chromium   # needed for UI validation
```

For Antigravity, `install.sh` copies the checkout into `~/.gemini/config/plugins/agent-swarm`; re-run it after every `git pull`. Runtime state in that folder (`.swarm_global/`, logs) is kept. For the other targets it creates symlinks to each skill folder. It never overwrites files or folders it did not create. On Windows, use WSL or copy the folders in `skills/` manually.

Check the Antigravity plugin with `agy plugin validate .` and the scripts with `python3 -m unittest discover -s tests`.

### Requirements

- Python 3 and `git`. The scripts use only the standard library (developed on Python 3.14).
- Playwright with Chromium for `web_ui_validator.py`. Without a browser, UI validation reports `FAIL (browser-unavailable)` instead of passing unverified; `--allow browser-unavailable` accepts static-only checks deliberately.
- Optional: Node.js (enables `node --check` on inline scripts) and `weasyprint` (regenerates the cheat sheet). See [`requirements.txt`](requirements.txt).

### Configuration

| Variable | Purpose |
| :--- | :--- |
| `AGENT_SWARM_HOME` | Root of the installed skill pack: the Antigravity plugin folder, or this checkout for symlink installs. Skills run `"$AGENT_SWARM_HOME/scripts/<tool>.py"`. If unset, agents resolve it from the skill file's real path. |
| `AGENT_SWARM_UI_PYTHON` | Optional Python interpreter that has Playwright. `web_ui_validator.py` re-execs into it when the current `python3` lacks Playwright. |
| `PLAYWRIGHT_BROWSERS_PATH` | Playwright's own setting for a custom browser cache. |
| `ZOTERO_API_KEY`, `ZOTERO_USER_ID` | Zotero Web API for `/deep-research` and `/paper-to-code`. Also read from `~/.env`, `./.env`, or the file named by `ZOTERO_ENV_FILE`. |
| `ZOTERO_SQLITE_PATH`, `ZOTERO_CACHE_DIR` | Offline Zotero database (default `~/Zotero/zotero.sqlite`) and cache (default `~/.cache/zotero`). |

All variables except `AGENT_SWARM_HOME` are optional; leave them unset if Playwright and Zotero are in their default locations. Agents only see variables from the environment the harness was started in, so set them where the harness inherits its environment (for example `~/.bashrc`) and restart the harness. If a setting is missing or wrong, the affected tool fails with a message saying what to set; it never silently passes.

### Harness compatibility

The skills refer to Antigravity's tool names. In other harnesses, use the equivalent tool:

| Antigravity tool | Purpose | Claude Code equivalent |
| :--- | :--- | :--- |
| `define_subagent`, `invoke_subagent` | Define and spawn a subagent | Agent tool |
| `send_message` | Message a running subagent | `SendMessage` |
| `manage_subagents` | List running subagents | Harness-specific |
| `ask_question` | Ask the user to choose between options | `AskUserQuestion` |
| `view_file` | Read a file | `Read` |
| `search_web`, `read_url_content` | Web search and page fetch | `WebSearch`, `WebFetch` |

- Without subagents, run the stages one after another. `/triad-audit` then records `Method: ⚠️ DEGRADED: single-context`, as it specifies.
- Antigravity only: `/swarm-diagnostics` and subagent revival (`immortal_watcher.py --check-subagents`) read Antigravity transcripts in `~/.gemini/antigravity/brain/`. All other scripts are harness-independent.
- `plugin.json` and `rules/ORCHESTRATOR.md` make up the Antigravity plugin. The rule uses `trigger: model_decision`, so Antigravity loads it only for swarm work. Other harnesses ignore `plugin.json`; reference `rules/ORCHESTRATOR.md` from your `AGENTS.md` or `CLAUDE.md` if you want its orchestrator rules loaded.

### Repository layout

```
skills/       22 skills, one folder each with a SKILL.md
scripts/      Python tools the skills call (goal_loop.py, web_ui_validator.py, ...)
rules/        ORCHESTRATOR.md orchestrator rules
tests/        python3 -m unittest discover -s tests
extras/       Skills tied to specific local infrastructure; not installed by default (see extras/README.md)
plugin.json   Antigravity plugin manifest
install.sh    Installer (copy for Antigravity, symlinks elsewhere)
LICENSE       MIT
```

---

## End-to-End Workflow Overview

The toolkit is divided into two cleanly separated phases — each with its own master shortcut (**`/product-discovery`** for Phase A, **`/invoke-swarm`** for Phase B), governed by the **Hierarchical Goal-Loop & Outcome Engine (`/goal-loop`)**, and **every individual skill can also be invoked standalone** on any repository at any time:

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│  PHASE A: INITIAL DISCOVERY, POTENTIAL SCOUTING & PRODUCT PLAN (/product-discovery)│
│                  (Invoked independently prior to running the swarm)                │
├────────────────────────────────────────────────────────────────────────────────────┤
│  [Wave 1: Parallel Web, Literature & Market Potential Scouting]                    │
│    ├── 1. /deep-research       ──► Web Crawl + High-Impact Papers + Zotero DB      │
│    ├── 2. /market-research     ──► 3-Agent Swarm: Competitors, VoC Pain & TAM/SAM  │
│    ├── 3. /commercial-strategy ──► 2-Agent Swarm: Open-Core/B2B Licensing, COGS &  │
│    │                               Kill-Risks + `.swarm/blueprint/market_dashboard.html`│
│    └── 4. /paper-to-code       ──► Extracts Zotero/arXiv equations into code+tests │
│                                          │                                         │
│                                          ▼                                         │
│  [Checkpoint 1: Interactive Product Planning, Review Focus & Goal-Loop Seeding]    │
│    └── 5. /coop-brainstorm     ──► High-ROI Potentials + Search-First Adopt/Build +│
│                                    Review Focus (Top 5 Implied Failure Modes) +    │
│                                    Seeds `.swarm/goal_loop.json` (Tasks/SubTasks)  │
│                                          │                                         │
│                                          ▼                                         │
│  [Wave 2 + Checkpoint 2: Dealt UI Directions, Craft Floor & 3-Viewport Gate]       │
│    └── 6. /ui-ux-design        ──► Surface Mode (Persuade/Operate/Read/Experience) │
│                                    + Design Dials (--variance/--motion/--density)  │
│                                    + `ui_direction_dealer.py` + Idea Sentence +    │
│                                    One Live Thing + 3 Single-File HTML Prototypes  │
│                                    (Verified at 1440/768/390 via /visual-ui-validator)│
└──────────────────────────────────────────┬─────────────────────────────────────────┘
                                           │ (Locked Product Plan, `DESIGN.md` & `.swarm/goal_loop.json`)
                                           ▼
╔════════════════════════════════════════════════════════════════════════════════════╗
║    PHASE B: GOAL-DRIVEN EVOLUTIONARY SWARM LOOP (/invoke-swarm — Until Goal Met)   ║
╠════════════════════════════════════════════════════════════════════════════════════╣
║  [Step 0 / 0.25 / 0.5] Load `.swarm/goal_loop.json`, run `goal_loop.py --preflight`║
║                 conflict scan, and `/contract-lock` freezes `src/contracts/`       ║
║                 │                                                                  ║
║                 ▼                                                                  ║
║  [Step 1]   Parallel Implementation Sub-Agents (Isolated Git Worktrees +           ║
║             Zero-Context-Bloat `.swarm/briefs/<ID>-brief.md` + `< 15 lines` return)║
║             + `immortal_watcher` (Auto-revives stalled or interrupted sub-agents)  ║
║             + Parallel `sota_web_scout` (Continuous SOTA web/literature crawling)  ║
║                 │                                                                  ║
║                 ▼                                                                  ║
║  [Step 1.5] `discriminator` Two-Verdict + Hard-Cap Gate (`/discriminator-gate`)    ║
║             Packages `BASE_SHA..HEAD` diff (`--review-package`), checks AST wiring ║
║             & `BLOCKING_FAIL` invariants, evaluates Spec Compliance (`PASS/FAIL`)  ║
║             + Severity Buckets (`Critical` [cap 6.0], `Important` [cap 7.0],       ║
║             `Minor` [deferred to `.swarm/deferred_minor_ledger.md`]).              ║
║             ├── Needs Fixes (Rounds 1-3) ──► Same Worker + Scoped `FIX_BASE..HEAD` ║
║             ├── Needs Fixes (Rounds 4-5) ──► Fresh Escalated Worker Sub-Agent      ║
║             ├── Round 5 Breaker          ──► Record `Ruling:` in `.swarm/ledger.md`║
║             └── Approved (0 Crit/Imp)    ──► Task Completed & Worker Approved      ║
║                 │                                                                  ║
║                 ▼                                                                  ║
║  [Step 2-3] Snapshot base (`--snapshot-create`), merge branches (`/merge-surgeon`),║
║             verify whole-repo authenticity (`--scan-authenticity`), write          ║
║             `intermittent_report.md` & render `.swarm/dashboard.html`              ║
║                 │                                                                  ║
║                 ├───────────────────────────────┬───────────────────────────────┐  ║
║                 ▼                               ▼                               ▼  ║
║  [Step 4-5] `rigor_auditor`           `safety_auditor`         `innovation_auditor`║
║             (Unanchored math/algo,    (`/agent-shield` scan,   (Novelty, 14-Pass   ║
║              AST wiring & `pass^k`)    resilience & threats)   UI & outcome craft) ║
║                 │                               │                               │  ║
║                 └───────────────┬───────────────┴───────────────┬───────────────┘  ║
║                                 ▼                               ▼                  ║
║  [Step 6]   `sota_web_scout` scores Innovation vs SOTA (1-10) & Implementation     ║
║             vs SOTA (1-10) against `.swarm/sota/sota_knowledge_base.md`            ║
║                                 │                                                  ║
║                                 ▼                                                  ║
║  [Step 7]   Orchestrator synchronizes all reports & checks Goal-Driven Convergence:║
║             ├── Converged & `goal_loop.py --verify-goal` PASS ──► FINAL REPORT     ║
║             └── Not Yet Met (`CONTINUE_NEXT_EPOCH` / `CONTINUE_UNTIL_GOAL_MET`)    ║
║                 ──► Writes `.swarm/epoch_<N+1>/adjusted_plan.md` & loops to Step 1!║
╚════════════════════════════════════════════════════════════════════════════════════╝
```

---

## 1. Phase A: Initial Discovery, Market Opportunity Scouting & Product Planning Skills

### 1.0 `/product-discovery` (Phase A Master Orchestrator) - [`skills/product-discovery/SKILL.md`](skills/product-discovery/SKILL.md)
* **What It Does:** Executes the entire **Phase A Web/Literature Scouting, Market Opportunity Analysis & Product Planning Pipeline** using **2 parallel autonomous waves**, **2 interactive human decision checkpoints**, and a built-in **Truth-in-Code Sufficiency & Anti-Bloat Gate** for existing repositories:
  * **Wave 1 (Parallel Intelligence Swarm):** Runs `/deep-research`, `/market-research`, and `/commercial-strategy` concurrently.
  * **Checkpoint 1 (`/coop-brainstorm` + Review Focus + Sufficiency Gate):** Synthesizes Wave 1 findings, locks high-ROI features (`Net-ROI >= 8.0`), defines the **`## Review Focus` (Top 5 Implied Failure Modes)** pinned to specific task tests, and seeds `.swarm/goal_loop.json`.
  * **Wave 2 & Checkpoint 2 (`/ui-ux-design`):** Classifies Surface Mode (`Persuade` / `Operate` / `Read` / `Experience`), sets Design Dials (`--variance`, `--motion`, `--density`), deals 3 empirical art directions via `scripts/ui_direction_dealer.py`, defines the Subject Inventory + **The Idea Sentence** + **One Live Thing**, builds 3 single-file HTML/CSS/JS prototypes, validates them across `1440`, `768`, and `390` viewports + `prefers-reduced-motion` via `scripts/web_ui_validator.py`, and persists `DESIGN.md` + `.swarm/surfaces/<slug>.md`.

### 1.1 `/deep-research` - [`skills/deep-research/SKILL.md`](skills/deep-research/SKILL.md)
* **What It Does:** Executes three parallel research streams (Zotero DB via `scripts/zotero_tool.py`, High-Impact Literature via OpenAlex/arXiv/PubMed, and Web/OSS SOTA crawl) under a strict positive structural output contract.

### 1.2 `/market-research` - [`skills/market-research/SKILL.md`](skills/market-research/SKILL.md)
* **What It Does:** Spawns 3 parallel market intelligence sub-agents (`competitor_teardown_scout`, `voice_of_customer_miner`, `tam_icp_gtm_analyst`).

### 1.3 `/commercial-strategy` - [`skills/commercial-strategy/SKILL.md`](skills/commercial-strategy/SKILL.md)
* **What It Does:** Spawns 2 parallel commercialization & adversarial sub-agents (`pricing_monetization_strategist`, `moat_and_risk_skeptic`) and generates `.swarm/blueprint/market_dashboard.html`.

### 1.4 `/coop-brainstorm` - [`skills/coop-brainstorm/SKILL.md`](skills/coop-brainstorm/SKILL.md)
* **What It Does:** Interactive ideation partner, Search-First Adopt/Build gate, **`## Review Focus` failure-mode generator**, and `.swarm/goal_loop.json` seeder.

### 1.5 `/ui-ux-design` - [`skills/ui-ux-design/SKILL.md`](skills/ui-ux-design/SKILL.md)
* **What It Does:** Combines the best of `leonxlnx/taste-skill`, `pbakaus/impeccable`, and `nextlevelbuilder/ui-ux-pro-max-skill`:
  1. **Surface Modes (`Persuade` | `Operate` | `Read` | `Experience`) & Parametric Design Dials (`--variance 1-10`, `--motion 1-10`, `--density 1-10`)**.
  2. **Dealt Empirical Art Directions (`scripts/ui_direction_dealer.py`)**: Deals 3 distinct, non-overlapping art directions with typography ratios, color tokens, and non-repeating section blueprints so the model never falls back to generic category averages.
  3. **Subject Inventory + "The Idea Sentence" (Competitor Swap Test) + "One Live Thing"**: Ensures every prototype is unmistakably tied to the product's domain and includes a working interactive micro-tool on the first viewport.
  4. **Craft Floor & Browser Surfaces**: Enforces custom `::selection`, focus rings, custom scrollbars, `tabular-nums`, and $\le 2$-line headlines, verified across 3 viewports (`1440/768/390`) + `prefers-reduced-motion` via `scripts/web_ui_validator.py`.

### 1.6 `/paper-to-code` - [`skills/paper-to-code/SKILL.md`](skills/paper-to-code/SKILL.md)
* **What It Does:** Extracts formal mathematical equations and algorithms from Zotero/arXiv papers into verified code and unit tests.

---

## 2. Evolutionary Swarm Loop & Standalone Stage Skills

### 2.1 `/invoke-swarm` - [`skills/invoke-swarm/SKILL.md`](skills/invoke-swarm/SKILL.md)
* **What It Does:** Master orchestrator for the autonomous **Steps 0.25 $\rightarrow$ 7 Goal-Driven Evolutionary Macro-Loop**. Runs `goal_loop.py --preflight`, locks contracts (`/contract-lock`), dispatches isolated worktree workers with `.swarm/briefs/<ID>-brief.md` file handoffs, gates each worker through `/discriminator-gate` (Two-Verdict + Hard Caps + 5-Round Escalating Loop), integrates via `/merge-surgeon`, audits via unanchored `/triad-audit` + `/agent-shield`, sweeps `.swarm/deferred_minor_ledger.md` in Epoch 3, and iterates until `goal_loop.py --verify-goal` passes.

### 2.2 `/contract-lock` (Step 0.5 + Pre-Flight + Brownfield `spec-miner`) - [`skills/contract-lock/SKILL.md`](skills/contract-lock/SKILL.md)
* **What It Does:** Runs `goal_loop.py --preflight` to detect shared-file/interface overlaps, freezes `src/contracts/`, and mines brownfield `WHEN -> THEN` & `ALWAYS TRUE` invariants into `docs/INVARIANTS.md`.

### 2.3 `/discriminator-gate` (Step 1.5 — Two-Verdict Gate + Hard Caps + 5-Round Escalating Loop) - [`skills/discriminator-gate/SKILL.md`](skills/discriminator-gate/SKILL.md)
* **What It Does:** Replaces brittle point-deduction arithmetic with **Deterministic Evidence Packaging + Structured Categorical Judgment + Hard Caps**:
  1. **Review Package (`goal_loop.py --review-package <ID>`):** Bundles `BASE_SHA..HEAD` commits, diff stats, `-U10` diffs, and deterministic `BLOCKING_FAIL` / `ADVISORY_WARN` checks into `.swarm/reviews/<ID>-review.diff.md`.
  2. **Part 1 — Spec & Outcome Compliance (`PASS` | `FAIL` | `UNVERIFIABLE`):** Audits `Missing`, `Extra (YAGNI)`, `Misunderstood`, and whether tests prove the plan's `## Review Focus` failure modes.
  3. **Part 2 — Code Quality Severity Buckets (`Approved` | `Needs Fixes`):**
     * **`Critical` (Must Fix):** Blocks immediately; **hard-caps telemetry score at `6.0/10`**.
     * **`Important` (Should Fix):** Blocks immediately; **hard-caps telemetry score at `7.0/10`**.
     * **`Minor` (Deferred to Ledger):** Logged to `.swarm/deferred_minor_ledger.md` for Epoch 3 Polish; **never blocks the task or triggers a fix loop**.
  4. **5-Round Escalating Fix Loop & Scoped Re-Review (`FIX_BASE..HEAD`):**
     * **Rounds 1–3:** Resume the *same* worker sub-agent with only the open `Critical`/`Important` items. Re-review is strictly scoped to `FIX_BASE..HEAD` (`ADDRESSED | NOT ADDRESSED` + `New Breakage in the Fix Diff`).
     * **Rounds 4–5 (Escalation):** Spawn a **fresh worker sub-agent** (`"A prior implementer attempted this task 3 times; you own it now"`).
     * **Round 5 Breaker (`Ruling:`):** Stops looping and records a typed ruling (`OVERRIDE`, `SPLIT_TASK`, `RE_ARCHITECT_CONTRACT`, or `ESCALATE_TO_USER`) with `Ruling: <decision> — <why> — <cost if wrong>` in `.swarm/ledger.md` to surface to the user. A ruling never overturns a deterministic `BLOCKING_FAIL`, and only `OVERRIDE` completes a task.

### 2.4 `/merge-surgeon` (Step 3 Integration + 4-Phase Conflict Root Cause) - [`skills/merge-surgeon/SKILL.md`](skills/merge-surgeon/SKILL.md)
* **What It Does:** Pre-merge Git snapshots (`--snapshot-create`), `git merge --no-ff`, systematic 4-phase conflict resolution (escalating architecture if 3 attempts fail), and post-merge verification.

### 2.5 `/triad-audit` (Steps 4-5 — Unanchored Parallel Isolation) - [`skills/triad-audit/SKILL.md`](skills/triad-audit/SKILL.md)
* **What It Does:** Spawns `rigor_auditor`, `safety_auditor` (`/agent-shield`), and `innovation_auditor` in **Unanchored Parallel Isolation** (each completes its semantic review before deterministic detector outputs are merged, declaring `Method: triad-isolated` in the header and applying `6.0` Hard Caps on critical rigor/safety failures).

### 2.6 `/agent-shield` - [`skills/agent-shield/SKILL.md`](skills/agent-shield/SKILL.md)
* **What It Does:** 5-category security, prompt-injection, Trojan-Source Unicode, hook pipe, MCP context-tax, and silent-failure scanner (`scripts/agent_shield.py`).

### 2.7 `/perf-benchmarker` - [`skills/perf-benchmarker/SKILL.md`](skills/perf-benchmarker/SKILL.md)
* **What It Does:** Quantitative latency, peak RSS memory, and `pass^k` non-flakiness tracker (`scripts/perf_tracker.py`).

### 2.8 `/visual-ui-validator` (3-Viewport Real-Browser Inspector + Unanchored Dual-Agent Critique) - [`skills/visual-ui-validator/SKILL.md`](skills/visual-ui-validator/SKILL.md)
* **What It Does:** Runs `scripts/web_ui_validator.py` across **`1440x900`, `768x1024`, and `390x844` + `prefers-reduced-motion`**, checking headline line counts ($\le 2$), `1.2s` `h1` visibility, outer margin symmetry, $<15\%$ empty screens, scroll text collisions, live motion counts, WCAG contrast, and anti-slop rules (eyebrow pills, `01/02/03` numbering, monospace prose, resting shadows, icon-card grids, AI purple / cream+terracotta), paired with **Unanchored Dual-Agent Critique (Assessment A: 14-Pass Visual Screenshot Rubric + Nielsen/Cognitive Load/Personas; Assessment B: Deterministic Inspector JSON + Hard Caps)**.

### 2.9 `/sota-web-scout` (Step 6) - [`skills/sota-web-scout/SKILL.md`](skills/sota-web-scout/SKILL.md)
* **What It Does:** Parallel web, GitHub, and literature SOTA benchmark researcher.

### 2.10 `/epoch-planner` (Steps 3 & 7) & `/immortal-agents`
* **What It Does:** Generates Step 3 Intermittent Reports and Step 7 Adjusted Plans (with mandatory `## Review Focus` failure modes), and supervises/revives active sub-agents.

### 2.11 `/swarm-diagnostics` (Evidence-Cited Session Diagnostics) - [`skills/swarm-diagnostics/SKILL.md`](skills/swarm-diagnostics/SKILL.md)
* **What It Does:** Runs `scripts/swarm_diagnostics.py` over Antigravity `transcript.jsonl` logs and `.swarm/` telemetry to diagnose repeated work, ignored plans, fix-loop escalations, errors/stumbles, skill firing timelines, and token/time bottlenecks—where **every finding cites exact `transcript.jsonl:<line>` or `step_index` evidence**.

---

## 3. Supporting Engineering & Integration Skills

| Skill | File | Description & Usage |
| :--- | :--- | :--- |
| **`/goal-loop`** | [`skills/goal-loop/SKILL.md`](skills/goal-loop/SKILL.md) | Hierarchical Goal $\rightarrow$ Tasks $\rightarrow$ Sub-Tasks engine (`scripts/goal_loop.py`). Supports `--preflight`, `--task-brief`, `--review-package`, AST call-site wiring checks, and Hard-Cap Two-Verdict recording. |
| **`/swarm-diagnostics`** | [`skills/swarm-diagnostics/SKILL.md`](skills/swarm-diagnostics/SKILL.md) | 7-dimension `transcript.jsonl:<line>` session & sub-agent diagnostic analyzer (`scripts/swarm_diagnostics.py`). |
| **`/quality-validator`** | [`skills/quality-validator/SKILL.md`](skills/quality-validator/SKILL.md) | Runs automated runtime smoke tests (`scripts/quality_validator.py`) enforcing fresh verification evidence before completion claims. |
| **`/tmux-orchestrator`** | [`skills/tmux-orchestrator/SKILL.md`](skills/tmux-orchestrator/SKILL.md) | Linux `tmux` session and split-pane CLI runbook for managing headless background runners. |
| **`/math-reasoning`** | [`extras/math-reasoning/SKILL.md`](extras/math-reasoning/SKILL.md) | Optional extra: routes complex mathematical proofs, competition math, and physics derivations to local GPU `Limite 1B - Violetto` (with native/SymPy fallback). |

---

## 4. Key CLI Scripts Reference (`scripts/`)

```bash
# 1. Goal-Loop, Pre-Flight, Task Briefs, Review Packages & Hard-Cap Recording:
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --init
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --preflight
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --task-brief TASK-001
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --review-package TASK-001 --base-sha <SHA>
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --audit-task TASK-001
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --record-task TASK-001 --spec-verdict PASS --critical-count 0 --important-count 0 --minor-count 1

# 2. UI Direction Dealer (Surface Modes + Design Dials + Dealt Directions + DESIGN.md Persistence):
python3 "$AGENT_SWARM_HOME/scripts/ui_direction_dealer.py" --mode persuade --query "AI code studio" --deal 3 --variance 8 --motion 7 --density 4
python3 "$AGENT_SWARM_HOME/scripts/ui_direction_dealer.py" --mode operate --query "analytics console" --variance 6 --motion 4 --density 8 --persist --output-dir . -p "Ops Console" --page dashboard

# 3. 3-Viewport (1440/768/390) + Reduced-Motion Real-Browser UI Inspector:
python3 "$AGENT_SWARM_HOME/scripts/web_ui_validator.py" .swarm/blueprint/ui_proposals/template_1.html --mode persuade --screenshots-dir .swarm/ui_inspect --json

# 4. Evidence-Cited Swarm Session Diagnostics:
python3 "$AGENT_SWARM_HOME/scripts/swarm_diagnostics.py" --conversation-id <CONV_ID> --out .swarm/diagnostics_report.md
```

---

## License

MIT, see [LICENSE](LICENSE).
