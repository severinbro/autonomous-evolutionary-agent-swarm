#!/usr/bin/env python3
"""Zotero Library Research & Reasoning Tool for Antigravity (`agent-swarm`).

Supports dual-mode operation:
  1. Zotero v3 Web API (using ZOTERO_API_KEY and ZOTERO_USER_ID from env, ~/.env,
     ./.env, or the file named by ZOTERO_ENV_FILE).
  2. Local Zotero SQLite Fallback (read-only query of ZOTERO_SQLITE_PATH or
     ~/Zotero/zotero.sqlite) when offline or when API keys are not configured.

Cache location: ZOTERO_CACHE_DIR (default ~/.cache/zotero).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CACHE_DIR = Path(os.environ.get("ZOTERO_CACHE_DIR") or Path.home() / ".cache" / "zotero")

SQLITE_CANDIDATES = [
    Path(os.environ.get("ZOTERO_SQLITE_PATH", "")) if os.environ.get("ZOTERO_SQLITE_PATH") else None,
    Path.home() / "Zotero" / "zotero.sqlite",
]


def find_local_sqlite() -> Path | None:
    for p in SQLITE_CANDIDATES:
        if p and p.is_file():
            return p
    return None


def load_credentials() -> tuple[str | None, str | None]:
    """Load ZOTERO_API_KEY and ZOTERO_USER_ID safely from environment or .env files."""
    api_key = os.environ.get("ZOTERO_API_KEY")
    user_id = os.environ.get("ZOTERO_USER_ID")

    if api_key and user_id:
        return api_key.strip(), user_id.strip()

    search_paths = [
        Path.home() / ".env",
        Path(os.environ["ZOTERO_ENV_FILE"]) if os.environ.get("ZOTERO_ENV_FILE") else None,
        Path.cwd() / ".env",
    ]
    for env_path in search_paths:
        if env_path and env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("ZOTERO_API_KEY=") and not api_key:
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            api_key = val
                    elif line.startswith("ZOTERO_USER_ID=") and not user_id:
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            user_id = val
            except OSError:
                continue

    return (api_key.strip() if api_key else None), (user_id.strip() if user_id else None)


def sqlite_search_fallback(query: str | None, limit: int = 25, as_json: bool = False) -> None:
    db_path = find_local_sqlite()
    if not db_path:
        print(
            "Error: Neither Zotero API credentials (ZOTERO_API_KEY, ZOTERO_USER_ID) nor a local "
            "zotero.sqlite database (ZOTERO_SQLITE_PATH or ~/Zotero/zotero.sqlite) were found.",
            file=sys.stderr,
        )
        sys.exit(1)

    uri = f"file:{db_path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    cur = conn.cursor()

    sql = """
    SELECT i.key, it.typeName,
           MAX(CASE WHEN f.fieldName = 'title' THEN idv.value END) AS title,
           MAX(CASE WHEN f.fieldName = 'date' THEN idv.value END) AS date_val,
           MAX(CASE WHEN f.fieldName = 'DOI' THEN idv.value END) AS doi_val,
           MAX(CASE WHEN f.fieldName = 'abstractNote' THEN idv.value END) AS abstract_val
    FROM items i
    JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
    LEFT JOIN itemData id ON i.itemID = id.itemID
    LEFT JOIN fields f ON id.fieldID = f.fieldID
    LEFT JOIN itemDataValues idv ON id.valueID = idv.valueID
    LEFT JOIN deletedItems di ON i.itemID = di.itemID
    WHERE di.itemID IS NULL
      AND it.typeName NOT IN ('attachment', 'note', 'annotation')
    GROUP BY i.itemID
    """
    rows = cur.execute(sql).fetchall()
    conn.close()

    q_lower = (query or "").lower()
    results = []
    for key, type_name, title, date_val, doi_val, abstract_val in rows:
        title_str = title or "Untitled"
        abs_str = abstract_val or ""
        if q_lower and (q_lower not in title_str.lower() and q_lower not in abs_str.lower()):
            continue
        results.append({
            "key": key,
            "itemType": type_name,
            "title": title_str,
            "year": (date_val or "")[:4],
            "doi": doi_val or "",
            "abstractPreview": abs_str[:250],
        })
        if len(results) >= limit:
            break

    if as_json:
        print(json.dumps(results, indent=2))
        return

    print(f"[Local SQLite: {db_path}] Found {len(results)} matching items:\n")
    for r in results:
        print(f"{r['key']:<10} | {r['year']:<4} | {r['title'][:65]}")


def zotero_request(
    endpoint: str,
    params: dict | None = None,
    raw_binary: bool = False,
    format_type: str | None = None,
):
    """Execute a GET request against the Zotero API."""
    api_key, user_id = load_credentials()
    if not api_key or not user_id:
        return None, None

    base_url = f"https://api.zotero.org/users/{user_id}"
    clean_endpoint = endpoint.lstrip("/")
    url = f"{base_url}/{clean_endpoint}"

    if params:
        query_str = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        if query_str:
            url += f"?{query_str}"

    headers = {
        "Zotero-API-Version": "3",
        "Zotero-API-Key": api_key,
        "User-Agent": "Antigravity-Zotero-Tool/2.0",
    }
    if format_type:
        headers["Accept"] = format_type

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            total_results = resp.headers.get("Total-Results")
            if raw_binary:
                return resp.read(), total_results
            content = resp.read().decode("utf-8", errors="replace")
            if format_type and format_type != "application/json":
                return content, total_results
            try:
                return json.loads(content), total_results
            except json.JSONDecodeError:
                return content, total_results
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode("utf-8", errors="replace")
        print(f"Zotero API Error {e.code}: {e.reason}\n{error_msg}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_collections(args):
    """List collections in the user's library."""
    data, _ = zotero_request("collections", {"limit": args.limit})
    if data is None:
        db_path = find_local_sqlite()
        if not db_path:
            print("Error: ZOTERO_API_KEY/ZOTERO_USER_ID not set and no local zotero.sqlite found.", file=sys.stderr)
            sys.exit(1)
        uri = f"file:{db_path}?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True)
        rows = conn.execute("SELECT key, collectionName FROM collections ORDER BY collectionName LIMIT ?", (args.limit,)).fetchall()
        conn.close()
        for k, name in rows:
            print(f"{k:<10} | {name}")
        return

    if not isinstance(data, list):
        print(data)
        return

    by_key = {}
    for c in data:
        d = c.get("data", {})
        meta = c.get("meta", {})
        k = d.get("key")
        parent = d.get("parentCollection") or None
        by_key[k] = {
            "key": k,
            "name": d.get("name"),
            "parentCollection": parent,
            "numItems": meta.get("numItems", 0),
            "numCollections": meta.get("numCollections", 0),
            "version": d.get("version"),
            "deleted": d.get("deleted", False),
        }

    def is_effectively_deleted(key):
        cur = key
        visited = set()
        while cur:
            if cur in visited:
                break
            visited.add(cur)
            cdata = by_key.get(cur)
            if not cdata:
                return True
            if cdata.get("deleted", False):
                return True
            cur = cdata.get("parentCollection")
            if not cur or cur is False:
                break
        return False

    if not args.include_deleted:
        active_keys = {k for k in by_key if not is_effectively_deleted(k)}
        by_key = {k: v for k, v in by_key.items() if k in active_keys}

    children_of = {}
    for k, c in by_key.items():
        parent = c["parentCollection"] if c["parentCollection"] in by_key else None
        children_of.setdefault(parent, []).append(k)

    if args.json:
        if args.root_only:
            root_colls = [by_key[k] for k in children_of.get(None, [])]
            print(json.dumps(root_colls, indent=2))
        else:
            print(json.dumps(list(by_key.values()), indent=2))
        return

    label = "all" if args.include_deleted else "active"
    print(f"Found {len(by_key)} {label} collection(s):\n")
    print(f"{'Key':<10} | {'Items':<6} | {'Name'}")
    print("-" * 65)

    def print_tree(parent_k, depth=0):
        for k in sorted(children_of.get(parent_k, []), key=lambda x: by_key[x]["name"].lower()):
            c = by_key[k]
            indent = "  " * depth + ("└── " if depth > 0 else "")
            del_marker = " [DELETED]" if c.get("deleted") else ""
            print(f"{c['key']:<10} | {c['numItems']:<6} | {indent}{c['name']}{del_marker}")
            if not args.root_only:
                print_tree(k, depth + 1)

    print_tree(None)


def cmd_search(args):
    """Search items in the user's library."""
    params = {
        "q": args.query,
        "itemType": args.item_type if args.item_type else "-attachment || note",
        "tag": args.tag,
        "sort": args.sort or "dateModified",
        "direction": args.direction or "desc",
        "limit": args.limit,
    }
    endpoint = f"collections/{args.collection}/items" if args.collection else "items"

    data, total = zotero_request(endpoint, params)
    if data is None:
        sqlite_search_fallback(args.query, limit=args.limit, as_json=args.json)
        return

    if not isinstance(data, list):
        print(data)
        return

    results = []
    for item in data:
        d = item.get("data", {})
        meta = item.get("meta", {})
        creators = d.get("creators", [])
        author_names = []
        for cr in creators:
            if "name" in cr:
                author_names.append(cr["name"])
            elif "lastName" in cr:
                author_names.append(cr["lastName"])
        author_str = ", ".join(author_names[:2])
        if len(author_names) > 2:
            author_str += " et al."

        year = d.get("date", "")[:4] if d.get("date") else ""
        results.append({
            "key": d.get("key"),
            "itemType": d.get("itemType"),
            "title": d.get("title", d.get("name", "Untitled")),
            "authors": author_str,
            "year": year,
            "publication": d.get("publicationTitle", d.get("proceedingsTitle", "")),
            "doi": d.get("doi", ""),
            "numChildren": meta.get("numChildren", 0),
        })

    if args.json:
        print(json.dumps(results, indent=2))
        return

    print(f"Found {total or len(results)} matching items (showing up to {args.limit}):\n")
    print(f"{'Key':<10} | {'Year':<4} | {'Authors':<25} | {'Title'}")
    print("-" * 80)
    for r in results:
        title = (r["title"][:45] + "...") if len(r["title"]) > 48 else r["title"]
        print(f"{r['key']:<10} | {r['year']:<4} | {r['authors'][:25]:<25} | {title}")


def cmd_get(args):
    """Get detailed metadata for a specific item, plus list children."""
    data, _ = zotero_request(f"items/{args.key}")
    if data is None:
        sqlite_search_fallback(args.key, limit=1, as_json=args.json)
        return
    children, _ = zotero_request(f"items/{args.key}/children")

    d = data.get("data", {})
    attachments = []
    notes = []

    if isinstance(children, list):
        for ch in children:
            cd = ch.get("data", {})
            if cd.get("itemType") == "attachment":
                attachments.append({
                    "key": cd.get("key"),
                    "contentType": cd.get("contentType"),
                    "filename": cd.get("filename"),
                    "linkMode": cd.get("linkMode"),
                    "title": cd.get("title"),
                })
            elif cd.get("itemType") == "note":
                notes.append({
                    "key": cd.get("key"),
                    "notePreview": re.sub(r"<[^>]+>", " ", cd.get("note", ""))[:120].strip(),
                })

    details = {
        "key": d.get("key"),
        "itemType": d.get("itemType"),
        "title": d.get("title"),
        "creators": d.get("creators", []),
        "date": d.get("date"),
        "publicationTitle": d.get("publicationTitle", d.get("proceedingsTitle", "")),
        "abstractNote": d.get("abstractNote", ""),
        "doi": d.get("doi"),
        "url": d.get("url"),
        "tags": [t.get("tag") for t in d.get("tags", [])],
        "attachments": attachments,
        "notes": notes,
    }

    if args.json:
        print(json.dumps(details, indent=2))
        return

    print(f"=== [{details['itemType']}] {details['title']} ===")
    print(f"Key:         {details['key']}")
    creators_str = ", ".join(
        c.get("name", f"{c.get('firstName', '')} {c.get('lastName', '')}".strip()) for c in details["creators"]
    )
    print(f"Authors:     {creators_str}")
    print(f"Date:        {details['date']}")
    if details["publicationTitle"]:
        print(f"Publication: {details['publicationTitle']}")
    if details["doi"]:
        print(f"DOI:         {details['doi']}")
    if details["tags"]:
        print(f"Tags:        {', '.join(details['tags'])}")
    if details["abstractNote"]:
        print(f"\nAbstract:\n{details['abstractNote']}")
    if attachments:
        print(f"\nAttachments ({len(attachments)}):")
        for att in attachments:
            print(f"  - [{att['key']}] {att.get('filename') or att.get('title')} ({att.get('contentType')})")
    if notes:
        print(f"\nNotes ({len(notes)}):")
        for n in notes:
            print(f"  - [{n['key']}] {n['notePreview']}")


def find_pdf_attachment(item_key: str) -> tuple[str | None, str | None]:
    data, _ = zotero_request(f"items/{item_key}")
    if data is None:
        return None, None
    d = data.get("data", {})
    if d.get("itemType") == "attachment" and d.get("contentType") == "application/pdf":
        return item_key, d.get("filename", f"{item_key}.pdf")

    children, _ = zotero_request(f"items/{item_key}/children")
    if isinstance(children, list):
        for ch in children:
            cd = ch.get("data", {})
            if cd.get("itemType") == "attachment" and cd.get("contentType") == "application/pdf":
                return cd.get("key"), cd.get("filename", f"{cd.get('key')}.pdf")

    return None, None


def cmd_pdf(args):
    """Download and extract text from a paper's PDF."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    att_key, filename = find_pdf_attachment(args.key)
    if not att_key:
        print(f"Error: No PDF attachment found for item key '{args.key}'", file=sys.stderr)
        sys.exit(1)

    cached_pdf = CACHE_DIR / f"{att_key}.pdf"
    if not cached_pdf.exists():
        print(f"Downloading PDF attachment {att_key} ({filename})...", file=sys.stderr)
        pdf_bytes, _ = zotero_request(f"items/{att_key}/file", raw_binary=True)
        cached_pdf.write_bytes(pdf_bytes)

    cmd = ["pdftotext"]
    if args.first_page:
        cmd.extend(["-f", str(args.first_page)])
    if args.last_page:
        cmd.extend(["-l", str(args.last_page)])
    cmd.extend([str(cached_pdf), "-"])

    try:
        text = subprocess.check_output(cmd).decode("utf-8", errors="replace")
    except subprocess.CalledProcessError as e:
        print(f"Error running pdftotext: {e}", file=sys.stderr)
        sys.exit(1)

    if args.grep:
        pattern = re.compile(args.grep, re.IGNORECASE)
        matching_lines = [line for line in text.splitlines() if pattern.search(line)]
        print(f"Matches for '{args.grep}' ({len(matching_lines)} lines):")
        print("\n".join(matching_lines[: args.limit]))
        return

    if args.max_chars and len(text) > args.max_chars:
        print(text[: args.max_chars])
        print(f"\n[... Truncated at {args.max_chars} chars. Total extracted: {len(text)} chars ...]")
    else:
        print(text)


def cmd_notes(args):
    """Retrieve all notes and annotations for an item."""
    children, _ = zotero_request(f"items/{args.key}/children")
    notes = []
    annotations = []

    if isinstance(children, list):
        for ch in children:
            cd = ch.get("data", {})
            itype = cd.get("itemType")
            if itype == "note":
                raw_html = cd.get("note", "")
                plain_text = re.sub(r"<[^>]+>", " ", raw_html).strip()
                notes.append({"key": cd.get("key"), "text": plain_text})
            elif itype == "attachment":
                att_children, _ = zotero_request(f"items/{cd.get('key')}/children")
                if isinstance(att_children, list):
                    for ach in att_children:
                        acd = ach.get("data", {})
                        if acd.get("itemType") == "annotation":
                            annotations.append({
                                "key": acd.get("key"),
                                "type": acd.get("annotationType"),
                                "text": acd.get("annotationText"),
                                "comment": acd.get("annotationComment"),
                                "color": acd.get("annotationColor"),
                                "page": acd.get("annotationPageLabel"),
                            })

    if args.json:
        print(json.dumps({"notes": notes, "annotations": annotations}, indent=2))
        return

    if not notes and not annotations:
        print(f"No notes or annotations found for item {args.key}.")
        return

    if notes:
        print(f"=== Notes ({len(notes)}) ===")
        for n in notes:
            print(f"[{n['key']}]")
            print(n["text"])
            print("-" * 40)

    if annotations:
        print(f"\n=== Annotations & Highlights ({len(annotations)}) ===")
        for a in annotations:
            page_info = f" (Page {a['page']})" if a.get("page") else ""
            print(f"[{a['key']} | {a['type'].upper()}{page_info}]")
            if a.get("text"):
                print(f"  Highlighted: \"{a['text']}\"")
            if a.get("comment"):
                print(f"  Comment: {a['comment']}")
            print("-" * 40)


def cmd_export(args):
    """Export item or collection in BibTeX or CSL format."""
    api_format = "bibtex" if args.format in ("bib", "bibtex") else "csljson"
    format_map = {
        "bibtex": "application/x-bibtex",
        "csljson": "application/vnd.citationstyles.csl+json",
    }
    format_type = format_map.get(api_format, "application/x-bibtex")
    endpoint = f"items/{args.key}" if args.key else f"collections/{args.collection}/items"

    content, _ = zotero_request(endpoint, {"format": api_format}, format_type=format_type)
    print(content)


def main():
    parser = argparse.ArgumentParser(description="Zotero Library Research & Reasoning Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_colls = subparsers.add_parser("collections", help="List collections")
    p_colls.add_argument("--limit", type=int, default=100, help="Max collections to fetch")
    p_colls.add_argument("--root-only", action="store_true", help="Only show root collections")
    p_colls.add_argument("--include-deleted", action="store_true", help="Include deleted collections")
    p_colls.add_argument("--json", action="store_true", help="Output JSON")
    p_colls.set_defaults(func=cmd_collections)

    p_search = subparsers.add_parser("search", help="Search items in library")
    p_search.add_argument("query", nargs="?", default=None, help="Search query string")
    p_search.add_argument("-c", "--collection", help="Filter by collection key")
    p_search.add_argument("-t", "--tag", help="Filter by tag")
    p_search.add_argument("--item-type", help="Filter by itemType")
    p_search.add_argument(
        "--sort",
        choices=["dateModified", "dateAdded", "title", "creator", "date"],
        default="dateModified",
    )
    p_search.add_argument("--direction", choices=["asc", "desc"], default="desc")
    p_search.add_argument("--limit", type=int, default=25, help="Number of items to return")
    p_search.add_argument("--json", action="store_true", help="Output JSON")
    p_search.set_defaults(func=cmd_search)

    p_get = subparsers.add_parser("get", help="Get item metadata and attachments")
    p_get.add_argument("key", help="Zotero item key")
    p_get.add_argument("--json", action="store_true", help="Output JSON")
    p_get.set_defaults(func=cmd_get)

    p_pdf = subparsers.add_parser("pdf", help="Download/cache and read PDF text")
    p_pdf.add_argument("key", help="Item key or attachment key")
    p_pdf.add_argument("-f", "--first-page", type=int, help="First page to extract")
    p_pdf.add_argument("-l", "--last-page", type=int, help="Last page to extract")
    p_pdf.add_argument("-m", "--max-chars", type=int, default=15000, help="Max characters to print")
    p_pdf.add_argument("-g", "--grep", help="Filter lines matching regex/text inside the PDF")
    p_pdf.add_argument("--limit", type=int, default=30, help="Max matching lines for grep")
    p_pdf.set_defaults(func=cmd_pdf)

    p_notes = subparsers.add_parser("notes", help="Get notes and annotations for an item")
    p_notes.add_argument("key", help="Item key")
    p_notes.add_argument("--json", action="store_true", help="Output JSON")
    p_notes.set_defaults(func=cmd_notes)

    p_export = subparsers.add_parser("export", help="Export citation in BibTeX or CSL-JSON")
    p_export.add_argument("-k", "--key", help="Item key")
    p_export.add_argument("-c", "--collection", help="Collection key")
    p_export.add_argument("-f", "--format", choices=["bib", "csljson"], default="bib", help="Export format")
    p_export.set_defaults(func=cmd_export)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
