#!/usr/bin/env python3
"""UI/UX Empirical Art Direction Dealer & Design System Generator (`ui_direction_dealer.py`).

Zero-external-dependency Python 3 CLI utility combining:
  1. `leonxlnx/taste-skill` (`draw.mjs`): Empirical art directions distilled from 247 curated
     gallery sites & 23 production app screens, non-repeating section blueprints, Subject Inventory,
     "The Idea Sentence" (Competitor Swap Test), and "One Live Thing".
  2. `pbakaus/impeccable`: Surface Modes (`persuade`, `operate`, `read`, `experience`),
     Craft Floor rules, and Browser Surfaces (`::selection`, custom scrollbars, `:focus-visible`,
     `tabular-nums`).
  3. `nextlevelbuilder/ui-ux-pro-max-skill`: BM25 lexical scoring + 3 Design Dials
     (`--variance 1-10`, `--motion 1-10`, `--density 1-10`) that compute exact CSS Custom Property
     token tables (`--space-*`, `--radius-*`, `--duration-*`, `--ease-*`, `--font-*`, `--color-*`)
     and persist the 3-tier design context (`DESIGN.md` + `.swarm/surfaces/<page>.md`).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SURFACE_MODES: dict[str, dict[str, Any]] = {
    "persuade": {
        "name": "Persuade (Landing / Marketing / Campaign / Launch)",
        "goal": "The visitor decides and acts; design is the proof. Earn attention and action through an unmistakable point of view and a live product artifact.",
        "typography_floor": "Body >= 16px (16-20px), measure 45-75ch, headlines <= 2 lines at every viewport (1440, 768, 390), headline-to-body ratio >= 3.2x.",
        "layout_rules": [
            "Equal outer left/right frame margins at every breakpoint; asymmetry belongs inside the grid, never in the outer frame.",
            "Every section uses a distinct layout archetype from its neighbors (zero consecutive identical layouts, zero 3-up icon-topped card rows).",
            "No eyebrows/kickers above headings, no decorative 01/02/03 numbering, no gradient text, no side-stripe borders (>1px), no monospace prose.",
        ],
    },
    "operate": {
        "name": "Operate (Dashboard / Workspace / Studio / DevTool / App UI)",
        "goal": "The visitor completes high-frequency domain work with zero friction. Scanability, keyboard efficiency, data density, and state clarity outrank ornament.",
        "typography_floor": "Data/table copy 13-14px, body 14-15px, screen title h1 18-28px, KPI numerals 20-36px with mandatory `font-variant-numeric: tabular-nums`.",
        "layout_rules": [
            "Quiet 1px structural borders (1.1-1.4:1 contrast against surface) or 1-step surface tone shifts; zero floating heavy box-shadows on resting panels.",
            "Right-align numeric columns and headers; enforce `tabular-nums` on all metrics, timestamps, counters, and tables.",
            "Color budget <= 5% of screen area: chrome stays neutral; spend chroma strictly on the primary data series and semantic status deltas.",
            "Mobile (<600px) collapses sidebars into a compact top/bottom bar so the workspace canvas retains 100% width.",
        ],
    },
    "read": {
        "name": "Read (Documentation / Editorial / Research Report / Reference Manual)",
        "goal": "The visitor comprehends complex material effortlessly. Typographic rhythm, scannable hierarchy, inline interactive figures, and zero extraneous cognitive load.",
        "typography_floor": "Body 17-19px, line-height 1.55-1.7, strict 55-70ch measure, clear heading weight/scale contrast, zero orphan headings.",
        "layout_rules": [
            "Single primary reading column anchored to a consistent left axis with optional margin notes/TOC rail (<= 4 sibling items per group).",
            "Code blocks, equations, and interactive figures sit flush with the reading column or bleed cleanly into the right margin.",
            "Zero popups, zero decorative card grids, zero floating glass chrome that obscures text.",
        ],
    },
    "experience": {
        "name": "Experience (Interactive Canvas / 3D Viewer / Spatial Lab / Portfolio Showcase)",
        "goal": "The visitor is inside the artifact itself from the first frame. Direct manipulation leads; HUD chrome recedes to quiet edges.",
        "typography_floor": "HUD controls 12-14px with `tabular-nums`, statement titles <= 2 lines, high-contrast overlay labels with solid or scrim backing.",
        "layout_rules": [
            "The live interactive canvas/artifact occupies >= 65% of the first viewport with immediate direct manipulation (scrub, inspect, rotate, filter).",
            "Floating HUD docks anchor cleanly to viewport margins without covering focal titles or canvas subjects.",
            "Under `prefers-reduced-motion: reduce`, all camera/scroll travel settles immediately into a readable, interactive state with zero hidden text.",
        ],
    },
}


# 18 empirically grounded art directions spanning Persuade, Experience, Operate, and Read modes
DIRECTIONS_LIBRARY: list[dict[str, Any]] = [
    # --- PERSUADE & EXPERIENCE DIRECTIONS (Distilled from taste-skill & impeccable) ---
    {
        "id": "product-performs",
        "name": "The Product Performs Live",
        "mode_affinity": ["persuade", "experience"],
        "variance_band": (5, 9),
        "keywords": ["saas", "ai", "developer", "tool", "studio", "code", "platform", "software", "gpu", "engine", "automation", "workflow", "cloud", "analytics"],
        "composition_philosophy": (
            "Instead of describing software with marketing cards, the page puts a live, working fragment "
            "of the product (`data-ui`) on stage at real size. The hero is an asymmetric split or full-bleed "
            "workbench where the visitor can toggle real inputs and watch output compute immediately."
        ),
        "hero_blueprint": (
            "12-column grid, 24px outer margins. Left 5 columns hold a <=2-line headline (clamp(2.5rem, 4.8vw, 4.5rem)), "
            "one plain-language supporting sentence (18px, max 52ch), and one solid primary action button (44px tall). "
            "Right 7 columns hold the live interactive product workbench (`[data-ui]`) cropped flush to the right margin."
        ),
        "section_blueprints": [
            {"role": "hero", "archetype": "asymmetric-workbench-split", "geometry": "5/7 column split; left statement + action, right live `[data-ui]` artifact with working controls."},
            {"role": "proof", "archetype": "telemetry-ledger-band", "geometry": "Full-width 4-column tabular metric ledger with real domain benchmarks and units (`tabular-nums`), separated by tone step."},
            {"role": "architecture", "archetype": "interactive-pipeline-trace", "geometry": "Sticky left narrative column (4 cols) paired with a 3-stage interactive SVG/DOM pipeline inspector (8 cols)."},
            {"role": "comparison", "archetype": "specimen-comparison-matrix", "geometry": "Unboxed high-contrast specification table comparing real latency/throughput/capabilities against baseline."},
            {"role": "cta-footer", "archetype": "monument-close", "geometry": "Inverted ground/ink full-bleed band with command-line or one-click launch action and full-width brand wordmark."},
        ],
        "typography_system": {
            "display_face": "Space Grotesk",
            "body_face": "Plus Jakarta Sans",
            "mono_face": "JetBrains Mono",
            "google_fonts_import": "@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Plus+Jakarta+Sans:wght@400;500;600&family=Space+Grotesk:wght@600;700&display=swap');",
            "headline_to_body_ratio": 3.8,
            "display_tracking": "-0.035em",
            "display_leading": "0.96",
            "body_size": "17px",
            "body_leading": "1.55",
            "measure": "62ch",
        },
        "color_system": {
            "theme": "dark",
            "ground": "#0B0F14",
            "surface": "#121820",
            "elevated_surface": "#1A222D",
            "ink": "#F1F5F9",
            "muted_ink": "#94A3B8",
            "primary_accent": "#10B981",
            "on_accent": "#042F2E",
            "border": "#1E293B",
            "selection_bg": "#10B981",
            "selection_fg": "#042F2E",
            "semantic": {"positive": "#10B981", "warning": "#F59E0B", "danger": "#EF4444", "info": "#0EA5E9"},
            "notes": "Obsidian carbon slate ground with signal emerald accent reserved strictly for the primary CTA and live execution state.",
        },
        "signature_motion": {
            "id": "instrument-settle",
            "name": "Instrument Reveal & Live Trace",
            "description": "Staggered 70ms section part arrival (heading -> copy -> live UI frame) with exponential ease-out (`cubic-bezier(0.22, 1, 0.36, 1)`) and real-time SVG path/bar transitions on user input.",
            "easing": "cubic-bezier(0.22, 1, 0.36, 1)",
            "duration": "420ms",
            "reduced_motion_fallback": "All text and UI frames render at `opacity: 1; transform: none` immediately; interactive state switches remain instant.",
        },
        "idea_prompt": "On this page, a live executable slice of the product's core engine becomes the hero illustration.",
        "live_thing_archetype": "Interactive input/parameter workbench where visitors switch real presets or adjust sliders and see live computed output, latency, and DOM/SVG telemetry update immediately.",
    },
    {
        "id": "quiet-instrument",
        "name": "Quiet Precision Instrument",
        "mode_affinity": ["persuade", "read", "operate"],
        "variance_band": (2, 7),
        "keywords": ["hardware", "audio", "science", "biotech", "medical", "climate", "engineering", "research", "industrial", "instrument", "security", "precision"],
        "composition_philosophy": (
            "Inspired by Dieter Rams, Teenage Engineering, and calibrated laboratory instruments. "
            "Warm low-chroma stone paper ground, razor-sharp typographic scale, technical schematics drawn in crisp SVG geometry, "
            "and tactile mechanical controls with zero decorative gradients."
        ),
        "hero_blueprint": (
            "Full-viewport calibrated frame with equal 28px margins. Top row anchors wordmark left and specification summary right. "
            "Main stage pairs a 2-line display title with an interactive calibrated schematic/instrument dial that responds to pointer/keyboard input."
        ),
        "section_blueprints": [
            {"role": "hero", "archetype": "calibrated-instrument-stage", "geometry": "6/6 split: left typographic specification and primary action; right interactive SVG instrument/schematic."},
            {"role": "specs", "archetype": "editorial-ledger", "geometry": "2-column asymmetrical specification ledger (3 cols category heading, 9 cols tabular parameter rows)."},
            {"role": "mechanism", "archetype": "full-bleed-artifact", "geometry": "Full-width dark slate contrast field holding an interactive cross-section diagram with selectable callout nodes."},
            {"role": "evidence", "archetype": "asymmetric-split", "geometry": "7/5 split: empirical benchmark chart on left, plain-language methodology and reproducible command on right."},
            {"role": "footer", "archetype": "colophon-close", "geometry": "Clean technical colophon with exact version, license, and full-width brand mark."},
        ],
        "typography_system": {
            "display_face": "Instrument Sans",
            "body_face": "Inter",
            "mono_face": "IBM Plex Mono",
            "google_fonts_import": "@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Instrument+Sans:wght@600;700&family=Inter:wght@400;500;600&display=swap');",
            "headline_to_body_ratio": 3.6,
            "display_tracking": "-0.03em",
            "display_leading": "0.98",
            "body_size": "16px",
            "body_leading": "1.55",
            "measure": "64ch",
        },
        "color_system": {
            "theme": "light",
            "ground": "#F3F2EE",
            "surface": "#EAE8E1",
            "elevated_surface": "#FFFFFF",
            "ink": "#141413",
            "muted_ink": "#575652",
            "primary_accent": "#D9381E",
            "on_accent": "#FFFFFF",
            "border": "#D6D3C9",
            "selection_bg": "#D9381E",
            "selection_fg": "#FFFFFF",
            "semantic": {"positive": "#15803D", "warning": "#B45309", "danger": "#B91C1C", "info": "#0369A1"},
            "notes": "Low-chroma anodized stone ground (#F3F2EE, saturation < 10%, avoiding yellow cream) with international Braun signal vermilion (#D9381E) on primary control only.",
        },
        "signature_motion": {
            "id": "detent-snap",
            "name": "Mechanical Detent & Calibrated Sweep",
            "description": "Crisp, low-overshoot transitions (`cubic-bezier(0.16, 1, 0.3, 1)`) on dial/filter changes and smooth SVG coordinate readouts.",
            "easing": "cubic-bezier(0.16, 1, 0.3, 1)",
            "duration": "280ms",
            "reduced_motion_fallback": "Instant state updates without sweep interpolation.",
        },
        "idea_prompt": "On this page, the subject's calibrated measurement tolerances become an interactive specification instrument.",
        "live_thing_archetype": "Calibrated parameter dial or tolerance comparator where the visitor scrubs operating conditions and reads exact computed physical/system responses.",
    },
    {
        "id": "name-as-monument",
        "name": "The Name as a Monument",
        "mode_affinity": ["persuade", "experience"],
        "variance_band": (7, 10),
        "keywords": ["studio", "agency", "portfolio", "architecture", "fashion", "culture", "music", "event", "brand", "creative", "game", "art"],
        "composition_philosophy": (
            "The subject's name or core thesis is set so large (12-18vw clamp) that it becomes architectural structure, "
            "spanning the viewport between tight equal margins while a live visual artifact sits embedded inside or directly beside it."
        ),
        "hero_blueprint": (
            "First screen: Monumental display title (<= 2 lines, clamp(3.2rem, 11vw, 8.5rem), tracking -0.04em, leading 0.88) "
            "anchored to shared 24px margins, paired with a high-impact interactive visual stage and a single corner-anchored supporting lead + primary button."
        ),
        "section_blueprints": [
            {"role": "hero", "archetype": "monument-wordmark-stage", "geometry": "Full-width monumental typography + embedded live visual canvas and concise 1-sentence lead + CTA."},
            {"role": "showcase", "archetype": "full-bleed-artifact", "geometry": "8/4 asymmetric showcase: large interactive case study / visual preview on left, specification & filter controls on right."},
            {"role": "capabilities", "archetype": "editorial-index-rows", "geometry": "Interactive full-width typographic index where selecting a capability expands its live preview and metrics inline."},
            {"role": "evidence", "archetype": "asymmetric-split", "geometry": "5/7 split: bold thesis statement on left, empirical output gallery/table on right."},
            {"role": "footer", "archetype": "inverted-monument-close", "geometry": "Full-bleed inverted ground/ink close returning the monumental wordmark across the bottom edge."},
        ],
        "typography_system": {
            "display_face": "Syne",
            "body_face": "DM Sans",
            "mono_face": "Space Mono",
            "google_fonts_import": "@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Space+Mono:wght@400&family=Syne:wght@700;800&display=swap');",
            "headline_to_body_ratio": 4.8,
            "display_tracking": "-0.04em",
            "display_leading": "0.88",
            "body_size": "17px",
            "body_leading": "1.55",
            "measure": "58ch",
        },
        "color_system": {
            "theme": "dark",
            "ground": "#0D0D0D",
            "surface": "#171717",
            "elevated_surface": "#222222",
            "ink": "#F5F5F3",
            "muted_ink": "#A3A39E",
            "primary_accent": "#E2FF32",
            "on_accent": "#0D0D0D",
            "border": "#2A2A28",
            "selection_bg": "#E2FF32",
            "selection_fg": "#0D0D0D",
            "semantic": {"positive": "#4ADE80", "warning": "#FACC15", "danger": "#F87171", "info": "#38BDF8"},
            "notes": "Carbon gallery black (#0D0D0D) with bone white ink (#F5F5F3) and acid chartreuse accent (#E2FF32) on the primary action.",
        },
        "signature_motion": {
            "id": "scaling-wordmark",
            "name": "Monumental Scale & Index Reveal",
            "description": "Smooth scale/mask arrival on the hero monument and instant preview morphing as index rows are selected.",
            "easing": "cubic-bezier(0.22, 1, 0.36, 1)",
            "duration": "500ms",
            "reduced_motion_fallback": "Static full-contrast display type; index selection swaps preview immediately.",
        },
        "idea_prompt": "On this page, the scale of the subject's name frames a live interactive window into its work.",
        "live_thing_archetype": "Interactive work/capability stage where clicking or scrubbing through items dynamically re-renders the visual canvas and specification readout.",
    },
    {
        "id": "sentence-as-layout",
        "name": "The Sentence Is the Layout",
        "mode_affinity": ["persuade", "read"],
        "variance_band": (6, 9),
        "keywords": ["editorial", "fintech", "climate", "nonprofit", "education", "publishing", "research", "policy", "health", "ai-product"],
        "composition_philosophy": (
            "A bold, concise thesis sentence at poster scale forms the structural backbone of the first screen, "
            "while each subsequent section pairs a left-column claim sentence with right-column empirical proof (interactive chart, calculator, or dataset)."
        ),
        "hero_blueprint": (
            "Poster-scale 2-line headline (clamp(2.6rem, 6vw, 5.2rem)) spanning 10 columns, followed immediately by a "
            "supporting lead paragraph (18px) and primary CTA button aligned on the left margin, plus an inline interactive proof figure."
        ),
        "section_blueprints": [
            {"role": "hero", "archetype": "poster-sentence-with-proof", "geometry": "Full-width 2-line thesis headline over a 5/7 split of lead+CTA (left) and live interactive calculator/chart (right)."},
            {"role": "claim-1", "archetype": "claim-and-evidence-split", "geometry": "6/6 split: left column holds a 28px statement; right column holds a live interactive data breakdown."},
            {"role": "claim-2", "archetype": "full-bleed-contrast-band", "geometry": "Inverted color field with a full-width interactive timeline or scenario comparator."},
            {"role": "specs", "archetype": "editorial-ledger", "geometry": "Structured 3-column tabular breakdown with right-aligned `tabular-nums` figures."},
            {"role": "footer", "archetype": "editorial-colophon", "geometry": "High-contrast closing statement, primary action button, and source citations."},
        ],
        "typography_system": {
            "display_face": "Fraunces",
            "body_face": "Plus Jakarta Sans",
            "mono_face": "JetBrains Mono",
            "google_fonts_import": "@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=JetBrains+Mono:wght@400;500&family=Plus+Jakarta+Sans:wght@400;500;600&display=swap');",
            "headline_to_body_ratio": 3.9,
            "display_tracking": "-0.025em",
            "display_leading": "0.98",
            "body_size": "17px",
            "body_leading": "1.6",
            "measure": "65ch",
        },
        "color_system": {
            "theme": "light",
            "ground": "#F7F8F6",
            "surface": "#ECEFED",
            "elevated_surface": "#FFFFFF",
            "ink": "#111A15",
            "muted_ink": "#4A5850",
            "primary_accent": "#0F766E",
            "on_accent": "#FFFFFF",
            "border": "#CFD8D3",
            "selection_bg": "#0F766E",
            "selection_fg": "#FFFFFF",
            "semantic": {"positive": "#15803D", "warning": "#B45309", "danger": "#B91C1C", "info": "#0369A1"},
            "notes": "Crisp mineral sage-white ground (#F7F8F6) with deep forest ink (#111A15) and oceanic teal accent (#0F766E).",
        },
        "signature_motion": {
            "id": "masked-headline",
            "name": "Editorial Line Reveal & Proof Sync",
            "description": "Clean vertical line arrival (`cubic-bezier(0.22, 1, 0.36, 1)`) paired with synchronized chart/table filtering.",
            "easing": "cubic-bezier(0.22, 1, 0.36, 1)",
            "duration": "400ms",
            "reduced_motion_fallback": "Immediate static display with instant interactive filtering.",
        },
        "idea_prompt": "On this page, every claim sentence is physically paired with an interactive proof dataset that the visitor can interrogate.",
        "live_thing_archetype": "Interactive scenario/impact calculator or live dataset filter where visitors test assumptions and see the numbers update in real time.",
    },
    {
        "id": "specimen-catalogue",
        "name": "Archival Specimen Catalogue",
        "mode_affinity": ["persuade", "read", "experience"],
        "variance_band": (6, 10),
        "keywords": ["library", "dataset", "biology", "chemistry", "protein", "genomics", "catalog", "archive", "font", "design-system", "hardware", "commerce"],
        "composition_philosophy": (
            "Treats the product's items, models, or capabilities like curated specimens in a scientific monograph "
            "or foundry specimen sheet. Exposed structural alignment, exact taxonomic metadata, and a live specimen inspector."
        ),
        "hero_blueprint": (
            "Top taxonomic header bar with live count and filter controls. Hero splits 4/8: left holds the <=2-line title, "
            "plain explanation, and primary CTA; right holds the featured interactive specimen viewer with zoom/layer toggles."
        ),
        "section_blueprints": [
            {"role": "hero", "archetype": "specimen-stage-split", "geometry": "4/8 split: left title + taxonomic summary + CTA; right interactive specimen canvas."},
            {"role": "catalogue", "archetype": "interactive-specimen-matrix", "geometry": "Filterable multi-column specimen index where clicking any specimen loads its full telemetry into the inspector."},
            {"role": "anatomy", "archetype": "annotated-diagram-split", "geometry": "7/5 split: SVG anatomical/architectural breakdown on left, synchronized specification table on right."},
            {"role": "benchmarks", "archetype": "dense-telemetry-grid", "geometry": "Full-width comparative benchmark table with sortable columns and `tabular-nums`."},
            {"role": "footer", "archetype": "archival-colophon", "geometry": "Structured archival index footer with export/download actions."},
        ],
        "typography_system": {
            "display_face": "Newsreader",
            "body_face": "IBM Plex Sans",
            "mono_face": "IBM Plex Mono",
            "google_fonts_import": "@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Newsreader:opsz,wght@6..72,600;6..72,700&display=swap');",
            "headline_to_body_ratio": 3.5,
            "display_tracking": "-0.02em",
            "display_leading": "0.98",
            "body_size": "16px",
            "body_leading": "1.55",
            "measure": "66ch",
        },
        "color_system": {
            "theme": "light",
            "ground": "#F4F4F0",
            "surface": "#E9E9E2",
            "elevated_surface": "#FFFFFF",
            "ink": "#121316",
            "muted_ink": "#52555A",
            "primary_accent": "#1D4ED8",
            "on_accent": "#FFFFFF",
            "border": "#D0D2CE",
            "selection_bg": "#1D4ED8",
            "selection_fg": "#FFFFFF",
            "semantic": {"positive": "#15803D", "warning": "#B45309", "danger": "#B91C1C", "info": "#1D4ED8"},
            "notes": "Archival limestone paper (#F4F4F0) with carbon ink (#121316) and cobalt blueprint accent (#1D4ED8).",
        },
        "signature_motion": {
            "id": "specimen-focus",
            "name": "Specimen Crossfade & Callout Lock",
            "description": "Crisp 240ms specimen switching with SVG callout line drawing.",
            "easing": "cubic-bezier(0.16, 1, 0.3, 1)",
            "duration": "240ms",
            "reduced_motion_fallback": "Instant specimen switching with all callouts visible.",
        },
        "idea_prompt": "On this page, the domain's core entities are catalogued and inspected like physical specimens on a laboratory light-table.",
        "live_thing_archetype": "Interactive specimen light-table where the visitor selects different specimens/models, toggles annotation layers, and compares live metrics.",
    },
    {
        "id": "colour-chapters",
        "name": "Full-Bleed Colour Chapters",
        "mode_affinity": ["persuade", "experience"],
        "variance_band": (7, 10),
        "keywords": ["consumer", "media", "creative", "event", "festival", "music", "design", "education", "brand", "campaign", "story"],
        "composition_philosophy": (
            "Every section is a distinct chapter with its own flat, full-bleed field color from floor to ceiling, "
            "held together by one rigorous 12-column grid, shared left edges, and one expressive typeface."
        ),
        "hero_blueprint": (
            "Full-bleed opening color field (90svh) with equal 28px margins. Bold 2-line display headline (8-10vw max 5rem) "
            "on the shared left edge, paired with an interactive chapter previewer and high-contrast primary button."
        ),
        "section_blueprints": [
            {"role": "hero", "archetype": "full-bleed-chapter-opener", "geometry": "Full-bleed primary field holding <=2-line display headline, supporting lead, CTA, and interactive artifact."},
            {"role": "chapter-1", "archetype": "asymmetric-split", "geometry": "Contrasting flat field color; 5/7 split with left narrative and right interactive visual explorer."},
            {"role": "chapter-2", "archetype": "interactive-workbench", "geometry": "Deep dark field color; full-width interactive configurator or schedule/lineup builder."},
            {"role": "chapter-3", "archetype": "editorial-ledger", "geometry": "Warm stone field color; structured comparison matrix and FAQ accordion."},
            {"role": "footer", "archetype": "monument-close", "geometry": "High-contrast closing chapter returning the wordmark at full width."},
        ],
        "typography_system": {
            "display_face": "Cabinet Grotesk, Plus Jakarta Sans",
            "body_face": "Plus Jakarta Sans",
            "mono_face": "JetBrains Mono",
            "google_fonts_import": "@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');",
            "headline_to_body_ratio": 4.2,
            "display_tracking": "-0.035em",
            "display_leading": "0.94",
            "body_size": "18px",
            "body_leading": "1.55",
            "measure": "60ch",
        },
        "color_system": {
            "theme": "light",
            "ground": "#F2F4F1",
            "surface": "#E3E8E1",
            "elevated_surface": "#102A24",
            "ink": "#0F1D19",
            "muted_ink": "#3F524C",
            "primary_accent": "#E04F33",
            "on_accent": "#FFFFFF",
            "border": "#C5D0C8",
            "selection_bg": "#E04F33",
            "selection_fg": "#FFFFFF",
            "semantic": {"positive": "#15803D", "warning": "#B45309", "danger": "#B91C1C", "info": "#0369A1"},
            "notes": "Alternates full-bleed flat chapter grounds (#F2F4F1 mist sage, #E3E8E1 stone, #102A24 deep pine) with high-contrast ink and cinnabar CTA (#E04F33).",
        },
        "signature_motion": {
            "id": "chapter-curtain",
            "name": "Chapter Field Transition & Stagger",
            "description": "Smooth chapter transitions and staggered 65ms content entrances.",
            "easing": "cubic-bezier(0.22, 1, 0.36, 1)",
            "duration": "380ms",
            "reduced_motion_fallback": "Static color chapters with zero opacity hiding.",
        },
        "idea_prompt": "On this page, each stage of the user's journey owns its own full-bleed color chapter.",
        "live_thing_archetype": "Interactive chapter configurator or live filter that updates the active specimen/schedule across chapters.",
    },
    {
        "id": "split-stage",
        "name": "Split Stage (Fixed Artifact + Scrolling Argument)",
        "mode_affinity": ["persuade", "experience", "read"],
        "variance_band": (6, 9),
        "keywords": ["sdk", "api", "compiler", "3d", "graphics", "simulation", "cad", "gis", "visualization", "game-engine", "model"],
        "composition_philosophy": (
            "Splits the desktop viewport into two coordinated stages: a narrative/control column and a live interactive "
            "visual stage (Canvas/SVG/Code workbench) that transforms as the user steps through chapters or clicks controls."
        ),
        "hero_blueprint": (
            "12-column split stage with equal 24px outer margins. Left 5 columns hold the <=2-line title, lead copy, "
            "primary action, and step selector; right 7 columns hold the live interactive canvas/SVG stage."
        ),
        "section_blueprints": [
            {"role": "hero", "archetype": "split-stage-opener", "geometry": "5/7 coordinated split: narrative + step controls on left, live interactive visual stage on right."},
            {"role": "deep-dive", "archetype": "interactive-workbench", "geometry": "Full-width parameter laboratory with real-time sliders, preset buttons, and live telemetry readout."},
            {"role": "benchmarks", "archetype": "specimen-comparison-matrix", "geometry": "Structured benchmark comparison table with live workload selector."},
            {"role": "integration", "archetype": "annotated-code-walkthrough", "geometry": "6/6 split: interactive step-by-step architecture callouts on left, copyable code/config view on right."},
            {"role": "footer", "archetype": "minimal-technical-close", "geometry": "Full-width technical footer with status indicator and primary launch CTA."},
        ],
        "typography_system": {
            "display_face": "Outfit",
            "body_face": "Inter",
            "mono_face": "Fira Code",
            "google_fonts_import": "@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&family=Inter:wght@400;500;600&family=Outfit:wght@600;700&display=swap');",
            "headline_to_body_ratio": 3.7,
            "display_tracking": "-0.03em",
            "display_leading": "0.96",
            "body_size": "16px",
            "body_leading": "1.55",
            "measure": "62ch",
        },
        "color_system": {
            "theme": "dark",
            "ground": "#090D16",
            "surface": "#111827",
            "elevated_surface": "#1E293B",
            "ink": "#F8FAFC",
            "muted_ink": "#94A3B8",
            "primary_accent": "#06B6D4",
            "on_accent": "#083344",
            "border": "#1E293B",
            "selection_bg": "#06B6D4",
            "selection_fg": "#083344",
            "semantic": {"positive": "#10B981", "warning": "#F59E0B", "danger": "#EF4444", "info": "#06B6D4"},
            "notes": "Deep naval abyss ground (#090D16) with high-luminance cyan laser accent (#06B6D4) and slate surfaces.",
        },
        "signature_motion": {
            "id": "stage-morph",
            "name": "Synchronized Stage State Morph",
            "description": "Selecting any narrative step or control smoothly morphs the right-hand canvas/SVG geometry and telemetry counters.",
            "easing": "cubic-bezier(0.22, 1, 0.36, 1)",
            "duration": "350ms",
            "reduced_motion_fallback": "Instant canvas state switch with zero hidden text.",
        },
        "idea_prompt": "On this page, the narrative column directly drives a live visual simulation on the adjacent stage.",
        "live_thing_archetype": "Synchronized interactive simulation canvas that updates its geometry, layers, and performance metrics as the visitor clicks steps or adjusts parameters.",
    },
    {
        "id": "dark-room",
        "name": "Obsidian Dark Room (Artifact-Led)",
        "mode_affinity": ["experience", "persuade"],
        "variance_band": (5, 10),
        "keywords": ["cinema", "video", "photography", "3d", "rendering", "shader", "spatial", "gallery", "molecular", "astronomy", "gaming", "audio"],
        "composition_philosophy": (
            "The page is a dark room built so luminous visual artifacts, shaders, 3D structures, or waveforms "
            "command 100% of the eye's attention. UI chrome is whisper-quiet, unboxed, and anchored to the perimeter."
        ),
        "hero_blueprint": (
            "First screen gives >=70% of the viewport to the live luminous canvas/artifact, with a crisp <=2-line "
            "display title, 1-sentence explanation, and primary action button anchored cleanly in the lower-left grid."
        ),
        "section_blueprints": [
            {"role": "hero", "archetype": "luminous-artifact-stage", "geometry": "Full-bleed interactive canvas stage with perimeter HUD readout and anchored <=2-line hero title + CTA."},
            {"role": "inspector", "archetype": "asymmetric-split", "geometry": "7/5 split: interactive layer/channel isolator on left, technical breakdown and metrics on right."},
            {"role": "gallery", "archetype": "uneven-specimen-pairs", "geometry": "Asymmetric 8/4 and 4/8 alternating specimen rows with live preview toggle."},
            {"role": "specs", "archetype": "telemetry-ledger-band", "geometry": "Minimalist tabular specification matrix with `tabular-nums`."},
            {"role": "footer", "archetype": "monument-close", "geometry": "Quiet high-contrast dark close with direct launch action."},
        ],
        "typography_system": {
            "display_face": "Plus Jakarta Sans",
            "body_face": "Inter",
            "mono_face": "JetBrains Mono",
            "google_fonts_import": "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&family=Plus+Jakarta+Sans:wght@600;700&display=swap');",
            "headline_to_body_ratio": 3.8,
            "display_tracking": "-0.03em",
            "display_leading": "0.95",
            "body_size": "16px",
            "body_leading": "1.55",
            "measure": "60ch",
        },
        "color_system": {
            "theme": "dark",
            "ground": "#050608",
            "surface": "#0C0E12",
            "elevated_surface": "#141820",
            "ink": "#F3F4F6",
            "muted_ink": "#8E95A2",
            "primary_accent": "#F59E0B",
            "on_accent": "#050608",
            "border": "#1F2430",
            "selection_bg": "#F59E0B",
            "selection_fg": "#050608",
            "semantic": {"positive": "#10B981", "warning": "#F59E0B", "danger": "#EF4444", "info": "#38BDF8"},
            "notes": "True cinema darkroom ground (#050608) with warm sodium-vapor amber accent (#F59E0B) and zero decorative borders.",
        },
        "signature_motion": {
            "id": "darkroom-exposure",
            "name": "Luminous Exposure & Smooth Scrub",
            "description": "Smooth exposure reveal and real-time 60fps canvas response to scrubbing/preset changes.",
            "easing": "cubic-bezier(0.22, 1, 0.36, 1)",
            "duration": "450ms",
            "reduced_motion_fallback": "Static high-contrast render with instant preset switching.",
        },
        "idea_prompt": "On this page, the darkroom frame disappears so the luminous domain artifact can be manipulated directly.",
        "live_thing_archetype": "Interactive viewport scrubber / channel isolator where visitors inspect real layers, lighting, or structural states.",
    },
    {
        "id": "page-is-the-object",
        "name": "The Page Is the Physical Artifact",
        "mode_affinity": ["persuade", "experience"],
        "variance_band": (8, 10),
        "keywords": ["print", "book", "ticket", "manifest", "ledger", "blueprint", "map", "schematic", "packaging", "craft", "architecture"],
        "composition_philosophy": (
            "Borrows the exact graphic grammar of a physical artifact from the subject's world — an engineering blueprint, "
            "a flight manifest, a laboratory assay sheet, or a press proof — and turns the entire viewport into that working document."
        ),
        "hero_blueprint": (
            "Document title block with authentic specification stamps, <=2-line primary title at display scale, "
            "plain-language mission summary, primary action button, and an interactive blueprint/schematic canvas."
        ),
        "section_blueprints": [
            {"role": "hero", "archetype": "artifact-title-block", "geometry": "Architectural title block header + 6/6 split of thesis/CTA and live interactive schematic."},
            {"role": "schedule", "archetype": "manifest-ledger-table", "geometry": "Full-width interactive manifest/assay table with live filtering and `tabular-nums`."},
            {"role": "diagram", "archetype": "full-bleed-artifact", "geometry": "Interactive vector cross-section with clickable inspection callouts."},
            {"role": "verification", "archetype": "asymmetric-split", "geometry": "4/8 split: verification stamp & methodology on left, live parameter calculator on right."},
            {"role": "footer", "archetype": "document-signoff-close", "geometry": "Blueprint revision block footer with full-width wordmark."},
        ],
        "typography_system": {
            "display_face": "Archivo",
            "body_face": "IBM Plex Sans",
            "mono_face": "IBM Plex Mono",
            "google_fonts_import": "@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@600;700;800&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');",
            "headline_to_body_ratio": 3.8,
            "display_tracking": "-0.03em",
            "display_leading": "0.94",
            "body_size": "16px",
            "body_leading": "1.55",
            "measure": "64ch",
        },
        "color_system": {
            "theme": "light",
            "ground": "#EEF2F6",
            "surface": "#E2E8F0",
            "elevated_surface": "#FFFFFF",
            "ink": "#0F172A",
            "muted_ink": "#475569",
            "primary_accent": "#0284C7",
            "on_accent": "#FFFFFF",
            "border": "#CBD5E1",
            "selection_bg": "#0284C7",
            "selection_fg": "#FFFFFF",
            "semantic": {"positive": "#15803D", "warning": "#B45309", "danger": "#B91C1C", "info": "#0284C7"},
            "notes": "Drafting vellum blue-grey ground (#EEF2F6) with Prussian slate ink (#0F172A) and cyanotype blue accent (#0284C7).",
        },
        "signature_motion": {
            "id": "blueprint-trace",
            "name": "Vector Schematic Trace & Stamp",
            "description": "Crisp vector stroke reveal and instant schematic dimension updates when parameters change.",
            "easing": "cubic-bezier(0.16, 1, 0.3, 1)",
            "duration": "300ms",
            "reduced_motion_fallback": "All schematic lines and labels visible immediately.",
        },
        "idea_prompt": "On this page, the domain's working technical document/manifest becomes the interactive layout itself.",
        "live_thing_archetype": "Interactive schematic/manifest where changing dimensions or filters updates the vector drawing and bill of metrics live.",
    },
    # --- OPERATE DIRECTIONS (App Screens, Dashboards, Workspaces, Consoles) ---
    {
        "id": "achromatic-ledger",
        "name": "Achromatic Ledger (High-Signal Monochrome + Single Data Hue)",
        "mode_affinity": ["operate", "read"],
        "variance_band": (1, 6),
        "keywords": ["finance", "ledger", "billing", "analytics", "commerce", "devtools", "report", "workspace", "dashboard", "admin", "metrics", "table"],
        "composition_philosophy": (
            "The application chrome holds zero brand color: surfaces are crisp stone/white, primary actions are deep carbon ink, "
            "and 100% of the screen's color budget (<2% of pixels) goes onto the primary data series (#1D5FBF) and semantic delta badges."
        ),
        "hero_blueprint": (
            "Open-plane app shell (240px left navigation rail + full-width workspace canvas). Top header bar holds the screen `h1` (22-24px), "
            "time-range/environment segmented control, and primary action button. First row displays un-tinted KPI figures (28-32px `tabular-nums`) "
            "above a main interactive SVG chart and filterable ledger table."
        ),
        "section_blueprints": [
            {"role": "header-bar", "archetype": "workspace-command-header", "geometry": "Single-row header: `h1` screen title left, live status + time-window selector + primary action right."},
            {"role": "kpi-strip", "archetype": "kpi-strip-chart-rail", "geometry": "4-column un-tinted metric strip (`tabular-nums`) paired with a 2-series interactive SVG trend chart (ink + #1D5FBF)."},
            {"role": "primary-workspace", "archetype": "table-filter-bar", "geometry": "Search/filter toolbar above a dense data table with right-aligned numeric columns and inline row inspection."},
            {"role": "detail-drawer", "archetype": "object-detail-header-grid", "geometry": "Live inspector pane showing selected row's breakdown, audit log, and action buttons."},
        ],
        "typography_system": {
            "display_face": "Plus Jakarta Sans",
            "body_face": "Inter",
            "mono_face": "JetBrains Mono",
            "google_fonts_import": "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Plus+Jakarta+Sans:wght@600;700&display=swap');",
            "headline_to_body_ratio": 1.7,
            "display_tracking": "-0.02em",
            "display_leading": "1.15",
            "body_size": "14px",
            "body_leading": "1.45",
            "measure": "68ch",
        },
        "color_system": {
            "theme": "light",
            "ground": "#F6F6F4",
            "surface": "#FFFFFF",
            "elevated_surface": "#EFEFEC",
            "ink": "#0A0A0A",
            "muted_ink": "#666662",
            "primary_accent": "#1D5FBF",
            "on_accent": "#FFFFFF",
            "border": "#E5E5E0",
            "selection_bg": "#1D5FBF",
            "selection_fg": "#FFFFFF",
            "semantic": {"positive": "#1E7B4F", "warning": "#92400E", "danger": "#C4242A", "info": "#1D5FBF"},
            "notes": "Achromatic stone ground (#F6F6F4) and white panels (#FFFFFF) with whisper 1px border (#E5E5E0) and #1D5FBF chart/focus accent.",
        },
        "signature_motion": {
            "id": "ledger-filter-snap",
            "name": "Instant Filter & Tabular Recalculation",
            "description": "Sub-150ms micro-transitions on table sort/filter and SVG bar/line updates.",
            "easing": "cubic-bezier(0.16, 1, 0.3, 1)",
            "duration": "140ms",
            "reduced_motion_fallback": "0ms instant state updates.",
        },
        "idea_prompt": "On this screen, zero-chroma chrome makes the single coloured data series and live ledger deltas impossible to miss.",
        "live_thing_archetype": "Interactive time-window / cohort filter that dynamically recalculates KPI totals, re-renders the SVG chart, and filters the ledger rows.",
    },
    {
        "id": "framed-sheet",
        "name": "Framed Sheet Workbench (L-Frame + Inset Canvas)",
        "mode_affinity": ["operate"],
        "variance_band": (3, 7),
        "keywords": ["analytics", "devtools", "observability", "cloud", "pipeline", "builder", "workflow", "admin", "platform", "monitoring"],
        "composition_philosophy": (
            "The outer sidebar and 48px top bar form one continuous, low-chroma tinted L-frame with no border between them, "
            "while the workspace sits on a crisp inset sheet (`border-radius: 12px`, `1px` border, zero shadow) so depth comes from a single tone step."
        ),
        "hero_blueprint": (
            "L-shaped outer frame holding navigation and breadcrumb/command bar; inset main sheet opens with a compact `h1` (22px), "
            "tabbed view switcher (2px active underline), and a 2-column live telemetry + execution workbench."
        ),
        "section_blueprints": [
            {"role": "shell-header", "archetype": "framed-sheet-header", "geometry": "48px top bar integrated with 224px sidebar; inset canvas header with `h1` and view tabs."},
            {"role": "overview", "archetype": "chart-pairs", "geometry": "Balanced 6/6 row of two synchronized SVG charts (throughput + latency distribution) with shared hover/scrub."},
            {"role": "workbench", "archetype": "insights-share-tables", "geometry": "8/4 split: live filterable execution/trace table on left, interactive node/span detail inspector on right."},
            {"role": "controls", "archetype": "settings-with-usage", "geometry": "Inline configuration controls with real-time quota/resource bar updates."},
        ],
        "typography_system": {
            "display_face": "IBM Plex Sans",
            "body_face": "IBM Plex Sans",
            "mono_face": "IBM Plex Mono",
            "google_fonts_import": "@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');",
            "headline_to_body_ratio": 1.6,
            "display_tracking": "-0.015em",
            "display_leading": "1.2",
            "body_size": "14px",
            "body_leading": "1.45",
            "measure": "68ch",
        },
        "color_system": {
            "theme": "light",
            "ground": "#F2F5F7",
            "surface": "#FFFFFF",
            "elevated_surface": "#F8FAFC",
            "ink": "#131416",
            "muted_ink": "#5A5D60",
            "primary_accent": "#1B6C80",
            "on_accent": "#FFFFFF",
            "border": "#E2E6EA",
            "selection_bg": "#1B6C80",
            "selection_fg": "#FFFFFF",
            "semantic": {"positive": "#1E7B4F", "warning": "#92400E", "danger": "#C4242A", "info": "#1B6C80"},
            "notes": "Cool mineral frame (#F2F5F7) holding a pure white inset sheet (#FFFFFF) with petrol teal accent (#1B6C80).",
        },
        "signature_motion": {
            "id": "sheet-tab-glide",
            "name": "2px Underline Glide & Synchronized Scrub",
            "description": "Fast 160ms tab/panel transitions and synchronized crosshair scrubbing across paired charts.",
            "easing": "cubic-bezier(0.16, 1, 0.3, 1)",
            "duration": "160ms",
            "reduced_motion_fallback": "Instant tab/chart state updates.",
        },
        "idea_prompt": "On this screen, the L-shaped frame separates navigation from a crisp inset workbench sheet where paired charts and trace tables stay synchronized.",
        "live_thing_archetype": "Synchronized trace/metric explorer where clicking a trace row or scrubbing the chart updates the inspector panel and highlights anomalies.",
    },
    {
        "id": "true-black-flat",
        "name": "True-Black Flat Precision Studio",
        "mode_affinity": ["operate", "experience"],
        "variance_band": (4, 8),
        "keywords": ["gpu", "ide", "code", "terminal", "cluster", "infrastructure", "security", "crypto", "trading", "telemetry", "ops", "dark", "ai", "model"],
        "composition_philosophy": (
            "OLED-grade dark studio (`#08090C` ground, `#101318` panels, `#1E232D` 1px borders) with zero blurred glass and zero drop-shadows. "
            "Hierarchy comes strictly from crisp 1px structural hairlines, high-contrast `tabular-nums` telemetry, and one electric signal accent."
        ),
        "hero_blueprint": (
            "Compact 44px command header (`h1` + keyboard shortcut badge `Ctrl+K` + live status pill) over a 3-pane studio grid: "
            "left resource/model rail, center interactive canvas/telemetry graph, and right live parameter/log inspector."
        ),
        "section_blueprints": [
            {"role": "command-bar", "archetype": "ruled-t-frame", "geometry": "Full-width 1px-ruled top command bar with live cluster/engine status and quick-filter input."},
            {"role": "telemetry-stage", "archetype": "deploy-health-lead", "geometry": "8/4 split: real-time multi-series SVG/Canvas telemetry monitor on left, live KPI & node health matrix on right."},
            {"role": "execution-grid", "archetype": "table-filter-bar", "geometry": "Dense interactive job/query table (`tabular-nums`) with status filters, row selection, and live detail pane."},
            {"role": "console-drawer", "archetype": "power-flow", "geometry": "Interactive command/parameter runner that appends real execution output to the state log."},
        ],
        "typography_system": {
            "display_face": "Inter",
            "body_face": "Inter",
            "mono_face": "JetBrains Mono",
            "google_fonts_import": "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');",
            "headline_to_body_ratio": 1.65,
            "display_tracking": "-0.02em",
            "display_leading": "1.15",
            "body_size": "14px",
            "body_leading": "1.45",
            "measure": "70ch",
        },
        "color_system": {
            "theme": "dark",
            "ground": "#08090C",
            "surface": "#101318",
            "elevated_surface": "#171B22",
            "ink": "#F1F5F9",
            "muted_ink": "#8B95A5",
            "primary_accent": "#22C55E",
            "on_accent": "#052E16",
            "border": "#1E2430",
            "selection_bg": "#22C55E",
            "selection_fg": "#052E16",
            "semantic": {"positive": "#22C55E", "warning": "#F59E0B", "danger": "#EF4444", "info": "#38BDF8"},
            "notes": "True-black flat studio (#08090C) with whisper 1px borders (#1E2430) and phosphor green signal accent (#22C55E).",
        },
        "signature_motion": {
            "id": "telemetry-tick",
            "name": "Zero-Latency Telemetry Tick & Command Palette",
            "description": "Crisp 120ms state transitions on filter/preset execution and smooth SVG polyline updates.",
            "easing": "cubic-bezier(0.16, 1, 0.3, 1)",
            "duration": "120ms",
            "reduced_motion_fallback": "Instant DOM/SVG state updates.",
        },
        "idea_prompt": "On this screen, an OLED-flat 1px-ruled grid lets live telemetry curves and execution states read with zero visual noise.",
        "live_thing_archetype": "Interactive workload/query dispatcher and live telemetry scrubber that mutates cluster/engine state and updates the SVG monitor.",
    },
    {
        "id": "data-terminal",
        "name": "High-Density Quantitative Terminal",
        "mode_affinity": ["operate"],
        "variance_band": (7, 10),
        "keywords": ["quant", "trading", "orderbook", "matrix", "database", "sql", "logs", "profiler", "benchmark", "network", "kernel", "compiler"],
        "composition_philosophy": (
            "Designed for power users who read dense multi-dimensional matrices and time-series at a glance. "
            "Every cell aligns on a strict baseline grid, numbers use `tabular-nums`, and keyboard/click selection cross-filters every panel."
        ),
        "hero_blueprint": (
            "No marketing hero: opens directly into aruled T-frame workspace with a 20px screen `h1`, "
            "live query/expression bar, 4-metric summary strip, and a synchronized 3-panel matrix + chart + detail layout."
        ),
        "section_blueprints": [
            {"role": "query-bar", "archetype": "command-expression-bar", "geometry": "Full-width interactive filter/expression bar with preset chips and execution latency badge."},
            {"role": "matrix-stage", "archetype": "cover-matrix", "geometry": "7/5 split: sortable quantitative heatmap/table on left, synchronized distribution & time-series SVG chart on right."},
            {"role": "inspector", "archetype": "tabbed-object-detail", "geometry": "Bottom or right docked detail ledger showing exact breakdown of the selected cell/row."},
        ],
        "typography_system": {
            "display_face": "IBM Plex Sans",
            "body_face": "IBM Plex Sans",
            "mono_face": "IBM Plex Mono",
            "google_fonts_import": "@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');",
            "headline_to_body_ratio": 1.55,
            "display_tracking": "-0.015em",
            "display_leading": "1.15",
            "body_size": "13.5px",
            "body_leading": "1.4",
            "measure": "72ch",
        },
        "color_system": {
            "theme": "dark",
            "ground": "#0A0D12",
            "surface": "#11161F",
            "elevated_surface": "#19202C",
            "ink": "#E2E8F0",
            "muted_ink": "#8492A6",
            "primary_accent": "#38BDF8",
            "on_accent": "#082F49",
            "border": "#1E293B",
            "selection_bg": "#38BDF8",
            "selection_fg": "#082F49",
            "semantic": {"positive": "#34D399", "warning": "#FBBF24", "danger": "#F87171", "info": "#38BDF8"},
            "notes": "Deep slate terminal (#0A0D12) with sky-cyan active cursor/series accent (#38BDF8) and emerald/coral delta markers.",
        },
        "signature_motion": {
            "id": "crossfilter-lock",
            "name": "Instant Cross-Filter Highlight",
            "description": "100ms cross-highlighting between table rows, heatmap cells, and chart series.",
            "easing": "cubic-bezier(0.16, 1, 0.3, 1)",
            "duration": "100ms",
            "reduced_motion_fallback": "Instant highlight state change.",
        },
        "idea_prompt": "On this screen, selecting any cell in the quantitative matrix cross-filters the entire terminal in one click.",
        "live_thing_archetype": "Cross-filtering quantitative matrix + expression bar where clicking rows or applying filter presets updates all charts and summary counters.",
    },
    {
        "id": "accent-ladder",
        "name": "Tactile Daylight Studio (Accent Ladder)",
        "mode_affinity": ["operate", "persuade"],
        "variance_band": (4, 8),
        "keywords": ["productivity", "project", "planning", "crm", "collaboration", "design-tool", "builder", "education", "health", "operations"],
        "composition_philosophy": (
            "Warm daylight workspace where surface elevation climbs a calibrated 3-step tone ladder "
            "(`#F4F3EF` ground -> `#FFFFFF` active card -> `#EAE8E1` recessed well) with crisp 1px borders and a single confident forest-emerald or cobalt accent."
        ),
        "hero_blueprint": (
            "Collapsible left navigation rail + daylight workspace canvas. Top header holds the screen `h1` (24px), "
            "active view switcher (Board / Table / Timeline), and primary creation button."
        ),
        "section_blueprints": [
            {"role": "workspace-header", "archetype": "workspace-home-greeting", "geometry": "Header with `h1`, status summary pills, view switcher, and primary action."},
            {"role": "interactive-board", "archetype": "count-cards-filter", "geometry": "Filterable status strip above an interactive workflow/pipeline board and synchronized metrics chart."},
            {"role": "detail-table", "archetype": "report-card-legend-table", "geometry": "Structured breakdown table (`tabular-nums`) with inline status toggling and search."},
        ],
        "typography_system": {
            "display_face": "Plus Jakarta Sans",
            "body_face": "Plus Jakarta Sans",
            "mono_face": "JetBrains Mono",
            "google_fonts_import": "@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');",
            "headline_to_body_ratio": 1.75,
            "display_tracking": "-0.02em",
            "display_leading": "1.18",
            "body_size": "14.5px",
            "body_leading": "1.5",
            "measure": "65ch",
        },
        "color_system": {
            "theme": "light",
            "ground": "#F4F3EF",
            "surface": "#FFFFFF",
            "elevated_surface": "#EAE8E1",
            "ink": "#161816",
            "muted_ink": "#5C605B",
            "primary_accent": "#15803D",
            "on_accent": "#FFFFFF",
            "border": "#DFDDD6",
            "selection_bg": "#15803D",
            "selection_fg": "#FFFFFF",
            "semantic": {"positive": "#15803D", "warning": "#B45309", "danger": "#B91C1C", "info": "#0369A1"},
            "notes": "Low-chroma warm stone ground (#F4F3EF) with crisp white surfaces and botanical green accent (#15803D).",
        },
        "signature_motion": {
            "id": "tactile-card-shift",
            "name": "Tactile State Shift & Counter Roll",
            "description": "180ms smooth state transitions when moving/filtering items and recalculating progress bars.",
            "easing": "cubic-bezier(0.22, 1, 0.36, 1)",
            "duration": "180ms",
            "reduced_motion_fallback": "Instant item state transitions.",
        },
        "idea_prompt": "On this screen, a 3-step daylight tone ladder organizes complex multi-stage workflows without visual clutter.",
        "live_thing_archetype": "Interactive workflow state switcher and filter bar that lets users advance item states and watch capacity/completion charts update.",
    },
    {
        "id": "spatial-canvas-hud",
        "name": "Direct-Manipulation Spatial Canvas & Docked Inspector",
        "mode_affinity": ["experience", "operate"],
        "variance_band": (6, 10),
        "keywords": ["canvas", "node-editor", "graph", "3d", "cad", "gis", "map", "molecular", "protein", "blender", "unity", "shader", "topology", "network"],
        "composition_philosophy": (
            "The interactive 2D/3D canvas or node graph IS the primary surface, filling the viewport while crisp, "
            "opaque 1px-bordered inspector docks anchor cleanly to the left and right edges without obscuring the center stage."
        ),
        "hero_blueprint": (
            "Top 44px toolbar with `h1` project/scene title, mode tools, and run/export button; "
            "center interactive SVG/Canvas viewport (70% width) flanked by a left hierarchy/layer tree and right property inspector."
        ),
        "section_blueprints": [
            {"role": "top-toolbar", "archetype": "canvas-command-bar", "geometry": "44px top bar with `h1` scene title, tool selector, zoom/fit readout (`tabular-nums`), and primary Run/Export CTA."},
            {"role": "canvas-stage", "archetype": "builder-canvas", "geometry": "3-column studio: 220px scene/node list (left), interactive SVG/Canvas viewport (center), 280px live property & metric inspector (right)."},
            {"role": "timeline-telemetry", "archetype": "leave-timeline", "geometry": "Bottom docked timeline/telemetry scrubber with frame/step metrics and live graph."},
        ],
        "typography_system": {
            "display_face": "Space Grotesk",
            "body_face": "Inter",
            "mono_face": "JetBrains Mono",
            "google_fonts_import": "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&family=Space+Grotesk:wght@600;700&display=swap');",
            "headline_to_body_ratio": 1.65,
            "display_tracking": "-0.02em",
            "display_leading": "1.15",
            "body_size": "14px",
            "body_leading": "1.45",
            "measure": "64ch",
        },
        "color_system": {
            "theme": "dark",
            "ground": "#0B0D11",
            "surface": "#13171F",
            "elevated_surface": "#1B202B",
            "ink": "#F1F5F9",
            "muted_ink": "#8E98A8",
            "primary_accent": "#0EA5E9",
            "on_accent": "#082F49",
            "border": "#222938",
            "selection_bg": "#0EA5E9",
            "selection_fg": "#082F49",
            "semantic": {"positive": "#10B981", "warning": "#F59E0B", "danger": "#EF4444", "info": "#0EA5E9"},
            "notes": "Graphite viewport ground (#0B0D11) with opaque docked inspector panels (#13171F) and cerulean selection/vector accent (#0EA5E9).",
        },
        "signature_motion": {
            "id": "canvas-direct-manip",
            "name": "Direct Canvas Manipulation & Inspector Sync",
            "description": "60fps canvas node/camera updates synchronized with inspector sliders and numeric scrubbers.",
            "easing": "cubic-bezier(0.16, 1, 0.3, 1)",
            "duration": "150ms",
            "reduced_motion_fallback": "Direct instant coordinate/node updates without camera coasting.",
        },
        "idea_prompt": "On this screen, direct manipulation on the spatial canvas and numeric scrubbing in the property dock are two views of the exact same live state.",
        "live_thing_archetype": "Interactive node/spatial canvas where clicking nodes or dragging property sliders updates the rendered geometry and computed metrics live.",
    },
    # --- READ & EDITORIAL DIRECTIONS (Docs, Technical Manuals, Research Reports, Notebooks) ---
    {
        "id": "editorial-report",
        "name": "Publication-Grade Research Monograph",
        "mode_affinity": ["read", "persuade"],
        "variance_band": (2, 7),
        "keywords": ["report", "research", "paper", "journal", "whitepaper", "analysis", "benchmark", "science", "economics", "policy", "documentation"],
        "composition_philosophy": (
            "Modelled on Distill.pub, Stripe Press, and classic scientific monographs. "
            "Generous warm daylight margins, authoritative serif display headings, a 62ch body column, "
            "and interactive figures that sit inline with the prose to prove every section's claim."
        ),
        "hero_blueprint": (
            "Editorial monograph header: <=2-line display title (clamp(2.2rem, 4.2vw, 3.6rem)), concise abstract lead (18px), "
            "metadata/author ledger bar (`tabular-nums`), and an opening interactive summary figure above the fold."
        ),
        "section_blueprints": [
            {"role": "hero", "archetype": "monograph-title-and-abstract", "geometry": "8-column anchored title + abstract + metadata bar, paired with a 4-column key findings summary."},
            {"role": "figure-1", "archetype": "interactive-inline-figure", "geometry": "Full-grid interactive SVG chart/simulation with parameter toggles and figure caption."},
            {"role": "methodology", "archetype": "prose-with-margin-notes", "geometry": "8-column main reading measure (62ch) with 4-column synchronized margin annotations and definitions."},
            {"role": "data-table", "archetype": "editorial-ledger", "geometry": "Publication-grade booktabs table (`tabular-nums`) with interactive sorting and cohort filter."},
            {"role": "footer", "archetype": "bibliography-colophon", "geometry": "Structured citations, reproducibility commands, and colophon."},
        ],
        "typography_system": {
            "display_face": "Source Serif 4, Newsreader",
            "body_face": "Source Sans 3, Inter",
            "mono_face": "JetBrains Mono",
            "google_fonts_import": "@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Newsreader:opsz,wght@6..72,600;6..72,700&family=Source+Sans+3:wght@400;500;600&display=swap');",
            "headline_to_body_ratio": 3.1,
            "display_tracking": "-0.02em",
            "display_leading": "1.05",
            "body_size": "18px",
            "body_leading": "1.65",
            "measure": "62ch",
        },
        "color_system": {
            "theme": "light",
            "ground": "#F8F7F4",
            "surface": "#EFECE6",
            "elevated_surface": "#FFFFFF",
            "ink": "#181816",
            "muted_ink": "#5A5852",
            "primary_accent": "#9A3412",
            "on_accent": "#FFFFFF",
            "border": "#DCD8CE",
            "selection_bg": "#9A3412",
            "selection_fg": "#FFFFFF",
            "semantic": {"positive": "#15803D", "warning": "#B45309", "danger": "#B91C1C", "info": "#1D4ED8"},
            "notes": "Low-chroma archival cotton paper (#F8F7F4) with deep ink (#181816) and scholarly oxide-crimson accent (#9A3412).",
        },
        "signature_motion": {
            "id": "figure-scrub",
            "name": "Interactive Figure Parameter Scrub",
            "description": "Smooth 200ms chart/diagram transitions as readers toggle assumptions inline.",
            "easing": "cubic-bezier(0.22, 1, 0.36, 1)",
            "duration": "200ms",
            "reduced_motion_fallback": "Instant chart redraws.",
        },
        "idea_prompt": "On this page, static equations and claims become interactive inline figures that the reader can test while reading.",
        "live_thing_archetype": "Inline interactive figure/model where readers adjust variables and watch the empirical curves and table values update live.",
    },
    {
        "id": "technical-codex",
        "name": "Precision Technical Codex & API Explorer",
        "mode_affinity": ["read", "operate"],
        "variance_band": (2, 6),
        "keywords": ["docs", "documentation", "sdk", "api", "cli", "reference", "guide", "manual", "specification", "protocol", "library"],
        "composition_philosophy": (
            "Structures technical knowledge for instant comprehension and execution: left navigation tree (<=4 top-level groups), "
            "center 65ch specification prose, and synchronized live request/code playground on the right."
        ),
        "hero_blueprint": (
            "3-column technical codex layout: left navigation rail (220px), center documentation header (`h1` <= 2 lines + lead + quick-start CTA), "
            "and right live interactive CLI/API playground."
        ),
        "section_blueprints": [
            {"role": "hero", "archetype": "codex-header-and-playground", "geometry": "Center `h1` specification overview paired with right-column live interactive request/command runner."},
            {"role": "parameters", "archetype": "schema-specification-ledger", "geometry": "Structured parameter & type contract table with interactive filter and validation examples."},
            {"role": "architecture", "archetype": "annotated-code-walkthrough", "geometry": "Step-by-step architectural state diagram synchronized with runnable code snippets."},
            {"role": "benchmarks", "archetype": "telemetry-ledger-band", "geometry": "Tabular latency/memory reference matrix (`tabular-nums`)."},
        ],
        "typography_system": {
            "display_face": "Plus Jakarta Sans",
            "body_face": "Inter",
            "mono_face": "JetBrains Mono",
            "google_fonts_import": "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&family=Plus+Jakarta+Sans:wght@600;700&display=swap');",
            "headline_to_body_ratio": 2.4,
            "display_tracking": "-0.025em",
            "display_leading": "1.1",
            "body_size": "16.5px",
            "body_leading": "1.6",
            "measure": "65ch",
        },
        "color_system": {
            "theme": "dark",
            "ground": "#0B0F17",
            "surface": "#111827",
            "elevated_surface": "#1F2937",
            "ink": "#F3F4F6",
            "muted_ink": "#9CA3AF",
            "primary_accent": "#38BDF8",
            "on_accent": "#082F49",
            "border": "#1F2937",
            "selection_bg": "#38BDF8",
            "selection_fg": "#082F49",
            "semantic": {"positive": "#10B981", "warning": "#F59E0B", "danger": "#EF4444", "info": "#38BDF8"},
            "notes": "Deep slate codex (#0B0F17) with crisp syntax-highlighted code blocks and sky blue interactive focus (#38BDF8).",
        },
        "signature_motion": {
            "id": "codex-sync",
            "name": "Synchronized Code & Schema Highlight",
            "description": "150ms instant highlight linking schema parameters to the live code/response preview.",
            "easing": "cubic-bezier(0.16, 1, 0.3, 1)",
            "duration": "150ms",
            "reduced_motion_fallback": "Instant highlight and response switch.",
        },
        "idea_prompt": "On this page, every documented parameter or command can be toggled and executed live in the adjacent response pane.",
        "live_thing_archetype": "Interactive API/CLI parameter builder that synthesizes valid commands/requests and renders the live structured output.",
    },
    {
        "id": "annotated-notebook",
        "name": "Executable Computational Notebook (Observable-Grade)",
        "mode_affinity": ["read", "experience", "operate"],
        "variance_band": (4, 8),
        "keywords": ["notebook", "data-science", "math", "simulation", "algorithm", "ml", "ai", "statistics", "educational", "explorable", "tutorial"],
        "composition_philosophy": (
            "Inspired by Observable notebooks and Bret Victor's explorable explanations. "
            "Prose, live reactive variables, executable cells, and reactive SVG charts live in one unified reactive document."
        ),
        "hero_blueprint": (
            "Reactive document header (`h1` <= 2 lines + lead explanation) followed immediately by the primary reactive cell: "
            "interactive input scrubbers bound directly to a live SVG visualization and computed output table."
        ),
        "section_blueprints": [
            {"role": "hero", "archetype": "reactive-notebook-stage", "geometry": "Header + primary reactive simulation cell with live input sliders and SVG canvas above the fold."},
            {"role": "derivation", "archetype": "claim-and-evidence-split", "geometry": "6/6 split: formal explanation/algorithm steps on left, live step-debugger state table on right."},
            {"role": "sensitivity", "archetype": "chart-pairs", "geometry": "Paired reactive sensitivity charts that update simultaneously as parameters change."},
            {"role": "export", "archetype": "editorial-ledger", "geometry": "Summary table of computed outputs (`tabular-nums`) with JSON/CSV copy action."},
        ],
        "typography_system": {
            "display_face": "Space Grotesk",
            "body_face": "Source Sans 3, Inter",
            "mono_face": "Fira Code",
            "google_fonts_import": "@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&family=Inter:wght@400;500;600&family=Space+Grotesk:wght@600;700&display=swap');",
            "headline_to_body_ratio": 2.8,
            "display_tracking": "-0.025em",
            "display_leading": "1.05",
            "body_size": "17px",
            "body_leading": "1.6",
            "measure": "66ch",
        },
        "color_system": {
            "theme": "light",
            "ground": "#F6F8FA",
            "surface": "#FFFFFF",
            "elevated_surface": "#EEF2F6",
            "ink": "#0F172A",
            "muted_ink": "#475569",
            "primary_accent": "#0D9488",
            "on_accent": "#FFFFFF",
            "border": "#D8E0E8",
            "selection_bg": "#0D9488",
            "selection_fg": "#FFFFFF",
            "semantic": {"positive": "#15803D", "warning": "#B45309", "danger": "#B91C1C", "info": "#0284C7"},
            "notes": "Clean notebook paper (#F6F8FA) with white reactive cells (#FFFFFF) and teal reactive variable accent (#0D9488).",
        },
        "signature_motion": {
            "id": "reactive-propagation",
            "name": "Reactive Variable Propagation",
            "description": "Immediate 60fps propagation from any slider/input cell to all dependent SVG charts and prose numbers.",
            "easing": "cubic-bezier(0.16, 1, 0.3, 1)",
            "duration": "120ms",
            "reduced_motion_fallback": "Direct reactive value updates.",
        },
        "idea_prompt": "On this page, numbers inside the paragraphs and curves inside the charts are bound to the same live reactive inputs.",
        "live_thing_archetype": "Reactive notebook cells where scrubbing any input variable updates inline prose numbers, tables, and SVG plots simultaneously.",
    },
]


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) >= 2]


def infer_mode(query: str, explicit_mode: str | None) -> str:
    if explicit_mode and explicit_mode in SURFACE_MODES:
        return explicit_mode
    tokens = set(_tokenize(query))
    if tokens & {"dashboard", "console", "workspace", "admin", "terminal", "monitor", "telemetry", "studio", "ide", "ops", "inbox", "settings", "ledger"}:
        return "operate"
    if tokens & {"docs", "documentation", "manual", "report", "paper", "monograph", "guide", "wiki", "reference", "notebook"}:
        return "read"
    if tokens & {"3d", "canvas", "shader", "viewer", "spatial", "game", "portfolio", "gallery", "simulation"}:
        return "experience"
    return "persuade"


def compute_dial_tokens(mode: str, variance: int, motion: int, density: int, direction: dict[str, Any]) -> dict[str, Any]:
    """Compute exact CSS Custom Property token tables tuned to `--variance`, `--motion`, `--density`, and `mode`."""
    variance = max(1, min(10, variance))
    motion = max(1, min(10, motion))
    density = max(1, min(10, density))

    # 1. Spacing scale driven by --density (1=spacious, 10=ultra-dense)
    if density <= 3:
        density_label = "Spacious / Editorial Gallery"
        space = {
            "--space-2xs": "4px",
            "--space-xs": "8px",
            "--space-sm": "16px",
            "--space-md": "24px",
            "--space-lg": "40px",
            "--space-xl": "64px",
            "--space-2xl": "96px",
            "--space-section": "160px",
            "--page-margin": "32px",
            "--grid-gap": "28px",
        }
    elif density <= 7:
        density_label = "Balanced / Structured Studio"
        space = {
            "--space-2xs": "4px",
            "--space-xs": "8px",
            "--space-sm": "12px",
            "--space-md": "16px",
            "--space-lg": "24px",
            "--space-xl": "40px",
            "--space-2xl": "64px",
            "--space-section": "120px" if mode in ("persuade", "experience") else "48px",
            "--page-margin": "24px",
            "--grid-gap": "20px",
        }
    else:
        density_label = "High-Density / Telemetry Workbench"
        space = {
            "--space-2xs": "2px",
            "--space-xs": "4px",
            "--space-sm": "8px",
            "--space-md": "12px",
            "--space-lg": "16px",
            "--space-xl": "24px",
            "--space-2xl": "32px",
            "--space-section": "32px" if mode == "operate" else "96px",
            "--page-margin": "20px",
            "--grid-gap": "12px",
        }

    # 2. Geometry & Radius tokens driven by --variance (1=symmetric/classic, 10=bold/architectural)
    if variance <= 3:
        variance_label = "Symmetric / Classical Restraint"
        radius = {"--radius-sm": "4px", "--radius-md": "8px", "--radius-lg": "12px", "--radius-pill": "9999px"}
        grid_template = "repeat(12, minmax(0, 1fr))"
    elif variance <= 7:
        variance_label = "Balanced Asymmetric Grid"
        radius = {"--radius-sm": "4px", "--radius-md": "6px", "--radius-lg": "10px", "--radius-pill": "9999px"}
        grid_template = "repeat(12, minmax(0, 1fr))"
    else:
        variance_label = "Bold Architectural / High-Contrast Asymmetry"
        radius = {"--radius-sm": "0px", "--radius-md": "2px", "--radius-lg": "4px", "--radius-pill": "9999px"}
        grid_template = "repeat(12, minmax(0, 1fr))"

    # 3. Motion tokens driven by --motion (1=minimal micro-feedback, 10=choreographed stage transitions)
    if motion <= 3:
        motion_label = "Subtle Micro-Feedback"
        motion_tokens = {
            "--duration-fast": "100ms",
            "--duration-base": "160ms",
            "--duration-slow": "240ms",
            "--stagger-step": "30ms",
            "--ease-out-expo": "cubic-bezier(0.16, 1, 0.3, 1)",
            "--ease-standard": "cubic-bezier(0.2, 0, 0, 1)",
        }
    elif motion <= 7:
        motion_label = "Standard Staggered Arrival & State Morph"
        motion_tokens = {
            "--duration-fast": "140ms",
            "--duration-base": "280ms",
            "--duration-slow": "420ms",
            "--stagger-step": "65ms",
            "--ease-out-expo": "cubic-bezier(0.22, 1, 0.36, 1)",
            "--ease-standard": "cubic-bezier(0.2, 0, 0, 1)",
        }
    else:
        motion_label = "Choreographed Stage & Scroll-Linked Dynamics"
        motion_tokens = {
            "--duration-fast": "160ms",
            "--duration-base": "360ms",
            "--duration-slow": "560ms",
            "--stagger-step": "80ms",
            "--ease-out-expo": "cubic-bezier(0.19, 1, 0.22, 1)",
            "--ease-standard": "cubic-bezier(0.22, 1, 0.36, 1)",
        }

    typo = direction["typography_system"]
    colors = direction["color_system"]

    if mode == "operate":
        font_tokens = {
            "--font-display": f"'{typo['display_face'].split(',')[0].strip()}', system-ui, sans-serif",
            "--font-sans": f"'{typo['body_face'].split(',')[0].strip()}', system-ui, sans-serif",
            "--font-mono": f"'{typo['mono_face'].split(',')[0].strip()}', ui-monospace, monospace",
            "--text-xs": "12px",
            "--text-sm": "13px",
            "--text-base": "14px",
            "--text-lg": "16px",
            "--text-xl": "20px",
            "--text-display": "clamp(1.35rem, 2.2vw, 1.75rem)",
            "--tracking-display": typo["display_tracking"],
            "--leading-display": typo["display_leading"],
            "--leading-body": typo["body_leading"],
            "--measure-body": typo["measure"],
        }
    else:
        font_tokens = {
            "--font-display": f"'{typo['display_face'].split(',')[0].strip()}', system-ui, sans-serif",
            "--font-sans": f"'{typo['body_face'].split(',')[0].strip()}', system-ui, sans-serif",
            "--font-mono": f"'{typo['mono_face'].split(',')[0].strip()}', ui-monospace, monospace",
            "--text-xs": "13px",
            "--text-sm": "14px",
            "--text-base": typo["body_size"],
            "--text-lg": "20px",
            "--text-xl": "clamp(1.5rem, 2.5vw, 2.25rem)",
            "--text-display": "clamp(2.25rem, 4.6vw, 4.25rem)",
            "--tracking-display": typo["display_tracking"],
            "--leading-display": typo["display_leading"],
            "--leading-body": typo["body_leading"],
            "--measure-body": typo["measure"],
        }

    color_tokens = {
        "--bg-ground": colors["ground"],
        "--bg-surface": colors["surface"],
        "--bg-elevated": colors["elevated_surface"],
        "--text-ink": colors["ink"],
        "--text-muted": colors["muted_ink"],
        "--accent-primary": colors["primary_accent"],
        "--accent-on-primary": colors["on_accent"],
        "--border-subtle": colors["border"],
        "--selection-bg": colors["selection_bg"],
        "--selection-fg": colors["selection_fg"],
        "--status-positive": colors["semantic"]["positive"],
        "--status-warning": colors["semantic"]["warning"],
        "--status-danger": colors["semantic"]["danger"],
        "--status-info": colors["semantic"]["info"],
    }

    return {
        "dials": {
            "variance": {"value": variance, "label": variance_label},
            "motion": {"value": motion, "label": motion_label},
            "density": {"value": density, "label": density_label},
        },
        "css_variables": {
            "colors": color_tokens,
            "typography": font_tokens,
            "spacing": space,
            "radius": radius,
            "motion": motion_tokens,
            "grid_template_columns": grid_template,
        },
    }


def score_and_deal_directions(
    mode: str,
    query: str,
    deal_count: int = 3,
    variance: int = 6,
    seed: int | None = None,
    forced_direction_id: str | None = None,
) -> list[dict[str, Any]]:
    """BM25-inspired lexical + mode affinity + variance dial scoring that deals `deal_count` distinct directions."""
    if forced_direction_id:
        for d in DIRECTIONS_LIBRARY:
            if d["id"] == forced_direction_id:
                return [d]

    query_tokens = _tokenize(query)
    rng = random.Random(seed if seed is not None else 42)

    # Compute IDF across directions
    N = len(DIRECTIONS_LIBRARY)
    df: dict[str, int] = {}
    doc_tokens_map: dict[str, list[str]] = {}
    for d in DIRECTIONS_LIBRARY:
        blob = " ".join([
            d["id"],
            d["name"],
            " ".join(d["keywords"]),
            d["composition_philosophy"],
            " ".join(d["mode_affinity"]),
        ])
        toks = _tokenize(blob)
        doc_tokens_map[d["id"]] = toks
        for tok in set(toks):
            df[tok] = df.get(tok, 0) + 1

    avgdl = sum(len(v) for v in doc_tokens_map.values()) / max(1, N)
    k1 = 1.5
    b = 0.75

    scored: list[tuple[float, dict[str, Any]]] = []
    for d in DIRECTIONS_LIBRARY:
        toks = doc_tokens_map[d["id"]]
        dl = len(toks)
        tf_map: dict[str, int] = {}
        for t in toks:
            tf_map[t] = tf_map.get(t, 0) + 1

        bm25 = 0.0
        for qt in query_tokens:
            # Exact or prefix match
            tf = tf_map.get(qt, 0)
            if tf == 0:
                tf = sum(1 for k in d["keywords"] if k.startswith(qt) or qt.startswith(k))
            if tf > 0:
                doc_freq = df.get(qt, 1)
                idf = math.log(1.0 + (N - doc_freq + 0.5) / (doc_freq + 0.5))
                bm25 += idf * ((tf * (k1 + 1.0)) / (tf + k1 * (1.0 - b + b * (dl / avgdl))))

        # Mode affinity boost
        if d["mode_affinity"][0] == mode:
            mode_score = 6.0
        elif mode in d["mode_affinity"]:
            mode_score = 4.0
        else:
            mode_score = 0.5

        # Variance dial affinity
        vmin, vmax = d["variance_band"]
        if vmin <= variance <= vmax:
            var_score = 2.5
        else:
            dist = min(abs(variance - vmin), abs(variance - vmax))
            var_score = max(0.0, 2.0 - 0.4 * dist)

        # Small deterministic tie-breaker jitter from seed
        jitter = rng.uniform(0.0, 0.35)
        total = mode_score + bm25 + var_score + jitter
        scored.append((round(total, 3), d))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Select top `deal_count` ensuring distinct themes/composition families where possible
    dealt: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    used_DisplayFaces: set[str] = set()

    for sc, d in scored:
        if len(dealt) >= deal_count:
            break
        face = d["typography_system"]["display_face"]
        if face in used_DisplayFaces and len(scored) - len(used_ids) > (deal_count - len(dealt)):
            continue
        dealt.append({**d, "match_score": sc})
        used_ids.add(d["id"])
        used_DisplayFaces.add(face)

    # Fill remaining if needed
    for sc, d in scored:
        if len(dealt) >= deal_count:
            break
        if d["id"] not in used_ids:
            dealt.append({**d, "match_score": sc})
            used_ids.add(d["id"])

    return dealt


def render_css_block(token_bundle: dict[str, Any], direction: dict[str, Any]) -> str:
    """Render ready-to-paste CSS `:root` tokens + Browser Surfaces (`impeccable` craft floor)."""
    cv = token_bundle["css_variables"]
    lines = [direction["typography_system"]["google_fonts_import"], "", ":root {"]
    for group_name in ("colors", "typography", "spacing", "radius", "motion"):
        lines.append(f"  /* {group_name.upper()} */")
        for k, v in cv[group_name].items():
            lines.append(f"  {k}: {v};")
    lines.append("}")
    lines.append("")
    lines.append("/* BROWSER SURFACES & CRAFT FLOOR (Mandatory across all viewports) */")
    lines.append("::selection { background: var(--selection-bg); color: var(--selection-fg); }")
    lines.append(":focus-visible { outline: 2px solid var(--accent-primary); outline-offset: 2px; }")
    lines.append("table, .tabular, [data-metric], [data-num], .kpi-value { font-variant-numeric: tabular-nums; }")
    lines.append("h1, h2, h3 { text-wrap: balance; letter-spacing: var(--tracking-display); line-height: var(--leading-display); }")
    lines.append("* { scrollbar-width: thin; scrollbar-color: var(--border-subtle) var(--bg-ground); }")
    lines.append("@media (prefers-reduced-motion: reduce) {")
    lines.append("  *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; }")
    lines.append("}")
    return "\n".join(lines)


def format_design_md(
    project_name: str,
    mode: str,
    query: str,
    dealt: list[dict[str, Any]],
    primary_bundle: dict[str, Any],
) -> str:
    """Generate the Master `DESIGN.md` combining `impeccable`, `taste-skill`, and `ui-ux-pro-max`."""
    primary = dealt[0]
    mode_info = SURFACE_MODES[mode]
    dials = primary_bundle["dials"]
    css_block = render_css_block(primary_bundle, primary)

    lines = [
        f"# {project_name} — Master Design System & Visual Architecture (`DESIGN.md`)",
        "",
        f"- **Surface Mode:** `{mode}` — {mode_info['name']}",
        f"- **Surface Goal:** {mode_info['goal']}",
        f"- **Domain Query:** `{query}`",
        f"- **Design Dials:** Variance `{dials['variance']['value']}/10` ({dials['variance']['label']}) · "
        f"Motion `{dials['motion']['value']}/10` ({dials['motion']['label']}) · "
        f"Density `{dials['density']['value']}/10` ({dials['density']['label']})",
        f"- **Primary Dealt Direction:** `{primary['id']}` — **{primary['name']}**",
        "",
        "---",
        "",
        "## 1. Dealt Art Directions (3 Empirical Candidates)",
        "",
    ]

    for idx, d in enumerate(dealt, start=1):
        c = d["color_system"]
        t = d["typography_system"]
        lines.extend([
            f"### Direction {idx}: `{d['id']}` — {d['name']} (Theme: `{c['theme']}`)",
            f"- **Composition Philosophy:** {d['composition_philosophy']}",
            f"- **Hero Blueprint:** {d['hero_blueprint']}",
            f"- **Typography Pairing:** Display `{t['display_face']}` · Body `{t['body_face']}` · Mono `{t['mono_face']}` (Ratio `{t['headline_to_body_ratio']}x`, Tracking `{t['display_tracking']}`, Measure `{t['measure']}`)",
            f"- **Palette Tokens:** Ground `{c['ground']}` · Surface `{c['surface']}` · Ink `{c['ink']}` · Muted `{c['muted_ink']}` · Accent `{c['primary_accent']}` · Border `{c['border']}`",
            f"- **Section Sequence (Non-Repeating Archetypes):** " + " $\\rightarrow$ ".join(
                f"`{s['role']}` (*{s['archetype']}*)" for s in d["section_blueprints"]
            ),
            f"- **Signature Motion:** **{d['signature_motion']['name']}** (`{d['signature_motion']['duration']}`, `{d['signature_motion']['easing']}`) — {d['signature_motion']['description']}",
            f"- **The Idea Prompt:** *{d['idea_prompt']}*",
            f"- **One Live Thing Archetype:** {d['live_thing_archetype']}",
            "",
        ])

    lines.extend([
        "---",
        "",
        "## 2. Master CSS Custom Property Tokens & Browser Surfaces",
        "",
        "```css",
        css_block,
        "```",
        "",
        "---",
        "",
        "## 3. Craft Floor & Anti-Slop House Rules (Enforced by `web_ui_validator.py`)",
        "",
        f"- **Typography Floor:** {mode_info['typography_floor']}",
        "- **Browser Surfaces:** Custom `::selection`, high-contrast `:focus-visible` rings, themed thin scrollbars, and `font-variant-numeric: tabular-nums` on every table cell, counter, metric, and timestamp.",
        "- **Hard Bans (`FAIL` at Gate):**",
        "  1. **Zero >2-Line Headlines (`headline-lines`):** Every `h1`–`h3` in `persuade`/`experience` mode must fit in $\\le 2$ lines at `1440px`, `768px`, and `390px`.",
        "  2. **Zero Horizontal Overflow (`horizontal-overflow`):** `scrollWidth <= innerWidth + 2` at `1440x900`, `768x1024`, and `390x844`.",
        "  3. **Zero Eyebrow Kickers (`slop-eyebrow`):** No uppercase/pill kicker labels stacked directly above `h1`/`h2` headings in `persuade` mode.",
        "  4. **Zero Gradient Text (`slop-gradient-text`):** Never use `-webkit-background-clip: text` with transparent text fill.",
        "  5. **Zero Side-Stripe Borders (`slop-side-stripe`):** No `border-left-width > 1px` accent stripes on cards or callouts.",
        "  6. **Zero Unrequested AI Palettes (`slop-ai-palette`):** Avoid default indigo/violet (`#6366f1`, hue `244..295`) and Assistant yellow-cream + terracotta pairings.",
        "  7. **Zero Reduced-Motion Hidden Content (`reduced-motion-hidden`):** Under `prefers-reduced-motion: reduce`, 100% of text and controls must be immediately visible (`opacity: 1`).",
        "",
    ])
    return "\n".join(lines)


def format_surface_md(
    project_name: str,
    page_slug: str,
    mode: str,
    query: str,
    dealt: list[dict[str, Any]],
    primary_bundle: dict[str, Any],
) -> str:
    """Generate `.swarm/surfaces/<page>.md` surface brief."""
    primary = dealt[0]
    mode_info = SURFACE_MODES[mode]
    lines = [
        f"# Surface Brief: `{page_slug}` ({project_name})",
        "",
        f"- **Surface Mode:** `{mode}` ({mode_info['name']})",
        f"- **Query / Brief:** `{query}`",
        f"- **Primary Direction:** `{primary['id']}` — **{primary['name']}**",
        f"- **Alternative Directions Dealt:** " + ", ".join(f"`{d['id']}` ({d['name']})" for d in dealt[1:]),
        "",
        "## 1. Subject Inventory (8–12 Unique Domain Facts)",
        "> Populate/verify these specific domain truths from the project codebase or `deep_research_report.md` (never generic category filler):",
        "1. **Core Engine / Artifact Name & Meaning:** Verified domain terminology and exact model/module identifiers.",
        "2. **Exact Quantitative Benchmarks & Units:** Real latency (`ms`), throughput (`tok/s` or `ops/s`), memory footprint (`MB`/`GB`), or accuracy metrics.",
        "3. **Architectural Constraint Turned Advantage:** The specific technical constraint (e.g., local-only execution, zero-dependency binary, deterministic lock) that differentiates this system.",
        "4. **Primary Input Material:** Exact file formats, query syntax, or data payloads the user feeds in.",
        "5. **Observable Output Artifact:** The concrete table, canvas render, diff, or report produced.",
        "6. **Key Workflow Ritual / Sequence:** The 3-5 step operational flow from input to verified outcome.",
        "7. **Domain Nomenclature:** Authentic column headers, status codes, and unit labels.",
        "8. **Verification Command / Proof:** Exact CLI or interactive check that proves the output is real.",
        "",
        "## 2. The Idea Sentence & Competitor Swap Test",
        f"- **Idea Sentence Template:** *\"{primary['idea_prompt']}\"*",
        "- **Competitor Swap Test:** If you substitute a generic competitor's name and the sentence still applies unchanged, the idea is too generic — anchor it to the specific artifact and metrics in Section 1.",
        "",
        "## 3. One Live Thing Specification",
        f"- **Interactive Device:** {primary['live_thing_archetype']}",
        "- **State Commitment:** Must mutate real client-side domain state in JavaScript and dynamically re-render the DOM, `<svg>`, or `<canvas>` with coherent numbers (`tabular-nums`).",
        "- **Responsive & Keyboard Contract:** Operable with keyboard (`Tab`/`Enter`/`Arrow` keys) and thumb-friendly (`>= 44px` hit targets) at `390px` mobile width.",
        "",
        "## 4. Section Blueprint Sequence",
    ]
    for idx, sec in enumerate(primary["section_blueprints"], start=1):
        lines.append(f"{idx}. **`{sec['role']}`** — Archetype: `{sec['archetype']}` — {sec['geometry']}")
    lines.append("")
    return "\n".join(lines)


def persist_design_context(
    output_dir: str,
    project_name: str,
    page_slug: str,
    mode: str,
    query: str,
    dealt: list[dict[str, Any]],
    primary_bundle: dict[str, Any],
) -> dict[str, Any]:
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)

    design_md_content = format_design_md(project_name, mode, query, dealt, primary_bundle)
    design_md_path = root / "DESIGN.md"
    design_md_path.write_text(design_md_content, encoding="utf-8")

    created_files = [str(design_md_path)]

    # Also write `.swarm/surfaces/<page>.md`
    surfaces_dir = root / ".swarm" / "surfaces"
    surfaces_dir.mkdir(parents=True, exist_ok=True)
    surface_path = surfaces_dir / f"{page_slug}.md"
    surface_content = format_surface_md(project_name, page_slug, mode, query, dealt, primary_bundle)
    surface_path.write_text(surface_content, encoding="utf-8")
    created_files.append(str(surface_path))

    # Save machine-readable direction sheet in `.swarm/surfaces/<page>.direction.json`
    direction_json_path = surfaces_dir / f"{page_slug}.direction.json"
    direction_json_path.write_text(
        json.dumps(
            {
                "project_name": project_name,
                "page": page_slug,
                "mode": mode,
                "query": query,
                "dials": primary_bundle["dials"],
                "css_variables": primary_bundle["css_variables"],
                "dealt_directions": dealt,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    created_files.append(str(direction_json_path))

    return {
        "status": "persisted",
        "design_md": str(design_md_path),
        "surface_md": str(surface_path),
        "direction_json": str(direction_json_path),
        "created_files": created_files,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Deal empirical UI/UX Art Directions, compute Design Dial CSS tokens, and persist DESIGN.md + .swarm/surfaces/<page>.md"
    )
    ap.add_argument("--mode", choices=["persuade", "operate", "read", "experience"], help="Surface mode (persuade, operate, read, experience)")
    ap.add_argument("--query", default="", help="Product type, domain, and style keywords")
    ap.add_argument("--deal", type=int, default=3, help="Number of distinct directions to deal (default: 3)")
    ap.add_argument("--direction", help="Lock a specific direction ID from the library")
    ap.add_argument("--variance", type=int, default=6, help="Layout/geometry variance dial 1-10 (default: 6)")
    ap.add_argument("--motion", type=int, default=6, help="Motion choreography dial 1-10 (default: 6)")
    ap.add_argument("--density", type=int, default=5, help="Visual & spacing density dial 1-10 (default: 5)")
    ap.add_argument("--seed", type=int, default=42, help="Deterministic seed for direction tie-breaking")
    ap.add_argument("--persist", action="store_true", help="Write DESIGN.md and .swarm/surfaces/<page>.md")
    ap.add_argument("--output-dir", default=".", help="Project root directory for --persist (default: current directory)")
    ap.add_argument("-p", "--project-name", default="", help="Project name for DESIGN.md header")
    ap.add_argument("--page", default="main", help="Surface page slug for .swarm/surfaces/<page>.md (default: main)")
    ap.add_argument("--list", action="store_true", help="List all 18 curated art directions in the library")
    ap.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = ap.parse_args()

    if args.list:
        for d in DIRECTIONS_LIBRARY:
            modes = ",".join(d["mode_affinity"])
            print(f"{d['id']:24s} [{modes:20s}] {d['name']}")
        sys.exit(0)

    resolved_mode = infer_mode(args.query, args.mode)
    deal_n = max(1, min(len(DIRECTIONS_LIBRARY), args.deal))
    dealt = score_and_deal_directions(
        mode=resolved_mode,
        query=args.query,
        deal_count=deal_n,
        variance=args.variance,
        seed=args.seed,
        forced_direction_id=args.direction,
    )

    # Enrich each dealt direction with its computed token table for the requested dials
    enriched_dealt: list[dict[str, Any]] = []
    for d in dealt:
        bundle = compute_dial_tokens(resolved_mode, args.variance, args.motion, args.density, d)
        enriched_dealt.append({
            **d,
            "dial_tokens": bundle["css_variables"],
            "css_root_snippet": render_css_block(bundle, d),
        })

    primary_bundle = compute_dial_tokens(resolved_mode, args.variance, args.motion, args.density, dealt[0])
    project_name = args.project_name.strip() or (args.query.strip().title() if args.query.strip() else "Project")
    page_slug = re.sub(r"[^a-z0-9_-]+", "-", args.page.strip().lower()).strip("-") or "main"

    persistence_info = None
    if args.persist:
        persistence_info = persist_design_context(
            output_dir=args.output_dir,
            project_name=project_name,
            page_slug=page_slug,
            mode=resolved_mode,
            query=args.query,
            dealt=dealt,
            primary_bundle=primary_bundle,
        )

    payload = {
        "project_name": project_name,
        "mode": resolved_mode,
        "mode_details": SURFACE_MODES[resolved_mode],
        "query": args.query,
        "dials": primary_bundle["dials"],
        "dealt_count": len(enriched_dealt),
        "directions": enriched_dealt,
        "persistence": persistence_info,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
        sys.exit(0)

    # Human-readable report
    print("================================================================================")
    print(f"UI/UX ART DIRECTION DEALER — MODE: {resolved_mode.upper()} | QUERY: \"{args.query}\"")
    print(
        f"DIALS: Variance {args.variance}/10 ({primary_bundle['dials']['variance']['label']}) · "
        f"Motion {args.motion}/10 ({primary_bundle['dials']['motion']['label']}) · "
        f"Density {args.density}/10 ({primary_bundle['dials']['density']['label']})"
    )
    print("================================================================================\n")

    for idx, d in enumerate(enriched_dealt, start=1):
        c = d["color_system"]
        t = d["typography_system"]
        print(f"[{idx}] `{d['id']}` — {d['name']} (Theme: {c['theme'].upper()}, Score: {d.get('match_score', 0)})")
        print(f"    Modes:       {', '.join(d['mode_affinity'])}")
        print(f"    Philosophy:  {d['composition_philosophy']}")
        print(f"    Hero:        {d['hero_blueprint']}")
        print(
            f"    Typography:  Display: {t['display_face']} | Body: {t['body_face']} | Mono: {t['mono_face']} "
            f"(Ratio {t['headline_to_body_ratio']}x, Tracking {t['display_tracking']}, Measure {t['measure']})"
        )
        print(
            f"    Palette:     Ground {c['ground']} | Surface {c['surface']} | Ink {c['ink']} | "
            f"Muted {c['muted_ink']} | Accent {c['primary_accent']} | Border {c['border']}"
        )
        print(
            "    Sections:    "
            + " -> ".join(f"{s['role']} ({s['archetype']})" for s in d["section_blueprints"])
        )
        print(f"    Motion:      {d['signature_motion']['name']} ({d['signature_motion']['duration']}, {d['signature_motion']['easing']})")
        print(f"    Idea Prompt: {d['idea_prompt']}")
        print(f"    Live Thing:  {d['live_thing_archetype']}\n")

    print("--- COMPUTED CSS CUSTOM PROPERTIES (DIRECTION 1 + DIALS) ---")
    print(enriched_dealt[0]["css_root_snippet"])
    print("")

    if persistence_info:
        print("--- PERSISTED DESIGN CONTEXT ---")
        for fpath in persistence_info["created_files"]:
            print(f"  + {fpath}")


if __name__ == "__main__":
    main()
