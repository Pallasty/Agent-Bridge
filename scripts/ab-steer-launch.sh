#!/usr/bin/env bash
# ab-steer-launch.sh — launch a long-lived agent inside a named tmux session
# following the remote-session-steering convention `ab:<project>:<role>`.
#
# This is the zero-code P1 entry point (see docs/REMOTE_SESSION_STEERING_SOP.md).
# It only enforces the naming convention + refuses to clobber a live session;
# the gate-aware programmatic path is the `agent_steer_*` MCP tools (P2/P3).
#
# Usage:
#   ab-steer-launch.sh <project> <role> [-- <command...>]
#
# Examples:
#   ab-steer-launch.sh biocortex-rs codex -- codex resume
#   ab-steer-launch.sh aiot reviewer            # defaults command to $SHELL
#
# Then drive it as a human (context-preserving, drift-proof):
#   ssh -t <user@host> 'tmux attach -t ab:<project>:<role>'
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <project> <role> [-- <command...>]" >&2
  exit 2
fi

project="$1"; shift
role="$1"; shift

# Optional `-- <command...>`; default to an interactive login shell.
cmd=()
if [[ "${1:-}" == "--" ]]; then
  shift
  cmd=("$@")
fi
if [[ ${#cmd[@]} -eq 0 ]]; then
  cmd=("${SHELL:-/bin/bash}")
fi

# tmux rewrites ':' (its session:window separator) and '.' to '_' in session
# names, so the logical handle `ab:<project>:<role>` cannot be a literal tmux
# name. The tmux-safe form is `ab__<project>__<role>` with a '__' delimiter and
# each component reduced to [A-Za-z0-9-] (dash is tmux-safe). The colon form is
# kept only for display.
sanitize() { printf '%s' "$1" | tr -c 'A-Za-z0-9-' '-' | sed 's/-\{2,\}/-/g; s/^-//; s/-$//'; }
proj_s="$(sanitize "$project")"; role_s="$(sanitize "$role")"
session="ab__${proj_s}__${role_s}"
logical="ab:${project}:${role}"

if ! command -v tmux >/dev/null 2>&1; then
  echo "error: tmux not found on PATH (brew install tmux / apt install tmux)" >&2
  exit 1
fi

if tmux has-session -t "=$session" 2>/dev/null; then
  echo "session already live: $session ($logical)" >&2
  echo "attach with: tmux attach -t $session" >&2
  exit 3
fi

# Join the command into a single shell-command for tmux (run via /bin/sh -c).
printf -v joined '%q ' "${cmd[@]}"
tmux new-session -d -s "$session" "$joined"

echo "launched: $session  (handle: $logical · command: ${cmd[*]})"
echo "attach:   tmux attach -t $session"
echo "remote:   ssh -t <user@host> 'tmux attach -t $session'"
