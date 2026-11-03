#!/usr/bin/env python3
"""Drive the Google Sites editor from a script, so a Claude session never clicks through it.

Google Sites has no API (CLAUDE.md §5). This attaches to a Chrome that a person already
signed in as classpages@sffriendsschool.org and started with remote debugging:

    open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir=<profile dir>

It never handles a password, never launches a browser of its own and never runs headless.
Docs, the editor DOM it depends on, and what has been tested: docs/sites-editor-driver.md.

Commands (one site, one page, one action per run; no loops over sites):

    tabs                                   what the attached Chrome has open
    list    --site class-2034 --page home  every embed on the page: URL, box, position (read-only)
    resize  --site .. --page .. --embed room-parents --box card [--apply]   (step 2; --apply not built yet)
    publish --site class-2034 [--apply]                                      (step 3; --apply not built yet)

`list --dump` also writes _editor/<site>-<page>-<time>.json (+ .png, .html): an inventory of
the editor DOM around each embed, for recording stable hooks in the doc when Google changes
the editor. `list --select` clicks a block to make the editor show its size label (the only
thing `list` touches; it changes nothing).

Exit codes: 0 ok, 1 the editor or Chrome isn't as expected (the message says what), 2 the
action isn't built yet.
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import re
import sys
import urllib.parse

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
PACE_MS = 1500          # pause after anything that changes what the editor shows; keeps actions human-paced
LOAD_WAIT = 40          # × 500 ms to wait for the editor to lay its embeds out
MIN_WINDOW_W = 1440     # registry boxes were measured in the editor at this width; narrower may scale the canvas
SIZE_LABEL = re.compile(r"^\s*(\d{2,4})\s*[×x]\s*(\d{2,4})\s*$")


class Stop(Exception):
    """The editor, Chrome or the registry isn't as this script expects. Say so and stop; don't guess."""


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


def page_title(slug):
    """Registry page slug -> the title shown in the editor's Pages panel ("email-digest" -> "Email Digest")."""
    return " ".join(w.capitalize() for w in slug.split("-"))


def norm(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def url_query(url):
    return {k: v[-1] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).items()}


# --- Chrome ------------------------------------------------------------------------------------

def attach(pw, cdp):
    try:
        browser = pw.chromium.connect_over_cdp(cdp, timeout=10000)
    except PlaywrightError as e:
        raise Stop(f"can't attach to Chrome at {cdp} ({str(e).splitlines()[0]}).\n"
                   f"Start Chrome with remote debugging, signed in as classpages@:\n"
                   f'  open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir=<profile dir>')
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
            return el.get_attribute("aria-label")
    return None


def viewport(page):
    return page.evaluate("() => ({w: window.innerWidth, h: window.innerHeight, dpr: window.devicePixelRatio})")


# --- the page being edited ----------------------------------------------------------------------

PAGE_ITEM_JS = """
(title) => {
  // Candidate page entries in the Pages panel: visible elements whose own text is exactly the title.
  const want = title.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
  const out = [];
  for (const el of document.querySelectorAll('[role=treeitem], [role=option], [role=listitem], [role=link], [role=button], li, a, div, span')) {
    const t = (el.innerText || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
    if (t !== want) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    // Prefer the smallest element with that text (the leaf), and record what it sits in.
    let p = el, chain = [];
    while (p && p !== document.body && chain.length < 8) {
      chain.push({tag: p.tagName.toLowerCase(), role: p.getAttribute('role'), aria: p.getAttribute('aria-label'),
                  selected: p.getAttribute('aria-selected')});
      p = p.parentElement;
    }
    out.push({text: el.innerText.trim(), tag: el.tagName.toLowerCase(), role: el.getAttribute('role'),
              area: r.width * r.height, x: r.x, y: r.y, w: r.width, h: r.height, chain});
  }
  out.sort((a, b) => a.area - b.area);
  return out;
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
    """Select the page in the Pages panel. Returns (title, editor URL after the click, how it was found)."""
    title = page_title(slug)
    clicked = open_pages_panel(page)
    items = page.evaluate(PAGE_ITEM_JS, title)
    # Prefer an entry inside the pages tree; otherwise the smallest exact-text match anywhere.
    in_tree = [i for i in items if any(c["role"] in ("tree", "treeitem") for c in i["chain"])]
    pick = (in_tree or items or [None])[0]
    if not pick:
        raise Stop(f"no entry titled '{title}' in the editor's Pages panel (registry page `{slug}`). "
                   f"Either the page is named differently or the panel isn't where this script looks")
    before = page.url
    page.mouse.click(pick["x"] + pick["w"] / 2, pick["y"] + pick["h"] / 2)
    pace(page)
    where = "pages tree" if pick in in_tree else f"<{pick['tag']} role={pick['role']}>"
    print(f"page '{title}': clicked its entry in the {where}"
          + (f"; panel opened via {clicked}" if clicked else "")
          + (f"; editor URL {before} -> {page.url}" if page.url != before else f"; editor URL unchanged ({page.url})"))
    return title, page.url, where


# --- embeds on the canvas -----------------------------------------------------------------------

def top_frame(frame):
    """The outermost frame below the editor document that contains this frame (Sites wraps URL embeds)."""
    while frame.parent_frame and frame.parent_frame.parent_frame:
        frame = frame.parent_frame
    return frame


def wait_for_embeds(page, reg, expected):
    for _ in range(LOAD_WAIT):
        found = our_frames(page, reg)
        if len(found) >= expected:
            return found
        page.wait_for_timeout(500)
    return our_frames(page, reg)


def our_frames(page, reg):
    """[(embed id, frame)] for every frame on the editor page whose URL is one of our Pages embeds."""
    out = []
    for f in page.frames:
        for eid, emb in reg["embeds"].items():
            if emb.get("path") and f.url.startswith(PAGES + emb["path"]):
                out.append((eid, f))
    return out


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


def describe_embeds(page, reg, slots):
    """One row per embed of ours on the canvas, outermost frame first, sorted top to bottom."""
    rows = []
    seen = set()
    for eid, frame in wait_for_embeds(page, reg, len(slots)):
        outer = top_frame(frame)
        if outer in seen:
            continue
        seen.add(outer)
        try:
            el = outer.frame_element()
        except PlaywrightError:
            continue
        box = el.bounding_box() or {}
        rows.append({
            "embed": eid,
            "url": frame.url,
            "query": url_query(frame.url),
            "wrapper_url": outer.url if outer is not frame else None,
            "x": round(box.get("x", 0)), "y": round(box.get("y", 0)),
            "w": round(box.get("width", 0)), "h": round(box.get("height", 0)),
            "sandbox": el.get_attribute("sandbox"),
            "ancestors": el.evaluate(ANCESTORS_JS),
        })
    rows.sort(key=lambda r: (r["y"], r["x"]))
    return rows


def size_labels(page):
    """Every visible element whose own text is a 'W × H' label (what the editor shows for a selected box)."""
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
        const attrs = {};
        for (const a of el.attributes) attrs[a.name] = a.value;
        out.push({text: n.textContent.trim(), w: +m[1], h: +m[2], tag: el.tagName.toLowerCase(), attrs,
                  x: Math.round(r.x), y: Math.round(r.y)});
      }
      return out;
    }""")


def select_block(page, row):
    """Click the block, not the iframe: the nearest ancestor that starts above the iframe gets a click on its top
    edge (a click inside the iframe goes to the embed, not the editor). Returns (where, size labels after it)."""
    above = [a for a in row["ancestors"][1:] if 0 < row["y"] - a["y"] < 60]
    if above:
        x, y, where = row["x"] + row["w"] / 2, above[0]["y"] + 1, f"top edge of <{above[0]['tag']} {above[0]['attrs']}>"
    else:
        x, y, where = row["x"] + 2, row["y"] + 2, "the iframe's top-left corner (no block element starts above it)"
    page.mouse.click(x, y)
    pace(page)
    labels = size_labels(page)
    labels.sort(key=lambda l: min(abs(l["y"] - row["y"]), abs(l["y"] - row["y"] - row["h"])))   # nearest the block first
    return where, labels


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
    print(f"window {vp['w']} × {vp['h']} (device pixel ratio {vp['dpr']})"
          + ("" if vp["w"] >= MIN_WINDOW_W else f"  ← narrower than {MIN_WINDOW_W}; the canvas may be scaled, so sizes below may not be editor-box sizes"))
    if not rows:
        print("no embed of ours on this page (no frame whose URL starts with " + PAGES + "shared/...)")
    for r in rows:
        want = next((s for s in slots if s["embed"] == r["embed"] and {k: str(v) for k, v in (s.get("query") or {}).items()} == r["query"]), None)
        box = box_of(reg, want["box"]) if want and want.get("box") else None
        shape = round(r["h"] / r["w"], 3) if r["w"] else None
        reg_note = (f"registry box {want['box']} = {box['w']} × {box['h']} (h/w {round(box['h']/box['w'], 3)})" if box
                    else "not a registered slot on this page" if not want else "registered, no box")
        print(f"- {r['embed']}  {r['url']}")
        print(f"    box {r['w']} × {r['h']} (h/w {shape}) at x={r['x']} y={r['y']} in the window; {reg_note}")
        if r["wrapper_url"]:
            print(f"    wrapped by {r['wrapper_url'][:100]}")
        chain = " > ".join(f"{p['tag']}" + (f"[role={p['attrs']['role']}]" if 'role' in p['attrs'] else "")
                           + (f"[aria-label={p['attrs']['aria-label']!r}]" if 'aria-label' in p['attrs'] else "")
                           for p in r["ancestors"][:6])
        print(f"    iframe ancestors: {chain}")
    for s in slots:
        if not any(r["embed"] == s["embed"] for r in rows):
            print(f"- MISSING: registry lists {s['embed']} on this page but no frame of ours carries its URL")


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
        if a.select:
            for r in rows:
                where, labels = select_block(page, r)
                print(f"- selected {r['embed']} by clicking {where}: size label(s) {[l['text'] for l in labels] or 'none found'}"
                      + (f"  (first lives in <{labels[0]['tag']} {labels[0]['attrs']}>)" if labels else ""))
        if a.dump:
            inventory(page, reg, a.site, a.page, rows)
    return 0


def cmd_resize(a, reg):
    site = site_of(reg, a.site)
    target = box_of(reg, a.box)
    slot = next((s for s in slots_on(site, a.page) if s["embed"] == a.embed), None)
    if not slot:
        raise Stop(f"registry.yaml doesn't list {a.embed} on {a.site}/{a.page}; resize only registered slots")
    print(f"resize {a.site}/{a.page} {a.embed} to box `{a.box}` = {target['w']} × {target['h']}"
          + ("" if a.apply else "  (dry run: nothing is dragged)"))
    with sync_playwright() as pw:
        browser = attach(pw, a.cdp)
        page = editor_tab(browser, site)
        go_to_page(page, a.page)
        rows = describe_embeds(page, reg, slots_on(site, a.page))
        want = {k: str(v) for k, v in (slot.get("query") or {}).items()}
        mine = [r for r in rows if r["embed"] == a.embed and r["query"] == want]
        if len(mine) != 1:
            raise Stop(f"expected exactly one {a.embed} frame with query {want or 'none'} on the page, found {len(mine)}")
        r = mine[0]
        print(f"before: {r['w']} × {r['h']} (h/w {round(r['h']/r['w'], 3)}); target {target['w']} × {target['h']}; "
              f"delta width {target['w'] - r['w']:+d}, height {target['h'] - r['h']:+d}")
    if not a.apply:
        print("dry run only. --apply isn't built yet: the drag needs the editor's size label and resize handle, "
              "which are recorded on the first real `list --select --dump` run (docs/sites-editor-driver.md, step 2)")
        return 0
    raise NotBuilt("resize --apply")


def cmd_publish(a, reg):
    site = site_of(reg, a.site)
    print(f"publish {a.site} ({site['live']})" + ("" if a.apply else "  (dry run: nothing is clicked)"))
    if not a.apply:
        print("dry run only. --apply isn't built yet: the Publish button and its confirmation dialog are recorded "
              "on the first real editor run (docs/sites-editor-driver.md, step 3)")
        return 0
    raise NotBuilt("publish --apply")


class NotBuilt(Exception):
    pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cdp", default=CDP, help=f"Chrome's remote-debugging URL (default {CDP})")
    ap.add_argument("--registry", default=str(ROOT / "registry.yaml"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("tabs", help="list what the attached Chrome has open")
    p = sub.add_parser("list", help="print every embed on one page of one site (read-only)")
    p.add_argument("--site", required=True, help="site key in registry.yaml, e.g. class-2034")
    p.add_argument("--page", default="home", help="page slug as in registry.yaml (home, email-digest)")
    p.add_argument("--select", action="store_true", help="click each block so the editor shows its size label")
    p.add_argument("--dump", action="store_true", help="write a DOM record to _editor/ (json, html, png)")
    p = sub.add_parser("resize", help="drag one embed's box to a standard box (dry run unless --apply)")
    p.add_argument("--site", required=True)
    p.add_argument("--page", required=True)
    p.add_argument("--embed", required=True, help="embed id in registry.yaml, e.g. room-parents")
    p.add_argument("--box", required=True, help="a box name from registry.yaml (card, page)")
    p.add_argument("--apply", action="store_true")
    p = sub.add_parser("publish", help="click Publish and confirm (dry run unless --apply)")
    p.add_argument("--site", required=True)
    p.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    try:
        reg = load_registry(a.registry)
        return {"tabs": cmd_tabs, "list": cmd_list, "resize": cmd_resize, "publish": cmd_publish}[a.cmd](a, reg)
    except Stop as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 1
    except NotBuilt as e:
        print(f"not built yet: {e}. Finish the DOM record first (docs/sites-editor-driver.md).", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
