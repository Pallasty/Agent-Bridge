#!/bin/bash
# Safe, race-resistant deploy of the agent-bridge MCP binary to the canonical
# trusted deployment root (the file the env-injection wrapper exec's).
#
# WHY THIS EXISTS
# ~/.local/bin/agent-bridge.real is a SINGLE shared deploy point. When two lanes
# each build from their own (possibly stale) branch and `cp` over it, the later
# deploy silently clobbers the earlier one's capabilities. 2026-06-03: a
# stale-master avatar/tts build overwrote a freshly-deployed item-3 binary,
# dropping item-3 from live while master source was fine (source-right /
# live-wrong). See lesson_deploy_race_stale_branch_binary_clobber_20260603.
#
# This script enforces the discipline that prevents that:
#   1. build from the LATEST selected remote/master (the superset of every merged lane),
#      never a stale branch;
#   2. re-fetch after the potentially long release build and refuse to deploy
#      when the selected remote/master advanced during that build;
#   3. anti-regression gate: the new binary must still contain every lane
#      feature-marker the CURRENTLY-deployed binary has (catches a stale build);
#   4. back up the current .real before overwriting (so a clobber is recoverable
#      — the clobbering lane on 2026-06-03 did NOT back ours up);
#   5. install repository-matched Python runtime assets at a stable path (the
#      release build worktree is disposable and cannot be a runtime dependency);
#   6. never touch the wrapper (only .real);
#   7. refresh canonical persistent launchd jobs onto the installed binary and
#      verify their declared health endpoints;
#   8. remind to /mcp reconnect (a running MCP server keeps the old binary).
#
# Companion to scripts/wrapper/install.sh (which installs the WRAPPER; this
# installs the BINARY). Honors the same env vars.
#
# Usage:
#   scripts/deploy_from_master.sh              # build latest master, gate, backup, deploy
#   scripts/deploy_from_master.sh --dry-run    # build + gate + show plan, but no backup/cp
#   scripts/deploy_from_master.sh --yes        # skip the interactive confirm
#   scripts/deploy_from_master.sh --admit-fresh-mcp
#                                             # consume one matching pending admission
#                                             # after an independent MCP stdio probe
#   scripts/deploy_from_master.sh --use-binary PATH   # contained regression mode only;
#                                                     # production never admits caller binaries
#
# Env:
#   AGENT_BRIDGE_DEPLOY_ROOT   required pre-existing trusted deployment root.
#                              Production paths are derived only from this root;
#                              there is no implicit HOME fallback.
#   AGENT_BRIDGE_INSTALL_DIR   legacy compatibility assertion; when set in
#                              production it must equal $DEPLOY_ROOT/bin
#   AGENT_BRIDGE_REAL_BIN      legacy compatibility assertion; when set in
#                              production it must equal
#                              $DEPLOY_ROOT/bin/agent-bridge.real
#   AGENT_BRIDGE_AUDIO_EMBODY_PATH installed adapter path
#                              (production: $DEPLOY_ROOT/share/ab-tts/audio_embody.py)
#   AGENT_BRIDGE_RUNTIME_ASSET_DIR stable script directory
#                              (production: $DEPLOY_ROOT/lib/agent-bridge/scripts)
#   CARGO_TARGET_DIR           optional pre-existing private build-cache base
#                              (exact 0700). The publisher appends a deployment-
#                              root fingerprint and master SHA so distinct trust
#                              domains can never share a candidate executable.
#                              Default: /var/tmp/agent-bridge-deploy-target-<uid>.
#   AGENT_BRIDGE_DEPLOY_REMOTE SSH git remote containing the authoritative
#                              governed master (default: gitlab). Production
#                              accepts only the pinned GitLab or GitHub project.
#   AGENT_BRIDGE_DEPLOY_FORCE_REINSTALL=1 plus AGENT_BRIDGE_DEPLOY_FORCE_REASON
#                              re-runs an exact pending candidate intentionally
#   AGENT_BRIDGE_DEPLOY_SUPERSEDE_PENDING=1 plus reason and the exact
#   AGENT_BRIDGE_DEPLOY_SUPERSEDE_EXPECTED_CHALLENGE
#                              replaces a different unverified pending admission
#   AGENT_BRIDGE_DEPLOY_RECOVERY=roll_forward plus reason
#                              resumes a durable failed publisher/handoff from
#                              authoritative remote source (never --use-binary/dry-run)
#
# Production binary, wrapper, assets, and publisher state all derive from the
# single AGENT_BRIDGE_DEPLOY_ROOT trust decision. Legacy leaf overrides may
# only repeat the exact derived path. Synthetic lease-test actions retain their
# isolated path overrides inside the contained regression-test mode.
set -euo pipefail

# Publisher-created directories and transaction files are private from their
# first inode. Individual activation files still receive explicit final modes.
umask 077

LEASE_TEST_MODE="${AGENT_BRIDGE_DEPLOY_LEASE_TEST_MODE:-0}"
case "$LEASE_TEST_MODE" in 0|1) ;; *) printf 'ERROR: AGENT_BRIDGE_DEPLOY_LEASE_TEST_MODE must be 0 or 1\n' >&2; exit 1 ;; esac

# Production orchestration never resolves git, lock, compiler helpers, or
# parsing tools from caller/HOME PATH. Contained tests retain their synthetic
# command shims inside a separately validated OS-temp root.
if [ "$LEASE_TEST_MODE" = 0 ]; then
    PATH=/usr/sbin:/usr/bin:/sbin:/bin
    export PATH
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SCRIPT_PATH="$SCRIPT_DIR/$(basename "${BASH_SOURCE[0]}")"
REPO="$(cd "$SCRIPT_DIR/.." && pwd -P)"
PROVISIONING_TOOL="$REPO/scripts/provision-trusted-deployment-root.py"

if [ "$LEASE_TEST_MODE" = 1 ]; then
    # The contained regression lane deliberately exercises arbitrary leaf
    # paths. validate_lease_test_environment binds every one beneath its
    # physical OS-temp root before it may create state.
    DEPLOY_ROOT_RAW=""
    INSTALL_DIR="${AGENT_BRIDGE_INSTALL_DIR:-$HOME/.local/bin}"
    REAL_PATH="${AGENT_BRIDGE_REAL_BIN:-$INSTALL_DIR/agent-bridge.real}"
    ADAPTER_PATH="${AGENT_BRIDGE_AUDIO_EMBODY_PATH:-$HOME/.local/share/ab-tts/audio_embody.py}"
    RUNTIME_ASSET_DIR="${AGENT_BRIDGE_RUNTIME_ASSET_DIR:-$HOME/.local/lib/agent-bridge/scripts}"
else
    DEPLOY_ROOT_RAW="${AGENT_BRIDGE_DEPLOY_ROOT:-}"
    INSTALL_DIR="$DEPLOY_ROOT_RAW/bin"
    REAL_PATH="$INSTALL_DIR/agent-bridge.real"
    ADAPTER_PATH="$DEPLOY_ROOT_RAW/share/ab-tts/audio_embody.py"
    RUNTIME_ASSET_DIR="$DEPLOY_ROOT_RAW/lib/agent-bridge/scripts"
fi
WRAPPER_PATH="$INSTALL_DIR/agent-bridge"
ASSET_SOURCE_ROOT="$REPO"
ADAPTER_SOURCE="$ASSET_SOURCE_ROOT/scripts/audio_embody.py"
AUDIO_ADAPTER_COMPANIONS=(
    omnivoice_mac_remote_synth.py
    omnivoice_onnx_bundle_synth.py
    omnivoice_onnx_official_decode.py
    omnivoice_tts_synth.py
    qwen3_lan_remote_synth.py
    qwen3_tts_rust_gate.py
    qwen3_tts_synth.py
    tts_canary_router.py
)
AUDIO_POLICY_ASSETS=(
    config/omnivoice-canary.json
    docs/reports/tts-comparison/human-review-decision-owner-2026-08-15.json
)
RUNTIME_ASSETS=(
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
DEPLOY_REMOTE="${AGENT_BRIDGE_DEPLOY_REMOTE:-gitlab}"
MASTER_REF="refs/remotes/$DEPLOY_REMOTE/master"

# Lane feature-markers. The gate asserts: every marker present in the CURRENT
# deployed binary is also present in the NEW one (new may add more — superset OK).
# Add a marker when a lane ships a distinctive capability string.
SENTINELS=(
    "app_control.py"        # protocol-first application control router
    "agent_bridge.app_control.operation_preflight.v0" # journal-only embodied episode admission
    "agent_bridge.app_control.track_settlement.v0" # bounded stable-track proof before durable verification
    "agent_bridge.app_control.wrapper_contract.v1" # action-before-version handshake for mutable media calls
    "agent_bridge.avatar.native_linux.v1" # compiled transparent Linux avatar backend
    "agent_bridge.mobile_projection_wait.v1" # exact Android draw-report receipt, never host-served inference
    "desktop_steer.py"      # steer control plane / cross-process injection (item 3)
    "desktop_action.py"     # computer-use: coordinate action
    "desktop_invoke.py"     # computer-use: AT-SPI semantic invoke
    "desktop_confirm"       # host-confirm phase-2 executor
    "macos_ax_focus_window.swift" # exact rank-1 macOS AX focus transaction
    "avatar_renderer"       # linux avatar renderer backend
    "present_voice"         # voice embodiment (ab-tts/Kokoro)
    "browser_navigate"      # browser CDP surface
    "memory_save"           # core memory
    "forum_post"            # core forum
    "agent_bridge.workload_receipt_commit.v1" # R9 immutable receipt ledger / replay boundary
)

# These markers are required even on a first install or --use-binary deploy;
# the ordinary superset gate only protects capabilities already present in the
# live binary and therefore cannot establish a newly introduced binary/runtime
# contract by itself.
REQUIRED_NEW_BINARY_MARKERS=(
    "agent_bridge.app_control.operation_preflight.v0"
    "agent_bridge.app_control.track_settlement.v0"
    "agent_bridge.app_control.wrapper_contract.v1"
    "agent_bridge.workload_receipt_commit.v1"
)

# Linux production builds must contain the transparent native avatar backend.
# Keep the feature explicit here: Cargo's default feature set intentionally
# remains small, while `linux-live` is only useful with this opt-in backend.
if [ "$(uname -s)" = "Linux" ]; then
    REQUIRED_NEW_BINARY_MARKERS+=("agent_bridge.avatar.native_linux.v1")
fi

DRY_RUN=0
ASSUME_YES=0
ADMIT_FRESH_MCP=0
USE_BINARY=""
DEPLOY_ORIGINAL_ARGS=("$@")
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --yes|-y) ASSUME_YES=1 ;;
        --admit-fresh-mcp) ADMIT_FRESH_MCP=1 ;;
        --use-binary) shift; USE_BINARY="${1:-}";;
        -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
    shift
done

say()  { printf '%s\n' "$*"; }
die()  { LEASE_FAILURE_REASON="$*"; printf 'ERROR: %s\n' "$*" >&2; exit 1; }

if [ "$ADMIT_FRESH_MCP" -eq 1 ]; then
    [ "$DRY_RUN" -eq 0 ] || die "--admit-fresh-mcp cannot be combined with --dry-run"
    [ "$ASSUME_YES" -eq 0 ] || die "--admit-fresh-mcp does not accept --yes"
    [ -z "$USE_BINARY" ] || die "--admit-fresh-mcp cannot be combined with --use-binary"
fi

file_inode() {
    case "$(/usr/bin/uname -s 2>/dev/null || uname -s)" in
        Darwin) stat -f %i "$1" 2>/dev/null ;;
        Linux) stat -c %i "$1" 2>/dev/null ;;
        *) return 1 ;;
    esac
}

file_device() {
    case "$(/usr/bin/uname -s 2>/dev/null || uname -s)" in
        Darwin) stat -f %d "$1" 2>/dev/null ;;
        Linux) stat -c %d "$1" 2>/dev/null ;;
        *) return 1 ;;
    esac
}

file_mode() {
    [ -e "$1" ] || { printf '%s\n' absent; return 0; }
    case "$(/usr/bin/uname -s 2>/dev/null || uname -s)" in
        Darwin) stat -f %Lp "$1" 2>/dev/null ;;
        Linux) stat -c %a "$1" 2>/dev/null ;;
        *) return 1 ;;
    esac
}

file_owner_uid() {
    case "$(/usr/bin/uname -s 2>/dev/null || uname -s)" in
        Darwin) stat -f %u "$1" 2>/dev/null ;;
        Linux) stat -c %u "$1" 2>/dev/null ;;
        *) return 1 ;;
    esac
}

file_size() {
    case "$(/usr/bin/uname -s 2>/dev/null || uname -s)" in
        Darwin) stat -f %z "$1" 2>/dev/null ;;
        Linux) stat -c %s "$1" 2>/dev/null ;;
        *) return 1 ;;
    esac
}

sha256_file() {
    local path="$1"
    [ -f "$path" ] || { printf '%s\n' absent; return 0; }
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$path" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$path" | awk '{print $1}'
    else
        die "sha256sum or shasum is required for publisher lease integrity"
    fi
}

sha256_text() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 | awk '{print $1}'
    else
        die "sha256sum or shasum is required for publisher lease integrity"
    fi
}

publish_exact_receipt() {
    local prepared="$1" target="$2"
    if [ -e "$target" ] || [ -L "$target" ]; then
        [ ! -L "$target" ] && [ -f "$target" ] ||
            die "prebound publisher receipt target is not a physical file: $target"
        [ "$(file_mode "$target")" = 600 ] ||
            die "prebound publisher receipt target mode is not 600: $target"
        cmp -s "$prepared" "$target" ||
            die "prebound publisher receipt already exists with different content: $target"
        rm -f "$prepared"
        return 0
    fi
    mv "$prepared" "$target" || die "cannot atomically publish prebound publisher receipt: $target"
}

canonical_target_path() {
    local path="$1" dir base resolved
    case "$path" in /*) ;; *) path="$PWD/$path" ;; esac
    [ ! -L "$path" ] || [ -e "$path" ] || return 2
    if [ -e "$path" ] && command -v realpath >/dev/null 2>&1; then
        realpath "$path"
        return
    fi
    dir="$(dirname "$path")"
    base="$(basename "$path")"
    [ -d "$dir" ] && [ ! -L "$dir" ] || return 1
    resolved="$(cd -P "$dir" && pwd -P)" || return 1
    printf '%s/%s\n' "$resolved" "$base"
}

process_start_fingerprint() {
    local pid="$1" raw
    if [ -r "/proc/$pid/stat" ]; then
        raw="$(awk '{ sub(/^.*\\) /, ""); print $20 }' "/proc/$pid/stat" 2>/dev/null)"
        [ -n "$raw" ] || return 1
        printf 'linux:%s\n' "$raw" | sha256_text
        return
    fi
    raw="$(LC_ALL=C TZ=UTC ps -p "$pid" -o lstart= 2>/dev/null | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [ -n "$raw" ] || return 1
    printf 'darwin:%s\n' "$raw" | sha256_text
}

process_is_zombie() {
    local pid="$1" state
    if [ -r "/proc/$pid/stat" ]; then
        state="$(awk '{ sub(/^.*\\) /, ""); print $1 }' "/proc/$pid/stat" 2>/dev/null)"
    else
        state="$(LC_ALL=C ps -p "$pid" -o stat= 2>/dev/null | sed 's/^[[:space:]]*//')"
    fi
    case "$state" in Z*) return 0 ;; *) return 1 ;; esac
}

boot_identity() {
    local raw
    if [ -r /proc/sys/kernel/random/boot_id ]; then
        raw="$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)"
    elif command -v sysctl >/dev/null 2>&1; then
        raw="$(LC_ALL=C TZ=UTC sysctl -n kern.boottime 2>/dev/null || true)"
    else
        raw=""
    fi
    [ -n "$raw" ] || return 1
    printf '%s\n' "$raw" | sha256_text
}

utc_now() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }
receipt_stamp() { date -u '+%Y%m%dT%H%M%SZ'; }
clean_field() { printf '%s' "$1" | tr '\r\n' '  '; }

meta_keys() { cut -d= -f1 "$1" 2>/dev/null | paste -sd, -; }
is_sha256_value() { printf '%s\n' "$1" | grep -Eq '^[0-9a-f]{64}$'; }
is_safe_id() {
    [ "${#1}" -ge 1 ] && [ "${#1}" -le 128 ] &&
        printf '%s\n' "$1" | grep -Eq '^[A-Za-z0-9._-]+$'
}
is_safe_candidate() {
    [ "${#1}" -ge 1 ] && [ "${#1}" -le 256 ] &&
        printf '%s\n' "$1" | grep -Eq '^[A-Za-z0-9._:+-]+$'
}
is_failed_phase() {
    case "$1" in acquired|building|prepared|committing|services_verifying|awaiting_fresh_mcp|recovery_required|corrupt_unknown) return 0 ;; *) return 1 ;; esac
}
meta_value() {
    local file="$1" line_no="$2" key="$3" line
    line="$(sed -n "${line_no}p" "$file" 2>/dev/null)"
    case "$line" in "$key="*) printf '%s\n' "${line#*=}" ;; *) return 1 ;; esac
}

# Durable publisher control metadata is executable state, not an ordinary
# parseable text input. Never follow a pre-planted symlink or resume from a
# file that another account (or a later permissive chmod) could replace. The
# enclosing state roots are separately required to be physical exact-0700
# directories; this leaf check closes the corresponding recovery-read gap.
metadata_file_is_trusted() {
    local file="$1" owner mode
    [ -f "$file" ] && [ ! -L "$file" ] || return 1
    owner="$(file_owner_uid "$file" 2>/dev/null)" || return 1
    mode="$(file_mode "$file" 2>/dev/null)" || return 1
    [ "$owner" = "$(id -u)" ] && [ "$mode" = 600 ]
}

read_active_lease() {
    local file="$1" keys
    metadata_file_is_trusted "$file" || return 1
    keys="$(meta_keys "$file")"
    [ "$keys" = "schema,lease_id,pid,process_start_fingerprint,boot_identity,real_path,shared_targets,phase,state_seq,started_at,updated_at,baseline_binary_sha256,candidate_commit,challenge,force_reinstall,force_reason,failed_phase,failure_reason" ] || return 1
    [ "$(wc -l < "$file" | tr -d ' ')" = 18 ] || return 1
    R_SCHEMA="$(meta_value "$file" 1 schema)" || return 1
    R_LEASE_ID="$(meta_value "$file" 2 lease_id)" || return 1
    R_PID="$(meta_value "$file" 3 pid)" || return 1
    R_START="$(meta_value "$file" 4 process_start_fingerprint)" || return 1
    R_BOOT="$(meta_value "$file" 5 boot_identity)" || return 1
    R_REAL_PATH="$(meta_value "$file" 6 real_path)" || return 1
    R_SHARED_TARGETS="$(meta_value "$file" 7 shared_targets)" || return 1
    R_PHASE="$(meta_value "$file" 8 phase)" || return 1
    R_SEQ="$(meta_value "$file" 9 state_seq)" || return 1
    R_STARTED="$(meta_value "$file" 10 started_at)" || return 1
    R_UPDATED="$(meta_value "$file" 11 updated_at)" || return 1
    R_BASELINE="$(meta_value "$file" 12 baseline_binary_sha256)" || return 1
    R_CANDIDATE="$(meta_value "$file" 13 candidate_commit)" || return 1
    R_CHALLENGE="$(meta_value "$file" 14 challenge)" || return 1
    R_FORCE="$(meta_value "$file" 15 force_reinstall)" || return 1
    R_FORCE_REASON="$(meta_value "$file" 16 force_reason)" || return 1
    R_FAILED_PHASE="$(meta_value "$file" 17 failed_phase)" || return 1
    R_FAILURE="$(meta_value "$file" 18 failure_reason)" || return 1
    [ "$R_SCHEMA" = agent_bridge.publisher_lease.v0 ] || return 1
    case "$R_PID" in ''|*[!0-9]*) return 1 ;; esac
    case "$R_SEQ" in ''|*[!0-9]*) return 1 ;; esac
    case "$R_PHASE" in acquired|building|prepared|committing|services_verifying|awaiting_fresh_mcp|recovery_required) ;; *) return 1 ;; esac
    case "$R_FAILED_PHASE" in ''|acquired|building|prepared|committing|services_verifying|awaiting_fresh_mcp|recovery_required) ;; *) return 1 ;; esac
    case "$R_FORCE" in 0|1) ;; *) return 1 ;; esac
    case "$R_REAL_PATH" in /*) ;; *) return 1 ;; esac
    is_safe_id "$R_LEASE_ID" && is_sha256_value "$R_START" && is_sha256_value "$R_BOOT" &&
        [ -n "$R_SHARED_TARGETS" ] &&
        { [ "$R_BASELINE" = absent ] || is_sha256_value "$R_BASELINE"; } &&
        is_sha256_value "$R_CHALLENGE" &&
        { [ "$R_CANDIDATE" = unknown ] || is_safe_candidate "$R_CANDIDATE"; }
}

read_pending_admission() {
    local file="$1" keys
    metadata_file_is_trusted "$file" || return 1
    keys="$(meta_keys "$file")"
    [ "$keys" = "schema,lease_id,challenge,real_path,shared_targets,candidate_commit,installed_binary_sha256,installed_binary_inode,installed_binary_mode,installed_assets_sha256,installed_at,fresh_mcp,force_reinstall,force_reason" ] || return 1
    [ "$(wc -l < "$file" | tr -d ' ')" = 14 ] || return 1
    P_SCHEMA="$(meta_value "$file" 1 schema)" || return 1
    P_LEASE_ID="$(meta_value "$file" 2 lease_id)" || return 1
    P_CHALLENGE="$(meta_value "$file" 3 challenge)" || return 1
    P_REAL_PATH="$(meta_value "$file" 4 real_path)" || return 1
    P_SHARED_TARGETS="$(meta_value "$file" 5 shared_targets)" || return 1
    P_CANDIDATE="$(meta_value "$file" 6 candidate_commit)" || return 1
    P_SHA="$(meta_value "$file" 7 installed_binary_sha256)" || return 1
    P_INODE="$(meta_value "$file" 8 installed_binary_inode)" || return 1
    P_MODE="$(meta_value "$file" 9 installed_binary_mode)" || return 1
    P_ASSETS_SHA="$(meta_value "$file" 10 installed_assets_sha256)" || return 1
    P_INSTALLED_AT="$(meta_value "$file" 11 installed_at)" || return 1
    P_FRESH="$(meta_value "$file" 12 fresh_mcp)" || return 1
    P_FORCE="$(meta_value "$file" 13 force_reinstall)" || return 1
    P_FORCE_REASON="$(meta_value "$file" 14 force_reason)" || return 1
    case "$P_INODE" in ''|*[!0-9]*) return 1 ;; esac
    case "$P_FORCE" in 0|1) ;; *) return 1 ;; esac
    case "$P_MODE" in ''|*[!0-7]*) return 1 ;; esac
    case "$P_REAL_PATH" in /*) ;; *) return 1 ;; esac
    [ "$P_SCHEMA" = agent_bridge.publisher_pending_admission.v0 ] &&
        is_safe_id "$P_LEASE_ID" && [ -n "$P_SHARED_TARGETS" ] &&
        is_safe_candidate "$P_CANDIDATE" &&
        [ "$P_FRESH" = unverified ] && is_sha256_value "$P_SHA" && is_sha256_value "$P_ASSETS_SHA" &&
        is_sha256_value "$P_CHALLENGE"
}

read_recovery_handoff() {
    local file="$1" keys
    metadata_file_is_trusted "$file" || return 1
    keys="$(meta_keys "$file")"
    [ "$keys" = "schema,predecessor_lease_id,predecessor_challenge,predecessor_phase,predecessor_failed_phase,predecessor_boot_identity,predecessor_binary_sha256,successor_lease_id,successor_challenge,successor_stage_path,real_path,shared_targets,started_at,reason" ] || return 1
    [ "$(wc -l < "$file" | tr -d ' ')" = 14 ] || return 1
    H_SCHEMA="$(meta_value "$file" 1 schema)" || return 1
    H_PREDECESSOR_LEASE_ID="$(meta_value "$file" 2 predecessor_lease_id)" || return 1
    H_PREDECESSOR_CHALLENGE="$(meta_value "$file" 3 predecessor_challenge)" || return 1
    H_PREDECESSOR_PHASE="$(meta_value "$file" 4 predecessor_phase)" || return 1
    H_PREDECESSOR_FAILED_PHASE="$(meta_value "$file" 5 predecessor_failed_phase)" || return 1
    H_PREDECESSOR_BOOT="$(meta_value "$file" 6 predecessor_boot_identity)" || return 1
    H_PREDECESSOR_BINARY_SHA="$(meta_value "$file" 7 predecessor_binary_sha256)" || return 1
    H_SUCCESSOR_LEASE_ID="$(meta_value "$file" 8 successor_lease_id)" || return 1
    H_SUCCESSOR_CHALLENGE="$(meta_value "$file" 9 successor_challenge)" || return 1
    H_SUCCESSOR_STAGE_PATH="$(meta_value "$file" 10 successor_stage_path)" || return 1
    H_REAL_PATH="$(meta_value "$file" 11 real_path)" || return 1
    H_SHARED_TARGETS="$(meta_value "$file" 12 shared_targets)" || return 1
    H_STARTED_AT="$(meta_value "$file" 13 started_at)" || return 1
    H_REASON="$(meta_value "$file" 14 reason)" || return 1
    [ "$H_SCHEMA" = agent_bridge.publisher_handoff_intent.v0 ] &&
        is_safe_id "$H_PREDECESSOR_LEASE_ID" && is_sha256_value "$H_PREDECESSOR_CHALLENGE" &&
        is_failed_phase "$H_PREDECESSOR_FAILED_PHASE" &&
        is_sha256_value "$H_PREDECESSOR_BOOT" &&
        { [ "$H_PREDECESSOR_BINARY_SHA" = absent ] || is_sha256_value "$H_PREDECESSOR_BINARY_SHA"; } &&
        is_safe_id "$H_SUCCESSOR_LEASE_ID" && is_sha256_value "$H_SUCCESSOR_CHALLENGE" &&
        { [ "$H_PREDECESSOR_PHASE" = recovery_required ] || [ "$H_PREDECESSOR_PHASE" = corrupt_unknown ]; } &&
        [ "${H_SUCCESSOR_STAGE_PATH#/}" != "$H_SUCCESSOR_STAGE_PATH" ] &&
        [ "${H_REAL_PATH#/}" != "$H_REAL_PATH" ] && [ -n "$H_SHARED_TARGETS" ] && [ -n "$H_REASON" ]
}

read_handoff_completion_intent() {
    local file="$1" keys
    metadata_file_is_trusted "$file" || return 1
    keys="$(meta_keys "$file")"
    [ "$keys" = "schema,successor_lease_id,successor_challenge,successor_candidate_commit,handoff_meta_sha256,quarantine_path,handoff_receipt_path,recovery_receipt_path,started_at" ] || return 1
    [ "$(wc -l < "$file" | tr -d ' ')" = 9 ] || return 1
    HC_SCHEMA="$(meta_value "$file" 1 schema)" || return 1
    HC_SUCCESSOR_LEASE_ID="$(meta_value "$file" 2 successor_lease_id)" || return 1
    HC_SUCCESSOR_CHALLENGE="$(meta_value "$file" 3 successor_challenge)" || return 1
    HC_SUCCESSOR_CANDIDATE="$(meta_value "$file" 4 successor_candidate_commit)" || return 1
    HC_META_SHA="$(meta_value "$file" 5 handoff_meta_sha256)" || return 1
    HC_QUARANTINE="$(meta_value "$file" 6 quarantine_path)" || return 1
    HC_HANDOFF_RECEIPT="$(meta_value "$file" 7 handoff_receipt_path)" || return 1
    HC_RECOVERY_RECEIPT="$(meta_value "$file" 8 recovery_receipt_path)" || return 1
    HC_STARTED_AT="$(meta_value "$file" 9 started_at)" || return 1
    [ "$HC_SCHEMA" = agent_bridge.publisher_handoff_completion_intent.v0 ] &&
        is_safe_id "$HC_SUCCESSOR_LEASE_ID" && is_sha256_value "$HC_SUCCESSOR_CHALLENGE" &&
        is_safe_candidate "$HC_SUCCESSOR_CANDIDATE" && is_sha256_value "$HC_META_SHA" &&
        [ "${HC_QUARANTINE#/}" != "$HC_QUARANTINE" ] &&
        [ "${HC_HANDOFF_RECEIPT#/}" != "$HC_HANDOFF_RECEIPT" ] &&
        [ "${HC_RECOVERY_RECEIPT#/}" != "$HC_RECOVERY_RECEIPT" ] && [ -n "$HC_STARTED_AT" ]
}

read_release_intent() {
    local file="$1" keys
    metadata_file_is_trusted "$file" || return 1
    keys="$(meta_keys "$file")"
    [ "$keys" = "schema,lease_id,challenge,disposition,reason,quarantine_path,active_meta_sha256,current_binary_sha256,current_binary_inode,receipt_path,real_path,shared_targets,started_at" ] || return 1
    [ "$(wc -l < "$file" | tr -d ' ')" = 13 ] || return 1
    Q_SCHEMA="$(meta_value "$file" 1 schema)" || return 1
    Q_LEASE_ID="$(meta_value "$file" 2 lease_id)" || return 1
    Q_CHALLENGE="$(meta_value "$file" 3 challenge)" || return 1
    Q_DISPOSITION="$(meta_value "$file" 4 disposition)" || return 1
    Q_REASON="$(meta_value "$file" 5 reason)" || return 1
    Q_QUARANTINE="$(meta_value "$file" 6 quarantine_path)" || return 1
    Q_META_SHA="$(meta_value "$file" 7 active_meta_sha256)" || return 1
    Q_CURRENT_SHA="$(meta_value "$file" 8 current_binary_sha256)" || return 1
    Q_CURRENT_INODE="$(meta_value "$file" 9 current_binary_inode)" || return 1
    Q_RECEIPT="$(meta_value "$file" 10 receipt_path)" || return 1
    Q_REAL_PATH="$(meta_value "$file" 11 real_path)" || return 1
    Q_SHARED_TARGETS="$(meta_value "$file" 12 shared_targets)" || return 1
    Q_STARTED_AT="$(meta_value "$file" 13 started_at)" || return 1
    case "$Q_CURRENT_INODE" in absent) ;; ''|*[!0-9]*) return 1 ;; esac
    [ "$Q_SCHEMA" = agent_bridge.publisher_release_intent.v0 ] &&
        is_safe_id "$Q_LEASE_ID" && is_sha256_value "$Q_CHALLENGE" && is_safe_id "$Q_DISPOSITION" &&
        [ -n "$Q_REASON" ] && is_sha256_value "$Q_META_SHA" &&
        { [ "$Q_CURRENT_SHA" = absent ] || is_sha256_value "$Q_CURRENT_SHA"; } &&
        [ "${Q_QUARANTINE#/}" != "$Q_QUARANTINE" ] && [ "${Q_RECEIPT#/}" != "$Q_RECEIPT" ] &&
        [ "${Q_REAL_PATH#/}" != "$Q_REAL_PATH" ] &&
        [ -n "$Q_SHARED_TARGETS" ] && [ -n "$Q_STARTED_AT" ]
}

path_has_symlink_component() {
    local path="$1" rest part current=""
    case "$path" in /*) rest="${path#/}" ;; *) return 0 ;; esac
    while [ -n "$rest" ]; do
        case "$rest" in */*) part="${rest%%/*}"; rest="${rest#*/}" ;; *) part="$rest"; rest="" ;; esac
        [ -n "$part" ] || continue
        current="$current/$part"
        [ ! -L "$current" ] || return 0
    done
    return 1
}

mode_value() {
    local mode="$1"
    case "$mode" in ''|*[!0-7]*) return 1 ;; esac
    printf '%s\n' "$((8#$mode))"
}

validate_trusted_deploy_root() {
    local raw="$1" canonical euid owner mode numeric ancestor
    [ -n "$raw" ] || die "AGENT_BRIDGE_DEPLOY_ROOT must not be empty"
    case "$raw" in
        *[!A-Za-z0-9._/-]*)
            die "AGENT_BRIDGE_DEPLOY_ROOT contains an unsupported character"
            ;;
    esac
    case "$raw" in /*) ;; *) die "AGENT_BRIDGE_DEPLOY_ROOT must be absolute: $raw" ;; esac
    [ -d "$raw" ] && [ ! -L "$raw" ] ||
        die "AGENT_BRIDGE_DEPLOY_ROOT must be a pre-existing physical directory: $raw"
    ! path_has_symlink_component "$raw" ||
        die "AGENT_BRIDGE_DEPLOY_ROOT must not traverse a symlink: $raw"
    canonical="$(cd -P "$raw" && pwd -P)" ||
        die "cannot canonicalize AGENT_BRIDGE_DEPLOY_ROOT: $raw"
    [ "$raw" = "$canonical" ] ||
        die "AGENT_BRIDGE_DEPLOY_ROOT must be an absolute canonical path: $raw"

    euid="$(id -u)"
    owner="$(file_owner_uid "$canonical")" ||
        die "cannot inspect AGENT_BRIDGE_DEPLOY_ROOT owner: $canonical"
    [ "$owner" = "$euid" ] ||
        die "AGENT_BRIDGE_DEPLOY_ROOT must be owned by euid $euid: $canonical"
    mode="$(file_mode "$canonical")" ||
        die "cannot inspect AGENT_BRIDGE_DEPLOY_ROOT mode: $canonical"
    numeric="$(mode_value "$mode")" ||
        die "cannot parse AGENT_BRIDGE_DEPLOY_ROOT mode: $canonical"
    [ "$mode" = 700 ] ||
        die "AGENT_BRIDGE_DEPLOY_ROOT mode must be exact 0700: $canonical (mode $mode)"

    ancestor="$(dirname "$canonical")"
    while :; do
        [ -d "$ancestor" ] && [ ! -L "$ancestor" ] ||
            die "AGENT_BRIDGE_DEPLOY_ROOT ancestor is not a physical directory: $ancestor"
        owner="$(file_owner_uid "$ancestor")" ||
            die "cannot inspect AGENT_BRIDGE_DEPLOY_ROOT ancestor owner: $ancestor"
        [ "$owner" = "$euid" ] || [ "$owner" = 0 ] ||
            die "AGENT_BRIDGE_DEPLOY_ROOT ancestor must be owned by euid $euid or root: $ancestor"
        mode="$(file_mode "$ancestor")" ||
            die "cannot inspect AGENT_BRIDGE_DEPLOY_ROOT ancestor mode: $ancestor"
        numeric="$(mode_value "$mode")" ||
            die "cannot parse AGENT_BRIDGE_DEPLOY_ROOT ancestor mode: $ancestor"
        if [ $((numeric & 0022)) -ne 0 ]; then
            [ "$owner" = 0 ] && [ $((numeric & 01000)) -ne 0 ] ||
                die "AGENT_BRIDGE_DEPLOY_ROOT ancestor is group/other writable without a root-owned sticky boundary: $ancestor (mode $mode)"
        fi
        [ "$ancestor" = / ] && break
        ancestor="$(dirname "$ancestor")"
    done
    DEPLOY_ROOT="$canonical"
}

validate_legacy_leaf_override() {
    local name="$1" present="$2" raw="$3" expected="$4"
    [ -z "$present" ] || [ "$raw" = "$expected" ] ||
        die "$name diverges from AGENT_BRIDGE_DEPLOY_ROOT; expected exact path: $expected"
}

verify_owned_directory_mode() {
    local path="$1" expected_mode="$2" label="$3" euid owner mode
    [ -d "$path" ] && [ ! -L "$path" ] || die "$label is not a physical directory: $path"
    euid="$(id -u)"
    owner="$(file_owner_uid "$path")" || die "cannot inspect $label owner: $path"
    [ "$owner" = "$euid" ] || die "$label must be owned by euid $euid: $path"
    mode="$(file_mode "$path")" || die "cannot inspect $label mode: $path"
    [ "$mode" = "$expected_mode" ] || die "$label mode must be $expected_mode: $path (mode $mode)"
}

protect_owned_directory() {
    local path="$1" label="$2"
    chmod 700 "$path" || die "cannot protect $label: $path"
    verify_owned_directory_mode "$path" 700 "$label"
}

verify_owned_regular_mode() {
    local path="$1" expected_mode="$2" label="$3" euid owner mode
    [ -f "$path" ] && [ ! -L "$path" ] || die "$label is not a physical regular file: $path"
    euid="$(id -u)"
    owner="$(file_owner_uid "$path")" || die "cannot inspect $label owner: $path"
    [ "$owner" = "$euid" ] || die "$label must be owned by euid $euid: $path"
    mode="$(file_mode "$path")" || die "cannot inspect $label mode: $path"
    [ "$mode" = "$expected_mode" ] || die "$label mode must be $expected_mode: $path (mode $mode)"
}

verify_owned_socket_mode() {
    local path="$1" expected_mode="$2" label="$3" euid owner mode
    [ -S "$path" ] && [ ! -L "$path" ] || die "$label is not a physical socket: $path"
    euid="$(id -u)"
    owner="$(file_owner_uid "$path")" || die "cannot inspect $label owner: $path"
    [ "$owner" = "$euid" ] || die "$label must be owned by euid $euid: $path"
    mode="$(file_mode "$path")" || die "cannot inspect $label mode: $path"
    [ "$mode" = "$expected_mode" ] || die "$label mode must be $expected_mode: $path (mode $mode)"
}

validate_trusted_agent_socket_path() {
    local path="$1" label="$2" euid owner mode numeric ancestor
    case "$path" in
        /*) ;;
        *) die "$label path must be absolute: $path" ;;
    esac
    case "$path" in
        *[!A-Za-z0-9._/-]*|*//*|*/./*|*/../*|*/.|*/..|*/)
            die "$label path is not canonical and shell-safe: $path"
            ;;
    esac
    ! path_has_symlink_component "$path" || die "$label path must not traverse a symlink: $path"
    verify_owned_socket_mode "$path" 600 "$label"
    euid="$(id -u)"
    ancestor="$(dirname "$path")"
    while :; do
        [ -d "$ancestor" ] && [ ! -L "$ancestor" ] ||
            die "$label ancestor is not a physical directory: $ancestor"
        owner="$(file_owner_uid "$ancestor")" || die "cannot inspect $label ancestor owner: $ancestor"
        [ "$owner" = "$euid" ] || [ "$owner" = 0 ] ||
            die "$label ancestor has an untrusted owner: $ancestor"
        mode="$(file_mode "$ancestor")" || die "cannot inspect $label ancestor mode: $ancestor"
        numeric="$(mode_value "$mode")" || die "cannot parse $label ancestor mode: $ancestor"
        if [ $((numeric & 0022)) -ne 0 ]; then
            [ "$owner" = 0 ] && [ $((numeric & 01000)) -ne 0 ] ||
                die "$label ancestor is replaceable: $ancestor (mode $mode)"
        fi
        [ "$ancestor" = / ] && break
        ancestor="$(dirname "$ancestor")"
    done
}

ensure_physical_directory_path() {
    local path="$1" rest part current=""
    case "$path" in /*) rest="${path#/}" ;; *) die "physical directory path must be absolute: $path" ;; esac
    while [ -n "$rest" ]; do
        case "$rest" in */*) part="${rest%%/*}"; rest="${rest#*/}" ;; *) part="$rest"; rest="" ;; esac
        [ -n "$part" ] || continue
        case "$part" in .|..) die "physical directory path contains a non-canonical component: $path" ;; esac
        current="$current/$part"
        if [ -e "$current" ] || [ -L "$current" ]; then
            [ -d "$current" ] && [ ! -L "$current" ] ||
                die "trusted path component is not a physical directory: $current"
        else
            mkdir "$current" || die "cannot create trusted directory component: $current"
            [ -d "$current" ] && [ ! -L "$current" ] ||
                die "created trusted path component is not a physical directory: $current"
        fi
    done
}

ensure_trusted_subdirectory_path() {
    local root="$1" path="$2" label="$3" relative part current
    case "$path" in
        "$root") verify_owned_directory_mode "$root" 700 "$label root"; return 0 ;;
        "$root"/*) relative="${path#"$root"/}" ;;
        *) die "$label escapes its trusted root: $path" ;;
    esac
    current="$root"
    verify_owned_directory_mode "$current" 700 "$label root"
    while [ -n "$relative" ]; do
        case "$relative" in
            */*) part="${relative%%/*}"; relative="${relative#*/}" ;;
            *) part="$relative"; relative="" ;;
        esac
        case "$part" in ''|.|..) die "$label contains a non-canonical path component: $path" ;; esac
        current="$current/$part"
        if [ -e "$current" ] || [ -L "$current" ]; then
            [ -d "$current" ] && [ ! -L "$current" ] ||
                die "$label component is not a physical directory: $current"
        else
            if ! mkdir -m 700 "$current"; then
                [ -d "$current" ] && [ ! -L "$current" ] ||
                    die "cannot create $label component: $current"
            fi
        fi
        verify_owned_directory_mode "$current" 700 "$label component"
    done
}

validate_existing_trusted_subdirectory_components() {
    local root="$1" path="$2" label="$3" relative part current
    case "$path" in
        "$root") verify_owned_directory_mode "$root" 700 "$label root"; return 0 ;;
        "$root"/*) relative="${path#"$root"/}" ;;
        *) die "$label escapes its trusted root: $path" ;;
    esac
    current="$root"
    verify_owned_directory_mode "$current" 700 "$label root"
    while [ -n "$relative" ]; do
        case "$relative" in
            */*) part="${relative%%/*}"; relative="${relative#*/}" ;;
            *) part="$relative"; relative="" ;;
        esac
        case "$part" in ''|.|..) die "$label contains a non-canonical path component: $path" ;; esac
        current="$current/$part"
        if [ ! -e "$current" ] && [ ! -L "$current" ]; then
            return 0
        fi
        [ -d "$current" ] && [ ! -L "$current" ] ||
            die "$label component is not a physical directory: $current"
        verify_owned_directory_mode "$current" 700 "$label component"
    done
}

validate_private_source_checkout() {
    local expected_repo source_dir invoked_script migration_script systemd_installer
    local local_git_override
    expected_repo="$DEPLOY_ROOT/source/agent-bridge"
    source_dir="$DEPLOY_ROOT/source"
    invoked_script="$SCRIPT_PATH"

    [ "$REPO" = "$expected_repo" ] ||
        die "production deploy must run from the fixed trusted checkout: $expected_repo"
    [ "$invoked_script" = "$expected_repo/scripts/deploy_from_master.sh" ] ||
        die "production deploy must execute the exact trusted orchestrator path: $expected_repo/scripts/deploy_from_master.sh"
    ! path_has_symlink_component "$invoked_script" ||
        die "production deploy script must not traverse a symlink: $invoked_script"
    verify_owned_directory_mode "$source_dir" 700 "trusted source directory"
    verify_owned_directory_mode "$REPO" 700 "trusted source checkout"
    verify_owned_directory_mode "$REPO/.git" 700 "trusted source Git metadata"
    verify_owned_directory_mode "$SCRIPT_DIR" 700 "trusted source scripts directory"
    verify_owned_regular_mode "$invoked_script" 700 "trusted deploy orchestrator"
    [ -x "$invoked_script" ] || die "trusted deploy orchestrator is not executable"
    migration_script="$REPO/scripts/migrate-trusted-runtime-state.py"
    systemd_installer="$REPO/scripts/systemd/install-trusted-daemon-root.sh"
    verify_owned_directory_mode "$REPO/scripts/systemd" 700 \
        "trusted source systemd directory"
    verify_owned_regular_mode "$migration_script" 700 \
        "trusted runtime-state migration orchestrator"
    verify_owned_regular_mode "$PROVISIONING_TOOL" 700 \
        "trusted deployment-root provisioning orchestrator"
    verify_owned_regular_mode "$systemd_installer" 700 \
        "trusted systemd binding orchestrator"
    # `git archive` honors repository-local info attributes, while legacy
    # grafts can rewrite object ancestry. Neither belongs in the root-bound
    # publisher clone: authoritative tree semantics come only from the fetched
    # GitLab objects and committed attributes.
    for local_git_override in "$REPO/.git/info/attributes" "$REPO/.git/info/grafts"; do
        ! path_has_symlink_component "$local_git_override" ||
            die "trusted source Git override path must not traverse a symlink: $local_git_override"
        [ ! -e "$local_git_override" ] && [ ! -L "$local_git_override" ] ||
            die "trusted source Git override must be absent: $local_git_override"
    done
}

verify_trusted_root_provisioning() {
    local inherited_fd="${1:-}" output candidate
    if [ -n "$inherited_fd" ]; then
        output="$(/usr/bin/env -i PATH=/usr/bin:/bin HOME="$DEPLOY_ROOT" \
            PYTHONNOUSERSITE=1 /usr/bin/python3 -I -B "$PROVISIONING_TOOL" verify \
            --deploy-root "$DEPLOY_ROOT" --inherited-lock-fd "$inherited_fd")" ||
            die "trusted-root provisioning receipt verification failed"
    else
        output="$(/usr/bin/env -i PATH=/usr/bin:/bin HOME="$DEPLOY_ROOT" \
            PYTHONNOUSERSITE=1 /usr/bin/python3 -I -B "$PROVISIONING_TOOL" verify \
            --deploy-root "$DEPLOY_ROOT")" ||
            die "trusted-root provisioning receipt verification failed"
    fi
    candidate="$(printf '%s' "$output" | /usr/bin/python3 -I -B -c '
import json, re, sys
try:
    value = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)
if set(value) != {"candidate_commit", "command", "receipt_digest", "schema", "status"}:
    raise SystemExit(1)
if value["schema"] != "agent_bridge.trusted_deployment_root_provisioning_result.v1":
    raise SystemExit(1)
if value["command"] != "verify" or value["status"] != "verified_provisioning_custody":
    raise SystemExit(1)
if not re.fullmatch(r"[0-9a-f]{40}", value["candidate_commit"]):
    raise SystemExit(1)
if not re.fullmatch(r"[0-9a-f]{64}", value["receipt_digest"]):
    raise SystemExit(1)
print(value["candidate_commit"])
')" || die "trusted-root provisioning verifier returned an invalid result"
    if [ -n "${PROVISIONED_SOURCE_CANDIDATE:-}" ] && \
            [ "$candidate" != "$PROVISIONED_SOURCE_CANDIDATE" ]; then
        die "trusted-root source candidate drifted between provisioning checks"
    fi
    PROVISIONED_SOURCE_CANDIDATE="$candidate"
}

validate_trusted_git_configuration() {
    local parsed observed_fingerprint inventory
    case "$DEPLOY_REMOTE" in
        gitlab)
            TRUSTED_GIT_PROVIDER=gitlab
            TRUSTED_GIT_AUTH_SCHEMA=agent_bridge.gitlab_agent_authentication.v1
            TRUSTED_GIT_KEY_FILENAME=gitlab_deploy_key
            TRUSTED_GIT_AGENT_PUBLIC_FILENAME=gitlab_agent_key.pub
            ;;
        github)
            TRUSTED_GIT_PROVIDER=github
            TRUSTED_GIT_AUTH_SCHEMA=agent_bridge.github_agent_authentication.v1
            TRUSTED_GIT_KEY_FILENAME=github_deploy_key
            TRUSTED_GIT_AGENT_PUBLIC_FILENAME=github_agent_key.pub
            ;;
        *) die "production deploy remote is not a governed authority" ;;
    esac
    TRUSTED_GIT_CONFIG_DIR="$DEPLOY_ROOT/config/git"
    TRUSTED_GIT_KEY="$TRUSTED_GIT_CONFIG_DIR/$TRUSTED_GIT_KEY_FILENAME"
    TRUSTED_GIT_AUTH="$TRUSTED_GIT_CONFIG_DIR/authentication.json"
    TRUSTED_GIT_AGENT_PUBLIC_KEY="$TRUSTED_GIT_CONFIG_DIR/$TRUSTED_GIT_AGENT_PUBLIC_FILENAME"
    TRUSTED_GIT_KNOWN_HOSTS="$TRUSTED_GIT_CONFIG_DIR/known_hosts"
    verify_owned_directory_mode "$DEPLOY_ROOT/config" 700 "trusted configuration root"
    verify_owned_directory_mode "$TRUSTED_GIT_CONFIG_DIR" 700 "trusted Git configuration"
    verify_owned_regular_mode "$TRUSTED_GIT_KNOWN_HOSTS" 600 "trusted authority known-hosts file"
    if [ -e "$TRUSTED_GIT_KEY" ] || [ -L "$TRUSTED_GIT_KEY" ]; then
        [ ! -e "$TRUSTED_GIT_AUTH" ] && [ ! -L "$TRUSTED_GIT_AUTH" ] &&
            [ ! -e "$TRUSTED_GIT_AGENT_PUBLIC_KEY" ] && [ ! -L "$TRUSTED_GIT_AGENT_PUBLIC_KEY" ] ||
            die "trusted Git configuration mixes file and agent authentication"
        verify_owned_regular_mode "$TRUSTED_GIT_KEY" 600 "trusted authority deploy key"
        TRUSTED_GIT_AUTH_MODE=file
        TRUSTED_GIT_SSH_COMMAND="/usr/bin/ssh -F /dev/null -o BatchMode=yes -o IdentitiesOnly=yes -o IdentityAgent=none -o IdentityFile=$TRUSTED_GIT_KEY -o UserKnownHostsFile=$TRUSTED_GIT_KNOWN_HOSTS -o GlobalKnownHostsFile=/dev/null -o StrictHostKeyChecking=yes"
        return
    fi
    [ -f "$TRUSTED_GIT_AUTH" ] && [ ! -L "$TRUSTED_GIT_AUTH" ] &&
        [ -f "$TRUSTED_GIT_AGENT_PUBLIC_KEY" ] && [ ! -L "$TRUSTED_GIT_AGENT_PUBLIC_KEY" ] ||
        die "trusted Git configuration has no exact authentication contract"
    verify_owned_regular_mode "$TRUSTED_GIT_AUTH" 600 "trusted authority authentication descriptor"
    verify_owned_regular_mode "$TRUSTED_GIT_AGENT_PUBLIC_KEY" 600 "trusted authority agent public key"
    parsed="$(/usr/bin/python3 -I -B -c '
import json, os, re, sys
def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError
        result[key] = value
    return result
try:
    with open(sys.argv[1], "rb") as handle:
        raw = handle.read(65537)
    if not raw or len(raw) > 65536:
        raise ValueError
    value = json.loads(raw.decode("ascii"), object_pairs_hook=pairs)
except Exception:
    raise SystemExit(1)
if set(value) != {"schema", "mode", "socket_path", "public_key_fingerprint", "public_key_path"}:
    raise SystemExit(1)
socket_path = value["socket_path"]
fingerprint = value["public_key_fingerprint"]
if value["schema"] != sys.argv[2] or value["mode"] != "agent_socket":
    raise SystemExit(1)
if value["public_key_path"] != sys.argv[3]:
    raise SystemExit(1)
if not isinstance(socket_path, str) or os.path.normpath(socket_path) != socket_path:
    raise SystemExit(1)
if not re.fullmatch(r"/[A-Za-z0-9._/-]+", socket_path):
    raise SystemExit(1)
if not isinstance(fingerprint, str) or not re.fullmatch(r"SHA256:[A-Za-z0-9+/]{43}", fingerprint):
    raise SystemExit(1)
print(socket_path + "\t" + fingerprint)
' "$TRUSTED_GIT_AUTH" "$TRUSTED_GIT_AUTH_SCHEMA" "$TRUSTED_GIT_AGENT_PUBLIC_FILENAME")" ||
        die "trusted authority authentication descriptor is invalid"
    IFS=$'\t' read -r TRUSTED_GIT_AGENT_SOCKET TRUSTED_GIT_AGENT_FINGERPRINT <<< "$parsed"
    [ -n "$TRUSTED_GIT_AGENT_SOCKET" ] && [ -n "$TRUSTED_GIT_AGENT_FINGERPRINT" ] ||
        die "trusted authority authentication descriptor is incomplete"
    validate_trusted_agent_socket_path "$TRUSTED_GIT_AGENT_SOCKET" "trusted authority agent socket"
    observed_fingerprint="$(/usr/bin/env -i PATH=/usr/bin:/bin LANG=C LC_ALL=C \
        /usr/bin/ssh-keygen -E sha256 -lf "$TRUSTED_GIT_AGENT_PUBLIC_KEY" 2>/dev/null | \
        /usr/bin/awk 'NR == 1 { print $2 }')" ||
        die "cannot inspect trusted authority agent public key"
    [ "$observed_fingerprint" = "$TRUSTED_GIT_AGENT_FINGERPRINT" ] ||
        die "trusted authority agent public-key fingerprint drifted"
    inventory="$(/usr/bin/env -i PATH=/usr/bin:/bin HOME="$DEPLOY_ROOT" LANG=C LC_ALL=C \
        SSH_AUTH_SOCK="$TRUSTED_GIT_AGENT_SOCKET" /usr/bin/ssh-add -l 2>/dev/null)" ||
        die "trusted authority agent inventory is unavailable"
    printf '%s\n' "$inventory" | /usr/bin/awk -v expected="$TRUSTED_GIT_AGENT_FINGERPRINT" \
        '$2 == expected { found = 1 } END { exit(found ? 0 : 1) }' ||
        die "required trusted authority agent identity is absent"
    TRUSTED_GIT_AUTH_MODE=agent_socket
    TRUSTED_GIT_SSH_COMMAND="/usr/bin/ssh -F /dev/null -o BatchMode=yes -o IdentitiesOnly=yes -o IdentityFile=$TRUSTED_GIT_AGENT_PUBLIC_KEY -o IdentityAgent=$TRUSTED_GIT_AGENT_SOCKET -o UserKnownHostsFile=$TRUSTED_GIT_KNOWN_HOSTS -o GlobalKnownHostsFile=/dev/null -o StrictHostKeyChecking=yes"
}

deploy_git() {
    if [ "$LEASE_TEST_MODE" = 1 ]; then
        command git "$@"
    else
        /usr/bin/env -i \
            PATH=/usr/sbin:/usr/bin:/sbin:/bin \
            HOME="$DEPLOY_ROOT" \
            LANG=C \
            GIT_CONFIG_GLOBAL=/dev/null \
            GIT_ATTR_NOSYSTEM=1 \
            GIT_NO_REPLACE_OBJECTS=1 \
            GIT_PROTOCOL_FROM_USER=0 \
            GIT_TERMINAL_PROMPT=0 \
            GIT_SSH_COMMAND="$TRUSTED_GIT_SSH_COMMAND" \
            /usr/bin/git \
                -c core.hooksPath=/dev/null \
                -c core.attributesFile=/dev/null \
                -c protocol.file.allow=never \
                -c protocol.ext.allow=never \
                "$@"
    fi
}

validate_authoritative_remote() {
    local url
    case "$DEPLOY_REMOTE" in
        ''|*[!A-Za-z0-9._-]*) die "AGENT_BRIDGE_DEPLOY_REMOTE is not a safe remote name" ;;
    esac
    url="$(deploy_git -C "$REPO" remote get-url "$DEPLOY_REMOTE" 2>/dev/null)" ||
        die "configured deploy remote does not exist: $DEPLOY_REMOTE"
    case "$DEPLOY_REMOTE:$url" in
        gitlab:git@gitlab.com:pallasting/agent-bridge.git|gitlab:ssh://git@gitlab.com/pallasting/agent-bridge.git) ;;
        github:git@github.com:pallasting/Agent-Bridge.git|github:ssh://git@github.com/pallasting/Agent-Bridge.git) ;;
        *) die "production deploy remote must be an exact governed SSH URL" ;;
    esac
    AUTHORITATIVE_REMOTE_URL="$url"
}

validate_trusted_build_toolchain() {
    local sysroot canonical_sysroot
    TRUSTED_TOOLCHAIN_ROOT="$DEPLOY_ROOT/toolchain"
    TRUSTED_TOOLCHAIN_BIN="$TRUSTED_TOOLCHAIN_ROOT/bin"
    TRUSTED_CARGO="$TRUSTED_TOOLCHAIN_BIN/cargo"
    TRUSTED_RUSTC="$TRUSTED_TOOLCHAIN_BIN/rustc"
    verify_owned_directory_mode "$TRUSTED_TOOLCHAIN_ROOT" 700 "trusted Rust toolchain"
    verify_owned_directory_mode "$TRUSTED_TOOLCHAIN_BIN" 700 "trusted Rust toolchain bin directory"
    verify_owned_regular_mode "$TRUSTED_CARGO" 700 "trusted Cargo executable"
    verify_owned_regular_mode "$TRUSTED_RUSTC" 700 "trusted rustc executable"
    [ -x "$TRUSTED_CARGO" ] && [ -x "$TRUSTED_RUSTC" ] ||
        die "trusted Rust toolchain executables must be executable"
    sysroot="$(/usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME="$DEPLOY_ROOT" \
        "$TRUSTED_RUSTC" --print sysroot 2>/dev/null)" ||
        die "trusted rustc cannot report its sysroot"
    case "$sysroot" in /*) ;; *) die "trusted rustc reported a non-absolute sysroot" ;; esac
    [ -d "$sysroot" ] && [ ! -L "$sysroot" ] ||
        die "trusted rustc sysroot is not a physical directory: $sysroot"
    ! path_has_symlink_component "$sysroot" ||
        die "trusted rustc sysroot must not traverse a symlink: $sysroot"
    canonical_sysroot="$(cd -P "$sysroot" && pwd -P)" || die "cannot canonicalize trusted rustc sysroot"
    case "$canonical_sysroot" in
        "$TRUSTED_TOOLCHAIN_ROOT"|"$TRUSTED_TOOLCHAIN_ROOT"/*) ;;
        *) die "trusted rustc sysroot escapes the trusted toolchain root" ;;
    esac
}

validate_private_build_base() {
    local raw="$1" canonical euid owner mode numeric ancestor
    [ -n "$raw" ] || die "private Cargo build-cache base must not be empty"
    case "$raw" in
        *[!A-Za-z0-9._/-]*) die "private Cargo build-cache base contains an unsupported character" ;;
    esac
    case "$raw" in /*) ;; *) die "private Cargo build-cache base must be absolute: $raw" ;; esac
    [ -d "$raw" ] && [ ! -L "$raw" ] ||
        die "private Cargo build-cache base must be a pre-existing physical directory: $raw"
    ! path_has_symlink_component "$raw" ||
        die "private Cargo build-cache base must not traverse a symlink: $raw"
    canonical="$(cd -P "$raw" && pwd -P)" || die "cannot canonicalize private Cargo build-cache base: $raw"
    [ "$canonical" = "$raw" ] || die "private Cargo build-cache base must be canonical: $raw"
    euid="$(id -u)"
    owner="$(file_owner_uid "$canonical")" || die "cannot inspect private Cargo build-cache base owner"
    [ "$owner" = "$euid" ] || die "private Cargo build-cache base must be owned by euid $euid: $canonical"
    mode="$(file_mode "$canonical")" || die "cannot inspect private Cargo build-cache base mode"
    [ "$mode" = 700 ] || die "private Cargo build-cache base mode must be exact 0700: $canonical (mode $mode)"
    ancestor="$(dirname "$canonical")"
    while :; do
        [ -d "$ancestor" ] && [ ! -L "$ancestor" ] ||
            die "private Cargo build-cache base ancestor is not a physical directory: $ancestor"
        owner="$(file_owner_uid "$ancestor")" || die "cannot inspect private Cargo build-cache base ancestor owner"
        [ "$owner" = "$euid" ] || [ "$owner" = 0 ] ||
            die "private Cargo build-cache base ancestor has an untrusted owner: $ancestor"
        mode="$(file_mode "$ancestor")" || die "cannot inspect private Cargo build-cache base ancestor mode"
        numeric="$(mode_value "$mode")" || die "cannot parse private Cargo build-cache base ancestor mode"
        if [ $((numeric & 0022)) -ne 0 ]; then
            [ "$owner" = 0 ] && [ $((numeric & 01000)) -ne 0 ] ||
                die "private Cargo build-cache base ancestor is replaceable: $ancestor (mode $mode)"
        fi
        [ "$ancestor" = / ] && break
        ancestor="$(dirname "$ancestor")"
    done
    DEPLOY_TARGET_BASE="$canonical"
}

canonical_contained_test_path() {
    local raw="$1" root="$2" label="$3" probe component suffix="" canonical
    [ -n "$raw" ] || die "publisher lease test $label path is empty"
    case "$raw" in /*) ;; *) raw="$PWD/$raw" ;; esac
    ! path_has_symlink_component "$raw" || die "publisher lease test $label path contains a symlink"
    if [ -e "$raw" ]; then
        canonical="$(realpath "$raw" 2>/dev/null)" || die "cannot canonicalize publisher lease test $label"
    else
        probe="$raw"
        while [ ! -e "$probe" ]; do
            component="$(basename "$probe")"
            case "$component" in ''|.|..) die "publisher lease test $label contains a non-canonical path component" ;; esac
            suffix="/$component$suffix"
            probe="$(dirname "$probe")"
        done
        [ -d "$probe" ] || die "publisher lease test $label descends through a non-directory"
        canonical="$(cd -P "$probe" && pwd -P)$suffix"
    fi
    case "$canonical" in "$root"|"$root"/*) ;; *) die "publisher lease test $label escapes its isolated root" ;; esac
    printf '%s\n' "$canonical"
}

validate_lease_test_environment() {
    local raw_root="$1" temp_base root mode path
    [ -d "$raw_root" ] && [ ! -L "$raw_root" ] || die "publisher lease test root must be a physical directory"
    command -v realpath >/dev/null 2>&1 || die "publisher lease test mode requires realpath"
    temp_base="$(realpath "${TMPDIR:-/tmp}")" || die "cannot establish physical OS temp directory"
    root="$(realpath "$raw_root")" || die "cannot canonicalize publisher lease test root"
    [ "$(dirname "$root")" = "$temp_base" ] || die "publisher lease test root must be a direct child of the physical OS temp directory"
    case "$(basename "$root")" in
        ab-publisher-lease-v0.*|ab-deploy-pinned-assets.*|ab-deploy-postbuild-race.*|ab-deploy-audio-parity.*) ;;
        *) die "publisher lease test root has an invalid name" ;;
    esac
    mode="$(file_mode "$root")"
    [ "$mode" = 700 ] || die "publisher lease test root mode must be 700"
    TEST_PHYSICAL_ROOT="$root"
    canonical_contained_test_path "$HOME" "$root" HOME >/dev/null
    canonical_contained_test_path "$INSTALL_DIR" "$root" install >/dev/null
    canonical_contained_test_path "$REAL_PATH" "$root" real_path >/dev/null
    canonical_contained_test_path "$ADAPTER_PATH" "$root" adapter >/dev/null
    canonical_contained_test_path "$RUNTIME_ASSET_DIR" "$root" runtime_assets >/dev/null
    canonical_contained_test_path "${AGENT_BRIDGE_DEPLOY_STATE_DIR:-}" "$root" state >/dev/null
    if [ -n "$USE_BINARY" ]; then
        # Store the canonical absolute result, not merely a successful check:
        # downstream native-magic/hash/copy tools must never receive a
        # caller-controlled leading-dash or relative operand.
        USE_BINARY="$(canonical_contained_test_path "$USE_BINARY" "$root" use_binary)"
    fi
    for path in "${AGENT_BRIDGE_DEPLOY_LEASE_TEST_PAYLOAD:-}" \
        "${AGENT_BRIDGE_DEPLOY_LEASE_TEST_READY_FILE:-}" \
        "${AGENT_BRIDGE_DEPLOY_LEASE_TEST_MUTATION_LOG:-}" \
        "${AGENT_BRIDGE_DEPLOY_LEASE_TEST_FRESH_MCP_PROBE:-}"; do
        [ -z "$path" ] || canonical_contained_test_path "$path" "$root" artifact >/dev/null
    done
    if [ -z "${AGENT_BRIDGE_DEPLOY_LEASE_TEST_ACTION:-}" ]; then
        canonical_contained_test_path "$REPO" "$root" repository >/dev/null
        canonical_contained_test_path "${CARGO_TARGET_DIR:-$HOME/.cache/agent-bridge-deploy-target}" \
            "$root" cargo_target >/dev/null
    fi
}

preflight_macos_launchagent() {
    local label="$1" expected_mode="$2" domain="gui/$(id -u)" target dump program arguments arg_program arg_mode
    local expected_count observed_count expected_index expected_arg observed_arg
    shift 2
    target="$domain/$label"
    if ! dump="$(launchctl print "$target" 2>&1)"; then
        case "$dump" in
            *"Could not find service"*|*"service not found"*)
                say "launchd service refresh: skipped $label (not loaded)"
                return 1
                ;;
            *) die "cannot inspect launchd service $label: $dump" ;;
        esac
    fi
    program="$(printf '%s\n' "$dump" | awk -F ' = ' '$1 ~ /^[[:space:]]*program$/ { print $2; exit }')"
    [ -n "$program" ] || die "launchd service has no parseable program: $label"

    # Test installs and alternate roots must not restart the host's real jobs.
    case "$program" in
        "$WRAPPER_PATH"|"$REAL_PATH") ;;
        *)
            say "launchd service refresh: skipped $label (program=$program)"
            return 1
            ;;
    esac

    arguments="$(printf '%s\n' "$dump" | awk '
        /^[[:space:]]*arguments = \{/ { inside=1; next }
        inside && /^[[:space:]]*}/ { exit }
        inside { sub(/^[[:space:]]*/, ""); print }
    ')"
    arg_program="$(printf '%s\n' "$arguments" | sed -n '1p')"
    arg_mode="$(printf '%s\n' "$arguments" | sed -n '2p')"
    [ "$arg_program" = "$program" ] ||
        die "launchd service argument program mismatch: $label"
    [ "$arg_mode" = "$expected_mode" ] ||
        die "launchd service mode mismatch: $label (expected $expected_mode, observed ${arg_mode:-none})"
    if [ "$#" -gt 0 ]; then
        observed_count="$(printf '%s\n' "$arguments" | awk 'END { print NR + 0 }')"
        expected_count=$((2 + $#))
        [ "$observed_count" -eq "$expected_count" ] ||
            die "launchd service argument count mismatch: $label (expected $expected_count, observed $observed_count)"
        expected_index=3
        for expected_arg in "$@"; do
            observed_arg="$(printf '%s\n' "$arguments" | sed -n "${expected_index}p")"
            [ "$observed_arg" = "$expected_arg" ] ||
                die "launchd service argument mismatch: $label (position $expected_index, expected $expected_arg, observed ${observed_arg:-none})"
            expected_index=$((expected_index + 1))
        done
    fi
    return 0
}

refresh_macos_launchagent() {
    local label="$1" expected_inode="$2" health_url="${3:-}" health_port="${4:-}" domain="gui/$(id -u)" target
    local dump pid loaded_inode attempt stable_pid stable_count health_ok
    if [ -n "$health_url" ]; then
        case "$health_port" in ''|*[!0-9]*) die "launchd service health port is invalid: $label" ;; esac
        [ "$health_port" -ge 1 ] && [ "$health_port" -le 65535 ] ||
            die "launchd service health port is out of range: $label ($health_port)"
    else
        [ -z "$health_port" ] || die "launchd service health port requires a URL: $label"
    fi
    target="$domain/$label"
    say ">> refreshing launchd service -> $label"
    launchctl kickstart -k "$target" || die "failed to restart launchd service: $label"

    attempt=0
    stable_pid=""
    stable_count=0
    while [ "$attempt" -lt "${AGENT_BRIDGE_SERVICE_VERIFY_ATTEMPTS:-200}" ]; do
        dump="$(launchctl print "$target" 2>/dev/null || true)"
        pid="$(printf '%s\n' "$dump" | awk -F ' = ' '$1 ~ /^[[:space:]]*pid$/ { print $2; exit }')"
        loaded_inode=""
        health_ok=0
        if [ -n "$pid" ]; then
            loaded_inode="$({ lsof -a -p "$pid" -d txt -F in 2>/dev/null || true; } |
                awk -v want="$REAL_PATH" '
                    /^i[0-9]+$/ { inode=substr($0, 2); next }
                    /^n/ && substr($0, 2) == want { print inode; exit }
                ')"
            if [ -z "$health_url" ]; then
                health_ok=1
            elif lsof -nP -a -p "$pid" -iTCP:"$health_port" -sTCP:LISTEN -F p 2>/dev/null |
                    grep -qx "p$pid" &&
                    curl -fsS --max-time 0.2 "$health_url" 2>/dev/null | grep -qx 'ok'; then
                health_ok=1
            fi
            if [ "$loaded_inode" = "$expected_inode" ] && [ "$health_ok" -eq 1 ]; then
                if [ "$pid" = "$stable_pid" ]; then
                    stable_count=$((stable_count + 1))
                else
                    stable_pid="$pid"
                    stable_count=1
                fi
            else
                stable_pid=""
                stable_count=0
            fi
            if [ "$stable_count" -ge 8 ]; then
                say "launchd service stable: OK ($label pid=$pid inode=$loaded_inode${health_url:+ health=$health_url})"
                SERVICE_REFRESHED=$((SERVICE_REFRESHED + 1))
                return 0
            fi
        else
            stable_pid=""
            stable_count=0
        fi
        attempt=$((attempt + 1))
        sleep 0.25
    done

    die "launchd service did not become stable and healthy: $label (expected inode $expected_inode, observed ${loaded_inode:-none}${health_url:+, health $health_url})"
}

# The anti-regression gate depends on `strings` (binutils). If it is missing,
# markers_in would return EMPTY for every binary and the gate would falsely pass
# ("superset" of nothing) — deploying completely unguarded. Fail closed instead.
command -v strings >/dev/null 2>&1 || die "strings (binutils) is required for the regression gate; install binutils"

# pipe-free native-executable check — ELF on Linux, Mach-O on macOS.
# (avoids `head | grep -q` SIGPIPE-under-pipefail flake). The byte magics below
# contain no NUL/newline, so they survive `$(...)` capture + `[ = ]` byte compare.
is_native_exe() {
    local magic
    magic="$(head -c4 "$1" 2>/dev/null)" || return 1
    [ "$magic" = $'\x7fELF' ]           && return 0   # ELF (Linux)
    [ "$magic" = $'\xcf\xfa\xed\xfe' ]  && return 0   # Mach-O 64-bit thin (macOS arm64/x86_64)
    [ "$magic" = $'\xce\xfa\xed\xfe' ]  && return 0   # Mach-O 32-bit thin
    [ "$magic" = $'\xca\xfe\xba\xbe' ]  && return 0   # Mach-O universal (fat, big-endian)
    [ "$magic" = $'\xbe\xba\xfe\xca' ]  && return 0   # Mach-O universal (fat, little-endian)
    return 1
}

# markers present in a binary (intersection with SENTINELS), one per line.
# strings is dumped to a temp file and grep reads the FILE directly — never
# `strings | grep -q`, which under `set -o pipefail` reports failure when grep -q
# closes the pipe early and strings dies of SIGPIPE (the original gate's bug:
# every marker read as "absent", so a stale-build regression sailed through).
markers_in() {
    local bin="$1" m tmp
    tmp="$(mktemp "$DEPLOY_TMPDIR/agent-bridge-markers.XXXXXX")"
    strings -a "$bin" 2>/dev/null > "$tmp" || true
    for m in "${SENTINELS[@]}"; do
        grep -qF -- "$m" "$tmp" && printf '%s\n' "$m"
    done
    rm -f "$tmp"
}

CLEANUP_WT=""
CLEANUP_RUNTIME_STAGE=""
CLEANUP_PKG_CONFIG=""
CLEANUP_BINARY_STAGE=""
CLEANUP_CANDIDATE_SNAPSHOT=""
CLEANUP_DEPLOY_LOCK=""
CLEANUP_LEASE_INTENT=""
CLEANUP_FRESH_MCP_TMP=""
LEASE_OWNED=0
LEASE_FINALIZED=0
LEASE_PHASE=""
LEASE_STATE_SEQ=0
LEASE_CANDIDATE=unknown
LEASE_FAILURE_REASON=""
LEASE_FAILED_PHASE=""
RECOVERY_PREDECESSOR_LEASE_ID=""
RECOVERY_PREDECESSOR_CHALLENGE=""
RECOVERY_PREDECESSOR_PHASE=""
RECOVERY_PREDECESSOR_FAILED_PHASE=""
RECOVERY_PREDECESSOR_BOOT=""
RECOVERY_PREDECESSOR_BINARY_SHA=""
CONSUMED_PENDING_META=""
CONSUMED_PENDING_ACTION=""
CONSUMED_PENDING_LEASE_ID=""
CONSUMED_PENDING_CHALLENGE=""
CONSUMED_PENDING_CANDIDATE=""
FORCE_REINSTALL="${AGENT_BRIDGE_DEPLOY_FORCE_REINSTALL:-0}"
FORCE_REASON="$(clean_field "${AGENT_BRIDGE_DEPLOY_FORCE_REASON:-}")"
case "$FORCE_REINSTALL" in
    0) ;;
    1) [ -n "$FORCE_REASON" ] || die "AGENT_BRIDGE_DEPLOY_FORCE_REASON is required when forcing a reinstall" ;;
    *) die "AGENT_BRIDGE_DEPLOY_FORCE_REINSTALL must be 0 or 1" ;;
esac

SUPERSEDE_PENDING="${AGENT_BRIDGE_DEPLOY_SUPERSEDE_PENDING:-0}"
SUPERSEDE_REASON="$(clean_field "${AGENT_BRIDGE_DEPLOY_SUPERSEDE_REASON:-}")"
SUPERSEDE_EXPECTED_CHALLENGE="${AGENT_BRIDGE_DEPLOY_SUPERSEDE_EXPECTED_CHALLENGE:-}"
case "$SUPERSEDE_PENDING" in
    0) ;;
    1)
        [ -n "$SUPERSEDE_REASON" ] || die "AGENT_BRIDGE_DEPLOY_SUPERSEDE_REASON is required when superseding pending admission"
        is_sha256_value "$SUPERSEDE_EXPECTED_CHALLENGE" ||
            die "AGENT_BRIDGE_DEPLOY_SUPERSEDE_EXPECTED_CHALLENGE must bind the exact pending admission"
        ;;
    *) die "AGENT_BRIDGE_DEPLOY_SUPERSEDE_PENDING must be 0 or 1" ;;
esac

RECOVERY_MODE="${AGENT_BRIDGE_DEPLOY_RECOVERY:-none}"
RECOVERY_REASON="$(clean_field "${AGENT_BRIDGE_DEPLOY_RECOVERY_REASON:-}")"
case "$RECOVERY_MODE" in
    none) ;;
    roll_forward)
        [ -n "$RECOVERY_REASON" ] || die "AGENT_BRIDGE_DEPLOY_RECOVERY_REASON is required for roll-forward recovery"
        [ -z "$USE_BINARY" ] || die "governed roll-forward recovery requires an authoritative remote build, not --use-binary"
        [ "$DRY_RUN" -eq 0 ] || die "governed roll-forward recovery must complete an authoritative install, not a dry-run"
        ;;
    *) die "AGENT_BRIDGE_DEPLOY_RECOVERY must be none or roll_forward" ;;
esac

if [ "$ADMIT_FRESH_MCP" -eq 1 ]; then
    [ "$FORCE_REINSTALL" -eq 0 ] || die "fresh MCP admission cannot force a reinstall"
    [ "$SUPERSEDE_PENDING" -eq 0 ] || die "fresh MCP admission cannot supersede pending state"
    [ "$RECOVERY_MODE" = none ] || die "fresh MCP admission cannot perform publisher recovery"
fi

if [ "$LEASE_TEST_MODE" = 0 ]; then
    validate_trusted_deploy_root "$DEPLOY_ROOT_RAW"
    derived_install="$DEPLOY_ROOT/bin"
    derived_real="$derived_install/agent-bridge.real"
    derived_adapter="$DEPLOY_ROOT/share/ab-tts/audio_embody.py"
    derived_runtime="$DEPLOY_ROOT/lib/agent-bridge/scripts"
    derived_state="$DEPLOY_ROOT/publisher-state/deploy"
    validate_legacy_leaf_override AGENT_BRIDGE_INSTALL_DIR \
        "${AGENT_BRIDGE_INSTALL_DIR+x}" "${AGENT_BRIDGE_INSTALL_DIR-}" "$derived_install"
    validate_legacy_leaf_override AGENT_BRIDGE_REAL_BIN \
        "${AGENT_BRIDGE_REAL_BIN+x}" "${AGENT_BRIDGE_REAL_BIN-}" "$derived_real"
    validate_legacy_leaf_override AGENT_BRIDGE_AUDIO_EMBODY_PATH \
        "${AGENT_BRIDGE_AUDIO_EMBODY_PATH+x}" "${AGENT_BRIDGE_AUDIO_EMBODY_PATH-}" "$derived_adapter"
    validate_legacy_leaf_override AGENT_BRIDGE_RUNTIME_ASSET_DIR \
        "${AGENT_BRIDGE_RUNTIME_ASSET_DIR+x}" "${AGENT_BRIDGE_RUNTIME_ASSET_DIR-}" "$derived_runtime"
    validate_legacy_leaf_override AGENT_BRIDGE_DEPLOY_STATE_DIR \
        "${AGENT_BRIDGE_DEPLOY_STATE_DIR+x}" "${AGENT_BRIDGE_DEPLOY_STATE_DIR-}" "$derived_state"
    INSTALL_DIR="$derived_install"
    REAL_PATH="$derived_real"
    WRAPPER_PATH="$derived_install/agent-bridge"
    ADAPTER_PATH="$derived_adapter"
    RUNTIME_ASSET_DIR="$derived_runtime"
    LEASE_STATE_RAW="$derived_state"
    for trusted_directory in \
        "$derived_install" \
        "$derived_state" \
        "$DEPLOY_ROOT/share/ab-tts" \
        "$derived_runtime"
    do
        validate_existing_trusted_subdirectory_components \
            "$DEPLOY_ROOT" "$trusted_directory" "canonical deployment directory"
    done
    derived_adapter_root="$(dirname "$(dirname "$derived_adapter")")"
    for asset in "${AUDIO_POLICY_ASSETS[@]}"; do
        trusted_policy_target="$derived_adapter_root/$asset"
        validate_existing_trusted_subdirectory_components \
            "$DEPLOY_ROOT" "$(dirname "$trusted_policy_target")" \
            "installed audio policy directory"
        ! path_has_symlink_component "$trusted_policy_target" ||
            die "installed audio policy path must not traverse a symlink: $trusted_policy_target"
    done
    for trusted_target in "$REAL_PATH" "$WRAPPER_PATH" "$ADAPTER_PATH" "$RUNTIME_ASSET_DIR" "$LEASE_STATE_RAW"; do
        ! path_has_symlink_component "$trusted_target" ||
            die "canonical deployment path must not traverse a symlink: $trusted_target"
    done
    # A publisher cannot bootstrap trust while executing from a replaceable
    # development checkout. Production is entered only through the fixed,
    # private clone provisioned beneath the deployment root.
    validate_private_source_checkout
    verify_trusted_root_provisioning
    [ -z "$USE_BINARY" ] ||
        die "--use-binary is disabled for production trusted-root deployment"
    DEPLOY_TARGET_ROOT=""
    if [ -z "$USE_BINARY" ] && [ "$ADMIT_FRESH_MCP" -eq 0 ]; then
        validate_trusted_git_configuration
        validate_authoritative_remote
        validate_trusted_build_toolchain
        if [ "${CARGO_TARGET_DIR+x}" = x ]; then
            validate_private_build_base "$CARGO_TARGET_DIR"
        else
            default_build_parent="$(cd -P /var/tmp 2>/dev/null && pwd -P)" ||
                die "cannot establish the default private Cargo build-cache parent"
            default_build_base="$default_build_parent/agent-bridge-deploy-target-$(id -u)"
            if [ -e "$default_build_base" ] || [ -L "$default_build_base" ]; then
                [ -d "$default_build_base" ] && [ ! -L "$default_build_base" ] ||
                    die "default private Cargo build-cache base is not a physical directory"
            else
                if ! mkdir -m 700 "$default_build_base"; then
                    [ -d "$default_build_base" ] && [ ! -L "$default_build_base" ] ||
                        die "cannot create the default private Cargo build-cache base"
                fi
            fi
            validate_private_build_base "$default_build_base"
        fi
        deploy_root_device="$(file_device "$DEPLOY_ROOT")" ||
            die "cannot inspect deployment-root device identity"
        deploy_root_inode="$(file_inode "$DEPLOY_ROOT")" ||
            die "cannot inspect deployment-root inode identity"
        deploy_root_fingerprint="$(printf '%s\t%s\t%s\n' \
            "$DEPLOY_ROOT" "$deploy_root_device" "$deploy_root_inode" | sha256_text)"
        DEPLOY_TARGET_ROOT="$DEPLOY_TARGET_BASE/root-$deploy_root_fingerprint"
        ensure_trusted_subdirectory_path \
            "$DEPLOY_TARGET_BASE" "$DEPLOY_TARGET_ROOT" "deployment-scoped Cargo build target"
        TRUSTED_CARGO_HOME="$DEPLOY_TARGET_ROOT/cargo-home"
        TRUSTED_BUILD_TMP="$DEPLOY_TARGET_ROOT/tmp"
        ensure_trusted_subdirectory_path \
            "$DEPLOY_TARGET_BASE" "$TRUSTED_CARGO_HOME" "trusted Cargo home"
        ensure_trusted_subdirectory_path \
            "$DEPLOY_TARGET_BASE" "$TRUSTED_BUILD_TMP" "trusted Cargo temporary directory"
    fi
fi

[ ! -L "$REAL_PATH" ] || [ -e "$REAL_PATH" ] ||
    die "deployment target is a dangling final symlink; fail closed: $REAL_PATH"
LEASE_TEST_LIVE_FRESH_MCP="${AGENT_BRIDGE_DEPLOY_LEASE_TEST_LIVE_FRESH_MCP:-0}"
LEASE_TEST_HOLD_AFTER_FRESH_MCP="${AGENT_BRIDGE_DEPLOY_LEASE_TEST_HOLD_AFTER_FRESH_MCP_SETTLED:-0}"
case "$LEASE_TEST_LIVE_FRESH_MCP" in 0|1) ;; *) die "AGENT_BRIDGE_DEPLOY_LEASE_TEST_LIVE_FRESH_MCP must be 0 or 1" ;; esac
case "$LEASE_TEST_HOLD_AFTER_FRESH_MCP" in 0|1) ;; *) die "AGENT_BRIDGE_DEPLOY_LEASE_TEST_HOLD_AFTER_FRESH_MCP_SETTLED must be 0 or 1" ;; esac
if [ "$LEASE_TEST_MODE" != 1 ] &&
        { [ "$LEASE_TEST_LIVE_FRESH_MCP" = 1 ] || [ "$LEASE_TEST_HOLD_AFTER_FRESH_MCP" = 1 ]; }; then
    die "fresh MCP lease-test controls require AGENT_BRIDGE_DEPLOY_LEASE_TEST_MODE=1"
fi
if [ -n "${AGENT_BRIDGE_DEPLOY_LEASE_TEST_ACTION:-}" ] && [ "$LEASE_TEST_MODE" != 1 ]; then
    die "publisher lease test action requires AGENT_BRIDGE_DEPLOY_LEASE_TEST_MODE=1"
fi
if [ "$LEASE_TEST_MODE" = 1 ]; then
    [ -n "${AGENT_BRIDGE_DEPLOY_LEASE_TEST_ROOT:-}" ] ||
        die "publisher lease test mode requires an isolated test root"
    validate_lease_test_environment "$AGENT_BRIDGE_DEPLOY_LEASE_TEST_ROOT"
    DEPLOY_TMPDIR="$TEST_PHYSICAL_ROOT/tmp"
    mkdir -p "$DEPLOY_TMPDIR"
    protect_owned_directory "$DEPLOY_TMPDIR" "publisher lease test temp directory"
else
    DEPLOY_TMPDIR="$DEPLOY_ROOT/publisher-state/tmp"
    ensure_trusted_subdirectory_path \
        "$DEPLOY_ROOT" "$DEPLOY_TMPDIR" "publisher temporary directory"
fi

if [ "$LEASE_TEST_MODE" = 1 ]; then
    LEASE_STATE_RAW="${AGENT_BRIDGE_DEPLOY_STATE_DIR:-}"
else
    ensure_trusted_subdirectory_path \
        "$DEPLOY_ROOT" "$INSTALL_DIR" "canonical deployment bin directory"
    # The publisher owns the persistent workload runtime substrate consumed by
    # both the fixed wrapper and the full user-systemd units. Provision every
    # leaf as an exact physical 0700 directory only after the deployment root,
    # private source, remote configuration, and toolchain gates have passed.
    # The service installer intentionally remains zero-write until its own
    # UnitPath/runtime-bus preflight succeeds, so it must never bootstrap these
    # trust roots itself.
    RUNTIME_STATE_ROOT="$DEPLOY_ROOT/runtime-state"
    ensure_trusted_subdirectory_path \
        "$DEPLOY_ROOT" "$RUNTIME_STATE_ROOT" "workload runtime-state root"
    for runtime_state_leaf in home data cache xdg-state tmp workload-tmp workload-receipts; do
        ensure_trusted_subdirectory_path \
            "$DEPLOY_ROOT" "$RUNTIME_STATE_ROOT/$runtime_state_leaf" \
            "workload runtime-state directory"
    done
fi
REAL_PATH="$(canonical_target_path "$REAL_PATH")" || die "cannot canonicalize deployment target: $REAL_PATH"
[ ! -L "$LEASE_STATE_RAW" ] || die "publisher lease state root must not be a symlink: $LEASE_STATE_RAW"
if [ "$LEASE_TEST_MODE" = 1 ]; then
    ensure_physical_directory_path "$LEASE_STATE_RAW"
else
    ensure_trusted_subdirectory_path \
        "$DEPLOY_ROOT" "$LEASE_STATE_RAW" "publisher state directory"
fi
LEASE_STATE_ROOT="$(cd -P "$LEASE_STATE_RAW" && pwd -P)"
LEASE_RECEIPT_DIR="$LEASE_STATE_ROOT/receipts"
LEASE_QUARANTINE_DIR="$LEASE_STATE_ROOT/quarantine"
LEASE_INTENT_DIR="$LEASE_STATE_ROOT/intents"
PENDING_ADMISSION="$LEASE_STATE_ROOT/pending-admission.meta"
RECOVERY_HANDOFF="$LEASE_STATE_ROOT/recovery-handoff.meta"
HANDOFF_COMPLETION_INTENT="$LEASE_STATE_ROOT/recovery-handoff-completion.meta"
RELEASE_INTENT="$LEASE_STATE_ROOT/release-intent.meta"
FRESH_MCP_ADMISSION_INTENT="$LEASE_STATE_ROOT/fresh-mcp-admission-intent.meta"
deploy_lock="$LEASE_STATE_ROOT/active.lock"
ACTIVE_META="$deploy_lock/lease.meta"
if [ "$LEASE_TEST_MODE" = 1 ]; then
    ensure_physical_directory_path "$LEASE_RECEIPT_DIR"
    ensure_physical_directory_path "$LEASE_QUARANTINE_DIR"
    ensure_physical_directory_path "$LEASE_INTENT_DIR"
else
    ensure_trusted_subdirectory_path "$DEPLOY_ROOT" "$LEASE_RECEIPT_DIR" "publisher receipt directory"
    ensure_trusted_subdirectory_path "$DEPLOY_ROOT" "$LEASE_QUARANTINE_DIR" "publisher quarantine directory"
    ensure_trusted_subdirectory_path "$DEPLOY_ROOT" "$LEASE_INTENT_DIR" "publisher intent directory"
fi
protect_owned_directory "$LEASE_STATE_ROOT" "publisher state root"
protect_owned_directory "$LEASE_RECEIPT_DIR" "publisher receipt directory"
protect_owned_directory "$LEASE_QUARANTINE_DIR" "publisher quarantine directory"
protect_owned_directory "$LEASE_INTENT_DIR" "publisher intent directory"
KERNEL_LOCK_FILE="$LEASE_STATE_ROOT/publisher.kernel.lock"
PUBLISHER_PREVIOUS_UMASK="$(umask)"
umask 077
if [ -e "$KERNEL_LOCK_FILE" ] || [ -L "$KERNEL_LOCK_FILE" ]; then
    verify_owned_regular_mode "$KERNEL_LOCK_FILE" 600 "publisher kernel mutex"
else
    : >"$KERNEL_LOCK_FILE" || die "cannot create the publisher kernel mutex"
    chmod 600 "$KERNEL_LOCK_FILE" || die "cannot protect the publisher kernel mutex"
fi
verify_owned_regular_mode "$KERNEL_LOCK_FILE" 600 "publisher kernel mutex"
umask "$PUBLISHER_PREVIOUS_UMASK"
HOST_KERNEL_OS="$(/usr/bin/uname -s 2>/dev/null || uname -s)"
# The publisher shell itself owns fd 9. No mutable-script re-exec or separate
# lock-holder process sits between validation and the transaction.
exec 9>>"$KERNEL_LOCK_FILE" || die "cannot open publisher kernel mutex"
case "$HOST_KERNEL_OS" in
    Darwin)
        [ -x /usr/bin/lockf ] || die "macOS lockf is required for publisher serialization"
        /usr/bin/lockf -s -t 0 9 || die "another publisher owns the kernel mutex"
        ;;
    Linux)
        [ -x /usr/bin/flock ] || die "Linux /usr/bin/flock is required for publisher serialization"
        /usr/bin/flock -n 9 || die "another publisher owns the kernel mutex"
        ;;
    *) die "unsupported publisher mutex platform: $HOST_KERNEL_OS" ;;
esac
[ -e /dev/fd/9 ] || die "publisher process does not own kernel mutex fd 9"
/usr/bin/env -i PATH=/usr/bin:/bin PYTHONNOUSERSITE=1 \
    /usr/bin/python3 -I - "$KERNEL_LOCK_FILE" 9 <<'PY' ||
import os
import stat
import sys

path = os.lstat(sys.argv[1])
opened = os.fstat(int(sys.argv[2]))
matches = (
    stat.S_ISREG(path.st_mode)
    and stat.S_ISREG(opened.st_mode)
    and (path.st_dev, path.st_ino) == (opened.st_dev, opened.st_ino)
)
raise SystemExit(0 if matches else 1)
PY
    die "publisher kernel mutex fd 9 does not identify the fixed lock file"
set +e
if [ "$HOST_KERNEL_OS" = Darwin ]; then
    /usr/bin/lockf -s -t 0 9 2>/dev/null
    KERNEL_LOCK_SELF_STATUS=$?
    /usr/bin/lockf -k -s -t 0 "$KERNEL_LOCK_FILE" /usr/bin/true 2>/dev/null
    KERNEL_LOCK_PROBE_STATUS=$?
    KERNEL_LOCK_EXPECTED_BUSY=75
else
    /usr/bin/flock -n 9 2>/dev/null
    KERNEL_LOCK_SELF_STATUS=$?
    /usr/bin/flock -n "$KERNEL_LOCK_FILE" /usr/bin/true 2>/dev/null
    KERNEL_LOCK_PROBE_STATUS=$?
    KERNEL_LOCK_EXPECTED_BUSY=1
fi
set -e
[ "$KERNEL_LOCK_SELF_STATUS" -eq 0 ] || die "publisher process does not own its inherited kernel mutex fd"
[ "$KERNEL_LOCK_PROBE_STATUS" -eq "$KERNEL_LOCK_EXPECTED_BUSY" ] ||
    die "publisher lock-holder marker is not backed by the expected live kernel mutex"
if [ "$LEASE_TEST_MODE" = 0 ]; then
    verify_trusted_root_provisioning 9
fi
CURRENT_BOOT_IDENTITY="$(boot_identity)" || die "cannot establish host boot identity for publisher lease"
SHARED_TARGETS="$(clean_field "$REAL_PATH|$ADAPTER_PATH|$RUNTIME_ASSET_DIR|$WRAPPER_PATH")"

installed_assets_sha256() {
    local adapter_dir adapter_root asset path
    adapter_dir="$(dirname "$ADAPTER_PATH")"
    adapter_root="$(dirname "$adapter_dir")"
    {
        path_has_symlink_component "$WRAPPER_PATH" && die "installed wrapper path must not traverse a symlink: $WRAPPER_PATH"
        printf 'wrapper\t%s\t%s\t%s\n' "$WRAPPER_PATH" "$(sha256_file "$WRAPPER_PATH")" "$(file_mode "$WRAPPER_PATH")"
        path_has_symlink_component "$ADAPTER_PATH" && die "installed adapter path must not traverse a symlink: $ADAPTER_PATH"
        printf 'adapter\t%s\t%s\t%s\n' "$ADAPTER_PATH" "$(sha256_file "$ADAPTER_PATH")" "$(file_mode "$ADAPTER_PATH")"
        for asset in "${AUDIO_ADAPTER_COMPANIONS[@]}"; do
            path="$adapter_dir/$asset"
            path_has_symlink_component "$path" && die "installed companion path must not traverse a symlink: $path"
            printf 'companion\t%s\t%s\t%s\n' "$path" "$(sha256_file "$path")" "$(file_mode "$path")"
        done
        for asset in "${AUDIO_POLICY_ASSETS[@]}"; do
            path="$adapter_root/$asset"
            path_has_symlink_component "$path" && die "installed policy path must not traverse a symlink: $path"
            printf 'policy\t%s\t%s\t%s\n' "$path" "$(sha256_file "$path")" "$(file_mode "$path")"
        done
        for asset in "${RUNTIME_ASSETS[@]}"; do
            path="$RUNTIME_ASSET_DIR/$asset"
            path_has_symlink_component "$path" && die "installed runtime path must not traverse a symlink: $path"
            printf 'runtime\t%s\t%s\t%s\n' "$path" "$(sha256_file "$path")" "$(file_mode "$path")"
        done
    } | sha256_text
}

write_active_values() {
    local tmp="$ACTIVE_META.tmp.$$.$RANDOM" pid_path pid_tmp
    {
        printf 'schema=%s\n' agent_bridge.publisher_lease.v0
        printf 'lease_id=%s\n' "$LEASE_ID"
        printf 'pid=%s\n' "$$"
        printf 'process_start_fingerprint=%s\n' "$LEASE_PROCESS_START"
        printf 'boot_identity=%s\n' "$CURRENT_BOOT_IDENTITY"
        printf 'real_path=%s\n' "$REAL_PATH"
        printf 'shared_targets=%s\n' "$SHARED_TARGETS"
        printf 'phase=%s\n' "$LEASE_PHASE"
        printf 'state_seq=%s\n' "$LEASE_STATE_SEQ"
        printf 'started_at=%s\n' "$LEASE_STARTED_AT"
        printf 'updated_at=%s\n' "$(utc_now)"
        printf 'baseline_binary_sha256=%s\n' "$LEASE_BASELINE_SHA"
        printf 'candidate_commit=%s\n' "$LEASE_CANDIDATE"
        printf 'challenge=%s\n' "$LEASE_CHALLENGE"
        printf 'force_reinstall=%s\n' "$FORCE_REINSTALL"
        printf 'force_reason=%s\n' "$FORCE_REASON"
        printf 'failed_phase=%s\n' "$LEASE_FAILED_PHASE"
        printf 'failure_reason=%s\n' "$(clean_field "$LEASE_FAILURE_REASON")"
    } > "$tmp"
    chmod 600 "$tmp"
    verify_owned_regular_mode "$tmp" 600 "staged publisher lease metadata"
    mv -f "$tmp" "$ACTIVE_META"
    verify_owned_regular_mode "$ACTIVE_META" 600 "publisher lease metadata"
    pid_path="$(dirname "$ACTIVE_META")/pid"
    pid_tmp="$pid_path.tmp.$$.$RANDOM"
    printf '%s\n' "$$" > "$pid_tmp"
    chmod 600 "$pid_tmp"
    verify_owned_regular_mode "$pid_tmp" 600 "staged publisher lease pid"
    mv -f "$pid_tmp" "$pid_path"
    verify_owned_regular_mode "$pid_path" 600 "publisher lease pid"
}

lease_phase_update() {
    LEASE_PHASE="$1"
    LEASE_STATE_SEQ=$((LEASE_STATE_SEQ + 1))
    write_active_values || die "cannot atomically update publisher lease phase $LEASE_PHASE"
}

archive_active_receipt() {
    local disposition="$1" reason="$2" meta="${3:-$ACTIVE_META}" receipt tmp current_sha current_inode
    read_active_lease "$meta" || return 1
    [ "$R_LEASE_ID" = "$LEASE_ID" ] && [ "$R_PID" = "$$" ] &&
        [ "$R_START" = "$LEASE_PROCESS_START" ] && [ "$R_BOOT" = "$CURRENT_BOOT_IDENTITY" ] || return 1
    current_sha="$(sha256_file "$REAL_PATH")"
    current_inode="$(file_inode "$REAL_PATH" 2>/dev/null || printf '%s\n' absent)"
    receipt="$LEASE_RECEIPT_DIR/$(receipt_stamp).$LEASE_ID.$disposition.meta"
    tmp="$receipt.tmp.$$.$RANDOM"
    {
        printf 'schema=%s\n' agent_bridge.publisher_lease_receipt.v0
        sed '1d' "$meta"
        printf 'disposition=%s\n' "$disposition"
        printf 'reason=%s\n' "$(clean_field "$reason")"
        printf 'finished_at=%s\n' "$(utc_now)"
        printf 'current_binary_sha256=%s\n' "$current_sha"
        printf 'current_binary_inode=%s\n' "$current_inode"
    } > "$tmp"
    chmod 600 "$tmp"
    mv -f "$tmp" "$receipt"
}

write_release_intent() {
    local disposition="$1" reason="$2" quarantine="$3" meta_sha current_sha current_inode receipt tmp
    [ ! -e "$RELEASE_INTENT" ] && [ ! -L "$RELEASE_INTENT" ] ||
        die "an unsettled publisher release intent already exists"
    is_safe_id "$disposition" && [ -n "$reason" ] || die "invalid publisher release disposition or reason"
    case "$quarantine" in "$LEASE_QUARANTINE_DIR"/*.lock) ;; *) die "publisher release quarantine path escapes the fixed state root" ;; esac
    read_active_lease "$ACTIVE_META" || die "cannot write release intent from an invalid active lease"
    [ "$R_LEASE_ID" = "$LEASE_ID" ] && [ "$R_CHALLENGE" = "$LEASE_CHALLENGE" ] ||
        die "active lease identity changed before release intent"
    meta_sha="$(sha256_file "$ACTIVE_META")"
    current_sha="$(sha256_file "$REAL_PATH")"
    current_inode="$(file_inode "$REAL_PATH" 2>/dev/null || printf '%s\n' absent)"
    receipt="$LEASE_RECEIPT_DIR/$LEASE_ID.$LEASE_CHALLENGE.$disposition.release-completed.meta"
    tmp="$RELEASE_INTENT.tmp.$$.$RANDOM"
    {
        printf 'schema=%s\n' agent_bridge.publisher_release_intent.v0
        printf 'lease_id=%s\n' "$LEASE_ID"
        printf 'challenge=%s\n' "$LEASE_CHALLENGE"
        printf 'disposition=%s\n' "$disposition"
        printf 'reason=%s\n' "$(clean_field "$reason")"
        printf 'quarantine_path=%s\n' "$quarantine"
        printf 'active_meta_sha256=%s\n' "$meta_sha"
        printf 'current_binary_sha256=%s\n' "$current_sha"
        printf 'current_binary_inode=%s\n' "$current_inode"
        printf 'receipt_path=%s\n' "$receipt"
        printf 'real_path=%s\n' "$REAL_PATH"
        printf 'shared_targets=%s\n' "$SHARED_TARGETS"
        printf 'started_at=%s\n' "$(utc_now)"
    } > "$tmp"
    chmod 600 "$tmp"
    mv -f "$tmp" "$RELEASE_INTENT"
    read_release_intent "$RELEASE_INTENT" && [ "$Q_LEASE_ID" = "$LEASE_ID" ] &&
        [ "$Q_CHALLENGE" = "$LEASE_CHALLENGE" ] && [ "$Q_RECEIPT" = "$receipt" ] &&
        [ "$Q_CURRENT_SHA" = "$current_sha" ] && [ "$Q_CURRENT_INODE" = "$current_inode" ] ||
        die "publisher release intent failed strict self-validation"
}

archive_release_completion() {
    local intent="$1" meta receipt_leaf tmp
    read_release_intent "$intent" || die "publisher release intent is unknown or corrupt"
    case "$Q_QUARANTINE" in "$LEASE_QUARANTINE_DIR"/*.lock) ;; *) die "publisher release intent quarantine escapes the fixed state root" ;; esac
    meta="$Q_QUARANTINE/lease.meta"
    [ "$(sha256_file "$meta")" = "$Q_META_SHA" ] || die "quarantined publisher lease does not match its release intent"
    read_active_lease "$meta" || die "quarantined publisher lease metadata is corrupt"
    [ "$R_LEASE_ID" = "$Q_LEASE_ID" ] && [ "$R_CHALLENGE" = "$Q_CHALLENGE" ] &&
        [ "$R_REAL_PATH" = "$Q_REAL_PATH" ] && [ "$R_SHARED_TARGETS" = "$Q_SHARED_TARGETS" ] ||
        die "quarantined publisher lease identity does not match its release intent"
    case "$Q_RECEIPT" in "$LEASE_RECEIPT_DIR"/*.meta) ;; *) die "publisher release receipt escapes the fixed receipt root" ;; esac
    receipt_leaf="${Q_RECEIPT#"$LEASE_RECEIPT_DIR/"}"
    case "$receipt_leaf" in ''|*/*) die "publisher release receipt must be a direct child of the fixed receipt root" ;; esac
    tmp="$Q_RECEIPT.tmp.$$.$RANDOM"
    {
        printf 'schema=%s\n' agent_bridge.publisher_lease_receipt.v0
        sed '1d' "$meta"
        printf 'disposition=%s\n' "$Q_DISPOSITION"
        printf 'reason=%s\n' "$Q_REASON"
        printf 'finished_at=%s\n' "$Q_STARTED_AT"
        printf 'current_binary_sha256=%s\n' "$Q_CURRENT_SHA"
        printf 'current_binary_inode=%s\n' "$Q_CURRENT_INODE"
    } > "$tmp"
    chmod 600 "$tmp"
    publish_exact_receipt "$tmp" "$Q_RECEIPT"
}

settle_release_intent() {
    local settled quarantine_leaf
    [ -e "$RELEASE_INTENT" ] || [ -L "$RELEASE_INTENT" ] || return 0
    [ ! -L "$RELEASE_INTENT" ] || die "publisher release intent must not be a symlink"
    read_release_intent "$RELEASE_INTENT" || die "publisher release intent is unknown or corrupt; fail closed"
    case "$Q_QUARANTINE" in "$LEASE_QUARANTINE_DIR"/*.lock) ;; *) die "publisher release intent quarantine escapes the fixed state root" ;; esac
    quarantine_leaf="${Q_QUARANTINE#"$LEASE_QUARANTINE_DIR/"}"
    case "$quarantine_leaf" in ''|*/*) die "publisher release quarantine must be a direct child of the fixed quarantine root" ;; esac
    [ "$Q_REAL_PATH" = "$REAL_PATH" ] && [ "$Q_SHARED_TARGETS" = "$SHARED_TARGETS" ] ||
        die "publisher release intent targets do not match this invocation"
    if [ -e "$Q_QUARANTINE" ] || [ -L "$Q_QUARANTINE" ]; then
        [ ! -L "$Q_QUARANTINE" ] && [ -d "$Q_QUARANTINE" ] ||
            die "publisher release quarantine is not a physical directory"
        [ ! -e "$deploy_lock" ] && [ ! -L "$deploy_lock" ] ||
            die "publisher release intent has both active and quarantined lease state"
    elif [ -e "$deploy_lock" ] || [ -L "$deploy_lock" ]; then
        [ ! -L "$deploy_lock" ] && [ -d "$deploy_lock" ] || die "active publisher release source is not a physical directory"
        [ "$(sha256_file "$deploy_lock/lease.meta")" = "$Q_META_SHA" ] ||
            die "active publisher lease does not match the unsettled release intent"
        mv "$deploy_lock" "$Q_QUARANTINE" || die "cannot finish the publisher release quarantine transition"
    else
        die "publisher release intent has neither its active nor quarantined lease state"
    fi
    archive_release_completion "$RELEASE_INTENT"
    settled="$LEASE_QUARANTINE_DIR/$(receipt_stamp).$Q_LEASE_ID.$$.$RANDOM.settled-release-intent.meta"
    mv "$RELEASE_INTENT" "$settled" || die "cannot retire the settled publisher release intent"
}

release_active_lease() {
    local disposition="$1" reason="$2" quarantine
    read_active_lease "$ACTIVE_META" || die "publisher lease changed before release; recovery required"
    [ "$R_LEASE_ID" = "$LEASE_ID" ] && [ "$R_PID" = "$$" ] &&
        [ "$R_START" = "$LEASE_PROCESS_START" ] && [ "$R_BOOT" = "$CURRENT_BOOT_IDENTITY" ] ||
        die "publisher lease ownership changed before release; recovery required"
    quarantine="$LEASE_QUARANTINE_DIR/$(receipt_stamp).$LEASE_ID.$$.$RANDOM.$disposition.lock"
    write_release_intent "$disposition" "$reason" "$quarantine"
    mv "$deploy_lock" "$quarantine" || die "cannot atomically quarantine released publisher lease"
    ACTIVE_META="$quarantine/lease.meta"
    LEASE_OWNED=0
    settle_release_intent
    LEASE_FINALIZED=1
}

archive_foreign_receipt() {
    local meta="$1" disposition="$2" reason="$3" receipt tmp current_sha current_inode
    read_active_lease "$meta" || return 1
    current_sha="$(sha256_file "$R_REAL_PATH")"
    current_inode="$(file_inode "$R_REAL_PATH" 2>/dev/null || printf '%s\n' absent)"
    receipt="$LEASE_RECEIPT_DIR/$(receipt_stamp).$R_LEASE_ID.$disposition.meta"
    tmp="$receipt.tmp.$$.$RANDOM"
    {
        printf 'schema=%s\n' agent_bridge.publisher_lease_receipt.v0
        sed '1d' "$meta"
        printf 'disposition=%s\n' "$disposition"
        printf 'reason=%s\n' "$(clean_field "$reason")"
        printf 'finished_at=%s\n' "$(utc_now)"
        printf 'current_binary_sha256=%s\n' "$current_sha"
        printf 'current_binary_inode=%s\n' "$current_inode"
    } > "$tmp" && chmod 600 "$tmp" && mv -f "$tmp" "$receipt"
}

archive_recovery_handoff() {
    local stage="$1" disposition receipt tmp
    [ -n "$RECOVERY_PREDECESSOR_LEASE_ID" ] || return 0
    case "$stage" in
        acquired) disposition=governed_roll_forward_successor_acquired ;;
        completed) disposition=governed_roll_forward_recovery_completed ;;
        *) return 1 ;;
    esac
    receipt="$LEASE_RECEIPT_DIR/$(receipt_stamp).$LEASE_ID.$disposition.meta"
    tmp="$receipt.tmp.$$.$RANDOM"
    {
        printf 'schema=%s\n' agent_bridge.publisher_recovery_handoff_receipt.v0
        printf 'disposition=%s\n' "$disposition"
        printf 'predecessor_lease_id=%s\n' "$RECOVERY_PREDECESSOR_LEASE_ID"
        printf 'predecessor_challenge=%s\n' "$RECOVERY_PREDECESSOR_CHALLENGE"
        printf 'successor_lease_id=%s\n' "$LEASE_ID"
        printf 'successor_challenge=%s\n' "$LEASE_CHALLENGE"
        printf 'successor_candidate_commit=%s\n' "$LEASE_CANDIDATE"
        printf 'real_path=%s\n' "$REAL_PATH"
        printf 'shared_targets=%s\n' "$SHARED_TARGETS"
        printf 'recorded_at=%s\n' "$(utc_now)"
    } > "$tmp"
    chmod 600 "$tmp"
    mv -f "$tmp" "$receipt"
}

archive_recovery_handoff_marker() {
    local disposition="$1" next_lease="$2" reason="$3" source="${4:-$RECOVERY_HANDOFF}" receipt tmp
    read_recovery_handoff "$source" ||
        die "recovery handoff intent is missing, unknown, or corrupt; fail closed"
    receipt="$LEASE_RECEIPT_DIR/$(receipt_stamp).$H_SUCCESSOR_LEASE_ID.$$.$RANDOM.$disposition.meta"
    tmp="$receipt.tmp.$$.$RANDOM"
    {
        printf 'schema=%s\n' agent_bridge.publisher_handoff_receipt.v0
        sed '1d' "$source"
        printf 'disposition=%s\n' "$disposition"
        printf 'next_successor_lease_id=%s\n' "$next_lease"
        printf 'archive_reason=%s\n' "$(clean_field "$reason")"
        printf 'archived_at=%s\n' "$(utc_now)"
    } > "$tmp"
    chmod 600 "$tmp"
    mv -f "$tmp" "$receipt"
}

write_recovery_handoff_intent() {
    local predecessor_lease="$1" predecessor_challenge="$2" predecessor_phase="$3" reason="$4" tmp old_snapshot=""
    is_safe_id "$predecessor_lease" && is_sha256_value "$predecessor_challenge" ||
        die "cannot bind an invalid recovery predecessor identity"
    case "$predecessor_phase" in recovery_required|corrupt_unknown) ;; *) die "invalid recovery predecessor phase" ;; esac
    is_failed_phase "$RECOVERY_PREDECESSOR_FAILED_PHASE" || die "cannot bind recovery without the original failed phase"
    is_sha256_value "$RECOVERY_PREDECESSOR_BOOT" || die "cannot bind recovery without the predecessor boot identity"
    { [ "$RECOVERY_PREDECESSOR_BINARY_SHA" = absent ] || is_sha256_value "$RECOVERY_PREDECESSOR_BINARY_SHA"; } ||
        die "cannot bind recovery without the predecessor binary fingerprint"
    if [ -e "$RECOVERY_HANDOFF" ]; then
        read_recovery_handoff "$RECOVERY_HANDOFF" || die "existing recovery handoff cannot be resumed because it is corrupt"
        old_snapshot="$LEASE_QUARANTINE_DIR/$(receipt_stamp).$H_SUCCESSOR_LEASE_ID.$$.$RANDOM.replaced-handoff.meta"
        cp "$RECOVERY_HANDOFF" "$old_snapshot" || die "cannot preserve the replaced recovery handoff intent"
        chmod 600 "$old_snapshot"
    fi
    tmp="$RECOVERY_HANDOFF.tmp.$$.$RANDOM"
    {
        printf 'schema=%s\n' agent_bridge.publisher_handoff_intent.v0
        printf 'predecessor_lease_id=%s\n' "$predecessor_lease"
        printf 'predecessor_challenge=%s\n' "$predecessor_challenge"
        printf 'predecessor_phase=%s\n' "$predecessor_phase"
        printf 'predecessor_failed_phase=%s\n' "$RECOVERY_PREDECESSOR_FAILED_PHASE"
        printf 'predecessor_boot_identity=%s\n' "$RECOVERY_PREDECESSOR_BOOT"
        printf 'predecessor_binary_sha256=%s\n' "$RECOVERY_PREDECESSOR_BINARY_SHA"
        printf 'successor_lease_id=%s\n' "$LEASE_ID"
        printf 'successor_challenge=%s\n' "$LEASE_CHALLENGE"
        printf 'successor_stage_path=%s\n' "$LEASE_STAGED_LOCK"
        printf 'real_path=%s\n' "$REAL_PATH"
        printf 'shared_targets=%s\n' "$SHARED_TARGETS"
        printf 'started_at=%s\n' "$(utc_now)"
        printf 'reason=%s\n' "$(clean_field "$reason")"
    } > "$tmp"
    chmod 600 "$tmp"
    mv -f "$tmp" "$RECOVERY_HANDOFF"
    read_recovery_handoff "$RECOVERY_HANDOFF" &&
        [ "$H_SUCCESSOR_LEASE_ID" = "$LEASE_ID" ] && [ "$H_SUCCESSOR_CHALLENGE" = "$LEASE_CHALLENGE" ] ||
        die "recovery handoff intent failed strict self-validation"
    [ -z "$old_snapshot" ] ||
        archive_recovery_handoff_marker governed_roll_forward_handoff_resumed "$LEASE_ID" "$reason" "$old_snapshot"
}

write_handoff_completion_intent() {
    local quarantine="$1" meta_sha handoff_receipt recovery_receipt tmp
    [ ! -e "$HANDOFF_COMPLETION_INTENT" ] && [ ! -L "$HANDOFF_COMPLETION_INTENT" ] ||
        die "an unsettled recovery handoff completion intent already exists"
    case "$quarantine" in "$LEASE_QUARANTINE_DIR"/*.meta) ;; *) die "recovery handoff completion quarantine escapes the fixed state root" ;; esac
    read_recovery_handoff "$RECOVERY_HANDOFF" || die "recovery handoff intent became corrupt before completion"
    [ "$H_SUCCESSOR_LEASE_ID" = "$LEASE_ID" ] && [ "$H_SUCCESSOR_CHALLENGE" = "$LEASE_CHALLENGE" ] &&
        [ "$H_REAL_PATH" = "$REAL_PATH" ] && [ "$H_SHARED_TARGETS" = "$SHARED_TARGETS" ] ||
        die "recovery handoff completion does not match the active successor"
    meta_sha="$(sha256_file "$RECOVERY_HANDOFF")"
    handoff_receipt="$LEASE_RECEIPT_DIR/$LEASE_ID.$LEASE_CHALLENGE.governed_roll_forward_handoff_completed.meta"
    recovery_receipt="$LEASE_RECEIPT_DIR/$LEASE_ID.$LEASE_CHALLENGE.governed_roll_forward_recovery_completed.meta"
    tmp="$HANDOFF_COMPLETION_INTENT.tmp.$$.$RANDOM"
    {
        printf 'schema=%s\n' agent_bridge.publisher_handoff_completion_intent.v0
        printf 'successor_lease_id=%s\n' "$LEASE_ID"
        printf 'successor_challenge=%s\n' "$LEASE_CHALLENGE"
        printf 'successor_candidate_commit=%s\n' "$LEASE_CANDIDATE"
        printf 'handoff_meta_sha256=%s\n' "$meta_sha"
        printf 'quarantine_path=%s\n' "$quarantine"
        printf 'handoff_receipt_path=%s\n' "$handoff_receipt"
        printf 'recovery_receipt_path=%s\n' "$recovery_receipt"
        printf 'started_at=%s\n' "$(utc_now)"
    } > "$tmp"
    chmod 600 "$tmp"
    mv -f "$tmp" "$HANDOFF_COMPLETION_INTENT"
    read_handoff_completion_intent "$HANDOFF_COMPLETION_INTENT" &&
        [ "$HC_SUCCESSOR_LEASE_ID" = "$LEASE_ID" ] && [ "$HC_SUCCESSOR_CHALLENGE" = "$LEASE_CHALLENGE" ] &&
        [ "$HC_SUCCESSOR_CANDIDATE" = "$LEASE_CANDIDATE" ] &&
        [ "$HC_HANDOFF_RECEIPT" = "$handoff_receipt" ] && [ "$HC_RECOVERY_RECEIPT" = "$recovery_receipt" ] ||
        die "recovery handoff completion intent failed strict self-validation"
}

archive_recovery_handoff_marker_exact() {
    local source="$1" receipt="$2" recorded_at="$3" tmp
    read_recovery_handoff "$source" ||
        die "recovery handoff completion marker is missing, unknown, or corrupt"
    tmp="$receipt.tmp.$$.$RANDOM"
    {
        printf 'schema=%s\n' agent_bridge.publisher_handoff_receipt.v0
        sed '1d' "$source"
        printf 'disposition=%s\n' governed_roll_forward_handoff_completed
        printf 'next_successor_lease_id=%s\n' none
        printf 'archive_reason=%s\n' recovery_completed
        printf 'archived_at=%s\n' "$recorded_at"
    } > "$tmp"
    chmod 600 "$tmp"
    publish_exact_receipt "$tmp" "$receipt"
}

archive_recovery_completion_from_marker() {
    local source="$1" candidate="$2" receipt="$3" recorded_at="$4" tmp
    read_recovery_handoff "$source" ||
        die "recovery handoff completion marker is missing, unknown, or corrupt"
    is_safe_candidate "$candidate" || die "recovery completion candidate is invalid"
    tmp="$receipt.tmp.$$.$RANDOM"
    {
        printf 'schema=%s\n' agent_bridge.publisher_recovery_handoff_receipt.v0
        printf 'disposition=%s\n' governed_roll_forward_recovery_completed
        printf 'predecessor_lease_id=%s\n' "$H_PREDECESSOR_LEASE_ID"
        printf 'predecessor_challenge=%s\n' "$H_PREDECESSOR_CHALLENGE"
        printf 'successor_lease_id=%s\n' "$H_SUCCESSOR_LEASE_ID"
        printf 'successor_challenge=%s\n' "$H_SUCCESSOR_CHALLENGE"
        printf 'successor_candidate_commit=%s\n' "$candidate"
        printf 'real_path=%s\n' "$H_REAL_PATH"
        printf 'shared_targets=%s\n' "$H_SHARED_TARGETS"
        printf 'recorded_at=%s\n' "$recorded_at"
    } > "$tmp"
    chmod 600 "$tmp"
    publish_exact_receipt "$tmp" "$receipt"
}

settle_handoff_completion_intent() {
    local settled quarantine_leaf handoff_receipt_leaf recovery_receipt_leaf
    [ -e "$HANDOFF_COMPLETION_INTENT" ] || [ -L "$HANDOFF_COMPLETION_INTENT" ] || return 0
    [ ! -L "$HANDOFF_COMPLETION_INTENT" ] || die "recovery handoff completion intent must not be a symlink"
    read_handoff_completion_intent "$HANDOFF_COMPLETION_INTENT" ||
        die "recovery handoff completion intent is unknown or corrupt; fail closed"
    case "$HC_QUARANTINE" in "$LEASE_QUARANTINE_DIR"/*.meta) ;; *) die "recovery handoff completion quarantine escapes the fixed state root" ;; esac
    quarantine_leaf="${HC_QUARANTINE#"$LEASE_QUARANTINE_DIR/"}"
    case "$quarantine_leaf" in ''|*/*) die "recovery handoff completion quarantine must be a direct child of the fixed quarantine root" ;; esac
    case "$HC_HANDOFF_RECEIPT" in "$LEASE_RECEIPT_DIR"/*.meta) ;; *) die "handoff completion receipt escapes the fixed receipt root" ;; esac
    case "$HC_RECOVERY_RECEIPT" in "$LEASE_RECEIPT_DIR"/*.meta) ;; *) die "formal recovery completion receipt escapes the fixed receipt root" ;; esac
    handoff_receipt_leaf="${HC_HANDOFF_RECEIPT#"$LEASE_RECEIPT_DIR/"}"
    recovery_receipt_leaf="${HC_RECOVERY_RECEIPT#"$LEASE_RECEIPT_DIR/"}"
    case "$handoff_receipt_leaf" in ''|*/*) die "handoff completion receipt must be a direct child of the fixed receipt root" ;; esac
    case "$recovery_receipt_leaf" in ''|*/*) die "formal recovery completion receipt must be a direct child of the fixed receipt root" ;; esac
    [ "$HC_HANDOFF_RECEIPT" != "$HC_RECOVERY_RECEIPT" ] ||
        die "handoff and formal recovery completion receipts must use distinct paths"
    if [ -e "$HC_QUARANTINE" ] || [ -L "$HC_QUARANTINE" ]; then
        [ ! -L "$HC_QUARANTINE" ] && [ -f "$HC_QUARANTINE" ] ||
            die "recovery handoff completion quarantine is not a physical file"
        [ ! -e "$RECOVERY_HANDOFF" ] && [ ! -L "$RECOVERY_HANDOFF" ] ||
            die "recovery handoff completion has both canonical and quarantined marker state"
    elif [ -e "$RECOVERY_HANDOFF" ] || [ -L "$RECOVERY_HANDOFF" ]; then
        [ ! -L "$RECOVERY_HANDOFF" ] && [ -f "$RECOVERY_HANDOFF" ] ||
            die "recovery handoff completion source is not a physical file"
        [ "$(sha256_file "$RECOVERY_HANDOFF")" = "$HC_META_SHA" ] ||
            die "canonical recovery handoff does not match its completion intent"
        mv "$RECOVERY_HANDOFF" "$HC_QUARANTINE" ||
            die "cannot finish the recovery handoff completion transition"
    else
        die "recovery handoff completion intent has neither canonical nor quarantined marker state"
    fi
    [ "$(sha256_file "$HC_QUARANTINE")" = "$HC_META_SHA" ] ||
        die "quarantined recovery handoff does not match its completion intent"
    read_recovery_handoff "$HC_QUARANTINE" || die "quarantined recovery handoff completion marker is corrupt"
    [ "$H_SUCCESSOR_LEASE_ID" = "$HC_SUCCESSOR_LEASE_ID" ] &&
        [ "$H_SUCCESSOR_CHALLENGE" = "$HC_SUCCESSOR_CHALLENGE" ] &&
        [ "$H_REAL_PATH" = "$REAL_PATH" ] && [ "$H_SHARED_TARGETS" = "$SHARED_TARGETS" ] ||
        die "quarantined recovery handoff identity does not match its completion intent"
    archive_recovery_handoff_marker_exact "$HC_QUARANTINE" "$HC_HANDOFF_RECEIPT" "$HC_STARTED_AT"
    archive_recovery_completion_from_marker "$HC_QUARANTINE" "$HC_SUCCESSOR_CANDIDATE" \
        "$HC_RECOVERY_RECEIPT" "$HC_STARTED_AT"
    settled="$LEASE_QUARANTINE_DIR/$(receipt_stamp).$HC_SUCCESSOR_LEASE_ID.$$.$RANDOM.settled-handoff-completion.meta"
    mv "$HANDOFF_COMPLETION_INTENT" "$settled" ||
        die "cannot retire the settled recovery handoff completion intent"
}

complete_recovery_handoff_intent() {
    local quarantine
    [ -e "$RECOVERY_HANDOFF" ] || return 0
    quarantine="$LEASE_QUARANTINE_DIR/$(receipt_stamp).$LEASE_ID.$$.$RANDOM.completed-recovery-handoff.meta"
    write_handoff_completion_intent "$quarantine"
    settle_handoff_completion_intent
}

inspect_existing_recovery_handoff() {
    local corrupt_inode corrupt_sha expected_id expected_challenge staged_owner_status active_quarantine stage_quarantine
    HANDOFF_PRESENT=0
    HANDOFF_ACTIVE_RELATION=none
    HANDOFF_RESUME_AFTER_RECLAIM=0
    [ -e "$RECOVERY_HANDOFF" ] || [ -L "$RECOVERY_HANDOFF" ] || return 0
    [ ! -L "$RECOVERY_HANDOFF" ] || die "recovery handoff intent must not be a symlink"
    read_recovery_handoff "$RECOVERY_HANDOFF" ||
        die "recovery handoff intent is unknown or corrupt; fail closed"
    case "$H_SUCCESSOR_STAGE_PATH" in "$LEASE_INTENT_DIR"/*.lock) ;; *) die "recovery handoff successor staging path escapes the intent root" ;; esac
    [ "$H_REAL_PATH" = "$REAL_PATH" ] && [ "$H_SHARED_TARGETS" = "$SHARED_TARGETS" ] ||
        die "recovery handoff intent targets do not match this invocation"
    [ "$RECOVERY_MODE" = roll_forward ] ||
        die "an incomplete governed recovery handoff exists; roll_forward with a nonempty reason is required"
    HANDOFF_PRESENT=1
    HANDOFF_ORIGINAL_PREDECESSOR_LEASE_ID="$H_PREDECESSOR_LEASE_ID"
    HANDOFF_ORIGINAL_PREDECESSOR_CHALLENGE="$H_PREDECESSOR_CHALLENGE"
    HANDOFF_ORIGINAL_PREDECESSOR_PHASE="$H_PREDECESSOR_PHASE"
    HANDOFF_ORIGINAL_PREDECESSOR_FAILED_PHASE="$H_PREDECESSOR_FAILED_PHASE"
    HANDOFF_ORIGINAL_PREDECESSOR_BOOT="$H_PREDECESSOR_BOOT"
    HANDOFF_ORIGINAL_PREDECESSOR_BINARY_SHA="$H_PREDECESSOR_BINARY_SHA"
    if [ -e "$deploy_lock" ] || [ -L "$deploy_lock" ]; then
        if ! read_active_lease "$deploy_lock/lease.meta"; then
            [ ! -L "$deploy_lock" ] && [ -d "$deploy_lock" ] ||
                die "corrupt recovery handoff active state is not a physical lock directory"
            if [ -z "$(find "$deploy_lock" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ] &&
                    [ -d "$H_SUCCESSOR_STAGE_PATH" ] && [ ! -L "$H_SUCCESSOR_STAGE_PATH" ]; then
                read_active_lease "$H_SUCCESSOR_STAGE_PATH/lease.meta" ||
                    die "partial recovery successor stage metadata is corrupt"
                [ "$R_LEASE_ID" = "$H_SUCCESSOR_LEASE_ID" ] && [ "$R_CHALLENGE" = "$H_SUCCESSOR_CHALLENGE" ] &&
                    [ "$R_REAL_PATH" = "$H_REAL_PATH" ] && [ "$R_SHARED_TARGETS" = "$H_SHARED_TARGETS" ] &&
                    [ "$R_PHASE" = acquired ] ||
                    die "empty active claim is unrelated to the exact staged recovery successor"
                set +e
                owner_exact_status
                staged_owner_status=$?
                set -e
                case "$staged_owner_status" in
                    0) die "the partially published recovery successor is still live; refusing overlapping recovery" ;;
                    2) die "the partially published recovery successor pid exists but its start fingerprint is unreadable" ;;
                esac
                active_quarantine="$LEASE_QUARANTINE_DIR/$(receipt_stamp).$H_SUCCESSOR_LEASE_ID.$$.$RANDOM.partial-successor-active.lock"
                stage_quarantine="$LEASE_QUARANTINE_DIR/$(receipt_stamp).$H_SUCCESSOR_LEASE_ID.$$.$RANDOM.partial-successor-stage.lock"
                mv "$deploy_lock" "$active_quarantine" ||
                    die "cannot quarantine the interrupted recovery successor active claim"
                mv "$H_SUCCESSOR_STAGE_PATH" "$stage_quarantine" ||
                    die "cannot quarantine the interrupted recovery successor stage"
                HANDOFF_ACTIVE_RELATION=partial_successor_reclaimed
            else
                [ "$H_PREDECESSOR_PHASE" = corrupt_unknown ] ||
                    die "active publisher lease cannot be related to the recovery handoff; fail closed"
                corrupt_inode="$(file_inode "$deploy_lock")" || die "cannot fingerprint corrupt handoff predecessor"
                corrupt_sha="$(sha256_file "$REAL_PATH")"
                expected_id="corrupt-lock-$corrupt_inode"
                expected_challenge="$(printf '%s\n' "$expected_id|$H_PREDECESSOR_BOOT|$REAL_PATH|$SHARED_TARGETS|$H_PREDECESSOR_BINARY_SHA" | sha256_text)"
                [ "$H_PREDECESSOR_LEASE_ID" = "$expected_id" ] &&
                    [ "$H_PREDECESSOR_CHALLENGE" = "$expected_challenge" ] &&
                    [ "$corrupt_sha" = "$H_PREDECESSOR_BINARY_SHA" ] ||
                    die "corrupt active publisher lease is unrelated to the exact recovery handoff predecessor"
                HANDOFF_ACTIVE_RELATION=corrupt_predecessor
            fi
        elif [ "$R_LEASE_ID" = "$H_PREDECESSOR_LEASE_ID" ] && [ "$R_CHALLENGE" = "$H_PREDECESSOR_CHALLENGE" ]; then
            HANDOFF_ACTIVE_RELATION=predecessor
        elif [ "$R_LEASE_ID" = "$H_SUCCESSOR_LEASE_ID" ] && [ "$R_CHALLENGE" = "$H_SUCCESSOR_CHALLENGE" ]; then
            HANDOFF_ACTIVE_RELATION=successor
            set +e
            owner_exact_status
            staged_owner_status=$?
            set -e
            case "$staged_owner_status" in
                0) die "the recovery handoff successor publisher is still live; refusing overlapping recovery" ;;
                2) die "the recovery handoff successor pid exists but its start fingerprint is unreadable" ;;
            esac
            case "$R_PHASE" in acquired|building|prepared) HANDOFF_RESUME_AFTER_RECLAIM=1 ;; esac
        else
            die "active publisher lease identity is unrelated to the recovery handoff intent"
        fi
    fi
    if [ ! -e "$deploy_lock" ] && [ ! -L "$deploy_lock" ]; then
        if [ -e "$H_SUCCESSOR_STAGE_PATH" ] || [ -L "$H_SUCCESSOR_STAGE_PATH" ]; then
            [ ! -L "$H_SUCCESSOR_STAGE_PATH" ] && [ -d "$H_SUCCESSOR_STAGE_PATH" ] ||
                die "recovery handoff successor stage is not a physical lease directory"
            read_active_lease "$H_SUCCESSOR_STAGE_PATH/lease.meta" ||
                die "recovery handoff successor stage metadata is corrupt"
            [ "$R_LEASE_ID" = "$H_SUCCESSOR_LEASE_ID" ] && [ "$R_CHALLENGE" = "$H_SUCCESSOR_CHALLENGE" ] ||
                die "recovery handoff successor stage identity does not match the marker"
            set +e
            owner_exact_status
            staged_owner_status=$?
            set -e
            case "$staged_owner_status" in
                0) die "the recovery handoff successor publisher is still live; refusing overlapping recovery" ;;
                2) die "the recovery handoff successor pid exists but its start fingerprint is unreadable" ;;
            esac
            stage_quarantine="$LEASE_QUARANTINE_DIR/$(receipt_stamp).$H_SUCCESSOR_LEASE_ID.$$.$RANDOM.interrupted-successor-stage.lock"
            mv "$H_SUCCESSOR_STAGE_PATH" "$stage_quarantine" ||
                die "cannot quarantine the interrupted recovery successor stage"
        fi
        RECOVERY_PREDECESSOR_LEASE_ID="$H_PREDECESSOR_LEASE_ID"
        RECOVERY_PREDECESSOR_CHALLENGE="$H_PREDECESSOR_CHALLENGE"
        RECOVERY_PREDECESSOR_PHASE="$H_PREDECESSOR_PHASE"
        RECOVERY_PREDECESSOR_FAILED_PHASE="$H_PREDECESSOR_FAILED_PHASE"
        RECOVERY_PREDECESSOR_BOOT="$H_PREDECESSOR_BOOT"
        RECOVERY_PREDECESSOR_BINARY_SHA="$H_PREDECESSOR_BINARY_SHA"
        write_recovery_handoff_intent "$RECOVERY_PREDECESSOR_LEASE_ID" "$RECOVERY_PREDECESSOR_CHALLENGE" \
            "$RECOVERY_PREDECESSOR_PHASE" "$RECOVERY_REASON"
    fi
}

mark_foreign_recovery_required() {
    local reason="$1" tmp="$ACTIVE_META.tmp.$$.$RANDOM" failed_phase
    failed_phase="$R_FAILED_PHASE"
    [ -n "$failed_phase" ] || failed_phase="$R_PHASE"
    R_SEQ=$((R_SEQ + 1))
    {
        printf 'schema=%s\n' agent_bridge.publisher_lease.v0
        printf 'lease_id=%s\n' "$R_LEASE_ID"
        printf 'pid=%s\n' "$R_PID"
        printf 'process_start_fingerprint=%s\n' "$R_START"
        printf 'boot_identity=%s\n' "$R_BOOT"
        printf 'real_path=%s\n' "$R_REAL_PATH"
        printf 'shared_targets=%s\n' "$R_SHARED_TARGETS"
        printf 'phase=%s\n' recovery_required
        printf 'state_seq=%s\n' "$R_SEQ"
        printf 'started_at=%s\n' "$R_STARTED"
        printf 'updated_at=%s\n' "$(utc_now)"
        printf 'baseline_binary_sha256=%s\n' "$R_BASELINE"
        printf 'candidate_commit=%s\n' "$R_CANDIDATE"
        printf 'challenge=%s\n' "$R_CHALLENGE"
        printf 'force_reinstall=%s\n' "$R_FORCE"
        printf 'force_reason=%s\n' "$R_FORCE_REASON"
        printf 'failed_phase=%s\n' "$failed_phase"
        printf 'failure_reason=%s\n' "$(clean_field "$reason")"
    } > "$tmp" && chmod 600 "$tmp" && mv -f "$tmp" "$ACTIVE_META"
    read_active_lease "$ACTIVE_META" && archive_foreign_receipt "$ACTIVE_META" recovery_required "$reason" || true
}

owner_exact_status() {
    local observed
    [ "$R_BOOT" = "$CURRENT_BOOT_IDENTITY" ] || return 1
    process_is_zombie "$R_PID" && return 1
    kill -0 "$R_PID" 2>/dev/null || return 1
    observed="$(process_start_fingerprint "$R_PID" 2>/dev/null)" || return 2
    [ "$observed" = "$R_START" ] || return 1
    process_is_zombie "$R_PID" && return 1
    return 0
}

read_lease_identity() {
    printf '%s|%s|%s|%s|%s|%s|%s|%s\n' \
        "$R_LEASE_ID" "$R_PID" "$R_START" "$R_BOOT" "$R_PHASE" "$R_SEQ" "$R_BASELINE" "$R_REAL_PATH"
}

reconcile_corrupt_active_lease() {
    local lock_inode current_sha predecessor_id predecessor_challenge receipt tmp quarantine
    [ "$RECOVERY_MODE" = roll_forward ] ||
        die "publisher lease metadata is missing, unknown, or corrupt; governed roll_forward recovery is required: $deploy_lock"
    [ ! -L "$deploy_lock" ] && [ -d "$deploy_lock" ] ||
        die "corrupt publisher lease is not a physical lock directory; fail closed"
    lock_inode="$(file_inode "$deploy_lock")" || die "cannot fingerprint corrupt publisher lease directory"
    current_sha="$(sha256_file "$REAL_PATH")"
    predecessor_id="corrupt-lock-$lock_inode"
    predecessor_challenge="$(printf '%s\n' "$predecessor_id|$CURRENT_BOOT_IDENTITY|$REAL_PATH|$SHARED_TARGETS|$current_sha" | sha256_text)"
    RECOVERY_PREDECESSOR_LEASE_ID="$predecessor_id"
    RECOVERY_PREDECESSOR_CHALLENGE="$predecessor_challenge"
    RECOVERY_PREDECESSOR_PHASE=corrupt_unknown
    RECOVERY_PREDECESSOR_FAILED_PHASE=corrupt_unknown
    RECOVERY_PREDECESSOR_BOOT="$CURRENT_BOOT_IDENTITY"
    RECOVERY_PREDECESSOR_BINARY_SHA="$current_sha"
    write_recovery_handoff_intent "$predecessor_id" "$predecessor_challenge" corrupt_unknown "$RECOVERY_REASON"
    receipt="$LEASE_RECEIPT_DIR/$(receipt_stamp).$predecessor_id.governed-corrupt-recovery-started.meta"
    tmp="$receipt.tmp.$$.$RANDOM"
    {
        printf 'schema=%s\n' agent_bridge.publisher_corrupt_lease_receipt.v0
        printf 'disposition=%s\n' governed_corrupt_recovery_started
        printf 'predecessor_lease_id=%s\n' "$predecessor_id"
        printf 'predecessor_challenge=%s\n' "$predecessor_challenge"
        printf 'lock_inode=%s\n' "$lock_inode"
        printf 'current_binary_sha256=%s\n' "$current_sha"
        printf 'successor_lease_id=%s\n' "$LEASE_ID"
        printf 'successor_challenge=%s\n' "$LEASE_CHALLENGE"
        printf 'reason=%s\n' "$RECOVERY_REASON"
        printf 'recorded_at=%s\n' "$(utc_now)"
    } > "$tmp"
    chmod 600 "$tmp"
    mv -f "$tmp" "$receipt"
    quarantine="$LEASE_QUARANTINE_DIR/$(receipt_stamp).$predecessor_id.$$.$RANDOM.corrupt-recovery-started.lock"
    mv "$deploy_lock" "$quarantine" || die "cannot atomically quarantine corrupt publisher lease"
}

reconcile_existing_lease() {
    local observed_identity rechecked_identity current_sha owner_status quarantine disposition reason failed_phase
    if ! read_active_lease "$ACTIVE_META"; then
        reconcile_corrupt_active_lease
        return 0
    fi
    observed_identity="$(read_lease_identity)"
    set +e
    owner_exact_status
    owner_status=$?
    set -e
    case "$owner_status" in
        0) die "another exact agent-bridge publisher lease is active (pid $R_PID, phase $R_PHASE, lease $R_LEASE_ID, target $R_REAL_PATH)" ;;
        2) die "publisher pid $R_PID exists but its start fingerprint is unreadable; fail closed" ;;
    esac

    # The kernel mutex already excludes every governed publisher and is released
    # by the OS on process death. Re-read the durable identity for audit, but do
    # not add another mkdir-based reclaim lock with its own SIGKILL leak window.
    read_active_lease "$ACTIVE_META" || die "publisher lease changed during reconciliation; fail closed"
    rechecked_identity="$(read_lease_identity)"
    [ "$rechecked_identity" = "$observed_identity" ] ||
        die "publisher lease identity changed during reconciliation; fail closed"
    set +e
    owner_exact_status
    owner_status=$?
    set -e
    case "$owner_status" in
        0) die "publisher lease owner became live during reconciliation; fail closed" ;;
        2) die "publisher pid exists but its start fingerprint became unreadable; fail closed" ;;
    esac
    current_sha="$(sha256_file "$R_REAL_PATH")"
    if [ "${HANDOFF_PRESENT:-0}" -eq 1 ] && [ "${HANDOFF_RESUME_AFTER_RECLAIM:-0}" -eq 1 ]; then
        [ "$current_sha" = "$R_BASELINE" ] || {
            mark_foreign_recovery_required interrupted_recovery_successor_baseline_changed
            die "interrupted pre-mutation recovery successor changed the baseline; governed recovery must be restarted"
        }
        disposition=governed_roll_forward_interrupted_successor_reclaimed
        reason="$RECOVERY_REASON"
    elif [ "${HANDOFF_PRESENT:-0}" -eq 1 ]; then
        disposition=governed_roll_forward_recovery_started
        reason="$RECOVERY_REASON"
        RECOVERY_PREDECESSOR_LEASE_ID="$R_LEASE_ID"
        RECOVERY_PREDECESSOR_CHALLENGE="$R_CHALLENGE"
        RECOVERY_PREDECESSOR_PHASE=recovery_required
        RECOVERY_PREDECESSOR_FAILED_PHASE="${R_FAILED_PHASE:-$R_PHASE}"
        RECOVERY_PREDECESSOR_BOOT="$R_BOOT"
        RECOVERY_PREDECESSOR_BINARY_SHA="$current_sha"
        write_recovery_handoff_intent "$RECOVERY_PREDECESSOR_LEASE_ID" "$RECOVERY_PREDECESSOR_CHALLENGE" \
            "$RECOVERY_PREDECESSOR_PHASE" "$RECOVERY_REASON"
    else case "$R_PHASE" in
        acquired|building|prepared)
            if [ "$current_sha" = "$R_BASELINE" ]; then
                disposition=aborted
                reason=dead_owner_pre_mutation_reclaimed
            else
                mark_foreign_recovery_required pre_mutation_baseline_changed
                die "dead publisher owner has a changed baseline; governed recovery required"
            fi
            ;;
        recovery_required)
            if [ "$RECOVERY_MODE" = roll_forward ]; then
                [ "$R_REAL_PATH" = "$REAL_PATH" ] && [ "$R_SHARED_TARGETS" = "$SHARED_TARGETS" ] ||
                    die "roll-forward recovery invocation does not match the failed publisher targets"
                disposition=governed_roll_forward_recovery_started
                reason="$RECOVERY_REASON"
                RECOVERY_PREDECESSOR_LEASE_ID="$R_LEASE_ID"
                RECOVERY_PREDECESSOR_CHALLENGE="$R_CHALLENGE"
                RECOVERY_PREDECESSOR_PHASE=recovery_required
                RECOVERY_PREDECESSOR_FAILED_PHASE="${R_FAILED_PHASE:-$R_PHASE}"
                RECOVERY_PREDECESSOR_BOOT="$R_BOOT"
                RECOVERY_PREDECESSOR_BINARY_SHA="$current_sha"
                write_recovery_handoff_intent "$RECOVERY_PREDECESSOR_LEASE_ID" "$RECOVERY_PREDECESSOR_CHALLENGE" \
                    "$RECOVERY_PREDECESSOR_PHASE" "$RECOVERY_REASON"
            else
                die "publisher lease requires governed recovery; set roll_forward with a nonempty reason"
            fi
            ;;
        *)
            failed_phase="$R_PHASE"
            mark_foreign_recovery_required "dead_owner_after_$failed_phase"
            die "dead publisher owner reached $R_PHASE; governed recovery required"
            ;;
    esac
    fi
    archive_foreign_receipt "$ACTIVE_META" "$disposition" "$reason" ||
        die "cannot archive the reconciliation-started receipt before releasing the old lease"
    quarantine="$LEASE_QUARANTINE_DIR/$(receipt_stamp).$R_LEASE_ID.$$.$RANDOM.$disposition.lock"
    mv "$deploy_lock" "$quarantine" || die "cannot atomically quarantine reconciled publisher lease"
}

cleanup() {
    local status="${1:-0}" current_sha
    if [ -n "$CLEANUP_WT" ]; then
        if [ "$LEASE_TEST_MODE" = 1 ]; then
            deploy_git -C "$REPO" worktree remove --force "$CLEANUP_WT" >/dev/null 2>&1 || true
        else
            case "$CLEANUP_WT" in
                "$DEPLOY_ROOT/build/worktrees/"*) rm -rf -- "$CLEANUP_WT" 2>/dev/null || true ;;
            esac
        fi
    fi
    [ -n "$CLEANUP_RUNTIME_STAGE" ] && rm -rf "$CLEANUP_RUNTIME_STAGE" 2>/dev/null || true
    [ -n "$CLEANUP_PKG_CONFIG" ] && rm -rf "$CLEANUP_PKG_CONFIG" 2>/dev/null || true
    [ -n "$CLEANUP_BINARY_STAGE" ] && rm -f "$CLEANUP_BINARY_STAGE" 2>/dev/null || true
    [ -n "$CLEANUP_CANDIDATE_SNAPSHOT" ] && rm -f "$CLEANUP_CANDIDATE_SNAPSHOT" 2>/dev/null || true
    [ -n "$CLEANUP_LEASE_INTENT" ] && rm -rf "$CLEANUP_LEASE_INTENT" 2>/dev/null || true
    [ -n "$CLEANUP_FRESH_MCP_TMP" ] && rm -rf "$CLEANUP_FRESH_MCP_TMP" 2>/dev/null || true
    if [ "$LEASE_OWNED" -eq 1 ] && [ "$LEASE_FINALIZED" -eq 0 ] &&
        { [ -e "$RELEASE_INTENT" ] || [ -L "$RELEASE_INTENT" ]; }; then
        # A normal signal may arrive anywhere in the release transaction.
        # Finish its exact journaled move/receipt now; SIGKILL leaves the same
        # intent for the next kernel-mutex holder to settle before admission.
        settle_release_intent
        LEASE_OWNED=0
        LEASE_FINALIZED=1
    fi
    if [ "$LEASE_OWNED" -eq 1 ] && [ "$LEASE_FINALIZED" -eq 0 ]; then
        current_sha="$(sha256_file "$REAL_PATH" 2>/dev/null || printf '%s\n' unknown)"
        case "$LEASE_PHASE" in
            acquired|building|prepared)
                if [ "$current_sha" = "$LEASE_BASELINE_SHA" ]; then
                    release_active_lease aborted "${LEASE_FAILURE_REASON:-exit_status_$status}"
                else
                    LEASE_FAILURE_REASON="pre_mutation_baseline_changed"
                    LEASE_FAILED_PHASE="$LEASE_PHASE"
                    lease_phase_update recovery_required >/dev/null 2>&1 || true
                fi
                ;;
            *)
                LEASE_FAILURE_REASON="${LEASE_FAILURE_REASON:-exit_status_$status}"
                if [ "$LEASE_PHASE" != recovery_required ]; then
                    LEASE_FAILED_PHASE="$LEASE_PHASE"
                    lease_phase_update recovery_required >/dev/null 2>&1 || true
                fi
                ;;
        esac
    fi
}
trap 'status=$?; trap - EXIT; cleanup "$status"; exit "$status"' EXIT

# Serialize the complete build/install/restart transaction within one canonical
# deployment domain. Per-root/per-SHA Cargo targets prevent candidate sharing;
# the installed binary, assets, backups, and launch jobs remain mutable as one
# unit under that domain's publisher lease.
if [ -e "$deploy_lock" ] || [ -L "$deploy_lock" ]; then
    [ -d "$deploy_lock" ] && [ ! -L "$deploy_lock" ] ||
        die "publisher active lease path is not a physical directory: $deploy_lock"
    if [ "$LEASE_TEST_MODE" = 1 ]; then
        protect_owned_directory "$deploy_lock" "publisher active lease directory"
    else
        verify_owned_directory_mode "$deploy_lock" 700 "publisher active lease directory"
    fi
fi
settle_handoff_completion_intent
settle_release_intent
if [ "$LEASE_TEST_MODE" = 1 ]; then
    mkdir -p "$INSTALL_DIR"
else
    ensure_trusted_subdirectory_path \
        "$DEPLOY_ROOT" "$INSTALL_DIR" "canonical deployment bin directory"
fi
LEASE_ID="lease-$(date -u '+%Y%m%dT%H%M%SZ')-$$-$RANDOM"
LEASE_PROCESS_START="$(process_start_fingerprint "$$")" || die "cannot establish publisher process start fingerprint"
LEASE_STARTED_AT="$(utc_now)"
LEASE_BASELINE_SHA="$(sha256_file "$REAL_PATH")"
LEASE_CHALLENGE="$(printf '%s\n' "$LEASE_ID|$LEASE_PROCESS_START|$CURRENT_BOOT_IDENTITY|$REAL_PATH|$LEASE_STARTED_AT" | sha256_text)"
LEASE_PHASE=acquired
LEASE_STATE_SEQ=1
LEASE_STAGED_LOCK="$LEASE_INTENT_DIR/$LEASE_ID.lock"
[ ! -e "$LEASE_STAGED_LOCK" ] || die "publisher lease staging intent already exists: $LEASE_STAGED_LOCK"
mkdir -m 700 "$LEASE_STAGED_LOCK" || die "cannot create publisher lease staging intent"
verify_owned_directory_mode "$LEASE_STAGED_LOCK" 700 "publisher staged lease directory"
CLEANUP_LEASE_INTENT="$LEASE_STAGED_LOCK"
ACTIVE_META="$LEASE_STAGED_LOCK/lease.meta"
write_active_values || die "cannot initialize publisher lease metadata"
protect_owned_directory "$LEASE_STAGED_LOCK" "publisher staged lease directory"
read_active_lease "$ACTIVE_META" && [ "$R_LEASE_ID" = "$LEASE_ID" ] && [ "$R_CHALLENGE" = "$LEASE_CHALLENGE" ] ||
    die "staged publisher lease failed strict self-validation"
STAGED_ACTIVE_META="$ACTIVE_META"
ACTIVE_META="$deploy_lock/lease.meta"
inspect_existing_recovery_handoff
if [ -e "$deploy_lock" ] || [ -L "$deploy_lock" ]; then
    reconcile_existing_lease
fi
if [ "$HANDOFF_RESUME_AFTER_RECLAIM" -eq 1 ]; then
    [ ! -e "$deploy_lock" ] && [ ! -L "$deploy_lock" ] ||
        die "reclaimed recovery successor still owns the active lease path"
    RECOVERY_PREDECESSOR_LEASE_ID="$HANDOFF_ORIGINAL_PREDECESSOR_LEASE_ID"
    RECOVERY_PREDECESSOR_CHALLENGE="$HANDOFF_ORIGINAL_PREDECESSOR_CHALLENGE"
    RECOVERY_PREDECESSOR_PHASE="$HANDOFF_ORIGINAL_PREDECESSOR_PHASE"
    RECOVERY_PREDECESSOR_FAILED_PHASE="$HANDOFF_ORIGINAL_PREDECESSOR_FAILED_PHASE"
    RECOVERY_PREDECESSOR_BOOT="$HANDOFF_ORIGINAL_PREDECESSOR_BOOT"
    RECOVERY_PREDECESSOR_BINARY_SHA="$HANDOFF_ORIGINAL_PREDECESSOR_BINARY_SHA"
    write_recovery_handoff_intent "$RECOVERY_PREDECESSOR_LEASE_ID" "$RECOVERY_PREDECESSOR_CHALLENGE" \
        "$RECOVERY_PREDECESSOR_PHASE" "$RECOVERY_REASON"
fi
[ ! -e "$deploy_lock" ] && [ ! -L "$deploy_lock" ] ||
    die "active publisher lease appeared while the kernel mutex was held"
mkdir -m 700 "$deploy_lock" || die "cannot exclusively claim the active publisher lease path"
protect_owned_directory "$deploy_lock" "publisher active lease directory"
mv "$LEASE_STAGED_LOCK/lease.meta" "$deploy_lock/lease.meta" ||
    die "cannot publish the staged publisher lease metadata"
mv "$LEASE_STAGED_LOCK/pid" "$deploy_lock/pid" ||
    die "cannot publish the staged publisher lease pid"
rmdir "$LEASE_STAGED_LOCK" || die "cannot retire the empty publisher lease staging directory"
ACTIVE_META="$deploy_lock/lease.meta"
read_active_lease "$ACTIVE_META" && [ "$R_LEASE_ID" = "$LEASE_ID" ] && [ "$R_CHALLENGE" = "$LEASE_CHALLENGE" ] ||
    die "published publisher lease identity does not match its staged intent"
CLEANUP_LEASE_INTENT=""
LEASE_OWNED=1
CLEANUP_DEPLOY_LOCK="$deploy_lock"
if ! archive_recovery_handoff acquired; then
    LEASE_FAILURE_REASON=recovery_successor_acquired_receipt_failed
    LEASE_FAILED_PHASE="$LEASE_PHASE"
    lease_phase_update recovery_required || true
    die "cannot bind the governed recovery predecessor to the acquired successor lease"
fi

archive_pending_receipt() {
    local meta="$1" disposition="$2" next_candidate="$3" reason="$4" receipt tmp
    read_pending_admission "$meta" || die "pending-admission metadata is unknown or corrupt; fail closed"
    receipt="$LEASE_RECEIPT_DIR/$(receipt_stamp).$P_LEASE_ID.pending-$disposition.meta"
    tmp="$receipt.tmp.$$.$RANDOM"
    {
        printf 'schema=%s\n' agent_bridge.publisher_pending_admission_receipt.v0
        sed '1d' "$meta"
        printf 'disposition=%s\n' "$disposition"
        printf 'next_candidate_commit=%s\n' "$next_candidate"
        printf 'reason=%s\n' "$(clean_field "$reason")"
        printf 'archived_at=%s\n' "$(utc_now)"
    } > "$tmp"
    chmod 600 "$tmp"
    mv -f "$tmp" "$receipt"
}

archive_pending_completion() {
    local receipt tmp
    [ -n "$CONSUMED_PENDING_ACTION" ] || return 0
    receipt="$LEASE_RECEIPT_DIR/$(receipt_stamp).$CONSUMED_PENDING_LEASE_ID.pending-$CONSUMED_PENDING_ACTION-completed.meta"
    tmp="$receipt.tmp.$$.$RANDOM"
    {
        printf 'schema=%s\n' agent_bridge.publisher_pending_transition_receipt.v0
        printf 'disposition=%s\n' "$CONSUMED_PENDING_ACTION-completed"
        printf 'predecessor_lease_id=%s\n' "$CONSUMED_PENDING_LEASE_ID"
        printf 'predecessor_challenge=%s\n' "$CONSUMED_PENDING_CHALLENGE"
        printf 'predecessor_candidate_commit=%s\n' "$CONSUMED_PENDING_CANDIDATE"
        printf 'successor_lease_id=%s\n' "$LEASE_ID"
        printf 'successor_challenge=%s\n' "$LEASE_CHALLENGE"
        printf 'successor_candidate_commit=%s\n' "$LEASE_CANDIDATE"
        printf 'completed_at=%s\n' "$(utc_now)"
    } > "$tmp"
    chmod 600 "$tmp"
    mv -f "$tmp" "$receipt"
}

pending_fingerprint_matches() {
    local current_sha current_inode current_mode current_assets_sha
    current_sha="$(sha256_file "$P_REAL_PATH")"
    current_inode="$(file_inode "$P_REAL_PATH" 2>/dev/null || printf '%s\n' absent)"
    current_mode="$(file_mode "$P_REAL_PATH")"
    current_assets_sha="$(installed_assets_sha256)"
    [ "$current_sha" = "$P_SHA" ] && [ "$current_inode" = "$P_INODE" ] &&
        [ "$current_mode" = "$P_MODE" ] &&
        [ "$current_assets_sha" = "$P_ASSETS_SHA" ]
}

inspect_pending_for_candidate() {
    local candidate="$1"
    PENDING_ACTION=none
    [ -e "$PENDING_ADMISSION" ] || return 0
    read_pending_admission "$PENDING_ADMISSION" ||
        die "pending-admission metadata is missing, unknown, or corrupt; fail closed"
    [ "$SUPERSEDE_PENDING" -eq 0 ] || [ "$SUPERSEDE_EXPECTED_CHALLENGE" = "$P_CHALLENGE" ] ||
        die "explicit supersede challenge does not match the exact pending admission"
    PENDING_OBSERVED_SHA256="$(sha256_file "$PENDING_ADMISSION")"
    if ! pending_fingerprint_matches; then
        if [ "$RECOVERY_MODE" = roll_forward ] && [ "$SUPERSEDE_PENDING" -eq 1 ]; then
            PENDING_ACTION=recovery_roll_forward
            return 0
        fi
        die "pending-admission fingerprint no longer matches the installed binary/assets; governed recovery plus exact pending supersede is required"
    fi
    if [ "$P_CANDIDATE" = "$candidate" ] && [ "$P_REAL_PATH" = "$REAL_PATH" ] &&
            [ "$P_SHARED_TARGETS" = "$SHARED_TARGETS" ]; then
        if [ -n "$RECOVERY_PREDECESSOR_LEASE_ID" ]; then
            if [ "$P_LEASE_ID" = "$RECOVERY_PREDECESSOR_LEASE_ID" ] &&
                    [ "$P_CHALLENGE" = "$RECOVERY_PREDECESSOR_CHALLENGE" ]; then
                PENDING_ACTION=recovery_roll_forward
            elif [ "$SUPERSEDE_PENDING" -eq 1 ]; then
                PENDING_ACTION=supersede
            else
                die "same-candidate pending admission is unrelated to the recovery predecessor; exact pending supersede is required"
            fi
        elif [ "$FORCE_REINSTALL" -eq 0 ]; then
            say "publisher lease: candidate $candidate is already installed with matching pending admission; no build, overwrite, or restart performed"
            release_active_lease idempotent_pending_match same_candidate_installed_fingerprint_match
            exit 0
        else
            PENDING_ACTION=force_reinstall
        fi
    elif [ "$SUPERSEDE_PENDING" -eq 1 ]; then
        PENDING_ACTION=supersede
    else
        die "a different candidate or target still has unverified pending admission; explicit audited supersede is required"
    fi
}

consume_pending_before_mutation() {
    local candidate="$1" pending_quarantine observed_sha
    case "$PENDING_ACTION" in
        none)
            [ ! -e "$PENDING_ADMISSION" ] ||
                die "pending-admission appeared after candidate inspection; fail closed"
            ;;
        force_reinstall|supersede|recovery_roll_forward)
            observed_sha="$(sha256_file "$PENDING_ADMISSION")"
            [ "$observed_sha" = "$PENDING_OBSERVED_SHA256" ] ||
                die "pending-admission identity changed after inspection; fail closed"
            read_pending_admission "$PENDING_ADMISSION" ||
                die "pending-admission changed before mutation; fail closed"
            [ "$SUPERSEDE_PENDING" -eq 0 ] || [ "$SUPERSEDE_EXPECTED_CHALLENGE" = "$P_CHALLENGE" ] ||
                die "pending-admission challenge changed before mutation; fail closed"
            if [ "$PENDING_ACTION" != recovery_roll_forward ]; then
                pending_fingerprint_matches ||
                    die "pending-admission fingerprint changed before mutation; governed recovery required"
            fi
            CONSUMED_PENDING_LEASE_ID="$P_LEASE_ID"
            CONSUMED_PENDING_CHALLENGE="$P_CHALLENGE"
            CONSUMED_PENDING_CANDIDATE="$P_CANDIDATE"
            if [ "$PENDING_ACTION" = force_reinstall ]; then
                [ "$P_CANDIDATE" = "$candidate" ] && [ "$P_REAL_PATH" = "$REAL_PATH" ] ||
                    die "force-reinstall pending identity changed; fail closed"
                CONSUMED_PENDING_ACTION=force-reinstall
                archive_pending_receipt "$PENDING_ADMISSION" force-reinstall-started "$candidate" "$FORCE_REASON"
            elif [ "$PENDING_ACTION" = recovery_roll_forward ]; then
                CONSUMED_PENDING_ACTION=recovery-roll-forward
                archive_pending_receipt "$PENDING_ADMISSION" recovery-roll-forward-started "$candidate" "$RECOVERY_REASON"
            else
                CONSUMED_PENDING_ACTION=supersede
                archive_pending_receipt "$PENDING_ADMISSION" supersede-started "$candidate" "$SUPERSEDE_REASON"
            fi
            pending_quarantine="$LEASE_QUARANTINE_DIR/$(receipt_stamp).$P_LEASE_ID.$$.$RANDOM.pending-$PENDING_ACTION.meta"
            mv "$PENDING_ADMISSION" "$pending_quarantine" ||
                die "cannot atomically quarantine consumed pending admission"
            ;;
        *) die "unknown pending-admission action: $PENDING_ACTION" ;;
    esac
}

write_pending_admission() {
    local candidate="$1" installed_sha installed_inode installed_mode installed_assets installed_at tmp
    [ ! -e "$PENDING_ADMISSION" ] || die "pending-admission already exists before commit receipt; fail closed"
    installed_sha="$(sha256_file "$REAL_PATH")"
    installed_inode="$(file_inode "$REAL_PATH")" || die "cannot read installed binary inode"
    installed_mode="$(file_mode "$REAL_PATH")"
    installed_assets="$(installed_assets_sha256)"
    [ "$installed_sha" != absent ] || die "installed binary missing before pending admission"
    installed_at="$(utc_now)"
    tmp="$PENDING_ADMISSION.tmp.$$.$RANDOM"
    {
        printf 'schema=%s\n' agent_bridge.publisher_pending_admission.v0
        printf 'lease_id=%s\n' "$LEASE_ID"
        printf 'challenge=%s\n' "$LEASE_CHALLENGE"
        printf 'real_path=%s\n' "$REAL_PATH"
        printf 'shared_targets=%s\n' "$SHARED_TARGETS"
        printf 'candidate_commit=%s\n' "$candidate"
        printf 'installed_binary_sha256=%s\n' "$installed_sha"
        printf 'installed_binary_inode=%s\n' "$installed_inode"
        printf 'installed_binary_mode=%s\n' "$installed_mode"
        printf 'installed_assets_sha256=%s\n' "$installed_assets"
        printf 'installed_at=%s\n' "$installed_at"
        printf 'fresh_mcp=%s\n' unverified
        printf 'force_reinstall=%s\n' "$FORCE_REINSTALL"
        printf 'force_reason=%s\n' "$FORCE_REASON"
    } > "$tmp"
    chmod 600 "$tmp"
    mv -f "$tmp" "$PENDING_ADMISSION"
}

domain_separated_meta_sha256() {
    local domain="$1" file="$2" body_lines="$3"
    case "$body_lines" in ''|*[!0-9]*) return 1 ;; esac
    {
        printf 'domain=%s\n' "$domain"
        sed -n "1,${body_lines}p" "$file"
    } | sha256_text
}

read_legacy_fresh_mcp_probe_fixture() {
    local file="$1" keys legacy_evidence
    [ "$LEASE_TEST_MODE" = 1 ] && metadata_file_is_trusted "$file" || return 1
    keys="$(meta_keys "$file")"
    [ "$keys" = "schema,server_name,server_version,protocol_version,build_git_sha,toolset,tool_count,capabilities_tool_present,probe_method,evidence_sha256" ] || return 1
    [ "$(wc -l < "$file" | tr -d ' ')" = 10 ] || return 1
    F_SCHEMA="$(meta_value "$file" 1 schema)" || return 1
    F_SERVER_NAME="$(meta_value "$file" 2 server_name)" || return 1
    F_SERVER_VERSION="$(meta_value "$file" 3 server_version)" || return 1
    F_PROTOCOL_VERSION="$(meta_value "$file" 4 protocol_version)" || return 1
    F_BUILD_SHA="$(meta_value "$file" 5 build_git_sha)" || return 1
    F_TOOLSET="$(meta_value "$file" 6 toolset)" || return 1
    F_TOOL_COUNT="$(meta_value "$file" 7 tool_count)" || return 1
    F_CAPABILITIES_PRESENT="$(meta_value "$file" 8 capabilities_tool_present)" || return 1
    F_METHOD="$(meta_value "$file" 9 probe_method)" || return 1
    F_EVIDENCE_SHA="$(meta_value "$file" 10 evidence_sha256)" || return 1
    case "$F_TOOL_COUNT" in ''|*[!0-9]*) return 1 ;; esac
    legacy_evidence="$({
        sed -n '1,9p' "$file"
    } | sha256_text)"
    [ "$F_SCHEMA" = agent_bridge.publisher_fresh_mcp_probe.v0 ] &&
        [ "$F_SERVER_NAME" = agent-bridge ] &&
        [ "$F_PROTOCOL_VERSION" = 2024-11-05 ] &&
        [ "$F_CAPABILITIES_PRESENT" = true ] &&
        [ "$F_METHOD" = independent_stdio_exact_installed_binary ] &&
        is_safe_candidate "$F_SERVER_VERSION" && [ "$F_TOOLSET" = codex-essential ] &&
        printf '%s\n' "$F_BUILD_SHA" | grep -Eq '^[0-9a-f]{12}$' &&
        [ "$legacy_evidence" = "$F_EVIDENCE_SHA" ]
}

read_fresh_mcp_probe_observation() {
    local file="$1" keys
    metadata_file_is_trusted "$file" || return 1
    keys="$(meta_keys "$file")"
    [ "$keys" = "schema,probe_nonce,probe_started_at,probe_finished_at,server_name,server_version,protocol_version,build_git_sha,toolset,tool_count,capabilities_tool_present,probe_method,copied_binary_sha256" ] || return 1
    [ "$(wc -l < "$file" | tr -d ' ')" = 13 ] || return 1
    F_SCHEMA="$(meta_value "$file" 1 schema)" || return 1
    F_NONCE="$(meta_value "$file" 2 probe_nonce)" || return 1
    F_STARTED_AT="$(meta_value "$file" 3 probe_started_at)" || return 1
    F_FINISHED_AT="$(meta_value "$file" 4 probe_finished_at)" || return 1
    F_SERVER_NAME="$(meta_value "$file" 5 server_name)" || return 1
    F_SERVER_VERSION="$(meta_value "$file" 6 server_version)" || return 1
    F_PROTOCOL_VERSION="$(meta_value "$file" 7 protocol_version)" || return 1
    F_BUILD_SHA="$(meta_value "$file" 8 build_git_sha)" || return 1
    F_TOOLSET="$(meta_value "$file" 9 toolset)" || return 1
    F_TOOL_COUNT="$(meta_value "$file" 10 tool_count)" || return 1
    F_CAPABILITIES_PRESENT="$(meta_value "$file" 11 capabilities_tool_present)" || return 1
    F_METHOD="$(meta_value "$file" 12 probe_method)" || return 1
    F_COPY_SHA="$(meta_value "$file" 13 copied_binary_sha256)" || return 1
    case "$F_TOOL_COUNT" in ''|*[!0-9]*) return 1 ;; esac
    [ "$F_SCHEMA" = agent_bridge.publisher_fresh_mcp_probe.v1 ] && is_sha256_value "$F_NONCE" &&
        [ -n "$F_STARTED_AT" ] && [ -n "$F_FINISHED_AT" ] &&
        [ "$F_SERVER_NAME" = agent-bridge ] && [ "$F_PROTOCOL_VERSION" = 2024-11-05 ] &&
        [ "$F_CAPABILITIES_PRESENT" = true ] &&
        [ "$F_METHOD" = independent_stdio_private_exact_binary_copy ] &&
        is_safe_candidate "$F_SERVER_VERSION" && [ "$F_TOOLSET" = codex-essential ] &&
        is_sha256_value "$F_COPY_SHA" &&
        printf '%s\n' "$F_BUILD_SHA" | grep -Eq '^[0-9a-f]{12}$'
}

write_bound_fresh_mcp_probe() {
    local target="$1" tmp digest
    tmp="$target.bound.$$.$RANDOM"
    {
        printf 'schema=%s\n' agent_bridge.publisher_fresh_mcp_probe.v1
        printf 'probe_nonce=%s\n' "$F_NONCE"
        printf 'probe_started_at=%s\n' "$F_STARTED_AT"
        printf 'probe_finished_at=%s\n' "$F_FINISHED_AT"
        printf 'server_name=%s\n' "$F_SERVER_NAME"
        printf 'server_version=%s\n' "$F_SERVER_VERSION"
        printf 'protocol_version=%s\n' "$F_PROTOCOL_VERSION"
        printf 'build_git_sha=%s\n' "$F_BUILD_SHA"
        printf 'toolset=%s\n' "$F_TOOLSET"
        printf 'tool_count=%s\n' "$F_TOOL_COUNT"
        printf 'capabilities_tool_present=%s\n' "$F_CAPABILITIES_PRESENT"
        printf 'probe_method=%s\n' "$F_METHOD"
        printf 'copied_binary_sha256=%s\n' "$F_COPY_SHA"
        printf 'pending_sha256=%s\n' "$PENDING_PROBE_SHA"
        printf 'pending_lease_id=%s\n' "$P_LEASE_ID"
        printf 'pending_challenge=%s\n' "$P_CHALLENGE"
        printf 'candidate_commit=%s\n' "$P_CANDIDATE"
        printf 'real_path=%s\n' "$P_REAL_PATH"
        printf 'shared_targets=%s\n' "$P_SHARED_TARGETS"
        printf 'installed_binary_sha256=%s\n' "$P_SHA"
        printf 'installed_binary_inode=%s\n' "$P_INODE"
        printf 'installed_binary_mode=%s\n' "$P_MODE"
        printf 'installed_assets_sha256=%s\n' "$P_ASSETS_SHA"
        printf 'pending_installed_at=%s\n' "$P_INSTALLED_AT"
        printf 'admission_lease_id=%s\n' "$LEASE_ID"
        printf 'admission_challenge=%s\n' "$LEASE_CHALLENGE"
    } > "$tmp"
    digest="$(domain_separated_meta_sha256 agent_bridge.publisher_fresh_mcp_probe_evidence.v1 "$tmp" 26)"
    printf 'evidence_sha256=%s\n' "$digest" >> "$tmp"
    chmod 600 "$tmp"
    mv -f "$tmp" "$target"
}

read_fresh_mcp_probe() {
    local file="$1" keys
    metadata_file_is_trusted "$file" || return 1
    keys="$(meta_keys "$file")"
    [ "$keys" = "schema,probe_nonce,probe_started_at,probe_finished_at,server_name,server_version,protocol_version,build_git_sha,toolset,tool_count,capabilities_tool_present,probe_method,copied_binary_sha256,pending_sha256,pending_lease_id,pending_challenge,candidate_commit,real_path,shared_targets,installed_binary_sha256,installed_binary_inode,installed_binary_mode,installed_assets_sha256,pending_installed_at,admission_lease_id,admission_challenge,evidence_sha256" ] || return 1
    [ "$(wc -l < "$file" | tr -d ' ')" = 27 ] || return 1
    F_SCHEMA="$(meta_value "$file" 1 schema)" || return 1
    F_NONCE="$(meta_value "$file" 2 probe_nonce)" || return 1
    F_STARTED_AT="$(meta_value "$file" 3 probe_started_at)" || return 1
    F_FINISHED_AT="$(meta_value "$file" 4 probe_finished_at)" || return 1
    F_SERVER_NAME="$(meta_value "$file" 5 server_name)" || return 1
    F_SERVER_VERSION="$(meta_value "$file" 6 server_version)" || return 1
    F_PROTOCOL_VERSION="$(meta_value "$file" 7 protocol_version)" || return 1
    F_BUILD_SHA="$(meta_value "$file" 8 build_git_sha)" || return 1
    F_TOOLSET="$(meta_value "$file" 9 toolset)" || return 1
    F_TOOL_COUNT="$(meta_value "$file" 10 tool_count)" || return 1
    F_CAPABILITIES_PRESENT="$(meta_value "$file" 11 capabilities_tool_present)" || return 1
    F_METHOD="$(meta_value "$file" 12 probe_method)" || return 1
    F_COPY_SHA="$(meta_value "$file" 13 copied_binary_sha256)" || return 1
    F_PENDING_SHA="$(meta_value "$file" 14 pending_sha256)" || return 1
    F_PENDING_LEASE_ID="$(meta_value "$file" 15 pending_lease_id)" || return 1
    F_PENDING_CHALLENGE="$(meta_value "$file" 16 pending_challenge)" || return 1
    F_CANDIDATE="$(meta_value "$file" 17 candidate_commit)" || return 1
    F_REAL_PATH="$(meta_value "$file" 18 real_path)" || return 1
    F_SHARED_TARGETS="$(meta_value "$file" 19 shared_targets)" || return 1
    F_INSTALLED_SHA="$(meta_value "$file" 20 installed_binary_sha256)" || return 1
    F_INSTALLED_INODE="$(meta_value "$file" 21 installed_binary_inode)" || return 1
    F_INSTALLED_MODE="$(meta_value "$file" 22 installed_binary_mode)" || return 1
    F_INSTALLED_ASSETS_SHA="$(meta_value "$file" 23 installed_assets_sha256)" || return 1
    F_PENDING_INSTALLED_AT="$(meta_value "$file" 24 pending_installed_at)" || return 1
    F_ADMISSION_LEASE_ID="$(meta_value "$file" 25 admission_lease_id)" || return 1
    F_ADMISSION_CHALLENGE="$(meta_value "$file" 26 admission_challenge)" || return 1
    F_EVIDENCE_SHA="$(meta_value "$file" 27 evidence_sha256)" || return 1
    case "$F_TOOL_COUNT" in ''|*[!0-9]*) return 1 ;; esac
    case "$F_INSTALLED_INODE" in ''|*[!0-9]*) return 1 ;; esac
    case "$F_INSTALLED_MODE" in ''|*[!0-7]*) return 1 ;; esac
    [ "$F_SCHEMA" = agent_bridge.publisher_fresh_mcp_probe.v1 ] && is_sha256_value "$F_NONCE" &&
        [ -n "$F_STARTED_AT" ] && [ -n "$F_FINISHED_AT" ] && [ "$F_SERVER_NAME" = agent-bridge ] &&
        [ "$F_PROTOCOL_VERSION" = 2024-11-05 ] && [ "$F_CAPABILITIES_PRESENT" = true ] &&
        [ "$F_METHOD" = independent_stdio_private_exact_binary_copy ] &&
        is_safe_candidate "$F_SERVER_VERSION" && [ "$F_TOOLSET" = codex-essential ] &&
        printf '%s\n' "$F_BUILD_SHA" | grep -Eq '^[0-9a-f]{12}$' &&
        is_sha256_value "$F_COPY_SHA" && is_sha256_value "$F_PENDING_SHA" &&
        is_safe_id "$F_PENDING_LEASE_ID" && is_sha256_value "$F_PENDING_CHALLENGE" &&
        printf '%s\n' "$F_CANDIDATE" | grep -Eq '^[0-9a-f]{40}$' &&
        case "$F_REAL_PATH" in /*) true ;; *) false ;; esac && [ -n "$F_SHARED_TARGETS" ] &&
        is_sha256_value "$F_INSTALLED_SHA" && is_sha256_value "$F_INSTALLED_ASSETS_SHA" &&
        is_safe_id "$F_ADMISSION_LEASE_ID" && is_sha256_value "$F_ADMISSION_CHALLENGE" &&
        is_sha256_value "$F_EVIDENCE_SHA" &&
        [ "$F_EVIDENCE_SHA" = "$(domain_separated_meta_sha256 agent_bridge.publisher_fresh_mcp_probe_evidence.v1 "$file" 26)" ]
}

read_fresh_mcp_admission_intent() {
    local file="$1" keys
    metadata_file_is_trusted "$file" || return 1
    keys="$(meta_keys "$file")"
    [ "$keys" = "schema,pending_lease_id,pending_challenge,candidate_commit,real_path,shared_targets,pending_sha256,installed_binary_sha256,installed_binary_inode,installed_binary_mode,installed_assets_sha256,pending_installed_at,admission_lease_id,admission_challenge,receipt_path,quarantine_path,probe_schema,probe_nonce,probe_started_at,probe_finished_at,probe_server_name,probe_server_version,probe_protocol_version,probe_build_git_sha,probe_toolset,probe_tool_count,probe_capabilities_tool_present,probe_method,probe_copied_binary_sha256,probe_evidence_sha256,admission_binding_sha256" ] || return 1
    [ "$(wc -l < "$file" | tr -d ' ')" = 31 ] || return 1
    A_SCHEMA="$(meta_value "$file" 1 schema)" || return 1
    A_PENDING_LEASE_ID="$(meta_value "$file" 2 pending_lease_id)" || return 1
    A_PENDING_CHALLENGE="$(meta_value "$file" 3 pending_challenge)" || return 1
    A_CANDIDATE="$(meta_value "$file" 4 candidate_commit)" || return 1
    A_REAL_PATH="$(meta_value "$file" 5 real_path)" || return 1
    A_SHARED_TARGETS="$(meta_value "$file" 6 shared_targets)" || return 1
    A_PENDING_SHA="$(meta_value "$file" 7 pending_sha256)" || return 1
    A_INSTALLED_SHA="$(meta_value "$file" 8 installed_binary_sha256)" || return 1
    A_INSTALLED_INODE="$(meta_value "$file" 9 installed_binary_inode)" || return 1
    A_INSTALLED_MODE="$(meta_value "$file" 10 installed_binary_mode)" || return 1
    A_INSTALLED_ASSETS_SHA="$(meta_value "$file" 11 installed_assets_sha256)" || return 1
    A_PENDING_INSTALLED_AT="$(meta_value "$file" 12 pending_installed_at)" || return 1
    A_ADMISSION_LEASE_ID="$(meta_value "$file" 13 admission_lease_id)" || return 1
    A_ADMISSION_CHALLENGE="$(meta_value "$file" 14 admission_challenge)" || return 1
    A_RECEIPT_PATH="$(meta_value "$file" 15 receipt_path)" || return 1
    A_QUARANTINE_PATH="$(meta_value "$file" 16 quarantine_path)" || return 1
    A_PROBE_SCHEMA="$(meta_value "$file" 17 probe_schema)" || return 1
    A_PROBE_NONCE="$(meta_value "$file" 18 probe_nonce)" || return 1
    A_PROBE_STARTED_AT="$(meta_value "$file" 19 probe_started_at)" || return 1
    A_PROBE_FINISHED_AT="$(meta_value "$file" 20 probe_finished_at)" || return 1
    A_PROBE_SERVER_NAME="$(meta_value "$file" 21 probe_server_name)" || return 1
    A_PROBE_SERVER_VERSION="$(meta_value "$file" 22 probe_server_version)" || return 1
    A_PROBE_PROTOCOL_VERSION="$(meta_value "$file" 23 probe_protocol_version)" || return 1
    A_PROBE_BUILD_SHA="$(meta_value "$file" 24 probe_build_git_sha)" || return 1
    A_PROBE_TOOLSET="$(meta_value "$file" 25 probe_toolset)" || return 1
    A_PROBE_TOOL_COUNT="$(meta_value "$file" 26 probe_tool_count)" || return 1
    A_PROBE_CAPABILITIES_PRESENT="$(meta_value "$file" 27 probe_capabilities_tool_present)" || return 1
    A_PROBE_METHOD="$(meta_value "$file" 28 probe_method)" || return 1
    A_PROBE_COPY_SHA="$(meta_value "$file" 29 probe_copied_binary_sha256)" || return 1
    A_PROBE_EVIDENCE_SHA="$(meta_value "$file" 30 probe_evidence_sha256)" || return 1
    A_BINDING_SHA="$(meta_value "$file" 31 admission_binding_sha256)" || return 1
    case "$A_PROBE_TOOL_COUNT" in ''|*[!0-9]*) return 1 ;; esac
    case "$A_INSTALLED_INODE" in ''|*[!0-9]*) return 1 ;; esac
    case "$A_INSTALLED_MODE" in ''|*[!0-7]*) return 1 ;; esac
    [ "$A_SCHEMA" = agent_bridge.publisher_fresh_mcp_admission_intent.v1 ] &&
        is_safe_id "$A_PENDING_LEASE_ID" && is_sha256_value "$A_PENDING_CHALLENGE" &&
        printf '%s\n' "$A_CANDIDATE" | grep -Eq '^[0-9a-f]{40}$' &&
        case "$A_REAL_PATH" in /*) true ;; *) false ;; esac && [ -n "$A_SHARED_TARGETS" ] &&
        is_sha256_value "$A_PENDING_SHA" && is_sha256_value "$A_INSTALLED_SHA" &&
        is_sha256_value "$A_INSTALLED_ASSETS_SHA" &&
        is_safe_id "$A_ADMISSION_LEASE_ID" && is_sha256_value "$A_ADMISSION_CHALLENGE" &&
        [ "$A_PROBE_SCHEMA" = agent_bridge.publisher_fresh_mcp_probe.v1 ] &&
        is_sha256_value "$A_PROBE_NONCE" && [ -n "$A_PROBE_STARTED_AT" ] && [ -n "$A_PROBE_FINISHED_AT" ] &&
        [ "$A_PROBE_SERVER_NAME" = agent-bridge ] &&
        is_safe_candidate "$A_PROBE_SERVER_VERSION" &&
        [ "$A_PROBE_PROTOCOL_VERSION" = 2024-11-05 ] &&
        [ "$A_PROBE_BUILD_SHA" = "${A_CANDIDATE:0:12}" ] &&
        [ "$A_PROBE_TOOLSET" = codex-essential ] &&
        [ "$A_PROBE_CAPABILITIES_PRESENT" = true ] &&
        [ "$A_PROBE_METHOD" = independent_stdio_private_exact_binary_copy ] &&
        is_sha256_value "$A_PROBE_COPY_SHA" && [ "$A_PROBE_COPY_SHA" = "$A_INSTALLED_SHA" ] &&
        is_sha256_value "$A_PROBE_EVIDENCE_SHA" && is_sha256_value "$A_BINDING_SHA" &&
        [ "$A_BINDING_SHA" = "$(domain_separated_meta_sha256 agent_bridge.publisher_fresh_mcp_admission_intent.v1 "$file" 30)" ]
}

write_fresh_mcp_admission_intent() {
    local pending_sha="$1" receipt="$2" quarantine="$3" tmp binding
    [ ! -e "$FRESH_MCP_ADMISSION_INTENT" ] && [ ! -L "$FRESH_MCP_ADMISSION_INTENT" ] ||
        die "an unsettled fresh MCP admission intent already exists"
    tmp="$FRESH_MCP_ADMISSION_INTENT.tmp.$$.$RANDOM"
    {
        printf 'schema=%s\n' agent_bridge.publisher_fresh_mcp_admission_intent.v1
        printf 'pending_lease_id=%s\n' "$P_LEASE_ID"
        printf 'pending_challenge=%s\n' "$P_CHALLENGE"
        printf 'candidate_commit=%s\n' "$P_CANDIDATE"
        printf 'real_path=%s\n' "$P_REAL_PATH"
        printf 'shared_targets=%s\n' "$P_SHARED_TARGETS"
        printf 'pending_sha256=%s\n' "$pending_sha"
        printf 'installed_binary_sha256=%s\n' "$P_SHA"
        printf 'installed_binary_inode=%s\n' "$P_INODE"
        printf 'installed_binary_mode=%s\n' "$P_MODE"
        printf 'installed_assets_sha256=%s\n' "$P_ASSETS_SHA"
        printf 'pending_installed_at=%s\n' "$P_INSTALLED_AT"
        printf 'admission_lease_id=%s\n' "$LEASE_ID"
        printf 'admission_challenge=%s\n' "$LEASE_CHALLENGE"
        printf 'receipt_path=%s\n' "$receipt"
        printf 'quarantine_path=%s\n' "$quarantine"
        printf 'probe_schema=%s\n' "$F_SCHEMA"
        printf 'probe_nonce=%s\n' "$F_NONCE"
        printf 'probe_started_at=%s\n' "$F_STARTED_AT"
        printf 'probe_finished_at=%s\n' "$F_FINISHED_AT"
        printf 'probe_server_name=%s\n' "$F_SERVER_NAME"
        printf 'probe_server_version=%s\n' "$F_SERVER_VERSION"
        printf 'probe_protocol_version=%s\n' "$F_PROTOCOL_VERSION"
        printf 'probe_build_git_sha=%s\n' "$F_BUILD_SHA"
        printf 'probe_toolset=%s\n' "$F_TOOLSET"
        printf 'probe_tool_count=%s\n' "$F_TOOL_COUNT"
        printf 'probe_capabilities_tool_present=%s\n' "$F_CAPABILITIES_PRESENT"
        printf 'probe_method=%s\n' "$F_METHOD"
        printf 'probe_copied_binary_sha256=%s\n' "$F_COPY_SHA"
        printf 'probe_evidence_sha256=%s\n' "$F_EVIDENCE_SHA"
    } > "$tmp"
    binding="$(domain_separated_meta_sha256 agent_bridge.publisher_fresh_mcp_admission_intent.v1 "$tmp" 30)"
    printf 'admission_binding_sha256=%s\n' "$binding" >> "$tmp"
    chmod 600 "$tmp"
    mv "$tmp" "$FRESH_MCP_ADMISSION_INTENT" ||
        die "cannot atomically publish fresh MCP admission intent"
    read_fresh_mcp_admission_intent "$FRESH_MCP_ADMISSION_INTENT" &&
        [ "$A_PENDING_SHA" = "$pending_sha" ] && [ "$A_RECEIPT_PATH" = "$receipt" ] &&
        [ "$A_QUARANTINE_PATH" = "$quarantine" ] ||
        die "fresh MCP admission intent failed strict self-validation"
}

settle_fresh_mcp_admission_intent() {
    local source prepared receipt_leaf quarantine_leaf receipt_binding
    FRESH_MCP_ADMISSION_SETTLED=0
    [ -e "$FRESH_MCP_ADMISSION_INTENT" ] || [ -L "$FRESH_MCP_ADMISSION_INTENT" ] || return 0
    [ ! -L "$FRESH_MCP_ADMISSION_INTENT" ] || die "fresh MCP admission intent must not be a symlink"
    read_fresh_mcp_admission_intent "$FRESH_MCP_ADMISSION_INTENT" ||
        die "fresh MCP admission intent is unknown or corrupt; fail closed"
    [ "$A_REAL_PATH" = "$REAL_PATH" ] && [ "$A_SHARED_TARGETS" = "$SHARED_TARGETS" ] ||
        die "fresh MCP admission intent targets do not match this publisher"
    case "$A_RECEIPT_PATH" in "$LEASE_RECEIPT_DIR"/*.meta) ;; *) die "fresh MCP admission receipt escapes the fixed receipt root" ;; esac
    case "$A_QUARANTINE_PATH" in "$LEASE_QUARANTINE_DIR"/*.meta) ;; *) die "fresh MCP admission quarantine escapes the fixed quarantine root" ;; esac
    receipt_leaf="${A_RECEIPT_PATH#"$LEASE_RECEIPT_DIR/"}"
    quarantine_leaf="${A_QUARANTINE_PATH#"$LEASE_QUARANTINE_DIR/"}"
    case "$receipt_leaf" in ''|*/*) die "fresh MCP admission receipt must be a direct child of the fixed receipt root" ;; esac
    case "$quarantine_leaf" in ''|*/*) die "fresh MCP admission quarantine must be a direct child of the fixed quarantine root" ;; esac

    if [ -e "$A_QUARANTINE_PATH" ] || [ -L "$A_QUARANTINE_PATH" ]; then
        [ ! -L "$A_QUARANTINE_PATH" ] && [ -f "$A_QUARANTINE_PATH" ] ||
            die "fresh MCP admitted pending quarantine is not a physical file"
        [ ! -e "$PENDING_ADMISSION" ] && [ ! -L "$PENDING_ADMISSION" ] ||
            die "fresh MCP admission intent has both canonical and quarantined pending state"
        source="$A_QUARANTINE_PATH"
    elif [ -e "$PENDING_ADMISSION" ] || [ -L "$PENDING_ADMISSION" ]; then
        [ ! -L "$PENDING_ADMISSION" ] && [ -f "$PENDING_ADMISSION" ] ||
            die "fresh MCP pending admission is not a physical file"
        source="$PENDING_ADMISSION"
    else
        die "fresh MCP admission intent has neither canonical nor quarantined pending state"
    fi
    [ "$(sha256_file "$source")" = "$A_PENDING_SHA" ] ||
        die "fresh MCP pending admission does not match its completion intent"
    read_pending_admission "$source" || die "fresh MCP pending admission is corrupt"
    [ "$P_LEASE_ID" = "$A_PENDING_LEASE_ID" ] && [ "$P_CHALLENGE" = "$A_PENDING_CHALLENGE" ] &&
        [ "$P_CANDIDATE" = "$A_CANDIDATE" ] && [ "$P_REAL_PATH" = "$A_REAL_PATH" ] &&
        [ "$P_SHARED_TARGETS" = "$A_SHARED_TARGETS" ] &&
        [ "$P_SHA" = "$A_INSTALLED_SHA" ] && [ "$P_INODE" = "$A_INSTALLED_INODE" ] &&
        [ "$P_MODE" = "$A_INSTALLED_MODE" ] && [ "$P_ASSETS_SHA" = "$A_INSTALLED_ASSETS_SHA" ] &&
        [ "$P_INSTALLED_AT" = "$A_PENDING_INSTALLED_AT" ] ||
        die "fresh MCP pending admission identity does not match its completion intent"
    pending_fingerprint_matches ||
        die "fresh MCP admitted binary/assets no longer match the completion intent"

    prepared="$A_RECEIPT_PATH.prepared.$$.$RANDOM"
    {
        printf 'schema=%s\n' agent_bridge.publisher_fresh_mcp_admission.v1
        printf 'pending_lease_id=%s\n' "$P_LEASE_ID"
        printf 'pending_challenge=%s\n' "$P_CHALLENGE"
        printf 'candidate_commit=%s\n' "$P_CANDIDATE"
        printf 'real_path=%s\n' "$P_REAL_PATH"
        printf 'shared_targets=%s\n' "$P_SHARED_TARGETS"
        printf 'installed_binary_sha256=%s\n' "$P_SHA"
        printf 'installed_binary_inode=%s\n' "$P_INODE"
        printf 'installed_binary_mode=%s\n' "$P_MODE"
        printf 'installed_assets_sha256=%s\n' "$P_ASSETS_SHA"
        printf 'pending_installed_at=%s\n' "$P_INSTALLED_AT"
        printf 'admission_lease_id=%s\n' "$A_ADMISSION_LEASE_ID"
        printf 'admission_challenge=%s\n' "$A_ADMISSION_CHALLENGE"
        printf 'fresh_mcp=%s\n' verified
        printf 'probe_schema=%s\n' "$A_PROBE_SCHEMA"
        printf 'probe_nonce=%s\n' "$A_PROBE_NONCE"
        printf 'probe_started_at=%s\n' "$A_PROBE_STARTED_AT"
        printf 'probe_finished_at=%s\n' "$A_PROBE_FINISHED_AT"
        printf 'probe_server_name=%s\n' "$A_PROBE_SERVER_NAME"
        printf 'probe_server_version=%s\n' "$A_PROBE_SERVER_VERSION"
        printf 'probe_protocol_version=%s\n' "$A_PROBE_PROTOCOL_VERSION"
        printf 'probe_build_git_sha=%s\n' "$A_PROBE_BUILD_SHA"
        printf 'probe_toolset=%s\n' "$A_PROBE_TOOLSET"
        printf 'probe_tool_count=%s\n' "$A_PROBE_TOOL_COUNT"
        printf 'probe_capabilities_tool_present=%s\n' "$A_PROBE_CAPABILITIES_PRESENT"
        printf 'probe_method=%s\n' "$A_PROBE_METHOD"
        printf 'probe_copied_binary_sha256=%s\n' "$A_PROBE_COPY_SHA"
        printf 'probe_evidence_sha256=%s\n' "$A_PROBE_EVIDENCE_SHA"
        printf 'admission_binding_sha256=%s\n' "$A_BINDING_SHA"
    } > "$prepared"
    receipt_binding="$(domain_separated_meta_sha256 agent_bridge.publisher_fresh_mcp_admission_receipt.v1 "$prepared" 29)"
    printf 'receipt_binding_sha256=%s\n' "$receipt_binding" >> "$prepared"
    chmod 600 "$prepared"
    publish_exact_receipt "$prepared" "$A_RECEIPT_PATH"

    if [ "$source" = "$PENDING_ADMISSION" ]; then
        [ ! -e "$A_QUARANTINE_PATH" ] && [ ! -L "$A_QUARANTINE_PATH" ] ||
            die "fresh MCP admission quarantine target appeared during settlement"
        mv "$PENDING_ADMISSION" "$A_QUARANTINE_PATH" ||
            die "cannot atomically retire the admitted pending state"
    fi
    [ "$(sha256_file "$A_QUARANTINE_PATH")" = "$A_PENDING_SHA" ] ||
        die "retired pending admission content changed"
    FRESH_MCP_ADMISSION_SETTLED=1
}

retire_fresh_mcp_admission_intent() {
    local retired
    [ "$FRESH_MCP_ADMISSION_SETTLED" -eq 1 ] || die "fresh MCP admission intent is not settled"
    retired="$LEASE_QUARANTINE_DIR/$A_PENDING_LEASE_ID.$A_PENDING_CHALLENGE.fresh-mcp-admission-intent.settled.meta"
    if [ -e "$retired" ] || [ -L "$retired" ]; then
        [ ! -L "$retired" ] && [ -f "$retired" ] && [ "$(file_mode "$retired")" = 600 ] ||
            die "fresh MCP admission settled-intent target is not an exact physical mode-600 file"
        cmp -s "$FRESH_MCP_ADMISSION_INTENT" "$retired" ||
            die "fresh MCP admission settled-intent target conflicts with canonical intent"
        rm -f "$FRESH_MCP_ADMISSION_INTENT" ||
            die "cannot retire replayed fresh MCP admission intent"
        return 0
    fi
    mv "$FRESH_MCP_ADMISSION_INTENT" "$retired" ||
        die "cannot retire the settled fresh MCP admission intent"
}

run_fresh_mcp_probe() {
    local pending_sha="$1" probe_root probe_meta probe_stderr fixture probe_binary copy_sha
    local python_bin python_owner python_mode python_mode_value probe_timeout=45 probe_stdout_limit=1048576
    local probe_stderr_limit=262144
    probe_root="$(mktemp -d "$DEPLOY_TMPDIR/ab-publisher-fresh-mcp.XXXXXX")"
    chmod 700 "$probe_root" || die "cannot protect fresh MCP probe root"
    CLEANUP_FRESH_MCP_TMP="$probe_root"
    probe_meta="$probe_root/probe.meta"
    probe_stderr="$probe_root/probe.stderr"
    PENDING_PROBE_SHA="$pending_sha"

    if [ "$LEASE_TEST_MODE" = 1 ] && [ "$LEASE_TEST_LIVE_FRESH_MCP" != 1 ]; then
        [ -f "${AGENT_BRIDGE_DEPLOY_LEASE_TEST_FRESH_MCP_PROBE:-}" ] ||
            die "lease test fresh MCP probe fixture missing"
        fixture="$probe_root/legacy-probe-fixture.meta"
        /bin/cp "$AGENT_BRIDGE_DEPLOY_LEASE_TEST_FRESH_MCP_PROBE" "$fixture" ||
            die "cannot copy lease test fresh MCP probe fixture"
        read_legacy_fresh_mcp_probe_fixture "$fixture" ||
            die "lease test fresh MCP probe fixture is invalid"
        F_SCHEMA=agent_bridge.publisher_fresh_mcp_probe.v1
        F_NONCE="$(printf '%s\n' "$LEASE_CHALLENGE|$P_CHALLENGE|$RANDOM|fixture" | sha256_text)"
        F_STARTED_AT="$(utc_now)"
        F_FINISHED_AT="$F_STARTED_AT"
        F_METHOD=independent_stdio_private_exact_binary_copy
        F_COPY_SHA="$P_SHA"
        write_bound_fresh_mcp_probe "$probe_meta"
    else
        python_bin="$(/usr/bin/readlink -f -- /usr/bin/python3 2>/dev/null)" ||
            die "cannot resolve the trusted /usr/bin/python3 target for fresh MCP admission"
        case "$python_bin" in
            /usr/bin/python3|/usr/bin/python3.[0-9]|/usr/bin/python3.[0-9][0-9]) ;;
            *) die "trusted /usr/bin/python3 resolves outside the allowed system interpreter path" ;;
        esac
        [ -x "$python_bin" ] && [ -f "$python_bin" ] && [ ! -L "$python_bin" ] ||
            die "trusted /usr/bin/python3 target is not a physical executable"
        python_owner="$(file_owner_uid "$python_bin")"
        python_mode="$(file_mode "$python_bin")"
        case "$python_owner:$python_mode" in 0:[0-7][0-7][0-7]) ;; *) die "trusted python3 target ownership or mode is invalid" ;; esac
        python_mode_value=$((8#$python_mode))
        [ $((python_mode_value & 0022)) -eq 0 ] || die "trusted python3 target is group/world writable"

        if [ -n "${AGENT_BRIDGE_DEPLOY_LEASE_TEST_FRESH_MCP_TIMEOUT_SECONDS:-}" ]; then
            [ "$LEASE_TEST_MODE" = 1 ] || die "fresh MCP timeout override is test-only"
            probe_timeout="$AGENT_BRIDGE_DEPLOY_LEASE_TEST_FRESH_MCP_TIMEOUT_SECONDS"
            case "$probe_timeout" in ''|*[!0-9]*) die "invalid lease test fresh MCP timeout" ;; esac
            [ "$probe_timeout" -ge 1 ] && [ "$probe_timeout" -le 45 ] || die "lease test fresh MCP timeout must be within 1..45 seconds"
        fi
        if [ -n "${AGENT_BRIDGE_DEPLOY_LEASE_TEST_FRESH_MCP_STDOUT_LIMIT_BYTES:-}" ]; then
            [ "$LEASE_TEST_MODE" = 1 ] || die "fresh MCP stdout limit override is test-only"
            probe_stdout_limit="$AGENT_BRIDGE_DEPLOY_LEASE_TEST_FRESH_MCP_STDOUT_LIMIT_BYTES"
            case "$probe_stdout_limit" in ''|*[!0-9]*) die "invalid lease test fresh MCP stdout limit" ;; esac
            [ "$probe_stdout_limit" -ge 1024 ] && [ "$probe_stdout_limit" -le 1048576 ] ||
                die "lease test fresh MCP stdout limit must be within 1024..1048576 bytes"
        fi

        mkdir -p "$probe_root/home" "$probe_root/xdg/data" "$probe_root/xdg/config" \
            "$probe_root/xdg/cache" "$probe_root/xdg/state" "$probe_root/private-state" "$probe_root/tmp"
        chmod 700 "$probe_root/home" "$probe_root/xdg" "$probe_root/xdg/data" \
            "$probe_root/xdg/config" "$probe_root/xdg/cache" "$probe_root/xdg/state" \
            "$probe_root/private-state" "$probe_root/tmp" || die "cannot protect fresh MCP private environment"
        probe_binary="$probe_root/agent-bridge.probe"
        /bin/cp "$P_REAL_PATH" "$probe_binary" || die "cannot create fresh MCP private binary copy"
        chmod 700 "$probe_binary" || die "cannot protect fresh MCP private binary copy"
        copy_sha="$(sha256_file "$probe_binary")"
        [ "$copy_sha" = "$P_SHA" ] || die "fresh MCP private binary copy does not match pending installed SHA"

        if ! /usr/bin/env -i \
            HOME="$probe_root/home" \
            PATH=/usr/bin:/bin:/usr/sbin:/sbin \
            TMPDIR="$probe_root/tmp" \
            XDG_DATA_HOME="$probe_root/xdg/data" \
            XDG_CONFIG_HOME="$probe_root/xdg/config" \
            XDG_CACHE_HOME="$probe_root/xdg/cache" \
            XDG_STATE_HOME="$probe_root/xdg/state" \
            AGENT_BRIDGE_STATE_DIR="$probe_root/private-state" \
            AGENT_BRIDGE_TOOLSET=codex-essential \
            AGENT_BRIDGE_TERMINAL=pty \
            AGENT_BRIDGE_CLIENT=publisher-admission-probe \
            AGENT_BRIDGE_MCP_SOURCE=publisher-admission-probe \
            "$python_bin" -I - "$probe_binary" "$P_CANDIDATE" "$copy_sha" "$probe_root" \
                "$probe_timeout" "$probe_stdout_limit" "$probe_stderr_limit" \
                >"$probe_meta" 2>"$probe_stderr" <<'PY'
import hashlib
import json
import os
import re
import secrets
import selectors
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

binary, expected_commit, expected_binary_sha, probe_root, timeout_raw, stdout_limit_raw, stderr_limit_raw = sys.argv[1:]
if not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
    raise SystemExit("pending candidate is not an authoritative commit")
if not re.fullmatch(r"[0-9a-f]{64}", expected_binary_sha):
    raise SystemExit("pending binary SHA is invalid")
timeout_seconds = int(timeout_raw)
stdout_limit = int(stdout_limit_raw)
stderr_limit = int(stderr_limit_raw)

def digest_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()

if digest_file(binary) != expected_binary_sha:
    raise SystemExit("private probe binary changed before launch")

def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def reject_duplicate_object_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value

def strict_json_loads(raw):
    return json.loads(raw, object_pairs_hook=reject_duplicate_object_keys)

probe_started_at = now_utc()
nonce = secrets.token_hex(32)
initialize_id = "ab-init-" + nonce
tools_list_id = "ab-tools-" + nonce
capabilities_id = "ab-capabilities-" + nonce

env = {
    "HOME": os.path.join(probe_root, "home"),
    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
    "TMPDIR": os.path.join(probe_root, "tmp"),
    "XDG_DATA_HOME": os.path.join(probe_root, "xdg", "data"),
    "XDG_CONFIG_HOME": os.path.join(probe_root, "xdg", "config"),
    "XDG_CACHE_HOME": os.path.join(probe_root, "xdg", "cache"),
    "XDG_STATE_HOME": os.path.join(probe_root, "xdg", "state"),
    "AGENT_BRIDGE_STATE_DIR": os.path.join(probe_root, "private-state"),
    "AGENT_BRIDGE_TOOLSET": "codex-essential",
    "AGENT_BRIDGE_TERMINAL": "pty",
    "AGENT_BRIDGE_CLIENT": "publisher-admission-probe",
    "AGENT_BRIDGE_MCP_SOURCE": "publisher-admission-probe",
}

messages = [
    {
        "jsonrpc": "2.0",
        "id": initialize_id,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "publisher-admission-probe", "version": "0"},
        },
    },
    {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
    {"jsonrpc": "2.0", "id": tools_list_id, "method": "tools/list", "params": {}},
    {
        "jsonrpc": "2.0",
        "id": capabilities_id,
        "method": "tools/call",
        "params": {"name": "capabilities", "arguments": {"compact": True}},
    },
]
payload = "".join(json.dumps(item, separators=(",", ":")) + "\n" for item in messages).encode()
stdout_bytes = bytearray()
stderr_bytes = bytearray()
process = None
selector = None
group_cleanup_attempted = False
parent_returncode = None

def kill_probe_group():
    global group_cleanup_attempted
    if process is None or group_cleanup_attempted:
        return
    group_cleanup_attempted = True
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass

try:
    process = subprocess.Popen(
        [binary, "mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env, close_fds=True, start_new_session=True,
    )
    process.stdin.write(payload)
    process.stdin.close()
    os.set_blocking(process.stdout.fileno(), False)
    os.set_blocking(process.stderr.fileno(), False)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, ("stdout", stdout_bytes, stdout_limit))
    selector.register(process.stderr, selectors.EVENT_READ, ("stderr", stderr_bytes, stderr_limit))
    deadline = time.monotonic() + timeout_seconds
    while selector.get_map() or process.poll() is None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SystemExit("fresh MCP process timed out")
        for key, _ in selector.select(min(remaining, 0.1)):
            label, accumulator, limit = key.data
            read_size = min(65536, limit - len(accumulator) + 1)
            chunk = os.read(key.fileobj.fileno(), read_size)
            if chunk:
                accumulator.extend(chunk)
                if len(accumulator) > limit:
                    raise SystemExit(f"fresh MCP {label} exceeded its admission limit")
            else:
                selector.unregister(key.fileobj)
                key.fileobj.close()
        if process.poll() is not None:
            parent_returncode = process.returncode
            # A conforming stdio MCP has no reason to retain descendants once
            # its parent exits. Kill the private process group immediately so
            # a descendant cannot hold pipes/state beyond this admission.
            kill_probe_group()
    parent_returncode = process.wait(timeout=2)
finally:
    if selector is not None:
        selector.close()
    kill_probe_group()
    if process is not None:
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            group_cleanup_attempted = False
            kill_probe_group()
            process.wait(timeout=2)

if parent_returncode != 0:
    raise SystemExit("fresh MCP process failed")
if digest_file(binary) != expected_binary_sha:
    raise SystemExit("private probe binary changed during execution")
stdout_text = bytes(stdout_bytes).decode("utf-8", errors="strict")

responses = {}
expected_ids = {initialize_id, tools_list_id, capabilities_id}
for line in stdout_text.splitlines():
    if not line:
        raise SystemExit("fresh MCP emitted an empty response line")
    value = strict_json_loads(line)
    if type(value) is not dict or value.get("jsonrpc") != "2.0":
        raise SystemExit("fresh MCP returned a non-JSON-RPC-2.0 response")
    response_id = value.get("id")
    if type(response_id) is not str or response_id not in expected_ids:
        raise SystemExit("fresh MCP returned an unknown or mistyped response id")
    if response_id in responses:
        raise SystemExit("fresh MCP returned a duplicate response id")
    if set(value) not in ({"jsonrpc", "id", "result"}, {"jsonrpc", "id", "error"}):
        raise SystemExit("fresh MCP response envelope is not strict")
    responses[response_id] = value
if set(responses) != expected_ids:
    raise SystemExit("fresh MCP response set is incomplete")
if any("error" in responses[idx] for idx in expected_ids):
    raise SystemExit("fresh MCP returned a protocol error")

init = responses[initialize_id]["result"]
if type(init) is not dict or type(init.get("serverInfo")) is not dict:
    raise SystemExit("fresh MCP initialize result is malformed")
server = init["serverInfo"]
if type(server.get("name")) is not str or type(server.get("version")) is not str:
    raise SystemExit("fresh MCP server identity types are malformed")
if server["name"] != "agent-bridge" or init.get("protocolVersion") != "2024-11-05":
    raise SystemExit("fresh MCP identity mismatch")

tools_result = responses[tools_list_id]["result"]
if type(tools_result) is not dict or set(tools_result) != {"tools"}:
    raise SystemExit("fresh MCP tools/list pagination or shape is unsupported")
tools = tools_result["tools"]
if type(tools) is not list or any(type(tool) is not dict or type(tool.get("name")) is not str for tool in tools):
    raise SystemExit("fresh MCP tool manifest is malformed")
tool_names = [tool["name"] for tool in tools]
if tool_names.count("capabilities") != 1:
    raise SystemExit("capabilities tool is not exposed exactly once")

result = responses[capabilities_id]["result"]
if type(result) is not dict or type(result.get("content")) is not list:
    raise SystemExit("capabilities result is malformed")
if "isError" in result and type(result["isError"]) is not bool:
    raise SystemExit("capabilities isError type is malformed")
if result.get("isError", False) is not False:
    raise SystemExit("capabilities tool reported an application error")
content = result["content"]
if len(content) != 1 or type(content[0]) is not dict or set(content[0]) != {"type", "text"}:
    raise SystemExit("capabilities result is not a single structured text block")
if content[0]["type"] != "text" or type(content[0]["text"]) is not str:
    raise SystemExit("capabilities result text block is malformed")
capabilities = strict_json_loads(content[0]["text"])
if type(capabilities) is not dict or type(capabilities.get("build")) is not dict or type(capabilities.get("mcp")) is not dict:
    raise SystemExit("capabilities payload is malformed")
build_sha = capabilities["build"]["git_sha"]
toolset = capabilities["mcp"]["toolset"]
exposed_count = capabilities["mcp"]["exposed_tool_count"]
if type(build_sha) is not str or type(toolset) is not str or type(exposed_count) is not int:
    raise SystemExit("capabilities payload types are malformed")
if build_sha != expected_commit[:12]:
    raise SystemExit("fresh MCP build does not match pending candidate")
if toolset != "codex-essential" or exposed_count != len(tools):
    raise SystemExit("fresh MCP tool manifest mismatch")

probe_finished_at = now_utc()
observation = {
    "schema": "agent_bridge.publisher_fresh_mcp_probe.v1",
    "probe_nonce": nonce,
    "probe_started_at": probe_started_at,
    "probe_finished_at": probe_finished_at,
    "server_name": server["name"],
    "server_version": server["version"],
    "protocol_version": init["protocolVersion"],
    "build_git_sha": build_sha,
    "toolset": toolset,
    "tool_count": len(tools),
    "capabilities_tool_present": True,
    "probe_method": "independent_stdio_private_exact_binary_copy",
    "copied_binary_sha256": expected_binary_sha,
}
ordered_keys = (
    "schema", "probe_nonce", "probe_started_at", "probe_finished_at", "server_name",
    "server_version", "protocol_version", "build_git_sha", "toolset", "tool_count",
    "capabilities_tool_present", "probe_method", "copied_binary_sha256",
)
for key in ordered_keys:
    value = observation[key]
    if isinstance(value, bool):
        value = str(value).lower()
    print(f"{key}={value}")
PY
        then
            die "fresh MCP admission probe failed; diagnostic details intentionally suppressed"
        fi
        read_fresh_mcp_probe_observation "$probe_meta" ||
            die "fresh MCP admission probe observation is invalid"
        [ "$F_COPY_SHA" = "$copy_sha" ] || die "fresh MCP probe reported a different private binary SHA"
        write_bound_fresh_mcp_probe "$probe_meta"
    fi

    chmod 600 "$probe_meta" || die "cannot protect fresh MCP admission probe receipt"
    read_fresh_mcp_probe "$probe_meta" || die "fresh MCP admission probe receipt is invalid"
    [ "$F_BUILD_SHA" = "${P_CANDIDATE:0:12}" ] ||
        die "fresh MCP admission probe build does not match pending candidate"
    [ "$F_PENDING_SHA" = "$pending_sha" ] && [ "$F_PENDING_LEASE_ID" = "$P_LEASE_ID" ] &&
        [ "$F_PENDING_CHALLENGE" = "$P_CHALLENGE" ] && [ "$F_CANDIDATE" = "$P_CANDIDATE" ] &&
        [ "$F_REAL_PATH" = "$P_REAL_PATH" ] && [ "$F_SHARED_TARGETS" = "$P_SHARED_TARGETS" ] &&
        [ "$F_INSTALLED_SHA" = "$P_SHA" ] && [ "$F_INSTALLED_INODE" = "$P_INODE" ] &&
        [ "$F_INSTALLED_MODE" = "$P_MODE" ] && [ "$F_INSTALLED_ASSETS_SHA" = "$P_ASSETS_SHA" ] &&
        [ "$F_PENDING_INSTALLED_AT" = "$P_INSTALLED_AT" ] &&
        [ "$F_ADMISSION_LEASE_ID" = "$LEASE_ID" ] && [ "$F_ADMISSION_CHALLENGE" = "$LEASE_CHALLENGE" ] ||
        die "fresh MCP admission probe evidence is not bound to the exact pending/admission context"
}

admit_pending_fresh_mcp() {
    local pending_sha receipt quarantine
    [ -e "$PENDING_ADMISSION" ] || die "no publisher pending admission exists"
    read_pending_admission "$PENDING_ADMISSION" ||
        die "pending-admission metadata is missing, unknown, or corrupt; fail closed"
    [ "$P_REAL_PATH" = "$REAL_PATH" ] && [ "$P_SHARED_TARGETS" = "$SHARED_TARGETS" ] ||
        die "pending admission targets do not match this publisher"
    printf '%s\n' "$P_CANDIDATE" | grep -Eq '^[0-9a-f]{40}$' ||
        die "fresh MCP admission requires an authoritative commit candidate"
    pending_fingerprint_matches ||
        die "pending-admission fingerprint no longer matches the installed binary/assets"
    pending_sha="$(sha256_file "$PENDING_ADMISSION")"

    LEASE_CANDIDATE="$P_CANDIDATE"
    lease_phase_update prepared
    run_fresh_mcp_probe "$pending_sha"

    [ "$(sha256_file "$PENDING_ADMISSION")" = "$pending_sha" ] ||
        die "pending admission changed during the fresh MCP probe"
    read_pending_admission "$PENDING_ADMISSION" && pending_fingerprint_matches ||
        die "pending admission fingerprint changed during the fresh MCP probe"

    receipt="$LEASE_RECEIPT_DIR/$P_LEASE_ID.$P_CHALLENGE.fresh-mcp-admitted.meta"
    quarantine="$LEASE_QUARANTINE_DIR/$P_LEASE_ID.$P_CHALLENGE.fresh-mcp-admitted.pending.meta"
    write_fresh_mcp_admission_intent "$pending_sha" "$receipt" "$quarantine"
    settle_fresh_mcp_admission_intent

    if [ "$LEASE_TEST_MODE" = 1 ] && [ "$LEASE_TEST_HOLD_AFTER_FRESH_MCP" = 1 ]; then
        [ -z "${AGENT_BRIDGE_DEPLOY_LEASE_TEST_READY_FILE:-}" ] ||
            printf '%s\n' "$$" > "$AGENT_BRIDGE_DEPLOY_LEASE_TEST_READY_FILE"
        while :; do sleep 1; done
    fi

    say "publisher fresh MCP admission: verified ($P_CANDIDATE, toolset=$F_TOOLSET, tools=$F_TOOL_COUNT)"
    release_active_lease fresh_mcp_admitted exact_independent_stdio_probe
    retire_fresh_mcp_admission_intent
}

lease_test_advance() {
    case "$1" in
        acquired) ;;
        building) lease_phase_update building ;;
        prepared) lease_phase_update building; lease_phase_update prepared ;;
        committing) lease_phase_update building; lease_phase_update prepared; lease_phase_update committing ;;
        *) die "unsupported lease test phase: $1" ;;
    esac
}

FRESH_MCP_ADMISSION_SETTLED=0
if [ -e "$FRESH_MCP_ADMISSION_INTENT" ] || [ -L "$FRESH_MCP_ADMISSION_INTENT" ]; then
    settle_fresh_mcp_admission_intent
    if [ "$ADMIT_FRESH_MCP" -eq 1 ] ||
            [ "${AGENT_BRIDGE_DEPLOY_LEASE_TEST_ACTION:-}" = admit-fresh-mcp ]; then
        say "publisher fresh MCP admission: recovered exact settled intent ($A_CANDIDATE)"
        release_active_lease fresh_mcp_admission_recovered exact_completion_intent_replay
        retire_fresh_mcp_admission_intent
        exit 0
    fi
    retire_fresh_mcp_admission_intent
fi

if [ -n "${AGENT_BRIDGE_DEPLOY_LEASE_TEST_ACTION:-}" ]; then
    test_root="$TEST_PHYSICAL_ROOT"
    if [ "$AGENT_BRIDGE_DEPLOY_LEASE_TEST_ACTION" = admit-fresh-mcp ]; then
        admit_pending_fresh_mcp
        exit 0
    fi
    LEASE_CANDIDATE="${AGENT_BRIDGE_DEPLOY_LEASE_TEST_CANDIDATE:-test-candidate}"
    is_safe_candidate "$LEASE_CANDIDATE" || die "publisher lease test candidate is invalid"
    lease_phase_update acquired
    inspect_pending_for_candidate "$LEASE_CANDIDATE"
    case "$AGENT_BRIDGE_DEPLOY_LEASE_TEST_ACTION" in
        hold)
            lease_test_advance "${AGENT_BRIDGE_DEPLOY_LEASE_TEST_PHASE:-building}"
            [ -z "${AGENT_BRIDGE_DEPLOY_LEASE_TEST_READY_FILE:-}" ] || printf '%s\n' "$$" > "$AGENT_BRIDGE_DEPLOY_LEASE_TEST_READY_FILE"
            while :; do sleep 1; done
            ;;
        probe)
            release_active_lease test_probe no_mutation_probe
            exit 0
            ;;
        install)
            [ -f "${AGENT_BRIDGE_DEPLOY_LEASE_TEST_PAYLOAD:-}" ] || die "lease test install payload missing"
            lease_phase_update building
            lease_phase_update prepared
            lease_phase_update committing
            consume_pending_before_mutation "$LEASE_CANDIDATE"
            cp "$AGENT_BRIDGE_DEPLOY_LEASE_TEST_PAYLOAD" "$REAL_PATH"
            [ -z "${AGENT_BRIDGE_DEPLOY_LEASE_TEST_MUTATION_LOG:-}" ] || printf '%s\n' "$LEASE_CANDIDATE" >> "$AGENT_BRIDGE_DEPLOY_LEASE_TEST_MUTATION_LOG"
            lease_phase_update services_verifying
            lease_phase_update awaiting_fresh_mcp
            write_pending_admission "$LEASE_CANDIDATE"
            archive_pending_completion
            complete_recovery_handoff_intent
            release_active_lease pending_admission fresh_mcp_unverified
            exit 0
            ;;
        *) die "unknown publisher lease test action: $AGENT_BRIDGE_DEPLOY_LEASE_TEST_ACTION" ;;
    esac
fi

if [ "$ADMIT_FRESH_MCP" -eq 1 ]; then
    admit_pending_fresh_mcp
    exit 0
fi

# ---- 1. obtain the NEW binary (build from latest master, or --use-binary) ----
NEW_BIN=""
PROVENANCE=""
if [ -n "$USE_BINARY" ]; then
    [ -f "$USE_BINARY" ] || die "--use-binary path not found: $USE_BINARY"
    is_native_exe "$USE_BINARY" || die "--use-binary is not a native executable (ELF/Mach-O): $USE_BINARY"
    LEASE_CANDIDATE="use-binary-sha256:$(sha256_file "$USE_BINARY")"
    lease_phase_update acquired
    inspect_pending_for_candidate "$LEASE_CANDIDATE"
    lease_phase_update building
    NEW_BIN="$USE_BINARY"
    PROVENANCE="--use-binary $USE_BINARY (provenance NOT verified)"
    say "WARNING: --use-binary skips the build-from-master guarantee."
    say "         Only the regression gate + backup protect this deploy."
else
    [ "$LEASE_TEST_MODE" = 1 ] || validate_trusted_git_configuration
    deploy_git -C "$REPO" remote get-url "$DEPLOY_REMOTE" >/dev/null 2>&1 ||
        die "configured deploy remote does not exist: $DEPLOY_REMOTE"
    say ">> fetching $DEPLOY_REMOTE/master ..."
    if [ "$LEASE_TEST_MODE" = 1 ]; then
        deploy_git -C "$REPO" fetch --no-auto-maintenance \
            "$DEPLOY_REMOTE" "+refs/heads/master:$MASTER_REF" --quiet
    else
        deploy_git -C "$REPO" fetch --no-auto-maintenance "$AUTHORITATIVE_REMOTE_URL" \
            "+refs/heads/master:$MASTER_REF" --quiet
    fi
    MASTER_SHA="$(deploy_git -C "$REPO" rev-parse --verify "$MASTER_REF")"
    if [ "$LEASE_TEST_MODE" = 0 ]; then
        [ "$MASTER_SHA" = "$PROVISIONED_SOURCE_CANDIDATE" ] ||
            die "$DEPLOY_REMOTE/master differs from the verified trusted source candidate; advance the private source HEAD and gitlab/master together, then rerun provisioning verification"
        PUBLISHED_ORCHESTRATOR_SHA="$(deploy_git -C "$REPO" show \
            "$MASTER_SHA:scripts/deploy_from_master.sh" | sha256_text)" ||
            die "cannot read the deploy orchestrator from authoritative master"
        [ "$PUBLISHED_ORCHESTRATOR_SHA" = "$(sha256_file "$SCRIPT_PATH")" ] ||
            die "running deploy orchestrator does not exactly match authoritative master"
    fi
    LEASE_CANDIDATE="$MASTER_SHA"
    lease_phase_update acquired
    inspect_pending_for_candidate "$LEASE_CANDIDATE"
    lease_phase_update building
    PROVENANCE="$DEPLOY_REMOTE/master @ ${MASTER_SHA:0:7}"
    # Production materializes the exact tree through `git archive`, which does
    # not run checkout hooks or smudge filters from local Git configuration.
    # Build identity is injected explicitly below, so the snapshot needs no
    # mutable .git link. Synthetic regression fixtures retain worktree behavior
    # to exercise their fake Git/Cargo lanes.
    if [ "$LEASE_TEST_MODE" = 1 ]; then
        BUILD_DIR="$(dirname "$REPO")/.ab-deploy-build.$$"
        deploy_git -C "$REPO" worktree remove --force "$BUILD_DIR" >/dev/null 2>&1 || true
        rm -rf "$BUILD_DIR" 2>/dev/null || true
        say ">> creating build worktree at $BUILD_DIR (detached @ ${MASTER_SHA:0:7})"
        deploy_git -C "$REPO" worktree add --detach "$BUILD_DIR" "$MASTER_SHA" >/dev/null
        CLEANUP_WT="$BUILD_DIR"
    else
        TRUSTED_WORKTREE_ROOT="$DEPLOY_ROOT/build/worktrees"
        ensure_trusted_subdirectory_path \
            "$DEPLOY_ROOT" "$TRUSTED_WORKTREE_ROOT" "trusted release worktree root"
        BUILD_DIR="$TRUSTED_WORKTREE_ROOT/master-$MASTER_SHA-$$"
        [ ! -e "$BUILD_DIR" ] && [ ! -L "$BUILD_DIR" ] ||
            die "trusted release worktree path already exists: $BUILD_DIR"
        mkdir -m 700 "$BUILD_DIR" || die "cannot create trusted release source snapshot"
        CLEANUP_WT="$BUILD_DIR"
        [ -x /usr/bin/tar ] || die "trusted release source snapshot requires /usr/bin/tar"
        deploy_git -C "$REPO" archive --format=tar "$MASTER_SHA" |
            /usr/bin/tar --extract --directory "$BUILD_DIR" \
                --no-same-owner --no-same-permissions ||
            die "cannot materialize authoritative release source snapshot"
        [ -z "$(find "$BUILD_DIR" -type l -print -quit)" ] ||
            die "authoritative release source snapshot contains a symlink"
    fi
    say ">> materialized authoritative release source at $BUILD_DIR (${MASTER_SHA:0:7})"
    # A production target is scoped first by canonical deployment-root identity
    # and then by authoritative master SHA. This keeps candidate executables
    # disjoint across trust domains while retaining Cargo reuse for repeated
    # attempts of the exact release. Synthetic contained tests keep their
    # caller-provided target root.
    if [ "$LEASE_TEST_MODE" = 1 ]; then
        DEPLOY_TARGET_ROOT="${CARGO_TARGET_DIR:-$HOME/.cache/agent-bridge-deploy-target}"
        ensure_physical_directory_path "$DEPLOY_TARGET_ROOT"
        protect_owned_directory "$DEPLOY_TARGET_ROOT" "publisher lease test Cargo target root"
    else
        [ -n "$DEPLOY_TARGET_ROOT" ] || die "production Cargo target root was not initialized"
    fi
    DEPLOY_TARGET_DIR="$DEPLOY_TARGET_ROOT/$MASTER_SHA"
    if [ "$LEASE_TEST_MODE" = 1 ]; then
        ensure_physical_directory_path "$DEPLOY_TARGET_DIR"
        protect_owned_directory "$DEPLOY_TARGET_DIR" "publisher lease test SHA Cargo target"
    else
        ensure_trusted_subdirectory_path \
            "$DEPLOY_TARGET_BASE" "$DEPLOY_TARGET_DIR" "authoritative SHA Cargo target"
    fi
    CARGO_FEATURE_ARGS=()
    if [ "$(uname -s)" = "Linux" ]; then
        CARGO_FEATURE_ARGS+=(--features linux-native-avatar)
        say ">> enabling linux-native-avatar for the production Linux binary"
    fi
    if [ "$LEASE_TEST_MODE" = 1 ]; then
        BUILD_PKG_CONFIG_PATH="${PKG_CONFIG_PATH:-}"
    else
        # Do not admit caller-controlled .pc search roots into an authoritative
        # production build. System defaults and the bounded shim below suffice.
        BUILD_PKG_CONFIG_PATH=""
    fi
    if [ "$(uname -s)" = "Linux" ] && ! pkg-config --exists xkbcommon >/dev/null 2>&1; then
        XKB_LIB="$(ldconfig -p 2>/dev/null | awk '/libxkbcommon\.so\.0 \(/ {print $NF; exit}')"
        [ -n "$XKB_LIB" ] || XKB_LIB="/usr/lib/x86_64-linux-gnu/libxkbcommon.so.0"
        [ -e "$XKB_LIB" ] || die "linux-native-avatar build requires libxkbcommon.so.0 (install runtime xkbcommon or provide PKG_CONFIG_PATH)"
        CLEANUP_PKG_CONFIG="$(mktemp -d "$DEPLOY_TMPDIR/agent-bridge-pkgconfig.XXXXXX")"
        ln -s "$XKB_LIB" "$CLEANUP_PKG_CONFIG/libxkbcommon.so"
        cat > "$CLEANUP_PKG_CONFIG/xkbcommon.pc" <<EOF
prefix=/usr
exec_prefix=\${prefix}
libdir=$CLEANUP_PKG_CONFIG
includedir=/usr/include

Name: xkbcommon
Description: XKB common library (runtime-only build shim)
Version: 0.0
Libs: -L\${libdir} -lxkbcommon
Cflags: -I\${includedir}
EOF
        BUILD_PKG_CONFIG_PATH="$CLEANUP_PKG_CONFIG${BUILD_PKG_CONFIG_PATH:+:$BUILD_PKG_CONFIG_PATH}"
        say ">> using runtime libxkbcommon pkg-config shim for linux-native-avatar"
    fi
    say ">> cargo build --release --bin agent-bridge ${CARGO_FEATURE_ARGS[*]-}"
    say "   (private deployment-scoped target dir: $DEPLOY_TARGET_DIR; takes several minutes) ..."
    if [ "$LEASE_TEST_MODE" = 0 ]; then
        if [ "${#CARGO_FEATURE_ARGS[@]}" -gt 0 ]; then
            ( cd "$BUILD_DIR" && /usr/bin/env -i \
                PATH=/usr/sbin:/usr/bin:/sbin:/bin \
                HOME="$DEPLOY_ROOT" \
                CARGO_HOME="$TRUSTED_CARGO_HOME" \
                CARGO_TARGET_DIR="$DEPLOY_TARGET_DIR" \
                CARGO_TERM_COLOR=never \
                PKG_CONFIG_PATH="$BUILD_PKG_CONFIG_PATH" \
                RUSTC="$TRUSTED_RUSTC" \
                TMPDIR="$TRUSTED_BUILD_TMP" \
                AGENT_BRIDGE_BUILD_SHA="${MASTER_SHA:0:12}" \
                AGENT_BRIDGE_BUILD_DESCRIBE="${MASTER_SHA:0:12}" \
                "$TRUSTED_CARGO" build --locked --release --bin agent-bridge \
                "${CARGO_FEATURE_ARGS[@]}" )
        else
            ( cd "$BUILD_DIR" && /usr/bin/env -i \
                PATH=/usr/sbin:/usr/bin:/sbin:/bin \
                HOME="$DEPLOY_ROOT" \
                CARGO_HOME="$TRUSTED_CARGO_HOME" \
                CARGO_TARGET_DIR="$DEPLOY_TARGET_DIR" \
                CARGO_TERM_COLOR=never \
                PKG_CONFIG_PATH="$BUILD_PKG_CONFIG_PATH" \
                RUSTC="$TRUSTED_RUSTC" \
                TMPDIR="$TRUSTED_BUILD_TMP" \
                AGENT_BRIDGE_BUILD_SHA="${MASTER_SHA:0:12}" \
                AGENT_BRIDGE_BUILD_DESCRIBE="${MASTER_SHA:0:12}" \
                "$TRUSTED_CARGO" build --locked --release --bin agent-bridge )
        fi
    elif [ "${#CARGO_FEATURE_ARGS[@]}" -gt 0 ]; then
        ( cd "$BUILD_DIR" && CARGO_TARGET_DIR="$DEPLOY_TARGET_DIR" PKG_CONFIG_PATH="$BUILD_PKG_CONFIG_PATH" CARGO_TERM_COLOR=never cargo build --locked --release --bin agent-bridge "${CARGO_FEATURE_ARGS[@]}" )
    else
        # macOS ships Bash 3.2, where expanding an empty array under `set -u`
        # raises "unbound variable" instead of yielding zero arguments.
        ( cd "$BUILD_DIR" && CARGO_TARGET_DIR="$DEPLOY_TARGET_DIR" PKG_CONFIG_PATH="$BUILD_PKG_CONFIG_PATH" CARGO_TERM_COLOR=never cargo build --locked --release --bin agent-bridge )
    fi
    NEW_BIN="$DEPLOY_TARGET_DIR/release/agent-bridge"
    [ -x "$NEW_BIN" ] || die "build produced no binary at $NEW_BIN"
    [ -f "$NEW_BIN" ] && [ ! -L "$NEW_BIN" ] ||
        die "build candidate is not a physical regular file: $NEW_BIN"
    [ "$(file_owner_uid "$NEW_BIN")" = "$(id -u)" ] ||
        die "build candidate is not owned by the effective publisher: $NEW_BIN"
    BUILT_VERSION="$("$NEW_BIN" --version 2>&1)" ||
        die "built binary does not execute for provenance verification"
    case "$BUILT_VERSION" in
        *"${MASTER_SHA:0:12}"*) ;;
        *) die "built binary provenance mismatch: expected ${MASTER_SHA:0:12}, got: $BUILT_VERSION" ;;
    esac
    say "OK: built binary reports master ${MASTER_SHA:0:12}."
fi

# Freeze one exact candidate inode before feature gates, operator confirmation,
# or any live-file mutation. The source is hashed on both sides of the copy so
# even the contained --use-binary regression lane cannot swap an equal-sized
# payload between candidate selection and custody.
CANDIDATE_SOURCE="$NEW_BIN"
CANDIDATE_SOURCE_SHA_BEFORE="$(sha256_file "$CANDIDATE_SOURCE")"
case "$LEASE_CANDIDATE" in
    use-binary-sha256:*)
        [ "${LEASE_CANDIDATE#use-binary-sha256:}" = "$CANDIDATE_SOURCE_SHA_BEFORE" ] ||
            die "caller binary changed after lease candidate selection"
        ;;
esac
CANDIDATE_SNAPSHOT="$LEASE_STATE_ROOT/.candidate.$LEASE_ID"
[ ! -e "$CANDIDATE_SNAPSHOT" ] && [ ! -L "$CANDIDATE_SNAPSHOT" ] ||
    die "private candidate snapshot path already exists"
cp "$CANDIDATE_SOURCE" "$CANDIDATE_SNAPSHOT" || die "cannot freeze the deployment candidate"
chmod 700 "$CANDIDATE_SNAPSHOT" || die "cannot protect the frozen deployment candidate"
CLEANUP_CANDIDATE_SNAPSHOT="$CANDIDATE_SNAPSHOT"
verify_owned_regular_mode "$CANDIDATE_SNAPSHOT" 700 "frozen deployment candidate"
CANDIDATE_SOURCE_SHA_AFTER="$(sha256_file "$CANDIDATE_SOURCE")"
FROZEN_CANDIDATE_SHA="$(sha256_file "$CANDIDATE_SNAPSHOT")"
[ "$CANDIDATE_SOURCE_SHA_BEFORE" = "$CANDIDATE_SOURCE_SHA_AFTER" ] &&
    [ "$CANDIDATE_SOURCE_SHA_BEFORE" = "$FROZEN_CANDIDATE_SHA" ] ||
    die "deployment candidate changed while entering private custody"
is_native_exe "$CANDIDATE_SNAPSHOT" || die "frozen deployment candidate is not native"
FROZEN_VERSION="$("$CANDIDATE_SNAPSHOT" --version 2>&1)" ||
    die "frozen deployment candidate does not execute"
if [ -z "$USE_BINARY" ]; then
    case "$FROZEN_VERSION" in
        *"${MASTER_SHA:0:12}"*) ;;
        *) die "frozen candidate provenance no longer matches authoritative master" ;;
    esac
fi
NEW_BIN="$CANDIDATE_SNAPSHOT"

# A normal deploy must install scripts from the exact archived master snapshot
# that produced NEW_BIN, never from the caller's possibly stale/dirty worktree.
# Otherwise two same-SHA deploys launched from different worktrees can end with
# the correct binary but whichever caller's runtime assets happened to run last.
# The contained --use-binary regression lane has no verified source snapshot,
# so it retains repository-matched fixture behavior and uses its invoking tree.
if [ -z "$USE_BINARY" ]; then
    ASSET_SOURCE_ROOT="$BUILD_DIR"
fi
ADAPTER_SOURCE="$ASSET_SOURCE_ROOT/scripts/audio_embody.py"
[ -f "$ADAPTER_SOURCE" ] || die "deploy-source audio adapter missing: $ADAPTER_SOURCE"
for asset in "${AUDIO_ADAPTER_COMPANIONS[@]}"; do
    [ -f "$ASSET_SOURCE_ROOT/scripts/$asset" ] ||
        die "deploy-source audio companion missing: $ASSET_SOURCE_ROOT/scripts/$asset"
done
for asset in "${AUDIO_POLICY_ASSETS[@]}"; do
    [ -f "$ASSET_SOURCE_ROOT/$asset" ] ||
        die "deploy-source audio policy asset missing: $ASSET_SOURCE_ROOT/$asset"
done
for asset in "${RUNTIME_ASSETS[@]}"; do
    [ -f "$ASSET_SOURCE_ROOT/scripts/$asset" ] ||
        die "deploy-source runtime asset missing: $ASSET_SOURCE_ROOT/scripts/$asset"
done
if [ "$LEASE_TEST_MODE" = 0 ]; then
    verify_owned_regular_mode "$WRAPPER_PATH" 755 "installed trusted wrapper"
    cmp -s "$ASSET_SOURCE_ROOT/scripts/wrapper/agent-bridge-wrapper.sh" "$WRAPPER_PATH" ||
        die "installed wrapper does not exactly match authoritative master; run the trusted wrapper installer before binary deployment"
fi
grep -q 'agent_bridge.app_control.operation_preflight.v0' \
    "$ASSET_SOURCE_ROOT/scripts/app_control.py" ||
    die "deploy-source app_control missing durable operation preflight before live-state mutation: $ASSET_SOURCE_ROOT/scripts/app_control.py"
grep -q 'agent_bridge.app_control.track_settlement.v0' \
    "$ASSET_SOURCE_ROOT/scripts/app_control.py" ||
    die "deploy-source app_control missing bounded durable track settlement: $ASSET_SOURCE_ROOT/scripts/app_control.py"
grep -q 'agent_bridge.app_control.wrapper_contract.v1' \
    "$ASSET_SOURCE_ROOT/scripts/app_control.py" ||
    die "deploy-source app_control missing action-before-version handshake: $ASSET_SOURCE_ROOT/scripts/app_control.py"

is_native_exe "$NEW_BIN" || die "new binary is not a native executable (ELF/Mach-O): $NEW_BIN"

# ---- 2. post-build master recheck ----
# A release build can take tens of minutes. Another lane may merge during that
# window, making this artifact stale even though it came from remote/master at
# build start. Re-check before the first live-state mutation (backup/copy).
if [ -z "$USE_BINARY" ]; then
    say ">> rechecking $DEPLOY_REMOTE/master after build ..."
    [ "$LEASE_TEST_MODE" = 1 ] || validate_trusted_git_configuration
    if [ "$LEASE_TEST_MODE" = 1 ]; then
        deploy_git -C "$REPO" fetch --no-auto-maintenance \
            "$DEPLOY_REMOTE" "+refs/heads/master:$MASTER_REF" --quiet
    else
        deploy_git -C "$REPO" fetch --no-auto-maintenance "$AUTHORITATIVE_REMOTE_URL" \
            "+refs/heads/master:$MASTER_REF" --quiet
    fi
    CURRENT_MASTER_SHA="$(deploy_git -C "$REPO" rev-parse --verify "$MASTER_REF")"
    if [ "$CURRENT_MASTER_SHA" != "$MASTER_SHA" ]; then
        die "$DEPLOY_REMOTE/master advanced during the release build (${MASTER_SHA:0:7} -> ${CURRENT_MASTER_SHA:0:7}); refusing to deploy a stale artifact before backup/copy. Re-run the deploy from the new master."
    fi
    say "OK: $DEPLOY_REMOTE/master is still ${MASTER_SHA:0:7}."
fi

# ---- 3. anti-regression gate vs the currently-deployed binary ----
say
say "=== feature gate (new binary must not drop any current capability) ==="
new_markers="$(markers_in "$NEW_BIN")"
for required_marker in "${REQUIRED_NEW_BINARY_MARKERS[@]}"; do
    grep -qxF -- "$required_marker" <<< "$new_markers" ||
        die "new binary missing required runtime-contract marker: $required_marker"
done
if [ -f "$REAL_PATH" ]; then
    cur_markers="$(markers_in "$REAL_PATH")"
    # markers present in current but missing in new = regression
    missing="$(comm -23 <(printf '%s\n' "$cur_markers" | sort -u) <(printf '%s\n' "$new_markers" | sort -u))"
    if [ -n "$missing" ]; then
        say "current deployed binary has these markers the NEW binary LACKS:"
        printf '  - %s\n' $missing
        die "regression detected — new binary drops a capability the live one has.
       This usually means it was built from a STALE branch, not latest master.
       Refusing to clobber. Rebuild from the authoritative remote/master."
    fi
    say "OK: new binary is a superset of the current deployed binary's markers."
else
    say "(no current $REAL_PATH — first install, nothing to regress against)"
fi
say "new binary markers present:"; printf '  + %s\n' $new_markers
lease_phase_update prepared

# ---- 4. plan summary ----
new_size="$(file_size "$NEW_BIN")"
cur_size="$( [ -f "$REAL_PATH" ] && file_size "$REAL_PATH" || echo 0 )"
say
say "=== deploy plan ==="
say "  source     : $PROVENANCE"
say "  new binary : $NEW_BIN ($new_size bytes)"
say "  target     : $REAL_PATH (current $cur_size bytes)"
say "  wrapper    : $WRAPPER_PATH (left untouched)"
say "  adapter    : $ADAPTER_SOURCE -> $ADAPTER_PATH"
say "  companions : ${#AUDIO_ADAPTER_COMPANIONS[@]} audio scripts -> $(dirname "$ADAPTER_PATH")"
say "  policy      : ${#AUDIO_POLICY_ASSETS[@]} review-bound assets -> $(dirname "$(dirname "$ADAPTER_PATH")")"
say "  runtime    : ${#RUNTIME_ASSETS[@]} scripts from $ASSET_SOURCE_ROOT -> $RUNTIME_ASSET_DIR"

if [ "$DRY_RUN" -eq 1 ]; then
    say
    say "[dry-run] gate passed; no backup/cp performed. Re-run without --dry-run to deploy."
    release_active_lease dry_run prepared_without_mutation
    exit 0
fi

# ---- 5. confirm ----
if [ "$ASSUME_YES" -ne 1 ]; then
    if [ ! -t 0 ]; then
        die "non-interactive stdin and no --yes given: re-run with --yes to deploy"
    fi
    printf 'Proceed with deploy? [y/N] '
    read -r ans || ans=""
    case "$ans" in
        y|Y|yes|YES) ;;
        *) say "aborted."; release_active_lease cancelled operator_declined_before_mutation; exit 0 ;;
    esac
fi

# ---- 6. backup current, then deploy ----
lease_phase_update committing
consume_pending_before_mutation "$LEASE_CANDIDATE"
if [ -f "$REAL_PATH" ]; then
    ts="$(date +%Y%m%dT%H%M%S)"
    # NB: ${MASTER_SHA:0:7} must not be expanded on the --use-binary path, where
    # MASTER_SHA is unset and `set -u` would abort here (before the backup+deploy).
    if [ -n "$USE_BINARY" ]; then tag="usebin"; else tag="${MASTER_SHA:0:7}"; fi
    bak="$REAL_PATH.bak-deploy-$tag-$ts-$LEASE_ID"
    [ ! -e "$bak" ] && [ ! -L "$bak" ] || die "binary backup target already exists: $bak"
    cp "$REAL_PATH" "$bak"
    say ">> backed up current binary -> $bak"
fi

# Install every repository-matched audio companion before activating the new
# adapter. A brief interruption can therefore leave the old adapter with extra
# compatible companions, never the new adapter with a missing sibling import.
adapter_dir="$(dirname "$ADAPTER_PATH")"
adapter_root="$(dirname "$adapter_dir")"
if [ "$LEASE_TEST_MODE" = 1 ]; then
    ensure_physical_directory_path "$adapter_dir"
    protect_owned_directory "$adapter_dir" "publisher lease test audio adapter directory"
else
    ensure_trusted_subdirectory_path \
        "$DEPLOY_ROOT" "$adapter_dir" "installed audio adapter directory"
fi
if [ -f "$ADAPTER_PATH" ]; then
    adapter_bak="$ADAPTER_PATH.bak-deploy-$(date +%Y%m%dT%H%M%S)-$LEASE_ID"
    [ ! -e "$adapter_bak" ] && [ ! -L "$adapter_bak" ] ||
        die "audio adapter backup target already exists: $adapter_bak"
    cp "$ADAPTER_PATH" "$adapter_bak"
    say ">> backed up current audio adapter -> $adapter_bak"
fi
for asset in "${AUDIO_ADAPTER_COMPANIONS[@]}"; do
    companion_source="$ASSET_SOURCE_ROOT/scripts/$asset"
    companion_target="$adapter_dir/$asset"
    companion_stage="$companion_target.stage.$$"
    [ ! -e "$companion_stage" ] && [ ! -L "$companion_stage" ] ||
        die "audio companion stage already exists: $companion_stage"
    cp "$companion_source" "$companion_stage"
    chmod 755 "$companion_stage"
    verify_owned_regular_mode "$companion_stage" 755 "staged audio companion"
    mv -f "$companion_stage" "$companion_target"
    verify_owned_regular_mode "$companion_target" 755 "installed audio companion"
    cmp -s "$companion_source" "$companion_target" ||
        die "installed audio companion differs from repository source: $asset"
done
adapter_stage="$ADAPTER_PATH.stage.$$"
[ ! -e "$adapter_stage" ] && [ ! -L "$adapter_stage" ] ||
    die "audio adapter stage already exists: $adapter_stage"
cp "$ADAPTER_SOURCE" "$adapter_stage"
chmod 755 "$adapter_stage"
verify_owned_regular_mode "$adapter_stage" 755 "staged audio adapter"
mv -f "$adapter_stage" "$ADAPTER_PATH"
verify_owned_regular_mode "$ADAPTER_PATH" 755 "installed audio adapter"
cmp -s "$ADAPTER_SOURCE" "$ADAPTER_PATH" ||
    die "installed audio adapter differs from repository source"
say ">> deployed matched audio adapter -> $ADAPTER_PATH"
say ">> deployed matched audio companions -> $adapter_dir"
for asset in "${AUDIO_POLICY_ASSETS[@]}"; do
    policy_source="$ASSET_SOURCE_ROOT/$asset"
    policy_target="$adapter_root/$asset"
    policy_dir="$(dirname "$policy_target")"
    if [ "$LEASE_TEST_MODE" = 1 ]; then
        ensure_physical_directory_path "$policy_dir"
        protect_owned_directory "$policy_dir" "publisher lease test audio policy directory"
    else
        ensure_trusted_subdirectory_path \
            "$DEPLOY_ROOT" "$policy_dir" "installed audio policy directory"
    fi
    policy_stage="$policy_target.stage.$$"
    [ ! -e "$policy_stage" ] && [ ! -L "$policy_stage" ] ||
        die "audio policy stage already exists: $policy_stage"
    cp "$policy_source" "$policy_stage"
    chmod 644 "$policy_stage"
    verify_owned_regular_mode "$policy_stage" 644 "staged audio policy asset"
    mv -f "$policy_stage" "$policy_target"
    verify_owned_regular_mode "$policy_target" 644 "installed audio policy asset"
    cmp -s "$policy_source" "$policy_target" ||
        die "installed audio policy asset differs from repository source: $asset"
done
say ">> deployed matched audio policy assets -> $adapter_root"

# Install script-backed MCP assets at a stable path. The release binary embeds
# its disposable build worktree in CARGO_MANIFEST_DIR, so compile-time fallback
# alone breaks as soon as the deploy cleanup removes that worktree. Stage the
# complete dependency set, then swap the directory as one repository-matched
# unit before installing the binary that resolves it.
runtime_parent="$(dirname "$RUNTIME_ASSET_DIR")"
if [ "$LEASE_TEST_MODE" = 1 ]; then
    ensure_physical_directory_path "$runtime_parent"
    protect_owned_directory "$runtime_parent" "publisher lease test runtime parent"
else
    ensure_trusted_subdirectory_path \
        "$DEPLOY_ROOT" "$runtime_parent" "installed runtime parent"
fi
runtime_stage="$RUNTIME_ASSET_DIR.stage.$$"
CLEANUP_RUNTIME_STAGE="$runtime_stage"
[ ! -e "$runtime_stage" ] && [ ! -L "$runtime_stage" ] ||
    die "runtime asset stage already exists: $runtime_stage"
mkdir -m 700 "$runtime_stage"
verify_owned_directory_mode "$runtime_stage" 700 "staged runtime asset directory"
for asset in "${RUNTIME_ASSETS[@]}"; do
    install -m 755 "$ASSET_SOURCE_ROOT/scripts/$asset" "$runtime_stage/$asset"
    verify_owned_regular_mode "$runtime_stage/$asset" 755 "staged runtime asset"
done
if [ -e "$RUNTIME_ASSET_DIR" ]; then
    runtime_bak="$RUNTIME_ASSET_DIR.bak-deploy-$(date +%Y%m%dT%H%M%S)-$LEASE_ID"
    [ ! -e "$runtime_bak" ] && [ ! -L "$runtime_bak" ] ||
        die "runtime asset backup target already exists: $runtime_bak"
    mv "$RUNTIME_ASSET_DIR" "$runtime_bak"
    if ! mv "$runtime_stage" "$RUNTIME_ASSET_DIR"; then
        mv "$runtime_bak" "$RUNTIME_ASSET_DIR" || true
        die "failed to activate staged runtime assets"
    fi
    say ">> backed up current runtime assets -> $runtime_bak"
else
    mv "$runtime_stage" "$RUNTIME_ASSET_DIR"
fi
CLEANUP_RUNTIME_STAGE=""
verify_owned_directory_mode "$RUNTIME_ASSET_DIR" 700 "installed runtime asset directory"
for asset in "${RUNTIME_ASSETS[@]}"; do
    verify_owned_regular_mode "$RUNTIME_ASSET_DIR/$asset" 755 "installed runtime asset"
done
say ">> deployed matched runtime assets -> $RUNTIME_ASSET_DIR"

binary_stage="$(dirname "$REAL_PATH")/.$(basename "$REAL_PATH").stage.$LEASE_ID.$$"
CLEANUP_BINARY_STAGE="$binary_stage"
[ ! -e "$binary_stage" ] || die "binary activation stage already exists: $binary_stage"
cp "$NEW_BIN" "$binary_stage"
chmod 755 "$binary_stage" || die "cannot set exact mode 0755 on staged binary"
verify_owned_regular_mode "$binary_stage" 755 "staged deployment binary"
staged_size="$(file_size "$binary_stage")"
[ "$staged_size" = "$new_size" ] || die "staged binary size $staged_size != built $new_size"
is_native_exe "$binary_stage" || die "staged binary is no longer a native executable"
STAGED_PRE_SIGN_SHA="$(sha256_file "$binary_stage")"
[ "$STAGED_PRE_SIGN_SHA" = "$FROZEN_CANDIDATE_SHA" ] ||
    die "staged binary differs from the frozen gated candidate"
if [ "$(uname -s)" = "Darwin" ]; then
    command -v codesign >/dev/null 2>&1 || die "codesign is required on macOS before activating the staged Mach-O binary"
    codesign --force --sign - "$binary_stage" >/dev/null
    codesign --verify "$binary_stage" >/dev/null 2>&1 || die "staged macOS binary signature verification failed"
    say ">> ad-hoc signed and verified staged macOS binary"
fi
verify_owned_regular_mode "$binary_stage" 755 "staged deployment binary"
"$binary_stage" --version >/dev/null 2>&1 || die "staged binary failed its execution check"
ACTIVATION_BINARY_SHA="$(sha256_file "$binary_stage")"
new_size="$(file_size "$binary_stage")"
mv -f "$binary_stage" "$REAL_PATH" || die "atomic binary activation failed"
CLEANUP_BINARY_STAGE=""
verify_owned_regular_mode "$REAL_PATH" 755 "installed deployment binary"
say ">> atomically deployed -> $REAL_PATH"
copied_size="$(file_size "$REAL_PATH")"
[ "$copied_size" = "$new_size" ] || die "deployed size $copied_size != staged $new_size"
[ "$(sha256_file "$REAL_PATH")" = "$ACTIVATION_BINARY_SHA" ] ||
    die "installed binary differs from the exact activation candidate"

# Replacing a Mach-O does not refresh long-lived launchd processes: they keep
# the old inode. Refresh only canonical jobs bound to this deployment, then
# prove that each new process maps the installed binary. MCP stdio children stay
# under their owning clients and remain covered by the reconnect report below.
SERVICE_REFRESHED=0
lease_phase_update services_verifying
if [ "$(uname -s)" = "Darwin" ] && command -v launchctl >/dev/null 2>&1; then
    refresh_daemon=0
    refresh_daemon_http=0
    refresh_palace=0
    if preflight_macos_launchagent "com.pallasting.agent-bridge.daemon" "daemon"; then
        refresh_daemon=1
    fi
    if preflight_macos_launchagent "com.pallasting.agent-bridge.daemon-http" "daemon-http"; then
        refresh_daemon_http=1
    fi
    if preflight_macos_launchagent "com.pallasting.agent-bridge.palace" "palace" \
        "serve" "--host" "127.0.0.1" "--port" "7979"; then
        refresh_palace=1
    fi
    if [ "$refresh_daemon" -eq 1 ] || [ "$refresh_daemon_http" -eq 1 ] || [ "$refresh_palace" -eq 1 ]; then
        command -v lsof >/dev/null 2>&1 ||
            die "lsof is required to verify refreshed launchd service inodes"
        if [ "$refresh_daemon_http" -eq 1 ] || [ "$refresh_palace" -eq 1 ]; then
            command -v curl >/dev/null 2>&1 ||
                die "curl is required to verify launchd service health"
        fi
        deployed_inode="$(file_inode "$REAL_PATH")" ||
            die "cannot read deployed binary inode for launchd verification: $REAL_PATH"
        [ "$refresh_daemon" -eq 0 ] ||
            refresh_macos_launchagent "com.pallasting.agent-bridge.daemon" "$deployed_inode"
        [ "$refresh_daemon_http" -eq 0 ] ||
            refresh_macos_launchagent "com.pallasting.agent-bridge.daemon-http" "$deployed_inode" \
                "http://127.0.0.1:7878/healthz" "7878"
        [ "$refresh_palace" -eq 0 ] ||
            refresh_macos_launchagent "com.pallasting.agent-bridge.palace" "$deployed_inode" \
                "http://127.0.0.1:7979/healthz" "7979"
    fi
    say "launchd service refresh: $SERVICE_REFRESHED service(s) adopted the deployed binary"
fi

# ---- 7. post-deploy verification ----
say
say "=== post-deploy verification ==="
dep_size="$(file_size "$REAL_PATH")"
[ "$dep_size" = "$new_size" ] || die "deployed size $dep_size != built $new_size (copy failed?)"
cmp -s "$ADAPTER_SOURCE" "$ADAPTER_PATH" ||
    die "post-deploy audio adapter parity check failed"
say "audio adapter parity: OK ($ADAPTER_PATH)"
for asset in "${AUDIO_ADAPTER_COMPANIONS[@]}"; do
    cmp -s "$ASSET_SOURCE_ROOT/scripts/$asset" "$adapter_dir/$asset" ||
        die "post-deploy audio companion parity check failed: $asset"
done
say "audio companion parity: OK (${#AUDIO_ADAPTER_COMPANIONS[@]} scripts in $adapter_dir)"
for asset in "${AUDIO_POLICY_ASSETS[@]}"; do
    cmp -s "$ASSET_SOURCE_ROOT/$asset" "$adapter_root/$asset" ||
        die "post-deploy audio policy parity check failed: $asset"
done
say "audio policy parity: OK (${#AUDIO_POLICY_ASSETS[@]} files under $adapter_root)"
for asset in "${RUNTIME_ASSETS[@]}"; do
    cmp -s "$ASSET_SOURCE_ROOT/scripts/$asset" "$RUNTIME_ASSET_DIR/$asset" ||
        die "post-deploy runtime asset parity check failed: $asset"
done
say "runtime asset parity: OK (${#RUNTIME_ASSETS[@]} scripts in $RUNTIME_ASSET_DIR)"
# Parity alone is insufficient if a stale/partial asset set comes from a
# different checkout. Check the protocol router's shipped action contract too;
# this turns a later MCP `script_missing`/unknown-action failure into a deploy
# gate failure with an actionable message.
APP_CONTROL_RUNTIME="$RUNTIME_ASSET_DIR/app_control.py"
[ -f "$APP_CONTROL_RUNTIME" ] || die "post-deploy app_control asset missing: $APP_CONTROL_RUNTIME"
grep -q '"playlist_current"' "$APP_CONTROL_RUNTIME" ||
    die "post-deploy app_control contract missing playlist_current: $APP_CONTROL_RUNTIME"
grep -q '"playlist_activate"' "$APP_CONTROL_RUNTIME" ||
    die "post-deploy app_control contract missing playlist_activate: $APP_CONTROL_RUNTIME"
grep -q 'agent_bridge.app_control.operation.v0' "$APP_CONTROL_RUNTIME" ||
    die "post-deploy app_control contract missing durable operation journal: $APP_CONTROL_RUNTIME"
grep -q 'agent_bridge.app_control.operation_preflight.v0' "$APP_CONTROL_RUNTIME" ||
    die "post-deploy app_control contract missing durable operation preflight: $APP_CONTROL_RUNTIME"
grep -q 'agent_bridge.app_control.track_settlement.v0' "$APP_CONTROL_RUNTIME" ||
    die "post-deploy app_control contract missing bounded durable track settlement: $APP_CONTROL_RUNTIME"
grep -q 'agent_bridge.app_control.wrapper_contract.v1' "$APP_CONTROL_RUNTIME" ||
    die "post-deploy app_control contract missing action-before-version handshake: $APP_CONTROL_RUNTIME"
say "app_control action contract: OK (playlist_current, playlist_activate, durable operation + preflight + track settlement v0 + wrapper handshake v1)"
# unquoted on purpose: markers are one-per-line + whitespace-free, so word-splitting
# gives one printf arg per marker (each gets its own "  + " prefix).
# shellcheck disable=SC2046,SC2086
say "deployed markers:"; printf '  + %s\n' $(markers_in "$REAL_PATH")
lease_phase_update awaiting_fresh_mcp
write_pending_admission "$LEASE_CANDIDATE"
archive_pending_completion
complete_recovery_handoff_intent

# Reconnect surface: a deployed-over .real shows as "(deleted)" in /proc/PID/exe
# for any MCP server still mapping the OLD inode. Report the count so the operator
# knows which sessions still need /mcp reconnect. Read-only — never kills anything.
stale=0; fresh=0; stale_list=""
for pid in $(pgrep -f 'agent-bridge.*mcp' 2>/dev/null || true); do
    exe="$(readlink "/proc/$pid/exe" 2>/dev/null || true)"
    case "$exe" in
        *"(deleted)")
            stale=$((stale + 1))
            # Identify the owning client so the operator knows exactly which session
            # to /mcp reconnect: parent process (CC/Codex/Cursor) + the server's cwd
            # (the project it serves). /proc only — this whole block is Linux-only;
            # on macOS readlink /proc returns nothing so stale stays 0 (no-op).
            ppid="$(awk '{print $4}' "/proc/$pid/stat" 2>/dev/null || echo '?')"
            pcomm="$(tr -d '\0' < "/proc/$ppid/comm" 2>/dev/null || echo '?')"
            cwd="$(readlink "/proc/$pid/cwd" 2>/dev/null || echo '?')"
            stale_list="${stale_list}
        - pid $pid  (client: ${ppid}/${pcomm}, cwd: ${cwd})"
            ;;
        */agent-bridge.real) fresh=$((fresh + 1)) ;;
    esac
done

say
say "DONE. The running MCP server still holds the OLD binary —"
say "      run /mcp reconnect (per CC session) to activate the new one."
if [ "$stale" -gt 0 ]; then
    say "      reconnect surface: $stale running MCP server(s) still on the OLD binary"
    say "      ($fresh already on the new one) — each needs its own /mcp reconnect"
    say "      (until reconnected, agent-bridge doctor reports warns>=1 and the strict"
    say "      warns=0 pre-write gate stays blocked). Servers to reconnect:"
    printf '%s\n' "$stale_list"
fi
if [ -n "${bak:-}${adapter_bak:-}${runtime_bak:-}" ]; then
    say "      recovery artifacts were retained; use the governed recovery workflow"
    say "      and its receipt checks instead of raw copy/move rollback commands."
fi
release_active_lease pending_admission fresh_mcp_unverified
# Explicit success: the final command above must not leave a nonzero status (a
# bare `[ -n "" ] && …` on a first install returns 1 and, as the last command
# under `set -e`, would falsely report deploy failure to callers checking $?).
exit 0
