#!/usr/bin/env bash
# Stop hook: compact stale memories then sync to git remote.
#
# Guard: skip when running inside a memory-curator sub-agent
# (AB_MEMORY_CURATOR=1 is set by ab-precompact-hook).
[[ -n "$AB_MEMORY_CURATOR" ]] && exit 0

_ab_state_dir() {
    if [[ -n "${XDG_DATA_HOME:-}" ]]; then
        printf '%s/agent-bridge' "$XDG_DATA_HOME"
    elif [[ "$(uname -s 2>/dev/null || echo "")" == "Darwin" ]]; then
        printf '%s/Library/Application Support/agent-bridge' "$HOME"
    else
        printf '%s/.local/share/agent-bridge' "$HOME"
    fi
}

_AB_STATE_DIR="$(_ab_state_dir)"
HOOK_PAYLOAD=$(cat 2>/dev/null || true)
_AB_HOOK_EVENT="stop"
if [[ "${AB_SESSION_END_CURATE:-}" == "1" ]]; then
    _AB_HOOK_EVENT="sessionEnd"
fi

# Log this hook run to the shared hook-runs.jsonl file (read by hook_status MCP tool).
_AB_HOOK_LOG="$_AB_STATE_DIR/hook-runs.jsonl"
_AB_HOOK_START=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")
_ab_log_hook_run() {
    mkdir -p "$(dirname "$_AB_HOOK_LOG")"
    printf '{"event":"%s","ts":"%s","exit_code":%d,"output_bytes":0}\n' \
        "$_AB_HOOK_EVENT" "$_AB_HOOK_START" "$1" >> "$_AB_HOOK_LOG" 2>/dev/null || true
}
trap '_ab_log_hook_run $?' EXIT

DB="${AGENT_BRIDGE_DB:-$_AB_STATE_DIR/state.db}"
[[ -f "$DB" ]] || exit 0

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
# memory_compact lives in the Niche tool tier (since the profile filter
# in commit 84c1680). Without AGENT_BRIDGE_TOOL_PROFILE=all the spawned
# mcp child returns "unknown tool: memory_compact" and the call silently
# fails — so 90-day pruning would never run. Force the all profile here.
if [[ -x "$AB" ]]; then
    AGENT_BRIDGE_TOOL_PROFILE=all "$AB" mcp 2>/dev/null <<'JSONRPC'
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

exit 0
