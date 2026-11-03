# Driving the Google Sites editor: `tools/sites_editor.py`

Google Sites has no API (CLAUDE.md §5), so sizing an embed box or publishing a site is editor work. This script does that work from the command line, attached to a Chrome that a person signed in, so a Claude session never clicks through the editor one screenshot at a time. Written 2026-11-03.

**Status (2026-11-03):** every command is built. `list` ran read-only on the real editor on 2026-11-02 (§4 has the record). `resize --apply` and `publish --apply` are built from the hooks that run confirmed, tested only on the mock editor (§7) and **not yet run on the real editor**; the first real run is the room-parents box on the 1st-grade homepage (§6). The real editor shows no size label, so `resize` measures the iframe after each drag and aims at the box's shape (h ÷ w), which is what Sites publishes (CLAUDE.md §5).

## 1. Set-up on the Mac (once per session, Ahin)

1. Start Chrome with remote debugging on a profile that is signed in as `classpages@sffriendsschool.org` (admin on the class Sites). The script never handles a password, never launches a browser of its own, and is not headless: it drives the account's own window.

   ```bash
   open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir="$HOME/Library/Application Support/Google/Chrome/classpages"
   ```

   The `--user-data-dir` is whichever profile directory holds the `classpages@` sign-in. A fresh directory works too: sign in by hand in that window, once. Make the window at least 1440px wide and as tall as the screen allows: below 1440 the editor scales its canvas (701px cards at 1200), so sizes print smaller than the registry's, though shapes still hold; and a drag needs the block's bottom edge plus the drag distance inside the window, or `resize` stops before touching anything. Keep at least one tab open in that Chrome, or Playwright can't attach (§4, record of real runs).

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
| `tabs` | lists the attached Chrome's tabs | no |
| `list --site class-2034 --page home` | opens the site's editor (or reuses its open tab), selects the page in the Pages panel, prints each embed of ours: URL, query, box size and position in the editor, the wrapper frame, the iframe's ancestor chain; flags registered slots that are missing | no |
| `list … --select` | also clicks each block's corner and reports whether the editor marked it selected (`aria-selected`), the hook `resize` relies on | no (a click selects; nothing changes) |
| `list … --dump` | also writes `_editor/<site>-<page>-<time>.json`, `.html`, `.png`: the DOM record (§4) | no |
| `resize --site class-2034 --page home --embed room-parents --box card` | dry run: prints the current box, the target shape and the drag it would do | no |
| `resize … --apply` | selects the block, drags its bottom-centre handle, re-measures, repeats (up to 6 drags) until h ÷ w is within 0.005 of the box; prints before and after; **never publishes**. Stops before dragging if the block won't select or the handle would leave the window; stops after a drag that changed the width or nothing (exit 2, message says what to check; ⌘Z in the editor undoes it) | yes, unpublished |
| `publish --site class-2034` | dry run: finds the app-bar Publish button | no |
| `publish … --apply` | clicks Publish, reads the dialog, clicks its single **Publish** button, waits for the dialog to close. If the dialog isn't one Cancel/Publish pair it presses Escape and stops (exit 2) with what it saw | yes, live |

Exit codes: 0 ok; 1 the editor, Chrome or the registry isn't as expected (the `STOP:` line says what, and the script guessed nothing); 2 a write stopped half-way (the `STOPPED HALF-WAY:` line says what to look at in the editor).

Sites and pages come from `registry.yaml`: `--site` is a site key (`class-2034`), `--page` a slot's page slug (`home`, `email-digest`), `--embed` an embed id, `--box` a standard box name (`card`, `page`). The editor URL is `https://sites.google.com/d/<site_id>/edit`.

Pacing: the script waits 1.5 s after anything that changes what the editor shows. Automating the editor is a grey area under Google's terms; keep it human-paced and run it only as the account's own browser.

## 3. Rollback

The editor's **⋮ → Version history** restores an earlier version; publish again afterwards. **Untested** (also `docs/site-template.md` §3). Test it on the 1st-grade site before the first `resize --apply`: make a trivial change, restore, confirm the published page is unchanged.

## 4. What in the editor DOM the script depends on

Google changes the editor without notice and its class names are obfuscated, so the script only uses hooks that are likely to be stable: iframe `src`, ARIA roles and labels, text content. Each row says whether it was **confirmed** on the real editor (with the date) or is still **assumed**. When something breaks, run `list --dump`, read the record, update the script and this table.

| Script needs | How it looks for it | Status |
|---|---|---|
| The editor tab | a tab whose URL starts with `https://sites.google.com/d/<site_id>/`; otherwise opens `…/d/<site_id>/edit` | **confirmed 2026-11-02**: `…/d/<site_id>/edit` redirects to `…/d/<site_id>/p/<page id>/edit` (class-2034 also added `?pli=1`) |
| Signed-in check | a redirect to `accounts.google.com` means "not signed in", stop | assumed (not exercised: the profile was signed in) |
| Who is signed in | `[aria-label^="Google Account"]` in the top bar (the avatar button, which names the account in Google apps) | **confirmed 2026-11-02**: `aria-label="Google Account: SFFS Class Pages (classpages@sffriendsschool.org)"` (a newline before the parenthesis) |
| The Pages panel | `[role=tree]`; if absent, a `[role=tab]`/button labelled "Pages" is clicked to open it | **confirmed 2026-11-02**: the panel was closed; `[role=tab]` "Pages" opened it; one `[role=tree]` with one `[role=treeitem]` per top-level page (`aria-labelledby` = the page's id, `aria-selected="true"` on the current page). Item labels: "Home page, titled Home.", "Room Info.", "Email Digest.", "Resources. Child pages available." |
| A page entry | the smallest visible element whose text is exactly the page title (`email-digest` → "Email Digest"), preferring one under `[role=tree]`/`[role=treeitem]`; clicked at its centre, then the editor URL is printed | **confirmed for Home 2026-11-02**: the element found is a role-less `div` inside the treeitem; the click worked. The editor had already opened on Home, so the URL didn't change: moving to a different page is not yet exercised |
| Our embeds (`list`) | every frame on the editor page whose URL starts with `https://sffs-class-sites.github.io/class-sites/shared/<id>/`, as in `tests/live_check.py`; the outermost frame below the editor document is the block (Sites wraps URL embeds in a `*-atari-embeds.googleusercontent.com` frame on the published site; the editor is expected to do the same) | **confirmed 2026-11-02**, but the wrapper differs: in the editor our page is a child of `https://www.gstatic.com/atari/embeds/<hash>/intermediate-frame-minified.html` (the `*-atari-embeds.googleusercontent.com` frames on the page belong to other Custom embeds, not ours). The wrapper's parent is `div[aria-label="Whole page embed"]`, which carries our URL in `data-url`. That is a hook that works without entering frames |
| Box size | the bounding box of that outermost iframe element, in CSS px of the editor window; expected to equal the editor's size label at a ≥1440px window | **measured only at a 1200px window** (2026-11-02): the canvas is scaled, so card embeds measure 701 wide against the registry's 935 (×0.75). The h/w ratios still hold: class-2034 room-parents 0.586, important-dates 0.666; class-2032 important-dates 0.669 (card = 0.668). Re-run at ≥1440 before `resize` |
| A block (`resize`) | `div[aria-label="Whole page embed"][data-url]` whose `data-url` is the embed's URL (same id and query as the registry slot); its `iframe` is the box | **confirmed 2026-11-02** in the DOM record; used by `resize` and `list --select` since 2026-11-03, not yet exercised on the real editor |
| Selecting a block | scroll it into view, click the iframe's top-left corner (+2, +2); then `div[role=gridcell][aria-label="IFRAME"]` above it must carry `aria-selected="true"` or the script stops | **confirmed 2026-11-02** (the click and the attribute); the scroll-first version not yet run for real |
| Size label | none: the real editor shows no `W × H` on a selected embed (2026-11-02). `resize` measures the iframe's bounding box after every drag instead, and aims at the registry box's shape | **confirmed absent 2026-11-02** |
| Resize handle | by position only: bottom centre of the selected block's iframe, `(x + w/2, y + h)`; the script moves there, presses, moves down in 12 steps, releases, and checks the iframe got taller and no wider | **seen 2026-11-02**, no DOM hook; the drag is **assumed** until the first real `resize --apply` |
| Publish | `[guidedhelpid="at-appbar-publish"]` (fallback: `div[role=button]` with text Publish); then a `[role=dialog]`/`[role=alertdialog]` with exactly one button whose text is Publish, which is clicked; the dialog must close within 10 s | button **found 2026-11-02**; the dialog is **assumed** (never opened) and the script stops with a dump of it if it differs |

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

## 5. What the DOM record holds

`list --dump` writes three files under `_editor/` (ignored by git; it holds the editor page's HTML, which may carry the signed-in account's name):

- `.json`: editor URL, window size, account label, each embed (URL, box, position, wrapper URL, sandbox, ancestor chain with roles/aria/data attributes and classes), every size label on the page, every frame and its parent, and counts of every `role`, `aria-label` and `data-*` attribute on the page.
- `.html`: the editor document (top frame only).
- `.png`: the window.

## 6. The plan the brief sets out

1. `list` (read-only) on both class sites: done, run on the Mac 2026-11-02, §4 filled. A re-run at a ≥1440px window is still needed for absolute box sizes.
2. `resize`: built 2026-11-03 (there is no size label, so it measures the iframe after each drag and aims at the box's shape). Dry run by default; `--apply` drags; never publishes. **Not yet run on the real editor.**
3. `publish`: built 2026-11-03: click Publish, confirm in the dialog. Separate command so a resize can be inspected in the editor first. **Not yet run on the real editor**; the dialog has never been seen, so the first run may stop and ask for it to be recorded.
4. Verify with `python3 tests/live_check.py --site class-2034`: the room-parents row should show h ÷ w 0.668 and no drift note; then update that slot's comment in `registry.yaml` and CLAUDE.md §7. Baseline run from a cloud session on 2026-11-03, before any resize: room-parents 1154 × 677 (0.587) on a desktop, 352 × 206 (0.585) on an iPhone, both listed as drift; everything else passed. That container reaches sites.google.com, so the check can run from there as well as from the Mac.

## 7. Mock test

`PW_CHROMIUM=<chrome> python3 tests/test_sites_editor.py` serves a fake editor built to the markup recorded in §4 (Pages tab and tree; one `Whole page embed` block per embed with our real Pages page inside a wrapper iframe, at 935 × 625, 935 × 549 and 935 × 875; a `gridcell` that gets `aria-selected` on a corner click; a bottom-centre handle that only resizes a selected block and snaps to 8px; a Publish button whose dialog has Cancel and Publish), launches a Chromium with `--remote-debugging-port`, and runs every command against it: `tabs`, `list` on both pages with `--select --dump`, the `resize` dry run, `resize --apply` (one drag takes 935 × 549 to 935 × 624), a second `resize --apply` that finds nothing to do, `publish` dry run and `publish --apply`, then checks the mock recorded the publish at the new height. It proves the script's logic and the record format. It proves nothing about the real editor; §4 says what is confirmed there.

Things the mock taught that also apply to the real editor: the mouse only acts inside the window, so blocks are scrolled into view before a click or drag and the drag's end point is checked against the window height first; a click on the iframe itself goes to the embed, which is why the mock's iframes ignore pointer events the way the editor's tiles do.

## 8. Editor-only error

In the editor, the class-2034 room-parents embed renders its error state ("Couldn't load room parent contacts"). The published page is fine: checked 2026-11-03 from a cloud session, the embed on the live homepage lists the five room parents, and the extract at `…/class-sites/data/room-parents.json` returns 200 with `access-control-allow-origin: *`. So the editor's preview frame blocks the fetch, which doesn't matter for families and doesn't affect `resize`. Not investigated further.
