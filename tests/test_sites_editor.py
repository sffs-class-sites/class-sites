#!/usr/bin/env python3
"""Check tools/sites_editor.py's plumbing against a fake editor, since the real one needs a signed-in Chrome.

Serves a mock Sites editor (Pages panel with Home and Email Digest, our real Pages embeds in
wrapper iframes at known box sizes), launches a Chromium with --remote-debugging-port, and
runs `list` against it the way it would run against the Mac's Chrome. This proves: attaching
over CDP, finding or opening the editor tab, the sign-in check, Pages-panel navigation by
title, nested-frame discovery, box measurement and the DOM record. It proves nothing about
the real editor's DOM; that is recorded by hand in docs/sites-editor-driver.md.

    python3 tests/test_sites_editor.py            # needs network for the Pages embeds
    PW_CHROMIUM=/path/to/chrome python3 tests/test_sites_editor.py
"""
import functools
import http.server
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


def wrapper(url):
    return f"<!doctype html><html><body style='margin:0'><iframe src='{url}' style='width:100%;height:100%;border:0'></iframe></body></html>"


def editor_page(page_id):
    """A page of the fake editor: a Pages tree on the right, blocks of our embeds on the canvas."""
    if page_id == "home":
        blocks = [("important-dates", PAGES + "shared/important-dates/", 935, 625),
                  ("room-parents", PAGES + "shared/room-parents/?class=2034", 935, 549)]
    else:
        blocks = [("updates", PAGES + "shared/updates/?class=2034", 935, 875)]
    canvas = "".join(
        f"<div role='region' aria-label='Embed block' data-mock-block='{eid}' style='margin:20px auto;width:{w}px;position:relative;padding-top:6px' "
        f"onclick=\"for (const l of document.querySelectorAll('.lbl')) l.style.display='none'; this.querySelector('.lbl').style.display='block'\">"
        f"<div class='lbl' style='display:none;position:absolute;top:-18px;left:0;font-size:11px'>{w} × {h}</div>"
        f"<iframe src='/wrap?u={u}' sandbox='allow-scripts allow-same-origin allow-popups allow-forms' "
        f"style='width:{w}px;height:{h}px;border:0'></iframe></div>" for eid, u, w, h in blocks)
    return f"""<!doctype html><html><head><title>mock editor</title></head><body style='margin:0;font-family:sans-serif'>
<a aria-label='Google Account: Class Pages (classpages@sffriendsschool.org)' href='#'>CP</a>
<div style='display:flex'>
 <main style='flex:1'>{canvas}</main>
 <aside style='width:260px'>
  <div role='tablist'><div role='tab' aria-label='Pages'>Pages</div></div>
  <div role='tree'>
   <div role='treeitem' aria-selected='{str(page_id == "home").lower()}' onclick="location.href='/d/{SITE_ID}/p/home/edit'"><span>Home</span></div>
   <div role='treeitem' aria-selected='{str(page_id != "home").lower()}' onclick="location.href='/d/{SITE_ID}/p/digest/edit'"><span>Email Digest</span></div>
  </div>
 </aside>
</div></body></html>"""


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
    origin = f"http://127.0.0.1:{port}"
    chrome = os.environ.get("PW_CHROMIUM")
    if not chrome:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            chrome = pw.chromium.executable_path
    profile = tempfile.mkdtemp(prefix="sites-editor-mock-")
    proc = subprocess.Popen([chrome, f"--remote-debugging-port={cdp_port}", f"--user-data-dir={profile}", "--headless=new",
                             "--no-sandbox", "--no-first-run", "--window-size=1600,1000", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json/version", timeout=1); break
            except Exception:
                time.sleep(0.2)
        os.environ["SITES_EDITOR_ORIGIN"] = origin
        import sites_editor
        sites_editor.PACE_MS = 200
        import io, contextlib
        problems = []

        def run(argv):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = sites_editor.main(["--cdp", f"http://127.0.0.1:{cdp_port}"] + argv)
            out = buf.getvalue()
            print(out)
            return code, out

        code, out = run(["tabs"])
        if code != 0:
            problems.append("tabs failed")
        code, out = run(["list", "--site", "class-2034", "--page", "home", "--select", "--dump"])
        if code != 0:
            problems.append(f"list home exit {code}")
        for want in ("classpages@sffriendsschool.org", "important-dates", "room-parents", "935 × 625", "935 × 549",
                     "registry box card", "DOM record written", "pages tree", "(h/w 0.587)",
                     "selected room-parents by clicking top edge of <div {'role': 'region', 'aria-label': 'Embed block', 'data-mock-block': 'room-parents'}>: size label(s) ['935 × 549']"):
            if want not in out:
                problems.append(f"list home: missing '{want}'")
        if "updates" in out.split("signed in as")[1]:
            problems.append("list home: updates (on the other page) was listed")
        # Second run reuses the open editor tab and navigates to the other page.
        code, out = run(["list", "--site", "class-2034", "--page", "email-digest"])
        if code != 0:
            problems.append(f"list email-digest exit {code}")
        for want in ("using the open editor tab", "updates", "935 × 875", "registry box page"):
            if want not in out:
                problems.append(f"list email-digest: missing '{want}'")
        # Dry-run resize reads the current box and refuses --apply.
        code, out = run(["resize", "--site", "class-2034", "--page", "home", "--embed", "room-parents", "--box", "card"])
        if code != 0 or "before: 935 × 549" not in out or "height +76" not in out:
            problems.append(f"resize dry run: exit {code}, out {out[-200:]!r}")
        code, out = run(["resize", "--site", "class-2034", "--page", "home", "--embed", "room-parents", "--box", "card", "--apply"])
        if code != 2:
            problems.append(f"resize --apply should exit 2 (not built), got {code}")
        code, out = run(["publish", "--site", "class-2034", "--apply"])
        if code != 2:
            problems.append(f"publish --apply should exit 2 (not built), got {code}")
        code, out = run(["list", "--site", "nope"])
        if code != 1:
            problems.append(f"unknown site should exit 1, got {code}")
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
