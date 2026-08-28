#!/bin/bash
# Install bounded, complete runtime replacements for the three long-lived
# Agent-Bridge services. The replacement units pin one permission-capable
# deployment root without copying repository units into HOME, enabling timers,
# or restarting live services.
#
# This is intentionally a current-boot binding: complete units are staged and
# atomically activated under the user runtime control directory before one
# daemon-reload. It is sufficient for an explicit install/restart/verify
# admission sequence, but it is not proof of reboot-persistent unit trust.
# The mount namespace narrows service writes, but a user manager and its D-Bus
# remain a local-UID boundary. Strong workload isolation requires root-managed
# system units running under dedicated service identities.
#
# Usage:
#   AGENT_BRIDGE_DEPLOY_ROOT=/private/root \
#     /private/root/source/agent-bridge/scripts/systemd/install-trusted-daemon-root.sh --dry-run
#   AGENT_BRIDGE_DEPLOY_ROOT=/private/root \
#     /private/root/source/agent-bridge/scripts/systemd/install-trusted-daemon-root.sh --install

set -euo pipefail
PATH=/usr/bin:/bin
LC_ALL=C
LANG=C
TZ=UTC
export PATH LC_ALL LANG TZ
unset LD_PRELOAD LD_LIBRARY_PATH LD_AUDIT LD_DEBUG LD_PROFILE GCONV_PATH \
    LOCPATH NLSPATH BASH_ENV ENV SHELLOPTS BASHOPTS CDPATH GLOBIGNORE \
    PYTHONPATH PYTHONHOME PERL5LIB RUBYLIB NODE_OPTIONS NODE_PATH \
    RUSTC_WRAPPER SYSTEMD_BUS_ADDRESS SYSTEMD_HOST SYSTEMD_MACHINE \
    SYSTEMD_PAGER SYSTEMD_PAGERSECURE PAGER 2>/dev/null || true

MODE=""
case "${1:-}" in
    --dry-run) MODE=dry-run ;;
    --install) MODE=install ;;
    -h|--help)
        sed -n '2,18p' "$0"
        exit 0
        ;;
    '') printf 'ERROR: choose --dry-run or --install\n' >&2; exit 2 ;;
    *) printf 'ERROR: unknown arg: %s\n' "$1" >&2; exit 2 ;;
esac
[ "$#" -eq 1 ] || { printf 'ERROR: expected exactly one mode argument\n' >&2; exit 2; }

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

SYSTEMD_BIND_TEST_MODE="${AGENT_BRIDGE_SYSTEMD_BIND_TEST_MODE:-0}"
case "$SYSTEMD_BIND_TEST_MODE" in
    0|1) ;;
    *) die "AGENT_BRIDGE_SYSTEMD_BIND_TEST_MODE must be 0 or 1" ;;
esac

host_os="$(/usr/bin/uname -s 2>/dev/null || uname -s)"
[ "$host_os" = Linux ] || die "trusted daemon binding requires Linux systemd"

path_mode() {
    case "$host_os" in
        Darwin) stat -f %Lp "$1" 2>/dev/null ;;
        Linux) stat -c %a "$1" 2>/dev/null ;;
    esac
}

path_owner_uid() {
    case "$host_os" in
        Darwin) stat -f %u "$1" 2>/dev/null ;;
        Linux) stat -c %u "$1" 2>/dev/null ;;
    esac
}

path_has_symlink_component() {
    local path="$1" rest part current=""
    case "$path" in /*) rest="${path#/}" ;; *) return 0 ;; esac
    while [ -n "$rest" ]; do
        case "$rest" in
            */*) part="${rest%%/*}"; rest="${rest#*/}" ;;
            *) part="$rest"; rest="" ;;
        esac
        [ -n "$part" ] || continue
        current="$current/$part"
        [ ! -L "$current" ] || return 0
    done
    return 1
}

mode_has_group_or_other_write() {
    local mode="$1"
    (( (8#$mode & 8#022) != 0 ))
}

mode_is_root_sticky_boundary() {
    local mode="$1" uid="$2"
    [ "$uid" = 0 ] && (( (8#$mode & 8#1000) != 0 )) &&
        mode_has_group_or_other_write "$mode"
}

validate_trusted_deploy_root() {
    local raw="$1" euid current rest part mode uid canonical
    [ -n "$raw" ] || die "AGENT_BRIDGE_DEPLOY_ROOT is required"
    case "$raw" in
        /) die "AGENT_BRIDGE_DEPLOY_ROOT must not be the filesystem root" ;;
        /*) ;;
        *) die "AGENT_BRIDGE_DEPLOY_ROOT must be absolute" ;;
    esac
    case "$raw" in
        *//*|*/./*|*/../*|*/.|*/..|*/)
            die "AGENT_BRIDGE_DEPLOY_ROOT must be canonical"
            ;;
    esac
    case "$raw" in
        *[!A-Za-z0-9._/-]*)
            die "AGENT_BRIDGE_DEPLOY_ROOT contains an unsupported character"
            ;;
    esac
    [ -d "$raw" ] && [ ! -L "$raw" ] ||
        die "AGENT_BRIDGE_DEPLOY_ROOT must be a pre-existing physical directory"

    euid="$(id -u)"
    current=""
    rest="${raw#/}"
    while [ -n "$rest" ]; do
        case "$rest" in
            */*) part="${rest%%/*}"; rest="${rest#*/}" ;;
            *) part="$rest"; rest="" ;;
        esac
        current="$current/$part"
        [ -d "$current" ] && [ ! -L "$current" ] ||
            die "deployment-root path component is not a physical directory: $current"
        mode="$(path_mode "$current")" || die "cannot inspect deployment-root mode"
        uid="$(path_owner_uid "$current")" || die "cannot inspect deployment-root owner"
        if [ "$uid" != "$euid" ] && [ "$uid" != 0 ]; then
            die "deployment-root ancestor has an untrusted owner"
        fi
        if mode_has_group_or_other_write "$mode" &&
                ! mode_is_root_sticky_boundary "$mode" "$uid"; then
            die "deployment-root ancestor is group/other writable"
        fi
    done

    uid="$(path_owner_uid "$raw")" || die "cannot inspect deployment-root owner"
    [ "$uid" = "$euid" ] || die "AGENT_BRIDGE_DEPLOY_ROOT must be owned by the effective user"
    mode="$(path_mode "$raw")" || die "cannot inspect deployment-root mode"
    [ "$mode" = 700 ] ||
        die "AGENT_BRIDGE_DEPLOY_ROOT mode must be exact 0700"
    canonical="$(cd -P "$raw" && pwd -P)" || die "cannot canonicalize AGENT_BRIDGE_DEPLOY_ROOT"
    [ "$canonical" = "$raw" ] || die "AGENT_BRIDGE_DEPLOY_ROOT must be a physical canonical path"
    printf '%s\n' "$canonical"
}

validate_installed_file() {
    local path="$1" expected_mode="$2" label="$3" owner mode
    ! path_has_symlink_component "$path" || die "$label path must not traverse a symlink"
    [ -f "$path" ] && [ ! -L "$path" ] || die "$label must be a physical regular file"
    owner="$(path_owner_uid "$path")" || die "cannot inspect $label owner"
    [ "$owner" = "$(id -u)" ] || die "$label must be owned by the effective user"
    mode="$(path_mode "$path")" || die "cannot inspect $label mode"
    [ "$mode" = "$expected_mode" ] || die "$label mode must be exact 0$expected_mode"
}

validate_private_directory_tree() {
    local path="$1" label="$2" current relative part owner mode
    case "$path" in
        "$DEPLOY_ROOT") relative="" ;;
        "$DEPLOY_ROOT"/*) relative="${path#"$DEPLOY_ROOT"/}" ;;
        *) die "$label escapes the trusted deployment root" ;;
    esac
    current="$DEPLOY_ROOT"
    while :; do
        [ -d "$current" ] && [ ! -L "$current" ] ||
            die "$label path component must be a physical directory: $current"
        owner="$(path_owner_uid "$current")" || die "cannot inspect $label directory owner"
        [ "$owner" = "$(id -u)" ] || die "$label directory must be owned by the effective user"
        mode="$(path_mode "$current")" || die "cannot inspect $label directory mode"
        [ "$mode" = 700 ] || die "$label directory mode must be exact 0700: $current"
        [ -n "$relative" ] || break
        case "$relative" in
            */*) part="${relative%%/*}"; relative="${relative#*/}" ;;
            *) part="$relative"; relative="" ;;
        esac
        case "$part" in ''|.|..) die "$label directory path is not canonical" ;; esac
        current="$current/$part"
    done
}

DEPLOY_ROOT="$(validate_trusted_deploy_root "${AGENT_BRIDGE_DEPLOY_ROOT:-}")"
WRAPPER="$DEPLOY_ROOT/bin/agent-bridge"
REAL_BIN="$DEPLOY_ROOT/bin/agent-bridge.real"
RUNTIME_STATE="$DEPLOY_ROOT/runtime-state"
RECEIPT_ROOT="$RUNTIME_STATE/workload-receipts"
CGROUP_TRANSIENT_ROOT="$RUNTIME_STATE/workload-tmp"
ADAPTER="$DEPLOY_ROOT/share/ab-tts/audio_embody.py"
RUNTIME_ASSETS="$DEPLOY_ROOT/lib/agent-bridge/scripts"
MACHINE_ENV="$DEPLOY_ROOT/config/agent-bridge/machine.env"
CREDENTIALS="$DEPLOY_ROOT/config/agent-bridge/credentials"
TRUSTED_HOME="$RUNTIME_STATE/home"
TRUSTED_XDG_CONFIG_HOME="$DEPLOY_ROOT/config"
TRUSTED_XDG_DATA_HOME="$RUNTIME_STATE/data"
TRUSTED_XDG_CACHE_HOME="$RUNTIME_STATE/cache"
TRUSTED_XDG_STATE_HOME="$RUNTIME_STATE/xdg-state"
TRUSTED_TMPDIR="$RUNTIME_STATE/tmp"
ACCOUNT_NAME="$(/usr/bin/id -un)" || die "cannot resolve the effective passwd account name"
case "$ACCOUNT_NAME" in
    ''|*[!A-Za-z0-9._-]*) die "effective passwd account name is not safe for a systemd environment" ;;
esac

PUBLISHER_STATE="$DEPLOY_ROOT/publisher-state/deploy"
PENDING_ADMISSION="$PUBLISHER_STATE/pending-admission.meta"
PUBLISHER_KERNEL_LOCK="$PUBLISHER_STATE/publisher.kernel.lock"
SOURCE_REPOSITORY="$DEPLOY_ROOT/source/agent-bridge"
GITLAB_REMOTE_URL=git@gitlab.com:pallasting/agent-bridge.git
PUBLISHER_LOCK_FD=""
PUBLISHER_ASSETS_SHA=""

acquire_publisher_kernel_lock() {
    local path_identity descriptor_identity
    validate_private_directory_tree "$DEPLOY_ROOT/publisher-state" "trusted publisher state root"
    validate_private_directory_tree "$PUBLISHER_STATE" "trusted publisher deploy state"
    validate_installed_file "$PUBLISHER_KERNEL_LOCK" 600 "publisher kernel lock"
    exec {PUBLISHER_LOCK_FD}<>"$PUBLISHER_KERNEL_LOCK" || die "cannot open publisher kernel lock"
    /usr/bin/flock -n "$PUBLISHER_LOCK_FD" ||
        die "publisher kernel lock is busy; trusted binding made no changes"
    path_identity="$(stat -Lc '%d:%i:%u:%a:%F' "$PUBLISHER_KERNEL_LOCK")" ||
        die "cannot re-inspect publisher kernel lock"
    descriptor_identity="$(stat -Lc '%d:%i:%u:%a:%F' "/proc/self/fd/$PUBLISHER_LOCK_FD")" ||
        die "cannot inspect acquired publisher kernel lock descriptor"
    [ "$descriptor_identity" = "$path_identity" ] ||
        die "publisher kernel lock identity changed during acquisition"
    [ -f "/proc/self/fd/$PUBLISHER_LOCK_FD" ] ||
        die "acquired publisher kernel lock descriptor is not a regular file"
    case "$descriptor_identity" in
        *:"$(id -u)":600:*) ;;
        *) die "acquired publisher kernel lock is not the exact trusted file" ;;
    esac
}

pending_admission_value() {
    local file="$1" line_number="$2" key="$3" line
    line="$(sed -n "${line_number}p" "$file" 2>/dev/null)" || return 1
    case "$line" in "$key="*) printf '%s\n' "${line#*=}" ;; *) return 1 ;; esac
}

sha256_file() {
    /usr/bin/sha256sum "$1" | /usr/bin/awk '{ print $1 }'
}

validate_publisher_candidate() {
    local keys schema lease_id challenge real_path shared_targets candidate
    local installed_sha installed_inode installed_mode assets_sha installed_at
    local fresh_mcp force_reinstall force_reason expected_targets actual_sha actual_inode
    validate_private_directory_tree "$DEPLOY_ROOT/publisher-state" "trusted publisher state root"
    validate_private_directory_tree "$PUBLISHER_STATE" "trusted publisher deploy state"
    validate_installed_file "$PENDING_ADMISSION" 600 "publisher pending admission"
    keys="$(cut -d= -f1 "$PENDING_ADMISSION" | paste -sd, -)" ||
        die "cannot parse publisher pending admission keys"
    [ "$keys" = "schema,lease_id,challenge,real_path,shared_targets,candidate_commit,installed_binary_sha256,installed_binary_inode,installed_binary_mode,installed_assets_sha256,installed_at,fresh_mcp,force_reinstall,force_reason" ] ||
        die "publisher pending admission schema is unknown or corrupt"
    [ "$(wc -l < "$PENDING_ADMISSION" | tr -d ' ')" = 14 ] ||
        die "publisher pending admission must contain exactly 14 fields"
    schema="$(pending_admission_value "$PENDING_ADMISSION" 1 schema)" || die "invalid pending schema field"
    lease_id="$(pending_admission_value "$PENDING_ADMISSION" 2 lease_id)" || die "invalid pending lease field"
    challenge="$(pending_admission_value "$PENDING_ADMISSION" 3 challenge)" || die "invalid pending challenge field"
    real_path="$(pending_admission_value "$PENDING_ADMISSION" 4 real_path)" || die "invalid pending binary path field"
    shared_targets="$(pending_admission_value "$PENDING_ADMISSION" 5 shared_targets)" || die "invalid pending shared-target field"
    candidate="$(pending_admission_value "$PENDING_ADMISSION" 6 candidate_commit)" || die "invalid pending candidate field"
    installed_sha="$(pending_admission_value "$PENDING_ADMISSION" 7 installed_binary_sha256)" || die "invalid pending binary SHA field"
    installed_inode="$(pending_admission_value "$PENDING_ADMISSION" 8 installed_binary_inode)" || die "invalid pending binary inode field"
    installed_mode="$(pending_admission_value "$PENDING_ADMISSION" 9 installed_binary_mode)" || die "invalid pending binary mode field"
    assets_sha="$(pending_admission_value "$PENDING_ADMISSION" 10 installed_assets_sha256)" || die "invalid pending asset SHA field"
    installed_at="$(pending_admission_value "$PENDING_ADMISSION" 11 installed_at)" || die "invalid pending install time field"
    fresh_mcp="$(pending_admission_value "$PENDING_ADMISSION" 12 fresh_mcp)" || die "invalid pending fresh-MCP field"
    force_reinstall="$(pending_admission_value "$PENDING_ADMISSION" 13 force_reinstall)" || die "invalid pending force field"
    force_reason="$(pending_admission_value "$PENDING_ADMISSION" 14 force_reason)" || die "invalid pending force-reason field"

    [ "$schema" = agent_bridge.publisher_pending_admission.v0 ] ||
        die "publisher pending admission schema mismatch"
    [[ "$lease_id" =~ ^[A-Za-z0-9._-]{1,128}$ ]] || die "publisher pending lease id is invalid"
    [[ "$challenge" =~ ^[0-9a-f]{64}$ ]] || die "publisher pending challenge is invalid"
    [[ "$candidate" =~ ^[0-9a-f]{40}$ ]] || die "publisher candidate commit must be a 40-hex object id"
    [[ "$installed_sha" =~ ^[0-9a-f]{64}$ ]] || die "publisher installed binary SHA is invalid"
    [[ "$assets_sha" =~ ^[0-9a-f]{64}$ ]] || die "publisher installed asset SHA is invalid"
    [[ "$installed_inode" =~ ^[0-9]+$ ]] || die "publisher installed binary inode is invalid"
    [ "$installed_mode" = 755 ] || die "publisher installed binary mode must be exact 0755"
    [[ "$installed_at" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] ||
        die "publisher installed-at value is invalid"
    [ "$fresh_mcp" = unverified ] || die "publisher pending admission is not awaiting fresh MCP"
    case "$force_reinstall" in 0|1) ;; *) die "publisher pending force flag is invalid" ;; esac
    [[ "$force_reason" =~ ^[[:print:]]*$ ]] || die "publisher pending force reason is invalid"
    [ "$real_path" = "$REAL_BIN" ] || die "publisher pending admission names a different installed binary"
    expected_targets="$REAL_BIN|$ADAPTER|$RUNTIME_ASSETS|$WRAPPER"
    [ "$shared_targets" = "$expected_targets" ] ||
        die "publisher pending admission shared targets do not match the trusted root"
    validate_installed_file "$REAL_BIN" 755 "publisher-installed real binary"
    actual_inode="$(stat -c %i "$REAL_BIN")" || die "cannot inspect publisher-installed binary inode"
    [ "$actual_inode" = "$installed_inode" ] || die "publisher-installed binary inode drifted after admission"
    actual_sha="$(sha256_file "$REAL_BIN")" || die "cannot hash publisher-installed real binary"
    [ "$actual_sha" = "$installed_sha" ] || die "publisher-installed binary SHA drifted after admission"
    PUBLISHER_CANDIDATE="$candidate"
    PUBLISHER_ASSETS_SHA="$assets_sha"
}

trusted_source_git() {
    /usr/bin/env -i \
        GIT_ATTR_NOSYSTEM=1 \
        GIT_CONFIG_GLOBAL=/dev/null \
        GIT_CONFIG_NOSYSTEM=1 \
        GIT_NO_REPLACE_OBJECTS=1 \
        HOME="$DEPLOY_ROOT" \
        LANG=C \
        PATH=/usr/bin:/bin \
        /usr/bin/git --no-pager \
        -c core.attributesFile=/dev/null \
        -c core.hooksPath=/dev/null \
        -C "$SOURCE_REPOSITORY" "$@"
}

validate_source_candidate_authority() {
    local expected="$1" head remote_master remote_urls remote_url_count override
    for override in \
        "$SOURCE_REPOSITORY/.git/info/attributes" \
        "$SOURCE_REPOSITORY/.git/info/grafts" \
        "$SOURCE_REPOSITORY/.git/objects/info/alternates" \
        "$SOURCE_REPOSITORY/.git/objects/info/http-alternates"
    do
        [ ! -e "$override" ] && [ ! -L "$override" ] ||
            die "trusted source repository contains a forbidden local object/attribute override: $override"
    done
    head="$(trusted_source_git rev-parse --verify 'HEAD^{commit}')" ||
        die "cannot resolve trusted source HEAD"
    [ "$head" = "$PUBLISHER_CANDIDATE" ] ||
        die "trusted source HEAD does not match the publisher candidate"
    remote_master="$(trusted_source_git rev-parse --verify 'refs/remotes/gitlab/master^{commit}')" ||
        die "cannot resolve trusted GitLab master ref"
    [ "$remote_master" = "$PUBLISHER_CANDIDATE" ] ||
        die "trusted GitLab master ref does not match the publisher candidate"
    remote_urls="$(trusted_source_git config --local --get-all remote.gitlab.url)" ||
        die "trusted source repository has no GitLab remote URL"
    remote_url_count="$(printf '%s\n' "$remote_urls" | awk 'NF { count += 1 } END { print count + 0 }')"
    [ "$remote_url_count" = 1 ] && [ "$remote_urls" = "$GITLAB_REMOTE_URL" ] ||
        die "trusted source repository GitLab URL is not exact"
    trusted_source_git cat-file -e "$PUBLISHER_CANDIDATE^{commit}" ||
        die "publisher candidate commit is absent from the trusted source repository"
    cmp -s "$expected" \
        <(trusted_source_git show --no-textconv --no-ext-diff \
            "$PUBLISHER_CANDIDATE:scripts/systemd/install-trusted-daemon-root.sh") ||
        die "trusted daemon installer bytes do not match the publisher candidate"
}

validate_published_installer_source() {
    local expected source_dir physical
    expected="$DEPLOY_ROOT/source/agent-bridge/scripts/systemd/install-trusted-daemon-root.sh"
    source_dir="$(dirname -- "${BASH_SOURCE[0]}")"
    physical="$(cd -P "$source_dir" 2>/dev/null && printf '%s/%s\n' "$(pwd -P)" \
        "$(basename -- "${BASH_SOURCE[0]}")")" ||
        die "cannot resolve trusted daemon installer source"
    [ "$physical" = "$expected" ] ||
        die "production trusted binding must run from the published safe clone: $expected"
    validate_private_directory_tree "$DEPLOY_ROOT/source" "trusted source root"
    validate_private_directory_tree "$DEPLOY_ROOT/source/agent-bridge" "trusted source repository"
    validate_private_directory_tree "$DEPLOY_ROOT/source/agent-bridge/.git" "trusted source repository metadata"
    validate_private_directory_tree "$DEPLOY_ROOT/source/agent-bridge/scripts" "trusted source scripts"
    validate_private_directory_tree "$DEPLOY_ROOT/source/agent-bridge/scripts/systemd" \
        "trusted systemd installer directory"
    validate_installed_file "$expected" 700 "trusted daemon installer"
    [ "$MODE" = install ] || return 0
    acquire_publisher_kernel_lock
    validate_publisher_candidate
    validate_source_candidate_authority "$expected"
}

if [ "$SYSTEMD_BIND_TEST_MODE" = 0 ]; then
    validate_published_installer_source
fi
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

publisher_installed_assets_sha256() {
    local audio_companion audio_policy runtime_asset path
    {
        printf 'wrapper\t%s\t%s\t%s\n' "$WRAPPER" "$(sha256_file "$WRAPPER")" "$(path_mode "$WRAPPER")"
        printf 'adapter\t%s\t%s\t%s\n' "$ADAPTER" "$(sha256_file "$ADAPTER")" "$(path_mode "$ADAPTER")"
        for audio_companion in "${AUDIO_ADAPTER_COMPANION_FILES[@]}"; do
            path="$(dirname "$ADAPTER")/$audio_companion"
            printf 'companion\t%s\t%s\t%s\n' "$path" "$(sha256_file "$path")" "$(path_mode "$path")"
        done
        for audio_policy in "${AUDIO_POLICY_FILES[@]}"; do
            path="$DEPLOY_ROOT/share/$audio_policy"
            printf 'policy\t%s\t%s\t%s\n' "$path" "$(sha256_file "$path")" "$(path_mode "$path")"
        done
        for runtime_asset in "${RUNTIME_ASSET_FILES[@]}"; do
            path="$RUNTIME_ASSETS/$runtime_asset"
            printf 'runtime\t%s\t%s\t%s\n' "$path" "$(sha256_file "$path")" "$(path_mode "$path")"
        done
    } | /usr/bin/sha256sum | /usr/bin/awk '{ print $1 }'
}

candidate_file_matches() {
    local installed="$1" repository_path="$2" label="$3"
    cmp -s "$installed" <(trusted_source_git show --no-textconv --no-ext-diff \
        "$PUBLISHER_CANDIDATE:$repository_path") ||
        die "$label bytes do not match the publisher candidate"
}

validate_installed_candidate_assets() {
    local audio_companion audio_policy runtime_asset actual_assets_sha
    actual_assets_sha="$(publisher_installed_assets_sha256)" ||
        die "cannot hash the publisher-installed asset manifest"
    [ "$actual_assets_sha" = "$PUBLISHER_ASSETS_SHA" ] ||
        die "publisher-installed asset manifest drifted after admission"
    candidate_file_matches "$WRAPPER" scripts/wrapper/agent-bridge-wrapper.sh \
        "trusted wrapper"
    candidate_file_matches "$ADAPTER" scripts/audio_embody.py "trusted audio adapter"
    for audio_companion in "${AUDIO_ADAPTER_COMPANION_FILES[@]}"; do
        candidate_file_matches "$(dirname "$ADAPTER")/$audio_companion" \
            "scripts/$audio_companion" "trusted audio adapter companion $audio_companion"
    done
    for audio_policy in "${AUDIO_POLICY_FILES[@]}"; do
        candidate_file_matches "$DEPLOY_ROOT/share/$audio_policy" "$audio_policy" \
            "trusted audio policy $audio_policy"
    done
    for runtime_asset in "${RUNTIME_ASSET_FILES[@]}"; do
        candidate_file_matches "$RUNTIME_ASSETS/$runtime_asset" "scripts/$runtime_asset" \
            "trusted runtime asset $runtime_asset"
    done
}

validate_machine_path_literal() {
    local key="$1" path="$2" parent relative part current owner mode numeric
    case "$path" in
        /*) ;;
        *) die "machine environment path for $key must be absolute" ;;
    esac
    case "$path" in
        *//*|*/./*|*/../*|*/.|*/..|*/)
            die "machine environment path for $key must be canonical"
            ;;
    esac
    case "$path" in
        "$DEPLOY_ROOT"/*) ;;
        *) die "machine environment path for $key must remain beneath the trusted deployment root" ;;
    esac
    ! path_has_symlink_component "$path" ||
        die "machine environment path for $key must not traverse a symlink"
    [ -e "$path" ] && [ ! -L "$path" ] ||
        die "machine environment path for $key must be pre-existing and physical"

    parent="${path%/*}"
    case "$parent" in
        "$DEPLOY_ROOT") relative="" ;;
        "$DEPLOY_ROOT"/*) relative="${parent#"$DEPLOY_ROOT"/}" ;;
        *) die "machine environment path for $key escaped its trusted parent" ;;
    esac
    current="$DEPLOY_ROOT"
    while [ -n "$relative" ]; do
        case "$relative" in
            */*) part="${relative%%/*}"; relative="${relative#*/}" ;;
            *) part="$relative"; relative="" ;;
        esac
        current="$current/$part"
        [ -d "$current" ] && [ ! -L "$current" ] ||
            die "machine environment path for $key has a non-physical parent"
        owner="$(path_owner_uid "$current")" ||
            die "cannot inspect machine environment path parent for $key"
        [ "$owner" = "$(id -u)" ] ||
            die "machine environment path parent for $key has an untrusted owner"
        mode="$(path_mode "$current")" ||
            die "cannot inspect machine environment path parent mode for $key"
        [ "$mode" = 700 ] ||
            die "machine environment path parent for $key must be exact mode 0700"
    done

    owner="$(path_owner_uid "$path")" ||
        die "cannot inspect machine environment path owner for $key"
    [ "$owner" = "$(id -u)" ] ||
        die "machine environment path for $key has an untrusted owner"
    mode="$(path_mode "$path")" ||
        die "cannot inspect machine environment path mode for $key"
    if [ -d "$path" ]; then
        [ "$mode" = 700 ] ||
            die "machine environment directory for $key must be exact mode 0700"
    elif [ -f "$path" ]; then
        numeric=$((8#$mode))
        [ $((numeric & 8#7022)) -eq 0 ] ||
            die "machine environment file for $key has an unsafe mode"
    else
        die "machine environment path for $key must be a regular file or directory"
    fi
    if [ "$key" = AB_SUBSTRATE_SVD_PATH ]; then
        [ -f "$path" ] && [ "$mode" = 600 ] ||
            die "machine environment SVD artifact must be a physical mode-0600 file"
    fi
}

validate_machine_regular_file_literal() {
    local key="$1" path="$2"
    validate_machine_path_literal "$key" "$path"
    [ -f "$path" ] || die "machine environment path for $key must be a regular file"
}

validate_machine_executable_literal() {
    local key="$1" path="$2"
    validate_machine_regular_file_literal "$key" "$path"
    [ -x "$path" ] || die "machine environment path for $key must be executable"
}

validate_machine_directory_literal() {
    local key="$1" path="$2"
    validate_machine_path_literal "$key" "$path"
    [ -d "$path" ] || die "machine environment path for $key must be a directory"
}

validate_machine_environment_contract() {
    local raw line assignment key value remote_port line_number=0 projection="" svd_path_seen=0
    local qwen_rust_enabled="" qwen_rust_bin_seen=0 qwen_rust_model_seen=0
    local qwen_rust_profile_seen=0
    local -A seen=()
    while IFS= read -r raw || [ -n "$raw" ]; do
        line_number=$((line_number + 1))
        line="${raw#"${raw%%[![:blank:]]*}"}"
        line="${line%"${line##*[![:blank:]]}"}"
        case "$line" in ''|'#'*) continue ;; esac
        case "$line" in
            export[[:blank:]]*)
                assignment="${line#export}"
                assignment="${assignment#"${assignment%%[![:blank:]]*}"}"
                ;;
            *) die "trusted machine environment line $line_number must be an explicit export assignment" ;;
        esac
        case "$assignment" in
            *=*) key="${assignment%%=*}"; value="${assignment#*=}" ;;
            *) die "trusted machine environment line $line_number is not a KEY=literal assignment" ;;
        esac
        [[ "$key" =~ ^[A-Z_][A-Z0-9_]*$ ]] ||
            die "trusted machine environment line $line_number has an invalid key"
        [ -n "$value" ] || die "trusted machine environment value for $key must not be empty"
        if [ "${seen[$key]+present}" = present ]; then
            die "trusted machine environment contains duplicate key $key"
        fi
        seen[$key]=1

        case "$key" in
            *API_KEY*|*AUTH_TOKEN*|*AUTH_SECRET*|*BEARER*|*COOKIE*|*CREDENTIAL*|\
            *PASSWORD*|*PASSWD*|*PRIVATE_KEY*|*SECRET*|*TOKEN*)
                die "secret-like key $key is forbidden in trusted machine environment"
                ;;
        esac
        case "$key" in
            AGENT_BRIDGE_DEPLOY_ROOT|AGENT_BRIDGE_INSTALL_DIR|AGENT_BRIDGE_REAL_BIN|\
            AGENT_BRIDGE_STATE_DIR|AGENT_BRIDGE_CGROUP_RECEIPT_DIR|\
            AGENT_BRIDGE_CGROUP_TRANSIENT_DIR|AGENT_BRIDGE_AUDIO_EMBODY_SCRIPT|\
            AGENT_BRIDGE_RUNTIME_ASSET_DIR|AGENT_BRIDGE_MACHINE_ENV|\
            AGENT_BRIDGE_CREDS_FILE|AB_APP_CONTROL_*|HOME|XDG_*|TMPDIR|PATH|\
            USER|LOGNAME|LANG|LC_*|DBUS_SESSION_BUS_ADDRESS)
                die "trusted machine environment may not override runtime pin $key"
                ;;
        esac
        [[ "$value" =~ ^[-A-Za-z0-9._/:+@%,]+$ ]] ||
            die "trusted machine environment value for $key must be a plain unquoted literal"

        case "$key" in
            AB_SUBSTRATE_PROJECTION)
                projection="$value"
                case "$value" in bucket_pool|svd) ;; *)
                    die "AB_SUBSTRATE_PROJECTION must be bucket_pool or svd" ;;
                esac
                ;;
            AB_SUBSTRATE_SVD_PATH)
                svd_path_seen=1
                validate_machine_regular_file_literal "$key" "$value"
                ;;
            AGENT_BRIDGE_CONTEXT_WINDOW)
                [[ "$value" =~ ^[1-9][0-9]{0,7}$ ]] ||
                    die "AGENT_BRIDGE_CONTEXT_WINDOW must be a bounded positive integer literal"
                [ "$value" -le 1000000 ] ||
                    die "AGENT_BRIDGE_CONTEXT_WINDOW exceeds the admitted maximum"
                ;;
            AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS)
                [ "$value" = organic ] ||
                    die "AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS must be organic for a persistent service"
                ;;
            AGENT_BRIDGE_TOOLSET)
                case "$value" in
                    codex-essential|codex-voice|codex-lean|codex-mobile-projection|\
                    codex-essential-mobile-projection|codex-ag-ui-readonly) ;;
                    *) die "AGENT_BRIDGE_TOOLSET has an unsupported bounded literal" ;;
                esac
                ;;
            AGENT_BRIDGE_EMBED_REMOTE_URL)
                [[ "$value" =~ ^http://127\.0\.0\.1:[1-9][0-9]{0,4}/embed$ ]] ||
                    die "AGENT_BRIDGE_EMBED_REMOTE_URL must be a literal loopback /embed URL"
                remote_port="${value#http://127.0.0.1:}"
                remote_port="${remote_port%/embed}"
                [ "$remote_port" -le 65535 ] ||
                    die "AGENT_BRIDGE_EMBED_REMOTE_URL port is outside the admitted range"
                ;;
            AB_QWEN3_TTS_RUST_ENABLED)
                case "$value" in 0|1) ;; *)
                    die "AB_QWEN3_TTS_RUST_ENABLED must be 0 or 1" ;;
                esac
                qwen_rust_enabled="$value"
                ;;
            AB_QWEN3_TTS_RUST_PROFILE)
                case "$value" in 0.6b-customvoice|1.7b-customvoice) ;; *)
                    die "AB_QWEN3_TTS_RUST_PROFILE has an unsupported literal" ;;
                esac
                qwen_rust_profile_seen=1
                ;;
            AB_TTS_SYNTH_BIN|AB_TTS_PIPER_PHONEMIZE|AB_TTS_STT_BIN)
                validate_machine_executable_literal "$key" "$value"
                ;;
            AB_QWEN3_TTS_RUST_BIN)
                validate_machine_executable_literal "$key" "$value"
                qwen_rust_bin_seen=1
                ;;
            AB_TTS_KOKORO_MODEL|AB_TTS_KOKORO_VOICES|AB_TTS_PIPER_MODEL|\
            AB_TTS_STT_MODEL)
                validate_machine_regular_file_literal "$key" "$value"
                ;;
            AB_QWEN3_TTS_RUST_MODEL_DIR)
                validate_machine_directory_literal "$key" "$value"
                qwen_rust_model_seen=1
                ;;
            AGENT_BRIDGE_ONNX_MODEL_DIR)
                validate_machine_directory_literal "$key" "$value"
                ;;
            *) die "unknown key $key is forbidden in trusted machine environment" ;;
        esac
    done < "$MACHINE_ENV"

    [ -n "$projection" ] ||
        die "trusted machine environment requires AB_SUBSTRATE_PROJECTION"
    case "$projection" in
        bucket_pool)
            [ "$svd_path_seen" = 0 ] ||
                die "AB_SUBSTRATE_SVD_PATH is only allowed with svd projection"
            ;;
        svd)
            [ "$svd_path_seen" = 1 ] ||
                die "svd substrate selection requires AB_SUBSTRATE_SVD_PATH"
            ;;
    esac
    case "$qwen_rust_enabled" in
        1)
            [ "$qwen_rust_bin_seen" = 1 ] && [ "$qwen_rust_model_seen" = 1 ] &&
                [ "$qwen_rust_profile_seen" = 1 ] ||
                die "enabled Qwen3 Rust requires its binary, model directory, and profile"
            ;;
        0|'')
            [ "$qwen_rust_bin_seen" = 0 ] && [ "$qwen_rust_model_seen" = 0 ] &&
                [ "$qwen_rust_profile_seen" = 0 ] ||
                die "Qwen3 Rust assets require AB_QWEN3_TTS_RUST_ENABLED=1"
            ;;
    esac
}

if [ "$MODE" = install ]; then
    validate_private_directory_tree "$DEPLOY_ROOT/bin" "trusted executable"
    validate_private_directory_tree "$(dirname "$ADAPTER")" "trusted audio adapter"
    validate_private_directory_tree "$RUNTIME_ASSETS" "trusted runtime assets"
    validate_private_directory_tree "$(dirname "$MACHINE_ENV")" "trusted configuration"
    validate_private_directory_tree "$RUNTIME_STATE" "trusted runtime state"
    validate_private_directory_tree "$RECEIPT_ROOT" "trusted workload receipt"
    validate_private_directory_tree "$CGROUP_TRANSIENT_ROOT" "trusted cgroup transient state"
    validate_private_directory_tree "$TRUSTED_HOME" "trusted service HOME"
    validate_private_directory_tree "$TRUSTED_XDG_CONFIG_HOME" "trusted XDG configuration root"
    validate_private_directory_tree "$TRUSTED_XDG_DATA_HOME" "trusted XDG data root"
    validate_private_directory_tree "$TRUSTED_XDG_CACHE_HOME" "trusted XDG cache root"
    validate_private_directory_tree "$TRUSTED_XDG_STATE_HOME" "trusted XDG state root"
    validate_private_directory_tree "$TRUSTED_TMPDIR" "trusted service temporary root"
    validate_installed_file "$WRAPPER" 755 "trusted wrapper"
    validate_installed_file "$REAL_BIN" 755 "trusted real binary"
    validate_installed_file "$ADAPTER" 755 "trusted audio adapter"
    for audio_companion in "${AUDIO_ADAPTER_COMPANION_FILES[@]}"; do
        validate_installed_file "$(dirname "$ADAPTER")/$audio_companion" 755 \
            "trusted audio adapter companion $audio_companion"
    done
    for audio_policy in "${AUDIO_POLICY_FILES[@]}"; do
        audio_policy_path="$DEPLOY_ROOT/share/$audio_policy"
        validate_private_directory_tree "$(dirname "$audio_policy_path")" \
            "trusted audio policy"
        validate_installed_file "$audio_policy_path" 644 "trusted audio policy $audio_policy"
    done
    for runtime_asset in "${RUNTIME_ASSET_FILES[@]}"; do
        validate_installed_file "$RUNTIME_ASSETS/$runtime_asset" 755 \
            "trusted runtime asset $runtime_asset"
    done
    validate_installed_file "$MACHINE_ENV" 600 "trusted machine environment"
    validate_machine_environment_contract
    if [ -e "$CREDENTIALS" ] || [ -L "$CREDENTIALS" ]; then
        validate_installed_file "$CREDENTIALS" 600 "trusted credentials"
    fi
    if [ "$SYSTEMD_BIND_TEST_MODE" = 0 ]; then
        validate_installed_candidate_assets
    fi
fi

units=(
    agent-bridge-daemon.service
    agent-bridge-daemon-http.service
    agent-bridge-palace.service
)
commands=(
    "$WRAPPER daemon"
    "$WRAPPER daemon-http --listen 0.0.0.0:7878"
    "$WRAPPER palace serve --port 7979"
)
descriptions=(
    "Agent-Bridge trusted state daemon"
    "Agent-Bridge trusted daemon HTTP endpoint"
    "Agent-Bridge trusted Palace viewer"
)
after_units=(
    "network.target"
    "network.target agent-bridge-daemon.service"
    "network.target agent-bridge-daemon.service"
)
before_units=(
    "agent-bridge-daemon-http.service agent-bridge-palace.service"
    ""
    ""
)
memory_high=(4G 4G 1G)
UNSET_ENVIRONMENT_NAMES=(
    LD_PRELOAD
    LD_LIBRARY_PATH
    LD_AUDIT
    LD_DEBUG
    LD_PROFILE
    GCONV_PATH
    LOCPATH
    NLSPATH
    BASH_ENV
    ENV
    SHELLOPTS
    BASHOPTS
    CDPATH
    GLOBIGNORE
    PYTHONPATH
    PYTHONHOME
    PERL5LIB
    RUBYLIB
    NODE_OPTIONS
    NODE_PATH
    RUSTC_WRAPPER
)

expected_environment() {
    printf '%s\n' \
        "AGENT_BRIDGE_DEPLOY_ROOT=$DEPLOY_ROOT" \
        "AGENT_BRIDGE_INSTALL_DIR=$DEPLOY_ROOT/bin" \
        "AGENT_BRIDGE_REAL_BIN=$REAL_BIN" \
        "AGENT_BRIDGE_STATE_DIR=$RUNTIME_STATE" \
        "AGENT_BRIDGE_CGROUP_RECEIPT_DIR=$RECEIPT_ROOT" \
        "AGENT_BRIDGE_CGROUP_TRANSIENT_DIR=$CGROUP_TRANSIENT_ROOT" \
        "AGENT_BRIDGE_AUDIO_EMBODY_SCRIPT=$ADAPTER" \
        "AGENT_BRIDGE_RUNTIME_ASSET_DIR=$RUNTIME_ASSETS" \
        "AGENT_BRIDGE_MACHINE_ENV=$MACHINE_ENV" \
        "AGENT_BRIDGE_CREDS_FILE=$CREDENTIALS" \
        "HOME=$TRUSTED_HOME" \
        "XDG_CONFIG_HOME=$TRUSTED_XDG_CONFIG_HOME" \
        "XDG_DATA_HOME=$TRUSTED_XDG_DATA_HOME" \
        "XDG_CACHE_HOME=$TRUSTED_XDG_CACHE_HOME" \
        "XDG_STATE_HOME=$TRUSTED_XDG_STATE_HOME" \
        "TMPDIR=$TRUSTED_TMPDIR" \
        "XDG_RUNTIME_DIR=$SYSTEMD_RUNTIME_DIR" \
        "DBUS_SESSION_BUS_ADDRESS=unix:path=$SYSTEMD_RUNTIME_DIR/bus" \
        "LANG=C.UTF-8" \
        "USER=$ACCOUNT_NAME" \
        "LOGNAME=$ACCOUNT_NAME" \
        "PATH=$DEPLOY_ROOT/bin:/usr/bin:/bin"
}

trusted_exec_command() {
    local index="$1" token
    printf '%s' '/usr/bin/env -i'
    while IFS= read -r token; do
        [ -n "$token" ] || continue
        printf ' %s' "$token"
    done < <(expected_environment)
    printf ' %s\n' "${commands[$index]}"
}

unit_body() {
    local index="$1" before_line="" exec_command
    [ -z "${before_units[$index]}" ] || before_line="Before=${before_units[$index]}"
    exec_command="$(trusted_exec_command "$index")"
    cat <<EOF
[Unit]
Description=${descriptions[$index]}
DefaultDependencies=yes
After=${after_units[$index]}
$before_line

[Service]
Type=simple
Slice=app.slice
UMask=0077
NoNewPrivileges=yes
ProtectSystem=strict
PrivateTmp=yes
InaccessiblePaths=/home /root
ReadOnlyPaths=$DEPLOY_ROOT $SYSTEMD_RUNTIME_DIR
ReadWritePaths=$RUNTIME_STATE
RestrictSUIDSGID=yes
LockPersonality=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
CapabilityBoundingSet=
AmbientCapabilities=
Environment=AGENT_BRIDGE_DEPLOY_ROOT=$DEPLOY_ROOT
Environment=AGENT_BRIDGE_INSTALL_DIR=$DEPLOY_ROOT/bin
Environment=AGENT_BRIDGE_REAL_BIN=$REAL_BIN
Environment=AGENT_BRIDGE_STATE_DIR=$RUNTIME_STATE
Environment=AGENT_BRIDGE_CGROUP_RECEIPT_DIR=$RECEIPT_ROOT
Environment=AGENT_BRIDGE_CGROUP_TRANSIENT_DIR=$CGROUP_TRANSIENT_ROOT
Environment=AGENT_BRIDGE_AUDIO_EMBODY_SCRIPT=$ADAPTER
Environment=AGENT_BRIDGE_RUNTIME_ASSET_DIR=$RUNTIME_ASSETS
Environment=AGENT_BRIDGE_MACHINE_ENV=$MACHINE_ENV
Environment=AGENT_BRIDGE_CREDS_FILE=$CREDENTIALS
Environment=HOME=$TRUSTED_HOME
Environment=XDG_CONFIG_HOME=$TRUSTED_XDG_CONFIG_HOME
Environment=XDG_DATA_HOME=$TRUSTED_XDG_DATA_HOME
Environment=XDG_CACHE_HOME=$TRUSTED_XDG_CACHE_HOME
Environment=XDG_STATE_HOME=$TRUSTED_XDG_STATE_HOME
Environment=TMPDIR=$TRUSTED_TMPDIR
Environment=XDG_RUNTIME_DIR=$SYSTEMD_RUNTIME_DIR
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=$SYSTEMD_RUNTIME_DIR/bus
Environment=LANG=C.UTF-8
Environment=USER=$ACCOUNT_NAME
Environment=LOGNAME=$ACCOUNT_NAME
Environment=PATH=$DEPLOY_ROOT/bin:/usr/bin:/bin
UnsetEnvironment=${UNSET_ENVIRONMENT_NAMES[*]}
WorkingDirectory=$DEPLOY_ROOT
ExecStart=$exec_command
Restart=on-failure
RestartPreventExitStatus=78
RestartSec=5
OOMScoreAdjust=-100
MemoryHigh=${memory_high[$index]}
StandardOutput=journal
StandardError=journal
TimeoutStartSec=30
TimeoutStopSec=30

[Install]
WantedBy=default.target
EOF
}

validate_systemd_test_root() {
    local raw="$1" temp_base canonical owner mode
    [ -d "$raw" ] && [ ! -L "$raw" ] || die "systemd binding test root must be physical"
    temp_base="$(cd -P "${TMPDIR:-/tmp}" && pwd -P)" || die "cannot resolve system temp root"
    canonical="$(cd -P "$raw" && pwd -P)" || die "cannot resolve systemd binding test root"
    [ "$(dirname "$canonical")" = "$temp_base" ] || die "systemd binding test root must be a direct temp child"
    case "$(basename "$canonical")" in ab-systemd-bind-test.*) ;; *) die "invalid systemd binding test root name" ;; esac
    owner="$(path_owner_uid "$canonical")" || die "cannot inspect systemd binding test root owner"
    mode="$(path_mode "$canonical")" || die "cannot inspect systemd binding test root mode"
    [ "$owner" = "$(id -u)" ] && [ "$mode" = 700 ] ||
        die "systemd binding test root must be euid-owned mode 0700"
    printf '%s\n' "$canonical"
}

case "$SYSTEMD_BIND_TEST_MODE" in
    0)
        [ -z "${AGENT_BRIDGE_SYSTEMD_BIND_TEST_ROOT:-}" ] ||
            die "systemd binding test root requires explicit test mode"
        SYSTEMCTL=/usr/bin/systemctl
        [ -x "$SYSTEMCTL" ] || die "trusted daemon binding requires /usr/bin/systemctl"
        SYSTEMD_RUNTIME_DIR="/run/user/$(id -u)"
        ;;
    1)
        SYSTEMD_TEST_ROOT="$(validate_systemd_test_root "${AGENT_BRIDGE_SYSTEMD_BIND_TEST_ROOT:-}")"
        [ "$DEPLOY_ROOT" = "$SYSTEMD_TEST_ROOT" ] ||
            die "systemd binding test deployment root must equal its isolated test root"
        SYSTEMCTL="$SYSTEMD_TEST_ROOT/fake-systemctl"
        SYSTEMD_RUNTIME_DIR="$SYSTEMD_TEST_ROOT/runtime"
        validate_installed_file "$SYSTEMCTL" 755 "systemd binding test systemctl"
        ;;
esac

SYSTEMD_TEST_FAIL_ACTIVATION="${AGENT_BRIDGE_SYSTEMD_BIND_TEST_FAIL_ACTIVATION:-none}"
if [ "$SYSTEMD_BIND_TEST_MODE" = 0 ]; then
    [ "$SYSTEMD_TEST_FAIL_ACTIVATION" = none ] ||
        die "systemd activation failpoint is test-only"
else
    case "$SYSTEMD_TEST_FAIL_ACTIVATION" in
        none|2|3) ;;
        *) die "systemd activation failpoint must be none, 2, or 3" ;;
    esac
fi

validate_runtime_directory() {
    local path="$1" owner mode
    [ -d "$path" ] && [ ! -L "$path" ] || die "user runtime directory must be physical"
    ! path_has_symlink_component "$path" || die "user runtime directory must not traverse a symlink"
    owner="$(path_owner_uid "$path")" || die "cannot inspect user runtime directory owner"
    mode="$(path_mode "$path")" || die "cannot inspect user runtime directory mode"
    [ "$owner" = "$(id -u)" ] && [ "$mode" = 700 ] ||
        die "user runtime directory must be euid-owned mode 0700"
}

validate_runtime_bus() {
    local path="$1" owner
    [ -S "$path" ] && [ ! -L "$path" ] ||
        die "user runtime bus must be a physical Unix socket"
    ! path_has_symlink_component "$path" ||
        die "user runtime bus must not traverse a symlink"
    owner="$(path_owner_uid "$path")" || die "cannot inspect user runtime bus owner"
    [ "$owner" = "$(id -u)" ] || die "user runtime bus must be owned by the effective user"
}

validate_runtime_parent_directory() {
    local path="$1" label="$2" owner mode
    [ -d "$path" ] && [ ! -L "$path" ] || die "$label must be a physical directory"
    ! path_has_symlink_component "$path" || die "$label must not traverse a symlink"
    owner="$(path_owner_uid "$path")" || die "cannot inspect $label owner"
    [ "$owner" = "$(id -u)" ] || die "$label must be owned by the effective user"
    mode="$(path_mode "$path")" || die "cannot inspect $label mode"
    ! mode_has_group_or_other_write "$mode" || die "$label must not be group/other writable"
}

ensure_runtime_parent_directory() {
    local path="$1" label="$2" expected_mode="$3"
    if [ ! -e "$path" ] && [ ! -L "$path" ]; then
        mkdir -m "$expected_mode" "$path" || die "cannot create $label"
    fi
    validate_runtime_parent_directory "$path" "$label"
    [ "$(path_mode "$path")" = "$expected_mode" ] ||
        die "$label mode must be exact 0$expected_mode"
}

account_home_directory() {
    local uid raw
    uid="$(id -u)"
    raw="$(/usr/bin/getent passwd "$uid" 2>/dev/null | /usr/bin/awk -F: 'NR == 1 { print $6 }')"
    if [ -z "$raw" ] && [ -r /etc/passwd ]; then
        raw="$(/usr/bin/awk -F: -v uid="$uid" '$3 == uid { print $6; exit }' /etc/passwd)"
    fi
    [ -n "$raw" ] || return 1
    printf '%s\n' "$raw"
}

validate_unit_search_path() {
    local path="$1" label="$2" rest part current="" owner mode numeric
    local last_existing="" last_mode=""
    case "$path" in /*) rest="${path#/}" ;; *) die "$label must be absolute: $path" ;; esac
    case "$path" in *//*|*/./*|*/../*|*/.|*/..|*/) die "$label must be canonical: $path" ;; esac
    while [ -n "$rest" ]; do
        case "$rest" in
            */*) part="${rest%%/*}"; rest="${rest#*/}" ;;
            *) part="$rest"; rest="" ;;
        esac
        current="$current/$part"
        if [ ! -e "$current" ] && [ ! -L "$current" ]; then
            if [ -n "$last_mode" ] && mode_has_group_or_other_write "$last_mode"; then
                die "$label missing suffix has a replaceable parent: $last_existing"
            fi
            return 0
        fi
        [ -d "$current" ] && [ ! -L "$current" ] ||
            die "$label component must be a physical directory: $current"
        owner="$(path_owner_uid "$current")" || die "cannot inspect $label owner: $current"
        [ "$owner" = "$(id -u)" ] || [ "$owner" = 0 ] ||
            die "$label component has an untrusted owner: $current"
        mode="$(path_mode "$current")" || die "cannot inspect $label mode: $current"
        numeric=$((8#$mode))
        if [ $((numeric & 8#022)) -ne 0 ]; then
            [ "$owner" = 0 ] && [ $((numeric & 8#1000)) -ne 0 ] ||
                die "$label component is group/other writable: $current"
        fi
        last_existing="$current"
        last_mode="$mode"
    done
    ! mode_has_group_or_other_write "$last_mode" ||
        die "$label final directory is group/other writable: $last_existing"
}

validate_user_unit_search_boundary() {
    local account_home unit_paths path count=0
    if [ "$SYSTEMD_BIND_TEST_MODE" = 0 ]; then
        [ "${XDG_CONFIG_HOME+x}" != x ] || die "production trusted binding rejects caller XDG_CONFIG_HOME"
        [ "${XDG_DATA_HOME+x}" != x ] || die "production trusted binding rejects caller XDG_DATA_HOME"
        [ "${XDG_CONFIG_DIRS+x}" != x ] || die "production trusted binding rejects caller XDG_CONFIG_DIRS"
        [ "${XDG_DATA_DIRS+x}" != x ] || die "production trusted binding rejects caller XDG_DATA_DIRS"
        [ "${SYSTEMD_UNIT_PATH+x}" != x ] || die "production trusted binding rejects caller SYSTEMD_UNIT_PATH"
        account_home="$(account_home_directory)" || die "cannot resolve passwd HOME for user-unit trust"
    else
        account_home="$SYSTEMD_TEST_ROOT/home"
    fi
    validate_unit_search_path "$account_home" "passwd HOME"
    validate_unit_search_path "$account_home/.config/systemd/user" "user configuration unit root"
    validate_unit_search_path "$account_home/.local/share/systemd/user" "user data unit root"
    unit_paths="$(systemctl_manager_value UnitPath)" ||
        die "cannot read the running user manager unit search paths"
    for path in $unit_paths; do
        count=$((count + 1))
        validate_unit_search_path "$path" "effective user unit root"
    done
    [ "$count" -gt 0 ] || die "running user manager unit search path was empty"
}

systemctl_value() {
    local unit="$1" property="$2"
    run_systemctl --user show "$unit" --property="$property" --value
}

systemctl_manager_value() {
    local property="$1"
    run_systemctl --user show --property="$property" --value
}

run_systemctl() {
    local passthrough=() name
    if [ "$SYSTEMD_BIND_TEST_MODE" = 1 ]; then
        for name in \
            AGENT_BRIDGE_FAKE_SYSTEMCTL_FAIL_RELOAD_ONCE \
            AGENT_BRIDGE_FAKE_SYSTEMCTL_INJECT_AFTER_RELOAD \
            AGENT_BRIDGE_FAKE_SYSTEMCTL_TAMPER_AFTER_RELOAD
        do
            if [ "${!name+x}" = x ]; then
                passthrough+=("$name=${!name}")
            fi
        done
    fi
    /usr/bin/env -i \
        HOME="$TRUSTED_HOME" \
        XDG_RUNTIME_DIR="$SYSTEMD_RUNTIME_DIR" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=$SYSTEMD_RUNTIME_DIR/bus" \
        LANG=C \
        PATH=/usr/bin:/bin \
        "${passthrough[@]}" \
        "$SYSTEMCTL" "$@"
}

DEPENDENCY_PROPERTIES=(
    Wants
    WantedBy
    Requires
    RequiredBy
    Requisite
    RequisiteOf
    BindsTo
    BoundBy
    PartOf
    ConsistsOf
    Upholds
    UpheldBy
    Conflicts
    ConflictedBy
    OnFailure
    OnFailureOf
    OnSuccess
    OnSuccessOf
    TriggeredBy
    Triggers
    PropagatesReloadTo
    ReloadPropagatedFrom
    PropagatesStopTo
    StopPropagatedFrom
    JoinsNamespaceOf
)
PREEXISTING_WANTED_BY=()

tokens_are_subset_of() {
    local observed="$1" allowed="$2" token
    for token in $observed; do
        case " $allowed " in *" $token "*) ;; *) return 1 ;; esac
    done
}

tokens_match_exact_set() {
    local observed="$1" expected="$2" observed_count=0 expected_count=0 token
    for token in $observed; do
        observed_count=$((observed_count + 1))
    done
    for token in $expected; do
        expected_count=$((expected_count + 1))
    done
    [ "$observed_count" = "$expected_count" ] || return 1
    tokens_are_subset_of "$observed" "$expected"
}

validate_preexisting_dependency_boundary() {
    local index="$1" unit="$2" property value allowed
    for property in "${DEPENDENCY_PROPERTIES[@]}"; do
        value="$(systemctl_value "$unit" "$property")" || return 1
        case "$property" in
            Requires) allowed="basic.target app.slice" ;;
            Conflicts) allowed="shutdown.target" ;;
            WantedBy)
                allowed="default.target"
                PREEXISTING_WANTED_BY[$index]="$value"
                ;;
            *) allowed="" ;;
        esac
        tokens_are_subset_of "$value" "$allowed" || return 1
    done
}

validate_final_dependency_boundary() {
    local index="$1" unit="$2" property value expected
    for property in "${DEPENDENCY_PROPERTIES[@]}"; do
        value="$(systemctl_value "$unit" "$property")" || return 1
        case "$property" in
            Requires) expected="basic.target app.slice" ;;
            Conflicts) expected="shutdown.target" ;;
            WantedBy) expected="${PREEXISTING_WANTED_BY[$index]}" ;;
            *) expected="" ;;
        esac
        tokens_match_exact_set "$value" "$expected" || return 1
    done
}

verify_effective_unit() {
    local index="$1" unit="${units[$1]}" fragment dropins working exec_value environment
    local property token expected_count observed_count expected_exec unset_environment
    local default_dependencies service_slice hardening_value
    fragment="$(systemctl_value "$unit" FragmentPath)" || return 1
    [ "$fragment" = "$RUNTIME_CONTROL_DIR/$unit" ] || return 1
    ! path_has_symlink_component "$fragment" || return 1
    validate_installed_file "$fragment" 600 "effective complete runtime unit" || return 1
    cmp -s "$fragment" <(unit_body "$index") || return 1
    dropins="$(systemctl_value "$unit" DropInPaths)" || return 1
    [ -z "$dropins" ] || return 1
    validate_final_dependency_boundary "$index" "$unit" || return 1
    default_dependencies="$(systemctl_value "$unit" DefaultDependencies)" || return 1
    [ "$default_dependencies" = yes ] || return 1
    service_slice="$(systemctl_value "$unit" Slice)" || return 1
    [ "$service_slice" = app.slice ] || return 1
    for property in \
        UMask NoNewPrivileges ProtectSystem PrivateTmp RestrictSUIDSGID \
        LockPersonality ProtectKernelTunables ProtectKernelModules ProtectControlGroups
    do
        hardening_value="$(systemctl_value "$unit" "$property")" || return 1
        case "$property" in
            UMask) [ "$hardening_value" = 0077 ] || return 1 ;;
            ProtectSystem) [ "$hardening_value" = strict ] || return 1 ;;
            *) [ "$hardening_value" = yes ] || return 1 ;;
        esac
    done
    hardening_value="$(systemctl_value "$unit" InaccessiblePaths)" || return 1
    tokens_match_exact_set "$hardening_value" "/home /root" || return 1
    hardening_value="$(systemctl_value "$unit" ReadOnlyPaths)" || return 1
    tokens_match_exact_set "$hardening_value" "$DEPLOY_ROOT $SYSTEMD_RUNTIME_DIR" || return 1
    hardening_value="$(systemctl_value "$unit" ReadWritePaths)" || return 1
    [ "$hardening_value" = "$RUNTIME_STATE" ] || return 1
    for property in CapabilityBoundingSet AmbientCapabilities; do
        [ -z "$(systemctl_value "$unit" "$property")" ] || return 1
    done
    working="$(systemctl_value "$unit" WorkingDirectory)" || return 1
    [ "$working" = "$DEPLOY_ROOT" ] || return 1
    for property in ExecCondition ExecStartPre ExecStartPost ExecReload ExecStop ExecStopPost EnvironmentFiles; do
        [ -z "$(systemctl_value "$unit" "$property")" ] || return 1
    done
    exec_value="$(systemctl_value "$unit" ExecStart)" || return 1
    expected_exec="$(trusted_exec_command "$index")"
    case "$exec_value" in
        "{ path=/usr/bin/env ; argv[]=$expected_exec ; ignore_errors=no ;"*) ;;
        *) return 1 ;;
    esac
    observed_count="$(printf '%s\n' "$exec_value" | grep -o '{ path=' | wc -l | tr -d ' ')"
    [ "$observed_count" = 1 ] || return 1
    environment="$(systemctl_value "$unit" Environment)" || return 1
    expected_count=0
    while IFS= read -r token; do
        [ -n "$token" ] || continue
        expected_count=$((expected_count + 1))
        case " $environment " in *" $token "*) ;; *) return 1 ;; esac
    done < <(expected_environment)
    observed_count="$(printf '%s\n' "$environment" | awk '{ print NF }')"
    [ "$observed_count" = "$expected_count" ] || return 1
    unset_environment="$(systemctl_value "$unit" UnsetEnvironment)" || return 1
    expected_count=0
    for token in "${UNSET_ENVIRONMENT_NAMES[@]}"; do
        expected_count=$((expected_count + 1))
        case " $unset_environment " in *" $token "*) ;; *) return 1 ;; esac
    done
    observed_count="$(printf '%s\n' "$unset_environment" | awk '{ print NF }')"
    [ "$observed_count" = "$expected_count" ] || return 1
}

RUNTIME_CONTROL_DIR="$SYSTEMD_RUNTIME_DIR/systemd/user.control"
SYSTEMD_USER_DIR="$SYSTEMD_RUNTIME_DIR/systemd"
runtime_fragment_path() { printf '%s/%s\n' "$RUNTIME_CONTROL_DIR" "$1"; }

validate_existing_runtime_control_tree() {
    if [ -e "$SYSTEMD_USER_DIR" ] || [ -L "$SYSTEMD_USER_DIR" ]; then
        validate_runtime_parent_directory "$SYSTEMD_USER_DIR" "user systemd runtime directory"
    fi
    if [ -e "$RUNTIME_CONTROL_DIR" ] || [ -L "$RUNTIME_CONTROL_DIR" ]; then
        validate_runtime_parent_directory "$RUNTIME_CONTROL_DIR" "user systemd control directory"
        [ "$(path_mode "$RUNTIME_CONTROL_DIR")" = 700 ] ||
            die "user systemd control directory mode must be exact 0700"
    fi
}

prepare_runtime_control_tree() {
    if [ ! -e "$SYSTEMD_USER_DIR" ] && [ ! -L "$SYSTEMD_USER_DIR" ]; then
        mkdir -m 700 "$SYSTEMD_USER_DIR" || die "cannot create user systemd runtime directory"
    fi
    validate_runtime_parent_directory "$SYSTEMD_USER_DIR" "user systemd runtime directory"
    ensure_runtime_parent_directory "$RUNTIME_CONTROL_DIR" "user systemd control directory" 700
}

file_device() { stat -c %d "$1" 2>/dev/null; }

validate_staged_unit() {
    local index="$1" path="$2"
    validate_installed_file "$path" 600 "staged complete runtime unit"
    cmp -s "$path" <(unit_body "$index") ||
        die "staged complete runtime unit differs from its exact template: ${units[$index]}"
}

if [ "$MODE" = dry-run ]; then
    for index in "${!units[@]}"; do
        printf '%s\n' "--- ${units[$index]} (complete current-boot replacement)"
        unit_body "$index"
    done
    printf '%s\n' "Dry run only; no unit or service state was changed."
    exit 0
fi

validate_runtime_directory "$SYSTEMD_RUNTIME_DIR"
validate_runtime_bus "$SYSTEMD_RUNTIME_DIR/bus"
export XDG_RUNTIME_DIR="$SYSTEMD_RUNTIME_DIR"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$SYSTEMD_RUNTIME_DIR/bus"
validate_user_unit_search_boundary
validate_existing_runtime_control_tree

# Foreign drop-ins and dependency-directory injections remain authoritative
# even when the main unit is replaced. Refuse them before the first filesystem
# mutation; migrate required values into the trusted machine.env and archive
# the external unit material explicitly before binding.
for index in "${!units[@]}"; do
    unit="${units[$index]}"
    foreign_dropins="$(systemctl_value "$unit" DropInPaths)" ||
        die "cannot inspect existing drop-ins for $unit"
    [ -z "$foreign_dropins" ] ||
        die "foreign drop-ins must be archived before trusted binding: $unit"
    validate_preexisting_dependency_boundary "$index" "$unit" ||
        die "foreign dependency injection must be archived before trusted binding: $unit"
done

existing_runtime_count=0
for unit in "${units[@]}"; do
    fragment="$(runtime_fragment_path "$unit")"
    if [ -e "$fragment" ] || [ -L "$fragment" ]; then
        existing_runtime_count=$((existing_runtime_count + 1))
    fi
done
if [ "$existing_runtime_count" -gt 0 ]; then
    [ "$existing_runtime_count" = "${#units[@]}" ] ||
        die "partial trusted runtime-unit state exists; inspect before retrying"
    for index in "${!units[@]}"; do
        verify_effective_unit "$index" || die "existing trusted runtime-unit state is not exact"
    done
    printf '%s\n' "Trusted current-boot units already match exactly; services were not restarted."
    exit 0
fi

prepare_runtime_control_tree

STAGE_DIR="$SYSTEMD_RUNTIME_DIR/.agent-bridge-systemd-stage.$$.$RANDOM"
STAGE_CREATED=0
ACTIVATION_CUSTODY=""
RELOAD_ATTEMPTED=0
rollback_runtime_units() {
    local unit fragment staged
    for unit in $ACTIVATION_CUSTODY; do
        fragment="$(runtime_fragment_path "$unit")"
        /usr/bin/rm -f -- "$fragment" 2>/dev/null || true
    done
    if [ "$STAGE_CREATED" -eq 1 ] && [ -d "$STAGE_DIR" ] && [ ! -L "$STAGE_DIR" ]; then
        for unit in "${units[@]}"; do
            staged="$STAGE_DIR/$unit"
            /usr/bin/rm -f -- "$staged" 2>/dev/null || true
        done
        /usr/bin/rmdir "$STAGE_DIR" 2>/dev/null || true
    fi
    if [ "$RELOAD_ATTEMPTED" -eq 1 ]; then
        run_systemctl --user daemon-reload >/dev/null 2>&1 || true
    fi
}
trap 'status=$?; trap - EXIT; [ "$status" -eq 0 ] || rollback_runtime_units; exit "$status"' EXIT

mkdir -m 700 "$STAGE_DIR" || die "cannot create private runtime-unit staging directory"
STAGE_CREATED=1
validate_runtime_parent_directory "$STAGE_DIR" "private runtime-unit staging directory"
[ "$(path_mode "$STAGE_DIR")" = 700 ] || die "private runtime-unit staging directory mode must be exact 0700"
[ "$(file_device "$STAGE_DIR")" = "$(file_device "$RUNTIME_CONTROL_DIR")" ] ||
    die "runtime-unit staging and activation directories must share one filesystem"

for index in "${!units[@]}"; do
    unit="${units[$index]}"
    staged="$STAGE_DIR/$unit"
    [ ! -e "$staged" ] && [ ! -L "$staged" ] || die "runtime-unit staging path already exists: $staged"
    unit_body "$index" > "$staged" || die "cannot render staged complete runtime unit: $unit"
    chmod 600 "$staged" || die "cannot protect staged complete runtime unit: $unit"
    validate_staged_unit "$index" "$staged"
done

for index in "${!units[@]}"; do
    unit="${units[$index]}"
    activation_number=$((index + 1))
    staged="$STAGE_DIR/$unit"
    fragment="$(runtime_fragment_path "$unit")"
    [ ! -e "$fragment" ] && [ ! -L "$fragment" ] ||
        die "runtime fragment appeared after the preflight: $unit"
    ACTIVATION_CUSTODY="${ACTIVATION_CUSTODY:+$ACTIVATION_CUSTODY }$unit"
    [ "$SYSTEMD_TEST_FAIL_ACTIVATION" != "$activation_number" ] ||
        die "test failpoint blocked staged activation $activation_number: $unit"
    /usr/bin/mv -- "$staged" "$fragment" || die "failed to atomically activate complete runtime unit: $unit"
    validate_installed_file "$fragment" 600 "activated complete runtime unit"
done
/usr/bin/rmdir "$STAGE_DIR" || die "cannot retire empty runtime-unit staging directory"
STAGE_CREATED=0

RELOAD_ATTEMPTED=1
run_systemctl --user daemon-reload || die "failed to reload the user service manager"
for index in "${!units[@]}"; do
    verify_effective_unit "$index" ||
        die "effective systemd configuration is not the exact trusted binding: ${units[$index]}"
done

trap - EXIT
printf '%s\n' "Installed and verified complete trusted current-boot units; services were not restarted."
