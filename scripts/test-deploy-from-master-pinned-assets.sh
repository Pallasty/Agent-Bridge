#!/usr/bin/env bash
# Regression probe: normal master deploys must install runtime assets from the
# detached master snapshot that produced the binary, not a stale/dirty caller
# worktree. This keeps concurrent same-SHA deploys source-consistent.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ab-deploy-pinned-assets.XXXXXX")"

cleanup() {
    case "$TEST_ROOT" in
        "${TMPDIR:-/tmp}"/ab-deploy-pinned-assets.*)
            find "$TEST_ROOT" -mindepth 1 -depth -delete 2>/dev/null || true
            rmdir "$TEST_ROOT" 2>/dev/null || true
            ;;
    esac
}
trap cleanup EXIT

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

REMOTE="$TEST_ROOT/remote.git"
SEED="$TEST_ROOT/seed"
REPO="$TEST_ROOT/repo"
FAKE_BIN="$TEST_ROOT/fake-bin"
ISOLATED_HOME="$TEST_ROOT/home"
INSTALL_DIR="$TEST_ROOT/install"
ADAPTER_PATH="$TEST_ROOT/share/audio_embody.py"
RUNTIME_ASSET_DIR="$TEST_ROOT/lib/agent-bridge/scripts"
TARGET_ROOT="$TEST_ROOT/target"
LAUNCHCTL_LOG="$TEST_ROOT/launchctl.log"
LSOF_COUNT="$TEST_ROOT/lsof.count"

mkdir -p "$FAKE_BIN" "$ISOLATED_HOME" "$INSTALL_DIR"
git init -q --bare "$REMOTE"
git init -q -b master "$SEED"
git -C "$SEED" config user.name deploy-pinned-assets-test
git -C "$SEED" config user.email deploy-pinned-assets-test@example.invalid
mkdir -p "$SEED/scripts"
for asset in deploy_from_master.sh audio_embody.py app_control.py app-control-recovery-candidates.py \
    app-control-recovery-authorization.py app-control-recovery-authorization-request.py \
    app-control-recovery-signer-status.py app-control-mobile-recovery-signer.py \
    app-control-recovery-hint-dedupe.py desktop_action.py \
    desktop_confirm_store.py desktop_grant.py desktop_invoke.py \
    desktop_snapshot.py desktop_steer.py desktop_verify.py \
    macos_ax_focus_window.swift macos_ax_probe.py macos_ax_verify.py macos_ax_watch.py \
    vision_grounding_ocr.py omnivoice_mac_remote_synth.py \
    omnivoice_onnx_bundle_synth.py omnivoice_onnx_official_decode.py \
    omnivoice_tts_synth.py qwen3_lan_remote_synth.py qwen3_tts_rust_gate.py qwen3_tts_synth.py \
    tts_canary_router.py; do
    cp "$SCRIPT_DIR/$asset" "$SEED/scripts/$asset"
done
mkdir -p "$SEED/config" "$SEED/docs/reports/tts-comparison"
cp "$SCRIPT_DIR/../config/omnivoice-canary.json" "$SEED/config/"
cp "$SCRIPT_DIR/../docs/reports/tts-comparison/human-review-decision-owner-2026-08-15.json" \
    "$SEED/docs/reports/tts-comparison/"
chmod +x "$SEED/scripts/deploy_from_master.sh"
git -C "$SEED" add scripts config docs
git -C "$SEED" commit -q -m pinned-master-assets
git -C "$SEED" remote add origin "$REMOTE"
git -C "$SEED" push -q -u origin master
git --git-dir="$REMOTE" symbolic-ref HEAD refs/heads/master
git clone -q "$REMOTE" "$REPO"

# The invoking checkout now disagrees with its own origin/master. A broken
# deploy copies these dirty markers; the correct deploy copies detached master.
printf '%s\n' '# DIRTY_CALLER_ADAPTER' > "$REPO/scripts/audio_embody.py"
printf '%s\n' '# DIRTY_CALLER_SNAPSHOT' > "$REPO/scripts/desktop_snapshot.py"
printf '%s\n' '# DIRTY_CALLER_APP_CONTROL' > "$REPO/scripts/app_control.py"

cat > "$FAKE_BIN/cargo" <<'FAKE_CARGO'
#!/usr/bin/env bash
set -euo pipefail
sha="$(git rev-parse HEAD)"
source_file="$CARGO_TARGET_DIR/fake-agent-bridge.c"
cat > "$source_file" <<EOF
#include <stdio.h>
int main(void) { puts("agent-bridge test ${sha} agent_bridge.app_control.operation_preflight.v0 agent_bridge.app_control.track_settlement.v0 agent_bridge.app_control.wrapper_contract.v1"); return 0; }
EOF
mkdir -p "$CARGO_TARGET_DIR/release"
"$AB_DEPLOY_PINNED_ASSETS_CC" "$source_file" -o "$CARGO_TARGET_DIR/release/agent-bridge"
FAKE_CARGO
chmod +x "$FAKE_BIN/cargo"

cat > "$FAKE_BIN/launchctl" <<'FAKE_LAUNCHCTL'
#!/usr/bin/env bash
set -euo pipefail
case "$1" in
    print)
        program="$AB_DEPLOY_SERVICE_TEST_WRAPPER"
        [ "${AB_DEPLOY_SERVICE_TEST_CASE:-success}" = unrelated ] && program=/usr/bin/true
        case "$2" in
            *daemon-http) mode=daemon-http ;;
            *) mode=daemon ;;
        esac
        printf 'program = %s\n' "$program"
        malformed=0
        if [ "${AB_DEPLOY_SERVICE_TEST_CASE:-success}" = malformed_second ]; then
            case "$2" in *daemon-http) malformed=1 ;; esac
        fi
        if [ "$malformed" -eq 0 ]; then
            printf 'arguments = {\n'
            printf '\t%s\n' "$program"
            printf '\t%s\n' "$mode"
            printf '}\n'
        fi
        printf 'pid = 4242\n'
        ;;
    kickstart)
        printf '%s\n' "$3" >> "$AB_DEPLOY_SERVICE_TEST_LOG"
        ;;
    *) exit 2 ;;
esac
FAKE_LAUNCHCTL
chmod +x "$FAKE_BIN/launchctl"

cat > "$FAKE_BIN/lsof" <<'FAKE_LSOF'
#!/usr/bin/env bash
set -euo pipefail
count=0
[ ! -f "$AB_DEPLOY_SERVICE_TEST_LSOF_COUNT" ] || count="$(cat "$AB_DEPLOY_SERVICE_TEST_LSOF_COUNT")"
count=$((count + 1))
printf '%s\n' "$count" > "$AB_DEPLOY_SERVICE_TEST_LSOF_COUNT"
[ "$count" -gt 1 ] || exit 1
inode="$(stat -f %i "$AB_DEPLOY_SERVICE_TEST_REAL" 2>/dev/null || stat -c %i "$AB_DEPLOY_SERVICE_TEST_REAL")"
printf 'p4242\nftxt\ni999\nn/tmp/not-the-agent-bridge-binary\nftxt\ni%s\nn%s\n' "$inode" "$AB_DEPLOY_SERVICE_TEST_REAL"
FAKE_LSOF
chmod +x "$FAKE_BIN/lsof"

cat > "$FAKE_BIN/uname" <<'FAKE_UNAME'
#!/usr/bin/env bash
printf 'Darwin\n'
FAKE_UNAME
chmod +x "$FAKE_BIN/uname"

cat > "$FAKE_BIN/codesign" <<'FAKE_CODESIGN'
#!/usr/bin/env bash
exit 0
FAKE_CODESIGN
chmod +x "$FAKE_BIN/codesign"

HOME="$ISOLATED_HOME" \
PATH="$FAKE_BIN:$PATH" \
CARGO_TARGET_DIR="$TARGET_ROOT" \
AGENT_BRIDGE_INSTALL_DIR="$INSTALL_DIR" \
AGENT_BRIDGE_AUDIO_EMBODY_PATH="$ADAPTER_PATH" \
AGENT_BRIDGE_RUNTIME_ASSET_DIR="$RUNTIME_ASSET_DIR" \
AB_DEPLOY_PINNED_ASSETS_CC="$(command -v cc)" \
AB_DEPLOY_SERVICE_TEST_WRAPPER="$INSTALL_DIR/agent-bridge" \
AB_DEPLOY_SERVICE_TEST_REAL="$INSTALL_DIR/agent-bridge.real" \
AB_DEPLOY_SERVICE_TEST_LOG="$LAUNCHCTL_LOG" \
AB_DEPLOY_SERVICE_TEST_LSOF_COUNT="$LSOF_COUNT" \
    "$REPO/scripts/deploy_from_master.sh" --yes >/dev/null

expected="$TEST_ROOT/expected"
git -C "$REPO" show origin/master:scripts/audio_embody.py > "$expected"
cmp -s "$expected" "$ADAPTER_PATH" || fail "audio adapter came from dirty caller"
for asset in omnivoice_mac_remote_synth.py omnivoice_onnx_bundle_synth.py \
    omnivoice_onnx_official_decode.py omnivoice_tts_synth.py \
    qwen3_lan_remote_synth.py qwen3_tts_rust_gate.py qwen3_tts_synth.py tts_canary_router.py; do
    git -C "$REPO" show "origin/master:scripts/$asset" > "$expected"
    cmp -s "$expected" "$(dirname "$ADAPTER_PATH")/$asset" ||
        fail "$asset came from dirty caller"
done
for asset in config/omnivoice-canary.json \
    docs/reports/tts-comparison/human-review-decision-owner-2026-08-15.json; do
    git -C "$REPO" show "origin/master:$asset" > "$expected"
    cmp -s "$expected" "$TEST_ROOT/$asset" || fail "$asset came from dirty caller"
done
for asset in app_control.py app-control-recovery-candidates.py \
    app-control-recovery-authorization.py app-control-recovery-authorization-request.py \
    app-control-recovery-signer-status.py app-control-mobile-recovery-signer.py \
    app-control-recovery-hint-dedupe.py \
    desktop_action.py desktop_confirm_store.py desktop_grant.py \
    desktop_invoke.py desktop_snapshot.py desktop_steer.py desktop_verify.py \
    macos_ax_focus_window.swift macos_ax_probe.py macos_ax_verify.py macos_ax_watch.py \
    vision_grounding_ocr.py; do
    git -C "$REPO" show "origin/master:scripts/$asset" > "$expected"
    cmp -s "$expected" "$RUNTIME_ASSET_DIR/$asset" ||
        fail "$asset came from dirty caller"
done
grep -q DIRTY_CALLER "$ADAPTER_PATH" && fail "dirty adapter marker deployed"
grep -q DIRTY_CALLER "$RUNTIME_ASSET_DIR/desktop_snapshot.py" &&
    fail "dirty snapshot marker deployed"
grep -q DIRTY_CALLER "$RUNTIME_ASSET_DIR/app_control.py" &&
    fail "dirty app_control marker deployed"
grep -q 'agent_bridge.app_control.operation_preflight.v0' "$RUNTIME_ASSET_DIR/app_control.py" ||
    fail "durable operation preflight marker missing from deployed app_control"
grep -q 'agent_bridge.app_control.track_settlement.v0' "$RUNTIME_ASSET_DIR/app_control.py" ||
    fail "durable track settlement marker missing from deployed app_control"
grep -q 'agent_bridge.app_control.wrapper_contract.v1' "$RUNTIME_ASSET_DIR/app_control.py" ||
    fail "wrapper/runtime handshake marker missing from deployed app_control"

[ "$(wc -l < "$LAUNCHCTL_LOG" | tr -d ' ')" = 2 ] ||
    fail "expected daemon and daemon-http launchd refreshes"
grep -qx 'gui/'"$(id -u)"'/com.pallasting.agent-bridge.daemon' "$LAUNCHCTL_LOG" ||
    fail "daemon launchd refresh missing"
grep -qx 'gui/'"$(id -u)"'/com.pallasting.agent-bridge.daemon-http' "$LAUNCHCTL_LOG" ||
    fail "daemon-http launchd refresh missing"

# An alternate install root must not restart jobs bound to another executable.
: > "$LAUNCHCTL_LOG"
HOME="$ISOLATED_HOME" \
PATH="$FAKE_BIN:$PATH" \
CARGO_TARGET_DIR="$TARGET_ROOT" \
AGENT_BRIDGE_INSTALL_DIR="$INSTALL_DIR" \
AGENT_BRIDGE_AUDIO_EMBODY_PATH="$ADAPTER_PATH" \
AGENT_BRIDGE_RUNTIME_ASSET_DIR="$RUNTIME_ASSET_DIR" \
AB_DEPLOY_PINNED_ASSETS_CC="$(command -v cc)" \
AB_DEPLOY_SERVICE_TEST_WRAPPER="$INSTALL_DIR/agent-bridge" \
AB_DEPLOY_SERVICE_TEST_REAL="$INSTALL_DIR/agent-bridge.real" \
AB_DEPLOY_SERVICE_TEST_LOG="$LAUNCHCTL_LOG" \
AB_DEPLOY_SERVICE_TEST_LSOF_COUNT="$LSOF_COUNT" \
AB_DEPLOY_SERVICE_TEST_CASE=unrelated \
    "$REPO/scripts/deploy_from_master.sh" --yes >/dev/null
[ ! -s "$LAUNCHCTL_LOG" ] || fail "unrelated launchd program was restarted"

# Both matching jobs are preflighted before mutation. A malformed second job
# must fail closed without restarting the already-valid first job.
: > "$LAUNCHCTL_LOG"
set +e
malformed_output="$({
    HOME="$ISOLATED_HOME" \
    PATH="$FAKE_BIN:$PATH" \
    CARGO_TARGET_DIR="$TARGET_ROOT" \
    AGENT_BRIDGE_INSTALL_DIR="$INSTALL_DIR" \
    AGENT_BRIDGE_AUDIO_EMBODY_PATH="$ADAPTER_PATH" \
    AGENT_BRIDGE_RUNTIME_ASSET_DIR="$RUNTIME_ASSET_DIR" \
    AB_DEPLOY_PINNED_ASSETS_CC="$(command -v cc)" \
    AB_DEPLOY_SERVICE_TEST_WRAPPER="$INSTALL_DIR/agent-bridge" \
    AB_DEPLOY_SERVICE_TEST_REAL="$INSTALL_DIR/agent-bridge.real" \
    AB_DEPLOY_SERVICE_TEST_LOG="$LAUNCHCTL_LOG" \
    AB_DEPLOY_SERVICE_TEST_LSOF_COUNT="$LSOF_COUNT" \
    AB_DEPLOY_SERVICE_TEST_CASE=malformed_second \
        "$REPO/scripts/deploy_from_master.sh" --yes
} 2>&1)"
malformed_status=$?
set -e
[ "$malformed_status" -ne 0 ] || fail "malformed launchd contract was accepted"
[ ! -s "$LAUNCHCTL_LOG" ] || fail "a service restarted before both preflights passed"
case "$malformed_output" in
    *"launchd service argument program mismatch"*) ;;
    *) fail "malformed launchd failure reason missing" ;;
esac

printf '%s\n' "pinned-master-runtime-assets-ok"
