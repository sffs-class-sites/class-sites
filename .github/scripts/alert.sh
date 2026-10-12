#!/usr/bin/env bash
# Keep one open issue per alert title: open it (assigned to Ahin) when a check fails,
# comment while it keeps failing, close it when the check passes again.
#   alert.sh "<title>" fail|pass <body-file>
set -euo pipefail
title=$1 status=$2 body=$3
num=$(gh issue list --state open --search "in:title \"$title\"" --json number,title \
      --jq "map(select(.title == \"$title\"))[0].number // empty")
if [ "$status" = fail ]; then
  if [ -n "$num" ]; then gh issue comment "$num" --body-file "$body"
  else gh issue create --title "$title" --assignee Ahin-SFFS --body-file "$body"; fi
elif [ -n "$num" ]; then
  gh issue close "$num" --comment "Passing again: $RUN_URL"
fi
