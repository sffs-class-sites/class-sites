#!/usr/bin/env python3
"""Checks for the Key School Systems embed (shared/key-systems/, built by build/build_key_systems.py).

1. The data file: schema, every system has a name, description and https link, no duplicates,
   no personal data.
2. The embed, inside an iframe with Sites' sandbox, at the `page` box it is placed at (alone on
   its own Site page: 1154 x 1080 on a desktop, 352 x 329 on an iPhone 13), and, like every
   shared embed, at the `card` box (1154 x 770, 352 x 235, 315 x 210) and a tablet: the title
   is at the top; every system is listed in the data's order with its link opening a new tab;
   the first system is fully visible on a phone without scrolling and the whole list fits a
   desktop frame; tap targets are at least 44px tall; no horizontal scroll.
3. The translation notice (tests/lang_check.py).

Usage: python3 tests/key_systems_check.py   (expects _site built)
"""
import functools
import http.server
import json
import pathlib
import re
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
SITE = ROOT / "_site"
sys.path.insert(0, str(ROOT / "tests"))
from render_check import SANDBOX  # noqa: E402

# registry.yaml `boxes`: `page` is where it is placed (desktop and iPhone 13); `card` is every shared embed's floor
FRAMES = [("desktop-page", 1154, 1080), ("desktop-card", 1154, 770), ("tablet", 700, 672),
          ("phone-page", 352, 329), ("phone-card", 352, 235), ("phone-narrow", 315, 210)]
failures = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    cond or failures.append(msg)


def serve(directory, port):
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def data_checks():
    print("[data]")
    d = json.loads((ROOT / "shared/key-systems/data.json").read_text())
    check(d.get("schema") == 1 and d.get("title") and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.get("updated", "")), "schema 1 with a title and an updated date")
    s = d["systems"]
    check(len(s) > 0, f"{len(s)} systems")
    check(all(x.get("name") and x.get("description") and x.get("url", "").startswith("https://") for x in s),
          "every system has a name, a description and an https link")
    check(len({x["name"].lower() for x in s}) == len(s), "no system listed twice")
    check(not [x for x in s for k in ("name", "description") if re.search(r":\s+[a-z]", x[k])],
          "house style: after a colon the next word starts with a capital letter")
    body = json.dumps({k: v for k, v in d.items() if k != "_note"})
    check(not re.search(r"[\w.+-]+@[\w-]+\.\w|\b\d{3}-\d{4}\b", body), "no email address or phone number in the data (public file)")
    return d


STATE = """() => {
  const q = s => document.querySelector(s), wrap = q('#wrap'), hint = q('#hint'), title = q('#title');
  const links = [...document.querySelectorAll('#list a.sys')];
  const box = e => { const r = e.getBoundingClientRect(); return {top: r.top, bottom: r.bottom, h: r.height}; };
  const limit = hint.hidden ? innerHeight : hint.getBoundingClientRect().top;
  return {title: title.textContent, title_box: box(title), sub: q('#sub').textContent, foot: q('#foot').textContent,
          names: links.map(a => a.querySelector('.name').textContent),
          links: links.map(a => ({href: a.href, target: a.target, rel: a.rel, h: a.getBoundingClientRect().height})),
          first: links.length ? box(links[0]) : null, last: links.length ? box(links[links.length - 1]) : null,
          limit, inner_h: innerHeight, hint_hidden: hint.hidden,
          hash_links: document.querySelectorAll('a[href^="#"]').length,
          hscroll: document.documentElement.scrollWidth > innerWidth + 1 || wrap.scrollWidth > wrap.clientWidth + 1};
}"""


def embed_checks(p, d):
    print("[embed]")
    harness = ROOT / "_harness"
    harness.mkdir(exist_ok=True)
    servers = [serve(SITE, 8731), serve(harness, 8732)]
    want_names = [x["name"] for x in d["systems"]]
    want_urls = [x["url"] for x in d["systems"]]
    b = p.chromium.launch()
    for label, fw, fh in FRAMES:
        (harness / "ks-host.html").write_text(
            f'<!doctype html><body style="margin:0"><iframe id="f" sandbox="{SANDBOX}" '
            f'src="http://127.0.0.1:8731/shared/key-systems/" style="border:0;width:{fw}px;height:{fh}px"></iframe></body>')
        ctx = b.new_context(viewport={"width": max(fw, 390), "height": fh + 40})
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto("http://127.0.0.1:8732/ks-host.html")
        page.frame_locator("#f").locator("#list a.sys").first.wait_for(timeout=8000)
        frame = next(f for f in page.frames if "/shared/key-systems/" in f.url)
        page.wait_for_timeout(700)
        tag = label
        st = frame.evaluate(STATE)
        check(not errors, f"{tag}: no script errors {errors or ''}")
        check(st["title"] == d["title"] and 0 <= st["title_box"]["top"] < 40, f"{tag}: title {d['title']!r} at the top of the frame")
        check(st["names"] == want_names, f"{tag}: all {len(want_names)} systems listed in the data's order")
        check([l["href"] for l in st["links"]] == want_urls, f"{tag}: each system links to its url")
        check(all(l["target"] == "_blank" and "noopener" in l["rel"] for l in st["links"]),
              f"{tag}: every link opens a new tab (target=_blank rel=noopener), never navigates the frame")
        check(min(l["h"] for l in st["links"]) >= 44, f"{tag}: every link at least 44px tall ({min(l['h'] for l in st['links']):.0f})")
        check(st["first"]["top"] >= 0 and st["first"]["bottom"] <= st["limit"] + 1,
              f"{tag}: the first system is fully visible without scrolling (bottom {st['first']['bottom']:.0f}, limit {st['limit']:.0f})")
        check(not st["hscroll"], f"{tag}: no horizontal scroll")
        check(st["hash_links"] == 0, f"{tag}: no href=\"#…\" links (they open new windows on iOS Chrome)")
        check("new tab" in st["foot"] and str(int(d["updated"][-2:])) in st["foot"], f"{tag}: footer says links open a new tab and when the list was updated")
        if label.startswith("desktop"):
            check(st["last"]["bottom"] <= st["inner_h"] + 1 and st["hint_hidden"],
                  f"{tag}: the whole list fits without scrolling (last bottom {st['last']['bottom']:.0f} of {st['inner_h']})")
        if label.startswith("phone"):
            check(not st["hint_hidden"], f"{tag}: scroll hint shown for the rest of the list")
        if label in ("desktop-page", "phone-page"):
            page.screenshot(path=str(harness / f"key-systems-{label}.png"))
        ctx.close()
    print("[translation notice]")
    from lang_check import check_lang
    check_lang(b, "http://127.0.0.1:8731/shared/key-systems/", check)
    b.close()
    for s in servers:
        s.shutdown()


def main():
    d = data_checks()
    built = SITE / "shared/key-systems/index.html"
    check(built.exists() and 'name="sffs-embed" content="key-systems@' in built.read_text(), "built page carries the sffs-embed version marker")
    with sync_playwright() as p:
        embed_checks(p, d)
    print("\nRESULT:", "PASS" if not failures else f"FAIL ({len(failures)})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
