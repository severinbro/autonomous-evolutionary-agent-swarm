#!/usr/bin/env python3
"""3-Viewport + Reduced-Motion Real-Browser Layout, Motion & Anti-Slop Inspector (`web_ui_validator.py`).

Upgraded from a single-viewport smoke test into a comprehensive 3-viewport (`1440x900`, `768x1024`, `390x844`)
+ `prefers-reduced-motion: reduce` Real-Browser Inspector combining:
  - `leonxlnx/taste-skill` (`inspect.mjs`, `probe.mjs`, `rules.mjs`): Real-browser geometry,
    headline line-wrap measurement (`<= 2` lines), outer frame symmetry, scroll-through empty screen &
    covered-text detection, and `prefers-reduced-motion` hidden-text detection.
  - `pbakaus/impeccable` (`craft-floor.md`): Surface Mode awareness (`persuade`, `operate`, `read`,
    `experience`, `auto`), Browser Surface checks (`::selection`, `tabular-nums`), and anti-slop bans
    (`slop-eyebrow`, `slop-gradient-text`, `slop-side-stripe`, `slop-ai-palette`, `slop-icon-cards`,
    `slop-ghost-card`, `slop-numbering`, `slop-mono-prose`).
  - 100% backward compatibility with `web_ui_validator.py <file_or_url> [--json]`.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import html.parser
import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

# When run as a script with a python3 that lacks Playwright, transparently re-exec into the
# Playwright-enabled interpreter named by AGENT_SWARM_UI_PYTHON (if set). Browser binaries are located
# via Playwright's own PLAYWRIGHT_BROWSERS_PATH. Importing this module never re-execs.
_UITEST_PYTHON = os.environ.get("AGENT_SWARM_UI_PYTHON", "")

if __name__ == "__main__":
    try:
        import playwright.sync_api as _pw_check  # type: ignore  # noqa: F401
    except Exception:
        if (
            os.path.isfile(_UITEST_PYTHON)
            and os.path.realpath(sys.executable) != os.path.realpath(_UITEST_PYTHON)
            and os.environ.get("_WEB_UI_VALIDATOR_REEXEC") != "1"
        ):
            os.environ["_WEB_UI_VALIDATOR_REEXEC"] = "1"
            os.execv(_UITEST_PYTHON, [_UITEST_PYTHON, *sys.argv])


VIEWPORT_HEIGHTS: dict[int, int] = {
    1440: 900,
    1280: 800,
    1024: 768,
    768: 1024,
    390: 844,
    375: 812,
}

VIEWPORT_NAMES: dict[int, str] = {
    1440: "desktop",
    1280: "desktop",
    1024: "laptop",
    768: "tablet",
    390: "mobile",
    375: "mobile",
}

# Rules skipped in `operate` (app/dashboard/workspace) mode where quiet 1px borders, compact labels,
# repeated panels, and dense layouts are expected domain conventions (`APP_SKIP`).
OPERATE_SKIP_RULES: set[str] = {
    "headline-lines",
    "empty-screens",
    "slop-eyebrow",
    "slop-icon-cards",
    "slop-numbering",
    "slop-mono-prose",
}


class HTMLStructureParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: dict[str, int] = {}
        self.in_style = False
        self.in_script = False
        self.script_is_external = False
        self.styles: list[str] = []
        self.scripts: list[str] = []
        self.text_chunks: list[str] = []
        self._buf: list[str] = []
        self.explicit_mode: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        self.tags[t] = self.tags.get(t, 0) + 1
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        if t in ("html", "body", "main") and attr_dict.get("data-mode") in (
            "persuade",
            "operate",
            "read",
            "experience",
        ):
            self.explicit_mode = attr_dict["data-mode"]
        elif t == "meta" and attr_dict.get("name", "").lower() == "surface-mode":
            val = attr_dict.get("content", "").lower().strip()
            if val in ("persuade", "operate", "read", "experience"):
                self.explicit_mode = val

        if t == "style":
            self.in_style = True
            self._buf = []
        elif t == "script":
            self.in_script = True
            self.script_is_external = "src" in attr_dict
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t == "style" and self.in_style:
            self.in_style = False
            self.styles.append("".join(self._buf).strip())
        elif t == "script" and self.in_script:
            self.in_script = False
            if not self.script_is_external:
                self.scripts.append("".join(self._buf).strip())

    def handle_data(self, data: str) -> None:
        if self.in_style or self.in_script:
            self._buf.append(data)
        else:
            stripped = data.strip()
            if stripped:
                self.text_chunks.append(stripped)


def check_js_syntax(js_code: str, index: int) -> list[str]:
    """Use `node --check` if node is installed to verify embedded JavaScript syntax."""
    if not js_code.strip() or not shutil.which("node"):
        return []
    errors: list[str] = []
    with tempfile.NamedTemporaryFile("w", suffix=f"_script_{index}.js", delete=False, encoding="utf-8") as tmp:
        tmp.write(js_code)
        tmp_path = tmp.name
    try:
        res = subprocess.run(["node", "--check", tmp_path], capture_output=True, text=True, check=False)
        if res.returncode != 0:
            err_msg = (res.stderr or res.stdout).strip()
            errors.append(f"Embedded <script> #{index} failed `node --check`: {err_msg[:300]}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    return errors


@contextlib.contextmanager
def serve_local_file(file_path: Path):
    """Serve the parent directory of `file_path` on a throwaway 127.0.0.1 HTTP port."""
    root_dir = str(file_path.parent)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root_dir)

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=root_dir, **kwargs)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            pass

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    try:
        server = ReusableTCPServer(("127.0.0.1", 0), QuietHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{port}/{file_path.name}"
        finally:
            server.shutdown()
            server.server_close()
    except Exception:
        yield file_path.as_uri()


# Self-contained in-browser probe executed at each viewport width in Playwright
BROWSER_VIEWPORT_PROBE_JS = r"""
(arg) => {
  const modeArg = (arg && arg.mode) || 'auto';
  const W = window.innerWidth;
  const H = window.innerHeight;
  const SY = window.scrollY;
  const round = (n, d = 2) => Math.round(n * (10 ** d)) / (10 ** d);

  // 1x1 canvas color normalizer
  const cvs = document.createElement('canvas');
  cvs.width = cvs.height = 1;
  const ctx = cvs.getContext('2d', { willReadFrequently: true });
  const colorCache = new Map();
  const rgba = (c) => {
    if (!c) return { r: 0, g: 0, b: 0, a: 0 };
    if (colorCache.has(c)) return colorCache.get(c);
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = 'rgba(0,0,0,0)';
    ctx.fillStyle = c;
    ctx.fillRect(0, 0, 1, 1);
    const d = ctx.getImageData(0, 0, 1, 1).data;
    const v = { r: d[0], g: d[1], b: d[2], a: round(d[3] / 255, 2) };
    colorCache.set(c, v);
    return v;
  };
  const hex = (v) => '#' + [v.r, v.g, v.b].map((n) => n.toString(16).padStart(2, '0')).join('');
  const lum = (v) => {
    const f = (x) => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(v.r) + 0.7152 * f(v.g) + 0.0722 * f(v.b);
  };
  const contrast = (a, b) => {
    const l1 = lum(a), l2 = lum(b);
    return round((Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05), 2);
  };
  const hsl = (v) => {
    const r = v.r / 255, g = v.g / 255, b = v.b / 255;
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
    const l = (mx + mn) / 2;
    let h = 0, s = 0;
    if (mx !== mn) {
      const d = mx - mn;
      s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
      h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
      h *= 60;
    }
    return { h: Math.round(h), s: round(s, 2), l: round(l, 2) };
  };

  // Monospace detector by glyph width comparison
  const mctx = document.createElement('canvas').getContext('2d');
  const monoCache = new Map();
  const isMono = (ff) => {
    if (!ff) return false;
    if (monoCache.has(ff)) return monoCache.get(ff);
    mctx.font = `32px ${ff}`;
    const wI = mctx.measureText('iiiiiiii').width;
    const wW = mctx.measureText('WWWWWWWW').width;
    const v = Math.abs(wI - wW) < 1.0 || /mono|fira|jetbrains|consolas|courier/i.test(ff);
    monoCache.set(ff, v);
    return v;
  };

  const selLabel = (el) => {
    if (!el || !el.tagName) return 'unknown';
    const tag = el.tagName.toLowerCase();
    const id = el.id ? `#${el.id}` : '';
    const cls = typeof el.className === 'string' && el.className.trim()
      ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.')
      : '';
    return `${tag}${id}${cls}`.slice(0, 64);
  };

  const srHidden = (el) => {
    for (let p = el, i = 0; p && p !== document.body && i < 5; p = p.parentElement, i++) {
      const cs = getComputedStyle(p);
      const r = p.getBoundingClientRect();
      if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity < 0.05) return true;
      if (cs.clip === 'rect(0px, 0px, 0px, 0px)' || /inset\(50%\)/.test(cs.clipPath) || (r.width <= 2 && r.height <= 2 && cs.overflow !== 'visible')) return true;
    }
    return false;
  };

  // Auto-detect surface mode if modeArg === 'auto'
  const detectMode = () => {
    if (modeArg && modeArg !== 'auto') return modeArg;
    const explicit = document.documentElement.dataset.mode || (document.body && document.body.dataset.mode);
    if (explicit && ['persuade', 'operate', 'read', 'experience'].includes(explicit)) return explicit;
    const hasSidebar = [...document.querySelectorAll('aside, nav, [role="navigation"]')].some((el) => {
      const r = el.getBoundingClientRect();
      return r.left <= 24 && r.width >= 140 && r.width <= 360 && r.height >= H * 0.5;
    });
    const tablesAndInputs = document.querySelectorAll('table, input, select, [role="tablist"], [data-metric]').length;
    const docH = Math.max(document.documentElement.scrollHeight, document.body.scrollHeight);
    const titleText = ((document.title || '') + ' ' + ((document.querySelector('h1') && document.querySelector('h1').innerText) || '')).toLowerCase();
    if ((hasSidebar && tablesAndInputs >= 3) || (/\b(dashboard|console|telemetry|workspace|terminal|admin|ledger|monitor)\b/.test(titleText) && docH <= H * 3.2)) {
      return 'operate';
    }
    if (document.querySelectorAll('article, pre code').length >= 3 && /\b(docs|documentation|manual|reference|report|monograph)\b/.test(titleText)) {
      return 'read';
    }
    return 'persuade';
  };
  const resolvedMode = detectMode();

  // 1. Zero-size visuals & broken images (`zero-size-visual`)
  const zeroVisuals = [];
  for (const el of document.querySelectorAll('canvas, svg, img')) {
    if (el.closest('[hidden], template') || getComputedStyle(el).display === 'none') continue;
    const r = el.getBoundingClientRect();
    if (el.tagName === 'IMG') {
      const src = el.getAttribute('src') || '';
      if (src && el.complete && el.naturalWidth === 0) {
        zeroVisuals.push(`${selLabel(el)} has broken image (naturalWidth == 0, src="${src.slice(0, 60)}")`);
        continue;
      }
    }
    if (r.width <= 0 || r.height <= 0) {
      zeroVisuals.push(`${selLabel(el)} has 0x0 bounding box (${Math.round(r.width)}x${Math.round(r.height)})`);
    }
  }

  // 2. Horizontal overflow (`horizontal-overflow`)
  const docScrollW = document.documentElement.scrollWidth;
  const horizontalOverflowPx = docScrollW > W + 2 ? docScrollW - W : 0;
  let overflowCulprits = [];
  if (horizontalOverflowPx > 0) {
    const allEls = [...document.body.querySelectorAll('*')].slice(0, 5000);
    const clippedByAnc = (el) => {
      for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
        const cs = getComputedStyle(p);
        if (cs.overflowX !== 'visible' && p.getBoundingClientRect().right <= W + 2) return true;
      }
      return false;
    };
    const wide = allEls.filter((el) => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.right > W + 2 && !clippedByAnc(el);
    });
    overflowCulprits = wide
      .filter((el) => !wide.some((o) => o !== el && el.contains(o)))
      .slice(0, 4)
      .map((el) => `${selLabel(el)} (+${Math.round(el.getBoundingClientRect().right - W)}px)`);
  }

  // Helper to count rendered text lines inside an element using Range.getClientRects()
  const countLines = (el, fontSize) => {
    const tops = [];
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const range = document.createRange();
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      if (!n.nodeValue || !n.nodeValue.trim()) continue;
      range.selectNodeContents(n);
      for (const rc of range.getClientRects()) {
        if (rc.width < 1 || rc.height < fontSize * 0.35) continue;
        const mid = rc.top + rc.height / 2;
        if (!tops.some((t) => Math.abs(t - mid) < fontSize * 0.55)) tops.push(mid);
      }
    }
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const lh = cs.lineHeight === 'normal' ? fontSize * 1.2 : parseFloat(cs.lineHeight) || (fontSize * 1.2);
    const ratioLines = lh > 0 ? r.height / lh : 1;
    return { lines: Math.max(1, tops.length), ratioLines: round(ratioLines, 2) };
  };

  // 3. Headline lines (`headline-lines`: h1-h3 wrapping past 2 lines)
  const over2LineHeadings = [];
  const allHeadings = [];
  for (const h of document.querySelectorAll('h1, h2, h3')) {
    if (srHidden(h) || h.closest('[data-ui]')) continue;
    const r = h.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    const cs = getComputedStyle(h);
    const size = parseFloat(cs.fontSize) || 16;
    const text = (h.innerText || '').replace(/\s+/g, ' ').trim();
    if (!text) continue;
    const { lines, ratioLines } = countLines(h, size);
    const entry = {
      tag: h.tagName.toLowerCase(),
      selector: selLabel(h),
      text: text.slice(0, 60),
      lines,
      ratioLines,
      size: round(size, 1),
      top: Math.round(r.top + SY),
      bottom: Math.round(r.bottom + SY),
      left: Math.round(r.left),
      right: Math.round(r.right),
      el: h
    };
    allHeadings.push(entry);
    if (lines > 2 || ratioLines > 2.35) {
      over2LineHeadings.push({
        tag: entry.tag,
        selector: entry.selector,
        text: entry.text,
        lines: Math.max(lines, Math.ceil(ratioLines - 0.35)),
        size: entry.size
      });
    }
  }

  // 4. Primary h1 (`late-title`)
  const h1 = document.querySelector('h1');
  let titleStatus = { ok: true, reason: null, text: '' };
  if (!h1) {
    titleStatus = { ok: false, reason: 'Primary <h1> element is missing from the page.' };
  } else {
    const r = h1.getBoundingClientRect();
    const text = (h1.innerText || '').replace(/\s+/g, ' ').trim();
    titleStatus.text = text.slice(0, 60);
    if (r.width < 2 || r.height < 2) {
      titleStatus = { ok: false, reason: `Primary <h1> ("${titleStatus.text}") has 0x0 size or display:none.` };
    } else if (r.top >= H * 0.95) {
      titleStatus = { ok: false, reason: `Primary <h1> ("${titleStatus.text}") starts outside the first viewport (top=${Math.round(r.top)}px, viewport height=${H}px).` };
    } else {
      let op = 1.0;
      let hidden = false;
      for (let p = h1; p && p !== document.documentElement; p = p.parentElement) {
        const cs = getComputedStyle(p);
        if (cs.visibility === 'hidden' || cs.display === 'none') { hidden = true; break; }
        op *= parseFloat(cs.opacity || '1');
      }
      if (hidden || op < 0.5) {
        titleStatus = { ok: false, reason: `Primary <h1> ("${titleStatus.text}") is hidden or translucent (opacity=${round(op, 2)}).` };
      } else {
        const cx = Math.min(W - 2, Math.max(2, r.left + r.width / 2));
        const cy = Math.min(H - 2, Math.max(2, r.top + Math.min(r.height, 80) / 2));
        const hit = document.elementFromPoint(cx, cy);
        if (hit && hit !== h1 && !h1.contains(hit) && !hit.contains(h1)) {
          const hcs = getComputedStyle(hit);
          if (rgba(hcs.backgroundColor).a > 0.1 || hcs.backgroundImage !== 'none' || /^(IMG|CANVAS|VIDEO|SVG)$/i.test(hit.tagName)) {
            titleStatus = { ok: false, reason: `Primary <h1> ("${titleStatus.text}") is covered at its center by ${selLabel(hit)}.` };
          }
        }
      }
    }
  }

  // 5. Outer frame symmetry (`off-centre-frame`)
  const hasDockedSidebar = [...document.querySelectorAll('aside, nav, [role="navigation"]')].some((el) => {
    const r = el.getBoundingClientRect();
    return r.left <= 24 && r.width >= 140 && r.width <= 360 && r.height >= H * 0.5;
  });
  let offCentreFrame = null;
  if (W >= 768 && !(hasDockedSidebar && (resolvedMode === 'operate' || resolvedMode === 'read'))) {
    const structural = [...document.querySelectorAll('main, section, header, article, .container, [class*="container"], [class*="wrapper"]')]
      .filter((el) => {
        const r = el.getBoundingClientRect();
        return r.width >= W * 0.35 && r.width <= W * 0.98 && r.height >= 120 && r.top < H * 3;
      });
    const probeEls = structural.length ? structural : [...document.body.children].filter((el) => {
      const r = el.getBoundingClientRect();
      return r.width >= 160 && r.height >= 120 && !/^(SCRIPT|STYLE|NOSCRIPT)$/i.test(el.tagName);
    });
    if (probeEls.length) {
      // Measure overall content bounding box across top-level content blocks
      const childrenRects = [...document.querySelectorAll('h1, h2, p, table, canvas, svg, img, form, [data-ui]')]
        .filter((el) => !srHidden(el))
        .map((el) => el.getBoundingClientRect())
        .filter((r) => r.width >= 40 && r.height >= 16 && r.left >= 0 && r.right <= W + 4 && r.top < H * 3);
      if (childrenRects.length >= 2) {
        const minLeft = Math.max(0, Math.min(...childrenRects.map((r) => r.left)));
        const maxRight = Math.min(W, Math.max(...childrenRects.map((r) => r.right)));
        const rightMargin = W - maxRight;
        const diff = Math.abs(minLeft - rightMargin);
        const maxSide = Math.max(minLeft, rightMargin);
        if (diff >= Math.max(64, W * 0.14) && maxSide >= W * 0.25) {
          offCentreFrame = {
            leftMargin: Math.round(minLeft),
            rightMargin: Math.round(rightMargin),
            message: `Outer page content sits off-centre at ${W}px: left margin is ${Math.round(minLeft)}px while right margin is ${Math.round(rightMargin)}px (${Math.round(maxSide / W * 100)}% of viewport empty on one side).`
          };
        }
      }
    }
  }

  // Collect visible text nodes for typography, contrast, eyebrow, numbering, and mono checks
  const allNodes = [...document.body.querySelectorAll('*')].slice(0, 6000);
  const texts = [];
  const bigBoxes = [];
  for (const el of allNodes) {
    const tag = el.tagName;
    if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT' || tag === 'TEMPLATE') continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity < 0.05) continue;
    if (r.width * r.height >= 60 * 30) {
      bigBoxes.push({ el, r, cs, area: r.width * r.height, top: r.top + SY });
    }
    let direct = '';
    for (const n of el.childNodes) {
      if (n.nodeType === 3) direct += n.nodeValue;
    }
    direct = direct.replace(/\s+/g, ' ').trim();
    if (!direct || tag === 'OPTION' || el.closest('svg') || srHidden(el)) continue;
    const size = parseFloat(cs.fontSize);
    if (!size || size < 6) continue;
    const ls = cs.letterSpacing === 'normal' ? 0 : (parseFloat(cs.letterSpacing) || 0) / size;
    const lh = cs.lineHeight === 'normal' ? 1.2 : (parseFloat(cs.lineHeight) || size * 1.2) / size;
    const clipProp = (cs.webkitBackgroundClip || cs.backgroundClip || '').toLowerCase();
    const fillCol = cs.webkitTextFillColor || cs.color;
    const isGradText = clipProp.includes('text') && (rgba(fillCol).a < 0.15 || cs.backgroundImage.includes('gradient'));
    texts.push({
      el,
      selector: selLabel(el),
      tag: tag.toLowerCase(),
      text: direct,
      chars: direct.length,
      ff: cs.fontFamily,
      size: round(size, 1),
      weight: +cs.fontWeight || 400,
      ls: round(ls, 3),
      lh: round(lh, 2),
      upper: cs.textTransform === 'uppercase' || (direct.length >= 3 && direct === direct.toUpperCase() && /[A-Z]{2}/.test(direct)),
      color: cs.color,
      top: r.top + SY,
      bottom: r.bottom + SY,
      left: r.left,
      right: r.right,
      w: r.width,
      h: r.height,
      inCode: !!el.closest('pre, code, kbd, samp, textarea'),
      inUI: !!el.closest('[data-ui]'),
      inTable: !!el.closest('table'),
      isGradText
    });
  }

  // 6. Slop Eyebrow (`slop-eyebrow`): small uppercase/pill kicker directly above h1/h2
  const eyebrows = [];
  for (const h of allHeadings.filter((x) => x.tag === 'h1' || x.tag === 'h2')) {
    const cands = texts.filter((t) =>
      !t.inUI &&
      !h.el.contains(t.el) &&
      t.size <= Math.min(16, h.size * 0.55) &&
      t.chars >= 2 &&
      t.chars <= 44 &&
      t.bottom <= h.top + 6 &&
      h.top - t.bottom <= 52 &&
      t.right > h.left - 12 &&
      t.left < h.right + 12 &&
      !t.el.closest('nav, header, footer, button, a[href]')
    ).sort((a, b) => b.bottom - a.bottom);
    const cand = cands[0];
    if (!cand) continue;
    let isPill = false;
    for (let p = cand.el, i = 0; p && p !== document.body && i < 3; p = p.parentElement, i++) {
      const pcs = getComputedStyle(p);
      const pr = p.getBoundingClientRect();
      if (pr.width < 420 && pr.height < 52 && parseFloat(pcs.borderTopLeftRadius) >= 10 && (rgba(pcs.backgroundColor).a > 0.04 || parseFloat(pcs.borderTopWidth) > 0)) {
        isPill = true;
      }
    }
    if (cand.upper || cand.ls >= 0.04 || isPill) {
      eyebrows.push({
        text: cand.text.slice(0, 40),
        above: h.text.slice(0, 40),
        selector: cand.selector,
        pill: isPill
      });
    }
  }

  // 7. Slop Gradient Text (`slop-gradient-text`)
  const gradientTexts = texts.filter((t) => t.isGradText).slice(0, 5).map((t) => `${t.selector} ("${t.text.slice(0, 35)}")`);

  // 8. Slop Side-Stripe (`slop-side-stripe`) & Slop Ghost Card (`slop-ghost-card`)
  const sideStripes = [];
  const ghostCards = [];
  for (const b of bigBoxes) {
    const { el, cs, r } = b;
    if (el.closest('pre, code')) continue;
    const bt = parseFloat(cs.borderTopWidth) || 0;
    const bb = parseFloat(cs.borderBottomWidth) || 0;
    const bl = parseFloat(cs.borderLeftWidth) || 0;
    const br = parseFloat(cs.borderRightWidth) || 0;
    if (bl > 1.5 && cs.borderLeftStyle !== 'none' && rgba(cs.borderLeftColor).a > 0.1 && bl > bt + 1 && r.height >= 32) {
      sideStripes.push(`${selLabel(el)} (border-left: ${round(bl, 1)}px solid ${cs.borderLeftColor})`);
    } else if (br > 1.5 && cs.borderRightStyle !== 'none' && rgba(cs.borderRightColor).a > 0.1 && br > bt + 1 && r.height >= 32) {
      sideStripes.push(`${selLabel(el)} (border-right: ${round(br, 1)}px solid ${cs.borderRightColor})`);
    }
    // Ghost card: 1px border + soft shadow with blur >= 16px
    const has1pxBorder = bt >= 0.5 && bt <= 1.5 && bb >= 0.5 && bb <= 1.5 && bl >= 0.5 && bl <= 1.5 && rgba(cs.borderTopColor).a > 0.04;
    if (has1pxBorder && cs.boxShadow && cs.boxShadow !== 'none') {
      // In computed boxShadow, numbers after rgb(...) are offset-x offset-y blur spread
      const shNoColor = cs.boxShadow.replace(/rgba?\([^)]+\)/g, '');
      const nums = (shNoColor.match(/-?\d+(\.\d+)?px/g) || []).map((x) => parseFloat(x));
      if (nums.length >= 3 && nums[2] >= 16) {
        ghostCards.push(`${selLabel(el)} (1px border + ${nums[2]}px blur shadow)`);
      }
    }
  }

  // 9. Slop AI Palette (`slop-ai-palette`: AI Purple/Indigo hue 244..295 or Cream + Terracotta)
  const inHue = (h, a, b) => h >= a && h <= b;
  const classifyFamily = (hslVal) => {
    if (!hslVal) return null;
    const { h, s, l } = hslVal;
    if (inHue(h, 244, 295) && s >= 0.42 && l >= 0.30 && l <= 0.82) return 'ai-purple';
    if (inHue(h, 22, 62) && s >= 0.16 && l >= 0.88 && l < 0.995) return 'cream';
    if (inHue(h, 6, 30) && s >= 0.38 && s <= 0.85 && l >= 0.42 && l <= 0.72) return 'terracotta';
    return null;
  };
  const paletteHits = { 'ai-purple': [], cream: [], terracotta: [] };
  const checkColorSample = (label, cssColor) => {
    const v = rgba(cssColor);
    if (v.a < 0.2) return;
    const fam = classifyFamily(hsl(v));
    if (fam && paletteHits[fam].length < 4) {
      paletteHits[fam].push(`${label} (${hex(v)})`);
    }
  };
  checkColorSample('body-bg', getComputedStyle(document.body).backgroundColor);
  for (const b of bigBoxes.slice(0, 40)) {
    checkColorSample(selLabel(b.el), b.cs.backgroundColor);
  }
  for (const btn of document.querySelectorAll('button, a, [role="button"]')) {
    const cs = getComputedStyle(btn);
    checkColorSample(selLabel(btn), cs.backgroundColor);
    checkColorSample(selLabel(btn) + ' text', cs.color);
  }

  // 10. Slop Icon Cards (`slop-icon-cards`)
  const iconCardRows = [];
  const seenParents = new Set();
  const emojiRe = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/u;
  for (const b of bigBoxes) {
    const p = b.el.parentElement;
    if (!p || seenParents.has(p) || p.closest('[data-ui]')) continue;
    seenParents.add(p);
    const kids = [...p.children].filter((k) => {
      const r = k.getBoundingClientRect();
      return r.width >= 140 && r.width < W * 0.85 && r.height >= 80 && (k.innerText || '').trim().length >= 12;
    });
    if (kids.length < 3) continue;
    const boxed = kids.filter((k) => {
      const cs = getComputedStyle(k);
      return rgba(cs.backgroundColor).a > 0.04 || parseFloat(cs.borderTopWidth) > 0 || cs.boxShadow !== 'none';
    });
    if (boxed.length < 3) continue;
    const w0 = boxed[0].getBoundingClientRect().width;
    const h0 = boxed[0].getBoundingClientRect().height;
    const sameSize = boxed.filter((k) => {
      const r = k.getBoundingClientRect();
      return Math.abs(r.width - w0) < 6 && Math.abs(r.height - h0) < 24;
    });
    if (sameSize.length < 3) continue;
    const withIcon = sameSize.filter((k) => {
      const iconEl = k.querySelector('svg, img, i, [class*="icon" i]');
      if (iconEl) {
        const ir = iconEl.getBoundingClientRect();
        if (ir.width > 0 && ir.width <= 64 && ir.height <= 64) return true;
      }
      return emojiRe.test((k.innerText || '').slice(0, 24));
    });
    if (withIcon.length >= 3) {
      iconCardRows.push(`${selLabel(p)} (${withIcon.length} identical icon-topped cards)`);
    }
  }

  // 11. Slop Numbering (`slop-numbering`)
  const numbered = texts.filter((t) =>
    !t.inCode &&
    !t.inUI &&
    !t.inTable &&
    (/^[(\[/#]?\s?0\d{1,2}\s?[)\]/\.:—–-]?$/.test(t.text) ||
     /^0\d\s?[/\.—–-]\s/.test(t.text) ||
     /^(step|phase|no\.?|chapter|part)\s?0\d{1,2}\b/i.test(t.text))
  ).slice(0, 6).map((t) => `"${t.text}" (${t.selector})`);

  // 12. Slop Mono Prose (`slop-mono-prose`)
  const monoProseSamples = [];
  let monoProseChars = 0;
  let totalProseChars = 0;
  for (const t of texts) {
    if (t.inCode || t.inUI || t.inTable) continue;
    totalProseChars += t.chars;
    if (isMono(t.ff) && t.chars >= 15 && !/^[0-9$€£%+.,:;\s/-]+$/.test(t.text)) {
      monoProseChars += t.chars;
      if (monoProseSamples.length < 4) {
        monoProseSamples.push(`${t.selector} ("${t.text.slice(0, 36)}")`);
      }
    }
  }

  // 13. Body size & measure (`body-size-small`)
  const bodyBlocks = texts.filter((t) => (t.tag === 'p' || t.tag === 'li' || t.tag === 'dd') && t.chars >= 55 && !t.inCode && !t.inUI && !t.el.closest('footer'));
  let dominantBodySize = null;
  let maxMeasureCh = 0;
  if (bodyBlocks.length) {
    const sizeCounts = new Map();
    for (const b of bodyBlocks) {
      const sz = Math.round(b.size * 2) / 2;
      sizeCounts.set(sz, (sizeCounts.get(sz) || 0) + b.chars);
      const ch = Math.round(b.w / (b.size * 0.52));
      if (ch > maxMeasureCh) maxMeasureCh = ch;
    }
    dominantBodySize = [...sizeCounts.entries()].sort((a, b) => b[1] - a[1])[0][0];
  }

  // 14. Browser surfaces (`browser-surfaces-default`: custom ::selection and tabular-nums)
  let hasSelectionRule = false;
  for (const sheet of document.styleSheets) {
    try {
      for (const rule of sheet.cssRules || []) {
        if (rule.selectorText && rule.selectorText.includes('::selection')) {
          hasSelectionRule = true;
          break;
        }
      }
    } catch (e) {}
  }
  if (!hasSelectionRule) {
    for (const st of document.querySelectorAll('style')) {
      if ((st.textContent || '').includes('::selection')) {
        hasSelectionRule = true;
        break;
      }
    }
  }
  const numericEls = texts.filter((t) => (t.inTable || t.el.matches('[data-metric], [data-num], .kpi, .metric')) && /\d{2,}/.test(t.text));
  let tabularCount = 0;
  for (const ne of numericEls) {
    const cs = getComputedStyle(ne.el);
    if ((cs.fontVariantNumeric || '').includes('tabular-nums') || (cs.fontFeatureSettings || '').includes('tnum') || isMono(cs.fontFamily)) {
      tabularCount++;
    }
  }
  const missingTabular = numericEls.length >= 3 && (tabularCount / numericEls.length) < 0.5;

  // 15. Contrast check (`low-contrast`)
  const bodyBg = (() => {
    for (const el of [document.body, document.documentElement]) {
      if (!el) continue;
      const v = rgba(getComputedStyle(el).backgroundColor);
      if (v.a > 0.5) return v;
    }
    return { r: 255, g: 255, b: 255, a: 1 };
  })();
  const bgBehind = (el) => {
    for (let p = el; p && p !== document.documentElement; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (cs.backgroundImage !== 'none' || /^(VIDEO|CANVAS|PICTURE)$/i.test(p.tagName)) return null;
      const v = rgba(cs.backgroundColor);
      if (v.a >= 0.85) return v;
    }
    return bodyBg;
  };
  const lowContrast = [];
  for (const t of texts) {
    if (t.chars < 4 || t.isGradText) continue;
    const fg = rgba(t.color);
    if (fg.a < 0.85) continue;
    const bg = bgBehind(t.el);
    if (!bg) continue;
    const ratio = contrast(fg, bg);
    const minRatio = (t.size >= 24 || (t.size >= 18.5 && t.weight >= 700)) ? 3.0 : 4.5;
    if (ratio < minRatio) {
      lowContrast.push({
        selector: t.selector,
        text: t.text.slice(0, 35),
        ratio,
        need: minRatio,
        fg: hex(fg),
        bg: hex(bg)
      });
    }
  }
  lowContrast.sort((a, b) => a.ratio - b.ratio);

  // 16. Scroll-through check for `empty-screens` and `covered-text`
  const pageH = Math.max(document.documentElement.scrollHeight, document.body.scrollHeight);
  const numScreens = Math.min(8, Math.max(1, Math.floor(pageH / H)));
  const emptyScreens = [];
  const coveredHeadings = [];

  const isTopNav = (el) => {
    for (let p = el; p && p !== document.body; p = p.parentElement) {
      const cs = getComputedStyle(p);
      const r = p.getBoundingClientRect();
      if ((cs.position === 'fixed' || cs.position === 'sticky') && r.top <= 24 && r.height <= 96) return true;
    }
    return false;
  };
  const paintsOpaque = (hit, targetEl) => {
    for (let p = hit; p && p !== document.body && !p.contains(targetEl); p = p.parentElement) {
      if (/^(IMG|VIDEO|CANVAS|SVG)$/i.test(p.tagName) || p.closest('svg')) return true;
      const pcs = getComputedStyle(p);
      if (pcs.backgroundImage !== 'none') return true;
      if (rgba(pcs.backgroundColor).a > 0.15) return true;
    }
    return false;
  };

  const pageBgStr = getComputedStyle(document.body).backgroundColor;
  for (let sIdx = 0; sIdx < numScreens; sIdx++) {
    window.scrollTo(0, sIdx * H);
    // Check covered headings (>24px) in current viewport
    for (const h of allHeadings) {
      if (h.size < 24) continue;
      const r = h.el.getBoundingClientRect();
      if (r.bottom <= 16 || r.top >= H - 16 || r.width < 10) continue;
      let totalPts = 0, coveredPts = 0;
      for (const fx of [0.2, 0.5, 0.8]) {
        const x = r.left + r.width * fx;
        const y = r.top + Math.min(r.height * 0.5, 36);
        if (x < 4 || x >= W - 4 || y < 4 || y >= H - 4) continue;
        totalPts++;
        const hit = document.elementFromPoint(x, y);
        if (hit && hit !== h.el && !h.el.contains(hit) && !hit.contains(h.el) && !isTopNav(hit) && paintsOpaque(hit, h.el)) {
          coveredPts++;
        }
      }
      if (totalPts >= 2 && (coveredPts / totalPts) >= 0.5) {
        if (!coveredHeadings.some((c) => c.text === h.text)) {
          coveredHeadings.push({ text: h.text, selector: h.selector, screen: sIdx + 1 });
        }
      }
    }

    // Check screen coverage at desktop width (W >= 1100)
    if (W >= 1100 && numScreens >= 2) {
      let filled = 0, samples = 0;
      const gxMax = 16, gyMax = 10;
      for (let gx = 0; gx < gxMax; gx++) {
        for (let gy = 0; gy < gyMax; gy++) {
          const x = (gx + 0.5) * (W / gxMax);
          const y = (gy + 0.5) * (H / gyMax);
          samples++;
          let el = document.elementFromPoint(x, y);
          let hasContent = false;
          for (let depth = 0; el && depth < 6 && el !== document.body && el !== document.documentElement; depth++, el = el.parentElement) {
            if (/^(IMG|VIDEO|CANVAS|SVG|TABLE|INPUT|BUTTON|SELECT|TEXTAREA|H1|H2|H3|H4|P|LI|CODE|PRE)$/i.test(el.tagName) || el.closest('svg, table, [data-ui]')) {
              hasContent = true;
              break;
            }
            const cs = getComputedStyle(el);
            if (cs.backgroundImage !== 'none' || parseFloat(cs.borderTopWidth) > 0) {
              hasContent = true;
              break;
            }
            if (rgba(cs.backgroundColor).a > 0.05 && cs.backgroundColor !== pageBgStr) {
              hasContent = true;
              break;
            }
          }
          if (hasContent) filled++;
        }
      }
      const coverage = round(filled / Math.max(1, samples), 2);
      if (coverage < 0.15) {
        emptyScreens.push({ screen: sIdx + 1, coverage });
      }
    }
  }
  window.scrollTo(0, 0);

  return {
    viewport: { w: W, h: H },
    resolvedMode,
    zeroVisuals,
    horizontalOverflowPx,
    overflowCulprits,
    over2LineHeadings,
    titleStatus,
    offCentreFrame,
    emptyScreens,
    coveredHeadings,
    eyebrows,
    gradientTexts,
    sideStripes: sideStripes.slice(0, 5),
    ghostCards: ghostCards.slice(0, 5),
    paletteHits,
    iconCardRows: iconCardRows.slice(0, 4),
    numbered,
    monoProseSamples,
    monoProseShare: round(monoProseChars / Math.max(1, totalProseChars), 3),
    dominantBodySize,
    maxMeasureCh,
    hasSelectionRule,
    missingTabular,
    lowContrast: lowContrast.slice(0, 5)
  };
}
"""

REDUCED_MOTION_PROBE_JS = r"""
() => {
  const W = window.innerWidth;
  const H = window.innerHeight;
  const hiddenTexts = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const range = document.createRange();
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const t = (n.nodeValue || '').replace(/\s+/g, ' ').trim();
    const el = n.parentElement;
    if (t.length < 3 || !el || el.closest('script, style, noscript, template, [aria-hidden="true"], [hidden]')) continue;
    range.selectNodeContents(n);
    const r = range.getClientRects()[0] || el.getBoundingClientRect();
    if (!r || r.width < 2 || r.top > H || r.bottom < 0) continue;
    let op = 1.0;
    let visHidden = false;
    let dispNone = false;
    for (let p = el; p && p !== document.documentElement; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (cs.display === 'none') { dispNone = true; break; }
      if (cs.visibility === 'hidden') { visHidden = true; break; }
      op *= parseFloat(cs.opacity || '1');
    }
    if (!dispNone && (visHidden || op < 0.1)) {
      hiddenTexts.push(`${el.tagName.toLowerCase()} ("${t.slice(0, 40)}")`);
    }
  }
  return hiddenTexts.slice(0, 6);
}
"""


def judge_probe_findings(
    probe_data: dict[str, Any],
    mode: str,
    allow: set[str],
) -> list[dict[str, Any]]:
    """Convert browser probe measurements at a single viewport into `FAIL` and `WARN` findings."""
    findings: list[dict[str, Any]] = []
    w = probe_data["viewport"]["w"]
    is_operate = mode == "operate"

    def add(level: str, rule_id: str, message: str, fix: str) -> None:
        if rule_id in allow:
            return
        if is_operate and rule_id in OPERATE_SKIP_RULES:
            return
        findings.append({
            "level": level,
            "id": rule_id,
            "viewport": w,
            "message": message,
            "fix": fix,
        })

    # FAIL 3: zero-size-visual
    if probe_data.get("zeroVisuals"):
        add(
            "FAIL",
            "zero-size-visual",
            f"Visual element(s) rendered with 0x0 size or broken image at {w}px: " + "; ".join(probe_data["zeroVisuals"][:4]),
            "Ensure all <canvas>, <svg>, and <img> elements have explicit non-zero dimensions and valid image sources.",
        )

    # FAIL 4: horizontal-overflow
    if probe_data.get("horizontalOverflowPx", 0) > 0:
        culprits = probe_data.get("overflowCulprits", [])
        culprit_str = f" Widest offending selectors: {', '.join(culprits)}." if culprits else ""
        add(
            "FAIL",
            "horizontal-overflow",
            f"Page scrolls sideways by {probe_data['horizontalOverflowPx']}px at {w}px viewport.{culprit_str}",
            "Constrain wide elements with `max-width: 100%`, responsive `grid-template-columns`, or `overflow-x: clip`.",
        )

    # FAIL 5: headline-lines (persuade/experience mode)
    if mode in ("persuade", "experience") and probe_data.get("over2LineHeadings"):
        items = probe_data["over2LineHeadings"]
        desc = "; ".join(f'{h["selector"]} "{h["text"]}" ({h["lines"]} lines @ {h["size"]}px)' for h in items[:3])
        add(
            "FAIL",
            "headline-lines",
            f"{len(items)} headline(s) (h1-h3) wrap past 2 lines at {w}px: {desc}",
            "Shorten headline copy (~5-8 words / <=36 chars), widen the heading column, or adjust `clamp()` display scale so every h1-h3 fits in <=2 lines.",
        )

    # FAIL 6: late-title
    ts = probe_data.get("titleStatus", {})
    if not ts.get("ok", True):
        add(
            "FAIL",
            "late-title",
            ts.get("reason") or f"Primary <h1> is missing, hidden, or outside the first viewport at {w}px.",
            "Include a visible, high-contrast <h1> in the first viewport with opacity >= 1 and no overlapping cover element.",
        )

    # FAIL 7: off-centre-frame
    if probe_data.get("offCentreFrame"):
        add(
            "FAIL",
            "off-centre-frame",
            probe_data["offCentreFrame"]["message"],
            "Center the page container (`margin-inline: auto`) or balance the grid columns so both outer page margins match.",
        )

    # FAIL 8: empty-screens (persuade mode at 1440px)
    if mode == "persuade" and w >= 1100 and len(probe_data.get("emptyScreens", [])) >= 2:
        scr_list = ", ".join(f"screen {s['screen']} ({int(s['coverage']*100)}%)" for s in probe_data["emptyScreens"])
        add(
            "FAIL",
            "empty-screens",
            f"{len(probe_data['emptyScreens'])} scrolled desktop screens have <15% visual/text coverage: {scr_list}.",
            "Remove excessive `min-height: 100vh` gaps on sparse sections or fill the stage with substantive domain content/visuals.",
        )

    # FAIL 9: covered-text
    if probe_data.get("coveredHeadings"):
        desc = "; ".join(f'{c["selector"]} "{c["text"]}" (screen {c["screen"]})' for c in probe_data["coveredHeadings"][:3])
        add(
            "FAIL",
            "covered-text",
            f"Large heading/statement text is covered by another element during scroll at {w}px: {desc}.",
            "Fix sticky/fixed layer stacking (`z-index`) or give the pinned bar a solid surface so scrolling content does not collide with headings.",
        )

    # FAIL 11: slop-eyebrow (persuade mode)
    if mode == "persuade" and probe_data.get("eyebrows"):
        desc = "; ".join(f'"{e["text"]}" above "{e["above"]}"' for e in probe_data["eyebrows"][:3])
        add(
            "FAIL",
            "slop-eyebrow",
            f"Small uppercase/pill eyebrow kicker(s) detected directly above h1/h2 headings: {desc}.",
            "Delete the decorative eyebrow kicker above the heading; fold essential context into the heading or lead sentence.",
        )

    # FAIL 12: slop-gradient-text
    if probe_data.get("gradientTexts"):
        add(
            "FAIL",
            "slop-gradient-text",
            f"Gradient-clipped text (`background-clip: text`) detected: {', '.join(probe_data['gradientTexts'][:3])}.",
            "Use solid high-contrast ink color (`var(--text-ink)`); achieve hierarchy through scale and weight, never gradient text.",
        )

    # FAIL 13: slop-side-stripe
    if probe_data.get("sideStripes"):
        add(
            "FAIL",
            "slop-side-stripe",
            f"Cards/callouts with thick side-stripe border (`border-left-width > 1px`) detected: {', '.join(probe_data['sideStripes'][:3])}.",
            "Remove the thick left accent border (`border-left > 1px`); separate callouts with a subtle background tone step or uniform 1px border.",
        )

    # WARN 1: slop-ai-palette
    ph = probe_data.get("paletteHits", {})
    if ph.get("ai-purple"):
        add(
            "WARN",
            "slop-ai-palette",
            f"Unrequested AI Purple/Indigo palette (`hue 244..295` high saturation) detected on: {', '.join(ph['ai-purple'][:3])}.",
            "Replace generic AI purple/indigo (#6366f1 / violet) with an intentional palette from `ui_direction_dealer.py`.",
        )
    if ph.get("cream") and ph.get("terracotta"):
        add(
            "WARN",
            "slop-ai-palette",
            f"Assistant Cream + Terracotta palette pairing detected ({', '.join((ph['cream'] + ph['terracotta'])[:4])}).",
            "Replace yellow-cream + terracotta with a low-chroma mineral stone/slate ground and domain-specific accent.",
        )

    # WARN 2: slop-icon-cards (persuade mode)
    if mode == "persuade" and probe_data.get("iconCardRows"):
        add(
            "WARN",
            "slop-icon-cards",
            f"Row(s) of >=3 identical-size cards topped with small icons/emojis detected: {', '.join(probe_data['iconCardRows'])}.",
            "Replace 3-up icon feature cards with a varied section blueprint (asymmetric split, editorial ledger, or interactive workbench).",
        )

    # WARN 3: slop-ghost-card
    if probe_data.get("ghostCards"):
        add(
            "WARN",
            "slop-ghost-card",
            f"Ghost card(s) combining a `1px` border with a wide soft `box-shadow` (`blur >= 16px`): {', '.join(probe_data['ghostCards'][:3])}.",
            "Declare elevation once: use either a crisp 1px border OR a subtle tone step, not a 1px border over a wide soft shadow.",
        )

    # WARN 4: slop-numbering (persuade mode)
    if mode == "persuade" and probe_data.get("numbered"):
        add(
            "WARN",
            "slop-numbering",
            f"Decorative `01 / 02 / 03` section numbering detected: {', '.join(probe_data['numbered'][:4])}.",
            "Remove decorative 01/02/03 labels unless the sequence is a genuine ordered procedure (`<ol>`).",
        )

    # WARN 5: slop-mono-prose (persuade mode)
    if mode == "persuade" and probe_data.get("monoProseSamples"):
        add(
            "WARN",
            "slop-mono-prose",
            f"Monospace font used on prose/labels outside `<code>`/`<pre>`/`[data-ui]`: {', '.join(probe_data['monoProseSamples'][:3])}.",
            "Reserve monospace strictly for `<code>`, `<pre>`, CLI commands, hashes, and IDs; set prose and labels in `--font-sans`.",
        )

    # WARN 6: body-size-small
    min_body = 12.5 if is_operate else 15.0
    dom_body = probe_data.get("dominantBodySize")
    max_ch = probe_data.get("maxMeasureCh", 0)
    if dom_body is not None and dom_body < min_body:
        add(
            "WARN",
            "body-size-small",
            f"Dominant running body copy is {dom_body}px at {w}px (minimum recommended for `{mode}` mode is {min_body}px).",
            f"Increase body font-size to >= {int(min_body)}px (16-18px for `persuade`/`read`, 13-14px for `operate`).",
        )
    elif max_ch > 85 and w >= 1024:
        add(
            "WARN",
            "body-size-small",
            f"Running body copy line measure reaches ~{max_ch}ch at {w}px (exceeds 85ch readability ceiling).",
            "Constrain reading paragraphs to `max-width: 60ch–75ch`.",
        )

    # WARN 7: browser-surfaces-default
    if w == probe_data["viewport"]["w"] and (not probe_data.get("hasSelectionRule") or probe_data.get("missingTabular")):
        missing_parts = []
        if not probe_data.get("hasSelectionRule"):
            missing_parts.append("custom `::selection` CSS rule")
        if probe_data.get("missingTabular"):
            missing_parts.append("`font-variant-numeric: tabular-nums` on numeric table/KPI elements")
        add(
            "WARN",
            "browser-surfaces-default",
            f"Unstyled browser default surfaces detected: missing {' and '.join(missing_parts)}.",
            "Add `::selection { background: var(--selection-bg); color: var(--selection-fg); }` and `font-variant-numeric: tabular-nums` on tables/metrics.",
        )

    # WARN 8: low-contrast
    if probe_data.get("lowContrast"):
        desc = "; ".join(
            f'{c["selector"]} "{c["text"]}" ({c["ratio"]}:1 < {c["need"]}:1, {c["fg"]} on {c["bg"]})'
            for c in probe_data["lowContrast"][:3]
        )
        add(
            "WARN",
            "low-contrast",
            f"Low foreground/background contrast detected at {w}px: {desc}.",
            "Adjust text or surface tokens so normal text achieves >= 4.5:1 contrast and large text achieves >= 3.0:1.",
        )

    return findings


def run_playwright_multi_viewport_inspection(
    target_url: str,
    target_stem: str,
    widths: list[int],
    mode: str,
    allow: set[str],
    screenshots_dir: str | None = None,
) -> dict[str, Any]:
    """Run 3-viewport + `prefers-reduced-motion` real-browser inspection via Playwright Chromium."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as exc:
        return {
            "ran": False,
            "reason": f"python playwright module not available ({exc})",
            "findings": [],
            "viewports": [],
            "screenshots": [],
        }

    console_errors: list[str] = []
    page_errors: list[str] = []
    all_findings: list[dict[str, Any]] = []
    viewport_reports: list[dict[str, Any]] = []
    screenshots: list[str] = []
    resolved_mode = mode

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for idx, w in enumerate(widths):
                h = VIEWPORT_HEIGHTS.get(w, max(600, round(w * 0.625)))
                vp_name = VIEWPORT_NAMES.get(w, f"w{w}")
                context = browser.new_context(viewport={"width": w, "height": h})
                page = context.new_page()
                if idx == 0:
                    page.on(
                        "console",
                        lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
                    )
                    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

                page.goto(target_url, wait_until="networkidle", timeout=15000)
                page.wait_for_timeout(350)

                if screenshots_dir:
                    os.makedirs(screenshots_dir, exist_ok=True)
                    fold_path = os.path.join(screenshots_dir, f"{target_stem}-{vp_name}-{w}-fold.png")
                    page.screenshot(path=fold_path, full_page=False)
                    screenshots.append(fold_path)
                    if idx == 0:
                        legacy_path = os.path.join(screenshots_dir, f"{target_stem}.png")
                        shutil.copyfile(fold_path, legacy_path)

                probe_res = page.evaluate(BROWSER_VIEWPORT_PROBE_JS, {"mode": mode})
                resolved_mode = probe_res.get("resolvedMode", resolved_mode)
                vp_findings = judge_probe_findings(probe_res, resolved_mode, allow)
                all_findings.extend(vp_findings)
                viewport_reports.append({
                    "width": w,
                    "height": h,
                    "mode": resolved_mode,
                    "findings_count": len(vp_findings),
                    "summary": {
                        "horizontal_overflow_px": probe_res.get("horizontalOverflowPx", 0),
                        "over_2line_headings": len(probe_res.get("over2LineHeadings", [])),
                        "zero_visuals": len(probe_res.get("zeroVisuals", [])),
                        "dominant_body_px": probe_res.get("dominantBodySize"),
                        "max_measure_ch": probe_res.get("maxMeasureCh"),
                    },
                })
                context.close()

            # Reduced-motion check (`reduced-motion-hidden`) at 1440x900
            if "reduced-motion-hidden" not in allow:
                rm_context = browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    reduced_motion="reduce",
                )
                rm_page = rm_context.new_page()
                rm_page.goto(target_url, wait_until="networkidle", timeout=15000)
                rm_page.wait_for_timeout(350)
                hidden_texts = rm_page.evaluate(REDUCED_MOTION_PROBE_JS)
                if hidden_texts:
                    all_findings.append({
                        "level": "FAIL",
                        "id": "reduced-motion-hidden",
                        "viewport": 1440,
                        "message": f"Under `prefers-reduced-motion: reduce`, {len(hidden_texts)} text element(s) remain hidden at opacity 0: {', '.join(hidden_texts[:4])}.",
                        "fix": "Ensure `@media (prefers-reduced-motion: reduce)` forces `opacity: 1 !important; transform: none !important;` or scope `opacity: 0` strictly inside `@media (prefers-reduced-motion: no-preference)`.",
                    })
                rm_context.close()

            browser.close()

        # Runtime console / page errors -> FAIL findings
        for pe in page_errors:
            if "runtime-page-error" not in allow:
                all_findings.insert(0, {
                    "level": "FAIL",
                    "id": "runtime-page-error",
                    "viewport": widths[0],
                    "message": f"Uncaught runtime pageerror: {pe}",
                    "fix": "Fix the uncaught JavaScript exception in the page script.",
                })
        for ce in console_errors:
            if "console-error" not in allow:
                all_findings.insert(0, {
                    "level": "FAIL",
                    "id": "console-error",
                    "viewport": widths[0],
                    "message": f"Runtime console.error: {ce}",
                    "fix": "Resolve all runtime `console.error` failures and broken network/resource loads.",
                })

        return {
            "ran": True,
            "resolved_mode": resolved_mode,
            "console_errors": console_errors,
            "page_errors": page_errors,
            "zero_box_visuals": [
                f["message"] for f in all_findings if f["id"] == "zero-size-visual"
            ],
            "viewports": viewport_reports,
            "findings": all_findings,
            "screenshots": screenshots,
            "screenshot": screenshots[0] if screenshots else None,
        }
    except Exception as exc:
        return {
            "ran": False,
            "reason": f"Headless browser check skipped: {exc}",
            "findings": [],
            "viewports": [],
            "screenshots": [],
        }


def deduplicate_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """De-duplicate identical rule findings across viewports while preserving viewport-specific layout issues."""
    merged: list[dict[str, Any]] = []
    viewport_specific_ids = {"horizontal-overflow", "headline-lines", "off-centre-frame"}
    for f in findings:
        if f["id"] not in viewport_specific_ids:
            existing = next((m for m in merged if m["id"] == f["id"] and m["level"] == f["level"]), None)
            if existing is not None:
                also = existing.setdefault("also_at_viewports", [])
                if f["viewport"] not in also and f["viewport"] != existing["viewport"]:
                    also.append(f["viewport"])
                continue
        merged.append(dict(f))
    return merged


def validate_target(
    target: str,
    require_single_file: bool = True,
    mode: str = "auto",
    widths: list[int] | None = None,
    screenshots_dir: str | None = None,
    allow: set[str] | None = None,
) -> dict[str, Any]:
    if widths is None:
        widths = [1440, 768, 390]
    if allow is None:
        allow = set()

    is_url = bool(re.match(r"^https?://", target, re.IGNORECASE))
    findings: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}

    if not is_url:
        p = Path(target).resolve()
        if not p.is_file():
            return {
                "target": target,
                "status": "FAIL",
                "hard_cap_score": 6.0,
                "surface_mode": mode,
                "findings": [{
                    "level": "FAIL",
                    "id": "file-not-found",
                    "viewport": widths[0],
                    "message": f"File not found: {target}",
                    "fix": "Verify the HTML file path exists before running `web_ui_validator.py`.",
                }],
                "errors": [f"File not found: {target}"],
                "warnings": [],
            }

        content = p.read_text(encoding="utf-8", errors="replace")
        parser = HTMLStructureParser()
        parser.feed(content)

        if mode == "auto" and parser.explicit_mode:
            mode = parser.explicit_mode

        total_css_chars = sum(len(s) for s in parser.styles)
        total_js_chars = sum(len(s) for s in parser.scripts)
        interactive_count = sum(
            parser.tags.get(t, 0) for t in ("button", "input", "select", "dialog", "details", "canvas", "svg")
        )
        metrics = {
            "size_bytes": p.stat().st_size,
            "style_blocks": len(parser.styles),
            "css_chars": total_css_chars,
            "script_blocks": len(parser.scripts),
            "js_chars": total_js_chars,
            "interactive_and_visual_tags": interactive_count,
            "canvas_count": parser.tags.get("canvas", 0),
            "svg_count": parser.tags.get("svg", 0),
        }

        if (parser.tags.get("html", 0) == 0 or parser.tags.get("body", 0) == 0) and "html-structure" not in allow:
            findings.append({
                "level": "FAIL",
                "id": "html-structure",
                "viewport": widths[0],
                "message": "Missing <html> or <body> root structure.",
                "fix": "Wrap the document in valid `<!DOCTYPE html><html><head>...</head><body>...</body></html>` tags.",
            })

        if require_single_file and "single-file-minimums" not in allow:
            if total_css_chars < 100:
                findings.append({
                    "level": "FAIL",
                    "id": "single-file-minimums",
                    "viewport": widths[0],
                    "message": f"Single-file template has insufficient embedded <style> CSS ({total_css_chars} chars).",
                    "fix": "Embed complete design tokens and responsive layout rules inside `<style>` (or pass `--allow-external`).",
                })
            if total_js_chars < 50:
                findings.append({
                    "level": "FAIL",
                    "id": "single-file-minimums",
                    "viewport": widths[0],
                    "message": f"Single-file template has insufficient embedded <script> interactivity ({total_js_chars} chars).",
                    "fix": "Implement stateful client-side interactivity in `<script>` for the surface's 'One Live Thing' (or pass `--allow-external`).",
                })

        # FAIL 1: js-syntax-error + dead handler stubs
        if "js-syntax-error" not in allow:
            for idx, js in enumerate(parser.scripts, start=1):
                for syn_err in check_js_syntax(js, idx):
                    findings.append({
                        "level": "FAIL",
                        "id": "js-syntax-error",
                        "viewport": widths[0],
                        "message": syn_err,
                        "fix": "Fix the JavaScript syntax error reported by `node --check`.",
                    })

            combined_js = "\n".join(parser.scripts)
            if re.search(r"alert\(\s*['\"](?:todo|coming\s+soon|not\s+implemented|placeholder)", combined_js, re.IGNORECASE):
                findings.append({
                    "level": "FAIL",
                    "id": "js-syntax-error",
                    "viewport": widths[0],
                    "message": "Contains half-baked `alert('TODO' / 'Coming soon' / 'Not implemented')` stub in JavaScript.",
                    "fix": "Replace `alert()` stubs with real client-side state updates and DOM/SVG re-rendering.",
                })
            if re.search(r"addEventListener\(\s*['\"][^'\"]+['\"]\s*,\s*\(\s*\)\s*=>\s*\{\s*\}\s*\)", combined_js):
                findings.append({
                    "level": "FAIL",
                    "id": "js-syntax-error",
                    "viewport": widths[0],
                    "message": "Contains empty no-op `addEventListener(..., () => {})` handler that does not commit state.",
                    "fix": "Wire every event listener to mutate real domain state and update the rendered view.",
                })
            if re.search(r"\bonclick\s*=\s*['\"]\s*(?:void\(0\);?|return\s+false;?)?\s*['\"]", content, re.IGNORECASE):
                findings.append({
                    "level": "FAIL",
                    "id": "js-syntax-error",
                    "viewport": widths[0],
                    "message": "Contains dead/no-op `onclick=\"\"` or `onclick=\"void(0)\"` attribute on an interactive element.",
                    "fix": "Bind a real state handler to interactive buttons and controls.",
                })

        # FAIL 2: placeholder-text
        if "placeholder-text" not in allow:
            full_text = " ".join(parser.text_chunks)
            placeholder_match = re.search(
                r"(?:\blorem\s+ipsum\b|\[\s*(?:TBD|TODO|FIXME)\s*\]|\bTODO\s*:|\bFIXME\s*:|\[\s*insert\b|\bcoming\s+soon\b|\bunder\s+construction\b|\bplaceholder\s+text\b)",
                full_text,
                re.IGNORECASE,
            )
            if placeholder_match:
                findings.append({
                    "level": "FAIL",
                    "id": "placeholder-text",
                    "viewport": widths[0],
                    "message": f"Contains banned placeholder text (`{placeholder_match.group(0)}`) instead of realistic domain data.",
                    "fix": "Replace all placeholder markers (`Lorem ipsum`, `TODO`, `FIXME`, `[insert...]`, `Coming soon`) with authentic domain data.",
                })

        if interactive_count == 0 and "no-interactive-controls" not in allow:
            findings.append({
                "level": "WARN",
                "id": "no-interactive-controls",
                "viewport": widths[0],
                "message": "No interactive controls (<button>, <input>, <select>) or visual elements (<canvas>, <svg>) found.",
                "fix": "Include at least 'One Live Thing' with interactive controls and visual feedback.",
            })

        with serve_local_file(p) as served_url:
            runtime = run_playwright_multi_viewport_inspection(
                target_url=served_url,
                target_stem=p.stem,
                widths=widths,
                mode=mode,
                allow=allow,
                screenshots_dir=screenshots_dir,
            )
        target_label = str(p)
    else:
        stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", target)[:40].strip("_") or "url_target"
        runtime = run_playwright_multi_viewport_inspection(
            target_url=target,
            target_stem=stem,
            widths=widths,
            mode=mode,
            allow=allow,
            screenshots_dir=screenshots_dir,
        )
        target_label = target

    if runtime.get("ran"):
        findings.extend(runtime.get("findings", []))
        resolved_mode = runtime.get("resolved_mode", mode)
    else:
        resolved_mode = mode if mode != "auto" else "persuade"
        # Fail closed: without a browser, the runtime, viewport, overflow, contrast and anti-slop DOM
        # rules never ran, so a PASS would be unverified. `--allow browser-unavailable` downgrades to WARN.
        findings.append({
            "level": "WARN" if "browser-unavailable" in allow else "FAIL",
            "id": "browser-unavailable",
            "viewport": widths[0],
            "message": (
                f"Real-browser inspection did not run ({runtime.get('reason')}); runtime errors, "
                "viewport geometry, overflow, contrast and anti-slop DOM rules were NOT checked."
            ),
            "fix": (
                "Install Playwright + Chromium (`pip install playwright && python3 -m playwright install chromium`) "
                "or set AGENT_SWARM_UI_PYTHON to a Python that has it. Pass `--allow browser-unavailable` "
                "only to accept static-only checks deliberately."
            ),
        })

    deduped = deduplicate_findings(findings)
    fails = [f for f in deduped if f["level"] == "FAIL"]
    warns = [f for f in deduped if f["level"] == "WARN"]

    errors_str = [
        f"[{f['id']} @{f['viewport']}px] {f['message']} -> Fix: {f['fix']}"
        for f in fails
    ]
    warnings_str = [
        f"[{f['id']} @{f['viewport']}px] {f['message']} -> Fix: {f['fix']}"
        for f in warns
    ]

    status = "PASS" if len(fails) == 0 else "FAIL"
    hard_cap_score = 6.0 if len(fails) > 0 else 10.0

    return {
        "target": target_label,
        "status": status,
        "hard_cap_score": hard_cap_score,
        "surface_mode": resolved_mode,
        "viewports_inspected": widths,
        "metrics": metrics,
        "findings": deduped,
        "fail_count": len(fails),
        "warn_count": len(warns),
        "screenshots": runtime.get("screenshots", []),
        "playwright_runtime": {
            "ran": runtime.get("ran", False),
            "reason": runtime.get("reason"),
            "console_errors": runtime.get("console_errors", []),
            "page_errors": runtime.get("page_errors", []),
            "zero_box_visuals": runtime.get("zero_box_visuals", []),
            "viewports": runtime.get("viewports", []),
            "screenshot": runtime.get("screenshot"),
        },
        "errors": errors_str,
        "warnings": warnings_str,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="3-Viewport (`1440,768,390`) + Reduced-Motion Real-Browser Layout, Motion & Anti-Slop Inspector"
    )
    ap.add_argument("targets", nargs="+", help="One or more HTML file paths or http(s) URLs to validate")
    ap.add_argument(
        "--mode",
        choices=["persuade", "operate", "read", "experience", "auto"],
        default="auto",
        help="Surface mode (`operate` skips marketing-only card/border/label bans; default: auto)",
    )
    ap.add_argument(
        "--widths",
        default="1440,768,390",
        help="Comma-separated viewport widths to inspect in headless Chromium (default: 1440,768,390)",
    )
    ap.add_argument(
        "--quick",
        action="store_true",
        help="Single-viewport quick check at 1440x900 only",
    )
    ap.add_argument(
        "--screenshots-dir",
        "--screenshot-dir",
        dest="screenshots_dir",
        help="Directory to save `<stem>-<viewport>-<width>-fold.png` screenshots for visual critique",
    )
    ap.add_argument(
        "--allow",
        default="",
        help="Comma-separated rule IDs to allow as intentional overrides (e.g. `slop-ai-palette,slop-numbering`)",
    )
    ap.add_argument(
        "--allow-external",
        action="store_true",
        help="Do not enforce embedded single-file <style>/<script> character minimums",
    )
    ap.add_argument("--json", action="store_true", help="Output machine-readable JSON report")
    args = ap.parse_args()

    widths = [1440] if args.quick else [int(x.strip()) for x in args.widths.split(",") if x.strip().isdigit()]
    if not widths:
        widths = [1440, 768, 390]

    allow_set = {r.strip() for r in args.allow.split(",") if r.strip()}

    if args.screenshots_dir:
        os.makedirs(args.screenshots_dir, exist_ok=True)

    results = []
    all_passed = True

    for t in args.targets:
        res = validate_target(
            target=t,
            require_single_file=not args.allow_external,
            mode=args.mode,
            widths=widths,
            screenshots_dir=args.screenshots_dir,
            allow=allow_set,
        )
        results.append(res)
        if res["status"] != "PASS":
            all_passed = False

    if args.json:
        print(
            json.dumps(
                {
                    "overall_status": "PASS" if all_passed else "FAIL",
                    "hard_cap_score": 10.0 if all_passed else 6.0,
                    "viewports_inspected": widths,
                    "results": results,
                },
                indent=2,
            )
        )
    else:
        print("=== 3-VIEWPORT REAL-BROWSER UI & ANTI-SLOP VALIDATION REPORT ===")
        for r in results:
            icon = "✅" if r["status"] == "PASS" else "❌"
            m = r.get("metrics", {})
            print(
                f"{icon} [{r['status']}] {r['target']} "
                f"(Mode: {r['surface_mode']}, Viewports: {r['viewports_inspected']}, "
                f"Hard-Cap: {r['hard_cap_score']}/10, "
                f"CSS: {m.get('css_chars', 0)} chars, JS: {m.get('js_chars', 0)} chars)"
            )
            for f in r.get("findings", []):
                also = f" (also @{','.join(map(str, f['also_at_viewports']))}px)" if f.get("also_at_viewports") else ""
                prefix = "❌ FAIL" if f["level"] == "FAIL" else "⚠️ WARN"
                print(f"    {prefix} [{f['id']}] @{f['viewport']}px{also}: {f['message']}")
                print(f"       -> Fix: {f['fix']}")
            if r.get("screenshots"):
                print("    📸 Screenshots:")
                for sp in r["screenshots"]:
                    print(f"       - {sp}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
