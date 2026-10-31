#!/usr/bin/env python3
"""The SFFS class and grade model, for builds and tests. Mirrors shared/class/class.js exactly.

A site follows a class (graduation year), never a grade (CLAUDE.md section 1). The grade is
worked out from the school year: grade = 8 - (grad_year - end_year), kindergarten = 0. The year
rolls over the day after the last day of school (shared/school-years.json). class_js() returns
the browser module with the same data inlined, for the embed builds.
"""
import datetime as dt
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
YEARS_FILE = ROOT / "shared" / "school-years.json"
JS_FILE = ROOT / "shared" / "class" / "class.js"
ORD = ["Kindergarten", "1st grade", "2nd grade", "3rd grade", "4th grade", "5th grade", "6th grade", "7th grade", "8th grade"]


def load_years(path=YEARS_FILE):
    rows = json.loads(path.read_text())["years"]
    for r in rows:
        for k in ("end_year", "label", "first_day", "last_day"):
            if k not in r:
                raise ValueError(f"school-years.json: row {r} is missing {k}")
        a, b = dt.date.fromisoformat(r["first_day"]), dt.date.fromisoformat(r["last_day"])
        if not (a < b and b.year == r["end_year"]):
            raise ValueError(f"school-years.json: {r['label']} must end in {r['end_year']}, after it starts")
    if len({r["end_year"] for r in rows}) != len(rows):
        raise ValueError("school-years.json: duplicate end_year")
    return rows


def class_js(years=None):
    """The browser module with the school years inlined."""
    rows = years if years is not None else load_years()
    return JS_FILE.read_text().replace("__SCHOOL_YEARS__", json.dumps(rows, ensure_ascii=False))


def school_year(today, years=None):
    rows = years if years is not None else load_years()
    guess = today.year + 1 if today.month >= 7 else today.year
    known = next((r for r in rows if r["end_year"] == guess), None)
    if not known:
        return {"end_year": guess, "label": f"{guess - 1}–{str(guess)[2:]}", "assumed": True}
    if today <= dt.date.fromisoformat(known["last_day"]):
        return {"end_year": known["end_year"], "label": known["label"], "assumed": False}
    nxt = guess + 1
    return {"end_year": nxt, "label": f"{nxt - 1}–{str(nxt)[2:]}", "assumed": True}


def grade(grad_year, end_year):
    return 8 - (grad_year - end_year)


def grade_name(g):
    if g < 0:
        return "not yet at SFFS"
    if g > 8:
        return "graduated"
    return ORD[g]


def class_info(search, today=None, years=None):
    m = re.search(r"[?&]class=(\d{4})(?:&|$)", search or "")
    g = re.search(r"[?&]grade=(\d)(?:&|$)", search or "")
    t = re.search(r"[?&]today=(\d{4}-\d{2}-\d{2})(?:&|$)", search or "")
    today = today or (dt.date.fromisoformat(t.group(1)) if t else dt.date.today())
    year = school_year(today, years)
    if not m:
        return {"cls": None, "year": year, "grade": None, "gradeName": None, "status": "none", "preview": False, "heading": ""}
    cls = int(m.group(1))
    gr = int(g.group(1)) if g else grade(cls, year["end_year"])
    status = "future" if gr < 0 else "alumni" if gr > 8 else "ok"
    heading = f"{grade_name(gr)} · Class of {cls}" if status == "ok" else f"Class of {cls} · {grade_name(gr)}"
    if g:
        heading += " (preview)"
    return {"cls": cls, "year": year, "grade": gr, "gradeName": grade_name(gr), "status": status, "preview": bool(g), "heading": heading}


if __name__ == "__main__":
    import sys
    print(json.dumps(class_info(sys.argv[1] if len(sys.argv) > 1 else ""), ensure_ascii=False, indent=2))
