# Swapping a site to the URL embed

A human task, about 10 minutes per site (CLAUDE.md §8 step 4). Do the 3rd grade first, check it, then the 1st grade. Nothing in the repo changes until the swap is published (section 4).

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
5. **Keep the box the same size.** Only its shape matters (CLAUDE.md §5). Both live pages use 935 × 935 in the editor, which publishes at 1154 × 1154 on a desktop and 352 × 352 on an iPhone.
   - **Height ÷ width must be at least 0.67** (since 2026-10-31; it was 0.95 before the compact phone layout), or phones show fewer than three upcoming dates before scrolling. The recommended box is **935 × 625** (0.67 with a little margin): 1154 × 770 published, 352 × 235 on an iPhone.
   - If the dialog won't switch to By URL, delete the box, use **Insert → Embed → By URL → Whole page**, and drag the new box to the full column width and the same height as the old one.
6. **Check the shape again before you publish.** On 2026-10-30 the swap changed the box's shape on both sites (3rd grade to 0.59, 1st grade to 0.78), so phones showed one or two dates. Drag the bottom edge until the box is at least two-thirds as tall as it is wide, then publish.
7. **Publish.**

## 2. Check it (desktop, then iPhone)

On a desktop browser, at the published address (not the editor):
- [ ] Dates appear, with "NEXT UP" on the next one.
- [ ] **No school** filters the list, and **All** brings everything back.
- [ ] A month button jumps to that month.
- [ ] **+ Google** opens Google Calendar in a new tab.
- [ ] Choose **Apple Calendar**, and **+ Apple** downloads a small .ics file.

On an iPhone, in Safari and in Chrome:
- [ ] The box is at least two-thirds as tall as it is wide and you can scroll inside it. "Scroll for more ↓" shows at the bottom.
- [ ] On the iPhone: three upcoming dates show before scrolling, tapping a date shows its details, and "Full page ↗" opens the calendar in a new tab.
- [ ] The next three dates show in full under the filter buttons without scrolling.
- [ ] Tapping a filter or month changes the list in place, and the page doesn't jump or open a new window.
- [ ] **+ Google** or **+ Apple** works.

## 3. If something is wrong

- *Untested:* in the Sites editor, **⋮ → Version history** restores the previous version, and then you publish again.
- If that's unavailable: since 2026-10-30 no class page has the pasted copy. The last one (identical on both pages, hash `86e0298ee805`) was saved on Ahin's Mac as `notes/1st-grade-pasted-important-dates-2026-10-30.html`, which is not in git. Paste it into the box's **Embed code** tab and publish. For a new site there is nothing to roll back to: delete the box.

## 4. Afterwards

- The next status check (daily, or on the next deploy) shows *Needs attention: now a URL embed: set status: url in registry.yaml*. That's the cue to change the site's slot in `registry.yaml` from `pasted-code` to `url` and delete its `hash` line. Ask Claude, or edit it in a PR. The status then turns *OK*, and the Harvey ball fills.
- The daily live check already covers the URL embed on the scratch Site. Once both class sites are swapped, the scratch Site can be deleted (CLAUDE.md §7).

## Box shapes for new embeds

Sites keeps a box's shape on phones, so a wide, short box is a letterbox there. The scratch Site's box (h/w 0.59) is 352 × 206 on an iPhone. For anything with a list, aim for a shape of 0.7 to 1. Important Dates needs at least 0.67 to show three dates on a 315px-wide phone (it has a compact layout below 400px); CI checks that at 315 × 210 for every day of the year. Picking a standard shape per embed is §9 item 6, the site template.

## Resizing an existing box

To bring a box down (for example the 935 × 935 Important Dates boxes to 935 × 625): open the page in the Sites editor, click the box, drag its bottom-centre handle up until the size label reads about 935 × 625, publish, then run the checks in section 2 on a desktop and an iPhone. Afterwards record the new `box` in `registry.yaml`. Changing the shape of a box never changes its content: the embed adapts to whatever frame it gets.
