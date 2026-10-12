# Class schedule one-pagers

Scope: turning a school-issued class schedule PDF into a kid-readable one-pager — printable PDF, Google Sites embed, and a Sheet snapshot. Repo-wide concerns (hosting, embed delivery, change control, directory conventions, personal data) live in `CLAUDE.md` and win over anything here.

Built for Gavin's First Grade Class (1A) and re-run unchanged for Nadia's First Grade Class (1B). Run it the same way for 3rd grade or any future year.

> **Conflict to resolve (see `CLAUDE.md` §0):** this pipeline builds a paste-in **Embed code** snippet and organises data in **teacher-named** directories (`gavin/`, `nadia/`). The repo embeds by **URL** and keys content by **graduating class**. Both of this pipeline's choices were fine for two classes and are probably wrong for nine. Don't change them unilaterally — they're on the reconciliation list.

## Running it for a class

One directory per class holds only data; all code is shared and takes a class-dir argument.

```
sched/
  build.py  axis.py  validate.py  fields.py      # shared
  check.js  echeck.js  scrollcheck.js  shot.js   # shared, take a file path
  gavin/    class.json  data.json  axis.json     # 1A
  nadia/    class.json  data.json  axis.json     # 1B
```

`class.json` carries everything class-specific:

```json
{ "slug": "1b", "grade": "First Grade", "teachers": "Nadia & Olivia",
  "title": "1B Weekly Schedule", "pdf_url": "https://drive.google.com/..." }
```

```
python3 validate.py nadia        # continuity: must PASS before anything else
python3 axis.py     nadia        # merge time boundaries -> axis.json
python3 build.py    nadia        # print + embed + artifact HTML
node shot.js  nadia/1b-schedule.html nadia/1b-schedule.pdf nadia/preview.png
python3 fields.py   nadia        # inject the PDF form fields
node check.js nadia/1b-schedule.html
node echeck.js nadia/embed-test.html
node scrollcheck.js nadia/embed-test.html
```

After refactoring anything shared, diff the other class's output against a saved copy to prove you changed only what you meant to.

## Outputs

| Output | What it's for |
|---|---|
| `<class>-schedule-fillable.pdf` | One Letter page, landscape, colour, with real PDF form fields |
| Published artifact page | Reopen or reprint from any device |
| `<name>-schedule-embed.html` | The Google Sites snippet |
| Google Sheet | A **snapshot export**, not a live source. Nothing reads it back |
| `data.json` | **The source of truth.** Every output is built from this |
| `axis.json` | Merged time-rail boundaries, regenerated whenever times change |

## 1 — Extract two ways, not one

Always do both, because they disagree:

```
pdftotext -layout schedule.pdf sched.txt     # the text layer
pdftoppm -r 300 -png schedule.pdf page       # what a human actually sees
```

Read the rendered PNG yourself. Do not trust the text layer alone.

## 2 — Cross-check for invisible junk

The school's scheduling tool leaves stale text under the coloured blocks. On one PDF, `Unscheduled 12:35 - 1:00 (Period MS-IS)` sat in the text layer on Thursday, painted over by the Homeroom rectangle — invisible on paper.

**Two tells that text is an artifact, not real:**

1. It does not appear in the 300dpi render at that position.
2. Every character is doubled in the extracted words (`UUnnsscchheedduulleedd`) — the generator drew the layer twice.

Drop anything that fails both checks, and say so in the summary rather than silently deleting it.

## 3 — Strip what a kid doesn't need

Remove teacher names, room numbers, period codes (`(Period sfs)`, `(Period 1AMRec)`), and grade prefixes (`1A `, `1st - `, `3A `, `3rd - `).

`1A Physical Education / Carla Carbajal - Play Yard` → `P.E.`

## 4 — Fill missing end times

Some blocks have a start only (`1st - Snack— 9:40`). The end time is the **next block's start time, no buffer**. Snack 9:40 → 9:55, Lunch 11:25 → 11:45.

## 5 — Audit continuity, then ask about every conflict

`validate.py` reports gaps and overlaps per day. **Do not resolve these silently.** Present each one and ask — but first check whether it's visible in the 300dpi render, because some are §2 artifacts.

Precedents already set, applied unless Ahin says otherwise:

- **Real overlap between a special and Homeroom** → the special keeps its full time; Homeroom starts when the special ends. (Library 1:55–2:30, Homeroom pushed to 2:30–2:45.)
- **A time that contradicts the other four days** → follow the pattern, treat the outlier as a typo. (Thu Homeroom 11:10 → 11:05, because Lunch Recess starts 11:05 every day.)
- **Gaps under 10 minutes** → close by extending the earlier activity.

`validate.py` must print `PASS — no gaps, no overlaps` before you build anything.

## 6 — Rename into kid language

Keep these identical across classes so siblings' sheets match.

| Source PDF | Use this |
|---|---|
| `1st - Recess` / `3rd - Recess` | Morning Recess |
| `1st - L Recess` | Lunch Recess |
| `1st - PM Recess` | Afternoon Recess |
| `1st - Snack` | Snack |
| `1st - Lunch` | Lunch |
| `1A Physical Education` | P.E. |
| `1A Music Class` | Music |
| `1A Art Class` | Art |
| `1A Spanish Class` | Spanish |
| `1A Library` | Library |
| `1A Dance - Fall` | Dance |
| `Meeting For Worship` | Meeting for Worship |
| `Buddies/Clubs/Assemblies` | Buddies & Clubs |

## 7 — The colour and icon map is fixed

**This is the part that matters most for reuse.** Siblings compare these sheets side by side; Music must be the same pink in both. Copy the `types` block verbatim and only *add* to it.

| Activity | Icon | Fill | Rail |
|---|---|---|---|
| Homeroom | 🏠 | `#CFE4FA` | `#5B9BD5` |
| Morning / Lunch / Afternoon Recess | 🏃 🌳 🛼 | `#D6F0D2` | `#6FBF63` |
| Snack | 🍎 | `#FFE2C2` | `#F0A055` |
| Lunch | 🍱 | `#FFD2D2` | `#E8706F` |
| Music | 🎵 | `#F3D2E8` | `#C878B0` |
| Art | 🎨 | `#FBEFB8` | `#D9BE3C` |
| Spanish | 💬 | `#C9EDEA` | `#4FB3AC` |
| P.E. | ⚽ | `#DFD2F5` | `#9375CE` |
| Dance | 💃 | `#FBD9EC` | `#DE7CB2` |
| Library | 📚 | `#EADCC6` | `#B08A55` |
| Meeting for Worship | 🕊️ | `#E4EAF1` | `#8AA0B8` |
| Buddies & Clubs | 🤝 | `#D8DFF7` | `#7A8CD1` |

All three recesses share one green on purpose — green means "outside." Keep any new subject clear of that green and of Homeroom blue.

Likely new types for 3rd grade, with non-colliding suggestions: Math `#FFE0D0`/`#E58A5E` 🔢, Writing `#E8E0F5`/`#A48BD0` ✏️, Science `#D4EAF7`/`#5FA8D3` 🔬, Reading `#F5E3D0`/`#C99A62` 📖.

## 8 — The shared time axis

A time rail runs down the left and all five days share it, so you can read across a row and see what every day is doing at that moment.

Collecting every distinct start/end time across the week gives **26 boundaries / 25 rows**. Split a page that many ways and short blocks (Snack, Lunch) end up ~20px tall, too small to read. So `axis.py` **merges boundaries that sit close together**, under one hard rule:

> No block may collapse. After merging, every activity must still span at least one row — check `slot(end) > slot(start)` for all 55 blocks before accepting a merge.

Greedily delete the boundary in the tightest cluster, test the rule, repeat. 26 → **16 boundaries / 15 rows**, which is what makes the blocks readable.

**The times printed inside each block stay exact.** Only the drawing is compressed — Wednesday's 9:15 recess and Monday's 9:20 recess share a row line, but each block reads its own true time. The layout is deliberately **not to scale**; row heights are `max(34px, duration × scale)` with the scale solved so rows exactly fill the page.

Two things fall out for free:

- **Wednesday's column ends early**, leaving space after 1:45, which the builder fills with a dashed "Early dismissal — day ends 1:45" note. Any short day gets this automatically.
- Blocks under 40px switch to a **one-line style** (name left, time right) instead of stacked.

Rail labels are **hour marks only** (plus the day's first and last time). Don't label every row — merged rows represent two nearby times, so an hour mark is the only unambiguous label.

## 9 — Build the outputs

`build.py` reads `data.json` + `axis.json` and writes the standalone printable page, the artifact version (no `<!doctype>`/`<head>`/`<body>`), and the Sites snippet.

**Keep the embed small as hygiene, not to hit a limit.** An earlier version of this doc claimed Google Sites caps embed code at 10,000 characters — that figure is **Webflow's** documented limit, not Google's, and Sites doesn't clearly publish one. If a paste is ever rejected, trim rather than redesign.

What actually keeps it small:

- **Colours in CSS classes** (`.a0`, `.a1`…), never inline `style` per block. Inline colours alone cost ~2,300 characters.
- **Heights as classes too** (`.h0`…`.h9`). Only ~10 distinct block heights exist, so `class="b a0 h3"` beats `style="height:80.3px"` on all 56 blocks.
- **Integer row positions.** Round the cumulative `Y` positions, then derive each block height as `Y[end] - Y[start] - GAP`. Rounding the *heights* instead lets error accumulate down a column and breaks alignment with the rail.
- `<p>` rather than `<div>` for blocks.

## 10 — Responsive behaviour

The embed carries **two layouts in one file**, switching at 760px. Media queries inside a Sites embed evaluate against the **iframe's** width, not the device's, so the switch works correctly once embedded.

**Desktop (≥760px):** five-column grid with the shared time rail, class header (grade bold, teachers lighter beside it), printable-version link.

**Mobile (<760px):** the grid is unusable — five columns in a 390px viewport means 1,280px of content and horizontal swiping. So mobile becomes **one day at a time**:

- A sticky row of day chips (Mon–Fri), each in that day's accent colour.
- The selected day as full-width rows, ~16px type, icon and time on one line.
- The time rail is dropped — it exists to compare days, and there's only one.
- A day header bar showing that day's hours ("Wednesday · 8:30–1:45").
- **It opens on today.** `new Date().getDay()`, falling back to Monday on weekends.

Two things to preserve when rebuilding:

1. **No-JS fallback.** Base mobile CSS shows *all* days stacked. The JS adds a `js` class to the root, and only `.sch.js .col{display:none}` hides them. If the script fails, the page degrades to a long scroll instead of a blank box.
2. **Neutralise the `.sm` compact style inside the mobile media query.** `.sch .b.sm b` is more specific than `.sch .b b`, so the desktop small-block font leaks into mobile and Snack/Lunch/Recess render visibly smaller than Homeroom. Override `.sch .b.sm b`, `.sch .b.sm i` and `.sch .b.sm::before` explicitly.

### The grid must FILL the frame, not assume it

Sites scales the embed frame by **aspect ratio** (see Environment assumptions), but a fixed-pixel grid has a constant height — so the two agree at exactly one width. Everywhere else you get dead space or, worse, clipping. The editor canvas is also **narrower than the published column** because of the side panel, so sizing against what you see in the editor is sizing against the wrong number.

The fix is to stop pinning pixels. In the embed variant (`layout(..., pct=True)`):

- The sheet is the frame: `.sch{display:flex;flex-direction:column;height:100vh}` with `.bd{flex:1 1 auto;min-height:0}`, so the grid takes whatever is left.
- Blocks are absolutely positioned with **percentage** tops and heights (`.et<i>{top:X%}`, `.eh<j>{height:calc(Y% - 3px)}`). Percentage tops keep every column aligned with the rail at any height; the 3px gap stays a crisp pixel value.
- Rail hour marks use percentages too.
- Type scales with `clamp(min, Nvw, max)`. Without this, shrinking the frame keeps text at full size and it overflows the shortened rows.

`fitcheck.js` asserts, across six frame sizes, that the page never scrolls, dead space stays at the 3px gap, and no block overflows. **Run it before publishing.**

### Two layouts, two geometries

`layout(body, minseg, tag)` solves row geometry for a given height, so the same data renders at two sizes:

- `P = layout(542, 32, 'p')` — print and artifact, sized to share one Letter page with the after-school band.
- `E = layout(1195, 62, 'e')` — the Sites embed, sized to fill the tall frame, with bigger rows and type (`EMBEDSCALE`).

Height classes are prefixed per variant (`ph0…`, `eh0…`) so the two never collide. If you change the embed's box height, change `E`'s body to match and re-check with `echeck.js` — larger type in shorter rows is exactly how blocks start overflowing again.

### Printable-version link

The embed header carries a "Printable version" button pointing at the published PDF. It's a single `PDF_URL` constant at the top of `build.py`. The link needs `target="_blank" rel="noopener"`, or it opens *inside* the embed's iframe. Hidden in print, absent from the PDF and the artifact.

### The mobile scroll affordance

The day list is taller than the frame, so it has to scroll. Letting the whole iframe scroll is invisible — there's no edge to signal it. So on mobile the selected day becomes its **own bounded scroller**:

- `max-height: calc(100vh - 132px)` — inside an iframe, `100vh` is the *frame* height, which is what makes this work.
- A 2px rounded border draws the scrollable region explicitly.
- The day header is `position: sticky; top: 0`, with `padding-top: 0` on the container and `margin: 0 -7px` on the header, so no content appears in the padding strip above it.
- A sticky pill at the bottom reads "Scroll for the rest of the day ↓".

Because the column is height-capped, the page itself no longer scrolls — exactly **one** scroll region, not a nested pair. `scrollcheck.js` asserts that.

**Stacking order matters.** Blocks are `position:relative; z-index:1`, so the sticky header (`z-index:3`) and the hint pill (`z-index:4`) must sit above them or they render *behind* the schedule rows — the pill's background silently disappears and text collides with blocks.

JS toggles two classes per column: `sc` when it actually overflows (no pointless border on a short day) and `bot` when scrolled to the end, fading the pill out so it stops advertising content that isn't there.

## 11 — The after-school band (PDF only)

The printed sheet goes to every family in the class, so the header is the **class** ("First Grade · Gavin · Olivia"), not one child, and the bottom band is where each family customises. Per day column: an **ED** and a **Carpool** checkbox, then two blank ruled lines.

The band is paper-only. It's absent from the embed markup entirely (not just hidden — that keeps the embed small), and on the artifact it's `display:none` on screen but visible in `@media print`.

### Making the fields real

**Chromium's print-to-PDF cannot emit AcroForm fields.** An `<input>` in the HTML becomes a picture of an input. So fields are added in a second pass:

1. **Draw placeholders in HTML** — `<i class=cb data-f="mon_ed">` for a checkbox, `<div class=ln data-f="mon_act1">` for a line. These give the printed look.
2. **Measure them in the browser** (`measure.js`) under `emulateMedia({media:'print'})` with the viewport set to the printable box (991×751 px = 10.32in × 7.82in).
3. **Replay as widgets** (`fields.py`) with reportlab at converted coordinates.
4. **Merge** into the Chromium PDF with pikepdf — copy the `/AcroForm`, then point the page's `/Annots` at those same field objects.

Coordinate conversion, with `@page margin: .34in`:

```
x_pt = 24.48 + css_x * 0.75
y_pt = page_height - 24.48 - css_y * 0.75 - height      # reportlab origin is bottom-left
```

The widgets are transparent and sit *on top of* the drawn boxes, so a blank printout still shows the checkbox and line, while a PDF editor offers a real field.

### Three things that will bite you

- **`c.showPage()` before `c.save()`.** Without it reportlab never emits the page and every widget's `/P` reference fails to resolve: *"forward reference to 'Page1' not resolved"*.
- **ZapfDingbats must be supplied.** reportlab draws the tick in `ZaDb`, but after the pikepdf merge neither `/AcroForm/DR/Font` nor the appearance streams carry that font. Viewers report *"Unknown font tag 'ZaDb'"* and render an empty box. Add `<< /Type /Font /Subtype /Type1 /BaseFont /ZapfDingbats >>` to `/DR/Font/ZaDb` **and** to every `/AP` state stream's `/Resources/Font`.
- **Set `/NeedAppearances true`** so viewers regenerate text-field appearances.

### Verify the fields, don't assume them

Run `DEBUG=1 python3 fields.py` to emit the widgets with **red visible borders**, render it, and confirm they sit exactly on the drawn boxes — the only real check on the coordinate math. Then fill the fields programmatically, render again, and confirm ticks and text appear where they should.

## 12 — Fonts

**Use no web fonts.** The stack is system-only: `"Trebuchet MS", Verdana, "DejaVu Sans", sans-serif`.

The original reason was an environment constraint (see below), but the rule should stay for a better one: **verify with the font that will actually be used.** When this switched away from Nunito, the wider Linux fallback (DejaVu Sans) exposed two latent bugs the narrower font had hidden — the name and time collided in one-line blocks, and "Meeting for Worship" overflowed its box and rendered as an empty grey rectangle.

Block text is sized from the box at build time — `''` above 46px, `.t2` above 38px, `.t3` below — with the name stacked above the time so it gets the full column width. Avoid `overflow-wrap:anywhere`: it hides overflow by snapping words mid-letter ("Homer / oom", "Musi / c").

## 13 — Verify before sending

```
node shot.js        # preview.png + the PDF at Letter landscape
node mob.js embed-test.html mobile.png 390    # phone
node mob.js embed-test.html desktop.png 1000  # Sites content width
node tap.js         # taps a day chip, asserts the right day shows
node check.js       # asserts NO block overflows and no name/time collision
python3 fields.py   # injects the PDF form fields
```

`check.js` is the important one: it compares `scrollHeight` to `clientHeight` on every block and checks the name and time rectangles don't intersect. Text that overflows a block is invisible, not obviously broken — the "Meeting for Worship" bug showed as an empty coloured box, easy to miss in a screenshot.

Playwright's page option is **`viewport`**, not `viewportSize` — the latter is silently ignored and every "mobile" screenshot comes back at the 1280px default, which looks fine and proves nothing. Assert the width in the test output.

Check: **PDF is exactly 1 page**, `scrollWidth` equals the viewport width at 390px, rail labels are not clipped, nothing overflows any column, every block's time matches `data.json`, and no two adjacent activities share a colour.

## 14 — The Google Sheet

Upload `data.csv` to Drive as a spreadsheet. Times are written `8:30 AM` / `1:30 PM` so Sheets parses them correctly and doesn't turn afternoon times into 2 a.m.

**Two things must be done by hand — the Drive API can't set either:**

1. **View → Show → uncheck Gridlines**
2. **Share → General access → Anyone with the link → Editor**

## 15 — Round-tripping an edit

There is no automation here; the Sheet is a dead end. When a time changes in the Sheet: download as CSV, regenerate `data.json`, re-run `validate.py` (must still pass), re-run `axis.py` (the boundary set changes when times change), rebuild, and **republish to the same artifact URL** so saved links keep working.

---

# Environment assumptions (verify these)

Everything in this section was measured or observed in a throwaway container driving a browser from a personal laptop. The repo now builds in GitHub Actions. Re-check each one before relying on it.

### Pixel measurements — the unresolved conflict

Measured live on a published class page: the embed iframe was **1154 × 500 px**.

- **Width tracks the Sites content column**, with no `max-width`. On a phone the column narrows and the iframe narrows with it, so the `max-width:759px` media query fires correctly. The responsive switch was never the problem.
- **Height is fixed at whatever was drawn when the embed was inserted** and never responds to content. At 500px it clipped the schedule around 1:00 PM on every device — which on a phone looked like "the schedule isn't visible."

**Sites scales embeds by ASPECT RATIO, not by height.** Measured:

| | Width | Height | Ratio |
|---|---|---|---|
| Desktop | 1031 | 521 | 1.98 |
| Phone | 315 | 160 | 1.97 |

There is no CSS transform — Sites genuinely resizes the frame, preserving the ratio drawn in the editor. So:

```
mobile_height = 315 × (desktop_height / desktop_width)   ≈ desktop_height × 0.31
```

Dragging the box from 500 to 680 buys about **55 mobile pixels**, which reads as "changing the height does nothing on mobile." It is doing something; the multiplier is brutal.

| Wanted on mobile | Desktop box must be |
|---|---|
| 300px | ~975px |
| 400px | ~1300px |
| 600px (full day, no scroll) | ~1950px |

A cross-origin iframe cannot resize its own frame, so this cannot be fixed from inside the embed. It is a genuine trade-off between the desktop page and the phone.

Chosen setting: **1022 × 1287 in the editor** (= 1154 × 1454 published), giving ~397px on a phone. Since the grid now fills whatever height it's handed, this is a *mobile* choice, not a desktop constraint.

| | Column width | Frame height | A fixed 1287px grid |
|---|---|---|---|
| Editor canvas | 1022 | 1287 | fits exactly |
| **Published page** | **1154** | **1454** | 167px dead space |
| Narrower laptop | 900 | 1134 | **clipped by 153px** |

> **This is conflict #1 in `CLAUDE.md` §0.** Editor 1022 → published 1154 is a factor of **1.129**. `CLAUDE.md` §5 records **1.234**, measured at a 1440px browser window. Both were measured live, so the factor most likely depends on window width — which would make both numbers wrong as constants. The window width for the measurements above was **not recorded**. Measure the factor as a function of window width before any doc states a number.
>
> **Resolved 2026-10-11** (see `CLAUDE.md` §0 item 1): there is no factor. Published width is Sites' content column (max 1154px), and height is width × the editor box's h ÷ w.

### Other environment-dependent notes

- **Web fonts were blocked.** That container's egress blocked `fonts.googleapis.com`, so PDFs silently rendered in the fallback while the web version would have used Nunito — two different-looking documents, and the one being verified was not the one families would see. GitHub Actions is not that container, so the *reason* no longer holds. Keep the rule anyway, per §12.
- **No API exists for current Google Sites.** Placing or resizing an embed box is a manual browser step. Content changes are not.
- **Browser automation can't click inside a cross-origin iframe** on a published Site, so live-embed interaction can't be verified that way. Playwright in Actions can reach `sites.google.com`.
- **The Drive API can't set gridlines or sharing** (§14). If that's still true, those two steps stay manual.
