#!/usr/bin/env python3
"""Checks for the Room Parents embed (pattern A). Fake people only; never touches _site/data.

1. The extract fails closed and keeps only publish-list columns.
2. The Apps Script's validateRows() blocks bad Drafts (run in Chromium; no Node needed).
3. The embed, inside an iframe with Sites' sandbox, shows each state correctly at desktop and
   phone width: loaded, empty class, not published (404), load error with retry, no ?class=.

Usage: python3 tests/room_parents_check.py   (expects _site built)
"""
import contextlib
import datetime as dt
import functools
import http.server
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading

import yaml
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "build"))
from extract_room_parents import extract  # noqa: E402
from render_check import SANDBOX  # noqa: E402

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


def shot(page, path):
    """Screenshots are for reviewers, not assertions: retry once, then just note it."""
    for attempt in (1, 2):
        try:
            page.screenshot(path=str(path))
            return
        except Exception as e:
            page.wait_for_timeout(500)
            err = e
    print(f"  note: no screenshot {path.name} ({str(err).splitlines()[0]})")


def extract_checks(tmp):
    print("[extract]")
    rows = [l.split(",") for l in (FIX / "room-parents-live.csv").read_text().splitlines()]
    today = dt.date(2026, 10, 12)
    data, err = extract(rows, ["Class year", "Name", "Email"], today)
    check(not err and data["schema"] == 1 and len(data["classes"]["2034"]) == 2, "approved columns extracted, grouped by class")
    check("555-0101" not in json.dumps(data), "Phone (not on the publish list) never reaches the extract")
    data, err = extract(rows, ["Class year", "Name"], today)
    check(not err and "example.org" not in json.dumps(data), "Email left off the publish list is left out")
    bad = rows + [["2034", "", "x@example.org", ""]]
    check(extract(bad, ["Class year", "Name", "Email"], today)[0] is None, "a blank name blocks the whole extract")
    bad = rows + [["2034", "Someone", "not-an-email", ""]]
    check(extract(bad, ["Class year", "Name", "Email"], today)[0] is None, "a bad email blocks the whole extract")
    bad = rows + [["1999", "Someone", "", ""]]
    check(extract(bad, ["Class year", "Name", "Email"], today)[0] is None, "an impossible class year blocks the whole extract")
    sm = tmp / "site-map.yaml"
    sm.write_text(yaml.safe_dump({"sources": [{"embed": "room-parents", "publishable": False, "blocked": ["no Approved by"]}]}))
    out = tmp / "out.json"
    r = subprocess.run([sys.executable, str(ROOT / "build/extract_room_parents.py"), "--csv", str(FIX / "room-parents-live.csv"),
                        "--site-map", str(sm), "--out", str(out)], capture_output=True, text=True)
    check(r.returncode == 0 and not out.exists(), f"not publishable in the Site Map: nothing written ({r.stdout.strip()})")


def apps_script_checks(page):
    print("[apps script]")
    page.set_content("<script>" + (ROOT / "apps-script/room-parents/Code.gs").read_text() + "</script>")
    run = lambda rows, live=0: page.evaluate(
        "([h, r, l]) => validateRows(h, r, l, new Date(2026, 9, 12))", [["Class year", "Name", "Email"], rows, live])
    good = [["2034", "Test Parent One", "one@example.org"], ["2032", "Test Parent Two", ""]]
    v = run(good)
    check(not v["errors"] and not v["warnings"], "a good Draft passes")
    check(run([["2034", "", "a@example.org"]])["errors"], "blank name is an error")
    check(run([["2034", "A", "nope"]])["errors"], "bad email is an error")
    check(run([["34", "A", ""]])["errors"], "class year '34' is an error")
    check(run([["", "", ""]])["errors"], "an empty Draft is an error")
    check(run(good, live=10)["warnings"] and not run(good, live=10)["errors"], "losing more than half the people is a warning to confirm")
    v = page.evaluate("() => validateRows(['Name','Email'], [], 0, new Date(2026,9,12))")
    check(v["errors"] and "Missing columns" in v["errors"][0], "missing Class year column is an error")


def embed_checks(p, tmp):
    print("[embed]")
    sites = {}
    for case, payload in [("ok", json.dumps({"schema": 1, "updated": "2026-10-01T12:00:00Z",
                                            "classes": {"2034": [{"name": "Test Parent One", "email": "parent.one@example.org"},
                                                                 {"name": "Test Parent Two With A Rather Long Name", "email": "a.really.long.address.for.testing@example.org"}]}})),
                          ("missing", None), ("broken", "{not json")]:
        d = tmp / case
        shutil.copytree(ROOT / "_site/shared/room-parents", d / "shared/room-parents")
        if payload is not None:
            (d / "data").mkdir(parents=True)
            (d / "data/room-parents.json").write_text(payload)
        sites[case] = d
    harness = tmp / "harness"
    harness.mkdir()
    servers = [serve(sites[c], port) for c, port in [("ok", 8711), ("missing", 8712), ("broken", 8713)]] + [serve(harness, 8714)]
    cases = [("loaded", 8711, "?class=2034", "Test Parent One"), ("empty class", 8711, "?class=2036", "No room parents are listed"),
             ("not published", 8712, "?class=2034", "haven’t been published"), ("load error", 8713, "?class=2034", "Couldn’t load"),
             ("no class", 8711, "", "needs a class")]
    b = p.chromium.launch()
    for label, fw, fh in [("desktop", 1154, 500), ("phone", 315, 300)]:
        for name, port, query, expect in cases:
            (harness / "index.html").write_text(
                f'<!doctype html><body style="margin:0"><iframe id="f" sandbox="{SANDBOX}" '
                f'src="http://127.0.0.1:{port}/shared/room-parents/{query}" style="border:0;width:{fw}px;height:{fh}px"></iframe></body>')
            ctx = b.new_context(viewport={"width": max(fw, 390), "height": fh + 40})
            page = ctx.new_page()
            page.goto("http://127.0.0.1:8714/index.html")
            fr = page.frame_locator("#f")
            try:
                fr.get_by_text(expect, exact=False).first.wait_for(timeout=8000)
                shown = True
            except Exception:
                shown = False
            check(shown, f"{label} / {name}: shows {expect!r}")
            frame = next(f for f in page.frames if "room-parents" in f.url)
            hs = frame.evaluate("() => document.documentElement.scrollWidth > innerWidth + 1 || document.getElementById('wrap').scrollWidth > document.getElementById('wrap').clientWidth + 1")
            check(not hs, f"{label} / {name}: no horizontal scroll")
            if name == "loaded":
                a = fr.locator("a.email").first
                check(a.get_attribute("href") == "mailto:parent.one@example.org" and a.get_attribute("target") == "_blank",
                      f"{label}: email opens mail in a new window, never navigates the frame")
                check(fr.locator("text=Updated").count() == 1, f"{label}: shows when the list was updated")
                shot(page, ROOT / "_harness" / f"room-parents-{label}.png")
            if name == "load error":
                check(fr.get_by_role("button", name="Try again").count() == 1, f"{label}: load error offers Try again")
            ctx.close()
    b.close()
    for s in servers:
        s.shutdown()


def main():
    (ROOT / "_harness").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        extract_checks(tmp)
        with sync_playwright() as p:
            b = p.chromium.launch()
            apps_script_checks(b.new_page())
            b.close()
            embed_checks(p, tmp)
    check(not (ROOT / "_site/data/room-parents.json").exists() or "example.org" not in (ROOT / "_site/data/room-parents.json").read_text(),
          "no fixture data in the real Pages output")
    print("\nRESULT:", "PASS" if not failures else f"FAIL ({len(failures)})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
