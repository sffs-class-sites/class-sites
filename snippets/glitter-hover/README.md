# Glitter hover

A paste-in Google Sites embed: hovering over (or tapping) a marked piece of
text rains glitter over the embed. Not deployed by Pages and not used by any
live site; kept here for whoever wants it.

## Use it

1. Copy `glitter-hover.html` somewhere outside the repo.
2. Replace the placeholder text with the real text. Wrap the trigger in
   `<span data-glitter>…</span>`. More than one trigger is fine.
3. In Sites: **Insert → Embed → Embed code**, paste the whole file.
4. Size the box against the published page and check a phone (see below).

**Never commit the filled-in copy.** Room-parent names and emails are
personal data and this repo is public (CLAUDE.md §3).

## Known limits

- Glitter stays inside the embed box. Sites embeds are sandboxed iframes and
  cannot draw over the rest of the page.
- Phones get a ~315px-wide frame with the box's aspect ratio
  (google-sites-playbook §2.2). A wide, short box of text becomes a tiny
  scrolling window on phones. Prefer narrow, tall boxes.
- Text inside the embed is edited in code, not the Sites editor.
- `prefers-reduced-motion: reduce` turns the effect off entirely.
- Links use `target="_blank" rel="noopener"`, because the Sites sandbox
  blocks top-level navigation.

## Styling

Defaults match the 1st-grade class page body text (Verdana 18.67px, centered,
black; links `rgb(0,65,165)`), measured in the Sites editor on 2026-10-29.
Change the `:root` variables for other sites.
