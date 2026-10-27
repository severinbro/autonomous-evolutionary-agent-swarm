---
name: product-discovery
description: "Use when starting a new product or a major new direction and the user wants research, market and commercial analysis, a locked plan, and UI prototypes before implementation, or asks whether an existing project needs changes at all."
disable-model-invocation: false
triggers: [user, model]
---

# Phase A Master Orchestrator: Web & Literature Scouting, Market Opportunity Analysis & Product Planning (`/product-discovery`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

Use `/product-discovery` to run an **initial end-to-end discovery, potential analysis, and product planning pass (Phase A)** before launching the autonomous evolutionary implementation swarm (`/invoke-swarm`, Phase B).

`/product-discovery` never runs automatically inside `/invoke-swarm`; it is your dedicated **upfront discovery & product-planning workflow** that crawls the web, literature, and market landscape in parallel first, evaluates where the highest-leverage technical and commercial potentials lie, and pauses only at the **two high-leverage human decision checkpoints** (Product Scope/Architecture Lock and UI/UX Prototype Selection).

---

## Core Mandate: Zero-Placeholder, Zero-Synthetic & 100% Outcome-Committed Product Plans

Every `/product-discovery` run enforces four strict anti-placeholder and outcome-commitment rules:

1. **ZERO `[TBD]`, `TODO`, OR `Lorem ipsum` PLACEHOLDERS:**
   - No discovery or planning artifact (`deep_research_report.md`, `market_research_report.md`, `commercial_strategy_report.md`, `brainstorm_blueprint.md`, `docs/ARCHITECTURE.md`, or `ui_proposals/*.html`) may contain `[TBD]`, `[TODO]`, `Lorem ipsum`, `"Coming soon"`, or hand-waved sections.
2. **100% OUTCOME PARTICIPATION & ENTRYPOINT WIRING PATHS:**
   - Every approved feature in `brainstorm_blueprint.md` and `docs/ARCHITECTURE.md` **MUST** specify:
     - **Outcome Participation:** How this feature directly contributes to the user's desired end-to-end product output (no conceptual-only or ornamental subsystems).
     - **Entrypoint Wiring Path:** Exact call chain from the application entrypoint (`CLI`/`HTTP`/`UI event`) $\rightarrow$ controller/pipeline $\rightarrow$ module $\rightarrow$ observable output.
     - **End-to-End Verification Command (`--outcome-cmd`):** The executable command that proves the feature works in the integrated product.
3. **AUTOMATIC `.swarm/goal_loop.json` TASK & SUB-TASK SEEDING:**
   - At Checkpoint 1, `/product-discovery` initializes `.swarm/goal_loop.json` via `scripts/goal_loop.py` (`--init-goal`, `--add-task`, `--add-subtask`) so `/invoke-swarm` and `/goal-loop` immediately inherit verifiable Tasks, Sub-Tasks, `--wiring-files`, `--required-symbols`, and `--outcome-cmd`.
4. **ZERO DECORATIVE / DEAD UI CONTROLS IN WAVE 2 PROTOTYPES:**
   - Every control in `template_1..3_<slug>.html` must mutate real client-side domain state and update the DOM/Canvas/SVG. `scripts/web_ui_validator.py` and `scripts/goal_loop.py --verify-blueprint` automatically reject empty event listeners (`() => {}`), `alert("TODO")`, and placeholder text, looping the designer until `100% PASS`.

---

## Calling Modes

| Invocation / Command | What It Runs | Composable Skills Used |
| :--- | :--- | :--- |
| **`/product-discovery`** *(Default: Full Discovery & Product Plan)* | Runs **Wave 1** (`/deep-research` + `/market-research` + `/commercial-strategy` in parallel to crawl web/literature/market potentials) $\rightarrow$ **Checkpoint 1** (`/coop-brainstorm` + `.swarm/goal_loop.json` product task seeding) $\rightarrow$ **Wave 2 & Checkpoint 2** (`/ui-ux-design` 3 HTML prototypes) $\rightarrow$ `--verify-blueprint`. | [`deep-research`](../deep-research/SKILL.md), [`market-research`](../market-research/SKILL.md), [`commercial-strategy`](../commercial-strategy/SKILL.md), [`coop-brainstorm`](../coop-brainstorm/SKILL.md), [`ui-ux-design`](../ui-ux-design/SKILL.md), [`goal-loop`](../goal-loop/SKILL.md) |
| **`/product-discovery no-ui`** *(Backend / CLI / SDK Mode)* | Runs **Wave 1** (Research + Market + Commercial scouting) $\rightarrow$ **Checkpoint 1** (`/coop-brainstorm` + `.swarm/goal_loop.json` seeding) $\rightarrow$ `--verify-blueprint`, skipping `/ui-ux-design`. | `deep-research`, `market-research`, `commercial-strategy`, `coop-brainstorm`, `goal-loop` |
| **`/product-discovery tech-only`** *(Academic / Internal Tool Mode)* | Runs `/deep-research` (Zotero + Literature + Web SOTA crawl) + optional `/paper-to-code` $\rightarrow$ **Checkpoint 1** (`/coop-brainstorm` + `.swarm/goal_loop.json` seeding) $\rightarrow$ **Wave 2** (`/ui-ux-design`) $\rightarrow$ `--verify-blueprint`, skipping market/commercial swarms. | `deep-research`, `paper-to-code`, `coop-brainstorm`, `ui-ux-design`, `goal-loop` |
| **`/product-discovery market-only`** *(Market Opportunity & Positioning Mode)* | Runs `/market-research` (3 agents) + `/commercial-strategy` (2 agents) in parallel to scout market potentials and generates `.swarm/blueprint/market_dashboard.html`. | `market-research`, `commercial-strategy` |

---

## Execution Architecture (2 Parallel Waves + 2 Human Checkpoints + Plan Verification Gate)

```text
╔════════════════════════════════════════════════════════════════════════════════════╗
║      PHASE A MASTER ORCHESTRATOR (/product-discovery -> Ready for /invoke-swarm)   ║
╠════════════════════════════════════════════════════════════════════════════════════╣
║  [Step 0] Create `.swarm/blueprint/ui_proposals` & `.swarm/sota` directories       ║
║                                         │                                          ║
║                                         ▼                                          ║
║  [Wave 1: Parallel Web, Literature & Market Potential Scouting]                    ║
║    ├── Stream 1 (`/deep-research`): Zotero Library (`zotero_tool.py`) + OpenAlex/  ║
║    │   arXiv High-Impact Literature + Web/GitHub SOTA Crawl                        ║
║    ├── Stream 2 (`/market-research`): `competitor_teardown_scout` +                ║
║    │   `voice_of_customer_miner` (Switch Triggers) + `tam_icp_gtm_analyst`         ║
║    ├── Stream 3 (`/commercial-strategy`): `pricing_monetization_strategist`        ║
║    │   (Open-Core/B2B Licensing & Unit Econ) + `moat_and_risk_skeptic` (Kill-Risks)║
║    └── (Optional `/paper-to-code`): Extracts Zotero/arXiv equations into tests     ║
║        ──► Writes `deep_research_report.md`, `market_research_report.md`,          ║
║            `commercial_strategy_report.md` & renders `market_dashboard.html`       ║
║                                         │                                          ║
║                                         ▼                                          ║
║  [Checkpoint 1: Interactive Product Planning & Sufficiency Gate (`/coop-brainstorm`)]
║    ├── Scores Existing Repo Sufficiency (1-10) across Tech, Market, Arch & UI      ║
║    ├── If All Pillars >= 8.5 & Zero Net-ROI >= 8.0 Gaps ──► "ALREADY OPTIMAL" DONE!║
║    ├── Otherwise synthesizes product plan:                                         ║
║    │   1. High-Potential Opportunities (filtered by Net-ROI >= 8.0 anti-bloat rule)║
║    │   2. 3-Epoch Feature Matrix + Mandatory Outcome Participation & Wiring Paths  ║
║    │   3. Architecture (`Option 0: Keep Existing` if >= 8.5 vs. Competing Designs) ║
║    └── Pauses via `ask_question` ──► Writes `brainstorm_blueprint.md`, `DESIGN.md` ║
║        & seeds `.swarm/goal_loop.json` (Tasks, Sub-Tasks, Wiring & `--outcome-cmd`)║
║                                         │                                          ║
║                                         ▼                                          ║
║  [Wave 2 + Checkpoint 2: Parallel 3-Template UI/UX Generator (`/ui-ux-design`)]    ║
║    ├── Auto-skipped if Existing UI scores >= 8.5 & passes `web_ui_validator.py`    ║
║    ├── Deals 3 non-repeating directions via `ui_direction_dealer.py` (`--mode`,    ║
║    │   `--variance`, `--motion`, `--density`) + Subject Inventory & Idea Sentence  ║
║    ├── Spawns 3 parallel UI Designers building real stateful JS ("One Live Thing") ║
║    ├── Validates across `1440,768,390` + reduced-motion via `web_ui_validator.py`  ║
║    │   + Unanchored 14-Pass Visual Critique until 0 FAIL & >= 8.0/10               ║
║    └── Pauses via `ask_question` ──► Persists chosen direction via `--persist`     ║
║        to `DESIGN.md`, `.swarm/surfaces/<slug>.md`, & `ui_ux_proposals.md`         ║
║                                         │                                          ║
║                                         ▼                                          ║
║  [Final Gate] Run `goal_loop.py --verify-blueprint` (0 placeholders/dead controls) ║
╚════════════════════════════════════════════════════════════════════════════════════╝
```

---

## Step-by-Step Execution Protocol

### Step 0: Initialize Discovery & Planning Directories
```bash
mkdir -p .swarm/blueprint/ui_proposals .swarm/sota docs
```

### Wave 1: Parallel Web, Literature & Market Potential Scouting (`/deep-research` + `/market-research` + `/commercial-strategy`)
Launch the Wave 1 research and market sub-agents concurrently via `invoke_subagent` so all external web, academic, and market evidence is gathered in a single parallel pass:
1. **Deep Web, SOTA & Literature Research ([`/deep-research`](../deep-research/SKILL.md)):**
   - Inspects the user's personal Zotero library via `scripts/zotero_tool.py` (`collections`, `search`, `notes`, `pdf --grep`).
   - Queries high-impact academic literature (`OpenAlex` cited_by_count, `arXiv`, `EuropePMC`/`PubMed`) and crawls web/GitHub SOTA for technical potentials.
   - If running on an existing repository, compares the current implementation against literature/SOTA and scores **Technical & SOTA Sufficiency (`1-10`)** (reporting `[ALREADY SOTA]` if $\ge 8.5$ with no high-ROI gaps).
   - Writes `.swarm/blueprint/deep_research_report.md` and seeds `.swarm/sota/sota_knowledge_base.md`.
2. **Market Opportunity & Switch-Trigger Intelligence ([`/market-research`](../market-research/SKILL.md)) *(skipped in `tech-only` mode)*:**
   - Spawns `competitor_teardown_scout`, `voice_of_customer_miner`, and `tam_icp_gtm_analyst` to crawl competitor gaps and user switch triggers.
   - On existing repositories, builds a **Truth-in-Code Capability Inventory** and scores **Market & Switch-Trigger Sufficiency (`1-10`)**.
   - Writes `.swarm/blueprint/market_research_report.md` and seeds `.swarm/blueprint/market_data.json`.
3. **Open-Core & B2B Commercial Strategy ([`/commercial-strategy`](../commercial-strategy/SKILL.md)) *(skipped in `tech-only` mode)*:**
   - Spawns `pricing_monetization_strategist` and `moat_and_risk_skeptic`.
   - On existing repositories, audits dependency licenses (`GPL`/`AGPL` check) and module boundaries, scoring **Commercial & License Sufficiency (`1-10`)**.
   - Writes `.swarm/blueprint/commercial_strategy_report.md`, updates `.swarm/blueprint/market_data.json`, and generates + validates the interactive single-file `.swarm/blueprint/market_dashboard.html`:
     ```bash
     python3 "$AGENT_SWARM_HOME/scripts/market_dashboard.py" \
       --data .swarm/blueprint/market_data.json \
       --out .swarm/blueprint/market_dashboard.html
     python3 "$AGENT_SWARM_HOME/scripts/web_ui_validator.py" \
       .swarm/blueprint/market_dashboard.html
     ```

### Checkpoint 1: Interactive Product Planning, Outcome Wiring Lock & Goal-Loop Seeding ([`/coop-brainstorm`](../coop-brainstorm/SKILL.md))
1. Present a concise synthesis of Wave 1 findings (with clickable links to `deep_research_report.md`, `market_research_report.md`, `commercial_strategy_report.md`, and `market_dashboard.html`) along with:
   - **Existing-Repo Sufficiency Scorecard (when run on an existing project):** Scores (`1-10`) for Technical/SOTA Parity, Market/Switch-Trigger Coverage, Commercial/License Hygiene, Architecture (`Option 0`), and Existing UI/UX.
   - **Pillar 1:** High-Potential Opportunities & Innovation Hypotheses filtered by **Net-ROI $\ge 8.0$** *(or `[ALREADY SOTA — NO NEW COMPLEXITY NEEDED]` if current implementation is optimal)*.
   - **Pillar 2:** 3-Epoch Product Feature Matrix tagged by Open-Core/B2B tier (`[OSS Core / Wedge]`, `[Pro Cloud]`, `[B2B Enterprise]`, `[Rejected Bloat / Anti-Goals]`), where every feature explicitly declares its **Outcome Participation & Entrypoint Wiring Path** and **End-to-End Verification Command**.
   - **Pillar 3:** `Option 0: Keep Existing Architecture As-Is` (recommended whenever existing repo scores $\ge 8.5/10$) vs. competing Software Architecture Options.
2. **Sufficiency Early-Exit Option:**
   - If the existing repository scores **$\ge 8.5 / 10$ across all applicable dimensions** and has zero candidate changes with **Net-ROI $\ge 8.0$**, highlight **`(Recommended) Keep Project As-Is — Already Optimal (Skip UI & Swarm)`** as Option 1 in `ask_question`.
   - Otherwise, let the user select/customize their preferred Product Opportunities, Feature Tier priorities, Open-Core/B2B Licensing model, and Software Architecture.
3. **Persist Locked Product Plan & Seed `.swarm/goal_loop.json`:**
   - Write the confirmed decisions (including the **Outcome Participation & Entrypoint Wiring Matrix**) to `.swarm/blueprint/brainstorm_blueprint.md` and `docs/ARCHITECTURE.md`.
   - Seed `.swarm/goal_loop.json` with the overall product goal, end-to-end `--outcome-cmd`, and hierarchical **Tasks (`T1..Tn`)** and **Sub-Tasks (`T1.1..`)** (with `--target-files`, `--wiring-files`, and `--required-symbols`) via `scripts/goal_loop.py`:
     ```bash
     python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" \
       --init-goal "<Locked Overall Product Goal>" \
       --outcome-cmd "<End-to-End Product Verification Command>" \
       --entrypoints <entrypoint_files>
     ```

### Wave 2 & Checkpoint 2: 3-Template UI/UX Prototype Generation ([`/ui-ux-design`](../ui-ux-design/SKILL.md))
*(Skip this stage if invoked with `/product-discovery no-ui`, `/product-discovery market-only`, OR if the existing repository's UI already scored $\ge 8.5/10$ and passed `web_ui_validator.py` at Checkpoint 1 without the user requesting a visual redesign.)*
1. **Surface Mode, Design Dials & 3-Direction Deal (`ui_direction_dealer.py`):**
   - Classify the primary surface mode (`persuade`, `operate`, `read`, or `experience`), set the 3 Design Dials (`--variance <1-10>`, `--motion <1-10>`, `--density <1-10>`), and deal 3 non-repeating aesthetic directions tailored to the locked product plan in `brainstorm_blueprint.md`:
     ```bash
     python3 "$AGENT_SWARM_HOME/scripts/ui_direction_dealer.py" \
       --mode <persuade|operate|read|experience> \
       --query "<product domain, target users, and primary job>" \
       --deal 3 \
       --variance <1-10> --motion <1-10> --density <1-10>
     ```
2. **Subject Inventory, Idea Sentence (Competitor Swap Test) & One Live Thing:**
   - Before writing HTML, define the **Subject Inventory** (real domain data, artifact, or interactive state), write a 1-sentence **Idea Sentence** that passes the Competitor Swap Test, and specify **One Live Thing** (real client-side state machine) for each of the 3 dealt directions.
3. **Generate 3 Self-Contained HTML/CSS/JS Templates:**
   - Build `.swarm/blueprint/ui_proposals/template_1..3_<slug>.html` adhering to the Craft Floor & Browser Surface rules (zero `[TBD]`, `"Coming soon"`, `alert("TODO")`, no-op handlers, or AI slop tells).
4. **3-Viewport + Reduced-Motion Browser Inspection & Unanchored 14-Pass Visual Critique:**
   - Validate all 3 templates across `1440x900`, `768x1024`, `390x844`, and `prefers-reduced-motion: reduce` before showing them (looping and fixing any template that fails until all 3 return `"status": "PASS"` with `0 FAIL` and $\ge 8.0/10$ post-cap score):
     ```bash
     python3 "$AGENT_SWARM_HOME/scripts/web_ui_validator.py" \
       .swarm/blueprint/ui_proposals/template_1_*.html \
       .swarm/blueprint/ui_proposals/template_2_*.html \
       .swarm/blueprint/ui_proposals/template_3_*.html \
       --mode <persuade|operate|read|experience> \
       --screenshots-dir .swarm/blueprint/ui_proposals/screenshots \
       --json
     ```
5. **User Selection & Master Design System Persistence (`--persist`):**
   - Present clickable links to all 3 `.html` files, rendered screenshots, and `.swarm/blueprint/ui_ux_proposals.md`, and use `ask_question` to record the user's chosen template (or `"Keep Existing Project UI"` if preferred).
   - Persist the chosen direction into `DESIGN.md` and `.swarm/surfaces/<slug>.md` as the authoritative UI reference for `/invoke-swarm` Epoch 1:
     ```bash
     python3 "$AGENT_SWARM_HOME/scripts/ui_direction_dealer.py" \
       --mode <persuade|operate|read|experience> \
       --query "<chosen direction id and product context>" \
       --deal 1 \
       --variance <1-10> --motion <1-10> --density <1-10> \
       --persist --output-dir . -p "<Project Name>" --page main
     ```

---

## Final Phase A Product Plan Authenticity Gate & Handoff Summary

Before concluding `/product-discovery`, execute the automated plan authenticity verifier:
```bash
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" \
  --cwd . --verify-blueprint
```
- **If `"status": "FAIL"`:** Fix all reported placeholder markers (`[TBD]`, `Lorem ipsum`, etc.), missing sections, or invalid HTML templates immediately and re-run `--verify-blueprint` until `"status": "PASS"`.
- **Once `"status": "PASS"`:** Present the **Phase A Product Discovery & Readiness Table** linking every generated file in `.swarm/blueprint/`, `.swarm/goal_loop.json`, and `docs/ARCHITECTURE.md`:
  - **If Changes Were Approved:** Provide the exact Phase B launch command:
    ```text
    /invoke-swarm Implement the locked product plan in docs/ARCHITECTURE.md, .swarm/blueprint/brainstorm_blueprint.md, and .swarm/goal_loop.json
    ```
  - **If Concluded `ALREADY OPTIMAL` (Zero Code Changes Needed):** Explicitly state that the repository is already SOTA/market-ready and that running `/invoke-swarm` is unnecessary (or suggest `/triad-audit` if the user wants a standalone security/rigor verification).
