#!/usr/bin/env bash
# UserPromptSubmit hook — inject scope-relevant agent-bridge memories.
#
# v5.0 (2026-07-05): route through session_bootstrap (true semantic ranking).
#   - Primary path spawns the local `agent-bridge mcp` server and calls
#     session_bootstrap(query=<user prompt>): GTE semantic ranking, feedback
#     preamble, work_memory slot, continuity kernel, retrieval-class quotas —
#     all server-side and identical to what agents get when they call
#     session_bootstrap themselves. Cold spawn is ~0.2 s on hosts with the
#     shared-embedding daemon (MCP delegates query embedding to /embed).
#   - The v4 pure-SQL static block remains as the fallback path (MCP failure,
#     timeout, empty result, or AB_MEMORY_HOOK_STATIC=1) and is labelled
#     `static-fallback` in its header so live output identifies the path.
#   - Drops the always-inject access_count self-bump: it was a ranking
#     flywheel (injected → access up → static rank higher → injected more)
#     and it silently no-oped on hosts without the sqlite3 CLI anyway.
#   - Env: AB_MEMORY_HOOK_STATIC=1 forces the legacy static path;
#     AB_MEMORY_HOOK_AB_BIN overrides the agent-bridge binary (tests).
#
# v4.0 (2026-05-19): A1 cooldown softening per docs/DESIGN-A1-B1-B3-RECALL-TIMING-v0.md §2.2.
#   - The v3.0 one-shot lock fired memory injection only once per session
#     (audit-gap A1 root cause: 17 untouched §6.5 working-def gap).
#   - Lock file now stores a per-session turn counter; injection re-fires
#     every AB_MEMORY_COOLDOWN_TURNS turns (default 8 per locked P-A1).
#   - Drift dim DROPPED per PROBE-A1-DRIFT-CALIBRATION-2026-05-17.md
#     (drift primitive could not separate same vs cross topic at any threshold).
#   - Ranked payload capped at top-8 (was top-20) per design §2.2.
#     concept+session_handoff always-inject unchanged at top-15 (L0 navigation).
#   - Opt-out: AB_MEMORY_COOLDOWN_TURNS=999999 effectively restores v3.0 one-shot.
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

_ab_active_pet_id() {
    python3 - <<'PY' 2>/dev/null || printf '%s\n' 'xiao-shu-v2'
import json
import os

def clean(value):
    value = (value or "").strip()
    cleaned = "".join(
        ch for ch in value
        if ch.isascii() and (ch.isalnum() or ch in "-_")
    )
    return cleaned or None

env_pet = clean(os.environ.get("AB_PET_ID"))
if env_pet:
    print(env_pet)
    raise SystemExit(0)

path = os.path.join(os.path.expanduser("~"), ".codex", ".codex-global-state.json")
try:
    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)
    selected = (
        state.get("electron-persisted-atom-state", {})
        .get("selected-avatar-id", "")
    )
    if selected.startswith("custom:"):
        pet = clean(selected.removeprefix("custom:"))
        if pet:
            print(pet)
            raise SystemExit(0)
except Exception:
    pass

print("xiao-shu-v2")
PY
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

_ab_pet_state_write() {
    [[ "${AB_PET_STATE_DISABLE:-}" == "1" ]] && return 0
    local pet_id
    pet_id="$(_ab_active_pet_id)"
    pet_id="${pet_id:-xiao-shu-v2}"
    local reason="user prompt submitted; agent is orienting"
    AB_HOOK_PAYLOAD="$HOOK_PAYLOAD" python3 - "$_AB_STATE_DIR" "$pet_id" "$SESSION_ID" "${PWD:-/}" "$reason" <<'PY' >/dev/null 2>&1 || true
import datetime
import json
import os
import tempfile
import sys

state_dir, pet_id, session_id, cwd, reason = sys.argv[1:6]
pet_id = "".join(
    ch for ch in pet_id
    if ch.isascii() and (ch.isalnum() or ch in "-_")
) or "xiao-shu-v2"
project = os.path.basename(cwd.rstrip(os.sep)) or cwd

# Payload is parsed only to accept session id variants. Prompt text is
# intentionally not persisted in pet state.
try:
    payload = json.loads(os.environ.get("AB_HOOK_PAYLOAD", "") or "{}")
    session_id = payload.get("session_id") or payload.get("sessionId") or session_id
except Exception:
    pass

now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
state = {
    "schema_version": 1,
    "pet_id": pet_id,
    "project": project,
    "cwd": cwd,
    "mode": "orienting",
    "mood": "calm",
    "reason": reason,
    "last_event": "UserPromptSubmit",
    "last_verified_at": None,
    "voice_line": None,
    "ritual": None,
    "source": "ab-memory-hook",
    "session_id": session_id,
    "updated_at": now,
}

out_dir = os.path.join(state_dir, "pet_state")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, f"{pet_id}.json")
fd, tmp_path = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=out_dir)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, out_path)
finally:
    if os.path.exists(tmp_path):
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
PY
}
_ab_pet_state_write

[[ -f "$DB" ]] || exit 0

LOCK="/tmp/ab-mem-injected-${SESSION_ID}"
COOLDOWN_TURNS="${AB_MEMORY_COOLDOWN_TURNS:-8}"
COUNT=$(cat "$LOCK" 2>/dev/null || echo "0")
case "$COUNT" in
    ''|*[!0-9]*) COUNT=0 ;;
esac
COUNT=$((COUNT + 1))
printf '%s\n' "$COUNT" > "$LOCK"
# Fire on turns 1, 1+N, 1+2N, ... (cooldown softening per A1 v0; drift dim dropped).
if (( COOLDOWN_TURNS > 0 )) && (( (COUNT - 1) % COOLDOWN_TURNS != 0 )); then
    exit 0
fi

CWD="${PWD:-/}"

# ── v5.0 primary path: session_bootstrap via local MCP (semantic ranking) ─────
AB_BIN="${AB_MEMORY_HOOK_AB_BIN:-$(command -v agent-bridge 2>/dev/null || echo "$HOME/.local/bin/agent-bridge")}"
OUTPUT=""
if [[ "${AB_MEMORY_HOOK_STATIC:-}" != "1" && -x "$AB_BIN" ]]; then
    OUTPUT=$(AB_HOOK_PAYLOAD="$HOOK_PAYLOAD" timeout 4 python3 - "$AB_BIN" <<'PY' 2>/dev/null
import json, os, re, subprocess, sys

AB = sys.argv[1]

prompt = ""
try:
    payload = json.loads(os.environ.get("AB_HOOK_PAYLOAD", "") or "{}")
    prompt = str(payload.get("prompt") or "")
except Exception:
    pass
# Collapse whitespace; cap so a pasted wall of text stays a cheap query.
query = re.sub(r"\s+", " ", prompt).strip()[:300]

args = {"query": query} if query else {}
msgs = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2024-11-05", "capabilities": {},
        "clientInfo": {"name": "ab-memory-hook", "version": "5.0"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
        "name": "session_bootstrap", "arguments": args}},
]
inp = "\n".join(json.dumps(m) for m in msgs) + "\n"
try:
    proc = subprocess.run(
        [AB, "mcp"], input=inp, capture_output=True, text=True, timeout=3.5,
    )
except Exception:
    sys.exit(1)

text = ""
for line in proc.stdout.splitlines():
    try:
        d = json.loads(line)
    except Exception:
        continue
    if d.get("id") == 2:
        result = d.get("result") or {}
        if result.get("isError"):
            sys.exit(1)
        content = result.get("content") or []
        if content and isinstance(content[0], dict):
            text = str(content[0].get("text") or "")

text = text.strip()
if not text or text.startswith("(no scoped memories"):
    sys.exit(1)

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": text,
    }
}))
PY
    ) || OUTPUT=""
fi

# ── Fallback: v4 pure-SQL static ranking (daemon-free, ~10-50 ms) ─────────────
if [[ -z "$OUTPUT" ]]; then
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
    f"ORDER BY {KIND_TIER}, {RANK} DESC LIMIT 8"
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
    f"=== Agent-Bridge Memory (scope: {CWD} | static-fallback) ===\n"
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
fi

_OUT_BYTES=${#OUTPUT}
trap "_ab_log_hook_run \$? $_OUT_BYTES" EXIT
printf '%s' "$OUTPUT"
