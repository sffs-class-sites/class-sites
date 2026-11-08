#!/usr/bin/env python3
"""Checks for the Team Schedule embed (shared/team-schedule/, built by build/build_team_schedule.py).

1. The team data files: schema, UIDs present, unique and never changed for a game that was
   already published (every UID in the pasted embed kept in tests/fixtures/hoops-2034-2027-winter/
   is still in the data), games in date order, no personal data.
2. The embed, inside an iframe with Sites' sandbox, at the standard `card` box on a desktop
   (1154 x 770), a tablet, an iPhone 13 (352 x 235) and the narrowest phones (315 x 210), on
   three days (before the season, mid-season on a game day, after the season): the next or
   today's game is in a lead card fully visible on a phone without scrolling, past games are
   hidden until asked, NEXT UP and today are marked, month jumps and the toggle work in place
   (no navigation, no new tab), the grade line comes from the class model, the handbook-style
   links open new tabs, no horizontal scroll.
3. Calendar adds: + Google opens Google Calendar in a new tab with the UTC times; the Outlook
   pill switches every button; + Apple downloads a one-event .ics with the frozen UID; Add all
   downloads every game, and those VEVENTs are exactly the ones the pasted embed shipped (so a
   family who re-imports is updated, not duplicated); the choice is remembered.
4. No team / unknown team messages, and the translation notice.

Usage: python3 tests/team_schedule_check.py   (expects _site built)
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
TEAMS = ROOT / "shared" / "team-schedule" / "teams"
PASTED = ROOT / "tests" / "fixtures" / "hoops-2034-2027-winter" / "pasted-embed.html"   # the code that was pasted on the Site until 2026-11-08
sys.path.insert(0, str(ROOT / "tests"))
from render_check import SANDBOX  # noqa: E402

TEAM = "hoops-2034-2027-winter"
# phone = the standard `card` box on an iPhone 13; phone-narrow = the same box on the narrowest phones (registry.yaml `boxes`)
FRAMES = [("desktop", 1154, 770), ("tablet", 700, 672), ("phone", 352, 235), ("phone-narrow", 315, 210)]
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


def pasted_events():
    """The VEVENT strings the live pasted embed carries (its `var ICS = [...]`)."""
    m = re.search(r"var ICS = (\[.*?\]);\n", PASTED.read_text(), re.S)
    return json.loads(m.group(1)) if m else []


def data_checks():
    print("[data]")
    files = sorted(TEAMS.glob("*.json"))
    check(files, f"team files present ({[f.name for f in files]})")
    teams = {}
    for f in files:
        t = json.loads(f.read_text())
        teams[f.stem] = t
        check(t.get("schema") == 1 and t.get("id") == f.stem, f"{f.name}: schema 1, id matches the file name")
        games = [g for g in t["games"] if not g.get("no_game")]
        uids = [g.get("uid") for g in games]
        check(all(uids) and len(set(uids)) == len(uids), f"{f.name}: every game has a uid, all distinct")
        check(all(u.endswith("@" + t["uid_domain"]) for u in uids), f"{f.name}: uids end in @{t['uid_domain']}")
        check([g["date"] for g in t["games"]] == sorted(g["date"] for g in t["games"]), f"{f.name}: games in date order")
        check(all(g["date"] < t["utc_offset_valid_until"] for g in t["games"]), f"{f.name}: every game before the offset's valid-until date")
        check(not re.search(r"[\w.+-]+@[\w-]+\.(com|org|net|edu)\b|\b\d{3}-\d{4}\b", json.dumps({k: v for k, v in t.items() if k != "games"})),
              f"{f.name}: no email address or phone number (non-personal file)")
    hoops = teams.get(TEAM)
    check(hoops is not None, f"{TEAM}.json exists (the 1st-grade basketball season)")
    live_uids = sorted(re.findall(r"UID:(\S+)", "\n".join(pasted_events())))
    data_uids = sorted(g["uid"] for g in hoops["games"] if not g.get("no_game")) if hoops else []
    check(live_uids and live_uids == data_uids, f"frozen UIDs: the data's {len(data_uids)} uids are exactly the pasted embed's {len(live_uids)}")
    return teams


def embed_checks(p, teams):
    print("[embed]")
    harness = ROOT / "_harness"
    harness.mkdir(exist_ok=True)
    servers = [serve(SITE, 8731), serve(harness, 8732)]
    hoops = teams[TEAM]
    games = [g for g in hoops["games"] if not g.get("no_game")]
    # (name, today, expected lead label, expected lead opponent, rows hidden)
    days = [("pre-season", "2026-12-20", "Next game", games[0]["opponent"], 0),
            ("game day", "2027-01-24", "Today’s game", "Cubs", 3),
            ("mid-season", "2027-02-10", "Next game", "Celtics", 6),
            ("season over", "2027-03-10", "Season finished", games[-1]["opponent"], 0)]
    b = p.chromium.launch()
    for label, fw, fh in FRAMES:
        for name, today, want_who, want_opp, want_hidden in days:
            src = f"http://127.0.0.1:8731/shared/team-schedule/?team={TEAM}&today={today}"
            (harness / "ts-host.html").write_text(
                f'<!doctype html><body style="margin:0"><iframe id="f" sandbox="{SANDBOX}" '
                f'src="{src}" style="border:0;width:{fw}px;height:{fh}px"></iframe></body>')
            ctx = b.new_context(viewport={"width": max(fw, 390), "height": fh + 40}, accept_downloads=True)
            ctx.route("https://calendar.google.com/**", lambda r: r.fulfill(status=200, content_type="text/html", body="<p>gcal stub</p>"))
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            popups = []
            ctx.on("page", lambda pg: popups.append(pg))
            page.goto("http://127.0.0.1:8732/ts-host.html")
            fr = page.frame_locator("#f")
            fr.locator("tr.ev").first.wait_for(state="attached", timeout=8000)
            frame = next(f for f in page.frames if "/shared/team-schedule/" in f.url)
            page.wait_for_timeout(300)
            tag = f"{label} / {name}"
            check(not errors, f"{tag}: no script errors {errors or ''}")
            st = frame.evaluate("""() => {
              const q = s => document.querySelector(s), rows = [...document.querySelectorAll('tr.ev')];
              const lead = q('#lead'), hint = q('#hint'), wrap = q('#wrap');
              const limit = hint.hidden ? innerHeight : hint.getBoundingClientRect().top;
              const r = lead.getBoundingClientRect();
              const vis = e => { const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0; };
              const shown = e => e && e.getClientRects().length > 0;
              return {title: [...q('#title').children].filter(shown).map(e => e.textContent).join(''), sub: [...q('#sub').children].filter(shown).map(e => e.textContent).join(''), lead_hidden: lead.hidden, lead: lead.textContent,
                      lead_top: r.top, lead_bottom: r.bottom, limit,
                      rows: rows.length, hidden: rows.filter(x => x.hidden).length, games: rows.filter(x => x.classList.contains('game')).length,
                      next: [...document.querySelectorAll('.next-flag')].map(f => f.closest('tr').getAttribute('data-date')),
                      today: [...document.querySelectorAll('tr.today')].map(t => t.getAttribute('data-date')),
                      off: rows.filter(x => x.classList.contains('off')).map(x => x.querySelector('.event-title').textContent),
                      btns: [...document.querySelectorAll('.cal-btn')].length,
                      hscroll: document.documentElement.scrollWidth > innerWidth + 1 || wrap.scrollWidth > wrap.clientWidth + 1,
                      wide: [...document.querySelectorAll('td, .chip, .btn, .add, .lead')].filter(e => vis(e) && e.getBoundingClientRect().right > innerWidth + 1 && !e.closest('.row')).length,
                      links: [...document.querySelectorAll('a[href^="http"]')].map(a => [a.target, a.rel])};
            }""")
            check(st["title"] == (hoops["title"] if fw > 560 else f"{hoops['team']} · {hoops['sport']}"), f"{tag}: title is the team's ({st['title']!r})")
            check(st["sub"].startswith("1st grade · Class of 2034") and (fw <= 560 or hoops["subtitle"] in st["sub"]), f"{tag}: grade line from the class model ({st['sub'][:32]!r})")
            check(not st["hscroll"] and st["wide"] == 0, f"{tag}: no horizontal scroll, nothing wider than the frame")
            check(st["rows"] == len(hoops["games"]) and st["games"] == len(games) and st["off"] == ["No game this week"], f"{tag}: every week listed, the bye as 'No game this week'")
            check(not st["lead_hidden"] and st["lead"].startswith(want_who) and want_opp in st["lead"], f"{tag}: lead card = {want_who} vs. {want_opp} ({st['lead'][:48]!r})")
            check(st["lead_top"] >= 0 and st["lead_bottom"] <= st["limit"] + 1, f"{tag}: the lead card is fully visible without scrolling (bottom {st['lead_bottom']:.0f}, limit {st['limit']:.0f})")
            check(st["hidden"] == want_hidden, f"{tag}: {want_hidden} past rows hidden ({st['hidden']})")
            if name == "game day":
                check(st["today"] == [today] and st["next"] == [], f"{tag}: today's game highlighted, no NEXT UP")
            elif want_who == "Next game":
                check(st["next"] == [next(g["date"] for g in games if g["opponent"] == want_opp)] and st["today"] == [], f"{tag}: NEXT UP on the next game")
            else:
                check(st["next"] == [] and st["hidden"] == 0, f"{tag}: finished season shows everything, no NEXT UP")
            check(st["btns"] == len(games), f"{tag}: one add button per game ({st['btns']})")
            check(st["links"] and all(t == "_blank" and "noopener" in r for t, r in st["links"]), f"{tag}: every outbound link opens a new tab with noopener")
            if name == "pre-season":
                page.screenshot(path=str(harness / f"team-schedule-{label}.png"))
            if name == "mid-season":
                url0 = frame.url
                fr.locator("#showpast").check()
                page.wait_for_timeout(200)
                check(frame.evaluate("() => [...document.querySelectorAll('tr.ev')].filter(x => x.hidden).length") == 0 and frame.url == url0 and not popups,
                      f"{tag}: Show past games reveals them in place")
                fr.locator(".chip.jump").first.click()
                page.wait_for_timeout(400)
                check(frame.url == url0 and not popups, f"{tag}: month jump: no navigation, no new tab")
            if label == "desktop" and name == "pre-season":
                print("[calendar adds]")
                g0 = games[0]
                with page.expect_popup(timeout=5000) as pop:
                    fr.locator("tr.game").first.locator(".cal-btn").click()
                pg = pop.value
                check(pg.url.startswith("https://calendar.google.com/calendar/render?action=TEMPLATE") and "dates=20270103T190000Z%2F20270103T200000Z" in pg.url.replace("/", "%2F"),
                      f"+ Google opens Google Calendar in a new tab with the UTC times ({pg.url[:70]})")
                check(frame.url == url_pre(src), "+ Google: the embed itself did not navigate")
                pg.close()
                fr.locator(".chip.pref[data-pref=outlook]").click()
                href = fr.locator("tr.game").first.locator(".cal-btn").get_attribute("href")
                check(href.startswith("https://outlook.live.com/calendar/0/deeplink/compose") and "startdt=2027-01-03T19%3A00%3A00Z" in href, "Outlook pill switches every button to Outlook links")
                fr.locator(".chip.pref[data-pref=apple]").click()
                with page.expect_download(timeout=5000) as dl:
                    fr.locator("tr.game").first.locator(".cal-btn").click()
                txt = pathlib.Path(dl.value.path()).read_text()
                check(txt.startswith("BEGIN:VCALENDAR") and txt.count("BEGIN:VEVENT") == 1 and f"UID:{g0['uid']}" in txt and "DTSTART:20270103T190000Z" in txt,
                      f"+ Apple downloads a one-event .ics with the frozen UID ({dl.value.suggested_filename})")
                with page.expect_download(timeout=5000) as dl:
                    fr.locator("#addall").click()
                txt = pathlib.Path(dl.value.path()).read_text()
                blocks = re.findall(r"BEGIN:VEVENT.*?END:VEVENT", txt, re.S)
                check(len(blocks) == len(games), f"Add all downloads every game ({len(blocks)})")
                norm = lambda s: "\n".join(l.strip() for l in s.replace("\r\n", "\n").split("\n"))
                check(sorted(norm(x) for x in blocks) == sorted(norm(x) for x in pasted_events()),
                      "the VEVENTs are exactly the ones the pasted embed shipped (UID, DTSTAMP, times, text), so re-imports update rather than duplicate")
                check("PRODID:-//SFFS Class Page//1st Grade Hoops//EN" in txt, "the calendar names the team")
                page.reload()
                fr.locator("tr.ev").first.wait_for(state="attached", timeout=8000)
                remembered = fr.locator(".chip.pref.on").get_attribute("data-pref")
                check(remembered == "apple", f"calendar choice remembered after reload ({remembered})")
                ctx.clear_cookies()
            ctx.close()
    print("[no team]")
    ctx = b.new_context(viewport={"width": 700, "height": 600})
    page = ctx.new_page()
    page.goto("http://127.0.0.1:8731/shared/team-schedule/")
    check("needs a team in its address" in page.locator(".msg").text_content(), "no ?team=: says what the address needs")
    page.goto("http://127.0.0.1:8731/shared/team-schedule/?team=nope")
    check('No team called "nope"' in page.locator(".msg").text_content(), "unknown team: named in the message")
    ctx.close()
    print("[translation notice]")
    from lang_check import check_lang
    check_lang(b, f"http://127.0.0.1:8731/shared/team-schedule/?team={TEAM}&today=2026-12-20", check)
    b.close()
    for s in servers:
        s.shutdown()


def url_pre(src):
    return src


def main():
    teams = data_checks()
    built = SITE / "shared/team-schedule/index.html"
    check(built.exists() and 'name="sffs-embed" content="team-schedule@' in built.read_text(), "built page carries the sffs-embed version marker")
    with sync_playwright() as p:
        embed_checks(p, teams)
    print("\nRESULT:", "PASS" if not failures else f"FAIL ({len(failures)})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
