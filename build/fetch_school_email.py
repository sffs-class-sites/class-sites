#!/usr/bin/env python3
"""Fetch forwarded school emails from the bot's Gmail and log their full text in Google Docs.

  python3 build/fetch_school_email.py                  # IMAP as the bot, write the Docs, update sources.json
  python3 build/fetch_school_email.py --dry-run        # IMAP, parse, classify, resolve links; write nothing
  python3 build/fetch_school_email.py --eml DIR        # parse .eml files instead of IMAP (tests, local runs)
  python3 build/fetch_school_email.py --eml DIR --dry-run --limit 5

Reads (never writes) the bot mailbox `sfquakerbot@gmail.com` over IMAP with an App Password
(BOT_GMAIL_APP_PASSWORD). Every message that came from Veracross, either forwarded by Ahin's
Gmail filter (original headers kept) or by a one-time manual forward ("Fwd:" with a forwarded
block), is classified into a stream, cleaned (Spanish half dropped, HTML flattened, Veracross
tracking links resolved) and appended to that stream's Google Doc for its school year, in the
Drive folder EMAIL_LOG_FOLDER_ID, as a dated Heading 1 plus the text. Docs are written as the
service account (GOOGLE_SERVICE_ACCOUNT_JSON) and shared "anyone with the link can view".

shared/updates/sources.json records every logged email with its Doc deep link, so the embed's
History links can point at the full text; build/build_updates.py merges it into the ledger at
build time. The log docs may contain parent details (docs/updates-pipeline.md); this index keeps
only the sender address, the subject and the date.
"""
import argparse
import datetime as dt
import email
import email.policy
import email.utils
import hashlib
import html
import imaplib
import json
import os
import pathlib
import re
import sys
import time
from html.parser import HTMLParser
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEDGER = ROOT / "shared" / "updates" / "data.json"
SOURCES = ROOT / "shared" / "updates" / "sources.json"
BOT = "sfquakerbot@gmail.com"

ORDINAL = {0: "Kindergarten", 1: "1st Grade", 2: "2nd Grade", 3: "3rd Grade", 4: "4th Grade",
           5: "5th Grade", 6: "6th Grade", 7: "7th Grade", 8: "8th Grade"}
GRADE_WORDS = {
    0: r"kindergarten|\bkinders?\b|\bk\s+(?:families|students|class|team|teachers)\b",
    1: r"\b1st[- ]grade|\bfirst[- ]grade|\b1st graders|\b1[ab]\b",
    2: r"\b2nd[- ]grade|\bsecond[- ]grade|\b2nd graders|\b2[ab]\b",
    3: r"\b3rd[- ]grade|\bthird[- ]grade|\b3rd graders|\b3[ab]\b",
    4: r"\b4th[- ]grade|\bfourth[- ]grade|\b4th graders|\b4[ab]\b",
    5: r"\b5th[- ]grade|\bfifth[- ]grade|\b5th graders",
    6: r"\b6th[- ]grade|\bsixth[- ]grade|\b6th graders",
    7: r"\b7th[- ]grade|\bseventh[- ]grade|\b7th graders",
    8: r"\b8th[- ]grade|\beighth[- ]grade|\b8th graders",
}
GRADE_FROM_ORDINAL = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5, "6th": 6, "7th": 7, "8th": 8,
                      "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
                      "seventh": 7, "eighth": 8, "kindergarten": 0, "k": 0}

SPANISH_MARKERS = re.compile(r"^\s*(para español|versi[oó]n en español|en español|español( abajo)?|"
                             r"\(español\)|spanish( version)?( below)?:?|traducci[oó]n)", re.I)
SPANISH_STOP = {"el", "la", "los", "las", "de", "del", "que", "para", "por", "con", "una", "este",
                "esta", "estudiantes", "familias", "escuela", "gracias", "favor", "nuestra", "nuestro",
                "también", "sobre", "hasta", "más", "será", "están", "como", "pero", "todos"}
RULE_LINE = re.compile(r"^\s*([-_=*~]\s*){4,}$")
FORWARD_BLOCK = re.compile(
    r"-{3,}\s*Forwarded message\s*-{3,}\s*\n(?P<hdr>(?:\s*(?:From|Date|Subject|To|Cc)\s*:.*\n)+)", re.I)
SCHOOL_SENDERS = ("veracross.com", "sffriendsschool.org", "sfquakers.org")
PACIFIC = "America/Los_Angeles"
URL_RE = re.compile(r"https?://[^\s<>()\"']+")


# ---------------------------------------------------------------- HTML to plain paragraphs

class _Text(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol",
             "blockquote", "section", "article", "header", "footer", "hr", "pre"}
    SKIP = {"script", "style", "head", "title"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.href, self.anchor = [], 0, None, []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "a":
            self.href = dict(attrs).get("href")
            self.anchor = []
        elif tag == "li":
            self.out.append("\n- ")
        elif tag == "hr":
            self.out.append("\n\n")
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag == "a":
            text = "".join(self.anchor).strip()
            href = (self.href or "").strip()
            if href.startswith("http") and text and text != href and not text.startswith("http"):
                self.out.append(f"{text} ({href})")
            elif href.startswith("http"):
                self.out.append(href)
            else:
                self.out.append(text)
            self.href, self.anchor = None, []
        elif tag == "li":
            pass  # the next <li> opens its own line
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if self.skip:
            return
        data = re.sub(r"[ \t\r\f\v]+", " ", data.replace("\xa0", " "))
        if self.href is not None:
            self.anchor.append(data)
        else:
            self.out.append(data)


def html_to_text(src):
    p = _Text()
    p.feed(src)
    p.close()
    return tidy("".join(p.out))


def tidy(text):
    """Collapse whitespace: one paragraph per line, blank lines between groups, no trailing space."""
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in text.replace("\r", "").split("\n")]
    out, blank = [], True
    for l in lines:
        if not l:
            if not blank:
                out.append("")
            blank = True
        else:
            out.append(l)
            blank = False
    while out and not out[-1]:
        out.pop()
    return "\n".join(out)


# ---------------------------------------------------------------- language

def looks_spanish(lines):
    words = re.findall(r"[a-záéíóúñü]+", " ".join(lines).lower())
    if len(words) < 12:
        return False
    hits = sum(1 for w in words if w in SPANISH_STOP)
    return hits / len(words) > 0.12


def strip_spanish(text):
    """Drop everything from the first Spanish marker, or from a rule line that a Spanish block follows."""
    lines = text.split("\n")
    for i, l in enumerate(lines):
        if SPANISH_MARKERS.match(l) and looks_spanish(lines[i + 1:i + 25]):
            return tidy("\n".join(lines[:i]))
        if RULE_LINE.match(l) and looks_spanish(lines[i + 1:i + 25]):
            return tidy("\n".join(lines[:i]))
    # No marker: a long Spanish tail after the last English paragraph
    for i in range(len(lines)):
        if looks_spanish(lines[i:]) and lines[i].strip() and not looks_spanish(lines[max(0, i - 6):i]):
            if i > 3 and not looks_spanish(lines[:i]):
                return tidy("\n".join(lines[:i]))
    return tidy(text)


# ---------------------------------------------------------------- links

def is_tracking(url):
    host = urlparse(url).netloc.lower()
    return host.endswith("veracross.com") and re.match(r"^/[ce]/", urlparse(url).path or "") is not None


def http_resolve(url, session=None):
    """Follow a tracking redirect to its destination (no body download). Returns url on failure."""
    import requests
    s = session or requests.Session()
    cur = url
    for _ in range(6):
        try:
            r = s.head(cur, allow_redirects=False, timeout=15,
                       headers={"User-Agent": "sffs-class-sites email log"})
            if r.status_code in (405, 403):
                r = s.get(cur, allow_redirects=False, timeout=15, stream=True,
                          headers={"User-Agent": "sffs-class-sites email log"})
                r.close()
        except Exception:
            return cur if not is_tracking(cur) else url
        loc = r.headers.get("Location")
        if r.status_code in (301, 302, 303, 307, 308) and loc:
            cur = loc if loc.startswith("http") else requests.compat.urljoin(cur, loc)
            if not is_tracking(cur):
                return cur
        else:
            break
    return cur if not is_tracking(cur) else url


def resolve_links(text, resolver, cache=None):
    cache = {} if cache is None else cache

    def sub(m):
        u = m.group(0).rstrip(".,;:!?)")
        tail = m.group(0)[len(u):]
        if is_tracking(u):
            if u not in cache:
                cache[u] = resolver(u)
            return cache[u] + tail
        return m.group(0)
    return URL_RE.sub(sub, text)


# ---------------------------------------------------------------- classification

ORD = r"(?:1st|2nd|3rd|4th|5th|6th|7th|8th|first|second|third|fourth|fifth|sixth|seventh|eighth|kindergarten)"
ORD_LIST = re.compile(rf"\b((?:{ORD}(?:\s*,\s*|\s+and\s+|\s*&\s*|\s*/\s*))+{ORD})\s+grades?\b", re.I)


def grades_mentioned(s):
    s = s.lower()
    found = {g for g, pat in GRADE_WORDS.items() if re.search(pat, s)}
    for m in ORD_LIST.finditer(s):  # "First and Second Grade", "3rd, 4th and 5th grade"
        found |= {GRADE_FROM_ORDINAL[w] for w in re.findall(ORD, m.group(1))}
    return found


def classify(subject, body=""):
    """Return (stream id, grade or None). Stream ids match shared/updates/data.json."""
    s = subject.strip()
    sl = s.lower()
    if re.search(r"\bcircle back\b", sl):
        return "circle-back", None
    if "head's desk" in sl or "heads desk" in sl or "head’s desk" in sl:
        return "head", None
    m = re.search(r"\b(1st|2nd|3rd|4th|5th|6th|7th|8th|k)\s+grade\s*\|\s*room parent digest", sl)
    if m:
        return f"digest-{GRADE_FROM_ORDINAL[m.group(1)]}", GRADE_FROM_ORDINAL[m.group(1)]
    if "room parent digest" in sl and len(grades_mentioned(sl)) == 1:
        g = grades_mentioned(sl).pop()
        return f"digest-{g}", g
    if re.search(r"specialists? newsletter", sl):
        return "specialists", None
    m = re.search(r"\b(1st|2nd|3rd|4th|5th|6th|7th|8th|first|second|third|fourth|fifth|sixth|seventh|eighth|kindergarten)\s+grade newsletter", sl)
    if m:
        g = GRADE_FROM_ORDINAL[m.group(1)]
        return f"teachers-{g}", g
    if sl.startswith("[sffs]"):
        return "school", None
    gs = grades_mentioned(sl)
    if len(gs) == 1:
        g = gs.pop()
        return f"teachers-{g}", g
    if not gs:
        gs = grades_mentioned(body[:300])  # the greeting: "Hello 1st grade families"
        if len(gs) == 1:
            g = gs.pop()
            return f"teachers-{g}", g
    return "school", None


def stream_label(stream, streams=None):
    if streams and stream in streams:
        return streams[stream]["label"]
    kind, _, g = stream.partition("-")
    if g.isdigit():
        name = ORDINAL[int(g)]
        return {"digest": f"{name} Room Parent Digest", "teachers": f"{name} teachers"}.get(kind, stream)
    return {"circle-back": "Circle Back", "head": "From the Head's Desk", "school": "School notices",
            "specialists": "Lower School Specialists Newsletter"}.get(stream, stream)


def school_year_label(d):
    y = d.year if d.month >= 7 else d.year - 1
    return f"{y}-{(y + 1) % 100:02d}"


# ---------------------------------------------------------------- message parsing

def clean_subject(s):
    s = re.sub(r"\s+", " ", s or "").strip()
    while True:
        n = re.sub(r"^(fwd?|fw|re|aw)\s*:\s*", "", s, flags=re.I)
        if n == s:
            return s
        s = n


def parse_forward_date(s):
    """The 'Date:' line of a forwarded block. It carries no zone; the one-time history forward
    (Gmail connector, 2026-11-01) wrote UTC, so a time is read as UTC and converted to Pacific.
    A person's own Gmail forward writes local time, which only shifts the date before 8am;
    build/build_updates.py matches ledger sources within two days anyway."""
    from zoneinfo import ZoneInfo
    s = re.sub(r"\s+", " ", s.strip())
    for fmt in ("%a, %b %d, %Y at %I:%M %p", "%a, %b %d, %Y, %I:%M %p", "%a, %d %b %Y at %H:%M",
                "%b %d, %Y at %I:%M %p"):
        try:
            t = dt.datetime.strptime(s, fmt).replace(tzinfo=dt.timezone.utc)
            return t.astimezone(ZoneInfo(PACIFIC)).date()
        except ValueError:
            pass
    try:
        return dt.datetime.strptime(s, "%a, %b %d, %Y").date()
    except ValueError:
        pass
    try:
        t = email.utils.parsedate_to_datetime(s)
        return t.date()
    except Exception:
        return None


def body_parts(msg):
    """Return (plain, html) decoded strings, either may be ''."""
    plain, htm = [], []
    for part in msg.walk():
        if part.get_content_maintype() != "text" or part.get("Content-Disposition", "").startswith("attachment"):
            continue
        try:
            t = part.get_content()
        except Exception:
            payload = part.get_payload(decode=True) or b""
            t = payload.decode(part.get_content_charset() or "utf-8", "replace")
        (htm if part.get_content_subtype() == "html" else plain).append(t)
    return "\n".join(plain), "\n".join(htm)


def parse_message(raw):
    """raw bytes → dict or None if it is not a school email.

    Handles the two shapes in the bot mailbox: a filter-forwarded copy (original From, Subject
    and Date; Gmail adds X-Forwarded-* headers) and a manual "Fwd:" with a forwarded block."""
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    message_id = (msg.get("Message-ID") or "").strip()
    subject = clean_subject(str(msg.get("Subject") or ""))
    sender = email.utils.parseaddr(str(msg.get("From") or ""))[1].lower()
    date = None
    try:
        date = email.utils.parsedate_to_datetime(msg.get("Date")).date()
    except Exception:
        pass
    plain, htm = body_parts(msg)
    tp = tidy(plain) if plain.strip() else ""
    th = html_to_text(htm) if htm.strip() else ""
    # Newsletters often carry a stub plain part ("view in browser"); take the richer one.
    text = tp if len(tp) >= 0.5 * len(th) else th
    shape, block_date = "filter", None

    fb = FORWARD_BLOCK.search(text)
    if fb:
        shape = "fwd"
        hdr = {}
        for line in fb.group("hdr").split("\n"):
            k, _, v = line.partition(":")
            if k.strip().lower() in ("from", "date", "subject", "to"):
                hdr[k.strip().lower()] = v.strip()
        if "from" in hdr:
            sender = email.utils.parseaddr(hdr["from"])[1].lower() or sender
        if "subject" in hdr:
            subject = clean_subject(hdr["subject"])
        if "date" in hdr:
            block_date = hdr["date"]
            date = parse_forward_date(hdr["date"]) or date
        text = text[fb.end():]
        # drop the "To:" leftovers and anything Gmail put above the block
        text = tidy(text)

    info = {"shape": shape, "header_date": str(msg.get("Date") or ""), "block_date": block_date,
            "plain_len": len(tp), "html_len": len(th), "subject": subject, "sender": sender}
    # A school email: sent by Veracross or the school (filter-forwarded copies keep the original
    # From), or forwarded by a person into the bot mailbox (a "Fwd:" with a forwarded block).
    if not (sender.endswith(SCHOOL_SENDERS) or shape == "fwd"
            or "veracross.com" in (msg.get("X-Forwarded-For") or "")):
        info["rejected"] = "not a school email, not forwarded"
        REJECTED.append(info)
        return None
    if not date:
        info["rejected"] = "no date"
        REJECTED.append(info)
        return None
    text = strip_spanish(text)
    return {"message_id": message_id, "sender": sender, "subject": subject, "date": date, "text": text, "info": info}


REJECTED = []  # parse_message() notes here why a message was not taken (for --debug)


def fingerprint(date, subject):
    key = f"{date}|{re.sub(r'[^a-z0-9]+', ' ', subject.lower()).strip()}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


# ---------------------------------------------------------------- IMAP

def imap_messages(password, since, user=BOT, folder='"[Gmail]/All Mail"'):
    """Yield raw messages in the bot mailbox dated on or after `since`. Read-only; nothing is marked."""
    box = imaplib.IMAP4_SSL("imap.gmail.com")
    box.login(user, password)
    box.select(folder, readonly=True)
    typ, data = box.uid("search", None, f'(SINCE {since.strftime("%d-%b-%Y")})')
    uids = data[0].split() if typ == "OK" else []
    for i in range(0, len(uids), 20):
        chunk = b",".join(uids[i:i + 20]).decode()
        typ, parts = box.uid("fetch", chunk, "(BODY.PEEK[])")
        if typ != "OK":
            continue
        for p in parts:
            if isinstance(p, tuple) and len(p) == 2:
                yield p[1]
    box.logout()


# ---------------------------------------------------------------- Google Docs

class Docs:
    DOCS = "https://docs.googleapis.com/v1/documents"
    DRIVE = "https://www.googleapis.com/drive/v3/files"

    def __init__(self, key_json, folder_id):
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
        creds = service_account.Credentials.from_service_account_info(
            json.loads(key_json), scopes=["https://www.googleapis.com/auth/documents",
                                          "https://www.googleapis.com/auth/drive"])
        self.s = AuthorizedSession(creds)
        self.folder = folder_id

    def _check(self, r, what):
        if r.status_code >= 400:
            body = r.text[:600]
            if "has not been used in project" in body or "is disabled" in body:
                sys.exit(f"{what}: the Google Docs or Drive API is not enabled in the bot's Cloud project. "
                         f"Enable it at https://console.cloud.google.com/apis/library (Google Docs API) and rerun.\n{body}")
            sys.exit(f"{what}: HTTP {r.status_code}\n{body}")
        return r.json() if r.text else {}

    def find_or_create(self, title):
        q = (f"name = '{title}' and '{self.folder}' in parents and trashed = false "
             f"and mimeType = 'application/vnd.google-apps.document'")
        r = self._check(self.s.get(self.DRIVE, params={"q": q, "fields": "files(id,name)",
                                                        "supportsAllDrives": "true"}), "Drive list")
        if r.get("files"):
            return r["files"][0]["id"], False
        r = self._check(self.s.post(self.DRIVE, params={"supportsAllDrives": "true"}, json={
            "name": title, "mimeType": "application/vnd.google-apps.document",
            "parents": [self.folder]}), "Drive create")
        doc_id = r["id"]
        self._check(self.s.post(f"{self.DRIVE}/{doc_id}/permissions", json={"role": "reader", "type": "anyone"}),
                    "Drive share")
        return doc_id, True

    def get(self, doc_id):
        return self._check(self.s.get(f"{self.DOCS}/{doc_id}"), "Docs get")

    def heading_ids(self, doc):
        out = {}
        for el in doc.get("body", {}).get("content", []):
            p = el.get("paragraph")
            if not p:
                continue
            st = p.get("paragraphStyle", {})
            if st.get("namedStyleType", "").startswith("HEADING") and st.get("headingId"):
                text = "".join(r.get("textRun", {}).get("content", "") for r in p.get("elements", [])).strip()
                out.setdefault(text, st["headingId"])
        return out

    def append(self, doc_id, heading, body):
        doc = self.get(doc_id)
        end = doc["body"]["content"][-1]["endIndex"] - 1
        empty = end <= 1
        lead = "" if empty else "\n"
        text = f"{lead}{heading}\n{body}\n"
        h0 = end + len(lead)
        h1 = h0 + len(heading)
        b0 = h1 + 1
        b1 = b0 + len(body) + 1
        reqs = [
            {"insertText": {"location": {"index": end}, "text": text}},
            {"updateParagraphStyle": {"range": {"startIndex": h0, "endIndex": h1 + 1},
                                      "paragraphStyle": {"namedStyleType": "HEADING_1"}, "fields": "namedStyleType"}},
            {"updateParagraphStyle": {"range": {"startIndex": b0, "endIndex": b1},
                                      "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"}, "fields": "namedStyleType"}},
            {"updateTextStyle": {"range": {"startIndex": b0, "endIndex": b1},
                                 "textStyle": {"bold": False, "italic": False}, "fields": "bold,italic"}},
        ]
        self._check(self.s.post(f"{self.DOCS}/{doc_id}:batchUpdate", json={"requests": reqs}), "Docs append")
        return self.heading_ids(self.get(doc_id)).get(heading)


# ---------------------------------------------------------------- main

def load_sources():
    if SOURCES.exists():
        return json.loads(SOURCES.read_text())
    return {"schema": 1, "note": "Generated by build/fetch_school_email.py: one entry per school email "
            "logged in Google Docs, with its deep link. Do not edit by hand.", "docs": {}, "messages": []}


def entry_heading(m):
    return f"{m['date'].isoformat()} {m['subject']}"[:200]


def run(messages, docs, sources, streams, dry_run, resolver, log=print):
    seen_ids = {m["message_id"] for m in sources["messages"] if m.get("message_id")}
    seen_fp = {m["fingerprint"] for m in sources["messages"]}
    cache, added, skipped = {}, [], 0
    fullest = {}
    for m in messages:  # a resend within one run: keep the fuller copy
        fp = fingerprint(m["date"], m["subject"])
        if fp not in fullest or len(m["text"]) > len(fullest[fp]["text"]):
            fullest[fp] = m
    skipped += len(messages) - len(fullest)
    for m in sorted(fullest.values(), key=lambda x: (x["date"], x["subject"])):
        if m["message_id"] in seen_ids:
            continue
        fp = fingerprint(m["date"], m["subject"])
        if fp in seen_fp:
            skipped += 1
            log(f"  skip (already logged, resend) {m['date']} {m['subject']}")
            continue
        stream, _ = classify(m["subject"], m["text"])
        year = school_year_label(m["date"])
        text = resolve_links(m["text"], resolver, cache)
        key = f"{stream}@{year}"
        title = f"{stream_label(stream, streams)} {year} (email log)"
        rec = {"message_id": m["message_id"], "fingerprint": fp, "stream": stream, "year": year,
               "date": m["date"].isoformat(), "subject": m["subject"], "sender": m["sender"]}
        if dry_run:
            log(f"  would log → {title}: {m['date']} {m['subject']}  ({len(text)} chars)")
            added.append(rec)
            continue
        if key not in sources["docs"]:
            doc_id, created = docs.find_or_create(title)
            sources["docs"][key] = {"title": title, "id": doc_id,
                                    "url": f"https://docs.google.com/document/d/{doc_id}/edit"}
            log(f"  {'created' if created else 'found'} doc {title}")
        d = sources["docs"][key]
        hid = docs.append(d["id"], entry_heading(m), text)
        rec.update({"doc_id": d["id"], "doc_url": d["url"],
                    "anchor": f"{d['url']}#heading={hid}" if hid else d["url"],
                    "logged_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
        sources["messages"].append(rec)
        seen_ids.add(m["message_id"]); seen_fp.add(fp)
        added.append(rec)
        log(f"  logged → {title}: {m['date']} {m['subject']}")
        time.sleep(0.5)  # Docs API write quota is per minute; be gentle
    return added, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eml", help="directory of .eml files instead of IMAP")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--since", help="YYYY-MM-DD; default 60 days before the school year's first day")
    ap.add_argument("--summary", help="write a markdown summary here (GitHub step summary)")
    ap.add_argument("--debug", action="store_true", help="print shape, dates and part sizes per message, and why others were rejected")
    a = ap.parse_args()

    ledger = json.loads(LEDGER.read_text())
    streams = ledger["streams"]
    first = dt.date.fromisoformat(ledger["school_year"]["first_day"])
    since = dt.date.fromisoformat(a.since) if a.since else first - dt.timedelta(days=60)

    if a.eml:
        raws = [p.read_bytes() for p in sorted(pathlib.Path(a.eml).glob("*.eml"))]
    else:
        pw = os.environ.get("BOT_GMAIL_APP_PASSWORD")
        if not pw:
            sys.exit("BOT_GMAIL_APP_PASSWORD is not set (the bot's Gmail App Password).")
        raws = list(imap_messages(pw, since))
    print(f"{len(raws)} messages in the mailbox since {since}")
    messages = [m for m in (parse_message(r) for r in raws) if m and m["date"] >= since]
    print(f"{len(messages)} are school emails")
    if a.debug:
        for m in messages:
            i = m["info"]
            print(f"  [{i['shape']}] {m['date']} hdr={i['header_date']!r} block={i['block_date']!r} "
                  f"plain={i['plain_len']} html={i['html_len']} {m['subject'][:60]}")
        for i in REJECTED:
            print(f"  rejected ({i['rejected']}) [{i['shape']}]: from={i['sender']} {i['subject'][:60]}")
    if a.limit:
        messages = messages[:a.limit]

    docs = None
    if not a.dry_run:
        key, folder = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"), os.environ.get("EMAIL_LOG_FOLDER_ID")
        if not key or not folder:
            sys.exit("GOOGLE_SERVICE_ACCOUNT_JSON and EMAIL_LOG_FOLDER_ID are needed to write the log.")
        docs = Docs(key, folder)

    sources = load_sources()
    resolver = http_resolve if not a.eml or not a.dry_run else (lambda u: u)
    if a.eml and a.dry_run:
        resolver = http_resolve if os.environ.get("RESOLVE_LINKS") else (lambda u: u)
    added, skipped = run(messages, docs, sources, streams, a.dry_run, resolver)

    if not a.dry_run and added:
        SOURCES.write_text(json.dumps(sources, indent=1, ensure_ascii=False) + "\n")
    verb = "Would log" if a.dry_run else "Logged"
    lines = [f"## Email log", f"{verb} {len(added)} email(s); {skipped} resend(s) skipped; "
             f"{len(sources['messages'])} in the index.", ""]
    for r in added:
        lines.append(f"- {r['date']} · {stream_label(r['stream'], streams)} · {r['subject']}"
                     + (f" · [full text]({r['anchor']})" if r.get("anchor") else ""))
    print("\n".join(lines))
    if a.summary:
        pathlib.Path(a.summary).write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
