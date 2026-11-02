# Updates pipeline — school emails, organised

Scope: the **Updates** embed (`shared/updates/`), the topic ledger behind it, the full-text log of school emails, and the pipeline that turns forwarded email into both. Repo-wide rules (hosting, change control, personal data) live in `CLAUDE.md` and win over anything here. The *event* side of email (candidates for Important Dates, UIDs, approval queues) is in `docs/dates-pipeline.md`; this pipeline feeds it and does not change its rules.

Decided with Ahin 2026-10-31. Status markers: **Built** / **Designed, not built** / **Needs Ahin**.

## The problem

Parents of a class receive a lot of email, all of it sent through Veracross (`m@mailN.veracross.com`). About 70 messages reached a 1st-and-3rd-grade family between Aug 4 and Oct 29, 2026. They fall into eight streams:

| Stream | How to recognise it | Cadence | Shape |
|---|---|---|---|
| Circle Back | subject `SFFS Circle Back: <Month D, YYYY>` | Weekly, Thursday ~noon PT | HTML; fixed sections: The Week Ahead, Save the Date, School Announcements, Student Quote, Athletics, PGA, Community Announcements, Quick Links |
| Room Parent Digest | subject `SFFS <Nth> Grade \| Room Parent Digest \| MM-DD-YY` | Every other Tuesday, per grade | Plain-text bullets, English then Spanish; *Grade news and reminders* and *Schoolwide highlights* |
| From the Head's Desk | subject contains `From the Head's Desk` | About monthly | Essay, English then Spanish |
| Grade Newsletter (teachers) | subject `<Nth> Grade Newsletter: <Month D, YYYY>` | About monthly, per grade | HTML; curriculum by subject, homework, routines, **conversation starters** (1st grade), teacher contacts, Vidigami link |
| Teacher one-offs | no pattern: "sharing in 3A", "school/home book plan", "Name Projects", "pre conference form" | As needed | Short plain text from the grade team |
| Lower School Specialists Newsletter | subject `Lower School Specialists Newsletter: <date>` | About monthly | HTML; library, PE, music, art, with "ask at home" prompts |
| School notices | subject usually starts `[SFFS]` (forms, enrichment, conferences, safety, brand, testimony) or comes from a division head | As needed | HTML or plain text, often bilingual |
| PGA and room-parent notices | no pattern: room-parent recruiting, Circle of Friends, picture-day volunteers, forwarded flyers | As needed | Plain text |

The first three were the original scope; the other five were added 2026-11-01 after reading every email of the year.

What makes them hard to keep up with, measured on the 20 emails of 2026–27 so far (Aug 18 – Oct 29):

- **Most of each email is last week's email.** Consecutive Circle Backs share most items word for word. The digests' schoolwide half restates Circle Back. The real information is the *delta*: an Annual Fund total, "tickets coming soon" becoming "on sale Nov 2", a play structure closing and reopening, a Kindergarten event moving by five days with a request to RSVP again.
- **Things are announced first and get their details later.** A date arrives weeks before its time, place, RSVP link or early-dismissal note.
- **Deadlines hide in prose.** "Orders close November 1", "designs by November 10", "sign up no later than Monday, October 26".
- **Nothing is grade-aware.** A family with children in two grades reads two digests plus everything else.

So the unit the pipeline tracks is a **topic**, not an email: one record per thing the school is telling families about, with a history of how it changed and a pointer into the full text of each email that mentioned it.

## What exists now

**Built (2026-10-31):**

- `shared/updates/data.json` — the topic ledger for 2026–27, backfilled by hand from every school email since Aug 4 (103 topics from 62 source emails across the eight streams; a resend or two emails on one subject count as one source). English only, no parent personal data.
- `build/build_updates.py` — builds `_site/shared/updates/index.html`. One page serves every class site: `?class=YYYY` resolves to a grade (`grade = 8 − (gradYear − schoolYearEndYear)`, rolling over the day after `school_year.last_day`), `?grade=N` overrides it, and a "Change grades" picker lets a family tick other grades, remembered in the browser. Tabs: **Action needed** (open sign-ups and deadlines, soonest first), **This week**, **Coming up**, **What changed** (topics updated in the last seven days of email, with an "Updated"/"New" badge and a History disclosure), **Classroom** (from the teachers and specialists: questions to ask your child, what the class is learning, homework, routines, resources, grouped by section), **Good to know** (standing notices and volunteer asks), **From the Head** (letters summarised). The grade comes from the shared class model (`shared/class/class.js`, inlined at build time). Dated items that are already on Important Dates are marked "On Important Dates". Non-official events get an "Add to Google Calendar" link (a one-time copy, no UID involved; see dates-pipeline.md for why that matters).
- `tests/validate_updates.py` — schema, dates, source references, no Veracross tracking links, and a personal-data sweep (fails on any email outside the school domain, phone numbers, street addresses other than the school's and known venues, or Spanish text).
- `tests/updates_check.py` — Playwright, Sites-style sandbox, desktop/tablet/phone: fills the frame, no horizontal scroll, tabs work in place, grade picker filters and persists, `?class=` and rollover resolve correctly, links open new tabs, phone first view shows the first card's title, date, summary and action.
- CI runs all three on every PR (`build.yml`), and the embed deploys with everything else. `registry.yaml` lists the embed; no site slot yet.

**Needs Ahin (one-time setup; nothing else can run until these exist):**

1. ~~**Gmail forwarding.**~~ **Done 2026-11-01.** `sfquakerbot@gmail.com` is a confirmed forwarding address on Ahin's Gmail (confirmation clicked from the bot inbox), the account-level setting is *Disable forwarding*, and one filter `from:(veracross.com)` → *Forward it to sfquakerbot@gmail.com* does the forwarding. Every school broadcast goes through Veracross, and the five added streams have no subject pattern, so sender is the criterion. The 2026–27 history (68 Veracross emails, Aug 4 – Oct 29) was forwarded to the bot in one pass the same day, so the log can start at the start of the year. Forwarded copies are recognised by their original subject; "Fwd:" is stripped.
2. ~~**Bot mailbox access for Actions**~~ **Done 2026-11-02.** Ahin turned on 2-Step Verification on `sfquakerbot@gmail.com`, created the App Password "class-sites actions" and stored it as the `BOT_GMAIL_APP_PASSWORD` Actions secret. IMAP is always on in current Gmail (no toggle). The fetcher reads over IMAP; nothing is deleted or marked. (Why not the Gmail API: a consumer Gmail account cannot delegate to the service account, and an OAuth app in testing mode expires its tokens weekly.)
3. ~~**A Drive folder for the log**~~ **Done 2026-11-01.** `Class sites - email log` in the bot's Drive (folder ID `1sX6Gx_KS_xt8rb8BRPiY_wXwxqznhn2N`, stored as the `EMAIL_LOG_FOLDER_ID` Actions variable), shared as Editor with the service account `sf-quaker-bot@sffs-class-sites.iam.gserviceaccount.com`. The Google Docs API may still need enabling in the bot's Cloud project; the first run of the fetch job says so if it does.

**Designed, not built** (in order):

- **E1a: fetch and log — built 2026-11-02, first real run pending.** `build/fetch_school_email.py`, run by `.github/workflows/email-log.yml` (Wednesday 09:00 and Thursday 13:30 Pacific, and on demand; a PR that touches the fetcher runs it as a dry run and puts what it would log in the job summary). IMAP as the bot, read-only, All Mail since 60 days before the school year's first day. Both shapes in the bot mailbox are handled: a filter-forwarded copy (original headers kept) and a manual "Fwd:" (date, sender and subject taken from the forwarded block). Each school email is classified into a stream by subject pattern (Circle Back, Room Parent Digest, Head's Desk, Grade Newsletter, Specialists Newsletter), else `[SFFS]` → School notices, else by grade words in the subject, then in the body (exactly one grade → that grade's teachers doc; two grades, or none → School notices). So the log has no separate PGA doc: a grade-specific PGA note sits in the grade's doc, the rest in School notices; the ledger's `pga` stream is a human classification and still links by subject and date. The Spanish half is dropped at a "Para español"-style marker or a rule line followed by Spanish; HTML becomes paragraphs, bullets and "label (url)" links; Veracross `/c/` tracking links are resolved to their destinations. The text is appended to `<stream label> <year> (email log)` in the Drive folder as a Heading 1 `YYYY-MM-DD <subject>` plus the body; one doc per stream per school year, shared "anyone with the link can view". **The docs are created by hand, as the bot account, in the log folder** (a service account has no Drive storage quota and cannot create files, found on the first real run 2026-11-02); the job names any doc that is missing and skips those emails until it exists. `shared/updates/sources.json` is the index: `{message_id, fingerprint, stream, year, date, subject, sender, doc_id, doc_url, anchor, logged_at}` per email, plus `docs`. A resend (same date and subject) is logged once. The job commits the index to the `email-log-auto` branch and opens one PR (body = what was logged, with links); merging it is the only human step and carries no judgment. `build/build_updates.py` merges the index into the ledger at build time (same date; subject equal, a part of an "A / B" subject, or a prefix of it), so History links start pointing at the full text as soon as the PR merges, and fills `log.docs`. `tests/test_fetch_school_email.py` covers all of this offline with made-up emails and runs in CI; `tests/validate_updates.py` checks the index (Veracross senders only, Docs links, no duplicates).
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

## What was left out, deliberately

- **Circle of Friends support drives** name the person being supported and a parent's payment handle; the ledger keeps only that the committee exists and what it does.
- **The 1st grade Star of the Week schedule** lists children's first names by week; the ledger keeps the format and says the schedule was emailed, and the teachers email each family the Friday before.
- **Room-parent recruiting emails** name volunteers and their children; the ledger keeps the role description.
- **Spanish and Chinese translations** in every email are dropped (English only, Ahin 2026-10-31).
- One short note, "Seeking volunteers for 3rd grade art class with Yara" (Oct 5), could not be read because of a connector rate limit; its content is the in-class art volunteering already in the ledger from the 3rd grade digest.

## How a session should work on this

1. `python3 tests/validate_updates.py && python3 build/build_updates.py && python3 tests/updates_check.py` before any PR.
2. Keep `built_through` at the date of the newest source and `sources` complete; a topic may only cite sources that exist.
3. When something moves (date, time, place), change `when`/`deadline`, rewrite `summary` to the current truth, and add an `updates` entry saying what moved. Never delete history.
4. A topic that recurs each year (Community MfW, Ages & Stages) gets a new id per occurrence; the ledger is per school year.
5. Classroom topics (`kind: classroom`) carry a `section` (`ask`, `learning`, `homework`, `routines`, `specialists`, `resources`) and, for `ask`, an `items` list of questions. When a newsletter sends a new set of questions, replace `items` and record the old set in the update note; when a unit changes, rewrite the `learning` topic's summary and add an update.
