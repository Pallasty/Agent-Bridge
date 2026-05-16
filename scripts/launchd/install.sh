#!/usr/bin/env bash
# Install macOS LaunchAgents shipped with agent-bridge.
#
# Currently installs:
#   - com.agentbridge.daily-hygiene  (ζ-17 — daily memory hygiene 03:42)
#   - com.agentbridge.sync           (D2-G1 — 15-min cross-machine sync)
#
# Usage:
#   ./scripts/launchd/install.sh           # copy + bootstrap LaunchAgents
#   ./scripts/launchd/install.sh --dry-run # show what would happen
#   ./scripts/launchd/install.sh --once    # also kickstart each agent once
#
# On Linux this script refuses to run — use scripts/systemd/install.sh
# instead. Keeping the two installers separate avoids "guess the OS"
# logic in a single script that has to maintain both.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# (plist_basename, wrapper_basename, label, tail_log_path) per agent.
# Adding a new agent = add a 4-tuple here + the matching files in
# scripts/launchd/. Each plist references the wrapper at
# $WRAPPER_INSTALL_DIR/<wrapper_basename> so a `git pull` of the repo
# doesn't disturb the loaded agent's pointer.
AGENTS=(
  "com.agentbridge.daily-hygiene.plist|daily-hygiene.sh|com.agentbridge.daily-hygiene|memory-decay-unused.log"
  "com.agentbridge.sync.plist|sync-frequent.sh|com.agentbridge.sync|sync.log"
)

LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
WRAPPER_INSTALL_DIR="$HOME/.local/share/agent-bridge/launchd"

DRY=0
RUN_ONCE=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --once)    RUN_ONCE=1 ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

# OS guard sits after --help so `./install.sh --help` works on Linux too
# (lets the operator preview what the installer does before SSH'ing into
# the Mac node to actually run it).
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "launchd installer is macOS-only. Use scripts/systemd/install.sh on Linux." >&2
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

UID_=$(id -u)
DOMAIN="gui/$UID_"

run mkdir -p "$LAUNCH_AGENT_DIR" "$WRAPPER_INSTALL_DIR"

for entry in "${AGENTS[@]}"; do
  IFS='|' read -r PLIST_BN WRAPPER_BN LABEL LOG_BN <<<"$entry"
  PLIST_SRC="$SCRIPT_DIR/$PLIST_BN"
  WRAPPER_SRC="$SCRIPT_DIR/$WRAPPER_BN"
  PLIST_DST="$LAUNCH_AGENT_DIR/$PLIST_BN"
  WRAPPER_DST="$WRAPPER_INSTALL_DIR/$WRAPPER_BN"

  echo
  echo "── $LABEL ───────────────────────────────────────────"
  # Sanity-check sources before touching the LaunchAgent dir.
  [[ -f "$PLIST_SRC"   ]] || { echo "missing: $PLIST_SRC"   >&2; exit 1; }
  [[ -f "$WRAPPER_SRC" ]] || { echo "missing: $WRAPPER_SRC" >&2; exit 1; }

  # plutil ships with macOS — fail loud on hand-edit typos.
  run plutil -lint "$PLIST_SRC"

  run cp -f "$WRAPPER_SRC" "$WRAPPER_DST"
  run chmod +x "$WRAPPER_DST"
  run cp -f "$PLIST_SRC"   "$PLIST_DST"

  # Bootstrap-or-reload pattern. `bootout` is idempotent (silently
  # returns 0 if not loaded); `bootstrap` requires plist at target.
  if [[ $DRY -eq 0 ]]; then
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
  fi
  run launchctl bootstrap "$DOMAIN" "$PLIST_DST"

  if [[ $RUN_ONCE -eq 1 ]]; then
    run launchctl kickstart -k "$DOMAIN/$LABEL"
    echo
    echo "Wrapper output (tail of ~/.cache/agent-bridge/$LOG_BN):"
    tail -n 20 "$HOME/.cache/agent-bridge/$LOG_BN" 2>/dev/null \
      || echo "(no log yet)"
  fi
done

echo
echo "Loaded LaunchAgents:"
for entry in "${AGENTS[@]}"; do
  IFS='|' read -r _ _ LABEL _ <<<"$entry"
  launchctl list | grep -F "$LABEL" || echo "  (not loaded: $LABEL — check launchctl error above)"
done
