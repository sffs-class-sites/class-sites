#!/usr/bin/env python3
"""Checks that build/sync_site_map.py fails closed. Runs in CI; no network."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "build"))
from sync_site_map import COLUMNS, from_csv, parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
H = COLUMNS
failures = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    cond or failures.append(msg)


def row(**kw):
    base = {"Source": "Room parents", "Embed": "room-parents", "Drive file ID": "abc123", "Shape": "Sheet",
            "Key": "class", "Publish list": "Class year, Name, Email", "Approved by": "Head of School",
            "Approved on": "2026-10-01", "Sync": "Yes", "Notes": ""}
    base.update(kw)
    return [base[c] for c in H]


s, e = parse([H, row()])
check(not e and s[0]["publishable"] and s[0]["publish"] == ["Class year", "Name", "Email"], "fully approved source is publishable")
for col, val in [("Sync", "No"), ("Approved by", ""), ("Approved on", ""), ("Publish list", ""), ("Drive file ID", "")]:
    s, e = parse([H, row(**{col: val})])
    check(not e and not s[0]["publishable"] and s[0]["blocked"], f"blocked when {col} is {val or 'blank'} ({s[0]['blocked']})")
s, e = parse([H[:-2], row()[:-2]])
check(e and "missing columns" in e[0], "missing columns stop the sync")
s, e = parse([H, row(), row()])
check(any("appears twice" in x for x in e), "duplicate embed stops the sync")
s, e = parse([H, row(Key="teacher")])
check(any("Key must be" in x for x in e), "unknown key stops the sync")
s, e = parse([H + ["Secret column"], row() + ["do not publish"]])
check(not e and "do not publish" not in str(s), "extra columns in the sheet never reach site-map.yaml")
s, e = parse(from_csv(ROOT / "tests/fixtures/site-map.csv"))
check(not e and len(s) == 4 and not any(x["publishable"] for x in s), "draft Site Map: 4 sources, none publishable yet")

print("RESULT:", "PASS" if not failures else f"FAIL ({len(failures)})")
sys.exit(1 if failures else 0)
