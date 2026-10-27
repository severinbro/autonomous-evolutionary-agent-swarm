---
name: knowledge-wiki
description: >-
  Insert, update, organize, and synchronize software manuals, architecture documentation,
  CLI/API references, and operational runbooks into the local Wiki.js Software Knowledge Wiki
  (/mnt/sda/wiki running at http://127.0.0.1:3001). Activate this skill whenever the user asks
  to document a project in the wiki, insert knowledge into the wiki, publish a user manual or
  architecture guide to Wiki.js, or update existing wiki pages.
---

# Software Knowledge Wiki — Knowledge Insertion Skill

This skill guides you through authoring, structuring, and publishing software manuals and technical documentation into the central **Wiki.js 2.x** instance located at **`/mnt/sda/wiki`** and served at **`http://127.0.0.1:3001`**.

---

## 1. Environment & Stack Reference

| Property | Value |
|---|---|
| **Wiki Root Directory** | `/mnt/sda/wiki` |
| **Markdown Pages Directory** | `/mnt/sda/wiki/pages` |
| **Web UI URL (Guest Read Enabled)** | `http://127.0.0.1:3001` |
| **GraphQL Endpoint** | `http://127.0.0.1:3001/graphql` |
| **Docker Compose File** | `/mnt/sda/wiki/docker-compose.yml` |
| **Sync Script** | `/mnt/sda/wiki/scripts/sync.sh` |
| **Wiki CLI** | `node /mnt/sda/wiki/scripts/wiki-cli.js` |
| **Page Template** | `/mnt/sda/wiki/templates/software-manual-template.md` |

---

## 2. Step-by-Step Knowledge Insertion Workflow

### Step 1: Ensure the Wiki.js Container Is Running

Before syncing pages, verify the container is healthy and start it if needed:

```bash
curl -sf http://127.0.0.1:3001/healthz || docker compose -f /mnt/sda/wiki/docker-compose.yml up -d
```

### Step 2: Choose the Project Namespace & Page Structure

Every software project gets its own subdirectory under `/mnt/sda/wiki/pages/<project-slug>/` (use lowercase `kebab-case` for `<project-slug>` and file names).

- **For comprehensive software projects (recommended multi-page structure):**
  - `/mnt/sda/wiki/pages/<project-slug>/overview.md` (`order: 10`, `navIcon: mdi-cube-outline`, `navLabel: "1. Overview & Quickstart"`)
  - `/mnt/sda/wiki/pages/<project-slug>/architecture.md` (`order: 20`, `navIcon: mdi-sitemap`, `navLabel: "2. System Architecture"`)
  - `/mnt/sda/wiki/pages/<project-slug>/user-manual.md` (`order: 30`, `navIcon: mdi-book-open-page-variant`, `navLabel: "3. User Manual"`)
  - `/mnt/sda/wiki/pages/<project-slug>/cli-and-api.md` (`order: 40`, `navIcon: mdi-console`, `navLabel: "4. CLI & API Reference"`)
  - `/mnt/sda/wiki/pages/<project-slug>/troubleshooting.md` (`order: 50`, `navIcon: mdi-wrench-clock`, `navLabel: "5. Operations & Runbook"`)
- **For smaller utilities or single-manual projects:**
  - `/mnt/sda/wiki/pages/<project-slug>/manual.md` (`order: 10`, `navIcon: mdi-book-open-page-variant`)

> **Important:** Never delete or overwrite unrelated project directories in `/mnt/sda/wiki/pages/`.

### Step 3: Author Markdown Pages with Wiki.js Frontmatter

Start every `.md` file with a YAML frontmatter header so `/mnt/sda/wiki/scripts/seed_wiki.js` configures both the Wiki.js page metadata and the left-hand navigation sidebar automatically:

```markdown
---
title: "<Project Name> — <Page Title>"
description: "<Concise 1-sentence summary of this page>"
published: true
tags: manual, architecture, <project-slug>
editor: markdown
section: "<Project Name>"
navLabel: "<Short Sidebar Label, e.g., 1. Overview & Quickstart>"
navIcon: mdi-rocket-launch
order: 10
---

# <Project Name> — <Page Title>

> **Executive Summary:** High-level summary of the software and what this page covers.
{.is-info}
```

#### Supported `navIcon` Values (Material Design Icons)
- **Overview / Home:** `mdi-home-analytics`, `mdi-cube-outline`
- **Quickstart / Setup:** `mdi-rocket-launch`
- **System Architecture:** `mdi-sitemap`, `mdi-layers-triple`, `mdi-brain`
- **User Manual / Guide:** `mdi-book-open-page-variant`
- **CLI / Terminal:** `mdi-console`
- **API / SDK / MCP:** `mdi-api`, `mdi-database-cog`
- **Web UI / Dashboard:** `mdi-monitor-dashboard`
- **Security / Risk:** `mdi-shield-lock`
- **Deployment / Runbook:** `mdi-wrench-clock`
- **Testing / Benchmarks:** `mdi-flask-outline`, `mdi-chart-bell-curve-cumulative`

#### Wiki.js Markdown Formatting Tips
- **Callout Blocks:** Append `{.is-info}`, `{.is-success}`, `{.is-warning}`, or `{.is-danger}` on the line immediately following a blockquote (`> ...`).
- **Mermaid Diagrams:** Use fenced ` ```mermaid ` blocks (`flowchart TD`, `flowchart LR`, `sequenceDiagram`, `stateDiagram-v2`, `classDiagram`, `erDiagram`). Always wrap node labels containing parentheses or special characters in double quotes, e.g., `A["Service (Port 8080)"]`.
- **Math Equations:** Use inline `$...$` or display `$$...$$` KaTeX blocks.

### Step 4: Register New Projects on the Landing Page (`pages/home.md`)

When adding a **new** software project to the wiki, check `/mnt/sda/wiki/pages/home.md` and add or update a **"Documented Software Catalog"** table entry linking to `/<project-slug>/overview` (or `/<project-slug>/manual`) so users browsing `http://127.0.0.1:3001/home` can jump directly to the project.

### Step 5: Sync to Wiki.js & Rebuild Sidebar Navigation

Run the synchronization script to upsert all Markdown pages via the Wiki.js GraphQL API and rebuild the sidebar navigation tree:

```bash
/mnt/sda/wiki/scripts/sync.sh
```

Alternatively, to upsert a single file directly via the CLI:

```bash
node /mnt/sda/wiki/scripts/wiki-cli.js upsert \
  --path "<project-slug>/<page-slug>" \
  --title "<Project Name> — <Page Title>" \
  --section "<Project Name>" \
  --tags "manual,<project-slug>" \
  --icon "mdi-book-open-page-variant" \
  --order 10 \
  --file /path/to/source.md
```

### Step 6: Verify Live Publication

Verify that the page is live and returns HTTP 200:

```bash
curl -sI "http://127.0.0.1:3001/<project-slug>/<page-slug>" | head -n 5
```

Report the live URL (`http://127.0.0.1:3001/<project-slug>/<page-slug>`) to the user.

---

## 3. Managing Existing Wiki Pages (CLI Reference)

```bash
# List all Markdown pages currently stored in /mnt/sda/wiki/pages
node /mnt/sda/wiki/scripts/wiki-cli.js list

# Print the Markdown source of an existing wiki page
node /mnt/sda/wiki/scripts/wiki-cli.js get <project-slug>/<page-slug>

# Delete an obsolete page from disk and prune it from Wiki.js
node /mnt/sda/wiki/scripts/wiki-cli.js delete <project-slug>/<page-slug>

# Sync all pages and prune any remote Wiki.js pages removed from disk
/mnt/sda/wiki/scripts/sync.sh --prune
```
