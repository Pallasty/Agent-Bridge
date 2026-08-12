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

mkdir -p "$FAKE_BIN" "$ISOLATED_HOME" "$INSTALL_DIR"
git init -q --bare "$REMOTE"
git init -q -b master "$SEED"
git -C "$SEED" config user.name deploy-pinned-assets-test
git -C "$SEED" config user.email deploy-pinned-assets-test@example.invalid
mkdir -p "$SEED/scripts"
for asset in deploy_from_master.sh audio_embody.py desktop_action.py \
    desktop_confirm_store.py desktop_grant.py desktop_invoke.py \
    desktop_snapshot.py desktop_steer.py desktop_verify.py \
    vision_grounding_ocr.py; do
    cp "$SCRIPT_DIR/$asset" "$SEED/scripts/$asset"
done
chmod +x "$SEED/scripts/deploy_from_master.sh"
git -C "$SEED" add scripts
git -C "$SEED" commit -q -m pinned-master-assets
git -C "$SEED" remote add origin "$REMOTE"
git -C "$SEED" push -q -u origin master
git --git-dir="$REMOTE" symbolic-ref HEAD refs/heads/master
git clone -q "$REMOTE" "$REPO"

# The invoking checkout now disagrees with its own origin/master. A broken
# deploy copies these dirty markers; the correct deploy copies detached master.
printf '%s\n' '# DIRTY_CALLER_ADAPTER' > "$REPO/scripts/audio_embody.py"
printf '%s\n' '# DIRTY_CALLER_SNAPSHOT' > "$REPO/scripts/desktop_snapshot.py"

cat > "$FAKE_BIN/cargo" <<'FAKE_CARGO'
#!/usr/bin/env bash
set -euo pipefail
sha="$(git rev-parse HEAD)"
source_file="$CARGO_TARGET_DIR/fake-agent-bridge.c"
cat > "$source_file" <<EOF
#include <stdio.h>
int main(void) { puts("agent-bridge test ${sha}"); return 0; }
EOF
mkdir -p "$CARGO_TARGET_DIR/release"
"$AB_DEPLOY_PINNED_ASSETS_CC" "$source_file" -o "$CARGO_TARGET_DIR/release/agent-bridge"
FAKE_CARGO
chmod +x "$FAKE_BIN/cargo"

HOME="$ISOLATED_HOME" \
PATH="$FAKE_BIN:$PATH" \
CARGO_TARGET_DIR="$TARGET_ROOT" \
AGENT_BRIDGE_INSTALL_DIR="$INSTALL_DIR" \
AGENT_BRIDGE_AUDIO_EMBODY_PATH="$ADAPTER_PATH" \
AGENT_BRIDGE_RUNTIME_ASSET_DIR="$RUNTIME_ASSET_DIR" \
AB_DEPLOY_PINNED_ASSETS_CC="$(command -v cc)" \
    "$REPO/scripts/deploy_from_master.sh" --yes >/dev/null

expected="$TEST_ROOT/expected"
git -C "$REPO" show origin/master:scripts/audio_embody.py > "$expected"
cmp -s "$expected" "$ADAPTER_PATH" || fail "audio adapter came from dirty caller"
for asset in desktop_action.py desktop_confirm_store.py desktop_grant.py \
    desktop_invoke.py desktop_snapshot.py desktop_steer.py desktop_verify.py \
    vision_grounding_ocr.py; do
    git -C "$REPO" show "origin/master:scripts/$asset" > "$expected"
    cmp -s "$expected" "$RUNTIME_ASSET_DIR/$asset" ||
        fail "$asset came from dirty caller"
done
grep -q DIRTY_CALLER "$ADAPTER_PATH" && fail "dirty adapter marker deployed"
grep -q DIRTY_CALLER "$RUNTIME_ASSET_DIR/desktop_snapshot.py" &&
    fail "dirty snapshot marker deployed"

printf '%s\n' "pinned-master-runtime-assets-ok"
