#!/usr/bin/env python3
"""Check every site in registry.yaml and write the status page.

Plain HTTP, no browser: fetches each published Site page and looks for each slot's embed,
either by its Pages URL (URL embed) or by its `match` text inside pasted code. Also checks
each shared embed on Pages. Clicking inside embeds is tests/live_check.py's job.

Embeds with `type: code` live only as pasted code on a Site (no Pages copy), e.g. one that
holds personal data. They skip the Pages check; their slots (`status: code`) are green when
the pasted code is there and matches the recorded hash.

Writes _site/status/index.html and status.json. Never fails the build; prints
status=green|amber|red to $GITHUB_OUTPUT for the alert job (red alerts, amber doesn't).
"""
import datetime as dt
import hashlib
import html
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "_site" / "status"
PAGES = "https://sffs-class-sites.github.io/class-sites/"
RANK = {"green": 0, "amber": 1, "red": 2}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "sffs-class-sites-monitor"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # DNS, timeout
        return 0, str(e)


def worst(states):
    return max(states, key=RANK.get, default="green")


def check_embed(eid, emb, today):
    if emb.get("type") == "code":
        return {"id": eid, "url": None, "state": "green", "version": None, "notes": ["pasted code only; nothing on Pages"]}
    url = PAGES + emb["path"]
    code, body = fetch(url)
    m = re.search(r'name="sffs-embed" content="([^"]+)"', body)
    if code != 200 or not m:
        return {"id": eid, "url": url, "state": "red", "version": None, "notes": [f"Pages returned {code or 'no answer'}"]}
    notes, state = [], "green"
    dcode, dbody = fetch(url + "data.json")
    if dcode == 200:
        events = json.loads(dbody).get("events", [])
        last = max((e.get("end") or e["date"] for e in events), default=None)
        if last and last < today.isoformat():
            state = "amber"
            notes.append(f"every date is past (last {last}); next year's calendar isn't loaded")
    return {"id": eid, "url": url, "state": state, "version": m.group(1), "notes": notes}


def check_slot(slot, emb, page_html):
    url_found = bool(emb.get("path")) and (PAGES + emb["path"]).split("://", 1)[1] in page_html
    codes = [html.unescape(c) for c in re.findall(r'data-code="([^"]*)"', page_html)]
    pasted = [c for c in codes if emb.get("match") and emb["match"] in c]
    digest = hashlib.sha256(pasted[0].encode()).hexdigest()[:12] if pasted else None
    want = slot.get("status")
    if emb.get("type") == "code":
        if not pasted:
            return "red", "embed not found on the page", None
        if slot.get("hash") and slot["hash"] != digest:
            return "amber", f"pasted code edited since it was recorded (hash {digest}, recorded {slot['hash']})", digest
        return "green", "pasted code in place (by design)", digest
    if url_found:
        if want == "url":
            return "green", "URL embed in place", digest
        return "amber", "now a URL embed: set status: url in registry.yaml", digest
    if pasted:
        if want == "url":
            return "amber", "registry says URL embed, but the Site still has the pasted copy", digest
        if slot.get("hash") and slot["hash"] != digest:
            return "amber", f"pasted copy, edited since it was recorded (hash {digest}, recorded {slot['hash']})", digest
        return "amber", "old pasted copy: swap to the URL embed (§8 step 4)", digest
    return "red", "embed not found on the page", None


def run(reg, today):
    embeds = {eid: check_embed(eid, e, today) for eid, e in reg["embeds"].items()}
    sites = []
    for sid, s in reg["sites"].items():
        slots, pages = [], {}
        for slot in s.get("slots", []):
            purl = s["live"].rstrip("/") + "/" + slot["page"]
            if purl not in pages:
                pages[purl] = fetch(purl)
            code, body = pages[purl]
            emb = reg["embeds"][slot["embed"]]
            if code != 200:
                state, note, digest = "red", f"page returned {code or 'no answer'}", None
            else:
                state, note, digest = check_slot(slot, emb, body)
            if embeds[slot["embed"]]["state"] == "red" and state == "green":
                state, note = "red", "URL embed in place, but the embed itself is down on Pages"
            slots.append({"page": slot["page"], "url": purl, "embed": slot["embed"], "state": state, "note": note, "hash": digest})
        done = sum(1 for x in slots if x["state"] == "green")
        sites.append({"id": sid, "name": s["name"], "kind": s.get("kind", "class"), "live": s["live"],
                      "state": worst(x["state"] for x in slots), "done": done, "total": len(slots), "slots": slots})
    overall = worst([x["state"] for x in sites] + [e["state"] for e in embeds.values()])
    return {"checked": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "state": overall,
            "sites": sites, "embeds": list(embeds.values())}


def ball(done, total):
    """Harvey ball: share of a site's slots that are healthy (URL embeds, or pasted code by design), in quarters."""
    q = round(4 * done / total) if total else 0
    paths = {0: "", 1: "M12 12V3A9 9 0 0 1 21 12Z", 2: "M12 12V3A9 9 0 0 1 12 21Z",
             3: "M12 12V3A9 9 0 1 1 3 12Z", 4: '<circle cx="12" cy="12" r="9"/>'}
    fill = paths[q] if q == 4 else (f'<path d="{paths[q]}"/>' if q else "")
    return (f'<svg class="ball" viewBox="0 0 24 24" role="img" aria-label="{done} of {total} done">'
            f'<circle cx="12" cy="12" r="9" class="ring"/>{fill}</svg>')


LABEL = {"green": "OK", "amber": "Needs attention", "red": "Broken"}


def page(st):
    e = html.escape
    def dot(s):
        return f'<span class="dot {s}"></span>{LABEL[s]}'
    def item(x):
        return "<li><b>%s</b> · %s: %s</li>" % (e(x["page"]), e(x["embed"]), e(x["note"]))
    site_rows = "".join(
        f'<tr><td><a href="{e(s["live"])}" target="_blank" rel="noopener">{e(s["name"])}</a>'
        f'{" <small>(test)</small>" if s["kind"] == "scratch" else ""}</td>'
        f'<td class="c">{ball(s["done"], s["total"])}<small>{s["done"]}/{s["total"]}</small></td>'
        f'<td>{dot(s["state"])}</td>'
        f'<td><ul>{"".join(item(x) for x in s["slots"])}</ul></td></tr>'
        for s in st["sites"])
    emb_rows = "".join(
        f'<tr><td><a href="{e(x["url"])}" target="_blank" rel="noopener">{e(x["id"])}</a></td><td>{dot(x["state"])}</td>'
        f'<td><code>{e(x["version"] or "-")}</code></td><td>{e("; ".join(x["notes"]) or "-")}</td></tr>'
        for x in st["embeds"] if x["url"])
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>Class Sites Status</title>
<style>
:root{{--ink:#1f2937;--sub:#5b6472;--line:#e2e5ea;--bg:#fff;--panel:#f7f8fa;--accent:#3457a6;--green:#1a7f5a;--amber:#b4720a;--red:#c0392b}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--ink:#e5e7eb;--sub:#9ca3af;--line:#374151;--bg:#111827;--panel:#1f2937;--accent:#93b0f0;--green:#4ade80;--amber:#fbbf24;--red:#f87171}}}}
:root[data-theme="dark"]{{--ink:#e5e7eb;--sub:#9ca3af;--line:#374151;--bg:#111827;--panel:#1f2937;--accent:#93b0f0;--green:#4ade80;--amber:#fbbf24;--red:#f87171}}
*{{box-sizing:border-box}}
body{{margin:0;padding:24px 16px;background:var(--bg);color:var(--ink);font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
main{{max-width:980px;margin:0 auto}}
h1{{font-size:1.4rem;margin:0 0 4px}} h2{{font-size:1.05rem;margin:28px 0 8px}}
.meta{{color:var(--sub);margin:0 0 16px}}
.overall{{display:inline-flex;gap:8px;align-items:center;font-weight:700;padding:8px 14px;border-radius:999px;background:var(--panel);border:1px solid var(--line)}}
.wrap{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse}}
th,td{{text-align:left;vertical-align:top;padding:10px 8px;border-bottom:1px solid var(--line)}}
th{{font-size:.8rem;color:var(--sub);font-weight:600}}
td.c{{white-space:nowrap}} td ul{{margin:0;padding-left:18px}}
a{{color:var(--accent)}}
.dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}}
.dot.green{{background:var(--green)}}.dot.amber{{background:var(--amber)}}.dot.red{{background:var(--red)}}
.ball{{width:22px;height:22px;vertical-align:middle;margin-right:6px;fill:var(--accent)}} .ball .ring{{fill:none;stroke:var(--accent);stroke-width:2}}
small{{color:var(--sub)}} code{{font-size:.8rem}}
.legend{{color:var(--sub);font-size:.85rem;margin-top:24px}}
@media (max-width:600px){{th:nth-child(4),td:nth-child(4){{min-width:220px}}}}
</style></head>
<body><main>
<h1>Class sites status</h1>
<p class="meta">Checked {e(st["checked"])}. Updated daily and on every change to the repo.</p>
<p class="overall">{dot(st["state"])}</p>
<h2>Sites</h2>
<div class="wrap"><table><thead><tr><th>Site</th><th>On URL embeds</th><th>Status</th><th>Details</th></tr></thead><tbody>{site_rows}</tbody></table></div>
<h2>Shared embeds</h2>
<div class="wrap"><table><thead><tr><th>Embed</th><th>Status</th><th>Version</th><th>Notes</th></tr></thead><tbody>{emb_rows}</tbody></table></div>
<p class="legend">The ball fills as a site's embed slots become healthy: URL embeds, or pasted code where that's by design (empty = none, full = all).
<b>Needs attention</b> means it works but has a to-do, such as an old pasted copy. <b>Broken</b> opens an issue for Ahin.</p>
</main></body></html>
"""


def main():
    reg = yaml.safe_load((ROOT / "registry.yaml").read_text())
    today = dt.date.fromisoformat(os.environ["MONITOR_TODAY"]) if os.environ.get("MONITOR_TODAY") else dt.date.today()
    st = run(reg, today)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(page(st))
    (OUT / "status.json").write_text(json.dumps(st, indent=2))
    lines = [f"Monitor: {st['state'].upper()} ({st['checked']})"]
    for s in st["sites"]:
        lines += [f"  {s['state']:5} {s['name']}: " + "; ".join(x["note"] for x in s["slots"])]
    for x in st["embeds"]:
        lines += [f"  {x['state']:5} embed {x['id']} {x['version']} {'; '.join(x['notes'])}"]
    print("\n".join(lines))
    if os.environ.get("GITHUB_OUTPUT"):
        broken = [f"{s['name']}: {x['note']}" for s in st["sites"] for x in s["slots"] if x["state"] == "red"]
        broken += [f"embed {x['id']}: {'; '.join(x['notes'])}" for x in st["embeds"] if x["state"] == "red"]
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"status={st['state']}\nbroken={' | '.join(broken)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
