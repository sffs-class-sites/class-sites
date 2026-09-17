#!/usr/bin/env python3
"""Check data.json against the transcribed source calendar.

Every dated line in the source must match exactly one event (start, end, star),
every event must come from a source line, and dates must fall in the school year.
"""
import datetime as dt
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "shared/important-dates/data.json").read_text())
SRC = (ROOT / "shared/important-dates/source-2026-27.txt").read_text()

MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}
SHORT = {k[:3]: v for k, v in MONTHS.items()}
FIRST_YEAR = 2026
VALID_CATS = set(DATA["categories"])

LINE = re.compile(r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
                  r"(\d{1,2})(?:-(?:(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+)?(\d{1,2}))?\s+(.*)$")


def year_for(month):
    return FIRST_YEAR if month >= 8 else FIRST_YEAR + 1


def parse_source():
    out = []
    for line in SRC.splitlines():
        m = LINE.match(line.strip())
        if not m:
            continue
        mon = MONTHS[m.group(1)]
        start = dt.date(year_for(mon), mon, int(m.group(2)))
        end = None
        if m.group(4):
            emon = SHORT[m.group(3)] if m.group(3) else mon
            end = dt.date(year_for(emon), emon, int(m.group(4)))
        rest = m.group(5).strip()
        out.append({"date": start.isoformat(), "end": end.isoformat() if end else None,
                    "star": rest.endswith("*"), "text": rest})
    return out


def main():
    errors = []
    src = parse_source()
    evs = DATA["events"]
    if len(src) != len(evs):
        errors.append(f"source has {len(src)} dated lines, data.json has {len(evs)} events")
    key = lambda e: (e["date"], e.get("end") or None)
    by_key = {}
    for e in evs:
        by_key.setdefault(key(e), []).append(e)
        if e["cat"] not in VALID_CATS:
            errors.append(f"{e['date']}: unknown category {e['cat']!r}")
        if e.get("end") and e["end"] <= e["date"]:
            errors.append(f"{e['date']}: end {e['end']} is not after start")
        first = e["title"].split()[0].lower().strip("'")
    for s in src:
        matches = by_key.get(key(s), [])
        if not matches:
            errors.append(f"missing from data.json: {s['date']}{'–' + s['end'] if s['end'] else ''} {s['text']}")
            continue
        e = matches.pop(0)
        if bool(e.get("star")) != s["star"]:
            errors.append(f"{s['date']}: star mismatch (source {s['star']}, data {e.get('star')})")
        if re.sub(r"[^a-z0-9-]", "", e["title"].split()[0].lower()) not in re.sub(r"[^a-z0-9 -]", "", s["text"].lower()):
            errors.append(f"{s['date']}: title {e['title']!r} not found in source line {s['text']!r}")
    leftovers = [e for v in by_key.values() for e in v]
    for e in leftovers:
        errors.append(f"in data.json but not in source: {e['date']} {e['title']}")
    for e in evs:
        if not ("2026-08-01" <= e["date"] <= "2027-06-30"):
            errors.append(f"{e['date']}: outside the 2026–27 school year")
    if errors:
        print("FAIL\n  " + "\n  ".join(errors))
        return 1
    print(f"OK: {len(evs)} events match {len(src)} source lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
