#!/usr/bin/env bash
# Install user-systemd units shipped with agent-bridge.
#
# Currently installs:
#   Timers (cadenced):
#     - agent-bridge-memory-decay-unused.timer (Phase 2.x #8 daily decay)
#     - agent-bridge-sync.timer (D2-G1 — 15-min cross-machine sync)
#     - agent-bridge-distill.timer (P2 — nightly propose-only distillation
#       draft batch via claude -p; 04:30, after the hygiene pass)
#     - agent-bridge-digest.timer (consolidation middle — nightly propose-only
#       digest-author draft batch via claude -p; 05:00, after distill)
#   Services (always-on, ship 2026-05-20 #325 backlog after recurring soft-hang):
#     - agent-bridge-daemon.service (state.db writer + P-α tick + C3 self-check)
#     - agent-bridge-palace.service (UI on port 7979)
#     - agent-bridge-daemon-http.service (local-default API on port 7878;
#       optional exact tailnet binding is an explicit deployment choice)
#
# Usage:
#   ./scripts/systemd/install.sh             # copy + reload + enable timers + services
#   ./scripts/systemd/install.sh --dry-run   # show what would happen
#   ./scripts/systemd/install.sh --once      # also run the decay service once
#   ./scripts/systemd/install.sh --no-daemons  # skip the 3 always-on daemons
#                                              # (for headless / sibling sessions
#                                              #  that don't want auto-start)
#   ./scripts/systemd/install.sh --replica     # replica node: enable ONLY the
#                                              # sync timer; disable the three
#                                              # store-mutating consolidator
#                                              # timers (decay/distill/digest).
#                                              # One consolidator per mesh —
#                                              # see docs/NEW-NODE-RUNBOOK.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

UNITS=(
  agent-bridge-memory-decay-unused.service
  agent-bridge-memory-decay-unused.timer
  agent-bridge-sync.service
  agent-bridge-sync.timer
  agent-bridge-distill.service
  agent-bridge-distill.timer
  agent-bridge-digest.service
  agent-bridge-digest.timer
  agent-bridge-daemon.service
  agent-bridge-palace.service
  agent-bridge-daemon-http.service
)

TIMERS=(
  agent-bridge-memory-decay-unused.timer
  agent-bridge-sync.timer
  agent-bridge-distill.timer
  agent-bridge-digest.timer
)

DAEMON_SERVICES=(
  agent-bridge-daemon.service
  agent-bridge-palace.service
  agent-bridge-daemon-http.service
)

DRY=0
RUN_ONCE=0
NO_DAEMONS=0
REPLICA=0
for arg in "$@"; do
  case "$arg" in
    --dry-run)    DRY=1 ;;
    --once)       RUN_ONCE=1 ;;
    --no-daemons) NO_DAEMONS=1 ;;
    --replica)    REPLICA=1 ;;
    -h|--help)
      sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

CONSOLIDATOR_TIMERS=(
  agent-bridge-memory-decay-unused.timer
  agent-bridge-distill.timer
  agent-bridge-digest.timer
)

if [[ $REPLICA -eq 1 ]]; then
  if [[ $RUN_ONCE -eq 1 ]]; then
    echo "--replica and --once conflict: --once runs the decay pass, a consolidator-only job" >&2
    exit 2
  fi
  TIMERS=(agent-bridge-sync.timer)
fi

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
if [[ $REPLICA -eq 1 ]]; then
  # Role correction: a prior full install may have enabled these. One
  # consolidator per mesh — docs/NEW-NODE-RUNBOOK.md stage 4.
  for t in "${CONSOLIDATOR_TIMERS[@]}"; do
    run systemctl --user disable --now "$t" || true
  done
fi
for t in "${TIMERS[@]}"; do
  run systemctl --user enable --now "$t"
done

if [[ $NO_DAEMONS -eq 0 ]]; then
  # Kill any setsid-launched manual daemons first to avoid double-spawn
  # on shared state.db — see lesson `daemon_restart_idempotency_2026_05_19`.
  # `pkill -f` matches the wrapper path; setsid orphans reparent to PID 1
  # so they're not in our process group.
  if [[ $DRY -eq 0 ]]; then
    for cmd in 'agent-bridge daemon$' 'agent-bridge palace serve' 'agent-bridge daemon-http'; do
      pids=$(pgrep -f "$cmd" 2>/dev/null || true)
      if [[ -n "$pids" ]]; then
        echo "+ pkill -TERM -f '$cmd' (pids: $pids)"
        pkill -TERM -f "$cmd" || true
      fi
    done
    sleep 2
  fi

  for s in "${DAEMON_SERVICES[@]}"; do
    run systemctl --user enable --now "$s"
  done
fi

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

if [[ $NO_DAEMONS -eq 0 ]]; then
  echo
  echo "Always-on services:"
  for s in "${DAEMON_SERVICES[@]}"; do
    state=$(systemctl --user is-active "$s" 2>/dev/null || echo "?")
    enabled=$(systemctl --user is-enabled "$s" 2>/dev/null || echo "?")
    printf "  %-44s %s / %s\n" "$s" "$state" "$enabled"
  done
fi
