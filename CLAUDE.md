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
| `docs/swap-to-url-embed.md` | Human checklist: swap a site's pasted copy to the URL embed, check desktop + iPhone, undo, then update `registry.yaml` |
| `docs/ROADMAP.md` | What's next, in order (sections A–G); the first thing a new session or parent reads. Keep it current when a step finishes |

**Precedence.** This file wins on anything repo-wide. A scoped doc wins on the internals of its own artefact — the colour map, the axis-merge algorithm, the event schema. **Where they conflict outside that split, stop and ask Ahin.** Do not average two numbers, do not assume the newer doc is right, do not quietly pick one and carry on.

The scoped docs were written for a single artefact built in a throwaway container. Their *reasoning* is sound and hard-won. Their *environment assumptions* are stale until you check them here.

### Known conflicts — flag these, don't resolve them yourself

Reconciled 2026-10-11 (§8 step 0). Each item is **Open**, **Decided** or **Resolved** (done); a decided item records Ahin's answer and when. Decided means the direction is set, not that it is built. An open item still needs Ahin.

1. **Sites scale factor — Resolved 2026-10-11: it isn't a scale factor.** `tests/live_check.py` measured the Important Dates frame on the published scratch Site. Width = Sites' content column: 905px at a 1024px window, and 1154px at 1280, 1440 and 1920 (that's the maximum). Height = width × the editor box's height ÷ width, which stayed 0.586–0.587 at every width, including an iPhone 13 (352 × 206). The 1.234 and 1.129 figures were 1154 divided by the editor canvas width in two different browser windows. Size a box by its **shape** (h ÷ w); published width is at most 1154. The daily live check re-measures and reports this table.
2. **Embed delivery — Decided 2026-10-11: schedules move to URL embeds** (served from Pages, placed once per site), like every other shared embed. `docs/schedules.md`'s paste-in "Embed code" snippet is superseded; the 2 existing pasted schedule embeds get re-placed once, after the schedules code is in this repo (#4).
3. **Directory and naming — Open (direction follows from #8).** `docs/schedules.md` uses teacher-named class directories (`gavin/`, `nadia/`). This repo is class-based (`?class=2034`) because teachers and grades change and a site lives nine years. Recommended: class-keyed paths, with teacher names and the year's sections as data. Apply when the schedules code moves in.
4. **Two test harnesses — Open: waiting on Ahin for where the schedules code lives.** The schedules code (`sched/`, `check.js`, `echeck.js`, `scrollcheck.js`, `fitcheck.js`, `mob.js`, `tap.js`, `shot.js`) is not in this repo. This repo tests with Python + Playwright (`tests/render_check.py`); the schedules checks are Node + Playwright and assert largely the same properties. Recommended: move the schedules code in unchanged, then port the checks to Python in a separate PR with identical assertions, before any behaviour change.
5. **UID rule vs. the code — Resolved 2026-10-11.** Each event in `shared/important-dates/data.json` now stores its `uid`, and `build/build_important_dates.py` reads it and refuses to build if one is missing or duplicated. Before freezing, the live pasted embeds on the 1st- and 3rd-grade homepages were run in headless Chromium and their "Download all dates" .ics was compared with the build: all 30 UIDs, dates and titles matched exactly, on both pages.
6. **Which way Google Sheets point — Open.** §2 here treats Sheets as the authoring source a bot reads. `docs/schedules.md` treats its Sheet as a dead-end snapshot export that nothing reads back. Both are deliberate; keep them distinct, and never let a contributor assume one behaves like the other. The schedules Sheet is shared *Anyone with the link → Editor*, so anyone can deface it. Recommended (manual, ~2 min): set it to Viewer and add "(snapshot, not read back)" to its title.
7. **"No web fonts" — Resolved 2026-10-11 (wording fixed in `docs/schedules.md`).** `docs/schedules.md` banned web fonts because its container blocked `fonts.googleapis.com`. That reason no longer holds in GitHub Actions. Keep the rule with a new reason: CI on Linux renders with fallback fonts (DejaVu/Liberation), not the San Francisco or Segoe families see, so verify against the widest likely font, and a web font would hide that.
8. **Class vs. section — Decided 2026-10-11: children are reshuffled into new sections every school year, and schedules are made new every year.** A section (1A, 1B) is not a stable identity, so it must never be part of a long-lived URL: a family's bookmark for "section A" would show a different group of children next year. Follows from this: schedule embeds stay keyed by class (`?class=2034`), and each year's sections and their schedules are dated data inside that class, chosen in the embed. Exact UI (both sections shown, or a section picker) is open.
9. **§1's design isn't built, and §7 doesn't say so — Resolved 2026-10-11: §7 now lists it under "Not built yet".** There is no `?class=` handling or grade calculation yet, only one Important Dates URL serving all grades, and `data.json` has `uid` (item 5) but not the other dates-pipeline fields (`audience`, `start_time`). §7 should list these as not built.
10. **`registry.yaml` keyed sites by grade — Decided 2026-10-11: rekeyed to `class-2032` (3rd grade in 2026–27) and `class-2034` (1st grade).** Its comment no longer states 1.234 or cites a "playbook §2.1" that isn't in the repo. Site names and URLs still contain the grade (§9 items 2–3).
11. **Extra hosting locations — Open (part of the schedules move).** Schedules publish a claude.ai artifact page tied to one person's account, and a PDF on Drive (`pdf_url`). That contradicts §1. Recommended: serve the page and the PDF from Pages under the class path.
12. **Room-parent approval vs. the PR gate — Decided 2026-10-11: (a) a bot opens the PR, links the room-parent approval record, and auto-merges once CI passes; the room-parent approval is the human review.** Ahin does not merge every PR. With 0 required approvals the ruleset already gates only on `build`, so no ruleset change is needed. §4 needs a matching line; the auto-merge job is built with §8 step 5. §4 line added 2026-10-11.
13. **Personal data in email ingestion — Open (design constraint).** Forwarded school emails carry family and staff names and addresses, and the alias ledger's storage is undecided. Recommended: raw emails and the ledger live in restricted Drive; the repo receives only approved event records (§3).
14. **Identities are scattered — Resolved 2026-10-11: one table in §3.** The bot rows were confirmed 2026-10-30 (`sfquakerbot@gmail.com` is the Drive and Gmail bot; school-domain address deferred); only "who else edits the live Sites" is still *unconfirmed*. `docs/dates-pipeline.md` says the bot is a Gmail account; §3 says a service account or school user. The scratch site sits on Ahin's personal Google account, and the GitHub bot is an org owner. Recommended: one table in §3 listing each identity, what it can access, and whether it exists yet.

## 1. Architecture (decided)

**Content lives in this repo, is built by GitHub Actions, and is served by GitHub Pages.** Each shared embed is placed in a Google Site once with **Insert → Embed → By URL → Whole page**. After that, repo changes reach every site within ~10 minutes (Pages sends `cache-control: max-age=600`) with no Sites edit and no republish.

**A site follows a class, not a grade.** Families keep one URL for nine years. Embed URLs name the class (`…/academics/?class=2034`) and the embed works out the grade at view time: `grade = 8 - (gradYear - schoolYearEndYear)`, rolling over on the **last day of school** (Ahin, 2026-10-30; replaces "August 1"). A `?grade=N` override exists for previewing next year. Because the class is in the URL, **nothing in Google Sites changes at rollover**.

*Built 2026-10-31:* `shared/class/class.js` is the model (inlined into every shared embed by `build/classinfo.py`, which mirrors it in Python for builds and tests), and `shared/school-years.json` holds each year's first and last day. **Add next year's row there when the school publishes its calendar**; until then the embeds assume the year ends June 30. Kindergarten is grade 0; before K the class is "not yet at SFFS", after 8th "graduated". The live embeds are still placed without `?class=` (one calendar for every grade); they get `?class=` when per-class filtering exists (`docs/ROADMAP.md` D3), so the Sites edit happens once.

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

**Bot identity (decided 2026-10-30):** `sfquakerbot@gmail.com` is the bot's Google account and `SFQuakerBot` its GitHub account. The Drive reader is a Google Cloud service account under that Gmail's project, view-only on the Site Map sheet, key stored as the `GOOGLE_SERVICE_ACCOUNT_JSON` Actions secret. A school-domain bot address is **deferred**: the school account cannot share Workspace files outside the school (see `classpages@` below), so migrating to it would stop the work. Never Ahin's personal account.

**Identities** (checked 2026-10-30 unless marked *unconfirmed*):

| Identity | What it is | Can access | Exists? |
|---|---|---|---|
| `Ahin-SFFS` | Ahin's GitHub account | Org owner (admin on every repo) | Yes |
| `SFQuakerBot` | GitHub account Claude sessions use; commits as `sfquakerbot@gmail.com` | **Org member with write on this repo** (demoted from owner 2026-10-31; confirmed through the API: org role `member`, repo permission `write`, `admin: false`). Token scopes `repo`, `workflow`, `read:org`, `gist` | Yes |
| `github-actions[bot]` | Per-run token inside workflows | What each job's `permissions:` grants: PR comments, issues for alerts, Pages deploy | Yes |
| `sfquakerbot@gmail.com` | Gmail behind the GitHub bot, and the "institutionally-named Gmail" `docs/dates-pipeline.md` planned for Drive (confirmed 2026-10-30). Owns the Google Cloud project and the Site Map sheet | Its own Drive; later the Gmail connector for email ingestion (`docs/ROADMAP.md` §G) | Yes |
| Drive bot identity (§3) | Service account in `sfquakerbot@gmail.com`'s Google Cloud project; reads the publish-list columns | View-only on the Site Map sheet; key in the `GOOGLE_SERVICE_ACCOUNT_JSON` secret | Yes (2026-10-30); first real sync opened PR #18 |
| School-domain bot address | e.g. `sites-bot@sffriendsschool.org`; would replace the Gmail bot | Same as above | **No — deferred** (school sharing limits; see bot identity above) |
| Ahin's personal Google account | Owns the scratch Site (§7) | Scratch Site | Yes; scratch Site to be deleted once proven |
| `classpages@sffriendsschool.org` | School account for the class sites; meant to become the service identity | Admin on the 1st- and 3rd-grade Sites. **Cannot share Workspace files with accounts outside the school** (school setting), so during development parents use their own accounts; once a finished site can be shown, the school is to allow a fixed set of parents to share with school accounts | Yes (Ahin, 2026-10-30). A Claude session drove the Sites editor as this account on 2026-10-30, signed in by Ahin in a local browser profile; publishing stayed with Ahin |
| School Google accounts | Edit the live class Sites on `sffriendsschool.org` | Live Sites | Yes; *unconfirmed* who else holds edit access |

Actions configuration (set 2026-10-30): secrets `GOOGLE_SERVICE_ACCOUNT_JSON` (Drive bot key) and `SYNC_BOT_TOKEN` (fine-grained token for `SFQuakerBot`, this repo only, pull-request write; needed because PRs opened with `github.token` never trigger the required `build` check); variable `SITE_MAP_SHEET_ID`.

## 4. Change control

- A push to `main` publishes to every live site. `main` is production: all changes go through a pull request.
- `main` is protected by the ruleset **protect main** (id 24882477, active since 2026-10-11): require a PR (0 approvals), require the `build` check from GitHub Actions, block force-push and deletion, no bypass actors. Required approvals stay at 0: **there is no second maintainer, by choice** (Ahin, 2026-10-30; accepted risk). Everything here assumes no second reviewer, so CI is the gate. GitHub won't let an author approve their own PR, so raising approvals would block Ahin.
- A direct push to `main` is refused with `GH013: Repository rule violations` ("Changes must be made through a pull request", "Required status check \"build\" is expected"). Tested 2026-10-11.
- `SFQuakerBot` (the GitHub account Claude sessions use) was an org owner during setup and is an **org member with write access** since 2026-10-31 (§9 item 11). It can open, push to and merge PRs but cannot change rulesets, repo settings, secrets or org membership; those are `Ahin-SFFS`'s alone.
- The ruleset has no bypass actors, so the bot **cannot** push past it (verified 2026-10-11 while it was still an owner). No session should change rulesets, branch settings or org membership without Ahin asking for it in that session; since the demotion the bot cannot anyway.
- Every PR must be reviewable without reading code: CI posts desktop + phone screenshots and a plain-English summary (events added/changed/removed).
- **Who merges** (§0 item 12): content PRs from the approval pipeline are merged by the bot once CI passes; the room parent's approval, linked in the PR, is the human review. Ahin does not merge every PR. The repo's auto-merge setting is off, so the job merges explicitly; turning the setting on is Ahin's call (§4 residual risk).
- Rollback = revert the merge commit.

**Sheet-sourced personal data has its own approval, in the sheet:**

1. People edit a **Draft** tab. The sites read a protected **Live** tab, so half-finished edits never appear.
2. A **Publish** menu item (Apps Script) validates first: required columns, email format, known class year, no blank names, row count sanity.
3. On success it copies Draft → Live, writes date/who/what to a **Log** tab, and keeps the previous version in **History** for one-click revert.
4. Sites show the change within a few minutes (Google's published-file cache; exact duration untested).

## 5. Rules learned the hard way

- Google Sites' iframe sandbox is `allow-scripts allow-popups allow-forms allow-same-origin allow-popups-to-escape-sandbox allow-downloads allow-storage-access-by-user-activation` — **no top-level navigation**. Filters, month jumps and tabs must be `<button>` + JS (they work in place). Outbound links need `target="_blank" rel="noopener"`. Never `href="#…"`: it opened new windows on iOS Chrome.
- Embeds fill their frame: `html,body{height:100%}`, one scroll container, scroll-hint pill. Anything that auto-scrolls on load must retry — Sites lays the iframe out late.
- Sites sizes a published embed by the editor box's **shape**, not a scale factor: width = the content column (max 1154px, from a ≥1280px window; 905px at 1024), height = width × box h ÷ w. Phones keep the same shape, so a wide box is a letterbox on a phone: Important Dates is 352 × 206 on an iPhone 13. Measured 2026-10-11 (§0 item 1).
- Important Dates on a phone shows the next three dates without scrolling, everything else behind the scroll. Below 400px the embed switches to a compact layout (one line per date, category as a coloured edge, badge and details on tap, a "Full page" link), so that needs a box with **h ÷ w ≥ 0.67** (worst day of the year, 315px phone, measured 2026-10-31; it was 0.95 before the compact layout). `tests/render_check.py` fails CI if a 315 × 210 frame shows fewer than three on any day, and checks tap-target size, text size, the tap-to-open details and the full-page link at phone widths. Recommended editor box: 935 × 625.
- **No API exists for current Google Sites.** Placing or resizing an embed is manual; content changes never are.
- Claude in Chrome cannot click inside a cross-origin iframe on a published Site, and browser automation is expensive. Use Playwright in GitHub Actions (it can reach sites.google.com) for live-site checks; a human does a 2-minute desktop + iPhone check per new embed type.
- .ics UIDs must never change for an existing event or families' re-imports duplicate. Each event's `uid` is stored in `data.json` and never recomputed. The 2026–27 values were frozen from the old derivation `<date>-<slug(title)>@sffs-calendar` (+`-2` for duplicates) and match the live pasted embeds; a new event gets its uid once, at approval.

## 6. Decisions from Ahin's dates-pipeline work

- Store `uid` explicitly per event, assigned once, never recomputed from the title. Done for 2026–27 (2026-10-11): frozen into `data.json`, and the build reads them.
- Schoolwide events are one shared record with per-grade additions. `audience` = grouping key or grade list (Lower School K–4, Middle School 5–8); the resolved list is snapshotted at approval.
- Optional `start_time`/`end_time` (absent = all-day). When timing arrives, the all-day event is replaced by a timed event with a new UID.
- Per-event calendar adds are one-time copies. A subscribed .ics feed is deferred: dropping a UID from a feed deletes it from subscribers' calendars.
- Email ingestion and per-grade approval queues are designed, not built.

## 7. Current state

- `shared/important-dates/` → https://sffs-class-sites.github.io/class-sites/shared/important-dates/ — 30 events for 2026–27, byte-identical to the local build.
- Embedded by URL on the scratch site `sites.google.com/view/zz-sffs-embed-test-scratch-saf` (Ahin's personal Google account; delete once the pattern is proven). The live 1st- and 3rd-grade homepages switched to the URL embed on 2026-10-30 and were resized on 2026-10-31 to 935 × 625 in the editor (h ÷ w 0.668) once the compact phone layout landed: published 1154 × 770 on a desktop and 352 × 235 on an iPhone 13, 4 dates visible without scrolling (measured on both live pages with Playwright). A Claude session did the resize in Chrome as `classpages@`; Ahin clicked Publish. No pasted copy is live any more; the last one is kept locally (not committed) in case of rollback.
- CI: validate data vs `source-2026-27.txt` → build → `tests/render_check.py` (Playwright; iframe with Sites' exact sandbox attributes; desktop/tablet/phone) → deploy. Daily, `.github/workflows/live-check.yml` opens the published scratch Site and clicks inside the embed (`tests/live_check.py`); a failure opens one issue assigned to Ahin-SFFS and it closes itself on the next pass. On a PR, the `pr-comment` job (not a required check) posts one comment, updated on every push: Important Dates events added/changed/removed, matched by `uid` (`tests/pr_summary.py`), plus links to each screenshot. The links need a GitHub login and expire after 90 days; screenshots are never committed (§3).
- `main` ruleset is on (see §4).
- Monitor: `tests/monitor.py` runs in every deploy and daily, and writes https://sffs-class-sites.github.io/class-sites/status/ from `registry.yaml` (plain HTTP, no browser). Per slot: URL embed present = green; old pasted copy = amber, with its hash compared to the recorded one; missing or page down = red; a `type: code` embed (pasted by design, e.g. the Class of 2034 glitter list) = green when present with its recorded hash, amber if edited since. Red opens one issue for Ahin-SFFS and it closes itself when fixed. Amber never alerts.
- Site Map: `build/sync_site_map.py` turns the sheet into `site-map.yaml` (generated; do not edit). It fails closed: a source is `publishable` only with Sync = Yes, a Drive file ID, a publish list, Approved by and Approved on; `tests/test_site_map.py` checks this in CI. `sync-site-map.yml` runs daily as the Drive bot and opens a PR when the sheet changes; configured 2026-10-30 (§3), first real run opened and merged PR #18 the same day. The sheet lives in `sfquakerbot@gmail.com`'s Drive (ID in the `SITE_MAP_SHEET_ID` variable). Put a role, not a person's name, in Approved by, since it lands in public git.
- Room parents (pattern A), **live since 2026-10-31** on the 1st-grade homepage (`?class=2034`, replacing the pasted glitter list): `shared/room-parents/?class=YYYY` fetches `data/room-parents.json` at view time and shows loading, loaded, empty, not-published and error states. `build/extract_room_parents.py` writes that file at deploy time from the master sheet's Live tab (sheet `1no4dA_ot7Hg3KTQLN1uFsUUn3IH6H3EIatn7arrZxNs`, in Ahin's Drive, service account as reader), keeping only publish-list columns, and only because the Site Map marks room-parents publishable (approved by School administration, 2026-10-31); an invalid row writes nothing and fails the deploy. The extract is never committed. The master sheet has Draft, Live, Log and History tabs; **`apps-script/room-parents/Code.gs` is not installed yet** (the Sites-to-Apps-Script hand-off failed with a Google error on 2026-10-31; until Ahin pastes it in, Live is edited by hand and the Log tab is filled by hand). `tests/room_parents_check.py` covers all three with fake people. The JSON shape in `build/build_room_parents.py` is the contract pattern B must keep.
- Class and grade model (§1): built 2026-10-31. Both shared embeds read `?class=`, `?grade=` and `?today=`; Important Dates shows a "1st grade · Class of 2034" line when placed with `?class=`, Room Parents titles itself by grade. `tests/test_classinfo.py` (Python) and `tests/render_check.py` (browser) check the same table, including both sides of the last-day-of-school rollover.
- Not built yet: the room-parents Publish menu is not installed (above); the 3rd-grade room-parent list is still plain text on its site. One Important Dates URL still serves every grade (D3); `data.json` has `uid` but not `audience` or `start_time`/`end_time` (D2).

## 8. Next steps (one at a time)

0. ~~Reconciliation pass, no code~~ (closed 2026-10-30). The memo for the record: the pass on 2026-10-11 found the 14 conflicts listed in §0, each with options, a recommendation and its cost written into the item itself rather than a separate memo. Ahin's answers were recorded in place as they came (items 2, 8, 10, 12 decided; 1, 5, 7, 9, 14 resolved by measurement or edits), so the list in §0 *is* the memo. Nothing in the scoped docs was found to contradict §1–§4 once the scale-factor myth (item 1) was measured away.

   Still open from that list: 3, 4, 6 and 11 (all wait on the schedules code moving into this repo) and 13 (where raw emails and the alias ledger live; the approval app is now decided, see `docs/dates-pipeline.md`). None blocks current work.
1. ~~Commit this file. Freeze explicit `uid`s into `shared/important-dates/data.json`; keep CI green~~ (done 2026-10-11; UIDs checked against both live pages first).
2. ~~Turn on the `main` ruleset; add the PR comment with screenshots and a plain-English change summary~~ (done 2026-10-11; screenshots are links to CI files, not inline, so nothing lands in git).
3. ~~Playwright job that opens the published scratch Site and clicks into the embed (filter, month jump, add button)~~ (done 2026-10-11; also measures frame size per window width).
4. ~~Ahin swaps the live 3rd-grade homepage to the URL embed; human check desktop + iPhone; then 1st grade~~ (done 2026-10-30). Checklist: `docs/swap-to-url-embed.md`.
5. ~~`Site Map` sheet + generated copy in the repo; Drive sync job (read via bot identity, open a PR with a readable diff)~~ (built 2026-10-11; credentials in and first real sync PR #18 merged 2026-10-30; the sheet is in the bot's Drive, not the school account).
6. ~~First pattern-A embed: room parent contacts~~ (built 2026-10-11; **live on the 1st-grade site 2026-10-31** after the school's OK: master sheet, Site Map row approved, first real sync and extract, embed placed with `?class=2034`). Left: install `Code.gs` on the master sheet and fill `PUBLISHERS` (Ahin); 3rd grade.
7. ~~Monitor + Harvey-ball dashboard across all sites~~ (done 2026-10-11: `/status/`; the ball fills as a site's slots become healthy URL embeds).

## 9. Scaling backlog (decisions still open)

1. **Rollover date — decided 2026-10-30: the last day of school** (not August 1). Still open: what a site shows when next year's content isn't written yet, "coming soon" or last year's (`docs/ROADMAP.md` D4).
2. **Site URLs — decided 2026-10-30: they stay grade-named** (`sffs-1st-class-page`), a school decision. Consequence: the grade in each URL goes stale at rollover, since the site follows the class (§1). Nothing redirects; families who bookmark get a URL that stops matching the grade.
3. **Site titles** are fixed text in Sites; make them class-based and let an embed show the grade. Stays open, and matters more now that URLs keep the grade (item 2).
4. **How parents submit changes** — email pipeline, Google Form, or both.
5. **Roles and access**, including yearly room-parent rotation. **No second maintainer — decided 2026-10-30:** Ahin is the single point by choice (§4), so this item is about hand-off documentation, not a second reviewer.
6. **Site template** with pre-sized embed slots so no one measures boxes per site.
7. **Room-parent guide**: what to edit, what not to touch, how to request a change, how to undo.
8. **Alerts**: who hears about failed CI, failed deploys, red/amber monitor, pending approvals. *So far:* red monitor and a failing live check open an issue assigned to Ahin-SFFS. Failed CI on a PR shows on the PR. Failed deploys and pending approvals alert nobody yet.
9. **Content standards**: accessibility checks in CI, Handbook accuracy with citations, search-engine indexing setting for sites showing personal data.
10. **Keep Claude usage low**: routine checks run in Actions; Claude handles submissions, new embed types and judgment calls.
11. ~~**Demote `SFQuakerBot` to org Member with write access on this repo.**~~ Done by Ahin 2026-10-31; confirmed through the API the same day: org role `member`, repo permission `write`, `admin: false`. The bot can no longer change the ruleset, settings, secrets or membership.
