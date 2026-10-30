# Glitter hover (room-parent list)

**Used only on the Class of 2034 site.** Not a standard component: don't add it
to other class sites without asking Ahin. The registry notes this too
(`registry.yaml`, under `class-2034`).

A paste-in Google Sites embed: the room-parent list, where hovering over one
name (desktop) or tapping anywhere in the list (phones) rains glitter over it.
Not deployed by Pages.

## Use it

1. Copy `glitter-hover.html` somewhere outside the repo.
2. Replace the placeholder rows with the real ones. Wrap the trigger name in
   `<span data-glitter>…</span>`.
3. In Sites: **Insert → Embed → Embed code**, paste the whole file.
4. Size the box to **296 × 252** in the editor at a 1440px window, starting at
   the 4-column position that centers it (its center lines up with the page's).

**Never commit the filled-in copy.** Names and emails are personal data and
this repo is public (CLAUDE.md §3).

## How it behaves

- **Desktop:** only hovering over the marked name triggers it; mouse clicks don't.
- **Phones/tablets:** any tap in the embed triggers it, including on an email
  link. The glitter starts and the mail app opens.
- `prefers-reduced-motion: reduce` turns the effect off.
- Links use `target="_blank" rel="noopener"` (Sites sandbox blocks top-level
  navigation). Opening the mail app was confirmed on a phone, 2026-10-30.

## Why the box is narrow and the text scales

- Glitter can't leave the embed box (sandboxed iframe).
- Phones get a ~315px-wide frame with the box's shape (h / w). A wide, short
  text box becomes a tiny scrolling window on phones.
- Sites shows the box larger on the published page than in the editor, but
  normal page text doesn't grow. Fixed-size text in the embed therefore leaves
  empty space under the list on the published page.
- So the text scales with the box: `font-size = 100vw × 18.67 / --design-w`,
  capped at 20px. The list fills the box at every width.
- 296px is the narrowest grid width that fits the longest line and sits exactly
  centered. Measured in Preview (2026-10-30): desktop text about the page's
  size, phone text about 16px, no scrolling.

Tradeoff: desktop text size follows the browser width, so it won't always match
the surrounding page text exactly (up to 20px on wide monitors).
