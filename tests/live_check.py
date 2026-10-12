#!/usr/bin/env python3
"""Open the published scratch Google Site and use the Important Dates embed inside it.

Proves live-site behaviour that tests/render_check.py can only imitate: Sites' real
iframe nesting, sandbox and sizing. At each window width it records the embed's frame
size (CLAUDE.md §0 item 1), then clicks a filter, a month jump and the add buttons.

Writes _live/report.md (+ report.json, screenshots). Exit 1 on any failure.
"""
import json
import pathlib
import re
import sys
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "_live"
SITE = "https://sites.google.com/view/zz-sffs-embed-test-scratch-saf"
EMBED = "https://sffs-class-sites.github.io/class-sites/shared/important-dates/"
SANDBOX = set("allow-scripts allow-popups allow-forms allow-same-origin allow-popups-to-escape-sandbox "
              "allow-downloads allow-storage-access-by-user-activation".split())
# (label, window width, window height, phone?)
WINDOWS = [("1024", 1024, 768, False), ("1280", 1280, 800, False), ("1440", 1440, 900, False),
           ("1920", 1920, 1080, False), ("iphone", 390, 844, True)]


def deployed_version():
    html = urllib.request.urlopen(EMBED, timeout=30).read().decode()
    return re.search(r'name="sffs-embed" content="([^"]+)"', html).group(1)


def main():
    OUT.mkdir(exist_ok=True)
    failures, rows = [], []
    expected = deployed_version()

    def check(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            failures.append(msg)
        return cond

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for label, w, h, phone in WINDOWS:
            print(f"[{label}]")
            opts = dict(viewport={"width": w, "height": h}, accept_downloads=True)
            if phone:
                opts.update(p.devices["iPhone 13"], accept_downloads=True)
            ctx = browser.new_context(**opts)
            page = ctx.new_page()
            page.goto(SITE, wait_until="domcontentloaded", timeout=60000)
            frame = None
            for _ in range(40):  # Sites lays embeds out late
                frame = next((f for f in page.frames if f.url.startswith(EMBED)), None)
                if frame:
                    break
                page.wait_for_timeout(500)
            if not check(frame is not None, f"{label}: embed frame found on the published Site"):
                page.screenshot(path=str(OUT / f"live-{label}.png"), full_page=True)
                ctx.close()
                continue
            frame.wait_for_load_state("load")
            el = frame.frame_element()
            el.scroll_into_view_if_needed()
            page.wait_for_timeout(2500)
            box = el.bounding_box()
            fw, fh = round(box["width"]), round(box["height"])
            sandbox = set((el.get_attribute("sandbox") or "").split())
            version = frame.evaluate("() => document.querySelector('meta[name=sffs-embed]')?.content")
            rows.append({"window": label, "window_w": w, "frame_w": fw, "frame_h": fh,
                         "aspect_h_over_w": round(fh / fw, 3), "version": version})
            print(f"  frame {fw}x{fh} (h/w {fh / fw:.3f}), version {version}")

            check(sandbox == SANDBOX, f"{label}: sandbox is exactly Sites' known set ({' '.join(sorted(sandbox - SANDBOX)) or 'no extras'}"
                                      f"{'; missing ' + ' '.join(sorted(SANDBOX - sandbox)) if SANDBOX - sandbox else ''})")
            check(version == expected, f"{label}: Site shows the deployed version ({version} vs {expected})")
            m = frame.evaluate("""() => { const w = document.getElementById('wrap');
                return {hscroll: document.documentElement.scrollWidth > innerWidth + 1 || w.scrollWidth > w.clientWidth + 1,
                        fills: Math.abs(w.getBoundingClientRect().height - innerHeight) < 2,
                        scrolls: w.scrollHeight > w.clientHeight} }""")
            check(not m["hscroll"], f"{label}: no horizontal scroll inside the embed")
            check(m["fills"], f"{label}: embed fills its frame")

            # Filter: a category chip hides every row of other categories.
            frame.locator('.chip.cat[data-cat="noschool"]').click()
            cats = frame.evaluate("() => [...document.querySelectorAll('tr.ev:not([hidden])')].map(r => r.dataset.cat)")
            check(cats and set(cats) == {"noschool"}, f"{label}: 'No school' filter shows only no-school rows ({len(cats)})")
            frame.locator('.chip.cat[data-cat="all"]').click()

            # Month jump: the target month lands just under the sticky filter bar.
            target = frame.evaluate("() => { const j = [...document.querySelectorAll('.chip.jump:not([hidden])')]; return j[j.length >> 1]?.dataset.jump }")
            before = frame.evaluate("() => document.getElementById('wrap').scrollTop")
            frame.locator(f'.chip.jump[data-jump="{target}"]').click()
            page.wait_for_timeout(1200)
            gap = frame.evaluate("""id => { const t = document.getElementById(id), bar = document.getElementById('toolbar');
                return Math.round(t.getBoundingClientRect().top - bar.getBoundingClientRect().bottom) }""", target)
            after, bottom = frame.evaluate("() => { const w = document.getElementById('wrap'); return [w.scrollTop, w.scrollHeight - w.clientHeight - w.scrollTop < 2] }")
            check(after != before and (-4 <= gap <= 12 or (bottom and gap > 0)),
                  f"{label}: month jump to {target} lands under the filter bar (gap {gap}px{', scrolled to the end' if bottom else ''})")

            # Add buttons: Google opens a new tab to Google Calendar; Apple downloads a one-event .ics.
            frame.locator('.chip.pref[data-pref="google"]').click()
            a = frame.locator("tr.ev:not([hidden]) .cal-btn").first
            href, tgt = a.get_attribute("href") or "", a.get_attribute("target")
            check(href.startswith("https://calendar.google.com/") and tgt == "_blank", f"{label}: Google add button opens Google Calendar in a new tab")
            frame.locator('.chip.pref[data-pref="apple"]').click()
            with page.expect_download(timeout=15000) as dl:
                frame.locator("tr.ev:not([hidden]) .cal-btn").first.click()
            ics = pathlib.Path(dl.value.path()).read_text()
            check(ics.count("BEGIN:VEVENT") == 1 and re.search(r"^UID:.+@sffs-calendar\r?$", ics, re.M) is not None,
                  f"{label}: Apple add button downloads a one-event .ics ({dl.value.suggested_filename})")
            frame.locator('.chip.pref[data-pref="google"]').click()  # leave the default for the screenshot
            el.screenshot(path=str(OUT / f"live-{label}.png"))
            ctx.close()
        browser.close()

    desk = [r for r in rows if r["window"] != "iphone"]
    lines = ["## Live scratch-Site check", "", f"Site: {SITE}", f"Deployed embed version: `{expected}`", "",
             "| Window | Embed frame (w × h) | h ÷ w |", "|---|---|---|"]
    lines += [f"| {r['window']} | {r['frame_w']} × {r['frame_h']} | {r['aspect_h_over_w']} |" for r in rows]
    if len(desk) > 1:
        same_w = len({r["frame_w"] for r in desk}) == 1
        same_a = max(r["aspect_h_over_w"] for r in desk) - min(r["aspect_h_over_w"] for r in desk) < 0.01
        lines += ["", f"Desktop frame width {'is the same' if same_w else 'changes'} across window widths; "
                      f"height ÷ width {'stays constant' if same_a else 'varies'}."]
    lines += ["", f"**Result: {'PASS' if not failures else 'FAIL (' + str(len(failures)) + ')'}**"]
    lines += [f"- {f}" for f in failures]
    (OUT / "report.md").write_text("\n".join(lines) + "\n")
    (OUT / "report.json").write_text(json.dumps({"rows": rows, "failures": failures}, indent=2))
    print("\n".join(lines))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
