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
AB_FACE_BIN_BASENAME="${AB_FACE_BIN##*/}"
export AB_FACE_STATE_URL="${AB_FACE_STATE_URL:-http://127.0.0.1:7878/avatar-surface/linux-renderer-state?project=agent-bridge}"
export AB_FACE_PET_ID="${AB_FACE_PET_ID:-xiao-shu-v2}"
export AB_FACE_MODE="${AB_FACE_MODE:-idle}"
export AB_FACE_ANCHOR="${AB_FACE_ANCHOR:-bottom-right}"
export AB_FACE_MR="${AB_FACE_MARGIN_RIGHT:-96}"
export AB_FACE_MB="${AB_FACE_MARGIN_BOTTOM:-96}"
export AB_FACE_W="${AB_FACE_WIDTH:-90}"
export AB_FACE_H="${AB_FACE_HEIGHT:-130}"
export AB_FACE_SPRITE_SCALE="${AB_FACE_SPRITE_SCALE_PERCENT:-39}"
export AB_FACE_DRAGGABLE="${AB_FACE_DRAGGABLE:-1}"
export AB_FACE_SEG="${AB_FACE_SEGMENT_MS:-86400000}"   # 24h per probe segment; loop re-spawns
export AB_FACE_OUTPUT="${AB_FACE_OUTPUT:-}"            # Wayland output name (e.g. DP-1); empty = compositor default
export AB_FACE_SESSION_ID="${AB_FACE_SESSION_ID:-com.agentbridge.avatar-face.agent-bridge}"
export AB_FACE_HEARTBEAT_SECS="${AB_FACE_HEARTBEAT_SECS:-15}"
export AB_FACE_ACTIVITY_STATE="${AB_FACE_ACTIVITY_STATE:-idle}"
# Sparse voice is an independent observer and remains explicitly default-off.
# When enabled, the launcher fail-closes unless its dry-run plan reports ready.
export AB_FACE_VOICE_ENABLED="${AB_FACE_VOICE_ENABLED:-0}"
export AB_FACE_VOICE_BACKEND="${AB_FACE_VOICE_BACKEND:-qwen3}"
export AB_FACE_VOICE_SEG="${AB_FACE_VOICE_SEGMENT_MS:-86400000}"
export AB_FACE_VOICE_POLL_MS="${AB_FACE_VOICE_POLL_MS:-500}"
export AB_FACE_VOICE_COOLDOWN_SECS="${AB_FACE_VOICE_COOLDOWN_SECS:-300}"
export AB_FACE_VOICE_MAX_UTTERANCES="${AB_FACE_VOICE_MAX_UTTERANCES:-3}"
export AB_FACE_VOICE_GAIN_DB="${AB_FACE_VOICE_GAIN_DB:-8}"
export AB_FACE_QWEN_WORKER="${AB_FACE_QWEN_WORKER:-${AB_QWEN3_TTS_WORKER_SOCKET:-}}"
export AB_FACE_VOICE_SCRIPT="${AB_FACE_VOICE_SCRIPT:-}"
export AB_FACE_VOICE_SINK="${AB_FACE_VOICE_SINK:-}"
if [ "$AB_FACE_VOICE_ENABLED" != "0" ] && [ "$AB_FACE_VOICE_ENABLED" != "1" ]; then
  echo "AB_FACE_VOICE_ENABLED must be 0 or 1." >&2
  exit 2
fi
if [ "$AB_FACE_DRAGGABLE" != "0" ] && [ "$AB_FACE_DRAGGABLE" != "1" ]; then
  echo "AB_FACE_DRAGGABLE must be 0 or 1." >&2
  exit 2
fi

# Single-instance lock + supervise-loop pidfile. Prefer XDG_RUNTIME_DIR (already
# user-private); the /tmp fallback is namespaced by uid so it isn't a shared
# cross-user path masquerading as a single-instance lock.
AB_FACE_RUNDIR="${XDG_RUNTIME_DIR:-/tmp/ab-face-$(id -u)}"
mkdir -p "$AB_FACE_RUNDIR" 2>/dev/null || true
AB_FACE_LOCK="$AB_FACE_RUNDIR/ab-face-native.lock"
AB_FACE_PIDFILE="$AB_FACE_RUNDIR/ab-face-native.pid"
export AB_FACE_VOICE_PIDFILE="$AB_FACE_RUNDIR/ab-face-voice-observer.pid"
export AB_FACE_VOICE_RECEIPT_LOG="${AB_FACE_VOICE_RECEIPT_LOG:-$AB_FACE_RUNDIR/ab-face-voice-receipts.jsonl}"

native_cmd_for_pid() {
  local pid="$1"
  [ -r "/proc/$pid/cmdline" ] || return 1
  local cmd
  cmd="$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true)"
  local exe="${cmd%% *}"
  [ "${exe##*/}" = "$AB_FACE_BIN_BASENAME" ] \
    && [[ "$cmd" == *" avatar linux-native-transparent "* ]]
}

voice_cmd_for_pid() {
  local pid="$1"
  [ -r "/proc/$pid/cmdline" ] || return 1
  local cmd
  cmd="$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true)"
  local exe="${cmd%% *}"
  [ "${exe##*/}" = "$AB_FACE_BIN_BASENAME" ] \
    && [[ "$cmd" == *" avatar voice-observe "* ]]
}

supervisor_cmd_for_pid() {
  local pid="$1"
  [ -r "/proc/$pid/cmdline" ] || return 1
  local cmd
  cmd="$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true)"
  [[ "$cmd" == bash\ -c* ]] \
    && [[ "$cmd" == *heartbeat_loop*linux-native-transparent* ]]
}

supervisor_pid() {
  local pid
  pid="$(cat "$AB_FACE_PIDFILE" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    printf '%s\n' "$pid"
  fi
}

voice_supervisor_pid() {
  local pid
  pid="$(cat "$AB_FACE_VOICE_PIDFILE" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null \
      && tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null | grep -q 'voice_loop' \
      && tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null | grep -q 'voice-observe'; then
    printf '%s\n' "$pid"
  fi
}

if [ "${1:-}" = "--status" ]; then
  json_status=0
  [ "${2:-}" = "--json" ] && json_status=1
  supervisor="$(supervisor_pid)"
  voice_supervisor="$(voice_supervisor_pid)"
  child=""
  voice_child=""
  for face_cmdline in /proc/[0-9]*/cmdline; do
    [ -r "$face_cmdline" ] || continue
    face_pid="${face_cmdline#/proc/}"
    face_pid="${face_pid%/cmdline}"
    if native_cmd_for_pid "$face_pid"; then
      child="$face_pid"
    elif voice_cmd_for_pid "$face_pid"; then
      voice_child="$face_pid"
    fi
  done
  endpoint="unreachable"
  if curl -fsS --max-time 1 -o /dev/null "${AB_FACE_STATE_URL%%\?*}" 2>/dev/null; then
    endpoint="reachable"
  fi
  if [ -n "$supervisor" ] && [ -n "$child" ]; then
    state="running"
  elif [ -n "$supervisor" ]; then
    state="supervisor_only"
  else
    state="stopped"
  fi
  if [ "$json_status" -eq 1 ]; then
    printf '{"surface":"linux_avatar_native_entrypoint_status","state":"%s","supervisor_pid":%s,"renderer_pid":%s,"voice_supervisor_pid":%s,"voice_observer_pid":%s,"voice_configured":%s,"state_endpoint":"%s"}\n' \
      "$state" "${supervisor:-null}" "${child:-null}" "${voice_supervisor:-null}" "${voice_child:-null}" \
      "$([ "$AB_FACE_VOICE_ENABLED" = "1" ] && printf true || printf false)" "$endpoint"
  else
    printf 'native Face status: %s\n' "$state"
    printf '  supervisor_pid: %s\n' "${supervisor:-none}"
    printf '  renderer_pid:   %s\n' "${child:-none}"
    printf '  voice_pid:      %s\n' "${voice_child:-none}"
    printf '  voice_supervisor_pid: %s\n' "${voice_supervisor:-none}"
    printf '  voice_config:   %s\n' "$([ "$AB_FACE_VOICE_ENABLED" = "1" ] && printf enabled || printf disabled)"
    printf '  state_endpoint: %s\n' "$endpoint"
  fi
  exit 0
fi

# `--stop`: self-validating teardown. Only group-kill the recorded PID if it is
# still alive AND its cmdline is our supervise loop — guards against PID reuse
# turning a copy-pasted kill into killing an unrelated process group.
if [ "${1:-}" = "--stop" ]; then
  pid="$(cat "$AB_FACE_PIDFILE" 2>/dev/null || true)"
  if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null \
      && tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null | grep -q 'linux-native-transparent'; then
    kill -- "-$pid" 2>/dev/null && echo "native Face stopped (group $pid)."
  else
    echo "no valid supervisor pid; checking exact renderer processes."
  fi
  # A renderer can outlive its supervisor if the Wayland child creates its own
  # process group. Sweep only exact Agent-Bridge renderer argv entries; never
  # use a broad pattern that could match this shell or another application.
  for face_cmdline in /proc/[0-9]*/cmdline; do
    [ -r "$face_cmdline" ] || continue
    face_pid="${face_cmdline#/proc/}"
    face_pid="${face_pid%/cmdline}"
    if supervisor_cmd_for_pid "$face_pid"; then
      kill -- "-$face_pid" 2>/dev/null || kill "$face_pid" 2>/dev/null || true
    elif native_cmd_for_pid "$face_pid" || voice_cmd_for_pid "$face_pid"; then
      kill "$face_pid" 2>/dev/null || true
    fi
  done
  rm -f "$AB_FACE_PIDFILE" "$AB_FACE_VOICE_PIDFILE"
  exit 0
fi

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

# already running? Inspect only the actual Agent-Bridge binary processes; a
# broad `pgrep -f` also matches the shell command that contains this pattern.
face_running=0
for face_cmdline in /proc/[0-9]*/cmdline; do
  [ -r "$face_cmdline" ] || continue
  face_pid="${face_cmdline#/proc/}"
  face_pid="${face_pid%/cmdline}"
  face_cmd="$(tr '\0' ' ' <"$face_cmdline" 2>/dev/null || true)"
  face_exe="${face_cmd%% *}"
  if [ "${face_exe##*/}" = "$AB_FACE_BIN_BASENAME" ] \
      && native_cmd_for_pid "$face_pid"; then
    face_running=1
    break
  fi
done
if [ "$face_running" -eq 1 ]; then
  echo "native Face already running."
  exit 0
fi

# An XDG toplevel is a real Sway container, unlike layer-shell. Register the
# exact app_id before it maps so Sway keeps it floating, sticky and borderless;
# the session's `floating_modifier $mod normal` then provides Super+left-drag.
if [ "$AB_FACE_DRAGGABLE" = "1" ]; then
  swaymsg 'for_window [app_id="^agent-bridge-avatar$"] floating enable, sticky enable, border none' \
    >/dev/null 2>&1 || {
      echo "draggable Face requires a reachable Sway IPC socket." >&2
      exit 1
    }
fi

# renderer-state endpoint reachable? (daemon-http must be up)
if ! curl -s -o /dev/null "${AB_FACE_STATE_URL%%\?*}" 2>/dev/null; then
  echo "renderer-state endpoint unreachable — is 'agent-bridge daemon-http' running?" >&2
  exit 1
fi

if [ "$AB_FACE_VOICE_ENABLED" = "1" ]; then
  voice_preflight=(
    avatar voice-observe --pet-id "$AB_FACE_PET_ID"
    --voice-backend "$AB_FACE_VOICE_BACKEND"
    --duration-ms "$AB_FACE_VOICE_SEG" --state-poll-ms "$AB_FACE_VOICE_POLL_MS"
    --voice-cooldown-secs "$AB_FACE_VOICE_COOLDOWN_SECS"
    --voice-max-utterances "$AB_FACE_VOICE_MAX_UTTERANCES" --dry-run --json
  )
  [ -n "$AB_FACE_QWEN_WORKER" ] && voice_preflight+=(--qwen-worker "$AB_FACE_QWEN_WORKER")
  [ -n "$AB_FACE_VOICE_SCRIPT" ] && voice_preflight+=(--voice-script "$AB_FACE_VOICE_SCRIPT")
  [ -n "$AB_FACE_VOICE_SINK" ] && voice_preflight+=(--voice-sink "$AB_FACE_VOICE_SINK")
  voice_plan="$("$AB_FACE_BIN" "${voice_preflight[@]}" 2>/dev/null)" || {
    echo "voice observer preflight failed — native Face was not started." >&2
    exit 1
  }
  if ! grep -Eq '"ready"[[:space:]]*:[[:space:]]*true' <<<"$voice_plan"; then
    echo "voice observer is not ready — native Face was not started." >&2
    exit 1
  fi
fi

# supervise loop, detached. The bounded probe exits after each segment; respawn
# it so the face stays up. setsid bash -c inherits the exported AB_FACE_* env, so
# no fragile quote-splicing. A short sleep avoids a hot respawn loop on failure.
setsid bash -c '
  # Do not inherit the launcher lock into the detached supervisor. Keeping fd 9
  # open would make every later invocation look like a concurrent startup even
  # after the original launcher has exited.
  exec 9>&-
  heartbeat_loop() {
    while true; do
      "$AB_FACE_BIN" avatar sync-presence \
        --pet-id "$AB_FACE_PET_ID" --session-id "$AB_FACE_SESSION_ID" \
        --project agent-bridge --role embodiment --tag native-face \
        --runtime local-cli --activity-state "$AB_FACE_ACTIVITY_STATE" \
        --cwd "$PWD" --json >/dev/null 2>&1 || true
      sleep "$AB_FACE_HEARTBEAT_SECS"
    done
  }
  voice_loop() {
    while true; do
      voice_args=(
        avatar voice-observe --pet-id "$AB_FACE_PET_ID"
        --voice-backend "$AB_FACE_VOICE_BACKEND"
        --duration-ms "$AB_FACE_VOICE_SEG" --state-poll-ms "$AB_FACE_VOICE_POLL_MS"
        --voice-cooldown-secs "$AB_FACE_VOICE_COOLDOWN_SECS"
        --voice-max-utterances "$AB_FACE_VOICE_MAX_UTTERANCES" --json
      )
      [ -n "$AB_FACE_QWEN_WORKER" ] && voice_args+=(--qwen-worker "$AB_FACE_QWEN_WORKER")
      [ -n "$AB_FACE_VOICE_SCRIPT" ] && voice_args+=(--voice-script "$AB_FACE_VOICE_SCRIPT")
      [ -n "$AB_FACE_VOICE_SINK" ] && voice_args+=(--voice-sink "$AB_FACE_VOICE_SINK")
      AB_TTS_PLAYBACK_GAIN_DB="$AB_FACE_VOICE_GAIN_DB" \
      AB_TTS_VOICE_RECEIPT_LOG="$AB_FACE_VOICE_RECEIPT_LOG" \
        "$AB_FACE_BIN" "${voice_args[@]}" >/dev/null 2>&1 || true
      sleep 1
    done
  }
  heartbeat_loop &
  AB_FACE_HEARTBEAT_PID=$!
  AB_FACE_VOICE_PID=""
  if [ "$AB_FACE_VOICE_ENABLED" = "1" ]; then
    voice_loop &
    AB_FACE_VOICE_PID=$!
    printf "%s\n" "$AB_FACE_VOICE_PID" >"$AB_FACE_VOICE_PIDFILE" 2>/dev/null || true
  fi
  cleanup_children() {
    kill "$AB_FACE_HEARTBEAT_PID" 2>/dev/null || true
    [ -z "$AB_FACE_VOICE_PID" ] || kill "$AB_FACE_VOICE_PID" 2>/dev/null || true
    rm -f "$AB_FACE_VOICE_PIDFILE"
  }
  trap cleanup_children EXIT
  trap "cleanup_children; exit 143" INT TERM
  while true; do
    render_args=(avatar linux-native-transparent \
      --mode "$AB_FACE_MODE" --pet-id "$AB_FACE_PET_ID" --state-url "$AB_FACE_STATE_URL" \
      --anchor "$AB_FACE_ANCHOR" --margin-right "$AB_FACE_MR" --margin-bottom "$AB_FACE_MB" \
      --width "$AB_FACE_W" --height "$AB_FACE_H" --duration-ms "$AB_FACE_SEG" \
      --sprite-scale-percent "$AB_FACE_SPRITE_SCALE")
    [ "$AB_FACE_DRAGGABLE" = "1" ] && render_args+=(--draggable)
    [ -n "$AB_FACE_OUTPUT" ] && render_args+=(--output "$AB_FACE_OUTPUT")
    "$AB_FACE_BIN" "${render_args[@]}" >/dev/null 2>&1 || true
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
echo "  draggable: $([ "$AB_FACE_DRAGGABLE" = "1" ] && printf 'Super+left mouse' || printf disabled)"
echo "  sparse voice: $([ "$AB_FACE_VOICE_ENABLED" = "1" ] && printf enabled || printf disabled)"
echo "  sparse voice gain: ${AB_FACE_VOICE_GAIN_DB}dB (adapter clamps to 0..8dB)"
echo "  stop with: $0 --stop   # self-validating: group-kills only if the recorded pid is alive AND ours"
echo "  (do NOT 'pkill -f face-native-launch' — that -f pattern matches your own shell and self-kills)"
