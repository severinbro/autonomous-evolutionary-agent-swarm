#!/usr/bin/env python3
"""Single-File Interactive Swarm Telemetry Dashboard Generator.

Reads the swarm state ledger (`swarm_tasks.json`), performance benchmarks
(`.swarm/benchmarks.json`), and cross-epoch negative memory (`lessons_learned`),
and generates a self-contained, interactive single-file HTML/CSS/JS dashboard
at `.swarm/dashboard.html`.
"""

from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
from typing import Any

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GLOBAL_TASKS_FILE = os.path.join(PLUGIN_DIR, "scripts", "swarm_tasks.json")
DEFAULT_TASKS_FILE = ".swarm/swarm_tasks.json"
DEFAULT_BENCH_FILE = ".swarm/benchmarks.json"
DEFAULT_GOAL_FILE = ".swarm/goal_loop.json"
DEFAULT_OUT_FILE = ".swarm/dashboard.html"


def load_json(path: str, fallback: dict[str, Any]) -> dict[str, Any]:
    if not os.path.exists(path):
        return fallback
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback


def generate_dashboard(
    tasks_file: str = DEFAULT_TASKS_FILE,
    bench_file: str = DEFAULT_BENCH_FILE,
    goal_file: str = DEFAULT_GOAL_FILE,
    out_file: str = DEFAULT_OUT_FILE,
) -> str:
    swarm_dir = os.path.dirname(os.path.abspath(tasks_file))
    if bench_file == DEFAULT_BENCH_FILE and not os.path.exists(bench_file):
        bench_file = os.path.join(swarm_dir, "benchmarks.json")
    if goal_file == DEFAULT_GOAL_FILE and not os.path.exists(goal_file):
        goal_file = os.path.join(swarm_dir, "goal_loop.json")
    if out_file == DEFAULT_OUT_FILE and tasks_file != DEFAULT_TASKS_FILE:
        out_file = os.path.join(swarm_dir, "dashboard.html")
    effective_tasks = tasks_file if os.path.exists(tasks_file) else GLOBAL_TASKS_FILE
    state = load_json(effective_tasks, {"current_epoch": 1, "max_epochs": 3, "subagents": {}, "epochs": {}, "lessons": []})
    bench = load_json(bench_file, {"benchmarks": {}})
    goal_state = load_json(goal_file, {"goal": "", "status": "IN_PROGRESS", "tasks": {}})

    state_json = json.dumps(state)
    bench_json = json.dumps(bench)
    goal_json = json.dumps(goal_state)
    goal_title = html.escape(state.get("project_goal") or goal_state.get("goal") or "Autonomous Evolutionary Agent Swarm")

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Swarm Telemetry Dashboard — {goal_title}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b0f17;
      --panel: #131b2e;
      --panel-alt: #19233c;
      --border: #263554;
      --text: #e2e8f0;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --green: #22c55e;
      --amber: #f59e0b;
      --red: #ef4444;
      --purple: #a855f7;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 24px;
      line-height: 1.5;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 20px 24px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      margin-bottom: 24px;
    }}
    h1 {{ font-size: 1.35rem; font-weight: 700; color: #fff; }}
    .subtitle {{ color: var(--muted); font-size: 0.9rem; margin-top: 4px; }}
    .badge {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .badge-pass {{ background: rgba(34, 197, 94, 0.18); color: var(--green); border: 1px solid rgba(34,197,94,0.4); }}
    .badge-warn {{ background: rgba(245, 158, 11, 0.18); color: var(--amber); border: 1px solid rgba(245,158,11,0.4); }}
    .badge-fail {{ background: rgba(239, 68, 68, 0.18); color: var(--red); border: 1px solid rgba(239,68,68,0.4); }}
    .badge-info {{ background: rgba(56, 189, 248, 0.18); color: var(--accent); border: 1px solid rgba(56,189,248,0.4); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 20px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
    }}
    .col-12 {{ grid-column: span 12; }}
    .col-6 {{ grid-column: span 6; }}
    .col-4 {{ grid-column: span 4; }}
    @media (max-width: 960px) {{
      .col-6, .col-4 {{ grid-column: span 12; }}
    }}
    h2 {{
      font-size: 1rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--accent);
      margin-bottom: 14px;
    }}
    .stepper {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 14px;
    }}
    .step-box {{
      padding: 14px 16px;
      border-radius: 10px;
      background: var(--panel-alt);
      border: 1px solid var(--border);
    }}
    .step-box.active {{
      border-color: var(--accent);
      box-shadow: 0 0 0 1px var(--accent);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
    }}
    th, td {{
      text-align: left;
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
    }}
    th {{ color: var(--muted); font-weight: 600; }}
    .bar-wrap {{
      width: 100%;
      background: #0d1322;
      height: 10px;
      border-radius: 6px;
      overflow: hidden;
      margin-top: 4px;
    }}
    .bar-fill {{
      height: 100%;
      background: linear-gradient(90deg, var(--accent), var(--green));
    }}
    .lesson-item {{
      padding: 10px 12px;
      background: var(--panel-alt);
      border-left: 3px solid var(--amber);
      border-radius: 6px;
      margin-bottom: 8px;
      font-size: 0.88rem;
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Autonomous Evolutionary Swarm &amp; Goal-Loop Telemetry</h1>
      <div class="subtitle" id="project-goal"></div>
    </div>
    <div id="epoch-pill"></div>
  </header>

  <div class="grid">
    <div class="card col-12">
      <h2>Evolutionary Funnel &amp; Goal-Convergence Progression (Runs UNTIL Desired Outcome Met)</h2>
      <div class="stepper" id="epoch-stepper"></div>
    </div>

    <div class="card col-12">
      <h2>Hierarchical Goal-Loop Tasks &amp; Sub-Tasks (Zero-Synthetic / Wired Outcome Verification)</h2>
      <div id="goal-loop-container"></div>
    </div>

    <div class="card col-6">
      <h2>Triad Audit &amp; SOTA Scores by Epoch (1–10)</h2>
      <div id="epoch-scores"></div>
    </div>

    <div class="card col-6">
      <h2>Cross-Epoch Negative Memory (Lessons Learned)</h2>
      <div id="lessons-list"></div>
    </div>

    <div class="card col-12">
      <h2>Worker Sub-Agents, Discriminator Loops (Max 8) &amp; Immortal Watcher Revivals</h2>
      <table>
        <thead>
          <tr>
            <th>Epoch</th>
            <th>Role</th>
            <th>Kind</th>
            <th>Branch</th>
            <th>Status</th>
            <th>Discriminator Loops</th>
            <th>Impl Score</th>
            <th>Goal Score</th>
            <th>Revives</th>
          </tr>
        </thead>
        <tbody id="subagents-tbody"></tbody>
      </table>
    </div>

    <div class="card col-12">
      <h2>Quantitative Performance &amp; Memory Benchmarks</h2>
      <div id="benchmarks-container"></div>
    </div>
  </div>

  <script>
    const STATE = {state_json};
    const BENCH = {bench_json};
    const GOAL = {goal_json};

    document.getElementById('project-goal').textContent =
      'Overall Project Goal: ' + (STATE.project_goal || GOAL.goal || 'Not set');
    const goalBadge = GOAL.status === 'GOAL_REACHED'
      ? '<span class="badge badge-pass" style="margin-right:8px;">GOAL REACHED</span>'
      : '<span class="badge badge-warn" style="margin-right:8px;">' + (GOAL.status || 'IN_PROGRESS') + '</span>';
    document.getElementById('epoch-pill').innerHTML =
      goalBadge + `<span class="badge badge-info">Epoch ${{STATE.current_epoch || 1}} / ${{STATE.max_epochs || 3}}</span>`;

    const funnelTitles = {{
      1: 'Epoch 1: Foundation, Core Architecture & Entrypoint Wiring',
      2: 'Epoch 2: SOTA Feature Injection & Elevation',
      3: 'Epoch 3: Hardening, Polish & Zero-Defect Outcome Convergence'
    }};

    const stepperEl = document.getElementById('epoch-stepper');
    const maxEp = Math.max(3, Number(STATE.max_epochs || 3), Number(STATE.current_epoch || 1));
    for (let ep = 1; ep <= maxEp; ep++) {{
      const rec = (STATE.epochs || {{}})[String(ep)] || {{}};
      const conv = (rec.convergence || {{}}).decision || (ep === STATE.current_epoch ? 'ACTIVE' : 'PENDING');
      const title = funnelTitles[ep] || `Epoch ${{ep}}: Goal-Loop Outcome & Authenticity Remediation`;
      const box = document.createElement('div');
      box.className = 'step-box' + (ep === STATE.current_epoch ? ' active' : '');
      box.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
          <strong>${{title}}</strong>
          <span class="badge ${{conv.includes('CONVERGED') ? 'badge-pass' : 'badge-info'}}">${{conv}}</span>
        </div>
        <div style="font-size:0.82rem;color:var(--muted);">
          Intermittent Report: ${{rec.intermittent_report ? rec.intermittent_report.report_path : 'Pending'}}
        </div>
      `;
      stepperEl.appendChild(box);
    }}

    const goalEl = document.getElementById('goal-loop-container');
    const gTasks = Object.values(GOAL.tasks || {{}});
    if (!gTasks.length) {{
      goalEl.innerHTML = '<div style="color:var(--muted);font-size:0.88rem;">No Goal-Loop tasks registered yet.</div>';
    }} else {{
      let gHtml = '<table><thead><tr><th>ID</th><th>Task / Sub-Task</th><th>Target / Wiring Files</th><th>Validation / Outcome Cmd</th><th>Iterations</th><th>Status</th></tr></thead><tbody>';
      gTasks.forEach(t => {{
        const tSt = t.status || 'PENDING';
        const tBadge = tSt === 'VERIFIED_COMPLETE' ? 'badge-pass' : (tSt === 'NEEDS_ITERATION' ? 'badge-fail' : 'badge-info');
        gHtml += `<tr><td><strong>${{t.task_id}}</strong></td><td><strong>${{t.title}}</strong><br><span style="color:var(--muted);font-size:0.8rem;">${{t.objective || ''}}</span></td><td><code>${{t.wiring_target || '-'}}</code></td><td><code>${{t.outcome_cmd || t.validation_cmd || '-'}}</code></td><td>-</td><td><span class="badge ${{tBadge}}">${{tSt}}</span></td></tr>`;
        Object.values(t.subtasks || {{}}).forEach(sub => {{
          const sSt = sub.status || 'PENDING';
          const sBadge = sSt === 'VERIFIED_COMPLETE' ? 'badge-pass' : (sSt === 'NEEDS_ITERATION' ? 'badge-fail' : 'badge-warn');
          const filesStr = [...(sub.target_files || []), ...(sub.wiring_files || [])].join(', ') || '-';
          gHtml += `<tr><td style="padding-left:24px;">↳ <code>${{sub.subtask_id}}</code></td><td>${{sub.title}}<br><span style="color:var(--muted);font-size:0.8rem;">${{sub.objective || ''}}</span></td><td><code>${{filesStr}}</code></td><td><code>${{sub.outcome_cmd || sub.validation_cmd || '-'}}</code></td><td>${{sub.iterations || 0}}</td><td><span class="badge ${{sBadge}}">${{sSt}}</span></td></tr>`;
        }});
      }});
      gHtml += '</tbody></table>';
      goalEl.innerHTML = gHtml;
    }}

    const scoresEl = document.getElementById('epoch-scores');
    const epochsObj = STATE.epochs || {{}};
    Object.keys(epochsObj).sort().forEach(epKey => {{
      const ep = epochsObj[epKey];
      const a = ep.audits || {{}};
      const s = ep.sota_evaluation || {{}};
      const metrics = [
        ['Rigor Audit', a.rigor ? a.rigor.score : null],
        ['Safety Audit', a.safety ? a.safety.score : null],
        ['Innovation Audit', a.innovation ? a.innovation.score : null],
        ['SOTA Innovation', s.innovation_vs_sota_score ?? null],
        ['SOTA Implementation', s.implementation_vs_sota_score ?? null]
      ];
      const block = document.createElement('div');
      block.style.marginBottom = '16px';
      block.innerHTML = `<div style="font-weight:600;margin-bottom:8px;">Epoch ${{epKey}} Scorecard</div>`;
      metrics.forEach(([label, val]) => {{
        const num = val !== null && val !== undefined ? Number(val) : 0;
        const pct = Math.min(100, Math.max(0, num * 10));
        block.innerHTML += `
          <div style="margin-bottom:8px;font-size:0.84rem;">
            <div style="display:flex;justify-content:space-between;">
              <span>${{label}}</span>
              <span>${{val !== null && val !== undefined ? num.toFixed(1) + ' / 10' : 'Pending'}}</span>
            </div>
            <div class="bar-wrap"><div class="bar-fill" style="width:${{pct}}%"></div></div>
          </div>
        `;
      }});
      scoresEl.appendChild(block);
    }});

    const lessonsEl = document.getElementById('lessons-list');
    const lessons = STATE.lessons || [];
    if (!lessons.length) {{
      lessonsEl.innerHTML = '<div style="color:var(--muted);font-size:0.88rem;">No negative memory invariants recorded yet.</div>';
    }} else {{
      lessons.forEach(item => {{
        const div = document.createElement('div');
        div.className = 'lesson-item';
        div.innerHTML = `<strong>[Epoch ${{item.epoch || 1}} | ${{item.category || 'general'}}]</strong> ${{item.lesson}}`;
        lessonsEl.appendChild(div);
      }});
    }}

    const tbody = document.getElementById('subagents-tbody');
    const subs = Object.values(STATE.subagents || {{}});
    if (!subs.length) {{
      tbody.innerHTML = '<tr><td colspan="9" style="color:var(--muted);">No sub-agents registered yet.</td></tr>';
    }} else {{
      subs.forEach(s => {{
        const st = s.status || 'RUNNING';
        const badgeClass = st === 'APPROVED' || st === 'MERGED' ? 'badge-pass' : (st === 'REFINING' ? 'badge-warn' : 'badge-info');
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${{s.epoch || 1}}</td>
          <td><strong>${{s.role || 'Worker'}}</strong></td>
          <td>${{s.agent_kind || 'worker'}}</td>
          <td><code>${{s.branch || '-'}}</code></td>
          <td><span class="badge ${{badgeClass}}">${{st}}</span></td>
          <td>${{s.loop_count || 0}} / ${{s.max_loops || 5}}</td>
          <td>${{s.impl_score !== null && s.impl_score !== undefined ? s.impl_score + '/10' : '-'}}</td>
          <td>${{s.goal_score !== null && s.goal_score !== undefined ? s.goal_score + '/10' : '-'}}</td>
          <td>${{s.revive_attempts || 0}} / ${{s.max_revive_attempts || 5}}</td>
        `;
        tbody.appendChild(tr);
      }});
    }}

    const benchContainer = document.getElementById('benchmarks-container');
    const benchMap = BENCH.benchmarks || {{}};
    const benchNames = Object.keys(benchMap);
    if (!benchNames.length) {{
      benchContainer.innerHTML = '<div style="color:var(--muted);font-size:0.88rem;">No quantitative benchmarks recorded yet.</div>';
    }} else {{
      let htmlRows = '<table><thead><tr><th>Benchmark</th><th>Epoch</th><th>Median (ms)</th><th>Mean (ms)</th><th>Peak RSS (KB)</th><th>Delta vs Baseline</th><th>Status</th></tr></thead><tbody>';
      benchNames.forEach(bName => {{
        (benchMap[bName] || []).forEach(r => {{
          const delta = r.delta_vs_baseline_pct !== null && r.delta_vs_baseline_pct !== undefined
            ? (r.delta_vs_baseline_pct > 0 ? '+' + r.delta_vs_baseline_pct + '%' : r.delta_vs_baseline_pct + '%')
            : 'Baseline';
          htmlRows += `
            <tr>
              <td><strong>${{bName}}</strong></td>
              <td>${{r.epoch}}</td>
              <td>${{r.median_ms}} ms</td>
              <td>${{r.mean_ms}} ms</td>
              <td>${{r.peak_rss_kb}} KB</td>
              <td>${{delta}}</td>
              <td><span class="badge ${{r.status === 'PASS' ? 'badge-pass' : 'badge-fail'}}">${{r.status}}</span></td>
            </tr>
          `;
        }});
      }});
      htmlRows += '</tbody></table>';
      benchContainer.innerHTML = htmlRows;
    }}
  </script>
</body>
</html>
"""
    os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print(f"Generated interactive Swarm Telemetry Dashboard at: {os.path.abspath(out_file)}")
    return os.path.abspath(out_file)


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate Single-File Interactive Swarm Telemetry Dashboard")
    ap.add_argument("--tasks-file", default=DEFAULT_TASKS_FILE, help="Path to swarm_tasks.json")
    ap.add_argument("--bench-file", default=DEFAULT_BENCH_FILE, help="Path to benchmarks.json")
    ap.add_argument("--out", default=DEFAULT_OUT_FILE, help="Output HTML file path (default: .swarm/dashboard.html)")
    args = ap.parse_args()
    generate_dashboard(tasks_file=args.tasks_file, bench_file=args.bench_file, out_file=args.out)


if __name__ == "__main__":
    main()
