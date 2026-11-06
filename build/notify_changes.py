#!/usr/bin/env python3
"""Email a plain-English summary of what just changed on the Updates embed.

Run by .github/workflows/deploy.yml after a push to main deploys. Compares the ledger
(shared/updates/data.json) and the email-log index (shared/updates/sources.json) before and
after the push, and sends one email from the bot's Gmail (sfquakerbot@gmail.com, App
Password in BOT_GMAIL_APP_PASSWORD) to UPDATES_NOTIFY_TO. Decided with Ahin 2026-11-05:
ledger changes publish without a review step, and this email is how they are reviewed.

  python3 build/notify_changes.py --base-data old.json --base-sources old-sources.json \
      [--send] [--to a@b] [--pages-url https://.../class-sites/]

Without --send it prints the email. Exit 0 with nothing to say when nothing changed.
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import smtplib
import sys
from zoneinfo import ZoneInfo
from email.message import EmailMessage

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "shared" / "updates" / "data.json"
SOURCES = ROOT / "shared" / "updates" / "sources.json"
BOT = "sfquakerbot@gmail.com"
PAGES = "https://sffs-class-sites.github.io/class-sites/"
GRADE_WORD = {"K": "Kindergarten", "1": "1st grade", "2": "2nd grade", "3": "3rd grade", "4": "4th grade",
              "5": "5th grade", "6": "6th grade", "7": "7th grade", "8": "8th grade"}


def load(path):
    p = pathlib.Path(path) if path else None
    if p and p.exists() and p.stat().st_size:
        return json.loads(p.read_text())
    return None


def when_text(t):
    w = t.get("when") or {}
    if t.get("deadline"):
        d = t["deadline"]
        return f"{d.get('what', 'Due')} by {fmt(d['date'])}"
    if w.get("date"):
        s = fmt(w["date"])
        if w.get("end") and w["end"] != w["date"]:
            s += " to " + fmt(w["end"])
        if w.get("start_time"):
            s += " " + clock(w["start_time"]) + ("–" + clock(w["end_time"]) if w.get("end_time") else "")
        if w.get("location"):
            s += ", " + w["location"]
        return s
    return ""


def fmt(d):
    x = dt.date.fromisoformat(d)
    return f"{x:%a %b} {x.day}"


def clock(hm):
    h, m = hm.split(":")
    h = int(h)
    suf = "am" if h < 12 else "pm"
    h = h % 12 or 12
    return f"{h}:{m} {suf}" if m != "00" else f"{h} {suf}"


# --- where a topic lands on the page: a port of the embed's tab rules (build_updates.py, TABS)
LOWER, MIDDLE = ["K", "1", "2", "3", "4"], ["5", "6", "7", "8"]


def _start(t):
    return (t.get("when") or {}).get("date")


def _end(t):
    w = t.get("when") or {}
    return w.get("end") or w.get("date")


def _span_days(t):
    if not _start(t):
        return 0
    return (dt.date.fromisoformat(_end(t)) - dt.date.fromisoformat(_start(t))).days + 1


def _short_span(t):
    return 0 < _span_days(t) <= 7


def _is_past(t, today):
    e = _end(t)
    return bool(e) and dt.date.fromisoformat(e) < today


def _latest_date(t):
    return t["updates"][-1]["date"]


def _has_open_action(t, today):
    if t.get("deadline"):
        return dt.date.fromisoformat(t["deadline"]["date"]) >= today
    return bool(t.get("action")) and not _is_past(t, today)


def tabs_for(t, today):
    """The tab labels the topic appears under today, in the page's tab order."""
    s, e = _start(t), _end(t)
    iso = today.isoformat()
    in7 = (today + dt.timedelta(days=7)).isoformat()
    out = []
    if _has_open_action(t, today):
        out.append("Deadlines")
    if s and _short_span(t) and e >= iso and s < in7:
        out.append("This week")
    if s and _short_span(t) and s >= in7:
        out.append("Coming up")
    if _latest_date(t) >= (today - dt.timedelta(days=7)).isoformat():
        out.append("What changed")
    if t["kind"] == "classroom":
        out.append("Classroom")
    if ((t["kind"] in ("notice", "volunteer")) or (s and not _short_span(t) and t["kind"] != "classroom")) \
            and t["kind"] != "letter" and not _is_past(t, today):
        out.append("Good to know")
    if t["kind"] == "letter":
        out.append("From the Head")
    return out


def views_for(t):
    """Which grade views show the topic (a site's ?class= resolves to one grade)."""
    a = t.get("audience")
    if a == "all":
        return "all grade views"
    if a == "lower":
        return "Lower School views (K–4)"
    if a == "middle":
        return "Middle School views (5–8) only; not on the 1st or 3rd grade sites unless a family adds those grades"
    return ", ".join(GRADE_WORD.get(g, g) for g in a) + " view" + ("s" if len(a) > 1 else "") + " only"


def filed_line(t, today):
    tabs = tabs_for(t, today)
    if not tabs:
        where = "no tab right now (its date has passed and it is older than a week); History only"
    else:
        where = " · ".join(tabs)
        if tabs == ["What changed"]:
            if _is_past(t, today):
                where += " only, because the date has passed; it leaves the page on " + fmt((dt.date.fromisoformat(_latest_date(t)) + dt.timedelta(days=8)).isoformat())
            else:
                where += " only; it leaves the page on " + fmt((dt.date.fromisoformat(_latest_date(t)) + dt.timedelta(days=8)).isoformat())
    return f"Filed under: {where}. Shown on: {views_for(t)}."


def audience(t):
    a = t.get("audience")
    if a == "all":
        return "everyone"
    if a == "lower":
        return "Lower School"
    if a == "middle":
        return "Middle School"
    return ", ".join(GRADE_WORD.get(g, g) for g in a)


def topic_line(t, note=None, today=None):
    bits = [t["title"]]
    w = when_text(t)
    if w:
        bits.append(w)
    bits.append("for " + audience(t))
    line = " · ".join(bits)
    if note:
        line += f"\n    {note}"
    if today:
        line += f"\n    {filed_line(t, today)}"
    return line


def diff(old, new, old_idx, new_idx):
    """{added: [topic], updated: [(topic, note)], emails: [index entry]}"""
    old_topics = {t["id"]: t for t in (old or {}).get("topics", [])}
    added, updated = [], []
    for t in new["topics"]:
        o = old_topics.get(t["id"])
        if not o:
            added.append(t)
        elif json.dumps(o, sort_keys=True) != json.dumps(t, sort_keys=True):
            new_notes = [u["note"] for u in t["updates"][len(o["updates"]):]]
            updated.append((t, "; ".join(new_notes) if new_notes else "Details changed."))
    old_src = {s["id"] for s in (old or {}).get("sources", [])}
    new_src = [s for s in new["sources"] if s["id"] not in old_src]
    old_fp = {m["fingerprint"] for m in (old_idx or {}).get("messages", [])}
    logged = [m for m in (new_idx or {}).get("messages", []) if m["fingerprint"] not in old_fp]
    return {"added": added, "updated": updated, "processed": new_src, "logged": logged, "index": new_idx or {}}


def compose(d, pages, today=None):
    today = today or dt.datetime.now(ZoneInfo("America/Los_Angeles")).date()
    n_add, n_upd = len(d["added"]), len(d["updated"])
    if n_add or n_upd:
        subject = "Class sites: " + ", ".join(x for x in [f"{n_add} new topic{'s' * (n_add != 1)}" if n_add else "",
                                                       f"{n_upd} updated" if n_upd else ""] if x) + " on the Updates page"
    elif d["processed"]:
        subject = f"Class sites: {len(d['processed'])} email{'s' * (len(d['processed']) != 1)} read, nothing new for the Updates page"
    elif d["logged"]:
        subject = f"Class sites: {len(d['logged'])} new school email{'s' * (len(d['logged']) != 1)} logged"
    else:
        return None, None
    anchors = {m["anchor"] for m in d["index"].get("messages", [])}
    by_fp = {(m["date"], m["subject"]): m["anchor"] for m in d["index"].get("messages", [])}
    lines = []
    review = pages.rstrip("/") + "/shared/updates/?class=2034&tab=changed"
    lines.append(f"Review the result on the Updates page (What changed tab, 1st grade view):\n{review}")
    lines.append(f"Same page for 3rd grade: {pages.rstrip('/')}/shared/updates/?class=2032&tab=changed")
    lines.append("Each item below says which tab it is filed under today and which grade views show it.")
    if d["added"]:
        lines.append(f"\nNew on the Updates page ({n_add}):")
        lines += ["  - " + topic_line(t, t["updates"][-1]["note"] if t["updates"] else None, today) for t in d["added"]]
    if d["updated"]:
        lines.append(f"\nUpdated ({n_upd}):")
        lines += ["  - " + topic_line(t, note, today) for t, note in d["updated"]]
    if d["processed"]:
        lines.append(f"\nEmails read for this change ({len(d['processed'])}):")
        for s in d["processed"]:
            link = s.get("doc_anchor") or by_fp.get((s["date"], s["subject"])) or ""
            lines.append(f"  - {fmt(s['date'])} · {s['subject']}" + (f"\n    full text: {link}" if link else ""))
    if d["logged"] and not d["processed"]:
        lines.append(f"\nNewly logged school emails ({len(d['logged'])}); the extraction step reads them next:")
        lines += [f"  - {fmt(m['date'])} · {m['subject']}\n    full text: {m['anchor']}" for m in d["logged"]]
    lines.append("\nHow this works: docs/updates-pipeline.md in github.com/sffs-class-sites/class-sites. "
                 "To change something, reply to this email or edit shared/updates/data.json through a PR.")
    return subject, "\n".join(lines)


def send(subject, body, to, password, sender=BOT):
    msg = EmailMessage()
    msg["From"] = f"SFFS class sites bot <{sender}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(sender, password)
        s.send_message(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-data", help="data.json before the push (missing or empty = everything is new)")
    ap.add_argument("--base-sources", help="sources.json before the push")
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--sources", default=str(SOURCES))
    ap.add_argument("--pages-url", default=PAGES)
    ap.add_argument("--to", default=os.environ.get("UPDATES_NOTIFY_TO", ""))
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--out", help="also write the subject and body to this file")
    ap.add_argument("--today", help="YYYY-MM-DD, for tests (default: today in America/Los_Angeles)")
    a = ap.parse_args()
    d = diff(load(a.base_data), load(a.data), load(a.base_sources), load(a.sources))
    subject, body = compose(d, a.pages_url, dt.date.fromisoformat(a.today) if a.today else None)
    if not subject:
        print("Nothing changed on the Updates page; no email.")
        return
    text = f"Subject: {subject}\n\n{body}\n"
    print(text)
    if a.out:
        pathlib.Path(a.out).write_text(text)
    if a.send:
        pw = os.environ.get("BOT_GMAIL_APP_PASSWORD", "")
        if not a.to or not pw:
            sys.exit("notify_changes: --send needs UPDATES_NOTIFY_TO and BOT_GMAIL_APP_PASSWORD")
        send(subject, body, a.to, pw)
        print(f"Sent to {a.to}.")


if __name__ == "__main__":
    main()
