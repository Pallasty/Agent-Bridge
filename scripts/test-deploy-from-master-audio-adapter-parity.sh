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
printf '\nagent_bridge.app_control.operation_preflight.v0\n' >> "$ROOT/new-agent-bridge"

# A --use-binary caller can provide a new binary from one source snapshot and
# runtime assets from another. The preflight marker must reject that mismatch
# before touching any live binary/runtime file, not only during postflight.
STALE_ROOT="$ROOT/stale-source"
mkdir -p "$STALE_ROOT" "$STALE_ROOT/config" \
    "$STALE_ROOT/docs/reports/tts-comparison"
cp -a "$SCRIPT_DIR" "$STALE_ROOT/scripts"
cp "$SCRIPT_DIR/../config/omnivoice-canary.json" "$STALE_ROOT/config/"
cp "$SCRIPT_DIR/../docs/reports/tts-comparison/human-review-decision-owner-2026-08-15.json" \
    "$STALE_ROOT/docs/reports/tts-comparison/"
sed -i '/agent_bridge\.app_control\.operation_preflight\.v0/d' \
    "$STALE_ROOT/scripts/app_control.py"
NEGATIVE_INSTALL="$ROOT/negative/bin"
NEGATIVE_ADAPTER="$ROOT/negative/share/audio_embody.py"
NEGATIVE_RUNTIME="$ROOT/negative/lib/agent-bridge/scripts"
mkdir -p "$NEGATIVE_INSTALL" "$(dirname "$NEGATIVE_ADAPTER")" "$NEGATIVE_RUNTIME"
cp "$(type -P true)" "$NEGATIVE_INSTALL/agent-bridge.real"
printf '%s\n' 'existing-adapter' > "$NEGATIVE_ADAPTER"
printf '%s\n' 'existing-runtime' > "$NEGATIVE_RUNTIME/app_control.py"
cp "$NEGATIVE_INSTALL/agent-bridge.real" "$ROOT/negative-real.before"
cp "$NEGATIVE_ADAPTER" "$ROOT/negative-adapter.before"
cp "$NEGATIVE_RUNTIME/app_control.py" "$ROOT/negative-runtime.before"
if AGENT_BRIDGE_INSTALL_DIR="$NEGATIVE_INSTALL" \
    AGENT_BRIDGE_AUDIO_EMBODY_PATH="$NEGATIVE_ADAPTER" \
    AGENT_BRIDGE_RUNTIME_ASSET_DIR="$NEGATIVE_RUNTIME" \
        "$STALE_ROOT/scripts/deploy_from_master.sh" \
        --use-binary "$ROOT/new-agent-bridge" --yes >/dev/null 2>&1; then
    printf '%s\n' 'FAIL: stale --use-binary runtime source unexpectedly passed' >&2
    exit 1
fi
cmp -s "$ROOT/negative-real.before" "$NEGATIVE_INSTALL/agent-bridge.real"
cmp -s "$ROOT/negative-adapter.before" "$NEGATIVE_ADAPTER"
cmp -s "$ROOT/negative-runtime.before" "$NEGATIVE_RUNTIME/app_control.py"

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
    macos_ax_focus_window.swift macos_ax_probe.py macos_ax_verify.py macos_ax_watch.py \
    vision_grounding_ocr.py; do
    test -x "$RUNTIME_ASSET_DIR/$asset"
    cmp -s "$SCRIPT_DIR/$asset" "$RUNTIME_ASSET_DIR/$asset"
done
grep -q '"playlist_current"' "$RUNTIME_ASSET_DIR/app_control.py"
grep -q '"playlist_activate"' "$RUNTIME_ASSET_DIR/app_control.py"
grep -q 'agent_bridge.app_control.operation.v0' "$RUNTIME_ASSET_DIR/app_control.py"
grep -q 'agent_bridge.app_control.operation_preflight.v0' "$RUNTIME_ASSET_DIR/app_control.py"

printf 'PASS: deploy keeps binary, audio adapter, and runtime scripts at repository parity\n'
