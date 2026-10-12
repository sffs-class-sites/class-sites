#!/usr/bin/env python3
"""Write the plain-English PR comment: what changes on the sites, with screenshot links.

Compares two copies of shared/important-dates/data.json (the PR's base and head),
matching events by their stored uid. Prints Markdown to stdout.

  python3 tests/pr_summary.py --base base.json --head shared/important-dates/data.json \
      [--files "changed paths, one per line"] [--run-url URL]

Screenshot links come from SHOT_<LABEL> environment variables (e.g. SHOT_DESKTOP),
set by the workflow from each upload's artifact-url.
"""
import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "build"))
from build_important_dates import fmt_range  # same date wording as the page

MARKER = "<!-- sffs-pr-summary -->"
SHOTS = [("desktop", "Desktop"), ("tablet", "Tablet"), ("phone", "Phone"), ("phone-tall", "Phone, taller box")]
PAGE_FIELDS = {"title": "page title", "subtitle": "subtitle", "source": "link to the original PDF",
               "star_note": "asterisk note", "footer": "footer text", "categories": "category names"}


def load(path):
    p = pathlib.Path(path)
    return json.loads(p.read_text()) if p.exists() and p.read_text().strip() else {}


def when(e):
    return fmt_range(e)


def label(e, data):
    return e.get("badge") or data.get("categories", {}).get(e["cat"], e["cat"])


def quote(s):
    return f"“{s}”" if s else "(none)"


def changes(old, new, old_data, new_data):
    out = []
    if (old["date"], old.get("end")) != (new["date"], new.get("end")):
        out.append(f"moved from {when(old)} to {when(new)}")
    if old["title"] != new["title"]:
        out.append(f"renamed from {quote(old['title'])}")
    if label(old, old_data) != label(new, new_data):
        out.append(f"label changed from {quote(label(old, old_data))} to {quote(label(new, new_data))}")
    if (old.get("details") or "") != (new.get("details") or ""):
        out.append(f"details changed from {quote(old.get('details'))} to {quote(new.get('details'))}")
    if bool(old.get("star")) != bool(new.get("star")):
        out.append("now marked “no enrichment classes”" if new.get("star") else "no longer marked “no enrichment classes”")
    return out


def summarize(base, head, files, run_url):
    old = {e["uid"]: e for e in base.get("events", []) if e.get("uid")}
    new = {e["uid"]: e for e in head.get("events", []) if e.get("uid")}
    added = sorted((new[u] for u in new.keys() - old.keys()), key=lambda e: e["date"])
    removed = sorted((old[u] for u in old.keys() - new.keys()), key=lambda e: e["date"])
    changed = [(old[u], new[u], c) for u in sorted(old.keys() & new.keys(), key=lambda u: new[u]["date"])
               if (c := changes(old[u], new[u], base, head))]
    page = [name for k, name in PAGE_FIELDS.items() if base.get(k) != head.get(k)] if base else []

    lines = [MARKER, "### What this PR changes on the class sites", "", "**Important Dates**", ""]
    if not base:
        lines.append(f"New calendar with {len(new)} events.")
    elif not (added or removed or changed or page):
        lines.append("No dates or page text change.")
    for e in added:
        lines.append(f"- **Added:** {e['title']}, {when(e)} ({label(e, head)})")
    for o, n, c in changed:
        lines.append(f"- **Changed:** {n['title']}, {when(n)}: " + "; ".join(c))
    for e in removed:
        lines.append(f"- **Removed:** {e['title']}, {when(e)}. Families who already added it keep it in their calendars.")
    if page:
        lines.append("- **Page text changed:** " + ", ".join(page))

    # Same date and title under a new uid means families who re-import get a duplicate.
    gone = {(e["date"], e["title"]) for e in removed}
    for e in added:
        if (e["date"], e["title"]) in gone:
            lines += ["", f"> ⚠️ **{e['title']}** ({when(e)}) was removed and re-added with a new ID. "
                          "Families who already added it will get it twice. Keep the old `uid` unless that is intended."]

    shots = [(name, os.environ.get(f"SHOT_{key.upper().replace('-', '_')}")) for key, name in SHOTS]
    if any(url for _, url in shots):
        lines += ["", "**Screenshots of this PR's build** (open while logged in to GitHub; links expire after 90 days)", "",
                  " · ".join(f"[{name}]({url})" for name, url in shots if url)]

    other = [f for f in files if f and f != "shared/important-dates/data.json"]
    if other:
        lines += ["", "<details><summary>Other files changed</summary>", ""] + [f"- `{f}`" for f in other] + ["", "</details>"]
    if run_url:
        lines += ["", f"[Checks and logs for this run]({run_url})"]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--files", default="")
    ap.add_argument("--run-url", default="")
    a = ap.parse_args()
    sys.stdout.write(summarize(load(a.base), load(a.head), a.files.splitlines(), a.run_url))


if __name__ == "__main__":
    main()
