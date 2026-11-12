#!/usr/bin/env python3
"""Build the Key School Systems embed: _site/shared/key-systems/index.html.

An index of the school's third-party systems (Veracross, Choicelunch, Vidigami, ...): name,
what it is for, and the link. Content is shared/key-systems/data.json, which holds no
personal data, so it lives in git and is inlined into the page. School-wide: no ?class=.

Made for the Resources page, whose sections are Google Sites collapsible groups. Sites cannot
put an embed inside a collapsible group, so the embed draws its own: a header row in the same
type, colour, chevron and rule as Sites' (measured on the published 1st-grade Resources page,
2026-11-11), closed on load, opening in place. The frame cannot change height (Sites sizes it
from the editor box, CLAUDE.md §5), so a closed embed leaves the rest of its box blank: place
it as the last block on the page. ?open=1 starts it open, for a site that would rather show
the list than the gap.

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
/* Sites' collapsible group on the Resources page: Verdana 24px/36px bold, rgb(0,65,165), 14px 48px 14px 8px padding,
   1px rgb(94,94,94) rule under the header; body text Verdana 16px rgb(28,28,28). */
:root{--head:#0041a5;--ink:#1c1c1c;--sub:#5f6368;--rule:#5e5e5e;--line:#e3e5e8;--hover:#f3f6fc;--accent:#3457a6;--accent-light:#eaeffb}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{overflow:hidden;background:#fff;color:var(--ink);font-family:Verdana,"DejaVu Sans",Geneva,sans-serif}
.wrap{height:100%;display:flex;flex-direction:column}
.head{display:flex;align-items:center;width:100%;margin:0;padding:14px 48px 14px 8px;position:relative;
  background:none;border:0;border-bottom:1px solid var(--rule);border-radius:0;cursor:pointer;text-align:left;font-family:inherit;color:var(--head)}
.hd{flex:0 0 auto;margin:0;font-size:24px;line-height:36px;font-weight:700}
.head{font-size:24px;line-height:36px;font-weight:700}
.head svg{position:absolute;right:14px;top:50%;width:24px;height:24px;margin-top:-12px;fill:#444;transition:transform .15s}
.head[aria-expanded="true"] svg{transform:rotate(180deg)}
.head:focus-visible{outline:3px solid #f0a055;outline-offset:-3px}
.body{flex:1 1 auto;min-height:0;overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;padding:10px 0 48px}
.body[hidden]{display:none}
ul{list-style:none;margin:0;padding:0}
li{border-bottom:1px solid var(--line)}
li:last-child{border-bottom:0}
a.sys{display:block;padding:10px 40px 10px 28px;position:relative;color:var(--ink);text-decoration:none;font-size:16px;line-height:22px}
a.sys:hover{background:var(--hover)}
a.sys:focus-visible{outline:3px solid #f0a055;outline-offset:-3px}
.name{font-weight:700;color:var(--head);text-decoration:underline;text-underline-offset:2px}
.desc{display:block;margin-top:2px}
.host{display:block;margin-top:2px;font-size:13px;line-height:18px;color:var(--sub)}
.go{position:absolute;right:14px;top:12px;width:18px;height:18px;fill:var(--sub)}
footer{padding:10px 28px 0;font-size:12px;line-height:18px;color:var(--sub)}
.sffs-fade{position:fixed;left:0;right:0;bottom:0;height:52px;z-index:8;pointer-events:none;background:linear-gradient(to bottom,rgba(255,255,255,0),#fff 72%)}
.sffs-hint{position:fixed;left:50%;bottom:10px;transform:translateX(-50%);z-index:9;pointer-events:none;white-space:nowrap;font:600 12px/1 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--accent);background:var(--accent-light);border:1px solid #d6dff5;padding:7px 13px;border-radius:999px;box-shadow:0 1px 5px rgba(0,0,0,.13)}
.sffs-fade[hidden],.sffs-hint[hidden]{display:none}
/* Wide frames: name on the left, what it is for on the right, so the whole list fits the desktop card. */
@media (min-width:531px){
  a.sys{display:grid;grid-template-columns:minmax(220px,30%) 1fr;column-gap:20px;padding:9px 44px 9px 28px}
  .name{grid-row:1 / span 2}
  .desc{margin-top:0}
}
/* Phones (the card box is 352 x 235 on an iPhone 13): Sites keeps the header at 24px, so do we; the list tightens. */
@media (max-width:530px){
  .body{padding:4px 0 44px}
  a.sys{padding:8px 34px 8px 8px;font-size:15px;line-height:20px}
  .desc{font-size:14px;line-height:18px}
  .host{display:none}
  .go{right:10px;top:10px}
  footer{padding:8px 8px 0}
}
/* The narrowest phones (315px): one line of header, or the first system drops below the fold. */
@media (max-width:359px){
  .hd,.head{font-size:20px;line-height:30px}
  .head{padding:12px 40px 12px 8px}
  .head svg{right:8px}
}
</style>
</head>
<body>
<div class="wrap" id="wrap">
  <h2 class="hd"><button type="button" class="head" id="head" aria-expanded="false" aria-controls="body"><span id="title">{{TITLE}}</span><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M16.59 8.59 12 13.17 7.41 8.59 6 10l6 6 6-6z"/></svg></button></h2>
  <div class="body" id="body" role="region" aria-labelledby="title" hidden>
    <ul id="list"></ul>
    <footer id="foot"></footer>
  </div>
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

  /* The collapsible header. Buttons only: Sites' sandbox has no top-level navigation (CLAUDE.md section 5). */
  var head = document.getElementById('head'), body = document.getElementById('body');
  function setOpen(open){ head.setAttribute('aria-expanded', open ? 'true' : 'false'); body.hidden = !open; upd(); }
  head.addEventListener('click', function(){ setOpen(head.getAttribute('aria-expanded') !== 'true'); });

  /* Scroll affordance: Sites lays the iframe out late, so re-check after load and on resize. */
  var h = document.getElementById('hint'), f = document.getElementById('fade');
  function upd(){ var more = !body.hidden && body.scrollHeight - body.clientHeight - body.scrollTop > 8; h.hidden = !more; f.hidden = !more; }
  body.addEventListener('scroll', upd, {passive: true});
  window.addEventListener('resize', upd);
  if (window.ResizeObserver) new ResizeObserver(upd).observe(body);

  setOpen(/[?&]open=1(&|$)/.test(location.search));
  setTimeout(upd, 120); setTimeout(upd, 600);
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
