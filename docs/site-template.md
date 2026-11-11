# Site template and rollout to K–8

How a new class site is made without anyone measuring a box or driving the Sites editor with Claude. Written 2026-11-02 (`docs/ROADMAP.md` F1). Steps marked *untested* are how Google Sites is expected to behave; nobody has done them yet.

## The idea

Every site has the same **core**: the shared embeds, placed once per site by URL at a standard box, keyed by class (`?class=YYYY`). Everything else on a site is the room parents' own and may differ from site to site. The daily Live Sites check (`tests/live_check.py`) knows the core from `registry.yaml` and reports, but never alerts on, anything else.

**Standard boxes** (`registry.yaml` → `boxes`, CLAUDE.md §5):

| Name | Editor box | Published desktop | iPhone 13 | Use for |
|---|---|---|---|---|
| `card` | 935 × 625 | 1154 × 770 | 352 × 235 | every slot |
| `page` | 935 × 875 | 1154 × 1080 | 352 × 329 | an embed that is the only thing on its page (none today) |

Every shared embed passes CI at the `card` phone size (352 × 235 and 315 × 210), so a slot is never tuned to its embed. If a new embed can't work at `card`, fix the embed, not the box.

**Core slots today:**

| Page | Embed | Box | URL |
|---|---|---|---|
| Home | Important Dates | `card` | `https://sffs-class-sites.github.io/class-sites/shared/important-dates/` (gets `?class=YYYY` when per-class dates exist, ROADMAP D3) |
| Home | School hours | `card` | `https://sffs-class-sites.github.io/class-sites/shared/school-hours/?class=YYYY` (live on both sites since 2026-11-08) |
| Home | Updates | `card` | `https://sffs-class-sites.github.io/class-sites/shared/updates/?class=YYYY` (on the 1st-grade Home since 2026-11-11; it was alone on an Email Digest page at `page` before, and that page is gone) |

Not core, and not on any site since 2026-11-11: the Room parents embed (`shared/room-parents/`), dormant because no personal data goes on a public Site (CLAUDE.md §3); contact lists live in each grade's Class Sheet, linked by hand where the room parents want it.

Not core yet (built 2026-11-11, not placed): **Key School Systems**, `https://sffs-class-sites.github.io/class-sites/shared/key-systems/` at `card` as the **last** block on the Resources page. It is the same on every site (no `?class=`) and draws its own collapsible header to match the page's collapsible groups; closed, the rest of its box is blank, which is why it goes last. `?open=1` places it open instead.

Not core, per site as needed: a team or club season is `https://sffs-class-sites.github.io/class-sites/shared/team-schedule/?team=<id>` at `card` on a page of the site's choosing (the 1st-grade Basketball page today), where `<id>` is a data file in `shared/team-schedule/teams/`.

## 1. Build the template Site once (Ahin, in the editor, ~20 minutes)

1. In Google Sites as `classpages@`, create a site named **Template – Class Page** (never published to families; it only gets copied).
2. Make the standard page: **Home** (every core embed lives there since 2026-11-11). Keep the name: the registry keys a slot by the page's URL slug (`home`).
3. On each page, **Insert → Embed → By URL → Whole page** for each core slot, using the URL above with `?class=0000` as a placeholder. Drag the box to full column width, then size it with the script (`tools/sites_editor.py resize --site <template key> --page <page> --embed <id> --box card --apply`, which needs the template in `registry.yaml` and Chrome started as in `docs/sites-editor-driver.md` §1), or drag the bottom handle by eye and check with `list`: the editor shows **no size label**. This is the only time a box is sized at all.
4. Add a text block under the core on Home titled **Room parents' corner** (or similar) so copies have an obvious place for their own content.
5. Publish once to yourself (*untested*: a site has to be published at least once for Make a copy to carry the published settings).

## 2. A new class site from the template (~15 minutes, no measuring)

1. Open the template, **⋮ → Make a copy**, name it per the school's grade-named URL convention (CLAUDE.md §9 item 2). *Untested:* the copy keeps every embed's URL and box size.
2. On each page, click each core embed → pencil → **By URL**, and change `?class=0000` to the class's graduating year, e.g. `?class=2036`. That is the whole customisation.
3. **Publish**. Check once on a desktop and a phone that each embed shows the right grade line ("Kindergarten · Class of 2039").
4. Add the site to `registry.yaml` (a PR; ask Claude or edit it): `site_id` from the editor URL, `live` URL, one slot per core embed with `box: card` or `box: page` and `query: {class: YYYY}` where the URL carries it. The next morning's Live Sites check measures every slot and reports.

Nine sites is an afternoon. Nothing here needs a Claude session in the browser.

## 3. What room parents may change (rules for the room-parent guide, ROADMAP F2)

Allowed, anywhere below the core on Home and on pages they create:
- Add text, images, links, their own embeds (a class photo album, a sign-up form, a video). The daily check lists these as "other content" and never alerts.
- Create new pages.

Not allowed (each one breaks the core or the check):
- Resize, move, delete or edit the URL of a core embed. A wrong `?class=` or a missing core embed opens an issue for Ahin the next morning; a resized box is listed as drift.
- Rename or delete **Home** (the registry keys slots by that page slug).
- Paste code embeds that show children's names or contact details (CLAUDE.md §3: personal data goes through pattern A, never pasted).
- Unpublish the site.

If something goes wrong: **⋮ → Version history** in the editor restores a previous version; then publish again. Scripted and tested 2026-11-06: `python3 tools/sites_editor.py restore --site <site> --apply`, then `publish … --apply` (`docs/sites-editor-driver.md` §3).

## 4. Drift is expected

After rollout, sites will differ. The check treats three kinds of change differently:

| Change | What happens |
|---|---|
| Core embed missing, or wrong `?class=` | Live Sites check fails; one issue for Ahin, closed on the next pass |
| Core box shape off its registry box by more than 0.02 | Listed under "Attention" in the run report; no issue |
| Anything else on the page | Listed under "Other content"; no issue |
