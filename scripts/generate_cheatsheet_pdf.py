#!/usr/bin/env python3
"""Generate a print-ready, 2-page A4 PDF Cheat Sheet (SWARM_CHEATSHEET.pdf) for agent-swarm.

Designed to be printed out (2 pages / front-and-back A4) and kept next to the desk
for instant lookup of which skill to use for what, calling modes, workflow graph,
scoring rules, and `.swarm/` artifact paths.
"""

from __future__ import annotations

import pathlib
import weasyprint

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Autonomous Evolutionary Agent Swarm — Desk Reference Cheat Sheet</title>
<style>
  @page {
    size: A4 portrait;
    margin: 6mm 8mm 6mm 8mm;
  }

  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  body {
    font-family: "Inter", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    color: #0f172a;
    background: #ffffff;
    font-size: 7.2pt;
    line-height: 1.24;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }

  code, .cmd {
    font-family: "JetBrains Mono", "Fira Code", "DejaVu Sans Mono", "Courier New", monospace;
    font-size: 6.7pt;
    background: #f1f5f9;
    color: #0f172a;
    padding: 0.5pt 2.5pt;
    border-radius: 2pt;
    border: 0.4pt solid #cbd5e1;
    font-weight: 600;
  }

  .cmd-primary {
    background: #ecfdf5;
    color: #065f46;
    border-color: #6ee7b7;
  }

  .cmd-swarm {
    background: #eff6ff;
    color: #1e40af;
    border-color: #93c5fd;
  }

  .cmd-util {
    background: #fef3c7;
    color: #92400e;
    border-color: #fcd34d;
  }

  .path {
    font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
    font-size: 6.3pt;
    color: #334155;
    background: #f8fafc;
    padding: 0.3pt 2pt;
    border-radius: 2pt;
    border: 0.4pt solid #e2e8f0;
  }

  /* Header Banner */
  .header-banner {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    color: #ffffff;
    padding: 5.5pt 9pt;
    border-radius: 4.5pt;
    margin-bottom: 4.5pt;
    width: 100%;
  }

  .header-table {
    width: 100%;
    border-collapse: collapse;
  }

  .header-title h1 {
    font-size: 11.8pt;
    font-weight: 800;
    letter-spacing: -0.2pt;
    color: #f8fafc;
  }

  .header-title p {
    font-size: 6.9pt;
    color: #94a3b8;
    margin-top: 1pt;
  }

  .master-pill {
    background: rgba(255, 255, 255, 0.08);
    border: 0.7pt solid rgba(255, 255, 255, 0.22);
    border-radius: 3.5pt;
    padding: 2.8pt 6pt;
    text-align: left;
    display: inline-block;
    margin-left: 4pt;
  }

  .master-pill.phase-a {
    border-left: 2.8pt solid #10b981;
  }

  .master-pill.phase-b {
    border-left: 2.8pt solid #3b82f6;
  }

  .master-pill .pill-cmd {
    font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
    font-size: 7.8pt;
    font-weight: 800;
  }

  .master-pill.phase-a .pill-cmd { color: #34d399; }
  .master-pill.phase-b .pill-cmd { color: #60a5fa; }

  .master-pill .pill-sub {
    font-size: 6.1pt;
    color: #cbd5e1;
    display: block;
  }

  /* Section Headings */
  .section-hdr {
    width: 100%;
    padding: 2.2pt 6pt;
    border-radius: 3pt;
    margin-top: 3.5pt;
    margin-bottom: 2.5pt;
    font-weight: 800;
    font-size: 7.5pt;
    letter-spacing: 0.15pt;
    text-transform: uppercase;
  }

  .section-hdr .sub {
    font-size: 6.3pt;
    font-weight: 600;
    text-transform: none;
    opacity: 0.88;
    margin-left: 6pt;
  }

  .section-hdr.amber {
    background: #fffbeb;
    color: #92400e;
    border-left: 3pt solid #f59e0b;
    border-top: 0.5pt solid #fde68a;
    border-right: 0.5pt solid #fde68a;
    border-bottom: 0.5pt solid #fde68a;
  }

  .section-hdr.teal {
    background: #ecfdf5;
    color: #065f46;
    border-left: 3pt solid #059669;
    border-top: 0.5pt solid #a7f3d0;
    border-right: 0.5pt solid #a7f3d0;
    border-bottom: 0.5pt solid #a7f3d0;
  }

  .section-hdr.blue {
    background: #eff6ff;
    color: #1e40af;
    border-left: 3pt solid #2563eb;
    border-top: 0.5pt solid #bfdbfe;
    border-right: 0.5pt solid #bfdbfe;
    border-bottom: 0.5pt solid #bfdbfe;
  }

  .section-hdr.purple {
    background: #f5f3ff;
    color: #5b21b6;
    border-left: 3pt solid #7c3aed;
    border-top: 0.5pt solid #ddd6fe;
    border-right: 0.5pt solid #ddd6fe;
    border-bottom: 0.5pt solid #ddd6fe;
  }

  .section-hdr.slate {
    background: #f1f5f9;
    color: #1e293b;
    border-left: 3pt solid #475569;
    border-top: 0.5pt solid #cbd5e1;
    border-right: 0.5pt solid #cbd5e1;
    border-bottom: 0.5pt solid #cbd5e1;
  }

  /* Quick Decision Table (2-Column True Table for WeasyPrint) */
  table.decision-table {
    width: 100%;
    border-collapse: collapse;
    background: #fffbeb;
    border: 0.6pt solid #fde68a;
    border-radius: 3.5pt;
    margin-bottom: 3pt;
  }

  table.decision-table td {
    padding: 1.8pt 4.5pt;
    border-bottom: 0.4pt dashed #fcd34d;
    font-size: 6.75pt;
    vertical-align: middle;
  }

  table.decision-table tr:last-child td {
    border-bottom: none;
  }

  table.decision-table td.q-col {
    color: #451a03;
    font-weight: 600;
    width: 31%;
  }

  table.decision-table td.a-col {
    text-align: right;
    width: 19%;
    white-space: nowrap;
    border-right: 0.6pt solid #fde68a;
    padding-right: 5pt;
  }

  table.decision-table td.a-col-right {
    text-align: right;
    width: 19%;
    white-space: nowrap;
  }

  /* Workflow SVG Box */
  .workflow-box {
    border: 0.7pt solid #cbd5e1;
    border-radius: 4pt;
    background: #f8fafc;
    padding: 2.5pt 3.5pt;
    margin-bottom: 3pt;
    text-align: center;
  }

  /* Skill Tables */
  table.skill-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 2.5pt;
    font-size: 6.75pt;
  }

  table.skill-table th {
    background: #1e293b;
    color: #ffffff;
    font-weight: 700;
    text-align: left;
    padding: 2.2pt 4pt;
    font-size: 6.4pt;
    text-transform: uppercase;
    letter-spacing: 0.15pt;
  }

  table.skill-table.phase-a th { background: #065f46; }
  table.skill-table.phase-b th { background: #1e3a8a; }
  table.skill-table.util-table th { background: #4c1d95; }

  table.skill-table td {
    padding: 1.75pt 4pt;
    border-bottom: 0.45pt solid #e2e8f0;
    vertical-align: top;
  }

  table.skill-table tr:nth-child(even) td {
    background: #f8fafc;
  }

  .mode-tag {
    display: inline-block;
    font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
    font-size: 5.9pt;
    background: #e2e8f0;
    color: #1e293b;
    padding: 0.2pt 2pt;
    border-radius: 1.8pt;
    margin-top: 1pt;
    margin-right: 1.2pt;
  }

  .when-to-use {
    font-weight: 700;
    color: #0f172a;
  }

  .page-break {
    page-break-before: always;
  }

  /* Bottom 2-Column Split Table on Page 2 */
  table.bottom-layout {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin-top: 2.5pt;
  }

  table.bottom-layout td.split-cell {
    vertical-align: top;
    width: 49%;
  }

  table.bottom-layout td.split-spacer {
    width: 2%;
  }

  .info-card {
    border: 0.7pt solid #cbd5e1;
    border-radius: 3.5pt;
    background: #f8fafc;
    padding: 4pt 5.5pt;
  }

  .info-card h3 {
    font-size: 7.2pt;
    font-weight: 800;
    color: #0f172a;
    margin-bottom: 2.5pt;
    border-bottom: 0.6pt solid #cbd5e1;
    padding-bottom: 1.5pt;
    text-transform: uppercase;
  }

  .rule-list {
    list-style: none;
    font-size: 6.55pt;
    line-height: 1.23;
  }

  .rule-list li {
    margin-bottom: 1.8pt;
    padding-left: 5.5pt;
    position: relative;
  }

  .rule-list li::before {
    content: "•";
    position: absolute;
    left: 0;
    color: #2563eb;
    font-weight: bold;
  }

  .score-pill {
    display: inline-block;
    font-family: "JetBrains Mono", monospace;
    font-size: 6.0pt;
    font-weight: 700;
    padding: 0.2pt 2pt;
    border-radius: 1.8pt;
  }

  .score-pass { background: #dcfce7; color: #166534; }
  .score-deduct { background: #fee2e2; color: #991b1b; }
  .score-base { background: #dbeafe; color: #1e40af; }

  .file-tree {
    font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
    font-size: 6.05pt;
    line-height: 1.25;
    color: #1e293b;
  }

  .file-tree .ft-dir {
    font-weight: 700;
    color: #0f172a;
  }

  .file-tree .ft-desc {
    font-family: "Inter", "Segoe UI", Arial, sans-serif;
    color: #475569;
    font-size: 6.0pt;
  }

  .footer-bar {
    margin-top: 3pt;
    padding-top: 2pt;
    border-top: 0.5pt solid #cbd5e1;
    font-size: 6.2pt;
    color: #64748b;
    width: 100%;
  }

  .footer-bar .right {
    float: right;
  }
</style>
</head>
<body>

<!-- ==================== PAGE 1 ==================== -->
<div class="header-banner">
  <table class="header-table">
    <tr>
      <td class="header-title" style="width: 62%;">
        <h1>AUTONOMOUS EVOLUTIONARY AGENT SWARM (v2.7)</h1>
        <p>Printable Desk Reference — Product Discovery &amp; Planning (Phase A), Goal-Loop Outcome Engine &amp; Swarm Loop (Phase B)</p>
      </td>
      <td style="width: 38%; text-align: right; vertical-align: middle;">
        <div class="master-pill phase-a">
          <span class="pill-cmd">/product-discovery</span>
          <span class="pill-sub">Phase A Master (Scout &amp; Plan)</span>
        </div>
        <div class="master-pill phase-b">
          <span class="pill-cmd">/invoke-swarm</span>
          <span class="pill-sub">Phase B Master (Until Goal Met)</span>
        </div>
      </td>
    </tr>
  </table>
</div>

<!-- 1. QUICK DECISION MATRIX (2-COLUMN COMPACT TABLE) -->
<div class="section-hdr amber">
  <span>1. Quick Decision Guide — "Which Skill Do I Type Right Now?"</span>
  <span class="sub">Pick by your immediate goal; every skill works standalone or via /product-discovery &amp; /invoke-swarm</span>
</div>
<table class="decision-table">
  <tr>
    <td class="q-col">Starting a brand-new product/idea (Full Phase A)?</td>
    <td class="a-col"><code class="cmd cmd-primary">/product-discovery</code></td>
    <td class="q-col" style="padding-left: 6pt;">Ready to build &amp; evolve code autonomously (3 Epochs)?</td>
    <td class="a-col-right"><code class="cmd cmd-swarm">/invoke-swarm</code></td>
  </tr>
  <tr>
    <td class="q-col">Backend / CLI / SDK product plan (skip HTML UI mockups)?</td>
    <td class="a-col"><code class="cmd cmd-primary">/product-discovery no-ui</code></td>
    <td class="q-col" style="padding-left: 6pt;">Just 1 implementation wave + merge (no 3-epoch loop)?</td>
    <td class="a-col-right"><code class="cmd cmd-swarm">/invoke-swarm single-epoch</code></td>
  </tr>
  <tr>
    <td class="q-col">Search my Zotero PDFs + high-impact papers + web SOTA?</td>
    <td class="a-col"><code class="cmd cmd-primary">/deep-research</code></td>
    <td class="q-col" style="padding-left: 6pt;">Freeze shared types + mine brownfield invariants?</td>
    <td class="a-col-right"><code class="cmd cmd-swarm">/contract-lock</code></td>
  </tr>
  <tr>
    <td class="q-col">Competitors, GitHub OSS parity, VoC pain &amp; TAM/SAM/SOM?</td>
    <td class="a-col"><code class="cmd cmd-primary">/market-research</code></td>
    <td class="q-col" style="padding-left: 6pt;">Zero-trust code review, silent-failure &amp; pass^k gate?</td>
    <td class="a-col-right"><code class="cmd cmd-swarm">/discriminator-gate</code></td>
  </tr>
  <tr>
    <td class="q-col">Open-Core vs. B2B Enterprise licensing, COGS &amp; kill-risks?</td>
    <td class="a-col"><code class="cmd cmd-primary">/commercial-strategy</code></td>
    <td class="q-col" style="padding-left: 6pt;">Run Rigor, Safety &amp; Innovation audit on existing repo?</td>
    <td class="a-col-right"><code class="cmd cmd-swarm">/triad-audit</code></td>
  </tr>
  <tr>
    <td class="q-col">Co-brainstorm features, Search-First Adopt &amp; architecture?</td>
    <td class="a-col"><code class="cmd cmd-primary">/coop-brainstorm</code></td>
    <td class="q-col" style="padding-left: 6pt;">Scan secrets, prompt-injection, Unicode &amp; MCP tax?</td>
    <td class="a-col-right"><code class="cmd cmd-swarm">/agent-shield</code></td>
  </tr>
  <tr>
    <td class="q-col">Generate 3 interactive single-file HTML/CSS/JS UI mockups?</td>
    <td class="a-col"><code class="cmd cmd-primary">/ui-ux-design</code></td>
    <td class="q-col" style="padding-left: 6pt;">Turn paper math/equations into verified code + unit tests?</td>
    <td class="a-col-right"><code class="cmd cmd-primary">/paper-to-code</code></td>
  </tr>
</table>

<!-- 2. VISUAL WORKFLOW GRAPH (SVG) -->
<div class="section-hdr slate">
  <span>2. End-to-End Architecture &amp; Execution Flow (Phase A &rarr; Phase B)</span>
  <span class="sub">Phase A (/product-discovery) is on-demand only; Phase B (/invoke-swarm) runs Steps 0.5 &rarr; 7 autonomously</span>
</div>
<div class="workflow-box">
  <svg viewBox="0 0 960 296" width="100%" height="auto" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <marker id="arrow-teal" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 1 L 9 5 L 0 9 z" fill="#059669"/>
      </marker>
      <marker id="arrow-blue" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 1 L 9 5 L 0 9 z" fill="#2563eb"/>
      </marker>
      <marker id="arrow-red" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 1 L 9 5 L 0 9 z" fill="#dc2626"/>
      </marker>
      <marker id="arrow-purple" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 1 L 9 5 L 0 9 z" fill="#7c3aed"/>
      </marker>
    </defs>

    <!-- PHASE A CONTAINER (TOP) -->
    <rect x="4" y="3" width="952" height="112" rx="6" fill="#ecfdf5" stroke="#10b981" stroke-width="1.5"/>
    <rect x="4" y="3" width="952" height="19" rx="5" fill="#059669"/>
    <text x="14" y="16" fill="#ffffff" font-family="Inter, Arial, sans-serif" font-size="9.8" font-weight="bold">PHASE A: INITIAL DISCOVERY, POTENTIAL SCOUTING &amp; PRODUCT PLANNING (/product-discovery — Human-in-the-Loop)</text>

    <!-- Wave 1 Box -->
    <rect x="14" y="27" width="335" height="82" rx="4" fill="#ffffff" stroke="#34d399" stroke-width="1.2"/>
    <text x="22" y="39.5" fill="#065f46" font-family="Inter, Arial, sans-serif" font-size="9.2" font-weight="bold">WAVE 1: Parallel Intelligence Swarm (Prompt Defense)</text>
    <text x="22" y="52.5" fill="#0f172a" font-family="DejaVu Sans Mono, monospace" font-size="8.3" font-weight="bold">1. /deep-research</text>
    <text x="132" y="52.5" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="8.0">Zotero DB + OpenAlex/arXiv + SOTA</text>
    <text x="22" y="65" fill="#0f172a" font-family="DejaVu Sans Mono, monospace" font-size="8.3" font-weight="bold">2. /market-research</text>
    <text x="132" y="65" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="8.0">3 Agents: Competitors, VoC, TAM/SAM</text>
    <text x="22" y="77.5" fill="#0f172a" font-family="DejaVu Sans Mono, monospace" font-size="8.3" font-weight="bold">3. /commercial-strategy</text>
    <text x="148" y="77.5" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="8.0">2 Agents: Open-Core/B2B, COGS, Moat</text>
    <text x="22" y="90" fill="#0f172a" font-family="DejaVu Sans Mono, monospace" font-size="8.3" font-weight="bold">4. /paper-to-code</text>
    <text x="132" y="90" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="8.0">(Opt) Zotero/arXiv Math &rarr; Code + Tests</text>
    <text x="22" y="103" fill="#047857" font-family="DejaVu Sans Mono, monospace" font-size="7.6">&rarr; .swarm/blueprint/{*_report.md, market_dashboard.html}</text>

    <!-- Arrow Wave 1 -> Checkpoint 1 -->
    <line x1="349" y1="68" x2="375" y2="68" stroke="#059669" stroke-width="1.8" marker-end="url(#arrow-teal)"/>

    <!-- Checkpoint 1 Box -->
    <rect x="378" y="27" width="275" height="82" rx="4" fill="#ffffff" stroke="#059669" stroke-width="1.4"/>
    <rect x="562" y="30" width="84" height="12.5" rx="3" fill="#fef3c7" stroke="#f59e0b" stroke-width="0.8"/>
    <text x="567" y="39" fill="#92400e" font-family="Inter, Arial, sans-serif" font-size="7.3" font-weight="bold">CHECKPOINT 1</text>
    <text x="386" y="39.5" fill="#065f46" font-family="DejaVu Sans Mono, monospace" font-size="9.2" font-weight="bold">5. /coop-brainstorm</text>
    <text x="386" y="53.5" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="8.0">&bull; Sufficiency Gate (&ge;8.5/10 &rarr; ALREADY OPTIMAL)</text>
    <text x="386" y="66" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="8.0">&bull; Search-First Adopt/Extend vs. Build Custom</text>
    <text x="386" y="78.5" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="8.0">&bull; 3-Epoch Features [OSS/Pro/B2B] &amp; Arch Option 0</text>
    <text x="386" y="91" fill="#b45309" font-family="Inter, Arial, sans-serif" font-size="7.8" font-weight="bold">Pauses via ask_question for User Co-Design</text>
    <text x="386" y="103" fill="#047857" font-family="DejaVu Sans Mono, monospace" font-size="7.6">&rarr; brainstorm_blueprint.md &amp; docs/ARCHITECTURE.md</text>

    <!-- Arrow Checkpoint 1 -> Wave 2 -->
    <line x1="653" y1="68" x2="679" y2="68" stroke="#059669" stroke-width="1.8" marker-end="url(#arrow-teal)"/>

    <!-- Wave 2 & Checkpoint 2 Box -->
    <rect x="682" y="27" width="264" height="82" rx="4" fill="#ffffff" stroke="#059669" stroke-width="1.4"/>
    <rect x="855" y="30" width="84" height="12.5" rx="3" fill="#fef3c7" stroke="#f59e0b" stroke-width="0.8"/>
    <text x="860" y="39" fill="#92400e" font-family="Inter, Arial, sans-serif" font-size="7.3" font-weight="bold">CHECKPOINT 2</text>
    <text x="690" y="39.5" fill="#065f46" font-family="DejaVu Sans Mono, monospace" font-size="9.2" font-weight="bold">6. /ui-ux-design</text>
    <text x="690" y="53.5" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="8.0">&bull; Skips if Existing UI &ge; 8.5/10 &amp; Validator Passes</text>
    <text x="690" y="66" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="8.0">&bull; Otherwise Spawns 3 Parallel Designers &rarr;</text>
    <text x="698" y="77" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="8.0">3 Single-File HTML/CSS/JS Templates</text>
    <text x="690" y="90" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="7.8">&bull; Verified via <tspan font-family="DejaVu Sans Mono, monospace" font-weight="bold">/visual-ui-validator</tspan></text>
    <text x="690" y="103" fill="#047857" font-family="DejaVu Sans Mono, monospace" font-size="7.6">&rarr; .swarm/blueprint/ui_proposals/template_1..3.html</text>

    <!-- Handoff Arrow Phase A -> Phase B -->
    <path d="M 814 109 L 814 124 L 75 124 L 75 153" fill="none" stroke="#059669" stroke-width="1.8" stroke-dasharray="4,2" marker-end="url(#arrow-blue)"/>
    <rect x="290" y="117" width="375" height="13" rx="3" fill="#ecfdf5" stroke="#10b981" stroke-width="0.8"/>
    <text x="300" y="126" fill="#065f46" font-family="Inter, Arial, sans-serif" font-size="8.0" font-weight="bold">Locked Blueprint Handoff to Phase B (or Early Exit if ALREADY OPTIMAL)</text>

    <!-- PHASE B CONTAINER (BOTTOM) -->
    <rect x="4" y="134" width="952" height="159" rx="6" fill="#eff6ff" stroke="#2563eb" stroke-width="1.5"/>
    <rect x="4" y="134" width="952" height="19" rx="5" fill="#1e40af"/>
    <text x="14" y="147" fill="#ffffff" font-family="Inter, Arial, sans-serif" font-size="9.8" font-weight="bold">PHASE B: AUTONOMOUS 3-EPOCH EVOLUTIONARY SWARM LOOP (/invoke-swarm — Max 3 Macro-Loops: Epoch 1 &rarr; 2 &rarr; 3)</text>

    <!-- Step 0.5 Contract Lock -->
    <rect x="14" y="158" width="122" height="78" rx="4" fill="#ffffff" stroke="#60a5fa" stroke-width="1.2"/>
    <text x="20" y="170" fill="#1e3a8a" font-family="Inter, Arial, sans-serif" font-size="8.6" font-weight="bold">[Step 0.5] Contracts</text>
    <text x="20" y="182.5" fill="#1e40af" font-family="DejaVu Sans Mono, monospace" font-size="8.0" font-weight="bold">/contract-lock</text>
    <text x="20" y="195" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="7.6">&bull; Freezes <tspan font-family="DejaVu Sans Mono, monospace">src/contracts/</tspan></text>
    <text x="20" y="205.5" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="7.6">&bull; Brownfield <tspan font-family="DejaVu Sans Mono, monospace">spec-miner</tspan></text>
    <text x="20" y="216" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="7.6">&bull; <tspan font-family="DejaVu Sans Mono, monospace">WHEN&rarr;THEN</tspan> &amp;</text>
    <text x="20" y="226.5" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="7.6">  <tspan font-family="DejaVu Sans Mono, monospace">INVARIANTS.md</tspan></text>

    <line x1="136" y1="197" x2="152" y2="197" stroke="#2563eb" stroke-width="1.6" marker-end="url(#arrow-blue)"/>

    <!-- Step 1 Parallel Workers -->
    <rect x="155" y="158" width="166" height="78" rx="4" fill="#ffffff" stroke="#60a5fa" stroke-width="1.2"/>
    <text x="161" y="170" fill="#1e3a8a" font-family="Inter, Arial, sans-serif" font-size="8.6" font-weight="bold">[Step 1] Parallel Workers</text>
    <text x="161" y="182.5" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="7.6">&bull; Isolated Git Worktrees</text>
    <text x="161" y="194" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="7.6">&bull; Top-K <tspan font-family="DejaVu Sans Mono, monospace">Instincts (0.3-0.95)</tspan></text>
    <text x="161" y="205.5" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="7.6">&bull; <tspan font-family="DejaVu Sans Mono, monospace" font-weight="bold">/immortal-agents</tspan> watchdog</text>
    <text x="161" y="217" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="7.6">&bull; Pipelined <tspan font-family="DejaVu Sans Mono, monospace">sota_web_scout</tspan></text>
    <text x="161" y="228.5" fill="#1e40af" font-family="DejaVu Sans Mono, monospace" font-size="7.3">Workspace: "share"</text>

    <line x1="321" y1="197" x2="337" y2="197" stroke="#2563eb" stroke-width="1.6" marker-end="url(#arrow-blue)"/>

    <!-- Step 1.5 Discriminator Gate -->
    <rect x="340" y="158" width="182" height="78" rx="4" fill="#ffffff" stroke="#2563eb" stroke-width="1.5"/>
    <text x="346" y="170" fill="#1e3a8a" font-family="Inter, Arial, sans-serif" font-size="8.6" font-weight="bold">[Step 1.5] Zero-Trust Gate</text>
    <text x="346" y="182.5" fill="#1e40af" font-family="DejaVu Sans Mono, monospace" font-size="8.0" font-weight="bold">/discriminator-gate</text>
    <text x="346" y="195" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="7.5">&bull; Diff, Silent-Fail &amp; Config Tamper</text>
    <text x="346" y="205.5" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="7.5">&bull; Runs <tspan font-family="DejaVu Sans Mono, monospace">--adversarial-cmd</tspan> + <tspan font-family="DejaVu Sans Mono, monospace">pass^k</tspan></text>
    <text x="346" y="216" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="7.6">&bull; Gate: <tspan font-weight="bold">0 Blocking, 0 Crit/Imp</tspan></text>
    <text x="346" y="227.5" fill="#dc2626" font-family="Inter, Arial, sans-serif" font-size="7.4" font-weight="bold">Fail: Record Instinct + Loop (5x)</text>

    <!-- Micro-loop arrow Step 1.5 -> Step 1 -->
    <path d="M 431 236 L 431 249 L 238 249 L 238 238" fill="none" stroke="#dc2626" stroke-width="1.3" stroke-dasharray="3,2" marker-end="url(#arrow-red)"/>
    <text x="272" y="246.5" fill="#dc2626" font-family="Inter, Arial, sans-serif" font-size="7.0" font-weight="bold">Gate failed: Fix Loop (Rounds 1-5)</text>

    <line x1="522" y1="197" x2="538" y2="197" stroke="#2563eb" stroke-width="1.6" marker-end="url(#arrow-blue)"/>

    <!-- Step 2-3 Merge Surgeon & Intermittent Report -->
    <rect x="541" y="158" width="132" height="78" rx="4" fill="#ffffff" stroke="#60a5fa" stroke-width="1.2"/>
    <text x="547" y="170" fill="#1e3a8a" font-family="Inter, Arial, sans-serif" font-size="8.6" font-weight="bold">[Step 2-3] Integrate</text>
    <text x="547" y="182.5" fill="#1e40af" font-family="DejaVu Sans Mono, monospace" font-size="8.0" font-weight="bold">/merge-surgeon</text>
    <text x="547" y="195" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="7.5">Git Snapshot Rollback Guard,</text>
    <text x="547" y="205.5" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="7.5">merges branches, writes</text>
    <text x="547" y="216" fill="#334155" font-family="DejaVu Sans Mono, monospace" font-size="7.2">intermittent_report.md</text>
    <text x="547" y="227.5" fill="#334155" font-family="DejaVu Sans Mono, monospace" font-size="7.2">&amp; .swarm/dashboard.html</text>

    <line x1="673" y1="197" x2="689" y2="197" stroke="#2563eb" stroke-width="1.6" marker-end="url(#arrow-blue)"/>

    <!-- Step 4-6 Triad Audit + AgentShield + Perf + SOTA -->
    <rect x="692" y="158" width="136" height="78" rx="4" fill="#ffffff" stroke="#7c3aed" stroke-width="1.3"/>
    <text x="698" y="170" fill="#5b21b6" font-family="Inter, Arial, sans-serif" font-size="8.6" font-weight="bold">[Step 4-6] Triad &amp; SOTA</text>
    <text x="698" y="182.5" fill="#6d28d9" font-family="DejaVu Sans Mono, monospace" font-size="7.8" font-weight="bold">/triad-audit (3 Agents)</text>
    <text x="698" y="194" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="7.3">&bull; Rigor + <tspan font-family="DejaVu Sans Mono, monospace">/perf-benchmarker</tspan></text>
    <text x="698" y="204.5" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="7.3">&bull; Safety + <tspan font-family="DejaVu Sans Mono, monospace" font-weight="bold">/agent-shield</tspan></text>
    <text x="698" y="215" fill="#334155" font-family="Inter, Arial, sans-serif" font-size="7.3">&bull; Innovation (UX/Novelty)</text>
    <text x="698" y="227.5" fill="#6d28d9" font-family="DejaVu Sans Mono, monospace" font-size="7.6" font-weight="bold">/sota-web-scout (Step 6)</text>

    <line x1="828" y1="197" x2="844" y2="197" stroke="#2563eb" stroke-width="1.6" marker-end="url(#arrow-blue)"/>

    <!-- Step 7 Convergence & Epoch Planner -->
    <rect x="847" y="158" width="100" height="78" rx="4" fill="#ffffff" stroke="#1e40af" stroke-width="1.5"/>
    <text x="853" y="170" fill="#1e3a8a" font-family="Inter, Arial, sans-serif" font-size="8.6" font-weight="bold">[Step 7] Replan</text>
    <text x="853" y="182.5" fill="#1e40af" font-family="DejaVu Sans Mono, monospace" font-size="7.8" font-weight="bold">/epoch-planner</text>
    <text x="853" y="195" fill="#047857" font-family="Inter, Arial, sans-serif" font-size="7.4" font-weight="bold">&bull; Converged / Ep 3:</text>
    <text x="859" y="204.5" fill="#047857" font-family="Inter, Arial, sans-serif" font-size="7.2">Promote Instincts</text>
    <text x="853" y="216" fill="#7c3aed" font-family="Inter, Arial, sans-serif" font-size="7.4" font-weight="bold">&bull; Epoch &lt; 3:</text>
    <text x="859" y="226.5" fill="#334155" font-family="DejaVu Sans Mono, monospace" font-size="7.0">adjusted_plan.md</text>

    <!-- Macro-Loop Return Arrow Step 7 -> Step 0.5 -->
    <path d="M 897 236 L 897 281 L 75 281 L 75 238" fill="none" stroke="#7c3aed" stroke-width="1.6" marker-end="url(#arrow-purple)"/>
    <rect x="275" y="271.5" width="430" height="14" rx="3" fill="#f5f3ff" stroke="#7c3aed" stroke-width="0.8"/>
    <text x="285" y="281" fill="#5b21b6" font-family="Inter, Arial, sans-serif" font-size="7.8" font-weight="bold">3-Epoch Evolutionary Funnel Loop (Epoch 1: Foundation &rarr; Epoch 2: SOTA Elevation &rarr; Epoch 3: Hardening)</text>
  </svg>
</div>

<!-- 3. PHASE A SKILLS TABLE -->
<div class="section-hdr teal">
  <span>3. Phase A Skills — Initial Discovery, Opportunity Scouting, Open-Core/B2B &amp; Product Planning</span>
  <span class="sub">Run all at once via /product-discovery or invoke any individual skill standalone on any repository</span>
</div>
<table class="skill-table phase-a">
  <thead>
    <tr>
      <th style="width: 22%;">Skill &amp; Calling Modes</th>
      <th style="width: 24%;">When to Use (Trigger Scenario)</th>
      <th style="width: 32%;">Sub-Agents &amp; Core Capabilities</th>
      <th style="width: 22%;">Persistent Outputs</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>
        <code class="cmd cmd-primary">/product-discovery</code><br>
        <span class="mode-tag">default</span><span class="mode-tag">no-ui</span><br>
        <span class="mode-tag">tech-only</span><span class="mode-tag">market-only</span>
      </td>
      <td><span class="when-to-use">New product OR existing repo audit.</span> Crawls web/literature/market potentials &amp; plans product (2 waves, 2 checkpoints).</td>
      <td><strong>Wave 1:</strong> <code>/deep-research</code> + <code>/market-research</code> + <code>/commercial-strategy</code>. <strong>Checkpoint 1:</strong> <code>/coop-brainstorm</code> (can declare <code>ALREADY OPTIMAL</code> if repo &ge; 8.5/10). <strong>Wave 2:</strong> <code>/ui-ux-design</code>.</td>
      <td>All <code>.swarm/blueprint/*</code> files + <code>docs/ARCHITECTURE.md</code></td>
    </tr>
    <tr>
      <td><code class="cmd cmd-primary">/deep-research</code></td>
      <td><span class="when-to-use">Literature &amp; Zotero grounding.</span> Academic rigor + your own curated Zotero notes/PDFs + web SOTA.</td>
      <td><strong>3 Parallel Streams (Prompt Defense):</strong> (A) Personal Zotero DB via <code>zotero_tool.py</code> (collections, notes, PDF grep), (B) High-impact papers (OpenAlex citations, arXiv, PubMed), (C) Web/OSS Build-vs-Adopt crawl.</td>
      <td><span class="path">.swarm/blueprint/deep_research_report.md</span><br><span class="path">.swarm/sota/sota_knowledge_base.md</span></td>
    </tr>
    <tr>
      <td><code class="cmd cmd-primary">/market-research</code></td>
      <td><span class="when-to-use">Competitive &amp; buyer validation.</span> Greenfield ideas OR existing repos (Truth-in-Code parity mode).</td>
      <td><strong>Spawns 3 Agents:</strong> <code>competitor_teardown_scout</code> (incumbents, SaaS, OSS velocity/licenses), <code>voice_of_customer_miner</code> (HN/Reddit/GitHub Switch Triggers), <code>tam_icp_gtm_analyst</code> (bottom-up TAM/SAM/SOM &amp; ICP).</td>
      <td><span class="path">.swarm/blueprint/market_research_report.md</span><br><span class="path">.swarm/blueprint/market_dashboard.html</span></td>
    </tr>
    <tr>
      <td><code class="cmd cmd-primary">/commercial-strategy</code></td>
      <td><span class="when-to-use">Open-Core &amp; B2B monetization.</span> Designing OSS vs. paid boundaries, pricing, COGS margins, and moats.</td>
      <td><strong>Spawns 2 Agents:</strong> <code>pricing_monetization_strategist</code> (MIT/Apache Core + <code>ee/</code> vs. BSL/AGPL, 3-tier OSS/Pro/B2B Enterprise gates, COGS) &amp; <code>moat_and_risk_skeptic</code> (cannibalization, IP/GPL scan, kill-risks).</td>
      <td><span class="path">.swarm/blueprint/commercial_strategy_report.md</span><br><span class="path">.swarm/blueprint/market_dashboard.html</span></td>
    </tr>
    <tr>
      <td><code class="cmd cmd-primary">/coop-brainstorm</code></td>
      <td><span class="when-to-use">Feature, arch &amp; Search-First gate.</span> Interactive ideation + 1-10 Sufficiency Scorecard before coding.</td>
      <td><strong>Sufficiency Gate (&ge;8.5/10 &rarr; <code>ALREADY OPTIMAL</code>) + 3 Pillars:</strong> (1) Innovations (Net-ROI &ge; 8.0), (2) Search-First <code>[ADOPT]</code>/<code>[EXTEND]</code>/<code>[BUILD]</code> + <code>[OSS]</code>/<code>[Pro]</code>/<code>[B2B]</code>, (3) Arch Option 0 vs. Alternatives.</td>
      <td><span class="path">.swarm/blueprint/brainstorm_blueprint.md</span><br><span class="path">docs/ARCHITECTURE.md</span></td>
    </tr>
    <tr>
      <td><code class="cmd cmd-primary">/ui-ux-design</code></td>
      <td><span class="when-to-use">Visual prototyping &amp; UX selection.</span> Audits existing UI (&ge;8.5/10 skips regen) or builds 3 HTML mockups.</td>
      <td>Audits existing UI via <code>web_ui_validator.py</code> (keeps if &ge; 8.5/10); otherwise proposes 3 distinct UI/UX philosophies, spawns 3 parallel UI Designers for self-contained HTML/CSS/JS files, and validates.</td>
      <td><span class="path">.swarm/blueprint/ui_proposals/template_1..3.html</span><br><span class="path">.swarm/blueprint/ui_ux_proposals.md</span></td>
    </tr>
    <tr>
      <td><code class="cmd cmd-primary">/paper-to-code</code></td>
      <td><span class="when-to-use">Translating papers to verified math code.</span> Turning Zotero/arXiv equations into tested reference modules.</td>
      <td>Extracts formal equations/algorithms from Zotero PDFs or arXiv, cross-verifies closed-form identities via SymPy (optionally a local math model), and writes golden unit tests.</td>
      <td><span class="path">.swarm/paper_spec.md</span> + Reference Module &amp; Unit Tests</td>
    </tr>
  </tbody>
</table>

<div class="footer-bar">
  <span>Autonomous Evolutionary Agent Swarm Toolkit (v2.7) — Google Antigravity</span>
  <span class="right">Page 1 of 2 (Flip for Phase B Swarm Skills, AgentShield, Scoring Rules &amp; File Bus Map &rarr;)</span>
</div>

<!-- ==================== PAGE 2 ==================== -->
<div class="page-break"></div>

<!-- 4. PHASE B SKILLS TABLE -->
<div class="section-hdr blue" style="margin-top: 0;">
  <span>4. Phase B Skills — Autonomous 3-Epoch Swarm Loop &amp; Standalone Stage Skills</span>
  <span class="sub">Run the full loop via /invoke-swarm or invoke any individual stage skill on any branch/repo</span>
</div>
<table class="skill-table phase-b">
  <thead>
    <tr>
      <th style="width: 24%;">Skill &amp; Calling Modes</th>
      <th style="width: 22%;">When to Use (Trigger Scenario)</th>
      <th style="width: 34%;">What It Does &amp; Gate Enforcement Rules</th>
      <th style="width: 20%;">Persistent Outputs</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>
        <code class="cmd cmd-swarm">/invoke-swarm</code><br>
        <span class="mode-tag">default (3-Epoch)</span><span class="mode-tag">single-epoch</span><br>
        <span class="mode-tag">discriminate-only</span><span class="mode-tag">audit-only</span><br>
        <span class="mode-tag">sota-only</span><span class="mode-tag">replan-only</span>
      </td>
      <td><span class="when-to-use">Autonomous multi-agent build &amp; evolution.</span> Executes Steps 0.5 &rarr; 7 across up to 3 Macro-Loops until convergence.</td>
      <td>Locks contracts + invariants, spawns parallel worktree workers (injected with Top-K <code>instincts.json</code>), supervises via <code>immortal_watcher</code>, gates each worker with <code>discriminator</code>, merges, runs Triad + AgentShield + SOTA Scout, and replans.</td>
      <td><span class="path">.swarm/swarm_tasks.json</span><br><span class="path">.swarm/dashboard.html</span><br><span class="path">.swarm/epoch_1..3/*</span></td>
    </tr>
    <tr>
      <td><code class="cmd cmd-swarm">/contract-lock</code><br><span class="mode-tag">Step 0.5</span><span class="mode-tag">spec-miner</span></td>
      <td><span class="when-to-use">Before parallel coding.</span> Prevents signature collisions &amp; mines brownfield invariants.</td>
      <td>Defines and freezes shared cross-module interfaces (<code>src/contracts/</code>) on <code>main</code>. On brownfield repos, runs Sample &amp; Expand <code>spec-miner</code> (15-file cap) to lock <code>WHEN&rarr;THEN</code> &amp; <code>ALWAYS TRUE</code> invariants.</td>
      <td><span class="path">src/contracts/*</span><br><span class="path">docs/INVARIANTS.md</span></td>
    </tr>
    <tr>
      <td><code class="cmd cmd-swarm">/discriminator-gate</code><br><span class="mode-tag">Step 1.5</span><span class="mode-tag">pass^k</span></td>
      <td><span class="when-to-use">Zero-trust branch review.</span> Auditing a sub-agent or feature branch before allowing merge.</td>
      <td>Inspects <code>git diff</code>, runs tests + <code>--adversarial-cmd</code> (with <code>--pass-hat-k</code>), Silent-Failure Hunter &amp; Config/Contract Tampering check. Enforces a <strong>categorical gate</strong> (0 <code>BLOCKING_FAIL</code>, spec <code>PASS</code>, 0 Critical/Important; loops up to 5x).</td>
      <td><span class="path">.swarm/instincts.json</span><br><span class="path">.swarm/lessons_learned.md</span></td>
    </tr>
    <tr>
      <td><code class="cmd cmd-swarm">/merge-surgeon</code><br><span class="mode-tag">Step 3</span><span class="mode-tag">snapshots</span></td>
      <td><span class="when-to-use">Integrating parallel branches.</span> Merging multiple Git worktrees cleanly into <code>main</code>.</td>
      <td>Creates pre-merge Git snapshots (<code>--snapshot-create</code>), merges approved worker branches (<code>git merge --no-ff</code>), resolves semantic conflicts honoring <code>src/contracts/</code>, and auto-restores (<code>--snapshot-restore</code>) on failure.</td>
      <td>Integrated <span class="path">main</span> branch + tag <span class="path">swarm-epoch-&lt;N&gt;</span></td>
    </tr>
    <tr>
      <td>
        <code class="cmd cmd-swarm">/triad-audit</code><br>
        <span class="mode-tag">default (All 3)</span><span class="mode-tag">rigor-only</span><br>
        <span class="mode-tag">safety-only</span><span class="mode-tag">innovation-only</span>
      </td>
      <td><span class="when-to-use">Deep codebase audit (Steps 4-5).</span> Finding math bugs, security holes, or UX/innovation gaps.</td>
      <td>Spawns 3 parallel auditors: <strong><code>rigor_auditor</code></strong> (math/algo complexity, <code>pass^k</code> &amp; <code>/perf-benchmarker</code>), <strong><code>safety_auditor</code></strong> (runs <code>/agent-shield</code> + threat tests), <strong><code>innovation_auditor</code></strong> (UX/visuals &amp; methods). Scores 1-10.</td>
      <td><span class="path">.swarm/epoch_&lt;N&gt;/audit_rigor.md</span><br><span class="path">audit_safety.md</span>, <span class="path">audit_innovation.md</span></td>
    </tr>
    <tr>
      <td><code class="cmd cmd-swarm">/agent-shield</code><br><span class="mode-tag">Step 4.2</span><span class="mode-tag">standalone</span></td>
      <td><span class="when-to-use">Security, Prompt-Injection &amp; MCP audit.</span> Scanning secrets, Unicode, hooks &amp; MCP tax.</td>
      <td>Runs <code>scripts/agent_shield.py</code> across 5 categories: (1) Secrets &amp; tracked <code>.env</code>, (2) Prompt-Injection &amp; Trojan-Source Unicode, (3) Unsafe hook pipes (<code>curl|sh</code>), (4) MCP Context-Tax (&le;5 servers), (5) Silent failures.</td>
      <td><span class="path">.swarm/security_shield_report.md</span> (Grade <code>A-F</code>, <code>0-100</code>)</td>
    </tr>
    <tr>
      <td><code class="cmd cmd-swarm">/perf-benchmarker</code><br><span class="mode-tag">Step 4.1</span><span class="mode-tag">pass_hat_k</span></td>
      <td><span class="when-to-use">Latency, RAM &amp; flakiness tracking.</span> Detecting speed, memory, or <code>pass^k</code> regressions.</td>
      <td>Runs <code>scripts/perf_tracker.py</code> across K iterations, measuring wall-clock latency (ms), peak RSS memory (KB), <code>pass_at_k</code> (&ge;1/K), and <code>pass_hat_k</code> (K/K non-flaky passes). Flags regressions &gt; 15%.</td>
      <td><span class="path">.swarm/benchmarks.json</span></td>
    </tr>
    <tr>
      <td><code class="cmd cmd-swarm">/visual-ui-validator</code><br><span class="mode-tag">UI Gate</span><span class="mode-tag">standalone</span></td>
      <td><span class="when-to-use">Validating HTML/JS UIs.</span> Checking UI prototypes or web apps for broken JS or empty canvases.</td>
      <td>Runs <code>scripts/web_ui_validator.py</code>: verifies HTML DOM structure, rejects <code>"Lorem ipsum"</code> placeholders, runs <code>node --check</code> on every inline <code>&lt;script&gt;</code>, and checks headless Chromium console/bounding boxes.</td>
      <td>JSON/CLI pass-fail report + optional screenshots</td>
    </tr>
    <tr>
      <td><code class="cmd cmd-swarm">/sota-web-scout</code><br><span class="mode-tag">Step 6</span><span class="mode-tag">standalone</span></td>
      <td><span class="when-to-use">External SOTA benchmarking.</span> Comparing your repo against leading tools &amp; papers.</td>
      <td>Crawls web, GitHub, and literature in parallel (under Prompt Defense Baseline) for SOTA visualizations, architectures, and Build-vs-Adopt packages. Scores <strong>Innovation vs. SOTA (1-10)</strong> and <strong>Implementation vs. SOTA (1-10)</strong>.</td>
      <td><span class="path">.swarm/sota/sota_knowledge_base.md</span><br><span class="path">.swarm/epoch_&lt;N&gt;/sota_evaluation.md</span></td>
    </tr>
    <tr>
      <td><code class="cmd cmd-swarm">/epoch-planner</code> &amp; <code class="cmd cmd-swarm">/immortal-agents</code></td>
      <td><span class="when-to-use">Milestone replanning (Steps 3/7) &amp; sub-agent revival watchdog.</span></td>
      <td><strong><code>/epoch-planner</code>:</strong> Writes <code>intermittent_report.md</code>, renders <code>dashboard.html</code>, checks convergence &amp; writes <code>adjusted_plan.md</code>. <strong><code>/immortal-agents</code>:</strong> Inspects <code>transcript.jsonl</code> &amp; revives stalled workers (up to 5x).</td>
      <td><span class="path">intermittent_report.md</span><br><span class="path">adjusted_plan.md</span><br><span class="path">.swarm/dashboard.html</span></td>
    </tr>
  </tbody>
</table>

<!-- 5. SUPPORTING ENGINEERING, MATH & 3D MCP SKILLS -->
<div class="section-hdr purple">
  <span>5. Supporting Engineering, GPU Math &amp; Live 3D Editor MCP Skills</span>
  <span class="sub">Specialized execution contracts, binary runtime smoke testing, local GPU math proofs &amp; singleton 3D scenes</span>
</div>
<table class="skill-table util-table">
  <thead>
    <tr>
      <th style="width: 21%;">Skill</th>
      <th style="width: 25%;">When to Use</th>
      <th style="width: 54%;">Capabilities &amp; Key Commands</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code class="cmd cmd-util">/goal-loop</code></td>
      <td><span class="when-to-use">Hierarchical Tasks, Briefs &amp; Hard-Cap Gate.</span></td>
      <td>Runs <code>scripts/goal_loop.py</code>: <code>--preflight</code> conflict scan, <code>--task-brief</code> &amp; <code>--review-package</code> bundlers, AST call-site wiring check, and Hard-Cap Two-Verdict recording.</td>
    </tr>
    <tr>
      <td><code class="cmd cmd-util">/swarm-diagnostics</code></td>
      <td><span class="when-to-use">Diagnose slow, looping, or stalled sessions.</span></td>
      <td>Runs <code>scripts/swarm_diagnostics.py</code> over <code>transcript.jsonl</code> &amp; <code>.swarm/</code> across 7 dimensions with mandatory <code>path:line</code> / <code>step_index</code> citations.</td>
    </tr>
    <tr>
      <td><code class="cmd cmd-util">/quality-validator</code></td>
      <td><span class="when-to-use">Smoke-testing compiled apps/games.</span></td>
      <td>Runs <code>scripts/quality_validator.py ./build/app --timeout 10</code> enforcing fresh verification evidence before completion claims.</td>
    </tr>
    <tr>
      <td><code class="cmd cmd-util">/math-reasoning</code> &amp; <code class="cmd cmd-util">/tmux-orchestrator</code></td>
      <td><span class="when-to-use">Optional local math model &amp; headless CLI daemons.</span></td>
      <td>Optional extra: routes derivations to a local math model (falls back to SymPy); manages multi-pane Linux <code>tmux</code> runners.</td>
    </tr>
  </tbody>
</table>

<!-- 6. BOTTOM SPLIT TABLE: TWO-VERDICT + HARD-CAP EVALUATION RULES + .SWARM FILE BUS MAP -->
<table class="bottom-layout">
  <tr>
    <td class="split-cell">
      <div class="info-card">
        <h3>6. Two-Verdict Gate, Hard Caps &amp; 5-Round Escalating Loop</h3>
        <ul class="rule-list">
          <li><strong>No Arbitrary Point Math — Deterministic Invariants + Semantic Gate:</strong> <code>goal_loop.py</code> checks binary <code>BLOCKING_FAIL</code> invariants (test exit code, AST wiring, zero stubs) &amp; bundles <code>BASE_SHA..HEAD</code> diffs.</li>
          <li><strong>Two-Verdict Discriminator:</strong> (1) <strong>Spec Compliance</strong> (<code>PASS | FAIL | UNVERIFIABLE</code> + <code>Review Focus</code> proof) &amp; (2) <strong>Severity Buckets</strong>: <code>Critical</code>, <code>Important</code>, <code>Minor (Deferred)</code>.</li>
          <li><strong>Strict Hard Caps (Override Arithmetic):</strong><br>
            <span class="score-pill score-deduct">Any BLOCKING_FAIL / Spec FAIL / Critical &rarr; Cap 6.0</span>
            <span class="score-pill score-deduct">Any Important &rarr; Cap 7.0</span>
            <span class="score-pill score-base">Minor &rarr; Deferred to Ledger (Never Blocks)</span>
          </li>
          <li><strong>5-Round Escalating Fix Loop &amp; Scoped Re-Review (<code>FIX_BASE..HEAD</code>):</strong> Rounds 1–3 resume same worker; <strong>Rounds 4–5 spawn a fresh worker sub-agent</strong>; <strong>Round 5 Breaker</strong> logs a typed <code>Ruling:</code> (<code>OVERRIDE</code> / <code>SPLIT_TASK</code> / <code>RE_ARCHITECT_CONTRACT</code> / <code>ESCALATE_TO_USER</code>) in <code>.swarm/ledger.md</code>; rulings never overturn a <code>BLOCKING_FAIL</code>.</li>
          <li><strong>UI Craft &amp; Unanchored Critique:</strong> <code>ui_direction_dealer.py</code> deals directions by Surface Mode + Design Dials; <code>web_ui_validator.py</code> checks <code>1440/768/390</code> + <code>reduced-motion</code>; Assessment A runs unanchored before B.</li>
        </ul>
      </div>
    </td>
    <td class="split-spacer"></td>
    <td class="split-cell">
      <div class="info-card">
        <h3>7. Persistent Repository File Bus (<code>.swarm/</code> &amp; <code>DESIGN.md</code>)</h3>
        <div class="file-tree">
          <div><span class="ft-dir">DESIGN.md &amp; .swarm/surfaces/</span> <span class="ft-desc">— 3-Tier Design System, Tokens &amp; Surface Briefs</span></div>
          <div><span class="ft-dir">.swarm/blueprint/</span> <span class="ft-desc">— Phase A Discovery, Market &amp; UI Prototypes</span></div>
          <div>&nbsp;&nbsp;&#9500;&#9472; <code>deep_research_report.md</code>, <code>market_research_report.md</code> &amp; <code>market_dashboard.html</code></div>
          <div>&nbsp;&nbsp;&#9500;&#9472; <code>brainstorm_blueprint.md</code> (with <code>Review Focus</code>) &amp; <code>docs/INVARIANTS.md</code></div>
          <div>&nbsp;&nbsp;&#9492;&#9472; <code>ui_proposals/template_1..3.html</code> <span class="ft-desc">(3-viewport verified HTML UIs)</span></div>
          <div style="margin-top: 2pt;"><span class="ft-dir">.swarm/</span> <span class="ft-desc">— Phase B Briefs, Diff Packages, Ledgers &amp; Telemetry</span></div>
          <div>&nbsp;&nbsp;&#9500;&#9472; <code>goal_loop.json</code>, <code>briefs/&lt;ID&gt;-brief.md</code> &amp; <code>reviews/&lt;ID&gt;-review.diff.md</code></div>
          <div>&nbsp;&nbsp;&#9500;&#9472; <code>ledger.md</code> <span class="ft-desc">(Round 5 Rulings)</span> &amp; <code>deferred_minor_ledger.md</code> <span class="ft-desc">(Minor notes)</span></div>
          <div>&nbsp;&nbsp;&#9500;&#9472; <code>dashboard.html</code>, <code>security_shield_report.md</code> &amp; <code>diagnostics_report.md</code></div>
          <div>&nbsp;&nbsp;&#9492;&#9472; <code>instincts.json</code>, <code>epoch_&lt;1..K&gt;/</code> &amp; <code>sota/sota_knowledge_base.md</code></div>
        </div>
      </div>
    </td>
  </tr>
</table>

<div class="footer-bar">
  <span>Repo: <code>https://github.com/severinbro/autonomous-evolutionary-agent-swarm</code> | Local: <code>~/.gemini/config/plugins/agent-swarm</code></span>
  <span class="right">Page 2 of 2</span>
</div>

</body>
</html>
"""


def main() -> None:
    out_pdf = pathlib.Path(__file__).resolve().parent.parent / "SWARM_CHEATSHEET.pdf"
    weasyprint.HTML(string=HTML_CONTENT).write_pdf(str(out_pdf))
    print(f"Generated {out_pdf} ({out_pdf.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
