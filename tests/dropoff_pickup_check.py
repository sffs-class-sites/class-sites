#!/usr/bin/env python3
"""Checks for the Drop-off & Pickup embed (shared/dropoff-pickup/, built by build/build_dropoff_pickup.py).

1. The data file: both modes have three steps (the map has pins 1 to 3), no email or phone number.
2. The embed, inside an iframe with Sites' sandbox, at the `page` box it is placed at (1154 x 1080,
   352 x 329 on an iPhone 13), at `card` (352 x 235, 315 x 210) and a tablet, in both modes:
   title at the top; the toggle shows the right mode and switches; the right route is drawn and the
   other hidden; three steps; the map (pin 3, the loading island) is in the first view on a phone at
   `page`; no circle-the-block loop, button or route text anywhere; times come from
   shared/school-hours/data.json with ?class= flagged; buttons at least 44px; no horizontal scroll;
   outbound links open a new tab.
3. The time-of-day default (morning before 11 a.m. Pacific) and the translation notice.

Usage: python3 tests/dropoff_pickup_check.py   (expects _site built)
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

BASE = "http://127.0.0.1:8741/shared/dropoff-pickup/"
FRAMES = [("desktop-page", 1154, 1080), ("tablet", 700, 672), ("phone-page", 352, 329), ("phone-card", 352, 235), ("phone-narrow", 315, 210)]
LINK = re.compile(r"\[([^\]]+)\]\(https://[^)\s]+\)")
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
    d = json.loads((ROOT / "shared/dropoff-pickup/data.json").read_text())
    check(d.get("schema") == 1 and d.get("title") and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.get("updated", "")), "schema 1 with a title and an updated date")
    check(len(d["modes"]["morning"]["steps"]) == 3 and len(d["modes"]["afternoon"]["steps"]) == 2, "3 morning steps and 2 afternoon steps (the map's pins)")
    body = json.dumps({k: v for k, v in d.items() if k != "_note"})
    check(not re.search(r"[\w.+-]+@[\w-]+\.\w|\b\d{3}-\d{4}\b", body), "no email address or phone number in the data (public file)")
    return d


STATE = """() => {
  const q = s => document.querySelector(s), vis = e => !!e && !e.closest('[hidden]') && e.getBoundingClientRect().height > 0;
  const box = e => { const r = e.getBoundingClientRect(); return {top: r.top, bottom: r.bottom, h: r.height}; };
  const mode = ['morning', 'afternoon'].find(k => q('#tab-' + k).getAttribute('aria-pressed') === 'true');
  return {title: q('#title').textContent, title_top: box(q('#title')).top, mode,
          routes: {morning: vis(q('#m-morning .route')), afternoon: vis(q('#m-afternoon .route'))},
          viewbox: q('#map').getAttribute('viewBox'), map: box(q('#map')), pin3: box(q('#m-' + mode + ' .pin:last-of-type')),
          headline: q('#headline').textContent, steps: [...document.querySelectorAll('#steps .st')].map(e => e.textContent),
          donts: [...document.querySelectorAll('#donts li')].map(l => [l.className === 'ok', l.querySelector('button') ? l.querySelector('button').childNodes[0].textContent : l.textContent]),
          pins: [...document.querySelectorAll('#m-' + mode + ' .pin text')].map(t => t.textContent), cars: document.querySelectorAll('#m-' + mode + ' .car').length,
          legend: [...document.querySelectorAll('#legend li')].map(l => l.textContent), has_dont_heading: /please don/i.test(q('.donts').textContent),
          bullets: [...document.querySelectorAll('.card')].filter(c => c.querySelector('ul')).map(c => c.querySelector('h3').textContent), loop_bits: document.querySelectorAll('#m-loop, .loop, #loopbtn, .looplink, #looptext').length,
          buttons: [...document.querySelectorAll('button')].map(b => b.getBoundingClientRect().height),
          rows: [...document.querySelectorAll('#cards table tbody tr')].map(r => [...r.cells].map(c => c.childNodes[0].textContent)),
          mine: [...document.querySelectorAll('#cards tr.mine td')].map(c => c.childNodes[0].textContent),
          cards: [...document.querySelectorAll('#cards .card h3, #always .card h3')].map(e => e.textContent),
          text: q('#wrap').textContent, full_hidden: q('#fullpage').hidden, inner_h: innerHeight,
          links: [...document.querySelectorAll('a[href]')].map(a => ({href: a.getAttribute('href'), target: a.target, rel: a.rel})),
          hash_links: document.querySelectorAll('a[href^="#"]').length,
          hscroll: document.documentElement.scrollWidth > innerWidth + 1 || q('#wrap').scrollWidth > q('#wrap').clientWidth + 1};
}"""


def embed_checks(p, d):
    print("[embed]")
    harness = ROOT / "_harness"
    harness.mkdir(exist_ok=True)
    servers = [serve(SITE, 8741), serve(harness, 8742)]
    hours = json.loads((ROOT / "shared/school-hours/data.json").read_text())["rows"]
    b = p.chromium.launch()
    for label, fw, fh in FRAMES:
        for mode in ("morning", "afternoon"):
            (harness / "dp-host.html").write_text(
                f'<!doctype html><body style="margin:0"><iframe id="f" sandbox="{SANDBOX}" '
                f'src="{BASE}?view={mode}&class=2034&today=2026-11-12" style="border:0;width:{fw}px;height:{fh}px"></iframe></body>')
            ctx = b.new_context(viewport={"width": max(fw, 390), "height": fh + 40})
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto("http://127.0.0.1:8742/dp-host.html")
            fl = page.frame_locator("#f")
            fl.locator("#steps li").first.wait_for(timeout=8000)
            frame = next(f for f in page.frames if "/shared/dropoff-pickup/" in f.url)
            page.wait_for_timeout(700)
            tag = f"{label} {mode}"
            m = d["modes"][mode]
            st = frame.evaluate(STATE)
            check(not errors, f"{tag}: no script errors {errors or ''}")
            check(st["title"] == d["title"] and 0 <= st["title_top"] < 40, f"{tag}: title at the top of the frame")
            check(st["mode"] == mode and st["routes"] == {"morning": mode == "morning", "afternoon": mode == "afternoon"} and st["viewbox"] == "0 0 360 250" and st["loop_bits"] == 0 and "15th" not in st["text"] and "on map" not in st["text"],
                  f"{tag}: toggle shows {mode}, only that route is drawn; no loop, loop button or loop text")
            check(st["headline"] == m["headline"] and st["steps"] == [s["t"] for s in m["steps"]], f"{tag}: headline and the {len(m['steps'])} steps from the data")
            check(st["donts"] == [[isinstance(x, dict) and bool(x.get("ok")), x["t"] if isinstance(x, dict) else x] for x in m["donts"]] and not st["has_dont_heading"],
                  f"{tag}: the rules box lists the data's lines with an X or a check, and has no heading")
            check(st["pins"] == [str(i + 1) for i in range(len(m["steps"]))], f"{tag}: one numbered pin per step ({st['pins']})")
            check(st["cars"] == (2 if mode == "morning" else 1), f"{tag}: {'two cars (down Valencia, and from Duboce)' if mode == 'morning' else 'one car'} on the route")
            check(st["legend"][0] == "SFFS Route", f"{tag}: legend calls the route 'SFFS Route'")
            check(st["bullets"] == [c["h"] for c in m["cards"] + d["always"] if c.get("bullets")], f"{tag}: bulleted cards are the ones the data marks ({len(st['bullets'])})")
            want = [[r["label"], r["regular"]["start"]] if mode == "morning" else [r["label"], r["regular"]["end"], r["wednesday"]["end"]] for r in hours]
            check(st["rows"] == want, f"{tag}: times by grade match shared/school-hours/data.json")
            check(st["mine"][:1] == ["1st Grade"], f"{tag}: ?class=2034 flags the 1st grade row")
            check(st["cards"] == [m["times_h"]] + [c["h"] for c in m["cards"]] + [c["h"] for c in d["always"]], f"{tag}: every card from the data, in order")
            check(all(LINK.sub(r"\1", t) in st["text"] for c in m["cards"] + d["always"] for t in c["p"]), f"{tag}: every line of every card is on the page")
            check(sum(1 for l in st["links"] if l["href"] == d["form_url"]) == (2 if mode == "afternoon" else 0), f"{tag}: the dismissal form is linked from its two cards (afternoon only)")
            check(min(st["buttons"]) >= 44, f"{tag}: every button at least 44px tall ({min(st['buttons']):.0f})")
            check(not st["hscroll"], f"{tag}: no horizontal scroll")
            check(not st["full_hidden"], f"{tag}: Full page link offered inside a frame")
            check(st["hash_links"] == 0 and all(l["target"] == "_blank" and "noopener" in l["rel"] for l in st["links"]),
                  f"{tag}: every link opens a new tab, none is href=\"#…\"")
            if label in ("phone-page", "desktop-page"):
                check(st["pin3"]["bottom"] <= st["inner_h"], f"{tag}: the loading island (pin 3) is in the first view (bottom {st['pin3']['bottom']:.0f} of {st['inner_h']})")
            else:
                check(st["map"]["top"] < st["inner_h"] - 40, f"{tag}: the map starts in the first view")
            if label in ("desktop-page", "phone-page"):
                page.screenshot(path=str(harness / f"dropoff-pickup-{label}-{mode}.png"))
            # the other mode
            other = "afternoon" if mode == "morning" else "morning"
            fl.locator(f"#tab-{other}").click()
            s3 = frame.evaluate(STATE)
            check(s3["mode"] == other and s3["routes"][other] and not s3["routes"][mode]
                  and s3["headline"] == d["modes"][other]["headline"], f"{tag}: the toggle switches to {other} in place")
            ctx.close()
    print("[time of day]")
    for iso, want in (("2026-11-12T15:30:00Z", "morning"), ("2026-11-12T22:30:00Z", "afternoon")):   # 7:30 a.m. and 2:30 p.m. Pacific
        ctx = b.new_context(viewport={"width": 800, "height": 700})
        page = ctx.new_page()
        page.clock.set_fixed_time(iso)
        page.goto(BASE)
        page.locator("#steps li").first.wait_for(timeout=8000)
        st = page.evaluate(STATE)
        check(st["mode"] == want and st["full_hidden"], f"{iso}: opens on {want}; no Full page link outside a frame")
        ctx.close()
    print("[translation notice]")
    from lang_check import check_lang
    check_lang(b, BASE, check)
    b.close()
    for s in servers:
        s.shutdown()


def main():
    d = data_checks()
    built = SITE / "shared/dropoff-pickup/index.html"
    check(built.exists() and 'name="sffs-embed" content="dropoff-pickup@' in built.read_text(), "built page carries the sffs-embed version marker")
    with sync_playwright() as p:
        embed_checks(p, d)
    print("\nRESULT:", "PASS" if not failures else f"FAIL ({len(failures)})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
