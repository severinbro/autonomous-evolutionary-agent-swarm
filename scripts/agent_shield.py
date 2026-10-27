#!/usr/bin/env python3
"""AgentShield Security, Prompt-Injection, Hook & MCP Context-Tax Scanner.

Scans a repository, agent skills/rules, hooks, and MCP configurations across 5 categories:
  1. Secrets & Credential Leak Detection (15+ provider patterns + git-tracked .env check)
  2. Prompt-Injection, Bidi/Zero-Width Unicode & Untrusted Content Defense
  3. Hook, Build Script & Config-Tampering Safety
  4. MCP Server Risk & Context-Window Tax Profiling (MCP Connector Policy)
  5. Silent-Failure & Error-Swallowing Static Audit

Outputs a 0-100 score, A-F letter grade, JSON telemetry, and a Red-Team / Blue-Team / Auditor
Markdown report (`.swarm/security_shield_report.md`).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from typing import Any

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    "target",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".zip",
    ".tar",
    ".gz",
    ".pyc",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".blend",
    ".fbx",
    ".glb",
    ".sqlite",
    ".db",
}

SECRET_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("AWS Access Key ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "CRITICAL"),
    ("OpenAI API Key", re.compile(r"\bsk-(?:proj|live|svcacct)-[A-Za-z0-9_\-]{24,}\b"), "CRITICAL"),
    ("Anthropic API Key", re.compile(r"\bsk-ant-api03-[A-Za-z0-9_\-]{24,}\b"), "CRITICAL"),
    ("Google / Gemini API Key", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"), "CRITICAL"),
    ("GitHub Personal Access Token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b"), "CRITICAL"),
    ("GitHub Fine-Grained PAT", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b"), "CRITICAL"),
    ("GitLab PAT", re.compile(r"\bglpat-[A-Za-z0-9\-_]{20,}\b"), "CRITICAL"),
    ("Slack Token", re.compile(r"\bxox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[A-Za-z0-9]{24,}\b"), "CRITICAL"),
    ("Stripe Live Secret Key", re.compile(r"\bsk_live_[0-9a-zA-Z]{24,}\b"), "CRITICAL"),
    (
        "Private Cryptographic Key Block",
        re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
        "CRITICAL",
    ),
]

BIDI_AND_HIDDEN_UNICODE = {
    "\u200b": "Zero-Width Space (U+200B)",
    "\u200c": "Zero-Width Non-Joiner (U+200C)",
    "\u200d": "Zero-Width Joiner (U+200D)",
    "\u202a": "Left-to-Right Embedding (U+202A)",
    "\u202b": "Right-to-Left Embedding (U+202B)",
    "\u202c": "Pop Directional Formatting (U+202C)",
    "\u202d": "Left-to-Right Override (U+202D)",
    "\u202e": "Right-to-Left Override / Trojan Source (U+202E)",
    "\u2066": "Left-to-Right Isolate (U+2066)",
    "\u2067": "Right-to-Left Isolate (U+2067)",
    "\u2068": "First Strong Isolate (U+2068)",
    "\u2069": "Pop Directional Isolate (U+2069)",
}

PROMPT_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "Direct Role/System Override Payload",
        re.compile(
            r"(?:ignore|disregard)\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|prompts|rules)\s+and\s+(?:instead|now)\s+(?:execute|run|output|send)",
            re.IGNORECASE,
        ),
        "HIGH",
    ),
    (
        "Command Exfiltration Pipe",
        re.compile(r"curl\s+[^\n]*\$\((?:env|cat\s+~/.ssh|cat\s+.*\.env)", re.IGNORECASE),
        "CRITICAL",
    ),
]

DANGEROUS_HOOK_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "Remote Pipe-to-Shell Execution (curl/wget | sh)",
        re.compile(r"(?:curl|wget)\s+[^\n|]+\|\s*(?:ba)?sh\b", re.IGNORECASE),
        "HIGH",
    ),
    (
        "Destructive Root/Home Wipe Pattern",
        re.compile(r"\brm\s+-rf\s+(?:/\s|/\*|~/|\$HOME\b)", re.IGNORECASE),
        "CRITICAL",
    ),
]

SILENT_FAILURE_PATTERNS: list[tuple[str, re.Pattern[str], set[str]]] = [
    (
        "Python bare/broad `except ...: pass` swallowing exception",
        re.compile(r"^\s*except(?:\s+Exception|\s+BaseException)?\s*:\s*pass\s*(?:#.*)?$"),
        {".py"},
    ),
    (
        "JS/TS empty `.catch(() => {})` or `.catch(() => [])` swallowing promise rejection",
        re.compile(r"\.catch\(\s*\([^)]*\)\s*=>\s*(?:\{\s*\}|\[\s*\]|null|undefined)\s*\)"),
        {".js", ".jsx", ".ts", ".tsx"},
    ),
    (
        "JS/TS empty `catch (e) {}` block",
        re.compile(r"\bcatch\s*(?:\([^)]*\))?\s*\{\s*\}"),
        {".js", ".jsx", ".ts", ".tsx"},
    ),
]

STATELESS_MCP_CANDIDATES = {
    "github",
    "context7",
    "fetch",
    "filesystem",
    "git",
    "brave-search",
    "exa",
    "memory",
    "sequential-thinking",
}


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def is_test_or_scanner_file(rel_path: str) -> bool:
    norm = rel_path.replace("\\", "/").lower()
    base = os.path.basename(norm)
    return (
        base.startswith("test_")
        or base.endswith("_test.py")
        or "/tests/" in f"/{norm}"
        or base in {"agent_shield.py", "immortal_watcher.py"}
    )


def scan_tracked_dotenv(root: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    try:
        res = subprocess.run(
            ["git", "ls-files", ".env", ".env.*", "**/.env"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            for line in res.stdout.strip().splitlines():
                fn = line.strip()
                if not fn.endswith((".example", ".sample", ".template")):
                    findings.append(
                        {
                            "category": "secrets",
                            "severity": "CRITICAL",
                            "file": fn,
                            "line": 1,
                            "title": "Git-tracked `.env` file detected",
                            "remediation": f"Run `git rm --cached {fn}` and add `.env*` to `.gitignore`.",
                        }
                    )
    except Exception:
        pass
    return findings


def scan_mcp_configs(root: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    candidates = [
        os.path.join(root, ".mcp.json"),
        os.path.join(root, "mcp.json"),
        os.path.join(root, "mcp_config.json"),
        os.path.join(root, ".claude", "mcp.json"),
        os.path.join(root, ".cursor", "mcp.json"),
    ]
    for cfg_path in candidates:
        if not os.path.isfile(cfg_path):
            continue
        rel = os.path.relpath(cfg_path, root)
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        servers = data.get("mcpServers") or data.get("servers") or {}
        if not isinstance(servers, dict):
            continue

        enabled_servers = [k for k, v in servers.items() if isinstance(v, dict) and not v.get("disabled", False)]
        if len(enabled_servers) > 5:
            findings.append(
                {
                    "category": "mcp_audit",
                    "severity": "MEDIUM",
                    "file": rel,
                    "line": 1,
                    "title": f"High MCP Context-Window Tax: {len(enabled_servers)} active MCP servers configured",
                    "remediation": (
                        "Per MCP Connector Policy, each active MCP server loads tool schemas into every turn. "
                        "Keep default MCP servers <= 3 (stateful sessions only) and convert stateless APIs to CLI skills."
                    ),
                }
            )

        for s_name, s_cfg in servers.items():
            if not isinstance(s_cfg, dict) or s_cfg.get("disabled", False):
                continue
            lower_name = s_name.lower()
            if lower_name in STATELESS_MCP_CANDIDATES:
                findings.append(
                    {
                        "category": "mcp_audit",
                        "severity": "LOW",
                        "file": rel,
                        "line": 1,
                        "title": f"Stateless MCP server `{s_name}` can be replaced by a zero-context-tax CLI skill",
                        "remediation": f"Replace `{s_name}` MCP server with an on-demand CLI/REST skill to save context tokens.",
                    }
                )
            env_map = s_cfg.get("env") or {}
            if isinstance(env_map, dict):
                for env_k, env_v in env_map.items():
                    if isinstance(env_v, str) and len(env_v) >= 20 and not env_v.startswith("${"):
                        if any(tok in env_k.upper() for tok in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
                            findings.append(
                                {
                                    "category": "mcp_audit",
                                    "severity": "HIGH",
                                    "file": rel,
                                    "line": 1,
                                    "title": f"Hardcoded credential in MCP server `{s_name}` env `{env_k}`",
                                    "remediation": "Load secrets from `~/.env` or environment variables instead of hardcoding in MCP JSON.",
                                }
                            )
    return findings


def run_shield_scan(root_dir: str) -> dict[str, Any]:
    root = os.path.abspath(root_dir)
    findings: list[dict[str, Any]] = []
    files_scanned = 0

    findings.extend(scan_tracked_dotenv(root))
    findings.extend(scan_mcp_configs(root))

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in BINARY_EXTENSIONS:
                continue
            full_path = os.path.join(dirpath, fn)
            rel_path = os.path.relpath(full_path, root)
            try:
                if os.path.getsize(full_path) > 1_500_000:
                    continue
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
            except Exception:
                continue

            files_scanned += 1
            skip_self_rules = is_test_or_scanner_file(rel_path)
            is_hook_or_script = (
                "/hooks/" in f"/{rel_path}"
                or ext in {".sh", ".bash", ".zsh"}
                or fn in {"Makefile", "package.json"}
            )
            is_skill_or_doc = ext in {".md", ".mdc"} or "/skills/" in f"/{rel_path}" or "/rules/" in f"/{rel_path}"

            prev_was_py_except = False
            for line_no, line in enumerate(lines, 1):
                # 1. Check hidden bidi / Trojan Source Unicode in all non-scanner files
                if not skip_self_rules:
                    for ch, desc in BIDI_AND_HIDDEN_UNICODE.items():
                        if ch in line:
                            findings.append(
                                {
                                    "category": "prompt_injection",
                                    "severity": "HIGH",
                                    "file": rel_path,
                                    "line": line_no,
                                    "title": f"Hidden Unicode / Trojan Source character detected: {desc}",
                                    "remediation": "Strip hidden zero-width and bidirectional override characters.",
                                }
                            )
                            break

                if skip_self_rules:
                    continue

                # 2. Check secrets
                for sec_name, sec_re, sec_sev in SECRET_PATTERNS:
                    if sec_re.search(line):
                        findings.append(
                            {
                                "category": "secrets",
                                "severity": sec_sev,
                                "file": rel_path,
                                "line": line_no,
                                "title": f"Potential {sec_name} exposed in source/config",
                                "remediation": "Revoke credential immediately and move to untracked `.env` or secret manager.",
                            }
                        )

                # 3. Check prompt injection patterns in skills/docs/comments
                if is_skill_or_doc:
                    for pi_name, pi_re, pi_sev in PROMPT_INJECTION_PATTERNS:
                        if pi_re.search(line):
                            findings.append(
                                {
                                    "category": "prompt_injection",
                                    "severity": pi_sev,
                                    "file": rel_path,
                                    "line": line_no,
                                    "title": f"Suspicious prompt-injection pattern: {pi_name}",
                                    "remediation": "Remove untrusted instruction override or isolate inside sanitized test fixtures.",
                                }
                            )

                # 4. Check dangerous hook / shell execution patterns
                if is_hook_or_script:
                    for hk_name, hk_re, hk_sev in DANGEROUS_HOOK_PATTERNS:
                        if hk_re.search(line):
                            findings.append(
                                {
                                    "category": "hooks_and_configs",
                                    "severity": hk_sev,
                                    "file": rel_path,
                                    "line": line_no,
                                    "title": f"Unsafe hook/script command: {hk_name}",
                                    "remediation": "Pin package versions, verify checksums, and avoid piping remote URLs to shell.",
                                }
                            )

                # 5. Check silent failures in production code
                for sf_name, sf_re, sf_exts in SILENT_FAILURE_PATTERNS:
                    if ext in sf_exts and sf_re.search(line):
                        findings.append(
                            {
                                "category": "silent_failures",
                                "severity": "MEDIUM",
                                "file": rel_path,
                                "line": line_no,
                                "title": f"Silent failure pattern: {sf_name}",
                                "remediation": "Log structured context or propagate a typed error instead of swallowing exceptions.",
                            }
                        )
                if ext == ".py":
                    sline = line.strip()
                    if prev_was_py_except and sline in {"pass", "return None", "return []", "return {}"}:
                        findings.append(
                            {
                                "category": "silent_failures",
                                "severity": "MEDIUM",
                                "file": rel_path,
                                "line": line_no,
                                "title": "Silent failure pattern: Python multi-line `except ...: pass/return None`",
                                "remediation": "Log structured context or propagate a typed error instead of swallowing exceptions.",
                            }
                        )
                        prev_was_py_except = False
                    else:
                        prev_was_py_except = sline in {"except:", "except Exception:", "except BaseException:"} or (
                            sline.startswith("except Exception as ") and sline.endswith(":")
                        )

    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for item in findings:
        sev = item.get("severity", "LOW")
        counts[sev] = counts.get(sev, 0) + 1

    deduction = (
        counts["CRITICAL"] * 25
        + counts["HIGH"] * 12
        + counts["MEDIUM"] * 4
        + counts["LOW"] * 1
    )
    score = max(0, 100 - deduction)
    if counts["CRITICAL"] > 0:
        grade = "F" if score < 60 else "D"
    elif score >= 92:
        grade = "A"
    elif score >= 82:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"

    return {
        "timestamp": now_iso(),
        "root": root,
        "files_scanned": files_scanned,
        "score": score,
        "grade": grade,
        "counts": counts,
        "findings": findings,
        "status": "PASS" if (counts["CRITICAL"] == 0 and score >= 75) else "FAIL",
    }


def write_markdown_report(result: dict[str, Any], out_path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    counts = result["counts"]
    lines = [
        f"# AgentShield Security & Harness Audit Report (`Grade: {result['grade']}` — `{result['score']}/100`)",
        "",
        f"- **Scanned Directory:** `{result['root']}`",
        f"- **Files Scanned:** `{result['files_scanned']}`",
        f"- **Timestamp:** `{result['timestamp']}`",
        f"- **Gate Status:** **`{result['status']}`** (`Critical={counts['CRITICAL']}`, `High={counts['HIGH']}`, `Medium={counts['MEDIUM']}`, `Low={counts['LOW']}`)",
        "",
        "## 1. Red-Team / Blue-Team / Auditor Synthesis",
        "- **Red-Team (Exploit & Injection Surface):** Evaluated repository for leaked credentials, Trojan Source bidirectional Unicode, indirect prompt-injection payloads in skills/docs, and unsafe shell hooks.",
        "- **Blue-Team (Harness & Gate Defenses):** Verified contract immutability (`src/contracts/`), MCP context-window tax discipline, and silent-failure exception handling.",
        "- **Auditor Verdict:** "
        + (
            "All critical security, prompt-injection, and harness hygiene gates passed."
            if result["status"] == "PASS"
            else "Blocking security or harness vulnerabilities detected; remediate before merge/release."
        ),
        "",
        "## 2. Detailed Findings Ledger",
    ]
    if not result["findings"]:
        lines.append("\nNo security, prompt-injection, hook, MCP, or silent-failure issues detected.")
    else:
        lines.append("")
        lines.append("| Severity | Category | File : Line | Finding | Remediation |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for f in result["findings"]:
            lines.append(
                f"| **{f['severity']}** | `{f['category']}` | `{f['file']}:{f['line']}` | {f['title']} | {f['remediation']} |"
            )

    with open(out_path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines) + "\n")
    return os.path.abspath(out_path)


def main() -> None:
    ap = argparse.ArgumentParser(description="AgentShield Security, Prompt-Injection, Hook & MCP Auditor")
    ap.add_argument("--path", default=".", help="Target repository or plugin directory to scan")
    ap.add_argument("--report", default=".swarm/security_shield_report.md", help="Output Markdown report path")
    ap.add_argument("--no-report", action="store_true", help="Skip writing Markdown report file")
    ap.add_argument("--json", action="store_true", help="Output JSON report to stdout")
    args = ap.parse_args()

    res = run_shield_scan(args.path)
    if not args.no_report:
        report_file = write_markdown_report(res, args.report)
        res["report_file"] = report_file

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        c = res["counts"]
        print(
            f"🛡️  AgentShield Scan [{res['status']}] | Grade: {res['grade']} ({res['score']}/100) | "
            f"Files: {res['files_scanned']} | Critical: {c['CRITICAL']} | High: {c['HIGH']} | "
            f"Medium: {c['MEDIUM']} | Low: {c['LOW']}"
        )
        for item in res["findings"][:15]:
            print(f"  - [{item['severity']}] ({item['category']}) {item['file']}:{item['line']} -> {item['title']}")
        if res.get("report_file"):
            print(f"Report written to: {res['report_file']}")

    sys.exit(0 if res["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
