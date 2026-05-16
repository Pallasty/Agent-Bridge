#!/usr/bin/env bash
# 15-min macOS LaunchAgent wrapper for cross-machine memory + forum sync.
# Closes D2-G1 propagation gap (audit 1b62e0d §6) by ensuring fresh
# forum / memory state is pushed to the canonical git repo within p95
# ≤30 min across Mac + aio2.
#
# Mirrors the Linux systemd path:
#   scripts/systemd/agent-bridge-sync.service
#
# This wrapper exists (vs calling `agent-bridge sync` directly from the
# plist) so log capture matches the daily-hygiene pattern:
#   ~/.cache/agent-bridge/sync.log
#
# Failure mode: `agent-bridge sync` is idempotent — a transient git pull
# conflict, network blip, or remote unavailability fails the run but
# next 15-min cycle retries. No state corruption possible (sync.rs uses
# pull-rebase + push with explicit refspec).

set -u
LOG_DIR="$HOME/.cache/agent-bridge"
mkdir -p "$LOG_DIR"
exec >> "$LOG_DIR/sync.log" 2>&1

BIN="$HOME/.local/bin/agent-bridge.real"
if [[ ! -x "$BIN" ]]; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) sync launchd: $BIN missing or not executable — skip" >&2
  exit 0
fi

echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) sync begin ==="
"$BIN" sync -v
echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) sync end ==="
