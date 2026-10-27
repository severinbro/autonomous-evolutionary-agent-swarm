---
name: commercial-strategy
description: "Use when deciding how a product will make money or be licensed: open-core versus permissive licensing, B2B tiers, pricing and unit economics, copyleft dependency risk, or competitive kill risks. Runs standalone or inside /product-discovery."
disable-model-invocation: false
triggers: [user, model]
---

# Commercial Strategy, Open-Core Licensing & Adversarial Moat Audit (`/commercial-strategy`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

## Overview

Design a verifiable **Open-Source / Commercial Open-Core / B2B Enterprise** monetization architecture, third-party dependency license audit, unit-economics COGS model, and adversarial kill-risk register. Output the complete specification to `.swarm/blueprint/commercial_strategy_report.md` and update the interactive simulator at `.swarm/blueprint/market_dashboard.html`.

**Core principle:** Every licensing boundary, tier gate, COGS estimate, and dependency audit row cites concrete repository files (`path:line`) or market research figures.

---

## 1. Observable Conditional Predicates (Input Grounding & License Sufficiency Gate)

Evaluate these observable workspace predicates before spawning subagents:

| Observable Workspace Condition | Required Action |
| :--- | :--- |
| **Condition A: `.swarm/blueprint/market_research_report.md` or `.swarm/blueprint/deep_research_report.md` exists** | Read those files first and bind Section 2–3 tier prices, ACV, and buyer personas directly to the verified competitor prices, switch triggers, and SOM formula in `.swarm/blueprint/market_research_report.md`. |
| **Condition B: Dependency manifests exist (`package.json`, `Cargo.toml`, `pyproject.toml`, `go.mod`, `LICENSE`)** | Inspect manifests and directory boundaries (`core/`, `ee/`, `enterprise/`). Flag any copyleft (`GPL`, `AGPL`, `SSPL`) dependency with its exact manifest `path:line` and specify either a permissive (`MIT`, `Apache-2.0`, `BSD`) replacement or process-level isolation boundary. |
| **Condition C: Existing Repo scores `Commercial & License Hygiene >= 8.5/10`** (clean license headers, zero copyleft contamination, clear OSS/B2B boundary or pure OSS goal, and gross margin $\ge 75\%$) | Record **`VERDICT: COMMERCIAL & LICENSE ARCHITECTURE ALREADY OPTIMAL (NO STRUCTURAL CHANGES REQUIRED)`** in Section 1 and set Section 5 Epoch 1 and Epoch 2 items to `NONE — ALREADY OPTIMAL`. |
| **Condition D: Greenfield Repo OR `Commercial & License Hygiene < 8.5/10`** | Record **`VERDICT: COMMERCIAL & LICENSE UPGRADES SPECIFIED`** in Section 1 and specify concrete repository boundary and monetization deliverables in Section 5. |

---

## 2. Two Parallel Commercial & Adversarial Sub-Agents

Define (`define_subagent`) and invoke (`invoke_subagent`) two specialized sub-agents in parallel:

### Agent 1: `pricing_monetization_strategist` (Open-Core Packaging, B2B Enterprise Gates & Unit Economics)
- **Output Slice:** `.swarm/blueprint/commercial_slice_pricing.md`
- **Required Deliverables:**
  1. **Licensing Architecture Selection:** Specify one of:
     - *Permissive Core (`MIT` / `Apache-2.0`) + Commercial Enterprise Directory (`ee/` or `enterprise/`)*
     - *Source-Available / Time-Delayed Open Source (`BSL 1.1` / `ELv2` / `FSL-1.1-Apache-2.0`)*
     - *Dual-Licensing (`AGPLv3` + Commercial B2B License)*
     - *Pure Permissive Open Source (`MIT` / `Apache-2.0`)* (when project goal is 100% open community utility)
  2. **3-Tier Feature-Gating Matrix:**
     - **Tier 1 (`OSS Core — $0`):** Complete single-player/local core engine, CLI/SDK, and standard import/export bridges so individual developers experience zero friction.
     - **Tier 2 (`Pro / Cloud Team — $X/seat/mo or Usage-Based`):** Managed cloud workspace, real-time collaboration sync, hosted compute/AI credits, and version history.
     - **Tier 3 (`B2B Enterprise — $Y/yr ACV`):** Governance, security, compliance, and scale features: SAML/OIDC SSO, granular RBAC, immutable audit logs, self-hosted Kubernetes/Docker deployment, air-gapped Ed25519 license keys, BYO-GPU/LLM endpoints, and SLA support.
  3. **Unit Economics & COGS Formula:** Compute monthly marginal COGS per Free OSS user (`$0` cloud cost via local-first/BYO-compute execution), per Paid Pro user, and per B2B Enterprise tenant (compute/GPU tokens, storage, relay bandwidth), verifying target SaaS/Enterprise Gross Margin $\ge 75\%$:
     $$\text{Gross Margin (\%)} = \frac{\text{ARPU} - \text{Monthly COGS per User}}{\text{ARPU}} \times 100$$

### Agent 2: `moat_and_risk_skeptic` (Adversarial VC Devil's Advocate, Cannibalization & IP Hygiene)
- **Output Slice:** `.swarm/blueprint/commercial_slice_moat.md`
- **Required Deliverables:**
  1. **Open-Source Cannibalization vs. Adoption Balance Check:** Verify that Tier 1 (`OSS Core`) solves individual developer workflows completely while Tier 3 (`B2B Enterprise`) gates multi-team governance/SSO/compliance that enterprises require during procurement.
  2. **Incumbent & Foundation-Model Kill-Risk Matrix:** Identify why an incumbent or frontier AI provider could bundle this in 6 months, and specify the concrete **structural moat** (deterministic domain kernel, local-first + air-gapped hybrid execution, proprietary workflow state, ecosystem/plugin lock-in).
  3. **B2B Procurement & IP Hygiene Audit:** Audit manifests (`path:line`) for copyleft contamination (`GPL`/`AGPL`/`SSPL`) and specify enterprise compliance controls (zero-telemetry air-gap mode, SOC2/GDPR data residency, offline cryptographic license verification).

---

## 3. Positive Structural Output Contract

Once both sub-agents finish their slices, produce the two mandatory deliverables:

### Deliverable A: `.swarm/blueprint/commercial_strategy_report.md`
Write `.swarm/blueprint/commercial_strategy_report.md` with these 5 sections in exact order:

```markdown
# Commercial Strategy, Open-Core Licensing & Moat Report: <Project Name>

## 1. Licensing Architecture, Sufficiency Score & Repository Boundary
- **Existing-Repo Commercial & License Hygiene Score:** `<X.X/10 or N/A — Greenfield>`
- **Sufficiency Verdict:** `<VERDICT: COMMERCIAL & LICENSE ARCHITECTURE ALREADY OPTIMAL (NO STRUCTURAL CHANGES REQUIRED) | VERDICT: COMMERCIAL & LICENSE UPGRADES SPECIFIED>`
- **Recommended License Model:** `<e.g., Apache-2.0 Core (src/core/) + Commercial B2B Enterprise (ee/)>`
- **Cloud-Strip-Mining & Adoption Rationale:** <2-3 sentences explaining how this model maximizes developer PLG adoption while protecting B2B revenue>
- **Dependency License Hygiene Table:**
  | Manifest File (`path:line`) | Dependency & Version | Detected License | Status (`CLEAN` / `COPYLEFT_RISK`) | Required Action (`Keep` / `Replace with <pkg>` / `Isolate`) |
  | :--- | :--- | :--- | :--- | :--- |
  | `<manifest:line>` | `<pkg@ver>` | `MIT` / `Apache-2.0` / `GPLv3` | `CLEAN` | `Keep` |

## 2. Three-Tier Packaging & Feature-Gating Matrix
| Feature / Module | Tier (`OSS Core ($0)` / `Pro Cloud` / `B2B Enterprise`) | Buyer Persona | Gating Rationale (Adoption Wedge vs. Governance Value) | Codebase Boundary (`src/core/` vs `ee/`) |
| :--- | :--- | :--- | :--- | :--- |
| `<Module/Feature>` | `<Tier>` | `<Persona>` | `<Rationale>` | `<Directory/File path>` |

## 3. Pricing Model & Unit Economics (COGS vs. Gross Margin)
| Tier | Price Point | Compute / Token COGS | Storage / Bandwidth COGS | Total Monthly COGS | Target Gross Margin (%) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tier 1: OSS Core** | `$0` (Local / BYO-Compute) | `$0.00` | `$0.00` | `$0.00` | `N/A (Zero Cloud Bleed)` |
| **Tier 2: Pro Cloud** | `$<X>/seat/mo` | `$<c1>` | `$<c2>` | `$<total>` | `<XX.X>%` |
| **Tier 3: B2B Enterprise** | `$<Y>/yr ACV` | `$<c1>` | `$<c2>` | `$<total>` | `<XX.X>%` |

## 4. Structural Moats & Adversarial Kill-Risk Register
| Threat Category (`Cannibalization` / `Incumbent Bundling` / `IP License` / `B2B Security`) | Specific Kill Scenario | Severity (`CRITICAL` / `HIGH` / `MEDIUM`) | Structural & Architectural Mitigation | Owning Module / Path |
| :--- | :--- | :--- | :--- | :--- |
| `<Category>` | `<Scenario>` | `<Severity>` | `<Concrete technical mitigation>` | `<path>` |

## 5. Commercial Requirements for `/coop-brainstorm` & `/invoke-swarm`
- **Epoch 1 Commercial Must-Haves:** `<NONE — ALREADY OPTIMAL | Clean src/core/ vs ee/ boundary, LICENSE headers, zero-cloud-cost local core>`
- **Epoch 2 Monetization Enablers:** `<NONE — ALREADY OPTIMAL | RBAC/SSO hooks, quota metering, offline Ed25519 license verifier, Docker/Helm self-hosted bundle>`
```

### Deliverable B: Update `.swarm/blueprint/market_data.json` & `.swarm/blueprint/market_dashboard.html`
1. Update `.swarm/blueprint/market_data.json` with `features` (`oss`, `pro`, `enterprise`), `kill_risks`, and `unit_economics_defaults` (`active_oss_users`, `pro_conversion_pct`, `pro_price_monthly`, `enterprise_deals`, `enterprise_acv`, `monthly_cogs_per_paid_user`).
2. Render and validate `.swarm/blueprint/market_dashboard.html` via `python3`:
   ```bash
   python3 "$AGENT_SWARM_HOME/scripts/market_dashboard.py" \
     --data .swarm/blueprint/market_data.json \
     --out .swarm/blueprint/market_dashboard.html
   python3 "$AGENT_SWARM_HOME/scripts/web_ui_validator.py" \
     .swarm/blueprint/market_dashboard.html
   ```

---

## 4. Zero-Context-Bloat Subagent Return Contract (`< 15 Lines`)

Both commercial subagents (and `/commercial-strategy` when returning to an orchestrator) write their full report to `.swarm/blueprint/` and return ONLY this `< 15 lines` summary:

```markdown
Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
Artifacts: .swarm/blueprint/commercial_strategy_report.md, .swarm/blueprint/market_dashboard.html (web_ui_validator: PASS)
Commercial Hygiene Score: <X.X/10 or N/A — Greenfield> (<Sufficiency Verdict>)
License Architecture: <Core License> (`src/core/`) + <Enterprise License> (`ee/`) | Copyleft Risks: <0 or N found>
Unit Economics: OSS $0 COGS | Pro $<X>/mo (<M1>% GM) | Enterprise $<Y>/yr ACV (<M2>% GM)
Top 3 Kill-Risk Mitigations:
1. <Risk 1> -> <Structural Mitigation>
2. <Risk 2> -> <Structural Mitigation>
3. <Risk 3> -> <Structural Mitigation>
Concerns / Blockers: None (or 1-line description)
```
