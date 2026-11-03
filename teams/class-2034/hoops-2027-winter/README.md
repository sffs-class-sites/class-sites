# Super Friends · 1st Grade Basketball · Winter 2027

The basketball schedule embed on the 1st-grade site's **Resources → Basketball** page (`sites.google.com/sffriendsschool.org/sffs-1st-class-page/resources/basketball`). Brought into the repo 2026-11-03 so nothing lives only on a machine (`docs/ROADMAP.md` C5).

| File | What it is |
|---|---|
| `source-team-tab.csv` | The league sheet's "1st Grade Hoops" tab as pasted by Ahin on 2026-10-29: the frozen source the data was typed from |
| `1st-hoops-data.json` | The data the build reads: games, venue, time zone offset, source link |
| `build_hoops.py` | Builds the embed from the data (`python3 build_hoops.py`, writes next to itself). Adapted from the Important Dates build: timed one-hour events in UTC, venue as location, Home/Away badge, "No game this week" rows |
| `1st-hoops-embed.html` | The built embed, byte-identical to the code pasted into the Site (hash `b627556d43b0` in `registry.yaml`; checked 2026-11-03). Committed because it is the record of what is live |

**How it is delivered today: pasted code**, not a URL embed. That is the opposite of the repo's rule (CLAUDE.md §1) and is tolerated only until C5. Consequences:

- A data change means: edit `1st-hoops-data.json`, run the build, open the Site's Basketball page in the editor, paste the new HTML into the embed, publish, then put the new hash in `registry.yaml`. The daily monitor shows the slot amber until the hash matches.
- `tests/live_check.py` cannot measure it (it only knows URL embeds); `tests/monitor.py` checks it is present and unedited.
- UIDs are derived at build time (`<date>-super-friends@sffs-1st-hoops`). CLAUDE.md §6 says UIDs must be stored, not recomputed; freeze them into the data file when C5 moves this to a URL embed, and never change one for an existing game (families who imported the .ics would get duplicates).
- All games are before DST starts (2027-03-14), so the build asserts that and uses a fixed UTC-8.

No personal data: team names, opponents, venue, and the league's public schedule link.
