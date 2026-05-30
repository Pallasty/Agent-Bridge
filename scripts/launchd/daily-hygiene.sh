#!/usr/bin/env bash
# ζ-17 macOS hygiene wrapper — six-stage daily cycle, callable from
# launchd. Mirrors the Linux systemd `ExecStart=` array in
# scripts/systemd/agent-bridge-memory-decay-unused.service. That file
# is the source of truth for the per-op rationale; keep the two
# in sync when adding or tuning ops.
#
# Log path matches the Linux node so cross-machine `tail -f` works
# without per-OS branching:
#   ~/.cache/agent-bridge/memory-decay-unused.log
#
# Failure mode: each op runs with `|| true` (mirror of systemd's
# `ExecStart=-`). A single op's transient failure (SQL lock contention
# with palace serve, etc.) shouldn't block the rest of the cycle —
# tomorrow's run will retry. Catastrophic failures (binary missing)
# bail early with a journal line.

set -u
LOG_DIR="$HOME/.cache/agent-bridge"
mkdir -p "$LOG_DIR"
exec >> "$LOG_DIR/memory-decay-unused.log" 2>&1

BIN="$HOME/.local/bin/agent-bridge.real"
if [[ ! -x "$BIN" ]]; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) ζ-17 launchd: $BIN missing or not executable — skip" >&2
  exit 0
fi

echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) ζ-17 daily hygiene begin ==="

# Subtract pass: decay → prune coact noise → prune degenerate relates
# → archive orphan stubs. Removes dead weight before reinforcement
# decides what's still worth amplifying.
"$BIN" dream decay-unused --window-days 30 --step 0.05 --floor 0.1 || true
"$BIN" dream prune-coactivation-noise --max-count 1 --older-than-days 30 || true
"$BIN" dream prune-degenerate-relates || true
"$BIN" dream archive-orphan-stubs --older-than-days 3 --alarm-threshold 25 || true

# Add pass: reinforce-active. Hebbian wire-strengthen — without this
# the system is entropy-monotonic (decay only, never reward).
"$BIN" dream reinforce-active --window-days 7 --min-access 5 --step 0.05 --ceiling 0.95 || true

# L7 self-learning pass: AGENT.md drift detector (propose-only, never
# auto-edits — user-gated per the L7 safety rule). Scans recent lessons not
# yet covered by AGENT.md and writes l7_proposed_update memories that surface
# in the next session bootstrap as review candidates. GUARDED on AGENT.md
# existence: with no AGENT.md the detector would treat every lesson as drift
# and emit daily noise, so the loop stays silent until a user opts in by
# creating the file. Default path mirrors agent_profile_path()
# (XDG_DATA_HOME override, else ~/.local/share/agent-bridge/AGENT.md).
AGENT_MD="${XDG_DATA_HOME:-$HOME/.local/share}/agent-bridge/AGENT.md"
if [[ -f "$AGENT_MD" ]]; then
  "$BIN" dream agent-md-drift --window-days 14 || true
else
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) ζ-17 L7 drift: no AGENT.md at $AGENT_MD — skip (propose-only loop dormant until user creates it)"
fi

# Record pass: snapshot last so it captures the post-hygiene state.
# Tomorrow's `dream diff --auto` (ζ-16) pairs this with the previous
# daily for the net delta.
"$BIN" dream snapshot --name daily || true

echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) ζ-17 daily hygiene end ==="
