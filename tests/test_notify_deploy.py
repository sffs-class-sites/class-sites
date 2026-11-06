#!/usr/bin/env python3
"""Checks build/notify_deploy.py's wording without git or network."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "build"))
import notify_deploy as n

failures = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    cond or failures.append(msg)


s, b = n.compose("Routine: plain push (#47)", "Why: the check refuses -f.\n\nCo-Authored-By: X <x@y>\n",
                 ["docs/extraction-routine.md", "shared/updates/data.json"], "https://example.test/run/1")
check(s == "Class sites: change deployed: Routine: plain push", f"subject drops the PR number: {s!r}")
check("PR: https://github.com/sffs-class-sites/class-sites/pull/47" in b, "links the PR")
check("Why: the check refuses -f." in b and "Co-Authored-By" not in b, "keeps the PR's summary, drops trailers")
check("  - docs/extraction-routine.md" in b and "data.json" not in b, "lists changed files, ledger files excluded")
check("Revert" in b and "https://example.test/run/1" in b, "says how to undo and links the run")
s2, _ = n.compose("Updates: 2 new topics (#46)", "", ["shared/updates/data.json"])
check(s2 is None, "a ledger-only deploy sends nothing here")

if failures:
    sys.exit(f"test_notify_deploy: {len(failures)} failure(s)")
print("test_notify_deploy: ok")
