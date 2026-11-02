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
                "también", "sobre", "hasta", "más", "será", "están", "como", "pero", "todos", "es", "en",
                "un", "se", "su", "sus", "al", "les", "nos", "año", "día", "hola", "queridas", "queridos"}
ENGLISH_STOP = {"the", "and", "of", "to", "for", "our", "your", "we", "is", "are", "with", "on", "at",
                "this", "that", "will", "be", "in", "you", "please", "have", "from", "it", "as", "or"}
RULE_LINE = re.compile(r"^\s*([-_=*~]\s*){4,}$")
FORWARD_MARK = re.compile(r"-{3,}\s*Forwarded message\s*-{3,}", re.I)
HDR_LINE = re.compile(r"^\s*(From|Date|Subject|To|Cc)\s*:\s*(.*)$", re.I)


def split_forward(text):
    """(headers dict, body) for a 'Fwd:' body, or (None, text). The header lines follow the
    marker in any order; a long display name may wrap onto the next line."""
    m = FORWARD_MARK.search(text)
    if not m:
        return None, text
    lines = text[m.end():].lstrip("\n").split("\n")
    hdr, last, blanks = {}, -1, 0
    for i, l in enumerate(lines[:14]):
        l = plain(l)
        h = HDR_LINE.match(l)
        if h:
            hdr[h.group(1).lower()] = h.group(2).strip()
            last = i
        elif not l.strip():
            blanks += 1
            if hdr and blanks >= 1 and last >= 0 and i > last:
                break
        elif hdr and i == last + 1 and ("@" in l or "<" in l) and "@" not in hdr[list(hdr)[-1]]:
            hdr[list(hdr)[-1]] += " " + l.strip()  # a wrapped display name: "From: Long Name\n <addr>"
            last = i
    if not hdr:
        return None, text
    return hdr, "\n".join(lines[last + 1:])
SCHOOL_SENDERS = ("veracross.com", "sffriendsschool.org", "sfquakers.org")
PACIFIC = "America/Los_Angeles"
URL_RE = re.compile(r"https?://[^\s<>()\"']+")


# ---------------------------------------------------------------- HTML to plain paragraphs

# Structure survives as private-use characters inside the text, so every later step (forwarded
# block, Spanish cut, link resolution) works on plain lines; the Docs writer turns them into styles.
B1, B0, I1, I0, U1, U0 = "\ue001", "\ue002", "\ue003", "\ue004", "\ue005", "\ue006"
H = {1: "\ue011", 2: "\ue012", 3: "\ue013", 4: "\ue014"}  # line prefix: a heading inside the email, by level
MARKS = re.compile("[\ue001-\ue006\ue011-\ue014]")


def plain(text):
    return MARKS.sub("", text)


class _Text(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol",
             "blockquote", "section", "article", "header", "footer", "hr", "pre"}
    SKIP = {"script", "style", "head", "title"}
    STYLE_TAGS = {"b": "b", "strong": "b", "i": "i", "em": "i", "u": "u"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.href, self.anchor = [], 0, None, []
        self.depth = {"b": 0, "i": 0, "u": 0}
        self.stack = []  # per open tag: the styles it switched on

    def _open(self, styles):
        for k in [k for k in ("b", "i", "u") if k in styles]:
            self.depth[k] += 1
            if self.depth[k] == 1:
                self._emit({"b": B1, "i": I1, "u": U1}[k])

    def _close(self, styles):
        for k in [k for k in ("u", "i", "b") if k in styles]:
            self.depth[k] = max(0, self.depth[k] - 1)
            if self.depth[k] == 0:
                self._emit({"b": B0, "i": I0, "u": U0}[k])

    def _emit(self, s):
        (self.anchor if self.href is not None else self.out).append(s)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        styles = set()
        if tag in self.STYLE_TAGS:
            styles.add(self.STYLE_TAGS[tag])
        st = (a.get("style") or "").lower().replace(" ", "")
        if re.search(r"font-weight:(bold|[6-9]00)", st):
            styles.add("b")
        if "font-style:italic" in st:
            styles.add("i")
        if "text-decoration:underline" in st or "text-decoration-line:underline" in st:
            styles.add("u")
        self.stack.append((tag, styles))
        if tag in self.SKIP:
            self.skip += 1
            return
        if tag == "a":
            self.href = a.get("href")
            self.anchor = []
        elif tag == "li":
            self.out.append("\n• ")
        elif tag == "hr":
            self.out.append("\n\n")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.out.append("\n" + H[min(int(tag[1]), 4)])
        elif tag in self.BLOCK:
            self.out.append("\n")
        self._open(styles)

    def handle_endtag(self, tag):
        styles = set()
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                styles = self.stack[i][1]
                del self.stack[i]
                break
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
            return
        self._close(styles)
        if tag == "a":
            text = "".join(self.anchor).strip()
            href = (self.href or "").strip()
            if href.startswith("http") and plain(text) and plain(text) != href and not plain(text).startswith("http"):
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
    """HTML → lines with structure markers (see MARKS); plain() strips them."""
    p = _Text()
    p.feed(src)
    p.close()
    return tidy("".join(p.out))


def star_bold(text):
    """Plain-text emails write *bold* with asterisks; keep the emphasis, drop the asterisks."""
    return re.sub(r"(?<![\w*])\*([^*\n]{1,120}?)\*(?![\w*])", lambda m: B1 + m.group(1) + B0, text)


POINTER_LINE = re.compile(r"^\W*(para (el )?español|en español|versi[oó]n en español|spanish( version)?|"
                          r"for spanish|中文|chinese( version)?)\b[^\n]{0,80}(abajo|below|continuaci[oó]n|下方|请见)[^\n]{0,20}$", re.I)


def drop_pointers(text):
    """Remove lines like 'Para español, mire más abajo.' that only point at a translation."""
    return tidy("\n".join(l for l in text.split("\n") if not POINTER_LINE.match(plain(l))))


def tidy(text):
    """Collapse whitespace: one paragraph per line, blank lines between groups, no trailing space."""
    text = text.replace("\r", "").replace("\u202f", " ").replace("\u2009", " ").replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in text.split("\n")]
    out, blank = [], True
    for l in lines:
        if not plain(l).strip():
            if l:  # markers on an otherwise blank line: keep them on the previous line
                if out:
                    out[-1] += l
                else:
                    out.append(l)
                    blank = False
            if not blank:
                out.append("")
            blank = True
            continue
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

def line_lang(l):
    """'es', 'en' or None (too short or undecided) for one line."""
    words = re.findall(r"[a-záéíóúñü]+", l.lower())
    if len(words) < 2:
        return None
    es = sum(1 for w in words if w in SPANISH_STOP) + sum(1 for w in words if re.search(r"[áéíóúñ]", w))
    en = sum(1 for w in words if w in ENGLISH_STOP)
    if es > en and (es >= 2 or len(words) <= 4):
        return "es"
    if en > es:
        return "en"
    return None


def mostly(lines, lang, n=6):
    tagged = [line_lang(l) for l in lines if l.strip()]
    tagged = [t for t in tagged if t][:n]
    return bool(tagged) and sum(1 for t in tagged if t == lang) * 10 >= len(tagged) * 7


def looks_spanish(lines):
    return mostly(lines, "es")


def strip_spanish(text):
    """Drop the Spanish translation that digests, letters and notices append after the English.

    Cut at a marker line ("Para español", "Versión en español") or a rule line when Spanish
    follows, else at the first Spanish line that starts a run of Spanish lines after a run of
    English ones, provided what follows is Spanish to the end."""
    lines = text.split("\n")
    for i, l in enumerate(lines):
        if (SPANISH_MARKERS.match(plain(l)) or RULE_LINE.match(plain(l))) and looks_spanish(lines[i + 1:i + 20]):
            return tidy("\n".join(lines[:i]))
    for i in range(2, len(lines)):
        if (line_lang(lines[i]) == "es" and mostly(lines[i:], "es", n=6) and mostly(lines[:i][::-1], "en", n=6)
                and mostly(lines[i:], "es", n=10 ** 6)):
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


def unwrap_google(u):
    """https://www.google.com/url?q=<dest>&source=gmail... → <dest>."""
    from urllib.parse import parse_qs, unquote
    p = urlparse(u)
    if p.netloc.endswith("google.com") and p.path == "/url":
        q = parse_qs(p.query).get("q")
        if q:
            return unquote(q[0])
    return u


def resolve_links(text, resolver, cache=None):
    cache = {} if cache is None else cache

    def sub(m):
        u = m.group(0).rstrip(".,;:!?)")
        tail = m.group(0)[len(u):]
        u = unwrap_google(u)
        if is_tracking(u):
            if u not in cache:
                cache[u] = resolver(u)
            return cache[u] + tail
        return u + tail
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
    s = re.sub(r"\s+", " ", s.replace("\u202f", " ").replace("\xa0", " ").strip())
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
    plain_part, htm = body_parts(msg)
    tp = star_bold(tidy(plain_part)) if plain_part.strip() else ""
    th = html_to_text(htm) if htm.strip() else ""
    # HTML keeps the email's structure; fall back to the plain part only when the HTML is a stub.
    text = th if len(plain(th)) >= 0.5 * len(plain(tp)) else tp
    shape, block_date = "filter", None

    hdr, rest = split_forward(text)
    if hdr is not None:
        shape = "fwd"
        if "from" in hdr:
            sender = email.utils.parseaddr(hdr["from"])[1].lower() or sender
        if "subject" in hdr:
            subject = clean_subject(hdr["subject"])
        if "date" in hdr:
            block_date = hdr["date"]
            date = parse_forward_date(hdr["date"]) or date
        text = tidy(rest)

    info = {"shape": shape, "header_date": str(msg.get("Date") or ""), "block_date": block_date,
            "plain_len": len(plain(tp)), "html_len": len(plain(th)), "subject": subject, "sender": sender}
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
    before = len(text)
    text = drop_pointers(strip_spanish(text))
    info["stripped"] = before - len(text)
    if not sender.endswith(SCHOOL_SENDERS):
        sender = ""  # a person forwarded it; never record their address (CLAUDE.md §3)
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

def u16len(s):
    """Docs API indexes count UTF-16 code units: an emoji is 2, not 1."""
    return len(s.encode("utf-16-le")) // 2


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

    def inventory(self):
        """title → [doc ids, oldest first] for the Google Docs in the log folder."""
        q = (f"'{self.folder}' in parents and trashed = false "
             f"and mimeType = 'application/vnd.google-apps.document'")
        r = self._check(self.s.get(self.DRIVE, params={"q": q, "fields": "files(id,name,createdTime)",
                                                        "orderBy": "createdTime", "pageSize": "200",
                                                        "supportsAllDrives": "true"}), "Drive list")
        out = {}
        for f in r.get("files", []):
            out.setdefault(f["name"], []).append(f["id"])
        return out

    def find(self, title):
        """The doc's id (the oldest if the title is duplicated), or None. A service account has
        no Drive storage quota, so it cannot create files (Google, 2025); the bot account creates
        each stream's doc in the folder once, by hand, and the job only appends to it."""
        ids = self.inventory().get(title, [])
        if len(ids) > 1:
            print(f"  note: {len(ids)} docs titled {title!r}; using the oldest. Trash the others.")
        return ids[0] if ids else None

    def share_anyone(self, doc_id):
        """Best effort: 'anyone with the link can view'. Fails harmlessly if the folder already grants it."""
        r = self.s.post(f"{self.DRIVE}/{doc_id}/permissions", json={"role": "reader", "type": "anyone"})
        return r.status_code < 400

    def get(self, doc_id):
        return self._check(self.s.get(f"{self.DOCS}/{doc_id}"), "Docs get")

    def paragraphs(self, doc):
        """[(text, headingId or None, startIndex, endIndex)] for every paragraph."""
        out = []
        for el in doc.get("body", {}).get("content", []):
            p = el.get("paragraph")
            if not p:
                continue
            st = p.get("paragraphStyle", {})
            text = "".join(r.get("textRun", {}).get("content", "") for r in p.get("elements", [])).strip()
            hid = st.get("headingId") if st.get("namedStyleType", "").startswith("HEADING") else None
            out.append((text, hid, el["startIndex"], el["endIndex"]))
        return out

    def heading_ids(self, doc):
        out = {}
        for text, hid, _, _ in self.paragraphs(doc):
            if hid:
                out.setdefault(text, hid)
        return out

    def repair_heading(self, doc_id, heading):
        """A title paragraph left unstyled by an earlier run (UTF-16 offsets, see u16len) becomes
        a Heading 1. Returns its headingId, or None if the text is not in the doc."""
        for text, hid, a, b in self.paragraphs(self.get(doc_id)):
            if text == heading and not hid:
                self._check(self.s.post(f"{self.DOCS}/{doc_id}:batchUpdate", json={"requests": [
                    {"updateParagraphStyle": {"range": {"startIndex": a, "endIndex": b},
                                              "paragraphStyle": {"namedStyleType": "HEADING_1"}, "fields": "namedStyleType"}}]}),
                    "Docs repair")
                return self.heading_ids(self.get(doc_id)).get(heading)
        return None

    def append(self, doc_id, heading, body):
        doc = self.get(doc_id)
        end = doc["body"]["content"][-1]["endIndex"] - 1
        reqs = entry_requests(end, heading, body, empty=end <= 1)
        for i in range(0, len(reqs), 400):  # a long newsletter can need many style runs
            self._check(self.s.post(f"{self.DOCS}/{doc_id}:batchUpdate", json={"requests": reqs[i:i + 400]}), "Docs append")
        return self.heading_ids(self.get(doc_id)).get(heading)

    def clear(self, doc_id):
        """Empty a doc (the rebuild mode). Returns the number of characters removed."""
        doc = self.get(doc_id)
        end = doc["body"]["content"][-1]["endIndex"]
        if end <= 2:
            return 0
        self._check(self.s.post(f"{self.DOCS}/{doc_id}:batchUpdate", json={"requests": [
            {"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end - 1}}}]}), "Docs clear")
        return end - 2


HEADING_STYLE = {1: {"bold": True, "underline": True, "italic": True}, 2: {"bold": True, "underline": True},
                 3: {"bold": True}, 4: {"underline": True}}  # Ahin's ladder: all three, then B+U, B, U (italic alone is inline)


def entry_requests(at, heading, body, empty):
    """Docs batchUpdate requests that append one email at index `at`: the entry heading as
    Heading 2, then the body with the email's own headings and bold/italic/underline runs as
    text styles. Offsets are UTF-16 units (u16len); the inserted text carries no markers."""
    lead = "" if empty else "\n"
    lines = body.split("\n")
    out_text, paras, runs = lead + heading + "\n", [], []
    h0 = at + u16len(lead)
    h1 = h0 + u16len(heading)
    paras.append((h0, h1 + 1, "HEADING_2", None))
    pos = h1 + 1
    for raw in lines:
        level = None
        if raw[:1] in H.values():
            level = [k for k, v in H.items() if v == raw[0]][0]
            raw = raw[1:]
        text, state, start = "", {"b": False, "i": False, "u": False}, {}
        cur = pos
        for ch in raw:
            if ch in (B1, I1, U1, B0, I0, U0):
                k = {B1: "b", B0: "b", I1: "i", I0: "i", U1: "u", U0: "u"}[ch]
                on = ch in (B1, I1, U1)
                if on and not state[k]:
                    state[k], start[k] = True, cur
                elif not on and state[k]:
                    state[k] = False
                    if cur > start[k]:
                        runs.append((start[k], cur, k))
                continue
            text += ch
            cur += u16len(ch)
        for k in state:
            if state[k] and cur > start[k]:
                runs.append((start[k], cur, k))
        out_text += text + "\n"
        paras.append((pos, cur + 1, "NORMAL_TEXT", level))
        pos = cur + 1
    reqs = [{"insertText": {"location": {"index": at}, "text": out_text}},
            {"updateParagraphStyle": {"range": {"startIndex": h0, "endIndex": pos}, "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"}, "fields": "namedStyleType"}},
            {"updateTextStyle": {"range": {"startIndex": h0, "endIndex": pos}, "textStyle": {"bold": False, "italic": False, "underline": False}, "fields": "bold,italic,underline"}},
            {"updateParagraphStyle": {"range": {"startIndex": h0, "endIndex": h1 + 1}, "paragraphStyle": {"namedStyleType": "HEADING_2"}, "fields": "namedStyleType"}}]
    for a, b, style, level in paras[1:]:
        if level and b - 1 > a:
            st = HEADING_STYLE[level]
            reqs.append({"updateTextStyle": {"range": {"startIndex": a, "endIndex": b - 1}, "textStyle": st, "fields": ",".join(st)}})
    for a, b, k in runs:
        key = {"b": "bold", "i": "italic", "u": "underline"}[k]
        reqs.append({"updateTextStyle": {"range": {"startIndex": a, "endIndex": b}, "textStyle": {key: True}, "fields": key}})
    return reqs


# ---------------------------------------------------------------- main

def load_sources():
    if SOURCES.exists():
        d = json.loads(SOURCES.read_text())
        for m in d.get("messages", []):  # an older index may carry a forwarder's address
            if not m.get("sender", "").endswith(SCHOOL_SENDERS):
                m["sender"] = ""
        return d
    return {"schema": 1, "note": "Generated by build/fetch_school_email.py: one entry per school email "
            "logged in Google Docs, with its deep link. Do not edit by hand.", "docs": {}, "messages": []}


def entry_heading(m):
    d = m["date"]
    return f"{d:%b} {d.day}, {d.year} · {m['subject']}"[:160]


def run(messages, docs, sources, streams, dry_run, resolver, log=print):
    seen_ids = {m["message_id"] for m in sources["messages"] if m.get("message_id")}
    seen_fp = {m["fingerprint"] for m in sources["messages"]}
    cache, added, skipped, missing, headings = {}, [], 0, set(), {}
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
            doc_id = docs.find(title)
            if not doc_id:
                missing.add(title)
                log(f"  no doc yet for {title}; skipping {m['date']} {m['subject']}")
                continue
            docs.share_anyone(doc_id)
            sources["docs"][key] = {"title": title, "id": doc_id,
                                    "url": f"https://docs.google.com/document/d/{doc_id}/edit"}
            log(f"  found doc {title}")
        d = sources["docs"][key]
        heading = entry_heading(m)
        if key not in headings:
            headings[key] = docs.heading_ids(docs.get(d["id"]))
        if heading in headings[key]:  # already in the doc (an earlier run whose index was lost): index it, don't re-append
            hid = headings[key][heading]
            log(f"  already in doc, indexed → {title}: {m['date']} {m['subject']}")
        elif (hid := docs.repair_heading(d["id"], heading)):
            headings[key][heading] = hid
            log(f"  already in doc (title restyled as a heading), indexed → {title}: {m['date']} {m['subject']}")
        else:
            hid = docs.append(d["id"], heading, text)
            headings[key][heading] = hid
            log(f"  logged → {title}: {m['date']} {m['subject']}")
            time.sleep(0.5)  # Docs API write quota is per minute; be gentle
        rec.update({"doc_id": d["id"], "doc_url": d["url"],
                    "anchor": f"{d['url']}#heading={hid}" if hid else d["url"],
                    "logged_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
        sources["messages"].append(rec)
        seen_ids.add(m["message_id"]); seen_fp.add(fp)
        added.append(rec)
    if missing:
        log("\nThese docs do not exist yet. Create each one, as the bot account, inside the log folder "
            "(New → Google Docs, then rename), and rerun:\n  " + "\n  ".join(sorted(missing)))
    return added, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eml", help="directory of .eml files instead of IMAP")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--since", help="YYYY-MM-DD; default 60 days before the school year's first day")
    ap.add_argument("--summary", help="write a markdown summary here (GitHub step summary)")
    ap.add_argument("--debug", action="store_true", help="print shape, dates and part sizes per message, and why others were rejected")
    ap.add_argument("--rebuild", action="store_true", help="empty every log doc and write all emails again (new formatting); resets the index")
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
                  f"plain={i['plain_len']} html={i['html_len']} text={len(m['text'])} stripped={i['stripped']} {m['subject'][:60]}")
            if len(m["text"]) < 400 and i["stripped"] > 200:
                print("      kept: " + repr(m["text"][-80:]))
        for i in REJECTED:
            print(f"  rejected ({i['rejected']}) [{i['shape']}]: from={i['sender']} {i['subject'][:60]}")
    if a.limit:
        messages = messages[:a.limit]

    docs = None
    key, folder = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"), os.environ.get("EMAIL_LOG_FOLDER_ID")
    if key and folder:
        docs = Docs(key, folder)
        inv = docs.inventory()
        print(f"{sum(len(v) for v in inv.values())} doc(s) in the log folder:")
        for t, ids in sorted(inv.items()):
            print(f"  {t}  ({len(ids)} copy)" if len(ids) > 1 else f"  {t}")
        need = {f"{stream_label(classify(m['subject'], m['text'])[0], streams)} {school_year_label(m['date'])} (email log)"
                for m in messages}
        for t in sorted(need - set(inv)):
            print(f"  MISSING: {t}")
    elif not a.dry_run:
        sys.exit("GOOGLE_SERVICE_ACCOUNT_JSON and EMAIL_LOG_FOLDER_ID are needed to write the log.")

    sources = load_sources()
    if a.rebuild:
        if a.dry_run or docs is None:
            sys.exit("--rebuild needs a real run with Docs access.")
        for title, ids in sorted(docs.inventory().items()):
            n = docs.clear(ids[0])
            print(f"  emptied {title} ({n} characters)")
        sources = {"schema": 1, "note": sources.get("note", ""), "docs": {}, "messages": []}
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
