#!/usr/bin/env python3
"""List the school emails that are in the email-log index but not yet in the Updates ledger,
and (with --text) fetch each one's cleaned text from its log Doc. This is the first step of
the extraction routine (docs/extraction-routine.md): what is new since the ledger was last
updated, and what it says.

  python3 build/pending_emails.py            # one line per pending email
  python3 build/pending_emails.py --text     # Markdown: each email with its full text
  python3 build/pending_emails.py --json out.json

An index entry is "pending" when build/build_updates.py cannot match it to a ledger source
(same date within two days, same subject or a part/prefix of a combined subject). The
extraction step adds a ledger source for every email it processes, even one that changes
no topic, so each email is pending exactly once.

The text comes from the log Doc's plain-text export (the docs are shared "anyone with the
link can view"); the entry is the part between its own heading, `Mon D, YYYY · <subject>`,
and the next heading. The text may contain parent names and addresses: it is read here and
never written into the repo.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_updates import apply_sources  # the same matching the build uses

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "shared" / "updates" / "data.json"
SOURCES = ROOT / "shared" / "updates" / "sources.json"

# Ledger source ids are <stream prefix>-MMDD (sc-1029, cb-1029, d1-1006, t3-0820, sp-0925),
# with b, c... appended when a stream has several emails on one day (sc-0908b).
PREFIX = {"circle-back": "cb", "head": "hd", "digest-1": "d1", "digest-3": "d3", "school": "sc",
          "pga": "pga", "teachers-1": "t1", "teachers-3": "t3", "specialists": "sp"}
HEADING = re.compile(r"^(?:﻿)?([A-Z][a-z]{2} \d{1,2}, \d{4}) · (.+?)\s*$")


def entry_heading(date, subject):
    d = dt.date.fromisoformat(date)
    return f"{d:%b} {d.day}, {d.year} · {subject}"[:160]


def pending(data, sources):
    """Index entries with no ledger source, oldest first."""
    data = json.loads(json.dumps(data))  # apply_sources writes doc links into the ledger copy
    apply_sources(data, sources)
    used = {s.get("doc_anchor") for s in data["sources"] if s.get("doc_anchor")}
    out = [m for m in sources.get("messages", []) if m.get("anchor") and m["anchor"] not in used]
    out.sort(key=lambda m: (m["date"], m.get("logged_at", "")))
    return out


def suggest_id(m, taken):
    base = f"{PREFIX.get(m['stream'], m['stream'])}-{m['date'][5:7]}{m['date'][8:10]}"
    sid = base
    for suffix in "bcdefgh":
        if sid not in taken:
            break
        sid = base + suffix
    taken.add(sid)
    return sid


def split_doc(text):
    """{heading: entry text} for a log Doc's plain-text export."""
    entries, cur = {}, None
    for line in text.splitlines():
        hm = HEADING.match(line)
        if hm:
            cur = f"{hm.group(1)} · {hm.group(2)}"
            entries[cur] = []
        elif cur is not None:
            entries[cur].append(line)
    # The export double-spaces paragraphs; collapse runs of blank lines.
    return {h: re.sub(r"\n{3,}", "\n\n", "\n".join(ls)).strip() for h, ls in entries.items()}


def fetch_doc_text(doc_id, opener=None):
    url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
    opener = opener or (lambda u: urllib.request.urlopen(u, timeout=60).read())
    return opener(url).decode("utf-8-sig", errors="replace")


def with_text(msgs, opener=None, log=print):
    cache = {}
    for m in msgs:
        if m["doc_id"] not in cache:
            try:
                cache[m["doc_id"]] = split_doc(fetch_doc_text(m["doc_id"], opener))
            except Exception as e:  # noqa: BLE001 - report and carry on with the others
                log(f"could not read doc {m['doc_id']}: {e}")
                cache[m["doc_id"]] = {}
        entries = cache[m["doc_id"]]
        h = entry_heading(m["date"], m["subject"])
        m["text"] = entries.get(h)
        if m["text"] is None:  # the heading was cut at 160 chars, or the export trimmed spaces
            for k, v in entries.items():
                if k.startswith(h[:80]):
                    m["text"] = v
                    break
    return msgs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", action="store_true", help="fetch each email's text from its log Doc")
    ap.add_argument("--json", help="write the list (with text if --text) to this file")
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--sources", default=str(SOURCES))
    a = ap.parse_args()
    data = json.loads(pathlib.Path(a.data).read_text())
    sources = json.loads(pathlib.Path(a.sources).read_text()) if pathlib.Path(a.sources).exists() else {"messages": []}
    msgs = pending(data, sources)
    taken = {s["id"] for s in data["sources"]}
    for m in msgs:
        m["suggested_id"] = suggest_id(m, taken)
    if a.text:
        with_text(msgs, log=lambda s: print(s, file=sys.stderr))
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(msgs, indent=1, ensure_ascii=False))
    if not msgs:
        print("No pending emails: every indexed email has a ledger source.")
        return
    print(f"{len(msgs)} pending email(s), built_through {data['built_through']}:\n")
    for m in msgs:
        print(f"- {m['date']} · {m['stream']} · {m['subject']} · id {m['suggested_id']} · {m['anchor']}")
        if a.text:
            print()
            print(m["text"] if m.get("text") else "  (text not found in the doc export)")
            print("\n---\n")


if __name__ == "__main__":
    main()
