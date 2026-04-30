#!/usr/bin/env bash
# PreCompact hook: curate memories via agent-bridge MCP (no claude -p needed).
#
# Workflow:
#   1. Parse session_id from stdin payload.
#   2. Locate transcript JSONL file.
#   3. Extract last ~60 turns and pre-process the text so bullet items under
#      "Lessons / Decisions / Summary" sections get `lesson:` / `decision:`
#      prefix markers — making session_curate's rule engine effective.
#   4. Call agent-bridge MCP: session_curate  (extract + persist memories).
#      Pass-2 tuning: set AGENT_BRIDGE_CURATE_SCORE_THRESHOLD /
#      AGENT_BRIDGE_CURATE_DEDUP_JACCARD in the environment of this hook
#      (or add implicit_* args to the JSON below if you fork this script).
#   5. Call agent-bridge MCP: session_finalize (importance decay + cleanup)
#   6. Return systemMessage summary for the IDE.

# ── Logging ────────────────────────────────────────────────────────────────────
_AB_HOOK_LOG="$HOME/.local/share/agent-bridge/hook-runs.jsonl"
_AB_HOOK_START=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")
_ab_log_hook_run() {
    mkdir -p "$(dirname "$_AB_HOOK_LOG")"
    printf '{"event":"preCompact","ts":"%s","exit_code":%d,"output_bytes":0}\n' \
        "$_AB_HOOK_START" "$1" >> "$_AB_HOOK_LOG" 2>/dev/null || true
}
trap '_ab_log_hook_run $?' EXIT

# ── Locate agent-bridge binary ─────────────────────────────────────────────────
AB=$(command -v agent-bridge 2>/dev/null || echo "$HOME/.local/bin/agent-bridge")
[[ -x "$AB" ]] || exit 0

# ── Parse session_id ──────────────────────────────────────────────────────────
HOOK_PAYLOAD=$(cat 2>/dev/null || true)
SESSION_ID=$(printf '%s' "$HOOK_PAYLOAD" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get("session_id", ""))
except Exception:
    pass
' 2>/dev/null)
SESSION_ID="${SESSION_ID:-${CLAUDE_SESSION_ID:-}}"
[[ -z "$SESSION_ID" ]] && exit 0

# ── Locate transcript ─────────────────────────────────────────────────────────
TRANSCRIPT=$(find "$HOME/.claude/projects" "$HOME/.cursor/projects" \
    -name "${SESSION_ID}.jsonl" 2>/dev/null | head -1)
[[ -f "$TRANSCRIPT" ]] || exit 0

# ── Temp workspace ────────────────────────────────────────────────────────────
TMPDIR_HOOK=$(mktemp -d /tmp/ab-precompact-XXXXXX)
trap 'rm -rf "$TMPDIR_HOOK"; _ab_log_hook_run $?' EXIT

CONVO_FILE="$TMPDIR_HOOK/convo.txt"
MCP_IN="$TMPDIR_HOOK/mcp-input.jsonl"
MCP_OUT="$TMPDIR_HOOK/mcp-output.txt"

# ── Extract + pre-process conversation ────────────────────────────────────────
# Produces a text file where bullet items under recognised section headers are
# rewritten to explicit marker prefixes so session_curate can detect them.
python3 - "$TRANSCRIPT" "$CONVO_FILE" <<'PY'
import sys, json, re

SECTION_KINDS = {
    "lesson": "lesson",
    "lessons": "lesson",
    "learned": "lesson",
    "learning": "lesson",
    "gotcha": "lesson",
    "gotchas": "lesson",
    "pitfall": "lesson",
    "pitfalls": "lesson",
    "insight": "lesson",
    "insights": "lesson",
    "decision": "decision",
    "decisions": "decision",
    "decided": "decision",
    "todo": "todo",
    "todos": "todo",
    "action item": "todo",
    "action items": "todo",
    "next step": "todo",
    "next steps": "todo",
    "summary": "context",
    "status": "context",
    "context": "context",
    "handoff": "session_handoff",
    "session handoff": "session_handoff",
}

BULLET_RE = re.compile(r'^[-*+•]\s+|^\d+\.\s+')

def detect_section(line: str):
    """Return kind if line looks like a section header, else None."""
    bare = line.strip().strip('*').rstrip(':').strip().lower()
    return SECTION_KINDS.get(bare)

def strip_bullet(line: str):
    m = BULLET_RE.match(line.strip())
    return line.strip()[m.end():].strip() if m else None

path = sys.argv[1]
out_path = sys.argv[2]

turns = []
with open(path, 'r', encoding='utf-8') as f:
    for raw in f:
        raw = raw.strip()
        if not raw:
            continue
        try:
            d = json.loads(raw)
        except Exception:
            continue
        if d.get('isSidechain'):
            continue
        msg = d.get('message', {})
        role = msg.get('role', '') or d.get('role', '')
        if role not in ('user', 'assistant'):
            continue
        content = msg.get('content', '')
        text = ''
        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            parts = [
                c.get('text', '')
                for c in content
                if isinstance(c, dict) and c.get('type') == 'text' and c.get('text', '').strip()
            ]
            text = '\n'.join(parts).strip()
        if not text:
            continue
        skip = (
            '<local-command', '<system-reminder', '<command-name',
            '<command-message', '<command-args',
        )
        if any(text.startswith(p) for p in skip):
            continue
        turns.append((role, text[:1200]))

recent = turns[-60:]
if not recent:
    sys.exit(0)

out_lines = []
for role, text in recent:
    out_lines.append(f'[{role.upper()}]')
    # Pre-process assistant turns: convert section bullets → explicit markers
    if role == 'assistant':
        section_kind = None
        blank_streak = 0
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                blank_streak += 1
                if blank_streak >= 2:
                    section_kind = None
                out_lines.append('')
                continue
            blank_streak = 0
            kind = detect_section(stripped)
            if kind:
                section_kind = kind
                out_lines.append(line)
                continue
            payload = strip_bullet(stripped)
            if payload and section_kind and len(payload) >= 8:
                out_lines.append(f'{section_kind}: {payload}')
            else:
                out_lines.append(line)
    else:
        out_lines.append(text)
    out_lines.append('')

with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(out_lines))
PY

[[ -s "$CONVO_FILE" ]] || exit 0

# ── Build MCP JSON-RPC messages ───────────────────────────────────────────────
python3 - "$CONVO_FILE" "$SESSION_ID" "$MCP_IN" <<'PY'
import json, sys

convo_path, session_id, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(convo_path, 'r', encoding='utf-8').read()
# Trim to avoid overwhelming the MCP handler; keep the most recent content
if len(text) > 12000:
    text = text[-12000:]

messages = [
    # 1. MCP handshake
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "ab-precompact-hook", "version": "1"}
    }},
    # 2. Initialized notification (required by MCP spec)
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    # 3. session_curate: extract + save memories from the conversation
    {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
        "name": "session_curate",
        "arguments": {
            "conversation_text": text,
            "session_id": session_id,
            "max_items": 10
        }
    }},
    # 4. session_finalize: importance decay + stale memory cleanup
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
        "name": "session_finalize",
        "arguments": {}
    }},
]

with open(out_path, 'w') as f:
    for m in messages:
        f.write(json.dumps(m) + '\n')
PY

# ── Run agent-bridge MCP ──────────────────────────────────────────────────────
DB="$HOME/.local/share/agent-bridge/state.db"
COUNT_BEFORE=$(sqlite3 "$DB" "SELECT COUNT(*) FROM memories;" 2>/dev/null || echo 0)

timeout 25 "$AB" mcp < "$MCP_IN" > "$MCP_OUT" 2>/dev/null

COUNT_AFTER=$(sqlite3 "$DB" "SELECT COUNT(*) FROM memories;" 2>/dev/null || echo 0)
SAVED=$(( COUNT_AFTER - COUNT_BEFORE ))

# ── Parse curate result for summary ──────────────────────────────────────────
CURATE_SUMMARY=$(python3 - "$MCP_OUT" <<'PY'
import json, sys
try:
    for line in open(sys.argv[1]):
        d = json.loads(line)
        if d.get("id") == 2:
            result = d.get("result", {})
            content = result.get("content", [])
            for item in content:
                text = item.get("text", "")
                try:
                    obj = json.loads(text)
                    saved = obj.get("saved_count", 0)
                    skipped = obj.get("skipped_duplicates", 0)
                    print(f"curated={saved} skipped={skipped}")
                except Exception:
                    pass
except Exception:
    pass
PY
)

echo "{\"systemMessage\": \"Memory precompact: +${SAVED} memories | ${CURATE_SUMMARY:-session_curate done} | session_finalize done\"}"
