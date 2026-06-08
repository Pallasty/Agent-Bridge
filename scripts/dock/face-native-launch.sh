#!/usr/bin/env bash
# LCC Face — native transparent renderer (wlroots layer-shell). THE FINAL FACE
# FORM: Xiao Shu's face floats frameless on the desktop (ARGB8888 alpha),
# rendering the grounded avatar_state live (the renderer polls
# /linux-renderer-state, so the sprite tracks real activity). This supersedes
# the browser floater (face-launch.sh) — true transparency the browser can't do
# (chrome on sway exits with --enable-transparent-visuals).
#
# `agent-bridge avatar linux-native-transparent` is a *bounded* probe (it exits
# after --duration-ms), so we wrap it in a setsid-detached supervise loop that
# re-spawns it each segment / on crash, keeping the face up. setsid survives the
# launching agent/shell (an agent-backgrounded GUI would otherwise be reaped).
#
# Placement: the native layer-shell surface lands on the compositor's default
# output (DP-3 here) — the CLI has no --output selector yet. Position within that
# output is AB_FACE_ANCHOR + margins (taste-led, env-overridable). Selecting a
# specific output is tracked as a follow-up (needs a CLI flag).
set -uo pipefail
export AB_FACE_BIN="${AB_BIN:-$HOME/.local/bin/agent-bridge.real}"
export AB_FACE_STATE_URL="${AB_FACE_STATE_URL:-http://127.0.0.1:7878/avatar-surface/linux-renderer-state?project=agent-bridge}"
export AB_FACE_PET_ID="${AB_FACE_PET_ID:-xiao-shu-v2}"
export AB_FACE_MODE="${AB_FACE_MODE:-idle}"
export AB_FACE_ANCHOR="${AB_FACE_ANCHOR:-bottom-right}"
export AB_FACE_MR="${AB_FACE_MARGIN_RIGHT:-96}"
export AB_FACE_MB="${AB_FACE_MARGIN_BOTTOM:-96}"
export AB_FACE_W="${AB_FACE_WIDTH:-360}"
export AB_FACE_H="${AB_FACE_HEIGHT:-520}"
export AB_FACE_SEG="${AB_FACE_SEGMENT_MS:-86400000}"   # 24h per probe segment; loop re-spawns
export AB_FACE_OUTPUT="${AB_FACE_OUTPUT:-}"            # Wayland output name (e.g. DP-1); empty = compositor default

# Single-instance lock + supervise-loop pidfile (XDG_RUNTIME_DIR, /tmp fallback).
AB_FACE_RUNDIR="${XDG_RUNTIME_DIR:-/tmp}"
AB_FACE_LOCK="$AB_FACE_RUNDIR/ab-face-native.lock"
AB_FACE_PIDFILE="$AB_FACE_RUNDIR/ab-face-native.pid"

# Atomic single-instance guard: hold an exclusive lock across the whole
# check-and-spawn. Without it, two near-simultaneous launches can both pass the
# pgrep liveness check before either spawns its loop (TOCTOU) and end up with
# two Faces. The lock auto-releases when fd 9 closes on script exit — by then
# the supervised loop is already detached, so steady-state re-launches are still
# caught by the pgrep check below.
exec 9>"$AB_FACE_LOCK"
if ! flock -n 9; then
  echo "another face-native-launch is already starting — aborting to avoid a second Face."
  exit 0
fi

# already running? (the supervise loop or a probe)
if pgrep -f "linux-native-transparent" >/dev/null 2>&1; then
  echo "native Face already running."
  exit 0
fi

# renderer-state endpoint reachable? (daemon-http must be up)
if ! curl -s -o /dev/null "${AB_FACE_STATE_URL%%\?*}" 2>/dev/null; then
  echo "renderer-state endpoint unreachable — is 'agent-bridge daemon-http' running?" >&2
  exit 1
fi

# supervise loop, detached. The bounded probe exits after each segment; respawn
# it so the face stays up. setsid bash -c inherits the exported AB_FACE_* env, so
# no fragile quote-splicing. A short sleep avoids a hot respawn loop on failure.
setsid bash -c '
  while true; do
    "$AB_FACE_BIN" avatar linux-native-transparent \
      --mode "$AB_FACE_MODE" --pet-id "$AB_FACE_PET_ID" --state-url "$AB_FACE_STATE_URL" \
      --anchor "$AB_FACE_ANCHOR" --margin-right "$AB_FACE_MR" --margin-bottom "$AB_FACE_MB" \
      --width "$AB_FACE_W" --height "$AB_FACE_H" --duration-ms "$AB_FACE_SEG" \
      ${AB_FACE_OUTPUT:+--output "$AB_FACE_OUTPUT"} >/dev/null 2>&1 || true
    sleep 1
  done
' </dev/null >/dev/null 2>&1 &
AB_FACE_LOOP_PID=$!
disown
# Record the supervise loop's PID for a clean, self-safe stop. setsid made it a
# session/group leader, so its PGID == its PID — killing the group takes down
# the loop AND the live probe child it spawned.
printf '%s\n' "$AB_FACE_LOOP_PID" >"$AB_FACE_PIDFILE" 2>/dev/null || true

echo "native Face up (supervised, detached) — anchor=$AB_FACE_ANCHOR ${AB_FACE_W}x${AB_FACE_H} segment=${AB_FACE_SEG}ms"
echo "  stop with: kill -- -\"\$(cat $AB_FACE_PIDFILE)\"   # kills the whole supervised group (loop + live probe)"
echo "  (do NOT use 'pkill -f face-native-launch' — the -f pattern matches your own shell's command line and self-kills)"
