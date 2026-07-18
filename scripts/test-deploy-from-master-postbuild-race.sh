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
cp "$DEPLOY_SCRIPT" "$SEED/scripts/deploy_from_master.sh"
chmod +x "$SEED/scripts/deploy_from_master.sh"
git -C "$SEED" add scripts/deploy_from_master.sh
git -C "$SEED" commit -q -m initial
git -C "$SEED" remote add origin "$REMOTE"
git -C "$SEED" push -q -u origin master
git --git-dir="$REMOTE" symbolic-ref HEAD refs/heads/master
git clone -q "$REMOTE" "$REPO"

cat > "$FAKE_BIN/cargo" <<'FAKE_CARGO'
#!/usr/bin/env bash
set -euo pipefail
advance="$AB_DEPLOY_RACE_TEST_ROOT/advance"
git clone -q "$AB_DEPLOY_RACE_TEST_REMOTE" "$advance"
git -C "$advance" config user.name deploy-race-test
git -C "$advance" config user.email deploy-race-test@example.invalid
printf '%s\n' advanced-during-build > "$advance/advanced-during-build.txt"
git -C "$advance" add advanced-during-build.txt
git -C "$advance" commit -q -m advance-during-build
git -C "$advance" push -q origin master
mkdir -p "$CARGO_TARGET_DIR/release"
cp "$AB_DEPLOY_RACE_NATIVE_TRUE" "$CARGO_TARGET_DIR/release/agent-bridge"
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
    AB_DEPLOY_RACE_NATIVE_TRUE="$NATIVE_TRUE" \
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
