#!/usr/bin/env bash
# ζ-17 — install the macOS LaunchAgent that mirrors the Linux systemd
# daily-hygiene timer (scripts/systemd/agent-bridge-memory-decay-unused.*).
#
# Usage:
#   ./scripts/launchd/install.sh           # copy + bootstrap LaunchAgent
#   ./scripts/launchd/install.sh --dry-run # show what would happen
#   ./scripts/launchd/install.sh --once    # also run the wrapper once now
#
# On Linux this script refuses to run — use scripts/systemd/install.sh
# instead. Keeping the two installers separate avoids "guess the OS"
# logic in a single script that has to maintain both.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_SRC="$SCRIPT_DIR/com.agentbridge.daily-hygiene.plist"
WRAPPER_SRC="$SCRIPT_DIR/daily-hygiene.sh"

# Where the loaded plist lives. ~/Library/LaunchAgents = per-user.
LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST_DST="$LAUNCH_AGENT_DIR/com.agentbridge.daily-hygiene.plist"

# Where the wrapper lives — referenced absolutely from the plist's
# ProgramArguments. Outside the repo so an `agent-bridge` git pull
# doesn't disturb a loaded agent's pointer.
WRAPPER_INSTALL_DIR="$HOME/.local/share/agent-bridge/launchd"
WRAPPER_DST="$WRAPPER_INSTALL_DIR/daily-hygiene.sh"

LABEL="com.agentbridge.daily-hygiene"

DRY=0
RUN_ONCE=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --once)    RUN_ONCE=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

# OS guard sits after --help so `./install.sh --help` works on Linux too
# (lets the operator preview what the installer does before SSH'ing into
# the Mac node to actually run it).
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "ζ-17 launchd installer is macOS-only. Use scripts/systemd/install.sh on Linux." >&2
  exit 2
fi

run() {
  if [[ $DRY -eq 1 ]]; then
    echo "[dry] $*"
  else
    echo "+ $*"
    "$@"
  fi
}

# Sanity-check the source files exist (clearer error than the cp later).
[[ -f "$PLIST_SRC"   ]] || { echo "missing: $PLIST_SRC"   >&2; exit 1; }
[[ -f "$WRAPPER_SRC" ]] || { echo "missing: $WRAPPER_SRC" >&2; exit 1; }

# Verify plist syntax before touching anything. plutil ships with macOS.
# Fail loud so a hand-edit typo doesn't silently bootstrap a broken agent.
run plutil -lint "$PLIST_SRC"

run mkdir -p "$LAUNCH_AGENT_DIR" "$WRAPPER_INSTALL_DIR"
run cp -f "$WRAPPER_SRC" "$WRAPPER_DST"
run chmod +x "$WRAPPER_DST"
run cp -f "$PLIST_SRC"   "$PLIST_DST"

# Bootstrap-or-reload pattern. `bootout` is idempotent (silently
# returns 0 if not loaded), and `bootstrap` requires the plist to be
# at the target path — that's why we copy first.
UID_=$(id -u)
DOMAIN="gui/$UID_"
if [[ $DRY -eq 0 ]]; then
  # Best-effort unload — first run will print "Could not find specified
  # service", that's fine. Subsequent runs need the reset to pick up
  # plist edits.
  launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
fi
run launchctl bootstrap "$DOMAIN" "$PLIST_DST"

if [[ $RUN_ONCE -eq 1 ]]; then
  run launchctl kickstart -k "$DOMAIN/$LABEL"
  echo
  echo "Wrapper output (tail):"
  tail -n 20 "$HOME/.cache/agent-bridge/memory-decay-unused.log" 2>/dev/null \
    || echo "(no log yet)"
fi

echo
echo "Loaded LaunchAgent:"
launchctl list | grep -F "$LABEL" || echo "(not in list — check launchctl error above)"
