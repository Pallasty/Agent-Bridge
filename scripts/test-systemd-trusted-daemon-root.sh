#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALLER="$SCRIPT_DIR/systemd/install-trusted-daemon-root.sh"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ab-systemd-bind-test.XXXXXX")"
TEST_TEMP_BASE="$(cd -P "${TMPDIR:-/tmp}" && pwd -P)"
BIND_TEST_ROOTS=()
EXTRA_TEST_ROOTS=()
cleanup() {
    local root
    rm -rf "$TEST_ROOT"
    for root in "${EXTRA_TEST_ROOTS[@]}"; do
        case "$root" in
            "$TEST_ROOT"-*) rm -rf "$root" ;;
        esac
    done
    for root in "${BIND_TEST_ROOTS[@]}"; do
        case "$root" in
            "$TEST_TEMP_BASE"/ab-systemd-bind-test.*) rm -rf "$root" ;;
        esac
    done
}
trap cleanup EXIT
chmod 700 "$TEST_ROOT"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

set +e
missing_root_output="$(/usr/bin/env -u AGENT_BRIDGE_DEPLOY_ROOT \
    -u AGENT_BRIDGE_SYSTEMD_BIND_TEST_MODE \
    -u AGENT_BRIDGE_SYSTEMD_BIND_TEST_ROOT \
    HOME="$TEST_ROOT" \
    "$INSTALLER" --dry-run 2>&1)"
missing_root_status=$?
set -e
[ "$missing_root_status" -ne 0 ] || fail "systemd installer inferred deployment root from HOME"
case "$missing_root_output" in *"AGENT_BRIDGE_DEPLOY_ROOT is required"*) ;; *)
    fail "missing explicit deployment-root rejection reason absent" ;;
esac
[ "$(find "$TEST_ROOT" -mindepth 1 -print -quit)" = "" ] ||
    fail "missing deployment-root request caused a mutation"

cp /usr/bin/true "$TEST_ROOT/fake-systemctl"
chmod 755 "$TEST_ROOT/fake-systemctl"
dry_before="$(find "$TEST_ROOT" -mindepth 1 -printf '%P %m\n' | sort)"
output="$(HOME="$TEST_ROOT/home-not-used" AGENT_BRIDGE_DEPLOY_ROOT="$TEST_ROOT" \
    AGENT_BRIDGE_SYSTEMD_BIND_TEST_MODE=1 \
    AGENT_BRIDGE_SYSTEMD_BIND_TEST_ROOT="$TEST_ROOT" \
    "$INSTALLER" --dry-run)"

[ "$(printf '%s\n' "$output" | grep -c '^--- agent-bridge-.*\.service (complete current-boot replacement)$')" = 3 ] ||
    fail "dry-run did not render exactly three complete runtime units"
[ "$(printf '%s\n' "$output" | grep -c '^\[Unit\]$')" = 3 ] &&
    [ "$(printf '%s\n' "$output" | grep -c '^\[Service\]$')" = 3 ] &&
    [ "$(printf '%s\n' "$output" | grep -c '^\[Install\]$')" = 3 ] ||
    fail "dry-run omitted a complete unit section"
[ "$(printf '%s\n' "$output" | grep -c "^Environment=AGENT_BRIDGE_CGROUP_RECEIPT_DIR=$TEST_ROOT/runtime-state/workload-receipts$")" = 3 ] ||
    fail "receipt root was not pinned for all services"
[ "$(printf '%s\n' "$output" | grep -c "^Environment=AGENT_BRIDGE_CGROUP_TRANSIENT_DIR=$TEST_ROOT/runtime-state/workload-tmp$")" = 3 ] ||
    fail "transient cgroup state root was not pinned for all services"
[ "$(printf '%s\n' "$output" | grep -c "^Environment=AGENT_BRIDGE_STATE_DIR=$TEST_ROOT/runtime-state$")" = 3 ] ||
    fail "writable runtime state was not separated for all services"
[ "$(printf '%s\n' "$output" | grep -c "^Environment=AGENT_BRIDGE_REAL_BIN=$TEST_ROOT/bin/agent-bridge.real$")" = 3 ] ||
    fail "real binary was not pinned for all services"
[ "$(printf '%s\n' "$output" | grep -c "^Environment=AGENT_BRIDGE_MACHINE_ENV=$TEST_ROOT/config/agent-bridge/machine.env$")" = 3 ] ||
    fail "safe machine environment was not pinned for all services"
[ "$(printf '%s\n' "$output" | grep -c "^Environment=PATH=$TEST_ROOT/bin:/usr/bin:/bin$")" = 3 ] ||
    fail "minimal trusted PATH was not pinned for all services"
for runtime_environment in \
    "HOME=$TEST_ROOT/runtime-state/home" \
    "XDG_CONFIG_HOME=$TEST_ROOT/config" \
    "XDG_DATA_HOME=$TEST_ROOT/runtime-state/data" \
    "XDG_CACHE_HOME=$TEST_ROOT/runtime-state/cache" \
    "XDG_STATE_HOME=$TEST_ROOT/runtime-state/xdg-state" \
    "TMPDIR=$TEST_ROOT/runtime-state/tmp" \
    "XDG_RUNTIME_DIR=$TEST_ROOT/runtime" \
    "DBUS_SESSION_BUS_ADDRESS=unix:path=$TEST_ROOT/runtime/bus" \
    "LANG=C.UTF-8" \
    "USER=$(id -un)" \
    "LOGNAME=$(id -un)"
do
    [ "$(printf '%s\n' "$output" | grep -c "^Environment=$runtime_environment$")" = 3 ] ||
        fail "trusted minimal runtime environment omitted $runtime_environment"
done
[ "$(printf '%s\n' "$output" | grep -c "^WorkingDirectory=$TEST_ROOT$")" = 3 ] ||
    fail "safe WorkingDirectory was not pinned for all services"
[ "$(printf '%s\n' "$output" | grep -c '^ExecStart=')" = 3 ] ||
    fail "complete units contain an extra or missing ExecStart"
[ "$(printf '%s\n' "$output" | grep -c '^DefaultDependencies=yes$')" = 3 ] &&
    [ "$(printf '%s\n' "$output" | grep -c '^Slice=app\.slice$')" = 3 ] ||
    fail "complete units did not preserve the normal user-service dependency baseline"
for hardening_line in \
    UMask=0077 \
    NoNewPrivileges=yes \
    ProtectSystem=strict \
    PrivateTmp=yes \
    "InaccessiblePaths=/home /root" \
    "ReadOnlyPaths=$TEST_ROOT $TEST_ROOT/runtime" \
    "ReadWritePaths=$TEST_ROOT/runtime-state" \
    RestrictSUIDSGID=yes \
    LockPersonality=yes \
    ProtectKernelTunables=yes \
    ProtectKernelModules=yes \
    ProtectControlGroups=yes \
    CapabilityBoundingSet= \
    AmbientCapabilities=
do
    [ "$(printf '%s\n' "$output" | grep -cxF "$hardening_line")" = 3 ] ||
        fail "complete units omitted exact hardening: $hardening_line"
done
[ "$(printf '%s\n' "$output" | grep -c '^UnsetEnvironment=')" = 3 ] ||
    fail "complete units omitted the loader/shell environment denylist"
for dangerous_env in LD_PRELOAD LD_LIBRARY_PATH LD_AUDIT BASH_ENV ENV PYTHONPATH \
    NODE_OPTIONS RUSTC_WRAPPER
do
    [ "$(printf '%s\n' "$output" | grep -c "^UnsetEnvironment=.*\\<$dangerous_env\\>")" = 3 ] ||
        fail "UnsetEnvironment omitted $dangerous_env"
done
for command in \
    "$TEST_ROOT/bin/agent-bridge daemon" \
    "$TEST_ROOT/bin/agent-bridge daemon-http --listen 0.0.0.0:7878" \
    "$TEST_ROOT/bin/agent-bridge palace serve --port 7979"
do
    case "$output" in *"ExecStart=/usr/bin/env -i "*" $command"*) ;; *)
        fail "missing sealed env -i ExecStart: $command" ;;
    esac
done
case "$output" in
    *"$TEST_ROOT/home-not-used"*|*"EnvironmentFile="*|*"ExecCondition="*|*"ExecStartPre="*|*"ExecStartPost="*|*"ExecReload="*|*"ExecStop="*|*"ExecStopPost="*)
        fail "complete unit retained a HOME path or inherited execution hook"
        ;;
esac
printf '%s\n' "$output" | grep -qxF 'Dry run only; no unit or service state was changed.' ||
    fail "dry-run completion marker missing"
[ "$(find "$TEST_ROOT" -mindepth 1 -printf '%P %m\n' | sort)" = "$dry_before" ] ||
    fail "dry-run mutated the trusted deployment root"
rm "$TEST_ROOT/fake-systemctl"

# An authoritative install may only run from the publisher-installed safe
# clone beneath the deployment root. A development-worktree invocation must
# fail before it can inspect or mutate user-manager runtime state.
set +e
unsafe_source_output="$(AGENT_BRIDGE_DEPLOY_ROOT="$TEST_ROOT" \
    AGENT_BRIDGE_SYSTEMD_BIND_TEST_MODE=0 \
    "$INSTALLER" --install 2>&1)"
unsafe_source_status=$?
set -e
[ "$unsafe_source_status" -ne 0 ] || fail "production install accepted an unsafe source checkout"
case "$unsafe_source_output" in *"must run from the published safe clone"*) ;; *)
    fail "unsafe installer source rejection reason missing" ;;
esac
[ "$(find "$TEST_ROOT" -mindepth 1 -print -quit)" = "" ] ||
    fail "unsafe installer source caused a mutation before rejection"

unsafe="$TEST_ROOT-unsafe"
EXTRA_TEST_ROOTS+=("$unsafe")
mkdir -m 777 "$unsafe"
set +e
unsafe_output="$(AGENT_BRIDGE_DEPLOY_ROOT="$unsafe" "$INSTALLER" --dry-run 2>&1)"
unsafe_status=$?
set -e
[ "$unsafe_status" -ne 0 ] || fail "world-writable deployment root was accepted"
case "$unsafe_output" in *"group/other writable"*|*"mode must be exact 0700"*) ;; *)
    fail "unsafe-root rejection reason missing" ;;
esac
rmdir "$unsafe"

for root_mode in 755 750; do
    broad="$TEST_ROOT-mode-$root_mode"
    EXTRA_TEST_ROOTS+=("$broad")
    mkdir -m "$root_mode" "$broad"
    set +e
    broad_output="$(AGENT_BRIDGE_DEPLOY_ROOT="$broad" "$INSTALLER" --dry-run 2>&1)"
    broad_status=$?
    set -e
    [ "$broad_status" -ne 0 ] || fail "systemd installer accepted deployment root mode $root_mode"
    case "$broad_output" in *"mode"*"700"*|*"mode"*"0700"*) ;; *)
        fail "systemd root mode $root_mode rejection reason missing" ;;
    esac
    [ "$(find "$broad" -mindepth 1 -print -quit)" = "" ] ||
        fail "systemd root mode $root_mode caused a mutation before rejection"
    rmdir "$broad"
done

link="$TEST_ROOT-link"
EXTRA_TEST_ROOTS+=("$link")
ln -s "$TEST_ROOT" "$link"
set +e
link_output="$(AGENT_BRIDGE_DEPLOY_ROOT="$link" "$INSTALLER" --dry-run 2>&1)"
link_status=$?
set -e
[ "$link_status" -ne 0 ] || fail "symlink deployment root was accepted"
case "$link_output" in *"pre-existing physical directory"*) ;; *)
    fail "symlink-root rejection reason missing" ;;
esac
rm "$link"

injected="$TEST_ROOT-bad:specifier"
EXTRA_TEST_ROOTS+=("$injected")
mkdir -m 700 "$injected"
set +e
injected_output="$(AGENT_BRIDGE_DEPLOY_ROOT="$injected" "$INSTALLER" --dry-run 2>&1)"
injected_status=$?
set -e
[ "$injected_status" -ne 0 ] || fail "systemd-significant deployment-root characters were accepted"
case "$injected_output" in *"unsupported character"*) ;; *)
    fail "path-injection rejection reason missing" ;;
esac
rmdir "$injected"

RUNTIME_ASSET_FILES=(
    app_control.py
    app-control-recovery-candidates.py
    app-control-recovery-authorization.py
    app-control-recovery-authorization-request.py
    app-control-recovery-signer-status.py
    app-control-mobile-recovery-signer.py
    app-control-recovery-hint-dedupe.py
    desktop_action.py
    desktop_confirm_store.py
    desktop_grant.py
    desktop_invoke.py
    desktop_snapshot.py
    desktop_steer.py
    desktop_verify.py
    macos_ax_focus_window.swift
    macos_ax_native_probe.swift
    macos_ax_probe.py
    macos_ax_verify.py
    macos_ax_watch.py
    vision_grounding_ocr.py
)
AUDIO_ADAPTER_COMPANION_FILES=(
    omnivoice_mac_remote_synth.py
    omnivoice_onnx_bundle_synth.py
    omnivoice_onnx_official_decode.py
    omnivoice_tts_synth.py
    qwen3_lan_remote_synth.py
    qwen3_tts_rust_gate.py
    qwen3_tts_synth.py
    tts_canary_router.py
)
AUDIO_POLICY_FILES=(
    config/omnivoice-canary.json
    docs/reports/tts-comparison/human-review-decision-owner-2026-08-15.json
)

make_install_fixture() {
    local root="$1" config_parent_mode="$2" machine_mode="$3" runtime_asset
    local audio_companion audio_policy audio_policy_path
    mkdir -p "$root/bin" "$root/share/ab-tts" \
        "$root/share/config" "$root/share/docs/reports/tts-comparison" \
        "$root/lib/agent-bridge/scripts" "$root/config/agent-bridge" "$root/home" \
        "$root/publisher-state/migrations" \
        "$root/runtime-state/workload-receipts" "$root/runtime-state/home" \
        "$root/runtime-state/workload-tmp" \
        "$root/runtime-state/cache" "$root/runtime-state/data" \
        "$root/runtime-state/xdg-state" "$root/runtime-state/tmp"
    chmod 700 "$root" "$root/bin" "$root/share" "$root/share/ab-tts" \
        "$root/share/config" "$root/share/docs" "$root/share/docs/reports" \
        "$root/share/docs/reports/tts-comparison" \
        "$root/lib" "$root/lib/agent-bridge" "$root/lib/agent-bridge/scripts" \
        "$root/config" "$root/home" "$root/publisher-state" \
        "$root/publisher-state/migrations" "$root/runtime-state" \
        "$root/runtime-state/workload-receipts" "$root/runtime-state/home" \
        "$root/runtime-state/workload-tmp" \
        "$root/runtime-state/cache" "$root/runtime-state/data" \
        "$root/runtime-state/xdg-state" "$root/runtime-state/tmp"
    chmod "$config_parent_mode" "$root/config/agent-bridge"
    printf '%s\n' fixture-valid > "$root/publisher-state/migrations/current.json"
    chmod 600 "$root/publisher-state/migrations/current.json"
cat > "$root/fake-migration-verify" <<'FAKE_MIGRATION_VERIFY'
#!/bin/bash
set -euo pipefail
[ "$#" -eq 3 ] && [ "$1" = verify ] && [ "$2" = --deploy-root ] || exit 64
root="$3"
receipt="$(cat "$root/publisher-state/migrations/current.json")"
case "$receipt" in
    fixture-valid) fail_on=0 ;;
    fixture-fail-on-second) fail_on=2 ;;
    fixture-fail-on-third) fail_on=3 ;;
    *) exit 65 ;;
esac
count_file="$root/migration-verify.count"
if [ -f "$count_file" ]; then count="$(cat "$count_file")"; else count=0; fi
count=$((count + 1))
printf '%s\n' "$count" > "$count_file"
chmod 600 "$count_file"
[ "$count" -ne "$fail_on" ] || exit 66
printf '%s\n' '{"command":"verify","receipt_digest":"0000000000000000000000000000000000000000000000000000000000000000","schema":"agent_bridge.trusted_runtime_state_migration_result.v1","status":"verified"}'
FAKE_MIGRATION_VERIFY
    chmod 755 "$root/fake-migration-verify"
    cp /usr/bin/true "$root/bin/agent-bridge"
    cp /usr/bin/true "$root/bin/agent-bridge.real"
    cp /usr/bin/true "$root/share/ab-tts/audio_embody.py"
    chmod 755 "$root/bin/agent-bridge" "$root/bin/agent-bridge.real" \
        "$root/share/ab-tts/audio_embody.py"
    for audio_companion in "${AUDIO_ADAPTER_COMPANION_FILES[@]}"; do
        cp /usr/bin/true "$root/share/ab-tts/$audio_companion"
        chmod 755 "$root/share/ab-tts/$audio_companion"
    done
    for audio_policy in "${AUDIO_POLICY_FILES[@]}"; do
        audio_policy_path="$root/share/$audio_policy"
        printf '%s\n' '{}' > "$audio_policy_path"
        chmod 644 "$audio_policy_path"
    done
    for runtime_asset in "${RUNTIME_ASSET_FILES[@]}"; do
        cp /usr/bin/true "$root/lib/agent-bridge/scripts/$runtime_asset"
        chmod 755 "$root/lib/agent-bridge/scripts/$runtime_asset"
    done
    printf '%s\n' \
        '# Strict machine-local literals; this file is never evaluated by the installer.' \
        '  export AB_SUBSTRATE_PROJECTION=bucket_pool  ' \
        > "$root/config/agent-bridge/machine.env"
    chmod "$machine_mode" "$root/config/agent-bridge/machine.env"
}

make_source_authority_fixture() {
    local root repo script migration candidate binary_sha binary_inode pending
    root="$(mktemp -d "$TEST_ROOT-authority.XXXXXX")"
    EXTRA_TEST_ROOTS+=("$root")
    chmod 700 "$root"
    repo="$root/source/agent-bridge"
    script="$repo/scripts/systemd/install-trusted-daemon-root.sh"
    migration="$repo/scripts/migrate-trusted-runtime-state.py"
    mkdir -p "$repo/scripts/systemd" "$root/bin" "$root/publisher-state/deploy"
    chmod 700 "$root/source" "$repo" "$repo/scripts" "$repo/scripts/systemd" \
        "$root/bin" "$root/publisher-state" "$root/publisher-state/deploy"
    cp "$INSTALLER" "$script"
    cp "$SCRIPT_DIR/migrate-trusted-runtime-state.py" "$migration"
    chmod 700 "$script" "$migration"
    /usr/bin/env -i HOME="$root" LANG=C PATH=/usr/bin:/bin \
        /usr/bin/git -C "$repo" init -q
    /usr/bin/env -i HOME="$root" LANG=C PATH=/usr/bin:/bin \
        /usr/bin/git -C "$repo" config user.name systemd-authority-test
    /usr/bin/env -i HOME="$root" LANG=C PATH=/usr/bin:/bin \
        /usr/bin/git -C "$repo" config user.email systemd-authority-test@example.invalid
    /usr/bin/env -i HOME="$root" LANG=C PATH=/usr/bin:/bin \
        /usr/bin/git -C "$repo" add scripts/systemd/install-trusted-daemon-root.sh \
            scripts/migrate-trusted-runtime-state.py
    /usr/bin/env -i HOME="$root" LANG=C PATH=/usr/bin:/bin \
        /usr/bin/git -C "$repo" -c commit.gpgsign=false commit -q -m trusted-installer
    candidate="$(/usr/bin/env -i HOME="$root" LANG=C PATH=/usr/bin:/bin \
        /usr/bin/git -C "$repo" rev-parse HEAD)"
    /usr/bin/env -i HOME="$root" LANG=C PATH=/usr/bin:/bin \
        /usr/bin/git -C "$repo" remote add gitlab git@gitlab.com:pallasting/agent-bridge.git
    /usr/bin/env -i HOME="$root" LANG=C PATH=/usr/bin:/bin \
        /usr/bin/git -C "$repo" update-ref refs/remotes/gitlab/master "$candidate"
    chmod 700 "$repo/.git"
    chmod 600 "$repo/.git/config"
    cp /usr/bin/true "$root/bin/agent-bridge.real"
    chmod 755 "$root/bin/agent-bridge.real"
    : > "$root/publisher-state/deploy/publisher.kernel.lock"
    chmod 600 "$root/publisher-state/deploy/publisher.kernel.lock"
    binary_sha="$(sha256sum "$root/bin/agent-bridge.real" | awk '{ print $1 }')"
    binary_inode="$(stat -c %i "$root/bin/agent-bridge.real")"
    pending="$root/publisher-state/deploy/pending-admission.meta"
    {
        printf 'schema=%s\n' agent_bridge.publisher_pending_admission.v0
        printf 'lease_id=%s\n' systemd-authority-test
        printf 'challenge=%064d\n' 0
        printf 'real_path=%s\n' "$root/bin/agent-bridge.real"
        printf 'shared_targets=%s\n' "$root/bin/agent-bridge.real|$root/share/ab-tts/audio_embody.py|$root/lib/agent-bridge/scripts|$root/bin/agent-bridge"
        printf 'candidate_commit=%s\n' "$candidate"
        printf 'installed_binary_sha256=%s\n' "$binary_sha"
        printf 'installed_binary_inode=%s\n' "$binary_inode"
        printf 'installed_binary_mode=%s\n' 755
        printf 'installed_assets_sha256=%064d\n' 0
        printf 'installed_at=%s\n' 2026-08-28T00:00:00Z
        printf 'fresh_mcp=%s\n' unverified
        printf 'force_reinstall=%s\n' 0
        printf 'force_reason=%s\n' ''
    } > "$pending"
    chmod 600 "$pending"
    AUTHORITY_ROOT="$root"
    AUTHORITY_REPO="$repo"
    AUTHORITY_SCRIPT="$script"
    AUTHORITY_MIGRATION="$migration"
    AUTHORITY_PENDING="$pending"
    AUTHORITY_CANDIDATE="$candidate"
}

run_authority_install() {
    local root="$1" script="$2"
    /usr/bin/env \
        -u XDG_CONFIG_HOME \
        -u XDG_DATA_HOME \
        -u XDG_CONFIG_DIRS \
        -u XDG_DATA_DIRS \
        -u SYSTEMD_UNIT_PATH \
        AGENT_BRIDGE_DEPLOY_ROOT="$root" \
        "$script" --install
}

# --install validates every credential-bearing path before contacting the user
# systemd manager. Point DBus/runtime at absent test-only sockets as a final
# safety net: if validation is accidentally skipped, the resulting systemctl
# error must not satisfy the expected local mode diagnostic.
bad_config_parent="$TEST_ROOT-config-parent"
EXTRA_TEST_ROOTS+=("$bad_config_parent")
mkdir -m 700 "$bad_config_parent"
make_install_fixture "$bad_config_parent" 755 600
set +e
config_parent_output="$(HOME="$bad_config_parent/home" \
    XDG_RUNTIME_DIR="$bad_config_parent/no-runtime" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=$bad_config_parent/no-bus" \
    AGENT_BRIDGE_DEPLOY_ROOT="$bad_config_parent" \
    AGENT_BRIDGE_SYSTEMD_BIND_TEST_MODE=1 \
    AGENT_BRIDGE_SYSTEMD_BIND_TEST_ROOT="$bad_config_parent" \
    "$INSTALLER" --install 2>&1)"
config_parent_status=$?
set -e
[ "$config_parent_status" -ne 0 ] || fail "systemd installer accepted mode-0755 config parent"
case "$config_parent_output" in *"config"*"mode"*"700"*|*"config"*"mode"*"0700"*) ;; *)
    fail "config-parent mode rejection reason missing" ;;
esac
rm -rf "$bad_config_parent"

bad_machine_mode="$TEST_ROOT-machine-mode"
EXTRA_TEST_ROOTS+=("$bad_machine_mode")
mkdir -m 700 "$bad_machine_mode"
make_install_fixture "$bad_machine_mode" 700 644
set +e
machine_mode_output="$(HOME="$bad_machine_mode/home" \
    XDG_RUNTIME_DIR="$bad_machine_mode/no-runtime" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=$bad_machine_mode/no-bus" \
    AGENT_BRIDGE_DEPLOY_ROOT="$bad_machine_mode" \
    AGENT_BRIDGE_SYSTEMD_BIND_TEST_MODE=1 \
    AGENT_BRIDGE_SYSTEMD_BIND_TEST_ROOT="$bad_machine_mode" \
    "$INSTALLER" --install 2>&1)"
machine_mode_status=$?
set -e
[ "$machine_mode_status" -ne 0 ] || fail "systemd installer accepted mode-0644 machine environment"
case "$machine_mode_output" in *"machine environment"*"0600"*) ;; *)
    fail "machine-environment mode rejection reason missing" ;;
esac
rm -rf "$bad_machine_mode"

# Production source authority binds the executable installer to the exact
# publisher candidate and installed binary before any runtime or manager
# interaction. First prove a valid authority fixture advances to the later
# installed-asset gate, then perturb each authority input independently.
make_source_authority_fixture
authority_positive_root="$AUTHORITY_ROOT"
set +e
authority_positive_output="$(run_authority_install "$AUTHORITY_ROOT" "$AUTHORITY_SCRIPT" 2>&1)"
authority_positive_status=$?
set -e
[ "$authority_positive_status" -ne 0 ] || fail "incomplete source-authority fixture unexpectedly installed"
case "$authority_positive_output" in *"trusted audio adapter path component must be a physical directory"*) ;; *)
    fail "valid publisher/source authority did not reach the installed-asset gate" ;;
esac
[ ! -e "$authority_positive_root/runtime" ] || fail "authority fixture reached user runtime state"

make_source_authority_fixture
pending_mode_root="$AUTHORITY_ROOT"
chmod 644 "$AUTHORITY_PENDING"
set +e
pending_mode_output="$(run_authority_install "$AUTHORITY_ROOT" "$AUTHORITY_SCRIPT" 2>&1)"
pending_mode_status=$?
set -e
[ "$pending_mode_status" -ne 0 ] || fail "source authority accepted mode-0644 pending admission"
case "$pending_mode_output" in *"publisher pending admission mode must be exact 0600"*) ;; *)
    fail "pending-admission mode rejection reason missing" ;;
esac
[ ! -e "$pending_mode_root/runtime" ] || fail "bad pending mode reached user runtime state"

make_source_authority_fixture
pending_link_root="$AUTHORITY_ROOT"
mv "$AUTHORITY_PENDING" "$AUTHORITY_PENDING.target"
ln -s "$AUTHORITY_PENDING.target" "$AUTHORITY_PENDING"
set +e
pending_link_output="$(run_authority_install "$AUTHORITY_ROOT" "$AUTHORITY_SCRIPT" 2>&1)"
pending_link_status=$?
set -e
[ "$pending_link_status" -ne 0 ] || fail "source authority accepted symlink pending admission"
case "$pending_link_output" in *"publisher pending admission path must not traverse a symlink"*) ;; *)
    fail "pending-admission symlink rejection reason missing" ;;
esac
[ ! -e "$pending_link_root/runtime" ] || fail "symlink pending admission reached user runtime state"

make_source_authority_fixture
candidate_mismatch_root="$AUTHORITY_ROOT"
sed -i 's/^candidate_commit=.*/candidate_commit=0000000000000000000000000000000000000000/' \
    "$AUTHORITY_PENDING"
chmod 600 "$AUTHORITY_PENDING"
set +e
candidate_mismatch_output="$(run_authority_install "$AUTHORITY_ROOT" "$AUTHORITY_SCRIPT" 2>&1)"
candidate_mismatch_status=$?
set -e
[ "$candidate_mismatch_status" -ne 0 ] || fail "source authority accepted a candidate/HEAD mismatch"
case "$candidate_mismatch_output" in *"trusted source HEAD does not match the publisher candidate"*) ;; *)
    fail "publisher candidate mismatch rejection reason missing" ;;
esac
[ ! -e "$candidate_mismatch_root/runtime" ] || fail "candidate mismatch reached user runtime state"

make_source_authority_fixture
dirty_installer_root="$AUTHORITY_ROOT"
printf '%s\n' '# post-publisher installer drift' >> "$AUTHORITY_SCRIPT"
set +e
dirty_installer_output="$(run_authority_install "$AUTHORITY_ROOT" "$AUTHORITY_SCRIPT" 2>&1)"
dirty_installer_status=$?
set -e
[ "$dirty_installer_status" -ne 0 ] || fail "source authority accepted a dirty installer"
case "$dirty_installer_output" in *"trusted daemon installer bytes do not match the publisher candidate"*) ;; *)
    fail "dirty/stale installer rejection reason missing" ;;
esac
[ ! -e "$dirty_installer_root/runtime" ] || fail "dirty installer reached user runtime state"

make_source_authority_fixture
dirty_migration_root="$AUTHORITY_ROOT"
printf '%s\n' '# post-publisher migration-tool drift' >> "$AUTHORITY_MIGRATION"
set +e
dirty_migration_output="$(run_authority_install "$AUTHORITY_ROOT" "$AUTHORITY_SCRIPT" 2>&1)"
dirty_migration_status=$?
set -e
[ "$dirty_migration_status" -ne 0 ] || fail "source authority accepted a dirty migration tool"
case "$dirty_migration_output" in *"trusted runtime-state migration tool bytes do not match the publisher candidate"*) ;; *)
    fail "dirty/stale migration-tool rejection reason missing" ;;
esac
[ ! -e "$dirty_migration_root/runtime" ] || fail "dirty migration tool reached user runtime state"

make_source_authority_fixture
binary_drift_root="$AUTHORITY_ROOT"
printf '%s' x >> "$AUTHORITY_ROOT/bin/agent-bridge.real"
set +e
binary_drift_output="$(run_authority_install "$AUTHORITY_ROOT" "$AUTHORITY_SCRIPT" 2>&1)"
binary_drift_status=$?
set -e
[ "$binary_drift_status" -ne 0 ] || fail "source authority accepted installed-binary SHA drift"
case "$binary_drift_output" in *"publisher-installed binary SHA drifted after admission"*) ;; *)
    fail "installed-binary SHA drift rejection reason missing" ;;
esac
[ ! -e "$binary_drift_root/runtime" ] || fail "binary drift reached user runtime state"

make_source_authority_fixture
publisher_busy_root="$AUTHORITY_ROOT"
exec {publisher_busy_fd}<>"$AUTHORITY_ROOT/publisher-state/deploy/publisher.kernel.lock"
/usr/bin/flock -n "$publisher_busy_fd" || fail "test could not hold publisher kernel lock"
set +e
publisher_busy_output="$(run_authority_install "$AUTHORITY_ROOT" "$AUTHORITY_SCRIPT" 2>&1)"
publisher_busy_status=$?
set -e
exec {publisher_busy_fd}>&-
[ "$publisher_busy_status" -ne 0 ] || fail "systemd install ignored a busy publisher kernel lock"
case "$publisher_busy_output" in *"publisher kernel lock is busy; trusted binding made no changes"*) ;; *)
    fail "busy publisher lock rejection reason missing" ;;
esac
[ ! -e "$publisher_busy_root/runtime" ] || fail "busy publisher lock caused runtime mutation"

make_source_authority_fixture
publisher_lock_mode_root="$AUTHORITY_ROOT"
chmod 644 "$AUTHORITY_ROOT/publisher-state/deploy/publisher.kernel.lock"
set +e
publisher_lock_mode_output="$(run_authority_install "$AUTHORITY_ROOT" "$AUTHORITY_SCRIPT" 2>&1)"
publisher_lock_mode_status=$?
set -e
[ "$publisher_lock_mode_status" -ne 0 ] || fail "systemd install accepted mode-0644 publisher lock"
case "$publisher_lock_mode_output" in *"publisher kernel lock mode must be exact 0600"*) ;; *)
    fail "publisher-lock mode rejection reason missing" ;;
esac
[ ! -e "$publisher_lock_mode_root/runtime" ] || fail "bad publisher-lock mode caused runtime mutation"

make_source_authority_fixture
publisher_lock_link_root="$AUTHORITY_ROOT"
publisher_lock_path="$AUTHORITY_ROOT/publisher-state/deploy/publisher.kernel.lock"
mv "$publisher_lock_path" "$publisher_lock_path.target"
ln -s "$publisher_lock_path.target" "$publisher_lock_path"
set +e
publisher_lock_link_output="$(run_authority_install "$AUTHORITY_ROOT" "$AUTHORITY_SCRIPT" 2>&1)"
publisher_lock_link_status=$?
set -e
[ "$publisher_lock_link_status" -ne 0 ] || fail "systemd install accepted symlink publisher lock"
case "$publisher_lock_link_output" in *"publisher kernel lock path must not traverse a symlink"*) ;; *)
    fail "publisher-lock symlink rejection reason missing" ;;
esac
[ ! -e "$publisher_lock_link_root/runtime" ] || fail "symlink publisher lock caused runtime mutation"

make_source_authority_fixture
attributes_override_root="$AUTHORITY_ROOT"
: > "$AUTHORITY_REPO/.git/info/attributes"
chmod 600 "$AUTHORITY_REPO/.git/info/attributes"
set +e
attributes_override_output="$(run_authority_install "$AUTHORITY_ROOT" "$AUTHORITY_SCRIPT" 2>&1)"
attributes_override_status=$?
set -e
[ "$attributes_override_status" -ne 0 ] || fail "source authority accepted .git/info/attributes"
case "$attributes_override_output" in *"forbidden local object/attribute override"*) ;; *)
    fail "repository attribute override rejection reason missing" ;;
esac
[ ! -e "$attributes_override_root/runtime" ] || fail "attribute override reached user runtime state"

install_fake_systemctl() {
    local root="$1"
    cat > "$root/fake-systemctl" <<'FAKE_SYSTEMCTL'
#!/bin/bash
set -euo pipefail
PATH=/usr/bin:/bin
export PATH

fake_root="$(cd -P "$(dirname "$0")" && pwd -P)"
runtime_control="$fake_root/runtime/systemd/user.control"
log="$fake_root/systemctl.log"

[ "${1:-}" = --user ] || exit 64
shift
action="${1:-}"
shift || true

case "$action" in
    show)
        unit=""
        property=""
        for arg in "$@"; do
            case "$arg" in
                --property=*) property="${arg#--property=}" ;;
                --value) ;;
                *) [ -n "$unit" ] || unit="$arg" ;;
            esac
        done
        printf 'show\t%s\t%s\n' "${unit:-manager}" "$property" >> "$log"
        if [ -z "$unit" ] && [ "$property" = UnitPath ]; then
            cat "$fake_root/unit-paths"
            exit 0
        fi
        [ -n "$unit" ] || exit 65
        fragment="$runtime_control/$unit"
        foreign="$fake_root/foreign-dropins/$unit"
        case "$property" in
            DropInPaths)
                [ ! -f "$foreign" ] || cat "$foreign"
                ;;
            FragmentPath)
                if [ -f "$fragment" ]; then
                    printf '%s\n' "$fragment"
                else
                    printf '/usr/lib/systemd/user/%s\n' "$unit"
                fi
                ;;
            WorkingDirectory)
                sed -n 's/^WorkingDirectory=//p' "$fragment"
                ;;
            ExecStart)
                command="$(sed -n 's/^ExecStart=//p' "$fragment")"
                executable="${command%% *}"
                printf '{ path=%s ; argv[]=%s ; ignore_errors=no ; start_time=[n/a] ; stop_time=[n/a] ; pid=0 ; code=(null) ; status=0/0 }\n' \
                    "$executable" "$command"
                ;;
            Environment)
                sed -n 's/^Environment=//p' "$fragment" | paste -sd' ' -
                ;;
            UnsetEnvironment)
                sed -n 's/^UnsetEnvironment=//p' "$fragment"
                ;;
            DefaultDependencies)
                sed -n 's/^DefaultDependencies=//p' "$fragment"
                ;;
            Slice)
                sed -n 's/^Slice=//p' "$fragment"
                ;;
            UMask|NoNewPrivileges|ProtectSystem|PrivateTmp|InaccessiblePaths|ReadOnlyPaths|ReadWritePaths|RestrictSUIDSGID|LockPersonality|ProtectKernelTunables|ProtectKernelModules|ProtectControlGroups|CapabilityBoundingSet|AmbientCapabilities)
                sed -n "s/^$property=//p" "$fragment"
                ;;
            Wants|WantedBy|Requires|RequiredBy|Requisite|RequisiteOf|\
            BindsTo|BoundBy|PartOf|ConsistsOf|Upholds|UpheldBy|\
            Conflicts|ConflictedBy|OnFailure|OnFailureOf|OnSuccess|OnSuccessOf|\
            TriggeredBy|Triggers|PropagatesReloadTo|ReloadPropagatedFrom|\
            PropagatesStopTo|StopPropagatedFrom|JoinsNamespaceOf)
                dependency="$fake_root/foreign-dependencies/$unit.$property"
                if [ -f "$dependency" ]; then
                    cat "$dependency"
                else
                    case "$property" in
                        Requires) printf '%s\n' 'app.slice basic.target' ;;
                        Conflicts) printf '%s\n' shutdown.target ;;
                    esac
                fi
                ;;
            ExecCondition|ExecStartPre|ExecStartPost|ExecReload|ExecStop|ExecStopPost|EnvironmentFiles)
                printf '\n'
                ;;
            ActiveState)
                state="$fake_root/unit-states/$unit.ActiveState"
                if [ -f "$state" ]; then cat "$state"; else printf '%s\n' inactive; fi
                ;;
            SubState)
                state="$fake_root/unit-states/$unit.SubState"
                if [ -f "$state" ]; then cat "$state"; else printf '%s\n' dead; fi
                ;;
            MainPID)
                state="$fake_root/unit-states/$unit.MainPID"
                if [ -f "$state" ]; then
                    cat "$state"
                else
                    case "$unit" in *.timer) printf '\n' ;; *) printf '%s\n' 0 ;; esac
                fi
                ;;
            LoadState)
                state="$fake_root/unit-states/$unit.LoadState"
                if [ -f "$state" ]; then
                    cat "$state"
                else
                    case "$unit" in
                        agent-bridge-day2-audit.timer) printf '%s\n' not-found ;;
                        *) printf '%s\n' loaded ;;
                    esac
                fi
                ;;
            UnitFileState)
                state="$fake_root/unit-states/$unit.UnitFileState"
                if [ -f "$state" ]; then
                    cat "$state"
                else
                    case "$unit" in
                        agent-bridge-day2-audit.timer) printf '\n' ;;
                        *) printf '%s\n' disabled ;;
                    esac
                fi
                ;;
            *) exit 65 ;;
        esac
        ;;
    edit)
        printf 'edit\tunexpected\n' >> "$log"
        exit 68
        ;;
    daemon-reload)
        printf 'daemon-reload\n' >> "$log"
        reload_count="$(awk '$1 == "daemon-reload" { count += 1 } END { print count + 0 }' "$log")"
        if [ "${AGENT_BRIDGE_FAKE_SYSTEMCTL_FAIL_RELOAD_ONCE:-0}" = 1 ] &&
                [ "$reload_count" = 1 ]; then
            exit 69
        fi
        if [ "${AGENT_BRIDGE_FAKE_SYSTEMCTL_INJECT_AFTER_RELOAD:-0}" = 1 ]; then
            mkdir -p "$fake_root/foreign-dependencies"
            chmod 700 "$fake_root/foreign-dependencies"
            printf '%s\n' post-reload-injected.service > \
                "$fake_root/foreign-dependencies/agent-bridge-daemon.service.Wants"
            chmod 600 "$fake_root/foreign-dependencies/agent-bridge-daemon.service.Wants"
        fi
        if [ "${AGENT_BRIDGE_FAKE_SYSTEMCTL_TAMPER_AFTER_RELOAD:-0}" = 1 ] &&
                [ ! -e "$fake_root/tamper-after-reload.done" ]; then
            printf '%s\n' 'LoadCredential=untrusted:/untrusted' >> \
                "$runtime_control/agent-bridge-daemon.service"
            : > "$fake_root/tamper-after-reload.done"
            chmod 600 "$fake_root/tamper-after-reload.done"
        fi
        if [ "${AGENT_BRIDGE_FAKE_SYSTEMCTL_REARM_WRITER_AFTER_RELOAD:-0}" = 1 ] &&
                [ ! -e "$fake_root/rearm-after-reload.done" ]; then
            mkdir -p "$fake_root/unit-states"
            chmod 700 "$fake_root/unit-states"
            printf '%s\n' active > \
                "$fake_root/unit-states/agent-bridge-sync.timer.ActiveState"
            printf '%s\n' waiting > \
                "$fake_root/unit-states/agent-bridge-sync.timer.SubState"
            printf '%s\n' 0 > \
                "$fake_root/unit-states/agent-bridge-sync.timer.MainPID"
            chmod 600 "$fake_root/unit-states/"*
            : > "$fake_root/rearm-after-reload.done"
            chmod 600 "$fake_root/rearm-after-reload.done"
        fi
        ;;
    *) exit 67 ;;
esac
FAKE_SYSTEMCTL
    chmod 755 "$root/fake-systemctl"
}

install_fake_manager_unit_paths() {
    local root="$1"
    {
        printf '%s\n' "$root/home/.config/systemd/user.control"
        printf '%s\n' "$root/runtime/systemd/user.control"
        printf '%s\n' "$root/home/.config/systemd/user"
        printf '%s\n' "$root/home/.local/share/systemd/user"
        printf '%s\n' /etc/systemd/user
        printf '%s\n' /usr/lib/systemd/user
    } > "$root/unit-paths"
    chmod 600 "$root/unit-paths"
}

new_bind_test_root() {
    BIND_ROOT="$(mktemp -d "$TEST_TEMP_BASE/ab-systemd-bind-test.XXXXXX")"
    BIND_TEST_ROOTS+=("$BIND_ROOT")
    chmod 700 "$BIND_ROOT"
    make_install_fixture "$BIND_ROOT" 700 600
    mkdir -m 700 "$BIND_ROOT/runtime"
    /usr/bin/python3 -I - "$BIND_ROOT/runtime/bus" <<'PY'
import socket
import sys

bus = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
bus.bind(sys.argv[1])
bus.close()
PY
    install_fake_systemctl "$BIND_ROOT"
    install_fake_manager_unit_paths "$BIND_ROOT"
}

run_test_install() {
    local root="$1"
    HOME="$root/home" \
    AGENT_BRIDGE_DEPLOY_ROOT="$root" \
    AGENT_BRIDGE_SYSTEMD_BIND_TEST_MODE=1 \
    AGENT_BRIDGE_SYSTEMD_BIND_TEST_ROOT="$root" \
    AMBIENT_DANGER=must_not_cross_env_i \
    BASH_ENV=/dev/null \
    LD_PRELOAD= \
        "$INSTALLER" --install
}

fake_log_count() {
    local root="$1" action="$2"
    [ -f "$root/systemctl.log" ] || { printf '%s\n' 0; return 0; }
    awk -F '\t' -v action="$action" '$1 == action { count += 1 } END { print count + 0 }' \
        "$root/systemctl.log"
}

migration_verify_count() {
    local root="$1"
    if [ -f "$root/migration-verify.count" ]; then
        cat "$root/migration-verify.count"
    else
        printf '%s\n' 0
    fi
}

assert_no_runtime_fragments() {
    local root="$1" fragment staging
    fragment="$(find "$root/runtime/systemd/user.control" -maxdepth 1 -type f -print -quit 2>/dev/null || true)"
    [ -z "$fragment" ] || fail "failed transaction retained runtime fragment: $fragment"
    staging="$(find "$root/runtime" -maxdepth 1 -name '.agent-bridge-systemd-stage.*' -print -quit 2>/dev/null || true)"
    [ -z "$staging" ] || fail "failed transaction retained private staging: $staging"
}

assert_machine_env_rejected_before_manager() {
    local root="$1" label="$2" expected="$3" forbidden_value="${4:-}"
    local before_sha output status after_sha
    before_sha="$(sha256sum "$root/config/agent-bridge/machine.env" | awk '{ print $1 }')"
    set +e
    output="$(run_test_install "$root" 2>&1)"
    status=$?
    set -e
    [ "$status" -ne 0 ] || fail "trusted binding accepted $label machine.env"
    case "$output" in *"$expected"*) ;; *)
        fail "$label machine.env rejection reason missing" ;;
    esac
    if [ -n "$forbidden_value" ]; then
        case "$output" in *"$forbidden_value"*)
            fail "$label machine.env rejection disclosed its value" ;;
        esac
    fi
    after_sha="$(sha256sum "$root/config/agent-bridge/machine.env" | awk '{ print $1 }')"
    [ "$after_sha" = "$before_sha" ] || fail "$label rejection mutated machine.env"
    [ "$(fake_log_count "$root" show)" = 0 ] &&
        [ "$(fake_log_count "$root" daemon-reload)" = 0 ] ||
        fail "$label machine.env reached the user manager"
    assert_no_runtime_fragments "$root"
}

units=(
    agent-bridge-daemon.service
    agent-bridge-daemon-http.service
    agent-bridge-palace.service
)

# The audio adapter's executable/import closure and its review-bound policy
# files are admitted as one manifest. Missing files and mode drift fail before
# the user manager is contacted.
for audio_asset_case in companion-missing companion-mode policy-missing policy-mode; do
    new_bind_test_root
    audio_asset_root="$BIND_ROOT"
    case "$audio_asset_case" in
        companion-missing)
            /usr/bin/unlink "$audio_asset_root/share/ab-tts/qwen3_tts_synth.py"
            ;;
        companion-mode)
            chmod 700 "$audio_asset_root/share/ab-tts/qwen3_tts_synth.py"
            ;;
        policy-missing)
            /usr/bin/unlink "$audio_asset_root/share/config/omnivoice-canary.json"
            ;;
        policy-mode)
            chmod 600 "$audio_asset_root/share/config/omnivoice-canary.json"
            ;;
    esac
    set +e
    audio_asset_output="$(run_test_install "$audio_asset_root" 2>&1)"
    audio_asset_status=$?
    set -e
    [ "$audio_asset_status" -ne 0 ] || fail "install accepted $audio_asset_case"
    case "$audio_asset_output" in *"trusted audio"*) ;; *)
        fail "$audio_asset_case rejection reason missing" ;;
    esac
    [ "$(fake_log_count "$audio_asset_root" show)" = 0 ] &&
        [ "$(fake_log_count "$audio_asset_root" daemon-reload)" = 0 ] ||
        fail "$audio_asset_case reached the user manager"
    assert_no_runtime_fragments "$audio_asset_root"
done

new_bind_test_root
bad_runtime_asset_root="$BIND_ROOT"
chmod 700 "$bad_runtime_asset_root/lib/agent-bridge/scripts/desktop_action.py"
set +e
bad_runtime_asset_output="$(run_test_install "$bad_runtime_asset_root" 2>&1)"
bad_runtime_asset_status=$?
set -e
[ "$bad_runtime_asset_status" -ne 0 ] || fail "install accepted a wrong-mode runtime asset"
case "$bad_runtime_asset_output" in *"trusted runtime asset desktop_action.py mode must be exact 0755"*) ;; *)
    fail "wrong-mode runtime asset rejection reason missing" ;;
esac
[ "$(fake_log_count "$bad_runtime_asset_root" show)" = 0 ] ||
    fail "wrong-mode runtime asset reached the user manager"

new_bind_test_root
bad_credentials_root="$BIND_ROOT"
: > "$bad_credentials_root/config/agent-bridge/credentials"
chmod 644 "$bad_credentials_root/config/agent-bridge/credentials"
set +e
bad_credentials_output="$(run_test_install "$bad_credentials_root" 2>&1)"
bad_credentials_status=$?
set -e
[ "$bad_credentials_status" -ne 0 ] || fail "install accepted wrong-mode credentials"
case "$bad_credentials_output" in *"trusted credentials mode must be exact 0600"*) ;; *)
    fail "wrong-mode credentials rejection reason missing" ;;
esac
[ "$(fake_log_count "$bad_credentials_root" show)" = 0 ] ||
    fail "wrong-mode credentials reached the user manager"

# machine.env is parsed as data, never sourced. Only explicit exports of
# allowlisted plain literals are admitted. Syntax, authority, and disclosure
# failures must occur before the first user-manager query or runtime write.
for machine_env_case in \
    bare-assignment legacy-home-expansion secret-key unknown-key duplicate-key \
    command-expansion quoted-value core-state-pin legacy-app-control \
    qwen-incomplete path-symlink path-wide-parent
do
    new_bind_test_root
    machine_env_root="$BIND_ROOT"
    machine_env_file="$machine_env_root/config/agent-bridge/machine.env"
    machine_env_marker="$machine_env_root/command-substitution-must-not-run"
    forbidden_machine_value=""
    case "$machine_env_case" in
        bare-assignment)
            printf '%s\n' 'AB_SUBSTRATE_PROJECTION=bucket_pool' > "$machine_env_file"
            expected_machine_error='must be an explicit export assignment'
            ;;
        legacy-home-expansion)
            printf '%s\n' \
                'export AB_SUBSTRATE_PROJECTION=bucket_pool' \
                'export AB_TTS_KOKORO_MODEL=$HOME/dev/voice-model.onnx' \
                > "$machine_env_file"
            expected_machine_error='value for AB_TTS_KOKORO_MODEL must be a plain unquoted literal'
            forbidden_machine_value='$HOME/dev/voice-model.onnx'
            ;;
        secret-key)
            printf '%s\n' \
                'export AB_SUBSTRATE_PROJECTION=bucket_pool' \
                'export OPENAI_API_KEY=machine-env-secret-sentinel' \
                > "$machine_env_file"
            expected_machine_error='secret-like key OPENAI_API_KEY is forbidden'
            forbidden_machine_value='machine-env-secret-sentinel'
            ;;
        unknown-key)
            printf '%s\n' \
                'export AB_SUBSTRATE_PROJECTION=bucket_pool' \
                'export AB_UNLISTED_MACHINE_SWITCH=1' \
                > "$machine_env_file"
            expected_machine_error='unknown key AB_UNLISTED_MACHINE_SWITCH is forbidden'
            ;;
        duplicate-key)
            printf '%s\n' \
                'export AB_SUBSTRATE_PROJECTION=bucket_pool' \
                'export AB_SUBSTRATE_PROJECTION=bucket_pool' \
                > "$machine_env_file"
            expected_machine_error='contains duplicate key AB_SUBSTRATE_PROJECTION'
            ;;
        command-expansion)
            printf '%s\n' \
                'export AB_SUBSTRATE_PROJECTION=bucket_pool' \
                "export AGENT_BRIDGE_TOOLSET=\$(touch $machine_env_marker)" \
                > "$machine_env_file"
            expected_machine_error='value for AGENT_BRIDGE_TOOLSET must be a plain unquoted literal'
            forbidden_machine_value="$machine_env_marker"
            ;;
        quoted-value)
            printf '%s\n' \
                'export AB_SUBSTRATE_PROJECTION=bucket_pool' \
                'export AGENT_BRIDGE_TOOLSET="codex-voice"' \
                > "$machine_env_file"
            expected_machine_error='value for AGENT_BRIDGE_TOOLSET must be a plain unquoted literal'
            forbidden_machine_value='"codex-voice"'
            ;;
        core-state-pin)
            printf '%s\n' \
                'export AB_SUBSTRATE_PROJECTION=bucket_pool' \
                "export AGENT_BRIDGE_STATE_DIR=$machine_env_root/runtime-state" \
                > "$machine_env_file"
            expected_machine_error='may not override runtime pin AGENT_BRIDGE_STATE_DIR'
            forbidden_machine_value="$machine_env_root/runtime-state"
            ;;
        legacy-app-control)
            printf '%s\n' \
                'export AB_SUBSTRATE_PROJECTION=bucket_pool' \
                "export AB_APP_CONTROL_OPERATION_DIR=$machine_env_root/app_control_operations" \
                > "$machine_env_file"
            expected_machine_error='may not override runtime pin AB_APP_CONTROL_OPERATION_DIR'
            forbidden_machine_value="$machine_env_root/app_control_operations"
            ;;
        qwen-incomplete)
            printf '%s\n' \
                'export AB_SUBSTRATE_PROJECTION=bucket_pool' \
                'export AB_QWEN3_TTS_RUST_ENABLED=1' \
                > "$machine_env_file"
            expected_machine_error='enabled Qwen3 Rust requires its binary, model directory, and profile'
            ;;
        path-symlink)
            mkdir -m 700 "$machine_env_root/share/machine-models"
            : > "$machine_env_root/share/machine-models/kokoro.onnx"
            chmod 600 "$machine_env_root/share/machine-models/kokoro.onnx"
            ln -s kokoro.onnx "$machine_env_root/share/machine-models/kokoro-link.onnx"
            printf '%s\n' \
                'export AB_SUBSTRATE_PROJECTION=bucket_pool' \
                "export AB_TTS_KOKORO_MODEL=$machine_env_root/share/machine-models/kokoro-link.onnx" \
                > "$machine_env_file"
            expected_machine_error='path for AB_TTS_KOKORO_MODEL must not traverse a symlink'
            forbidden_machine_value="$machine_env_root/share/machine-models/kokoro-link.onnx"
            ;;
        path-wide-parent)
            mkdir -m 755 "$machine_env_root/share/machine-models"
            : > "$machine_env_root/share/machine-models/kokoro.onnx"
            chmod 600 "$machine_env_root/share/machine-models/kokoro.onnx"
            printf '%s\n' \
                'export AB_SUBSTRATE_PROJECTION=bucket_pool' \
                "export AB_TTS_KOKORO_MODEL=$machine_env_root/share/machine-models/kokoro.onnx" \
                > "$machine_env_file"
            expected_machine_error='path parent for AB_TTS_KOKORO_MODEL must be exact mode 0700'
            forbidden_machine_value="$machine_env_root/share/machine-models/kokoro.onnx"
            ;;
    esac
    chmod 600 "$machine_env_file"
    assert_machine_env_rejected_before_manager "$machine_env_root" \
        "$machine_env_case" "$expected_machine_error" "$forbidden_machine_value"
    [ ! -e "$machine_env_marker" ] ||
        fail "machine.env command expansion executed during $machine_env_case validation"
done

# A richer safe configuration proves that admitted scalar and path keys retain
# useful semantics without shell expansion. Every referenced asset is a
# pre-existing physical object beneath the private deployment root.
new_bind_test_root
safe_machine_root="$BIND_ROOT"
mkdir -m 700 "$safe_machine_root/share/machine-models" \
    "$safe_machine_root/share/machine-models/qwen3-rust"
: > "$safe_machine_root/share/machine-models/substrate-svd.bin"
chmod 600 "$safe_machine_root/share/machine-models/substrate-svd.bin"
cp /usr/bin/true "$safe_machine_root/share/machine-models/qwen3-tts"
chmod 755 "$safe_machine_root/share/machine-models/qwen3-tts"
printf '%s\n' \
    'export AB_SUBSTRATE_PROJECTION=svd' \
    "export AB_SUBSTRATE_SVD_PATH=$safe_machine_root/share/machine-models/substrate-svd.bin" \
    'export AGENT_BRIDGE_CONTEXT_WINDOW=1000000' \
    'export AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS=organic' \
    'export AGENT_BRIDGE_TOOLSET=codex-voice' \
    'export AGENT_BRIDGE_EMBED_REMOTE_URL=http://127.0.0.1:7878/embed' \
    'export AB_QWEN3_TTS_RUST_ENABLED=1' \
    "export AB_QWEN3_TTS_RUST_BIN=$safe_machine_root/share/machine-models/qwen3-tts" \
    "export AB_QWEN3_TTS_RUST_MODEL_DIR=$safe_machine_root/share/machine-models/qwen3-rust" \
    'export AB_QWEN3_TTS_RUST_PROFILE=0.6b-customvoice' \
    "export AB_TTS_SYNTH_BIN=$safe_machine_root/bin/agent-bridge.real" \
    "export AGENT_BRIDGE_ONNX_MODEL_DIR=$safe_machine_root/share/machine-models" \
    > "$safe_machine_root/config/agent-bridge/machine.env"
chmod 600 "$safe_machine_root/config/agent-bridge/machine.env"
# Also model already-enabled services. The trusted binder must preserve this
# effective reverse relation exactly; it must not derive one merely from the
# retained [Install] WantedBy= metadata.
mkdir -m 700 "$safe_machine_root/foreign-dependencies"
for unit in "${units[@]}"; do
    printf '%s\n' default.target > \
        "$safe_machine_root/foreign-dependencies/$unit.WantedBy"
    chmod 600 "$safe_machine_root/foreign-dependencies/$unit.WantedBy"
done
safe_machine_output="$(run_test_install "$safe_machine_root")"
printf '%s\n' "$safe_machine_output" | grep -qxF \
    'Installed and verified complete trusted current-boot units; services were not restarted.' ||
    fail "safe literal machine.env did not complete a trusted transaction"
[ "$(fake_log_count "$safe_machine_root" daemon-reload)" = 1 ] ||
    fail "safe literal machine.env reload count mismatch"

new_bind_test_root
unsafe_substrate_root="$BIND_ROOT"
printf '%s\n' \
    'export AB_SUBSTRATE_PROJECTION=svd' \
    'export AB_SUBSTRATE_SVD_PATH=/Data/CascadeProjects/AiOT/build/svd_projection_v1.bin' \
    > "$unsafe_substrate_root/config/agent-bridge/machine.env"
chmod 600 "$unsafe_substrate_root/config/agent-bridge/machine.env"
set +e
unsafe_substrate_output="$(run_test_install "$unsafe_substrate_root" 2>&1)"
unsafe_substrate_status=$?
set -e
[ "$unsafe_substrate_status" -ne 0 ] ||
    fail "install accepted a development-tree substrate SVD artifact"
case "$unsafe_substrate_output" in *"machine environment path for AB_SUBSTRATE_SVD_PATH must remain beneath the trusted deployment root"*) ;; *)
    fail "unsafe substrate SVD rejection reason missing" ;;
esac
case "$unsafe_substrate_output" in *"/Data/CascadeProjects/AiOT"*)
    fail "unsafe substrate rejection disclosed the configured path" ;;
esac
[ "$(fake_log_count "$unsafe_substrate_root" show)" = 0 ] ||
    fail "unsafe substrate SVD selection reached the user manager"

new_bind_test_root
regular_bus_root="$BIND_ROOT"
rm "$regular_bus_root/runtime/bus"
: > "$regular_bus_root/runtime/bus"
chmod 600 "$regular_bus_root/runtime/bus"
set +e
regular_bus_output="$(run_test_install "$regular_bus_root" 2>&1)"
regular_bus_status=$?
set -e
[ "$regular_bus_status" -ne 0 ] || fail "trusted binding accepted a regular-file runtime bus"
case "$regular_bus_output" in *"user runtime bus must be a physical Unix socket"*) ;; *)
    fail "runtime bus type rejection reason missing" ;;
esac
[ "$(fake_log_count "$regular_bus_root" show)" = 0 ] || fail "invalid runtime bus reached systemctl"
assert_no_runtime_fragments "$regular_bus_root"

# HOME and every enumerated user-unit search root are part of the execution
# trust boundary. Reject a replaceable tree before the first systemctl query,
# fragment write, or reload.
new_bind_test_root
unsafe_home_root="$BIND_ROOT"
chmod 777 "$unsafe_home_root/home"
set +e
unsafe_home_output="$(run_test_install "$unsafe_home_root" 2>&1)"
unsafe_home_status=$?
set -e
[ "$unsafe_home_status" -ne 0 ] || fail "trusted binding accepted an unsafe passwd HOME"
case "$unsafe_home_output" in *"passwd HOME component is group/other writable"*) ;; *)
    fail "unsafe passwd HOME rejection reason missing" ;;
esac
[ "$(fake_log_count "$unsafe_home_root" show)" = 0 ] &&
    [ "$(fake_log_count "$unsafe_home_root" daemon-reload)" = 0 ] ||
    fail "unsafe passwd HOME reached systemctl"
assert_no_runtime_fragments "$unsafe_home_root"

new_bind_test_root
unsafe_search_root="$BIND_ROOT"
mkdir -m 777 "$unsafe_search_root/replaceable-unit-search"
printf '%s\n' "$unsafe_search_root/replaceable-unit-search" >> "$unsafe_search_root/unit-paths"
set +e
unsafe_search_output="$(run_test_install "$unsafe_search_root" 2>&1)"
unsafe_search_status=$?
set -e
[ "$unsafe_search_status" -ne 0 ] || fail "trusted binding accepted a replaceable user-unit search root"
case "$unsafe_search_output" in *"effective user unit root component is group/other writable"*) ;; *)
    fail "replaceable user-unit search rejection reason missing" ;;
esac
[ "$(fake_log_count "$unsafe_search_root" show)" = 1 ] &&
    [ "$(fake_log_count "$unsafe_search_root" daemon-reload)" = 0 ] ||
    fail "replaceable user-unit search root progressed beyond the manager UnitPath query"
assert_no_runtime_fragments "$unsafe_search_root"

new_bind_test_root
missing_search_root="$BIND_ROOT"
missing_search_path="/tmp/ab-systemd-unit-path-missing.$RANDOM"
[ ! -e "$missing_search_path" ] && [ ! -L "$missing_search_path" ] ||
    fail "missing UnitPath test target unexpectedly exists"
printf '%s\n' "$missing_search_path" >> "$missing_search_root/unit-paths"
set +e
missing_search_output="$(run_test_install "$missing_search_root" 2>&1)"
missing_search_status=$?
set -e
[ "$missing_search_status" -ne 0 ] ||
    fail "trusted binding accepted a missing UnitPath below a sticky writable boundary"
case "$missing_search_output" in *"effective user unit root missing suffix has a replaceable parent: /tmp"*) ;; *)
    fail "replaceable missing UnitPath rejection reason missing" ;;
esac
[ "$(fake_log_count "$missing_search_root" show)" = 1 ] &&
    [ "$(fake_log_count "$missing_search_root" daemon-reload)" = 0 ] ||
    fail "replaceable missing UnitPath progressed beyond its manager query"
assert_no_runtime_fragments "$missing_search_root"

# The current-boot binder cannot bypass the body-state migration transaction.
# Missing or tampered completion evidence is rejected before the manager is
# inspected and before any runtime fragment exists.
new_bind_test_root
missing_migration_root="$BIND_ROOT"
rm "$missing_migration_root/publisher-state/migrations/current.json"
set +e
missing_migration_output="$(run_test_install "$missing_migration_root" 2>&1)"
missing_migration_status=$?
set -e
[ "$missing_migration_status" -ne 0 ] || fail "trusted binding accepted a missing migration receipt"
case "$missing_migration_output" in *"trusted runtime-state migration receipt must be a physical regular file"*) ;; *)
    fail "missing migration-receipt rejection reason absent" ;;
esac
[ "$(fake_log_count "$missing_migration_root" show)" = 0 ] ||
    fail "missing migration receipt reached the user manager"
assert_no_runtime_fragments "$missing_migration_root"

new_bind_test_root
tampered_migration_root="$BIND_ROOT"
printf '%s\n' fixture-tampered > \
    "$tampered_migration_root/publisher-state/migrations/current.json"
set +e
tampered_migration_output="$(run_test_install "$tampered_migration_root" 2>&1)"
tampered_migration_status=$?
set -e
[ "$tampered_migration_status" -ne 0 ] || fail "trusted binding accepted a tampered migration receipt"
case "$tampered_migration_output" in *"trusted runtime-state migration receipt verification failed"*) ;; *)
    fail "tampered migration-receipt rejection reason absent" ;;
esac
[ "$(fake_log_count "$tampered_migration_root" show)" = 0 ] ||
    fail "tampered migration receipt reached the user manager"
assert_no_runtime_fragments "$tampered_migration_root"

# Binding cannot consume a migration handoff while any registered long-lived
# writer, maintenance timer, or maintenance one-shot remains live.  This gate
# runs before the first runtime fragment or daemon-reload mutation.
new_bind_test_root
active_writer_root="$BIND_ROOT"
mkdir -m 700 "$active_writer_root/unit-states"
printf '%s\n' active > \
    "$active_writer_root/unit-states/agent-bridge-sync.timer.ActiveState"
printf '%s\n' waiting > \
    "$active_writer_root/unit-states/agent-bridge-sync.timer.SubState"
printf '%s\n' 0 > \
    "$active_writer_root/unit-states/agent-bridge-sync.timer.MainPID"
chmod 600 "$active_writer_root/unit-states/"*
set +e
active_writer_output="$(run_test_install "$active_writer_root" 2>&1)"
active_writer_status=$?
set -e
[ "$active_writer_status" -ne 0 ] || fail "trusted binding accepted a rearmed migration writer"
case "$active_writer_output" in
    *"runtime-state migration writer is not quiesced: agent-bridge-sync.timer"*) ;;
    *) fail "active migration-writer rejection reason missing" ;;
esac
assert_no_runtime_fragments "$active_writer_root"
[ "$(fake_log_count "$active_writer_root" daemon-reload)" = 0 ] ||
    fail "active migration writer reached daemon-reload"

new_bind_test_root
triggerable_timer_root="$BIND_ROOT"
mkdir -m 700 "$triggerable_timer_root/unit-states"
printf '%s\n' enabled > \
    "$triggerable_timer_root/unit-states/agent-bridge-sync.timer.UnitFileState"
chmod 600 "$triggerable_timer_root/unit-states/"*
set +e
triggerable_timer_output="$(run_test_install "$triggerable_timer_root" 2>&1)"
triggerable_timer_status=$?
set -e
[ "$triggerable_timer_status" -ne 0 ] || fail "trusted binding accepted an enabled legacy timer"
case "$triggerable_timer_output" in
    *"runtime-state migration timer remains triggerable: agent-bridge-sync.timer"*) ;;
    *) fail "triggerable migration-timer rejection reason missing" ;;
esac
assert_no_runtime_fragments "$triggerable_timer_root"
[ "$(fake_log_count "$triggerable_timer_root" daemon-reload)" = 0 ] ||
    fail "triggerable migration timer reached daemon-reload"

# systemd represents an absent timer as LoadState=not-found with an empty
# UnitFileState.  Reject contradictory metadata rather than treating the
# literal string "not-found" as a UnitFileState value.
new_bind_test_root
missing_timer_state_root="$BIND_ROOT"
mkdir -m 700 "$missing_timer_state_root/unit-states"
printf '%s\n' disabled > \
    "$missing_timer_state_root/unit-states/agent-bridge-day2-audit.timer.UnitFileState"
chmod 600 "$missing_timer_state_root/unit-states/"*
set +e
missing_timer_state_output="$(run_test_install "$missing_timer_state_root" 2>&1)"
missing_timer_state_status=$?
set -e
[ "$missing_timer_state_status" -ne 0 ] ||
    fail "trusted binding accepted contradictory missing-timer metadata"
case "$missing_timer_state_output" in
    *"missing runtime-state migration timer has an inconsistent unit-file state: agent-bridge-day2-audit.timer"*) ;;
    *) fail "missing-timer metadata rejection reason absent" ;;
esac
assert_no_runtime_fragments "$missing_timer_state_root"
[ "$(fake_log_count "$missing_timer_state_root" daemon-reload)" = 0 ] ||
    fail "contradictory missing-timer metadata reached daemon-reload"

# The receipt is sampled again at both mutation boundaries. A drift detected
# after staging must leave no fragment; a drift detected after reload must
# roll fragments back and issue the one compensating reload.
new_bind_test_root
second_receipt_root="$BIND_ROOT"
printf '%s\n' fixture-fail-on-second > \
    "$second_receipt_root/publisher-state/migrations/current.json"
set +e
second_receipt_output="$(run_test_install "$second_receipt_root" 2>&1)"
second_receipt_status=$?
set -e
[ "$second_receipt_status" -ne 0 ] || fail "binding accepted receipt drift before activation"
case "$second_receipt_output" in *"migration receipt verification failed"*) ;;
    *) fail "pre-activation receipt drift reason absent" ;;
esac
[ "$(migration_verify_count "$second_receipt_root")" = 2 ] ||
    fail "binding did not resample receipt immediately before activation"
assert_no_runtime_fragments "$second_receipt_root"
[ "$(fake_log_count "$second_receipt_root" daemon-reload)" = 0 ] ||
    fail "pre-activation receipt drift reached daemon-reload"

new_bind_test_root
third_receipt_root="$BIND_ROOT"
printf '%s\n' fixture-fail-on-third > \
    "$third_receipt_root/publisher-state/migrations/current.json"
set +e
third_receipt_output="$(run_test_install "$third_receipt_root" 2>&1)"
third_receipt_status=$?
set -e
[ "$third_receipt_status" -ne 0 ] || fail "binding accepted receipt drift after reload"
case "$third_receipt_output" in *"migration receipt verification failed"*) ;;
    *) fail "post-reload receipt drift reason absent" ;;
esac
[ "$(migration_verify_count "$third_receipt_root")" = 3 ] ||
    fail "binding did not resample receipt after effective-unit verification"
assert_no_runtime_fragments "$third_receipt_root"
[ "$(fake_log_count "$third_receipt_root" daemon-reload)" = 2 ] ||
    fail "post-reload receipt drift did not perform one compensating reload"

# A positive transaction writes three complete runtime units, reloads once,
# verifies their effective values through systemctl show, and never restarts a
# service. Exact replay is read-only while the migration freeze remains held;
# normal post-adoption writes intentionally make the migration receipt stale.
new_bind_test_root
positive_root="$BIND_ROOT"
mkdir -m 700 "$positive_root/unit-states"
printf '%s\n' masked > "$positive_root/unit-states/agent-bridge-sync.timer.LoadState"
printf '%s\n' masked > "$positive_root/unit-states/agent-bridge-sync.timer.UnitFileState"
chmod 600 "$positive_root/unit-states/"*
positive_output="$(run_test_install "$positive_root")"
printf '%s\n' "$positive_output" | grep -qxF \
    'Installed and verified complete trusted current-boot units; services were not restarted.' ||
    fail "positive full-unit transaction completion marker missing"
for unit in "${units[@]}"; do
    fragment="$positive_root/runtime/systemd/user.control/$unit"
    [ -f "$fragment" ] && [ ! -L "$fragment" ] || fail "positive transaction omitted $unit"
    [ "$(stat -c %u "$fragment")" = "$(id -u)" ] || fail "runtime fragment is not euid-owned: $unit"
    [ "$(stat -c %a "$fragment")" = 600 ] || fail "runtime fragment mode is not exact 0600: $unit"
    grep -qxF "WorkingDirectory=$positive_root" "$fragment" ||
        fail "runtime fragment has wrong WorkingDirectory: $unit"
    grep -qxF "Environment=PATH=$positive_root/bin:/usr/bin:/bin" "$fragment" ||
        fail "runtime fragment has wrong PATH: $unit"
    grep -qxF "Environment=AGENT_BRIDGE_STATE_DIR=$positive_root/runtime-state" "$fragment" ||
        fail "runtime fragment has wrong writable state boundary: $unit"
    grep -qxF "Environment=AGENT_BRIDGE_CGROUP_TRANSIENT_DIR=$positive_root/runtime-state/workload-tmp" "$fragment" ||
        fail "runtime fragment has wrong cgroup transient boundary: $unit"
    grep -qxF "Environment=HOME=$positive_root/runtime-state/home" "$fragment" ||
        fail "runtime fragment has wrong trusted HOME: $unit"
    grep -qxF "Environment=XDG_DATA_HOME=$positive_root/runtime-state/data" "$fragment" ||
        fail "runtime fragment has wrong writable XDG data root: $unit"
    grep -qxF "Environment=XDG_STATE_HOME=$positive_root/runtime-state/xdg-state" "$fragment" ||
        fail "runtime fragment has wrong trusted XDG state root: $unit"
    grep -qxF "ReadOnlyPaths=$positive_root $positive_root/runtime" "$fragment" &&
        grep -qxF "ReadWritePaths=$positive_root/runtime-state" "$fragment" ||
        fail "runtime fragment has wrong read-only/read-write split: $unit"
    grep -qxF 'NoNewPrivileges=yes' "$fragment" &&
        grep -qxF 'ProtectSystem=strict' "$fragment" &&
        grep -qxF 'CapabilityBoundingSet=' "$fragment" ||
        fail "runtime fragment hardening is incomplete: $unit"
    grep -q '^ExecStart=/usr/bin/env -i ' "$fragment" ||
        fail "runtime fragment does not clear manager ambient environment: $unit"
    grep -q '^UnsetEnvironment=.*LD_PRELOAD.*BASH_ENV.*PYTHONPATH.*NODE_OPTIONS.*RUSTC_WRAPPER' "$fragment" ||
        fail "runtime fragment loader/shell denylist is incomplete: $unit"
    grep -q 'AMBIENT_DANGER\|must_not_cross_env_i' "$fragment" &&
        fail "runtime fragment captured an arbitrary ambient variable: $unit"
    case "$(cat "$fragment")" in *EnvironmentFile=*|*ExecStartPre=*|*ExecStartPost=*)
        fail "runtime fragment retained an inherited hook: $unit" ;;
    esac
done
grep -qxF '  export AB_SUBSTRATE_PROJECTION=bucket_pool  ' \
    "$positive_root/config/agent-bridge/machine.env" ||
    fail "positive machine.env literal fixture changed unexpectedly"
[ "$(fake_log_count "$positive_root" edit)" = 0 ] || fail "positive transaction called systemctl edit"
[ "$(fake_log_count "$positive_root" daemon-reload)" = 1 ] || fail "positive transaction reload count mismatch"
[ "$(migration_verify_count "$positive_root")" = 3 ] ||
    fail "positive transaction did not verify migration handoff at all three boundaries"
case "$(cat "$positive_root/systemctl.log")" in *restart*) fail "positive transaction restarted a service" ;; esac
edits_before="$(fake_log_count "$positive_root" edit)"
idempotent_output="$(run_test_install "$positive_root")"
printf '%s\n' "$idempotent_output" | grep -qxF \
    'Trusted current-boot units already match exactly; services were not restarted.' ||
    fail "exact full-unit replay was not idempotent"
[ "$(fake_log_count "$positive_root" edit)" = "$edits_before" ] ||
    fail "idempotent replay rewrote a trusted runtime unit"
[ "$(migration_verify_count "$positive_root")" = 4 ] ||
    fail "freeze-window replay did not revalidate the migration handoff"

# Exact idempotence includes directives that are not represented by the
# ordinary property checklist. A pre-existing fragment with one extra
# credential directive must be diagnosed without rewrite or reload.
printf '%s\n' 'LoadCredential=untrusted:/untrusted' >> \
    "$positive_root/runtime/systemd/user.control/agent-bridge-daemon.service"
set +e
tampered_existing_output="$(run_test_install "$positive_root" 2>&1)"
tampered_existing_status=$?
set -e
[ "$tampered_existing_status" -ne 0 ] || fail "idempotent path accepted a tampered runtime fragment"
case "$tampered_existing_output" in *"existing trusted runtime-unit state is not exact"*) ;; *)
    fail "tampered idempotent fragment rejection reason missing" ;;
esac
[ "$(fake_log_count "$positive_root" daemon-reload)" = 1 ] ||
    fail "tampered idempotent fragment triggered a reload"

# A failed second or third atomic activation rolls the transaction all the way
# back to its empty pre-state, without exposing partial state through reload.
for failure_unit in agent-bridge-daemon-http.service agent-bridge-palace.service; do
    new_bind_test_root
    failure_root="$BIND_ROOT"
    set +e
    case "$failure_unit" in
        agent-bridge-daemon-http.service) failpoint=2 ;;
        agent-bridge-palace.service) failpoint=3 ;;
    esac
    failure_output="$(AGENT_BRIDGE_SYSTEMD_BIND_TEST_FAIL_ACTIVATION="$failpoint" \
        run_test_install "$failure_root" 2>&1)"
    failure_status=$?
    set -e
    [ "$failure_status" -ne 0 ] || fail "transaction accepted failed edit for $failure_unit"
    case "$failure_output" in *"test failpoint blocked staged activation $failpoint: $failure_unit"*) ;; *)
        fail "failed-activation diagnostic missing for $failure_unit" ;;
    esac
    assert_no_runtime_fragments "$failure_root"
    [ "$(fake_log_count "$failure_root" daemon-reload)" = 0 ] ||
        fail "pre-reload activation failure unexpectedly reloaded: $failure_unit"
done

# A failed commit reload removes every fragment installed by this invocation
# and performs exactly one compensating reload attempt.
new_bind_test_root
reload_failure_root="$BIND_ROOT"
set +e
reload_failure_output="$(AGENT_BRIDGE_FAKE_SYSTEMCTL_FAIL_RELOAD_ONCE=1 \
    run_test_install "$reload_failure_root" 2>&1)"
reload_failure_status=$?
set -e
[ "$reload_failure_status" -ne 0 ] || fail "transaction accepted a failed daemon-reload"
case "$reload_failure_output" in *"failed to reload the user service manager"*) ;; *)
    fail "daemon-reload failure reason missing" ;;
esac
assert_no_runtime_fragments "$reload_failure_root"
[ "$(fake_log_count "$reload_failure_root" daemon-reload)" = 2 ] ||
    fail "failed commit reload did not issue one compensating reload"

# A fragment that changes between activation and final verification models an
# effective-config mismatch outside the checked property subset. Exact body
# comparison must catch it and roll the complete transaction back.
new_bind_test_root
post_reload_tamper_root="$BIND_ROOT"
set +e
post_reload_tamper_output="$(AGENT_BRIDGE_FAKE_SYSTEMCTL_TAMPER_AFTER_RELOAD=1 \
    run_test_install "$post_reload_tamper_root" 2>&1)"
post_reload_tamper_status=$?
set -e
[ "$post_reload_tamper_status" -ne 0 ] || fail "post-reload fragment tamper was accepted"
case "$post_reload_tamper_output" in *"effective systemd configuration is not the exact trusted binding: agent-bridge-daemon.service"*) ;; *)
    fail "post-reload exact-body mismatch reason missing" ;;
esac
assert_no_runtime_fragments "$post_reload_tamper_root"
[ "$(fake_log_count "$post_reload_tamper_root" daemon-reload)" = 2 ] ||
    fail "post-reload exact-body mismatch did not perform compensating reload"

# A maintenance timer rearmed after the commit reload invalidates the
# migration handoff.  Final quiescence verification must roll back all three
# fragments and perform the compensating reload.
new_bind_test_root
post_reload_writer_root="$BIND_ROOT"
set +e
post_reload_writer_output="$(AGENT_BRIDGE_FAKE_SYSTEMCTL_REARM_WRITER_AFTER_RELOAD=1 \
    run_test_install "$post_reload_writer_root" 2>&1)"
post_reload_writer_status=$?
set -e
[ "$post_reload_writer_status" -ne 0 ] || fail "post-reload writer rearm was accepted"
case "$post_reload_writer_output" in
    *"runtime-state migration writer is not quiesced: agent-bridge-sync.timer"*) ;;
    *) fail "post-reload writer-rearm rejection reason missing" ;;
esac
assert_no_runtime_fragments "$post_reload_writer_root"
[ "$(fake_log_count "$post_reload_writer_root" daemon-reload)" = 2 ] ||
    fail "post-reload writer rearm did not perform one compensating reload"

# If effective verification fails after the one commit reload, rollback must
# remove all three fragments and issue exactly one compensating reload.
new_bind_test_root
post_reload_root="$BIND_ROOT"
set +e
post_reload_output="$(AGENT_BRIDGE_FAKE_SYSTEMCTL_INJECT_AFTER_RELOAD=1 \
    run_test_install "$post_reload_root" 2>&1)"
post_reload_status=$?
set -e
[ "$post_reload_status" -ne 0 ] || fail "post-reload dependency injection was accepted"
case "$post_reload_output" in *"effective systemd configuration is not the exact trusted binding: agent-bridge-daemon.service"*) ;; *)
    fail "post-reload verification failure reason missing" ;;
esac
assert_no_runtime_fragments "$post_reload_root"
[ "$(fake_log_count "$post_reload_root" daemon-reload)" = 2 ] ||
    fail "post-reload rollback did not issue one compensating reload"

# Foreign drop-ins are inspected for all units before the first edit. Their
# presence must leave the runtime transaction completely untouched.
new_bind_test_root
foreign_root="$BIND_ROOT"
mkdir -m 700 "$foreign_root/foreign-dropins"
printf '%s\n' /untrusted/home/drop-in.conf > \
    "$foreign_root/foreign-dropins/agent-bridge-daemon-http.service"
chmod 600 "$foreign_root/foreign-dropins/agent-bridge-daemon-http.service"
set +e
foreign_output="$(run_test_install "$foreign_root" 2>&1)"
foreign_status=$?
set -e
[ "$foreign_status" -ne 0 ] || fail "transaction accepted a foreign drop-in"
case "$foreign_output" in *"foreign drop-ins must be archived before trusted binding: agent-bridge-daemon-http.service"*) ;; *)
    fail "foreign drop-in rejection reason missing" ;;
esac
[ "$(fake_log_count "$foreign_root" edit)" = 0 ] || fail "foreign drop-in was rejected after a runtime write"
[ "$(fake_log_count "$foreign_root" daemon-reload)" = 0 ] ||
    fail "foreign drop-in rejection unexpectedly reloaded"
assert_no_runtime_fragments "$foreign_root"

# Dependency directories, timers, sockets, paths, and reverse success hooks can
# inject activation relationships without appearing in DropInPaths. Every such
# property is inspected before activation and verified again after reload.
for dependency_property in \
    Wants WantedBy Requires TriggeredBy OnSuccess RequisiteOf BoundBy UpheldBy \
    ConsistsOf ConflictedBy OnFailureOf OnSuccessOf
do
    new_bind_test_root
    dependency_root="$BIND_ROOT"
    mkdir -m 700 "$dependency_root/foreign-dependencies"
    case "$dependency_property" in
        TriggeredBy) injected_dependency=evil.timer ;;
        OnSuccess) injected_dependency=evil-success.service ;;
        WantedBy) injected_dependency=evil.target ;;
        *) injected_dependency=untrusted-agent-bridge-sidecar.service ;;
    esac
    printf '%s\n' "$injected_dependency" > \
        "$dependency_root/foreign-dependencies/agent-bridge-daemon-http.service.$dependency_property"
    chmod 600 \
        "$dependency_root/foreign-dependencies/agent-bridge-daemon-http.service.$dependency_property"
    set +e
    dependency_output="$(run_test_install "$dependency_root" 2>&1)"
    dependency_status=$?
    set -e
    [ "$dependency_status" -ne 0 ] || fail "transaction accepted foreign $dependency_property injection"
    case "$dependency_output" in *"foreign dependency injection must be archived before trusted binding: agent-bridge-daemon-http.service"*) ;; *)
        fail "foreign $dependency_property rejection reason missing" ;;
    esac
    [ "$(fake_log_count "$dependency_root" daemon-reload)" = 0 ] ||
        fail "foreign $dependency_property rejection unexpectedly reloaded"
    assert_no_runtime_fragments "$dependency_root"
done

printf '%s\n' systemd-trusted-daemon-root-ok
