#!/usr/bin/env python3
"""Build the Team Schedule embed: _site/shared/team-schedule/index.html (ROADMAP C5 step 2).

One shared page for every sport and club. Each team is a data file in
shared/team-schedule/teams/<id>.json (no personal data: team names, opponents, venue, the
league's public link); the build inlines them all, and at view time the page reads
?team=<id>, draws that season (month jumps, show-past toggle, Home/Away, "No game this
week" rows, NEXT UP and today), and offers per-game and whole-season calendar adds for
Google, Outlook and Apple (.ics built in the browser). The team's class gives the grade
line through shared/class/class.js.

Replaces teams/class-2034/hoops-2027-winter/build_hoops.py, which produced paste-in code.
The .ics events are the same as that build's: UIDs are stored in the data (frozen from the
old derivation, CLAUDE.md section 6), DTSTAMP is stored, times are written in UTC from the
team's fixed offset, so a family who re-imports is updated, not duplicated.

This file validates the data (tests/team_schedule_check.py checks more) and fails the build
on a missing or duplicate uid, a bad time, or a game past the offset's valid date.
"""
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import classinfo
import style

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEAMS = ROOT / "shared" / "team-schedule" / "teams"
OUT = ROOT / "_site" / "shared" / "team-schedule"
UID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*@[A-Za-z0-9][A-Za-z0-9.-]*$")


def load_team(path):
    t = json.loads(path.read_text())
    tid = path.stem
    if t.get("schema") != 1 or t.get("id") != tid:
        raise SystemExit(f"{path.name}: schema 1 and id == file name ({tid}) required")
    for k in ("title", "team", "event_suffix", "ics_name", "uid_domain", "dtstamp", "duration_minutes",
              "utc_offset_hours", "utc_offset_valid_until", "source", "venue", "games", "class"):
        if k not in t:
            raise SystemExit(f"{path.name}: missing {k}")
    issues = style.data_issues(t)
    if issues:
        raise SystemExit(f"{path.name}: after a colon, start the next word with a capital letter:\n  " + "\n  ".join(issues))
    if not re.fullmatch(r"\d{8}T\d{6}Z", t["dtstamp"]):
        raise SystemExit(f"{path.name}: dtstamp must look like 20261029T000000Z")
    limit = dt.date.fromisoformat(t["utc_offset_valid_until"])
    uids, dates = set(), []
    for g in t["games"]:
        day = dt.date.fromisoformat(g["date"])
        dates.append(day)
        if day >= limit:
            raise SystemExit(f"{path.name}: {g['date']} is on or after {limit}, when the UTC offset stops being right")
        if g.get("no_game"):
            continue
        for k in ("time", "opponent", "home_away", "court", "uid"):
            if not g.get(k):
                raise SystemExit(f"{path.name}: game {g['date']} is missing {k}")
        if not re.fullmatch(r"\d{2}:\d{2}", g["time"]):
            raise SystemExit(f"{path.name}: game {g['date']} time must be HH:MM (24h)")
        if g["home_away"] not in ("Home", "Away"):
            raise SystemExit(f"{path.name}: game {g['date']} home_away must be Home or Away")
        if not UID_RE.match(g["uid"]) or g["uid"] in uids:
            raise SystemExit(f"{path.name}: game {g['date']} uid missing, malformed or duplicate: {g.get('uid')}")
        uids.add(g["uid"])
    if dates != sorted(dates):
        raise SystemExit(f"{path.name}: games must be in date order")
    return {k: v for k, v in t.items() if not k.startswith("_")}


def load_all():
    files = sorted(TEAMS.glob("*.json"))
    if not files:
        raise SystemExit(f"no team files in {TEAMS}")
    teams = {p.stem: load_team(p) for p in files}
    raw = b"".join(p.read_bytes() for p in files)
    newest = max(t["source"]["retrieved"] for t in teams.values())
    return teams, f"{newest}.{hashlib.sha256(raw).hexdigest()[:8]}"


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="sffs-embed" content="team-schedule@{{VERSION}}">
<meta name="robots" content="noindex">
<title>Team Schedule</title>
<style>
:root{--ink:#1f2937;--sub:#5b6472;--line:#e2e5ea;--bg:#fff;--panel:#f7f8fa;--accent:#3457a6;--accent-light:#eaeffb;--home:#1a7f5a;--home-bg:#e7f6ef;--away:#2166b0;--away-bg:#e8f1fb;--hl-bg:#fff6d8;--hl-border:#e3c22b;--warn:#b4720a;--warn-bg:#fdf3e0}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg);line-height:1.45}
.wrap{height:100%;overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;border:2px solid #d6dff5;border-radius:12px;padding:16px 16px 56px}
h1{font-size:1.25rem;margin:0 0 2px}
.sub{color:var(--sub);font-size:.88rem;margin:0 0 10px}
.t-short{display:none}
.lead{border:1px solid var(--hl-border);background:var(--hl-bg);border-radius:12px;padding:10px 14px;margin:0 0 12px}
.lead[hidden]{display:none}
.lead .who{font-size:.78rem;font-weight:800;letter-spacing:.03em;text-transform:uppercase;color:#7a5b00;margin:0 0 3px}
.lead p{margin:2px 0;font-size:.98rem}
.lead .when{font-weight:700}
.lead .who-vs{font-weight:600}
.msg{padding:14px;border-radius:12px;background:var(--warn-bg);border:1px solid #f1d9a8;color:#6b4a07}
.toolbar{position:sticky;top:-16px;z-index:5;background:#fff;margin:0 -16px;padding:8px 16px;border-bottom:1px solid var(--line)}
.row{display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;align-items:center}
.row::-webkit-scrollbar{display:none}
.chip{flex:0 0 auto;font-family:inherit;font-weight:600;font-size:.8rem;line-height:1;padding:7px 11px;border-radius:999px;border:1px solid var(--line);background:var(--panel);color:var(--ink);cursor:pointer;display:inline-flex;align-items:center;gap:6px}
.chip:hover{background:var(--accent-light)}
.chip.on{background:var(--accent);border-color:var(--accent);color:#fff}
.chip[hidden]{display:none}
.chip:focus-visible,.btn:focus-visible,.add:focus-visible,a:focus-visible,.toggle input:focus-visible{outline:3px solid #f0a055;outline-offset:2px}
.toggle{font-size:.8rem;color:var(--sub);display:inline-flex;align-items:center;gap:6px;margin-left:auto;white-space:nowrap}
table{width:100%;border-collapse:collapse;margin-top:6px}
td{padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:top;font-size:.9rem}
.month-row td{background:var(--panel);font-weight:700;color:var(--accent);padding:7px 8px}
.date-cell,.time-cell{white-space:nowrap;font-weight:700;width:1%}
.time-cell{font-weight:600}
.badge{display:inline-block;font-weight:700;font-size:.72rem;line-height:1;padding:4px 7px;border-radius:999px;white-space:nowrap;margin-right:4px}
.badge.home{color:var(--home);background:var(--home-bg)}.badge.away{color:var(--away);background:var(--away-bg)}
.event-title{font-weight:600}
.event-details{color:var(--sub);font-size:.84rem;margin-top:2px}
tr.off td{color:var(--sub)}
tr.off .event-title{font-weight:500;font-style:italic}
.next-flag{display:inline-block;margin-left:8px;font-size:.64rem;font-weight:800;letter-spacing:.04em;color:#fff;background:var(--accent);border-radius:999px;padding:3px 7px;vertical-align:2px}
.action-cell{white-space:nowrap;text-align:right;width:1%}
.add{font-family:inherit;font-weight:600;font-size:.75rem;line-height:1;padding:6px 9px;border-radius:8px;border:1px solid var(--line);background:#fff;color:var(--accent);text-decoration:none;cursor:pointer;display:inline-block;margin-left:4px}
.add:hover{background:var(--accent-light)}
tr.today td{background:var(--hl-bg)}
tr.today td:first-child{box-shadow:inset 4px 0 0 var(--hl-border)}
tr[hidden]{display:none}
.empty{padding:18px;text-align:center;color:var(--sub)}
.tools{margin-top:14px;padding:10px 12px;background:var(--panel);border:1px solid var(--line);border-radius:12px}
.tools p{margin:0 0 8px;font-size:.84rem;font-weight:600}
.pills{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.btn{display:inline-flex;align-items:center;gap:6px;font-family:inherit;font-weight:600;font-size:.82rem;line-height:1;padding:8px 12px;border-radius:999px;border:1px solid var(--line);background:#fff;color:var(--accent);text-decoration:none;cursor:pointer}
.btn:hover{background:var(--accent-light)}
.note{margin:8px 0 0;color:var(--sub);font-size:.8rem}
.note strong{color:var(--ink)}
footer{margin-top:14px;font-size:.82rem;color:var(--sub)}
footer p{margin:4px 0}
footer a{color:var(--accent);font-weight:600}
.sffs-fade{position:fixed;left:2px;right:2px;bottom:2px;height:58px;z-index:8;pointer-events:none;background:linear-gradient(to bottom,rgba(255,255,255,0),#fff 72%);border-radius:0 0 10px 10px}
.sffs-hint{position:fixed;left:50%;bottom:12px;transform:translateX(-50%);z-index:9;pointer-events:none;white-space:nowrap;font:600 12px/1 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--accent);background:var(--accent-light);border:1px solid #d6dff5;padding:7px 13px;border-radius:999px;box-shadow:0 1px 5px rgba(0,0,0,.13)}
.sffs-fade[hidden],.sffs-hint[hidden]{display:none}
/* Narrow frames (the card box on a phone): one card per game, no sideways scrolling */
@media (max-width:560px){
  .wrap{padding:12px 12px 52px}
  .toolbar{top:-12px;margin:0 -12px;padding:6px 12px}
  h1{font-size:1.1rem}
  .t-long{display:none}.t-short{display:inline}
  .sub{font-size:.78rem;margin-bottom:8px}
  .sub .more{display:none}
  .lead{padding:8px 12px;margin-bottom:10px}
  .lead .who{margin-bottom:2px}
  .lead p{font-size:.92rem}
  table,tbody,tr,td{display:block;width:100%}
  tr.month-row td{margin-top:8px;border-radius:8px;border:0}
  tr.ev{border:1px solid var(--line);border-radius:12px;padding:9px 11px;margin:8px 0;display:grid;grid-template-columns:auto 1fr;column-gap:10px;row-gap:4px}
  tr.ev[hidden]{display:none}
  tr.ev td{border:0;padding:0;width:auto}
  .date-cell{grid-column:1}
  .time-cell{grid-column:2;text-align:right}
  .what-cell{grid-column:1/3}
  .action-cell{grid-column:1/3;text-align:left}
  tr.off .action-cell,tr.off .time-cell{display:none}
  .add{margin:2px 6px 0 0}
}
@media print{html,body{height:auto}body{overflow:visible}.wrap{height:auto;overflow:visible;border:0}.toolbar,.action-cell,.tools,.sffs-fade,.sffs-hint{display:none}}
</style>
</head>
<body>
<div class="wrap" id="wrap">
  <h1 id="title">Team schedule</h1>
  <p class="sub" id="sub"></p>
  <div class="lead" id="lead" hidden></div>
  <div id="body"></div>
</div>
<div class="sffs-fade" id="fade" hidden></div>
<div class="sffs-hint" id="hint" hidden>Scroll for more &#8595;</div>
<script>
{{CLASS_JS}}
</script>
<script>
{{LANG_JS}}
</script>
<script>
(function(){
  var TEAMS = {{TEAMS}};
  var MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var MON_LONG = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  var DOW = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  var KEY = 'sffsCalendarPref', LABEL = {google: 'Google', outlook: 'Outlook', apple: 'Apple'};
  function safeGet(k){ try { return localStorage.getItem(k); } catch(e) { return null; } }
  function safeSet(k, v){ try { localStorage.setItem(k, v); } catch(e) {} }
  function el(tag, cls, text){ var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function ymd(s){ var p = s.split('-'); return new Date(+p[0], +p[1]-1, +p[2]); }
  function clock(t){ var p = t.split(':'), h = +p[0]; return ((h + 11) % 12 + 1) + ':' + p[1] + ' ' + (h < 12 ? 'AM' : 'PM'); }
  function dayLabel(s){ var d = ymd(s); return DOW[d.getDay()] + ', ' + MON[d.getMonth()] + ' ' + d.getDate(); }
  /* iCalendar helpers: UTC from the team's fixed offset (the data says until when it holds). */
  function utc(dateStr, timeStr, offH){ var p = dateStr.split('-'), t = timeStr.split(':'); return new Date(Date.UTC(+p[0], +p[1]-1, +p[2], +t[0], +t[1]) - offH * 3600000); }
  function z(d){ return d.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, ''); }
  function iso(d){ return d.toISOString().replace(/\.\d{3}/, ''); }
  function icsEsc(s){ return s.replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\n/g, '\\n'); }
  function enc(s){ return encodeURIComponent(s); }

  var wrap = document.getElementById('wrap'), body = document.getElementById('body'), lead = document.getElementById('lead');
  var search = location.search;
  var m = /[?&]team=([A-Za-z0-9_-]+)(?:&|$)/.exec(search);
  var team = m && TEAMS[m[1]];
  var tq = /[?&]today=(\d{4}-\d{2}-\d{2})(?:&|$)/.exec(search);   // for tests
  var today = tq ? ymd(tq[1]) : new Date(); today.setHours(0, 0, 0, 0);

  if (!team) {
    document.getElementById('sub').textContent = 'A season schedule for one team.';
    body.appendChild(el('div', 'msg', m ? 'No team called "' + m[1] + '" is published. Check the ?team= in this embed\u2019s address.'
                                        : 'This embed needs a team in its address, for example ?team=hoops-2034-2027-winter.'));
    return;
  }

  /* Title and the class line, from the class model (CLAUDE.md section 1). */
  var h1 = document.getElementById('title'); h1.textContent = '';
  h1.appendChild(el('span', 't-long', team.title));
  h1.appendChild(el('span', 't-short', team.short_title || (team.team + ' \u00b7 ' + team.sport)));   /* phones: one line */
  var ci = SFFS.classInfo('?class=' + team.class + (tq ? '&today=' + tq[1] : ''));
  var sub = document.getElementById('sub'); sub.textContent = '';
  sub.appendChild(el('span', 'cls', ci.heading || ''));
  sub.appendChild(el('span', 'more', (ci.heading ? ' \u00b7 ' : '') + team.subtitle));   /* hidden on phones; the venue is in the footer too */

  /* Events: one per game, same fields and UIDs as the data. */
  var venue = team.venue.name + ', ' + team.venue.address;
  var events = [];
  team.games.forEach(function(g){
    if (g.no_game) return;
    var s = utc(g.date, g.time, team.utc_offset_hours), e = new Date(s.getTime() + team.duration_minutes * 60000);
    var title = team.team + ' vs. ' + g.opponent + ' ' + team.event_suffix;
    var details = g.home_away + ' game, ' + g.court + '. ' + venue;
    events.push({g: g, title: title, details: details, start: s, end: e,
      ics: ['BEGIN:VEVENT', 'UID:' + g.uid, 'DTSTAMP:' + team.dtstamp, 'DTSTART:' + z(s), 'DTEND:' + z(e),
            'SUMMARY:' + icsEsc(title), 'DESCRIPTION:' + icsEsc(details), 'LOCATION:' + icsEsc(venue), 'END:VEVENT'].join('\r\n'),
      file: g.uid.split('@')[0] + '.ics',
      google: 'https://calendar.google.com/calendar/render?action=TEMPLATE&text=' + enc(title) + '&dates=' + z(s) + '/' + z(e) + '&details=' + enc(details) + '&location=' + enc(venue),
      outlook: 'https://outlook.live.com/calendar/0/deeplink/compose?path=/calendar/action/compose&rru=addevent&startdt=' + enc(iso(s)) + '&enddt=' + enc(iso(e)) + '&subject=' + enc(title) + '&body=' + enc(details) + '&location=' + enc(venue)});
  });
  function wrapCal(list){ return 'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//SFFS Class Page//' + team.ics_name + '//EN\r\nCALSCALE:GREGORIAN\r\n' + list.join('\r\n') + '\r\nEND:VCALENDAR\r\n'; }
  function download(name, text){
    var blob = new Blob([text], {type: 'text/calendar;charset=utf-8'});
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click();
    setTimeout(function(){ URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }

  /* The next game first, so a phone shows it without scrolling. */
  var next = null, todays = null;
  events.forEach(function(ev){ var d = ymd(ev.g.date); if (d.getTime() === today.getTime()) todays = ev; if (!next && d >= today) next = ev; });
  var over = events.length && !next;
  function badge(ev){ var b = el('span', 'badge ' + ev.g.home_away.toLowerCase(), ev.g.home_away); return b; }
  if (todays || next || over) {
    var ev = todays || next || events[events.length - 1];
    lead.appendChild(el('p', 'who', todays ? 'Today\u2019s game' : next ? 'Next game' : 'Season finished \u00b7 last game'));
    lead.appendChild(el('p', 'when', dayLabel(ev.g.date) + ' \u00b7 ' + clock(ev.g.time)));
    var p = el('p', 'who-vs', 'vs. ' + ev.g.opponent + ' '); p.appendChild(badge(ev)); p.appendChild(document.createTextNode(' ' + ev.g.court)); lead.appendChild(p);
    lead.hidden = false;
  }

  /* Toolbar: month jumps and the past toggle. */
  var months = [];
  team.games.forEach(function(g){ var k = g.date.slice(0, 7); if (months.indexOf(k) < 0) months.push(k); });
  var bar = el('nav', 'toolbar'); bar.id = 'toolbar'; bar.setAttribute('aria-label', 'Jump to month');
  var row = el('div', 'row'); row.setAttribute('role', 'group'); row.setAttribute('aria-label', 'Jump to month');
  var jumps = months.map(function(k){ var b = el('button', 'chip jump', MON[+k.slice(5) - 1]); b.type = 'button'; b.setAttribute('data-jump', 'm-' + k); row.appendChild(b); return b; });
  var tog = el('label', 'toggle'); var cb = el('input'); cb.type = 'checkbox'; cb.id = 'showpast'; tog.appendChild(cb); tog.appendChild(document.createTextNode(' Show past games')); row.appendChild(tog);
  bar.appendChild(row); body.appendChild(bar);

  /* The season as rows. */
  var table = el('table'), tbody = el('tbody'); tbody.id = 'cal-body'; table.appendChild(tbody); body.appendChild(table);
  var rows = [], monthRows = [], idx = 0;
  team.games.forEach(function(g){
    var k = 'm-' + g.date.slice(0, 7);
    if (!monthRows.some(function(r){ return r.getAttribute('data-month') === k; })) {
      var mr = el('tr', 'month-row'); mr.id = k; mr.setAttribute('data-month', k);
      var d = ymd(g.date); var td = el('td', null, MON_LONG[d.getMonth()] + ' ' + d.getFullYear()); td.colSpan = 4; mr.appendChild(td);
      monthRows.push(mr); tbody.appendChild(mr);
    }
    var tr = el('tr', 'ev ' + (g.no_game ? 'off' : 'game')); tr.setAttribute('data-date', g.date); tr.setAttribute('data-month', k);
    tr.appendChild(el('td', 'date-cell', dayLabel(g.date)));
    if (g.no_game) {
      var t0 = el('td', 'time-cell'); t0.innerHTML = '&nbsp;'; tr.appendChild(t0);
      var w0 = el('td', 'what-cell'); w0.appendChild(el('div', 'event-title', 'No game this week')); tr.appendChild(w0);
      tr.appendChild(el('td', 'action-cell'));
    } else {
      var ev = events[idx]; tr.setAttribute('data-i', String(idx)); idx++;
      tr.appendChild(el('td', 'time-cell', clock(g.time)));
      var w = el('td', 'what-cell'); var ti = el('div', 'event-title', 'vs. ' + g.opponent);
      if (ev === todays) tr.classList.add('today');
      else if (ev === next) ti.appendChild(el('span', 'next-flag', 'NEXT UP'));
      w.appendChild(ti);
      var de = el('div', 'event-details'); de.appendChild(badge(ev)); de.appendChild(document.createTextNode(' ' + g.court)); w.appendChild(de);
      tr.appendChild(w); tr.appendChild(el('td', 'action-cell'));
    }
    rows.push(tr); tbody.appendChild(tr);
  });
  var empty = el('p', 'empty', 'No games to show.'); empty.id = 'empty'; empty.hidden = true; body.appendChild(empty);

  /* Calendar tools, after the list: pick a calendar, add all. */
  var tools = el('div', 'tools'); tools.id = 'tools';
  tools.appendChild(el('p', null, 'Add games to your calendar. Which one do you use?'));
  var pills = el('div', 'pills'); pills.setAttribute('role', 'group'); pills.setAttribute('aria-label', 'Your calendar');
  ['google', 'outlook', 'apple'].forEach(function(p){ var b = el('button', 'chip pref', p === 'google' ? 'Google Calendar' : p === 'outlook' ? 'Outlook' : 'Apple Calendar'); b.type = 'button'; b.setAttribute('data-pref', p); b.setAttribute('aria-pressed', 'false'); pills.appendChild(b); });
  var all = el('button', 'btn', 'Add all games'); all.type = 'button'; all.id = 'addall'; pills.appendChild(all);
  tools.appendChild(pills);
  var note = el('p', 'note'); note.id = 'addall-note'; tools.appendChild(note);
  body.appendChild(tools);
  all.addEventListener('click', function(){ download(team.id + '-games.ics', wrapCal(events.map(function(e){ return e.ics; }))); });
  var NOTE = {
    google: ['Each game has a + Google button. ', 'Add all games', ' downloads one calendar file: In Google Calendar, Settings \u2192 Import & export \u2192 Import, and choose the file.'],
    outlook: ['Each game has a + Outlook button. ', 'Add all games', ' downloads one calendar file: Open it, or use Import in your calendar settings.'],
    apple: ['Each game has a + Apple button. ', 'Add all games', ' downloads one calendar file: Open it and Apple Calendar offers to add them all.']
  };
  function renderButtons(pref){
    rows.forEach(function(r){
      if (!r.classList.contains('game')) return;
      var ev = events[+r.getAttribute('data-i')], cell = r.querySelector('.action-cell'), b;
      cell.textContent = '';
      if (pref === 'apple') { b = el('button'); b.type = 'button'; b.addEventListener('click', function(){ download(ev.file, wrapCal([ev.ics])); }); }
      else { b = el('a'); b.href = pref === 'outlook' ? ev.outlook : ev.google; b.target = '_blank'; b.rel = 'noopener noreferrer'; }
      b.className = 'add cal-btn'; b.textContent = '+ ' + LABEL[pref];
      b.setAttribute('aria-label', 'Add ' + ev.title + ' to ' + LABEL[pref] + (pref === 'apple' ? ' Calendar' : ''));
      cell.appendChild(b);
    });
  }
  function setPref(pref){
    if (!LABEL[pref]) pref = 'google';
    [].slice.call(pills.querySelectorAll('.chip.pref')).forEach(function(b){ var on = b.getAttribute('data-pref') === pref; b.classList.toggle('on', on); b.setAttribute('aria-pressed', String(on)); });
    note.textContent = ''; note.appendChild(document.createTextNode(NOTE[pref][0])); note.appendChild(el('strong', null, NOTE[pref][1])); note.appendChild(document.createTextNode(NOTE[pref][2]));
    renderButtons(pref);
  }
  [].slice.call(pills.querySelectorAll('.chip.pref')).forEach(function(b){ b.addEventListener('click', function(){ var p = b.getAttribute('data-pref'); safeSet(KEY, p); setPref(p); }); });
  setPref(safeGet(KEY) || 'google');

  /* Footer: venue, map, the league's own schedule. */
  var foot = el('footer');
  var pv = el('p', null, venue + ' \u00a0'); var map = el('a', null, 'Map \u2197'); map.href = 'https://www.google.com/maps/search/?api=1&query=' + enc(venue); map.target = '_blank'; map.rel = 'noopener noreferrer'; pv.appendChild(map); foot.appendChild(pv);
  var ps = el('p', null, 'Source: '); var src = el('a', null, team.source.label + ' \u2197'); src.href = team.source.url; src.target = '_blank'; src.rel = 'noopener noreferrer'; ps.appendChild(src);
  ps.appendChild(document.createTextNode(' (' + team.source.tab + ' tab, as of ' + team.source.retrieved + ').')); foot.appendChild(ps);
  body.appendChild(foot);

  /* Past games hidden until asked; a finished season shows everything. */
  function isPast(r){ return ymd(r.getAttribute('data-date')) < today; }
  var allPast = rows.every(isPast);
  function apply(){
    var past = cb.checked || allPast, any = false;
    rows.forEach(function(r){ var hide = !past && isPast(r); r.hidden = hide; if (!hide) any = true; });
    monthRows.forEach(function(mr){
      var k = mr.getAttribute('data-month'), vis = rows.some(function(r){ return !r.hidden && r.getAttribute('data-month') === k; });
      mr.hidden = !vis; jumps.forEach(function(j){ if (j.getAttribute('data-jump') === k) j.hidden = !vis; });
    });
    empty.hidden = any; hint();
  }
  function jump(id){
    var t = document.getElementById(id); if (!t) return;
    var top = t.getBoundingClientRect().top - wrap.getBoundingClientRect().top - wrap.clientTop + wrap.scrollTop - bar.offsetHeight - 2;
    try { wrap.scrollTo({top: Math.max(0, top), behavior: 'smooth'}); } catch(e) { wrap.scrollTop = Math.max(0, top); }
  }
  jumps.forEach(function(j){ j.addEventListener('click', function(){ jump(j.getAttribute('data-jump')); }); });
  cb.addEventListener('change', apply);

  /* Scroll affordance: Sites lays the iframe out late, so re-check after load and on resize. */
  var h = document.getElementById('hint'), f = document.getElementById('fade');
  function hint(){ var more = wrap.scrollHeight - wrap.clientHeight - wrap.scrollTop > 8; h.hidden = !more; f.hidden = !more; }
  wrap.addEventListener('scroll', hint, {passive: true});
  window.addEventListener('resize', hint);
  if (window.ResizeObserver) new ResizeObserver(hint).observe(wrap);
  apply(); setTimeout(hint, 120); setTimeout(hint, 600);
})();
</script>
</body>
</html>
"""


def build(teams, version):
    page = (PAGE.replace("{{VERSION}}", version)
                .replace("{{CLASS_JS}}", classinfo.class_js())
                .replace("{{LANG_JS}}", classinfo.lang_js())
                .replace("{{TEAMS}}", json.dumps(teams, ensure_ascii=False).replace("</", "<\\/")))
    assert "{{" not in page, "unfilled placeholder"
    return page


def main():
    teams, version = load_all()
    OUT.mkdir(parents=True, exist_ok=True)
    page = build(teams, version)
    (OUT / "index.html").write_text(page)
    summary = ", ".join(f"{k} ({sum(1 for g in t['games'] if not g.get('no_game'))} games)" for k, t in teams.items())
    print(f"team-schedule@{version}: {summary} -> {OUT / 'index.html'} ({len(page)} bytes)")


if __name__ == "__main__":
    main()
