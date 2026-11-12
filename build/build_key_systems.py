#!/usr/bin/env python3
"""Build the Key School Systems embed: _site/shared/key-systems/index.html.

An index of the school's third-party systems (Veracross, Choicelunch, Vidigami, ...): name,
what it is for, and the link. Content is shared/key-systems/data.json, which holds no
personal data, so it lives in git and is inlined into the page. School-wide: no ?class=.

A whole-page embed (Ahin, 2026-11-12): it is placed alone on its own Site page at the `page`
box (registry.yaml), in the same card style as the other shared embeds. The first version drew
a Sites-style collapsible header to sit among the Resources page's collapsible groups, but a
frame cannot change height, so closing it left its box blank; that version is gone. Like
every shared embed it also works at the `card` box on a phone (CLAUDE.md section 5).

Style (Ahin, 2026-11-12): after a colon the next word starts with a capital letter
("Tuition and fees: Every SFFS bill ..."). load() refuses a name or description that breaks it.

A <meta name="sffs-embed"> marker carries id@version for the monitor: the data's `updated`
date plus a hash of the file, so any edit changes the version.
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
SRC = ROOT / "shared" / "key-systems" / "data.json"
OUT = ROOT / "_site" / "shared" / "key-systems"

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="sffs-embed" content="key-systems@{{VERSION}}">
<meta name="robots" content="noindex">
<title>{{TITLE}}</title>
<style>
:root{--ink:#1f2937;--sub:#5b6472;--line:#e2e5ea;--bg:#fff;--hover:#f3f6fc;--accent:#3457a6;--accent-light:#eaeffb}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg);line-height:1.45}
.wrap{height:100%;overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;border:2px solid #d6dff5;border-radius:12px;padding:16px 16px 56px}
h1{font-size:1.25rem;margin:0 0 2px}
.sub{color:var(--sub);font-size:.88rem;margin:0 0 12px}
ul{list-style:none;margin:0;padding:0;border:1px solid var(--line);border-radius:10px;overflow:hidden}
li{border-bottom:1px solid var(--line)}
li:last-child{border-bottom:0}
a.sys{display:grid;grid-template-columns:minmax(200px,30%) 1fr;column-gap:20px;padding:11px 44px 11px 14px;position:relative;color:var(--ink);text-decoration:none;font-size:.95rem;line-height:1.4}
a.sys:hover{background:var(--hover)}
a.sys:focus-visible{outline:3px solid #f0a055;outline-offset:-3px}
.name{grid-row:1 / span 2;font-weight:700;color:var(--accent);text-decoration:underline;text-underline-offset:2px}
.host{font-size:.8rem;color:var(--sub);margin-top:1px}
.go{position:absolute;right:14px;top:13px;width:18px;height:18px;fill:var(--sub)}
footer{margin-top:14px;font-size:.8rem;color:var(--sub)}
.sffs-fade{position:fixed;left:0;right:0;bottom:0;height:58px;z-index:8;pointer-events:none;background:linear-gradient(to bottom,rgba(255,255,255,0),#fff 72%);border-radius:0 0 12px 12px}
.sffs-hint{position:fixed;left:50%;bottom:12px;transform:translateX(-50%);z-index:9;pointer-events:none;white-space:nowrap;font:600 12px/1 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--accent);background:var(--accent-light);border:1px solid #d6dff5;padding:7px 13px;border-radius:999px;box-shadow:0 1px 5px rgba(0,0,0,.13)}
.sffs-fade[hidden],.sffs-hint[hidden]{display:none}
/* Narrow frames (a phone): one system per block, name over description, no sideways scrolling. */
@media (max-width:530px){
  .wrap{padding:12px 12px 52px}
  h1{font-size:1.1rem}
  .sub{font-size:.78rem;margin-bottom:8px}
  a.sys{display:block;padding:9px 36px 9px 12px;font-size:.95rem}
  .name,.desc{display:block}
  .desc{margin-top:2px;font-size:.88rem;line-height:1.35}
  .host{display:none}
  .go{right:10px;top:11px}
}
/* The narrowest phones (315 x 210 at the card box): drop the subtitle so the first system shows whole. */
@media (max-width:359px){
  .wrap{padding:10px 10px 52px}
  h1{margin-bottom:6px}
  .sub{display:none}
  a.sys{padding:8px 32px 8px 10px}
  .desc{font-size:.84rem;line-height:1.3}
}
</style>
</head>
<body>
<div class="wrap" id="wrap">
  <h1 id="title">{{TITLE}}</h1>
  <p class="sub" id="sub">What each school system is for, and where to sign in.</p>
  <ul id="list" aria-labelledby="title"></ul>
  <footer id="foot"></footer>
</div>
<div class="sffs-fade" id="fade" hidden></div>
<div class="sffs-hint" id="hint" hidden>Scroll for more &#8595;</div>
<script>
{{LANG_JS}}
</script>
<script>
(function(){
  var DATA = {{DATA}};
  var GO = 'M19 19H5V5h7V3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z';

  /* Text only (textContent), never innerHTML with data. */
  function el(tag, cls, text){ var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  /* Each system is one link that opens a new tab: Sites' sandbox has no top-level navigation (CLAUDE.md section 5). */
  var list = document.getElementById('list');
  DATA.systems.forEach(function(s){
    var li = el('li'), a = el('a', 'sys');
    a.href = s.url; a.target = '_blank'; a.rel = 'noopener';
    a.appendChild(el('span', 'name', s.name));
    a.appendChild(el('span', 'desc', s.description));
    a.appendChild(el('span', 'host', s.host));
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24'); svg.setAttribute('class', 'go'); svg.setAttribute('aria-hidden', 'true');
    var path = document.createElementNS('http://www.w3.org/2000/svg', 'path'); path.setAttribute('d', GO); svg.appendChild(path);
    a.appendChild(svg);
    li.appendChild(a); list.appendChild(li);
  });
  document.getElementById('foot').textContent = 'Each link opens in a new tab. List updated ' + DATA.updated_label + '.';

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

PERSONAL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\b\d{3}[-. ]\d{3}[-. ]\d{4}\b|\b\d{3}-\d{4}\b")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def load():
    """Read and validate the data file; any problem stops the build (the previous deploy stays up)."""
    raw = SRC.read_bytes()
    data = json.loads(raw)
    errs = []
    if data.get("schema") != 1:
        errs.append("expected schema 1")
    if not data.get("title"):
        errs.append("title is missing")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(data.get("updated", ""))):
        errs.append("updated must be YYYY-MM-DD")
    systems = data.get("systems") or []
    if not systems:
        errs.append("no systems")
    seen = set()
    for i, s in enumerate(systems, 1):
        tag = f"system {i} ({s.get('name') or 'no name'})"
        extra = set(s) - {"name", "description", "url"}
        if extra:
            errs.append(f"{tag}: unknown field(s) {sorted(extra)}")
        for k in ("name", "description", "url"):
            if not str(s.get(k, "")).strip():
                errs.append(f"{tag}: {k} is empty")
        if s.get("name", "").lower() in seen:
            errs.append(f"{tag}: listed twice")
        seen.add(s.get("name", "").lower())
        u = urlparse(s.get("url", ""))
        if u.scheme != "https" or not u.netloc:
            errs.append(f"{tag}: url must be a full https:// link")
        for k in ("name", "description"):
            for snip in style.colon_issues(s.get(k, "")):
                errs.append(f"{tag}: {k} has a lowercase letter after a colon ({snip}); house style (build/style.py) starts the next word with a capital")
        if len(s.get("description", "")) > 160:
            errs.append(f"{tag}: description is over 160 characters; keep it to one line on a desktop")
    if PERSONAL.search(json.dumps({k: v for k, v in data.items() if k != "_note"})):
        errs.append("looks like an email address or phone number; this file is public and must hold no personal data")
    if errs:
        raise SystemExit("key-systems/data.json:\n  " + "\n  ".join(errs))
    return data, raw


def build(data, raw):
    version = f"{data['updated']}.{hashlib.sha256(raw).hexdigest()[:8]}"
    y, m, d = (int(x) for x in data["updated"].split("-"))
    public = {
        "title": data["title"],
        "updated_label": f"{MONTHS[m - 1]} {d}, {y}",
        "systems": [dict(s, host=urlparse(s["url"]).netloc.removeprefix("www.")) for s in data["systems"]],
    }
    title = data["title"].replace("&", "&amp;").replace("<", "&lt;")
    page = (PAGE.replace("{{VERSION}}", version)
                .replace("{{TITLE}}", title)
                .replace("{{LANG_JS}}", classinfo.lang_js())
                .replace("{{DATA}}", json.dumps(public, ensure_ascii=False).replace("</", "<\\/")))
    return page, version


def main():
    data, raw = load()
    page, version = build(data, raw)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(page)
    print(f"key-systems@{version} -> {OUT / 'index.html'} ({len(page)} bytes, {len(data['systems'])} systems)")


if __name__ == "__main__":
    main()
