# SFFS class sites

Source of truth for content shared across the SFFS K–8 class Google Sites.

- `shared/` — platform-wide embeds, served by GitHub Pages and embedded **by URL** in every class site.
- `build/` — scripts that turn data (`*.json`) into embed pages.
- `tests/` — render checks run in CI before anything deploys.
- `tools/` — `sites_editor.py`, the script that resizes and publishes embeds in the Google Sites editor (`docs/sites-editor-driver.md`).
- `registry.yaml` — which embed goes in which slot on which site. The monitor and the live check read it.
- `requirements.txt` — the pinned Python packages CI installs (`.github/actions/setup` installs them in every workflow).

**Status page:** https://sffs-class-sites.github.io/class-sites/status/ shows every site and shared embed as OK, Needs attention or Broken. It's refreshed daily and on every deploy, and Broken opens a GitHub issue for Ahin.

Every change runs through `.github/workflows/deploy.yml`: validate data against the source calendar, build, render-check inside a Google Sites-style sandbox at desktop/tablet/phone widths, then publish to GitHub Pages.

## Run the checks locally

The same steps CI runs, from the repo root (Python 3.12 in CI; the Mini's system Python works for the builds and unit tests):

```bash
pip install -r requirements.txt && python3 -m playwright install chromium
```

```bash
for b in build/build_*.py; do python3 "$b"; done
```

```bash
for t in tests/test_*.py tests/validate_*.py; do python3 "$t" || break; done
```

Then the browser checks, each on its own: `tests/render_check.py`, `tests/room_parents_check.py`, `tests/updates_check.py`, `tests/school_hours_check.py`, `tests/team_schedule_check.py`, `tests/live_check.py --mock`. Screenshots land in `_harness/` and `_live/` (ignored by git).


## Embed URLs

| Embed | URL to paste into Google Sites (Insert → Embed → By URL → Whole page) |
|---|---|
| Important Dates | https://sffs-class-sites.github.io/class-sites/shared/important-dates/ |
| Room Parents | https://sffs-class-sites.github.io/class-sites/shared/room-parents/?class=2034 (use the class's graduation year). Live on the 1st-grade homepage since 2026-10-31. Says "not published yet" for a class whose list the school has not approved in the Site Map. |
| Updates | https://sffs-class-sites.github.io/class-sites/shared/updates/?class=2034 (use the class's graduation year). What the school emails said, by grade. Live on the 1st-grade Email Digest page since 2026-11-02, at the `page` box. |
| School Hours | https://sffs-class-sites.github.io/class-sites/shared/school-hours/?class=2034 (use the class's graduation year; the viewer's grade row is flagged THIS CLASS). From the Family Handbook §4. Live on both homepages since 2026-11-08. |
| Team Schedule | https://sffs-class-sites.github.io/class-sites/shared/team-schedule/?team=hoops-2034-2027-winter (one `?team=` per season; the teams are data files in `shared/team-schedule/teams/`). Live on the 1st-grade Basketball page since 2026-11-08, replacing the pasted schedule. |
