# Swapping a site to the URL embed

A human task, about 10 minutes per site (CLAUDE.md §8 step 4). Do the 3rd grade first, check it, then the 1st grade. Nothing in the repo changes until step 7.

**Steps marked *untested*** are how Google Sites is expected to behave. Nobody has done them on a live site yet.

## Before you start

- You need edit access to the site in the school's Google account.
- Open the [status page](https://sffs-class-sites.github.io/class-sites/status/). The site should show *Needs attention: old pasted copy*.
- Families who already added dates to their calendars are safe. The URL embed gives every event the same ID as the pasted copy (checked 2026-10-11), so re-importing updates events instead of duplicating them.

## 1. Swap the embed

1. Open the site in the Sites editor and go to **Home**.
2. Click the Important Dates box, then the pencil (Edit). *Untested:* the dialog has **Embed code** and **By URL** tabs.
3. Choose **By URL** and paste:
   `https://sffs-class-sites.github.io/class-sites/shared/important-dates/`
4. Choose **Whole page**, then **Insert** (or **Update**).
5. **Keep the box the same size.** Only its shape matters (CLAUDE.md §5). On the 3rd-grade page the box is 935 × 897 in the editor, and it publishes at 1154 × 1107 on a desktop and about 352 × 338 on an iPhone.
   - If the dialog won't switch to By URL, delete the box, use **Insert → Embed → By URL → Whole page**, and drag the new box to the full column width and the same height as the old one.
6. **Publish.**

## 2. Check it (desktop, then iPhone)

On a desktop browser, at the published address (not the editor):
- [ ] Dates appear, with "NEXT UP" on the next one.
- [ ] **No school** filters the list, and **All** brings everything back.
- [ ] A month button jumps to that month.
- [ ] **+ Google** opens Google Calendar in a new tab.
- [ ] Choose **Apple Calendar**, and **+ Apple** downloads a small .ics file.

On an iPhone, in Safari and in Chrome:
- [ ] The box is roughly square and you can scroll inside it. "Scroll for more ↓" shows at the bottom.
- [ ] Tapping a filter or month changes the list in place, and the page doesn't jump or open a new window.
- [ ] **+ Google** or **+ Apple** works.

## 3. If something is wrong

- *Untested:* in the Sites editor, **⋮ → Version history** restores the previous version, and then you publish again.
- If that's unavailable: the 1st-grade page still has the identical pasted copy. Copy its embed code (click the box, then the pencil) into this page and publish.

## 4. Afterwards

- The next status check (daily, or on the next deploy) shows *Needs attention: now a URL embed: set status: url in registry.yaml*. That's the cue to change the site's slot in `registry.yaml` from `pasted-code` to `url` and delete its `hash` line. Ask Claude, or edit it in a PR. The status then turns *OK*, and the Harvey ball fills.
- The daily live check already covers the URL embed on the scratch Site. Once both class sites are swapped, the scratch Site can be deleted (CLAUDE.md §7).

## Box shapes for new embeds

Sites keeps a box's shape on phones, so a wide, short box is a letterbox there. The scratch Site's box (h/w 0.59) is 352 × 206 on an iPhone. For anything with a list, aim for a shape of about 1 (h ≈ w). Picking a standard shape per embed is §9 item 6, the site template.
