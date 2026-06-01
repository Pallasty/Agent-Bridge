#!/usr/bin/env bash
# waybar `custom/claude` on-click: open (or focus) the full dock panel.
#
#   - ensures dock_snapshot.json exists and a localhost http server is serving
#     this dir (so the panel's fetch() works; idempotent + detached)
#   - if a dock window is already mapped, focuses it; otherwise opens a small
#     floating, sticky Chrome --app window tagged ab-dock so sway can place it
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${AB_DOCK_PORT:-8777}"
PROFILE="$HOME/.cache/agent-bridge/dock-chrome-profile"
CHROME="$(command -v google-chrome || command -v chromium || command -v chromium-browser || echo google-chrome)"

python3 "$DIR/aggregate.py" >/dev/null 2>&1 || true

# ensure the http server (idempotent, detached from this click)
if ! curl -s -o /dev/null "http://127.0.0.1:$PORT/dock.html" 2>/dev/null; then
  ( cd "$DIR" && setsid python3 "$DIR/dock_server.py" "$PORT" >/dev/null 2>&1 </dev/null & )
  sleep 0.4
fi

# focus an existing dock window. Chrome --app derives a stable app_id like
# `chrome-127.0.0.1__dock.html-Default`, so match the `dock.html` substring
# (covers the chrome-generated id AND our --class=ab-dock) rather than relying
# on --class alone.
if swaymsg -t get_tree 2>/dev/null | grep -qE '"(app_id|class)": ?"[^"]*(dock\.html|ab-dock)'; then
  swaymsg '[app_id="(?i).*dock\.html.*"] focus' >/dev/null 2>&1 \
    || swaymsg '[app_id="ab-dock"] focus' >/dev/null 2>&1 \
    || swaymsg '[class="ab-dock"] focus' >/dev/null 2>&1
  exit 0
fi

# float + keep-on-all-workspaces for the dock, whichever app_id chrome assigns
swaymsg 'for_window [app_id="(?i).*dock\.html.*"] floating enable, sticky enable, border pixel 2' >/dev/null 2>&1 || true
swaymsg 'for_window [app_id="ab-dock"] floating enable, sticky enable, border pixel 2' >/dev/null 2>&1 || true

setsid "$CHROME" \
  --app="http://127.0.0.1:$PORT/dock.html" \
  --class=ab-dock \
  --user-data-dir="$PROFILE" \
  --window-size=400,480 \
  --no-first-run --no-default-browser-check --disable-features=Translate \
  >/dev/null 2>&1 </dev/null &
