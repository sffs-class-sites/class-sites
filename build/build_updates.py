#!/usr/bin/env python3
"""Build the Updates embed from shared/updates/data.json.

Output: _site/shared/updates/index.html (+ data.json)

The Updates embed shows what the school's emails said, organised by what a parent needs:
Action needed, This week, Coming up, What changed, Good to know, From the Head.
Everything is rendered client-side from the topic ledger so the same page serves every
class site: ?class=YYYY picks the grade (CLAUDE.md §1), ?grade=N overrides it, and a
family with children in several grades can tick extra grades (remembered in the browser).

Rules shared with the other embeds (CLAUDE.md §5): fills its frame, one scroll region,
scroll-hint pill, <button>s not href="#", outbound links open a new tab, a
<meta name="sffs-embed"> marker carries id@version for the monitor.

Personal data: the ledger carries no parent names, addresses, phone numbers or personal
emails (tests/validate_updates.py enforces this). Those stay in the full-text log docs.
"""
import hashlib
import html
import json
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import classinfo  # the shared class and grade model (shared/class/class.js)

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "shared" / "updates" / "data.json"
OUT = ROOT / "_site" / "shared" / "updates"


def build(data):
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    version = f"{data['built_through']}.{hashlib.sha256(raw).hexdigest()[:8]}"
    page = TEMPLATE
    for k, v in {
        "{{ID}}": data["id"],
        "{{VERSION}}": version,
        "{{TITLE}}": html.escape(data["title"]),
        "{{SUBTITLE}}": html.escape(data["subtitle"]),
        "{{DATA_JSON}}": json.dumps(data, ensure_ascii=False).replace("</", "<\\/"),
        "{{CLASS_JS}}": classinfo.class_js(),
    }.items():
        page = page.replace(k, v)
    return page, version


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
  --due:#c0392b;--due-bg:#fdecea;--event:#1a7f5a;--event-bg:#e7f6ef;
  --notice:#2166b0;--notice-bg:#e8f1fb;--vol:#7a4fb5;--vol-bg:#f2ebfa;--letter:#b4720a;--letter-bg:#fdf3e0;
  --new:#b4720a;--new-bg:#fff6d8;
}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg);line-height:1.45}
.wrap{height:100%;overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;border:2px solid #d6dff5;border-radius:12px;padding:16px}
header{margin-bottom:8px}
h1{font-size:1.35rem;margin:0 0 2px}
.subtitle{margin:0 0 8px;color:var(--sub);font-size:.9rem}
.showing{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:.82rem;color:var(--sub)}
.chip.tiny{padding:5px 9px;font-size:.74rem;background:#fff}
.grades{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:.8rem;color:var(--sub);margin-top:6px}
.grades[hidden]{display:none}
.grades .lbl{margin-right:2px}
.chip{flex:0 0 auto;font-family:inherit;font-weight:600;font-size:.8rem;line-height:1;padding:7px 11px;border-radius:999px;border:1px solid var(--line);background:var(--panel);color:var(--ink);cursor:pointer;display:inline-flex;align-items:center;gap:6px}
.chip:hover{background:var(--accent-light)}
.chip.on{background:var(--accent);border-color:var(--accent);color:#fff}
.chip.g{padding:6px 9px;font-size:.76rem}
.chip[hidden]{display:none}
.chip:focus-visible,.btn:focus-visible,.lnk:focus-visible,summary:focus-visible{outline:3px solid #f0a055;outline-offset:2px}
.toolbar{position:sticky;top:-16px;z-index:5;background:#fff;margin:0 -16px;padding:8px 16px;border-bottom:1px solid var(--line)}
.row{display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;padding-bottom:2px}
.row::-webkit-scrollbar{display:none}
.tab .n{font-weight:800;font-size:.7rem;background:rgba(0,0,0,.08);border-radius:999px;padding:2px 6px}
.tab.on .n{background:rgba(255,255,255,.25)}
.intro{margin:10px 0 6px;color:var(--sub);font-size:.84rem}
.card{border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:8px 0;background:#fff}
.card.new{box-shadow:inset 4px 0 0 var(--new)}
.top{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:4px}
.badge{display:inline-block;font-weight:700;font-size:.7rem;line-height:1;padding:5px 8px;border-radius:999px;white-space:nowrap}
.badge.due{color:var(--due);background:var(--due-bg)}.badge.event{color:var(--event);background:var(--event-bg)}
.badge.notice{color:var(--notice);background:var(--notice-bg)}.badge.volunteer{color:var(--vol);background:var(--vol-bg)}
.badge.letter{color:var(--letter);background:var(--letter-bg)}.badge.aud{color:var(--sub);background:var(--panel)}
.badge.newb{color:var(--new);background:var(--new-bg)}.badge.official{color:var(--sub);background:var(--panel);font-weight:600}
.t{font-weight:700;font-size:1rem;margin:0}
.when{color:var(--ink);font-weight:600;font-size:.88rem;margin:2px 0}
.sum{margin:4px 0 6px;font-size:.9rem}
.acts{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.lnk,.btn{display:inline-flex;align-items:center;gap:5px;font-family:inherit;font-weight:600;font-size:.8rem;line-height:1;padding:7px 11px;border-radius:999px;border:1px solid var(--line);background:#fff;color:var(--accent);text-decoration:none;cursor:pointer}
.lnk:hover,.btn:hover{background:var(--accent-light)}
.lnk.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.lnk.primary:hover{background:#2a4788}
details{margin-top:6px;font-size:.82rem;color:var(--sub)}
summary{cursor:pointer;font-weight:600;color:var(--accent);list-style:none;display:inline-block;padding:2px 0}
summary::-webkit-details-marker{display:none}
summary::before{content:"▸ "}
details[open] summary::before{content:"▾ "}
.hist{margin:4px 0 0;padding-left:0;list-style:none}
.hist li{padding:2px 0;border-top:1px dashed var(--line)}
.hist .d{font-weight:700;color:var(--ink);white-space:nowrap}
.hist .s{color:var(--sub)}
.badge.classroom{color:#1a7f5a;background:#e7f6ef}
.items{margin:4px 0 6px;padding-left:20px;font-size:.9rem}
.items li{margin:2px 0}
h2.sec{font-size:.8rem;text-transform:uppercase;letter-spacing:.06em;color:var(--sub);margin:14px 0 2px}
.empty{padding:18px;text-align:center;color:var(--sub)}
footer{margin-top:14px;color:var(--sub);font-size:.78rem}
footer p{margin:4px 0}
.sffs-fade{position:fixed;left:2px;right:2px;bottom:2px;height:58px;z-index:8;pointer-events:none;background:linear-gradient(to bottom,rgba(255,255,255,0),#fff 72%);border-radius:0 0 10px 10px}
.sffs-hint{position:fixed;left:50%;bottom:12px;transform:translateX(-50%);z-index:9;pointer-events:none;white-space:nowrap;font:600 12px/1 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#3457a6;background:#eaeffb;border:1px solid #d6dff5;padding:7px 13px;border-radius:999px;box-shadow:0 1px 5px rgba(0,0,0,.13)}
.sffs-fade[hidden],.sffs-hint[hidden]{display:none}
@media (max-width:560px){
  .wrap{padding:12px}
  .toolbar{top:-12px;margin:0 -12px;padding:6px 12px}
  h1{font-size:1.05rem;margin:0}
  .subtitle{display:none}
  .showing{font-size:.76rem}
  header{margin-bottom:3px}
  .intro{display:none}  /* the tab name says it; the phone needs the room */
  .chip{padding:6px 10px;font-size:.78rem}
  .card{padding:8px 10px;margin:5px 0}
  .top{margin-bottom:2px;gap:4px}
  .badge{font-size:.66rem;padding:4px 7px}
  .t{font-size:.92rem;line-height:1.25}
  .when{font-size:.82rem;margin:2px 0}
  .sum{font-size:.82rem;margin:3px 0 4px;line-height:1.35}
  .items{font-size:.82rem;padding-left:16px}
  .acts{gap:4px;margin-top:4px}
  .lnk,.btn{font-size:.76rem;padding:6px 9px}
  details{margin-top:3px;font-size:.78rem}
  .toolbar{padding:5px 12px}
  .sffs-fade{height:30px}
  .sffs-hint{bottom:6px;padding:5px 11px;font-size:11px}
}
@media print{html,body{height:auto}body{overflow:visible}.wrap{height:auto;overflow:visible;border:0}.toolbar,.sffs-fade,.sffs-hint{display:none}}
</style>
</head>
<body>
<div class="wrap" id="wrap">
  <header>
    <h1>{{TITLE}}</h1>
    <p class="subtitle" id="subtitle">{{SUBTITLE}}</p>
    <div class="showing"><span id="showing"></span> <button type="button" class="chip tiny" id="gradesToggle" aria-expanded="false" aria-controls="grades">Change grades</button></div>
    <div class="grades" id="grades" role="group" aria-label="Which grades to show" hidden><span class="lbl">Show, as well as schoolwide:</span></div>
  </header>
  <nav class="toolbar" id="toolbar" aria-label="Sections">
    <div class="row" id="tabs" role="tablist"></div>
  </nav>
  <p class="intro" id="intro"></p>
  <div id="list" aria-live="polite"></div>
  <p class="empty" id="empty" hidden>Nothing here right now.</p>
  <footer id="foot"></footer>
</div>
<div class="sffs-fade" hidden></div>
<div class="sffs-hint" hidden>Scroll for more &#8595;</div>
<script>
{{CLASS_JS}}
</script>
<script>
(function(){
  var DATA = {{DATA_JSON}};
  var GRADES = ['K','1','2','3','4','5','6','7','8'];
  var LOWER = ['K','1','2','3','4'], MIDDLE = ['5','6','7','8'];
  var MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var DAYS = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  var KEY = 'sffsUpdatesGrades';
  function safeGet(k){ try { return localStorage.getItem(k); } catch(e) { return null; } }
  function safeSet(k, v){ try { localStorage.setItem(k, v); } catch(e) {} }
  function ymd(s){ var p = s.split('-'); return new Date(+p[0], +p[1]-1, +p[2]); }
  function iso(d){ return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0'); }
  function addDays(d, n){ var x = new Date(d); x.setDate(x.getDate()+n); return x; }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  var qs = location.search;
  var today = new Date(); today.setHours(0,0,0,0);
  var mt = qs.match(/[?&]today=(\d{4}-\d{2}-\d{2})/); if (mt) today = ymd(mt[1]);  // for tests
  var TODAY = iso(today);

  // Grade from ?class= (CLAUDE.md §1) via the shared model: rollover on the last day of school, ?grade=N preview.
  var ci = SFFS.classInfo(qs, today);
  var siteGrade = ci.status === 'ok' ? (ci.grade === 0 ? 'K' : String(ci.grade)) : null;
  var selected = (function(){
    var saved = safeGet(KEY); var s = saved ? saved.split(',').filter(function(g){ return GRADES.indexOf(g) >= 0; }) : [];
    if (siteGrade && s.indexOf(siteGrade) < 0) s.push(siteGrade);
    return s;
  })();

  function gradeLabel(g){ return g === 'K' ? 'Kindergarten' : g + ({1:'st',2:'nd',3:'rd'}[g] || 'th') + ' grade'; }
  function audienceLabel(a){
    if (a === 'all') return 'Schoolwide'; if (a === 'lower') return 'Lower School (K–4)'; if (a === 'middle') return 'Middle School (5–8)';
    return a.map(gradeLabel).join(', ');
  }
  function forMe(t){
    var a = t.audience; if (a === 'all') return true;
    if (!selected.length) return true;  // no grade known: show everything
    var set = a === 'lower' ? LOWER : a === 'middle' ? MIDDLE : a;
    return set.some(function(g){ return selected.indexOf(g) >= 0; });
  }
  function start(t){ return t.when && t.when.date ? t.when.date : null; }
  function end(t){ return t.when ? (t.when.end || t.when.date) : null; }
  function isPast(t){ var e = end(t); return !!e && e < TODAY; }
  function spanDays(t){ return t.when && t.when.date ? daysBetween(t.when.date, end(t)) + 1 : 0; }
  function daysBetween(a, b){ return Math.round((ymd(b) - ymd(a)) / 86400000); }
  function shortSpan(t){ return spanDays(t) > 0 && spanDays(t) <= 7; }  // a long range is a standing notice, not a "this week" item
  function latest(t){ return t.updates[t.updates.length-1]; }
  function isNew(t){ return latest(t).date >= iso(addDays(today, -7)); }
  function hasOpenAction(t){
    if (t.deadline) return t.deadline.date >= TODAY;
    if (!t.action) return false;
    return !isPast(t);
  }
  function fmtTime(s){ var p = s.split(':'), h = +p[0], m = p[1]; var ap = h >= 12 ? 'pm' : 'am'; h = h % 12 || 12; return h + (m === '00' ? '' : ':' + m) + ' ' + ap; }
  function fmtDate(s){ var d = ymd(s); return DAYS[d.getDay()] + ' ' + MONTHS[d.getMonth()] + ' ' + d.getDate(); }
  function fmtWhen(t){
    var w = t.when; if (!w || !w.date) return '';
    var s = fmtDate(w.date);
    if (w.end && w.end !== w.date) { var e = ymd(w.end); s = MONTHS[ymd(w.date).getMonth()] + ' ' + ymd(w.date).getDate() + ' – ' + MONTHS[e.getMonth()] + ' ' + e.getDate(); }
    if (w.start_time) s += ', ' + fmtTime(w.start_time) + (w.end_time ? '–' + fmtTime(w.end_time) : '');
    if (w.location) s += ' · ' + w.location;
    return s;
  }
  function daysUntil(s){ return Math.round((ymd(s) - today) / 86400000); }
  function dueLabel(s){ var n = daysUntil(s); return n < 0 ? 'Closed' : n === 0 ? 'Due today' : n === 1 ? 'Due tomorrow' : 'Due ' + fmtDate(s); }
  function sourceLabel(id){ var s = DATA.sources.filter(function(x){ return x.id === id; })[0]; if (!s) return id; return DATA.streams[s.stream].label + ', ' + MONTHS[ymd(s.date).getMonth()] + ' ' + ymd(s.date).getDate(); }
  function sourceHref(id){ var s = DATA.sources.filter(function(x){ return x.id === id; })[0]; return s && s.doc_anchor ? s.doc_anchor : null; }

  function q(v){ return encodeURIComponent(v); }
  function gcal(t){
    var w = t.when, a = w.date.replace(/-/g,''), b;
    if (w.start_time) { var e = w.end_time || w.start_time; a = a + 'T' + w.start_time.replace(':','') + '00'; b = (w.end || w.date).replace(/-/g,'') + 'T' + e.replace(':','') + '00'; }
    else { b = iso(addDays(ymd(w.end || w.date), 1)).replace(/-/g,''); }
    return 'https://calendar.google.com/calendar/render?action=TEMPLATE&text=' + q(t.title) + '&dates=' + a + '/' + b + '&details=' + q(t.summary) + '&location=' + q(w.location || 'SFFS') + (w.start_time ? '&ctz=America/Los_Angeles' : '');
  }

  var SECTION_LABEL = {ask: 'Ask your child', learning: 'What we\'re learning', homework: 'Homework', routines: 'Routines', resources: 'Resources', specialists: 'Specialists'};
  var SECTION_ORDER = ['ask', 'learning', 'homework', 'routines', 'specialists', 'resources'];
  var TABS = [
    {id:'action', label:'Action needed', pick:function(t){ return hasOpenAction(t); }, sort:function(a,b){ return (a.deadline ? a.deadline.date : end(a) || '9') < (b.deadline ? b.deadline.date : end(b) || '9') ? -1 : 1; },
     intro:'Sign-ups, RSVPs and deadlines that are still open, soonest first.'},
    {id:'week', label:'This week', pick:function(t){ var s = start(t), e = end(t); return s && shortSpan(t) && e >= TODAY && s < iso(addDays(today, 7)); }, sort:function(a,b){ return start(a) < start(b) ? -1 : 1; },
     intro:'Happening in the next seven days.'},
    {id:'coming', label:'Coming up', pick:function(t){ var s = start(t); return s && shortSpan(t) && s >= iso(addDays(today, 7)); }, sort:function(a,b){ return start(a) < start(b) ? -1 : 1; },
     intro:'Further out. Items marked "On Important Dates" are also on the calendar above.'},
    {id:'changed', label:'What changed', pick:function(t){ return isNew(t); }, sort:function(a,b){ return latest(a).date > latest(b).date ? -1 : 1; },
     intro:'Topics that were new or updated in the last seven days of email, newest first. Open "History" to see how each one evolved.'},
    {id:'classroom', label:'Classroom', pick:function(t){ return t.kind === 'classroom'; }, sort:function(a,b){ var d = SECTION_ORDER.indexOf(a.section) - SECTION_ORDER.indexOf(b.section); return d !== 0 ? d : (latest(a).date > latest(b).date ? -1 : 1); },
     intro:"From the teachers' newsletters: questions to ask your child, what the class is learning, homework and routines. Newest first within each group."},
    {id:'know', label:'Good to know', pick:function(t){ return ((t.kind === 'notice' || t.kind === 'volunteer') || (t.when && !shortSpan(t) && t.kind !== 'classroom')) && t.kind !== 'letter' && !isPast(t); }, sort:function(a,b){ return latest(a).date > latest(b).date ? -1 : 1; },
     intro:'Standing notices and ways to help. Not tied to one date.'},
    {id:'head', label:'From the Head', pick:function(t){ return t.kind === 'letter'; }, sort:function(a,b){ return latest(a).date > latest(b).date ? -1 : 1; },
     intro:"Brenda Leaks' letters, newest first, in a few lines each. The full text is in the log."}
  ];
  var tab = 'action';
  var tm = qs.match(/[?&]tab=([a-z]+)/); if (tm && TABS.some(function(t){ return t.id === tm[1]; })) tab = tm[1];

  var list = document.getElementById('list'), empty = document.getElementById('empty'), intro = document.getElementById('intro');
  var tabsEl = document.getElementById('tabs'), gradesEl = document.getElementById('grades');

  function card(t){
    var div = document.createElement('div'); div.className = 'card' + (isNew(t) ? ' new' : '');
    var badges = '';
    if (t.deadline) badges += '<span class="badge due">' + esc(dueLabel(t.deadline.date)) + (t.deadline.what ? ': ' + esc(t.deadline.what) : '') + '</span>';
    else if (t.kind === 'event' && t.when) badges += '<span class="badge event">Event</span>';
    else if (t.kind === 'classroom') badges += '<span class="badge classroom">' + esc(SECTION_LABEL[t.section] || 'Classroom') + (t.subject ? ' · ' + esc(t.subject) : '') + '</span>';
    else badges += '<span class="badge ' + esc(t.kind) + '">' + esc({notice:'Notice', volunteer:'Volunteer', letter:'Letter', deadline:'Deadline', event:'Event'}[t.kind] || t.kind) + '</span>';
    if (t.audience !== 'all') badges += '<span class="badge aud">' + esc(audienceLabel(t.audience)) + '</span>';
    if (t.official) badges += '<span class="badge official">On Important Dates</span>';
    if (isNew(t)) badges += '<span class="badge newb">' + (t.updates.length > 1 ? 'Updated' : 'New') + '</span>';
    var h = '<div class="top">' + badges + '</div><p class="t">' + esc(t.title) + '</p>';
    var when = fmtWhen(t); if (when) h += '<p class="when">' + esc(when) + '</p>';
    h += '<p class="sum">' + esc(t.summary) + '</p>';
    if (t.items && t.items.length) h += '<ul class="items">' + t.items.map(function(x){ return '<li>' + esc(x) + '</li>'; }).join('') + '</ul>';
    var acts = '';
    (t.links || []).forEach(function(l, i){ acts += '<a class="lnk' + (i === 0 && hasOpenAction(t) ? ' primary' : '') + '" href="' + esc(l.url) + '" target="_blank" rel="noopener noreferrer">' + esc(l.label) + ' ↗</a>'; });
    if (t.when && t.when.date && shortSpan(t) && !t.official && !isPast(t)) acts += '<a class="lnk" href="' + esc(gcal(t)) + '" target="_blank" rel="noopener noreferrer">Add to Google Calendar</a>';
    if (acts) h += '<div class="acts">' + acts + '</div>';
    h += '<details><summary>History (' + t.updates.length + ')</summary><ul class="hist">' + t.updates.map(function(u){
      var href = sourceHref(u.source), lab = esc(sourceLabel(u.source));
      return '<li><span class="d">' + esc(fmtDate(u.date)) + '</span> · ' + esc(u.note) + ' <span class="s">(' + (href ? '<a href="' + esc(href) + '" target="_blank" rel="noopener noreferrer">' + lab + '</a>' : lab) + ')</span></li>';
    }).join('') + '</ul></details>';
    div.innerHTML = h;
    return div;
  }

  function render(){
    var def = TABS.filter(function(x){ return x.id === tab; })[0];
    var items = DATA.topics.filter(forMe).filter(def.pick).sort(def.sort);
    list.textContent = '';
    var lastSection = null;
    items.forEach(function(t){
      if (tab === 'classroom' && t.section !== lastSection) { var h = document.createElement('h2'); h.className = 'sec'; h.textContent = SECTION_LABEL[t.section] || t.section; list.appendChild(h); lastSection = t.section; }
      list.appendChild(card(t));
    });
    empty.hidden = items.length > 0;
    intro.textContent = def.intro;
    [].slice.call(tabsEl.children).forEach(function(b){
      var on = b.getAttribute('data-tab') === tab; b.classList.toggle('on', on); b.setAttribute('aria-selected', on);
      var d = TABS.filter(function(x){ return x.id === b.getAttribute('data-tab'); })[0];
      b.querySelector('.n').textContent = DATA.topics.filter(forMe).filter(d.pick).length;
    });
    [].slice.call(gradesEl.querySelectorAll('.chip')).forEach(function(c){ var on = selected.indexOf(c.getAttribute('data-g')) >= 0; c.classList.toggle('on', on); c.setAttribute('aria-pressed', on); });
    document.getElementById('showing').textContent = 'Showing schoolwide' + (selected.length ? ' + ' + selected.slice().sort(function(a,b){ return GRADES.indexOf(a) - GRADES.indexOf(b); }).map(gradeLabel).join(', ') : ' and every grade') + '.';
    hint();
  }

  TABS.forEach(function(d){
    var b = document.createElement('button'); b.type = 'button'; b.className = 'chip tab'; b.setAttribute('role', 'tab'); b.setAttribute('data-tab', d.id);
    b.innerHTML = esc(d.label) + ' <span class="n"></span>';
    b.addEventListener('click', function(){ tab = d.id; render(); try { w.scrollTo({top: 0}); } catch(e) { w.scrollTop = 0; } });
    tabsEl.appendChild(b);
  });
  GRADES.forEach(function(g){
    var c = document.createElement('button'); c.type = 'button'; c.className = 'chip g'; c.setAttribute('data-g', g); c.setAttribute('aria-pressed', 'false');
    c.textContent = g === 'K' ? 'K' : g; c.title = gradeLabel(g);
    c.addEventListener('click', function(){
      var i = selected.indexOf(g); if (i >= 0) selected.splice(i, 1); else selected.push(g);
      safeSet(KEY, selected.join(',')); render();
    });
    gradesEl.appendChild(c);
  });

  var toggle = document.getElementById('gradesToggle');
  function setGrades(open){ gradesEl.hidden = !open; toggle.setAttribute('aria-expanded', open); toggle.textContent = open ? 'Done' : 'Change grades'; }
  toggle.addEventListener('click', function(){ setGrades(gradesEl.hidden); hint(); });
  var wide = window.innerWidth > 560;
  setGrades(wide); toggle.hidden = wide;  // wide frames: picker always open, no toggle; phones: behind the button

  var foot = document.getElementById('foot');
  var streams = Object.keys(DATA.streams).map(function(k){ return DATA.streams[k].label; });
  foot.innerHTML = '<p>Built from ' + DATA.sources.length + ' school emails (' + esc(streams.join(', ')) + ') through ' + esc(fmtDate(DATA.built_through)) + '. Summaries are ours; the school\'s wording is in the full-text log. Always check the original email for anything time-critical.</p>';
  if (siteGrade) document.getElementById('subtitle').textContent = 'What the school emails said, organised for ' + gradeLabel(siteGrade) + ' families. Tick other grades if you have children in them.';

  var w = document.getElementById('wrap');
  var fade = document.querySelector('.sffs-fade'), hintEl = document.querySelector('.sffs-hint');
  function hint(){ var more = w.scrollHeight - w.clientHeight - w.scrollTop > 24; fade.hidden = !more; hintEl.hidden = !more; }
  w.addEventListener('scroll', hint); window.addEventListener('resize', hint);
  render();
  setTimeout(hint, 400); setTimeout(hint, 1500); setTimeout(hint, 3000);  // Sites lays the iframe out late
})();
</script>
</body>
</html>
"""


def main():
    data = json.loads(SRC.read_text())
    page, version = build(data)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(page)
    shutil.copy(SRC, OUT / "data.json")
    print(f"built {OUT.relative_to(ROOT)}/index.html  {len(data['topics'])} topics  version {version}")


if __name__ == "__main__":
    main()
