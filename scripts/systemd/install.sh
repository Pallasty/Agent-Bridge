#!/usr/bin/env bash
# Install user-systemd timers shipped with agent-bridge.
#
# Currently installs:
#   - agent-bridge-memory-decay-unused.timer (Phase 2.x #8 daily decay)
#
# Usage:
#   ./scripts/systemd/install.sh           # copy + reload + enable timers
#   ./scripts/systemd/install.sh --dry-run # show what would happen
#   ./scripts/systemd/install.sh --once    # also run the decay service once

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

UNITS=(
  agent-bridge-memory-decay-unused.service
  agent-bridge-memory-decay-unused.timer
)

TIMERS=(
  agent-bridge-memory-decay-unused.timer
)

DRY=0
RUN_ONCE=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --once)    RUN_ONCE=1 ;;
    -h|--help)
      sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

run() {
  if [[ $DRY -eq 1 ]]; then
    echo "[dry] $*"
  else
    echo "+ $*"
    "$@"
  fi
}

mkdir -p "$TARGET_DIR"
for unit in "${UNITS[@]}"; do
  src="$SCRIPT_DIR/$unit"
  dst="$TARGET_DIR/$unit"
  if [[ ! -f "$src" ]]; then
    echo "missing template: $src" >&2; exit 1
  fi
  run cp -f "$src" "$dst"
done

run systemctl --user daemon-reload
for t in "${TIMERS[@]}"; do
  run systemctl --user enable --now "$t"
done

if [[ $RUN_ONCE -eq 1 ]]; then
  # Trigger the .service once now, not the .timer — gives a fresh wet-test.
  run systemctl --user start agent-bridge-memory-decay-unused.service
  echo
  echo "log tail:"
  tail -n 20 "$HOME/.cache/agent-bridge/memory-decay-unused.log" 2>/dev/null \
    || echo "(no log yet)"
fi

echo
echo "Installed timers:"
systemctl --user list-timers --all "${TIMERS[@]}" 2>/dev/null || true
