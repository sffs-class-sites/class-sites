# Super Friends · 1st Grade Basketball · Winter 2027

The basketball schedule embed on the 1st-grade site's **Resources → Basketball** page (`sites.google.com/sffriendsschool.org/sffs-1st-class-page/resources/basketball`). Brought into the repo 2026-11-03 so nothing lives only on a machine (`docs/ROADMAP.md` C5).

**Since 2026-11-08 (C5 step 2) the season is a data file for the shared team-schedule embed:** `shared/team-schedule/teams/hoops-2034-2027-winter.json`, built by `build/build_team_schedule.py` and served at `https://sffs-class-sites.github.io/class-sites/shared/team-schedule/?team=hoops-2034-2027-winter`. `build_hoops.py` and the data file that lived here are gone. This folder keeps the record of the pasted copy that is still live, until Ahin swaps the Basketball page to the URL embed (then `registry.yaml`'s slot becomes `embed: team-schedule`, `query: {team: hoops-2034-2027-winter}`, `status: url`, and this folder can go).

| File | What it is |
|---|---|
| `source-team-tab.csv` | The league sheet's "1st Grade Hoops" tab as pasted by Ahin on 2026-10-29: the frozen source the data was typed from |
| `1st-hoops-embed.html` | The pasted embed as it is live on the Site (hash `b627556d43b0` in `registry.yaml`; checked 2026-11-03). `tests/team_schedule_check.py` reads its .ics events and proves the URL embed produces the same VEVENTs (UIDs, DTSTAMP, times, text) |

**How it is delivered today: pasted code**, not a URL embed. That is the opposite of the repo's rule (CLAUDE.md §1) and is tolerated only until the swap. Consequences:

- Until the swap, a data change reaches the Site only by re-pasting: there is no build for the pasted copy any more, so swap first, then edit the data file (the URL embed updates within ~10 minutes).
- `tests/live_check.py` cannot measure it (it only knows URL embeds); `tests/monitor.py` checks it is present and unedited.
- UIDs were derived at build time (`<date>-super-friends@sffs-1st-hoops`). They are now stored in the data file, frozen to those values (CLAUDE.md §6), and never change for an existing game (families who imported the .ics would get duplicates).
- All games are before DST starts (2027-03-14), so the build asserts that and uses a fixed UTC-8.

No personal data: team names, opponents, venue, and the league's public schedule link.
