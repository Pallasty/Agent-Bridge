#!/usr/bin/env bash
# ab-kilo-run.sh — drive the FREE `kilo` agent on a remote node as a headless
# executor (zero codex/paid-API quota), with retry-on-miss for the
# `kilo/kilo-auto/free` gateway's intermittent ProviderModelNotFoundError.
#
# Companion to ab-steer-launch.sh. Where the steer tools drive a long-lived
# *interactive* TUI inside tmux, this is the one-shot `kilo run` path: no tmux,
# no session — fire a task, get the result. Ideal for the cheap exec/collect
# half of the remote-steering boundary.
#
# Boundary (non-negotiable, see docs/REMOTE_SESSION_STEERING_SOP.md):
#   execution / collection may be driven freely; any research JUDGMENT kilo
#   produces still needs a human ground-truth gate before it is trusted.
#
# It targets a standing workspace (~/ab-kilo on the node) whose kilo.jsonc wires
# the agent-bridge MCP server, so kilo has the full AB toolset — WITHOUT touching
# the user's global kilo config (a config-file `mcp` block REPLACES, not merges,
# the DB-stored global servers, so we keep it scoped to the workspace).
#
# Usage:
#   ab-kilo-run.sh "Write fib.py printing the first 10 Fibonacci numbers, run it."
#   ab-kilo-run.sh --json "List the top 5 processes by memory as JSON"
#   ab-kilo-run.sh --model kilo/kilo-auto/free --retries 4 "<task>"
#
# Env overrides:
#   AB_KILO_NODE     (default 100.93.4.56)   AB_KILO_USER  (default pallasting)
#   AB_KILO_DIR      (default \$HOME/ab-kilo) AB_KILO_RETRIES (default 3)
#   AB_KILO_SSH_KEY  (default ~/.ssh/id_ed25519)
set -euo pipefail

NODE="${AB_KILO_NODE:-100.93.4.56}"
SSH_USER="${AB_KILO_USER:-pallasting}"
REMOTE_DIR="${AB_KILO_DIR:-}"                 # empty => remote default $HOME/ab-kilo
SSH_KEY="${AB_KILO_SSH_KEY:-$HOME/.ssh/id_ed25519}"
RETRIES="${AB_KILO_RETRIES:-3}"
FORMAT="default"
MODEL=""            # empty => workspace config default (kilo/kilo-auto/free)

usage() {
  sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

# ---- parse flags then the trailing message ----
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json)            FORMAT="json"; shift ;;
    --model)           MODEL="${2:?--model needs a value}"; shift 2 ;;
    --retries)         RETRIES="${2:?--retries needs a value}"; shift 2 ;;
    --node)            NODE="${2:?--node needs a value}"; shift 2 ;;
    --user)            SSH_USER="${2:?--user needs a value}"; shift 2 ;;
    --dir)             REMOTE_DIR="${2:?--dir needs a value}"; shift 2 ;;
    -h|--help)         usage 0 ;;
    --)                shift; break ;;
    -*)                echo "unknown flag: $1" >&2; usage 2 ;;
    *)                 break ;;
  esac
done

MSG="${*:-}"
if [[ -z "$MSG" ]]; then
  echo "error: no task message given" >&2
  usage 2
fi

# base64 the message so it survives transport with zero quoting hazard.
B64="$(printf '%s' "$MSG" | base64 | tr -d '\n')"

# Remote program body (literal). It reads its inputs from env vars, which we pass
# as a `printf %q`-quoted env PREFIX on the ssh command rather than via ssh argv:
# ssh flattens argv through a remote shell and silently DROPS empty args (so a
# bare MODEL="" would shift $5 off the end → "$5: unbound variable").
read -r -d '' REMOTE_PROG <<'REMOTE' || true
set -uo pipefail
RDIR="${RDIR:-$HOME/ab-kilo}"               # default workspace (agent-bridge MCP wired)
MSG="$(printf '%s' "$B64" | base64 -d)"
K="$HOME/.kilo/bin/kilo"
[ -x "$K" ] || { echo "ab-kilo-run: kilo not found at $K" >&2; exit 127; }
mkdir -p "$RDIR"; cd "$RDIR" || exit 1
mf=(); [ -n "${MODEL:-}" ] && mf=(--model "$MODEL")
ff=(); [ "${FMT:-default}" = json ] && ff=(--format json)
a=0
while :; do
  a=$((a+1))
  out="$(timeout 220 "$K" run --dir "$RDIR" "${mf[@]}" "${ff[@]}" "$MSG" </dev/null 2>&1)"
  if printf '%s' "$out" | grep -qiE 'ProviderModelNotFoundError|Model not found'; then
    if [ "$a" -lt "${RETRIES:-3}" ]; then echo "[ab-kilo-run: free-pool miss, retry $a/${RETRIES:-3}]" >&2; sleep 4; continue; fi
  fi
  break
done
printf '%s\n' "$out" | sed -E 's/\x1b\[[0-9;]*m//g'   # strip ANSI for clean piping
REMOTE

ssh -o BatchMode=yes -o ConnectTimeout=10 -i "$SSH_KEY" "$SSH_USER@$NODE" \
  "B64=$(printf %q "$B64") RDIR=$(printf %q "$REMOTE_DIR") FMT=$(printf %q "$FORMAT") MODEL=$(printf %q "$MODEL") RETRIES=$(printf %q "$RETRIES") bash -s" \
  <<<"$REMOTE_PROG"
