#!/usr/bin/env bash
# UserPromptSubmit hook — inject scope-relevant agent-bridge memories.
#
# v3.0 (2026-05-03): pure-SQL static ranking
#   - Drops the v2.0 Python FNV-1a re-ranking: it computed 512-dim hash
#     vectors but the DB now stores 384-dim ONNX embeddings, so the cosine
#     was mathematically meaningless.
#   - Hook stays cheap and deterministic (~10-50 ms). The agent can call
#     session_bootstrap(query="...") to get true semantic ranking on demand —
#     that path uses the real ONNX model and is ~25 ms per query.
#   - Always-inject: concept nodes + session_handoff (≤15 combined) first.
#   - Then: top-20 from scope-matching candidates ordered by
#     kind tier + access*recency + importance.
#
# v2.0: semantic re-ranking (broken after 512→384 dim migration; reverted).
# v1.0: pure-SQL static sort.

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
DB="${AGENT_BRIDGE_DB:-$_AB_STATE_DIR/state.db}"

_AB_HOOK_LOG="$_AB_STATE_DIR/hook-runs.jsonl"
_AB_HOOK_START=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")
_ab_log_hook_run() {
    local exit_code="$1" output_bytes="$2"
    mkdir -p "$(dirname "$_AB_HOOK_LOG")"
    printf '{"event":"beforeSubmitPrompt","ts":"%s","exit_code":%d,"output_bytes":%d}\n' \
        "$_AB_HOOK_START" "$exit_code" "$output_bytes" >> "$_AB_HOOK_LOG" 2>/dev/null || true
}
trap '_ab_log_hook_run $? 0' EXIT

[[ -f "$DB" ]] || exit 0

# Skip inside memory-curator sub-agents to avoid recursive context bloat.
[[ "${AB_MEMORY_CURATOR:-}" == "1" ]] && exit 0

HOOK_PAYLOAD=$(cat 2>/dev/null || true)
SESSION_ID=$(printf '%s' "$HOOK_PAYLOAD" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get("session_id", ""))
except Exception:
    pass
' 2>/dev/null)
SESSION_ID="${SESSION_ID:-${CLAUDE_SESSION_ID:-$$}}"

LOCK="/tmp/ab-mem-injected-${SESSION_ID}"
[[ -f "$LOCK" ]] && exit 0
touch "$LOCK"

CWD="${PWD:-/}"

OUTPUT=$(python3 - "$DB" "$CWD" <<'PY'
import sys, sqlite3, json

DB_PATH = sys.argv[1]
CWD     = sys.argv[2]

try:
    con = sqlite3.connect(DB_PATH, timeout=3)
    con.row_factory = sqlite3.Row
except Exception:
    sys.exit(0)

# Static score: folds in importance so a high-importance lesson beats
# a low-importance todo of similar age.
#   access_count × 86400 = each access worth 1 day of recency
#   updated_at           = unix seconds, dominates among unread rows
#   importance × 1e7     = ~115 days of recency-equivalent
RANK = "(access_count * 86400 + updated_at + COALESCE(importance,0.5) * 10000000)"

KIND_TIER = """CASE kind
     WHEN 'concept'         THEN 0
     WHEN 'session_handoff' THEN 1
     WHEN 'lesson'          THEN 2
     WHEN 'decision'        THEN 3
     WHEN 'todo'            THEN 4
     ELSE 5 END"""

# 1. Always-inject: concept nodes (L0 navigation) + session_handoff (continuity).
always_rows = con.execute(
    f"SELECT kind, key, tags, scope, substr(content,1,120) AS snippet "
    f"FROM memories "
    f"WHERE status='active' AND kind IN ('concept','session_handoff') "
    f"ORDER BY {KIND_TIER}, {RANK} DESC LIMIT 15"
).fetchall()

# 2. Scope-filtered candidate pool (excluding always-inject kinds).
esc_cwd = CWD.replace("'", "''")
scope_filter = (
    "(scope IS NULL OR scope='global' "
    f"OR scope='project:{esc_cwd}' "
    f"OR (scope LIKE 'project:%' AND '{esc_cwd}' LIKE (SUBSTR(scope,9)||'%')) "
    "OR scope LIKE 'domain:%')"
)
ranked_rows = con.execute(
    f"SELECT kind, key, tags, scope, substr(content,1,120) AS snippet "
    f"FROM memories "
    f"WHERE status='active' AND kind NOT IN ('concept','session_handoff') "
    f"AND {scope_filter} "
    f"ORDER BY {KIND_TIER}, {RANK} DESC LIMIT 20"
).fetchall()
con.close()

def fmt(row) -> str:
    kind    = row["kind"]
    key     = row["key"]
    tags    = row["tags"] or ""
    scope   = row["scope"] or ""
    snippet = (row["snippet"] or "").replace("\n", " ").strip()
    if len(snippet) == 120:
        snippet += "…"
    tags_str  = f" [{tags}]" if tags else ""
    scope_str = ""
    if scope and scope not in ("", "global"):
        scope_str = " [proj]" if scope.startswith("project:") else f" [{scope[7:]}]"
    return f"[{kind}]{scope_str} {key}{tags_str}: {snippet}"

lines = [fmt(r) for r in always_rows] + [fmt(r) for r in ranked_rows]
if not lines:
    sys.exit(0)

block = (
    f"=== Agent-Bridge Memory (scope: {CWD} | static) ===\n"
    "Use memory_get <key> for full content. For semantic ranking call\n"
    "session_bootstrap(query='<task description>') or memory_search(mode=semantic).\n\n"
    + "\n".join(lines)
    + "\n=== End Memory ==="
)
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": block,
    }
}))
PY
)

# Bump access counts for injected always-inject rows.
sqlite3 "$DB" \
  "UPDATE memories
   SET access_count=access_count+1,
       last_accessed_at=CAST(strftime('%s','now') AS INTEGER)
   WHERE status='active' AND kind IN ('concept','session_handoff')
   ORDER BY (access_count*86400+updated_at) DESC LIMIT 15" 2>/dev/null || true

_OUT_BYTES=${#OUTPUT}
trap "_ab_log_hook_run \$? $_OUT_BYTES" EXIT
printf '%s' "$OUTPUT"
