# Updates pipeline — school emails, organised

Scope: the **Updates** embed (`shared/updates/`), the topic ledger behind it, the full-text log of school emails, and the pipeline that turns forwarded email into both. Repo-wide rules (hosting, change control, personal data) live in `CLAUDE.md` and win over anything here. The *event* side of email (candidates for Important Dates, UIDs, approval queues) is in `docs/dates-pipeline.md`; this pipeline feeds it and does not change its rules.

Decided with Ahin 2026-10-31; publishing without a review step decided 2026-11-05 (see E1b). Status markers: **Built** / **Designed, not built** / **Needs Ahin**.

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
- CI runs all three on every PR (`build.yml`), and the embed deploys with everything else. `registry.yaml` lists the embed and its first slot: the 1st-grade site's **Email Digest** page, placed by Ahin 2026-11-02 with `?class=2034` in a 935 × 875 editor box (publishes 1154 × 1080 on a desktop, 352 × 329 on an iPhone 13; the first card's title, date, summary and action show without scrolling, measured live with Playwright). A 315px-wide phone needs one scroll to reach the button; a taller box would not fix that without making the desktop box very tall, so it stays.

**Needs Ahin (one-time setup; nothing else can run until these exist):**

1. ~~**Gmail forwarding.**~~ **Done 2026-11-01.** `sfquakerbot@gmail.com` is a confirmed forwarding address on Ahin's Gmail (confirmation clicked from the bot inbox), the account-level setting is *Disable forwarding*, and one filter `from:(veracross.com)` → *Forward it to sfquakerbot@gmail.com* does the forwarding. Every school broadcast goes through Veracross, and the five added streams have no subject pattern, so sender is the criterion. The 2026–27 history (68 Veracross emails, Aug 4 – Oct 29) was forwarded to the bot in one pass the same day, so the log can start at the start of the year. Forwarded copies are recognised by their original subject; "Fwd:" is stripped.
2. ~~**Bot mailbox access for Actions**~~ **Done 2026-11-02.** Ahin turned on 2-Step Verification on `sfquakerbot@gmail.com`, created the App Password "class-sites actions" and stored it as the `BOT_GMAIL_APP_PASSWORD` Actions secret. IMAP is always on in current Gmail (no toggle). The fetcher reads over IMAP; nothing is deleted or marked. (Why not the Gmail API: a consumer Gmail account cannot delegate to the service account, and an OAuth app in testing mode expires its tokens weekly.)
3. ~~**A Drive folder for the log**~~ **Done 2026-11-01.** `Class sites - email log` in the bot's Drive (folder ID `1sX6Gx_KS_xt8rb8BRPiY_wXwxqznhn2N`, stored as the `EMAIL_LOG_FOLDER_ID` Actions variable), shared as Editor with the service account `sf-quaker-bot@sffs-class-sites.iam.gserviceaccount.com`. The Google Docs API may still need enabling in the bot's Cloud project; the first run of the fetch job says so if it does.

**Built (E1a, E1b) and designed (E1c), in order:**

- **E1a: fetch and log — built 2026-11-02, running since; hourly since 2026-11-05.** `build/fetch_school_email.py`, run by `.github/workflows/email-log.yml` (hourly at :07 Pacific-agnostic UTC, and on demand; before 2026-11-05 it ran Wednesday 09:00 and Thursday 13:30 Pacific; a PR that touches the fetcher runs it as a dry run and puts what it would log in the job summary). IMAP as the bot, read-only, All Mail since 60 days before the school year's first day. Both shapes in the bot mailbox are handled: a filter-forwarded copy (original headers kept) and a manual "Fwd:" (date, sender and subject taken from the forwarded block). Each school email is classified into a stream by subject pattern (Circle Back, Room Parent Digest, Head's Desk, Grade Newsletter, Specialists Newsletter), else `[SFFS]` → School notices, else by grade words in the subject, then in the body (exactly one grade → that grade's teachers doc; two grades, or none → School notices). So the log has no separate PGA doc: a grade-specific PGA note sits in the grade's doc, the rest in School notices; the ledger's `pga` stream is a human classification and still links by subject and date. The Spanish half is dropped at a "Para español"-style marker or a rule line followed by Spanish; HTML becomes paragraphs, bullets and "label (url)" links; Veracross `/c/` tracking links are resolved to their destinations. The text is appended to `<stream label> <year> (email log)` in the Drive folder as a Heading 2 `Mon D, YYYY · <subject>` plus the body, keeping the email's structure (2026-11-02, Ahin's ask): the email's own headings become bold+underline+italic / bold+underline / bold / underline by level, inline bold, italic and underline runs are kept, bullets are `•`, plain-text `*bold*` becomes bold, and pointer lines like "Para español, mire más abajo" are dropped. `--rebuild` (the workflow's *rebuild* box) empties every doc and writes all emails again after a formatting change; one doc per stream per school year, shared "anyone with the link can view". **The docs are created by hand, as the bot account, in the log folder** (a service account has no Drive storage quota and cannot create files, found on the first real run 2026-11-02); the job names any doc that is missing and skips those emails until it exists. `shared/updates/sources.json` is the index: `{message_id, fingerprint, stream, year, date, subject, sender, doc_id, doc_url, anchor, logged_at}` per email, plus `docs`. A resend (same date and subject) is logged once, and an email whose heading is already in the doc is indexed from that heading rather than appended again, so a run is safe to repeat. The Google Docs API had to be enabled in the bot's Cloud project (done 2026-11-02). The job commits the index to the `email-log-auto` branch and opens one PR (body = what was logged, with links); since 2026-11-05 `deploy.yml`'s `automerge` job merges it once the `build` check passes, so no human step remains. `build/build_updates.py` merges the index into the ledger at build time (same date; subject equal, a part of an "A / B" subject, or a prefix of it), so History links start pointing at the full text as soon as the PR merges, and fills `log.docs`. `tests/test_fetch_school_email.py` covers all of this offline with made-up emails and runs in CI; `tests/validate_updates.py` checks the index (Veracross senders only, Docs links, no duplicates).
- **E1b: extract — built 2026-11-05.** The judgment step, run as the scheduled Claude routine **"Class sites: email extraction"** (hourly 7am–9pm Pacific, in Claude's cloud on Ahin's account, the repo cloned fresh each run; ROADMAP §G). Its stored prompt says only to read and follow `docs/extraction-routine.md`, so the rules live in the repo. Each run: `build/pending_emails.py --text` lists the indexed emails with no ledger source and fetches their text from the log Docs' plain-text export (no sign-in needed; the text is read, never committed); if none, the run ends in seconds. Otherwise the routine updates `data.json` (new topics, `updates` entries on existing ones, changed `when`/`deadline`/`summary`, a source entry per email read, `built_through`), runs the validator and build, commits with a plain-English message, pushes `updates-auto` and opens the PR (`updates-pr.yml` opens it if the routine could not). CI runs the full check, `automerge` merges, the site deploys, and `notify` emails Ahin. **Approval (decided 2026-11-05, Ahin):** none before publishing. Ahin had been the only approver since 2026-10-30; now the review is the notification email, and a correction is a follow-up PR. A room-parent queue still comes later with the approval app. `tests/test_pending_emails.py` covers the pending logic and the Doc slicing offline. **First real run 2026-11-05 20:35 PT** (minutes after PR #45 merged): 14 pending emails read, 7 topics added and 7 updated, pushed and opened as PR #46 by `updates-pr.yml` in 3 minutes; the routine's container has no Playwright and its permission check refuses `git push -f`, so the instructions use a plain push from the existing branch when one exists.
- **Notification — built 2026-11-05.** `build/notify_changes.py`, run by `deploy.yml`'s `notify` job after every push to main that touched `data.json` or `sources.json`: diffs the ledger and the index against the previous commit and emails one plain-English summary from `sfquakerbot@gmail.com` (SMTP with the same App Password) to the `UPDATES_NOTIFY_TO` Actions variable: new topics with date, time, place and audience; updated topics with the delta; the emails read, each with its full-text link; and a link to the page's What changed tab (`?class=2034&tab=changed`). Since 2026-11-06 each topic also says where it is filed: the tabs it appears under today (a port of the embed's tab rules, so a past event reads "What changed only, because the date has passed; it leaves the page on …") and which grade views show it (Ahin's ask after the first email left the Valkyries spirit day's place unclear). An index-only merge (emails logged, not yet read) sends a shorter note. `tests/test_notify_changes.py` covers the wording offline.
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

- **Circle of Friends support drives** name the person being supported and a parent's payment handle; the ledger keeps only that the committee exists and what it does. **Since 2026-11-05 the fetcher reduces any subject containing "Circle of Friends" to exactly that phrase** (`clean_subject`), because the subject is public in the index, the ledger, the PR body and the change email; `tests/validate_updates.py` fails on any other Circle of Friends subject in either file, and the three earlier ones were redacted the same day (Ahin's ask after "Welcome baby …" reached the page as a History label). The log Docs keep the original heading.
- **The 1st grade Star of the Week schedule** lists children's first names by week; the ledger keeps the format and says the schedule was emailed, and the teachers email each family the Friday before.
- **Room-parent recruiting emails** name volunteers and their children; the ledger keeps the role description.
- **Spanish and Chinese translations** in every email are dropped (English only, Ahin 2026-10-31).
- One short note, "Seeking volunteers for 3rd grade art class with Yara" (Oct 5), could not be read because of a connector rate limit; its content is the in-class art volunteering already in the ledger from the 3rd grade digest.

## How a session should work on this

The routine follows `docs/extraction-routine.md`, which restates these rules with the judgment calls spelled out. For a person:

1. `python3 tests/validate_updates.py && python3 build/build_updates.py && python3 tests/updates_check.py` before any PR.
2. Keep `built_through` at the date of the newest source and `sources` complete; a topic may only cite sources that exist.
3. When something moves (date, time, place), change `when`/`deadline`, rewrite `summary` to the current truth, and add an `updates` entry saying what moved. Never delete history.
4. A topic that recurs each year (Community MfW, Ages & Stages) gets a new id per occurrence; the ledger is per school year.
5. Classroom topics (`kind: classroom`) carry a `section` (`ask`, `learning`, `homework`, `routines`, `specialists`, `resources`) and, for `ask`, an `items` list of questions. When a newsletter sends a new set of questions, replace `items` and record the old set in the update note; when a unit changes, rewrite the `learning` topic's summary and add an update.
