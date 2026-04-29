#!/usr/bin/env bash
# Stop hook: compact stale memories then sync to git remote.
#
# Guard: skip when running inside a memory-curator sub-agent
# (AB_MEMORY_CURATOR=1 is set by ab-precompact-hook).
[[ -n "$AB_MEMORY_CURATOR" ]] && exit 0

# Log this hook run to the shared hook-runs.jsonl file (read by hook_status MCP tool).
_AB_HOOK_LOG="$HOME/.local/share/agent-bridge/hook-runs.jsonl"
_AB_HOOK_START=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")
_ab_log_hook_run() {
    mkdir -p "$(dirname "$_AB_HOOK_LOG")"
    printf '{"event":"stop","ts":"%s","exit_code":%d,"output_bytes":0}\n' \
        "$_AB_HOOK_START" "$1" >> "$_AB_HOOK_LOG" 2>/dev/null || true
}
trap '_ab_log_hook_run $?' EXIT

DB="$HOME/.local/share/agent-bridge/state.db"
[[ -f "$DB" ]] || exit 0

AB=$(command -v agent-bridge 2>/dev/null || echo "$HOME/.local/bin/agent-bridge")
SYNC="${AGENT_BRIDGE_MEMORY_REPO:-$HOME/agent-bridge-memory}/sync.sh"

# Compact: time-only policy — remove memories not accessed in 90 days.
# min_uses is intentionally omitted: new memories start at access_count=0
# and would be immediately deleted by an OR-based min_uses policy.
if [[ -x "$AB" ]]; then
    "$AB" mcp 2>/dev/null <<'JSONRPC'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","clientInfo":{"name":"stop-hook","version":"1"},"capabilities":{}}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"memory_compact","arguments":{"older_than_days":90,"dry_run":false}}}
JSONRPC
fi

# Sync to git remote if the memory repo exists.
if [[ -x "$SYNC" ]]; then
    AGENT_BRIDGE_BIN="$AB" bash "$SYNC" >/dev/null 2>&1 &
fi

exit 0
