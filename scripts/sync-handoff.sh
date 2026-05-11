#!/usr/bin/env bash
# sync-handoff.sh — one-shot cross-machine memory sync via ssh + scp.
#
# Codifies the 2026-05-11 dogfood pattern (aio2 → 192.168.1.99 via direct ssh,
# no Tailscale required). Defaults bake in the lessons-learned env vars so
# new machines work first-try:
#   AGENT_BRIDGE_EMBED_BACKEND=hash   — avoids ONNX silent-hang on fresh hosts
#                                       (lesson: feedback_onnx_backend_hangs_without_model.md)
#   AGENT_BRIDGE_TOOL_PROFILE=all     — memory_export/import are Niche tier
#   loose_edges=true                  — narrow-filter exports keep cross-set
#                                       edges; destination skips + counts danglers
#                                       (lesson resolved: e41bfb1)
#
# Usage:
#   ./scripts/sync-handoff.sh user@host
#   ./scripts/sync-handoff.sh user@host --kind project
#   ./scripts/sync-handoff.sh user@host --since-ts 1700000000
#   ./scripts/sync-handoff.sh user@host --dry-run
#
# Flags:
#   --kind <K>            kind filter (default: chat_session)
#   --since-ts <N>        only memories with updated_at >= N (unix seconds)
#   --remote-binary <P>   path to agent-bridge on remote (default: scp ours)
#   --remote-xdg <P>      XDG_DATA_HOME on remote (default: /tmp/handoff-xdg-<ts>)
#   --keep-temp           don't rm exports / remote temp files at exit
#   --dry-run             print the steps without executing
#   --no-tools-profile    don't set AGENT_BRIDGE_TOOL_PROFILE=all on remote
#                         (only relevant if remote binary differs)
#   --remote-onnx         don't force EMBED_BACKEND=hash on remote (use ONNX)

set -euo pipefail

# ── defaults ────────────────────────────────────────────────────────────────
TARGET=""
KIND="chat_session"
SINCE_TS=""
REMOTE_BINARY=""
REMOTE_XDG=""
KEEP_TEMP=0
DRY_RUN=0
REMOTE_PROFILE_ALL=1
REMOTE_HASH_EMBED=1

LOCAL_BIN="${AGENT_BRIDGE_BIN:-$HOME/.local/bin/agent-bridge.real}"
TS="$(date +%s)"
TMP_DIR="/tmp/handoff-$TS"

# ── parse args ──────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --kind)            KIND="$2"; shift 2 ;;
    --since-ts)        SINCE_TS="$2"; shift 2 ;;
    --remote-binary)   REMOTE_BINARY="$2"; shift 2 ;;
    --remote-xdg)      REMOTE_XDG="$2"; shift 2 ;;
    --keep-temp)       KEEP_TEMP=1; shift ;;
    --dry-run)         DRY_RUN=1; shift ;;
    --no-tools-profile) REMOTE_PROFILE_ALL=0; shift ;;
    --remote-onnx)     REMOTE_HASH_EMBED=0; shift ;;
    -h|--help)
      sed -n '2,/^set -euo/p' "$0" | sed -n '/^# /p'
      exit 0
      ;;
    -*)
      echo "unknown flag: $1" >&2; exit 2 ;;
    *)
      if [[ -z "$TARGET" ]]; then TARGET="$1"; else
        echo "extra positional: $1" >&2; exit 2
      fi
      shift ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  echo "usage: $0 <user@host> [flags] — see --help" >&2; exit 2
fi
[[ -z "$REMOTE_BINARY" ]] && REMOTE_BINARY="/tmp/agent-bridge-handoff-$TS"
[[ -z "$REMOTE_XDG" ]] && REMOTE_XDG="/tmp/handoff-xdg-$TS"

run() {
  if [[ "$DRY_RUN" == 1 ]]; then
    echo "DRY: $*"
  else
    "$@"
  fi
}
log() { echo "→ $*"; }

cleanup() {
  if [[ "$KEEP_TEMP" == 1 ]]; then
    log "keep-temp: leaving $TMP_DIR + remote $REMOTE_XDG"
    return
  fi
  [[ "$DRY_RUN" == 1 ]] && return
  rm -rf "$TMP_DIR" 2>/dev/null || true
  ssh -o BatchMode=yes "$TARGET" \
    "rm -rf '$REMOTE_XDG' '$REMOTE_BINARY' '/tmp/handoff-mem-$TS.jsonl' '/tmp/handoff-edges-$TS.jsonl' '/tmp/handoff-req-$TS.json'" \
    2>/dev/null || true
}
trap cleanup EXIT

# ── step 1: local export (loose_edges) ──────────────────────────────────────
mkdir -p "$TMP_DIR"
MEM_LOCAL="$TMP_DIR/mem.jsonl"
EDGES_LOCAL="$TMP_DIR/edges.jsonl"

log "step 1: local export — kind=$KIND loose_edges=true${SINCE_TS:+ since_ts=$SINCE_TS}"

ARGS_JSON="{\"path\":\"$MEM_LOCAL\",\"edges_out_path\":\"$EDGES_LOCAL\",\"loose_edges\":true,\"kind\":\"$KIND\""
[[ -n "$SINCE_TS" ]] && ARGS_JSON="$ARGS_JSON,\"since_ts\":$SINCE_TS"
ARGS_JSON="$ARGS_JSON}"

REQ_LOCAL="$TMP_DIR/req-export.json"
cat > "$REQ_LOCAL" <<JSON
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","clientInfo":{"name":"handoff","version":"0.1"},"capabilities":{}}}
{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"memory_export","arguments":$ARGS_JSON}}
JSON

if [[ "$DRY_RUN" == 1 ]]; then
  echo "DRY: ( cat $REQ_LOCAL && sleep 3 ) | AGENT_BRIDGE_TOOL_PROFILE=all $LOCAL_BIN mcp"
else
  EXPORT_OUT=$( ( cat "$REQ_LOCAL" && sleep 3 ) | \
    AGENT_BRIDGE_TOOL_PROFILE=all timeout 15 "$LOCAL_BIN" mcp 2>/dev/null \
    | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line)
        if d.get('id') == 2:
            content = d.get('result', {}).get('content', [])
            for c in content:
                if c.get('type') == 'text':
                    print(c.get('text', ''))
    except: pass
")
  echo "$EXPORT_OUT"
fi
[[ -f "$MEM_LOCAL" ]] || { [[ "$DRY_RUN" == 1 ]] || { echo "export produced no file" >&2; exit 1; }; }

# ── step 2: scp binary + exports to remote ──────────────────────────────────
log "step 2: scp binary + exports to $TARGET"
run scp -q "$LOCAL_BIN" "$TARGET:$REMOTE_BINARY"
run ssh -o BatchMode=yes "$TARGET" "chmod +x '$REMOTE_BINARY'"
REMOTE_MEM="/tmp/handoff-mem-$TS.jsonl"
REMOTE_EDGES="/tmp/handoff-edges-$TS.jsonl"
run scp -q "$MEM_LOCAL"   "$TARGET:$REMOTE_MEM"
run scp -q "$EDGES_LOCAL" "$TARGET:$REMOTE_EDGES"

# ── step 3: remote import (with hardened env defaults) ──────────────────────
log "step 3: remote import — XDG=$REMOTE_XDG profile=$([[ $REMOTE_PROFILE_ALL == 1 ]] && echo all || echo default) embed=$([[ $REMOTE_HASH_EMBED == 1 ]] && echo hash || echo onnx)"
REMOTE_REQ="/tmp/handoff-req-$TS.json"
ENV_PARTS=()
[[ "$REMOTE_PROFILE_ALL" == 1 ]] && ENV_PARTS+=("AGENT_BRIDGE_TOOL_PROFILE=all")
[[ "$REMOTE_HASH_EMBED" == 1 ]] && ENV_PARTS+=("AGENT_BRIDGE_EMBED_BACKEND=hash")
ENV_STR="${ENV_PARTS[*]}"

# Build remote command in heredoc — the request file is built on remote so
# quoting stays sane regardless of local shell variant.
if [[ "$DRY_RUN" == 1 ]]; then
  echo "DRY: ssh $TARGET 'build req-$TS.json; ( cat req && sleep 5 ) | XDG_DATA_HOME=$REMOTE_XDG $ENV_STR $REMOTE_BINARY mcp'"
else
  REPORT=$(ssh -o BatchMode=yes "$TARGET" bash -s <<EOF
set -e
mkdir -p "$REMOTE_XDG"
cat > "$REMOTE_REQ" <<REQ
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","clientInfo":{"name":"handoff","version":"0.1"},"capabilities":{}}}
{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"memory_import","arguments":{"path":"$REMOTE_MEM","edges_path":"$REMOTE_EDGES","conflict_policy":"skip"}}}
REQ
( cat "$REMOTE_REQ" && sleep 8 ) | \
  XDG_DATA_HOME="$REMOTE_XDG" $ENV_STR \
  timeout 30 "$REMOTE_BINARY" mcp 2>/dev/null \
  | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line)
        if d.get('id') == 2:
            for c in d.get('result', {}).get('content', []):
                if c.get('type') == 'text':
                    print(c.get('text', ''))
    except: pass
"
EOF
)
  echo "$REPORT"
fi

log "done."
