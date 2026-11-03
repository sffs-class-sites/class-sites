#!/usr/bin/env python3
"""Check tools/sites_editor.py against a fake editor, since the real one needs a signed-in Chrome.

Serves a mock Sites editor built to the markup recorded on the real editor on 2026-11-02
(docs/sites-editor-driver.md §4): a Pages tab and tree, one `div[aria-label="Whole page
embed"][data-url]` per URL embed with our real Pages page inside a wrapper iframe, a
`div[role=gridcell][aria-label="IFRAME"]` that gets aria-selected on a corner click, a
bottom-centre resize handle that only works while selected and snaps to an 8px grid, and a
Publish button that opens a dialog with Cancel and Publish. Launches a Chromium with
--remote-debugging-port and runs every command against it the way they run on the Mac.

This proves the script's logic (attach, navigate, find, measure, select, the drag loop, the
publish dialog) and nothing about the real editor; that is recorded in the doc.

    PW_CHROMIUM=/path/to/chrome python3 tests/test_sites_editor.py     # needs network for the Pages embeds
"""
import contextlib
import http.server
import io
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
PAGES = "https://sffs-class-sites.github.io/class-sites/"
SITE_ID = "1vqA_IFOx0oCDUi95RtQ-PPo-3LcD_szY"   # class-2034 in registry.yaml

EDITOR_JS = """
// Selection: a mousedown on the block (outside the iframe) selects its gridcell; elsewhere deselects.
document.addEventListener('mousedown', e => {
  const cell = e.target.closest('[role=gridcell]');
  for (const c of document.querySelectorAll('[role=gridcell]')) {
    const on = c === cell;
    c.setAttribute('aria-selected', on); c.setAttribute('aria-grabbed', on);
    c.style.outline = on ? '2px solid #1a73e8' : 'none';
    c.querySelector('.handle').style.display = on ? 'block' : 'none';
  }
  if (cell && !e.target.closest('.handle')) document.getElementById('published').textContent = 'edited';
});
// Resize: dragging within 12px of the bottom centre of a *selected* block's iframe changes its height, snapped to 8px.
let drag = null;
document.addEventListener('mousedown', e => {
  for (const cell of document.querySelectorAll('[role=gridcell][aria-selected=true]')) {
    const f = cell.querySelector('iframe'), r = f.getBoundingClientRect();
    if (Math.abs(e.clientX - (r.x + r.width / 2)) < 12 && Math.abs(e.clientY - (r.y + r.height)) < 12)
      drag = {f, h0: r.height, y0: e.clientY};
  }
});
document.addEventListener('mousemove', e => {
  if (drag) drag.f.style.height = (Math.round((drag.h0 + e.clientY - drag.y0) / 8) * 8) + 'px';
});
document.addEventListener('mouseup', () => { if (drag) document.getElementById('published').textContent = 'edited'; drag = null; });
// Publish: a dialog with Cancel and Publish.
function openPublish() {
  const d = document.getElementById('dlg'); d.style.display = 'block';
}
function confirmPublish() {
  document.getElementById('dlg').style.display = 'none';
  document.getElementById('published').textContent = 'published ' + document.querySelector('[data-url*=room-parents] iframe').style.height;
}
"""


def wrapper(url):
    return f"<!doctype html><html><body style='margin:0'><iframe src='{url}' style='width:100%;height:100%;border:0'></iframe></body></html>"


def editor_page(page_id):
    if page_id == "home":
        blocks = [("important-dates", PAGES + "shared/important-dates/", 935, 625),
                  ("room-parents", PAGES + "shared/room-parents/?class=2034", 935, 549)]
    else:
        blocks = [("updates", PAGES + "shared/updates/?class=2034", 935, 875)]
    canvas = "".join(
        f"<div role='gridcell' aria-label='IFRAME' aria-selected='false' aria-grabbed='false' tabindex='-1' style='position:relative;margin:24px auto;width:{w}px'><div class='handle' style='display:none;position:absolute;left:50%;bottom:-7px;width:14px;height:14px;margin-left:-7px;border-radius:50%;background:#1a73e8;z-index:2'></div>"
        f"<div><div aria-label='Whole page embed' data-url='{u}'>"
        f"<iframe src='/wrap?u={u}' sandbox='allow-scripts allow-same-origin allow-popups allow-forms' "
        f"style='display:block;width:{w}px;height:{h}px;border:0;pointer-events:none'></iframe></div></div></div>" for u_eid, u, w, h in [(b[0], b[1], b[2], b[3]) for b in blocks])
    return f"""<!doctype html><html><head><title>mock editor</title></head><body style='margin:0;font-family:sans-serif'>
<div style='display:flex;align-items:center;gap:12px;padding:6px'>
 <a aria-label='Google Account: SFFS Class Pages&#10;(classpages@sffriendsschool.org)' href='#'>CP</a>
 <div role='button' guidedhelpid='at-appbar-publish' data-tooltip='Publish' onclick='openPublish()' style='padding:4px 8px;border:1px solid #888'>Publish</div>
 <span id='published'>clean</span>
</div>
<div role='dialog' id='dlg' style='display:none;z-index:10;position:fixed;top:100px;left:300px;padding:20px;background:#fff;border:1px solid #333'>
 <p>Review changes and publish</p>
 <div role='button' onclick="document.getElementById('dlg').style.display='none'">Cancel</div>
 <div role='button' onclick='confirmPublish()'>Publish</div>
</div>
<div style='display:flex'>
 <main style='flex:1'>{canvas}<footer style='height:900px'>footer (the real editor has one too, so the canvas can scroll past the last block)</footer></main>
 <aside style='width:260px'>
  <div role='tablist'><div role='tab' aria-label='Pages'>Pages</div></div>
  <div role='tree'>
   <div role='treeitem' aria-selected='{str(page_id == "home").lower()}' onclick="if (!location.pathname.includes('/p/home/')) location.href='/d/{SITE_ID}/p/home/edit'"><div>Home</div></div>
   <div role='treeitem' aria-selected='{str(page_id != "home").lower()}' onclick="if (!location.pathname.includes('/p/digest/')) location.href='/d/{SITE_ID}/p/digest/edit'"><div>Email Digest</div></div>
  </div>
 </aside>
</div>
<script>{EDITOR_JS}</script>
</body></html>"""


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        from urllib.parse import urlsplit, parse_qs
        u = urlsplit(self.path)
        if u.path == f"/d/{SITE_ID}/edit":
            self.send_response(302); self.send_header("Location", f"/d/{SITE_ID}/p/home/edit"); self.end_headers(); return
        if u.path.startswith(f"/d/{SITE_ID}/p/"):
            body = editor_page(u.path.split("/")[4])
        elif u.path == "/wrap":
            body = wrapper(parse_qs(u.query)["u"][0])
        else:
            self.send_error(404); return
        data = body.encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    port, cdp_port = free_port(), free_port()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    chrome = os.environ.get("PW_CHROMIUM")
    if not chrome:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            chrome = pw.chromium.executable_path
    profile = tempfile.mkdtemp(prefix="sites-editor-mock-")
    proc = subprocess.Popen([chrome, f"--remote-debugging-port={cdp_port}", f"--user-data-dir={profile}", "--headless=new",
                             "--no-sandbox", "--no-first-run", "--window-size=1600,1000", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    problems = []
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json/version", timeout=1); break
            except Exception:
                time.sleep(0.2)
        os.environ["SITES_EDITOR_ORIGIN"] = f"http://127.0.0.1:{port}"
        import sites_editor
        sites_editor.PACE_MS = 200

        def run(argv, expect_code, *wants):
            buf, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                code = sites_editor.main(["--cdp", f"http://127.0.0.1:{cdp_port}"] + argv)
            out = buf.getvalue() + err.getvalue()
            print(out)
            if code != expect_code:
                problems.append(f"{' '.join(argv)}: exit {code}, expected {expect_code}")
            for w in wants:
                if w not in out:
                    problems.append(f"{' '.join(argv)}: missing {w!r}")
            return out

        run(["tabs"], 0, "context 0")
        out = run(["list", "--site", "class-2034", "--page", "home", "--select", "--dump"], 0,
                  "classpages@sffriendsschool.org", "935 × 625 (h/w 0.668)", "935 × 549 (h/w 0.587)", "registry box card",
                  "with this data-url; our page is in Playwright's frame tree", "DOM record written", "pages tree",
                  "selected room-parents by a corner click: editor marks it selected = True")
        if "updates" in out.split("signed in as")[1]:
            problems.append("list home: updates (on the other page) was listed")
        run(["list", "--site", "class-2034", "--page", "email-digest"], 0,
            "using the open editor tab", "935 × 875 (h/w 0.936)", "registry box page")
        # resize: dry run reads and plans; --apply drags until the shape is right; a second run has nothing to do.
        run(["resize", "--site", "class-2034", "--page", "home", "--embed", "room-parents", "--box", "card"], 0,
            "before: 935 × 549 (h/w 0.587)", "by +76px", "dry run only")
        run(["resize", "--site", "class-2034", "--page", "home", "--embed", "room-parents", "--box", "card", "--apply"], 0,
            "drag 1:", "after: 935 × 624 (h/w 0.667)", "not published")
        run(["resize", "--site", "class-2034", "--page", "home", "--embed", "room-parents", "--box", "card", "--apply"], 0,
            "already at the target shape")
        run(["resize", "--site", "class-2034", "--page", "home", "--embed", "updates", "--box", "card"], 1,
            "doesn't list updates")
        # publish: dry run finds the button; --apply clicks it, confirms in the dialog, and the mock records the new height.
        run(["publish", "--site", "class-2034"], 0, "Publish button found: 'Publish'", "dry run only")
        out = run(["publish", "--site", "class-2034", "--apply"], 0, "buttons ['Cancel', 'Publish']", "published.")
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}")
            pg = next(p for p in b.contexts[0].pages if "/p/home/" in p.url)
            state = pg.evaluate("() => document.getElementById('published').textContent")
            if state != "published 624px":
                problems.append(f"mock state after publish: {state!r}, expected 'published 624px'")
        run(["list", "--site", "nope"], 1, "no site `nope`")
    finally:
        proc.terminate()
        srv.shutdown()
    if problems:
        print("PROBLEMS:\n  " + "\n  ".join(problems))
        return 1
    print("sites_editor mock test: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
