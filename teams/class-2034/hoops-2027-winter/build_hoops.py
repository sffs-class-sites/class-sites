#!/usr/bin/env python3
"""Build the 1st-grade basketball schedule embed from 1st-hoops-data.json.

One-off (not in the class-sites repo). Adapted from the repo's Important Dates
build so it looks and behaves the same, with these differences:
- Timed one-hour events (Important Dates is all-day only), written in UTC.
- Every calendar event carries the venue as its location.
- Rows are games (date / time / opponent / Home-Away / court); no category filter.
- A "No game this week" row with no add button.
- UID = <date>-super-friends@sffs-1st-hoops, so a time change never duplicates.
Delivered as paste-in embed code: re-paste into Sites after any data change.
"""
import datetime as dt
import hashlib
import html
import json
import pathlib
import sys
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "1st-hoops-data.json"
OUT = HERE / "1st-hoops-embed.html"

MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MON_LONG = ["January", "February", "March", "April", "May", "June", "July",
            "August", "September", "October", "November", "December"]
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DST_START_2027 = dt.date(2027, 3, 14)


def q(v):
    return urllib.parse.quote(v, safe="-_.!~*'()")


def ics_escape(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def clock(t):
    h, m = map(int, t.split(":"))
    return f"{(h - 1) % 12 + 1}:{m:02d} {'AM' if h < 12 else 'PM'}"


def build(data):
    off = dt.timedelta(hours=data["utc_offset_hours"])
    dur = dt.timedelta(minutes=data["duration_minutes"])
    venue = f'{data["venue"]["name"]}, {data["venue"]["address"]}'
    maps = "https://www.google.com/maps/search/?api=1&query=" + q(venue)
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    version = f'{data["source"]["retrieved"]}.{hashlib.sha256(raw).hexdigest()[:8]}'

    rows, months, ics, meta = [], [], [], []
    for e in sorted(data["games"], key=lambda g: g["date"]):
        day = dt.date.fromisoformat(e["date"])
        assert day < DST_START_2027, f"{day} is after DST starts; fix the UTC offset"
        mkey = f"m-{day.year}-{day.month:02d}"
        if mkey not in months:
            months.append(mkey)
            rows.append(f'<tr class="month-row" id="{mkey}" data-month="{mkey}">'
                        f'<td colspan="4">{MON_LONG[day.month-1]} {day.year}</td></tr>')
        label = f"{DOW[day.weekday()]}, {MON[day.month-1]} {day.day}"

        if e.get("no_game"):
            rows.append(f'<tr class="ev off" data-date="{e["date"]}" data-month="{mkey}">'
                        f'<td class="date-cell">{label}</td><td class="time-cell">&nbsp;</td>'
                        f'<td class="what-cell"><div class="event-title">No game this week</div></td>'
                        f'<td class="action-cell"></td></tr>')
            continue

        i = len(meta)
        start_local = dt.datetime.combine(day, dt.time.fromisoformat(e["time"]))
        s_utc, e_utc = start_local - off, start_local - off + dur
        title = f'{data["team"]} vs. {e["opponent"]} {data["event_suffix"]}'
        details = f'{e["home_away"]} game, {e["court"]}. {venue}'
        uid = f'{e["date"]}-super-friends@sffs-1st-hoops'
        z = "%Y%m%dT%H%M%SZ"
        ics.append("\r\n".join([
            "BEGIN:VEVENT", f"UID:{uid}", "DTSTAMP:20261029T000000Z",
            f"DTSTART:{s_utc:{z}}", f"DTEND:{e_utc:{z}}",
            f"SUMMARY:{ics_escape(title)}", f"DESCRIPTION:{ics_escape(details)}",
            f"LOCATION:{ics_escape(venue)}", "END:VEVENT"]))
        meta.append({
            "t": title,
            "f": f'{e["date"]}-super-friends.ics',
            "g": ("https://calendar.google.com/calendar/render?action=TEMPLATE"
                  f"&text={q(title)}&dates={s_utc:{z}}/{e_utc:{z}}"
                  f"&details={q(details)}&location={q(venue)}"),
            "o": ("https://outlook.live.com/calendar/0/deeplink/compose?path=/calendar/action/compose&rru=addevent"
                  f"&startdt={q(s_utc.strftime('%Y-%m-%dT%H:%M:%SZ'))}&enddt={q(e_utc.strftime('%Y-%m-%dT%H:%M:%SZ'))}"
                  f"&subject={q(title)}&body={q(details)}&location={q(venue)}"),
        })
        ha = e["home_away"].lower()
        rows.append(
            f'<tr class="ev game" data-i="{i}" data-date="{e["date"]}" data-month="{mkey}">'
            f'<td class="date-cell">{label}</td>'
            f'<td class="time-cell">{clock(e["time"])}</td>'
            f'<td class="what-cell"><div class="event-title">vs. {html.escape(e["opponent"])}</div>'
            f'<div class="event-details"><span class="badge {ha}">{html.escape(e["home_away"])}</span> {html.escape(e["court"])}</div></td>'
            f'<td class="action-cell"></td></tr>')

    jumps = "".join(f'<button type="button" class="chip jump" data-jump="{m}">{MON[int(m[-2:])-1]}</button>'
                    for m in months)
    page = TEMPLATE
    for k, v in {
        "{{ID}}": data["id"], "{{VERSION}}": version,
        "{{TITLE}}": html.escape(data["title"]), "{{SUBTITLE}}": html.escape(data["subtitle"]),
        "{{VENUE_NAME}}": html.escape(data["venue"]["name"]),
        "{{VENUE_ADDR}}": html.escape(data["venue"]["address"]),
        "{{MAPS_URL}}": html.escape(maps),
        "{{SOURCE_URL}}": html.escape(data["source"]["url"]),
        "{{SOURCE_LABEL}}": html.escape(data["source"]["label"]),
        "{{MONTH_BUTTONS}}": jumps, "{{ROWS}}": "\n".join(rows),
        "{{ICS_EVENTS_JSON}}": json.dumps(ics).replace("</", "<\\/"),
        "{{META_JSON}}": json.dumps(meta, ensure_ascii=False).replace("</", "<\\/"),
    }.items():
        page = page.replace(k, v)
    assert "{{" not in page, "unfilled placeholder"
    return page, version, len(meta)


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="sffs-embed" content="{{ID}}@{{VERSION}}">
<meta name="robots" content="noindex">
<title>{{TITLE}}</title>
<style>
:root{
  --ink:#1f2937;--sub:#5b6472;--line:#e2e5ea;--bg:#fff;--panel:#f7f8fa;
  --accent:#3457a6;--accent-light:#eaeffb;
  --home:#1a7f5a;--home-bg:#e7f6ef;--away:#2166b0;--away-bg:#e8f1fb;
  --today-bg:#fff6d8;--today-border:#e3c22b;
}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg);line-height:1.45}
.wrap{height:100%;overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;border:2px solid #d6dff5;border-radius:12px;padding:16px}
header{margin-bottom:10px}
h1{font-size:1.35rem;margin:0 0 4px}
.subtitle{margin:0 0 4px;color:var(--sub);font-size:.9rem}
.venue{margin:0 0 10px;font-size:.9rem}
.venue a{color:var(--accent);font-weight:600}
.header-actions{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.btn,.source-link{display:inline-flex;align-items:center;gap:6px;font-family:inherit;font-weight:600;font-size:.82rem;line-height:1;padding:8px 12px;border-radius:999px;border:1px solid var(--line);background:#fff;color:var(--accent);text-decoration:none;cursor:pointer}
.btn:hover,.source-link:hover{background:var(--accent-light)}
.toolbar{position:sticky;top:-16px;z-index:5;background:#fff;margin:0 -16px;padding:10px 16px 8px;border-bottom:1px solid var(--line)}
.row{display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;padding-bottom:2px;align-items:center}
.row::-webkit-scrollbar{display:none}
.chip{flex:0 0 auto;font-family:inherit;font-weight:600;font-size:.8rem;line-height:1;padding:7px 11px;border-radius:999px;border:1px solid var(--line);background:var(--panel);color:var(--ink);cursor:pointer;display:inline-flex;align-items:center;gap:6px}
.chip:hover{background:var(--accent-light)}
.chip.on,.chip.pref.on{background:var(--accent);border-color:var(--accent);color:#fff}
.chip:focus-visible,.btn:focus-visible,.add:focus-visible,.source-link:focus-visible,.venue a:focus-visible{outline:3px solid #f0a055;outline-offset:2px}
.chip[hidden]{display:none}
.toggle{font-size:.8rem;color:var(--sub);display:inline-flex;align-items:center;gap:6px;margin-left:auto;white-space:nowrap}
table{width:100%;border-collapse:collapse;margin-top:6px}
td{padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:top;font-size:.9rem}
.month-row td{background:var(--panel);font-weight:700;color:var(--accent);padding:7px 8px;scroll-margin-top:96px}
.date-cell,.time-cell{white-space:nowrap;font-weight:700;width:1%}
.time-cell{font-weight:600}
.badge{display:inline-block;font-weight:700;font-size:.72rem;line-height:1;padding:4px 7px;border-radius:999px;white-space:nowrap;margin-right:4px}
.badge.home{color:var(--home);background:var(--home-bg)}.badge.away{color:var(--away);background:var(--away-bg)}
.event-title{font-weight:600}
.event-details{color:var(--sub);font-size:.84rem;margin-top:2px}
tr.off td{color:var(--sub)}
tr.off .event-title{font-weight:500;font-style:italic}
.next-flag{display:inline-block;margin-left:8px;font-size:.64rem;font-weight:800;letter-spacing:.04em;color:#fff;background:var(--accent);border-radius:999px;padding:3px 7px;vertical-align:2px}
.addall-note{margin:8px 0 0;color:var(--sub);font-size:.8rem}
.pref-row{margin-top:10px;padding:10px 12px;background:var(--panel);border:1px solid var(--line);border-radius:12px}
.pref-label{margin:0 0 8px;font-size:.84rem;font-weight:600}
.pref-pills{display:flex;flex-wrap:wrap;gap:6px}
.pref-hint{display:block;margin-top:6px;font-size:.75rem;color:var(--sub)}
.action-cell{white-space:nowrap;text-align:right;width:1%}
.add{font-family:inherit;font-weight:600;font-size:.75rem;line-height:1;padding:6px 9px;border-radius:8px;border:1px solid var(--line);background:#fff;color:var(--accent);text-decoration:none;cursor:pointer;display:inline-block;margin-left:4px}
.add:hover{background:var(--accent-light)}
tr.today td{background:var(--today-bg)}
tr.today td:first-child{box-shadow:inset 4px 0 0 var(--today-border)}
tr[hidden]{display:none}
.empty{padding:18px;text-align:center;color:var(--sub)}
.sffs-fade{position:fixed;left:2px;right:2px;bottom:2px;height:58px;z-index:8;pointer-events:none;background:linear-gradient(to bottom,rgba(255,255,255,0),#fff 72%);border-radius:0 0 10px 10px}
.sffs-hint{position:fixed;left:50%;bottom:12px;transform:translateX(-50%);z-index:9;pointer-events:none;white-space:nowrap;font:600 12px/1 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#3457a6;background:#eaeffb;border:1px solid #d6dff5;padding:7px 13px;border-radius:999px;box-shadow:0 1px 5px rgba(0,0,0,.13)}
.sffs-fade[hidden],.sffs-hint[hidden]{display:none}
@media (max-width:560px){
  .wrap{padding:12px}
  .toolbar{top:-12px;margin:0 -12px;padding:8px 12px}
  h1{font-size:1.15rem}
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
@media print{html,body{height:auto}body{overflow:visible}.wrap{height:auto;overflow:visible;border:0}.toolbar,.action-cell,.header-actions,.pref-row,.addall-note,.sffs-fade,.sffs-hint{display:none}}
</style>
</head>
<body>
<div class="wrap" id="wrap">
  <header>
    <h1>{{TITLE}}</h1>
    <p class="subtitle">{{SUBTITLE}}</p>
    <p class="venue">{{VENUE_NAME}}, {{VENUE_ADDR}} &nbsp;<a href="{{MAPS_URL}}" target="_blank" rel="noopener noreferrer">Map ↗</a></p>
    <div class="header-actions">
      <a class="source-link" href="{{SOURCE_URL}}" target="_blank" rel="noopener noreferrer">{{SOURCE_LABEL}} ↗</a>
      <button type="button" class="btn" id="addall">Add all games to my calendar</button>
    </div>
    <p class="addall-note" id="addall-note"></p>
    <div class="pref-row">
      <p class="pref-label">Which calendar do you use? Each game below will get one matching "add" button.</p>
      <div class="pref-pills" role="group" aria-label="Your calendar">
        <button type="button" class="chip pref" data-pref="google" aria-pressed="false">Google Calendar</button>
        <button type="button" class="chip pref" data-pref="outlook" aria-pressed="false">Outlook</button>
        <button type="button" class="chip pref" data-pref="apple" aria-pressed="false">Apple Calendar</button>
      </div>
      <span class="pref-hint">Remembers your choice next time you visit this page.</span>
    </div>
  </header>
  <nav class="toolbar" id="toolbar" aria-label="Jump to month">
    <div class="row" role="group" aria-label="Jump to month">{{MONTH_BUTTONS}}
      <label class="toggle"><input type="checkbox" id="showpast"> Show past games</label>
    </div>
  </nav>
  <table><tbody id="cal-body">
{{ROWS}}
  </tbody></table>
  <p class="empty" id="empty" hidden>No games to show.</p>
</div>
<div class="sffs-fade" hidden></div>
<div class="sffs-hint" hidden>Scroll for more &#8595;</div>
<script>
(function(){
  var ICS = {{ICS_EVENTS_JSON}};
  var META = {{META_JSON}};
  var KEY = 'sffsCalendarPref', LABEL = {google: 'Google', outlook: 'Outlook', apple: 'Apple'};
  function safeGet(k){ try { return localStorage.getItem(k); } catch(e) { return null; } }
  function safeSet(k, v){ try { localStorage.setItem(k, v); } catch(e) {} }
  var w = document.getElementById('wrap');
  var bar = document.getElementById('toolbar');
  var rows = [].slice.call(document.querySelectorAll('tr.ev'));
  var games = rows.filter(function(r){ return r.classList.contains('game'); });
  var months = [].slice.call(document.querySelectorAll('tr.month-row'));
  var jumps = [].slice.call(document.querySelectorAll('.chip.jump'));
  var showPast = document.getElementById('showpast');
  var empty = document.getElementById('empty');

  function ymd(s){ var p = s.split('-'); return new Date(+p[0], +p[1]-1, +p[2]); }
  var today = new Date(); today.setHours(0,0,0,0);
  if (/[?&]today=\d{4}-\d{2}-\d{2}/.test(location.search)) { today = ymd(location.search.match(/today=(\d{4}-\d{2}-\d{2})/)[1]); }  // for tests
  function isPast(r){ return ymd(r.getAttribute('data-date')) < today; }
  var allPast = rows.every(isPast);  // season over: show everything rather than an empty box

  var upcoming = null;
  games.forEach(function(r){
    var a = ymd(r.getAttribute('data-date'));
    if (a.getTime() === today.getTime()) r.classList.add('today');
    if (!upcoming && a >= today) upcoming = r;
  });
  if (upcoming && !upcoming.classList.contains('today')) {
    var flag = document.createElement('span'); flag.className = 'next-flag'; flag.textContent = 'NEXT UP';
    upcoming.querySelector('.event-title').appendChild(flag);
  }

  function apply(){
    var past = showPast.checked || allPast, any = false;
    rows.forEach(function(r){ var hide = !past && isPast(r); r.hidden = hide; if (!hide) any = true; });
    months.forEach(function(m){
      var key = m.getAttribute('data-month');
      var vis = rows.some(function(r){ return !r.hidden && r.getAttribute('data-month') === key; });
      m.hidden = !vis;
      jumps.forEach(function(j){ if (j.getAttribute('data-jump') === key) j.hidden = !vis; });
    });
    empty.hidden = any;
    hint();
  }

  function jump(id){
    var t = document.getElementById(id); if (!t) return;
    var top = t.getBoundingClientRect().top - w.getBoundingClientRect().top - w.clientTop + w.scrollTop - bar.offsetHeight - 2;
    try { w.scrollTo({top: Math.max(0, top), behavior: 'smooth'}); } catch(e) { w.scrollTop = Math.max(0, top); }
  }
  jumps.forEach(function(j){ j.addEventListener('click', function(){ jump(j.getAttribute('data-jump')); }); });
  showPast.addEventListener('change', apply);

  function download(name, text){
    var blob = new Blob([text], {type: 'text/calendar;charset=utf-8'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click();
    setTimeout(function(){ URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }
  function wrapCal(list){
    return 'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//SFFS Class Page//1st Grade Hoops//EN\r\nCALSCALE:GREGORIAN\r\n' + list.join('\r\n') + '\r\nEND:VCALENDAR\r\n';
  }
  document.getElementById('addall').addEventListener('click', function(){
    download('Super-Friends-winter-2027-games.ics', wrapCal(ICS));
  });

  var NOTE = {
    google: 'Downloads a calendar file with every game. In Google Calendar, go to <strong>Settings &rarr; Import &amp; export &rarr; Import</strong> and choose the downloaded file to add them all at once.',
    outlook: 'Downloads a calendar file with every game. In Outlook, open the file (or use <strong>Import</strong> in your calendar settings) to add them all at once.',
    apple: 'Downloads a calendar file with every game. Open it and Apple Calendar will offer to add them all at once.'
  };
  function renderButtons(pref){
    games.forEach(function(r){
      var i = +r.getAttribute('data-i'), m = META[i], cell = r.querySelector('.action-cell'), el;
      cell.textContent = '';
      if (pref === 'apple') {
        el = document.createElement('button'); el.type = 'button';
        el.addEventListener('click', function(){ download(m.f, wrapCal([ICS[i]])); });
      } else {
        el = document.createElement('a'); el.href = pref === 'outlook' ? m.o : m.g;
        el.target = '_blank'; el.rel = 'noopener noreferrer';
      }
      el.className = 'add cal-btn';
      el.textContent = '+ ' + LABEL[pref];
      el.setAttribute('aria-label', 'Add ' + m.t + ' to ' + LABEL[pref] + (pref === 'apple' ? ' Calendar' : ''));
      cell.appendChild(el);
    });
  }
  function setPref(pref){
    if (!LABEL[pref]) pref = 'google';
    [].slice.call(document.querySelectorAll('.chip.pref')).forEach(function(b){
      var on = b.getAttribute('data-pref') === pref; b.classList.toggle('on', on); b.setAttribute('aria-pressed', on);
    });
    document.getElementById('addall-note').innerHTML = NOTE[pref];
    renderButtons(pref);
  }
  [].slice.call(document.querySelectorAll('.chip.pref')).forEach(function(b){
    b.addEventListener('click', function(){ var p = b.getAttribute('data-pref'); safeSet(KEY, p); setPref(p); });
  });
  setPref(safeGet(KEY) || 'google');

  var h = document.querySelector('.sffs-hint'), f = document.querySelector('.sffs-fade');
  function hint(){ var more = w.scrollHeight - w.clientHeight - w.scrollTop > 8; h.hidden = !more; f.hidden = !more; }
  w.addEventListener('scroll', hint, {passive: true});
  window.addEventListener('resize', hint);
  if (window.ResizeObserver) new ResizeObserver(hint).observe(w);

  apply();
})();
</script>
</body>
</html>
"""


def main():
    data = json.loads(SRC.read_text())
    page, version, n = build(data)
    OUT.write_text(page)
    print(f"1st-hoops@{version}: {n} games -> {OUT} ({len(page)} bytes)")


if __name__ == "__main__":
    sys.exit(main())
