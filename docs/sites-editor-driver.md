# Driving the Google Sites editor: `tools/sites_editor.py`

Google Sites has no API (CLAUDE.md §5), so sizing an embed box or publishing a site is editor work. This script does that work from the command line, attached to a Chrome that a person signed in, so a Claude session never clicks through the editor one screenshot at a time. Written 2026-11-03.

**Status (2026-11-02, Mac time):** `list` is built and tested against a mock editor (`tests/test_sites_editor.py`). On 2026-11-02 it also ran read-only against the real editor for class-2034 and class-2032 (§4 has the record). The real editor shows no size label, so `resize` has to measure the iframe instead. `resize --apply` and `publish --apply` are still not built: both commands dry-run and `--apply` exits 2.

## 1. Set-up on the Mac (once per session, Ahin)

1. Start Chrome with remote debugging on a profile that is signed in as `classpages@sffriendsschool.org` (admin on the class Sites). The script never handles a password, never launches a browser of its own, and is not headless: it drives the account's own window.

   ```bash
   open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir="$HOME/Library/Application Support/Google/Chrome/classpages"
   ```

   The `--user-data-dir` is whichever profile directory holds the `classpages@` sign-in. A fresh directory works too: sign in by hand in that window, once. Make the window at least 1440px wide; the registry's boxes were measured in the editor at that width, and a narrower window may scale the canvas.

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
| `list … --select` | also clicks each block so the editor shows its size label, and prints the label text and the element it lives in | no (a click selects; nothing changes) |
| `list … --dump` | also writes `_editor/<site>-<page>-<time>.json`, `.html`, `.png`: the DOM record (§4) | no |
| `resize --site class-2034 --page home --embed room-parents --box card` | dry run: prints the current box and the delta to the standard box | no |
| `resize … --apply` | **not built** (exit 2) | would |
| `publish --site class-2034` | dry run | no |
| `publish … --apply` | **not built** (exit 2) | would |

Exit codes: 0 ok; 1 the editor, Chrome or the registry isn't as expected (the `STOP:` line says what, and the script guessed nothing); 2 the action isn't built yet.

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
| Our embeds | every frame on the editor page whose URL starts with `https://sffs-class-sites.github.io/class-sites/shared/<id>/`, as in `tests/live_check.py`; the outermost frame below the editor document is the block (Sites wraps URL embeds in a `*-atari-embeds.googleusercontent.com` frame on the published site; the editor is expected to do the same) | **confirmed 2026-11-02**, but the wrapper differs: in the editor our page is a child of `https://www.gstatic.com/atari/embeds/<hash>/intermediate-frame-minified.html` (the `*-atari-embeds.googleusercontent.com` frames on the page belong to other Custom embeds, not ours). The wrapper's parent is `div[aria-label="Whole page embed"]`, which carries our URL in `data-url`. That is a hook that works without entering frames |
| Box size | the bounding box of that outermost iframe element, in CSS px of the editor window; expected to equal the editor's size label at a ≥1440px window | **measured only at a 1200px window** (2026-11-02): the canvas is scaled, so card embeds measure 701 wide against the registry's 935 (×0.75). The h/w ratios still hold: class-2034 room-parents 0.586, important-dates 0.666; class-2032 important-dates 0.669 (card = 0.668). Re-run at ≥1440 before `resize` |
| Selecting a block | a click on the top edge of the nearest ancestor element that starts above the iframe (a click inside the iframe goes to the embed); falls back to the iframe's top-left corner | **confirmed 2026-11-02** via the fallback (every ancestor shares the iframe's top edge). The corner click selects the block: its `div[role=gridcell][aria-label="IFRAME"]` gets `aria-selected="true" aria-grabbed="true"`, which is a usable "is selected" hook. On screen: a blue outline with 8 round handles, a floating toolbar ("Open in a new tab", "Remove") and a section toolbar on the left |
| Size label | after selecting, every visible text node matching `W × H` (digits, × or x), nearest the block first; its element's attributes are printed so the real hook can be recorded here | **does not exist** (2026-11-02): the real editor shows no `W × H` label on a selected embed (none in either DOM record or screenshot). `resize` has to read the iframe's bounding box after each drag, not a label |
| Resize handle | not yet looked for; expected at the bottom centre of the selected block | **seen, no DOM hook** (2026-11-02): the screenshot shows a round handle at the bottom centre of the selected block's outline, `(x + w/2, y + h)`, plus corners and side midpoints. No ARIA/role/data hook found for it in the dump; it would have to be driven by position |
| Publish | not yet looked for; expected a button labelled "Publish" and a confirmation dialog with its own "Publish" button | **found, not clicked** (2026-11-02): `div[role=button]` with text "Publish", `data-tooltip="Publish"`, `guidedhelpid="at-appbar-publish"`; next to it a `[aria-label="Publish options"]` menu button. The confirmation dialog has not been seen |

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
2. `resize`: select the block, drag the bottom-centre handle until the size label reads the target height, reading the label after each drag (the editor snaps to a grid). Dry run by default; `--apply` drags; never publishes.
3. `publish`: click Publish, confirm. Separate command so a resize can be inspected in the editor first.
4. Verify with `python3 tests/live_check.py --site class-2034`: the room-parents row should show h ÷ w 0.668 and no drift note; then update that slot's comment in `registry.yaml` and CLAUDE.md §7.

## 7. Mock test

`PW_CHROMIUM=<chrome> python3 tests/test_sites_editor.py` serves a fake editor (Pages tree, our real Pages embeds inside wrapper iframes at 935 × 625, 935 × 549 and 935 × 875, a size label that appears on click), launches a Chromium with `--remote-debugging-port`, and runs `tabs`, `list` on both pages, the `resize` dry run and the two `--apply` refusals against it. It proves the attachment, navigation, frame discovery, measurement and the record format. It proves nothing about the real editor's DOM.
