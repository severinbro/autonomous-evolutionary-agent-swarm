---
name: visual-ui-validator
description: "Use when checking a web page or HTML prototype for broken layout, responsiveness, accessibility, runtime errors, or generic AI-looking design, especially before showing UI to the user or accepting a UI change."
disable-model-invocation: false
triggers: [user, model]
---

# Real-Browser Inspector & Unanchored 14-Pass Visual UI Validator (`/visual-ui-validator`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

Use this skill **standalone**, inside **`/ui-ux-design`** (to verify all 3 generated single-file HTML/CSS/JS templates across desktop, tablet, mobile, and reduced-motion viewports), or inside **`/discriminator-gate`** whenever a sub-agent implements or modifies HTML/CSS/JS user interfaces or interactive visualizations.

---

## 1. Automated Multi-Viewport Browser Execution (`scripts/web_ui_validator.py`)

Run the real-browser inspector against one or more `.html` files or URLs:

```bash
# Validate the 3 single-file HTML/CSS/JS templates from /ui-ux-design across 1440, 768, 390 + reduced-motion:
python3 "$AGENT_SWARM_HOME/scripts/web_ui_validator.py" \
  .swarm/blueprint/ui_proposals/template_1_*.html \
  .swarm/blueprint/ui_proposals/template_2_*.html \
  .swarm/blueprint/ui_proposals/template_3_*.html \
  --mode persuade \
  --screenshots-dir .swarm/blueprint/ui_proposals/screenshots \
  --json

# Validate an operational workbench / dashboard (dense multi-panel mode):
python3 "$AGENT_SWARM_HOME/scripts/web_ui_validator.py" \
  ./dist/index.html --mode operate --allow-external --screenshots-dir .swarm/screenshots --json

# Quick desktop-only pass (1440x900) or with an explicit rule opt-out:
python3 "$AGENT_SWARM_HOME/scripts/web_ui_validator.py" \
  ./dist/index.html --quick --allow slop-ghost-card,slop-mono-prose --json
```

### CLI Flags
- `--mode {persuade,operate,read,experience,auto}`: Surface mode (`auto` infers `operate` for dense apps/workbenches, `read` for docs/prose, `persuade` for landing/product pages).
- `--widths 1440,768,390`: Comma-separated viewport widths (`1440x900`, `768x1024`, `390x844` by default).
- `--quick`: Desktop (`1440x900`) only.
- `--screenshots-dir <dir>` (alias `--screenshot-dir`): Writes `<stem>-desktop-1440-fold.png`, `<stem>-tablet-768-fold.png`, and `<stem>-mobile-390-fold.png`. The reduced-motion pass is checked by the `reduced-motion-hidden` rule, without a screenshot.
- `--allow <rule1,rule2>`: Opt out of specific rule IDs when a direction intentionally breaks a convention.
- `--allow-external`: Allow external `<script src="...">` and `<link rel="stylesheet">` bundles.
- `--json`: Emit structured JSON report with per-file `summary`, `hard_cap`, `errors`, `warnings`, `findings`, and `screenshots`.

---

## 2. Deterministic Geometric, Runtime & Anti-Slop Rules (`FAIL` vs. `WARN`)

`web_ui_validator.py` probes each viewport at `1440x900`, `768x1024`, and `390x844`, plus a fourth pass at `1440x900` with `prefers-reduced-motion: reduce`:

| Rule ID | Severity | What It Checks |
| :--- | :--- | :--- |
| `js-syntax-error` | **`FAIL`** | Runs `node --check` on every inline `<script>` block before launching Chromium. |
| `runtime-page-error` | **`FAIL`** | Any uncaught `pageerror` exception during render or interaction. |
| `console-error` | **`FAIL`** | Any `console.error` emitted during render. |
| `placeholder-text` | **`FAIL`** | Any `"Lorem ipsum"`, `[TBD]`, `[TODO]`, or `"Coming soon"` placeholder text, or empty event handlers (`() => {}`, `alert("TODO")`). |
| `zero-size-visual` | **`FAIL`** | Any `<canvas>` or `<svg>` container with `width == 0` or `height == 0`. |
| `horizontal-overflow` | **`FAIL`** | `documentElement.scrollWidth > window.innerWidth + 2` at `1440`, `768`, or `390`. |
| `headline-lines` | **`FAIL`** | Any `<h1>`–`<h3>` wraps past `2` lines (`persuade` and `experience` modes). |
| `late-title` | **`FAIL`** | Primary `<h1>` top edge is below `85%` of viewport height (`h1.top > vh * 0.85`). |
| `off-centre-frame` | **`FAIL`** | Main frame (`[data-frame]`, `<main>`, or first `<section>`) is off-centre by $> 24\text{px}$ when narrower than $92\%$ of viewport (skipped in `operate` mode). |
| `empty-screens` | **`FAIL`** | `> 1` consecutive $80\text{vh}$ scroll steps below the fold with zero visible content (`persuade`/`experience` modes). |
| `covered-text` | **`FAIL`** | `document.elementFromPoint(cx, cy)` on `h1, h2, h3, p, a, button` hits an unrelated overlapping element (`z-index`/sticky overlap bug). |
| `reduced-motion-hidden` | **`FAIL`** | Under `prefers-reduced-motion: reduce`, any `h1`, `h2`, or `main` remains stuck at `opacity < 0.1` or `visibility: hidden`. |
| `slop-eyebrow` | **`FAIL`** | Pill badge (`border-radius >= 8px` + background/border) directly above `<h1>`/`<h2>` with uppercase `letter-spacing >= 1.5px`. |
| `slop-gradient-text` | **`FAIL`** | `-webkit-background-clip: text` with `color: transparent` on `<h1>`/`<h2>`/`<h3>`. |
| `slop-side-stripe` | **`FAIL`** | Accent side-stripe card (`border-left-width >= 3px` while `border-top-width <= 1px`). |
| `slop-ai-palette` | `WARN` | Default indigo/violet (`#6366f1`, `#8b5cf6`, `#a855f7`) paired with cyan/teal (`#06b6d4`, `#14b8a6`, `#22d3ee`). |
| `slop-icon-cards` | `WARN` | Row of $\ge 3$ equal-height sibling cards each starting with an icon/SVG badge. |
| `slop-ghost-card` | `WARN` | Translucent card (`0 < bg.alpha <= 0.12`) with faint $1\text{px}$ border (`alpha <= 0.2`) and `border-radius >= 8px`. |
| `slop-numbering` | `WARN` | Decorative `01 / 02 / 03` ordinal indices on cards or headings. |
| `slop-mono-prose` | `WARN` | Monospace font applied to body prose `<p>` ($\ge 60$ chars) rather than numbers/code/tabular readouts. |
| `body-size-small` | `WARN` | Computed `<body>` font-size $< 14\text{px}$ (or $< 15\text{px}$ in `persuade`/`read` mode). |
| `browser-surfaces-default` | `WARN` | Missing `color-scheme` or `::selection` styling on the document. |
| `low-contrast` | `WARN` | Sampled visible text elements failing WCAG AA ($< 4.5:1$ normal text or $< 3.0:1$ large text $\ge 24\text{px}$). |

---

## 3. Unanchored Dual-Agent Critique & 14-Pass Visual Screenshot Rubric

To prevent **confirmation bias** (where an evaluator sees a green script output and rubber-stamps a mediocre layout, or only looks for what the script flagged), enforce the **Unanchored Dual-Agent Critique Protocol**:

### Step A: Unanchored Visual & Heuristic Review (Run BEFORE Reading `web_ui_validator.py` JSON)
Inspect the rendered screenshots (`*-desktop-1440-fold.png`, `*-tablet-768-fold.png`, `*-mobile-390-fold.png`) via `view_file` and score **Assessment A** *before* reading the `web_ui_validator.py` JSON output:

1. **The 14 Visual Passes (`taste-skill`):**
   - **Pass 1 (5-Second Title Pass):** Within 5 seconds of viewing `*-desktop-1440-fold.png`, is it obvious what this product is, who it is for, and why it differs?
   - **Pass 2 (Subject Presence):** Does the real subject (live workbench, artifact, interactive preview) occupy $\ge 45\%$ of the first viewport on Persuade/Experience surfaces, or is it buried under marketing chrome?
   - **Pass 3 (Focal Point & Squint Test):** Squinting at `*-desktop-1440-fold.png`, is there one clear primary focal point, a secondary anchor, and quiet breathing room?
   - **Pass 4 (Competitor Swap Test):** If you swapped the brand name and accent color with a generic competitor, would the layout still be unmistakably specific to this product's Idea Sentence?
   - **Pass 5 (One Live Thing):** Is the primary interactive state machine (command palette, filterable telemetry, scrubbable timeline, live inspector) immediately operable and responsive?
   - **Pass 6 (Typography & Hierarchy):** Are display headlines tight (`<= 2` lines), prose measures comfortable (`55ch-70ch`), and numeric tables `tabular-nums`?
   - **Pass 7 (Color & Atmospheric Polarity):** Are surfaces tinted toward a coherent hue rather than flat `#000`/`#fff` or default AI indigo/cyan gradients?
   - **Pass 8 (Rhythm & Section Pacing):** Does each scroll section change density/tempo (dense $\rightarrow$ open $\rightarrow$ full-bleed) rather than repeating uniform 3-column card rows?
   - **Pass 9 (Card Necessity):** Are cards used only when items have heterogeneous actions or user-arranged state, using Hairline Grid (`gap: 1px`), Index List, or Open Prose elsewhere?
   - **Pass 10 (Edge, Alignment & Frame Centering):** Are left edges shared, frames centred within $\pm 24\text{px}$, and badges/labels aligned on a common baseline?
   - **Pass 11 (Scroll & Choreographed Motion):** Are there zero dead scroll screens and zero hidden elements when `prefers-reduced-motion: reduce` is active (the validator's `reduced-motion-hidden` result)?
   - **Pass 12 (Tablet `768px` Adaptation):** Does `*-tablet-768-fold.png` adapt multi-column grids gracefully without orphaned single cards or crushed sidebars?
   - **Pass 13 (Mobile `390px` Adaptation):** Does `*-mobile-390-fold.png` preserve tap targets ($\ge 44\times 44\text{px}$), readable hierarchy, and zero horizontal overflow?
   - **Pass 14 (Slop Tell Sweep):** Are there zero eyebrow pills, gradient-clipped headings, left-border stripe cards, ghost glass cards, or `01 / 02 / 03` decorative numbers?
2. **Nielsen's 10 Usability Heuristics (`0-4` Severity Scale):**
   - Rate Visibility of System Status, Match Between System & Real World, User Control & Freedom, Consistency & Standards, Error Prevention, Recognition Rather Than Recall, Flexibility & Efficiency of Use, Aesthetic & Minimalist Design, Error Recovery, and Help/Documentation (`0` = no issue, `1` = cosmetic, `2` = minor, `3` = major usability defect, `4` = usability catastrophe).
3. **Cognitive Load Check:**
   - Verify $\le 4$ distinct component groups visible without scrolling and $\le 4$ working-memory chunks required to complete the primary action.
4. **Persona Red-Flag Walk:**
   - **Alex (Power User):** Can Alex operate key actions rapidly via keyboard/command bar without modal traps?
   - **Jordan (First-Timer):** Does Jordan immediately understand the primary action without jargon overload?
   - **Sam (Accessibility / Reduced Motion / Low Vision):** Does Sam get full content visibility under `prefers-reduced-motion`, WCAG AA contrast, and `:focus-visible` rings?
   - **Riley (Stress Tester):** What happens when Riley enters long strings, rapid clicks, zero-results filters, or narrow `390px` viewports?

### Step B: Synthesize with `web_ui_validator.py` & Apply Hard Caps
Now inspect **Assessment B** (the deterministic JSON output of `web_ui_validator.py`) and apply these mandatory **Hard Caps** to the final UI score (`1-10`):

| Trigger Condition | Hard Cap Applied |
| :--- | :--- |
| Any **`FAIL`** rule triggered in `web_ui_validator.py` (`errors > 0`) | **Overall Score capped at `6.0 / 10`** (Automatic Gate Failure) |
| Visible AI slop tells (`slop-*`) or `> 1` empty scroll screens | **Visual Craft capped at `6.5 / 10`** |
| 5-Second Title Pass fails OR `covered-text` / Nielsen Severity $\ge 3$ defect | **Usability capped at `6.0 / 10`** |
| Competitor Swap Test fails (generic SaaS template) | **Creativity capped at `6.0 / 10`** |
| Missing or non-functional **One Live Thing** | **Creativity capped at `7.5 / 10`** |

---

## 4. Failure Feedback Loop

If `web_ui_validator.py` exits with code `1` (`FAIL`) or the post-cap score is `< 8.0 / 10`:
- Extract the exact `errors` and `warnings` arrays from `web_ui_validator.py` along with the failed passes from the 14-Pass Visual Rubric.
- In `/ui-ux-design`, fix the template immediately and re-run `web_ui_validator.py` until all 3 templates achieve `0 FAIL` and $\ge 8.0 / 10$ before presenting links to the user.
- In `/discriminator-gate`, put the `web_ui_validator.py` command in the task's `verification_commands` so any `FAIL` becomes a `BLOCKING_FAIL` in `--audit-task`, and list the exact rule IDs, viewport widths, and coordinates in the worker's fix prompt.
