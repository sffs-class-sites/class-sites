#!/usr/bin/env python3
"""Validate shared/updates/data.json: shape, dates, references, and no parent personal data.

CLAUDE.md §3 and docs/updates-pipeline.md: the ledger is public (git + Pages), so it may
name school staff and school-domain addresses but never a parent's or student's name,
a home address, a phone number or a personal email. Those stay in the full-text log.
"""
import datetime as dt
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "shared" / "updates" / "data.json"

KINDS = {"event", "deadline", "notice", "volunteer", "letter", "classroom"}
SECTIONS = {"learning", "ask", "homework", "routines", "resources", "specialists"}
GRADES = {"K", "1", "2", "3", "4", "5", "6", "7", "8"}
ALLOWED_EMAIL_DOMAINS = {"sffriendsschool.org", "sfquakers.org"}
# Organisational mailboxes named in the emails that are fine to show (not a person's own address).
ALLOWED_EMAILS = {"friendsatsop@gmail.com"}
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"\(?\b\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b")
# A street number followed by a street name and suffix: home addresses. School and venue
# addresses (250/260 Valencia, 100 Harvard Ave, 65 9th Street) are listed explicitly.
STREET = re.compile(r"\b\d{1,5} [A-Z][a-zA-Z]+ (Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Way|Place|Pl)\b")
KNOWN_PLACES = {"250 Valencia Street", "260 Valencia St", "100 Harvard Ave", "65 9th Street", "14th Street", "Brosnan Street", "Valencia Street", "Lake Street"}


def date(s, where, errors):
    try:
        return dt.date.fromisoformat(s)
    except Exception:
        errors.append(f"{where}: bad date {s!r}")


def walk_text(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from walk_text(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_text(v)


def main():
    data = json.loads(SRC.read_text())
    errors = []
    for k in ("schema", "id", "title", "school_year", "built_through", "streams", "sources", "topics"):
        if k not in data:
            errors.append(f"missing top-level key {k}")
    if errors:
        sys.exit("validate_updates: " + "; ".join(errors))

    sy = data["school_year"]
    for k in ("first_day", "last_day"):
        date(sy[k], f"school_year.{k}", errors)
    date(data["built_through"], "built_through", errors)

    def cof_check(subject, where):
        # Circle of Friends subjects name people; the fetcher reduces them to the phrase and so
        # must anyone editing by hand (docs/updates-pipeline.md, personal data rule).
        if "circle of friends" in subject.lower() and subject != "Circle of Friends":
            errors.append(f"{where}: a Circle of Friends subject must be exactly 'Circle of Friends' (it names people): {subject!r}")

    src_ids = set()
    for s in data["sources"]:
        cof_check(s.get("subject", ""), f"source {s.get('id')}")
        for k in ("id", "stream", "date", "subject"):
            if k not in s:
                errors.append(f"source {s.get('id')}: missing {k}")
        if s["id"] in src_ids:
            errors.append(f"duplicate source id {s['id']}")
        src_ids.add(s["id"])
        if s["stream"] not in data["streams"]:
            errors.append(f"source {s['id']}: unknown stream {s['stream']}")
        date(s["date"], f"source {s['id']}", errors)

    ids = set()
    for t in data["topics"]:
        w = f"topic {t.get('id')}"
        for k in ("id", "kind", "audience", "title", "summary", "updates"):
            if k not in t:
                errors.append(f"{w}: missing {k}")
        if t["id"] in ids:
            errors.append(f"duplicate topic id {t['id']}")
        ids.add(t["id"])
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", t["id"]):
            errors.append(f"{w}: id must be lowercase slug")
        if t["kind"] not in KINDS:
            errors.append(f"{w}: kind {t['kind']!r} not in {sorted(KINDS)}")
        a = t["audience"]
        if not (a in ("all", "lower", "middle") or (isinstance(a, list) and a and set(a) <= GRADES)):
            errors.append(f"{w}: audience must be all|lower|middle or a list of grades, got {a!r}")
        if t["kind"] == "classroom":
            if t.get("section") not in SECTIONS:
                errors.append(f"{w}: classroom topics need a section in {sorted(SECTIONS)}")
            if t.get("section") == "ask" and not t.get("items"):
                errors.append(f"{w}: an 'ask' topic needs items (the questions)")
        elif "section" in t:
            errors.append(f"{w}: only classroom topics carry a section")
        if "pin" in t and not isinstance(t["pin"], bool):
            errors.append(f"{w}: pin must be true or false")
        if "items" in t and not (isinstance(t["items"], list) and all(isinstance(x, str) and x for x in t["items"])):
            errors.append(f"{w}: items must be a list of non-empty strings")
        if "when" in t:
            wd = t["when"]
            if "date" in wd:
                d0 = date(wd["date"], f"{w} when.date", errors)
                if wd.get("end"):
                    d1 = date(wd["end"], f"{w} when.end", errors)
                    if d0 and d1 and d1 < d0:
                        errors.append(f"{w}: when.end before when.date")
            for k in ("start_time", "end_time"):
                if wd.get(k) and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", wd[k]):
                    errors.append(f"{w}: {k} must be HH:MM, got {wd[k]!r}")
        if "deadline" in t:
            date(t["deadline"]["date"], f"{w} deadline", errors)
        if not t["updates"]:
            errors.append(f"{w}: needs at least one update (the email it came from)")
        last = None
        for u in t["updates"]:
            if u.get("source") not in src_ids:
                errors.append(f"{w}: update cites unknown source {u.get('source')!r}")
            d = date(u.get("date", ""), f"{w} update", errors)
            if d and last and d < last:
                errors.append(f"{w}: updates must be in date order")
            last = d or last
            if not u.get("note"):
                errors.append(f"{w}: update without a note")
        for l in t.get("links", []):
            if not (l.get("label") and str(l.get("url", "")).startswith("https://")):
                errors.append(f"{w}: link needs label and https url: {l}")
            if "veracross.com/c/" in l.get("url", ""):
                errors.append(f"{w}: link is a Veracross tracking redirect; store the destination")

    # Personal data sweep over every string in the file.
    for s in walk_text(data):
        for m in EMAIL.findall(s):
            dom = m.split("@")[1].lower().rstrip(".")
            if dom not in ALLOWED_EMAIL_DOMAINS and m.lower().rstrip(".") not in ALLOWED_EMAILS:
                errors.append(f"personal email address in ledger: {m}")
        if PHONE.search(s):
            errors.append(f"phone number in ledger: {PHONE.search(s).group(0)}")
        for m in STREET.finditer(s):
            if m.group(0) not in KNOWN_PLACES:
                errors.append(f"street address in ledger: {m.group(0)!r} (home addresses stay in the log)")
        if "Spanish" not in s and re.search(r"\b(el|la|los|las) \w+ (de|del) \w+\b", s) and re.search(r"[áéíóñ¡¿]", s):
            errors.append(f"looks like Spanish text; the ledger is English only: {s[:60]!r}")

    # The email-log index (written by build/fetch_school_email.py) carries only dates, subjects,
    # the Veracross sender and Docs links; the same sweep applies to it.
    idx_path = SRC.parent / "sources.json"
    if idx_path.exists():
        idx = json.loads(idx_path.read_text())
        fps = set()
        for m in idx.get("messages", []):
            for k in ("message_id", "fingerprint", "stream", "year", "date", "subject", "anchor"):
                if not m.get(k):
                    errors.append(f"sources.json entry missing {k}: {m.get('subject')!r}")
            date(m.get("date", ""), f"sources.json {m.get('subject')!r}", errors)
            if m.get("fingerprint") in fps:
                errors.append(f"sources.json: duplicate fingerprint for {m.get('subject')!r}")
            fps.add(m.get("fingerprint"))
            if m.get("sender") and not m["sender"].endswith("veracross.com"):
                errors.append(f"sources.json: sender is not Veracross: {m['sender']}")
            cof_check(m.get("subject", ""), f"sources.json {m.get('date')}")
            for s in (m.get("subject", ""),):
                if PHONE.search(s):
                    errors.append(f"sources.json: phone number in subject {s!r}")
            if not str(m.get("anchor", "")).startswith("https://docs.google.com/document/d/"):
                errors.append(f"sources.json: anchor is not a Docs link for {m.get('subject')!r}")

    if errors:
        print("validate_updates: FAIL")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print(f"validate_updates: ok ({len(data['topics'])} topics, {len(data['sources'])} sources)")


if __name__ == "__main__":
    main()
