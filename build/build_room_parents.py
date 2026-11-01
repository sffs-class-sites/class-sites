#!/usr/bin/env python3
"""Build the Room Parents embed: _site/shared/room-parents/index.html.

Pattern A (CLAUDE.md §3): no names are baked into the page or committed. At view time
the page reads ?class=YYYY and fetches DATA_URL, a small extract written at deploy time
by build/extract_room_parents.py from the sheet's protected Live tab.

Kept in three parts so pattern B (signed-in viewers, Apps Script data source) only swaps
loadData(): loadData() fetches, pick() selects one class, render() draws. The JSON shape
is the contract and must stay stable:

  {"schema": 1, "updated": "<ISO time>", "classes": {"2034": [{"name": "...", "email": "..."}]}}
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import classinfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "_site" / "shared" / "room-parents"

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="sffs-embed" content="room-parents@1">
<meta name="robots" content="noindex">
<title>Room Parents</title>
<style>
:root{--ink:#1f2937;--sub:#5b6472;--line:#e2e5ea;--bg:#fff;--panel:#f7f8fa;--accent:#3457a6;--accent-light:#eaeffb;--warn:#b4720a;--warn-bg:#fdf3e0}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg);line-height:1.45}
.wrap{height:100%;overflow-y:auto;overscroll-behavior:contain;border:2px solid #d6dff5;border-radius:12px;padding:16px}
h1{font-size:1.25rem;margin:0 0 2px}
.sub{color:var(--sub);font-size:.88rem;margin:0 0 14px}
ul{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}
li{border:1px solid var(--line);border-radius:12px;padding:12px 14px;background:var(--panel);min-width:0}
.name{font-weight:700;margin:0 0 4px;overflow-wrap:anywhere}
.email{color:var(--accent);font-weight:600;font-size:.9rem;text-decoration:none;overflow-wrap:anywhere}
.email:hover{text-decoration:underline}
.msg{padding:14px;border-radius:12px;background:var(--panel);border:1px solid var(--line);color:var(--sub)}
.msg.warn{background:var(--warn-bg);border-color:#f1d9a8;color:#6b4a07}
.btn{margin-top:10px;font:inherit;font-weight:600;font-size:.85rem;padding:7px 12px;border-radius:999px;border:1px solid var(--line);background:#fff;color:var(--accent);cursor:pointer}
.btn:focus-visible,.email:focus-visible{outline:3px solid #f0a055;outline-offset:2px}
.skel{height:64px;border-radius:12px;background:linear-gradient(90deg,var(--panel),#eef0f3,var(--panel));background-size:200% 100%;animation:sh 1.2s infinite}
@keyframes sh{to{background-position:-200% 0}}
@media (prefers-reduced-motion:reduce){.skel{animation:none}}
footer{margin-top:14px;color:var(--sub);font-size:.78rem}
@media (max-width:420px){.wrap{padding:12px}h1{font-size:1.1rem}ul{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap" id="wrap">
  <h1 id="title">Room parents</h1>
  <p class="sub" id="sub">Your class's volunteer contacts.</p>
  <div id="body" aria-live="polite"><ul aria-hidden="true"><li class="skel"></li><li class="skel"></li></ul></div>
  <footer id="foot"></footer>
</div>
<script>
{{CLASS_JS}}
</script>
<script>
(function(){
  var DATA_URL = '../../data/room-parents.json';

  /* 1. Fetch. Pattern B replaces only this function. Resolves {status, data}. */
  function loadData(){
    return fetch(DATA_URL, {cache: 'no-cache'}).then(function(r){
      if (r.status === 404) return {status: 'unpublished'};
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json().then(function(d){
        if (!d || d.schema !== 1 || typeof d.classes !== 'object') throw new Error('unexpected data');
        return {status: 'ok', data: d};
      });
    });
  }

  /* 2. Select one class. */
  function pick(data, cls){ return (data.classes && data.classes[cls]) || []; }

  /* 3. Render. Text only (textContent), never innerHTML with data. */
  var body = document.getElementById('body');
  function el(tag, cls, text){ var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function message(text, warn, retry){
    body.textContent = '';
    var m = el('div', 'msg' + (warn ? ' warn' : ''), text);
    if (retry) { var b = el('button', 'btn', 'Try again'); b.type = 'button'; b.addEventListener('click', start); m.appendChild(el('br')); m.appendChild(b); }
    body.appendChild(m);
  }
  function render(people, updated){
    body.textContent = '';
    if (!people.length) { message('No room parents are listed for this class yet.'); return; }
    var ul = el('ul');
    people.forEach(function(p){
      var li = el('li');
      li.appendChild(el('p', 'name', p.name));
      if (p.email) {
        var a = el('a', 'email', p.email);
        a.href = 'mailto:' + encodeURIComponent(p.email).replace(/%40/g, '@');
        a.target = '_blank'; a.rel = 'noopener';
        li.appendChild(a);
      }
      ul.appendChild(li);
    });
    body.appendChild(ul);
    if (updated) document.getElementById('foot').textContent = 'Updated ' + new Date(updated).toLocaleDateString(undefined, {month: 'long', day: 'numeric', year: 'numeric'}) + '.';
  }

  /* Class and grade from the address (CLAUDE.md section 1): ?class=2034, optional ?grade= preview. */
  var ci = SFFS.classInfo(location.search);
  var cls = ci.cls && String(ci.cls);
  if (cls) {
    document.getElementById('title').textContent = (ci.status === 'ok' ? ci.gradeName + ' room parents' : 'Class of ' + cls + ' room parents');
    document.getElementById('sub').textContent = ci.heading + " \u00b7 your class's volunteer contacts.";
  }

  function start(){
    if (!cls) { message('This embed needs a class in its address, for example ?class=2034.', true); return; }
    body.innerHTML = '<ul aria-hidden="true"><li class="skel"></li><li class="skel"></li></ul>';
    var slow = setTimeout(function(){ document.getElementById('sub').textContent = 'Still loading…'; }, 4000);
    loadData().then(function(res){
      clearTimeout(slow);
      document.getElementById('sub').textContent = ci.heading + " \u00b7 your class's volunteer contacts.";
      if (res.status === 'unpublished') { message('Room parent contacts haven’t been published yet.'); return; }
      render(pick(res.data, cls), res.data.updated);
    }).catch(function(){
      clearTimeout(slow);
      message('Couldn’t load room parent contacts. Check your connection and try again.', true, true);
    });
  }
  start();
})();
</script>
</body>
</html>
"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    page = PAGE.replace("{{CLASS_JS}}", classinfo.class_js())
    (OUT / "index.html").write_text(page)
    print(f"room-parents -> {OUT / 'index.html'} ({len(page)} bytes)")


if __name__ == "__main__":
    main()
