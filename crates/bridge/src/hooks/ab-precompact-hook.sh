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
# Match the MCP wrapper's trusted per-machine configuration. Direct IDE hooks
# do not inherit the wrapper environment. Never print this file (may contain keys).
_AB_MACHINE_ENV="${AGENT_BRIDGE_MACHINE_ENV:-$HOME/.config/agent-bridge/machine.env}"
if [[ -f "$_AB_MACHINE_ENV" ]]; then
    . "$_AB_MACHINE_ENV" >/dev/null 2>&1
fi
unset _AB_MACHINE_ENV

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
_AB_HOOK_OUTPUT_BYTES=0
_AB_EFFECT_STATUS=unknown
_AB_EFFECT_CODE=hook_did_not_reach_outcome
_AB_EFFECT_ACTUAL=none
_ab_log_hook_run() {
    mkdir -p "$(dirname "$_AB_HOOK_LOG")"
    python3 - "$_AB_HOOK_LOG" "$_AB_HOOK_EVENT" "$_AB_HOOK_START" "$1" \
        "$_AB_HOOK_OUTPUT_BYTES" "$_AB_EFFECT_STATUS" "$_AB_EFFECT_CODE" \
        "$_AB_EFFECT_ACTUAL" "${SESSION_ID:-}" <<'PY_RECEIPT' 2>/dev/null || true
import hashlib, json, sys
path, event, ts, exit_code, size, status, code, actual, session = sys.argv[1:]
row = {"event": event, "ts": ts, "exit_code": int(exit_code), "output_bytes": int(size),
       "session_id_sha256": hashlib.sha256(session.encode()).hexdigest() if session else None,
       "effect_feedback": {"status": status, "code": code,
           "requested": "session_lifecycle_precompact", "actual": actual, "dropped": [],
           "verification_scope": "hook_and_mcp_response_only"}}
with open(path, "a", encoding="utf-8") as stream:
    stream.write(json.dumps(row) + "\n")
PY_RECEIPT
}
trap '_ab_log_hook_run $?' EXIT

# ── Parse session_id ──────────────────────────────────────────────────────────
HOOK_PAYLOAD=$(cat 2>/dev/null || true)
SESSION_ID=$(printf '%s' "$HOOK_PAYLOAD" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
    session = d.get("session_id") or d.get("sessionId") or ""
    if isinstance(session, str): print(session)
except Exception:
    pass
' 2>/dev/null)
SESSION_ID="${SESSION_ID:-${CLAUDE_SESSION_ID:-}}"
if [[ -z "$SESSION_ID" ]]; then
    _AB_EFFECT_STATUS=skipped; _AB_EFFECT_CODE=session_id_missing
    exit 0
fi

AB=$(command -v agent-bridge 2>/dev/null || echo "$HOME/.local/bin/agent-bridge")
if [[ ! -x "$AB" ]]; then
    _AB_EFFECT_STATUS=skipped; _AB_EFFECT_CODE=binary_missing
    exit 0
fi

# ── Locate transcript ─────────────────────────────────────────────────────────
TRANSCRIPT=$(find "$HOME/.claude/projects" "$HOME/.cursor/projects" "$HOME/.codex/sessions" \
    \( -name "${SESSION_ID}.jsonl" -o -name "*${SESSION_ID}*.jsonl" \) 2>/dev/null | head -1)
if [[ ! -f "$TRANSCRIPT" ]]; then
    _AB_EFFECT_STATUS=skipped; _AB_EFFECT_CODE=transcript_missing
    exit 0
fi

# ── Temp workspace ────────────────────────────────────────────────────────────
TMPDIR_HOOK=$(mktemp -d /tmp/ab-precompact-XXXXXX) || {
    _AB_EFFECT_STATUS=failed; _AB_EFFECT_CODE=temporary_workspace_failed
    exit 0
}
_ab_cleanup() {
    local code=$?
    rm -rf "$TMPDIR_HOOK"
    _ab_log_hook_run "$code"
}
trap _ab_cleanup EXIT

CONVO_FILE="$TMPDIR_HOOK/convo.txt"
MCP_IN="$TMPDIR_HOOK/mcp-input.jsonl"
MCP_OUT="$TMPDIR_HOOK/mcp-output.txt"

# ── Extract + pre-process conversation ────────────────────────────────────────
# Produces a text file where bullet items under recognised section headers are
# rewritten to explicit marker prefixes so session_curate can detect them.
python3 - "$TRANSCRIPT" "$CONVO_FILE" <<'PY' 2>/dev/null
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

if [[ $? -ne 0 ]]; then
    _AB_EFFECT_STATUS=failed; _AB_EFFECT_CODE=transcript_read_failed
    exit 0
fi
if [[ ! -s "$CONVO_FILE" ]]; then
    _AB_EFFECT_STATUS=skipped; _AB_EFFECT_CODE=conversation_empty
    exit 0
fi

# ── Build MCP JSON-RPC messages ───────────────────────────────────────────────
python3 - "$CONVO_FILE" "$SESSION_ID" "$MCP_IN" <<'PY'
import json, os, sys

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
            "cwd": os.getcwd(),
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
if [[ $? -ne 0 ]]; then
    _AB_EFFECT_STATUS=failed; _AB_EFFECT_CODE=request_build_failed
    exit 0
fi

# ── Run agent-bridge MCP ──────────────────────────────────────────────────────
# The curator only runs the LOCAL `agent-bridge mcp` server against the on-disk
# store (session_lifecycle_step → curate/finalize); it makes no Anthropic API
# call, so it must NOT inherit the parent session's OAuth/API credentials.
# Start from an empty environment (env -i) and pass through only a safe base
# plus agent-bridge's own non-secret config (AGENT_BRIDGE_*, including the
# AGENT_BRIDGE_CURATE_* tuning knobs, and XDG_* so the child resolves the same
# store path as the hook). CLAUDE_*, ANTHROPIC_*, *_TOKEN, *_KEY drop.
# Enumerate via bash builtins (${!PREFIX@}) — never via `env`, which a user
# PATH shim (~/.local/bin/env) can shadow with a non-coreutils wrapper. Use the
# absolute /usr/bin/env (real coreutils on Linux + macOS) for `-i` isolation.
_AB_ENV_PASS=()
for _k in ${!AGENT_BRIDGE_@}; do
    _AB_ENV_PASS+=("$_k=${!_k}")
done
for _k in XDG_DATA_HOME XDG_CONFIG_HOME XDG_RUNTIME_DIR; do
    [[ -n "${!_k:-}" ]] && _AB_ENV_PASS+=("$_k=${!_k}")
done

/usr/bin/env -i \
    PATH="$PATH" HOME="$HOME" USER="${USER:-}" LOGNAME="${LOGNAME:-}" \
    LANG="${LANG:-}" LC_ALL="${LC_ALL:-}" TERM="${TERM:-}" TMPDIR="${TMPDIR:-}" \
    "${_AB_ENV_PASS[@]}" \
    AGENT_BRIDGE_CLIENT=hook \
    AGENT_BRIDGE_MCP_SOURCE=hook \
    AGENT_BRIDGE_TOOLSET=hook-lifecycle \
    AGENT_BRIDGE_TOOL_PROFILE=standard \
    timeout 25 "$AB" mcp < "$MCP_IN" > "$MCP_OUT" 2>/dev/null
_AB_MCP_EXIT=$?

# ── Inspect the matching response, never infer completion from process exit. ──
# A timeout/error can follow partial writes: "not_confirmed" does not mean none.
# Counts come from this call's result, not a delta in a concurrently written DB.
python3 - "$MCP_OUT" "$_AB_MCP_EXIT" > "$TMPDIR_HOOK/outcome.txt" <<'PY'
import json, sys

def outcome(status, code, actual="not_confirmed", summary=None):
    return status, code, actual, summary or f"lifecycle completion not confirmed ({code})"

def count(value):
    return type(value) is int and value >= 0

def inspect():
    rc = int(sys.argv[2])
    if rc in (124, 137): return outcome("unknown", "lifecycle_timeout")
    if rc != 0: return outcome("failed", "lifecycle_process_failed")
    replies = []
    for line in open(sys.argv[1], encoding="utf-8"):
        try: item = json.loads(line)
        except ValueError: continue
        if isinstance(item, dict) and item.get("id") == 2: replies.append(item)
    if not replies: return outcome("unknown", "lifecycle_response_missing")
    if len(replies) != 1: return outcome("unknown", "lifecycle_response_invalid")
    reply = replies[0]
    if "error" in reply: return outcome("failed", "lifecycle_rpc_error")
    result = reply.get("result")
    if not isinstance(result, dict): return outcome("unknown", "lifecycle_response_invalid")
    if result.get("isError") is True: return outcome("failed", "lifecycle_tool_error")
    if result.get("isError", False) is not False:
        return outcome("unknown", "lifecycle_response_invalid")
    objects = []
    for item in result.get("content", []):
        if not isinstance(item, dict) or item.get("type") != "text": continue
        try: objects.append(json.loads(item.get("text", "")))
        except (ValueError, TypeError): continue
    if len(objects) != 1 or not isinstance(objects[0], dict):
        return outcome("unknown", "lifecycle_response_invalid")
    obj = objects[0]
    cur, fin, work = (obj.get(k) for k in ("session_curate", "session_finalize", "work_memory"))
    if obj.get("step") != "precompact" or not all(isinstance(v, dict) for v in (cur, fin, work)):
        return outcome("unknown", "lifecycle_response_invalid")
    if (cur.get("dry_run") is not False or fin.get("dry_run") is not False
            or not all(count(cur.get(k)) for k in ("saved_count", "skipped_duplicates"))
            or not isinstance(cur.get("errors"), list) or type(work.get("saved")) is not bool
            or not count(fin.get("removed_count")) or not isinstance(fin.get("decay"), dict)
            or not count(fin["decay"].get("archived_count"))):
        return outcome("unknown", "lifecycle_response_invalid")
    counts = (f"curated={cur['saved_count']} skipped={cur['skipped_duplicates']} "
              f"removed={fin['removed_count']} decay_archived={fin['decay']['archived_count']}")
    if cur['errors'] or not work['saved']:
        return outcome("degraded", "lifecycle_partial_result", "lifecycle_response",
                       "lifecycle reported partial result; " + counts + "; completion not confirmed")
    return outcome("completed", "lifecycle_completed", "lifecycle_response",
                   "lifecycle response confirmed; " + counts)

try: values = inspect()
except Exception: values = outcome("unknown", "lifecycle_response_invalid")
print("\n".join(values))
PY
if [[ $? -eq 0 ]]; then
    {
        IFS= read -r _AB_EFFECT_STATUS
        IFS= read -r _AB_EFFECT_CODE
        IFS= read -r _AB_EFFECT_ACTUAL
        IFS= read -r CURATE_SUMMARY
    } < "$TMPDIR_HOOK/outcome.txt"
else
    _AB_EFFECT_STATUS=unknown; _AB_EFFECT_CODE=lifecycle_response_invalid
    _AB_EFFECT_ACTUAL=not_confirmed
    CURATE_SUMMARY="lifecycle completion not confirmed (lifecycle_response_invalid)"
fi

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

_AB_OUTPUT=$(python3 - "$CURATE_SUMMARY" "$DRIFT_SUMMARY" "$CROSS_DRIFT" <<'PY'
import json, sys
print(json.dumps({"systemMessage": "Memory precompact: " + "".join(sys.argv[1:])}))
PY
)
_AB_HOOK_OUTPUT_BYTES=$(printf '%s\n' "$_AB_OUTPUT" | wc -c | tr -d ' ')
printf '%s\n' "$_AB_OUTPUT"
