# Updates pipeline — school emails, organised

Scope: the **Updates** embed (`shared/updates/`), the topic ledger behind it, the full-text log of school emails, and the pipeline that turns forwarded email into both. Repo-wide rules (hosting, change control, personal data) live in `CLAUDE.md` and win over anything here. The *event* side of email (candidates for Important Dates, UIDs, approval queues) is in `docs/dates-pipeline.md`; this pipeline feeds it and does not change its rules.

Decided with Ahin 2026-10-31. Status markers: **Built** / **Designed, not built** / **Needs Ahin**.

## The problem

Parents of a class receive three streams, all sent by Veracross (`m@mailN.veracross.com`):

| Stream | Subject pattern | Cadence | Shape |
|---|---|---|---|
| Circle Back | `SFFS Circle Back: <Month D, YYYY>` | Weekly, Thursday ~noon PT | HTML; fixed sections: The Week Ahead, Save the Date, School Announcements, Student Quote, Athletics, PGA, Community Announcements, Quick Links |
| Room Parent Digest | `SFFS <Nth> Grade \| Room Parent Digest \| MM-DD-YY` | Every other Tuesday, per grade | Plain-text bullets, English then Spanish; sections *Grade news and reminders* and *Schoolwide highlights* |
| From the Head's Desk | contains `From the Head's Desk` | About monthly | Essay, English then Spanish, one or two links |

What makes them hard to keep up with, measured on the 20 emails of 2026–27 so far (Aug 18 – Oct 29):

- **Most of each email is last week's email.** Consecutive Circle Backs share most items word for word. The digests' schoolwide half restates Circle Back. The real information is the *delta*: an Annual Fund total, "tickets coming soon" becoming "on sale Nov 2", a play structure closing and reopening, a Kindergarten event moving by five days with a request to RSVP again.
- **Things are announced first and get their details later.** A date arrives weeks before its time, place, RSVP link or early-dismissal note.
- **Deadlines hide in prose.** "Orders close November 1", "designs by November 10", "sign up no later than Monday, October 26".
- **Nothing is grade-aware.** A family with children in two grades reads two digests plus everything else.

So the unit the pipeline tracks is a **topic**, not an email: one record per thing the school is telling families about, with a history of how it changed and a pointer into the full text of each email that mentioned it.

## What exists now

**Built (2026-10-31):**

- `shared/updates/data.json` — the topic ledger for 2026–27, backfilled by hand from the 20 emails since Aug 18 (70 topics, 17 source emails; the duplicate 1st grade digest of 09-22 is one source). English only, no parent personal data.
- `build/build_updates.py` — builds `_site/shared/updates/index.html`. One page serves every class site: `?class=YYYY` resolves to a grade (`grade = 8 − (gradYear − schoolYearEndYear)`, rolling over the day after `school_year.last_day`), `?grade=N` overrides it, and a "Change grades" picker lets a family tick other grades, remembered in the browser. Tabs: **Action needed** (open sign-ups and deadlines, soonest first), **This week**, **Coming up**, **What changed** (topics updated in the last seven days of email, with an "Updated"/"New" badge and a History disclosure), **Good to know** (standing notices and volunteer asks), **From the Head** (letters summarised). Dated items that are already on Important Dates are marked "On Important Dates". Non-official events get an "Add to Google Calendar" link (a one-time copy, no UID involved; see dates-pipeline.md for why that matters).
- `tests/validate_updates.py` — schema, dates, source references, no Veracross tracking links, and a personal-data sweep (fails on any email outside the school domain, phone numbers, street addresses other than the school's and known venues, or Spanish text).
- `tests/updates_check.py` — Playwright, Sites-style sandbox, desktop/tablet/phone: fills the frame, no horizontal scroll, tabs work in place, grade picker filters and persists, `?class=` and rollover resolve correctly, links open new tabs, phone first view shows the first card's title, date, summary and action.
- CI runs all three on every PR (`build.yml`), and the embed deploys with everything else. `registry.yaml` lists the embed; no site slot yet.

**Needs Ahin (one-time setup; nothing else can run until these exist):**

1. **Gmail forwarding, three filters** in Ahin's inbox, each forwarding to `sfquakerbot@gmail.com`. Gmail first emails a confirmation code to the bot inbox; confirm it once, then the filters can use the address. Filter texts (the *Subject* field; no sender restriction, so a change of mail host doesn't break them):
   - `Circle Back`
   - `Room Parent Digest`
   - `Head's Desk`
   Then forward the 2026–27 history once, so the log is complete from the first day of school: the 7 Circle Backs (Sep 17 – Oct 29), 6 digests (1st and 3rd grade, 09-22, 10-06, 10-20) and 4 Head's Desk letters (Aug 18, Sep 4, Sep 18 "Friends Community Commitments", Oct 23). Each forwarded copy is recognised by its original subject; "Fwd:" is stripped.
2. **Bot mailbox access for Actions**: on `sfquakerbot@gmail.com`, turn on 2-Step Verification, create an **App Password** (Google Account → Security → App passwords, name it "class-sites actions"), make sure IMAP is enabled, and store the 16-character password as the `BOT_GMAIL_APP_PASSWORD` Actions secret. The fetcher reads over IMAP; nothing is deleted or marked. (Why not the Gmail API: a consumer Gmail account cannot delegate to the service account, and an OAuth app in testing mode expires its tokens weekly.)
3. **A Drive folder for the log**: in the bot's Drive create `Class sites — email log`, share it as **Editor** with the service account's address (the `client_email` field in the key already stored as `GOOGLE_SERVICE_ACCOUNT_JSON`), and store the folder ID (the part of the URL after `/folders/`) as the `EMAIL_LOG_FOLDER_ID` Actions variable. Enable the **Google Docs API** in the bot's Cloud project if it isn't already (the first run says so if it isn't).

**Designed, not built** (in order):

- **E1a: fetch and log.** `build/fetch_school_email.py` (Actions, scheduled Thursday 13:30 PT and Wednesday 09:00 PT, and on demand): IMAP as the bot → for each unseen message matching the three subject patterns: strip the Spanish half (digests and letters put it after a rule or after "Para español"), resolve every Veracross tracking link to its destination, convert to plain paragraphs, and append to the stream's Google Doc for the school year as a dated H1 heading plus body, written through the service account. Record `{message_id, stream, date, subject, doc_url, heading_id}` in `shared/updates/sources.json`. Deep links are `https://docs.google.com/document/d/<id>/edit#heading=<heading_id>`; Google Docs heading IDs are stable. The docs are shared "anyone with the link can view" so a parent can follow a History link; they contain parent details, which is what Ahin decided (log and calendar invites may; the repo and the embed may not).
- **E1b: extract.** The judgment step, run as a scheduled Claude task signed in as the bot (ROADMAP §G) or in a session until that exists. Input: the new emails' plain text and the current ledger. Output: a PR that updates `data.json` (new topics, new `updates` entries on existing ones, changed `when`/`deadline`/`summary`), keeps the ledger English-only and PII-free, and leaves the UID rules of `docs/dates-pipeline.md` untouched. The PR comment lists topics added/updated so Ahin can approve without reading JSON. Ahin is the only approver (decided 2026-10-30); a room-parent queue comes later with the approval app.
- **E1c: calendar.** Email-derived dated topics become candidates for Important Dates with `audience` and `source`, behind filters, so one calendar embed serves official dates and email dates (ROADMAP D2/D3). Deadlines become events too. UIDs are assigned once, at approval.
- **Second site:** the 3rd grade site, then K and 2nd (ROADMAP §E pilot order).

## The ledger (`shared/updates/data.json`)

```
school_year  {label, first_day, last_day, end_year}     end_year + last_day drive the grade calculation
streams      id → {label, cadence, audience}
sources      [{id, stream, date, subject, doc_url?, doc_anchor?, note?}]   one per email
topics       [{id, kind, audience, title, summary, when?, deadline?, action?, official?, links?, updates}]
```

- `kind`: `event` (has a `when`), `deadline` (the date that matters is the deadline), `notice`, `volunteer`, `letter`.
- `audience`: `all`, `lower` (K–4), `middle` (5–8), or a list of grades (`["1","2"]`). Grade-specific digest items use the grade; the embed resolves a site's class to a grade at view time, so the ledger never names a class.
- `when`: `{date, end?, start_time?, end_time?, location?}`; times are `HH:MM` local. Absent times mean all-day.
- `deadline`: `{date, what}`. A topic with a future deadline is "Action needed" regardless of kind.
- `official: true`: already on Important Dates. Shown with a tag, never duplicated into a calendar add.
- `updates`: in date order, one per email that said something, `{source, date, note}`; the first is the announcement. The last one's date decides "What changed". `note` is the delta in plain words.
- `links`: `{label, url}`, final destinations only (`validate_updates.py` rejects Veracross redirects).

## Personal data rule (decided 2026-10-31)

Parent and student personal data stays **off the repo and the embed**: no parent names (room-parent sign-offs included), no student names, no home addresses, no phone numbers, no personal email addresses. School staff names and `@sffriendsschool.org` addresses are fine, as are organisational mailboxes named in the emails. When an item needs a personal detail (a party at a family's home, an RSVP to a parent), the summary says "see the email" and the History link leads to the full text.

The **full-text log docs and calendar invites may contain parent details** (Ahin, 2026-10-31). Consequence for calendars: an event's address can go into an invite generated at view time, but not into `data.json`; until the calendar step is built, such events carry no address and link to the log instead.

The ledger is **English only**. Spanish-speaking families use browser translation on the site (Ahin, 2026-10-31); the Spanish halves of digests and letters are dropped at ingestion.

## Out of scope, noticed during the backfill

Ahin's inbox holds about 68 Veracross emails since August; the three streams are 20 of them. The rest include teacher **Grade Newsletters** (`1st Grade Newsletter: <date>`, `3rd Grade Newsletter: <date>`, `Lower School Specialists Newsletter`), one-off school notices (`[SFFS] Fall Conference Signups Now Open!`, the emergency test, the 3rd grade overnight trip), teacher one-offs (Star of the Week, field trip reminders) and Circle of Friends messages. The grade newsletters look like a fourth stream worth adding once the first three are running; nothing else is proposed.

## How a session should work on this

1. `python3 tests/validate_updates.py && python3 build/build_updates.py && python3 tests/updates_check.py` before any PR.
2. Keep `built_through` at the date of the newest source and `sources` complete; a topic may only cite sources that exist.
3. When something moves (date, time, place), change `when`/`deadline`, rewrite `summary` to the current truth, and add an `updates` entry saying what moved. Never delete history.
4. A topic that recurs each year (Community MfW, Ages & Stages) gets a new id per occurrence; the ledger is per school year.
