#!/usr/bin/env python3
"""Checks build/pending_emails.py without network: which index entries count as pending,
suggested source ids, and slicing one email out of a log Doc's text export. The ledger and
index here are made up; no real family appears."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "build"))
import pending_emails as p

failures = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    cond or failures.append(msg)


DOC = "https://docs.google.com/document/d/DOC1/edit"
data = {"school_year": {"first_day": "2026-08-26"}, "built_through": "2026-10-29",
        "log": {"docs": {"school": None}},
        "sources": [{"id": "sc-1029", "stream": "school", "date": "2026-10-29", "subject": "[SFFS] Trip (3rd grade)"},
                    {"id": "cb-1029", "stream": "circle-back", "date": "2026-10-29", "subject": "SFFS Circle Back: October 29, 2026"}],
        "topics": []}


def msg(date, subject, anchor, stream="school", doc="DOC1"):
    return {"message_id": anchor, "fingerprint": anchor, "stream": stream, "year": "2026-27", "date": date,
            "subject": subject, "sender": "m@mail3.veracross.com", "doc_id": doc,
            "doc_url": DOC, "anchor": DOC + "#heading=" + anchor, "logged_at": "2026-11-04T21:00:00Z"}


sources = {"docs": {}, "messages": [
    msg("2026-10-29", "[SFFS] Trip", "a1"),                      # matched: ledger subject has a "(3rd grade)" note
    msg("2026-10-29", "SFFS Circle Back: October 29, 2026", "a2", "circle-back"),
    msg("2026-11-03", "[SFFS] Craft Fair", "a3"),                 # pending
    msg("2026-11-03", "[SFFS] Spirit Day", "a4"),                 # pending, same stream and day
    msg("2026-11-04", "SFFS 1st Grade | Room Parent Digest | 11-03-26", "a5", "digest-1"),
]}

pend = p.pending(data, sources)
check([m["anchor"][-2:] for m in pend] == ["a3", "a4", "a5"], "matched emails are not pending; the rest are, oldest first")
taken = {s["id"] for s in data["sources"]}
ids = [p.suggest_id(m, taken) for m in pend]
check(ids == ["sc-1103", "sc-1103b", "d1-1104"], f"suggested ids follow the ledger convention: {ids}")
check(p.suggest_id(msg("2026-10-29", "x", "z"), taken) == "sc-1029b", "an id already in the ledger gets a suffix")

export = ("﻿Nov 3, 2026 · [SFFS] Craft Fair\nSave the date.\n\n\nTables are $40.\n\n"
          "Nov 3, 2026 · [SFFS] Spirit Day\nWear purple.\n\nNov 4, 2026 · Something else\nOther.\n")
entries = p.split_doc(export)
check(entries.get("Nov 3, 2026 · [SFFS] Craft Fair") == "Save the date.\n\nTables are $40.", "an entry is sliced between its heading and the next")
check(entries.get("Nov 3, 2026 · [SFFS] Spirit Day") == "Wear purple.", "the last line before a heading belongs to the earlier entry")
check(p.entry_heading("2026-11-03", "[SFFS] Craft Fair") == "Nov 3, 2026 · [SFFS] Craft Fair", "heading format matches the fetcher's")

got = p.with_text(pend[:2], opener=lambda u: export.encode("utf-8"), log=lambda s: None)
check(got[0]["text"] == "Save the date.\n\nTables are $40." and got[1]["text"] == "Wear purple.", "--text attaches each pending email's text")
calls = []
p.with_text(pend[:2], opener=lambda u: (calls.append(u), export.encode())[1], log=lambda s: None)
check(len(calls) == 1 and calls[0].endswith("/d/DOC1/export?format=txt"), "one export per doc, from the txt export URL")

if failures:
    sys.exit(f"test_pending_emails: {len(failures)} failure(s)")
print("test_pending_emails: ok")
