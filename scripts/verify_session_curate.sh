#!/usr/bin/env bash
# Smoke-test session_curate over stdio MCP: dry_run, resolved `options`, optional overrides.
# Usage: ./scripts/verify_session_curate.sh
# Requires: agent-bridge on PATH or ~/.local/bin/agent-bridge, python3, timeout.

set -euo pipefail

AB="$(command -v agent-bridge 2>/dev/null || true)"
[[ -z "$AB" && -x "${HOME}/.local/bin/agent-bridge" ]] && AB="${HOME}/.local/bin/agent-bridge"
if [[ ! -x "$AB" ]]; then
    echo "FAIL: agent-bridge not found (install or add ~/.local/bin to PATH)" >&2
    exit 1
fi

TMPDIR_RUN="$(mktemp -d "${TMPDIR:-/tmp}/ab-verify-curate-XXXXXX")"
export TMPDIR_RUN
trap 'rm -rf "$TMPDIR_RUN"' EXIT

export VERIFY_SAMPLE='lesson: run cargo check before build
We found that the naive retry loop was exhausting the connection pool under load.'

run_mcp() {
    local inp="$1"
    local out="$2"
    timeout 20 "$AB" mcp < "$inp" > "$out" 2>&1 || true
}

python3 <<PY
import json, os

sample = os.environ["VERIFY_SAMPLE"]
base = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "verify-session-curate", "version": "1"}
    }},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
]

def write(path, args):
    msgs = base + [
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "session_curate",
            "arguments": args,
        }},
    ]
    with open(path, "w") as f:
        for m in msgs:
            f.write(json.dumps(m) + "\n")

out_dir = "${TMPDIR_RUN}"
write(
    os.path.join(out_dir, "in1.jsonl"),
    {
        "conversation_text": sample,
        "dry_run": True,
        "max_items": 8,
    },
)
write(
    os.path.join(out_dir, "in2.jsonl"),
    {
        "conversation_text": sample,
        "dry_run": True,
        "max_items": 8,
        "implicit_score_threshold": 0.72,
        "implicit_dedup_jaccard": 0.61,
    },
)
PY

run_mcp "$TMPDIR_RUN/in1.jsonl" "$TMPDIR_RUN/out1.txt"
run_mcp "$TMPDIR_RUN/in2.jsonl" "$TMPDIR_RUN/out2.txt"

python3 <<'PY'
import json, sys

def parse_curate(path):
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("id") != 2:
            continue
        err = d.get("error")
        if err:
            return None, f"MCP error id=2: {err}"
        content = d.get("result", {}).get("content", [])
        for item in content:
            text = item.get("text", "")
            try:
                return json.loads(text), None
            except json.JSONDecodeError:
                continue
    return None, "no tools/call id=2 JSON result in output"

def main():
    import os
    o1 = os.path.join(os.environ["TMPDIR_RUN"], "out1.txt")
    o2 = os.path.join(os.environ["TMPDIR_RUN"], "out2.txt")

    p1, e1 = parse_curate(o1)
    if e1:
        print(f"FAIL: {e1}")
        raw = open(o1).read().strip()
        if raw:
            print("--- mcp output (truncated) ---")
            print(raw[:2000])
        sys.exit(1)

    opts = p1.get("options")
    if not opts or "implicit_score_threshold" not in opts or "implicit_dedup_jaccard" not in opts:
        print(f"FAIL: dry_run response missing options: {p1!r}")
        sys.exit(1)
    print(
        f"OK: default dry_run options implicit_score_threshold={opts['implicit_score_threshold']} "
        f"implicit_dedup_jaccard={opts['implicit_dedup_jaccard']}"
    )

    cands = p1.get("candidates")
    if not isinstance(cands, list):
        print(f"FAIL: expected candidates list, got {type(cands)}")
        sys.exit(1)
    print(f"OK: dry_run candidates count={len(cands)}")

    p2, e2 = parse_curate(o2)
    if e2:
        print(f"FAIL (override run): {e2}")
        sys.exit(1)
    o2opts = p2.get("options", {})
    st = o2opts.get("implicit_score_threshold")
    dj = o2opts.get("implicit_dedup_jaccard")
    if st is None or dj is None:
        print(f"FAIL: missing options in override run: {o2opts!r}")
        sys.exit(1)
    if abs(float(st) - 0.72) > 0.001 or abs(float(dj) - 0.61) > 0.001:
        print(f"FAIL: MCP overrides not reflected in options: {o2opts!r}")
        sys.exit(1)
    print(f"OK: override options implicit_score_threshold={st} implicit_dedup_jaccard={dj}")

    print("verify_session_curate: all checks passed")

if __name__ == "__main__":
    main()
PY
