# Autonomous Evolutionary Agent Swarm & Product Discovery Suite (`agent-swarm` v3.0)

A multi-agent orchestration plugin, literature/market/commercial discovery suite (`/product-discovery`), hierarchical Goal-Loop & AST wiring/authenticity engine (`/goal-loop` / `scripts/goal_loop.py`), Two-Verdict Categorical Discriminator Gate (`/discriminator-gate`), empirical UI/UX Art Direction Dealer & 3-Viewport Real-Browser Inspector (`/ui-ux-design`, `scripts/ui_direction_dealer.py`, `scripts/web_ui_validator.py`), security & prompt-injection scanner (`/agent-shield`), evidence-cited session diagnostics (`/swarm-diagnostics`), goal-driven development loop (`/invoke-swarm`: **Lite Mode** by default, opt-in **best-of-3** and **Full Mode**), and an experimental **design track** ported from Google's Elephant-Goldfish Model (`/coop-brainstorm` lenses, `/design-draft`, `/goldfish-review`, `goal_loop.py --import-design`).

Rather than claiming "zero fake code", `scripts/goal_loop.py` enforces concrete static and AST checks that catch:
- Unimplemented stubs (`TODO`/`FIXME`/`NotImplementedError`/empty `pass` or `...` bodies) and mock imports in production files.
- Constant returns adjacent to fake/stub/hardcoded comments (`CONSTANT_RETURN_WITH_FAKE_COMMENT`, e.g., `return 1.25  # fake`).
- Test files that only assert on mocks (`MOCK_ONLY_TEST_FILE`, e.g., `MagicMock`, `AsyncMock`, `patch`, `.assert_called*`, `jest.fn`) without asserting on real production outputs, or vacuous tautological test files (`VACUOUS_TEST_FILE`, e.g., `assert True`).
- Missing call-site wiring across entrypoints (`verify_wiring`) and unreferenced orphan modules (`ORPHAN_UNWIRED_MODULE`).

> **Printable Desk Reference (2-Page A4 PDF):** A print-ready 2-page (front-and-back A4) PDF cheat sheet featuring a quick skill decision guide, vector SVG workflow graph, all skills, Two-Verdict categorical gate rules, and `.swarm/` file mappings is included at [`SWARM_CHEATSHEET.pdf`](SWARM_CHEATSHEET.pdf) (regenerated via `scripts/generate_cheatsheet_pdf.py`).

---

## Benchmark: What the Swarm Adds

We ran 6 build tasks (`T1`–`T6`) 3 times each across three arms on the same model (`inherit`): a **single agent** with the spec only, a **checked single agent** that also gets acceptance criteria and self-check commands, and **Swarm Lite** (the same criteria plus a separate Discriminator Gate reviewer). We then ran 2 follow-up tasks (`T7`: 6 modules split across 3 parallel workers on a shared contract; `T8`: 4 stated invariants with 12 unstated edge-case traps) 3 times each in `single_agent_checked` vs. `swarm_lite` (**66 runs total**). Full data, threats to validity, and reproduction steps are in [`benchmarks/RESULTS.md`](benchmarks/RESULTS.md).

| Metric (`T1`–`T6`, 18 runs per arm) | Single agent | Checked single agent | Swarm Lite (Worker + Gate) |
| :--- | :---: | :---: | :---: |
| Runs passing all held-out checks | 16 / 18 | 18 / 18 | 18 / 18 |
| Defects found afterwards | 2 (both on the UI task) | 0 | 0 |
| Reviewer findings that changed shipped code | n/a | n/a | 0 (all 18 passed review on round 1) |
| Transcript tokens (estimate: chars / 4) | 194k | 198k | 433k |
| Wall-clock time, sum | 6,010 s | 5,472 s | 7,396 s |

| Follow-up (`T7` & `T8`, 3 runs per cell; `swarm_lite` includes orchestrator) | Checked single agent | Swarm Lite (Orchestrator + Workers + Gate) | Ratio (`swarm` / `checked`) |
| :--- | :---: | :---: | :---: |
| **T7** Parallel order fulfilment (6 modules, 11 seam checks) | **3 / 3** · 269 s · 13.0k tok | **3 / 3** · 782 s · 99.0k tok (73.3k subagents) | **2.91×** time · **7.59×** tok (`0` defects) |
| **T8** Expense ledger traps (4 invariants, 12 unstated edge cases) | **3 / 3** · 252 s · 9.5k tok | **3 / 3** · 543 s · 30.8k tok (19.5k subagents) | **2.16×** time · **3.24×** tok (`0` defects) |

**What this shows:**
- The quality gain comes from giving the worker acceptance criteria and self-check tools (`web_ui_validator.py`, `goal_loop.py --audit-task`), at no measurable extra cost (`+1.8%` tokens on `T1`–`T6`).
- Across all 36 Discriminator Gate reviews (`18` on `T1`–`T6`, `15` on `T7`, `3` on `T8`), the separate reviewer subagent recorded `0` blocking findings (`0` failed rounds). `/invoke-swarm lite` runs the deterministic gate always and skips the reviewer subagent unless acceptance cannot be checked by a command, parallel work merges on a shared contract, or you ask for it.
- On a 6-module task that a single checked agent finishes in ~4.5 minutes (`T7`), 3-wave orchestration (`T7.0` contract → 3 parallel workers → `T7.D` integration) prevented integration defects (`0/11` seam failures) but took `2.91×` wall time and `7.59×` tokens; reserve parallel worker dispatch for much larger modules.
- On `T8`, both arms derived all 12 unstated edge cases from the 4 stated invariants on round 1 (`3/3` each), hitting the same model ceiling as `T1`–`T3` and `T5`–`T6`.

**Harder tasks and shared-goal peers** (Claude Code runs, separate harness and model; see `RESULTS.md` §7):
- A single checked agent solved four harder tasks graded against reference implementations perfectly: npm semver ranges, cron schedules, `.gitignore` matching, and a full CommonMark 0.31.2 renderer (652/652 spec examples, 3 of 3 runs). No task left a quality gap for a multi-agent design to close.
- On the CommonMark task (~15–20 minutes for one agent), **three self-organising peers with one shared goal** ([`/peer-swarm`](skills/peer-swarm/SKILL.md): no orchestrator, no reviewer, a shared board) matched that quality in all 3 runs and finished in **0.57×** the wall time for **1.92×** the tokens. That is the one setup here where adding agents paid off: time, at about twice the token price, on a task large enough to split. On 3.5- and 7-minute tasks the same peers saved no time (1.24× and 0.97×) at about 3× the tokens.
- Acceptance criteria can narrow the spec: on `T1`, every run given a narrowed checklist item **inside the spec** implemented the narrow version. A follow-up (`RESULTS.md` §9) put the same item only in the task's checklist: all 6 runs (current pack and v2.7) built the full rule, and in all 3 current-pack runs `/invoke-swarm` Step 0.1 caught and rewrote the item before dispatch.

**Real bugs with hidden tests** (SWE-bench Verified, 20 instances, `RESULTS.md` §8): one checked agent resolved 14/20; `best-of-3` 17/20 at 3.0× the tokens; Lite Mode with the reviewer 17/20 at 2.1×. The reviewer stopped 4 tasks and caught 3 regressions the hidden tests cannot see. One run each, so suggestive rather than significant. This is why `/invoke-swarm` now defaults to Lite and offers best-of-3 as an option.

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

**Upgrading from v2.x:** re-run `./install.sh claude-code` (or your target) after pulling. It links the two new skills (`/design-draft`, `/goldfish-review`) and the read-only reviewer agent `agents/goldfish.md` into `~/.claude/agents/`. `/invoke-swarm` without an argument now runs Lite Mode; use `/invoke-swarm full` for the 3-epoch funnel.

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
| `ZOTERO_API_KEY`, `ZOTERO_USER_ID` | Zotero Web API for `/tech-research` and `/paper-to-code`. Also read from `~/.env`, `./.env`, or the file named by `ZOTERO_ENV_FILE`. |
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
skills/       25 skills, one folder each with a SKILL.md
agents/       goldfish.md, the read-only reviewer agent for Claude Code (linked by install.sh)
docs/designs/ Design documents (this pack's own: skill-pack-v3.md)
scripts/      Python tools the skills call (goal_loop.py, web_ui_validator.py, ...)
benchmarks/   Single agent vs. checked single agent vs. Swarm Lite benchmark harness, results & next-run guide
rules/        ORCHESTRATOR.md orchestrator rules
tests/        python3 -m unittest discover -s tests
extras/       Skills tied to specific local infrastructure; not installed by default (see extras/README.md)
plugin.json   Antigravity plugin manifest
install.sh    Installer (copy for Antigravity, symlinks elsewhere)
LICENSE       MIT
```

---

## End-to-End Workflow Overview

The toolkit is divided into two phases — **`/product-discovery`** for Phase A and **`/invoke-swarm`** (Lite by default; `best-of-3` or `full` on request) for Phase B, governed by the **Hierarchical Goal-Loop & Outcome Engine (`/goal-loop`)**, and **every individual skill can also be invoked standalone**:

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│  PHASE A: INITIAL DISCOVERY, POTENTIAL SCOUTING & PRODUCT PLAN (/product-discovery)│
│                  (Invoked independently prior to running the swarm)                │
├────────────────────────────────────────────────────────────────────────────────────┤
│  [Wave 1: Parallel Web, Literature & Market Potential Scouting]                    │
│    ├── 1. /tech-research       ──► Web Crawl + High-Impact Papers + Zotero DB      │
│    ├── 2. /market-research     ──► 3-Agent Swarm: Competitors, VoC Pain & TAM/SAM  │
│    ├── 3. /commercial-strategy ──► 2-Agent Swarm: Open-Core/B2B Licensing, COGS &  │
│    │                               Kill-Risks + `.swarm/blueprint/market_dashboard.html`│
│    └── 4. /paper-to-code       ──► Extracts Zotero/arXiv equations into code+tests │
│                                          │                                         │
│                                          ▼                                         │
│  [Checkpoint 1: Interactive Product Planning & Six-Lens Goldfish Critique]         │
│    └── 5. /coop-brainstorm     ──► High-ROI Potentials + Search-First Adopt/Build +│
│                                    6 read-only lens reviewers ──► product notes    │
│                                          │                                         │
│                                          ▼                                         │
│  [Wave 2 + Checkpoint 2: Dealt UI Directions, Craft Floor & 3-Viewport Gate]       │
│    └── 6. /ui-ux-design        ──► Surface Mode (Persuade/Operate/Read/Experience) │
│                                    + Design Dials (--variance/--motion/--density)  │
│                                    + `ui_direction_dealer.py` + Idea Sentence +    │
│                                    One Live Thing + 3 Single-File HTML Prototypes  │
│                                    (Verified at 1440/768/390 via /visual-ui-validator)│
│                                          │                                         │
│                                          ▼                                         │
│  [Design: Elephant drafts, Goldfish review, plan imported]  (experimental)         │
│    ├── 7. /design-draft        ──► docs/designs/<product>.md, section by section   │
│    ├── 8. /goldfish-review     ──► 4 stages of read-only fresh reviewers           │
│    └── 9. goal_loop.py --import-design ──► `.swarm/goal_loop.json` tasks           │
└──────────────────────────────────────────┬─────────────────────────────────────────┘
                                           │ (Reviewed design, `DESIGN.md` & `.swarm/goal_loop.json`)
                                           ▼
╔════════════════════════════════════════════════════════════════════════════════════╗
║  PHASE B: GOAL-DRIVEN SWARM LOOP (/invoke-swarm — Lite default, best-of-3, Full)   ║
╠════════════════════════════════════════════════════════════════════════════════════╣
║  [Step 0 / 0.25 / 0.5] Load `.swarm/goal_loop.json`, run `goal_loop.py --preflight`║
║                 conflict scan, and `/contract-lock` freezes `src/contracts/`       ║
║                 │                                                                  ║
║                 ▼                                                                  ║
║  [Step 1]   Parallel Implementation Sub-Agents (Isolated Git Worktrees +           ║
║             Zero-Context-Bloat `.swarm/briefs/<ID>-brief.md` + `< 15 lines` return)║
║             + `immortal_watcher` (Auto-revives stalled or interrupted sub-agents)  ║
║             + Parallel `sota_web_scout` (Full mode only)                           ║
║                 │                                                                  ║
║                 ▼                                                                  ║
║  [Step 1.5] `discriminator` Two-Verdict Categorical Gate (`/discriminator-gate`)   ║
║             Packages `BASE_SHA..HEAD` diff (`--review-package`), checks AST wiring ║
║             & `BLOCKING_FAIL` invariants, evaluates Spec Compliance (`PASS/FAIL`)  ║
║             + Severity Buckets (`Critical` [blocks], `Important` [blocks],         ║
║             `Minor` [deferred to `.swarm/deferred_minor_ledger.md`]).              ║
║             ├── Needs Fixes (Rounds 1-3) ──► Same Worker + Scoped `FIX_BASE..HEAD` ║
║             ├── Needs Fixes (Rounds 4-5) ──► Fresh Escalated Worker Sub-Agent      ║
║             ├── Round 5 Breaker          ──► Record `Ruling:` in `.swarm/ledger.md`║
║             └── Approved (0 Crit/Imp)    ──► Task Completed & Worker Approved      ║
║                 │                                                                  ║
║                 ▼                                                                  ║
║  [Step 2-3] Snapshot base (`--snapshot-create`), merge branches (`/merge-surgeon`),║
║             verify whole-repo authenticity (`--scan-authenticity`) & Validator     ║
║             ├── LITE MODE (`--lite`): Check `goal_loop.py --verify-goal` &         ║
║             │                         `immortal_watcher.py --check-convergence --lite`║
║             │                         ──► DONE in 1 Epoch (skips Steps 4-6)!       ║
║             └── FULL MODE: Write `intermittent_report.md` & continue to Steps 4-7  ║
║                 │                                                                  ║
║                 ├───────────────────────────────┬───────────────────────────────┐  ║
║                 ▼                               ▼                               ▼  ║
║  [Step 4-5] `rigor_auditor`           `safety_auditor`         `innovation_auditor`║
║             (Unanchored math/algo,    (`/agent-shield` scan,   (Novelty, 14-Pass   ║
║              AST wiring & `pass^k`)    resilience & threats)   UI & outcome craft) ║
║                 │                               │                               │  ║
║                 └───────────────┬───────────────┴───────────────┬───────────────┘  ║
║                                 ▼                               ▼                  ║
║  [Step 6]   `sota_web_scout` evaluates `ALREADY_SOTA` vs `UPGRADES_AVAILABLE`      ║
║             against `.swarm/sota/sota_knowledge_base.md`                           ║
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
* **What It Does:** Executes the **Phase A Web/Literature Scouting, Market Opportunity Analysis & Product Planning Pipeline** using **2 parallel autonomous waves**, **2 interactive human decision checkpoints**, and a built-in **Truth-in-Code Sufficiency & Anti-Bloat Gate** for existing repositories:
  * **Wave 1 (Parallel Intelligence Swarm):** Runs `/tech-research`, `/market-research`, and `/commercial-strategy` concurrently.
  * **Checkpoint 1 (`/coop-brainstorm` + Sufficiency Gate + Lens Review):** Synthesizes Wave 1 findings, has six read-only Goldfish lenses critique the concept, locks `HIGH` Net-ROI features, and writes product notes plus the root goal.
  * **Design (`/design-draft` → `/goldfish-review` → `--import-design`):** Writes the design document, reviews it with fresh read-only reviewers, and imports its implementation plan as the task list (after the user confirms the commands it will run).
  * **Wave 2 & Checkpoint 2 (`/ui-ux-design`):** Classifies Surface Mode (`Persuade` / `Operate` / `Read` / `Experience`), sets Design Dials (`--variance`, `--motion`, `--density`), deals 3 empirical art directions via `scripts/ui_direction_dealer.py`, defines the Subject Inventory + **The Idea Sentence** + **One Live Thing**, builds 3 single-file HTML/CSS/JS prototypes, validates them across `1440`, `768`, and `390` viewports + `prefers-reduced-motion` via `scripts/web_ui_validator.py`, and persists `DESIGN.md` + `.swarm/surfaces/<slug>.md`.

### 1.1 `/tech-research` - [`skills/tech-research/SKILL.md`](skills/tech-research/SKILL.md)
* **What It Does:** Executes three parallel research streams (Zotero DB via `scripts/zotero_tool.py`, High-Impact Literature via OpenAlex/arXiv/PubMed, and Web/OSS SOTA crawl) and writes `.swarm/blueprint/tech_research_report.md` (renamed from `/deep-research` to avoid clashing with built-in harness skills).

### 1.2 `/market-research` - [`skills/market-research/SKILL.md`](skills/market-research/SKILL.md)
* **What It Does:** Spawns 3 parallel market intelligence sub-agents (`competitor_teardown_scout`, `voice_of_customer_miner`, `tam_icp_gtm_analyst`).

### 1.3 `/commercial-strategy` - [`skills/commercial-strategy/SKILL.md`](skills/commercial-strategy/SKILL.md)
* **What It Does:** Spawns 2 parallel commercialization & adversarial sub-agents (`pricing_monetization_strategist`, `moat_and_risk_skeptic`) and generates `.swarm/blueprint/market_dashboard.html`.

### 1.4 `/coop-brainstorm` - [`skills/coop-brainstorm/SKILL.md`](skills/coop-brainstorm/SKILL.md)
* **What It Does:** Interactive ideation partner and Search-First Adopt/Build gate. Before the user locks the concept, six read-only Goldfish lenses critique it (need, ergonomics, cost, migration, observability, maintenance). Writes product notes for `/design-draft` and the root goal; no tasks.

### 1.5 `/ui-ux-design` - [`skills/ui-ux-design/SKILL.md`](skills/ui-ux-design/SKILL.md)
* **What It Does:** Combines the best of `leonxlnx/taste-skill`, `pbakaus/impeccable`, and `nextlevelbuilder/ui-ux-pro-max-skill`:
  1. **Surface Modes (`Persuade` | `Operate` | `Read` | `Experience`) & Parametric Design Dials (`--variance 1-10`, `--motion 1-10`, `--density 1-10`)**.
  2. **Dealt Empirical Art Directions (`scripts/ui_direction_dealer.py`)**: Deals 3 distinct, non-overlapping art directions with typography ratios, color tokens, and non-repeating section blueprints so the model never falls back to generic category averages.
  3. **Subject Inventory + "The Idea Sentence" (Competitor Swap Test) + "One Live Thing"**: Ensures every prototype is unmistakably tied to the product's domain and includes a working interactive micro-tool on the first viewport.
  4. **Craft Floor & Browser Surfaces**: Enforces custom `::selection`, focus rings, custom scrollbars, `tabular-nums`, and $\le 2$-line headlines, verified across 3 viewports (`1440/768/390`) + `prefers-reduced-motion` via `scripts/web_ui_validator.py`.

### 1.6 `/paper-to-code` - [`skills/paper-to-code/SKILL.md`](skills/paper-to-code/SKILL.md)
* **What It Does:** Extracts formal mathematical equations and algorithms from Zotero/arXiv papers into verified code and unit tests.

### 1.7 `/design-draft` (experimental) - [`skills/design-draft/SKILL.md`](skills/design-draft/SKILL.md)
* **What It Does:** The Elephant writes `docs/designs/<name>.md` with the user, one section group at a time, from the product notes or the user's notes. It then lists where the draft contradicts the notes, and checks the implementation plan with `goal_loop.py --import-design --dry-run`. The plan's `### Task` blocks (files, dependencies, changes, verification, review focus) become the task list.

### 1.8 `/goldfish-review` (experimental) - [`skills/goldfish-review/SKILL.md`](skills/goldfish-review/SKILL.md)
* **What It Does:** Reviews any Markdown document with read-only reviewers that have no conversation history (Claude Code: `agents/goldfish.md`; Antigravity: write tools off). The stages run in order: zoom-out first (stops on a Blocker), then comprehension (the reviewer restates the document), critics, and implementation readiness, with an import dry run. The Elephant classifies each finding as fix, contest, escalate or decline, and the user decides before any edit. It shows a token estimate first: about 100k tokens per reviewer, measured on this pack's own design.

---

## 2. Evolutionary Swarm Loop & Standalone Stage Skills

### 2.1 `/invoke-swarm` (Lite by default, best-of-3, Full) - [`skills/invoke-swarm/SKILL.md`](skills/invoke-swarm/SKILL.md)
* **What It Does:** Master orchestrator for the goal-driven swarm loop. No argument means Lite; the orchestrator may suggest another mode in one line and switches only when you say so.

  | Mode | Fits when | Tokens vs. one checked agent | Wall time |
  | :--- | :--- | :--- | :--- |
  | one checked agent (not a swarm) | One task, acceptance runnable | 1× | 1× |
  | **`lite` (default)**, reviewer skipped | Acceptance runnable as commands | estimated 2–3× | not measured |
  | `lite` + reviewer | Real acceptance hidden or judgment-heavy | 2.1× SWE-bench | 2.3× SWE-bench |
  | `best-of-3` (opt-in) | Several plausible fixes, Python tests, wall time matters | 3.0× SWE-bench | 1.5× SWE-bench |
  | `/peer-swarm` | One build of 15+ min that splits along modules | 1.9× (T12) | 0.57× (T12) |
  | `full` (opt-in) | You ask for multi-epoch hardening | not measured | not measured |

  * **Lite Mode (`/invoke-swarm`):** **1 epoch** with Pre-Flight (`goal_loop.py --preflight`), workers dispatched in waves of ready tasks (`depends_on`) that run their own acceptance checks (`.swarm/briefs/<ID>-brief.md`), the deterministic gate (`goal_loop.py --audit-task` / `--record-task`), and the **Validator** (tests + `/visual-ui-validator` + `goal_loop.py --verify-goal`). The **Discriminator Gate** reviewer runs only when acceptance cannot be checked by a command, parallel work merges on a shared contract, or you ask for it. At the exit gate you can request a release-level audit (`/triad-audit` + `/sota-web-scout`); the findings you pick become `AUDIT-<n>` tasks.
  * **Best-of-3 (`/invoke-swarm best-of-3`, opt-in):** Three workers in separate git worktrees, `scripts/attempt_picker.py` cross-tests their new tests, and the winner is merged and gated.
  * **Full Mode (`/invoke-swarm full`, opt-in):** Runs up to 3 macro-epochs adding unanchored `/triad-audit` + `/agent-shield`, `/sota-web-scout`, `/epoch-planner` re-planning, and the Epoch 3 `.swarm/deferred_minor_ledger.md` sweep.

### 2.1b `/peer-swarm` (Shared Goal, Self-Organising Peers) - [`skills/peer-swarm/SKILL.md`](skills/peer-swarm/SKILL.md)
* **What It Does:** Starts 3 peer agents at once in one workspace on one shared goal (`TASK_SPEC.md` with its acceptance checks). The peers split the work, agree interfaces, and test each other's code through `.swarm/board.md`; there is no orchestrator and no reviewer. You verify the result with the acceptance commands and `goal_loop.py --scan-authenticity`.
* **When To Use It:** One large build (roughly 15+ minutes for a single agent) that splits along natural module boundaries, when finishing sooner is worth about twice the tokens. Benchmarked at 0.57× wall time and 1.92× tokens with identical quality on a CommonMark renderer.

### 2.2 `/contract-lock` (Step 0.5 + Pre-Flight + Brownfield `spec-miner`) - [`skills/contract-lock/SKILL.md`](skills/contract-lock/SKILL.md)
* **What It Does:** Runs `goal_loop.py --preflight` to detect shared-file/interface overlaps, freezes `src/contracts/`, and mines brownfield `WHEN -> THEN` & `ALWAYS TRUE` invariants into `docs/INVARIANTS.md`.

### 2.3 `/discriminator-gate` (Step 1.5 — Two-Verdict Categorical Gate + 5-Round Escalating Loop) - [`skills/discriminator-gate/SKILL.md`](skills/discriminator-gate/SKILL.md)
* **What It Does:** Evaluates worker diffs using **Deterministic Evidence Packaging + Categorical Verdicts** (no arbitrary decimal scores):
  1. **Review Package (`goal_loop.py --review-package <ID>`):** Bundles `BASE_SHA..HEAD` commits, diff stats, `-U10` diffs, and deterministic `BLOCKING_FAIL` / `ADVISORY_WARN` checks into `.swarm/reviews/<ID>-review.diff.md`.
  2. **Restatement first:** the reviewer gets the spec path, restates what the task requires, and never writes to the workspace.
  3. **Part 1 — Spec & Outcome Compliance (`PASS` | `FAIL` | `UNVERIFIABLE`):** Audits `Missing`, `Extra (YAGNI)`, `Misunderstood`, and whether tests prove the plan's `## Review Focus` failure modes.
  4. **Part 2 — Code Quality Severity Buckets (`Approved` | `Needs Fixes`):**
     * **`Critical` (`critical_count > 0`):** Blocks immediately (`gate_verdict: FAIL`).
     * **`Important` (`important_count > 0`):** Blocks immediately (`gate_verdict: FAIL`).
     * **`Minor` (`minor_count > 0`):** Logged to `.swarm/deferred_minor_ledger.md` for Epoch 3 Polish; **never blocks the task or triggers a fix loop**.
  5. **5-Round Escalating Fix Loop & Scoped Re-Review (`FIX_BASE..HEAD`):**
     * **Rounds 1–3:** Resume the *same* worker sub-agent with only the open `Critical`/`Important` items. Re-review is strictly scoped to `FIX_BASE..HEAD` (`ADDRESSED | NOT ADDRESSED` + `New Breakage in the Fix Diff`).
     * **Rounds 4–5 (Escalation):** Spawn a **fresh worker sub-agent** (`"A prior implementer attempted this task 3 times; you own it now"`).
     * **Round 5 Breaker (`Ruling:`):** Stops looping and records a typed ruling (`OVERRIDE`, `SPLIT_TASK`, `RE_ARCHITECT_CONTRACT`, or `ESCALATE_TO_USER`) with `Ruling: <decision> — <why> — <cost if wrong>` in `.swarm/ledger.md` to surface to the user. A ruling never overturns a deterministic `BLOCKING_FAIL`, and only `OVERRIDE` completes a task.

### 2.4 `/merge-surgeon` (Step 3 Integration + 4-Phase Conflict Root Cause) - [`skills/merge-surgeon/SKILL.md`](skills/merge-surgeon/SKILL.md)
* **What It Does:** Pre-merge Git snapshots (`--snapshot-create`), `git merge --no-ff`, systematic 4-phase conflict resolution (escalating architecture if 3 attempts fail), and post-merge verification.

### 2.5 `/triad-audit` (Steps 4-5 — Unanchored Parallel Isolation) - [`skills/triad-audit/SKILL.md`](skills/triad-audit/SKILL.md)
* **What It Does:** Spawns `rigor_auditor`, `safety_auditor` (`/agent-shield`), and `innovation_auditor` in **Unanchored Parallel Isolation** (each completes its semantic review before deterministic detector outputs are merged, declaring `Method: triad-isolated` in the header and reporting categorical `PASS`/`FAIL` verdicts based on `critical_count == 0 and high_count == 0`).

### 2.6 `/agent-shield` - [`skills/agent-shield/SKILL.md`](skills/agent-shield/SKILL.md)
* **What It Does:** 5-category security, prompt-injection, Trojan-Source Unicode, hook pipe, MCP context-tax, and silent-failure scanner (`scripts/agent_shield.py`).

### 2.7 `/perf-benchmarker` - [`skills/perf-benchmarker/SKILL.md`](skills/perf-benchmarker/SKILL.md)
* **What It Does:** Quantitative latency, peak RSS memory, and `pass^k` non-flakiness tracker (`scripts/perf_tracker.py`).

### 2.8 `/visual-ui-validator` (3-Viewport Real-Browser Inspector + Unanchored Dual-Agent Critique) - [`skills/visual-ui-validator/SKILL.md`](skills/visual-ui-validator/SKILL.md)
* **What It Does:** Runs `scripts/web_ui_validator.py` across **`1440x900`, `768x1024`, and `390x844` + `prefers-reduced-motion`**, checking headline line counts ($\le 2$), `1.2s` `h1` visibility, outer margin symmetry, $<15\%$ empty screens, scroll text collisions, live motion counts, WCAG contrast, and anti-slop rules (eyebrow pills, `01/02/03` numbering, monospace prose, resting shadows, side-stripe borders, icon-card grids, AI purple / cream+terracotta), paired with **Unanchored Dual-Agent Critique (Assessment A: 14-Pass Visual Screenshot Rubric; Assessment B: Deterministic Inspector JSON `PASS`/`FAIL`)**.

### 2.9 `/sota-web-scout` (Step 6) - [`skills/sota-web-scout/SKILL.md`](skills/sota-web-scout/SKILL.md)
* **What It Does:** Parallel web, GitHub, and literature SOTA benchmark researcher outputting categorical `ALREADY_SOTA` or `UPGRADES_AVAILABLE` verdicts.

### 2.10 `/epoch-planner` (Full Mode, opt-in) & `/immortal-agents`
* **What It Does:** `/epoch-planner` generates Step 3 Intermittent Reports and Step 7 Adjusted Plans (with mandatory `## Review Focus` failure modes) in Full Mode or standalone. `/immortal-agents` supervises and revives active sub-agents in every mode.

### 2.11 `/swarm-diagnostics` (Evidence-Cited Session Diagnostics) - [`skills/swarm-diagnostics/SKILL.md`](skills/swarm-diagnostics/SKILL.md)
* **What It Does:** Runs `scripts/swarm_diagnostics.py` over Antigravity `transcript.jsonl` logs and `.swarm/` telemetry to diagnose repeated work, ignored plans, fix-loop escalations, errors/stumbles, skill firing timelines, and token/time bottlenecks—where **every finding cites exact `transcript.jsonl:<line>` or `step_index` evidence**.

---

## 3. Supporting Engineering & Integration Skills

| Skill | File | Description & Usage |
| :--- | :--- | :--- |
| **`/goal-loop`** | [`skills/goal-loop/SKILL.md`](skills/goal-loop/SKILL.md) | Hierarchical Goal $\rightarrow$ Tasks $\rightarrow$ Sub-Tasks engine (`scripts/goal_loop.py`). Supports `--preflight`, `--task-brief`, `--review-package`, AST call-site wiring checks, constant-return/mock-only test detection, and categorical Two-Verdict recording. |
| **`/swarm-diagnostics`** | [`skills/swarm-diagnostics/SKILL.md`](skills/swarm-diagnostics/SKILL.md) | 7-dimension `transcript.jsonl:<line>` session & sub-agent diagnostic analyzer (`scripts/swarm_diagnostics.py`). |
| **`/quality-validator`** | [`skills/quality-validator/SKILL.md`](skills/quality-validator/SKILL.md) | Runs automated runtime smoke tests (`scripts/quality_validator.py`) enforcing fresh verification evidence before completion claims. |
| **`/tmux-orchestrator`** | [`skills/tmux-orchestrator/SKILL.md`](skills/tmux-orchestrator/SKILL.md) | Linux `tmux` session and split-pane CLI runbook for managing headless background runners. |
| **`/math-reasoning`** | [`extras/math-reasoning/SKILL.md`](extras/math-reasoning/SKILL.md) | Optional extra: routes complex mathematical proofs, competition math, and physics derivations to local GPU `Limite 1B - Violetto` (with native/SymPy fallback). |

---

## 4. Key CLI Scripts Reference (`scripts/`)

```bash
# 1. Goal-Loop, Pre-Flight, Task Briefs, Review Packages & Categorical Gate Recording:
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --init
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --preflight
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --task-brief TASK-001
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --review-package TASK-001 --base-sha <SHA>
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --audit-task TASK-001
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --record-task TASK-001 --spec-verdict PASS --critical-count 0 --important-count 0 --minor-count 1
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --import-design docs/designs/<name>.md --dry-run   # then without --dry-run

# 2. Swarm Lite Mode Initialization & Convergence Check (Lite is the default; add --full for Full Mode):
python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" --init-swarm --project-goal "<GOAL>"
python3 "$AGENT_SWARM_HOME/scripts/immortal_watcher.py" --check-convergence --lite

# 3. UI Direction Dealer (Surface Modes + Design Dials + Dealt Directions + DESIGN.md Persistence):
python3 "$AGENT_SWARM_HOME/scripts/ui_direction_dealer.py" --mode persuade --query "AI code studio" --deal 3 --variance 8 --motion 7 --density 4
python3 "$AGENT_SWARM_HOME/scripts/ui_direction_dealer.py" --mode operate --query "analytics console" --variance 6 --motion 4 --density 8 --persist --output-dir . -p "Ops Console" --page dashboard

# 4. 3-Viewport (1440/768/390) + Reduced-Motion Real-Browser UI Inspector:
python3 "$AGENT_SWARM_HOME/scripts/web_ui_validator.py" .swarm/blueprint/ui_proposals/template_1.html --mode persuade --screenshots-dir .swarm/ui_inspect --json

# 5. Evidence-Cited Swarm Session Diagnostics:
python3 "$AGENT_SWARM_HOME/scripts/swarm_diagnostics.py" --conversation-id <CONV_ID> --out .swarm/diagnostics_report.md
```

---

## Acknowledgements

The design track (`/design-draft`, `/goldfish-review`, the `/coop-brainstorm` lenses) adapts ideas from Google's [Elephant-Goldfish Model](https://github.com/google/elephant-goldfish-model) (Apache-2.0), rewritten for this pack; no EGM files are copied. The design that planned this port, reviewed by its own method, is [`docs/designs/skill-pack-v3.md`](docs/designs/skill-pack-v3.md).

## License

MIT, see [LICENSE](LICENSE).
