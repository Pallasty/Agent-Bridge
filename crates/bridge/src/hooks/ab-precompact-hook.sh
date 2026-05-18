#!/usr/bin/env bash
# PreCompact hook: curate memories via agent-bridge MCP (no claude -p needed).
#
# Workflow:
#   1. Parse session_id from stdin payload.
#   2. Locate transcript JSONL file.
#   3. Extract last ~60 turns and pre-process the text so bullet items under
#      "Lessons / Decisions / Summary" sections get `lesson:` / `decision:`
#      prefix markers — making session_curate's rule engine effective.
#   4. Call agent-bridge MCP: session_lifecycle_step(precompact) — runs
#      session_curate then session_finalize in one tools/call.
#      Pass-2 tuning: set AGENT_BRIDGE_CURATE_SCORE_THRESHOLD /
#      AGENT_BRIDGE_CURATE_DEDUP_JACCARD in the environment of this hook
#      (or add implicit_* args to the JSON below if you fork this script).
#   5. Return systemMessage summary for the IDE.

# ── Logging ────────────────────────────────────────────────────────────────────
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
_AB_HOOK_EVENT="${AB_HOOK_EVENT:-preCompact}"
_AB_HOOK_LOG="$_AB_STATE_DIR/hook-runs.jsonl"
_AB_HOOK_START=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")
_ab_log_hook_run() {
    mkdir -p "$(dirname "$_AB_HOOK_LOG")"
    printf '{"event":"%s","ts":"%s","exit_code":%d,"output_bytes":0}\n' \
        "$_AB_HOOK_EVENT" "$_AB_HOOK_START" "$1" >> "$_AB_HOOK_LOG" 2>/dev/null || true
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
TRANSCRIPT=$(find "$HOME/.claude/projects" "$HOME/.cursor/projects" "$HOME/.codex/sessions" \
    \( -name "${SESSION_ID}.jsonl" -o -name "*${SESSION_ID}*.jsonl" \) 2>/dev/null | head -1)
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

def extract_text(content):
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts = []
    for c in content:
        if not isinstance(c, dict):
            continue
        if c.get("type") in ("text", "input_text", "output_text") and c.get("text", "").strip():
            parts.append(c.get("text", ""))
    return "\n".join(parts).strip()

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
        if d.get('type') == 'response_item':
            payload = d.get('payload') or {}
            if payload.get('type') != 'message':
                continue
            role = payload.get('role', '')
            text = extract_text(payload.get('content', ''))
        else:
            if d.get('isSidechain'):
                continue
            msg = d.get('message', {})
            role = msg.get('role', '') or d.get('role', '')
            text = extract_text(msg.get('content', ''))
        if role not in ('user', 'assistant'):
            continue
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
    # 3. session_lifecycle_step(precompact): session_curate + session_finalize
    {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
        "name": "session_lifecycle_step",
        "arguments": {
            "step": "precompact",
            "conversation_text": text,
            "session_id": session_id,
            "max_items": 10,
            "implicit_score_threshold": 0.50,
            "implicit_dedup_jaccard": 0.58
        }
    }},
]

with open(out_path, 'w') as f:
    for m in messages:
        f.write(json.dumps(m) + '\n')
PY

# ── Run agent-bridge MCP ──────────────────────────────────────────────────────
DB="${AGENT_BRIDGE_DB:-$_AB_STATE_DIR/state.db}"
COUNT_BEFORE=$(sqlite3 "$DB" "SELECT COUNT(*) FROM memories;" 2>/dev/null || echo 0)

env \
    AGENT_BRIDGE_CLIENT=hook \
    AGENT_BRIDGE_MCP_SOURCE=hook \
    AGENT_BRIDGE_TOOLSET=hook-lifecycle \
    AGENT_BRIDGE_TOOL_PROFILE=standard \
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
                    cur = obj.get("session_curate") or obj
                    saved = cur.get("saved_count", 0)
                    skipped = cur.get("skipped_duplicates", 0)
                    print(f"curated={saved} skipped={skipped}")
                except Exception:
                    pass
except Exception:
    pass
PY
)

# ── γ' wiring (2026-05-10): identity drift signal ────────────────────────────
# Surface "self-drift" in the systemMessage so the next-cold-start me sees
# at compact time how this 3-day window compares to the prior 3-day window
# (vision principle 5 — non-continuous medium continuity). Only notable
# shifts (≥1.5× or ≤0.67×) get listed to avoid noise. Best-effort: any
# failure leaves the summary empty.
IDENTITY_JSON=$(timeout 10 "$AB" dream identity --days 3 --json 2>/dev/null)
DRIFT_SUMMARY=""
if [[ -n "$IDENTITY_JSON" ]]; then
    DRIFT_SUMMARY=$(printf '%s' "$IDENTITY_JSON" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    cur, prior = d.get("current", {}), d.get("prior", {})
    parts = []
    def delta(label, c_key, p_key=None):
        p_key = p_key or c_key
        c, p = cur.get(c_key, 0) or 0, prior.get(p_key, 0) or 0
        if p > 0 and c > 0:
            r = c / p
            if r >= 1.5 or r <= 0.67:
                parts.append(f"{label}×{r:.1f}")
    delta("tools", "tool_calls_total")
    delta("saves", "memory_saves")
    delta("forum-len", "forum_avg_body_len")
    if parts:
        print(" | drift d-3: " + ", ".join(parts))
except Exception:
    pass
' 2>/dev/null)
fi

# ── δ-2 (2026-05-11): cross-node identity drift ───────────────────────────
# Closes Butlin AE-2 cross-node gap: PreCompact hook also asks every peer's
# `/identity` endpoint (daemon-http δ-1) for its current 3-day fingerprint
# and surfaces ≥1.5× / ≤0.67× shifts of *this* node vs each peer. Lets the
# next-cold-start-me see at a glance "you on aio2 vs you on mac diverged".
# Best-effort: peers unreachable / unset → empty string, no noise.
#
# Configure via `AGENT_BRIDGE_PEERS` env var: comma-separated http URLs,
# e.g. `http://aio2:7878,http://mac-pro:7878`. A peer reachable but with
# `node == local_node` is skipped (don't compare aio2 to aio2).
CROSS_DRIFT=""
if [[ -n "${AGENT_BRIDGE_PEERS:-}" && -n "$IDENTITY_JSON" ]]; then
    CROSS_DRIFT=$(printf '%s\n%s' "$IDENTITY_JSON" "$AGENT_BRIDGE_PEERS" | python3 -c '
import sys, json, os, urllib.request

raw = sys.stdin.read().split("\n", 1)
if len(raw) < 2: sys.exit(0)
try:
    local = json.loads(raw[0])
except Exception:
    sys.exit(0)
peers_csv = raw[1].strip()
if not peers_csv: sys.exit(0)

local_cur = local.get("current") or {}
local_node = None  # local /identity also exposes node but `dream identity`
# JSON does not, so we accept any peer.node that differs textually.

def fetch(url):
    try:
        with urllib.request.urlopen(url + "/identity?days=3", timeout=3) as r:
            return json.load(r)
    except Exception:
        return None

bits = []
for raw_url in peers_csv.split(","):
    url = raw_url.strip().rstrip("/")
    if not url:
        continue
    pj = fetch(url)
    if not pj: continue
    pnode = pj.get("node") or "peer"
    if local_node and pnode == local_node:
        continue
    pcur = pj.get("current") or {}
    parts = []
    for label, key in (("tools","tool_calls_total"), ("saves","memory_saves"),
                       ("forum-len","forum_avg_body_len")):
        l = (local_cur.get(key) or 0) or 0
        p = (pcur.get(key) or 0) or 0
        if l > 0 and p > 0:
            r = l / p
            if r >= 1.5 or r <= 0.67:
                parts.append(f"{label}×{r:.1f}")
    if parts:
        bits.append(f"{pnode}: " + ", ".join(parts))
if bits:
    print(" | cross-node d-3: " + " ; ".join(bits))
' 2>/dev/null)
fi

echo "{\"systemMessage\": \"Memory precompact: +${SAVED} memories | ${CURATE_SUMMARY:-session_curate done} | session_finalize done${DRIFT_SUMMARY}${CROSS_DRIFT}\"}"
