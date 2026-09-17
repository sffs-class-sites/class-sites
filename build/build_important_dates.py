#!/usr/bin/env python3
"""Build the Important Dates embed page from shared/important-dates/data.json.

Output: _site/shared/important-dates/index.html (+ data.json, events.ics)

Design rules (see docs/architecture.md §7 and the Google Sites playbook):
- Served by GitHub Pages and embedded BY URL in every class Google Site.
- Fills whatever box Sites gives it: one scroll region, scroll hint on phones.
- Interactive controls are <button>s + JS. No href="#..." anywhere.
- Outbound links open in a new tab (Sites' sandbox blocks top-level navigation).
- A <meta name="sffs-embed"> marker carries id@version for the monitor.
"""
import datetime as dt
import hashlib
import html
import json
import pathlib
import re
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "shared" / "important-dates" / "data.json"
OUT = ROOT / "_site" / "shared" / "important-dates"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]
CAT_ORDER = ["noschool", "break", "early", "event", "info"]


def d(s):
    return dt.date.fromisoformat(s)


def fmt_range(e):
    a = d(e["date"])
    if not e.get("end"):
        return f"{MONTHS[a.month-1]} {a.day}"
    b = d(e["end"])
    if a.month == b.month:
        return f"{MONTHS[a.month-1]} {a.day}–{b.day}"
    return f"{MONTHS[a.month-1]} {a.day} – {MONTHS[b.month-1]} {b.day}"


def q(v):
    """encodeURIComponent equivalent."""
    return urllib.parse.quote(v, safe="-_.!~*'()")


def full_details(e):
    b, t = e.get("badge") or "", e.get("details") or ""
    return f"{b}. {t}" if b and t else (b or t)


def span(e):
    a = d(e["date"])
    b = d(e.get("end") or e["date"]) + dt.timedelta(days=1)  # all-day end is exclusive
    return a, b


def gcal_url(e):
    a, b = span(e)
    return ("https://calendar.google.com/calendar/render?action=TEMPLATE"
            f"&text={q(e['title'])}&dates={a:%Y%m%d}/{b:%Y%m%d}&details={q(full_details(e))}&location={q('SFFS')}")


def outlook_url(e):
    a, b = span(e)
    return ("https://outlook.live.com/calendar/0/deeplink/compose?path=/calendar/action/compose&rru=addevent"
            f"&startdt={q(a.isoformat() + 'T00:00:00')}&enddt={q(b.isoformat() + 'T00:00:00')}"
            f"&subject={q(e['title'])}&body={q(full_details(e))}&location={q('SFFS')}&allday=true")


def slugify(text):
    """Same as the live embed, so UIDs match and re-importing never duplicates events."""
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", (text or "").lower()))[:40] or "event"


def ics_escape(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def ics_event(e, uid):
    a, b = span(e)
    lines = ["BEGIN:VEVENT", f"UID:{uid}", "DTSTAMP:20260101T000000Z",
             f"DTSTART;VALUE=DATE:{a:%Y%m%d}", f"DTEND;VALUE=DATE:{b:%Y%m%d}",
             f"SUMMARY:{ics_escape(e['title'])}"]
    if full_details(e):
        lines.append(f"DESCRIPTION:{ics_escape(full_details(e))}")
    lines.append("END:VEVENT")
    return "\r\n".join(lines)


def ics_calendar(vevents):
    return ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//SFFS Class Page//Important Dates//EN\r\n"
            "CALSCALE:GREGORIAN\r\n" + "\r\n".join(vevents) + "\r\nEND:VCALENDAR\r\n")


def build(data):
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    version = f"{data['source']['revised']}.{hashlib.sha256(raw).hexdigest()[:8]}"
    events = sorted(data["events"], key=lambda e: e["date"])
    seen, vevents, metas = {}, [], []

    rows, months_seen = [], []
    for i, e in enumerate(events):
        a = d(e["date"])
        mkey = f"m-{a.year}-{a.month:02d}"
        if mkey not in months_seen:
            months_seen.append(mkey)
            rows.append(f'<tr class="month-row" id="{mkey}" data-month="{mkey}">'
                        f'<td colspan="4">{MONTHS_LONG[a.month-1]} {a.year}</td></tr>')
        base = f"{e['date']}-{slugify(e['title'])}"
        seen[base] = seen.get(base, 0) + 1
        uid = (base + (f"-{seen[base]}" if seen[base] > 1 else "")) + "@sffs-calendar"
        vevents.append(ics_event(e, uid))
        metas.append({"g": gcal_url(e), "o": outlook_url(e), "f": f"{e['date']}-{slugify(e['title'])}.ics", "t": e["title"]})
        cat = e["cat"]
        star = ' <span class="star" title="{0}" aria-label="{0}">*</span>'.format(html.escape(data["star_note"])) if e.get("star") else ""
        details = f'<div class="event-details">{html.escape(e["details"])}</div>' if e.get("details") else ""
        end_attr = f' data-date-end="{e["end"]}"' if e.get("end") else ""
        rows.append(
            f'<tr class="ev" data-i="{i}" data-date="{e["date"]}"{end_attr} data-cat="{cat}" data-month="{mkey}">'
            f'<td class="date-cell">{fmt_range(e)}</td>'
            f'<td class="badge-cell"><span class="badge {cat}">{html.escape(e.get("badge") or data["categories"][cat])}</span></td>'
            f'<td class="what-cell"><div class="event-title">{html.escape(e["title"])}{star}</div>{details}</td>'
            f'<td class="action-cell"></td></tr>'
        )

    month_btns = "".join(
        f'<button type="button" class="chip jump" data-jump="{m}">{MONTHS[int(m[-2:])-1]}</button>'
        for m in months_seen)
    cat_btns = '<button type="button" class="chip cat on" data-cat="all" aria-pressed="true">All</button>' + "".join(
        f'<button type="button" class="chip cat" data-cat="{c}" aria-pressed="false"><span class="dot {c}"></span>{html.escape(data["categories"][c])}</button>'
        for c in CAT_ORDER if any(e["cat"] == c for e in events))
    footer = "".join(f"<p>{html.escape(p)}</p>" for p in data["footer"])

    page = TEMPLATE
    for k, v in {
        "{{ID}}": data["id"],
        "{{VERSION}}": version,
        "{{TITLE}}": html.escape(data["title"]),
        "{{SUBTITLE}}": html.escape(data["subtitle"]),
        "{{SOURCE_URL}}": html.escape(data["source"]["url"]),
        "{{SOURCE_LABEL}}": html.escape(data["source"]["label"]),
        "{{STAR_NOTE}}": html.escape(data["star_note"]),
        "{{MONTH_BUTTONS}}": month_btns,
        "{{CAT_BUTTONS}}": cat_btns,
        "{{ROWS}}": "\n".join(rows),
        "{{FOOTER}}": footer,
        "{{ICS_EVENTS_JSON}}": json.dumps(vevents).replace("</", "<\\/"),
        "{{META_JSON}}": json.dumps(metas, ensure_ascii=False).replace("</", "<\\/"),
        "{{YEAR}}": data["title"].split()[1],
    }.items():
        page = page.replace(k, v)
    return page, ics_calendar(vevents), version


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
  --noschool:#c0392b;--noschool-bg:#fdecea;--break:#7a4fb5;--break-bg:#f2ebfa;
  --early:#b4720a;--early-bg:#fdf3e0;--event:#1a7f5a;--event-bg:#e7f6ef;
  --info:#2166b0;--info-bg:#e8f1fb;--today-bg:#fff6d8;--today-border:#e3c22b;
}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg);line-height:1.45}
.wrap{height:100%;overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;border:2px solid #d6dff5;border-radius:12px;padding:16px 16px 16px}
header{margin-bottom:10px}
h1{font-size:1.35rem;margin:0 0 4px}
.subtitle{margin:0 0 10px;color:var(--sub);font-size:.9rem}
.header-actions{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.btn,.source-link{display:inline-flex;align-items:center;gap:6px;font-family:inherit;font-weight:600;font-size:.82rem;line-height:1;padding:8px 12px;border-radius:999px;border:1px solid var(--line);background:#fff;color:var(--accent);text-decoration:none;cursor:pointer}
.btn:hover,.source-link:hover{background:var(--accent-light)}
.toolbar{position:sticky;top:-16px;z-index:5;background:#fff;margin:0 -16px;padding:10px 16px 8px;border-bottom:1px solid var(--line)}
.row{display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;padding-bottom:2px}
.row::-webkit-scrollbar{display:none}
.row+.row{margin-top:6px}
.chip{flex:0 0 auto;font-family:inherit;font-weight:600;font-size:.8rem;line-height:1;padding:7px 11px;border-radius:999px;border:1px solid var(--line);background:var(--panel);color:var(--ink);cursor:pointer;display:inline-flex;align-items:center;gap:6px}
.chip:hover{background:var(--accent-light)}
.chip.on,.chip.pref.on{background:var(--accent);border-color:var(--accent);color:#fff}
.chip:focus-visible,.btn:focus-visible,.add:focus-visible{outline:3px solid #f0a055;outline-offset:2px}
.chip[hidden]{display:none}
.toggle{font-size:.8rem;color:var(--sub);display:inline-flex;align-items:center;gap:6px;margin-left:auto;white-space:nowrap}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block}
.dot.noschool{background:var(--noschool)}.dot.break{background:var(--break)}.dot.early{background:var(--early)}.dot.event{background:var(--event)}.dot.info{background:var(--info)}
table{width:100%;border-collapse:collapse;margin-top:6px}
td{padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:top;font-size:.9rem}
.month-row td{background:var(--panel);font-weight:700;color:var(--accent);padding:7px 8px;scroll-margin-top:96px}
.date-cell{white-space:nowrap;font-weight:700;width:1%}
.badge{display:inline-block;font-family:inherit;font-weight:700;font-size:.72rem;line-height:1;padding:5px 8px;border-radius:999px;white-space:nowrap}
.badge.noschool{color:var(--noschool);background:var(--noschool-bg)}.badge.break{color:var(--break);background:var(--break-bg)}
.badge.early{color:var(--early);background:var(--early-bg)}.badge.event{color:var(--event);background:var(--event-bg)}.badge.info{color:var(--info);background:var(--info-bg)}
.event-title{font-weight:600}
.next-flag{display:inline-block;margin-left:8px;font-size:.64rem;font-weight:800;letter-spacing:.04em;color:#fff;background:var(--accent);border-radius:999px;padding:3px 7px;vertical-align:2px}
.addall-note{margin:8px 0 0;color:var(--sub);font-size:.8rem}
.pref-row{margin-top:10px;padding:10px 12px;background:var(--panel);border:1px solid var(--line);border-radius:12px}
.pref-label{margin:0 0 8px;font-size:.84rem;font-weight:600}
.pref-pills{display:flex;flex-wrap:wrap;gap:6px}
.pref-hint{display:block;margin-top:6px;font-size:.75rem;color:var(--sub)}
.event-details{color:var(--sub);font-size:.84rem}
.star{color:var(--early);font-weight:700;cursor:help}
.action-cell{white-space:nowrap;text-align:right;width:1%}
.add{font-family:inherit;font-weight:600;font-size:.75rem;line-height:1;padding:6px 9px;border-radius:8px;border:1px solid var(--line);background:#fff;color:var(--accent);text-decoration:none;cursor:pointer;display:inline-block;margin-left:4px}
.add:hover{background:var(--accent-light)}
tr.today td{background:var(--today-bg)}
tr.today td:first-child{box-shadow:inset 4px 0 0 var(--today-border)}
tr[hidden]{display:none}
.empty{padding:18px;text-align:center;color:var(--sub)}
footer{margin-top:14px;color:var(--sub);font-size:.8rem}
footer p{margin:4px 0}
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
  .badge-cell{grid-column:2;text-align:right}
  .what-cell{grid-column:1/3}
  .action-cell{grid-column:1/3;text-align:left}
  .add{margin:2px 6px 0 0}
  .toggle{margin-left:0}
}
@media print{html,body{height:auto}body{overflow:visible}.wrap{height:auto;overflow:visible;border:0}.toolbar,.action-cell,.header-actions,.sffs-fade,.sffs-hint{display:none}}
</style>
</head>
<body>
<div class="wrap" id="wrap">
  <header>
    <h1>{{TITLE}}</h1>
    <p class="subtitle">{{SUBTITLE}}</p>
    <div class="header-actions">
      <a class="source-link" href="{{SOURCE_URL}}" target="_blank" rel="noopener noreferrer">{{SOURCE_LABEL}} ↗</a>
      <button type="button" class="btn" id="addall">Add all dates to my calendar</button>
    </div>
    <p class="addall-note" id="addall-note"></p>
    <div class="pref-row">
      <p class="pref-label">Which calendar do you use? Each date below will get one matching "add" button.</p>
      <div class="pref-pills" role="group" aria-label="Your calendar">
        <button type="button" class="chip pref" data-pref="google" aria-pressed="false">Google Calendar</button>
        <button type="button" class="chip pref" data-pref="outlook" aria-pressed="false">Outlook</button>
        <button type="button" class="chip pref" data-pref="apple" aria-pressed="false">Apple Calendar</button>
      </div>
      <span class="pref-hint">Remembers your choice next time you visit this page.</span>
    </div>
  </header>
  <nav class="toolbar" id="toolbar" aria-label="Filter dates">
    <div class="row" role="group" aria-label="Show">{{CAT_BUTTONS}}
      <label class="toggle"><input type="checkbox" id="showpast"> Show past dates</label>
    </div>
    <div class="row" role="group" aria-label="Jump to month">{{MONTH_BUTTONS}}</div>
  </nav>
  <table><tbody id="cal-body">
{{ROWS}}
  </tbody></table>
  <p class="empty" id="empty" hidden>Nothing matches this filter.</p>
  <footer>
    {{FOOTER}}
  </footer>
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
  var months = [].slice.call(document.querySelectorAll('tr.month-row'));
  var jumps = [].slice.call(document.querySelectorAll('.chip.jump'));
  var cats = [].slice.call(document.querySelectorAll('.chip.cat'));
  var showPast = document.getElementById('showpast');
  var empty = document.getElementById('empty');
  var state = {cat: 'all'};

  function ymd(s){ var p = s.split('-'); return new Date(+p[0], +p[1]-1, +p[2]); }
  var today = new Date(); today.setHours(0,0,0,0);
  if (/[?&]today=\d{4}-\d{2}-\d{2}/.test(location.search)) { today = ymd(location.search.match(/today=(\d{4}-\d{2}-\d{2})/)[1]); }  // for tests
  function isPast(r){ return ymd(r.getAttribute('data-date-end') || r.getAttribute('data-date')) < today; }
  var allPast = rows.every(isPast);  // year over or stale calendar: never render empty

  var upcoming = null;
  rows.forEach(function(r){
    var a = ymd(r.getAttribute('data-date')), b = ymd(r.getAttribute('data-date-end') || r.getAttribute('data-date'));
    if (a <= today && today <= b) r.classList.add('today');
    if (!upcoming && b >= today) upcoming = r;
  });
  if (upcoming && !upcoming.classList.contains('today')) {
    var flag = document.createElement('span'); flag.className = 'next-flag'; flag.textContent = 'NEXT UP';
    upcoming.querySelector('.event-title').appendChild(flag);
  }

  function apply(){
    var past = showPast.checked || allPast, any = false;
    rows.forEach(function(r){
      var hide = (!past && isPast(r)) || (state.cat !== 'all' && r.getAttribute('data-cat') !== state.cat);
      r.hidden = hide; if (!hide) any = true;
    });
    months.forEach(function(m){
      var key = m.getAttribute('data-month');
      var vis = rows.some(function(r){ return !r.hidden && r.getAttribute('data-month') === key; });
      m.hidden = !vis;
      jumps.forEach(function(j){ if (j.getAttribute('data-jump') === key) j.hidden = !vis; });
    });
    empty.hidden = any;
    cats.forEach(function(c){ var on = c.getAttribute('data-cat') === state.cat; c.classList.toggle('on', on); c.setAttribute('aria-pressed', on); });
    hint();
  }

  function jump(id){
    var t = document.getElementById(id); if (!t) return;
    var top = t.getBoundingClientRect().top - w.getBoundingClientRect().top - w.clientTop + w.scrollTop - bar.offsetHeight - 2;  // land just under the stuck filter bar
    try { w.scrollTo({top: Math.max(0, top), behavior: 'smooth'}); } catch(e) { w.scrollTop = Math.max(0, top); }
  }

  cats.forEach(function(c){ c.addEventListener('click', function(){ state.cat = c.getAttribute('data-cat'); apply(); }); });
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
    return 'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//SFFS Class Page//Important Dates//EN\r\nCALSCALE:GREGORIAN\r\n' + list.join('\r\n') + '\r\nEND:VCALENDAR\r\n';
  }
  document.getElementById('addall').addEventListener('click', function(){
    download('SFFS-{{YEAR}}-important-dates.ics', wrapCal(ICS));
  });

  var NOTE = {
    google: 'Downloads a calendar file with every date below. In Google Calendar, go to <strong>Settings &rarr; Import &amp; export &rarr; Import</strong> and choose the downloaded file to add them all at once.',
    outlook: 'Downloads a calendar file with every date below. In Outlook, open the file (or use <strong>Import</strong> in your calendar settings) to add them all at once.',
    apple: 'Downloads a calendar file with every date below. Open it and Apple Calendar will offer to add them all at once.'
  };
  function renderButtons(pref){
    rows.forEach(function(r){
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

  /* Open with the filter bar at the top. Sites lays the frame out late, so retry; stop if the reader acts first. */
  var done = false, touched = false;
  ['wheel','touchstart','keydown','mousedown'].forEach(function(ev){ window.addEventListener(ev, function(){ touched = true; }, {passive: true}); });
  function start(){
    if (done || touched) return;
    if (w.clientHeight < 40 || w.scrollHeight <= w.clientHeight + 8) return;
    var top = bar.getBoundingClientRect().top - w.getBoundingClientRect().top - w.clientTop + w.scrollTop; if (top <= 0) { done = true; return; }
    w.scrollTop = top; if (w.scrollTop > 0) done = true;
  }
  [0,120,350,700,1200,2000,3000].forEach(function(ms){ setTimeout(start, ms); });
  window.addEventListener('load', start);
  if (window.ResizeObserver) new ResizeObserver(start).observe(w);
})();
</script>
</body>
</html>
"""


def main():
    data = json.loads(SRC.read_text())
    page, ics, version = build(data)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(page)
    (OUT / "events.ics").write_text(ics)
    (OUT / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"important-dates@{version}: {len(data['events'])} events -> {OUT / 'index.html'} ({len(page)} bytes)")


if __name__ == "__main__":
    sys.exit(main())
