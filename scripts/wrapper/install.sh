#!/usr/bin/env bash
# Install or update the agent-bridge env-injection wrapper at
# ~/.local/bin/agent-bridge, moving the existing real binary aside to
# ~/.local/bin/agent-bridge.real if needed.
#
# Idempotent: re-running upgrades the wrapper template without touching
# the real binary or the credentials file.
#
# Usage:
#   scripts/wrapper/install.sh               # install/update with defaults
#   scripts/wrapper/install.sh --uninstall   # restore .real to plain agent-bridge
#   scripts/wrapper/install.sh --dry-run     # show what would happen, no writes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER_TEMPLATE="$SCRIPT_DIR/agent-bridge-wrapper.sh"
CREDS_TEMPLATE="$SCRIPT_DIR/creds.example"

INSTALL_DIR="${AGENT_BRIDGE_INSTALL_DIR:-$HOME/.local/bin}"
WRAPPER_PATH="$INSTALL_DIR/agent-bridge"
REAL_PATH="$INSTALL_DIR/agent-bridge.real"

DRY_RUN=0
UNINSTALL=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --uninstall) UNINSTALL=1 ;;
        -h|--help)
            sed -n '2,12p' "$0"
            exit 0
            ;;
        *)
            echo "unknown arg: $arg" >&2
            exit 2
            ;;
    esac
done

run() {
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[dry-run] $*"
    else
        "$@"
    fi
}

# Heuristic: a shell wrapper is a small text file (<32 KiB) whose head
# mentions agent-bridge; the real binary is an ELF/Mach-O > 1 MiB.
is_wrapper_script() {
    local path="$1"
    [ -f "$path" ] || return 1
    if head -c 4 "$path" 2>/dev/null | grep -qE '^(\x7fELF|\xcf\xfa\xed\xfe|\xfe\xed\xfa)'; then
        return 1
    fi
    head -1 "$path" 2>/dev/null | grep -q '^#!.*\(bash\|sh\)' || return 1
    grep -q 'agent-bridge\.real' "$path" 2>/dev/null
}

if [ "$UNINSTALL" -eq 1 ]; then
    if [ ! -f "$REAL_PATH" ]; then
        echo "no $REAL_PATH found — nothing to uninstall" >&2
        exit 0
    fi
    if [ -f "$WRAPPER_PATH" ] && is_wrapper_script "$WRAPPER_PATH"; then
        echo "Restoring real binary: $REAL_PATH -> $WRAPPER_PATH"
        run mv -f "$REAL_PATH" "$WRAPPER_PATH"
    else
        echo "$WRAPPER_PATH doesn't look like our wrapper — leaving alone" >&2
        echo "(real binary is still at $REAL_PATH)" >&2
        exit 1
    fi
    echo "Uninstalled. Wrapper removed; agent-bridge is now the plain binary."
    exit 0
fi

# ---- Install path ----

if [ ! -f "$WRAPPER_TEMPLATE" ]; then
    echo "wrapper template missing: $WRAPPER_TEMPLATE" >&2
    exit 1
fi

run mkdir -p "$INSTALL_DIR"

# Decide what existing $WRAPPER_PATH is.
if [ ! -e "$WRAPPER_PATH" ]; then
    echo "No existing $WRAPPER_PATH found."
    echo "  After install, place the real binary at $REAL_PATH"
    echo "  (e.g. \`cp target/release/agent-bridge $REAL_PATH\`)"
elif is_wrapper_script "$WRAPPER_PATH"; then
    echo "Existing wrapper at $WRAPPER_PATH — will replace with newer template."
    if [ ! -f "$REAL_PATH" ]; then
        echo "WARNING: $REAL_PATH missing. The wrapper will fail at exec time." >&2
        echo "         Reinstall the real binary before running agent-bridge." >&2
    fi
else
    # Looks like the real binary is currently at $WRAPPER_PATH (no wrapper yet).
    if [ -f "$REAL_PATH" ]; then
        echo "Both $WRAPPER_PATH and $REAL_PATH exist, and $WRAPPER_PATH"
        echo "doesn't look like our wrapper (not a shell script exec'ing agent-bridge.real)." >&2
        echo "Inspect manually, then re-run." >&2
        exit 1
    fi
    echo "Moving existing binary aside: $WRAPPER_PATH -> $REAL_PATH"
    run mv -f "$WRAPPER_PATH" "$REAL_PATH"
fi

echo "Installing wrapper: $WRAPPER_TEMPLATE -> $WRAPPER_PATH"
run install -m 755 "$WRAPPER_TEMPLATE" "$WRAPPER_PATH"

# Credentials file hint.
default_creds="$HOME/Documents/ClaudeCode.txt"
[ -d "/Media/Ubuntu/Documents" ] && default_creds="/Media/Ubuntu/Documents/ClaudeCode.txt"
if [ -n "${AGENT_BRIDGE_CREDS_FILE:-}" ]; then
    creds_to_check="$AGENT_BRIDGE_CREDS_FILE"
else
    creds_to_check="$default_creds"
fi

echo
if [ -f "$creds_to_check" ]; then
    echo "Credentials file detected: $creds_to_check"
    if grep -q "^[[:space:]]*#[[:space:]]*Agent-Bridge[[:space:]]\+Primary" "$creds_to_check"; then
        echo "  Found '# Agent-Bridge Primary' section — wrapper will use it."
    else
        echo "  No '# Agent-Bridge Primary' section yet."
        echo "  Wrapper will fall back to the first 'export ANTHROPIC_AUTH_TOKEN=sk-...' line in the file."
        echo "  To pin the active proxy, copy the section from $CREDS_TEMPLATE."
    fi
else
    echo "No credentials file at $creds_to_check yet."
    echo "  Copy the template:  cp $CREDS_TEMPLATE $creds_to_check"
    echo "  Edit and replace the REPLACE_ME placeholders with real tokens."
fi

echo

# Repo-level githooks wire-up (P23) — opt-in by ENV in case the user
# is running from outside the working tree (e.g. system-wide install).
# Idempotent; running this every wrapper install is fine.
GITHOOKS_INSTALLER="$(cd "$SCRIPT_DIR/.." && pwd)/install-githooks.sh"
if [ -x "$GITHOOKS_INSTALLER" ] && git -C "$(dirname "$GITHOOKS_INSTALLER")" rev-parse --show-toplevel >/dev/null 2>&1; then
    if [[ "${AGENT_BRIDGE_SKIP_GITHOOKS:-0}" == "1" ]]; then
        echo "Skipping githooks install (AGENT_BRIDGE_SKIP_GITHOOKS=1)."
    else
        echo "Wiring repo githooks (pre-commit cargo check, etc):"
        "$GITHOOKS_INSTALLER" 2>&1 | sed 's/^/  /'
        echo "  Bypass with AGENT_BRIDGE_SKIP_GITHOOKS=1 next time, or"
        echo "  AGENT_BRIDGE_SKIP_PRECOMMIT=1 / --no-verify per commit."
    fi
fi

echo
echo "Done. Verify with:  $WRAPPER_PATH --version"
