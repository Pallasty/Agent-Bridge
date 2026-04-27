#!/usr/bin/env bash
# UserPromptSubmit hook: inject agent-bridge memory index on first message.
#
# Scope-aware: global + project-matching + domain memories are loaded.
# Runs exactly once per session (lock file keyed on CLAUDE_SESSION_ID).

DB="$HOME/.local/share/agent-bridge/state.db"
[[ -f "$DB" ]] || exit 0

SESSION_ID="${CLAUDE_SESSION_ID:-$$}"
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
   updated_at DESC
   LIMIT 80" 2>/dev/null) || exit 0

[[ -z "$ROWS" ]] && exit 0

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
