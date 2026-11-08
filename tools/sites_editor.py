#!/usr/bin/env python3
"""Drive the Google Sites editor from a script, so a Claude session never clicks through it.

Google Sites has no API (CLAUDE.md §5). This attaches to a Chrome that a person already
signed in as classpages@sffriendsschool.org and started with remote debugging:

    open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir=<profile dir>

It never handles a password, never launches a browser of its own and never runs headless.
Docs, the editor DOM it depends on, and what has been tested: docs/sites-editor-driver.md.

Commands (one site, one page, one action per run; no loops over sites):

    chrome                                 start Chrome for the script: the classpages@ data dir, maximised, debug port on
    tabs                                   what the attached Chrome has open
    list    --site class-2034 --page home  every embed on the page: URL, box, position (read-only)
    resize  --site .. --page .. --embed room-parents --box card [--apply]   drag the box to a standard shape
    publish --site class-2034 [--apply]                                      click Publish and confirm

`list --dump` also writes _editor/<site>-<page>-<time>.json (+ .png, .html): an inventory of
the editor DOM around each embed, for recording stable hooks in the doc when Google changes
the editor. `list --select` clicks each block and reports whether the editor marked it
selected (it changes nothing).

Every write needs --apply; without it the command prints what it would do and the before
size. Exit codes: 0 ok, 1 the editor or Chrome isn't as expected (the message says what,
and nothing was guessed), 2 a write stopped half-way (the message says what to check).
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

import yaml

try:
    from playwright.sync_api import sync_playwright, Error as PlaywrightError
except ImportError:  # pragma: no cover
    sys.exit("needs Playwright: pip install playwright pyyaml  (no browser install needed; it attaches to Chrome)")

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "_editor"
PAGES = "https://sffs-class-sites.github.io/class-sites/"
# SITES_EDITOR_ORIGIN is only for the mock test (tests/test_sites_editor.py); the real editor is on sites.google.com.
SITES = os.environ.get("SITES_EDITOR_ORIGIN", "https://sites.google.com")
EDITOR = SITES + "/d/{site_id}/edit"
CDP = "http://localhost:9222"
ACCOUNT = "classpages@sffriendsschool.org"
# A Chrome *user data dir* of its own, signed in once as classpages@ (Chrome 136+ refuses --remote-debugging-port
# on the default data dir). Override with --user-data-dir or SITES_EDITOR_CHROME_DIR.
CHROME_DIR = os.environ.get("SITES_EDITOR_CHROME_DIR") or str(pathlib.Path.home() / "Library/Application Support/Google/Chrome/classpages")
PACE_MS = 1500          # pause after anything that changes what the editor shows; keeps actions human-paced
LOAD_WAIT = 40          # × 500 ms to wait for the editor to lay its embeds out
MIN_WINDOW_W = 1440     # registry boxes were measured in the editor at this width; narrower scales the canvas
SHAPE_TOL = 0.005       # a resized box is done when |h/w - target| is within this (≈3px at 700px wide)
MAX_DRAGS = 12          # resize gives up after this many drags that don't reach the target (a block at the bottom of a
                        # page gets only the window's spare room per drag, so a big change takes several)
MIN_DRAG = 8            # px: less room than this and a drag is pointless (the editor snaps to a grid)
DRAG_STEPS = 12         # mouse moves per drag, so the editor sees a human-like drag

# Hooks confirmed on the real editor 2026-11-02 (docs/sites-editor-driver.md §4).
BLOCK_SEL = 'div[aria-label="Whole page embed"][data-url]'   # one per URL embed; data-url = the embed URL
CELL_SEL = 'div[role=gridcell][aria-label="IFRAME"]'          # ancestor that carries aria-selected / aria-grabbed
PUBLISH_SEL = '[guidedhelpid="at-appbar-publish"]'            # the app-bar Publish button
PUBLISH_FALLBACK = 'div[role=button]:has-text("Publish")'
VH_OPEN = '[aria-label="Open version history"]'               # app bar; opens the full-window Version history
VH_RESTORE_SITE = '[aria-label="Restore this site version"]'  # appears once a version other than the current one is selected


class Stop(Exception):
    """The editor, Chrome or the registry isn't as this script expects. Say so and stop; don't guess."""


class HalfDone(Exception):
    """A write started and stopped before it was verified. The message says what to check in the editor."""


# --- registry -----------------------------------------------------------------------------------

def load_registry(path):
    reg = yaml.safe_load(pathlib.Path(path).read_text())
    for need in ("boxes", "embeds", "sites"):
        if need not in reg:
            raise Stop(f"registry.yaml has no `{need}` section")
    return reg


def site_of(reg, sid):
    site = reg["sites"].get(sid)
    if not site:
        raise Stop(f"no site `{sid}` in registry.yaml (have: {', '.join(reg['sites'])})")
    if not site.get("site_id"):
        raise Stop(f"site `{sid}` has no site_id in registry.yaml, so there is no editor URL for it")
    return site


def box_of(reg, name_or_dict):
    if isinstance(name_or_dict, dict):
        return name_or_dict
    box = reg["boxes"].get(name_or_dict)
    if not box:
        raise Stop(f"no box `{name_or_dict}` in registry.yaml boxes (have: {', '.join(reg['boxes'])})")
    return box


def slots_on(site, page_slug):
    return [s for s in site.get("slots", []) if s.get("page") == page_slug]


def slot_query(slot):
    return {k: str(v) for k, v in (slot.get("query") or {}).items()}


def page_title(slug):
    """One registry page-slug segment -> the title shown in the editor's Pages panel ("email-digest" -> "Email Digest").
    A child page's slug is "parent/child" (registry `page: resources/basketball`); callers split on "/" first."""
    return " ".join(w.capitalize() for w in slug.split("-"))


def url_query(url):
    return {k: v[-1] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).items()}


def embed_of(reg, url):
    """(embed id, query) for one of our embed URLs, else (None, None)."""
    for eid, emb in reg["embeds"].items():
        if emb.get("path") and url.startswith(PAGES + emb["path"]):
            return eid, url_query(url)
    return None, None


# --- Chrome ------------------------------------------------------------------------------------

def attach(pw, cdp):
    try:
        browser = pw.chromium.connect_over_cdp(cdp, timeout=10000)
    except PlaywrightError as e:
        raise Stop(f"can't attach to Chrome at {cdp} ({str(e).splitlines()[0]}).\n"
                   f"Start Chrome for the script first:  python3 tools/sites_editor.py chrome")
    if not browser.contexts:
        raise Stop("attached to Chrome but it has no browser context (no window open?)")
    return browser


def pace(page, ms=PACE_MS):
    page.wait_for_timeout(ms)


def editor_tab(browser, site, reopen=False):
    """The editor tab for this site: an open one if there is one, else a new tab at the editor URL."""
    ctx = browser.contexts[0]
    prefix = f"{SITES}/d/{site['site_id']}/"
    page = next((p for p in ctx.pages if p.url.startswith(prefix)), None)
    if page and not reopen:
        print(f"using the open editor tab {page.url}")
        page.bring_to_front()
    else:
        page = ctx.new_page()
        url = EDITOR.format(site_id=site["site_id"])
        print(f"opening {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
    pace(page)
    if "accounts.google.com" in page.url or "ServiceLogin" in page.url:
        raise Stop(f"the editor asked for a sign-in ({page.url[:80]}...). Chrome at this port isn't signed in as "
                   f"classpages@; sign it in by hand first (this script never handles a password)")
    if not page.url.startswith(prefix):
        raise Stop(f"expected the editor at {prefix}..., got {page.url}")
    return page


def account_label(page):
    """Who Chrome is signed in as, from the account button Google apps put in the top bar; None if not found."""
    for sel in ('a[aria-label^="Google Account"]', '[aria-label*="Google Account"]'):
        el = page.query_selector(sel)
        if el:
            return " ".join((el.get_attribute("aria-label") or "").split())
    return None


def viewport(page):
    return page.evaluate("() => ({w: window.innerWidth, h: window.innerHeight, dpr: window.devicePixelRatio})")


def window_note(vp):
    return "" if vp["w"] >= MIN_WINDOW_W else (f"  ← narrower than {MIN_WINDOW_W}: the editor scales its canvas, so sizes "
                                                f"are smaller than editor-box sizes; shapes (h/w) still hold")


# --- the page being edited ----------------------------------------------------------------------

PAGE_ITEM_JS = """
(title) => {
  // Candidate page entries in the Pages panel: visible elements whose own text is exactly the title.
  // Prefer one inside the pages tree, then the smallest; scroll it into view and measure it fresh.
  const want = title.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
  const out = [];
  for (const el of document.querySelectorAll('[role=treeitem], [role=option], [role=listitem], [role=link], [role=button], li, a, div, span')) {
    const t = (el.innerText || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
    if (t !== want) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    out.push({el, area: r.width * r.height, in_tree: !!el.closest('[role=tree], [role=treeitem]')});
  }
  out.sort((a, b) => (b.in_tree - a.in_tree) || (a.area - b.area));
  if (!out.length) return null;
  const pick = out[0];
  pick.el.scrollIntoView({block: 'center', behavior: 'instant'});
  const r = pick.el.getBoundingClientRect();
  return {text: pick.el.innerText.trim(), tag: pick.el.tagName.toLowerCase(), role: pick.el.getAttribute('role'),
          in_tree: pick.in_tree, candidates: out.length, x: r.x, y: r.y, w: r.width, h: r.height};
}
"""


TREE_LABELS_JS = """
() => [...document.querySelectorAll('[role=treeitem]')].map(t => ({
  label: (t.getAttribute('aria-label') || t.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 80),
  expanded: t.getAttribute('aria-expanded'),
  visible: t.getBoundingClientRect().height > 0}))
"""

EXPAND_JS = """
(title) => {
  // Open the child list under the Pages-panel entry for `title`: click its expander if it has one,
  // else report that the entry needs the keyboard (focus + ArrowRight, done by the caller).
  const want = title.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
  const items = [...document.querySelectorAll('[role=treeitem]')].filter(t => {
    const l = (t.getAttribute('aria-label') || t.innerText || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
    return l === want || l.startsWith(want + ' ');
  });
  if (!items.length) return {found: false};
  const t = items[0];
  const toggle = t.querySelector('[aria-expanded="false"], [aria-label*="xpand" i], [aria-label*="hild pages" i], [aria-label*="ubpages" i]');
  if (toggle && toggle !== t) { toggle.click(); return {found: true, clicked: toggle.getAttribute('aria-label') || toggle.tagName.toLowerCase()}; }
  t.scrollIntoView({block: 'center', behavior: 'instant'});
  const r = t.getBoundingClientRect();
  return {found: true, clicked: null, expanded: t.getAttribute('aria-expanded'), x: r.x, y: r.y, w: r.width, h: r.height};
}
"""


def open_pages_panel(page):
    """Make sure the right-hand Pages panel is showing. Returns what it clicked, or None if it was already open."""
    if page.evaluate("() => !!document.querySelector('[role=tree]')"):
        return None
    for sel in ('[role=tab][aria-label*="Pages" i]', '[role=tab]:has-text("Pages")', 'button:has-text("Pages")'):
        el = page.query_selector(sel)
        if el and el.is_visible():
            el.click()
            pace(page)
            return sel
    raise Stop("can't find the Pages panel or a tab that opens it ([role=tree], or a tab/button labelled 'Pages'). "
               "Run `list --dump` and record what the editor shows instead (docs/sites-editor-driver.md)")


def go_to_page(page, slug):
    """Select the page in the Pages panel. A child page (`resources/basketball`) is reached segment by segment:
    click the parent, expand it if its children aren't shown, click the child. Returns (title, editor URL, how)."""
    clicked = open_pages_panel(page)
    before = page.url
    segments = slug.strip("/").split("/")
    title = where = None
    for i, seg in enumerate(segments):
        title = page_title(seg)
        pick = page.evaluate(PAGE_ITEM_JS, title)
        how = ""
        if not pick and i > 0:
            parent = page_title(segments[i - 1])
            ex = page.evaluate(EXPAND_JS, parent)
            if ex.get("found") and ex.get("clicked"):
                how = f" (after clicking the expander '{ex['clicked']}' on '{parent}')"
            elif ex.get("found"):
                page.mouse.click(ex["x"] + ex["w"] / 2, ex["y"] + ex["h"] / 2)
                page.keyboard.press("ArrowRight")
                how = f" (after focusing '{parent}' and pressing ArrowRight; it had aria-expanded={ex.get('expanded')})"
            pace(page, 700)
            pick = page.evaluate(PAGE_ITEM_JS, title) if ex.get("found") else None
        if not pick:
            tree = page.evaluate(TREE_LABELS_JS)
            shown = "; ".join(f"{t['label']}" + (f" [aria-expanded={t['expanded']}]" if t["expanded"] else "")
                              + ("" if t["visible"] else " [hidden]") for t in tree) or "no [role=treeitem] at all"
            raise Stop(f"no entry titled '{title}' in the editor's Pages panel (registry page `{slug}`, segment {i + 1} of "
                       f"{len(segments)}). Tree entries seen: {shown}. Either the page is named differently or its parent "
                       f"didn't expand; record what the panel shows in docs/sites-editor-driver.md §4")
        page.mouse.click(pick["x"] + pick["w"] / 2, pick["y"] + pick["h"] / 2)
        pace(page)
        where = ("pages tree" if pick["in_tree"] else f"<{pick['tag']} role={pick['role']}>") + how
        print(f"page '{title}': clicked its entry in the {where}"
              + (f"; panel opened via {clicked}" if clicked and i == 0 else ""))
    print(f"editor URL {before} -> {page.url}" if page.url != before else f"editor URL unchanged ({page.url})")
    return title, page.url, where


# --- embeds on the canvas -----------------------------------------------------------------------

def our_blocks(page, reg):
    """[(embed id, query, block element)] for every URL-embed block on the editor page whose data-url is one of ours.
    Found in the editor document itself: on a tab that was open before the script attached, Playwright's frame tree
    shows the gstatic wrapper frames with an empty URL and nothing below them (2026-11-02), so frames can't be relied on."""
    out = []
    for b in page.query_selector_all(BLOCK_SEL):
        eid, q = embed_of(reg, b.get_attribute("data-url") or "")
        if eid:
            out.append((eid, q, b))
    return out


def wait_for_embeds(page, reg, expected):
    for _ in range(LOAD_WAIT):
        found = our_blocks(page, reg)
        if len(found) >= expected:
            return found
        page.wait_for_timeout(500)
    return our_blocks(page, reg)


ANCESTORS_JS = """
(el) => {
  const out = [];
  let p = el;
  while (p && p !== document.body && out.length < 12) {
    const attrs = {};
    for (const a of p.attributes) if (/^(role|aria-.*|data-.*|contenteditable|draggable|tabindex)$/.test(a.name)) attrs[a.name] = a.value;
    const r = p.getBoundingClientRect();
    out.push({tag: p.tagName.toLowerCase(), attrs, classes: p.className && p.className.baseVal === undefined ? p.className : '',
              w: Math.round(r.width), h: Math.round(r.height), x: Math.round(r.x), y: Math.round(r.y)});
    p = p.parentElement;
  }
  return out;
}
"""

MEASURE_JS = """
(el) => {
  const r = el.getBoundingClientRect();
  return {x: r.x, y: r.y, w: r.width, h: r.height, layout_w: el.offsetWidth, layout_h: el.offsetHeight};
}
"""


PASTED_SEL = 'iframe[aria-label="Custom embed"]'   # a pasted-code ("Embed code") block's iframe; confirmed 2026-11-08

OTHER_FRAMES_JS = """
([pastedSel, blockSel]) => {
  // Pasted-code blocks on the canvas. The editor keeps the pasted code in a data-code attribute on the block's
  // parent div (confirmed 2026-11-08), so the code can be hashed here the way tests/monitor.py hashes the published
  // page. The editor's own iframes (account bar, canvas chrome) carry no aria-label and are left out.
  const out = [];
  for (const f of document.querySelectorAll(pastedSel)) {
    if (f.closest(blockSel)) continue;
    const r = f.getBoundingClientRect();
    const anc = [];
    let code = null, p = f;
    while (p && p !== document.body && anc.length < 10) {
      const attrs = {};
      for (const a of p.attributes) {
        if (a.name === 'data-code' && code === null) code = a.value;
        if (/^(role|aria-.*|data-.*|guidedhelpid)$/.test(a.name)) attrs[a.name] = a.value.length > 60 ? a.value.slice(0, 57) + '...' : a.value;
      }
      anc.push({tag: p.tagName.toLowerCase(), attrs});
      p = p.parentElement;
    }
    out.push({src: f.src || '', x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
              ancestors: anc, code});
  }
  return out;
}
"""


def code_embeds(reg):
    """[(embed id, match text)] for registry embeds that live as pasted code (type: code, or any with a match)."""
    return [(eid, e.get("match")) for eid, e in reg["embeds"].items() if e.get("match")]


def code_hash(code):
    """tests/monitor.py's hash of pasted code: sha256 of the code, first 12 hex."""
    return hashlib.sha256(code.encode()).hexdigest()[:12]


def frame_of(page, el):
    """The Playwright frame whose <iframe> element is `el`, matched by identity (not URL: a pasted block's inner
    frame is about:blank, and the editor has several frames with no URL at all). None if the tree lacks it."""
    for f in page.frames:
        try:
            fe = f.frame_element()
        except PlaywrightError:
            continue
        if el.evaluate("(a, b) => a === b", fe):
            return f
    return None


def describe_other_blocks(page, reg, site, slug):
    """Pasted-code blocks on the canvas (PASTED_SEL), identified by the registry: the block's data-code hash equal to
    a slot's recorded hash, else a registry embed's `match` text in the code, else in the frame's own text."""
    matches = code_embeds(reg)
    slot_hashes = {s_["hash"]: s_["embed"] for s_ in slots_on(site, slug) if s_.get("hash")}
    rows = page.evaluate(OTHER_FRAMES_JS, [PASTED_SEL, BLOCK_SEL])
    els = page.query_selector_all(PASTED_SEL)
    els = [e for e in els if not e.evaluate(f"e => !!e.closest('{BLOCK_SEL}')")]
    for r, el in zip(rows, els):
        code = r.pop("code")
        r["hash"] = code_hash(code) if code else None
        r["code_hits"] = [eid for eid, m in matches if code and m and m in code]
        r["frame_text"], r["frame_hits"] = None, []
        fr = frame_of(page, el)
        if fr:
            try:
                r["frame_text"] = " ".join(fr.evaluate("() => document.body ? document.body.innerText : ''").split())[:80]
                html_ = fr.content()
                r["frame_hits"] = [eid for eid, m in matches if m and m in html_]
            except PlaywrightError:
                pass
        if r["hash"] in slot_hashes:
            r["embed"], r["how"] = slot_hashes[r["hash"]], "hash (equals the registry slot's)"
        else:
            hits = list(dict.fromkeys(r["code_hits"] + r["frame_hits"]))
            r["embed"] = hits[0] if len(hits) == 1 else None
            r["ambiguous"] = hits if len(hits) > 1 else []
            r["how"] = ("match text in data-code" if r["code_hits"] else "match text in the frame" if r["frame_hits"] else
                        "unidentified" + ("" if code else "; no data-code on the block") + ("" if fr else "; frame not in Playwright's tree"))
        r.setdefault("ambiguous", [])
    rows.sort(key=lambda r: (r["y"], r["x"]))
    return rows


def describe_embeds(page, reg, slots):
    """One row per URL-embed block of ours on the canvas, sorted top to bottom."""
    rows = []
    frames = {f.url for f in page.frames}
    for eid, q, block in wait_for_embeds(page, reg, len(slots)):
        el = block_iframe(block)
        m = el.evaluate(MEASURE_JS)
        url = block.get_attribute("data-url")
        rows.append({
            "embed": eid,
            "url": url,
            "query": q,
            "wrapper_url": el.get_attribute("src"),
            "frame_seen": url in frames,   # whether Playwright's frame tree also shows our page (it doesn't on a reused tab)
            "x": round(m["x"]), "y": round(m["y"]), "w": round(m["w"]), "h": round(m["h"]),
            "layout_w": m["layout_w"], "layout_h": m["layout_h"],
            "sandbox": el.get_attribute("sandbox"),
            "ancestors": el.evaluate(ANCESTORS_JS),
            "block_data_url": url,
        })
    rows.sort(key=lambda r: (r["y"], r["x"]))
    return rows


def size_labels(page):
    """Visible 'W × H' text on the page. The real editor shows none (2026-11-02); kept for the record."""
    return page.evaluate("""
    () => {
      const out = [];
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let n;
      while ((n = walker.nextNode())) {
        const m = n.textContent.match(/^\\s*(\\d{2,4})\\s*[×x]\\s*(\\d{2,4})\\s*$/);
        if (!m) continue;
        const el = n.parentElement, r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        out.push({text: n.textContent.trim(), tag: el.tagName.toLowerCase(), x: Math.round(r.x), y: Math.round(r.y)});
      }
      return out;
    }""")


# --- one block: find, select, measure, drag -----------------------------------------------------

def find_block(page, reg, eid, query):
    """The block (BLOCK_SEL element) for one embed, by its data-url. Exactly one, or Stop."""
    hits = []
    for b in page.query_selector_all(BLOCK_SEL):
        got_eid, got_q = embed_of(reg, b.get_attribute("data-url") or "")
        if got_eid == eid and got_q == query:
            hits.append(b)
    if len(hits) != 1:
        raise Stop(f"expected exactly one block with data-url for {eid} and query {query or 'none'} "
                   f"({BLOCK_SEL}), found {len(hits)}")
    return hits[0]


def block_iframe(block):
    el = block.query_selector("iframe")
    if not el:
        raise Stop("the block has no iframe inside it; the editor's embed markup changed")
    return el


def measure(block):
    m = block_iframe(block).evaluate(MEASURE_JS)
    m["shape"] = round(m["h"] / m["w"], 3) if m["w"] else None
    return m


def selected(block):
    return block.evaluate(f"b => b.closest('{CELL_SEL}')?.getAttribute('aria-selected')") == "true"


SCROLL_BY_JS = """
(el, dy) => {
  // Scroll the nearest scrollable ancestor (the editor's canvas scrolls inside the page, not the window).
  let p = el.parentElement;
  while (p && !(p.scrollHeight > p.clientHeight && /(auto|scroll)/.test(getComputedStyle(p).overflowY))) p = p.parentElement;
  (p || window).scrollBy(0, dy);
}
"""


def bring_into_view(page, block, bottom_room=0):
    """Scroll the editor so the whole block is on screen, with `bottom_room` px free below its bottom edge
    (the mouse can only act inside the viewport, and a drag needs room to move)."""
    el = block_iframe(block)
    el.evaluate("e => e.scrollIntoView({block: 'center', behavior: 'instant'})")
    page.wait_for_timeout(300)
    m = measure(block)
    short = (m["y"] + m["h"] + bottom_room) - (viewport(page)["h"] - 20)
    if short > 0:
        el.evaluate(SCROLL_BY_JS, short)
        page.wait_for_timeout(300)
        m = measure(block)
    page.wait_for_timeout(200)
    return m


def select_block(page, block):
    """Click the iframe's top-left corner (confirmed 2026-11-02: a click there selects the block, not the embed)."""
    m = bring_into_view(page, block)
    page.mouse.click(m["x"] + 2, m["y"] + 2)
    pace(page)
    return selected(block)


def drag_bottom_handle(page, block, delta_px):
    """Drag the bottom-centre resize handle of the selected block towards delta_px (positive = taller), as far as
    the window allows in one go. Returns the distance actually dragged; the caller re-measures and repeats.

    The mouse can only act inside the viewport. For a block at the bottom of a page the canvas can't scroll far
    enough to make room for a big drag (2026-11-08: two School Hours boxes needed +500 and +95 px with 212 and 94 px
    of room), so the drag is cut to the room there is rather than refused; only a handle that is itself off-screen,
    or room too small for the editor's grid, stops the command."""
    m = bring_into_view(page, block, bottom_room=max(delta_px, 0))
    x, y = m["x"] + m["w"] / 2, m["y"] + m["h"]
    vp = viewport(page)
    lo, hi = 20, vp["h"] - 20
    if not (lo < y < hi):
        raise Stop(f"the bottom handle (y={round(y)}) is outside the window ({vp['w']} × {vp['h']}) even after scrolling; "
                   f"make the Chrome window taller and run again")
    room = (hi - 1 - y) if delta_px > 0 else (y - lo - 1)
    if room < MIN_DRAG:
        raise Stop(f"only {round(room)}px of room {'below' if delta_px > 0 else 'above'} the bottom handle (y={round(y)}) in a "
                   f"{vp['w']} × {vp['h']} window; make the Chrome window taller and run again")
    if abs(delta_px) > room:
        delta_px = room if delta_px > 0 else -room
    page.mouse.move(x, y)
    page.wait_for_timeout(300)
    page.mouse.down()
    page.wait_for_timeout(300)
    for i in range(1, DRAG_STEPS + 1):
        page.mouse.move(x, y + delta_px * i / DRAG_STEPS)
        page.wait_for_timeout(60)
    page.wait_for_timeout(300)
    page.mouse.up()
    pace(page)
    return delta_px


def fmt(m):
    return f"{round(m['w'])} × {round(m['h'])} (h/w {m['shape']})"


def inventory(page, reg, site_key, slug, rows):
    """Write the DOM record Google's editor changes would be diagnosed from: _editor/<site>-<page>-<time>.{json,png,html}."""
    OUT.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = OUT / f"{site_key}-{slug}-{stamp}"
    hooks = page.evaluate("""
    () => {
      const count = (sel, attr) => {
        const m = {};
        for (const el of document.querySelectorAll(sel)) { const v = el.getAttribute(attr); m[v] = (m[v] || 0) + 1; }
        return m;
      };
      const data = {};
      for (const el of document.querySelectorAll('*')) for (const a of el.attributes) if (a.name.startsWith('data-')) data[a.name] = (data[a.name] || 0) + 1;
      return {roles: count('[role]', 'role'), aria_labels: count('[aria-label]', 'aria-label'), data_attributes: data,
              iframes: [...document.querySelectorAll('iframe')].map(f => {
                const r = f.getBoundingClientRect();
                return {src: f.src, w: Math.round(r.width), h: Math.round(r.height), x: Math.round(r.x), y: Math.round(r.y),
                        sandbox: f.getAttribute('sandbox'), title: f.title, name: f.name};
              })};
    }""")
    record = {"when": stamp, "site": site_key, "page": slug, "editor_url": page.url, "viewport": viewport(page),
              "account": account_label(page), "embeds": rows, "size_labels": size_labels(page),
              "frames": [{"url": f.url, "parent": f.parent_frame.url if f.parent_frame else None} for f in page.frames],
              "hooks": hooks}
    base.with_suffix(".json").write_text(json.dumps(record, indent=1))
    base.with_suffix(".html").write_text(page.content())
    page.screenshot(path=str(base.with_suffix(".png")), full_page=False)
    print(f"DOM record written: {base}.json / .html / .png")
    return base


# --- starting Chrome -----------------------------------------------------------------------------

def profiles_in(data_dir):
    """{profile directory name: [account emails]} for every profile in a Chrome user data dir."""
    out = {}
    for pref in pathlib.Path(data_dir).glob("*/Preferences"):
        try:
            info = json.loads(pref.read_text()).get("account_info") or []
        except (OSError, ValueError):
            continue
        out[pref.parent.name] = [a.get("email", "") for a in info if isinstance(a, dict)]
    return out


def debug_port_up(cdp):
    try:
        with urllib.request.urlopen(cdp.rstrip("/") + "/json/version", timeout=2) as r:
            return json.load(r).get("Browser")
    except Exception:
        return None


def chrome_command(data_dir, profile, port, url):
    """The command that starts the real Chrome app with this data dir, maximised, debug port on, one tab open."""
    args = [f"--remote-debugging-port={port}", f"--user-data-dir={data_dir}", f"--profile-directory={profile}",
            "--start-maximized", "--no-first-run", "--no-default-browser-check", url]
    if os.environ.get("SITES_EDITOR_HEADLESS"):   # mock test only: no display on CI
        args[0:0] = ["--headless=new", "--no-sandbox"]
    if platform.system() == "Darwin" and not os.environ.get("PW_CHROMIUM"):
        return ["open", "-na", "Google Chrome", "--args"] + args
    exe = os.environ.get("PW_CHROMIUM") or shutil.which("google-chrome") or shutil.which("chromium")
    if not exe:
        raise Stop("no Chrome found: set PW_CHROMIUM=<path to the Chrome binary>")
    return [exe] + args


def cmd_chrome(a, reg):
    cdp = a.cdp
    port = urllib.parse.urlsplit(cdp).port or 9222
    up = debug_port_up(cdp)
    if up:
        print(f"Chrome is already listening at {cdp} ({up}); nothing to start")
        return 0
    data_dir = pathlib.Path(a.user_data_dir).expanduser()
    unreadable = None
    try:
        exists = data_dir.exists()
        if exists:
            os.listdir(data_dir)   # only to find out whether this process may read it
    except OSError as e:
        # macOS keeps Chrome's data dir from some processes (the claude CLI on the Mini, 2026-11-06: EPERM on
        # listing, though the dir is the user's own). Then the script can't tell who is signed in; Chrome can
        # still start there, and `list` prints the account.
        exists, unreadable = True, e
    profiles = profiles_in(data_dir) if exists and not unreadable else {}
    signed_in = [name for name, emails in profiles.items() if ACCOUNT in emails]
    if not exists or (not signed_in and not unreadable):
        # First time: make the data dir, open Chrome on the Google sign-in page, and leave the sign-in to a person.
        data_dir.mkdir(parents=True, exist_ok=True)
        cmd = chrome_command(data_dir, "Default", port, "https://accounts.google.com/")
        why = "doesn't exist yet" if not exists else f"has no profile signed in as {ACCOUNT} (profiles: {profiles})"
        print(f"{data_dir} {why}. Starting Chrome there on the Google sign-in page; sign in as {ACCOUNT} by hand, "
              f"once, then run this command again. (This script never handles a password.)")
        print("  " + " ".join(cmd))
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return 1
    profile = signed_in[0] if signed_in else "Default"
    cmd = chrome_command(data_dir, profile, port, "about:blank")
    if unreadable:
        print(f"can't read {data_dir} ({unreadable.strerror}): this process isn't allowed to look at Chrome's data, so who is "
              f"signed in is unknown. Starting Chrome there anyway, maximised, debug port {port}; `list` prints the account:")
    else:
        print(f"starting Chrome with {data_dir} (profile {profile!r}, signed in as {ACCOUNT}), maximised, debug port {port}:")
    print("  " + " ".join(cmd))
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        time.sleep(0.5)
        up = debug_port_up(cdp)
        if up:
            print(f"Chrome is up: {up} at {cdp}. Next: list / resize / publish")
            return 0
    raise Stop(f"Chrome didn't open the debug port within 20 s. Most likely a Chrome using {data_dir} was already running "
               f"without it (macOS then just focuses that window and ignores the flags): quit that window and run again")


# --- commands -----------------------------------------------------------------------------------

def cmd_tabs(a, reg):
    with sync_playwright() as pw:
        browser = attach(pw, a.cdp)
        for i, ctx in enumerate(browser.contexts):
            for p in ctx.pages:
                print(f"context {i}: {p.url}")
                print(f"           title: {p.title()[:80]}")
    return 0


def show_rows(reg, site, slug, rows, vp):
    slots = slots_on(site, slug)
    print(f"window {vp['w']} × {vp['h']} (device pixel ratio {vp['dpr']})" + window_note(vp))
    if not rows:
        print(f"no embed of ours on this page (no {BLOCK_SEL} whose data-url starts with {PAGES}shared/...)")
    for r in rows:
        want = next((s for s in slots if s["embed"] == r["embed"] and slot_query(s) == r["query"]), None)
        box = box_of(reg, want["box"]) if want and want.get("box") else None
        shape = round(r["h"] / r["w"], 3) if r["w"] else None
        reg_note = (f"registry box {want['box']} = {box['w']} × {box['h']} (h/w {round(box['h']/box['w'], 3)})" if box
                    else "not a registered slot on this page" if not want else "registered, no box")
        print(f"- {r['embed']}  {r['url']}")
        print(f"    box {r['w']} × {r['h']} (h/w {shape}) at x={r['x']} y={r['y']} in the window; {reg_note}")
        if r["layout_w"] and abs(r["layout_w"] - r["w"]) > 1:
            print(f"    laid out at {r['layout_w']} × {r['layout_h']}, drawn scaled ×{round(r['w'] / r['layout_w'], 3)}")
        if r["wrapper_url"]:
            print(f"    wrapped by {r['wrapper_url'][:100]}")
        print(f"    block: {BLOCK_SEL[:36]}…] with this data-url; our page {'is' if r['frame_seen'] else 'is not'} in Playwright's frame tree")
        chain = " > ".join(f"{p['tag']}" + (f"[role={p['attrs']['role']}]" if 'role' in p['attrs'] else "")
                           + (f"[aria-label={p['attrs']['aria-label']!r}]" if 'aria-label' in p['attrs'] else "")
                           for p in r["ancestors"][:6])
        print(f"    iframe ancestors: {chain}")
    for s in slots:
        if s.get("status", "url") == "url" and not any(r["embed"] == s["embed"] for r in rows):
            print(f"- MISSING: registry lists {s['embed']} on this page but no URL-embed block carries its URL")


def show_other_blocks(reg, site, slug, others):
    """Pasted-code blocks: what they are, their data-code hash against the registry (ROADMAP C4)."""
    slots = [s_ for s_ in slots_on(site, slug) if s_.get("status") == "code"]
    if not others and not slots:
        return
    print(f"pasted-code blocks on the page ({PASTED_SEL}): {len(others)}")
    for r in others:
        known = next((s_ for s_ in slots if s_["embed"] == r["embed"]), None) if r["embed"] else None
        what = (f"{r['embed']} (registered on this page, status code)" if known else
                f"{r['embed']} (in registry, but not as a slot on this page)" if r["embed"] else
                f"ambiguous: matches {r['ambiguous']}" if r["ambiguous"] else "not in registry.yaml")
        print(f"- {what}; identified by {r['how']}")
        hash_note = (f"hash {r['hash']}" + (f" = registry" if known and known.get("hash") == r["hash"] else
                     f" ≠ registry {known['hash']} (pasted code edited since it was recorded)" if known and known.get("hash") else "")
                     if r["hash"] else "no data-code to hash")
        print(f"    iframe {r['w']} × {r['h']} at x={r['x']} y={r['y']}; {hash_note}")
        if r["frame_text"]:
            print(f"    starts: {r['frame_text']!r}")
        chain = " > ".join(f"{p['tag']}" + "".join(f"[{k}={v!r}]" for k, v in p["attrs"].items()
                           if k in ("role", "aria-label", "data-tile-id", "data-in-editor") or k == "data-code")
                           for p in r["ancestors"][:4])
        print(f"    ancestors: {chain}")
    for s_ in slots:
        if not any(r["embed"] == s_["embed"] for r in others):
            print(f"- MISSING: registry lists pasted-code embed {s_['embed']} on this page but no block here carries its hash or match text")


def cmd_list(a, reg):
    site = site_of(reg, a.site)
    with sync_playwright() as pw:
        browser = attach(pw, a.cdp)
        page = editor_tab(browser, site)
        acct = account_label(page)
        print(f"signed in as: {acct or 'unknown (no Google Account button found)'}")
        go_to_page(page, a.page)
        rows = describe_embeds(page, reg, slots_on(site, a.page))
        show_rows(reg, site, a.page, rows, viewport(page))
        show_other_blocks(reg, site, a.page, describe_other_blocks(page, reg, site, a.page))
        if a.select:
            for r in rows:
                try:
                    block = find_block(page, reg, r["embed"], r["query"])
                except Stop as e:
                    print(f"- {r['embed']}: can't select ({e})")
                    continue
                ok = select_block(page, block)
                labels = [l["text"] for l in size_labels(page)]
                print(f"- selected {r['embed']} by a corner click: editor marks it selected = {ok}"
                      f"; size label(s) {labels or 'none (the editor shows none)'}")
        if a.dump:
            inventory(page, reg, a.site, a.page, rows)
    return 0


def cmd_resize(a, reg):
    site = site_of(reg, a.site)
    target = box_of(reg, a.box)
    want_shape = target["h"] / target["w"]
    slot = next((s for s in slots_on(site, a.page) if s["embed"] == a.embed), None)
    if not slot:
        raise Stop(f"registry.yaml doesn't list {a.embed} on {a.site}/{a.page}; resize only registered slots")
    print(f"resize {a.site}/{a.page} {a.embed} to box `{a.box}` = {target['w']} × {target['h']} (h/w {round(want_shape, 3)})"
          + ("" if a.apply else "  (dry run: nothing is dragged)"))
    with sync_playwright() as pw:
        browser = attach(pw, a.cdp)
        page = editor_tab(browser, site)
        go_to_page(page, a.page)
        wait_for_embeds(page, reg, len(slots_on(site, a.page)))
        vp = viewport(page)
        print(f"window {vp['w']} × {vp['h']}" + window_note(vp))
        block = find_block(page, reg, a.embed, slot_query(slot))
        before = measure(block)
        # The editor keeps the width (the column); only the height is dragged, so the target is a height
        # for the width as drawn now. At a narrow window the canvas is scaled and the numbers are smaller,
        # but the shape is what Sites publishes (CLAUDE.md §5), so the shape is what we aim at.
        target_h = before["w"] * want_shape
        plan = f"drag the bottom-centre handle by {round(target_h - before['h']):+d}px (to ≈{round(before['w'])} × {round(target_h)})"
        print(f"before: {fmt(before)}; {plan}")
        if abs(before["shape"] - want_shape) <= SHAPE_TOL:
            print("already at the target shape; nothing to do")
            return 0
        if not a.apply:
            print("dry run only; add --apply to drag. Nothing is published by resize.")
            return 0
        if not select_block(page, block):
            raise Stop(f"the corner click didn't select the block ({CELL_SEL} has no aria-selected=true); "
                       f"the editor's selection changed, nothing was dragged")
        cur = before
        for i in range(1, MAX_DRAGS + 1):
            delta = cur["w"] * want_shape - cur["h"]
            done = drag_bottom_handle(page, block, delta)
            block = find_block(page, reg, a.embed, slot_query(slot))   # the editor may re-render the block
            new = measure(block)
            part = "" if abs(done - delta) < 1 else f" (of {round(delta):+d} wanted; the window had room for {round(done):+d})"
            print(f"drag {i}: by {round(done):+d}px{part} -> {fmt(new)}")
            if abs(new["w"] - cur["w"]) > 1:
                raise HalfDone(f"the width changed ({round(cur['w'])} -> {round(new['w'])}) although only the bottom handle "
                               f"should have moved. Check the block in the editor; Undo (⌘Z) or Version history puts it back")
            if abs(new["h"] - cur["h"]) < 1:
                raise HalfDone(f"drag {i} changed nothing (still {fmt(new)}): the handle isn't at the bottom centre of the "
                               f"iframe, or the block lost its selection. Nothing else was touched")
            cur = new
            if abs(cur["shape"] - want_shape) <= SHAPE_TOL:
                break
        else:
            raise HalfDone(f"after {MAX_DRAGS} drags the box is {fmt(cur)}, target h/w {round(want_shape, 3)} (±{SHAPE_TOL}). "
                           f"The editor's grid may not allow it; check in the editor before publishing")
        print(f"after: {fmt(cur)} (was {fmt(before)}); target h/w {round(want_shape, 3)} reached within ±{SHAPE_TOL}")
        print("not published. Look at it in the editor, then: publish --site " + a.site + " --apply")
    return 0


def dialog_state(page):
    """The open dialog's text and its buttons' labels, or None if no dialog is open."""
    return page.evaluate("""
    () => {
      const d = [...document.querySelectorAll('[role=dialog], [role=alertdialog]')].find(e => e.getBoundingClientRect().height > 0);
      if (!d) return null;
      const buttons = [...d.querySelectorAll('[role=button], button')].filter(b => b.getBoundingClientRect().height > 0)
        .map(b => (b.innerText || b.getAttribute('aria-label') || '').trim());
      return {text: d.innerText.trim().slice(0, 400), buttons};
    }""")


def cmd_publish(a, reg):
    site = site_of(reg, a.site)
    print(f"publish {a.site} ({site['live']})" + ("" if a.apply else "  (dry run: nothing is clicked)"))
    with sync_playwright() as pw:
        browser = attach(pw, a.cdp)
        page = editor_tab(browser, site)
        d = dialog_state(page)
        if d and "publish" in d["text"].lower():
            # The review dialog covers the app bar, so look for it before the button (a previous run may have left it).
            print("the publish dialog is already open")
            if not a.apply:
                print(f"dialog: {d['text'][:200]!r}; buttons {d['buttons']}")
                print("dry run only; left the dialog as it was")
                return 0
        else:
            btn = page.query_selector(PUBLISH_SEL) or page.query_selector(PUBLISH_FALLBACK)
            if not btn or not btn.is_visible():
                raise Stop(f"no Publish button ({PUBLISH_SEL} or {PUBLISH_FALLBACK}) in the editor's app bar")
            print(f"Publish button found: '{' '.join((btn.inner_text() or '').split())}'")
            if not a.apply:
                print("dry run only; add --apply to click Publish and confirm in its dialog")
                return 0
            btn.click()
            pace(page)
            d = dialog_state(page)
        if not d:
            raise HalfDone("clicked Publish but no dialog opened. Look at the editor: if it published without asking, "
                           "check the live page; otherwise nothing changed")
        print(f"dialog: {d['text'][:200]!r}; buttons {d['buttons']}")
        buttons = page.locator('[role=dialog] [role=button], [role=dialog] button, [role=alertdialog] [role=button]')
        if re.search(r"no unpublished changes", d["text"], re.I):
            # The review dialog with nothing to review: its Publish is disabled (seen 2026-11-06 after a restore).
            back = buttons.filter(has_text=re.compile(r"^\s*return to editor\s*$", re.I))
            if back.count():
                back.first.click()
            else:
                page.keyboard.press("Escape")
            pace(page)
            print("nothing to publish: the draft is what is live already ('There are no unpublished changes to review'); "
                  "returned to the editor")
            return 0
        confirm = [b for b in d["buttons"] if b.lower() == "publish"]
        if len(confirm) != 1:
            page.keyboard.press("Escape")
            raise HalfDone(f"the dialog has no single 'Publish' button (buttons: {d['buttons']}); pressed Escape to close it. "
                           f"Nothing was published; record the dialog in docs/sites-editor-driver.md §4")
        ok = buttons.filter(has_text=re.compile(r"^\s*Publish\s*$")).first
        if ok.get_attribute("aria-disabled") == "true":
            page.keyboard.press("Escape")
            raise HalfDone("the dialog's Publish button is disabled though the dialog doesn't say why; pressed Escape. "
                           "Nothing was published; look at the editor")
        ok.click(timeout=10000)
        for _ in range(20):
            page.wait_for_timeout(500)
            if not dialog_state(page):
                break
        else:
            raise HalfDone("confirmed Publish but the dialog is still open after 10 s; look at the editor")
        pace(page)
        print(f"published. Verify on the live Site: python3 tests/live_check.py --site {a.site}")
    return 0


def confirm_dialog(page):
    """Like dialog_state, but the smallest open dialog: Version history is itself a full-window [role=dialog]."""
    return page.evaluate("""
    () => {
      const ds = [...document.querySelectorAll('[role=dialog], [role=alertdialog]')]
        .map(e => [e, e.getBoundingClientRect()]).filter(([e, r]) => r.height > 0)
        .sort((a, b) => a[1].width * a[1].height - b[1].width * b[1].height);
      if (!ds.length) return null;
      const d = ds[0][0];
      const buttons = [...d.querySelectorAll('[role=button], button')].filter(b => b.getBoundingClientRect().height > 0)
        .map(b => (b.innerText || b.getAttribute('aria-label') || '').trim());
      return {text: d.innerText.trim().slice(0, 400), buttons, w: ds[0][1].width};
    }""")


def close_version_history(page):
    page.keyboard.press("Escape")
    pace(page)
    if page.query_selector(VH_RESTORE_SITE) or page.locator('[role=complementary]').filter(has_text="Version history").count():
        back = page.query_selector('[role=dialog] [aria-label="Back"], [role=dialog] [aria-label="Close"]')
        if back:
            back.click()
            pace(page)


def cmd_restore(a, reg):
    """Make the newest published version (what families see now) the draft again, dropping unpublished edits.

    The editor's rollback (docs/sites-editor-driver.md §3). Never publishes: after a restore the draft equals the
    live site, so `publish` afterwards changes nothing visible; after a bad publish, `restore` then `publish` is
    the way back."""
    site = site_of(reg, a.site)
    print(f"restore {a.site} to its newest published version" + ("" if a.apply else "  (dry run: nothing is restored)"))
    with sync_playwright() as pw:
        browser = attach(pw, a.cdp)
        page = editor_tab(browser, site)
        panel = page.locator('[role=complementary]').filter(has_text="Version history").first
        if panel.count():
            print("version history is already open")
        else:
            btn = page.query_selector(VH_OPEN)
            if not btn or not btn.is_visible():
                raise Stop(f"no {VH_OPEN} button in the editor's app bar")
            btn.click()
            pace(page, 3000)
            panel = page.locator('[role=complementary]').filter(has_text="Version history").first
        if not panel.count():
            raise Stop("clicked version history but no panel titled 'Version history' opened")
        lines = [l.strip() for l in panel.inner_text().split("\n") if l.strip()]
        print("versions, newest first: " + " | ".join(lines[2:14]) + (" …" if len(lines) > 14 else ""))
        published = panel.get_by_text(re.compile(r"^Published ")).first
        if not published.count():
            close_version_history(page)
            raise Stop("no 'Published …' version in the list (closed the panel)")
        label = published.inner_text().strip()
        published.click()
        pace(page)
        header = page.evaluate("(document.querySelector('[role=dialog]') || {innerText: ''}).innerText.split('\\n')[0]")
        print(f"selected '{label}' (the editor heads it {header!r})")
        restore = page.query_selector(VH_RESTORE_SITE)
        if not restore or not restore.is_visible():
            close_version_history(page)
            raise Stop(f"no {VH_RESTORE_SITE} button after selecting that version (closed the panel)")
        if not a.apply:
            close_version_history(page)
            print("dry run only; add --apply to click 'Restore this site version' and confirm. Nothing is published by restore.")
            return 0
        restore.click()
        pace(page)
        d = confirm_dialog(page)
        if not d or d["w"] > 1200:
            raise HalfDone("clicked 'Restore this site version' but no confirmation dialog opened; look at the editor")
        print(f"dialog: {d['text'][:200]!r}; buttons {d['buttons']}")
        confirm = [b for b in d["buttons"] if b.lower() == "restore"]
        if len(confirm) != 1:
            page.keyboard.press("Escape")
            raise HalfDone(f"the dialog has no single 'Restore' button (buttons: {d['buttons']}); pressed Escape to close it. "
                           f"Nothing was restored; record the dialog in docs/sites-editor-driver.md §4")
        page.locator('[role=dialog] [role=button], [role=dialog] button, [role=alertdialog] [role=button]').filter(
            has_text=re.compile(r"^\s*Restore\s*$")).last.click()
        for _ in range(20):
            page.wait_for_timeout(500)
            vh = page.query_selector(VH_OPEN)
            if not page.query_selector(VH_RESTORE_SITE) and vh and vh.is_visible():
                break
        else:
            raise HalfDone("confirmed Restore but the version history is still open after 10 s; look at the editor")
        pace(page)
        print(f"restored '{label}' as the draft; not published. Check with: list --site {a.site} --page <page>")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cdp", default=CDP, help=f"Chrome's remote-debugging URL (default {CDP})")
    ap.add_argument("--registry", default=str(ROOT / "registry.yaml"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("chrome", help="start the real Chrome on the classpages@ data dir, maximised, with the debug port on")
    p.add_argument("--user-data-dir", default=CHROME_DIR, help=f"Chrome user data dir signed in as {ACCOUNT} (default {CHROME_DIR})")
    sub.add_parser("tabs", help="list what the attached Chrome has open")
    p = sub.add_parser("list", help="print every embed on one page of one site (read-only)")
    p.add_argument("--site", required=True, help="site key in registry.yaml, e.g. class-2034")
    p.add_argument("--page", default="home", help="page slug as in registry.yaml (home, email-digest)")
    p.add_argument("--select", action="store_true", help="click each block and report whether the editor selected it")
    p.add_argument("--dump", action="store_true", help="write a DOM record to _editor/ (json, html, png)")
    p = sub.add_parser("resize", help="drag one embed's box to a standard box (dry run unless --apply); never publishes")
    p.add_argument("--site", required=True)
    p.add_argument("--page", required=True)
    p.add_argument("--embed", required=True, help="embed id in registry.yaml, e.g. room-parents")
    p.add_argument("--box", required=True, help="a box name from registry.yaml (card, page)")
    p.add_argument("--apply", action="store_true")
    p = sub.add_parser("publish", help="click Publish and confirm (dry run unless --apply)")
    p.add_argument("--site", required=True)
    p.add_argument("--apply", action="store_true")
    p = sub.add_parser("restore", help="make the newest published version the draft again, via Version history (dry run unless --apply); never publishes")
    p.add_argument("--site", required=True)
    p.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    try:
        reg = load_registry(a.registry)
        return {"chrome": cmd_chrome, "tabs": cmd_tabs, "list": cmd_list, "resize": cmd_resize, "publish": cmd_publish,
                "restore": cmd_restore}[a.cmd](a, reg)
    except Stop as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 1
    except HalfDone as e:
        print(f"STOPPED HALF-WAY: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
