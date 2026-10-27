#!/usr/bin/env python3
"""Interactive Single-File Market & Commercial Strategy HTML Dashboard Generator.

Reads `.swarm/blueprint/market_data.json` (or generates a rich template if not yet populated)
and emits a 100% self-contained, interactive single-file HTML/CSS/JS dashboard at
`.swarm/blueprint/market_dashboard.html` featuring:
  1. 2x2 Competitive Positioning Quadrant (Interactive SVG Scatter Radar)
  2. Filterable Open-Core & B2B Enterprise Feature-Gating & Parity Matrix
  3. Interactive Pricing, Unit Economics & 12-Month ARR Simulator (Live Sliders + SVG Chart)
  4. Voice-of-Customer Switch Triggers & Adversarial Kill-Risk Register
"""

from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
from typing import Any

DEFAULT_DATA_FILE = ".swarm/blueprint/market_data.json"
DEFAULT_OUT_FILE = ".swarm/blueprint/market_dashboard.html"


def default_market_data() -> dict[str, Any]:
    return {
        "project_name": "Project Market & Commercial Strategy",
        "positioning_statement": "Open-Core + B2B Enterprise platform combining local-first execution speed with enterprise governance and collaborative cloud workflows.",
        "x_axis_label": "Architecture Openness & Extensibility (Closed SaaS -> Open-Core / Self-Hostable)",
        "y_axis_label": "Workflow Depth & Automation Rigor (Basic -> SOTA / Automated)",
        "tam_sam_som": {
            "tam_usd": "$4.2B",
            "tam_formula": "350,000 global target orgs x $12,000 blended ACV",
            "sam_usd": "$680M",
            "sam_formula": "42,500 mid-market & enterprise engineering teams x $16,000 ACV",
            "som_usd": "$14.4M (Year 3)",
            "som_formula": "600 Pro Teams ($8k/yr) + 160 B2B Enterprise deployments ($60k/yr)",
            "beachhead_icp": "Mid-market & Enterprise B2B technical teams requiring self-hosted data sovereignty, scriptable CLI/API automation, and zero vendor lock-in.",
        },
        "competitors": [
            {"name": "Our Project (Target)", "x": 88, "y": 90, "category": "us", "license": "Open-Core (MIT/Apache + Enterprise)", "price": "$0 OSS / $29 Pro / $99 Ent", "wedge": "Full open-core extensibility + B2B self-hosted governance"},
            {"name": "Legacy Incumbent Suite", "x": 22, "y": 78, "category": "incumbent", "license": "Proprietary Desktop/Cloud", "price": "$180+/seat/mo", "wedge": "High seat cost, closed file formats, slow release cycle"},
            {"name": "Cloud-Only SaaS Challenger", "x": 35, "y": 68, "category": "saas", "license": "Closed SaaS", "price": "$45/seat/mo", "wedge": "No air-gapped/on-prem option; blocks B2B enterprise security review"},
            {"name": "Community OSS Tool", "x": 92, "y": 42, "category": "oss", "license": "GPLv3 / MIT", "price": "Free", "wedge": "Fragmented UX, no RBAC/SSO, no commercial SLA or team sync"},
        ],
        "features": [
            {"feature": "Core Engine, Local CLI & SDK", "tier": "oss", "role": "Wedge / Adoption Hook", "us": "Full (Open-Source)", "incumbent": "Closed / Paid Add-on", "saas": "Limited API", "oss": "Full"},
            {"feature": "Standard File Import/Export Bridge", "tier": "oss", "role": "Switch Trigger", "us": "Lossless Bidirectional", "incumbent": "Proprietary Lock-in", "saas": "Export Watermarked", "oss": "Partial"},
            {"feature": "Real-Time Multiplayer & Cloud Workspace", "tier": "pro", "role": "Monetization Gate", "us": "Built-in CRDT Sync", "incumbent": "bolt-on PDM ($)", "saas": "Built-in", "oss": "None"},
            {"feature": "Managed AI / Compute Credits", "tier": "pro", "role": "Usage Upsell", "us": "Included + BYO-GPU", "incumbent": "Cloud Credits Only", "saas": "Metered Add-on", "oss": "Manual Setup"},
            {"feature": "Self-Hosted Docker/K8s + Air-Gapped Mode", "tier": "enterprise", "role": "B2B Enterprise Gate", "us": "First-Class Helm/Binary", "incumbent": "Legacy License Server", "saas": "Unavailable", "oss": "DIY Unmanaged"},
            {"feature": "SAML/OIDC SSO, RBAC & Audit Logs", "tier": "enterprise", "role": "B2B Enterprise Gate", "us": "Full Compliance Suite", "incumbent": "Enterprise Tier Only", "saas": "Enterprise Tier Only", "oss": "None"},
        ],
        "switch_triggers": [
            {"pain": "Cloud-only competitors fail B2B Enterprise infosec/air-gap reviews", "source": "HN / Enterprise Buyer Interviews", "severity": "CRITICAL", "response": "Offer single-binary / Docker self-hosted B2B Enterprise deployment"},
            {"pain": "Incumbent per-seat pricing penalizes occasional reviewers and stakeholders", "source": "Reddit / G2 Churn Reviews", "severity": "HIGH", "response": "Unlimited free read/comment seats + open-source core CLI"},
            {"pain": "Proprietary format lock-in prevents automated CI/CD pipeline validation", "source": "GitHub Issues", "severity": "HIGH", "response": "Git-friendly deterministic text/JSON schema + open CLI"},
        ],
        "kill_risks": [
            {"risk": "Open-Source Cannibalization (Free tier is 'too good', B2B buyers never upgrade)", "severity": "HIGH", "mitigation": "Gate multi-user governance (SSO/RBAC, audit logs, centralized team sync, SLA) in Enterprise while keeping single-player core 100% open."},
            {"risk": "Incumbent bundles a 'good enough' AI/automation feature into existing enterprise contracts", "severity": "MEDIUM", "mitigation": "Win on open-core extensibility, local/on-prem privacy, and 10x faster CLI/SDK integration."},
            {"risk": "Copyleft (GPL/AGPL) dependency contamination blocking B2B commercial licensing", "severity": "HIGH", "mitigation": "Enforce strict MIT/Apache-2.0/BSD dependency whitelist in CI before Epoch 1."},
        ],
        "unit_economics_defaults": {
            "active_oss_users": 5000,
            "pro_conversion_pct": 4.0,
            "pro_price_monthly": 29,
            "enterprise_deals": 12,
            "enterprise_acv": 24000,
            "monthly_cogs_per_paid_user": 4.5,
        },
    }


def load_data(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return default_market_data()
    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            base = default_market_data()
            base.update(loaded)
            return base
    except Exception:
        return default_market_data()


def generate_market_dashboard(
    data_file: str = DEFAULT_DATA_FILE,
    out_file: str = DEFAULT_OUT_FILE,
) -> str:
    data = load_data(data_file)
    data_json = json.dumps(data)
    title = html.escape(data.get("project_name") or "Market & Commercial Strategy")
    pos = html.escape(data.get("positioning_statement") or "")

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title} - Market &amp; Commercial Strategy</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #090d16;
      --panel: #111827;
      --panel-alt: #1e293b;
      --text: #f8fafc;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --oss: #10b981;
      --pro: #a855f7;
      --ent: #f59e0b;
      --danger: #ef4444;
      --border: #334155;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 1.5rem 2rem;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 1rem;
      border-bottom: 1px solid var(--border);
      padding-bottom: 1rem;
      margin-bottom: 1.5rem;
    }}
    h1 {{ font-size: 1.45rem; font-weight: 700; letter-spacing: -0.02em; }}
    .subtitle {{ color: var(--muted); font-size: 0.9rem; max-width: 68ch; margin-top: 0.25rem; }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1rem;
      margin-bottom: 1.5rem;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 0.75rem;
      padding: 1.15rem;
    }}
    .card-label {{
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
    }}
    .card-val {{
      font-size: 1.65rem;
      font-weight: 700;
      margin: 0.2rem 0;
    }}
    .card-formula {{ font-size: 0.78rem; color: var(--muted); }}
    .two-col {{
      display: grid;
      grid-template-columns: 1.05fr 1fr;
      gap: 1.25rem;
      margin-bottom: 1.5rem;
    }}
    @media (max-width: 980px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
    h2 {{
      font-size: 1.02rem;
      font-weight: 600;
      margin-bottom: 0.85rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .filter-bar {{ display: flex; gap: 0.4rem; flex-wrap: wrap; }}
    button {{
      background: var(--panel-alt);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 0.4rem;
      padding: 0.3rem 0.65rem;
      font-size: 0.78rem;
      cursor: pointer;
    }}
    button.active {{
      background: var(--accent);
      color: #090d16;
      border-color: var(--accent);
      font-weight: 600;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.83rem; }}
    th, td {{
      text-align: left;
      padding: 0.58rem 0.65rem;
      border-bottom: 1px solid var(--border);
    }}
    th {{ color: var(--muted); font-size: 0.74rem; text-transform: uppercase; }}
    .badge {{
      display: inline-block;
      padding: 0.14rem 0.48rem;
      border-radius: 999px;
      font-size: 0.7rem;
      font-weight: 600;
    }}
    .tier-oss {{ background: rgba(16, 185, 129, 0.16); color: var(--oss); }}
    .tier-pro {{ background: rgba(168, 85, 247, 0.16); color: var(--pro); }}
    .tier-enterprise {{ background: rgba(245, 158, 11, 0.16); color: var(--ent); }}
    .sev-CRITICAL, .sev-HIGH {{ background: rgba(239, 68, 68, 0.16); color: var(--danger); }}
    .sev-MEDIUM {{ background: rgba(245, 158, 11, 0.16); color: var(--ent); }}
    .slider-row {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 0.35rem;
      margin-bottom: 0.65rem;
      font-size: 0.82rem;
    }}
    input[type="range"] {{
      grid-column: 1 / -1;
      width: 100%;
      accent-color: var(--accent);
    }}
    .sim-summary {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 0.6rem;
      margin: 0.85rem 0;
      padding: 0.75rem;
      background: rgba(15, 23, 42, 0.65);
      border-radius: 0.5rem;
      border: 1px solid var(--border);
    }}
    .sim-metric-val {{ font-size: 1.15rem; font-weight: 700; color: var(--accent); }}
    svg {{ width: 100%; height: auto; display: block; }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>{title}</h1>
      <p class="subtitle">{pos}</p>
    </div>
    <span class="badge tier-oss" id="icp-pill">Open-Core + B2B Enterprise Strategy</span>
  </header>

  <section class="kpi-grid" id="sizing-cards"></section>

  <div class="two-col">
    <section class="card">
      <h2>
        <span>2x2 Competitive Positioning Quadrant</span>
        <span style="font-size:0.75rem;color:var(--muted)">Click or hover nodes</span>
      </h2>
      <svg id="quadrant-svg" viewBox="0 0 520 320" role="img" aria-label="2x2 Competitive Positioning Quadrant"></svg>
      <div id="competitor-detail" style="margin-top:0.65rem;font-size:0.82rem;color:var(--muted)"></div>
    </section>

    <section class="card">
      <h2>
        <span>Interactive Open-Core &amp; B2B Unit Economics Simulator</span>
      </h2>
      <div id="sliders-box">
        <div class="slider-row">
          <span>Active Open-Source / Free Users</span>
          <strong id="lbl-oss">5000</strong>
          <input type="range" id="inp-oss" min="500" max="50000" step="500" value="5000" />
        </div>
        <div class="slider-row">
          <span>OSS-to-Pro Conversion (%) &amp; Pro Price ($/mo)</span>
          <strong id="lbl-pro">4.0% @ $29/mo</strong>
          <input type="range" id="inp-conv" min="0.5" max="15" step="0.5" value="4.0" />
        </div>
        <div class="slider-row">
          <span>B2B Enterprise Self-Hosted Contracts (Count)</span>
          <strong id="lbl-ent-deals">12 deals</strong>
          <input type="range" id="inp-ent-deals" min="0" max="100" step="1" value="12" />
        </div>
        <div class="slider-row">
          <span>B2B Enterprise Annual Contract Value (ACV $)</span>
          <strong id="lbl-ent-acv">$24,000/yr</strong>
          <input type="range" id="inp-ent-acv" min="5000" max="120000" step="2500" value="24000" />
        </div>
        <div class="slider-row">
          <span>Monthly Cloud/AI COGS per Paid Pro User ($)</span>
          <strong id="lbl-cogs">$4.50/mo</strong>
          <input type="range" id="inp-cogs" min="0.5" max="25" step="0.5" value="4.5" />
        </div>
      </div>
      <div class="sim-summary">
        <div>
          <div class="card-label">Total ARR</div>
          <div class="sim-metric-val" id="out-arr">$0</div>
        </div>
        <div>
          <div class="card-label">Gross Margin</div>
          <div class="sim-metric-val" id="out-margin">0%</div>
        </div>
        <div>
          <div class="card-label">B2B Ent Share</div>
          <div class="sim-metric-val" id="out-ent-share">0%</div>
        </div>
      </div>
      <svg id="econ-svg" viewBox="0 0 480 110" role="img" aria-label="ARR Breakdown Chart"></svg>
    </section>
  </div>

  <section class="card" style="margin-bottom:1.5rem">
    <h2>
      <span>Open-Core &amp; B2B Enterprise Feature-Gating &amp; Competitor Parity Matrix</span>
      <div class="filter-bar" id="tier-filters">
        <button data-tier="all" class="active">All Tiers</button>
        <button data-tier="oss">Open-Source Core</button>
        <button data-tier="pro">Pro / Cloud</button>
        <button data-tier="enterprise">B2B Enterprise</button>
      </div>
    </h2>
    <table>
      <thead>
        <tr>
          <th>Feature / Capability</th>
          <th>Packaging Tier</th>
          <th>Commercial Role</th>
          <th>Our Project</th>
          <th>Legacy Incumbent</th>
          <th>Closed SaaS</th>
          <th>Community OSS</th>
        </tr>
      </thead>
      <tbody id="feature-tbody"></tbody>
    </table>
  </section>

  <div class="two-col">
    <section class="card">
      <h2>Voice-of-Customer Pain Ledger &amp; Switch Triggers</h2>
      <table>
        <thead>
          <tr><th>Customer Pain / Churn Trigger</th><th>Severity</th><th>Our Wedge Response</th></tr>
        </thead>
        <tbody id="voc-tbody"></tbody>
      </table>
    </section>

    <section class="card">
      <h2>Adversarial Moat &amp; Kill-Risk Register</h2>
      <table>
        <thead>
          <tr><th>Kill Risk / Cannibalization Threat</th><th>Risk</th><th>Structural Mitigation</th></tr>
        </thead>
        <tbody id="risk-tbody"></tbody>
      </table>
    </section>
  </div>

  <script>
    const DATA = {data_json};

    function renderSizing() {{
      const s = DATA.tam_sam_som || {{}};
      const box = document.getElementById("sizing-cards");
      const items = [
        {{ label: "Bottom-Up TAM", val: s.tam_usd || "N/A", desc: s.tam_formula || "" }},
        {{ label: "Serviceable Market (SAM)", val: s.sam_usd || "N/A", desc: s.sam_formula || "" }},
        {{ label: "Target SOM (Year 3)", val: s.som_usd || "N/A", desc: s.som_formula || "" }},
        {{ label: "Beachhead B2B ICP", val: "Beachhead", desc: s.beachhead_icp || "" }}
      ];
      box.innerHTML = items.map(i => `
        <div class="card">
          <div class="card-label">${{i.label}}</div>
          <div class="card-val">${{i.val}}</div>
          <div class="card-formula">${{i.desc}}</div>
        </div>
      `).join("");
    }}

    function renderQuadrant() {{
      const svg = document.getElementById("quadrant-svg");
      const detail = document.getElementById("competitor-detail");
      const padL = 44, padR = 24, padT = 20, padB = 34;
      const w = 520 - padL - padR;
      const h = 320 - padT - padB;
      const midX = padL + w / 2;
      const midY = padT + h / 2;

      let out = `
        <rect x="${{padL}}" y="${{padT}}" width="${{w}}" height="${{h}}" fill="#0b1324" stroke="#334155" rx="6" />
        <line x1="${{midX}}" y1="${{padT}}" x2="${{midX}}" y2="${{padT + h}}" stroke="#334155" stroke-dasharray="4 4" />
        <line x1="${{padL}}" y1="${{midY}}" x2="${{padL + w}}" y2="${{midY}}" stroke="#334155" stroke-dasharray="4 4" />
        <text x="${{padL + w - 8}}" y="${{padT + 16}}" fill="#38bdf8" font-size="10" text-anchor="end">Open-Core + High Rigor Leader</text>
        <text x="${{padL + 8}}" y="${{padT + 16}}" fill="#94a3b8" font-size="10">Closed Legacy / High Depth</text>
        <text x="${{padL + w - 8}}" y="${{padT + h - 8}}" fill="#94a3b8" font-size="10" text-anchor="end">Community OSS / Basic</text>
        <text x="${{midX}}" y="312" fill="#94a3b8" font-size="10" text-anchor="middle">${{DATA.x_axis_label || "Openness"}}</text>
      `;

      const colors = {{ us: "#38bdf8", incumbent: "#f59e0b", saas: "#a855f7", oss: "#10b981" }};
      (DATA.competitors || []).forEach((c, idx) => {{
        const cx = padL + (Math.max(0, Math.min(100, c.x)) / 100) * w;
        const cy = padT + h - (Math.max(0, Math.min(100, c.y)) / 100) * h;
        const col = colors[c.category] || "#38bdf8";
        const r = c.category === "us" ? 8 : 6;
        out += `
          <g class="comp-node" data-idx="${{idx}}" style="cursor:pointer">
            <circle cx="${{cx.toFixed(1)}}" cy="${{cy.toFixed(1)}}" r="${{r}}" fill="${{col}}" stroke="#090d16" stroke-width="2" />
            <text x="${{(cx + 10).toFixed(1)}}" y="${{(cy + 4).toFixed(1)}}" fill="#f8fafc" font-size="11" font-weight="600">${{c.name}}</text>
          </g>
        `;
      }});
      svg.innerHTML = out;

      const nodes = svg.querySelectorAll(".comp-node");
      const showComp = (idx) => {{
        const c = (DATA.competitors || [])[idx];
        if (!c) return;
        detail.innerHTML = `<strong>${{c.name}}</strong> | License: <code>${{c.license}}</code> | Pricing: <code>${{c.price}}</code><br/>Wedge / Gap: ${{c.wedge}}`;
      }};
      nodes.forEach(n => n.addEventListener("click", () => showComp(Number(n.dataset.idx))));
      nodes.forEach(n => n.addEventListener("mouseenter", () => showComp(Number(n.dataset.idx))));
      showComp(0);
    }}

    function renderFeatures(tierFilter = "all") {{
      const tbody = document.getElementById("feature-tbody");
      const rows = (DATA.features || []).filter(f => tierFilter === "all" || f.tier === tierFilter);
      tbody.innerHTML = rows.map(f => `
        <tr>
          <td><strong>${{f.feature}}</strong></td>
          <td><span class="badge tier-${{f.tier}}">${{f.tier.toUpperCase()}}</span></td>
          <td>${{f.role}}</td>
          <td style="color:var(--accent);font-weight:600">${{f.us}}</td>
          <td>${{f.incumbent}}</td>
          <td>${{f.saas}}</td>
          <td>${{f.oss}}</td>
        </tr>
      `).join("");
    }}

    function setupUnitEconomics() {{
      const d = DATA.unit_economics_defaults || {{}};
      const inpOss = document.getElementById("inp-oss");
      const inpConv = document.getElementById("inp-conv");
      const inpEntDeals = document.getElementById("inp-ent-deals");
      const inpEntAcv = document.getElementById("inp-ent-acv");
      const inpCogs = document.getElementById("inp-cogs");
      const proPrice = d.pro_price_monthly || 29;

      if (d.active_oss_users) inpOss.value = d.active_oss_users;
      if (d.pro_conversion_pct) inpConv.value = d.pro_conversion_pct;
      if (d.enterprise_deals !== undefined) inpEntDeals.value = d.enterprise_deals;
      if (d.enterprise_acv) inpEntAcv.value = d.enterprise_acv;
      if (d.monthly_cogs_per_paid_user) inpCogs.value = d.monthly_cogs_per_paid_user;

      const recalc = () => {{
        const ossUsers = Number(inpOss.value);
        const convPct = Number(inpConv.value);
        const entDeals = Number(inpEntDeals.value);
        const entAcv = Number(inpEntAcv.value);
        const cogsMo = Number(inpCogs.value);

        const paidProUsers = Math.round(ossUsers * (convPct / 100));
        const proArr = paidProUsers * proPrice * 12;
        const entArr = entDeals * entAcv;
        const totalArr = proArr + entArr;
        const totalCogs = (paidProUsers * cogsMo * 12) + (entDeals * 1200);
        const grossMarginPct = totalArr > 0 ? Math.max(0, ((totalArr - totalCogs) / totalArr) * 100) : 0;
        const entSharePct = totalArr > 0 ? (entArr / totalArr) * 100 : 0;

        document.getElementById("lbl-oss").textContent = ossUsers.toLocaleString() + " users";
        document.getElementById("lbl-pro").textContent = `${{convPct.toFixed(1)}}% (${{paidProUsers}} seats @ $${{proPrice}}/mo)`;
        document.getElementById("lbl-ent-deals").textContent = `${{entDeals}} B2B contracts`;
        document.getElementById("lbl-ent-acv").textContent = `$${{entAcv.toLocaleString()}}/yr`;
        document.getElementById("lbl-cogs").textContent = `$${{cogsMo.toFixed(2)}}/mo`;

        document.getElementById("out-arr").textContent = `$${{Math.round(totalArr).toLocaleString()}}`;
        document.getElementById("out-margin").textContent = `${{grossMarginPct.toFixed(1)}}%`;
        document.getElementById("out-ent-share").textContent = `${{entSharePct.toFixed(0)}}%`;

        const svg = document.getElementById("econ-svg");
        const maxW = 440;
        const proW = totalArr > 0 ? (proArr / totalArr) * maxW : 0;
        const entW = totalArr > 0 ? (entArr / totalArr) * maxW : 0;
        svg.innerHTML = `
          <text x="20" y="24" fill="#94a3b8" font-size="11">ARR Mix: Pro PLG ($${{proArr.toLocaleString()}}) vs. B2B Enterprise ($${{entArr.toLocaleString()}})</text>
          <rect x="20" y="34" width="${{proW.toFixed(1)}}" height="26" fill="#a855f7" rx="4" />
          <rect x="${{(20 + proW).toFixed(1)}}" y="34" width="${{entW.toFixed(1)}}" height="26" fill="#f59e0b" rx="4" />
          <text x="20" y="82" fill="#10b981" font-size="11">Annual Gross Profit: $${{Math.max(0, totalArr - totalCogs).toLocaleString()}} (Annual COGS: $${{Math.round(totalCogs).toLocaleString()}})</text>
        `;
      }};

      [inpOss, inpConv, inpEntDeals, inpEntAcv, inpCogs].forEach(el => el.addEventListener("input", recalc));
      recalc();
    }}

    function renderTables() {{
      const vocBody = document.getElementById("voc-tbody");
      vocBody.innerHTML = (DATA.switch_triggers || []).map(v => `
        <tr>
          <td><strong>${{v.pain}}</strong><br/><span style="color:var(--muted);font-size:0.75rem">${{v.source}}</span></td>
          <td><span class="badge sev-${{v.severity}}">${{v.severity}}</span></td>
          <td>${{v.response}}</td>
        </tr>
      `).join("");

      const riskBody = document.getElementById("risk-tbody");
      riskBody.innerHTML = (DATA.kill_risks || []).map(r => `
        <tr>
          <td><strong>${{r.risk}}</strong></td>
          <td><span class="badge sev-${{r.severity}}">${{r.severity}}</span></td>
          <td>${{r.mitigation}}</td>
        </tr>
      `).join("");
    }}

    document.querySelectorAll("#tier-filters button").forEach(btn => {{
      btn.addEventListener("click", () => {{
        document.querySelectorAll("#tier-filters button").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        renderFeatures(btn.dataset.tier);
      }});
    }});

    renderSizing();
    renderQuadrant();
    renderFeatures("all");
    setupUnitEconomics();
    renderTables();
  </script>
</body>
</html>
"""
    out_path = Path(out_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_doc, encoding="utf-8")
    print(f"Generated interactive market & commercial dashboard at {out_path.resolve()}")
    return str(out_path.resolve())


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate single-file interactive Market & Commercial Strategy HTML dashboard")
    parser.add_argument("--data", default=DEFAULT_DATA_FILE, help="Path to market_data.json")
    parser.add_argument("--out", default=DEFAULT_OUT_FILE, help="Output HTML file path")
    parser.add_argument("--init-sample-json", action="store_true", help="Write sample market_data.json template if missing")
    args = parser.parse_args()

    if args.init_sample_json:
        p = Path(args.data)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(default_market_data(), indent=2), encoding="utf-8")
        print(f"Initialized sample market_data.json at {p.resolve()}")

    generate_market_dashboard(data_file=args.data, out_file=args.out)


if __name__ == "__main__":
    main()
