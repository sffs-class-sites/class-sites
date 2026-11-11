#!/usr/bin/env python3
"""Build the School Hours embed: _site/shared/school-hours/index.html.

Replaces the pasted "SFFS School Hours & Early Dismissal" code on the class homepages
(ROADMAP C4; pasted hashes 5d656010830c on the 1st-grade home and fd7690d8c3e5 on the
3rd-grade home, which differed only in which grade row was flagged "THIS CLASS").

The content is shared/school-hours/data.json, transcribed from the SFFS Family Handbook
(the file cites the section and page). It holds no personal data, so it lives in git and is
inlined into the page. At view time the page reads ?class=YYYY through shared/class/class.js
and highlights the viewer's grade row the way the pasted copies did, with a lead card that
puts that row's hours first on a phone. Without ?class= it shows the plain table.

A <meta name="sffs-embed"> marker carries id@version for the monitor: the handbook's
revision month plus a hash of the data, so an edit to the hours changes the version.
"""
import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import classinfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "shared" / "school-hours" / "data.json"
OUT = ROOT / "_site" / "shared" / "school-hours"

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="sffs-embed" content="school-hours@{{VERSION}}">
<meta name="robots" content="noindex">
<title>School Hours &amp; Early Dismissal</title>
<style>
:root{--ink:#1f2937;--sub:#5b6472;--line:#e2e5ea;--bg:#fff;--panel:#f7f8fa;--accent:#3457a6;--accent-light:#eaeffb;--wed:#b4720a;--wed-bg:#fdf3e0;--hl-bg:#fff6d8;--hl-border:#e3c22b}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg);line-height:1.45}
.wrap{height:100%;overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;border:2px solid #d6dff5;border-radius:12px;padding:16px 16px 56px}
h1{font-size:1.25rem;margin:0 0 2px}
.sub{color:var(--sub);font-size:.88rem;margin:0 0 12px}
.lead{border:1px solid var(--hl-border);background:var(--hl-bg);border-radius:12px;padding:10px 14px;margin:0 0 14px}
.lead[hidden]{display:none}
.lead .who{font-size:.78rem;font-weight:800;letter-spacing:.03em;text-transform:uppercase;color:#7a5b00;margin:0 0 4px}
.lead p{margin:2px 0;font-size:.98rem;display:flex;gap:12px;flex-wrap:wrap}
.lead .k{color:var(--sub);font-weight:600;flex:0 0 6.5em}
.lead .v{font-weight:700;white-space:nowrap}
h2{font-size:1rem;margin:18px 0 8px}
.table-scroll{border:1px solid var(--line);border-radius:10px;overflow:hidden}
table{border-collapse:collapse;width:100%;font-size:.92rem}
thead th{text-align:left;padding:9px 12px;font-size:.72rem;letter-spacing:.02em;text-transform:uppercase;background:var(--ink);color:#fff}
tbody td{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}
tbody tr:last-child td{border-bottom:none}
.grade-cell{font-weight:700;white-space:nowrap;width:1%}
.time-main{font-weight:600;white-space:nowrap}
.time-sub{color:var(--wed);font-weight:600;white-space:nowrap}
tr.is-highlight td{background:var(--hl-bg)}
tr.is-highlight .grade-cell{border-left:3px solid var(--hl-border);padding-left:9px}
.flag{display:inline-block;margin-left:6px;font-size:.66rem;font-weight:800;color:#7a5b00;background:#ffe9a3;padding:2px 6px;border-radius:5px;vertical-align:middle}
.callout{margin:18px 0 0;padding:12px 14px;background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:8px;font-size:.92rem}
.callout h2{margin:0 0 6px;font-size:.95rem}
.callout p{margin:4px 0}
.wed-badge{display:inline-block;font-size:.72rem;font-weight:700;padding:3px 9px;border-radius:999px;color:var(--wed);background:var(--wed-bg);margin-right:6px}
footer{margin-top:16px;font-size:.8rem;color:var(--sub)}
footer p{margin:4px 0}
a.src{color:var(--accent);font-weight:600}
a.src:focus-visible{outline:3px solid #f0a055;outline-offset:2px}
.sffs-fade{position:fixed;left:0;right:0;bottom:0;height:58px;z-index:8;pointer-events:none;background:linear-gradient(to bottom,rgba(255,255,255,0),#fff 72%);border-radius:0 0 12px 12px}
.sffs-hint{position:fixed;left:50%;bottom:12px;transform:translateX(-50%);z-index:9;pointer-events:none;white-space:nowrap;font:600 12px/1 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--accent);background:var(--accent-light);border:1px solid #d6dff5;padding:7px 13px;border-radius:999px;box-shadow:0 1px 5px rgba(0,0,0,.13)}
.sffs-fade[hidden],.sffs-hint[hidden]{display:none}
/* Narrow frames (the card box on a phone): one card per grade, both times stacked, no sideways scrolling */
@media (max-width:530px){
  .wrap{padding:12px 12px 52px}
  h1{font-size:1.1rem}
  .sub{font-size:.78rem;margin-bottom:8px}
  .lead{padding:8px 12px;margin-bottom:10px}
  .lead .who{margin-bottom:2px}
  .lead p{font-size:.92rem;display:block;white-space:nowrap}
  .lead .k{display:inline;margin-right:6px}
  h2{font-size:.95rem;margin:12px 0 6px}
  .table-scroll{border:none;border-radius:0;overflow:visible}
  thead{display:none}
  table,tbody,tr{display:block;width:100%}
  table{font-size:1rem}
  tbody tr{border:1px solid var(--line);border-radius:12px;padding:9px 12px;margin-bottom:8px;background:#fff}
  tbody tr.is-highlight{background:var(--hl-bg);border-color:var(--hl-border)}
  tbody tr.is-highlight td{background:transparent}
  tbody td{display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding:2px 0;border:none}
  tbody td.grade-cell{display:block;width:auto;font-size:1.02rem;border-left:none;padding-left:0;margin-bottom:4px;white-space:normal}
  tbody td.time-main::before{content:"Regular";color:var(--sub);font-weight:600;font-size:.85rem}
  tbody td.time-sub::before{content:"Wednesday";color:var(--sub);font-weight:600;font-size:.85rem}
}
</style>
</head>
<body>
<div class="wrap" id="wrap">
  <h1 id="title">School Hours &amp; Early Dismissal</h1>
  <p class="sub" id="sub"></p>
  <div class="lead" id="lead" hidden></div>
  <h2 id="table-h">Regular hours &amp; Wednesday early dismissal, by grade</h2>
  <div class="table-scroll" role="region" aria-labelledby="table-h">
    <table>
      <thead><tr><th>Grade</th><th>Regular school hours</th><th>Wednesday early dismissal</th></tr></thead>
      <tbody id="rows"></tbody>
    </table>
  </div>
  <div class="callout"><h2>Building hours</h2><div id="building"></div></div>
  <footer id="foot"></footer>
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
  var DATA = {{DATA}};

  /* Text only (textContent), never innerHTML with data. */
  function el(tag, cls, text){ var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function span(a, b){ return a + ' – ' + b; }

  /* Class and grade from the address (CLAUDE.md section 1): ?class=2034, optional ?grade= preview, ?today= for tests. */
  var ci = SFFS.classInfo(location.search);
  var mine = null;
  if (ci.status === 'ok') {
    for (var i = 0; i < DATA.rows.length; i++) if (DATA.rows[i].grades.indexOf(ci.grade) >= 0) mine = DATA.rows[i];
  }
  var src = DATA.source;
  /* One short line: the class, or where the hours come from. The full citation is in the footer. */
  document.getElementById('sub').textContent = ci.cls ? ci.heading : 'From the ' + src.title + ', ' + src.section.split(':')[0] + '.';

  /* The viewer's own hours first, so a phone shows them without scrolling. */
  var lead = document.getElementById('lead');
  if (mine) {
    lead.appendChild(el('p', 'who', ci.gradeName + (ci.preview ? ' (preview)' : '') + ' · this class'));
    var p1 = el('p'); p1.appendChild(el('span', 'k', 'Regular')); p1.appendChild(el('span', 'v', span(mine.regular.start, mine.regular.end))); lead.appendChild(p1);
    var p2 = el('p'); p2.appendChild(el('span', 'k', 'Wednesdays')); p2.appendChild(el('span', 'v', span(mine.wednesday.start, mine.wednesday.end))); lead.appendChild(p2);
    lead.hidden = false;
  }

  var tbody = document.getElementById('rows');
  DATA.rows.forEach(function(r){
    var tr = el('tr');
    var g = el('td', 'grade-cell', r.label);
    if (r === mine) { tr.className = 'is-highlight'; g.appendChild(el('span', 'flag', 'THIS CLASS')); tr.setAttribute('aria-current', 'true'); }
    tr.appendChild(g);
    tr.appendChild(el('td', 'time-main', span(r.regular.start, r.regular.end)));
    tr.appendChild(el('td', 'time-sub', span(r.wednesday.start, r.wednesday.end)));
    tbody.appendChild(tr);
  });

  var b = document.getElementById('building');
  DATA.building.forEach(function(x){ var p = el('p'); p.appendChild(el('strong', null, x.label + ': ')); p.appendChild(document.createTextNode(x.text)); b.appendChild(p); });

  var foot = document.getElementById('foot');
  var n0 = el('p'); n0.appendChild(el('span', 'wed-badge', 'Wednesdays')); n0.appendChild(document.createTextNode(DATA.notes[0])); foot.appendChild(n0);
  var cite = el('p', null, 'Source: ' + src.title + ', ' + src.section + ', p. ' + src.page + '. Updated ' + src.updated + '. ');
  var a = el('a', 'src', 'View the Family Handbook'); a.href = src.url; a.target = '_blank'; a.rel = 'noopener'; cite.appendChild(a);
  foot.appendChild(cite);
  for (var k = 1; k < DATA.notes.length; k++) foot.appendChild(el('p', null, DATA.notes[k]));

  /* Scroll affordance: Sites lays the iframe out late, so re-check after load and on resize. */
  var w = document.getElementById('wrap'), h = document.getElementById('hint'), f = document.getElementById('fade');
  function upd(){ var more = w.scrollHeight - w.clientHeight - w.scrollTop > 8; h.hidden = !more; f.hidden = !more; }
  w.addEventListener('scroll', upd, {passive: true});
  window.addEventListener('resize', upd);
  if (window.ResizeObserver) new ResizeObserver(upd).observe(w);
  upd(); setTimeout(upd, 120); setTimeout(upd, 600);
})();
</script>
</body>
</html>
"""


def load():
    raw = SRC.read_bytes()
    data = json.loads(raw)
    if data.get("schema") != 1 or not data.get("rows") or not data.get("source"):
        raise SystemExit("school-hours/data.json: expected schema 1 with rows and source")
    return data, raw


def build(data, raw):
    version = f"{data['source']['updated_iso']}.{hashlib.sha256(raw).hexdigest()[:8]}"
    page = (PAGE.replace("{{VERSION}}", version)
                .replace("{{CLASS_JS}}", classinfo.class_js())
                .replace("{{LANG_JS}}", classinfo.lang_js())
                .replace("{{DATA}}", json.dumps({k: v for k, v in data.items() if not k.startswith("_")}, ensure_ascii=False)
                         .replace("</", "<\\/")))
    return page, version


def main():
    data, raw = load()
    page, version = build(data, raw)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(page)
    print(f"school-hours@{version} -> {OUT / 'index.html'} ({len(page)} bytes)")


if __name__ == "__main__":
    main()
