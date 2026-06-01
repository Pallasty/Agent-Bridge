#!/usr/bin/env bash
# waybar `custom/claude` exec: refresh the snapshot from live AB state, then
# emit the {text,tooltip,class} JSON line. Runs every few seconds (waybar
# `interval`), which is also what keeps dock_snapshot.json fresh for the panel.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/aggregate.py" >/dev/null 2>&1 || true
python3 "$DIR/waybar_status.py"
