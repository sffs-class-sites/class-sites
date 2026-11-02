#!/usr/bin/env python3
"""Checks build/fetch_school_email.py without network: both forwarded shapes, the stream
classifier against every subject in the ledger, Spanish stripping, link resolution, dedupe.
Fixture emails are made up here; no real family appears."""
import datetime as dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "build"))
import fetch_school_email as f

ROOT = pathlib.Path(__file__).resolve().parents[1]
failures = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    cond or failures.append(msg)


def eml(subject, body, html=None, sender="SFFS <m@mail3.veracross.com>", date="Thu, 29 Oct 2026 12:05:00 -0700",
        mid="<abc@mail3.veracross.com>", extra=""):
    if html is None:
        return (f"From: {sender}\nTo: ahin@example.test\nSubject: {subject}\nDate: {date}\nMessage-ID: {mid}\n"
                f"{extra}Content-Type: text/plain; charset=utf-8\n\n{body}").encode()
    return (f"From: {sender}\nTo: ahin@example.test\nSubject: {subject}\nDate: {date}\nMessage-ID: {mid}\n{extra}"
            f"MIME-Version: 1.0\nContent-Type: multipart/alternative; boundary=\"b\"\n\n--b\n"
            f"Content-Type: text/plain; charset=utf-8\n\n{body}\n--b\nContent-Type: text/html; charset=utf-8\n\n{html}\n--b--\n").encode()


# --- filter-forwarded copy: original headers kept, Gmail adds X-Forwarded-For
m = f.parse_message(eml("SFFS Circle Back: October 29, 2026", "The Week Ahead\nThursday: Picture day.",
                        extra="X-Forwarded-For: ahin@example.test sfquakerbot@gmail.com\n"))
check(m and m["subject"] == "SFFS Circle Back: October 29, 2026" and m["date"] == dt.date(2026, 10, 29)
      and m["sender"] == "m@mail3.veracross.com", "filter-forwarded copy keeps original subject, date, sender")

# --- manual Fwd: with a forwarded block (the one-time history forward)
fwd = ("Here you go.\n\n---------- Forwarded message ---------\nFrom: SFFS <m@mail1.veracross.com>\n"
       "Date: Tue, Sep 22, 2026 at 4:10 PM\nSubject: SFFS 1st Grade | Room Parent Digest | 09-22-26\n"
       "To: <ahin@example.test>\n\n\nGrade news and reminders\n- Library day is Monday.\n")
m = f.parse_message(eml("Fwd: SFFS 1st Grade | Room Parent Digest | 09-22-26", fwd, sender="Ahin <ahin@example.test>",
                        date="Sun, 1 Nov 2026 10:00:00 -0800", mid="<fwd1@mail.gmail.com>"))
check(m and m["date"] == dt.date(2026, 9, 22) and m["sender"] == "m@mail1.veracross.com"
      and m["subject"].startswith("SFFS 1st Grade | Room Parent Digest"), "manual Fwd: takes date, sender, subject from the block")
check(m and m["text"].startswith("Grade news and reminders") and "Forwarded message" not in m["text"],
      "manual Fwd: body starts after the block")

# --- not a school email
check(f.parse_message(eml("Security alert", "New sign-in.", sender="Google <no-reply@accounts.google.com>")) is None,
      "a non-Veracross email is ignored")

# --- HTML flattening: paragraphs, lists, links
h = ("<html><body><h2>The Week Ahead</h2><p>Picture day is <b>Friday</b>.</p><ul><li>Bring a smile</li>"
     "<li>See the <a href=\"https://www.sfquakers.org/calendar\">calendar</a></li></ul>"
     "<hr><p>Second part</p></body></html>")
m = f.parse_message(eml("[SFFS] Picture Day", "", html=h))
t = m["text"]
check("The Week Ahead\n\nPicture day is Friday." in t and "- Bring a smile\n- See the" in t
      and "calendar (https://www.sfquakers.org/calendar)" in t and "Second part" in t, "HTML becomes paragraphs, bullets and labelled links")

# --- Spanish stripping
sp = ("Please sign up by Monday.\n\nThank you,\nThe office\n\nPara español:\n\nPor favor regístrese antes del lunes. "
      "Gracias a todas las familias de la escuela por su apoyo este año y para los estudiantes.\n\nLa oficina")
check(f.strip_spanish(sp) == "Please sign up by Monday.\n\nThank you,\nThe office", "Spanish after 'Para español' is dropped")
rule = ("Hello families, the field trip is Tuesday.\n\n----------\n\nHola familias, la excursión es el martes. "
        "Gracias por su apoyo a los estudiantes de la escuela y para las familias que ayudan con este viaje.")
check(f.strip_spanish(rule) == "Hello families, the field trip is Tuesday.", "Spanish after a rule line is dropped")
eng = "Line one about the Annual Fund.\n\n----------\n\nLine two about the gala and the auction for the school."
check(f.strip_spanish(eng) == eng, "English after a rule line is kept")

# --- link resolution
txt = "Sign up: https://www.veracross.com/c/abc123?x=1. Portal: https://portals.veracross.com/sffs/parent."
out = f.resolve_links(txt, lambda u: "https://forms.gle/xyz")
check(out == "Sign up: https://forms.gle/xyz. Portal: https://portals.veracross.com/sffs/parent.",
      "tracking links resolve, trailing punctuation and portal links untouched")

# --- classifier against every subject in the ledger
ledger = json.loads((ROOT / "shared" / "updates" / "data.json").read_text())
patterned = {"circle-back", "head", "digest-1", "digest-3", "specialists"}
bad = []
for s in ledger["sources"]:
    for subj in s["subject"].split(" / "):
        got, _ = f.classify(subj)
        exp = s["stream"]
        if exp in patterned or subj.lower().endswith("grade newsletter: " + subj.lower().split(": ")[-1]) and exp.startswith("teachers"):
            if got != exp:
                bad.append(f"{subj!r}: {got} != {exp}")
        elif got not in ("school", "teachers-1", "teachers-3", "teachers-2"):
            bad.append(f"{subj!r}: {got}")
check(not bad, "every ledger subject classifies to its stream (patterned) or to a grade or school doc: " + "; ".join(bad[:5]))
check(f.classify("First and Second Grade Ages & Stages") == ("school", None), "two grades in the subject → school")
check(f.classify("sharing in 3A") == ("teachers-3", 3), "a section name picks the grade")
check(f.classify("Picture Day Volunteers Needed!", "Hello 1st grade families, we need two parents.") == ("teachers-1", 1),
      "no grade in the subject → one grade in the body")
check(f.classify("Welcome to First Grade!") == ("teachers-1", 1), "grade words in a one-off")
check(f.school_year_label(dt.date(2026, 8, 4)) == "2026-27" and f.school_year_label(dt.date(2027, 5, 3)) == "2026-27",
      "school year label spans August to June")

# --- run(): dedupe by message id and by resend fingerprint; anchors from a fake Docs
class FakeDocs:
    def __init__(self): self.appended = []
    def find_or_create(self, title): return "DOC" + str(len(title)), True
    def append(self, doc_id, heading, body): self.appended.append((doc_id, heading, body)); return "h.abc"

msgs = [f.parse_message(eml("SFFS Circle Back: October 29, 2026", "A", mid="<1@v>")),
        f.parse_message(eml("SFFS Circle Back: October 29, 2026", "A fixed typo", mid="<2@v>")),
        f.parse_message(eml("[SFFS] Forms", "B", mid="<3@v>", date="Mon, 5 Oct 2026 09:00:00 -0700"))]
src = f.load_sources.__wrapped__() if hasattr(f.load_sources, "__wrapped__") else {"schema": 1, "docs": {}, "messages": []}
fd = FakeDocs()
f.time.sleep = lambda s: None
added, skipped = f.run(msgs, fd, src, ledger["streams"], False, lambda u: u, log=lambda *a: None)
check(len(added) == 2 and skipped == 1, "a resend with the same subject and date is logged once")
check(all(r["anchor"].endswith("#heading=h.abc") for r in added) and set(src["docs"]) == {"circle-back@2026-27", "school@2026-27"},
      "entries carry the doc anchor; one doc per stream per year")
check(fd.appended[0][1] == "2026-10-05 [SFFS] Forms" and fd.appended[1][2] == "A", "heading is the date and subject; body is the text")
added2, _ = f.run(msgs, fd, src, ledger["streams"], False, lambda u: u, log=lambda *a: None)
check(added2 == [] and len(fd.appended) == 2, "a second run logs nothing new")
check(all("sender" in r and "@" in r["sender"] and r["sender"].endswith("veracross.com") for r in added),
      "the index stores only the Veracross sender")

# --- build-time merge of the index into the ledger
import build_updates as b
idx = {"docs": {"circle-back@2026-27": {"url": "https://docs.google.com/document/d/D1/edit"}},
       "messages": [
           {"date": "2026-10-29", "subject": "SFFS Circle Back: October 29, 2026", "doc_url": "https://docs.google.com/document/d/D1/edit", "anchor": "https://docs.google.com/document/d/D1/edit#heading=h.1"},
           {"date": "2026-08-25", "subject": "Join Our First Grade Room Parent Team", "doc_url": "u", "anchor": "u#heading=h.2"},
           {"date": "2026-09-04", "subject": "Hello from your room parents!", "doc_url": "u", "anchor": "u#heading=h.3"},
           {"date": "2026-09-04", "subject": "Something else entirely", "doc_url": "u", "anchor": "u#heading=h.9"}]}
data = json.loads(json.dumps(ledger))
n = b.apply_sources(data, idx)
by = {s["id"]: s for s in data["sources"]}
cb = [s for s in data["sources"] if s["date"] == "2026-10-29" and s["stream"] == "circle-back"][0]
check(cb["doc_anchor"].endswith("#heading=h.1"), "exact subject on the same date links the ledger source")
combo = [s for s in data["sources"] if s["subject"].startswith("Join Our First Grade")][0]
check(combo["doc_anchor"].endswith("h.2"), "one part of a combined 'A / B' subject links")
hello = [s for s in data["sources"] if s["subject"].startswith("Hello from your room parents")][0]
check(hello["doc_anchor"].endswith("h.3"), "a ledger subject with a trailing note links by prefix")
check(n == 3 and data["log"]["docs"]["circle-back"].endswith("/D1/edit") and data["log"]["docs"]["head"] is None,
      "three linked; log.docs filled per stream for the current year only")

print(f"test_fetch_school_email: {'ok' if not failures else str(len(failures)) + ' failure(s)'}")
sys.exit(1 if failures else 0)
