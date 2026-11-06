#!/usr/bin/env python3
"""Email a short note when a deploy changed anything other than the Updates ledger: the PR
title, its summary (the squash commit's body), the files changed, and how to revert.

Run by .github/workflows/deploy.yml's notify job after a push to main. Decided with Ahin
2026-11-06: Claude's PRs merge themselves once the build check passes, and this email is how
Ahin sees each change. Ledger changes have their own email (build/notify_changes.py).

  python3 build/notify_deploy.py --before <sha> [--send] [--run-url URL]
"""
import argparse
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from notify_changes import send  # same sender and App Password

REPO = "https://github.com/sffs-class-sites/class-sites"
LEDGER = {"shared/updates/data.json", "shared/updates/sources.json"}


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def compose(subject_line, body, files, run_url=""):
    """(email subject, email body) for one deploy, or (None, None) if only the ledger changed."""
    m = re.search(r"\(#(\d+)\)\s*$", subject_line)
    pr = m.group(1) if m else None
    title = re.sub(r"\s*\(#\d+\)\s*$", "", subject_line).strip()
    files = [f for f in files if f not in LEDGER]
    if not files:
        return None, None
    lines = [f"Deployed to the class sites: {title}", ""]
    body = re.sub(r"^(Co-Authored-By|Claude-Session|🤖 Generated).*$", "", body, flags=re.M).strip()
    if body:
        lines += ["What changed, in the PR's words:", body, ""]
    lines.append(f"Files ({len(files)}):")
    lines += [f"  - {f}" for f in files[:40]]
    if len(files) > 40:
        lines.append(f"  ... and {len(files) - 40} more")
    lines.append("")
    if pr:
        lines.append(f"PR: {REPO}/pull/{pr}")
    if run_url:
        lines.append(f"Build and deploy log: {run_url}")
    lines.append("To undo: open the PR, click Revert, and merge the revert (CI runs on it like any PR). "
                 "Or reply to this email.")
    return f"Class sites: change deployed: {title}"[:200], "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True, help="the commit main was at before this push")
    ap.add_argument("--run-url", default="")
    ap.add_argument("--to", default=os.environ.get("UPDATES_NOTIFY_TO", ""))
    ap.add_argument("--send", action="store_true")
    a = ap.parse_args()
    subject_line = git("log", "-1", "--format=%s").strip()
    body = git("log", "-1", "--format=%b")
    files = git("diff", "--name-only", a.before, "HEAD").split()
    subject, text = compose(subject_line, body, files, a.run_url)
    if not subject:
        print("Only the Updates ledger changed; the ledger email covers it.")
        return
    print(f"Subject: {subject}\n\n{text}\n")
    if a.send:
        pw = os.environ.get("BOT_GMAIL_APP_PASSWORD", "")
        if not a.to or not pw:
            sys.exit("notify_deploy: --send needs UPDATES_NOTIFY_TO and BOT_GMAIL_APP_PASSWORD")
        send(subject, text, a.to, pw)
        print(f"Sent to {a.to}.")


if __name__ == "__main__":
    main()
