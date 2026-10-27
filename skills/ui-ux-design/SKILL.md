---
name: ui-ux-design
description: "Use when designing or redesigning a web interface such as a landing page, dashboard, documentation site, or interactive tool, and the user wants distinctive art directions and working HTML prototypes instead of a generic template look."
disable-model-invocation: false
triggers: [user, model]
---

# Empirical UI/UX Art Direction Dealer, 3-Prototype Builder & 3-Viewport Inspector (`/ui-ux-design`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

Use this skill during **initial product discovery & planning** (`/product-discovery` Wave 2, after `/coop-brainstorm` and before `/invoke-swarm` Epoch 1) or **standalone** whenever the user wants award-level, anti-slop UI/UX art direction and **three self-contained, interactive single-file HTML/CSS/JS prototypes** verified in a real headless browser across Desktop (`1440x900`), Tablet (`768x1024`), and Mobile (`390x844`).

---

## 0. Prerequisite: Existing-UI Sufficiency Gate (When Run on an Existing Repository)

If the repository already has an implemented UI (`src/`, `index.html`, etc.):
1. Inspect the existing UI at `1440,768,390` and run `scripts/web_ui_validator.py --screenshots-dir .swarm/blueprint/ui_proposals/screenshots`.
2. Score the existing UI (`1-10`) using the **14-Pass Visual Rubric + Hard Caps** (in [`/visual-ui-validator`](../visual-ui-validator/SKILL.md)).
3. If the existing UI already scores **$\ge 8.5 / 10$** with **`0 FAIL`** findings in `web_ui_validator.py`, report **`VERDICT: EXISTING UI ALREADY OPTIMAL`** in `.swarm/blueprint/ui_ux_proposals.md` and ask the user via `ask_question` whether to **keep their existing UI as-is (Recommended)** or still deal and generate 3 alternative redesign prototypes.

---

## Step 1: Surface Mode Classification (`Persuade` | `Operate` | `Read` | `Experience`) & Design Dials

Before writing a single line of CSS or picking colors, classify the surface by **what visitor success looks like** (`impeccable`) and set the **3 Design Dials** (`ui-ux-pro-max`):

| Surface Mode (`--mode`) | Visitor Success & Primary Surfaces | Ambition & Craft Register | Recommended Dials (`--variance` / `--motion` / `--density`) |
| :--- | :--- | :--- | :--- |
| **`persuade`** | **Visitor decides and acts.** Landing pages, product launches, campaigns, pricing pages. | Bold point of view, expressive scale (`>= 3.5x` headline-to-body ratio), non-repeating section archetypes, live interactive product proof. | Variance `6-9` · Motion `6-8` · Density `3-5` |
| **`operate`** | **Visitor completes high-frequency tasks.** Dashboards, IDEs, studios, telemetry consoles, admin & settings screens. | Scanability, keyboard efficiency, quiet `1px` borders or `1`-step tone shifts, `tabular-nums`, color budget $\le 5\%$ spent strictly on primary data series and status deltas. | Variance `3-7` · Motion `2-5` · Density `7-10` |
| **`read`** | **Visitor comprehends complex material.** Documentation, research monographs, technical manuals, notebooks. | Authoritative typographic hierarchy, `55-70ch` reading measure, inline interactive figures/code runners, zero extraneous chrome. | Variance `2-6` · Motion `2-4` · Density `4-6` |
| **`experience`** | **Visitor manipulates the artifact directly.** 3D viewers, spatial canvases, node editors, shader labs, interactive portfolios. | Artifact occupies $\ge 65\%$ of first viewport; direct manipulation leads from frame 1; perimeter HUD docks recede. | Variance `7-10` · Motion `6-9` · Density `4-7` |

---

## Step 2: Subject Inventory (8–12 Unique Facts), "The Idea Sentence" & "One Live Thing" (`taste-skill`)

Models default to generic templates when they design from a category label instead of the subject's own material. Before building, write down in your working notes (and in `.swarm/blueprint/ui_ux_proposals.md`):

1. **Subject Inventory (8–12 Specific Domain Facts):**
   - Extract 8–12 concrete truths that belong to *this specific project* and no generic competitor: its exact engine/model names, real CLI flags or API endpoints, actual benchmark numbers and units (`ms`, `tok/s`, `GB`, `pLDDT`), architectural constraints turned into strengths, input formats, and observable output artifacts.
2. **"The Idea Sentence" & The Competitor Swap Test:**
   - Complete this exact sentence from your Subject Inventory:
     > *"On this surface, **[specific material/artifact from the Subject Inventory]** becomes **[the compositional device of the dealt direction]**."*
   - **Competitor Swap Test:** Substitute a generic competitor's name into the sentence. If the sentence still works unchanged, the idea is a category cliché — rewrite it using a specific mechanism, metric, or artifact from the Subject Inventory.
3. **"One Live Thing" (Mandatory Stateful Interactive Device):**
   - Define the one high-leverage interactive mechanism on the surface that proves the product's claim (e.g., a live parameter workbench, an interactive telemetry cross-filter, an inline reactive simulation cell, or a calibrated tolerance comparator).
   - **Rules:** It must use realistic domain data, mutate real client-side state in JavaScript, re-render the DOM/`<svg>`/`<canvas>`, work via keyboard and at `390px` mobile width (`>= 44px` hit targets), and never block reading.

---

## Step 3: Deal 3 Empirical Art Directions via `ui_direction_dealer.py`

Never invent 3 generic LLM styles (`"Dark Mode"`, `"Light Minimal"`, `"Glassmorphism"`). Instead, run `scripts/ui_direction_dealer.py` to deal **3 distinct, non-overlapping, empirically grounded Art Directions** from its 18-direction library and compute the exact CSS Custom Property token tables for your mode and dials:

```bash
python3 "$AGENT_SWARM_HOME/scripts/ui_direction_dealer.py" \
  --mode <persuade|operate|read|experience> \
  --query "<product type, domain, and style keywords>" \
  --deal 3 \
  --variance <1-10> --motion <1-10> --density <1-10>
```

Each dealt direction supplies:
- **`id` & `name`** + **`composition_philosophy`**
- **`hero_blueprint`** + **`section_blueprints`** (ordered list of non-repeating layout archetypes such as `asymmetric-workbench-split`, `telemetry-ledger-band`, `specimen-comparison-matrix`, `kpi-strip-chart-rail`, `framed-sheet-header`, `annotated-code-walkthrough`)
- **`typography_system`** (`display_face`, `body_face`, `mono_face`, `@import` URL, `headline_to_body_ratio`, `display_tracking`, `display_leading`, `measure`)
- **`color_system`** (`ground`, `surface`, `elevated_surface`, `ink`, `muted_ink`, `primary_accent`, `border`, `selection_bg`, `selection_fg`, `semantic` tokens — strictly free of unrequested AI purple `#6366f1` and Assistant cream+terracotta)
- **`signature_motion`** + **`dial_tokens`** (`--space-*`, `--radius-*`, `--duration-*`, `--ease-*`, `--font-*`)

---

## Step 4: Build 3 Complete Prototypes Applying the Craft Floor & Browser Surfaces (`impeccable` + `taste-skill`)

Generate **three complete, self-contained single-file HTML/CSS/JS prototypes** (sequentially or via 3 parallel UI Designer sub-agents):
- `.swarm/blueprint/ui_proposals/template_1_<slug>.html` *(adopting Dealt Direction 1)*
- `.swarm/blueprint/ui_proposals/template_2_<slug>.html` *(adopting Dealt Direction 2)*
- `.swarm/blueprint/ui_proposals/template_3_<slug>.html` *(adopting Dealt Direction 3)*

Every prototype **MUST** enforce the **Craft Floor & Browser Surfaces**:
1. **Paste & Use the Dealt `:root` Token Block:** Reference `var(--bg-ground)`, `var(--bg-surface)`, `var(--text-ink)`, `var(--accent-primary)`, `var(--space-*)`, `var(--font-*)` throughout.
2. **Browser Surfaces (Never Ship Browser Defaults):**
   - Custom text selection: `::selection { background: var(--selection-bg); color: var(--selection-fg); }`
   - Keyboard focus ring: `:focus-visible { outline: 2px solid var(--accent-primary); outline-offset: 2px; }`
   - Tabular numerals: `font-variant-numeric: tabular-nums` on every `<table>`, metric, counter, timestamp, and axis label.
   - Custom thin scrollbars: `* { scrollbar-width: thin; scrollbar-color: var(--border-subtle) var(--bg-ground); }`
   - Reduced-motion safety: `@media (prefers-reduced-motion: reduce)` must leave 100% of text and controls at `opacity: 1; transform: none`.
3. **Strict Headline & Frame Geometry:**
   - Every `h1`–`h3` in `persuade`/`experience` mode must fit in **$\le 2$ lines** at `1440px`, `768px`, and `390px` (keep headlines concise: 4–8 words / $\le 36$ chars with `text-wrap: balance` and responsive `clamp()`).
   - Primary `<h1>` must be visible (`opacity: 1`), uncovered, and inside the first viewport at all 3 widths.
   - Equal outer left/right page margins at every breakpoint (`margin-inline: auto`), zero horizontal overflow (`scrollWidth <= innerWidth`), and responsive mobile layout (`@media (max-width: 800px)` collapses multi-column splits and sidebars cleanly).
4. **Zero AI Slop Tells:**
   - **NO** uppercase/pill eyebrow kickers directly above `h1`/`h2` headings (`slop-eyebrow`).
   - **NO** `-webkit-background-clip: text` gradient text (`slop-gradient-text`).
   - **NO** `border-left-width > 1px` side-stripe callouts (`slop-side-stripe`).
   - **NO** 3-up identical icon-topped card rows (`slop-icon-cards`), decorative `01 / 02 / 03` section numbers (`slop-numbering`), `1px` border + wide blur ghost cards (`slop-ghost-card`), or monospace prose (`slop-mono-prose`).
   - **NO** `"Lorem ipsum"`, `TODO`, `FIXME`, `[TBD]`, `"Coming soon"`, `alert("TODO")`, or no-op event listeners.

---

## Step 5: 3-Viewport Real-Browser Gate (`web_ui_validator.py`) + Unanchored Dual-Agent Critique

1. **Run the 3-Viewport + Reduced-Motion Real-Browser Inspector:**
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/web_ui_validator.py" \
     .swarm/blueprint/ui_proposals/template_1_*.html \
     .swarm/blueprint/ui_proposals/template_2_*.html \
     .swarm/blueprint/ui_proposals/template_3_*.html \
     --mode <persuade|operate|read|experience> \
     --screenshots-dir .swarm/blueprint/ui_proposals/screenshots
   ```
2. **Zero-`FAIL` Gate & Unanchored Visual Critique ([`/visual-ui-validator`](../visual-ui-validator/SKILL.md)):**
   - Inspect the rendered screenshots (`*-desktop-1440-fold.png`, `*-tablet-768-fold.png`, `*-mobile-390-fold.png`) using `view_file` and apply the **14-Pass Visual Rubric + Hard Caps**.
   - Any `FAIL` from `web_ui_validator.py` caps the template's score at **`6.0/10`** and blocks completion. Fix every `FAIL` and address or explicitly defend every `WARN` in 1 sentence until all 3 templates return `"status": "PASS"` (`0 FAIL`).

---

## Step 6: Present Comparison & Persist Chosen Direction (`DESIGN.md` + `.swarm/surfaces/<slug>.md`)

1. Write the comparative critique, Subject Inventory, Idea Sentence, Live Thing specification, and 3-viewport scores to `.swarm/blueprint/ui_ux_proposals.md`.
2. Present clickable markdown links to all 3 validated `.html` templates (`[template_1_*.html](file:///...)`, `[template_2_*.html](file:///...)`, `[template_3_*.html](file:///...)`) and ask the user via `ask_question` to choose their preferred direction (or hybrid combination).
3. Persist the chosen direction into `DESIGN.md` and `.swarm/surfaces/<slug>.md` so all `/invoke-swarm` worker agents inherit the exact tokens, blueprints, and Craft Floor contract:
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/ui_direction_dealer.py" \
     --mode <persuade|operate|read|experience> \
     --query "<product query>" \
     --direction <chosen_direction_id> \
     --variance <1-10> --motion <1-10> --density <1-10> \
     --persist --output-dir . -p "<Project Name>" --page <slug>
   ```
