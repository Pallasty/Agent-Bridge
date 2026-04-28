#!/usr/bin/env bash
# UserPromptSubmit hook: inject agent-bridge memory index on first message.
#
# Scope-aware: global + project-matching + domain memories are loaded.
# Runs exactly once per session (lock file keyed on session_id).
#
# v0.7.2: read session_id from Claude Code's hook JSON payload on stdin.
# CLAUDE_SESSION_ID is NOT set in the hook env (verified empirically — see
# `lesson_hook_session_id_from_stdin`), so the previous
# `${CLAUDE_SESSION_ID:-$$}` fallback collapsed to the bash PID and was
# different on every invocation, defeating the once-per-session lock and
# causing memory index to re-inject on every UserPromptSubmit.

DB="$HOME/.local/share/agent-bridge/state.db"
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

SCOPE_SQL="(
  scope IS NULL
  OR scope = 'global'
  OR scope = 'project:${CWD}'
  OR (scope LIKE 'project:%' AND '${CWD}' LIKE (SUBSTR(scope, 9) || '%'))
  OR scope LIKE 'domain:%'
)"

ROWS=$(sqlite3 "$DB" \
  "SELECT kind, key, tags, scope, substr(content,1,120) FROM memories
   WHERE ${SCOPE_SQL}
   ORDER BY CASE kind
     WHEN 'lesson'           THEN 1
     WHEN 'decision'         THEN 2
     WHEN 'session_handoff'  THEN 3
     WHEN 'todo'             THEN 4
     ELSE 5 END,
   CASE WHEN scope = 'project:${CWD}'
          OR (scope LIKE 'project:%' AND '${CWD}' LIKE (SUBSTR(scope, 9) || '%'))
        THEN 0 ELSE 1 END,
   (access_count * 86400 + updated_at) DESC
   LIMIT 80" 2>/dev/null) || exit 0

[[ -z "$ROWS" ]] && exit 0

# v0.8: bump access_count + last_accessed_at on the rows we just injected
# so the "Frequent" / "Recent" sorts (and compaction's healthy default) reflect
# what is actually in front of Claude. We use the same WHERE clause; a small
# race window where another writer inserts between SELECT and UPDATE is
# acceptable — eventual consistency is fine for usage stats.
sqlite3 "$DB" \
  "UPDATE memories
   SET access_count    = access_count + 1,
       last_accessed_at = CAST(strftime('%s','now') AS INTEGER)
   WHERE rowid IN (
     SELECT rowid FROM memories
     WHERE ${SCOPE_SQL}
     ORDER BY CASE kind
       WHEN 'lesson'           THEN 1
       WHEN 'decision'         THEN 2
       WHEN 'session_handoff'  THEN 3
       WHEN 'todo'             THEN 4
       ELSE 5 END,
     CASE WHEN scope = 'project:${CWD}'
            OR (scope LIKE 'project:%' AND '${CWD}' LIKE (SUBSTR(scope, 9) || '%'))
          THEN 0 ELSE 1 END,
     (access_count * 86400 + updated_at) DESC
     LIMIT 80
   )" 2>/dev/null || true

python3 - "$ROWS" "$CWD" <<'PY'
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
