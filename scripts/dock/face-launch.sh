#!/usr/bin/env bash
# LCC Face floater launcher — Xiao Shu's face on the desktop, rendering the
# grounded avatar_state live (the renderer HTML polls /linux-renderer-state, so
# the sprite tracks real activity: working->sorting_glow, idle->idle_breathe).
#
# Companion to claude-open.sh: that opens the dock (LCC Evidence layer); this
# opens the LCC Face layer. It is a sibling of `agent-bridge avatar
# linux-floater`, but deliberately bypasses that CLI: the CLI's swaymsg uses a
# `[title="Linux Codex Avatar Renderer"]` criteria that never matches the chrome
# wayland window, whose app_id is `chrome-...avatar-surface_linux-renderer-...`
# (so the CLI fails with `swaymsg exit=2` and the window never floats). We use
# an app_id sway rule instead.
#
#   - verifies the daemon-http renderer endpoint is reachable
#   - if a Face window is already mapped, focuses it (no duplicates)
#   - else opens a small floating, sticky chrome --app window
#
# Browser renderer => the window has a background frame. A truly transparent,
# frameless face needs a native wlroots layer-shell renderer (avatar_native.rs
# is probe-only today) — tracked as the LCC Face stage-2 work.
set -uo pipefail
BASE="${AB_FACE_BASE:-http://127.0.0.1:7878}"
URL="$BASE/avatar-surface/linux-renderer"
PROFILE="${AB_FACE_PROFILE:-$HOME/.cache/agent-bridge/avatar-chrome-profile}"
GEOM="${AB_FACE_GEOM:-360,520}"
CHROME="$(command -v google-chrome || command -v chromium || command -v chromium-browser || echo google-chrome)"

# chrome derives a stable app_id from host+path; match this substring (covers
# the chrome-generated id AND our --class) rather than relying on --class alone.
APPID_SUBSTR="avatar-surface_linux-renderer"

# renderer endpoint reachable? (daemon-http must be running)
if ! curl -s -o /dev/null "$URL" 2>/dev/null; then
  echo "Face renderer not reachable at $URL — is 'agent-bridge daemon-http' running?" >&2
  exit 1
fi

# focus an existing Face window instead of opening a second one.
if swaymsg -t get_tree 2>/dev/null | grep -qE "\"app_id\": ?\"[^\"]*${APPID_SUBSTR}"; then
  swaymsg "[app_id=\"(?i).*${APPID_SUBSTR}.*\"] focus" >/dev/null 2>&1 || true
  echo "Face already up — focused."
  exit 0
fi

# pre-register a sway rule so the window floats the instant it maps (avoids the
# title-vs-app_id race). Placement is left to the owner's taste: by default sway
# puts it on the focused output and the window is draggable; set AB_FACE_POS
# ("X Y", relative to the focused output) for an explicit corner.
swaymsg "for_window [app_id=\"(?i).*${APPID_SUBSTR}.*\"] floating enable, sticky enable, border none" >/dev/null 2>&1 || true

rm -f "$PROFILE"/Singleton* 2>/dev/null || true   # stale lock => chrome silently won't start
setsid "$CHROME" \
  --app="$URL" \
  --user-data-dir="$PROFILE" \
  --window-size="$GEOM" \
  --class=agent-bridge-avatar \
  --no-first-run --no-default-browser-check --disable-features=Translate \
  >/dev/null 2>&1 </dev/null &
disown

# explicit placement once it maps, only if the owner pinned a position.
if [[ -n "${AB_FACE_POS:-}" ]]; then
  for _ in $(seq 1 30); do
    if swaymsg -t get_tree 2>/dev/null | grep -qE "\"app_id\": ?\"[^\"]*${APPID_SUBSTR}"; then
      swaymsg "[app_id=\"(?i).*${APPID_SUBSTR}.*\"] resize set ${GEOM/,/ }, move position ${AB_FACE_POS}" >/dev/null 2>&1 || true
      break
    fi
    sleep 0.3
  done
fi
echo "Face floater up — $URL"
