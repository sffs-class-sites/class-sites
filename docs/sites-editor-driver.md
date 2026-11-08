# Driving the Google Sites editor: `tools/sites_editor.py`

Google Sites has no API (CLAUDE.md §5), so sizing an embed box or publishing a site is editor work. This script does that work from the command line, attached to a Chrome that a person signed in, so a Claude session never clicks through the editor one screenshot at a time. Written 2026-11-03.

**Status (2026-11-03):** every command is built. `list` ran read-only on the real editor on 2026-11-02 (§4 has the record). `resize --apply` ran on the real editor on 2026-11-02: it resized the room-parents box on the 1st-grade homepage, Ahin published that by hand, and the live check confirmed it on 2026-11-03 (§4, §6). On 2026-11-06 on the Mini: `chrome` started the signed-in Chrome; `resize --apply` dragged the same box to `page`; `restore --apply` (new: the editor's Version history, §3) put the live version back as the draft; `publish --apply` opened the real publish dialog, found "There are no unpublished changes to review" and returned to the editor; the live check passed unchanged (§4). The one thing still unexercised is the dialog's Publish button itself: it was disabled, because there was nothing to publish. The real editor shows no size label, so `resize` measures the iframe after each drag and aims at the box's shape (h ÷ w), which is what Sites publishes (CLAUDE.md §5).

## 1. Set-up on the Mac (once per session, Ahin)

1. Start Chrome for the script. The script can do it (added 2026-11-03; on the Mini, 2026-11-06, it started the signed-in Chrome twice, §4):

   ```bash
   python3 tools/sites_editor.py chrome
   ```

   It looks in `~/Library/Application Support/Google/Chrome/classpages` (override: `--user-data-dir`, or `SITES_EDITOR_CHROME_DIR`), a Chrome user data dir of its own, because Chrome 136+ refuses `--remote-debugging-port` on the default one. If that dir has a profile whose `Preferences` lists `classpages@sffriendsschool.org` under `account_info`, it starts the real Chrome app on it (`open -na "Google Chrome"`), maximised, debug port 9222, one blank tab, and waits for the port. If the dir is missing or not signed in, it starts Chrome there on the Google sign-in page, says so, and exits 1: a person signs in as `classpages@` once, then runs the command again. If the dir exists but the process may not read it (on the Mini, macOS refuses the claude CLI a look inside Chrome's data dir: "Operation not permitted", with or without Claude Code's own sandbox), it can't tell who is signed in, so it starts Chrome there anyway on a blank tab and exits 0 once the port is up; `list` then prints the account. If the port is already up it does nothing. If a Chrome on that dir is already running without the port, macOS just focuses it and the command stops after 20 s with that explanation: quit that window and run again. A Claude session on the Mini runs this behind its normal permission prompt. The script never handles a password, and it is not headless: it drives the account's own window.

   By hand, the same thing is:

   ```bash
   open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir="$HOME/Library/Application Support/Google/Chrome/classpages"
   ```

   The `--user-data-dir` is the data dir that holds the `classpages@` sign-in. A fresh directory works too: sign in by hand in that window, once. Make the window at least 1440px wide and as tall as the screen allows: below 1440 the editor scales its canvas (701px cards at 1200), so sizes print smaller than the registry's, though shapes still hold; and a drag needs the block's bottom edge plus the drag distance inside the window, or `resize` stops before touching anything. Keep at least one tab open in that Chrome, or Playwright can't attach (§4, record of real runs).

2. Python side (same as the live check):

   ```bash
   pip install playwright pyyaml
   ```

   No `playwright install`: nothing is launched.

3. Check the attachment:

   ```bash
   python3 tools/sites_editor.py tabs
   ```

   It prints every open tab. `--cdp http://localhost:NNNN` if Chrome is on another port.

## 2. Commands

One site, one page, one action per run. No command loops over sites. Every write needs `--apply`; without it the command prints what it would do and the before size.

| Command | Does | Writes to the Site? |
|---|---|---|
| `chrome` | starts the real Chrome on the `classpages@` data dir, maximised, debug port on, one tab (§1) | no |
| `tabs` | lists the attached Chrome's tabs | no |
| `list --site class-2034 --page home` | opens the site's editor (or reuses its open tab), selects the page in the Pages panel (a child page as `resources/basketball`: parent first, expanded if its children are hidden, then the child), finds each URL-embed block of ours by its `data-url` and prints its URL, query, box size and position, wrapper src and ancestor chain; then every other block on the canvas (pasted code and the like), identified by registry `match` text found in the block's attributes or the frame's HTML, so ROADMAP C4's inventory can be taken from the editor; flags registered slots that are missing | no |
| `list … --select` | also clicks each block's corner and reports whether the editor marked it selected (`aria-selected`), the hook `resize` relies on | no (a click selects; nothing changes) |
| `list … --dump` | also writes `_editor/<site>-<page>-<time>.json`, `.html`, `.png`: the DOM record (§4) | no |
| `resize --site class-2034 --page home --embed room-parents --box card` | dry run: prints the current box, the target shape and the drag it would do | no |
| `resize … --apply` | selects the block, drags its bottom-centre handle, re-measures, repeats (up to 12 drags) until h ÷ w is within 0.005 of the box; each drag goes as far as the window has room for (a block at the bottom of a page gets a few hundred px per drag, so a big change takes several, printed as "by +180px (of +500 wanted; the window had room for +180)"); prints before and after; **never publishes**. Stops before dragging if the block won't select, or if the handle itself is off-screen or has under 8 px of room even after scrolling; stops after a drag that changed the width or nothing (exit 2, message says what to check; ⌘Z in the editor undoes it) | yes, unpublished |
| `publish --site class-2034` | dry run: finds the app-bar Publish button | no |
| `publish … --apply` | clicks Publish, reads the review dialog; if it says there are no unpublished changes, clicks **Return to editor** and exits 0 with "nothing to publish"; otherwise clicks its single **Publish** button (stops if that button is disabled) and waits for the dialog to close. A dialog it doesn't understand: Escape, exit 2, with what it saw | yes, live |
| `restore --site class-2034` | dry run: opens Version history, lists the versions, selects the newest **Published …** one (what families see now), closes the panel | no |
| `restore … --apply` | the same, then **Restore this site version** and its **Restore** confirmation: the draft becomes the live version again, unpublished edits are dropped; **never publishes**. The rollback (§3): after a bad publish, `restore` then `publish` | yes, unpublished |

Exit codes: 0 ok; 1 the editor, Chrome or the registry isn't as expected (the `STOP:` line says what, and the script guessed nothing); 2 a write stopped half-way (the `STOPPED HALF-WAY:` line says what to look at in the editor).

Sites and pages come from `registry.yaml`: `--site` is a site key (`class-2034`), `--page` a slot's page slug (`home`, `email-digest`), `--embed` an embed id, `--box` a standard box name (`card`, `page`). The editor URL is `https://sites.google.com/d/<site_id>/edit`.

Pacing: the script waits 1.5 s after anything that changes what the editor shows. Automating the editor is a grey area under Google's terms; keep it human-paced and run it only as the account's own browser.

## 3. Rollback

`python3 tools/sites_editor.py restore --site <site> --apply` makes the newest published version the draft again through the editor's Version history (what a person does by hand with **⋮ → Version history → Restore this site version**), then `publish … --apply` puts it live. **Tested 2026-11-06** on the 1st-grade site (§4): a box was dragged to the wrong shape, `restore` put the live version back, `publish` found nothing to publish, and the live check still passed. What `restore` can't do: pick an older version than the newest published one (do that by hand), or undo a publish that has already happened (that is `restore` of the version before it, by hand, then `publish`). Also `docs/site-template.md` §3.

## 4. What in the editor DOM the script depends on

Google changes the editor without notice and its class names are obfuscated, so the script only uses hooks that are likely to be stable: iframe `src`, ARIA roles and labels, text content. Each row says whether it was **confirmed** on the real editor (with the date) or is still **assumed**. When something breaks, run `list --dump`, read the record, update the script and this table.

| Script needs | How it looks for it | Status |
|---|---|---|
| `chrome` (starting the debug Chrome) | `GET http://localhost:9222/json/version`; if it answers, nothing to start. Otherwise `~/Library/Application Support/Google/Chrome/classpages`: a profile whose `Preferences` names `classpages@` → start Chrome there maximised on a blank tab; unreadable dir → start it anyway, exit 0 when the port is up; missing or not signed in → start on the sign-in page, exit 1 | **confirmed 2026-11-06** (unreadable dir, Chrome started, port up; §4 record) and **2026-11-07** (port already up: "Chrome is already listening … nothing to start", exit 0, nothing opened). The signed-in-profile branch and the sign-in-page branch are still **assumed**: on the Mini the dir is unreadable, so neither has run for real |
| The editor tab | a tab whose URL starts with `https://sites.google.com/d/<site_id>/`; otherwise opens `…/d/<site_id>/edit` | **confirmed 2026-11-02**: `…/d/<site_id>/edit` redirects to `…/d/<site_id>/p/<page id>/edit` (class-2034 also added `?pli=1`) |
| Signed-in check | a redirect to `accounts.google.com` means "not signed in", stop | assumed (not exercised: the profile was signed in) |
| Who is signed in | `[aria-label^="Google Account"]` in the top bar (the avatar button, which names the account in Google apps) | **confirmed 2026-11-02**: `aria-label="Google Account: SFFS Class Pages (classpages@sffriendsschool.org)"` (a newline before the parenthesis) |
| The Pages panel | `[role=tree]`; if absent, a `[role=tab]`/button labelled "Pages" is clicked to open it | **confirmed 2026-11-02**: the panel was closed; `[role=tab]` "Pages" opened it; one `[role=tree]` with one `[role=treeitem]` per top-level page (`aria-labelledby` = the page's id, `aria-selected="true"` on the current page). Item labels: "Home page, titled Home.", "Room Info.", "Email Digest.", "Resources. Child pages available." |
| A page entry | the smallest visible element whose text is exactly the page title (`email-digest` → "Email Digest"), preferring one under `[role=tree]`/`[role=treeitem]`; clicked at its centre, then the editor URL is printed | **confirmed for Home 2026-11-02**: the element found is a role-less `div` inside the treeitem; the click worked. The editor had already opened on Home, so the URL didn't change: moving to a different page is not yet exercised |
| A child page | the slug's segments in turn: click the parent's entry; if the child's title isn't shown, click an expander inside the parent's `[role=treeitem]` (`[aria-expanded="false"]`, or an aria-label containing "xpand", "hild pages" or "ubpages"), else focus the parent and press ArrowRight; then click the child. On failure the STOP line lists every treeitem's label, `aria-expanded` and visibility | **confirmed 2026-11-08** (`list --site class-2034 --page resources/basketball`): the parent "Resources" was clicked as an `<a role=link>` (not the role-less `div` the other entries are), then "Basketball" was found at once and clicked as a `div role=None`, and the editor URL moved to the child's page id (`…/p/1NRzBnIB1XKJNeOWkWwnVys6q-sUBigC5/edit`). The child's title was already visible after the parent click, so the expander and ArrowRight branches did **not** run and stay **assumed**; what the expander looks like is still unrecorded |
| Pasted-code blocks | every visible `iframe` on the canvas not inside a URL-embed block; identified by a registry embed's `match` text appearing in an attribute of the iframe or its ancestors (the published page keeps pasted code in `data-code`; whether the editor does is checked, not assumed), else in the frame's own HTML when Playwright's frame tree has it; else reported unidentified with its first text | **confirmed in part 2026-11-08** (`list` on class-2034 `resources/basketball` and `home`). What held: the editor keeps the pasted code on the block: each pasted block is `iframe[aria-label='Custom embed']` whose parent is `div[data-code='<the pasted code>'][data-url='https://<n>-atari-embeds.googleusercontent.com/embe…'][data-tile-id][data-in-editor='true']`, so the `match` text is found **by attribute** (hoops on `resources/basketball`, `data-code` starting `<!DOCTYPE html>`). Blocks without a registry `match` (the birthdays roster, `data-code` starting `<style>\n  .sffs-roster-wrap`, 562 × 638; school hours, 661 × 808, both on `home`) are reported "not in registry.yaml; identified by unidentified" with **no** `starts:` text, so the fall-back to the frame's own text did not deliver. Pasted blocks are narrower than URL embeds (hoops 760 × 999 at x=403; URL embeds 1154 wide). What differed: (a) three non-block iframes are listed on every page: a 148 × 148 one with no src at y=−1584, a 424 × 210 `iframe[role='presentation']` with src `about:blank` inside `header[role='none'] > div[data-ogsr-up]` (the Google account bar) at x=1406 y=57, and a 1445 × 867 one with no src at x=193 y=72 under `div[data-exclude-global-shortcuts]`; (b) the frame-content step pairs frames by URL, and the pasted embed's inner frame is `about:blank`, so the header iframe was credited with the pasted page's text ("identified by frame content", `starts: 'Super Friends …'` on basketball, `'SFFS School Hours …'` on home) while the real block got none. So `data-code` is the hook to use and hash from; the frame-content path and the iframe filter need fixing (§4 record 2026-11-08) **Script changed 2026-11-08 after this run (not yet re-run on the real editor):** only `iframe[aria-label="Custom embed"]` counts, so the editor's own iframes drop out; the block's `data-code` is hashed exactly as `tests/monitor.py` hashes the published page and compared with the registry slot's `hash` ("= registry" or "≠ registry", which is C4 checkable from the editor); a block's frame is found by element identity, not URL, so `starts:` text now belongs to the right block; identification order is hash, then `match` text in `data-code`, then `match` text in the frame. The mock holds the real hoops code and its hash matches the registry there |
| Our embeds | `div[aria-label="Whole page embed"][data-url]` elements in the editor document whose `data-url` is one of our Pages URLs (`…/class-sites/shared/<id>/…`); the `iframe` inside is the box. Both `list` and `resize` use this since 2026-11-03. Playwright's frame tree is only reported ("our page is / is not in Playwright's frame tree"): on a tab that was open before the script attached it shows the gstatic wrapper frames with an empty URL and nothing below them, which is why `list` reported every embed MISSING on 2026-11-02 evening | **confirmed 2026-11-02** (the `data-url` hook, by `resize`), **2026-11-06** (`list`): on a tab that had been open for days, `list` found both class-2034 embeds by `data-url`, though Playwright's frame tree still didn't show our page; and **2026-11-07** (`list`, both sites): the reused class-2034 tab again found both by `data-url` with our page absent from the frame tree, and class-2032, opened fresh by the script, found its embed with our page present in the frame tree, so the frame-tree line is a reused-tab symptom only. The gstatic wrapper path had changed between runs (`…/embeds/9581c1cb…` on 2026-11-02 and 11-06, `…/embeds/197a9c19…` on 11-07); the script never matches on it |
| Box size | the bounding box of that outermost iframe element, in CSS px of the editor window; expected to equal the editor's size label at a ≥1440px window | **confirmed at an 1830px window** (2026-11-02 evening and 2026-11-06): card embeds measure 1154 wide, the same as the published desktop frame, and the editor shape matches the live check's (room-parents 0.669 in both). At a 1200px window (2026-11-02) the canvas is scaled to 701 wide (×0.75), but the h/w ratios still hold. The registry's 935 is never the measured width at these windows; the script compares shape (h ÷ w), not width |
| A block (`resize`) | `div[aria-label="Whole page embed"][data-url]` whose `data-url` is the embed's URL (same id and query as the registry slot); its `iframe` is the box | **confirmed 2026-11-02**: `resize` found class-2034 room-parents this way on a reused tab, where frame URLs failed |
| Selecting a block | scroll it into view, click the iframe's top-left corner (+2, +2); then `div[role=gridcell][aria-label="IFRAME"]` above it must carry `aria-selected="true"` or the script stops | **confirmed 2026-11-02** (the click and the attribute) and **2026-11-06** (scroll first): important-dates, starting at y=2002 in a 963px-tall window, was scrolled to, clicked and marked selected |
| Size label | none: the real editor shows no `W × H` on a selected embed (2026-11-02). `resize` measures the iframe's bounding box after every drag instead, and aims at the registry box's shape | **confirmed absent 2026-11-02** |
| Resize handle | by position only: bottom centre of the selected block's iframe, `(x + w/2, y + h)`; the script moves there, presses, moves down in 12 steps, releases, and checks the iframe got taller and no wider | **confirmed 2026-11-02**: one drag of +95px took room-parents from 1154 × 677 to 1154 × 772, width unchanged, no snapping visible. **2026-11-08**: a block at the bottom of a page has only the window's spare room below its handle (212 px for a +500 drag, 94 px for +95) and the canvas won't scroll further; since the fix that evening the drag is cut to that room and repeated (done by hand with the same function on both School Hours boxes, +180/+180/+139 and +60/+35, both reaching the card shape) |
| Publish | `[guidedhelpid="at-appbar-publish"]` (fallback: `div[role=button]` with text Publish); then a `[role=dialog]`/`[role=alertdialog]` with exactly one button whose text is Publish, which is clicked; the dialog must close within 10 s | button **found 2026-11-02**; dialog **seen 2026-11-06**: a full-window "Review changes and publish" with buttons Back, Publish settings, Publish, and (when there is nothing to publish) the text "There are no unpublished changes to review", a disabled Publish (`aria-disabled="true"`) and a RETURN TO EDITOR button. The enabled Publish was **clicked for real 2026-11-08** (class-2034, the School Hours swap): dialog "Review changes and publish … Updated Home", Publish enabled, clicked, closed, exit 0 |
| Version history (`restore`) | `[aria-label="Open version history"]` in the app bar opens a full-window `[role=dialog]` with a `[role=complementary]` panel titled "Version history", newest first: "Current version", then entries whose italic label starts "Published …"; clicking an entry shows its date in the dialog's header and two buttons, `[aria-label="Restore this site version"]` and "Restore this page version"; the site one opens a small confirmation "Restore this version?" with Cancel and Restore; after Restore the panel closes and the app bar is back | **confirmed 2026-11-06** (all of it, one run) |

### Record of real runs

**2026-11-02, Ahin's Mac, Chrome 156.0.8078.80, Playwright 1.60.0, window 1200 × 919 (narrower than the 1440 the doc asks for).** Read-only; nothing in either Site was changed or published.

What stopped the first attempt: Chrome had been started with `--remote-debugging-port=9222` but had **no tabs open**, and `tabs` failed with `STOP: can't attach to Chrome at http://localhost:9222 (BrowserType.connect_over_cdp: Protocol error (Browser.setDownloadBehavior): Browser context management is not supported.)`. Opening one tab (`curl -X PUT 'http://localhost:9222/json/new?about:blank'`) fixed it. Keep at least one Chrome window open before attaching.

`python3 tools/sites_editor.py list --site class-2034 --page home --select --dump` (exit 0):

```
opening https://sites.google.com/d/1vqA_IFOx0oCDUi95RtQ-PPo-3LcD_szY/edit
signed in as: Google Account: SFFS Class Pages  
(classpages@sffriendsschool.org)
page 'Home': clicked its entry in the <div role=None>; panel opened via [role=tab]:has-text("Pages"); editor URL unchanged (https://sites.google.com/d/1vqA_IFOx0oCDUi95RtQ-PPo-3LcD_szY/p/13dwUNzc1KK6w3xcGRqiyBHCDDldaatKq/edit?pli=1)
window 1200 × 919 (device pixel ratio 1)  ← narrower than 1440; the canvas may be scaled, so sizes below may not be editor-box sizes
- room-parents  https://sffs-class-sites.github.io/class-sites/shared/room-parents/?class=2034
    box 701 × 411 (h/w 0.586) at x=117 y=634 in the window; registry box card = 935 × 625 (h/w 0.668)
    wrapped by https://www.gstatic.com/atari/embeds/9581c1cb067d2cf0b0db63dc0d8422ac/intermediate-frame-minified.ht
    iframe ancestors: iframe > div[aria-label='Whole page embed'] > div > div > div > div[role=gridcell][aria-label='IFRAME']
- important-dates  https://sffs-class-sites.github.io/class-sites/shared/important-dates/
    box 701 × 467 (h/w 0.666) at x=117 y=1766 in the window; registry box card = 935 × 625 (h/w 0.668)
    wrapped by https://www.gstatic.com/atari/embeds/9581c1cb067d2cf0b0db63dc0d8422ac/intermediate-frame-minified.ht
    iframe ancestors: iframe > div[aria-label='Whole page embed'] > div > div > div > div[role=gridcell][aria-label='IFRAME']
- selected room-parents by clicking the iframe's top-left corner (no block element starts above it): size label(s) none found
- selected important-dates by clicking the iframe's top-left corner (no block element starts above it): size label(s) none found
DOM record written: /Users/thomasfamilybot/code/sffs/class-sites/_editor/class-2034-home-20261102-194812.json / .html / .png
```

`python3 tools/sites_editor.py list --site class-2032 --page home --select --dump` (exit 0):

```
opening https://sites.google.com/d/1x30kZaz22W2SSzdL3fTxNm0jbSVyKWo9/edit
signed in as: Google Account: SFFS Class Pages  
(classpages@sffriendsschool.org)
page 'Home': clicked its entry in the <div role=None>; panel opened via [role=tab]:has-text("Pages"); editor URL unchanged (https://sites.google.com/d/1x30kZaz22W2SSzdL3fTxNm0jbSVyKWo9/p/1lD9M1-iZL34rVm03vuw-aotRWE5FtwNj/edit)
window 1200 × 919 (device pixel ratio 1)  ← narrower than 1440; the canvas may be scaled, so sizes below may not be editor-box sizes
- important-dates  https://sffs-class-sites.github.io/class-sites/shared/important-dates/
    box 701 × 469 (h/w 0.669) at x=117 y=448 in the window; registry box card = 935 × 625 (h/w 0.668)
    wrapped by https://www.gstatic.com/atari/embeds/9581c1cb067d2cf0b0db63dc0d8422ac/intermediate-frame-minified.ht
    iframe ancestors: iframe > div[aria-label='Whole page embed'] > div > div > div > div[role=gridcell][aria-label='IFRAME']
- selected important-dates by clicking the iframe's top-left corner (no block element starts above it): size label(s) none found
DOM record written: /Users/thomasfamilybot/code/sffs/class-sites/_editor/class-2032-home-20261102-194828.json / .html / .png
```

Full ancestor chain from the DOM record (the same for all three embeds; obfuscated classes left out), from the iframe outwards:

```
iframe[tabindex=-1][name=<tile data-id>]          the gstatic wrapper frame; the box
div[aria-label="Whole page embed"][data-url=<our embed URL>]   (height 0)
div[aria-disabled=true]
div
div[data-id=<tile id>]
div[role=gridcell][aria-label="IFRAME"][aria-selected][aria-grabbed][tabindex=-1]   selection state lives here
div
tile[data-id=<tile id>]
div  (class includes row_Default)
div
row[data-id=<row id>]
div  (class includes group_Default)
```

What the records also show:

- Room-parents on class-2034 is the only embed off the card ratio (0.586 vs 0.668). That fits §6 step 4.
- In the editor, the class-2034 room-parents embed renders its error state: "Couldn't load room parent contacts. Check your connection and try again." The published page wasn't checked here.
- Both sites' top bars carry an element labelled "Can't copy link for unpublished site". It is probably the copy-link button's disabled tooltip, always in the DOM. Not interpreted yet; look at it before building `publish`.
- No size label is the main change for step 2: `resize` must measure the iframe after each drag.

**2026-11-02 (evening), Ahin's Mac, Chrome 156.0.8078.80, Playwright 1.60.0, window maximised to 1830 × 1050 (viewport 1830 × 963) on a 1920 × 1080 screen.** First real `resize --apply`. The script didn't publish; Ahin then published class-2034 by hand from the editor, so `publish --apply` still hasn't run for real. `python3 tests/live_check.py --site class-2034` on the Mac, 2026-11-03: **PASS**, room-parents 1154 × 772 (0.669) at 1440 and 352 × 235 (0.668) on an iPhone, no drift note (it was 1154 × 677 / 352 × 206, both drift, before).

`python3 tools/sites_editor.py resize --site class-2034 --page home --embed room-parents --box card` (dry run, exit 0):

```
resize class-2034/home room-parents to box `card` = 935 × 625 (h/w 0.668)  (dry run: nothing is dragged)
using the open editor tab https://sites.google.com/d/1vqA_IFOx0oCDUi95RtQ-PPo-3LcD_szY/p/13dwUNzc1KK6w3xcGRqiyBHCDDldaatKq/edit?pli=1
page 'Home': clicked its entry in the <div role=None>; editor URL unchanged (https://sites.google.com/d/1vqA_IFOx0oCDUi95RtQ-PPo-3LcD_szY/p/13dwUNzc1KK6w3xcGRqiyBHCDDldaatKq/edit?pli=1)
window 1830 × 963
before: 1154 × 677 (h/w 0.586); drag the bottom-centre handle by +95px (to ≈1154 × 772)
dry run only; add --apply to drag. Nothing is published by resize.
```

The same with `--apply` (exit 0):

```
resize class-2034/home room-parents to box `card` = 935 × 625 (h/w 0.668)
using the open editor tab https://sites.google.com/d/1vqA_IFOx0oCDUi95RtQ-PPo-3LcD_szY/p/13dwUNzc1KK6w3xcGRqiyBHCDDldaatKq/edit?pli=1
page 'Home': clicked its entry in the <div role=None>; editor URL unchanged (https://sites.google.com/d/1vqA_IFOx0oCDUi95RtQ-PPo-3LcD_szY/p/13dwUNzc1KK6w3xcGRqiyBHCDDldaatKq/edit?pli=1)
window 1830 × 963
before: 1154 × 677 (h/w 0.586); drag the bottom-centre handle by +95px (to ≈1154 × 772)
drag 1: by +95px -> 1154 × 772 (h/w 0.669)
after: 1154 × 772 (h/w 0.669) (was 1154 × 677 (h/w 0.586)); target h/w 0.668 reached within ±0.005
not published. Look at it in the editor, then: publish --site class-2034 --apply
```

At 1830 wide the card embeds measure 1154 wide, the same as the published page's desktop width in §6 step 4 (1154 × 677), so the editor box and the published box agree at this window size.

What stopped the check afterwards: `list --site class-2034 --page home --select --dump`, run straight after to check the result, printed:

```
no embed of ours on this page (no frame whose URL starts with https://sffs-class-sites.github.io/class-sites/shared/...)
- MISSING: registry lists important-dates on this page but no frame of ours carries its URL
- MISSING: registry lists room-parents on this page but no frame of ours carries its URL
```

The same happened on a second `list`. The embeds are there. Editor state from that DOM record (`_editor/class-2034-home-20261102-202342.*`) and screenshot:
- "All changes saved in Drive".
- The room-parents iframe (same tile, `name="56709396dcb81339_0"`) is 1154 × 772 at x=205 y=608.
- important-dates is 1154 × 769 (0.666).
- Chrome's own `/json/list` shows both of our frames.
- The room-parents embed now renders the five room parents in the editor, not the error in §8.

The cause is in the script, not the editor: on a reused tab, Playwright's frame tree has `url == ""` for the gstatic wrapper frames and leaves out the frames below them. See the "Our embeds (`list`)" row above. Fixed 2026-11-03 (`list` finds blocks by `data-url`) and confirmed on the real editor 2026-11-06 (below).

**2026-11-06, the Mini, Chrome 156.0.8078.80, the same debug Chrome and editor tab as 2026-11-02, window 1830 × 963.** Read-only: the checks the PR #41 after-merge note asked for. Nothing was changed or published.

`python3 tools/sites_editor.py chrome` (exit 0):

```
Chrome is already listening at http://localhost:9222 (Chrome/156.0.8078.80); nothing to start
```

`python3 tools/sites_editor.py list --site class-2034 --page home --select --dump` (exit 0):

```
using the open editor tab https://sites.google.com/d/1vqA_IFOx0oCDUi95RtQ-PPo-3LcD_szY/p/13dwUNzc1KK6w3xcGRqiyBHCDDldaatKq/edit?pli=1
signed in as: Google Account: SFFS Class Pages (classpages@sffriendsschool.org)
page 'Home': clicked its entry in the <div role=None>; panel opened via [role=tab]:has-text("Pages"); editor URL unchanged (https://sites.google.com/d/1vqA_IFOx0oCDUi95RtQ-PPo-3LcD_szY/p/13dwUNzc1KK6w3xcGRqiyBHCDDldaatKq/edit?pli=1)
window 1830 × 963 (device pixel ratio 1)
- room-parents  https://sffs-class-sites.github.io/class-sites/shared/room-parents/?class=2034
    box 1154 × 772 (h/w 0.669) at x=205 y=608 in the window; registry box card = 935 × 625 (h/w 0.668)
    wrapped by https://www.gstatic.com/atari/embeds/9581c1cb067d2cf0b0db63dc0d8422ac/intermediate-frame-minified.ht
    block: div[aria-label="Whole page embed"][d…] with this data-url; our page is not in Playwright's frame tree
    iframe ancestors: iframe > div[aria-label='Whole page embed'] > div > div > div > div[role=gridcell][aria-label='IFRAME']
- important-dates  https://sffs-class-sites.github.io/class-sites/shared/important-dates/
    box 1154 × 769 (h/w 0.666) at x=205 y=2002 in the window; registry box card = 935 × 625 (h/w 0.668)
    wrapped by https://www.gstatic.com/atari/embeds/9581c1cb067d2cf0b0db63dc0d8422ac/intermediate-frame-minified.ht
    block: div[aria-label="Whole page embed"][d…] with this data-url; our page is not in Playwright's frame tree
    iframe ancestors: iframe > div[aria-label='Whole page embed'] > div > div > div > div[role=gridcell][aria-label='IFRAME']
- selected room-parents by a corner click: editor marks it selected = True; size label(s) none (the editor shows none)
- selected important-dates by a corner click: editor marks it selected = True; size label(s) none (the editor shows none)
```

So on the same kind of reused tab where `list` reported both embeds MISSING on 2026-11-02, the `data-url` lookup finds both, at the sizes `resize` left and the live check reports. Scroll-then-select works on a block below the fold. Starting Chrome with `chrome` was tested later the same day (below).

**2026-11-06 (afternoon), the Mini: `chrome` starting Chrome.** The signed-in debug Chrome was quit (`tell application "Google Chrome" to quit`, which also left the Mini's ordinary Chrome running), then:

```
$ python3 tools/sites_editor.py chrome
/Users/thomasfamilybot/Library/Application Support/Google/Chrome/classpages doesn't exist yet. Starting Chrome there on the Google sign-in page; sign in as classpages@sffriendsschool.org by hand, once, then run this command again. (This script never handles a password.)
  open -na Google Chrome --args --remote-debugging-port=9222 --user-data-dir=/Users/thomasfamilybot/Library/Application Support/Google/Chrome/classpages --profile-directory=Default --start-maximized --no-first-run --no-default-browser-check https://accounts.google.com/
exit=1
```

The message was wrong: the dir existed and was signed in, but the claude CLI on the Mini may not read it (`ls` says "Operation not permitted" on `…/Google/Chrome` and `…/classpages`, both `drwx------` and the user's own; the same without Claude Code's sandbox, so it is macOS, not the tool). `profiles_in` found no profile, and the script took that for "no data dir". Chrome did start, signed in: the sign-in page went straight to `myaccount.google.com`, the port was up a few seconds later, and `list` printed the account and both class-2034 embeds at the sizes of the morning's run (the blank-tab rule in §1 holds: Chrome opened with one tab). Fixed the same day: an unreadable dir now starts Chrome on a blank tab and exits 0 when the port is up. Re-tested by killing that Chrome (`kill -TERM`) and running `chrome` again:

```
$ python3 tools/sites_editor.py chrome
can't read /Users/thomasfamilybot/Library/Application Support/Google/Chrome/classpages (Operation not permitted): this process isn't allowed to look at Chrome's data, so who is signed in is unknown. Starting Chrome there anyway, maximised, debug port 9222; `list` prints the account:
  open -na Google Chrome --args --remote-debugging-port=9222 --user-data-dir=/Users/thomasfamilybot/Library/Application Support/Google/Chrome/classpages --profile-directory=Default --start-maximized --no-first-run --no-default-browser-check about:blank
Chrome is up: Chrome/156.0.8078.80 at http://localhost:9222. Next: list / resize / publish
exit=0
```

`tabs` then showed one `about:blank`. The window came up 1830 × 963 (maximised on the 1920 × 1080 screen). The mock test (`PW_CHROMIUM="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"`) passes on the Mini; it runs on free ports and a temp profile, so it can run beside the live Chrome.

**2026-11-06 (evening), the Mini: rollback and publish, on the 1st-grade site.** The test §3 asked for, done so that families would see no change. In order:

1. `resize --site class-2034 --page home --embed room-parents --box page --apply`: one drag of +308px, 1154 × 772 (0.669) → 1154 × 1080 (0.936). Unpublished.
2. `restore --site class-2034` (dry run, built for this): opened Version history, listed `TODAY | Current version | SFFS Class Pages | MONDAY | Published November 3, 7:17 AM | SFFS Class Pages | Published November 2, 7:54 AM | Ahin Thomas | …`, selected "Published November 3, 7:17 AM" (headed "November 2, 8:23 PM": the draft's save time, published the next morning by Ahin), found the Restore button, closed the panel.
3. `restore … --apply`: the same, then the confirmation `'Restore this version?\nFollow these steps to restore your site to the version from November 2 at 8:23 PM.\n\n1. Select the Restore button.\n2. Review your draft site.\n3. Select the Publish button to make …'; buttons ['Cancel', 'Restore']`; clicked Restore; the panel closed. `list` then measured room-parents at 1154 × 772 (0.669) again.
4. `publish --site class-2034 --apply`: the app-bar button opened `'Review changes and publish\nPublish\nThere are no unpublished changes to review\nRETURN TO EDITOR'; buttons ['Back', 'Publish settings', 'Publish', 'RETURN TO EDITOR']`. The first version of the script tried to click that Publish, which is disabled, and timed out with a traceback, leaving the dialog open. Fixed the same evening (it now reads the "no unpublished changes" text, clicks RETURN TO EDITOR and exits 0; and it looks for an already-open dialog before the app-bar button, which the dialog covers). The re-run printed `nothing to publish: the draft is what is live already …; returned to the editor`.
5. `tests/live_check.py --site class-2034`: PASS, room-parents 1154 × 772 (0.669) desktop, 352 × 235 (0.668) iPhone, unchanged. The mock test still passes.

So the rollback works and the publish dialog is known. Not exercised: clicking an enabled Publish, which needs a real change; the first real one will be the next box or page edit. Two things about running this from a Claude session on the Mini: Claude Code's auto-mode classifier refused `resize --apply` once and `restore --apply` twice as writes to a shared resource, though a person had said yes in chat; Ahin had an allow rule added to the Mini's `~/.claude/settings.json` for `python3 /Users/thomasfamilybot/code/sffs/class-sites/tools/sites_editor.py *`. That clone was deleted on 2026-11-07; the Mini's working clone is `~/Documents/sffs/class-sites`, and the rule has to name that path (`python3 /Users/thomasfamilybot/Documents/sffs/class-sites/tools/sites_editor.py *`) or every `--apply` run hits the classifier again. A run started from a `cd` into any other clone isn't covered by the rule. The `/Users/thomasfamilybot/code/…` paths in the run records above are historical.

**2026-11-07, the Mini, Chrome 156.0.8078.80, the same debug Chrome as 2026-11-06, window 1830 × 963.** Read-only: `chrome`, then `list` on both sites' Home pages, run from the `~/Documents/sffs/class-sites` clone by the script's full path (the `~/code/sffs/class-sites` clone was removed the same day after `git status` and the unpushed-commits check both came back empty). Nothing in either Site was changed or published.

`python3 tools/sites_editor.py chrome` (exit 0): the debug Chrome from the day before was still running, so the port-already-up branch ran and the script opened nothing:

```
Chrome is already listening at http://localhost:9222 (Chrome/156.0.8078.80); nothing to start
```

`python3 tools/sites_editor.py list --site class-2034 --page home` (exit 0), on the editor tab that had stayed open since 2026-11-06 (its URL had lost the `?pli=1` seen on 11-02 and 11-06):

```
using the open editor tab https://sites.google.com/d/1vqA_IFOx0oCDUi95RtQ-PPo-3LcD_szY/p/13dwUNzc1KK6w3xcGRqiyBHCDDldaatKq/edit
signed in as: Google Account: SFFS Class Pages (classpages@sffriendsschool.org)
page 'Home': clicked its entry in the <div role=None>; editor URL unchanged (https://sites.google.com/d/1vqA_IFOx0oCDUi95RtQ-PPo-3LcD_szY/p/13dwUNzc1KK6w3xcGRqiyBHCDDldaatKq/edit)
window 1830 × 963 (device pixel ratio 1)
- room-parents  https://sffs-class-sites.github.io/class-sites/shared/room-parents/?class=2034
    box 1154 × 772 (h/w 0.669) at x=205 y=608 in the window; registry box card = 935 × 625 (h/w 0.668)
    wrapped by https://www.gstatic.com/atari/embeds/197a9c195ad050c899a9ec96432b0a19/intermediate-frame-minified.ht
    block: div[aria-label="Whole page embed"][d…] with this data-url; our page is not in Playwright's frame tree
    iframe ancestors: iframe > div[aria-label='Whole page embed'] > div > div > div > div[role=gridcell][aria-label='IFRAME']
- important-dates  https://sffs-class-sites.github.io/class-sites/shared/important-dates/
    box 1154 × 769 (h/w 0.666) at x=205 y=2002 in the window; registry box card = 935 × 625 (h/w 0.668)
    wrapped by https://www.gstatic.com/atari/embeds/197a9c195ad050c899a9ec96432b0a19/intermediate-frame-minified.ht
    block: div[aria-label="Whole page embed"][d…] with this data-url; our page is not in Playwright's frame tree
    iframe ancestors: iframe > div[aria-label='Whole page embed'] > div > div > div > div[role=gridcell][aria-label='IFRAME']
```

`python3 tools/sites_editor.py list --site class-2032 --page home` (exit 0). No tab for this site was open, so the script opened the editor itself (the first time `list` has opened a fresh tab since 2026-11-02), and the Pages panel had to be opened:

```
opening https://sites.google.com/d/1x30kZaz22W2SSzdL3fTxNm0jbSVyKWo9/edit
signed in as: Google Account: SFFS Class Pages (classpages@sffriendsschool.org)
page 'Home': clicked its entry in the <div role=None>; panel opened via [role=tab]:has-text("Pages"); editor URL unchanged (https://sites.google.com/d/1x30kZaz22W2SSzdL3fTxNm0jbSVyKWo9/p/1lD9M1-iZL34rVm03vuw-aotRWE5FtwNj/edit)
window 1830 × 963 (device pixel ratio 1)
- important-dates  https://sffs-class-sites.github.io/class-sites/shared/important-dates/
    box 1154 × 772 (h/w 0.669) at x=205 y=448 in the window; registry box card = 935 × 625 (h/w 0.668)
    wrapped by https://www.gstatic.com/atari/embeds/197a9c195ad050c899a9ec96432b0a19/intermediate-frame-minified.ht
    block: div[aria-label="Whole page embed"][d…] with this data-url; our page is in Playwright's frame tree
    iframe ancestors: iframe > div[aria-label='Whole page embed'] > div > div > div > div[role=gridcell][aria-label='IFRAME']
```

What worked: every step of both commands, with no `STOP`. All three embeds measure the card shape (0.666–0.669) at 1830 wide, the same sizes as 2026-11-06 for class-2034 and the 1830-window equivalent of the 2026-11-02 measurement for class-2032 (701 × 469 then, 1154 × 772 now, 0.669 both times). On the fresh class-2032 tab our page **is** in Playwright's frame tree; on the reused class-2034 tab it is not. The `data-url` lookup found every embed either way.

What didn't, or changed: nothing failed. Two things to know about: the gstatic wrapper hash changed from `9581c1cb…` to `197a9c19…`, so that path is Google's deploy id, not a hook; and the Mini's `~/.claude/settings.json` allow rule still names `python3 /Users/thomasfamilybot/code/sffs/class-sites/tools/sites_editor.py *`, a path that no longer exists, so a `--apply` run from the `~/Documents` clone will meet the auto-mode classifier again until that rule is changed to the new path (CLAUDE.md §5 also names the old path). Read-only `list` ran without a prompt this time.

**2026-11-08, the Mini, Chrome 156.0.8078.80, the same debug Chrome and class-2034 editor tab as 2026-11-07, window 1830 × 963.** Read-only: the first real run of `list` after PR #64 (child pages, other blocks). Run from `~/Documents/sffs/class-sites` by full path. Nothing in either Site was changed or published. `chrome` printed "Chrome is already listening … nothing to start" (exit 0).

`python3 tools/sites_editor.py list --site class-2034 --page resources/basketball` (exit 0):

```
using the open editor tab https://sites.google.com/d/1vqA_IFOx0oCDUi95RtQ-PPo-3LcD_szY/p/17k7BfcaLK3QojPHbvp5Nctotwvbjel2J/edit
signed in as: Google Account: SFFS Class Pages (classpages@sffriendsschool.org)
page 'Resources': clicked its entry in the <a role=link>
page 'Basketball': clicked its entry in the <div role=None>
editor URL https://sites.google.com/d/1vqA_IFOx0oCDUi95RtQ-PPo-3LcD_szY/p/17k7BfcaLK3QojPHbvp5Nctotwvbjel2J/edit -> https://sites.google.com/d/1vqA_IFOx0oCDUi95RtQ-PPo-3LcD_szY/p/1NRzBnIB1XKJNeOWkWwnVys6q-sUBigC5/edit
window 1830 × 963 (device pixel ratio 1)
no embed of ours on this page (no div[aria-label="Whole page embed"][data-url] whose data-url starts with https://sffs-class-sites.github.io/class-sites/shared/...)
other blocks on the page (not URL embeds of ours): 4
- not in registry.yaml; identified by unidentified; frame not in Playwright's tree, so its content couldn't be read
    iframe 148 × 148 at x=0 y=-1584, src host no src
    ancestors: iframe
- hoops-2034-2027-winter (registered on this page, status code); identified by frame content
    iframe 424 × 210 at x=1406 y=57, src host about:blank
    starts: 'Super Friends · 1st Grade Basketball · Winter 2027 Every game is at St. Stephen '
    ancestors: iframe[role='presentation'] > div > div[data-ogsr-up=''] > header[role='none'] > div
- not in registry.yaml; identified by unidentified; frame not in Playwright's tree, so its content couldn't be read
    iframe 1445 × 867 at x=193 y=72, src host no src
    ancestors: iframe > span > div > div > div[data-exclude-global-shortcuts='']
- hoops-2034-2027-winter (registered on this page, status code); identified by attribute
    iframe 760 × 999 at x=403 y=448, src host www.gstatic.com
    ancestors: iframe[aria-label='Custom embed'] > div[data-enable-interaction='false'][data-url='https://692785319-atari-embeds.googleusercontent.com/embe...'][data-code='<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="ut...'][data-tile-id='561aee0d90206948_0'][data-enable-html-sites-gen-ai='false'][data-is-liquid-artifact='false'][data-enable-liquid-apps-vertical-scrolling='false'][data-in-editor='true'] > div > div > div[data-id='561aee0d90206948_0']
```

`python3 tools/sites_editor.py list --site class-2034 --page home` (exit 0); the two URL-embed rows are as on 2026-11-07 (room-parents 1154 × 772, important-dates 1154 × 769, both found by `data-url`, and this time our page **was** in Playwright's frame tree on the reused tab), then:

```
other blocks on the page (not URL embeds of ours): 5
- not in registry.yaml; identified by unidentified; frame not in Playwright's tree, so its content couldn't be read
    iframe 148 × 148 at x=0 y=-1584, src host no src
    ancestors: iframe
- not in registry.yaml; identified by unidentified
    iframe 424 × 210 at x=1406 y=57, src host about:blank
    starts: 'SFFS School Hours & Early Dismissal From the SFFS Family Handbook 2026–27, Secti'
    ancestors: iframe[role='presentation'] > div > div[data-ogsr-up=''] > header[role='none'] > div
- not in registry.yaml; identified by unidentified; frame not in Playwright's tree, so its content couldn't be read
    iframe 1445 × 867 at x=193 y=72, src host no src
    ancestors: iframe > span > div > div > div[data-exclude-global-shortcuts='']
- not in registry.yaml; identified by unidentified
    iframe 562 × 638 at x=501 y=3001, src host www.gstatic.com
    ancestors: iframe[aria-label='Custom embed'] > div[data-enable-interaction='false'][data-url='https://692785319-atari-embeds.googleusercontent.com/embe...'][data-code='<style>\n  .sffs-roster-wrap {\n    font-family: Arial, Hel...'][data-tile-id='5806beb90a400101_0'][data-enable-html-sites-gen-ai='false'][data-is-liquid-artifact='false'][data-enable-liquid-apps-vertical-scrolling='false'][data-in-editor='true'] > div > div > div[data-id='5806beb90a400101_0']
- not in registry.yaml; identified by unidentified
    iframe 661 × 808 at x=403 y=3687, src host www.gstatic.com
    ancestors: iframe[aria-label='Custom embed'] > div[data-enable-interaction='false'][data-url='https://692785319-atari-embeds.googleusercontent.com/embe...'][data-code='<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UT...'][data-tile-id='5806beb90a400101_34'][data-enable-html-sites-gen-ai='false'][data-is-liquid-artifact='false'][data-enable-liquid-apps-vertical-scrolling='false'][data-in-editor='true'] > div > div > div[data-id='5806beb90a400101_34']
```

What worked:

- The child page. "Resources" then "Basketball", two clicks, the URL moved to the child's page id, no STOP. The parent entry is an `<a role=link>`, unlike the role-less `div` of the other entries; the child's title was visible straight after the parent click, so neither expander branch ran.
- The editor keeps the pasted code: every pasted block is `iframe[aria-label='Custom embed']` under a `div[data-code=…][data-url=https://<n>-atari-embeds.googleusercontent.com/…][data-tile-id=…][data-in-editor='true']`. The registered hoops block was identified **by attribute** (its `match` text is inside `data-code`). That is the hook for ROADMAP C4: the editor's `data-code` can be hashed exactly as `tests/monitor.py` hashes the published page's, so a registry hash can be checked from the editor too.
- The two unregistered home-page blocks (the birthdays roster and school hours, ROADMAP C4) are listed as blocks, with their `data-code` starts and sizes (562 × 638 at y=3001 and 661 × 808 at y=3687; pasted blocks are narrower than the 1154px URL embeds).

What differed from the assumption, to fix in the script:

- Three iframes that are not blocks are listed on every page: a 148 × 148 one with no src at y=−1584 (off-canvas), the 424 × 210 `iframe[role='presentation']` with src `about:blank` inside `header[role='none'] > div[data-ogsr-up]` (the Google account bar, top right), and a 1445 × 867 one with no src at x=193 y=72 under `div[data-exclude-global-shortcuts]`. Only iframes with `aria-label='Custom embed'` (or a `data-code` ancestor) should count as pasted blocks.
- The frame-content step pairs a block with a Playwright frame by URL. The pasted block's wrapper iframe has a gstatic src, and its inner frame (the one with the pasted page) is `about:blank`, so `frames.get("about:blank")` landed on the header iframe's row: it was credited with "identified by frame content" and the pasted page's text (hoops on basketball, school hours on home), while the real blocks got no `starts:` line. Match on `data-code` only, and for the first-text fall-back read the frame nested inside the block's wrapper rather than keying by URL.
- Otherwise the unidentified rows are right: those two blocks have no registry `match` text yet.


**2026-11-08 (afternoon), the Mini, Chrome 156.0.8078.80, window 1830 × 963: the first swap of a pasted block for a URL embed, and the first real `publish --apply` with a change.** class-2034 Home: the pasted School Hours block (hash `5d656010830c`) replaced by `…/shared/school-hours/?class=2034` at box `card`. Ahin approved from a screenshot of the draft before the publish. The birthdays roster block was not touched.

What was done, in order (an ad-hoc Playwright script importing this script's helpers for the parts the script has no command for; each step screenshotted and checked before the next):

1. The pasted block's **Edit** (pencil) button appeared above its top-left corner after a corner click (with **Remove** beside it), though `selected()` reported False: the `aria-selected` lives on a `[role=gridcell][aria-label="IFRAME"]` for URL embeds, and the pasted block's gridcell is labelled differently. Its dialog is **"Edit embed", one textarea "HTML code goes here", Cancel and Next: no By URL tab.** Escaped.
2. Double-clicking the block itself does nothing. Double-clicking the **section's empty canvas** beside it (x=250 at this window, inside the content column but left of the block) opens the in-place menu: `[role=menuitem]` Images, Embed, Text, Upload, From Drive in a ring. **Embed** opens "Embed from the web" with `[role=tab]` **By URL** (selected) and **Embed code**, a text input labelled "Paste the URL (link) of the site you'd like to embed.", and Cancel / Insert (Insert `aria-disabled` until a URL is typed). After typing the URL and ~4 s the dialog read "Enter URL / Whole page / Show dynamically updating site page. / Not what you want?" and Insert was enabled; no Preview option for our page.
3. Insert put the new `div[aria-label="Whole page embed"][data-url=…school-hours…]` **in the same row as the old block**, 464 × 272 at x=205, with the old block pushed right. Removing the old block (corner click, then its **Remove** button) left the new one alone in the row at 464 × 272, still where the old block had been.
4. Dragging the new block's **right-middle handle** to the column's right edge (x=1359) made it 1154 wide (full column), height unchanged. The element handle went stale after the drag (measured 0 × 0 until re-queried by `data-url`).
5. `resize --site class-2034 --page home --embed school-hours --box card --apply` **stopped before dragging**: `STOP: the bottom handle (y=731) or where it has to go (y=1231) is outside the window (1830 × 963)`. The block sits at the bottom of the page, so `bring_into_view` cannot scroll it high enough for one +500 px drag. The same drag done in steps with `drag_bottom_handle` (+180, +180, +139) reached 1154 × 771 (h/w 0.668). **Fixed the same evening: `resize` drags by the room it has and repeats; the mock test covers a bottom-of-page block.**
6. `publish --site class-2034 --apply`: the review dialog read "Review changes and publish / Last published 25 minutes ago / Changes / Updated Home / Draft / Currently published"; buttons Back, Publish settings, Publish, Hide sidebar, Expand, Expand. Publish was enabled and was clicked; the dialog closed; `published.` (exit 0). **The enabled Publish row in §4 is now confirmed.**
7. `tests/live_check.py --site class-2034`: PASS; `school-hours` on home with `class=2034`, 1154 × 771 (0.668) at 1440, 352 × 235 (0.668) on the iPhone, 905 × 605 at 1024, version `school-hours@2026-08.413e64b6`, no drift note once the slot was `status: url`, `box: card`.

**2026-11-08 (later), the Mini, same Chrome and tab, window 1830 × 963: `resize --apply` and `publish --apply` as the doc describes them, start to finish.** Ahin had placed the School Hours URL embed (`?class=2034`) on class-2034 Home himself, unpublished. `list` found it at 1154 × 677 (h/w 0.586), the only URL embed off the card shape, plus the three others unchanged and the birthdays roster as the one pasted block. `resize … --embed school-hours --box card` (dry run) planned `+95px (to ≈1154 × 772)`; with `--apply`: `drag 1: by +95px -> 1154 × 772 (h/w 0.669)`, target reached within ±0.005, one drag, no stop (the block's bottom plus 95 px fit the window). Ahin approved from a screenshot. `publish --apply`: dialog "Review changes and publish / Last published 2 hours ago / Changes / Updated Home", Publish clicked, `published.`, exit 0. `tests/live_check.py --site class-2034` with the slot at `status: url`, `box: card`: PASS, 1154 × 772 (0.669) at 1280 and 1440, 905 × 605 (0.669) at 1024, 352 × 235 (0.668) on the iPhone, version `school-hours@2026-08.413e64b6`, no drift. So the two commands in §2 have now each run for real with a visible change, end to end, in one sitting.

## 5. What the DOM record holds

`list --dump` writes three files under `_editor/` (ignored by git; it holds the editor page's HTML, which may carry the signed-in account's name):

- `.json`: editor URL, window size, account label, each embed (URL, box, position, wrapper URL, sandbox, ancestor chain with roles/aria/data attributes and classes), every size label on the page, every frame and its parent, and counts of every `role`, `aria-label` and `data-*` attribute on the page.
- `.html`: the editor document (top frame only).
- `.png`: the window.

## 6. The plan the brief sets out

1. `list` (read-only) on both class sites: done, run on the Mac 2026-11-02, §4 filled; re-run on class-2034 at an 1830px window 2026-11-06 with the `data-url` lookup.
2. `resize`: built 2026-11-03 (there is no size label, so it measures the iframe after each drag and aims at the box's shape). Dry run by default; `--apply` drags; never publishes. **Run for real 2026-11-02 on class-2034 room-parents: 1154 × 677 → 1154 × 772 (0.669); Ahin published it by hand** (§4).
3. `publish`: built 2026-11-03: click Publish, confirm in the dialog. Separate command so a resize can be inspected in the editor first. **Run for real 2026-11-06**: the dialog is recorded in §4; there was nothing to publish, so the enabled Publish button is still unclicked. `restore` (the §3 rollback) was built and run for real the same day.
4. Verify with `python3 tests/live_check.py --site class-2034`: the room-parents row should show h ÷ w 0.668 and no drift note; then update that slot's comment in `registry.yaml` and CLAUDE.md §7. Baseline run from a cloud session on 2026-11-03, before any resize: room-parents 1154 × 677 (0.587) on a desktop, 352 × 206 (0.585) on an iPhone, both listed as drift; everything else passed. That container reaches sites.google.com, so the check can run from there as well as from the Mac. **Done 2026-11-03** on the Mac after Ahin published: PASS, room-parents 1154 × 772 (0.669) on a desktop and 352 × 235 (0.668) on an iPhone, no drift note; `registry.yaml` and CLAUDE.md §7 updated.

## 7. Mock test

`PW_CHROMIUM=<chrome> python3 tests/test_sites_editor.py` serves a fake editor built to the markup recorded in §4 (Pages tab and tree; one `Whole page embed` block per embed with our real Pages page inside a wrapper iframe, at 935 × 625, 935 × 549 and 935 × 875; a `gridcell` that gets `aria-selected` on a corner click; a bottom-centre handle that only resizes a selected block and snaps to 8px; a Publish button whose dialog has Cancel and Publish), launches a Chromium with `--remote-debugging-port`, and runs every command against it: `tabs`, `list` on both pages with `--select --dump`, the `resize` dry run, `resize --apply` (one drag takes 935 × 549 to 935 × 624), a second `resize --apply` that finds nothing to do, `publish` dry run and `publish --apply`, then checks the mock recorded the publish at the new height. It proves the script's logic and the record format. It proves nothing about the real editor; §4 says what is confirmed there.

Things the mock taught that also apply to the real editor: the mouse only acts inside the window, so blocks are scrolled into view before a click or drag and the drag's end point is checked against the window height first; a click on the iframe itself goes to the embed, which is why the mock's iframes ignore pointer events the way the editor's tiles do.

## 8. Editor-only error

In the editor, the class-2034 room-parents embed renders its error state ("Couldn't load room parent contacts"). The published page is fine: checked 2026-11-03 from a cloud session, the embed on the live homepage lists the five room parents, and the extract at `…/class-sites/data/room-parents.json` returns 200 with `access-control-allow-origin: *`. So the editor's preview frame blocks the fetch, which doesn't matter for families and doesn't affect `resize`. Not investigated further.
