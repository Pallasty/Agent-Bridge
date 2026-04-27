#!/usr/bin/env bash
# PreCompact hook: save important memories before context is compacted.
#
# Spawns a claude -p sub-agent with agent-bridge MCP access.
# AB_MEMORY_CURATOR=1 prevents the sub-agent's Stop hook from running
# memory_compact (which would delete newly-saved memories).

SESSION_ID="${CLAUDE_SESSION_ID:-}"
[[ -z "$SESSION_ID" ]] && exit 0

# Locate transcript by session ID across all Claude project dirs
TRANSCRIPT=$(find "$HOME/.claude/projects" -name "${SESSION_ID}.jsonl" 2>/dev/null | head -1)
[[ -f "$TRANSCRIPT" ]] || exit 0

AB=$(command -v agent-bridge 2>/dev/null || echo "$HOME/.local/bin/agent-bridge")
[[ -x "$AB" ]] || exit 0

TMPDIR_HOOK=$(mktemp -d /tmp/ab-precompact-XXXXXX)
trap 'rm -rf "$TMPDIR_HOOK"' EXIT

CONVO_FILE="$TMPDIR_HOOK/convo.txt"
PROMPT_FILE="$TMPDIR_HOOK/prompt.txt"

python3 - "$TRANSCRIPT" "$CONVO_FILE" <<'PY'
import sys, json

path = sys.argv[1]
out_path = sys.argv[2]
turns = []
with open(path, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get('isSidechain'):
            continue
        role = d.get('message', {}).get('role', '')
        if role not in ('user', 'assistant'):
            continue
        content = d.get('message', {}).get('content', '')
        text = ''
        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            parts = [
                c.get('text', '')
                for c in content
                if c.get('type') == 'text' and c.get('text', '').strip()
            ]
            text = '\n'.join(parts).strip()
        if not text:
            continue
        skip_prefixes = (
            '<local-command', '<system-reminder', '<command-name',
            '<command-message', '<command-args'
        )
        if any(text.startswith(p) for p in skip_prefixes):
            continue
        turns.append(f'[{role.upper()}]\n{text[:700]}')

recent = turns[-60:]
if recent:
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n\n---\n\n'.join(recent))
PY

[[ -s "$CONVO_FILE" ]] || exit 0

TODAY=$(date +%Y%m%d)

cat > "$PROMPT_FILE" <<PROMPT
You are a memory curator for an AI assistant (Claude Code). This session's context
is about to be compacted — the full conversation history will be lost after this.

Your job: call memory_save for each piece of knowledge worth carrying into future
sessions. You have access to memory_list and memory_search to avoid duplicates.

Use these kinds:
- lesson: learned behavior, bug/gotcha, env quirk, non-obvious fix
- decision: architectural or design choice that should not be revisited lightly
- context: project state hard to reconstruct from code alone
- session_handoff: ONE overall status note (key=session_handoff_${TODAY})

Guidelines:
- Do NOT save what is visible in code or git history
- Do NOT save temporary debugging steps or one-off commands
- Check existing memories first with memory_search or memory_list to avoid duplicates
- Keys: stable snake_case, e.g. lesson_sqlite_fts5_trigger_bug
- Content: concise markdown, under 500 chars per record
- Save 3–8 items maximum; write session_handoff last

Conversation to analyze:
$(cat "$CONVO_FILE")
PROMPT

DB="$HOME/.local/share/agent-bridge/state.db"
COUNT_BEFORE=$(sqlite3 "$DB" "SELECT COUNT(*) FROM memories;" 2>/dev/null || echo 0)

MCP_JSON="{\"mcpServers\":{\"ab\":{\"command\":\"${AB}\",\"args\":[\"mcp\"]}}}"
SETTINGS="$HOME/.config/agent-bridge/memory-curator-settings.json"

AB_MEMORY_CURATOR=1 claude -p "$(cat "$PROMPT_FILE")" \
    --mcp-config "$MCP_JSON" \
    --settings "$SETTINGS" \
    --max-turns 15 \
    < /dev/null \
    > "$TMPDIR_HOOK/agent-out.txt" 2>&1

COUNT_AFTER=$(sqlite3 "$DB" "SELECT COUNT(*) FROM memories;" 2>/dev/null || echo 0)
SAVED=$(( COUNT_AFTER - COUNT_BEFORE ))

echo "{\"systemMessage\": \"Memory curator: +${SAVED} new memories saved before compact.\"}"
