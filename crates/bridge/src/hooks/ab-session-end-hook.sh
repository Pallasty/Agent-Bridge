#!/usr/bin/env bash
# Stop hook: compact stale memories then sync to git remote.
#
# Guard: skip when running inside a memory-curator sub-agent
# (AB_MEMORY_CURATOR=1 is set by ab-precompact-hook).
if [[ -n "$AB_MEMORY_CURATOR" ]]; then
    printf '{}\n'
    exit 0
fi

_ab_state_dir() {
    if [[ -n "${XDG_DATA_HOME:-}" ]]; then
        printf '%s/agent-bridge' "$XDG_DATA_HOME"
    elif [[ "$(uname -s 2>/dev/null || echo "")" == "Darwin" ]]; then
        printf '%s/Library/Application Support/agent-bridge' "$HOME"
    else
        printf '%s/.local/share/agent-bridge' "$HOME"
    fi
}

_ab_active_pet_id() {
    python3 - <<'PY' 2>/dev/null || printf '%s\n' 'xiao-shu-v2'
import json
import os

def clean(value):
    value = (value or "").strip()
    cleaned = "".join(
        ch for ch in value
        if ch.isascii() and (ch.isalnum() or ch in "-_")
    )
    return cleaned or None

env_pet = clean(os.environ.get("AB_PET_ID"))
if env_pet:
    print(env_pet)
    raise SystemExit(0)

path = os.path.join(os.path.expanduser("~"), ".codex", ".codex-global-state.json")
try:
    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)
    selected = (
        state.get("electron-persisted-atom-state", {})
        .get("selected-avatar-id", "")
    )
    if selected.startswith("custom:"):
        pet = clean(selected.removeprefix("custom:"))
        if pet:
            print(pet)
            raise SystemExit(0)
except Exception:
    pass

print("xiao-shu-v2")
PY
}

_AB_STATE_DIR="$(_ab_state_dir)"
HOOK_PAYLOAD=$(cat 2>/dev/null || true)
_AB_HOOK_EVENT="stop"
if [[ "${AB_SESSION_END_CURATE:-}" == "1" ]]; then
    _AB_HOOK_EVENT="sessionEnd"
fi

_ab_pet_auto_tts_enabled() {
    local spec="${AB_PET_AUTO_TTS:-}"
    [[ -n "$spec" ]] || return 1

    local spec_lc event_lc
    spec_lc=$(printf '%s' "$spec" | tr '[:upper:]' '[:lower:]' | tr '; ' ',,')
    event_lc=$(printf '%s' "$_AB_HOOK_EVENT" | tr '[:upper:]' '[:lower:]')

    case ",$spec_lc," in
        *,0,*|*,false,*|*,off,*|*,no,*|*,none,*) return 1 ;;
        *,1,*|*,true,*|*,yes,*|*,on,*|*,all,*|*,handoff,*) return 0 ;;
    esac
    case ",$spec_lc," in
        *,"$event_lc",*) return 0 ;;
    esac
    return 1
}

_ab_pet_auto_tts_emit() {
    [[ "${AB_PET_STATE_DISABLE:-}" == "1" ]] && return 0
    _ab_pet_auto_tts_enabled || return 0

    local ab channel cooldown
    ab="${AGENT_BRIDGE_BIN:-$(command -v agent-bridge 2>/dev/null || echo "$HOME/.local/bin/agent-bridge")}"
    [[ -x "$ab" ]] || return 0

    channel="${AB_PET_AUTO_TTS_CHANNEL:-tts}"
    case "$channel" in
        tts|notification|both) ;;
        *) channel="tts" ;;
    esac

    cooldown="${AB_PET_AUTO_TTS_COOLDOWN_SECONDS:-1800}"
    case "$cooldown" in
        ''|*[!0-9]*) cooldown="1800" ;;
    esac

    (
        # Local-only MCP call (pet_state_ritual on the on-disk store); strip the
        # parent session's OAuth/API creds. Enumerate via bash builtins and use
        # absolute /usr/bin/env (~/.local/bin/env may be a non-coreutils shim).
        _AB_ENV_PASS=()
        for _k in ${!AGENT_BRIDGE_@}; do
            _AB_ENV_PASS+=("$_k=${!_k}")
        done
        for _k in XDG_DATA_HOME XDG_CONFIG_HOME XDG_RUNTIME_DIR; do
            [[ -n "${!_k:-}" ]] && _AB_ENV_PASS+=("$_k=${!_k}")
        done
        /usr/bin/env -i \
            PATH="$PATH" HOME="$HOME" USER="${USER:-}" LOGNAME="${LOGNAME:-}" \
            LANG="${LANG:-}" LC_ALL="${LC_ALL:-}" TERM="${TERM:-}" TMPDIR="${TMPDIR:-}" \
            "${_AB_ENV_PASS[@]}" \
            AGENT_BRIDGE_CLIENT=hook \
            AGENT_BRIDGE_MCP_SOURCE=hook \
            AGENT_BRIDGE_TOOLSET=hook-lifecycle \
            AGENT_BRIDGE_TOOL_PROFILE=standard \
            "$ab" mcp <<JSONRPC
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","clientInfo":{"name":"pet-auto-tts-hook","version":"1"},"capabilities":{}}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"pet_state_ritual","arguments":{"channel":"$channel","enabled":true,"cooldown_seconds":$cooldown}}}
JSONRPC
    ) >/dev/null 2>&1 &
}

_ab_pet_state_write() {
    [[ "${AB_PET_STATE_DISABLE:-}" == "1" ]] && return 0
    local pet_id
    pet_id="$(_ab_active_pet_id)"
    pet_id="${pet_id:-xiao-shu-v2}"
    local reason="session stop hook launched memory compact/sync"
    if [[ "$_AB_HOOK_EVENT" == "sessionEnd" ]]; then
        reason="session end hook launched memory curate/sync"
    fi
    AB_HOOK_PAYLOAD="$HOOK_PAYLOAD" python3 - "$_AB_STATE_DIR" "$pet_id" "$_AB_HOOK_EVENT" "${PWD:-/}" "$reason" <<'PY' >/dev/null 2>&1 || true
import datetime
import json
import os
import tempfile
import sys

state_dir, pet_id, event, cwd, reason = sys.argv[1:6]
pet_id = "".join(
    ch for ch in pet_id
    if ch.isascii() and (ch.isalnum() or ch in "-_")
) or "xiao-shu-v2"
project = os.path.basename(cwd.rstrip(os.sep)) or cwd
session_id = ""
try:
    payload = json.loads(os.environ.get("AB_HOOK_PAYLOAD", "") or "{}")
    session_id = payload.get("session_id") or payload.get("sessionId") or ""
except Exception:
    pass

now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
state = {
    "schema_version": 1,
    "pet_id": pet_id,
    "project": project,
    "cwd": cwd,
    "mode": "handoff",
    "mood": "calm",
    "reason": reason,
    "last_event": event,
    "last_verified_at": None,
    "voice_line": "本轮交接已完成。",
    "ritual": "handoff",
    "source": "ab-session-end-hook",
    "session_id": session_id,
    "updated_at": now,
}

out_dir = os.path.join(state_dir, "pet_state")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, f"{pet_id}.json")
fd, tmp_path = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=out_dir)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, out_path)
finally:
    if os.path.exists(tmp_path):
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
PY
}
_ab_pet_state_write
_ab_pet_auto_tts_emit

# Log this hook run to the shared hook-runs.jsonl file (read by hook_status MCP tool).
_AB_HOOK_LOG="$_AB_STATE_DIR/hook-runs.jsonl"
_AB_HOOK_START=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")
_AB_HOOK_OUTPUT_BYTES=3
_ab_log_hook_run() {
    mkdir -p "$(dirname "$_AB_HOOK_LOG")"
    printf '{"event":"%s","ts":"%s","exit_code":%d,"output_bytes":%d}\n' \
        "$_AB_HOOK_EVENT" "$_AB_HOOK_START" "$1" "$_AB_HOOK_OUTPUT_BYTES" >> "$_AB_HOOK_LOG" 2>/dev/null || true
}
trap '_ab_log_hook_run $?' EXIT

DB="${AGENT_BRIDGE_DB:-$_AB_STATE_DIR/state.db}"
if [[ ! -f "$DB" ]]; then
    printf '{}\n'
    exit 0
fi

AB=$(command -v agent-bridge 2>/dev/null || echo "$HOME/.local/bin/agent-bridge")
PRECOMPACT=$(command -v ab-precompact-hook 2>/dev/null || echo "$HOME/.local/bin/ab-precompact-hook")

# Codex has a real SessionEnd hook in addition to Stop. For that event, run
# the same transcript curator used by PreCompact before pruning/syncing.
if [[ "${AB_SESSION_END_CURATE:-}" == "1" && -x "$PRECOMPACT" ]]; then
    printf '%s' "$HOOK_PAYLOAD" \
        | AB_HOOK_EVENT=sessionEndCurate "$PRECOMPACT" >/dev/null 2>&1 || true
fi

# Compact: time-only policy — remove memories not accessed in 90 days.
# min_uses is intentionally omitted: new memories start at access_count=0
# and would be immediately deleted by an OR-based min_uses policy.
#
# The hook only needs lifecycle-safe tools. Keep this child on the
# hook-lifecycle toolset instead of exposing the full developer registry.
if [[ -x "$AB" ]]; then
    # Local-only MCP call (memory_compact on the on-disk store, no Anthropic
    # API call), so strip the parent session's OAuth/API credentials: start
    # from env -i and pass through only a safe base + agent-bridge's own
    # non-secret AGENT_BRIDGE_*/XDG_* config. (The `agent-bridge sync` below is
    # separate and intentionally keeps git/push credentials.)
    # Enumerate via bash builtins (${!PREFIX@}) — never via `env`, which a user
    # PATH shim (~/.local/bin/env) can shadow with a non-coreutils wrapper. Use
    # absolute /usr/bin/env (real coreutils on Linux + macOS) for `-i` isolation.
    _AB_ENV_PASS=()
    for _k in ${!AGENT_BRIDGE_@}; do
        _AB_ENV_PASS+=("$_k=${!_k}")
    done
    for _k in XDG_DATA_HOME XDG_CONFIG_HOME XDG_RUNTIME_DIR; do
        [[ -n "${!_k:-}" ]] && _AB_ENV_PASS+=("$_k=${!_k}")
    done

    /usr/bin/env -i \
        PATH="$PATH" HOME="$HOME" USER="${USER:-}" LOGNAME="${LOGNAME:-}" \
        LANG="${LANG:-}" LC_ALL="${LC_ALL:-}" TERM="${TERM:-}" TMPDIR="${TMPDIR:-}" \
        "${_AB_ENV_PASS[@]}" \
        AGENT_BRIDGE_CLIENT=hook \
        AGENT_BRIDGE_MCP_SOURCE=hook \
        AGENT_BRIDGE_TOOLSET=hook-lifecycle \
        AGENT_BRIDGE_TOOL_PROFILE=standard \
        "$AB" mcp >/dev/null 2>/dev/null <<'JSONRPC'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","clientInfo":{"name":"stop-hook","version":"1"},"capabilities":{}}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"memory_compact","arguments":{"older_than_days":90,"dry_run":false}}}
JSONRPC
fi

# Sync to git remote in the background (no-op if not initialised).
# Path resolution lives inside `agent-bridge sync`; honours
# AGENT_BRIDGE_MEMORY_REPO and falls back to legacy locations.
if [[ -x "$AB" ]]; then
    "$AB" sync >/dev/null 2>&1 &
fi

printf '{}\n'
exit 0
