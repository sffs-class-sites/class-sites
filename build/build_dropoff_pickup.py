#!/usr/bin/env python3
"""Build the Drop-off & Pickup embed: _site/shared/dropoff-pickup/index.html.

How to do morning drop-off and afternoon pickup at 250 Valencia: one toggle (morning /
afternoon, chosen by the time of day in San Francisco), a simplified street diagram with the
route drawn on it and cars moving along it, numbered steps that match the numbered pins, and the rest of the school's rules in short cards below.

Facts and wording: shared/dropoff-pickup/data.json (edited down from the school's "Arrival,
Dismissal and Carpool Information"; no emails or phone numbers, and the only names are the two
staff contacts for Middle School self-dismissal, an exception Ahin made on 2026-11-12). Start and dismissal times come from
shared/school-hours/data.json so they are kept in one place. The map (streets and routes) is
drawn here, in MAP: a diagram, not to scale, traced from the
school's two satellite maps.

A whole-page embed: alone on its own Site page at the `page` box. Placed with ?class=YYYY it
flags that class's times. ?view=morning|afternoon overrides the time-of-day choice (tests,
and links from elsewhere).
"""
import hashlib
import json
import pathlib
import re
import sys
from urllib.parse import urlparse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import classinfo
import style

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "shared" / "dropoff-pickup" / "data.json"
HOURS = ROOT / "shared" / "school-hours" / "data.json"
OUT = ROOT / "_site" / "shared" / "dropoff-pickup"

# Street diagram, 360 units wide. North is up. Guerrero x 24-58 (northbound lane x=49),
# Valencia x 272-312 (southbound lane x=282, the school side), Duboce y 20-48 (eastbound lane
# y=40), Clinton Park y 96-114, Brosnan y 206-224. The view stops just below Brosnan (height 250).
# No circle-the-block loop is drawn (Ahin, 2026-11-12): staff outside direct it.
MAP = r"""
<svg id="map" viewBox="0 0 360 250" role="img" aria-labelledby="map-desc" xmlns="http://www.w3.org/2000/svg">
  <desc id="map-desc"></desc>
  <defs>
    <pattern id="hatch-no" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="6" height="6" fill="#fde3e1"/><rect width="2.4" height="6" fill="#e2574c"/>
    </pattern>
    <pattern id="hatch-wait" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="6" height="6" fill="#fff1cf"/><rect width="2.4" height="6" fill="#e0a21b"/>
    </pattern>
  </defs>
  <rect x="0" y="0" width="360" height="250" fill="#e8ecf1"/>
  <!-- roads -->
  <g fill="#fff" stroke="#c9d0da" stroke-width="1">
    <rect x="-2" y="20" width="364" height="28"/>
    <rect x="58" y="96" width="214" height="18"/>
    <rect x="58" y="206" width="214" height="18"/>
    <rect x="24" y="-2" width="34" height="384"/>
    <rect x="272" y="-2" width="40" height="384"/>
  </g>
  <g fill="#fff"><rect x="25" y="21" width="32" height="340"/><rect x="273" y="21" width="38" height="340"/>
    <rect x="57" y="97" width="3" height="16"/><rect x="270" y="97" width="4" height="16"/><rect x="57" y="207" width="3" height="16"/><rect x="270" y="207" width="4" height="16"/></g>
  <!-- school -->
  <rect x="150" y="119" width="118" height="82" rx="3" fill="#3457a6"/>
  <text x="209" y="141" class="t-school">Friends School</text>
  <text x="209" y="154" class="t-addr">250 Valencia</text>
  <rect x="266" y="172" width="5" height="10" fill="#fff"/>
  <text x="262" y="181" class="t-gate">South Gate &#9656;</text>
  <!-- Brosnan Gate: the middle of the school building on Brosnan (Ahin, 2026-11-12) -->
  <rect x="204" y="199" width="10" height="5" fill="#fff"/>
  <text x="209" y="196" class="t-gate" style="text-anchor:middle">Brosnan Gate &#9662;</text>
  <!-- street names -->
  <g class="t-street">
    <text x="150" y="32" text-anchor="middle">Duboce</text>
    <text x="64" y="91">Clinton Park</text>
    <text x="64" y="237">Brosnan</text>
    <text transform="translate(15 160) rotate(-90)" text-anchor="middle">Guerrero</text>
    <text transform="translate(331 96) rotate(-90)" text-anchor="middle">Valencia</text>
  </g>
  <text x="346" y="14" class="t-n" text-anchor="middle">N &#8593;</text>

  <!-- MORNING -->
  <g id="m-morning">
    <rect x="59" y="97" width="212" height="16" fill="url(#hatch-no)"/>
    <rect x="59" y="207" width="212" height="16" fill="url(#hatch-no)"/>
    <rect x="273" y="48" width="18" height="48" fill="url(#hatch-wait)"/>
    <text x="266" y="76" class="t-wait" text-anchor="end">No waiting</text>
    <rect x="268" y="130" width="7" height="60" rx="3" class="island"/>
    <!-- two ways in: down Valencia, or along Duboce and right onto Valencia; that car starts on Duboce itself, so it reads as coming from Duboce or from Guerrero (Ahin, 2026-11-12) -->
    <path class="route" d="M282,0 V250"/>
    <path class="route" d="M74,40 H282"/>
    <g class="arrow"><path d="M222,40 l-9,-6 v12z"/><path d="M282,116 l-6,-9 h12z"/><path d="M282,236 l-6,-9 h12z"/></g>
    <g class="car"><rect x="-7" y="-4" width="14" height="8" rx="3"/>
      <animateMotion dur="7s" begin="3.5s" repeatCount="indefinite" rotate="auto" calcMode="linear" path="M74,40 H282 V262" keyPoints="0;0.763;0.763;1" keyTimes="0;0.5;0.72;1"/></g>
    <g class="car"><rect x="-7" y="-4" width="14" height="8" rx="3"/>
      <animateMotion dur="7s" repeatCount="indefinite" rotate="auto" calcMode="linear" path="M282,-12 V262" keyPoints="0;0.628;0.628;1" keyTimes="0;0.42;0.72;1"/></g>
    <g class="pin"><circle cx="301" cy="30" r="8.5"/><text x="301" y="34">1</text></g>
    <g class="pin"><circle cx="301" cy="72" r="8.5"/><text x="301" y="76">2</text></g>
    <g class="pin"><circle cx="301" cy="160" r="8.5"/><text x="301" y="164">3</text></g>
  </g>

  <!-- AFTERNOON -->
  <g id="m-afternoon" hidden>
    <rect x="59" y="207" width="212" height="16" fill="url(#hatch-no)"/>
    <rect x="273" y="48" width="18" height="48" fill="url(#hatch-wait)"/>
    <text x="266" y="76" class="t-wait" text-anchor="end">No stopping</text>
    <text x="268" y="91" class="t-go" text-anchor="end">Line up &#183; 8 cars max</text>
    <rect x="268" y="130" width="7" height="60" rx="3" class="island"/>
    <path class="route" d="M49,250 V105 H282 V250"/>
    <g class="arrow"><path d="M49,150 l-6,9 h12z"/><path d="M175,105 l-9,-6 v12z"/><path d="M282,236 l-6,-9 h12z"/></g>
    <g class="car"><rect x="-7" y="-4" width="14" height="8" rx="3"/>
      <animateMotion dur="10s" repeatCount="indefinite" rotate="auto" calcMode="linear" path="M49,262 V105 H282 V262" keyPoints="0;0.47;0.47;0.814;0.814;1" keyTimes="0;0.27;0.45;0.62;0.86;1"/></g>
    <g class="pin"><circle cx="215" cy="105" r="8.5"/><text x="215" y="109">1</text></g>
    <g class="pin"><circle cx="301" cy="160" r="8.5"/><text x="301" y="164">2</text></g>
  </g>

</svg>
"""

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="sffs-embed" content="dropoff-pickup@{{VERSION}}">
<meta name="robots" content="noindex">
<title>{{TITLE}}</title>
<style>
:root{--ink:#1f2937;--sub:#5b6472;--line:#e2e5ea;--bg:#fff;--accent:#3457a6;--accent-light:#eaeffb;--go:#12784a;--go-light:#e3f4ea;--no:#b3261e;--no-light:#fdeceb;--wait:#8a5a00}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg);line-height:1.45}
.wrap{height:100%;overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;border:2px solid #d6dff5;border-radius:12px;padding:16px 18px 60px}
.inner{max-width:1100px;margin:0 auto}
header{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:10px}
h1{font-size:1.3rem;margin:0}
.sub{color:var(--sub);font-size:.88rem;margin:0;flex:1}
a.full{font-size:.82rem;font-weight:600;color:var(--accent);text-decoration:none;border:1px solid #d6dff5;border-radius:999px;padding:5px 11px;white-space:nowrap}
a.full[hidden]{display:none}
.seg{display:grid;grid-template-columns:1fr 1fr;gap:0;border:2px solid var(--accent);border-radius:12px;overflow:hidden;margin-bottom:12px}
.seg button{min-height:46px;border:0;background:#fff;color:var(--accent);font-family:inherit;font-weight:700;font-size:1rem;line-height:1.15;cursor:pointer;padding:6px 8px}
.seg button[aria-pressed="true"]{background:var(--accent);color:#fff}
.seg button:focus-visible,a:focus-visible{outline:3px solid #f0a055;outline-offset:-3px}
.main{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:22px;align-items:start}
figure{margin:0}
#map{display:block;width:100%;height:auto;border:1px solid var(--line);border-radius:10px;background:#e8ecf1}
#map [hidden]{display:none}
.t-school{font:700 12.5px sans-serif;fill:#fff;text-anchor:middle}
.t-addr{font:10px sans-serif;fill:#dfe7fa;text-anchor:middle}
.t-gate{font:700 10px sans-serif;fill:#fff;text-anchor:end}
.t-street text{font:600 10px sans-serif;fill:#4b5563;paint-order:stroke;stroke:#fff;stroke-width:3px;stroke-linejoin:round}
.t-n{font:700 9.5px sans-serif;fill:#6b7280}
.t-wait{font:700 10px sans-serif;fill:var(--wait)}
.t-go{font:700 10px sans-serif;fill:var(--go)}
.island{fill:var(--go);stroke:#fff;stroke-width:1.5}
.route{fill:none;stroke:var(--go);stroke-width:5;stroke-linecap:round;stroke-linejoin:round;opacity:.85}
.arrow path{fill:#fff;stroke:var(--go);stroke-width:1.6;stroke-linejoin:round}
.car rect{fill:#111827;stroke:#fff;stroke-width:1.5}
.pin circle{fill:#111827;stroke:#fff;stroke-width:1.5}
.pin text{font:700 11px sans-serif;fill:#fff;text-anchor:middle}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;margin:8px 0 0;padding:0;list-style:none;font-size:.8rem;color:var(--sub)}
.legend i{display:inline-block;width:18px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.legend .route i{background:var(--go)}
.legend .no i{background:repeating-linear-gradient(45deg,#e2574c 0 3px,#fde3e1 3px 6px)}
.legend .wait i{background:repeating-linear-gradient(45deg,#e0a21b 0 3px,#fff1cf 3px 6px)}
.legend [hidden]{display:none}
h2{font-size:1.08rem;margin:0 0 8px}
.ready{margin:0 0 10px;padding:8px 12px;border-radius:10px;background:var(--go-light);color:#0d5a37;font-weight:600;font-size:.95rem}
ol.steps{list-style:none;margin:0;padding:0}
ol.steps li{display:grid;grid-template-columns:30px 1fr;gap:10px;padding:9px 0;border-top:1px solid var(--line)}
ol.steps li:first-child{border-top:0}
.num{width:28px;height:28px;border-radius:50%;background:#111827;color:#fff;font-weight:700;font-size:.9rem;display:flex;align-items:center;justify-content:center}
.st{font-weight:700;display:block}
.sd{display:block;color:#374151;font-size:.92rem;margin-top:1px}
.donts{margin:12px 0 0;padding:10px 12px;border-radius:10px;background:var(--no-light);border:1px solid #f5c6c2}
.donts ul{margin:0;padding:0;list-style:none}
.donts li{padding:4px 0 4px 28px;position:relative;font-size:.93rem}
.donts li:before{content:"\2716";position:absolute;left:1px;top:1px;color:var(--no);font-weight:900;font-size:1.2rem;line-height:1.5}
.donts li.ok:before{content:"\2714";color:var(--go)}
.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:18px}
.card{border:1px solid var(--line);border-radius:10px;padding:11px 13px}
.card h3{margin:0 0 5px;font-size:.98rem;color:var(--accent)}
.card p{margin:0 0 6px;font-size:.92rem}
.card p:last-child{margin-bottom:0}
.card ul{margin:0;padding:0 0 0 18px;font-size:.92rem}
.card li{margin:0 0 5px}
.card li:last-child{margin-bottom:0}
.card a{color:var(--accent);font-weight:600}
.card.times{grid-column:span 1}
table{border-collapse:collapse;width:100%;font-size:.9rem;margin-top:4px}
th,td{text-align:left;padding:4px 6px 4px 0;border-top:1px solid var(--line);vertical-align:top}
th{font-size:.75rem;color:var(--sub);font-weight:600;border-top:0}
tr.mine td{font-weight:700;background:var(--accent-light)}
tr.mine td:first-child{box-shadow:-6px 0 0 var(--accent-light)}
.flag{display:inline-block;margin-left:6px;font-size:.62rem;letter-spacing:.05em;background:var(--accent);color:#fff;border-radius:4px;padding:1px 5px;vertical-align:1px}
.section-h{margin:20px 0 0;font-size:.8rem;letter-spacing:.05em;text-transform:uppercase;color:var(--sub)}
.section-h + .cards{margin-top:8px}
footer{margin-top:16px;font-size:.8rem;color:var(--sub)}
.sffs-fade{position:fixed;left:0;right:0;bottom:0;height:58px;z-index:8;pointer-events:none;background:linear-gradient(to bottom,rgba(255,255,255,0),#fff 72%);border-radius:0 0 12px 12px}
.sffs-hint{position:fixed;left:50%;bottom:12px;transform:translateX(-50%);z-index:9;pointer-events:none;white-space:nowrap;font:600 12px/1 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--accent);background:var(--accent-light);border:1px solid #d6dff5;padding:7px 13px;border-radius:999px;box-shadow:0 1px 5px rgba(0,0,0,.13)}
.sffs-fade[hidden],.sffs-hint[hidden]{display:none}
@media (max-width:860px){
  .main{grid-template-columns:1fr;gap:14px}
  .cards{grid-template-columns:repeat(2,minmax(0,1fr))}
}
/* A phone: title and toggle on two short lines, then the map, so the first view is the route. */
@media (max-width:560px){
  .wrap{padding:8px 10px 56px}
  header{margin-bottom:6px;flex-wrap:nowrap;align-items:center}
  h1{font-size:1.05rem;white-space:nowrap}
  .sub{font-size:.74rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  a.full{padding:4px 9px;font-size:.76rem}
  .seg{margin-bottom:8px}
  .seg button{min-height:44px;font-size:.92rem}
  .cards{grid-template-columns:1fr;gap:10px}
}
@media (max-width:359px){ .sub{display:none} h1{flex:1} }
</style>
</head>
<body>
<div class="wrap" id="wrap"><div class="inner">
  <header>
    <h1 id="title">{{TITLE}}</h1>
    <p class="sub" id="sub"></p>
    <a class="full" id="fullpage" href="" target="_blank" rel="noopener" hidden>Full page &#8599;</a>
  </header>
  <div class="seg" role="group" aria-label="Time of day">
    <button type="button" id="tab-morning" aria-pressed="false"></button>
    <button type="button" id="tab-afternoon" aria-pressed="false"></button>
  </div>
  <div class="main">
    <figure>
      {{MAP}}
      <ul class="legend" id="legend"></ul>
    </figure>
    <section aria-labelledby="headline">
      <h2 id="headline"></h2>
      <p class="ready" id="ready"></p>
      <ol class="steps" id="steps"></ol>
      <div class="donts"><ul id="donts" aria-label="Rules for drivers"></ul></div>
    </section>
  </div>
  <div class="cards" id="cards"></div>
  <h2 class="section-h">Morning and afternoon</h2>
  <div class="cards" id="always"></div>
  <footer id="foot"></footer>
</div></div>
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
  var DATA = {{DATA}};
  function $(id){ return document.getElementById(id); }
  /* Text only (textContent), never innerHTML with data. */
  function el(tag, cls, text){ var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function param(k){ var m = new RegExp('[?&]' + k + '=([^&]*)').exec(location.search); return m ? decodeURIComponent(m[1]) : null; }

  var ci = SFFS.classInfo(location.search);
  var mine = null;
  if (ci.status === 'ok') DATA.hours.forEach(function(r){ if (r.grades.indexOf(ci.grade) >= 0) mine = r; });
  $('sub').textContent = DATA.address + ' · ' + (ci.cls ? ci.heading : DATA.year_label);

  /* Morning before 11 a.m. in San Francisco, afternoon after; ?view= overrides. */
  function defaultMode(){
    var v = param('view'); if (v === 'morning' || v === 'afternoon') return v;
    var h = 12;
    try { h = parseInt(new Intl.DateTimeFormat('en-US', {timeZone: 'America/Los_Angeles', hour: 'numeric', hourCycle: 'h23'}).format(new Date()), 10); } catch (e) { h = new Date().getHours(); }
    return h < 11 ? 'morning' : 'afternoon';
  }
  var mode = defaultMode();

  /* [words](https://link) in the data becomes a link that opens a new tab; everything else is plain text. */
  function rich(node, text){
    var re = /\[([^\]]+)\]\((https:\/\/[^)\s]+)\)/g, last = 0, m;
    while ((m = re.exec(text))) {
      node.appendChild(document.createTextNode(text.slice(last, m.index)));
      var a = el('a', null, m[1]); a.href = m[2]; a.target = '_blank'; a.rel = 'noopener'; node.appendChild(a);
      last = re.lastIndex;
    }
    node.appendChild(document.createTextNode(text.slice(last)));
    return node;
  }
  function card(c){
    var d = el('div', 'card'); d.appendChild(el('h3', null, c.h));
    if (c.bullets) { var ul = el('ul'); c.p.forEach(function(t){ ul.appendChild(rich(el('li'), t)); }); d.appendChild(ul); }
    else c.p.forEach(function(t){ d.appendChild(rich(el('p'), t)); });
    if (c.portal) { var p = el('p'), a = el('a', null, DATA.portal.label + ' ↗'); a.href = DATA.portal.url; a.target = '_blank'; a.rel = 'noopener'; p.appendChild(a); d.appendChild(p); }
    return d;
  }
  function times(m){
    var d = el('div', 'card times'); d.appendChild(el('h3', null, m.times_h)); d.appendChild(el('p', null, m.times_lead));
    var t = el('table'), hr = el('tr');
    var cols = mode === 'morning' ? ['Grade', 'School starts'] : ['Grade', 'Mon, Tue, Thu, Fri', 'Wednesday'];
    cols.forEach(function(c){ var th = el('th', null, c); th.scope = 'col'; hr.appendChild(th); });
    var thead = el('thead'); thead.appendChild(hr); t.appendChild(thead);
    var tb = el('tbody');
    DATA.hours.forEach(function(r){
      var tr = el('tr'), g = el('td', null, r.label);
      if (r === mine) { tr.className = 'mine'; tr.setAttribute('aria-current', 'true'); g.appendChild(el('span', 'flag', 'THIS CLASS')); }
      tr.appendChild(g);
      if (mode === 'morning') tr.appendChild(el('td', null, r.regular.start));
      else { tr.appendChild(el('td', null, r.regular.end)); tr.appendChild(el('td', null, r.wednesday.end)); }
      tb.appendChild(tr);
    });
    t.appendChild(tb); d.appendChild(t);
    return d;
  }
  function fill(node, kids){ while (node.firstChild) node.removeChild(node.firstChild); kids.forEach(function(k){ node.appendChild(k); }); }

  function render(){
    var m = DATA.modes[mode];
    ['morning', 'afternoon'].forEach(function(k){
      $('tab-' + k).setAttribute('aria-pressed', String(k === mode));
      $('m-' + k).toggleAttribute('hidden', k !== mode);
    });
    $('map-desc').textContent = m.headline + '. ' + m.steps.map(function(s, i){ return (i + 1) + ': ' + s.t; }).join('. ') + '.';
    $('headline').textContent = m.headline;
    $('ready').textContent = m.ready;
    fill($('steps'), m.steps.map(function(s, i){
      var li = el('li'); li.appendChild(el('span', 'num', String(i + 1)));
      var b = el('div'); b.appendChild(el('span', 'st', s.t)); b.appendChild(rich(el('span', 'sd'), s.d)); li.appendChild(b); return li;
    }));
    fill($('donts'), m.donts.map(function(x){
      if (typeof x === 'string') return el('li', null, x);
      var li = el('li', x.ok ? 'ok' : null);
      li.textContent = x.t; return li;
    }));
    var lg = m.legend.map(function(x){ var li = el('li', x[0]); li.appendChild(el('i')); li.appendChild(document.createTextNode(x[1])); return li; });
    fill($('legend'), lg);
    fill($('cards'), [times(m)].concat(m.cards.map(card)));
    upd();
  }
  $('tab-morning').textContent = DATA.modes.morning.tab;
  $('tab-afternoon').textContent = DATA.modes.afternoon.tab;
  $('tab-morning').addEventListener('click', function(){ mode = 'morning'; render(); });
  $('tab-afternoon').addEventListener('click', function(){ mode = 'afternoon'; render(); });
  fill($('always'), DATA.always.map(card));
  $('foot').textContent = 'From the school’s ' + DATA.source_title + '. The map is a simplified diagram, not to scale. Updated ' + DATA.updated_label + '.';

  /* Reduced motion: no moving cars; park each one at its stop instead. */
  if (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) {
    Array.prototype.forEach.call(document.querySelectorAll('#map animateMotion'), function(a){ a.parentNode.removeChild(a); });
    document.querySelector('#m-morning .car').setAttribute('transform', 'translate(282 160) rotate(90)');
    document.querySelector('#m-afternoon .car').setAttribute('transform', 'translate(282 160) rotate(90)');
  }

  /* Inside a Site the frame is small on a phone: offer the same page in its own tab. */
  var full = $('fullpage');
  full.href = location.href.split('#')[0];
  if (window.self !== window.top) full.hidden = false;

  /* Scroll affordance: Sites lays the iframe out late, so re-check after load and on resize. */
  var w = $('wrap'), h = $('hint'), f = $('fade');
  function upd(){ var more = w.scrollHeight - w.clientHeight - w.scrollTop > 8; h.hidden = !more; f.hidden = !more; }
  w.addEventListener('scroll', upd, {passive: true});
  window.addEventListener('resize', upd);
  if (window.ResizeObserver) new ResizeObserver(upd).observe(w);
  render(); setTimeout(upd, 120); setTimeout(upd, 600);
})();
</script>
</body>
</html>
"""

PERSONAL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\b\d{3}[-. ]\d{3}[-. ]\d{4}\b|\b\d{3}-\d{4}\b")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
PINS = {"morning": 3, "afternoon": 2}   # numbered pins drawn in MAP for each mode
SOURCE_TITLE = "Arrival, Dismissal and Carpool Information, {year}"


def load():
    """Read and validate the data file; any problem stops the build (the previous deploy stays up)."""
    raw = SRC.read_bytes()
    data = json.loads(raw)
    errs = []
    if data.get("schema") != 1:
        errs.append("expected schema 1")
    for k in ("title", "address", "year_label"):
        if not data.get(k):
            errs.append(f"{k} is missing")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(data.get("updated", ""))):
        errs.append("updated must be YYYY-MM-DD")
    if urlparse((data.get("portal") or {}).get("url", "")).scheme != "https":
        errs.append("portal.url must be a full https:// link")
    for name in ("morning", "afternoon"):
        m = (data.get("modes") or {}).get(name) or {}
        for k in ("tab", "headline", "ready", "steps", "legend", "donts", "cards", "times_h", "times_lead"):
            if not m.get(k):
                errs.append(f"modes.{name}.{k} is missing")
        if len(m.get("steps") or []) != PINS[name]:
            errs.append(f"modes.{name}.steps: the {name} map has {PINS[name]} numbered pins, so there must be exactly {PINS[name]} steps")
    if not data.get("always"):
        errs.append("always is missing")
    for where, s in style.walk_strings(data):
        for issue in style.colon_issues(s):
            errs.append(f"{where}: lowercase letter after a colon in {issue}; house style starts the next word with a capital")
        if PERSONAL.search(s):
            errs.append(f"looks like an email address or phone number in {s[:60]!r}; this file is public")
    if errs:
        raise SystemExit("dropoff-pickup/data.json:\n  " + "\n  ".join(errs))
    hours_raw = HOURS.read_bytes()
    hours = json.loads(hours_raw)["rows"]
    return data, hours, raw + hours_raw


def build(data, hours, raw):
    version = f"{data['updated']}.{hashlib.sha256(raw + MAP.encode()).hexdigest()[:8]}"
    y, m, d = (int(x) for x in data["updated"].split("-"))
    public = {k: v for k, v in data.items() if not k.startswith("_")}
    public["hours"] = hours
    public["updated_label"] = f"{MONTHS[m - 1]} {d}, {y}"
    public["source_title"] = SOURCE_TITLE.format(year=data["year_label"])
    title = data["title"].replace("&", "&amp;").replace("<", "&lt;")
    page = (PAGE.replace("{{VERSION}}", version)
                .replace("{{TITLE}}", title)
                .replace("{{MAP}}", MAP.strip())
                .replace("{{CLASS_JS}}", classinfo.class_js())
                .replace("{{LANG_JS}}", classinfo.lang_js())
                .replace("{{DATA}}", json.dumps(public, ensure_ascii=False).replace("</", "<\\/")))
    return page, version


def main():
    data, hours, raw = load()
    page, version = build(data, hours, raw)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(page)
    print(f"dropoff-pickup@{version} -> {OUT / 'index.html'} ({len(page)} bytes)")


if __name__ == "__main__":
    main()
