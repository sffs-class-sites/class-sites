#!/usr/bin/env python3
"""Checks for the School Hours embed (shared/school-hours/, built by build/build_school_hours.py).

1. The data file: schema, every grade K-8 covered by exactly one row, handbook citation, times
   in the handbook's own form.
2. The embed, inside an iframe with Sites' sandbox, at the standard `card` box on a desktop
   (1154 x 770), a tablet, an iPhone 13 (352 x 235) and the narrowest phones (315 x 210):
   the viewer's grade row is highlighted and flagged "THIS CLASS" for ?class= (and ?grade=
   preview), the lead card with that class's hours is fully visible on a phone without
   scrolling, no horizontal scroll anywhere, the whole table fits a desktop frame, the handbook
   link opens a new tab, and without ?class= nothing is highlighted.
3. The translation notice (tests/lang_check.py).

Usage: python3 tests/school_hours_check.py   (expects _site built)
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

TODAY = "2026-10-12"   # inside 2026-27, so ?class= resolves as the data file's school year expects
# phone = the standard `card` box on an iPhone 13; phone-narrow = the same box on the narrowest phones (registry.yaml `boxes`)
sys.path.insert(0, str(ROOT / "build"))
from build_school_hours import dropoff_links  # noqa: E402

DROPOFF = dropoff_links()
FRAMES = [("desktop", 1154, 770), ("tablet", 700, 672), ("phone", 352, 235), ("phone-narrow", 315, 210)]
TIME = re.compile(r"^\d{1,2}:\d{2} [ap]\.m\.$")
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
    d = json.loads((ROOT / "shared/school-hours/data.json").read_text())
    check(d.get("schema") == 1, "schema 1")
    covered = [g for r in d["rows"] for g in r["grades"]]
    check(sorted(covered) == list(range(9)), f"every grade K-8 in exactly one row ({sorted(covered)})")
    check(all(TIME.match(r[k][e]) for r in d["rows"] for k in ("regular", "wednesday") for e in ("start", "end")),
          "every time reads like the handbook's (e.g. 8:30 a.m.)")
    check(all(r["label"] for r in d["rows"]) and d["building"] and d["notes"], "labels, building hours and notes present")
    s = d["source"]
    check(all(s.get(k) for k in ("title", "section", "page", "updated", "updated_iso", "url")) and "Handbook" in s["title"],
          "source cites the Family Handbook: title, section, page, revision, link")
    check(not re.search(r"@|\b\d{3}-\d{4}\b", json.dumps(d)), "no email address or phone number in the data (non-personal file)")
    return d


def embed_checks(p, d):
    print("[embed]")
    harness = ROOT / "_harness"
    harness.mkdir(exist_ok=True)
    servers = [serve(SITE, 8721), serve(harness, 8722)]
    row_for = {g: r["label"] for r in d["rows"] for g in r["grades"]}
    # (name, query, expected highlighted row label or None, expected lead heading start)
    cases = [("1st grade", f"?class=2034&today={TODAY}", row_for[1], "1st grade"),
             ("3rd grade", f"?class=2032&today={TODAY}", row_for[3], "3rd grade"),
             ("kindergarten", f"?class=2035&today={TODAY}", row_for[0], "Kindergarten"),
             ("8th grade", f"?class=2027&today={TODAY}", row_for[8], "8th grade"),
             ("grade preview", f"?class=2034&grade=4&today={TODAY}", row_for[4], "4th grade (preview)"),
             ("future class", f"?class=2040&today={TODAY}", None, None),
             ("no class", f"?today={TODAY}", None, None)]
    b = p.chromium.launch()
    for label, fw, fh in FRAMES:
        for name, query, want_row, want_lead in cases:
            (harness / "sh-host.html").write_text(
                f'<!doctype html><body style="margin:0"><iframe id="f" sandbox="{SANDBOX}" '
                f'src="http://127.0.0.1:8721/shared/school-hours/{query}" style="border:0;width:{fw}px;height:{fh}px"></iframe></body>')
            ctx = b.new_context(viewport={"width": max(fw, 390), "height": fh + 40})
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto("http://127.0.0.1:8722/sh-host.html")
            fr = page.frame_locator("#f")
            fr.locator("#rows tr").first.wait_for(timeout=8000)
            frame = next(f for f in page.frames if "/shared/school-hours/" in f.url)
            page.wait_for_timeout(250)
            tag = f"{label} / {name}"
            check(not errors, f"{tag}: no script errors {errors or ''}")
            st = frame.evaluate("""() => {
              const q = s => document.querySelector(s), rows = [...document.querySelectorAll('#rows tr')];
              const hl = rows.filter(r => r.classList.contains('is-highlight'));
              const wrap = q('#wrap'), lead = q('#lead'), hint = q('#hint'), last = rows[rows.length - 1];
              const limit = hint.hidden ? innerHeight : hint.getBoundingClientRect().top;
              const box = e => { const r = e.getBoundingClientRect(); return {top: r.top, bottom: r.bottom}; };
              return {rows: rows.length, hl: hl.map(r => r.querySelector('.grade-cell').firstChild.textContent),
                      flags: hl.map(r => r.querySelector('.flag') && r.querySelector('.flag').textContent),
                      lead_hidden: lead.hidden, lead_text: lead.textContent, lead_box: box(lead), limit, inner_h: innerHeight,
                      last_bottom: box(last).bottom, hint_hidden: hint.hidden,
                      hscroll: document.documentElement.scrollWidth > innerWidth + 1 || wrap.scrollWidth > wrap.clientWidth + 1,
                      sub: q('#sub').textContent, foot: q('#foot').textContent,
                      link: (a => a && {href: a.href, target: a.target, rel: a.rel})(q('a.src'))};
            }""")
            check(st["rows"] == len(d["rows"]), f"{tag}: all {len(d['rows'])} grade rows rendered")
            check(not st["hscroll"], f"{tag}: no horizontal scroll")
            cls = re.search(r"class=(\d{4})", query)
            want_dp = DROPOFF.get(cls.group(1)) if cls else None
            dp = frame.evaluate("() => { const p = document.querySelector('#dropoff'), a = document.querySelector('#dropoff-link'); return p.hidden ? null : {href: a.getAttribute('href'), target: a.target, rel: a.rel, h: a.getBoundingClientRect().height, below: a.getBoundingClientRect().top >= document.querySelector('table').getBoundingClientRect().bottom}; }")
            if want_dp:
                check(dp and dp["href"] == want_dp and dp["target"] == "_blank" and "noopener" in dp["rel"] and dp["below"] and dp["h"] >= 32,
                      f"{tag}: under the table, a link to this class's Drop-off & Pickup page ({want_dp}) that opens a new tab")
            else:
                check(dp is None, f"{tag}: no Drop-off & Pickup link (this class's Site has no such page in registry.yaml)")
            if want_row:
                check(st["hl"] == [want_row] and st["flags"] == ["THIS CLASS"], f"{tag}: row {want_row!r} highlighted and flagged THIS CLASS ({st['hl']})")
                check(not st["lead_hidden"] and st["lead_text"].startswith(want_lead), f"{tag}: lead card names the viewer's grade ({st['lead_text'][:40]!r})")
                check(st["lead_box"]["top"] >= 0 and st["lead_box"]["bottom"] <= st["limit"] + 1,
                      f"{tag}: the viewer's hours are fully visible without scrolling (lead bottom {st['lead_box']['bottom']:.0f}, limit {st['limit']:.0f})")
                reg = [r for r in d["rows"] if r["label"] == want_row][0]
                check(reg["regular"]["end"] in st["lead_text"] and reg["wednesday"]["end"] in st["lead_text"], f"{tag}: lead shows the regular and Wednesday times")
            else:
                check(st["hl"] == [] and st["lead_hidden"], f"{tag}: nothing highlighted and no lead card")
            if label == "desktop":
                check(st["last_bottom"] <= st["inner_h"] + 1, f"{tag}: the whole table fits the desktop card without scrolling")
            if label.startswith("phone") and want_row:
                check(not st["hint_hidden"], f"{tag}: scroll hint shown for the rest of the page")
            check(st["link"] and st["link"]["href"] == d["source"]["url"] and st["link"]["target"] == "_blank" and "noopener" in st["link"]["rel"],
                  f"{tag}: handbook link opens in a new tab, never navigates the frame")
            check(d["source"]["title"] in st["foot"] and d["source"]["section"] in st["foot"] and f"p. {d['source']['page']}" in st["foot"] and d["source"]["updated"] in st["foot"],
                  f"{tag}: cites the handbook section, page and revision")
            if want_row:
                check(st["sub"].startswith(want_lead.replace(" (preview)", "")) and ("(preview)" in st["sub"]) == ("preview" in name), f"{tag}: subtitle is the class line ({st['sub']!r})")
            else:
                check(st["sub"].startswith(("From the", "Class of")), f"{tag}: subtitle without a grade row ({st['sub']!r})")
            if name == "1st grade":
                page.screenshot(path=str(harness / f"school-hours-{label}.png"))
            ctx.close()
    print("[translation notice]")
    from lang_check import check_lang
    check_lang(b, f"http://127.0.0.1:8721/shared/school-hours/?class=2034&today={TODAY}", check)
    b.close()
    for s in servers:
        s.shutdown()


def main():
    d = data_checks()
    built = SITE / "shared/school-hours/index.html"
    check(built.exists() and 'name="sffs-embed" content="school-hours@' in built.read_text(), "built page carries the sffs-embed version marker")
    with sync_playwright() as p:
        embed_checks(p, d)
    print("\nRESULT:", "PASS" if not failures else f"FAIL ({len(failures)})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
