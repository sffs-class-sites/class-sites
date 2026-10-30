# ROADMAP — SFFS class sites

Written 2026-10-30 from the committed repo (`main`), the project files, and the decision records. Replaces `START-HERE.md` and the runbook; those were setup documents and setup is done. Keep it current — it is what a new session or a new parent reads to know what's next. Repo-wide rules stay in `CLAUDE.md`, which wins where they differ.

## Where things stand (verified against `main`)

**Done and live**
- Important Dates is a URL embed on both live homepages (swapped 2026-10-30). Boxes 935×935 editor → 1154×1154 published → 352×352 on an iPhone 13, four dates visible. No pasted copy remains.
- UIDs are frozen in `data.json` (30 events), checked against both live pages first.
- `main` is protected: PR only, `build` must pass, no bypass — verified by a rejected push from an org owner.
- Every PR gets a comment: events added/changed/removed by UID, plus screenshot links.
- Daily live check clicks inside the embed on the published scratch Site; daily monitor writes the Harvey-ball status page at `/status/`. Both open an issue on failure and close it on recovery.
- Site Map sync and the room-parents (pattern A) embed are built and tested with fake data, **stopped at the credential boundary** — nothing real has synced yet.

**Open right now (2026-10-30, after section A)**
- Section A housekeeping is done; section B (credentials) is done. Next is **C1** (phone layout for Important Dates) and **C2** (room parents go live), which needs the school's OK first.
- The scratch Site still exists; it goes when the live check points at a real site (A5 / C3).

---

## A. Housekeeping first (one session, no judgment calls)

**A1. ~~Record the decisions in `CLAUDE.md` §9~~ (done 2026-10-30).** Rollover = **last day of school** (replaces August 1). Site URLs **stay grade-named** — school decision; close item 2, and record the consequence that the grade in each URL goes stale at rollover (item 3 stays open). **No second maintainer** — accepted risk, Ahin is the single point by choice; everything should assume no second reviewer. Bot identity = `sfquakerbot@gmail.com` / GitHub `SFQuakerBot`; the school-issued account has sharing limits, so the school-domain migration is deferred.

**A2. ~~Bring `docs/dates-pipeline.md` up to date~~ (done 2026-10-30)** with the email-pipeline decisions: approval app on **Cloudflare Workers + D1** (chosen over Apps Script so the code lives in the repo under PR + CI); security by unlisted URL accepted; build ingestion/extraction first with Ahin as sole approver, no app; pilot on 1st and 3rd together; next wave kindergarten and 2nd; volume target ~15 school emails per grade per month, nine grades.

**A3. ~~Close out the open PRs~~ (done 2026-10-30).** #17 (monitor tracks the glitter embed as `type: code`) and #18 (first real Site Map sync) were both green and merged.

**A4. ~~Mark §8 step 0 done or drop it~~ (done 2026-10-30: struck, with a two-paragraph memo in place).** The reconciliation memo never happened as a memo, but conflict #1 is resolved (ratio rule, recorded in `registry.yaml`) and the rest were settled in passing. Either write the two-paragraph memo for the record or strike the step.

**A5. Delete the scratch Site** once the live check is pointed at a real site instead (see C3). Until then it earns its keep.

---

## B. ~~Unblock the credential boundary~~ (done 2026-10-30: all three in, first sync opened PR #18)

Everything in Site Map sync and room parents is waiting on three things. None of them is code.

**B1. Drive bot key.** Create a Google Cloud project under `sfquakerbot@gmail.com`, make a service account, download its JSON key, store it as the `GOOGLE_SERVICE_ACCOUNT_JSON` Actions secret. Share the Site Map sheet with the service account's email, view-only.

**B2. `SYNC_BOT_TOKEN`.** A fine-grained personal access token for `SFQuakerBot` on this one repo, with pull-request write. Store as an Actions secret. (`github.token` can't be used — PRs it opens never trigger the required `build` check.)

**B3. The Site Map sheet.** Move the draft from Ahin's personal Drive to `sfquakerbot@gmail.com`'s Drive (the school account's sharing limits rule it out for now). Hide gridlines. Store its ID as the `SITE_MAP_SHEET_ID` Actions variable. Put a **role**, not a name, in "Approved by" — it lands in public git.

**Done when:** `sync-site-map.yml` runs on its schedule and opens a PR with a readable diff of `site-map.yaml`.

---

## C. Finish the live product (Claude Code, Ahin reviews)

**C1. Phone layout for Important Dates.** The 935×935 box gets 352px and four dates on a phone — workable, and it cost a 1154px-tall square on desktop. The better fix is inside the embed: below ~400px, a compact layout showing three upcoming dates without scrolling, a bordered scroll region with a sticky "scroll for more" pill, and a link to the full page. `docs/schedules.md` §10 is the pattern. Then the box can come back down. Add phone-width **usability** assertions to `render_check.py` — today it only proves nothing overflows, which a useless layout also passes.

**C2. Room parents go live.** School's OK on publishing names/emails → install `apps-script/room-parents/Code.gs` on the master sheet (in the bot's Drive) and fill `PUBLISHERS` → mark the Site Map row approved → place the embed by URL with `?class=2034` on the 1st-grade site. Then replace the pasted "glitter" room-parent list on that site, which is currently uncheckable by the monitor.

**C3. Point the live check at a real site**, not the scratch one, then delete scratch (A5).

**C4. The remaining pasted embeds.** The 1st and 3rd homepages still carry pasted-code embeds the monitor can't check — school hours, the birthdays roster, the glitter list. Each becomes either a shared URL embed in the repo or an explicit registry entry marked `type: code` with a hash, so the status page stops being blind to them. The birthdays roster holds children's data and must follow §3 (pattern A extract, never committed).

**C5. Bring the basketball schedule into the repo.** `build_hoops.py` is a one-off outside the repo, delivered as paste-in code, with its own UID scheme (`@sffs-1st-hoops`). It's a third copy of the calendar pattern. Make a shared **team-schedule** embed type driven by a data file, place it by URL, register it. Every sport and club from here on is a data file, not a new build script.

---

## D. The class/grade model (not built — the architecture depends on it)

**D1. `?class=YYYY` handling and the grade calculation** in the shared embeds: `grade = 8 − (gradYear − schoolYearEndYear)`, rolling over on the **last day of school**, with `?grade=N` as a preview override. The config block also drives header strings ("Welcome to 3rd grade — Class of 2032").

**D2. `audience` and `start_time`/`end_time` on Important Dates events**, per the agreed schema: audience as a grouping key or grade list, resolved list snapshotted at approval; absent times mean all-day; a timed version replaces an all-day one with a new UID.

**D3. One Important Dates URL per class**, filtering by audience, instead of one URL serving every grade. Needed before any grade-specific date exists.

**D4. What a site shows when next year's content isn't written yet** — "coming soon" or last year's. Decide, then build it.

---

## E. Email → Important Dates pipeline (the big build; design is in `docs/dates-pipeline.md`)

Build in this order, each step useful on its own:

**E1. Ingestion.** One forwarding address, plus-addressed by class (`…+2034@…`). Extraction of candidate events from forwarded school email into the agreed schema. Ahin is the only approver; no app yet. Pilot on 1st and 3rd.

**E2. Cross-queue dedupe and near-match** with ranked candidates and reasons; decisions stored as aliases in a ledger so a phrasing seen once is never surfaced again.

**E3. The approval app** on Cloudflare Workers + D1, unlisted URL, with per-grade queues, approve/reject/request-changes, and escalation of scope changes to Ahin.

**E4. Room-parent designation** — how a person becomes a grade's approver, and how that rotates each year. Undecided.

---

## F. Scaling to other parents (what "hand-off" actually requires)

**F1. Site template.** One template Site with standard pages and pre-sized embed slots at known ratios, so a new grade is: copy, set `?class=`, add a registry entry, publish. Nobody measures boxes again.

**F2. Room-parent guide**, one page: what you may edit, which boxes are shared and must not be touched, how to request a change, how to undo (Sites version history).

**F3. How parents submit changes** — the email pipeline (E), a Google Form, or both. Decide.

**F4. Alerts that reach someone other than Ahin.** Today red monitor and failed live checks open an issue assigned to `Ahin-SFFS`; failed deploys and pending approvals alert nobody. Define who hears what, through what channel (email is simplest), per role.

**F5. Roles and access written down**: who holds the org, who holds the bot identity, who is Sites owner per site, what rotates yearly, and what happens at hand-off. Include demoting `SFQuakerBot` to org Member (§9 item 11) once B is done.

**F6. Content standards**: accessibility checks in CI; Handbook accuracy with citations; search-engine indexing turned off on any site showing personal data.

---

## G. The Mac Mini and "always-on" — what runs where

Not everything should run on the Mini, and most of it shouldn't.

| Work | Where it runs | Why |
|---|---|---|
| Builds, tests, deploys, daily live check, monitor, Site Map sync | **GitHub Actions** (already) | Deterministic, free for a public repo, no machine to keep awake |
| Email extraction, near-match, anything needing judgment on a schedule | **Scheduled Claude task** — cloud, with the Gmail connector signed in as `sfquakerbot` | Runs without the Mini; Claude only does the judgment step, Actions does the rest |
| Interactive development, reviews, new embed types | **Claude Code in the desktop app on the Mini**, repo folder connected | Where the bot identity lives: `gh` as SFQuakerBot, Chrome as sfquakerbot |
| Live-site measurement, Sites editor work, Apps Script installs | **The Mini's browser**, driven from a desktop-app session | Needs a signed-in Chrome; nothing else does |

**Mini setup (once, at the console):**
1. Energy Saver: never sleep, wake for network access.
2. Sharing: turn on **Screen Sharing** and **Remote Login** for `thomasfamilybot`. Screen Sharing is the one to use remotely — it joins the real desktop session where the keychain is already unlocked; SSH doesn't, which is why `claude` hung over SSH.
3. Install the Claude desktop app, sign in with the account that holds Claude Code access, connect `~/Documents/sffs/class-sites` as a folder.
4. Chrome signed in as `sfquakerbot@gmail.com` with the Claude extension installed.
5. Keep usage low: routine checks in Actions, Claude for submissions, new embed types and judgment calls (§9 item 10).

**Suggested order:** A → B → C1, C2 → D → C3–C5 → E → F. A and B are an afternoon. B is the only thing blocking everything built on 10-11 from doing real work.
