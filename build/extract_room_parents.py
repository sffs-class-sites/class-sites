#!/usr/bin/env python3
"""Write the Room Parents extract the embed fetches: _site/data/room-parents.json.

Pattern A (CLAUDE.md §3): runs at deploy time, signed in as the Drive bot, reads the
master sheet's protected Live tab, and keeps only the columns on the Site Map's publish
list. The extract goes into the Pages deployment and is never committed.

  python3 build/extract_room_parents.py --csv live.csv [--site-map site-map.yaml]
  python3 build/extract_room_parents.py --sheet          # Live tab of the sheet in site-map.yaml

Fails closed:
- room-parents not publishable in site-map.yaml -> writes nothing, exit 0 (the embed says
  "not published yet").
- any invalid row -> writes nothing, exit 1. Never publishes a partial list.
Only "Name" and "Email" can reach the extract, and only if they are on the publish list;
"Class year" is required and becomes the grouping key.
"""
import argparse
import csv
import datetime as dt
import io
import json
import os
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "_site" / "data" / "room-parents.json"
FIELDS = {"Name": "name", "Email": "email"}  # sheet column -> contract field
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def source(site_map):
    for s in yaml.safe_load(pathlib.Path(site_map).read_text()).get("sources", []):
        if s.get("embed") == "room-parents":
            return s
    return None


def rows_from_sheet(sheet_id):
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    creds = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    r = AuthorizedSession(creds).get(f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/'Live'!A:Z")
    r.raise_for_status()
    return r.json().get("values", [])


def extract(rows, publish, today):
    """Returns (data, errors). rows: header + data rows."""
    if "Class year" not in publish:
        return None, ["publish list must include Class year"]
    if not rows:
        return None, ["Live tab is empty"]
    header = [h.strip() for h in rows[0]]
    keep = {col: FIELDS[col] for col in publish if col in FIELDS}
    missing = [c for c in ["Class year", *keep] if c not in header]
    if missing:
        return None, [f"Live tab is missing columns: {', '.join(missing)}"]
    lo, hi = today.year, today.year + 10  # classes still at school
    classes, errors = {}, []
    for n, row in enumerate(rows[1:], start=2):
        cell = lambda c: (row[header.index(c)] if header.index(c) < len(row) else "").strip()
        if not any(x.strip() for x in row):
            continue
        year = cell("Class year")
        if not (year.isdigit() and lo <= int(year) <= hi):
            errors.append(f"row {n}: class year {year!r} is not between {lo} and {hi}")
        person = {field: cell(col) for col, field in keep.items()}
        if "name" in person and not person["name"]:
            errors.append(f"row {n}: blank name")
        if person.get("email") and not EMAIL.match(person["email"]):
            errors.append(f"row {n}: email {person['email']!r} doesn't look like an email address")
        classes.setdefault(year, []).append({k: v for k, v in person.items() if v})
    if errors:
        return None, errors
    return {"schema": 1, "updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "classes": classes}, []


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv")
    src.add_argument("--sheet", action="store_true")
    ap.add_argument("--site-map", default=str(ROOT / "site-map.yaml"))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    s = source(a.site_map)
    if not s or not s.get("publishable"):
        why = "; ".join((s or {}).get("blocked") or ["not in the Site Map"])
        print(f"room-parents not published: {why}")
        return 0
    rows = list(csv.reader(io.StringIO(pathlib.Path(a.csv).read_text()))) if a.csv else rows_from_sheet(s["drive_file_id"])
    data, errors = extract(rows, s["publish"], dt.date.today())
    if errors:
        print("room-parents extract NOT written:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False))
    print(f"room-parents: {sum(map(len, data['classes'].values()))} people in {len(data['classes'])} classes -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
