#!/usr/bin/env python3
"""Render-check embeds inside an iframe that copies Google Sites' sandbox.

The sandbox attribute below was read from a published Google Site on 2026-09-16.
It allows scripts/popups/downloads but NOT top-level navigation, which is exactly
what decides whether filters stay in place and links open new tabs.

Usage: python3 tests/render_check.py   (expects ./_site built)
"""
import contextlib
import functools
import http.server
import pathlib
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
SITE = ROOT / "_site"
SANDBOX = ("allow-scripts allow-popups allow-forms allow-same-origin allow-popups-to-escape-sandbox "
           "allow-downloads allow-storage-access-by-user-activation")

# (label, frame width, frame height). Desktop = measured published homepage box.
# Phone = Sites' ~315px column, height from the same aspect ratio.
FRAMES = [("desktop", 1154, 1107), ("tablet", 700, 672), ("phone", 315, 302), ("phone-tall", 315, 560)]
TODAY = "2026-09-16"


def serve(directory, port):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def main():
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
    harness_dir = ROOT / "_harness"
    harness_dir.mkdir(exist_ok=True)
    s1 = serve(SITE, 8701)       # "GitHub Pages"
    s2 = serve(harness_dir, 8702)  # "Google Sites" (different origin)
    failures = []

    def check(cond, msg):
        (print("  ok  ", msg) if cond else (failures.append(msg), print("  FAIL", msg)))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for label, fw, fh in FRAMES:
            print(f"[{label} {fw}x{fh}]")
            src = f"http://127.0.0.1:8701/shared/important-dates/?today={TODAY}"
            (harness_dir / "index.html").write_text(
                f'<!doctype html><body style="margin:0"><iframe id="f" sandbox="{SANDBOX}" '
                f'src="{src}" style="border:0;width:{fw}px;height:{fh}px"></iframe></body>')
            ctx = browser.new_context(viewport={"width": max(fw, 390), "height": fh + 40}, accept_downloads=True)
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            # CI/sandbox may have no internet: answer Google Calendar locally so the popup URL is observable
            ctx.route("https://calendar.google.com/**", lambda route: route.fulfill(status=200, content_type="text/html", body="<p>gcal stub</p>"))
            page.goto("http://127.0.0.1:8702/index.html")
            frame = page.frame_locator("#f")
            fr = next(f for f in page.frames if "important-dates" in f.url)
            fr.wait_for_load_state("load")
            page.wait_for_timeout(3300)  # let the on-load scroll retries finish
            url0 = fr.url

            m = fr.evaluate("""() => {
              const w = document.getElementById('wrap');
              return {vw: innerWidth, docSW: document.documentElement.scrollWidth, docSH: document.documentElement.scrollHeight,
                      docCH: document.documentElement.clientHeight, wrapSW: w.scrollWidth, wrapCW: w.clientWidth,
                      wrapSH: w.scrollHeight, wrapCH: w.clientHeight, scrollTop: w.scrollTop,
                      marker: document.querySelector('meta[name=sffs-embed]')?.content,
                      hashLinks: document.querySelectorAll('a[href^="#"]').length,
                      badLinks: [...document.querySelectorAll('a[href]')].filter(a => a.target !== '_blank' || !/noopener/.test(a.rel)).length,
                      visibleRows: [...document.querySelectorAll('tr.ev')].filter(r => !r.hidden).length,
                      totalRows: document.querySelectorAll('tr.ev').length,
                      pastVisible: [...document.querySelectorAll('tr.ev')].filter(r => !r.hidden && (r.dataset.dateEnd||r.dataset.date) < '2026-09-16').length,
                      overflowCells: [...document.querySelectorAll('td, .chip, .btn, .add')].filter(e => e.getBoundingClientRect().right > innerWidth + 1 && !e.closest('.row')).length }
            }""")
            check(not errors, f"no JS errors {errors[:1]}")
            check(m["marker"] and m["marker"].startswith("important-dates@"), f"version marker present ({m['marker']})")
            check(m["hashLinks"] == 0, "no href=\"#...\" links")
            check(m["badLinks"] == 0, "every link opens a new tab with rel=noopener")
            check(m["docSW"] <= m["vw"], f"no horizontal scroll on the page ({m['docSW']} <= {m['vw']})")
            check(m["wrapSW"] <= m["wrapCW"], f"no horizontal scroll inside the embed ({m['wrapSW']} <= {m['wrapCW']})")
            check(m["overflowCells"] == 0, "no cell or button pokes past the right edge")
            check(m["docSH"] <= m["docCH"], "page itself never scrolls (one scroll region)")
            check(m["pastVisible"] == 0 and m["visibleRows"] < m["totalRows"], f"past dates hidden ({m['visibleRows']}/{m['totalRows']} shown)")
            check(m["scrollTop"] > 0 or m["wrapSH"] <= m["wrapCH"] + 8, f"opens scrolled to the filter bar (scrollTop {m['scrollTop']})")

            # Category filter stays in place
            popups = []
            ctx.on("page", lambda pg: popups.append(pg))
            frame.locator('.chip.cat[data-cat="noschool"]').click()
            page.wait_for_timeout(200)
            vis = fr.evaluate("() => [...document.querySelectorAll('tr.ev')].filter(r => !r.hidden).map(r => r.dataset.cat)")
            check(vis and all(c == "noschool" for c in vis), f"'No school' filter shows only no-school rows ({len(vis)})")
            check(fr.url == url0 and not popups, "filter click: no navigation, no new tab")

            frame.locator('.chip.cat[data-cat="all"]').click()
            frame.locator("#showpast").check()
            page.wait_for_timeout(150)
            allv = fr.evaluate("() => [...document.querySelectorAll('tr.ev')].filter(r => !r.hidden).length")
            check(allv == m["totalRows"], f"'Show past dates' shows everything ({allv})")

            before = fr.evaluate("() => document.getElementById('wrap').scrollTop")
            frame.locator('.chip.jump[data-jump="m-2027-03"]').click()
            page.wait_for_timeout(900)
            after = fr.evaluate("() => document.getElementById('wrap').scrollTop")
            check(after != before, f"month jump scrolls the embed ({before} -> {after})")
            vis_mar = fr.evaluate("""() => { const t = document.getElementById('m-2027-03').getBoundingClientRect();
                                             const b = document.getElementById('toolbar').getBoundingClientRect();
                                             return t.top >= b.bottom - 1 && t.top < innerHeight; }""")
            check(vis_mar, "March heading lands just below the sticky filter bar")
            check(fr.url == url0 and not popups, "month jump: no navigation, no new tab")

            nxt = fr.evaluate("() => [...document.querySelectorAll('.next-flag')].map(f => f.closest('tr').dataset.date)")
            check(nxt == ["2026-09-17"], f"NEXT UP flag on the next upcoming date ({nxt})")

            # Calendar preference: Google (default) -> link in new tab
            n_btn = fr.evaluate("() => [...document.querySelectorAll('tr.ev')].filter(r => r.querySelectorAll('.cal-btn').length === 1).length")
            check(n_btn == m["totalRows"], f"exactly one add button per date ({n_btn})")
            with ctx.expect_page(timeout=5000) as newp:
                frame.locator("a.cal-btn").first.click()
            pg = newp.value
            pg.wait_for_load_state()
            check(pg.url.startswith("https://calendar.google.com/calendar/render?action=TEMPLATE"), f"+ Google opens Google Calendar in a new tab ({pg.url[:55]})")
            pg.close()
            check(fr.url == url0, "+ Google: embed did not navigate")

            # Outlook
            frame.locator('.chip.pref[data-pref="outlook"]').click()
            href = fr.evaluate("() => document.querySelector('.cal-btn').href")
            check(href.startswith("https://outlook.live.com/calendar/0/deeplink/compose"), "Outlook pill switches every button to Outlook links")
            check(fr.url == url0 and len(popups) <= 1, "choosing a calendar: no navigation")

            # Apple -> .ics download
            frame.locator('.chip.pref[data-pref="apple"]').click()
            with page.expect_download(timeout=5000) as dl:
                frame.locator("button.cal-btn").first.click()
            txt = pathlib.Path(dl.value.path()).read_text()
            check(txt.startswith("BEGIN:VCALENDAR") and txt.count("BEGIN:VEVENT") == 1 and "UID:2026-08-26-first-day-of-school@sffs-calendar" in txt,
                  f"+ Apple downloads a one-event .ics with the live embed's UID ({dl.value.suggested_filename})")
            with page.expect_download(timeout=5000) as dl:
                frame.locator("#addall").click()
            txt = pathlib.Path(dl.value.path()).read_text()
            check(txt.count("BEGIN:VEVENT") == m["totalRows"], f"Add all downloads every date ({txt.count('BEGIN:VEVENT')})")

            # Remembered after reload
            fr.evaluate("() => location.reload()")
            page.wait_for_timeout(1500)
            fr = next(f for f in page.frames if "important-dates" in f.url)
            remembered = fr.evaluate("() => document.querySelector('.chip.pref.on')?.dataset.pref")
            check(remembered == "apple", f"calendar choice remembered after reload ({remembered})")

            page.screenshot(path=str(ROOT / "_harness" / f"shot-{label}.png"))
            ctx.close()
        browser.close()
    s1.shutdown(); s2.shutdown()
    print("\nRESULT:", "PASS" if not failures else f"FAIL ({len(failures)})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
