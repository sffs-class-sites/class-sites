# Extraction routine (E1b): turning new school emails into Updates

These are the working instructions for the scheduled Claude routine **"Class sites: email extraction"** (runs hourly at :50, 7am–9pm Pacific, after the :23 fetch, in Claude's cloud; configured at https://claude.ai/code/routines). The routine's stored prompt only says: clone the repo, read this file, follow it. Keeping the instructions here puts them under the same PR and CI gate as everything else (`CLAUDE.md` §4). A person running a session can follow the same steps.

Decided with Ahin 2026-11-05: ledger changes **publish without a review step**. The routine pushes a branch, CI checks it, a bot merges it, the site deploys, and `build/notify_changes.py` emails Ahin a plain-English summary with a link to the page. That email is the review; a mistake is fixed by a follow-up PR (or by replying to the email). Before this date Ahin approved every ledger change in the session that produced it.

Repo-wide rules still win: `CLAUDE.md` (personal data, change control) and `docs/updates-pipeline.md` (the ledger's shape and the rules at the bottom of it). Read both sections referenced below before editing.

## Steps

1. **Start from the latest main, or from the open branch.** Never force-push: the cloud session's permission check refuses `git push -f` (seen on the first run, 2026-11-05), and it is not needed. The `automerge` job deletes `updates-auto` when its PR merges, so the branch normally does not exist. If it does exist, an earlier PR is still open (its build failed, or it is mid-merge): build on it so a plain push fast-forwards.
   ```
   git fetch origin main
   if git fetch origin updates-auto 2>/dev/null; then
     git checkout -B updates-auto origin/updates-auto && git merge --no-edit origin/main
   else
     git checkout -B updates-auto origin/main
   fi
   git config user.name "SFQuakerBot" && git config user.email "sfquakerbot@gmail.com"
   ```
2. **Find what is new.** `python3 build/pending_emails.py --text --json "$RUNNER_TEMP/pending.json"` (any temp path). It lists every email in the email-log index (`shared/updates/sources.json`) that has no source in the ledger (`shared/updates/data.json`), with its cleaned English text from the log Doc. **If it prints "No pending emails", stop here** and reply with one line saying so. Do not push anything.
3. **Read the ledger.** `shared/updates/data.json`: `school_year`, `streams`, `sources`, `topics`. Also skim `shared/important-dates/data.json` (the official calendar) so you can mark `official: true` on topics that are already on it.
4. **Update the ledger** for every pending email, following the judgment rules below. For each email, whatever you decide about topics, **add a source entry** `{"id", "stream", "date", "subject"}` using the `suggested_id` and the index's stream, date and subject exactly (the build links it to the full text by date and subject). Set `built_through` to the newest source date.
5. **Check.** All of these must pass; fix the ledger until they do:
   ```
   python3 tests/validate_updates.py
   python3 build/build_updates.py
   python3 tests/test_pending_emails.py
   python3 build/pending_emails.py        # must now say "No pending emails"
   python3 tests/updates_check.py         # only if Playwright is installed (it is not in the routine's container); CI runs it regardless
   ```
6. **Commit and push.** One commit. The first line is the PR title, the body is the PR body; both are read by people who will not open the JSON:
   ```
   Updates: 2 new topics, 3 updated (emails of Nov 3–4)

   New:
   - Craft Fair, Sat Dec 12 10am–2pm at SFFS (everyone). Table sign-ups open.
   - Winter enrichment registration opens Wed Nov 11, 7pm (everyone).
   Updated:
   - Fall play: tickets on sale, link added.
   Emails read: Nov 3 [SFFS] Save the Date! Craft Fair…; Nov 4 SFFS 1st Grade | Room Parent Digest | 11-03-26; …
   ```
   Then `git push -u origin updates-auto` (no `-f`) and `gh pr create --head updates-auto --base main --fill || true`. If `gh` is not signed in, the push alone is enough: `.github/workflows/updates-pr.yml` opens the PR from the commit message (that is what happened on the first run; `gh` was not needed). CI runs, `deploy.yml`'s `automerge` job merges it once the `build` check passes, the site deploys, and the notification email goes out. You are done; say in one line what you pushed.
7. **If something cannot be resolved** (an email you cannot read, a check that will not pass, a personal-data question), do not push a half-done ledger. Push nothing, and open an issue: `gh issue create --title "Email extraction needs a look" --assignee Ahin-SFFS --body "<what happened, which emails>"` (or say so in your reply if `gh` is unavailable). The emails stay pending and the next run tries again.

## Judgment rules

The unit is a **topic**: one record per thing the school is telling families about, with a history of how it changed. Most of every email repeats last week's email; the ledger records the **delta**.

- **Existing topic, nothing new:** add nothing to the topic. (The source entry is still added, so the email is not pending next time.) A Circle Back item repeated word for word, or a digest's "schoolwide highlights" restating Circle Back, is not news.
- **Existing topic, something changed** (a date, time or place; an RSVP link or form appears; "coming soon" becomes "on sale"; a total is updated; a reminder names a new deadline): change `when` / `deadline` / `links` / `action` to the **current truth**, rewrite `summary` so it reads as true today, and append `{"source", "date", "note"}` to `updates` with the delta in plain words ("Moved to Nov 20.", "RSVP form added.", "Now $41,200 of $150,000."). Never delete history or an earlier update.
- **New thing:** a new topic. `id` is a lowercase slug, descriptive, with the year or month when the thing recurs (`craft-fair-2026`, `community-mfw-2026-12-02`). `kind`: `event` (has a `when`), `deadline` (the date that matters is the deadline: orders, sign-ups, forms), `notice`, `volunteer`, `letter` (Head's Desk), `classroom` (teachers' and specialists' newsletters; needs `section` ∈ learning, ask, homework, routines, resources, specialists, and `items` for `ask`). `audience`: `all`, `lower` (K–4), `middle` (5–8), or a grade list such as `["1"]`. Grade digests and grade teachers' emails are that grade's audience unless the item is plainly schoolwide. `when` = `{date, end?, start_time?, end_time?, location?}`, times `HH:MM` 24-hour; absent times mean all-day. `deadline` = `{date, what}`. `action` is the verb a parent needs ("RSVP", "Sign up", "Order"). `links` are final destinations with a label; the log text already resolved tracking links, but never store a `veracross.com/c/` URL. The first `updates` entry is the announcement ("Announced.", "Sent.").
- **Already on Important Dates** (same event in `shared/important-dates/data.json`): `official: true`, and the topic may still carry the email's extra detail.
- **Classroom content** (`kind: classroom`): a newsletter's "questions to ask", "what we're learning", homework, routines, resources and the specialists' sections each map to one topic per grade (or `lower` for specialists). When a newsletter sends a new set of questions, replace `items` and say in the update note that the earlier set was replaced; when a unit changes, rewrite the `learning` topic's summary and add an update.
- **Head's Desk** letters: one `letter` topic per letter, titled "Head's letter: <gist>", summary in a few lines, plus separate topics for anything actionable the letter announces.
- **Personal data stays out** (`CLAUDE.md` §3, `docs/updates-pipeline.md`): no parent or student names (room-parent sign-offs included), no home addresses, no phone numbers, no personal email addresses. School staff names and `@sffriendsschool.org` addresses are fine. When an item needs a personal detail (a party at a family's home, an RSVP to a parent), write "see the email" and let the History link lead to the full text. `tests/validate_updates.py` enforces most of this; it does not catch a name, so you must.
- **Circle of Friends emails** (meal trains, support for a family or staff member): no names anywhere, not the person being supported, not a baby, not the organisers, not in the title, summary or update notes. Say "a staff member", "a 1st grade family". The subject is already reduced to "Circle of Friends" by the fetcher (Ahin, 2026-11-05); keep the source entry's subject exactly that.
- **English only.** The log already dropped the Spanish half; if any remains, ignore it.
- **Emails older than `built_through`** can appear pending: the hand-built ledger named some sources differently or left a few out on purpose (`docs/updates-pipeline.md`, "What was left out, deliberately"). Add the source entry. If the email's content is already in a topic, attach nothing or at most one `updates` entry on that topic; **never create a second topic for the same thing.**
- **Resends** (same subject, different day) and the same news in two grade digests: one topic; at most one update note per email that actually adds something.
- **Ids never change** once published: never rename a topic id or a source id, never delete a topic. Something no longer true gets a dated update note ("Cancelled.") and, for events, keeps its `when`.
- When in doubt between two topics, prefer attaching to the existing one. When in doubt whether a detail is personal, leave it out and say "see the email".
