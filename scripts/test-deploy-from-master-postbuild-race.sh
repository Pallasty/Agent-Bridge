#!/usr/bin/env bash
# Regression probe for deploy_from_master.sh's post-build origin/master gate.
# Uses an isolated repository, bare remote, HOME, install dir, and fake cargo.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_SCRIPT="$SCRIPT_DIR/deploy_from_master.sh"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ab-deploy-postbuild-race.XXXXXX")"

cleanup() {
    case "$TEST_ROOT" in
        "${TMPDIR:-/tmp}"/ab-deploy-postbuild-race.*)
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

hash_file() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

REMOTE="$TEST_ROOT/remote.git"
SEED="$TEST_ROOT/seed"
REPO="$TEST_ROOT/repo"
FAKE_BIN="$TEST_ROOT/fake-bin"
ISOLATED_HOME="$TEST_ROOT/home"
INSTALL_DIR="$TEST_ROOT/install"
TARGET_DIR="$TEST_ROOT/target"
if [ -x /usr/bin/true ]; then
    NATIVE_TRUE=/usr/bin/true
else
    NATIVE_TRUE=/bin/true
fi

mkdir -p "$FAKE_BIN" "$ISOLATED_HOME" "$INSTALL_DIR"
git init -q --bare "$REMOTE"
git init -q -b master "$SEED"
git -C "$SEED" config user.name deploy-race-test
git -C "$SEED" config user.email deploy-race-test@example.invalid
mkdir -p "$SEED/scripts"
for asset in deploy_from_master.sh audio_embody.py app_control.py app-control-recovery-candidates.py desktop_action.py \
    desktop_confirm_store.py desktop_grant.py desktop_invoke.py \
    desktop_snapshot.py desktop_steer.py desktop_verify.py \
    macos_ax_focus_window.swift macos_ax_probe.py macos_ax_verify.py macos_ax_watch.py \
    vision_grounding_ocr.py omnivoice_mac_remote_synth.py \
    omnivoice_onnx_bundle_synth.py omnivoice_onnx_official_decode.py \
    omnivoice_tts_synth.py qwen3_tts_rust_gate.py qwen3_tts_synth.py \
    tts_canary_router.py; do
    cp "$SCRIPT_DIR/$asset" "$SEED/scripts/$asset"
done
mkdir -p "$SEED/config" "$SEED/docs/reports/tts-comparison"
cp "$SCRIPT_DIR/../config/omnivoice-canary.json" "$SEED/config/"
cp "$SCRIPT_DIR/../docs/reports/tts-comparison/human-review-decision-owner-2026-08-15.json" \
    "$SEED/docs/reports/tts-comparison/"
chmod +x "$SEED/scripts/deploy_from_master.sh"
git -C "$SEED" add scripts config docs
git -C "$SEED" commit -q -m initial
git -C "$SEED" remote add origin "$REMOTE"
git -C "$SEED" push -q -u origin master
git --git-dir="$REMOTE" symbolic-ref HEAD refs/heads/master
git clone -q "$REMOTE" "$REPO"

cat > "$FAKE_BIN/cargo" <<'FAKE_CARGO'
#!/usr/bin/env bash
set -euo pipefail
master_sha="$(git --git-dir="$AB_DEPLOY_RACE_TEST_REMOTE" rev-parse refs/heads/master)"
source_file="$AB_DEPLOY_RACE_TEST_ROOT/fake-agent-bridge.c"
cat > "$source_file" <<EOF
#include <stdio.h>
int main(void) { puts("agent-bridge test ${master_sha} agent_bridge.app_control.operation_preflight.v0 agent_bridge.app_control.track_settlement.v0 agent_bridge.app_control.wrapper_contract.v1"); return 0; }
EOF
mkdir -p "$CARGO_TARGET_DIR/release"
"$AB_DEPLOY_RACE_TEST_CC" "$source_file" -o "$CARGO_TARGET_DIR/release/agent-bridge"

advance="$AB_DEPLOY_RACE_TEST_ROOT/advance"
git clone -q "$AB_DEPLOY_RACE_TEST_REMOTE" "$advance"
git -C "$advance" config user.name deploy-race-test
git -C "$advance" config user.email deploy-race-test@example.invalid
printf '%s\n' advanced-during-build > "$advance/advanced-during-build.txt"
git -C "$advance" add advanced-during-build.txt
git -C "$advance" commit -q -m advance-during-build
git -C "$advance" push -q origin master
FAKE_CARGO
chmod +x "$FAKE_BIN/cargo"

cp "$NATIVE_TRUE" "$INSTALL_DIR/agent-bridge.real"
before_hash="$(hash_file "$INSTALL_DIR/agent-bridge.real")"

set +e
output="$({
    HOME="$ISOLATED_HOME" \
    PATH="$FAKE_BIN:$PATH" \
    CARGO_TARGET_DIR="$TARGET_DIR" \
    AGENT_BRIDGE_INSTALL_DIR="$INSTALL_DIR" \
    AB_DEPLOY_RACE_TEST_ROOT="$TEST_ROOT" \
    AB_DEPLOY_RACE_TEST_REMOTE="$REMOTE" \
    AB_DEPLOY_RACE_TEST_CC="$(command -v cc)" \
    "$REPO/scripts/deploy_from_master.sh" --yes
} 2>&1)"
status=$?
set -e

[ "$status" -ne 0 ] || fail "stale build unexpectedly deployed"
case "$output" in
    *"origin/master advanced during the release build"*) ;;
    *) fail "missing post-build master-advance error" ;;
esac

after_hash="$(hash_file "$INSTALL_DIR/agent-bridge.real")"
[ "$after_hash" = "$before_hash" ] || fail "live target changed before the gate"

backup="$(find "$INSTALL_DIR" -maxdepth 1 -name 'agent-bridge.real.bak-deploy-*' -print -quit)"
[ -z "$backup" ] || fail "backup was created before the gate: $backup"

staging="$(find "$TEST_ROOT" -maxdepth 1 -name '.ab-deploy-build.*' -print -quit)"
[ -z "$staging" ] || fail "staging worktree leaked: $staging"

printf '%s\n' "postbuild-master-race-gate-ok"
