#!/usr/bin/env bash
# Regression probe: normal master deploys must install runtime assets from the
# detached master snapshot that produced the binary, not a stale/dirty caller
# worktree. This keeps concurrent same-SHA deploys source-consistent.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ab-deploy-pinned-assets.XXXXXX")"
TEST_ROOT="$(cd -P "$TEST_ROOT" && pwd -P)"
TEST_TEMP_BASE="$(cd -P "${TMPDIR:-/tmp}" && pwd -P)"

cleanup() {
    case "$TEST_ROOT" in
        "$TEST_TEMP_BASE"/ab-deploy-pinned-assets.*)
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
STATE_DIR="$TEST_ROOT/state"
ADAPTER_PATH="$TEST_ROOT/share/audio_embody.py"
RUNTIME_ASSET_DIR="$TEST_ROOT/lib/agent-bridge/scripts"
TARGET_ROOT="$TEST_ROOT/target"
LAUNCHCTL_LOG="$TEST_ROOT/launchctl.log"
LSOF_COUNT="$TEST_ROOT/lsof.count"
CURL_COUNT="$TEST_ROOT/curl.count"
CURL_LOG="$TEST_ROOT/curl.log"

mkdir -p "$FAKE_BIN" "$ISOLATED_HOME" "$INSTALL_DIR" "$STATE_DIR"
CANONICAL_REAL_PATH="$(cd "$INSTALL_DIR" && pwd -P)/agent-bridge.real"
export AGENT_BRIDGE_DEPLOY_LEASE_TEST_MODE=1
export AGENT_BRIDGE_DEPLOY_PROFILE=r9
export AGENT_BRIDGE_DEPLOY_LEASE_TEST_ROOT="$TEST_ROOT"
export AGENT_BRIDGE_DEPLOY_REMOTE=origin
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
    macos_ax_focus_window.swift macos_ax_native_probe.swift macos_ax_probe.py macos_ax_verify.py macos_ax_watch.py \
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
int main(void) { puts("agent-bridge test ${sha} agent_bridge.app_control.operation_preflight.v0 agent_bridge.app_control.track_settlement.v0 agent_bridge.app_control.wrapper_contract.v1 agent_bridge.workload_receipt_commit.v1"); return 0; }
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
        if [ "${AB_DEPLOY_SERVICE_TEST_CASE:-success}" = palace_missing ]; then
            case "$2" in
                *palace)
                    printf 'Could not find service "%s" in domain for user\n' "$2" >&2
                    exit 113
                    ;;
            esac
        fi
        program="$AB_DEPLOY_SERVICE_TEST_WRAPPER"
        [ "${AB_DEPLOY_SERVICE_TEST_CASE:-success}" = unrelated ] && program=/usr/bin/true
        case "$2" in
            *daemon-http) mode=daemon-http; pid=4242 ;;
            *palace) mode=palace; pid=4243 ;;
            *) mode=daemon; pid=4241 ;;
        esac
        printf 'program = %s\n' "$program"
        printf 'arguments = {\n'
        printf '\t%s\n' "$program"
        printf '\t%s\n' "$mode"
        if [ "$mode" = palace ]; then
            printf '\t%s\n' serve
            printf '\t%s\n' --host
            printf '\t%s\n' 127.0.0.1
            printf '\t%s\n' --port
            if [ "${AB_DEPLOY_SERVICE_TEST_CASE:-success}" = malformed_palace_port ]; then
                printf '\t%s\n' 7980
            else
                printf '\t%s\n' 7979
            fi
        fi
        printf '}\n'
        printf 'pid = %s\n' "$pid"
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
pid=""
previous=""
for arg in "$@"; do
    if [ "$previous" = -p ]; then
        pid="$arg"
        break
    fi
    previous="$arg"
done
[ -n "$pid" ] || exit 2
case "$pid:$*" in
    4242:*"-iTCP:7878"*|4243:*"-iTCP:7979"*)
        printf 'p%s\n' "$pid"
        exit 0
        ;;
    *" -iTCP:"*) exit 1 ;;
esac
count=0
count_file="$AB_DEPLOY_SERVICE_TEST_LSOF_COUNT.$pid"
[ ! -f "$count_file" ] || count="$(cat "$count_file")"
count=$((count + 1))
printf '%s\n' "$count" > "$count_file"
case "$(/usr/bin/uname -s 2>/dev/null || uname -s)" in
    Darwin) inode="$(stat -f %i "$AB_DEPLOY_SERVICE_TEST_REAL")" ;;
    Linux) inode="$(stat -c %i "$AB_DEPLOY_SERVICE_TEST_REAL")" ;;
    *) exit 2 ;;
esac
[ "$count" -gt 1 ] || inode=999
printf 'p%s\nftxt\ni999\nn/tmp/not-the-agent-bridge-binary\nftxt\ni%s\nn%s\n' "$pid" "$inode" "$AB_DEPLOY_SERVICE_TEST_REAL"
FAKE_LSOF
chmod +x "$FAKE_BIN/lsof"

cat > "$FAKE_BIN/curl" <<'FAKE_CURL'
#!/usr/bin/env bash
set -euo pipefail
count=0
[ ! -f "$AB_DEPLOY_SERVICE_TEST_CURL_COUNT" ] || count="$(cat "$AB_DEPLOY_SERVICE_TEST_CURL_COUNT")"
count=$((count + 1))
printf '%s\n' "$count" > "$AB_DEPLOY_SERVICE_TEST_CURL_COUNT"
[ -z "${AB_DEPLOY_SERVICE_TEST_CURL_LOG:-}" ] || printf '%s\n' "${!#}" >> "$AB_DEPLOY_SERVICE_TEST_CURL_LOG"
case "${!#}" in
    http://127.0.0.1:7878/healthz|http://127.0.0.1:7979/healthz) ;;
    *) exit 2 ;;
esac
[ "${AB_DEPLOY_SERVICE_TEST_CASE:-success}" != never_healthy ] || exit 22
if [ "${AB_DEPLOY_SERVICE_TEST_CASE:-success}" = palace_never_healthy ] &&
        [ "${!#}" = "http://127.0.0.1:7979/healthz" ]; then
    exit 22
fi
[ "$count" -gt 4 ] || exit 22
printf 'ok\n'
FAKE_CURL
chmod +x "$FAKE_BIN/curl"

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
AGENT_BRIDGE_DEPLOY_STATE_DIR="$STATE_DIR" \
AGENT_BRIDGE_AUDIO_EMBODY_PATH="$ADAPTER_PATH" \
AGENT_BRIDGE_RUNTIME_ASSET_DIR="$RUNTIME_ASSET_DIR" \
AB_DEPLOY_PINNED_ASSETS_CC="$(command -v cc)" \
AB_DEPLOY_SERVICE_TEST_WRAPPER="$INSTALL_DIR/agent-bridge" \
AB_DEPLOY_SERVICE_TEST_REAL="$CANONICAL_REAL_PATH" \
AB_DEPLOY_SERVICE_TEST_LOG="$LAUNCHCTL_LOG" \
AB_DEPLOY_SERVICE_TEST_LSOF_COUNT="$LSOF_COUNT" \
AB_DEPLOY_SERVICE_TEST_CURL_COUNT="$CURL_COUNT" \
AB_DEPLOY_SERVICE_TEST_CURL_LOG="$CURL_LOG" \
    "$REPO/scripts/deploy_from_master.sh" --yes >/dev/null
[ "$(grep -c '^http://127.0.0.1:7878/healthz$' "$CURL_LOG")" -ge 8 ] ||
    fail "daemon-http health recovery was not polled to stability"
[ "$(grep -c '^http://127.0.0.1:7979/healthz$' "$CURL_LOG")" -ge 8 ] ||
    fail "Palace health recovery was not polled to stability"

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
    macos_ax_focus_window.swift macos_ax_native_probe.swift macos_ax_probe.py macos_ax_verify.py macos_ax_watch.py \
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

[ "$(wc -l < "$LAUNCHCTL_LOG" | tr -d ' ')" = 3 ] ||
    fail "expected daemon, daemon-http, and Palace launchd refreshes"
grep -qx 'gui/'"$(id -u)"'/com.pallasting.agent-bridge.daemon' "$LAUNCHCTL_LOG" ||
    fail "daemon launchd refresh missing"
grep -qx 'gui/'"$(id -u)"'/com.pallasting.agent-bridge.daemon-http' "$LAUNCHCTL_LOG" ||
    fail "daemon-http launchd refresh missing"
grep -qx 'gui/'"$(id -u)"'/com.pallasting.agent-bridge.palace' "$LAUNCHCTL_LOG" ||
    fail "Palace launchd refresh missing"

# A host without the optional Palace LaunchAgent must still deploy the two core
# jobs. The missing job is a skip, not a partial-refresh failure.
: > "$LAUNCHCTL_LOG"
HOME="$ISOLATED_HOME" \
PATH="$FAKE_BIN:$PATH" \
CARGO_TARGET_DIR="$TARGET_ROOT" \
AGENT_BRIDGE_INSTALL_DIR="$INSTALL_DIR" \
AGENT_BRIDGE_DEPLOY_STATE_DIR="$STATE_DIR" \
AGENT_BRIDGE_AUDIO_EMBODY_PATH="$ADAPTER_PATH" \
AGENT_BRIDGE_RUNTIME_ASSET_DIR="$RUNTIME_ASSET_DIR" \
AB_DEPLOY_PINNED_ASSETS_CC="$(command -v cc)" \
AB_DEPLOY_SERVICE_TEST_WRAPPER="$INSTALL_DIR/agent-bridge" \
AB_DEPLOY_SERVICE_TEST_REAL="$CANONICAL_REAL_PATH" \
AB_DEPLOY_SERVICE_TEST_LOG="$LAUNCHCTL_LOG" \
AB_DEPLOY_SERVICE_TEST_LSOF_COUNT="$LSOF_COUNT" \
AB_DEPLOY_SERVICE_TEST_CURL_COUNT="$CURL_COUNT" \
AB_DEPLOY_SERVICE_TEST_CASE=palace_missing \
AGENT_BRIDGE_DEPLOY_FORCE_REINSTALL=1 \
AGENT_BRIDGE_DEPLOY_FORCE_REASON=pinned-assets-palace-missing-regression \
    "$REPO/scripts/deploy_from_master.sh" --yes >/dev/null
[ "$(wc -l < "$LAUNCHCTL_LOG" | tr -d ' ')" = 2 ] ||
    fail "missing Palace did not preserve the two core refreshes"
grep -q 'agent-bridge.palace' "$LAUNCHCTL_LOG" &&
    fail "missing Palace LaunchAgent was restarted"

# An alternate install root must not restart jobs bound to another executable.
: > "$LAUNCHCTL_LOG"
HOME="$ISOLATED_HOME" \
PATH="$FAKE_BIN:$PATH" \
CARGO_TARGET_DIR="$TARGET_ROOT" \
AGENT_BRIDGE_INSTALL_DIR="$INSTALL_DIR" \
AGENT_BRIDGE_DEPLOY_STATE_DIR="$STATE_DIR" \
AGENT_BRIDGE_AUDIO_EMBODY_PATH="$ADAPTER_PATH" \
AGENT_BRIDGE_RUNTIME_ASSET_DIR="$RUNTIME_ASSET_DIR" \
AB_DEPLOY_PINNED_ASSETS_CC="$(command -v cc)" \
AB_DEPLOY_SERVICE_TEST_WRAPPER="$INSTALL_DIR/agent-bridge" \
AB_DEPLOY_SERVICE_TEST_REAL="$CANONICAL_REAL_PATH" \
AB_DEPLOY_SERVICE_TEST_LOG="$LAUNCHCTL_LOG" \
AB_DEPLOY_SERVICE_TEST_LSOF_COUNT="$LSOF_COUNT" \
AB_DEPLOY_SERVICE_TEST_CURL_COUNT="$CURL_COUNT" \
AB_DEPLOY_SERVICE_TEST_CASE=unrelated \
AGENT_BRIDGE_DEPLOY_FORCE_REINSTALL=1 \
AGENT_BRIDGE_DEPLOY_FORCE_REASON=pinned-assets-unrelated-service-regression \
    "$REPO/scripts/deploy_from_master.sh" --yes >/dev/null
[ ! -s "$LAUNCHCTL_LOG" ] || fail "unrelated launchd program was restarted"

# Every matching job is preflighted before service mutation. A Palace endpoint
# drift must fail closed without restarting either already-valid core job.
: > "$LAUNCHCTL_LOG"
set +e
malformed_output="$({
    HOME="$ISOLATED_HOME" \
    PATH="$FAKE_BIN:$PATH" \
    CARGO_TARGET_DIR="$TARGET_ROOT" \
    AGENT_BRIDGE_INSTALL_DIR="$INSTALL_DIR" \
    AGENT_BRIDGE_DEPLOY_STATE_DIR="$STATE_DIR" \
    AGENT_BRIDGE_AUDIO_EMBODY_PATH="$ADAPTER_PATH" \
    AGENT_BRIDGE_RUNTIME_ASSET_DIR="$RUNTIME_ASSET_DIR" \
    AB_DEPLOY_PINNED_ASSETS_CC="$(command -v cc)" \
    AB_DEPLOY_SERVICE_TEST_WRAPPER="$INSTALL_DIR/agent-bridge" \
    AB_DEPLOY_SERVICE_TEST_REAL="$CANONICAL_REAL_PATH" \
    AB_DEPLOY_SERVICE_TEST_LOG="$LAUNCHCTL_LOG" \
    AB_DEPLOY_SERVICE_TEST_LSOF_COUNT="$LSOF_COUNT" \
    AB_DEPLOY_SERVICE_TEST_CURL_COUNT="$CURL_COUNT" \
    AB_DEPLOY_SERVICE_TEST_CASE=malformed_palace_port \
    AGENT_BRIDGE_DEPLOY_FORCE_REINSTALL=1 \
    AGENT_BRIDGE_DEPLOY_FORCE_REASON=pinned-assets-malformed-service-regression \
        "$REPO/scripts/deploy_from_master.sh" --yes
} 2>&1)"
malformed_status=$?
set -e
[ "$malformed_status" -ne 0 ] || fail "malformed launchd contract was accepted"
[ ! -s "$LAUNCHCTL_LOG" ] || fail "a service restarted before both preflights passed"
case "$malformed_output" in
    *"launchd service argument mismatch"*) ;;
    *) fail "malformed launchd failure reason missing" ;;
esac
# A process with the deployed inode but no healthy HTTP endpoint must fail
# closed. Keep the test timeout short via the deployment's testable poll cap.
: > "$LAUNCHCTL_LOG"
: > "$CURL_COUNT"
set +e
unhealthy_output="$({
    HOME="$ISOLATED_HOME" \
    PATH="$FAKE_BIN:$PATH" \
    CARGO_TARGET_DIR="$TARGET_ROOT" \
    AGENT_BRIDGE_INSTALL_DIR="$INSTALL_DIR" \
    AGENT_BRIDGE_DEPLOY_STATE_DIR="$STATE_DIR" \
    AGENT_BRIDGE_AUDIO_EMBODY_PATH="$ADAPTER_PATH" \
    AGENT_BRIDGE_RUNTIME_ASSET_DIR="$RUNTIME_ASSET_DIR" \
    AGENT_BRIDGE_SERVICE_VERIFY_ATTEMPTS=12 \
    AB_DEPLOY_PINNED_ASSETS_CC="$(command -v cc)" \
    AB_DEPLOY_SERVICE_TEST_WRAPPER="$INSTALL_DIR/agent-bridge" \
    AB_DEPLOY_SERVICE_TEST_REAL="$CANONICAL_REAL_PATH" \
    AB_DEPLOY_SERVICE_TEST_LOG="$LAUNCHCTL_LOG" \
    AB_DEPLOY_SERVICE_TEST_LSOF_COUNT="$LSOF_COUNT" \
    AB_DEPLOY_SERVICE_TEST_CURL_COUNT="$CURL_COUNT" \
    AB_DEPLOY_SERVICE_TEST_CASE=never_healthy \
    AGENT_BRIDGE_DEPLOY_RECOVERY=roll_forward \
    AGENT_BRIDGE_DEPLOY_RECOVERY_REASON=pinned-assets-continue-after-malformed-receipt \
        "$REPO/scripts/deploy_from_master.sh" --yes
} 2>&1)"
unhealthy_status=$?
set -e
[ "$unhealthy_status" -ne 0 ] || fail "unhealthy daemon-http was accepted"
case "$unhealthy_output" in
    *"did not become stable and healthy"*) ;;
    *) fail "unhealthy daemon-http failure reason missing" ;;
esac

# Reconcile the retained recovery_required lease through the governed
# roll-forward path. Recovery must finish an authoritative install so the
# durable handoff cannot be mistaken for a completed repair.
HOME="$ISOLATED_HOME" \
PATH="$FAKE_BIN:$PATH" \
CARGO_TARGET_DIR="$TARGET_ROOT" \
AGENT_BRIDGE_INSTALL_DIR="$INSTALL_DIR" \
AGENT_BRIDGE_DEPLOY_STATE_DIR="$STATE_DIR" \
AGENT_BRIDGE_AUDIO_EMBODY_PATH="$ADAPTER_PATH" \
AGENT_BRIDGE_RUNTIME_ASSET_DIR="$RUNTIME_ASSET_DIR" \
AB_DEPLOY_PINNED_ASSETS_CC="$(command -v cc)" \
AB_DEPLOY_SERVICE_TEST_WRAPPER="$INSTALL_DIR/agent-bridge" \
AB_DEPLOY_SERVICE_TEST_REAL="$CANONICAL_REAL_PATH" \
AB_DEPLOY_SERVICE_TEST_LOG="$LAUNCHCTL_LOG" \
AB_DEPLOY_SERVICE_TEST_LSOF_COUNT="$LSOF_COUNT" \
AB_DEPLOY_SERVICE_TEST_CURL_COUNT="$CURL_COUNT" \
AGENT_BRIDGE_DEPLOY_RECOVERY=roll_forward \
AGENT_BRIDGE_DEPLOY_RECOVERY_REASON=pinned-assets-post-health-recovery \
    "$REPO/scripts/deploy_from_master.sh" --yes >/dev/null

# Palace has its own listener contract. A healthy daemon-http must not mask a
# Palace process that adopted the binary but never opened port 7979.
: > "$LAUNCHCTL_LOG"
set +e
palace_unhealthy_output="$({
    HOME="$ISOLATED_HOME" \
    PATH="$FAKE_BIN:$PATH" \
    CARGO_TARGET_DIR="$TARGET_ROOT" \
    AGENT_BRIDGE_INSTALL_DIR="$INSTALL_DIR" \
    AGENT_BRIDGE_DEPLOY_STATE_DIR="$STATE_DIR" \
    AGENT_BRIDGE_AUDIO_EMBODY_PATH="$ADAPTER_PATH" \
    AGENT_BRIDGE_RUNTIME_ASSET_DIR="$RUNTIME_ASSET_DIR" \
    AGENT_BRIDGE_SERVICE_VERIFY_ATTEMPTS=12 \
    AB_DEPLOY_PINNED_ASSETS_CC="$(command -v cc)" \
    AB_DEPLOY_SERVICE_TEST_WRAPPER="$INSTALL_DIR/agent-bridge" \
    AB_DEPLOY_SERVICE_TEST_REAL="$CANONICAL_REAL_PATH" \
    AB_DEPLOY_SERVICE_TEST_LOG="$LAUNCHCTL_LOG" \
    AB_DEPLOY_SERVICE_TEST_LSOF_COUNT="$LSOF_COUNT" \
    AB_DEPLOY_SERVICE_TEST_CURL_COUNT="$CURL_COUNT" \
    AB_DEPLOY_SERVICE_TEST_CASE=palace_never_healthy \
    AGENT_BRIDGE_DEPLOY_FORCE_REINSTALL=1 \
    AGENT_BRIDGE_DEPLOY_FORCE_REASON=pinned-assets-palace-health-regression \
        "$REPO/scripts/deploy_from_master.sh" --yes
} 2>&1)"
palace_unhealthy_status=$?
set -e
[ "$palace_unhealthy_status" -ne 0 ] || fail "unhealthy Palace was accepted"
case "$palace_unhealthy_output" in
    *"did not become stable and healthy: com.pallasting.agent-bridge.palace"*) ;;
    *)
        printf '%s\n' "$palace_unhealthy_output" >&2
        fail "unhealthy Palace failure reason missing"
        ;;
esac

# Settle the Palace health failure through the same governed roll-forward path.
HOME="$ISOLATED_HOME" \
PATH="$FAKE_BIN:$PATH" \
CARGO_TARGET_DIR="$TARGET_ROOT" \
AGENT_BRIDGE_INSTALL_DIR="$INSTALL_DIR" \
AGENT_BRIDGE_DEPLOY_STATE_DIR="$STATE_DIR" \
AGENT_BRIDGE_AUDIO_EMBODY_PATH="$ADAPTER_PATH" \
AGENT_BRIDGE_RUNTIME_ASSET_DIR="$RUNTIME_ASSET_DIR" \
AB_DEPLOY_PINNED_ASSETS_CC="$(command -v cc)" \
AB_DEPLOY_SERVICE_TEST_WRAPPER="$INSTALL_DIR/agent-bridge" \
AB_DEPLOY_SERVICE_TEST_REAL="$CANONICAL_REAL_PATH" \
AB_DEPLOY_SERVICE_TEST_LOG="$LAUNCHCTL_LOG" \
AB_DEPLOY_SERVICE_TEST_LSOF_COUNT="$LSOF_COUNT" \
AB_DEPLOY_SERVICE_TEST_CURL_COUNT="$CURL_COUNT" \
AGENT_BRIDGE_DEPLOY_RECOVERY=roll_forward \
AGENT_BRIDGE_DEPLOY_RECOVERY_REASON=pinned-assets-post-palace-health-recovery \
    "$REPO/scripts/deploy_from_master.sh" --yes >/dev/null

# A live deploy owner must block a second invocation before any launchd job is
# mutated. This is the shared install-state serialization boundary.
: > "$LAUNCHCTL_LOG"
mkdir -p "$STATE_DIR/active.lock"
printf '%s\n' "$$" > "$STATE_DIR/active.lock/pid"
set +e
locked_output="$({
    HOME="$ISOLATED_HOME" \
    PATH="$FAKE_BIN:$PATH" \
    CARGO_TARGET_DIR="$TARGET_ROOT" \
    AGENT_BRIDGE_INSTALL_DIR="$INSTALL_DIR" \
    AGENT_BRIDGE_DEPLOY_STATE_DIR="$STATE_DIR" \
    AGENT_BRIDGE_AUDIO_EMBODY_PATH="$ADAPTER_PATH" \
    AGENT_BRIDGE_RUNTIME_ASSET_DIR="$RUNTIME_ASSET_DIR" \
    AB_DEPLOY_PINNED_ASSETS_CC="$(command -v cc)" \
        "$REPO/scripts/deploy_from_master.sh" --yes
} 2>&1)"
locked_status=$?
set -e
[ "$locked_status" -ne 0 ] || fail "concurrent deploy lock was ignored"
[ ! -s "$LAUNCHCTL_LOG" ] || fail "launchd mutated while deploy lock was held"
case "$locked_output" in
    *"publisher lease metadata is missing, unknown, or corrupt"*) ;;
    *) fail "legacy/unknown deploy lock failure reason missing" ;;
esac

printf '%s\n' "pinned-master-runtime-assets-ok"
