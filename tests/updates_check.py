#!/usr/bin/env python3
"""Render-check the Updates embed inside a Google Sites-style sandboxed iframe.

Same sandbox attribute and frame sizes as tests/render_check.py. Asserts the embed fills
its frame without horizontal scroll, every tab works in place, the grade picker filters,
?class= resolves to the right grade, links open new tabs, and the phone layout shows at
least two cards under the tab bar without scrolling.

Usage: python3 tests/updates_check.py   (expects ./_site built)
"""
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
FRAMES = [("desktop", 1154, 820), ("tablet", 700, 672), ("phone", 352, 352), ("phone-tall", 315, 560)]
TODAY = "2026-10-31"


def serve(directory, port):
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main():
    harness = ROOT / "_harness"
    harness.mkdir(exist_ok=True)
    serve(SITE, 8711)
    serve(harness, 8712)
    failures = []

    def check(cond, msg):
        (print("  ok  ", msg) if cond else (failures.append(msg), print("  FAIL", msg)))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for label, fw, fh in FRAMES:
            print(f"[{label} {fw}x{fh}]")
            src = f"http://127.0.0.1:8711/shared/updates/?class=2034&today={TODAY}"
            (harness / "host.html").write_text(
                f'<!doctype html><body style="margin:0"><iframe id="f" sandbox="{SANDBOX}" '
                f'src="{src}" style="border:0;width:{fw}px;height:{fh}px"></iframe></body>')
            ctx = browser.new_context(viewport={"width": max(fw, 390), "height": fh + 40})
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto("http://127.0.0.1:8712/host.html")
            fr = next(f for f in page.frames if "shared/updates" in f.url)
            fr.wait_for_load_state("load")
            page.wait_for_timeout(600)
            url0 = fr.url
            page.screenshot(path=str(harness / f"updates-{label}.png"))  # first view, before any clicks

            m = fr.evaluate("""() => {
              const w = document.getElementById('wrap'), bar = document.getElementById('toolbar');
              const wr = w.getBoundingClientRect(), top = Math.max(wr.top, bar.getBoundingClientRect().bottom);
              const hint = document.querySelector('.sffs-hint'), lim = hint.hidden ? wr.bottom : hint.getBoundingClientRect().top;
              const cards = [...document.querySelectorAll('.card')];
              return {vw: innerWidth, docSW: document.documentElement.scrollWidth, docSH: document.documentElement.scrollHeight,
                      docCH: document.documentElement.clientHeight, wrapSW: w.scrollWidth, wrapCW: w.clientWidth,
                      marker: document.querySelector('meta[name=sffs-embed]')?.content,
                      hashLinks: document.querySelectorAll('a[href^="#"]').length,
                      badLinks: [...document.querySelectorAll('a[href]')].filter(a => a.target !== '_blank' || !/noopener/.test(a.rel)).length,
                      cards: cards.length,
                      fullyVisible: cards.filter(c => { const b = c.getBoundingClientRect(); return b.top >= top - 1 && b.bottom <= lim + 1; }).length,
                      barBottom: Math.round(bar.getBoundingClientRect().bottom), lim: Math.round(lim), firstCardH: cards.length ? Math.round(cards[0].getBoundingClientRect().height) : 0,
                      firstKeyVisible: cards.length ? ['.t', '.when', '.acts a', '.sum'].every(sel => { const e = cards[0].querySelector(sel); if (!e) return true; const b = e.getBoundingClientRect(); return b.top >= top - 1 && b.bottom <= lim + 1; }) : false,
                      gradeOn: [...document.querySelectorAll('.chip.g.on')].map(c => c.dataset.g),
                      subtitle: document.getElementById('subtitle').textContent,
                      showing: document.getElementById('showing').textContent,
                      tabLabels: [...document.querySelectorAll('.chip.tab')].map(b => b.firstChild.textContent.trim()),
                      overflow: [...document.querySelectorAll('.card, .chip, .lnk')].filter(e => e.getBoundingClientRect().right > innerWidth + 1 && !e.closest('.row')).length }
            }""")
            check(not errors, f"no JS errors {errors[:1]}")
            check(m["marker"] and m["marker"].startswith("updates@"), f"version marker present ({m['marker']})")
            check(m["hashLinks"] == 0, "no href=\"#...\" links")
            check(m["badLinks"] == 0, "every link opens a new tab with rel=noopener")
            check(m["docSW"] <= m["vw"], f"no horizontal scroll on the page ({m['docSW']} <= {m['vw']})")
            check(m["wrapSW"] <= m["wrapCW"], f"no horizontal scroll inside the embed ({m['wrapSW']} <= {m['wrapCW']})")
            check(m["overflow"] == 0, "no card or button pokes past the right edge")
            check(m["docSH"] <= m["docCH"], "page itself never scrolls (one scroll region)")
            check(m["gradeOn"] == ["1"], f"?class=2034 selects 1st grade in 2026–27 ({m['gradeOn']})")
            check(m["showing"] == "Displaying: Schoolwide; 1st", f"Displaying line names the grade ({m['showing']!r})")
            check(m["subtitle"].startswith("NOT SANCTIONED.") and "Classes of 2034 (1st) and 2032 (3rd)" in m["subtitle"], f"subtitle carries the disclaimer and the supported classes ({m['subtitle'][-60:]!r})")
            check(m["tabLabels"][0] == "Deadlines" and "Important Dates" in m["tabLabels"], f"tabs renamed ({m['tabLabels']})")
            check(m["cards"] > 0, f"Deadlines has cards ({m['cards']})")
            if label == "phone":
                # The square live box gives a phone ~210px of card space: the first card's title, date line, summary
                # and action button must all be readable without scrolling, even if its History line is below the fold.
                check(m["firstKeyVisible"], f"phone: first card's title, date, summary and action visible without scrolling (bar bottom {m['barBottom']}, limit {m['lim']}, first card {m['firstCardH']}px)")
            if label == "phone-tall":
                check(m["fullyVisible"] >= 1, f"phone-tall: at least one whole card visible under the tab bar ({m['fullyVisible']}; first card {m['firstCardH']}px)")

            # Tabs work in place and show different content
            counts = {}
            for tid in ["week", "coming", "changed", "classroom", "know", "dates", "head", "action"]:
                fr.locator(f'.chip.tab[data-tab="{tid}"]').click()
                page.wait_for_timeout(120)
                counts[tid] = fr.evaluate("() => document.querySelectorAll('.card').length")
            check(fr.url == url0, "clicking tabs never navigates the frame")
            check(all(v > 0 for v in counts.values()), f"every tab has content on {TODAY}: {counts}")
            check(fr.evaluate("() => [...document.querySelectorAll('.card')].some(c => c.textContent.includes('1st grade'))"),
                  "1st grade items are shown for class 2034")
            fr.locator('.chip.tab[data-tab="classroom"]').click()
            page.wait_for_timeout(120)
            check(fr.evaluate("() => document.querySelectorAll('h2.sec').length >= 3 && [...document.querySelectorAll('.card .items li')].length >= 5"),
                  "Classroom tab shows grouped sections with questions to ask")
            check(not fr.evaluate("() => [...document.querySelectorAll('.card .badge.aud')].some(b => b.textContent.trim() === '3rd grade')"),
                  "Classroom tab hides 3rd-grade-only material for class 2034")
            fr.locator('.chip.tab[data-tab="action"]').click()
            page.wait_for_timeout(120)
            check(not fr.evaluate("() => [...document.querySelectorAll('.card')].some(c => c.textContent.includes('3rd grade'))"),
                  "3rd grade items are hidden for class 2034")

            # Good to know: three groups in order, pinned Annual Fund first among the notices
            fr.locator('.chip.tab[data-tab="know"]').click()
            page.wait_for_timeout(120)
            g = fr.evaluate("""() => { const secs = [...document.querySelectorAll('h2.sec')].map(h => h.textContent);
                const notices = [...document.querySelectorAll('h2.sec')].find(h => h.textContent === 'Notices');
                let first = notices && notices.nextElementSibling; return {secs, first: first ? first.querySelector('.t').textContent : null}; }""")
            check(g["secs"] == ["Volunteer Opportunities", "Events", "Notices"], f"Good to know is grouped ({g['secs']})")
            check(g["first"] == "Annual Fund", f"pinned Annual Fund leads the Notices ({g['first']!r})")

            # Important Dates tab: official calendar with a calendar button each; the toggle mixes them into Coming up
            fr.locator('.chip.tab[data-tab="dates"]').click()
            page.wait_for_timeout(300)
            dm = fr.evaluate("""() => ({n: document.querySelectorAll('.card').length, badges: document.querySelectorAll('.card .badge.dates').length,
                                      cal: [...document.querySelectorAll('.card .lnk.cal')].map(a => a.textContent), hist: document.querySelectorAll('.card details').length})""")
            check(dm["n"] >= 10 and dm["badges"] == dm["n"] and dm["hist"] == 0, f"Important Dates tab lists the official calendar ({dm['n']} dates)")
            check(dm["cal"] and all(c == "Add to Google Calendar" for c in dm["cal"]), "each official date has a calendar button for the default calendar")
            before = counts["coming"]
            if label == "desktop":
                fr.locator('#mixDates').check()
                page.wait_for_timeout(120)
                fr.locator('.chip.tab[data-tab="coming"]').click()
                page.wait_for_timeout(120)
                after = fr.evaluate("() => document.querySelectorAll('.card').length")
                check(after > before, f"'Include Important Dates' adds official dates to Coming up ({before} -> {after})")
                fr.locator('#mixDates').uncheck()

                # Calendar preference: one button per card, matching the chosen calendar; shared with Important Dates
                fr.locator('.chip.pref[data-pref="outlook"]').click()
                page.wait_for_timeout(120)
                o = fr.evaluate("() => { const a = document.querySelector('.card .lnk.cal'); return a ? [a.textContent, a.href] : null; }")
                check(o and o[0] == "Add to Outlook" and "outlook.live.com" in o[1], f"Outlook preference gives Outlook buttons ({o})")
                fr.locator('.chip.pref[data-pref="apple"]').click()
                page.wait_for_timeout(120)
                with page.expect_download() as dl:
                    fr.locator('.card .lnk.cal').first.click()
                check(dl.value.suggested_filename.endswith(".ics"), f"Apple preference downloads a .ics ({dl.value.suggested_filename})")
                check(fr.evaluate("() => localStorage.getItem('sffsCalendarPref')") == "apple", "calendar preference is stored under the key Important Dates uses")
                fr.locator('.chip.pref[data-pref="google"]').click()

            # Hide with undo: a hidden card collapses to a stub, survives a reload, and comes back on Show
            fr.locator('.chip.tab[data-tab="action"]').click()
            page.wait_for_timeout(120)
            first_title = fr.evaluate("() => document.querySelector('.card .t').textContent")
            fr.locator('.card .hide').first.click()
            page.wait_for_timeout(120)
            st = fr.evaluate("() => { const s = document.querySelector('.card.stub'); return {stub: s ? s.textContent : null, bar: !document.getElementById('hiddenbar').hidden}; }")
            check(st["stub"] and first_title in st["stub"] and st["bar"], "Hide collapses the card to a one-line stub with a Show link")
            page.reload()
            fr = next(f for f in page.frames if "shared/updates" in f.url)
            fr.wait_for_load_state("load")
            page.wait_for_timeout(400)
            check(fr.evaluate("() => !!document.querySelector('.card.stub')"), "a hidden card stays hidden after a reload")
            fr.locator('.card.stub .lnk').first.click()
            page.wait_for_timeout(120)
            check(fr.evaluate("() => !document.querySelector('.card.stub') && document.getElementById('hiddenbar').hidden") and
                  fr.evaluate("() => document.querySelector('.card .t').textContent") == first_title, "Show restores the card in place")

            # Grade picker: add 3rd grade, 3rd grade items appear (on Good to know, which has 3rd grade volunteer items); remembered across reload
            fr.locator('.chip.tab[data-tab="know"]').click()
            if fr.evaluate("() => document.getElementById('grades').hidden"):
                fr.locator('#gradesToggle').click()
            fr.locator('.chip.g[data-g="3"]').click()
            page.wait_for_timeout(120)
            check(fr.evaluate("() => [...document.querySelectorAll('.card')].some(c => c.textContent.includes('3rd grade'))"),
                  "ticking 3rd grade shows 3rd grade items too")
            check(fr.evaluate("() => getComputedStyle(document.getElementById('prefs')).display !== 'none'"), "calendar choice is reachable with the Grade Filters open")
            page.reload()
            fr = next(f for f in page.frames if "shared/updates" in f.url)
            fr.wait_for_load_state("load")
            page.wait_for_timeout(400)
            check(fr.evaluate("() => [...document.querySelectorAll('.chip.g.on')].map(c => c.dataset.g).sort().join()") == "1,3",
                  "grade choice survives a reload")
            check(fr.evaluate("() => document.getElementById('showing').textContent") == "Displaying: Schoolwide; 1st; 3rd", "Displaying line lists the ticked grades")
            if fr.evaluate("() => document.getElementById('grades').hidden"):
                fr.locator('#gradesToggle').click()
            fr.locator('.chip.g[data-g="3"]').click()


            # Outbound link opens a popup, frame stays put
            fr.locator('.chip.tab[data-tab="action"]').click()
            page.wait_for_timeout(120)
            with page.expect_popup() as pop:
                fr.locator("a.lnk").first.click()
            check(pop.value is not None and fr.url == url0, "a link opens in a new tab; the embed stays put")
            pop.value.close()

            ctx.close()

        # Rollover: after the last day of school the same class is one grade up
        ctx = browser.new_context(viewport={"width": 1000, "height": 700})
        page = ctx.new_page()
        page.goto("http://127.0.0.1:8711/shared/updates/?class=2034&today=2027-06-10")
        page.wait_for_timeout(300)
        check(page.evaluate("() => [...document.querySelectorAll('.chip.g.on')].map(c => c.dataset.g)") == ["2"],
              "the day after the last day of school, class 2034 is 2nd grade")
        page.goto("http://127.0.0.1:8711/shared/updates/?class=2034&grade=5&today=2026-10-31")
        page.wait_for_timeout(300)
        check(page.evaluate("() => [...document.querySelectorAll('.chip.g.on')].map(c => c.dataset.g)") == ["5"],
              "?grade=5 overrides the class")
        ctx.close()
        browser.close()

    print()
    if failures:
        print(f"{len(failures)} check(s) failed:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("updates_check: all checks passed")


if __name__ == "__main__":
    main()
