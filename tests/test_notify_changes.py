#!/usr/bin/env python3
"""Checks build/notify_changes.py without network: the diff of two ledgers and the wording
of the email. Made-up topics; no real family appears."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "build"))
import notify_changes as n

failures = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    cond or failures.append(msg)


def topic(i, title, kind="event", **kw):
    t = {"id": i, "kind": kind, "audience": "all", "title": title, "summary": "x",
         "updates": [{"source": "sc-1103", "date": "2026-11-03", "note": "Announced."}]}
    t.update(kw)
    return t


old = {"sources": [{"id": "cb-1029", "stream": "circle-back", "date": "2026-10-29", "subject": "Circle Back"}],
       "topics": [topic("fair", "Craft Fair", when={"date": "2026-12-12", "start_time": "10:00", "end_time": "14:00", "location": "SFFS"})]}
new = {"sources": old["sources"] + [{"id": "sc-1103", "stream": "school", "date": "2026-11-03", "subject": "[SFFS] Craft Fair",
                                     "doc_anchor": "https://docs.google.com/document/d/D/edit#heading=h.1"}],
       "topics": [topic("fair", "Craft Fair", when={"date": "2026-12-12", "start_time": "10:00", "end_time": "14:00", "location": "SFFS"}),
                  topic("tee", "Spirit tee", kind="deadline", audience=["1", "3"], deadline={"date": "2026-11-10", "what": "Order"})]}
new["topics"][0]["updates"].append({"source": "sc-1103", "date": "2026-11-03", "note": "Table sign-ups open."})
idx_old = {"messages": []}
idx_new = {"messages": [{"fingerprint": "f1", "date": "2026-11-03", "subject": "[SFFS] Craft Fair",
                         "anchor": "https://docs.google.com/document/d/D/edit#heading=h.1"}]}

d = n.diff(old, new, idx_old, idx_new)
check([t["id"] for t in d["added"]] == ["tee"], "a topic not in the old ledger is new")
check(d["updated"] and d["updated"][0][1] == "Table sign-ups open.", "an updated topic reports its new update note")
check([s["id"] for s in d["processed"]] == ["sc-1103"], "the emails read are the new ledger sources")

subject, body = n.compose(d, "https://example.test/class-sites/")
check(subject == "Class sites: 1 new topic, 1 updated on the Updates page", f"subject counts: {subject!r}")
check("Spirit tee · Order by Tue Nov 10 · for 1st grade, 3rd grade" in body, "deadline topics say what is due when, and for whom")
check("Craft Fair · Sat Dec 12 10 am–2 pm, SFFS · for everyone" in body, "events say date, time and place")
check("?class=2034&tab=changed" in body, "links to the What changed tab")
check("full text: https://docs.google.com/document/d/D/edit#heading=h.1" in body, "each email read links to its full text")

s2, b2 = n.compose(n.diff(new, new, idx_old, idx_new), "https://example.test/")
check(s2 == "Class sites: 1 new school email logged" and "extraction step reads them next" in b2, "index-only change: logged, not yet read")
s3, _ = n.compose(n.diff(new, new, idx_new, idx_new), "https://example.test/")
check(s3 is None, "no change, no email")
only_src = {"sources": new["sources"], "topics": old["topics"]}
s4, _ = n.compose(n.diff(old, only_src, idx_new, idx_new), "https://example.test/")
check(s4 == "Class sites: 1 email read, nothing new for the Updates page", f"an email read with no topic change still reports: {s4!r}")

if failures:
    sys.exit(f"test_notify_changes: {len(failures)} failure(s)")
print("test_notify_changes: ok")
