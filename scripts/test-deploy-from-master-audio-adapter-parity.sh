#!/usr/bin/env bash
# Regression probe: a binary deploy that advertises present_voice must install
# the repository-matched audio_embody.py in the same gated operation.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(mktemp -d /tmp/ab-deploy-audio-parity.XXXXXX)"
cleanup() {
    rm -rf "$ROOT"
}
trap cleanup EXIT

INSTALL_DIR="$ROOT/bin"
ADAPTER_PATH="$ROOT/share/audio_embody.py"
mkdir -p "$INSTALL_DIR"
cp /bin/true "$ROOT/new-agent-bridge"

AGENT_BRIDGE_INSTALL_DIR="$INSTALL_DIR" \
AGENT_BRIDGE_AUDIO_EMBODY_PATH="$ADAPTER_PATH" \
    "$SCRIPT_DIR/deploy_from_master.sh" --use-binary "$ROOT/new-agent-bridge" --yes >/dev/null

test -f "$ADAPTER_PATH"
cmp -s "$SCRIPT_DIR/audio_embody.py" "$ADAPTER_PATH"
test -x "$ADAPTER_PATH"

printf 'PASS: deploy keeps agent-bridge.real and audio_embody.py at repository parity\n'
