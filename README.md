# SFFS class sites

Source of truth for content shared across the SFFS K–8 class Google Sites.

- `shared/` — platform-wide embeds, served by GitHub Pages and embedded **by URL** in every class site.
- `build/` — scripts that turn data (`*.json`) into embed pages.
- `tests/` — render checks run in CI before anything deploys.
- `registry.yaml` — which embed goes in which slot on which site. The monitor reads it.

**Status page:** https://sffs-class-sites.github.io/class-sites/status/ shows every site and shared embed as OK, Needs attention or Broken. It's refreshed daily and on every deploy, and Broken opens a GitHub issue for Ahin.

Every change runs through `.github/workflows/deploy.yml`: validate data against the source calendar, build, render-check inside a Google Sites-style sandbox at desktop/tablet/phone widths, then publish to GitHub Pages.


## Embed URLs

| Embed | URL to paste into Google Sites (Insert → Embed → By URL → Whole page) |
|---|---|
| Important Dates | https://sffs-class-sites.github.io/class-sites/shared/important-dates/ |
| Room Parents (not live yet) | https://sffs-class-sites.github.io/class-sites/shared/room-parents/?class=2034 (use the class's graduation year). Says "not published yet" until the school approves the list. |
