---
name: product-discovery
description: "Use when starting a new product or a major new direction and the user wants research, market and commercial analysis, a locked plan, and UI prototypes before implementation, or asks whether an existing project needs changes at all."
disable-model-invocation: false
triggers: [user, model]
---

# Phase A Master Orchestrator: Discovery, Market Analysis & Elephant-Goldfish Planning (`/product-discovery`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

Use `/product-discovery` to run an **initial end-to-end discovery, potential analysis, and Elephant-Goldfish product planning pass (Phase A)** before launching `/invoke-swarm` (Phase B). It crawls the web, literature, and market landscape in parallel, then pauses at interactive human checkpoints using the **active harness's native polling tool** (`ask_question` in Antigravity, `AskUserQuestion` in Claude Code, `request_user_input` in Codex CLI; see `$AGENT_SWARM_HOME/references/harness-polling.md`).

---

## Core Mandate: Verified, Zero-Open-Question Product Plans

Every `/product-discovery` run enforces five rules:

1. **NO `[TBD]`, `TODO`, OR `Lorem ipsum` PLACEHOLDERS** in `tech_research_report.md`, `market_research_report.md`, `commercial_strategy_report.md`, `brainstorm_blueprint.md`, `docs/designs/<product>.md`, or `ui_proposals/*.html`.
2. **POLL VIA HARNESS TOOL — NEVER INSIDE PLAN/DESIGN FILES:** Every Elephant question, scope choice, UI pick, Goldfish resolution, and command confirmation uses the harness polling tool (`ask_question` / `AskUserQuestion` / `request_user_input`) with `(Recommended)` first. `goal_loop.py --import-design` and `--verify-blueprint` fail if any `## Open Questions` heading or `[?]` marker appears in a blueprint or design file.
3. **VERTICAL-SLICE OUTCOME PARTICIPATION & ENTRYPOINT WIRING:** Every task in `docs/designs/<product>.md` names `Files`, `Depends on`, `Changes`, `Called by` / `Symbols` where wired, and a failing-first `Verification` command; `### Goal` names the end-to-end `Outcome` command.
4. **TASKS COME FROM THE REVIEWED DESIGN:** Checkpoint 1 writes product notes and `--init-goal` only. Tasks come exclusively from `goal_loop.py --import-design docs/designs/<product>.md` after `/design-draft` and `/goldfish-review`.
5. **NO DEAD UI CONTROLS IN WAVE 2 PROTOTYPES:** Validated across `1440,768,390` + `prefers-reduced-motion` via `scripts/web_ui_validator.py` (`0 FAIL`).

---

## Calling Modes

| Invocation / Command | What It Runs | Composable Skills Used |
| :--- | :--- | :--- |
| **`/product-discovery`** *(Default)* | **Wave 1** (`/tech-research` + `/market-research` + `/commercial-strategy`) → **Checkpoint 1** (`/coop-brainstorm` + 6 Goldfish lenses) → **Wave 2** (`/ui-ux-design`) → **Design** (`/design-draft` → `/goldfish-review` → `--import-design`) → `--verify-blueprint`. | `tech-research`, `market-research`, `commercial-strategy`, `coop-brainstorm`, `ui-ux-design`, `design-draft`, `goldfish-review`, `goal-loop` |
| **`/product-discovery no-ui`** *(Backend / CLI / SDK)* | **Wave 1** → **Checkpoint 1** (`/coop-brainstorm`) → **Design** (`/design-draft` → `/goldfish-review` → `--import-design`) → `--verify-blueprint`. | `tech-research`, `market-research`, `commercial-strategy`, `coop-brainstorm`, `design-draft`, `goldfish-review`, `goal-loop` |
| **`/product-discovery tech-only`** *(Academic / Internal)* | `/tech-research` + optional `/paper-to-code` → **Checkpoint 1** → **Wave 2** → **Design** → `--verify-blueprint`. | `tech-research`, `paper-to-code`, `coop-brainstorm`, `ui-ux-design`, `design-draft`, `goldfish-review`, `goal-loop` |
| **`/product-discovery market-only`** *(Market Positioning)* | `/market-research` + `/commercial-strategy` in parallel → `.swarm/blueprint/market_dashboard.html`. | `market-research`, `commercial-strategy` |

---

## Step-by-Step Execution Protocol

### Step 0: Initialize Directories
```bash
mkdir -p .swarm/blueprint/ui_proposals .swarm/sota docs/designs
```

### Wave 1: Parallel Web, Literature & Market Potential Scouting
Spawn Wave 1 subagents concurrently:
1. **Technical & Literature Research ([`/tech-research`](../tech-research/SKILL.md)):** Zotero (`scripts/zotero_tool.py`), OpenAlex/arXiv/PubMed, and Web/OSS SOTA crawl → `.swarm/blueprint/tech_research_report.md` & `.swarm/sota/sota_knowledge_base.md`.
2. **Market & Switch-Trigger Intelligence ([`/market-research`](../market-research/SKILL.md)) *(skip in `tech-only`)*:** `competitor_teardown_scout`, `voice_of_customer_miner`, `tam_icp_gtm_analyst` → `.swarm/blueprint/market_research_report.md` & `market_data.json`.
3. **Open-Core & B2B Commercial Strategy ([`/commercial-strategy`](../commercial-strategy/SKILL.md)) *(skip in `tech-only`)*:** `pricing_monetization_strategist` + `moat_and_risk_skeptic` → `.swarm/blueprint/commercial_strategy_report.md`, plus:
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/market_dashboard.py" --data .swarm/blueprint/market_data.json --out .swarm/blueprint/market_dashboard.html
   python3 "$AGENT_SWARM_HOME/scripts/web_ui_validator.py" .swarm/blueprint/market_dashboard.html
   ```

### Checkpoint 1: Elephant Grilling, Sufficiency Gate & Six-Lens Critique ([`/coop-brainstorm`](../coop-brainstorm/SKILL.md))
1. Present Wave 1 links, the **Existing-Repo Sufficiency Table** (`OPTIMAL` vs `UPGRADE_NEEDED`), `HIGH` Net-ROI opportunities, Open-Core/B2B scope tiers, `Option 0` vs competing architectures, and the merged findings from the **six read-only Goldfish lenses** on `.swarm/blueprint/concept.md`.
2. **Poll via Harness Polling Tool (`ask_question` / `AskUserQuestion` / `request_user_input`):**
   - If all dimensions are `OPTIMAL` with zero `HIGH` Net-ROI gaps, place `(Recommended) Keep Project As-Is — Already Optimal (Skip UI & Swarm)` first.
   - Otherwise poll scope, architecture, and whether to run Wave 2 UI prototypes, with `(Recommended)` first.
3. Persist `.swarm/blueprint/brainstorm_blueprint.md` (zero open questions) and initialise the root goal only:
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --init-goal "<Locked Product Goal>" --outcome-cmd "<End-to-End Verification Command>" --entrypoints <entrypoint_files>
   ```

### Wave 2 & Checkpoint 2: 3-Template UI/UX Prototype Generation ([`/ui-ux-design`](../ui-ux-design/SKILL.md))
*(Skip in `no-ui`, `market-only`, or if existing UI passed `web_ui_validator.py` at Checkpoint 1.)*
1. Deal 3 directions via `scripts/ui_direction_dealer.py --mode <mode> --query "<domain>" --deal 3 --variance <1-10> --motion <1-10> --density <1-10>`.
2. Define Subject Inventory, Idea Sentence, and One Live Thing; build `.swarm/blueprint/ui_proposals/template_1..3_<slug>.html`.
3. Validate across `1440,768,390` + `prefers-reduced-motion`:
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/web_ui_validator.py" .swarm/blueprint/ui_proposals/template_1_*.html .swarm/blueprint/ui_proposals/template_2_*.html .swarm/blueprint/ui_proposals/template_3_*.html --mode <mode> --screenshots-dir .swarm/blueprint/ui_proposals/screenshots --json
   ```
4. Poll user selection via the **harness polling tool** (`ask_question` / `AskUserQuestion` / `request_user_input`) and persist tokens via `ui_direction_dealer.py ... --persist --output-dir . -p "<Project Name>" --page main`.

### Design: Draft, Goldfish Review & Confirmed Import ([`/design-draft`](../design-draft/SKILL.md), [`/goldfish-review`](../goldfish-review/SKILL.md))
*(Skip if `ALREADY OPTIMAL` or `market-only`.)*
1. Run `/design-draft` to draft `docs/designs/<product>.md` in 4 polled section groups (recording settled choices in `## Resolved Decisions`, never `## Open Questions`).
2. Run `/goldfish-review docs/designs/<product>.md` (polling stage confirmation and resolution via the harness polling tool).
3. Run dry run, show every command the gate will execute, poll confirmation via the harness polling tool, then import:
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd . --import-design docs/designs/<product>.md --dry-run
   python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd . --import-design docs/designs/<product>.md
   ```

---

## Final Phase A Authenticity Gate & Handoff

```bash
python3 "$AGENT_SWARM_HOME/scripts/goal_loop.py" --cwd . --verify-blueprint
```
Fix any placeholder, open-question violation, invalid HTML prototype, or import error until `"status": "PASS"`, disclose any skipped stages (`ponytail` transparency), and present the Phase B launch command:
```text
/invoke-swarm Implement docs/designs/<product>.md (tasks in .swarm/goal_loop.json)
```
