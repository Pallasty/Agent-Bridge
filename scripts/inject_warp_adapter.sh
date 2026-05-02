#!/usr/bin/env bash
# inject_warp_adapter.sh — Inject the agent-bridge Warp adapter into a Warp source tree.
#
# Idempotent: safe to re-run after a Warp upstream upgrade to re-apply the
# adapter files and patches.
#
# Usage:
#   scripts/inject_warp_adapter.sh [WARP_DIR]
#
# WARP_DIR may also be set via the environment variable.
# Defaults to /Data/CascadeProjects/warp if it exists.
#
# What this script does:
#   1. Copies warp-adapter/app/src/agent_bridge/ → $WARP_DIR/app/src/agent_bridge/
#   2. Copies warp-adapter/crates/agent_bridge/  → $WARP_DIR/crates/agent_bridge/
#   3. Patches $WARP_DIR/app/src/lib.rs          (mod + init call)
#   4. Patches $WARP_DIR/app/Cargo.toml          (dependency entry)
#
# After injection, verify with:
#   cd $WARP_DIR && cargo check -p warp 2>&1 | grep ^error | head -20

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ADAPTER_DIR="${ROOT}/warp-adapter"

# ── resolve WARP_DIR ────────────────────────────────────────────────────────
if [[ $# -ge 1 ]]; then
    WARP_DIR="$1"
elif [[ -n "${WARP_DIR:-}" ]]; then
    : # use env var
elif [[ -d "/Data/CascadeProjects/warp" ]]; then
    WARP_DIR="/Data/CascadeProjects/warp"
else
    echo "ERROR: WARP_DIR not specified and no default found." >&2
    echo "Usage: $0 <WARP_DIR>" >&2
    exit 1
fi

WARP_DIR="$(cd "${WARP_DIR}" && pwd)"
echo "Target Warp tree: ${WARP_DIR}"
echo ""

# ── 1. Copy GPUI module ──────────────────────────────────────────────────────
DEST_MOD="${WARP_DIR}/app/src/agent_bridge"
mkdir -p "${DEST_MOD}"
cp -r "${ADAPTER_DIR}/app/src/agent_bridge/." "${DEST_MOD}/"
echo "[1/4] Copied app/src/agent_bridge/ ($(ls "${DEST_MOD}" | wc -l | tr -d ' ') files)"

# ── 2. Copy protocol crate ───────────────────────────────────────────────────
DEST_CRATE="${WARP_DIR}/crates/agent_bridge"
mkdir -p "${DEST_CRATE}/src"
cp "${ADAPTER_DIR}/crates/agent_bridge/Cargo.toml"    "${DEST_CRATE}/Cargo.toml"
cp "${ADAPTER_DIR}/crates/agent_bridge/src/lib.rs"    "${DEST_CRATE}/src/lib.rs"
cp "${ADAPTER_DIR}/crates/agent_bridge/src/protocol.rs" "${DEST_CRATE}/src/protocol.rs"
echo "[2/4] Copied crates/agent_bridge/"

# ── 3. Patch app/src/lib.rs ──────────────────────────────────────────────────
python3 - "${WARP_DIR}/app/src/lib.rs" <<'PY'
import sys, re

path = sys.argv[1]
src = open(path).read()
changed = False

# Add `mod agent_bridge;` if missing — insert before the first `mod ` line.
if 'mod agent_bridge;' not in src:
    src = re.sub(r'^(mod \w)', r'mod agent_bridge;\n\1', src, count=1, flags=re.MULTILINE)
    changed = True
    print("[3/4] Patched lib.rs: added `mod agent_bridge;`")
else:
    print("[3/4] lib.rs: `mod agent_bridge;` already present — skip")

# Add `agent_bridge::init(ctx);` before ensure_warp_watch_roots_exist().
INIT_CALL = 'agent_bridge::init(ctx);'
ANCHOR    = 'ensure_warp_watch_roots_exist();'
if INIT_CALL not in src:
    if ANCHOR in src:
        src = src.replace(ANCHOR, f'{INIT_CALL}\n\n    {ANCHOR}', 1)
        changed = True
        print("         Patched lib.rs: added `agent_bridge::init(ctx);`")
    else:
        print("WARNING: anchor `ensure_warp_watch_roots_exist()` not found in lib.rs.", file=sys.stderr)
        print("         Add manually:  agent_bridge::init(ctx);", file=sys.stderr)
else:
    print("         lib.rs: `agent_bridge::init(ctx)` already present — skip")

if changed:
    open(path, 'w').write(src)
PY

# ── 4. Patch app/Cargo.toml ──────────────────────────────────────────────────
python3 - "${WARP_DIR}/app/Cargo.toml" <<'PY'
import sys, re

path = sys.argv[1]
src = open(path).read()

DEP = 'warp_agent_bridge = { path = "../crates/agent_bridge" }'

if 'warp_agent_bridge' in src:
    print("[4/4] Cargo.toml: warp_agent_bridge already present — skip")
    sys.exit(0)

# Insert alphabetically after `warp-workflows` if present,
# otherwise after the [dependencies] header.
if 'warp-workflows' in src:
    src = re.sub(
        r'(warp-workflows[^\n]+)',
        r'\1\n' + DEP,
        src, count=1
    )
    open(path, 'w').write(src)
    print("[4/4] Patched Cargo.toml: added warp_agent_bridge after warp-workflows")
elif '[dependencies]' in src:
    src = src.replace('[dependencies]\n', '[dependencies]\n' + DEP + '\n', 1)
    open(path, 'w').write(src)
    print("[4/4] Patched Cargo.toml: added warp_agent_bridge under [dependencies]")
else:
    print("[4/4] WARNING: could not find insertion point in Cargo.toml.", file=sys.stderr)
    print(f"      Add manually: {DEP}", file=sys.stderr)
PY

echo ""
echo "inject_warp_adapter.sh: done."
echo ""
echo "Next: cd ${WARP_DIR} && cargo check -p warp 2>&1 | grep '^error' | head -20"
