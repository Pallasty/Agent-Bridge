#!/usr/bin/env bash
# PostToolUse hook — ground the avatar embodiment state in the real tool event.
#
# Companion to ab-memory-hook.sh (UserPromptSubmit). That hook grounds only the
# "just got a prompt -> orienting" edge, leaving the state stuck at orienting /
# calm / focus=null for the rest of the turn. This hook grounds `focus` (= the
# tool's target) and activity=working from each tool use, and writes a
# `*_source` provenance marker for every truth-claim field so that
# pet_ground::audit_grounding can tell grounded fields from decoration.
#
# Gated: no-op unless AB_PET_GROUND_TOOLS=1 (opt-in; avoids per-tool cost until
# the owner enables it). The grounding contract — focus derivation, activity
# vocabulary, provenance — mirrors crates/bridge/src/pet_ground.rs, which is the
# tested single source of truth (an e2e test audits this hook's output).

set -u

[[ "${AB_PET_GROUND_TOOLS:-}" == "1" ]] || exit 0
[[ "${AB_MEMORY_CURATOR:-}" == "1" ]] && exit 0
[[ "${AB_PET_STATE_DISABLE:-}" == "1" ]] && exit 0

_ab_state_dir() {
    if [[ -n "${XDG_DATA_HOME:-}" ]]; then
        printf '%s/agent-bridge' "$XDG_DATA_HOME"
    elif [[ "$(uname -s 2>/dev/null || echo "")" == "Darwin" ]]; then
        printf '%s/Library/Application Support/agent-bridge' "$HOME"
    else
        printf '%s/.local/share/agent-bridge' "$HOME"
    fi
}

HOOK_PAYLOAD=$(cat 2>/dev/null || true)

AB_HOOK_PAYLOAD="$HOOK_PAYLOAD" python3 - "$(_ab_state_dir)" "${PWD:-/}" <<'PY' >/dev/null 2>&1 || true
import datetime
import json
import os
import sys
import tempfile

state_dir, shell_cwd = sys.argv[1:3]


def clean_pet_id(value):
    value = (value or "").strip()
    cleaned = "".join(
        ch for ch in value if ch.isascii() and (ch.isalnum() or ch in "-_")
    )
    return cleaned or None


pet_id = clean_pet_id(os.environ.get("AB_PET_ID")) or "xiao-shu-v2"

try:
    payload = json.loads(os.environ.get("AB_HOOK_PAYLOAD", "") or "{}")
    if not isinstance(payload, dict):
        payload = {}
except Exception:
    payload = {}

event = payload.get("hook_event_name") or payload.get("hookEventName") or "PostToolUse"
tool_name = payload.get("tool_name") or payload.get("toolName") or ""
tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
if not isinstance(tool_input, dict):
    tool_input = {}
session_id = payload.get("session_id") or payload.get("sessionId") or ""
cwd = payload.get("cwd") or shell_cwd

# Mirror pet_ground::derive_focus_from_tool — never invent a target.
TARGET_KEYS = {
    "Edit": "file_path",
    "Write": "file_path",
    "Read": "file_path",
    "NotebookEdit": "file_path",
    "memory_get": "key",
    "memory_save": "key",
    "memory_delete": "key",
    "Bash": "description",
    "shell_exec": "description",
}
base = tool_name.rsplit("__", 1)[-1]
focus_key = TARGET_KEYS.get(base)
focus = ""
if focus_key:
    raw = tool_input.get(focus_key)
    if isinstance(raw, str):
        focus = raw.strip()

# Mirror pet_ground::activity_for_event.
activity = {
    "UserPromptSubmit": "orienting",
    "PostToolUse": "working",
    "PreToolUse": "working",
    "Stop": "idle",
    "Notification": "waiting_for_user",
}.get(event, "working")

out_dir = os.path.join(state_dir, "pet_state")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, f"{pet_id}.json")

# Preserve existing sidecar fields; ground the embodiment fields on top. We do
# NOT touch fields we are not grounding (e.g. a pre-existing decorative `mood`):
# leaving it lets audit_grounding keep flagging it honestly.
state = {}
try:
    with open(out_path, "r", encoding="utf-8") as f:
        existing = json.load(f)
    if isinstance(existing, dict):
        state = existing
except Exception:
    state = {}

now = (
    datetime.datetime.now(datetime.timezone.utc)
    .replace(microsecond=0)
    .isoformat()
    .replace("+00:00", "Z")
)
state.setdefault("schema_version", 1)
state["pet_id"] = pet_id
state["project"] = os.path.basename(cwd.rstrip(os.sep)) or cwd
state["cwd"] = cwd
state["mode"] = activity
state["activity_state"] = activity
state["last_event"] = event
if activity == "idle":
    # Idle clears focus — mirror pet_ground::ground_patch (not attending).
    state["focus"] = None
    state["focus_source"] = None
elif focus:
    state["focus"] = focus
    state["focus_source"] = f"tool:{tool_name}"
if session_id:
    state["session_id"] = session_id
# Mirror pet_ground::derive_reason — restate activity+focus; never invent motive.
# Grounding reason here stops a stale constant from another hook from lingering.
if activity == "orienting":
    reason = "orienting to the new prompt"
elif activity == "idle":
    reason = "idle — last task complete, awaiting next"
elif activity == "waiting_for_user":
    reason = "waiting for user input"
elif focus:
    reason = f"{activity}: {focus}"
else:
    reason = activity
state["reason"] = reason
state["reason_source"] = "ab-pet-ground"
state["source"] = "ab-pet-ground"
state["updated_at"] = now

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
