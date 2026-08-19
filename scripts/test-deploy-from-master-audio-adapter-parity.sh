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
RUNTIME_ASSET_DIR="$ROOT/lib/agent-bridge/scripts"
mkdir -p "$INSTALL_DIR"
cp "$(type -P true)" "$ROOT/new-agent-bridge"

AGENT_BRIDGE_INSTALL_DIR="$INSTALL_DIR" \
AGENT_BRIDGE_AUDIO_EMBODY_PATH="$ADAPTER_PATH" \
AGENT_BRIDGE_RUNTIME_ASSET_DIR="$RUNTIME_ASSET_DIR" \
    "$SCRIPT_DIR/deploy_from_master.sh" --use-binary "$ROOT/new-agent-bridge" --yes >/dev/null

test -f "$ADAPTER_PATH"
cmp -s "$SCRIPT_DIR/audio_embody.py" "$ADAPTER_PATH"
test -x "$ADAPTER_PATH"
for asset in omnivoice_mac_remote_synth.py omnivoice_onnx_bundle_synth.py \
    omnivoice_onnx_official_decode.py omnivoice_tts_synth.py \
    qwen3_tts_rust_gate.py qwen3_tts_synth.py tts_canary_router.py; do
    test -x "$(dirname "$ADAPTER_PATH")/$asset"
    cmp -s "$SCRIPT_DIR/$asset" "$(dirname "$ADAPTER_PATH")/$asset"
done
for asset in config/omnivoice-canary.json \
    docs/reports/tts-comparison/human-review-decision-owner-2026-08-15.json; do
    test -f "$ROOT/$asset"
    cmp -s "$(dirname "$SCRIPT_DIR")/$asset" "$ROOT/$asset"
done
for asset in app_control.py desktop_action.py desktop_confirm_store.py desktop_grant.py \
    desktop_invoke.py desktop_snapshot.py desktop_steer.py desktop_verify.py \
    macos_ax_probe.py macos_ax_verify.py \
    vision_grounding_ocr.py; do
    test -x "$RUNTIME_ASSET_DIR/$asset"
    cmp -s "$SCRIPT_DIR/$asset" "$RUNTIME_ASSET_DIR/$asset"
done
grep -q '"playlist_current"' "$RUNTIME_ASSET_DIR/app_control.py"
grep -q '"playlist_activate"' "$RUNTIME_ASSET_DIR/app_control.py"

printf 'PASS: deploy keeps binary, audio adapter, and runtime scripts at repository parity\n'
