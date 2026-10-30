# Important Dates pipeline

Scope: the Important Dates embed and the email-to-event pipeline that will feed it. Repo-wide concerns — hosting, embed delivery, change control, personal data — live in `CLAUDE.md` and win over anything here.

> **Provenance.** Reconstructed from the decision record of the "Extract dates f/ email" conversation, not written by that conversation. The decisions below are reliable. Implementation detail that was never written down is missing — see **Known gaps** at the end. Treat this as a complete record of *what was decided* and an incomplete record of *what was built*.

## Current state (updated 2026-10-30)

- The embed is live on the 1st grade (Class of 2034) and 3rd grade (Class of 2032) Home pages as a **URL embed** built from `shared/important-dates/data.json` (swapped 2026-10-30, `CLAUDE.md` §7). No hand-pasted copy remains; the last pasted copy is kept locally, uncommitted, for rollback.
- 30 events for 2026–27, each with a stored `uid`. `audience`, `start_time` and `end_time` are in the schema below but not yet in `data.json` or the build (`docs/ROADMAP.md` D2).
- Email ingestion and approval: designed, decisions recorded below, nothing built (`docs/ROADMAP.md` §E).

## UID rules — the part that must not be got wrong

A UID is the hidden identifier that travels into a parent's calendar when they add an event. Get it wrong and families get duplicates.

- **`uid` is stored explicitly on each event**, assigned once at first approval, and **never recomputed from the title**. Renaming an event changes the title only.
- Retired UIDs stay on the record for near-match provenance. They are never reused.
- **Done 2026-10-11:** `data.json` stores each event's `uid` and the build reads it; the frozen values were checked against both live pasted embeds and match exactly. History: the code used to derive the UID from date + title slug. That derivation was itself a fix for an earlier row-index-based scheme, and shipping it cost one accepted round of duplicates for families who had imported before the fix. The frozen values had to match the live embeds exactly, or that cost would have been paid a second time.

## Event schema

- `uid` — see above.
- `audience` — either a grouping key or an explicit grade list. Groupings are **data in a registry**, extensible beyond the first two.
  - Lower School = K–4. Middle School = 5–8. SFFS says "Middle School", not "Upper School" (Family Handbook §12–13).
  - The **resolved** grade list is snapshotted onto the event at approval, so redefining a grouping later cannot silently change already-approved events.
- `start_time` / `end_time` — optional. Absent means all-day; present means timed.
- Per-grade verdicts live on one shared record: approved / rejected / pending tracked per grade, while date and title stay shared.
- Per-grade overrides carry only what differs — usually a time.
- Grade is **computed, never stored**: `grade = 8 - (gradYear - schoolYearEndYear)`, rolling over on the last day of school (Ahin, 2026-10-30). The same config block drives header strings like "Welcome to X grade (Class of Y)".

## Schoolwide events

One shared record that every site renders, with per-grade additions. **Not** copies per grade. This is what makes a schoolwide date correctable in one place.

## All-day → timed transition

The annual Important Dates release publishes everything as all-day. When a real time arrives later:

1. The all-day event is **removed** from the embed.
2. A timed event **with its own new UID** replaces it.

Early importers keep their all-day block, because per-event adds are detached copies. Parents who didn't import are assumed not to have wanted it, and get only the timed version.

**This design depends on per-event adds being one-time copies.** A subscription feed inverts it: dropping a UID from a subscribed feed *deletes* it from subscribers' calendars. A feed therefore cannot be added later without revisiting this rule.

## Calendar update behavior (researched, not assumed)

- Per-event Google deep links and .ics downloads are **one-time copies**. Editing the embed never reaches a calendar a parent has already added to.
- Only a **subscribed** .ics feed pushes updates. Apple refreshes roughly hourly, user-configurable down to 5 minutes. Google refreshes every 12–24 hours with no faster setting available.
- A feed is **deferred**, for the reason in the section above.

## Email ingestion and approval (designed, not built)

- All school email forwards to one fixed address, **plus-addressed with the class graduation year** (`…+2034@…`) to identify the grade.
- Room parents forward school email, so the same event arrives several times, worded differently, days apart. **Dedupe must work across queues**, not within one.
- Near-match surfaces ranked candidates with reasons. Three options per candidate: edit-of-existing, genuinely new, ignore.
- Decisions are stored as **aliases in a ledger**, so a phrasing seen before resolves silently and is never surfaced again.
- Routing:
  - Event matching a pre-existing grouping → admin (Ahin) queue.
  - Multi-grade with no pre-existing grouping → each grade's room parent.
  - Ahin owns the schoolwide queue; one designated room parent per grade owns that grade's queue. **Designation mechanism is undecided.**
- Room parents may approve, reject, or request changes to the event record. Anything beyond that routes to Ahin.
- Any one room parent can reject independently; it does not affect other grades' decisions.
- A scope change (grade → schoolwide) **escalates to Ahin** rather than executing.

## Email pipeline: decisions made 2026-10-30

These settle the "where does it run and who approves" questions above. Build order is in `docs/ROADMAP.md` §E.

- **Build ingestion and extraction first, with no app.** Ahin is the sole approver until the approval app exists; candidates are reviewed in the Claude session or PR that produced them.
- **Approval app on Cloudflare Workers + D1**, chosen over Google Apps Script so the app's code lives in this repo under the same PR + CI gate as everything else. (Apps Script code lives in Google's editor, outside change control.)
- **Security by unlisted URL is accepted** for the approval app. No sign-in layer at first; the URL is shared only with the designated approvers. Revisit if the app ever shows more than event candidates.
- **Pilot on 1st and 3rd grade together** (the two live sites), then the **next wave is kindergarten and 2nd grade**.
- **Volume target:** roughly 15 school emails per grade per month, across nine grades, so about 135 a month at full scale. Dedupe across queues matters at that volume because most of those are the same schoolwide email forwarded by several room parents.
- Still undecided: how a room parent is designated as a grade's approver and how that rotates yearly (`docs/ROADMAP.md` E4), and where raw emails and the alias ledger are stored (`CLAUDE.md` §0 item 13; the recommendation there is restricted Drive, with D1 now a second candidate for the ledger).

## Environment assumptions (verify these)

Everything in this section was true of a browser-driven workflow on a personal laptop. The repo now builds in GitHub Actions, so re-check each one.

- Browser automation against Google Sites timed out frequently on the personal laptop, suspected to be concurrent Claude sessions contending for the Chrome extension. GitHub Actions has no such contention.
- Google Sites has no API, so placing or resizing an embed box stays a manual browser step. Content changes do not.
- Identity: one institutionally-named Gmail account for the class-sites work, since it will be handed to a successor. **Confirmed 2026-10-30: it is `sfquakerbot@gmail.com`** (`CLAUDE.md` §3). The school-domain address is deferred because the school account cannot share files outside the school; the design should still migrate without pausing work when that changes.
- No pixel measurements were recorded by this pipeline. Embed sizing is settled in `CLAUDE.md` §0 item 1: there is no scale factor; a box's shape carries over.

## Known gaps

Things that were decided but whose implementation detail is not recorded here, because it was never written down:

- How events are actually extracted from an email — prompt design, what fields are parsed, how dates in prose are interpreted, handling of date ranges and ambiguous years.
- The near-match scoring itself: what makes two events a candidate pair, and how candidates are ranked.
- The ledger's storage format and where it lives.
- How approvers authenticate beyond the unlisted URL (decided 2026-10-30: the queues are presented by an app on Cloudflare Workers + D1, see above).
- ~~Whether any of this was built, or whether it is all design.~~ It is all design (confirmed 2026-10-30).

If a future session needs one of these, ask Ahin before inventing it.
