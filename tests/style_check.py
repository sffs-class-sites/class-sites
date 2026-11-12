#!/usr/bin/env python3
"""House style on the rendered embeds (build/style.py): after a colon, the next word starts with a capital letter.

The data checks hold each embed's data file to the rule; this check opens every built embed in Chromium
and reads all of its text nodes (hidden tabs and panels included, scripts and styles left out), so wording
in the page templates and text the page writes at view time is held to it too. Email subjects quoted in
the Updates embed are exempt, as in the data check: they are the emails' own words.

Usage: python3 tests/style_check.py   (expects _site built)
"""
import functools
import http.server
import json
import pathlib
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
SITE = ROOT / "_site"
sys.path.insert(0, str(ROOT / "build"))
from style import colon_issues  # noqa: E402

TODAY = "2026-10-12"
SUBJECTS = {s["subject"] for s in json.loads((ROOT / "shared/updates/data.json").read_text())["sources"]}
EMBEDS = [
    "shared/important-dates/",
    f"shared/important-dates/?class=2034&today={TODAY}",
    f"shared/updates/?class=2034&today={TODAY}",
    f"shared/school-hours/?class=2034&today={TODAY}",
    "shared/team-schedule/?team=hoops-2034-2027-winter&today=2026-12-01",
    "shared/key-systems/",
    f"shared/room-parents/?class=2034&today={TODAY}",
]
TEXT_JS = """() => {
  const out = [], w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {acceptNode: n =>
    n.parentElement.closest('script, style, noscript') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT});
  let n; while ((n = w.nextNode())) { const t = n.textContent.replace(/\\s+/g, ' ').trim(); if (t) out.push(t); }
  // Text split across elements ("Note:" in <b>, the rest after it) is read joined per block as well.
  for (const el of document.querySelectorAll('p, li, h1, h2, h3, h4, dt, dd, td, th, button, a, label, summary, figcaption, div'))
    if (![...el.children].some(c => /^(P|LI|DIV|UL|OL|TABLE|SECTION)$/.test(c.tagName))) {
      const t = (el.textContent || '').replace(/\\s+/g, ' ').trim(); if (t) out.push(t); }
  for (const el of document.querySelectorAll('[title], [aria-label], [placeholder]'))
    for (const a of ['title', 'aria-label', 'placeholder']) if (el.getAttribute(a)) out.push(el.getAttribute(a));
  return [...new Set(out)];
}"""


def serve(directory, port):
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    srv = serve(SITE, 8741)
    failures = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for path in EMBEDS:
            page = b.new_page(viewport={"width": 1154, "height": 1080})
            page.goto(f"http://127.0.0.1:8741/{path}")
            page.wait_for_timeout(800)
            texts = page.evaluate(TEXT_JS)
            bad = [s for t in texts if not any(subj in t for subj in SUBJECTS if ":" in subj) for s in colon_issues(t)]
            bad = sorted(set(bad))
            print(("  ok   " if not bad else "  FAIL ") + f"{path}: {len(texts)} text pieces, capital after every colon"
                  + "".join(f"\n         {s}" for s in bad[:12]))
            failures += [f"{path}: {s}" for s in bad]
            page.close()
        b.close()
    srv.shutdown()
    print("\nRESULT:", "PASS" if not failures else f"FAIL ({len(failures)})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
