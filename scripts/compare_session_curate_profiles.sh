#!/usr/bin/env bash
# Compare session_curate profile behavior on the same input.
#
# Usage examples:
#   ./scripts/compare_session_curate_profiles.sh \
#       --transcript "/path/to/session.jsonl"
#
#   ./scripts/compare_session_curate_profiles.sh \
#       --conversation-file ./tmp/convo.txt
#
# Notes:
# - For transcript input, this script mirrors the precompact hook extraction logic
#   (recent turns + section-bullet marker normalization).
# - Calls `session_curate` in dry_run mode over stdio MCP and compares outputs.

set -euo pipefail

AB="$(command -v agent-bridge 2>/dev/null || true)"
[[ -z "$AB" && -x "${HOME}/.local/bin/agent-bridge" ]] && AB="${HOME}/.local/bin/agent-bridge"
if [[ ! -x "$AB" ]]; then
    echo "FAIL: agent-bridge not found (install or add ~/.local/bin to PATH)" >&2
    exit 1
fi

TRANSCRIPT=""
CONVERSATION_FILE=""
MAX_ITEMS=20
TURN_LIMIT=80
CHAR_LIMIT=16000
JSON_OUT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --transcript)
            TRANSCRIPT="${2:-}"
            shift 2
            ;;
        --conversation-file)
            CONVERSATION_FILE="${2:-}"
            shift 2
            ;;
        --max-items)
            MAX_ITEMS="${2:-20}"
            shift 2
            ;;
        --turn-limit)
            TURN_LIMIT="${2:-80}"
            shift 2
            ;;
        --char-limit)
            CHAR_LIMIT="${2:-16000}"
            shift 2
            ;;
        --json-out)
            JSON_OUT="${2:-}"
            shift 2
            ;;
        *)
            echo "Unknown arg: $1" >&2
            exit 1
            ;;
    esac
done

if [[ -z "$TRANSCRIPT" && -z "$CONVERSATION_FILE" ]]; then
    echo "Usage: $0 --transcript <session.jsonl> | --conversation-file <text-file>" >&2
    exit 1
fi

if [[ -n "$TRANSCRIPT" && ! -f "$TRANSCRIPT" ]]; then
    echo "FAIL: transcript not found: $TRANSCRIPT" >&2
    exit 1
fi
if [[ -n "$CONVERSATION_FILE" && ! -f "$CONVERSATION_FILE" ]]; then
    echo "FAIL: conversation file not found: $CONVERSATION_FILE" >&2
    exit 1
fi

TMPDIR_RUN="$(mktemp -d "${TMPDIR:-/tmp}/ab-compare-curate-XXXXXX")"
export TMPDIR_RUN
trap 'rm -rf "$TMPDIR_RUN"' EXIT

TEXT_FILE="$TMPDIR_RUN/conversation.txt"
if [[ -n "$CONVERSATION_FILE" ]]; then
    cp "$CONVERSATION_FILE" "$TEXT_FILE"
else
    python3 - "$TRANSCRIPT" "$TEXT_FILE" "$TURN_LIMIT" "$CHAR_LIMIT" <<'PY'
import json
import re
import sys

transcript, out_path, turn_limit_s, char_limit_s = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
turn_limit = int(turn_limit_s)
char_limit = int(char_limit_s)

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
BULLET_RE = re.compile(r"^[-*+•]\s+|^\d+\.\s+")

def detect_section(line: str):
    bare = line.strip().strip("*").rstrip(":").strip().lower()
    return SECTION_KINDS.get(bare)

def strip_bullet(line: str):
    m = BULLET_RE.match(line.strip())
    return line.strip()[m.end():].strip() if m else None

turns = []
with open(transcript, "r", encoding="utf-8") as f:
    for raw in f:
        raw = raw.strip()
        if not raw:
            continue
        try:
            d = json.loads(raw)
        except Exception:
            continue
        if d.get("isSidechain"):
            continue
        msg = d.get("message", {})
        role = msg.get("role", "") or d.get("role", "")
        if role not in ("user", "assistant"):
            continue
        content = msg.get("content", "")
        text = ""
        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            parts = [
                c.get("text", "")
                for c in content
                if isinstance(c, dict) and c.get("type") == "text" and c.get("text", "").strip()
            ]
            text = "\n".join(parts).strip()
        if not text:
            continue
        skip = ("<local-command", "<system-reminder", "<command-name", "<command-message", "<command-args")
        if any(text.startswith(p) for p in skip):
            continue
        turns.append((role, text[:1200]))

recent = turns[-turn_limit:]
out_lines = []
for role, text in recent:
    out_lines.append(f"[{role.upper()}]")
    if role == "assistant":
        section_kind = None
        blank_streak = 0
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                blank_streak += 1
                if blank_streak >= 2:
                    section_kind = None
                out_lines.append("")
                continue
            blank_streak = 0
            kind = detect_section(stripped)
            if kind:
                section_kind = kind
                out_lines.append(line)
                continue
            payload = strip_bullet(stripped)
            if payload and section_kind and len(payload) >= 8:
                out_lines.append(f"{section_kind}: {payload}")
            else:
                out_lines.append(line)
    else:
        out_lines.append(text)
    out_lines.append("")

text = "\n".join(out_lines)
if len(text) > char_limit:
    text = text[-char_limit:]

with open(out_path, "w", encoding="utf-8") as f:
    f.write(text)
PY
fi

python3 - "$TEXT_FILE" "$MAX_ITEMS" "$AB" "$JSON_OUT" <<'PY'
import collections
import json
import subprocess
import sys
from typing import Any, Dict, List

text_path, max_items_s, ab, json_out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
max_items = int(max_items_s)
text = open(text_path, "r", encoding="utf-8").read()

profiles = [
    ("baseline", None, None),
    ("balanced", 0.50, 0.58),
    ("strict", 0.58, 0.62),
    ("aggressive", 0.40, 0.52),
]

def call_curate(score_th, dedup_th) -> Dict[str, Any]:
    args: Dict[str, Any] = {
        "conversation_text": text,
        "dry_run": True,
        "max_items": max_items,
    }
    if score_th is not None:
        args["implicit_score_threshold"] = score_th
    if dedup_th is not None:
        args["implicit_dedup_jaccard"] = dedup_th

    msgs = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "compare-session-curate", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "session_curate", "arguments": args},
        },
    ]
    payload = "\n".join(json.dumps(m) for m in msgs) + "\n"
    p = subprocess.run([ab, "mcp"], input=payload, text=True, capture_output=True, timeout=30)
    for line in p.stdout.splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("id") != 2:
            continue
        if d.get("error"):
            return {"error": d["error"]}
        for item in d.get("result", {}).get("content", []):
            t = item.get("text", "")
            try:
                return json.loads(t)
            except Exception:
                pass
    return {"error": "no session_curate result payload"}

runs: Dict[str, Dict[str, Any]] = {}
for name, s, d in profiles:
    runs[name] = call_curate(s, d)

print("== session_curate profile comparison ==")
print(f"input_chars={len(text)} max_items={max_items}")

for name, payload in runs.items():
    if "error" in payload:
        print(f"- {name}: ERROR {payload['error']}")
        continue
    cands = payload.get("candidates", [])
    kinds = collections.Counter(c.get("kind", "?") for c in cands)
    implicit = sum(1 for c in cands if "implicit" in c.get("tags", []))
    opts = payload.get("options", {})
    print(
        f"- {name}: total={len(cands)} implicit={implicit} kinds={dict(kinds)} "
        f"opts={opts}"
    )

baseline_payload = runs.get("baseline", {})
diffs: Dict[str, Dict[str, Any]] = {}
if "error" not in baseline_payload:
    base_set = {
        (c.get("kind", "?"), c.get("content", ""))
        for c in baseline_payload.get("candidates", [])
    }
    for name in ("balanced", "strict", "aggressive"):
        payload = runs.get(name, {})
        if "error" in payload:
            continue
        cur_set = {(c.get("kind", "?"), c.get("content", "")) for c in payload.get("candidates", [])}
        only_cur = list(cur_set - base_set)
        only_base = list(base_set - cur_set)
        diffs[name] = {
            f"only_{name}_count": len(only_cur),
            "only_baseline_count": len(only_base),
            f"only_{name}_samples": [
                {"kind": k, "content": c} for (k, c) in only_cur[:10]
            ],
            "only_baseline_samples": [
                {"kind": k, "content": c} for (k, c) in only_base[:10]
            ],
        }
        print(f"\n[{name} vs baseline]")
        print(f"  only_{name}={len(only_cur)} only_baseline={len(only_base)}")
        for label, rows in ((f"only_{name}", only_cur[:3]), ("only_baseline", only_base[:3])):
            if not rows:
                continue
            print(f"  {label} samples:")
            for k, c in rows:
                snippet = c.replace("\n", " ")[:140]
                print(f"    - ({k}) {snippet}")

if json_out:
    summary: Dict[str, Any] = {
        "input_chars": len(text),
        "max_items": max_items,
        "profiles": {},
        "diffs_vs_baseline": diffs,
    }
    for name, payload in runs.items():
        if "error" in payload:
            summary["profiles"][name] = {"error": payload["error"]}
            continue
        cands = payload.get("candidates", [])
        kinds = collections.Counter(c.get("kind", "?") for c in cands)
        implicit = sum(1 for c in cands if "implicit" in c.get("tags", []))
        summary["profiles"][name] = {
            "total": len(cands),
            "implicit": implicit,
            "kinds": dict(kinds),
            "options": payload.get("options", {}),
            "candidates": cands,
        }
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nJSON report written: {json_out}")
PY

