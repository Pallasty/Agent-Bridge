#!/usr/bin/env bash
# Slice 0 of the desktop embodiment dock — launcher.
#
# Stands up the read-only "functional presence dock": a small Chrome --app
# window that renders AB's live state and refreshes itself every few seconds.
#
#   - a local http.server serves the dock dir (so fetch() works, no file:// CORS)
#   - a background loop regenerates dock_snapshot.json from real AB state
#   - Chrome opens dock.html as a frameless app window on its OWN profile
#     (never touches AB's CDP chrome-profile)
#
# Env: AB_DOCK_PORT (8777) · AB_DOCK_INTERVAL (3) · AB_CHROME (google-chrome)
#      AB_DOCK_GEOMETRY (380,460) · AB_DOCK_POS (40,40)
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${AB_DOCK_PORT:-8777}"
INTERVAL="${AB_DOCK_INTERVAL:-3}"
CHROME="${AB_CHROME:-$(command -v google-chrome || command -v chromium || command -v chromium-browser || echo google-chrome)}"
GEOM="${AB_DOCK_GEOMETRY:-380,460}"
POS="${AB_DOCK_POS:-40,40}"
PROFILE="$HOME/.cache/agent-bridge/dock-chrome-profile"

cd "$DIR"
python3 aggregate.py >/dev/null   # first snapshot before the window opens

# background: keep the snapshot fresh
( while true; do python3 aggregate.py >/dev/null 2>&1 || true; sleep "$INTERVAL"; done ) &
AGG_PID=$!

# background: serve the dock dir on localhost
( python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 ) &
HTTP_PID=$!

cleanup() { kill "$AGG_PID" "$HTTP_PID" "${CHROME_PID:-}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

sleep 0.4
"$CHROME" \
  --app="http://127.0.0.1:$PORT/dock.html" \
  --user-data-dir="$PROFILE" \
  --window-size="$GEOM" --window-position="$POS" \
  --no-first-run --no-default-browser-check --disable-features=Translate \
  >/dev/null 2>&1 &
CHROME_PID=$!

echo "🪟  dock up — http://127.0.0.1:$PORT/dock.html"
echo "    aggregator pid=$AGG_PID  http pid=$HTTP_PID  chrome pid=$CHROME_PID  refresh=${INTERVAL}s"
echo "    (close the window or Ctrl-C here to stop everything)"
wait "$CHROME_PID"
