#!/usr/bin/env python3
"""Render-check embeds inside an iframe that copies Google Sites' sandbox.

The sandbox attribute below was read from a published Google Site on 2026-09-16.
It allows scripts/popups/downloads but NOT top-level navigation, which is exactly
what decides whether filters stay in place and links open new tabs.

Usage: python3 tests/render_check.py   (expects ./_site built)
"""
import contextlib
import datetime
import functools
import json
import http.server
import pathlib
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
SITE = ROOT / "_site"
SANDBOX = ("allow-scripts allow-popups allow-forms allow-same-origin allow-popups-to-escape-sandbox "
           "allow-downloads allow-storage-access-by-user-activation")

# (label, frame width, frame height). Desktop = the live homepage box (1154 x 1154 published).
# Phone = Sites' narrowest phone column (315px) at the recommended box shape; phone-tall = a taller box.
FRAMES = [("desktop", 1154, 1154), ("tablet", 700, 672), ("phone", 315, 210), ("phone-tall", 315, 560)]
TODAY = "2026-09-16"

# Phone: the next three dates must be fully visible on first load, below the sticky filter bar and
# above the scroll pill, on every day of the year (the upcoming set changes as dates pass).
# 315 x 210 (h / w = 0.667) is the shape the embed is designed for: an editor box of about 935 x 625,
# which publishes at 1154 x 770 and 352 x 235 on an iPhone 13. Below 400px the embed switches to one
# line per date (the compact layout); this frame is the floor that layout must keep clearing.
THREE_UP_FRAME = (315, 210)
PHONE_MAX = 400  # the compact layout's breakpoint, in the embed's CSS
UPCOMING_JS = """() => {
  const w = document.getElementById('wrap'), bar = document.getElementById('toolbar');
  const wr = w.getBoundingClientRect(), top = Math.max(wr.top, bar.getBoundingClientRect().bottom);
  const hint = document.querySelector('.sffs-hint'), lim = hint.hidden ? wr.bottom : hint.getBoundingClientRect().top;
  return [...document.querySelectorAll('tr.ev')].filter(r => !r.hidden).filter(r => {
    const b = r.getBoundingClientRect(); return b.top >= top - 1 && b.bottom <= lim + 1; }).length;
}"""


def upcoming_days():
    """First day of school, plus the day after each date ends: every distinct 'next three'."""
    events = json.loads((SITE / "shared/important-dates/data.json").read_text())["events"]
    ends = [e.get("end") or e["date"] for e in events]
    days = {events[0]["date"]} | {(datetime.date.fromisoformat(x) + datetime.timedelta(days=1)).isoformat() for x in ends}
    return sorted(d for d in days if sum(x >= d for x in ends) >= 3)


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

            # Phone usability: the compact layout must stay usable, not just fit. Wider frames keep the
            # full layout: details inline, no tap-to-open, no full-page link.
            frame.locator("#showpast").uncheck()
            page.wait_for_timeout(150)
            u = fr.evaluate("""() => {
              const box = e => e.getBoundingClientRect();
              const vis = e => box(e).height > 0 && box(e).width > 0;  // collapsed month headings don't count
              const targets = [...document.querySelectorAll('.chip, .add, .toggle')].filter(vis);
              const small = targets.filter(e => box(e).height < 24 || box(e).width < 24).map(e => e.textContent.trim().slice(0, 12) + ' ' + Math.round(box(e).width) + 'x' + Math.round(box(e).height));
              const texty = [...document.querySelectorAll('td, .chip, .add, .next-flag, .sffs-hint, .badge, .event-details, .toggle')].filter(vis);
              const tiny = texty.filter(e => parseFloat(getComputedStyle(e).fontSize) < 11).map(e => e.className + ' ' + getComputedStyle(e).fontSize);
              const full = document.getElementById('fullpage');
              const row = [...document.querySelectorAll('tr.ev')].find(r => !r.hidden && r.querySelector('.event-details'));
              return {small, tiny, fullShown: vis(full), fullHref: full.href, fullBlank: full.target === '_blank',
                      detailsShown: !!row && vis(row.querySelector('.event-details')), rowDate: row && row.dataset.date};
            }""")
            check(not u["small"], f"every tap target is at least 24px ({u['small'][:3]})")
            check(not u["tiny"], f"no text under 11px ({u['tiny'][:3]})")
            embed_url = src.split("?")[0]
            if fw <= PHONE_MAX:
                check(u["fullShown"] and u["fullHref"] == embed_url and u["fullBlank"], f"'Full page' link shows in a phone frame and opens the embed in a new tab ({u['fullHref']})")
                check(not u["detailsShown"], "compact layout: details hidden until tapped")
                row = frame.locator(f'tr.ev[data-date="{u["rowDate"]}"]')
                row.locator(".what-cell").click()
                page.wait_for_timeout(150)
                opened = fr.evaluate(f"() => {{ const r = document.querySelector('tr.ev[data-date=\"{u['rowDate']}\"]'); return r.classList.contains('open') && r.getAttribute('aria-expanded') === 'true' && r.querySelector('.event-details').getClientRects().length > 0 && r.querySelector('.badge').getClientRects().length > 0; }}")
                check(opened, f"tapping a date shows its badge and details ({u['rowDate']})")
                row.locator(".what-cell").click()
                page.wait_for_timeout(150)
                closed = fr.evaluate(f"() => {{ const r = document.querySelector('tr.ev[data-date=\"{u['rowDate']}\"]'); return !r.classList.contains('open') && r.querySelector('.event-details').getClientRects().length === 0; }}")
                check(closed, "tapping again hides them")
                check(fr.url == url0 and not popups, "tapping a date: no navigation, no new tab")
                with ctx.expect_page(timeout=5000) as newp:
                    frame.locator("#fullpage").click()
                pg = newp.value
                pg.wait_for_load_state()
                check(pg.url == embed_url, f"'Full page' opens the embed itself in a new tab ({pg.url})")
                pg.close()
                popups.clear()
            else:
                check(not u["fullShown"], "no 'Full page' link in a wide frame")
                check(u["detailsShown"], "wide frame: details shown inline")
                frame.locator(f'tr.ev[data-date="{u["rowDate"]}"] .what-cell').click()
                page.wait_for_timeout(100)
                check(not fr.evaluate("() => !!document.querySelector('tr.ev.open')"), "wide frame: clicking a date does nothing")
            frame.locator("#showpast").check()  # back to the state the next checks expect
            page.wait_for_timeout(150)

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

        fw, fh = THREE_UP_FRAME
        print(f"[phone {fw}x{fh}: three upcoming dates without scrolling, every day of the year]")
        short = []
        ctx = browser.new_context(viewport={"width": 390, "height": fh + 40})
        for day in upcoming_days():
            (harness_dir / "index.html").write_text(
                f'<!doctype html><body style="margin:0"><iframe id="f" sandbox="{SANDBOX}" '
                f'src="http://127.0.0.1:8701/shared/important-dates/?today={day}" style="border:0;width:{fw}px;height:{fh}px"></iframe></body>')
            page = ctx.new_page()
            page.goto("http://127.0.0.1:8702/index.html")
            page.wait_for_timeout(1300)  # on-load scroll to the filter bar
            fr = next(f for f in page.frames if "important-dates" in f.url)
            n = fr.evaluate(UPCOMING_JS)
            if n < 3:
                short.append(f"{day}: {n}")
            page.close()
        ctx.close()
        check(not short, f"3 upcoming dates fully visible on load ({len(upcoming_days())} days checked; short: {short[:5]})")
        browser.close()
    s1.shutdown(); s2.shutdown()
    print("\nRESULT:", "PASS" if not failures else f"FAIL ({len(failures)})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
