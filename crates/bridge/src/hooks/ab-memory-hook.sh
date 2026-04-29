#!/usr/bin/env bash
# UserPromptSubmit hook: inject agent-bridge memory index on first message.
#
# Scope-aware: global + project-matching + domain memories are loaded.
# Runs exactly once per session (lock file keyed on session_id).
#
# v0.9.2: concept nodes get a dedicated always-first budget (≤15 slots).
# kind='concept' rows are excluded from domain/other queries so they never
# compete for those slots and are never sorted to the back by KIND_TIER.
#
# v0.9.1: split injection budget — domain memories get a reserved 20-slot
# budget injected first; project/global memories fill the remaining 60 slots.
# This prevents a large global memory store from crowding out domain knowledge.
#
# v0.9: project-scope sort priority (3-tier: kind → proj-match → recency×freq)
# v0.8: access_count bump on injected rows; session_id from stdin payload.
# v0.7.2: read session_id from Claude Code's hook JSON payload on stdin.
# CLAUDE_SESSION_ID is NOT set in the hook env (verified empirically — see
# `lesson_hook_session_id_from_stdin`), so the previous
# `${CLAUDE_SESSION_ID:-$$}` fallback collapsed to the bash PID and was
# different on every invocation, defeating the once-per-session lock and
# causing memory index to re-inject on every UserPromptSubmit.

DB="$HOME/.local/share/agent-bridge/state.db"

# Log this hook run to the shared hook-runs.jsonl file (read by hook_status MCP tool).
_AB_HOOK_LOG="$HOME/.local/share/agent-bridge/hook-runs.jsonl"
_AB_HOOK_START=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")
_ab_log_hook_run() {
    local exit_code="$1" output_bytes="$2"
    mkdir -p "$(dirname "$_AB_HOOK_LOG")"
    printf '{"event":"beforeSubmitPrompt","ts":"%s","exit_code":%d,"output_bytes":%d}\n' \
        "$_AB_HOOK_START" "$exit_code" "$output_bytes" >> "$_AB_HOOK_LOG" 2>/dev/null || true
}
trap '_ab_log_hook_run $? 0' EXIT

[[ -f "$DB" ]] || exit 0

# Skip memory injection inside curator sub-agents (PreCompact hook sets this)
# to avoid recursive context bloat.
[[ "${AB_MEMORY_CURATOR:-}" == "1" ]] && exit 0

# Hook input is one line of JSON on stdin. Buffer it so subsequent reads
# (none today, but future-proof) don't lose it; then extract session_id.
# Falls back to env / PID if stdin is empty (manual invocation, etc.).
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

# Sort expression shared by both queries (within each kind tier):
# access_count × 86400 gives each access the weight of one extra day of recency.
FREQ_SORT="(access_count * 86400 + updated_at) DESC"

KIND_TIER="CASE kind
     WHEN 'concept'          THEN 0
     WHEN 'lesson'           THEN 1
     WHEN 'decision'         THEN 2
     WHEN 'session_handoff'  THEN 3
     WHEN 'todo'             THEN 4
     ELSE 5 END"

# Query 0: concept nodes — L0 navigation layer, always injected first.
# Up to 15 slots; excluded from domain/other budgets below.
CONCEPT_ROWS=$(sqlite3 "$DB" \
  "SELECT kind, key, tags, scope, substr(content,1,120) FROM memories
   WHERE kind = 'concept'
   ORDER BY ${FREQ_SORT}
   LIMIT 15" 2>/dev/null) || true

# Query 1: domain-scoped memories — reserved 20-slot budget, injected second.
# These are cross-project transferable knowledge; they must appear regardless
# of how large the global store grows.
DOMAIN_ROWS=$(sqlite3 "$DB" \
  "SELECT kind, key, tags, scope, substr(content,1,120) FROM memories
   WHERE scope LIKE 'domain:%' AND kind != 'concept'
   ORDER BY ${KIND_TIER}, ${FREQ_SORT}
   LIMIT 20" 2>/dev/null) || true

# Query 2: project-scoped + global memories — up to 60 slots.
# 3-tier sort: kind → project-CWD match (0=match, 1=no match) → recency×freq.
OTHER_SCOPE="(
  scope IS NULL
  OR scope = 'global'
  OR scope = 'project:${CWD}'
  OR (scope LIKE 'project:%' AND '${CWD}' LIKE (SUBSTR(scope, 9) || '%'))
)"

PROJ_MATCH="CASE WHEN scope = 'project:${CWD}'
          OR (scope LIKE 'project:%' AND '${CWD}' LIKE (SUBSTR(scope, 9) || '%'))
        THEN 0 ELSE 1 END"

OTHER_ROWS=$(sqlite3 "$DB" \
  "SELECT kind, key, tags, scope, substr(content,1,120) FROM memories
   WHERE ${OTHER_SCOPE} AND kind != 'concept'
   ORDER BY ${KIND_TIER}, ${PROJ_MATCH}, ${FREQ_SORT}
   LIMIT 60" 2>/dev/null) || true

# Merge: concept nodes first (L0 nav), then domain, then project/global.
# NL must be declared outside double-quotes for $'\n' to expand correctly.
NL=$'\n'
ROWS=""
[[ -n "$CONCEPT_ROWS" ]] && ROWS="$CONCEPT_ROWS"
[[ -n "$DOMAIN_ROWS"  ]] && ROWS="${ROWS:+${ROWS}${NL}}${DOMAIN_ROWS}"
[[ -n "$OTHER_ROWS"   ]] && ROWS="${ROWS:+${ROWS}${NL}}${OTHER_ROWS}"
[[ -z "$ROWS" ]] && exit 0

# Bump access_count + last_accessed_at for all three sets (mirrors the SELECTs above).
sqlite3 "$DB" \
  "UPDATE memories
   SET access_count    = access_count + 1,
       last_accessed_at = CAST(strftime('%s','now') AS INTEGER)
   WHERE rowid IN (
     SELECT rowid FROM memories
     WHERE kind = 'concept'
     ORDER BY ${FREQ_SORT}
     LIMIT 15
   )" 2>/dev/null || true

sqlite3 "$DB" \
  "UPDATE memories
   SET access_count    = access_count + 1,
       last_accessed_at = CAST(strftime('%s','now') AS INTEGER)
   WHERE rowid IN (
     SELECT rowid FROM memories
     WHERE scope LIKE 'domain:%' AND kind != 'concept'
     ORDER BY ${KIND_TIER}, ${FREQ_SORT}
     LIMIT 20
   )" 2>/dev/null || true

sqlite3 "$DB" \
  "UPDATE memories
   SET access_count    = access_count + 1,
       last_accessed_at = CAST(strftime('%s','now') AS INTEGER)
   WHERE rowid IN (
     SELECT rowid FROM memories
     WHERE ${OTHER_SCOPE} AND kind != 'concept'
     ORDER BY ${KIND_TIER}, ${PROJ_MATCH}, ${FREQ_SORT}
     LIMIT 60
   )" 2>/dev/null || true

OUTPUT=$(python3 - "$ROWS" "$CWD" <<'PY'
import json, sys

rows_raw = sys.argv[1]
cwd = sys.argv[2] if len(sys.argv) > 2 else "/"
lines = []
for row in rows_raw.strip().splitlines():
    parts = row.split("|", 4)
    if len(parts) < 5:
        continue
    kind, key, tags, scope, snippet = parts
    tags_str = f" [{tags}]" if tags else ""
    scope_str = ""
    if scope and scope not in ("", "global"):
        if scope.startswith("project:"):
            scope_str = " [proj]"
        elif scope.startswith("domain:"):
            scope_str = f" [{scope[7:]}]"
    snippet = snippet.replace("\n", " ").strip()
    if len(snippet) == 120:
        snippet += "…"
    lines.append(f"[{kind}]{scope_str} {key}{tags_str}: {snippet}")

if not lines:
    sys.exit(0)

block = (
    "=== Agent-Bridge Self-Memory (scope: " + cwd + ") ===\n"
    "Use memory_get <key> for full content, memory_search for keyword lookup.\n\n"
    + "\n".join(lines)
    + "\n=== End Memory ==="
)
print(json.dumps({"additionalContext": block}))
PY
)
_OUT_BYTES=${#OUTPUT}
trap "_ab_log_hook_run \$? $_OUT_BYTES" EXIT
printf '%s' "$OUTPUT"
