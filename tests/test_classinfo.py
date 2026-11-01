#!/usr/bin/env python3
"""Unit checks for the class and grade model (build/classinfo.py). Runs in CI; no network, no browser.
The browser copy (shared/class/class.js) is checked against the same table by tests/render_check.py."""
import datetime as dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "build"))
import classinfo as ci

failures = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    cond or failures.append(msg)


YEARS = [{"end_year": 2027, "label": "2026–27", "first_day": "2026-08-26", "last_day": "2027-06-09"}]

# (query, today, expected heading). The same table drives the browser check in render_check.py.
TABLE = [
    ("?class=2034", "2026-09-16", "1st grade · Class of 2034"),
    ("?class=2032", "2026-09-16", "3rd grade · Class of 2032"),
    ("?class=2035", "2026-09-16", "Kindergarten · Class of 2035"),
    ("?class=2027", "2026-09-16", "8th grade · Class of 2027"),
    ("?class=2034", "2027-06-09", "1st grade · Class of 2034"),          # last day of school: still this year
    ("?class=2034", "2027-06-10", "2nd grade · Class of 2034"),          # the day after: next year
    ("?class=2034", "2027-08-01", "2nd grade · Class of 2034"),          # summer counts as next year
    ("?class=2034", "2026-08-01", "1st grade · Class of 2034"),          # summer before the year started
    ("?class=2036", "2026-09-16", "Class of 2036 · not yet at SFFS"),
    ("?class=2026", "2026-09-16", "Class of 2026 · graduated"),
    ("?class=2034&grade=3", "2026-09-16", "3rd grade · Class of 2034 (preview)"),
    ("?grade=3", "2026-09-16", ""),                                        # no class: nothing to say
    ("?class=34", "2026-09-16", ""),                                       # malformed class ignored
    ("?today=2027-06-10&class=2034", None, "2nd grade · Class of 2034"),   # today from the query, any order
]
pathlib.Path(__file__).with_name("classinfo_table.json").write_text(json.dumps(TABLE, ensure_ascii=False, indent=1))

for q, today, want in TABLE:
    got = ci.class_info(q, dt.date.fromisoformat(today) if today else None, YEARS)["heading"]
    check(got == want, f"{q} on {today}: {got!r}")

y = ci.school_year(dt.date(2028, 3, 1), YEARS)
check(y["end_year"] == 2028 and y["assumed"], "a year with no row is assumed (ends June 30) and flagged")
check(ci.school_year(dt.date(2028, 7, 1), YEARS)["end_year"] == 2029, "July of an unknown year starts the next school year")
check(ci.grade(2034, 2027) == 1 and ci.grade(2035, 2027) == 0 and ci.grade(2027, 2027) == 8, "grade = 8 - (gradYear - endYear)")

real = ci.load_years()
check(real and real[-1]["end_year"] >= 2027, f"shared/school-years.json loads ({len(real)} year(s))")
bad = pathlib.Path(__file__).with_name("_bad_years.json")
bad.write_text(json.dumps({"years": [{"end_year": 2027, "label": "x", "first_day": "2027-09-01", "last_day": "2027-06-09"}]}))
try:
    ci.load_years(bad); check(False, "a year that ends before it starts is refused")
except ValueError:
    check(True, "a year that ends before it starts is refused")
bad.unlink()
js = ci.class_js(YEARS)
check("__SCHOOL_YEARS__" not in js and '"end_year": 2027' in js and "var SFFS" in js, "class_js() inlines the school years")

print("\nRESULT:", "PASS" if not failures else f"FAIL ({len(failures)})")
sys.exit(1 if failures else 0)
