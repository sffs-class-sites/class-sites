# CLAUDE.md — SFFS class sites

Context for any Claude session working in `sffs-class-sites/class-sites`. Keep this file current; it is the handoff between sessions and between people.

## What this is
Shared content for the San Francisco Friends School (SFFS) K–8 class Google Sites. Two sites exist today (1st and 3rd grade); nine are planned. Maintainer: Ahin, parent committee admin. Room parents and other volunteers are non-technical and must never need GitHub.

Working style: one item at a time. Don't anchor on a vendor or a design without checking alternatives. Say what was tested versus assumed.

---

## 0. Related docs and precedence — READ THIS BEFORE ANYTHING ELSE

Three separate Claude threads fed this repo. Their notes live here as scoped docs:

| Doc | Covers |
|---|---|
| `CLAUDE.md` (this file) | Architecture, hosting, embed delivery, directory layout, naming, change control, personal data — repo-wide |
| `docs/dates-pipeline.md` | Important Dates: event schema, UID rules, audience/grouping model, email ingestion, approval queues |
| `docs/schedules.md` | Class schedule one-pagers: PDF extraction, colour/icon map, time-axis merge, fillable PDF form fields |

**Precedence.** This file wins on anything repo-wide. A scoped doc wins on the internals of its own artefact — the colour map, the axis-merge algorithm, the event schema. **Where they conflict outside that split, stop and ask Ahin.** Do not average two numbers, do not assume the newer doc is right, do not quietly pick one and carry on.

The scoped docs were written for a single artefact built in a throwaway container. Their *reasoning* is sound and hard-won. Their *environment assumptions* are stale until you check them here.

### Known conflicts — flag these, don't resolve them yourself

1. **Sites scale factor.** This file says published ≈ editor × 1.234 (measured at a 1440px window). `docs/schedules.md` measured 1022 editor → 1154 published = × 1.129. Both were measured live. They cannot both be general. Most likely the factor depends on browser window width, which would make *both* numbers useless as constants. **Measure it as a function of window width before any doc states a number.**
2. **Embed delivery.** Shared embeds here go in by URL and update without touching Sites. `docs/schedules.md` builds a paste-in "Embed code" snippet. Pasted code was fine for two classes; at nine it means nine re-pastes per change. Decide whether schedules move to URL embeds.
3. **Directory and naming.** `docs/schedules.md` uses teacher-named class directories (`gavin/`, `nadia/`). This repo is class-based (`?class=2034`) precisely because teachers and grades change and a site lives nine years. Teacher-named paths break on the first teacher change.
4. **Two test harnesses.** This repo tests with Python + Playwright (`tests/render_check.py`). The schedules work uses Node + Playwright (`check.js`, `echeck.js`, `scrollcheck.js`, `fitcheck.js`, `mob.js`, `tap.js`, `shot.js`), asserting largely the same properties: no horizontal scroll, one scroll region, nothing overflows, the embed fills its frame. One repo should not carry two harnesses in two languages. Consolidating is real work and must not be done while also changing behaviour.
5. **UID rule vs. the code.** `docs/dates-pipeline.md` says `uid` is stored explicitly, assigned once at first approval, never recomputed. `build/build_important_dates.py` computes it from date + title. The doc is the decision; the code is the exception. See §8 step 1.
6. **Which way Google Sheets point.** §2 here treats Sheets as the authoring source a bot reads. `docs/schedules.md` treats its Sheet as a dead-end snapshot export that nothing reads back. Both are deliberate. Keep them distinct, and never let a contributor assume one behaves like the other.
7. **"No web fonts."** `docs/schedules.md` banned web fonts because that container blocked `fonts.googleapis.com`. GitHub Actions is not that container, so the stated reason no longer holds — but the rule should probably stay, because verifying with a font other than the one families see is how two of its bugs stayed hidden. Keep the rule, fix the reason.

## 1. Architecture (decided)

**Content lives in this repo, is built by GitHub Actions, and is served by GitHub Pages.** Each shared embed is placed in a Google Site once with **Insert → Embed → By URL → Whole page**. After that, repo changes reach every site within ~10 minutes (Pages sends `cache-control: max-age=600`) with no Sites edit and no republish.

**A site follows a class, not a grade.** Families keep one URL for nine years. Embed URLs name the class (`…/academics/?class=2034`) and the embed works out the grade at view time: `grade = 8 - (gradYear - schoolYearEndYear)`, rolling over in August (exact rollover date still to confirm with Ahin). A `?grade=N` override exists for previewing next year. Because the class is in the URL, **nothing in Google Sites changes at rollover**.

**Repo is public and stays public.** Considered and rejected going private: Pages from a private repo needs a paid plan, Actions minutes stop being free (unlimited for public repos; 2,000/month on Free, 3,000 on Team for private), and the published site is public either way. Private would protect history, not the page.

**Never transfer the repo.** GitHub redirects repository URLs after a transfer but *not* Pages URLs, which would break every embed. Ownership moves by adding/removing org owners.

## 2. Data sources and the content map

Humans author in Google Docs and Sheets. A `Site Map` sheet (authored by Ahin) is the index; the repo keeps a generated copy that agents read. Per source it records:

- **Drive file ID** (not a path — IDs survive renames and moves)
- **Shape**: one Doc split by grade headings, one file per grade, or a Sheet with a row/tab per grade
- **Key**: `grade` (academics), `school-year` (Important Dates), or `class` (room parents, teachers)
- **Publish list**: the exact columns or sections allowed on the site, plus who approved and when

**Fail closed.** Anything not on the publish list is never published, including newly added columns. Removing an entry removes it from the sites on the next sync.

## 3. Personal data: pattern A now, pattern B next school year

"Approved for the website" (the school's OK, recorded in the publish list) is not the same as "fine in permanent git history". So:

- **Non-personal content** (dates, academics, school hours) → data files in this repo, normal PR review.
- **Approved personal content** (room parent name/email, later student first names by class) → **never committed**. The master sheet is restricted to authorized accounts; a scheduled job signed in as the bot identity reads only the publish-list columns and writes a small extract that the embed fetches at view time.

**Pattern A (now):** restricted master sheet → published extract → public embed. Protects the master file and its extra columns; the displayed data is public, which matches today's public sites.

**Pattern B (next school year):** viewer must be signed in. Needs a Google Apps Script layer deployed to the school domain. Measured costs from earlier testing: 0.6–3.5s to load versus ~20ms for Pages, and one failure in ~16 loads. Required before publishing anything that must not be public, e.g. class lists. **Build A so the switch to B is a swap of the data source, not a rewrite:** keep fetching, rendering and formatting separate, and keep the data contract (the JSON shape) stable.

**Bot identity:** a dedicated account (service account, or a school user like `sites-bot@sffriendsschool.org`), view-only on the specific Drive folder, credential stored as a GitHub Actions secret. Never Ahin's personal account.

## 4. Change control

- A push to `main` publishes to every live site. `main` is production: all changes go through a pull request.
- `main` is protected by the ruleset **protect main** (id 24882477, active since 2026-10-11): require a PR (0 approvals), require the `build` check from GitHub Actions, block force-push and deletion, no bypass actors. Raise required approvals only once a second maintainer exists (GitHub won't let an author approve their own PR).
- A direct push to `main` is refused with `GH013: Repository rule violations` ("Changes must be made through a pull request", "Required status check \"build\" is expected"). Tested 2026-10-11.
- `SFQuakerBot` has write access, not admin, so it cannot edit or remove the ruleset. Ruleset changes are made by an org owner.
- Every PR must be reviewable without reading code: CI posts desktop + phone screenshots and a plain-English summary (events added/changed/removed).
- Rollback = revert the merge commit.

**Sheet-sourced personal data has its own approval, in the sheet:**

1. People edit a **Draft** tab. The sites read a protected **Live** tab, so half-finished edits never appear.
2. A **Publish** menu item (Apps Script) validates first: required columns, email format, known class year, no blank names, row count sanity.
3. On success it copies Draft → Live, writes date/who/what to a **Log** tab, and keeps the previous version in **History** for one-click revert.
4. Sites show the change within a few minutes (Google's published-file cache; exact duration untested).

## 5. Rules learned the hard way

- Google Sites' iframe sandbox is `allow-scripts allow-popups allow-forms allow-same-origin allow-popups-to-escape-sandbox allow-downloads allow-storage-access-by-user-activation` — **no top-level navigation**. Filters, month jumps and tabs must be `<button>` + JS (they work in place). Outbound links need `target="_blank" rel="noopener"`. Never `href="#…"`: it opened new windows on iOS Chrome.
- Embeds fill their frame: `html,body{height:100%}`, one scroll container, scroll-hint pill. Anything that auto-scrolls on load must retry — Sites lays the iframe out late.
- Sites scales embeds on publish: published ≈ editor × 1.234 at a 1440px window; phones get a ~315px frame that preserves the box's aspect ratio. Size boxes against the published page, never the editor.
- **No API exists for current Google Sites.** Placing or resizing an embed is manual; content changes never are.
- Claude in Chrome cannot click inside a cross-origin iframe on a published Site, and browser automation is expensive. Use Playwright in GitHub Actions (it can reach sites.google.com) for live-site checks; a human does a 2-minute desktop + iPhone check per new embed type.
- .ics UIDs must never change for an existing event or families' re-imports duplicate. Current UIDs: `<date>-<slug(title)>@sffs-calendar` (+`-2` for duplicates), matching the embed already live.

## 6. Decisions from Ahin's dates-pipeline work

- Store `uid` explicitly per event, assigned once, never recomputed from the title. **Todo:** freeze today's computed UIDs into `data.json` and make the build read them.
- Schoolwide events are one shared record with per-grade additions. `audience` = grouping key or grade list (Lower School K–4, Middle School 5–8); the resolved list is snapshotted at approval.
- Optional `start_time`/`end_time` (absent = all-day). When timing arrives, the all-day event is replaced by a timed event with a new UID.
- Per-event calendar adds are one-time copies. A subscribed .ics feed is deferred: dropping a UID from a feed deletes it from subscribers' calendars.
- Email ingestion and per-grade approval queues are designed, not built.

## 7. Current state

- `shared/important-dates/` → https://sffs-class-sites.github.io/class-sites/shared/important-dates/ — 30 events for 2026–27, byte-identical to the local build.
- Embedded by URL on the scratch site `sites.google.com/view/zz-sffs-embed-test-scratch-saf` (Ahin's personal Google account; delete once the pattern is proven). **The live 1st- and 3rd-grade homepages still carry the older pasted-code embed.**
- CI: validate data vs `source-2026-27.txt` → build → `tests/render_check.py` (Playwright; iframe with Sites' exact sandbox attributes; desktop/tablet/phone) → deploy.
- `main` ruleset is on (see §4).
- Not built yet: the `Site Map` index, Drive sync, the monitor/dashboard, PR screenshots.

## 8. Next steps (one at a time)

0. **Reconciliation pass, no code.** Read this file and both scoped docs. Confirm or add to the conflict list in §0. Produce one short memo: each conflict, the options, a recommendation, and what it costs. Change nothing until Ahin has answered. Anything you find that contradicts a decision in §1–§4 goes in the memo too.
1. Commit this file. Freeze explicit `uid`s into `shared/important-dates/data.json`; keep CI green.
2. ~~Turn on the `main` ruleset~~ (done 2026-10-11). Add the PR comment with screenshots and a plain-English change summary.
3. Playwright job that opens the published scratch Site and clicks into the embed (filter, month jump, add button) — proves live-site behaviour without browser automation.
4. Ahin swaps the live 3rd-grade homepage to the URL embed; human check desktop + iPhone; then 1st grade.
5. `Site Map` sheet + generated copy in the repo; Drive sync job (read via bot identity, open a PR with a readable diff).
6. First pattern-A embed: room parent contacts (Draft/Live/Log/History tabs, Publish menu item, extract, loading and failure states).
7. Monitor + Harvey-ball dashboard across all sites.

## 9. Scaling backlog (decisions still open)

1. **Rollover date** — August 1 or first day of school? What shows when next year's content isn't written yet: "coming soon" or last year's?
2. **Site URLs** — current published URLs contain the grade (`sffs-1st-class-page`). Class-based URLs (`sffs-class-of-2034`) are needed before families bookmark them; Sites likely does not redirect the old URL (untested).
3. **Site titles** are fixed text in Sites; make them class-based and let an embed show the grade.
4. **How parents submit changes** — email pipeline, Google Form, or both.
5. **Roles and access**, including yearly room-parent rotation, and a second maintainer.
6. **Site template** with pre-sized embed slots so no one measures boxes per site.
7. **Room-parent guide**: what to edit, what not to touch, how to request a change, how to undo.
8. **Alerts**: who hears about failed CI, failed deploys, red/amber monitor, pending approvals.
9. **Content standards**: accessibility checks in CI, Handbook accuracy with citations, search-engine indexing setting for sites showing personal data.
10. **Keep Claude usage low**: routine checks run in Actions; Claude handles submissions, new embed types and judgment calls.
