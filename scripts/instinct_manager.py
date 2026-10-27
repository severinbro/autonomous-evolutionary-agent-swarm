#!/usr/bin/env python3
"""Cross-Project Instincts & Context-Budgeted Memory Engine (Continuous Learning v2).

Upgrades flat `.swarm/lessons_learned.md` into confidence-scored, stack-ranked
atomic Instincts with automatic project-to-global promotion and context-budgeted
Top-K prompt injection (inspired by ECC continuous-learning-v2 / Homunculus).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
from typing import Any

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GLOBAL_SWARM_DIR = os.path.join(PLUGIN_DIR, ".swarm_global")
GLOBAL_INSTINCTS_FILE = os.path.join(GLOBAL_SWARM_DIR, "instincts.json")
GLOBAL_PROJECTS_FILE = os.path.join(GLOBAL_SWARM_DIR, "projects.json")

DEFAULT_MIN_CONFIDENCE = 0.70
DEFAULT_MAX_INJECTED = 6
PROMOTE_CONFIDENCE_THRESHOLD = 0.80


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def slugify(text: str, max_len: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].strip("-") or "instinct"


def get_project_id(cwd: str | None = None) -> tuple[str, str]:
    """Return (project_hash, project_root_path)."""
    root = os.path.abspath(cwd or os.getcwd())
    proj_hash = hashlib.sha256(root.encode("utf-8")).hexdigest()[:12]
    return proj_hash, root


def detect_repo_stacks(cwd: str | None = None) -> list[str]:
    """Auto-detect programming languages and frameworks in the target workspace."""
    root = os.path.abspath(cwd or os.getcwd())
    stacks: set[str] = {"general"}
    try:
        entries = set(os.listdir(root))
    except Exception:
        return sorted(stacks)

    if entries & {"pyproject.toml", "requirements.txt", "setup.py", "Pipfile"}:
        stacks.add("python")
    if entries & {"package.json", "tsconfig.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb"}:
        stacks.add("typescript")
        stacks.add("web")
    if "Cargo.toml" in entries:
        stacks.add("rust")
    if "go.mod" in entries:
        stacks.add("go")
    if "ProjectSettings" in entries or "Assets" in entries:
        stacks.add("unity")

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", ".venv", "venv", "target", "dist", "build"}]
        for fn in filenames:
            if fn.endswith(".py"):
                stacks.add("python")
            elif fn.endswith((".ts", ".tsx", ".js", ".jsx", ".html", ".css")):
                stacks.add("typescript")
                stacks.add("web")
            elif fn.endswith(".rs"):
                stacks.add("rust")
            elif fn.endswith(".go"):
                stacks.add("go")
            elif fn.endswith(".cs"):
                stacks.add("unity")
        if len(stacks) >= 5:
            break

    return sorted(stacks)


def _load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def resolve_project_instincts_file(cwd: str | None = None) -> str:
    root = os.path.abspath(cwd or os.getcwd())
    return os.path.join(root, ".swarm", "instincts.json")


def register_project(cwd: str | None = None) -> str:
    proj_id, root = get_project_id(cwd)
    projects = _load_json(GLOBAL_PROJECTS_FILE, {"projects": {}})
    projects.setdefault("projects", {})[proj_id] = {
        "id": proj_id,
        "name": os.path.basename(root) or root,
        "path": root,
        "stacks": detect_repo_stacks(root),
        "last_updated": now_iso(),
    }
    _save_json(GLOBAL_PROJECTS_FILE, projects)
    return proj_id


def record_instinct(
    rule: str,
    instinct_id: str = "",
    category: str = "architecture",
    stacks: list[str] | None = None,
    initial_confidence: float = 0.70,
    cwd: str | None = None,
    auto_promote: bool = True,
) -> dict[str, Any]:
    """Record or reinforce an atomic instinct in project memory and auto-promote if qualified."""
    proj_id = register_project(cwd)
    detected_stacks = stacks if stacks else detect_repo_stacks(cwd)
    iid = instinct_id.strip() if instinct_id else slugify(f"{category}-{rule[:40]}")

    proj_file = resolve_project_instincts_file(cwd)
    store = _load_json(proj_file, {"instincts": {}})
    instincts = store.setdefault("instincts", {})

    if iid in instincts:
        entry = instincts[iid]
        entry["observations"] = int(entry.get("observations", 1)) + 1
        entry["confidence"] = round(min(0.95, float(entry.get("confidence", initial_confidence)) + 0.12), 2)
        existing_stacks = set(entry.get("stacks", [])) | set(detected_stacks)
        entry["stacks"] = sorted(existing_stacks)
        seen = set(entry.get("projects_seen", [proj_id])) | {proj_id}
        entry["projects_seen"] = sorted(seen)
        entry["last_seen"] = now_iso()
    else:
        entry = {
            "id": iid,
            "rule": rule.strip(),
            "category": category.strip() or "general",
            "stacks": sorted(set(detected_stacks)),
            "confidence": round(max(0.30, min(0.95, float(initial_confidence))), 2),
            "observations": 1,
            "projects_seen": [proj_id],
            "scope": "project",
            "created_at": now_iso(),
            "last_seen": now_iso(),
        }
        instincts[iid] = entry

    _save_json(proj_file, store)

    if auto_promote:
        _sync_with_global(entry)

    return entry


def _sync_with_global(project_entry: dict[str, Any]) -> bool:
    """Merge instinct sighting into global store and promote if cross-project or high-confidence."""
    global_store = _load_json(GLOBAL_INSTINCTS_FILE, {"instincts": {}})
    g_instincts = global_store.setdefault("instincts", {})
    iid = project_entry["id"]

    if iid in g_instincts:
        g_entry = g_instincts[iid]
        seen = set(g_entry.get("projects_seen", [])) | set(project_entry.get("projects_seen", []))
        g_entry["projects_seen"] = sorted(seen)
        g_entry["observations"] = max(int(g_entry.get("observations", 1)), int(project_entry.get("observations", 1))) + (
            1 if len(seen) > 1 else 0
        )
        g_entry["confidence"] = round(
            min(0.95, max(float(g_entry.get("confidence", 0.7)), float(project_entry.get("confidence", 0.7))) + 0.08),
            2,
        )
        g_entry["stacks"] = sorted(set(g_entry.get("stacks", [])) | set(project_entry.get("stacks", [])))
        g_entry["last_seen"] = now_iso()
    else:
        g_entry = dict(project_entry)

    # Promotion rule: seen in >= 2 projects OR (confidence >= 0.80 and universal/recurring)
    is_universal_cat = g_entry.get("category") in {"security", "silent-failure", "config-tampering", "contracts"}
    if len(g_entry.get("projects_seen", [])) >= 2 or (
        float(g_entry.get("confidence", 0.0)) >= PROMOTE_CONFIDENCE_THRESHOLD
        and (int(g_entry.get("observations", 1)) >= 2 or is_universal_cat)
    ):
        g_entry["scope"] = "global"
        g_instincts[iid] = g_entry
        _save_json(GLOBAL_INSTINCTS_FILE, global_store)
        return True

    return False


def promote_qualifying_instincts(cwd: str | None = None, force_id: str = "") -> list[dict[str, Any]]:
    """Promote qualifying project instincts into global cross-project memory."""
    proj_file = resolve_project_instincts_file(cwd)
    proj_store = _load_json(proj_file, {"instincts": {}})
    global_store = _load_json(GLOBAL_INSTINCTS_FILE, {"instincts": {}})
    g_instincts = global_store.setdefault("instincts", {})

    promoted: list[dict[str, Any]] = []
    for iid, entry in proj_store.get("instincts", {}).items():
        if force_id and iid != force_id:
            continue
        conf = float(entry.get("confidence", 0.0))
        obs = int(entry.get("observations", 1))
        if force_id == iid or conf >= PROMOTE_CONFIDENCE_THRESHOLD or obs >= 2:
            g_copy = dict(entry)
            g_copy["scope"] = "global"
            g_copy["confidence"] = max(conf, PROMOTE_CONFIDENCE_THRESHOLD)
            g_instincts[iid] = g_copy
            entry["scope"] = "global"
            promoted.append(g_copy)

    if promoted:
        _save_json(GLOBAL_INSTINCTS_FILE, global_store)
        _save_json(proj_file, proj_store)
    return promoted


def get_ranked_instincts(
    cwd: str | None = None,
    stacks: list[str] | None = None,
    max_k: int = DEFAULT_MAX_INJECTED,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> list[dict[str, Any]]:
    """Return top-K instincts ranked by confidence + project scope + stack relevance."""
    active_stacks = set(stacks if stacks else detect_repo_stacks(cwd))
    proj_file = resolve_project_instincts_file(cwd)
    proj_instincts = _load_json(proj_file, {"instincts": {}}).get("instincts", {})
    global_instincts = _load_json(GLOBAL_INSTINCTS_FILE, {"instincts": {}}).get("instincts", {})

    merged: dict[str, dict[str, Any]] = {}
    for iid, g_item in global_instincts.items():
        item = dict(g_item)
        item["_is_project_local"] = False
        merged[iid] = item

    for iid, p_item in proj_instincts.items():
        item = dict(p_item)
        item["_is_project_local"] = True
        if iid in merged:
            item["confidence"] = max(float(item.get("confidence", 0.0)), float(merged[iid].get("confidence", 0.0)))
        merged[iid] = item

    candidates: list[dict[str, Any]] = []
    for item in merged.values():
        conf = float(item.get("confidence", 0.0))
        if conf < min_confidence:
            continue
        item_stacks = set(item.get("stacks", ["general"]))
        stack_overlap = bool(active_stacks & (item_stacks - {"general"})) or ("general" in item_stacks)
        rank_score = conf
        if item.get("_is_project_local"):
            rank_score += 0.15
        if active_stacks & (item_stacks - {"general"}):
            rank_score += 0.15
        if stack_overlap:
            enriched = dict(item)
            enriched["rank_score"] = round(rank_score, 3)
            enriched.pop("_is_project_local", None)
            candidates.append(enriched)

    candidates.sort(key=lambda x: (x["rank_score"], x.get("observations", 1)), reverse=True)
    return candidates[:max_k]


def format_injection_block(
    cwd: str | None = None,
    stacks: list[str] | None = None,
    max_k: int = DEFAULT_MAX_INJECTED,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> str:
    """Format top-K ranked instincts as a compact prompt injection block for Step 1 workers."""
    top = get_ranked_instincts(cwd=cwd, stacks=stacks, max_k=max_k, min_confidence=min_confidence)
    if not top:
        return "No high-confidence instincts recorded yet for this stack."
    lines = [
        f"### Context-Budgeted Anti-Regression Instincts (Top {len(top)} / Max {max_k}, Confidence >= {min_confidence:.2f})"
    ]
    for idx, inst in enumerate(top, 1):
        lines.append(
            f"{idx}. **[{inst.get('category', 'general').upper()} | conf={inst.get('confidence'):.2f} | {inst.get('scope', 'project')}]** "
            f"{inst.get('rule')}"
        )
    return "\n".join(lines)


def evolve_instincts_to_markdown(cwd: str | None = None, out_path: str = ".swarm/evolved_rules.md") -> dict[str, Any]:
    """Cluster high-confidence instincts by category into a reusable evolved rules markdown document."""
    ranked = get_ranked_instincts(cwd=cwd, max_k=50, min_confidence=0.65)
    clusters: dict[str, list[dict[str, Any]]] = {}
    for inst in ranked:
        cat = inst.get("category", "general")
        clusters.setdefault(cat, []).append(inst)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    lines = [
        "# Evolved Swarm Engineering Rules & Clustered Instincts",
        "",
        f"Generated at `{now_iso()}` from project and global cross-repo instincts.",
        "",
    ]
    for cat, items in sorted(clusters.items()):
        lines.append(f"## Category: `{cat}` ({len(items)} instinct(s))")
        for item in items:
            lines.append(
                f"- **`{item['id']}`** (Confidence: `{item['confidence']:.2f}`, Scope: `{item.get('scope')}`, "
                f"Stacks: `{','.join(item.get('stacks', []))}`): {item['rule']}"
            )
        lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return {
        "evolved_file": os.path.abspath(out_path),
        "total_instincts": len(ranked),
        "categories": {k: len(v) for k, v in clusters.items()},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Cross-Project Instincts & Context-Budgeted Memory Engine")
    ap.add_argument("--record", metavar="RULE", help="Record or reinforce an atomic instinct rule")
    ap.add_argument("--id", default="", help="Optional deterministic slug ID for the instinct")
    ap.add_argument("--category", default="architecture", help="Category (e.g. silent-failure, security, architecture)")
    ap.add_argument("--stacks", default="", help="Comma-separated stack tags (auto-detected if omitted)")
    ap.add_argument("--confidence", type=float, default=0.70, help="Initial confidence (0.30 - 0.95)")
    ap.add_argument("--status", action="store_true", help="List ranked instincts for the current repository")
    ap.add_argument("--inject", action="store_true", help="Print context-budgeted Top-K Markdown injection block")
    ap.add_argument("--max-k", type=int, default=DEFAULT_MAX_INJECTED, help="Max instincts to inject (default: 6)")
    ap.add_argument(
        "--min-confidence",
        type=float,
        default=DEFAULT_MIN_CONFIDENCE,
        help="Minimum confidence threshold for injection (default: 0.70)",
    )
    ap.add_argument("--promote", action="store_true", help="Promote qualifying project instincts to global scope")
    ap.add_argument("--evolve", action="store_true", help="Cluster high-confidence instincts into .swarm/evolved_rules.md")
    ap.add_argument("--cwd", default=None, help="Target workspace directory")
    ap.add_argument("--json", action="store_true", help="Output JSON format")
    args = ap.parse_args()

    stack_list = [s.strip() for s in args.stacks.split(",") if s.strip()] if args.stacks else None

    if args.record:
        res = record_instinct(
            rule=args.record,
            instinct_id=args.id,
            category=args.category,
            stacks=stack_list,
            initial_confidence=args.confidence,
            cwd=args.cwd,
        )
        print(json.dumps(res, indent=2))
    elif args.promote:
        promoted = promote_qualifying_instincts(cwd=args.cwd, force_id=args.id)
        print(json.dumps({"promoted_count": len(promoted), "promoted": promoted}, indent=2))
    elif args.evolve:
        res = evolve_instincts_to_markdown(cwd=args.cwd)
        print(json.dumps(res, indent=2))
    elif args.inject:
        if args.json:
            print(
                json.dumps(
                    get_ranked_instincts(
                        cwd=args.cwd, stacks=stack_list, max_k=args.max_k, min_confidence=args.min_confidence
                    ),
                    indent=2,
                )
            )
        else:
            print(
                format_injection_block(
                    cwd=args.cwd, stacks=stack_list, max_k=args.max_k, min_confidence=args.min_confidence
                )
            )
    else:
        ranked = get_ranked_instincts(cwd=args.cwd, stacks=stack_list, max_k=args.max_k, min_confidence=0.30)
        if args.json:
            print(json.dumps(ranked, indent=2))
        else:
            print(f"Detected Repo Stacks: {', '.join(detect_repo_stacks(args.cwd))}")
            print(f"Ranked Instincts ({len(ranked)}):")
            for item in ranked:
                print(
                    f"  - [{item['id']}] conf={item['confidence']:.2f} rank={item['rank_score']:.2f} "
                    f"({item['scope']} | {item['category']}): {item['rule']}"
                )


if __name__ == "__main__":
    main()
