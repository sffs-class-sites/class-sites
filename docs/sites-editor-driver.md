# Driving the Google Sites editor: `tools/sites_editor.py`

Google Sites has no API (CLAUDE.md §5), so sizing an embed box or publishing a site is editor work. This script does that work from the command line, attached to a Chrome that a person signed in, so a Claude session never clicks through the editor one screenshot at a time. Written 2026-11-03.

**Status (2026-11-03):** `list` is built and tested against a mock editor only (`tests/test_sites_editor.py`). **It has not yet run against the real editor**, because the session that wrote it ran in a cloud container with no connection to the Mac. `resize --apply` and `publish --apply` are not built: they wait for the DOM record in §4, which the first real `list --select --dump` run fills in. Until then both commands dry-run and `--apply` exits 2.

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
| The editor tab | a tab whose URL starts with `https://sites.google.com/d/<site_id>/`; otherwise opens `…/d/<site_id>/edit` | assumed (URL pattern from the task brief; the editor is expected to redirect to `…/p/<page id>/edit`) |
| Signed-in check | a redirect to `accounts.google.com` means "not signed in", stop | assumed |
| Who is signed in | `[aria-label^="Google Account"]` in the top bar (the avatar button, which names the account in Google apps) | assumed |
| The Pages panel | `[role=tree]`; if absent, a `[role=tab]`/button labelled "Pages" is clicked to open it | assumed |
| A page entry | the smallest visible element whose text is exactly the page title (`email-digest` → "Email Digest"), preferring one under `[role=tree]`/`[role=treeitem]`; clicked at its centre, then the editor URL is printed | assumed |
| Our embeds | every frame on the editor page whose URL starts with `https://sffs-class-sites.github.io/class-sites/shared/<id>/`, as in `tests/live_check.py`; the outermost frame below the editor document is the block (Sites wraps URL embeds in a `*-atari-embeds.googleusercontent.com` frame on the published site; the editor is expected to do the same) | assumed |
| Box size | the bounding box of that outermost iframe element, in CSS px of the editor window; expected to equal the editor's size label at a ≥1440px window | assumed |
| Selecting a block | a click on the top edge of the nearest ancestor element that starts above the iframe (a click inside the iframe goes to the embed); falls back to the iframe's top-left corner | assumed |
| Size label | after selecting, every visible text node matching `W × H` (digits, × or x), nearest the block first; its element's attributes are printed so the real hook can be recorded here | assumed; the mock shows one |
| Resize handle | not yet looked for; expected at the bottom centre of the selected block | **not recorded** (needed for step 2) |
| Publish | not yet looked for; expected a button labelled "Publish" and a confirmation dialog with its own "Publish" button | **not recorded** (needed for step 3) |

Record of real runs: *none yet*. When the first `list --select --dump` runs on the Mac, paste here: the date, the editor URL after selecting Home, the ancestor chain printed for a block, the element the size label lives in, and anything the script stopped on.

## 5. What the DOM record holds

`list --dump` writes three files under `_editor/` (ignored by git; it holds the editor page's HTML, which may carry the signed-in account's name):

- `.json`: editor URL, window size, account label, each embed (URL, box, position, wrapper URL, sandbox, ancestor chain with roles/aria/data attributes and classes), every size label on the page, every frame and its parent, and counts of every `role`, `aria-label` and `data-*` attribute on the page.
- `.html`: the editor document (top frame only).
- `.png`: the window.

## 6. The plan the brief sets out

1. `list` (read-only) on both class sites: done in code; **run it on the Mac and fill §4 before anything else.**
2. `resize`: select the block, drag the bottom-centre handle until the size label reads the target height, reading the label after each drag (the editor snaps to a grid). Dry run by default; `--apply` drags; never publishes.
3. `publish`: click Publish, confirm. Separate command so a resize can be inspected in the editor first.
4. Verify with `python3 tests/live_check.py --site class-2034`: the room-parents row should show h ÷ w 0.668 and no drift note; then update that slot's comment in `registry.yaml` and CLAUDE.md §7.

## 7. Mock test

`PW_CHROMIUM=<chrome> python3 tests/test_sites_editor.py` serves a fake editor (Pages tree, our real Pages embeds inside wrapper iframes at 935 × 625, 935 × 549 and 935 × 875, a size label that appears on click), launches a Chromium with `--remote-debugging-port`, and runs `tabs`, `list` on both pages, the `resize` dry run and the two `--apply` refusals against it. It proves the attachment, navigation, frame discovery, measurement and the record format. It proves nothing about the real editor's DOM.
