#!/usr/bin/env python3
"""Open every published Google Site in registry.yaml and measure every registered embed slot.

Proves live-site behaviour that tests/render_check.py can only imitate: Sites' real iframe
nesting, sandbox and sizing. For each site and page in the registry, at a desktop window and
on an iPhone, it finds each slot's embed frame and records its size and shape (CLAUDE.md §0
item 1), then clicks inside Important Dates (filter, month jump, add buttons).

What fails the run (exit 1, which opens an issue for Ahin on the scheduled run):
  - a registered slot's embed is missing from its page, or placed with the wrong query
    (`?class=` for another class), or the Site shows a version Pages no longer serves;
  - Sites' sandbox changed, or the embed no longer fills its frame;
  - an Important Dates click no longer works on the live Site.

What is reported but never fails (sites are allowed to drift, CLAUDE.md §7):
  - a box whose shape (h ÷ w) is off the registry's `box` by more than SHAPE_TOL;
  - one of our embeds placed on a page the registry doesn't list it on;
  - other content a room parent added: every iframe on the page that isn't ours, by host.

Writes _live/report.md (+ report.json, screenshots). `--mock` builds a fake Site from the local
build in _site/ and checks the checker itself (used in CI, where sites.google.com is also
reachable; used locally where it isn't). PW_CHROMIUM=<path> launches that Chromium instead of
Playwright's own.
"""
import argparse
import functools
import http.server
import json
import os
import pathlib
import re
import sys
import threading
import urllib.parse
import urllib.request

import yaml
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "_live"
PAGES = "https://sffs-class-sites.github.io/class-sites/"
SANDBOX = set("allow-scripts allow-popups allow-forms allow-same-origin allow-popups-to-escape-sandbox "
              "allow-downloads allow-storage-access-by-user-activation".split())
# (label, window width, window height, phone?)
DESKTOP = ("1440", 1440, 900, False)
PHONE = ("iphone", 390, 844, True)
EXTRA_WIDTHS = [("1024", 1024, 768, False), ("1280", 1280, 800, False), ("1920", 1920, 1080, False)]
SHAPE_TOL = 0.02   # measured h ÷ w may differ from the registry box by this much before it counts as drift
LAYOUT_WAIT = 40   # × 500ms: Sites lays embeds out late


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "sffs-class-sites-live-check"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def deployed_versions(reg, pages):
    out = {}
    for eid, emb in reg["embeds"].items():
        if emb.get("type") == "code" or not emb.get("path"):
            continue
        try:
            m = re.search(r'name="sffs-embed" content="([^"]+)"', fetch(pages + emb["path"]))
            out[eid] = m.group(1) if m else None
        except Exception as e:  # Pages down: the monitor reports that; here every slot will read as a version mismatch
            out[eid] = f"unreachable ({e})"
    return out


def slot_query(slot):
    return {k: str(v) for k, v in (slot.get("query") or {}).items()}


def url_query(url):
    return {k: v[-1] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).items()}


def our_frames(page, reg, pages):
    """Every frame on the page whose URL is one of our embeds: [(embed id, frame)]."""
    found = []
    for f in page.frames:
        for eid, emb in reg["embeds"].items():
            if emb.get("path") and f.url.startswith(pages + emb["path"]):
                found.append((eid, f))
    return found


def is_ours_or_wraps_ours(frame, ours):
    if frame in ours:
        return True
    return any(is_ours_or_wraps_ours(c, ours) for c in frame.child_frames)


def host(url):
    return urllib.parse.urlsplit(url).netloc or url[:40]


class Checker:
    def __init__(self, reg, pages, chromium=None, gcal_stub=False):
        self.reg, self.pages, self.chromium, self.gcal_stub = reg, pages, chromium, gcal_stub
        self.failures, self.attention, self.rows, self.extras, self.widths = [], [], [], [], []
        self.versions = deployed_versions(reg, pages)

    def check(self, cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            self.failures.append(msg)
        return cond

    def box(self, slot):
        """A slot's editor box: {w, h}, or the name of one of the registry's standard `boxes`."""
        b = slot.get("box")
        return self.reg.get("boxes", {}).get(b) if isinstance(b, str) else b

    def note(self, msg):
        print("  note " + msg)
        self.attention.append(msg)

    # --- one page at one window -------------------------------------------------------------
    def check_page(self, browser, p, sid, site, page_name, slots, window, interact=True, shot=True, record=True):
        label, w, h, phone = window
        purl = site["live"].rstrip("/") + "/" + page_name
        tag = f"{sid}/{page_name}@{label}"
        print(f"[{tag}] {purl}")
        opts = dict(viewport={"width": w, "height": h}, accept_downloads=True)
        if phone:
            opts.update(p.devices["iPhone 13"], accept_downloads=True)
        ctx = browser.new_context(**opts)
        if self.gcal_stub:
            ctx.route("https://calendar.google.com/**", lambda r: r.fulfill(status=200, content_type="text/html", body="<p>gcal stub</p>"))
        page = ctx.new_page()
        try:
            page.goto(purl, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            self.check(False, f"{tag}: page loads ({e.__class__.__name__})")
            ctx.close()
            return
        # Wait until every slot's embed is present, or give up after LAYOUT_WAIT.
        wanted = [(s["embed"], slot_query(s)) for s in slots]
        for _ in range(LAYOUT_WAIT):
            ours = our_frames(page, self.reg, self.pages)
            if all(any(e == eid and url_query(f.url) == q for e, f in ours) for eid, q in wanted):
                break
            page.wait_for_timeout(500)
        ours = our_frames(page, self.reg, self.pages)
        used = set()
        for slot in slots:
            eid, q = slot["embed"], slot_query(slot)
            stag = f"{tag} {eid}"
            exact = [f for e, f in ours if e == eid and url_query(f.url) == q and f not in used]
            near = [f for e, f in ours if e == eid and f not in used]
            frame = (exact or near or [None])[0]
            row = {"site": sid, "page": page_name, "window": label, "window_w": w, "embed": eid, "found": frame is not None,
                   "query": q, "frame_w": None, "frame_h": None, "aspect_h_over_w": None, "box_h_over_w": None,
                   "drift": None, "version": None, "url": frame.url if frame else None}
            self.rows.append(row)
            if not self.check(frame is not None, f"{stag}: embed frame found on the published page"):
                continue
            used.add(frame)
            got = url_query(frame.url)
            self.check(got == q, f"{stag}: placed with the registered query ({urllib.parse.urlencode(got) or 'none'}"
                                 f"{'' if got == q else ', registry says ' + (urllib.parse.urlencode(q) or 'none')})")
            frame.wait_for_load_state("load")
            el = frame.frame_element()
            el.scroll_into_view_if_needed()
            page.wait_for_timeout(2500)
            box = el.bounding_box()
            fw, fh = round(box["width"]), round(box["height"])
            shape = round(fh / fw, 3) if fw else None
            row.update(frame_w=fw, frame_h=fh, aspect_h_over_w=shape)
            version = frame.evaluate("() => document.querySelector('meta[name=sffs-embed]')?.content")
            row["version"] = version
            print(f"  frame {fw}x{fh} (h/w {shape}), version {version}")
            sandbox = set((el.get_attribute("sandbox") or "").split())
            self.check(sandbox == SANDBOX, f"{stag}: sandbox is exactly Sites' known set ({' '.join(sorted(sandbox - SANDBOX)) or 'no extras'}"
                                           f"{'; missing ' + ' '.join(sorted(SANDBOX - sandbox)) if SANDBOX - sandbox else ''})")
            self.check(version == self.versions.get(eid), f"{stag}: Site shows the deployed version ({version} vs {self.versions.get(eid)})")
            m = frame.evaluate("""() => { const w = document.getElementById('wrap') || document.body;
                return {hscroll: document.documentElement.scrollWidth > innerWidth + 1 || w.scrollWidth > w.clientWidth + 1,
                        fills: Math.abs(document.body.getBoundingClientRect().height - innerHeight) < 2} }""")
            self.check(not m["hscroll"], f"{stag}: no horizontal scroll inside the embed")
            self.check(m["fills"], f"{stag}: embed fills its frame")
            box = self.box(slot)
            if box and shape:
                want = round(box["h"] / box["w"], 3)
                row["box_h_over_w"] = want
                row["drift"] = abs(shape - want) > SHAPE_TOL
                if row["drift"] and record:
                    self.note(f"{stag}: box shape drifted: h ÷ w {shape} on the Site, {want} in registry.yaml ({slot['box']} = {box['w']} × {box['h']})")
            elif shape and record:
                self.note(f"{stag}: no box recorded in registry.yaml; measured h ÷ w {shape}")
            if interact and eid == "important-dates":
                self.important_dates_clicks(page, frame, stag)
            if shot:
                el.screenshot(path=str(OUT / f"{sid}-{page_name}-{eid}-{label}.png"))
        # Our embeds on this page that the registry doesn't list here.
        for e, f in ours:
            if f not in used and record:
                self.note(f"{tag}: {e} is on this page with query '{urllib.parse.urlencode(url_query(f.url)) or 'none'}' but registry.yaml doesn't list it here")
        # Everything else embedded on the page (room-parent additions): report, never fail.
        ours_set = {f for _, f in ours}
        others = [f for f in page.main_frame.child_frames if not is_ours_or_wraps_ours(f, ours_set)]
        if others and record:
            hosts = {}
            for f in others:
                hosts[host(f.url)] = hosts.get(host(f.url), 0) + 1
            self.extras.append({"site": sid, "page": page_name, "window": label, "hosts": hosts})
            print("  other embeds on the page: " + ", ".join(f"{k} ×{v}" for k, v in hosts.items()))
        if shot:
            page.screenshot(path=str(OUT / f"{sid}-{page_name}-{label}.png"), full_page=True)
        ctx.close()

    def important_dates_clicks(self, page, frame, stag):
        # Filter: a category chip hides every row of other categories.
        frame.locator('.chip.cat[data-cat="noschool"]').click()
        cats = frame.evaluate("() => [...document.querySelectorAll('tr.ev:not([hidden])')].map(r => r.dataset.cat)")
        self.check(cats and set(cats) == {"noschool"}, f"{stag}: 'No school' filter shows only no-school rows ({len(cats)})")
        frame.locator('.chip.cat[data-cat="all"]').click()

        # Month jump: the target month lands just under the sticky filter bar.
        target = frame.evaluate("() => { const j = [...document.querySelectorAll('.chip.jump:not([hidden])')]; return j[j.length >> 1]?.dataset.jump }")
        before = frame.evaluate("() => document.getElementById('wrap').scrollTop")
        frame.locator(f'.chip.jump[data-jump="{target}"]').click()
        page.wait_for_timeout(1200)
        gap = frame.evaluate("""id => { const t = document.getElementById(id), bar = document.getElementById('toolbar');
            return Math.round(t.getBoundingClientRect().top - bar.getBoundingClientRect().bottom) }""", target)
        after, bottom = frame.evaluate("() => { const w = document.getElementById('wrap'); return [w.scrollTop, w.scrollHeight - w.clientHeight - w.scrollTop < 2] }")
        self.check(after != before and (-4 <= gap <= 12 or (bottom and gap > 0)),
                   f"{stag}: month jump to {target} lands under the filter bar (gap {gap}px{', scrolled to the end' if bottom else ''})")

        # Add buttons: Google opens a new tab to Google Calendar; Apple downloads a one-event .ics.
        frame.locator('.chip.pref[data-pref="google"]').click()
        a = frame.locator("tr.ev:not([hidden]) .cal-btn").first
        href, tgt = a.get_attribute("href") or "", a.get_attribute("target")
        self.check(href.startswith("https://calendar.google.com/") and tgt == "_blank", f"{stag}: Google add button opens Google Calendar in a new tab")
        frame.locator('.chip.pref[data-pref="apple"]').click()
        try:
            with page.expect_download(timeout=15000) as dl:
                frame.locator("tr.ev:not([hidden]) .cal-btn").first.click()
            ics = pathlib.Path(dl.value.path()).read_text()
            ok, name = ics.count("BEGIN:VEVENT") == 1 and re.search(r"^UID:.+@sffs-calendar\r?$", ics, re.M) is not None, dl.value.suggested_filename
        except Exception as e:
            ok, name = False, e.__class__.__name__
        self.check(ok, f"{stag}: Apple add button downloads a one-event .ics ({name})")
        frame.locator('.chip.pref[data-pref="google"]').click()  # leave the default for the screenshot

    # --- the whole registry -------------------------------------------------------------------
    def run(self, only=None):
        OUT.mkdir(exist_ok=True)
        sites = {sid: s for sid, s in self.reg["sites"].items() if not only or sid in only}
        # The reference page for the width table (§0 item 1): the first class site with Important Dates.
        ref = next(((sid, s["page"]) for sid, site in sites.items() if site.get("kind", "class") == "class"
                    for s in site.get("slots", []) if s["embed"] == "important-dates"), None)
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=self.chromium) if self.chromium else p.chromium.launch()
            for sid, site in sites.items():
                by_page = {}
                for s in site.get("slots", []):
                    if s.get("status", "url") == "url" and self.reg["embeds"][s["embed"]].get("path"):
                        by_page.setdefault(s["page"], []).append(s)
                for page_name, slots in by_page.items():
                    windows = [DESKTOP, PHONE] + (EXTRA_WIDTHS if (sid, page_name) == ref else [])
                    for win in windows:
                        extra = win in EXTRA_WIDTHS
                        self.check_page(browser, p, sid, site, page_name, slots, win, interact=not extra, shot=not extra, record=not extra)
            browser.close()
        if ref:
            self.widths = sorted((r for r in self.rows if (r["site"], r["page"]) == ref and r["embed"] == "important-dates" and r["found"]),
                                 key=lambda r: r["window_w"])
        return self.report()

    def report(self):
        lines = ["## Live Sites check", "", "Deployed embed versions: " + ", ".join(f"`{k}` {v}" for k, v in self.versions.items()), "",
                 "| Site | Page | Window | Embed | Frame (w × h) | h ÷ w | Registry h ÷ w | |", "|---|---|---|---|---|---|---|---|"]
        for r in self.rows:
            if r["window_w"] in {x[1] for x in EXTRA_WIDTHS}:
                continue
            if not r["found"]:
                lines.append(f"| {r['site']} | {r['page']} | {r['window']} | {r['embed']} | missing | | | **FAIL** |")
                continue
            flag = "drift" if r["drift"] else ("" if r["box_h_over_w"] else "no box recorded")
            lines.append(f"| {r['site']} | {r['page']} | {r['window']} | {r['embed']} | {r['frame_w']} × {r['frame_h']} | {r['aspect_h_over_w']} | {r['box_h_over_w'] or '-'} | {flag} |")
        if self.widths:
            lines += ["", f"Sites' content column by window width ({self.widths[0]['site']}/{self.widths[0]['page']}, Important Dates):", "",
                      "| Window | Embed frame (w × h) | h ÷ w |", "|---|---|---|"]
            lines += [f"| {r['window']} | {r['frame_w']} × {r['frame_h']} | {r['aspect_h_over_w']} |" for r in self.widths]
        if self.extras:
            lines += ["", "Other content on the pages (not ours; room-parent additions are fine):", ""]
            lines += [f"- {x['site']}/{x['page']} ({x['window']}): " + ", ".join(f"{k} ×{v}" for k, v in x["hosts"].items()) for x in self.extras]
        if self.attention:
            lines += ["", "Attention (reported, not failing):", ""] + [f"- {a}" for a in self.attention]
        lines += ["", f"**Result: {'PASS' if not self.failures else 'FAIL (' + str(len(self.failures)) + ')'}**"]
        lines += [f"- {f}" for f in self.failures]
        (OUT / "report.md").write_text("\n".join(lines) + "\n")
        (OUT / "report.json").write_text(json.dumps({"versions": self.versions, "rows": self.rows, "extras": self.extras,
                                                     "attention": self.attention, "failures": self.failures}, indent=2))
        print("\n".join(lines))
        return 1 if self.failures else 0


# --- mock: a fake Google Site built from the local build, to test the checker ------------------
def serve(directory, port):
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def mock(chromium):
    """Build a fake Site: Sites' column (max 1154px, 19px side gutters), embeds in sandboxed iframes
    sized by shape, one wrapped in an intermediate iframe like Sites does, one extra foreign iframe,
    one box drifted, one wrong class, one missing. Then assert the checker says exactly that."""
    pages = "http://127.0.0.1:8701/"
    site = "http://127.0.0.1:8702/"
    real = yaml.safe_load((ROOT / "registry.yaml").read_text())
    reg = {"embeds": real["embeds"], "boxes": real["boxes"], "sites": {
        "class-2034": {"name": "mock 1st", "live": site + "class-2034", "slots": [
            {"page": "home", "embed": "important-dates", "box": "card", "status": "url"},
            {"page": "home", "embed": "room-parents", "query": {"class": 2034}, "box": {"w": 935, "h": 549}, "status": "url"},
            {"page": "email-digest", "embed": "updates", "query": {"class": 2034}, "box": {"w": 935, "h": 875}, "status": "url"}]},
        "class-2032": {"name": "mock 3rd", "live": site + "class-2032", "slots": [
            {"page": "home", "embed": "important-dates", "box": {"w": 935, "h": 625}, "status": "url"},
            {"page": "home", "embed": "room-parents", "query": {"class": 2032}, "box": {"w": 935, "h": 549}, "status": "url"}]},
        "class-2031": {"name": "mock 4th", "live": site + "class-2031", "slots": [
            {"page": "home", "embed": "updates", "query": {"class": 2031}, "status": "url"}]}}}
    sb = " ".join(sorted(SANDBOX))
    root = ROOT / "_live" / "mock"
    root.mkdir(parents=True, exist_ok=True)
    (root / "wrap.html").write_text('<!doctype html><html style="height:100%"><body style="margin:0;height:100%">'
                                    '<script>document.write(\'<iframe sandbox="' + sb + '" src="\' + decodeURIComponent(location.search.slice(5)) + '
                                    '\'" style="border:0;width:100%;height:100%;display:block"></iframe>\')</script></body></html>')

    def iframe(src, w, h, wrapped=False):
        src = site + "wrap.html?src=" + urllib.parse.quote(src, safe="") if wrapped else src
        return f'<iframe sandbox="{sb}" src="{src}" style="border:0;display:block;width:100%;height:auto;aspect-ratio:{w}/{h}"></iframe>'

    def sitepage(*body):
        return ('<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head>'
                '<body style="margin:0"><main style="max-width:1154px;box-sizing:border-box;margin:0 auto;padding:0 19px"><h1>Welcome</h1>'
                + "".join(body) + "</main></body></html>")

    (root / "extra.html").write_text("<p>a room parent's video</p>")
    for sid, page_name, body in [
        ("class-2034", "home", [iframe(pages + "shared/important-dates/", 935, 625, wrapped=True),
                                iframe(pages + "shared/room-parents/?class=2034", 935, 655),      # drifted: registry says 549
                                iframe(site + "extra.html", 560, 315)]),                          # a room parent's own embed
        ("class-2034", "email-digest", [iframe(pages + "shared/updates/?class=2034", 935, 875)]),
        ("class-2032", "home", [iframe(pages + "shared/important-dates/", 935, 625),
                                iframe(pages + "shared/room-parents/?class=2034", 935, 549),      # wrong class
                                iframe(pages + "shared/updates/?class=2032", 935, 875)]),         # not registered on this page
        ("class-2031", "home", ["<p>nothing here</p>"]),                                          # missing
    ]:
        d = root / sid
        d.mkdir(exist_ok=True)
        (d / page_name).write_text(sitepage(*body))
    # /class-2034/home must serve as HTML although it has no extension.
    http.server.SimpleHTTPRequestHandler.extensions_map[""] = "text/html"
    s1, s2 = serve(ROOT / "_site", 8701), serve(root, 8702)
    try:
        c = Checker(reg, pages, chromium, gcal_stub=True)
        c.run()
    finally:
        s1.shutdown()
        s2.shutdown()
    failed = {(r["site"], r["page"], r["embed"]) for r in c.rows if not r["found"]}
    wrong_q = {m.split(":")[0] for m in c.failures if "registered query" in m}
    problems = []
    if failed != {("class-2031", "home", "updates")}:
        problems.append(f"missing slots: {failed}")
    if wrong_q != {"class-2032/home@1440 room-parents", "class-2032/home@iphone room-parents"}:
        problems.append(f"wrong-query slots: {wrong_q}")
    other = [f for f in c.failures if "registered query" not in f and "frame found" not in f]
    if other:
        problems.append("unexpected failures: " + "; ".join(other))
    drift = {(r["site"], r["embed"]) for r in c.rows if r["drift"]}
    if drift != {("class-2034", "room-parents")}:
        problems.append(f"drift: {drift}")
    if not any("updates is on this page" in a and a.startswith("class-2032/home") for a in c.attention):
        problems.append("unregistered placement of updates on class-2032/home not reported")
    if {(x["site"], x["page"]) for x in c.extras} != {("class-2034", "home")}:
        problems.append(f"extras: {c.extras}")
    if not (c.widths and {r["window"] for r in c.widths} >= {"1024", "1280", "1440", "1920"}):
        problems.append("width table not measured on the reference page")
    print("\nMock self-test: " + ("PASS" if not problems else "FAIL\n- " + "\n- ".join(problems)))
    return 1 if problems else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", action="append", help="only this site id from registry.yaml (repeatable)")
    ap.add_argument("--mock", action="store_true", help="check the checker against a fake Site built from _site/")
    ap.add_argument("--registry", default=str(ROOT / "registry.yaml"))
    ap.add_argument("--pages", default=PAGES, help="base URL the embeds are served from")
    a = ap.parse_args()
    chromium = os.environ.get("PW_CHROMIUM")
    if a.mock:
        return mock(chromium)
    reg = yaml.safe_load(pathlib.Path(a.registry).read_text())
    return Checker(reg, a.pages, chromium).run(a.site)


if __name__ == "__main__":
    sys.exit(main())
