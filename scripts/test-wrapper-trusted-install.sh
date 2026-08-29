#!/bin/bash
# Isolated trust-chain checks for the fixed-root wrapper installer.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SOURCE_INSTALLER="$SCRIPT_DIR/wrapper/install.sh"
SOURCE_WRAPPER="$SCRIPT_DIR/wrapper/agent-bridge-wrapper.sh"
SOURCE_CREDS="$SCRIPT_DIR/wrapper/creds.example"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ab-wrapper-install.XXXXXX")"
TEST_PARENT="$(cd -P "${TMPDIR:-/tmp}" && pwd -P)"
trap 'case "$TEST_ROOT" in "$TEST_PARENT"/ab-wrapper-install.*) find "$TEST_ROOT" -mindepth 1 -depth -delete 2>/dev/null || true; rmdir "$TEST_ROOT" 2>/dev/null || true ;; esac' EXIT
chmod 700 "$TEST_ROOT"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

mode_of() { stat -c %a "$1"; }
owner_of() { stat -c %u "$1"; }
inode_of() { stat -c %i "$1"; }

prepare_root() {
    local root="$1" repo wrapper_dir provisioner
    repo="$root/source/agent-bridge"
    wrapper_dir="$repo/scripts/wrapper"
    provisioner="$repo/scripts/provision-trusted-deployment-root.py"
    mkdir -p "$wrapper_dir" "$repo/.git" \
        "$root/provisioning" "$root/publisher-state/deploy"
    chmod 700 "$root" "$root/source" "$repo" "$repo/.git" \
        "$repo/scripts" "$wrapper_dir" "$root/provisioning" \
        "$root/publisher-state" "$root/publisher-state/deploy"
    cp "$SOURCE_INSTALLER" "$wrapper_dir/install.sh"
    cp "$SOURCE_WRAPPER" "$wrapper_dir/agent-bridge-wrapper.sh"
    cp "$SOURCE_CREDS" "$wrapper_dir/creds.example"
    cat > "$provisioner" <<'PY'
#!/usr/bin/python3
import argparse
import json
import os
import stat

parser = argparse.ArgumentParser()
parser.add_argument("command")
parser.add_argument("--deploy-root", required=True)
parser.add_argument("--inherited-lock-fd", type=int)
args = parser.parse_args()
if args.command != "verify":
    raise SystemExit(2)
receipt = os.path.join(args.deploy_root, "provisioning/current.json")
lock = os.path.join(args.deploy_root, "publisher-state/deploy/publisher.kernel.lock")
if open(receipt, encoding="ascii").read() != "fixture-provisioning-receipt\n":
    raise SystemExit(1)
path = os.stat(lock, follow_symlinks=False)
if not stat.S_ISREG(path.st_mode) or stat.S_IMODE(path.st_mode) != 0o600:
    raise SystemExit(1)
if args.inherited_lock_fd is not None:
    opened = os.fstat(args.inherited_lock_fd)
    if (opened.st_dev, opened.st_ino) != (path.st_dev, path.st_ino):
        raise SystemExit(1)
print(json.dumps({
    "schema": "agent_bridge.trusted_deployment_root_provisioning_result.v1",
    "command": "verify",
    "status": "verified_provisioning_custody",
    "candidate_commit": "a" * 40,
    "receipt_digest": "b" * 64,
}, sort_keys=True, separators=(",", ":")))
PY
    printf '%s\n' fixture-provisioning-receipt > "$root/provisioning/current.json"
    : > "$root/publisher-state/deploy/publisher.kernel.lock"
    chmod 600 "$wrapper_dir/install.sh" \
        "$wrapper_dir/agent-bridge-wrapper.sh" "$wrapper_dir/creds.example" \
        "$root/provisioning/current.json" \
        "$root/publisher-state/deploy/publisher.kernel.lock"
    chmod 700 "$provisioner"
    FIXTURE_INSTALLER="$wrapper_dir/install.sh"
    FIXTURE_WRAPPER="$wrapper_dir/agent-bridge-wrapper.sh"
}

missing_receipt_root="$TEST_ROOT/missing-provisioning-receipt"
mkdir -p "$missing_receipt_root"
prepare_root "$missing_receipt_root"
rm "$missing_receipt_root/provisioning/current.json"
set +e
missing_receipt_output="$(AGENT_BRIDGE_DEPLOY_ROOT="$missing_receipt_root" \
    /bin/bash "$FIXTURE_INSTALLER" --dry-run 2>&1)"
missing_receipt_status=$?
set -e
[ "$missing_receipt_status" -ne 0 ] || fail "installer accepted a missing provisioning receipt"
case "$missing_receipt_output" in *"provisioning receipt verification failed"*) ;; *)
    fail "missing provisioning receipt reason absent" ;;
esac
[ ! -e "$missing_receipt_root/bin" ] ||
    fail "missing provisioning receipt reached wrapper mutation"

wrong_root="$TEST_ROOT/wrong-source"
mkdir -p "$wrong_root"
chmod 700 "$wrong_root"
set +e
wrong_output="$(AGENT_BRIDGE_DEPLOY_ROOT="$wrong_root" \
    /bin/bash "$SOURCE_INSTALLER" --dry-run 2>&1)"
wrong_status=$?
set -e
[ "$wrong_status" -ne 0 ] || fail "installer accepted a replaceable source checkout"
case "$wrong_output" in *"fixed trusted checkout"*) ;; *) fail "wrong-source reason missing" ;; esac
[ ! -e "$wrong_root/bin" ] || fail "wrong-source rejection mutated the install root"

wide_root="$TEST_ROOT/wide-source"
mkdir -p "$wide_root"
prepare_root "$wide_root"
chmod 755 "$wide_root/source/agent-bridge/scripts/wrapper"
set +e
wide_output="$(AGENT_BRIDGE_DEPLOY_ROOT="$wide_root" \
    /bin/bash "$FIXTURE_INSTALLER" --dry-run 2>&1)"
wide_status=$?
set -e
[ "$wide_status" -ne 0 ] || fail "installer accepted widened source custody"
case "$wide_output" in *"trusted wrapper source directory mode must be exact 0700"*) ;; *)
    fail "widened-source reason missing" ;;
esac
[ ! -e "$wide_root/bin" ] || fail "widened-source rejection mutated the install root"

alias_root="$TEST_ROOT/source-alias"
mkdir -p "$alias_root"
prepare_root "$alias_root"
alias_installer="$(dirname "$FIXTURE_INSTALLER")/install-alias.sh"
cp "$FIXTURE_INSTALLER" "$alias_installer"
chmod 600 "$alias_installer"
set +e
alias_output="$(AGENT_BRIDGE_DEPLOY_ROOT="$alias_root" \
    /bin/bash "$alias_installer" --dry-run 2>&1)"
alias_status=$?
set -e
[ "$alias_status" -ne 0 ] || fail "installer accepted a same-directory source alias"
case "$alias_output" in *"exact trusted installer path"*) ;; *)
    fail "same-directory installer alias reason missing" ;;
esac
[ ! -e "$alias_root/bin" ] ||
    fail "same-directory installer alias mutated the deployment root"

for unsafe_kind in fifo directory; do
    unsafe_root="$TEST_ROOT/unsafe-existing-$unsafe_kind"
    mkdir -p "$unsafe_root"
    prepare_root "$unsafe_root"
    mkdir -m 700 "$unsafe_root/bin"
    if [ "$unsafe_kind" = fifo ]; then
        mkfifo "$unsafe_root/bin/agent-bridge"
    else
        mkdir "$unsafe_root/bin/agent-bridge"
    fi
    chmod 755 "$unsafe_root/bin/agent-bridge"
    set +e
    unsafe_output="$(AGENT_BRIDGE_DEPLOY_ROOT="$unsafe_root" \
        /bin/bash "$FIXTURE_INSTALLER" 2>&1)"
    unsafe_status=$?
    set -e
    [ "$unsafe_status" -ne 0 ] || fail "installer accepted an existing $unsafe_kind"
    case "$unsafe_output" in *"must be a physical regular file"*) ;; *)
        fail "existing $unsafe_kind rejection reason missing" ;;
    esac
    [ ! -e "$unsafe_root/bin/agent-bridge.real" ] ||
        fail "existing $unsafe_kind was moved into real-binary custody"
done

text_root="$TEST_ROOT/unsafe-existing-text"
mkdir -p "$text_root"
prepare_root "$text_root"
mkdir -m 700 "$text_root/bin"
printf '%s\n' 'not a wrapper or native binary' > "$text_root/bin/agent-bridge"
chmod 755 "$text_root/bin/agent-bridge"
set +e
text_output="$(AGENT_BRIDGE_DEPLOY_ROOT="$text_root" \
    /bin/bash "$FIXTURE_INSTALLER" 2>&1)"
text_status=$?
set -e
[ "$text_status" -ne 0 ] || fail "installer accepted a non-native text file"
case "$text_output" in *"neither our wrapper nor a native executable"*) ;; *)
    fail "non-native text rejection reason missing" ;;
esac
[ ! -e "$text_root/bin/agent-bridge.real" ] ||
    fail "non-native text file was moved into real-binary custody"

install_root="$TEST_ROOT/positive"
mkdir -p "$install_root"
prepare_root "$install_root"
before="$(find "$install_root" -mindepth 1 -printf '%P %m\n' | sort)"
dry_output="$(AGENT_BRIDGE_DEPLOY_ROOT="$install_root" \
    /bin/bash "$FIXTURE_INSTALLER" --dry-run)"
[ "$(find "$install_root" -mindepth 1 -printf '%P %m\n' | sort)" = "$before" ] ||
    fail "wrapper dry-run changed filesystem state"
case "$dry_output" in *"Dry"*|*"dry-run"*) ;; *) fail "wrapper dry-run evidence missing" ;; esac

# Production installation must not require or derive trust from a caller HOME.
env -i PATH=/usr/bin:/bin \
    AGENT_BRIDGE_DEPLOY_ROOT="$install_root" \
    /bin/bash "$FIXTURE_INSTALLER" >/dev/null
installed="$install_root/bin/agent-bridge"
[ -f "$installed" ] && [ ! -L "$installed" ] || fail "wrapper was not installed physically"
[ "$(owner_of "$install_root/bin")" = "$(id -u)" ] && \
    [ "$(mode_of "$install_root/bin")" = 700 ] || fail "install bin trust boundary is wrong"
[ "$(owner_of "$installed")" = "$(id -u)" ] && \
    [ "$(mode_of "$installed")" = 755 ] || fail "installed wrapper owner/mode is wrong"
cmp -s "$FIXTURE_WRAPPER" "$installed" || fail "installed wrapper content differs from source"
[ "$(find "$install_root/bin" -maxdepth 1 -name '.agent-bridge.wrapper-stage.*' -print -quit)" = "" ] ||
    fail "wrapper install left a staging file"
publisher_lock="$install_root/publisher-state/deploy/publisher.kernel.lock"
[ -f "$publisher_lock" ] && [ ! -L "$publisher_lock" ] ||
    fail "wrapper install did not establish a physical shared publisher mutex"
[ "$(owner_of "$publisher_lock")" = "$(id -u)" ] && \
    [ "$(mode_of "$publisher_lock")" = 600 ] || fail "shared publisher mutex owner/mode is wrong"

# A concurrent publisher/binder owns the same inode. The wrapper installer
# must fail before even an idempotent atomic replacement changes the wrapper
# inode, proving the gate covers the mutation rather than only its content.
installed_inode="$(inode_of "$installed")"
exec 8>>"$publisher_lock"
/usr/bin/flock -n 8 || fail "test could not acquire shared publisher mutex"
set +e
locked_output="$(env -i PATH=/usr/bin:/bin \
    AGENT_BRIDGE_DEPLOY_ROOT="$install_root" \
    /bin/bash "$FIXTURE_INSTALLER" 2>&1)"
locked_status=$?
set -e
/usr/bin/flock -u 8
exec 8>&-
[ "$locked_status" -ne 0 ] || fail "wrapper installer ignored a live publisher mutex owner"
case "$locked_output" in *"owns the publisher kernel mutex"*) ;; *)
    fail "publisher mutex conflict reason missing" ;;
esac
[ "$(inode_of "$installed")" = "$installed_inode" ] ||
    fail "publisher mutex conflict replaced the wrapper"

printf '%s\n' wrapper-trusted-install-ok
