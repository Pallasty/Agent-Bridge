#!/bin/bash
# Install or update the agent-bridge env-injection wrapper at the canonical
# trusted deployment root, moving an existing binary in that same root aside
# to agent-bridge.real if needed.
#
# Idempotent: re-running upgrades the wrapper template without touching
# the real binary or the credentials file.
#
# Usage (run this file through /bin/bash from the fixed private source clone):
#   /bin/bash scripts/wrapper/install.sh               # install/update
#   /bin/bash scripts/wrapper/install.sh --uninstall   # restore plain binary
#   /bin/bash scripts/wrapper/install.sh --dry-run     # plan only

set -euo pipefail
umask 077
PATH=/usr/bin:/bin
export PATH

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
INSTALLER_PATH="$SCRIPT_DIR/$(basename "${BASH_SOURCE[0]}")"
SOURCE_REPO="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
WRAPPER_TEMPLATE="$SCRIPT_DIR/agent-bridge-wrapper.sh"
CREDS_TEMPLATE="$SCRIPT_DIR/creds.example"

DEPLOY_ROOT_RAW="${AGENT_BRIDGE_DEPLOY_ROOT:-}"
INSTALL_DIR="$DEPLOY_ROOT_RAW/bin"
WRAPPER_PATH="$INSTALL_DIR/agent-bridge"
REAL_PATH="$INSTALL_DIR/agent-bridge.real"

DRY_RUN=0
UNINSTALL=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --uninstall) UNINSTALL=1 ;;
        -h|--help)
            sed -n '2,12p' "$0"
            exit 0
            ;;
        *)
            echo "unknown arg: $arg" >&2
            exit 2
            ;;
    esac
done

run() {
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[dry-run] $*"
    else
        "$@"
    fi
}

file_mode() {
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

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

validate_trusted_deploy_root() {
    local raw="$1" canonical euid owner mode numeric ancestor
    [ -n "$raw" ] || fail "AGENT_BRIDGE_DEPLOY_ROOT must not be empty"
    case "$raw" in
        *[!A-Za-z0-9._/-]*)
            fail "AGENT_BRIDGE_DEPLOY_ROOT contains an unsupported character"
            ;;
    esac
    case "$raw" in /*) ;; *) fail "AGENT_BRIDGE_DEPLOY_ROOT must be absolute: $raw" ;; esac
    [ -d "$raw" ] && [ ! -L "$raw" ] ||
        fail "AGENT_BRIDGE_DEPLOY_ROOT must be a pre-existing physical directory: $raw"
    ! path_has_symlink_component "$raw" ||
        fail "AGENT_BRIDGE_DEPLOY_ROOT must not traverse a symlink: $raw"
    canonical="$(cd -P "$raw" && pwd -P)" || fail "cannot canonicalize AGENT_BRIDGE_DEPLOY_ROOT: $raw"
    [ "$raw" = "$canonical" ] ||
        fail "AGENT_BRIDGE_DEPLOY_ROOT must be an absolute canonical path: $raw"
    euid="$(id -u)"
    owner="$(file_owner_uid "$canonical")" || fail "cannot inspect deployment root owner"
    [ "$owner" = "$euid" ] || fail "AGENT_BRIDGE_DEPLOY_ROOT must be owned by euid $euid: $canonical"
    mode="$(file_mode "$canonical")" || fail "cannot inspect deployment root mode"
    numeric="$(mode_value "$mode")" || fail "cannot parse deployment root mode"
    [ "$mode" = 700 ] ||
        fail "AGENT_BRIDGE_DEPLOY_ROOT mode must be exact 0700: $canonical (mode $mode)"
    ancestor="$(dirname "$canonical")"
    while :; do
        [ -d "$ancestor" ] && [ ! -L "$ancestor" ] ||
            fail "AGENT_BRIDGE_DEPLOY_ROOT ancestor is not a physical directory: $ancestor"
        owner="$(file_owner_uid "$ancestor")" || fail "cannot inspect deployment root ancestor owner"
        [ "$owner" = "$euid" ] || [ "$owner" = 0 ] ||
            fail "AGENT_BRIDGE_DEPLOY_ROOT ancestor must be owned by euid $euid or root: $ancestor"
        mode="$(file_mode "$ancestor")" || fail "cannot inspect deployment root ancestor mode"
        numeric="$(mode_value "$mode")" || fail "cannot parse deployment root ancestor mode"
        if [ $((numeric & 0022)) -ne 0 ]; then
            [ "$owner" = 0 ] && [ $((numeric & 01000)) -ne 0 ] ||
                fail "AGENT_BRIDGE_DEPLOY_ROOT ancestor is group/other writable without a root-owned sticky boundary: $ancestor (mode $mode)"
        fi
        [ "$ancestor" = / ] && break
        ancestor="$(dirname "$ancestor")"
    done
    DEPLOY_ROOT="$canonical"
}

validate_leaf_override() {
    local name="$1" present="$2" raw="$3" expected="$4"
    [ -z "$present" ] || [ "$raw" = "$expected" ] ||
        fail "$name diverges from AGENT_BRIDGE_DEPLOY_ROOT; expected exact path: $expected"
}

validate_owned_safe_directory() {
    local path="$1" label="${2:-trusted directory}" euid owner mode
    [ -d "$path" ] && [ ! -L "$path" ] || fail "$label is not a physical directory: $path"
    euid="$(id -u)"
    owner="$(file_owner_uid "$path")" || fail "cannot inspect $label owner: $path"
    [ "$owner" = "$euid" ] || fail "$label must be owned by euid $euid: $path"
    mode="$(file_mode "$path")" || fail "cannot inspect $label mode: $path"
    [ "$mode" = 700 ] || fail "$label mode must be exact 0700: $path (mode $mode)"
}

ensure_owned_safe_subdirectory() {
    local parent="$1" path="$2" label="$3"
    validate_owned_safe_directory "$parent" "$label parent"
    if [ ! -e "$path" ] && [ ! -L "$path" ]; then
        if ! mkdir -m 700 "$path"; then
            [ -d "$path" ] && [ ! -L "$path" ] || fail "cannot create $label: $path"
        fi
    fi
    validate_owned_safe_directory "$path" "$label"
}

acquire_publisher_mutex() {
    local state_parent state_root lock path_inode path_device fd_inode fd_device host_os
    state_parent="$DEPLOY_ROOT/publisher-state"
    state_root="$state_parent/deploy"
    lock="$state_root/publisher.kernel.lock"
    ensure_owned_safe_subdirectory "$DEPLOY_ROOT" "$state_parent" "publisher state parent"
    ensure_owned_safe_subdirectory "$state_parent" "$state_root" "publisher state root"
    if [ ! -e "$lock" ] && [ ! -L "$lock" ]; then
        if (set -o noclobber; : > "$lock") 2>/dev/null; then
            chmod 600 "$lock" || fail "cannot protect publisher kernel mutex"
        fi
    fi
    validate_owned_source_file "$lock" 600 "publisher kernel mutex"
    exec 9>>"$lock" || fail "cannot open publisher kernel mutex"
    path_inode="$(file_inode "$lock")" || fail "cannot inspect publisher kernel mutex inode"
    path_device="$(file_device "$lock")" || fail "cannot inspect publisher kernel mutex device"
    host_os="$(/usr/bin/uname -s 2>/dev/null || uname -s)"
    case "$host_os" in
        Linux)
            fd_inode="$(stat -Lc %i /proc/self/fd/9 2>/dev/null)" ||
                fail "cannot inspect opened publisher mutex inode"
            fd_device="$(stat -Lc %d /proc/self/fd/9 2>/dev/null)" ||
                fail "cannot inspect opened publisher mutex device"
            ;;
        Darwin)
            fd_inode="$(stat -f %i /dev/fd/9 2>/dev/null)" ||
                fail "cannot inspect opened publisher mutex inode"
            fd_device="$(stat -f %d /dev/fd/9 2>/dev/null)" ||
                fail "cannot inspect opened publisher mutex device"
            ;;
        *) fail "unsupported publisher mutex platform: $host_os" ;;
    esac
    [ "$path_inode:$path_device" = "$fd_inode:$fd_device" ] ||
        fail "publisher kernel mutex changed while it was opened"
    case "$host_os" in
        Linux)
            [ -x /usr/bin/flock ] || fail "publisher serialization requires /usr/bin/flock"
            /usr/bin/flock -n 9 || fail "another publisher or trusted installer owns the publisher kernel mutex"
            ;;
        Darwin)
            [ -x /usr/bin/lockf ] || fail "publisher serialization requires /usr/bin/lockf"
            /usr/bin/lockf -s -t 0 9 ||
                fail "another publisher or trusted installer owns the publisher kernel mutex"
            ;;
        *) fail "unsupported publisher mutex platform: $host_os" ;;
    esac
}

validate_owned_source_file() {
    local path="$1" expected_mode="$2" label="$3" owner mode
    ! path_has_symlink_component "$path" || fail "$label path must not traverse a symlink"
    [ -f "$path" ] && [ ! -L "$path" ] || fail "$label must be a physical regular file"
    owner="$(file_owner_uid "$path")" || fail "cannot inspect $label owner"
    [ "$owner" = "$(id -u)" ] || fail "$label must be owned by the effective user"
    mode="$(file_mode "$path")" || fail "cannot inspect $label mode"
    [ "$mode" = "$expected_mode" ] || fail "$label mode must be exact 0$expected_mode"
}

validate_existing_runtime_file() {
    local path="$1" label="$2" owner mode
    [ -f "$path" ] && [ ! -L "$path" ] ||
        fail "$label must be a physical regular file: $path"
    owner="$(file_owner_uid "$path")" || fail "cannot inspect $label owner: $path"
    [ "$owner" = "$(id -u)" ] || fail "$label must be owned by the effective user: $path"
    mode="$(file_mode "$path")" || fail "cannot inspect $label mode: $path"
    [ "$mode" = 755 ] || fail "$label mode must be exact 0755: $path (mode $mode)"
}

validate_private_source_checkout() {
    local expected_repo="$DEPLOY_ROOT/source/agent-bridge"
    local expected_installer="$DEPLOY_ROOT/source/agent-bridge/scripts/wrapper/install.sh"
    [ "$SOURCE_REPO" = "$expected_repo" ] ||
        fail "wrapper install must run from the fixed trusted checkout: $expected_repo"
    [ "$INSTALLER_PATH" = "$expected_installer" ] ||
        fail "wrapper install must execute the exact trusted installer path: $expected_installer"
    validate_owned_safe_directory "$DEPLOY_ROOT/source" "trusted source directory"
    validate_owned_safe_directory "$SOURCE_REPO" "trusted source checkout"
    validate_owned_safe_directory "$SOURCE_REPO/.git" "trusted source Git metadata"
    validate_owned_safe_directory "$SOURCE_REPO/scripts" "trusted source scripts directory"
    validate_owned_safe_directory "$SCRIPT_DIR" "trusted wrapper source directory"
    validate_owned_source_file "$INSTALLER_PATH" 600 "trusted wrapper installer"
    validate_owned_source_file "$WRAPPER_TEMPLATE" 600 "trusted wrapper template"
    validate_owned_source_file "$CREDS_TEMPLATE" 600 "trusted credentials example"
}

# Heuristic: a shell wrapper is a small text file (<32 KiB) whose head
# mentions agent-bridge; the real binary is an ELF/Mach-O > 1 MiB.
is_wrapper_script() {
    local path="$1"
    [ -f "$path" ] || return 1
    if head -c 4 "$path" 2>/dev/null | grep -qE '^(\x7fELF|\xcf\xfa\xed\xfe|\xfe\xed\xfa)'; then
        return 1
    fi
    head -1 "$path" 2>/dev/null | grep -q '^#!.*\(bash\|sh\)' || return 1
    grep -q 'agent-bridge\.real' "$path" 2>/dev/null
}

is_native_executable() {
    local magic
    magic="$(head -c 4 "$1" 2>/dev/null)" || return 1
    [ "$magic" = $'\x7fELF' ] && return 0
    [ "$magic" = $'\xcf\xfa\xed\xfe' ] && return 0
    [ "$magic" = $'\xce\xfa\xed\xfe' ] && return 0
    [ "$magic" = $'\xca\xfe\xba\xbe' ] && return 0
    [ "$magic" = $'\xbe\xba\xfe\xca' ] && return 0
    return 1
}

validate_trusted_deploy_root "$DEPLOY_ROOT_RAW"
derived_install="$DEPLOY_ROOT/bin"
derived_real="$derived_install/agent-bridge.real"
validate_leaf_override AGENT_BRIDGE_INSTALL_DIR \
    "${AGENT_BRIDGE_INSTALL_DIR+x}" "${AGENT_BRIDGE_INSTALL_DIR-}" "$derived_install"
validate_leaf_override AGENT_BRIDGE_REAL_BIN \
    "${AGENT_BRIDGE_REAL_BIN+x}" "${AGENT_BRIDGE_REAL_BIN-}" "$derived_real"
validate_leaf_override AGENT_BRIDGE_AUDIO_EMBODY_PATH \
    "${AGENT_BRIDGE_AUDIO_EMBODY_PATH+x}" "${AGENT_BRIDGE_AUDIO_EMBODY_PATH-}" \
    "$DEPLOY_ROOT/share/ab-tts/audio_embody.py"
validate_leaf_override AGENT_BRIDGE_RUNTIME_ASSET_DIR \
    "${AGENT_BRIDGE_RUNTIME_ASSET_DIR+x}" "${AGENT_BRIDGE_RUNTIME_ASSET_DIR-}" \
    "$DEPLOY_ROOT/lib/agent-bridge/scripts"
validate_leaf_override AGENT_BRIDGE_DEPLOY_STATE_DIR \
    "${AGENT_BRIDGE_DEPLOY_STATE_DIR+x}" "${AGENT_BRIDGE_DEPLOY_STATE_DIR-}" \
    "$DEPLOY_ROOT/publisher-state/deploy"
INSTALL_DIR="$derived_install"
WRAPPER_PATH="$derived_install/agent-bridge"
REAL_PATH="$derived_real"
for trusted_path in "$INSTALL_DIR" "$WRAPPER_PATH" "$REAL_PATH"; do
    ! path_has_symlink_component "$trusted_path" ||
        fail "canonical deployment path must not traverse a symlink: $trusted_path"
done
if [ -e "$INSTALL_DIR" ] || [ -L "$INSTALL_DIR" ]; then
    validate_owned_safe_directory "$INSTALL_DIR" "install bin directory"
fi
validate_private_source_checkout
for existing_runtime_path in "$WRAPPER_PATH" "$REAL_PATH"; do
    if [ -e "$existing_runtime_path" ] || [ -L "$existing_runtime_path" ]; then
        case "$existing_runtime_path" in
            "$WRAPPER_PATH") existing_runtime_label="existing wrapper or binary" ;;
            *) existing_runtime_label="existing real binary" ;;
        esac
        validate_existing_runtime_file "$existing_runtime_path" "$existing_runtime_label"
        if [ "$existing_runtime_path" = "$REAL_PATH" ]; then
            is_native_executable "$existing_runtime_path" ||
                fail "existing real binary is not a native executable: $existing_runtime_path"
        fi
    fi
done

# Wrapper replacement and binary publication share one kernel mutex. The
# first trusted wrapper install creates the private publisher-state hierarchy;
# subsequent publishers/installers must observe and lock the same inode before
# any deployment mutation. A dry run remains strictly read-only.
if [ "$DRY_RUN" -eq 0 ]; then
    acquire_publisher_mutex
fi

if [ "$UNINSTALL" -eq 1 ]; then
    if [ ! -f "$REAL_PATH" ]; then
        echo "no $REAL_PATH found — nothing to uninstall" >&2
        exit 0
    fi
    if [ -f "$WRAPPER_PATH" ] && is_wrapper_script "$WRAPPER_PATH"; then
        echo "Restoring real binary: $REAL_PATH -> $WRAPPER_PATH"
        run mv -f "$REAL_PATH" "$WRAPPER_PATH"
        if [ "$DRY_RUN" -eq 0 ]; then
            chmod 755 "$WRAPPER_PATH" || fail "cannot set restored binary mode to exact 0755"
            [ "$(file_owner_uid "$WRAPPER_PATH")" = "$(id -u)" ] &&
                [ "$(file_mode "$WRAPPER_PATH")" = 755 ] ||
                fail "restored binary does not satisfy trusted owner/mode"
        fi
    else
        echo "$WRAPPER_PATH doesn't look like our wrapper — leaving alone" >&2
        echo "(real binary is still at $REAL_PATH)" >&2
        exit 1
    fi
    echo "Uninstalled. Wrapper removed; agent-bridge is now the plain binary."
    exit 0
fi

# ---- Install path ----

if [ ! -f "$WRAPPER_TEMPLATE" ]; then
    echo "wrapper template missing: $WRAPPER_TEMPLATE" >&2
    exit 1
fi

if [ ! -e "$INSTALL_DIR" ]; then
    run mkdir -m 700 "$INSTALL_DIR"
fi
if [ "$DRY_RUN" -eq 0 ]; then
    validate_owned_safe_directory "$INSTALL_DIR" "install bin directory"
fi

# Decide what existing $WRAPPER_PATH is.
if [ ! -e "$WRAPPER_PATH" ]; then
    echo "No existing $WRAPPER_PATH found."
    echo "  After install, place the real binary at $REAL_PATH"
    echo "  (e.g. \`cp target/release/agent-bridge $REAL_PATH\`)"
elif is_wrapper_script "$WRAPPER_PATH"; then
    echo "Existing wrapper at $WRAPPER_PATH — will replace with newer template."
    if [ ! -f "$REAL_PATH" ]; then
        echo "WARNING: $REAL_PATH missing. The wrapper will fail at exec time." >&2
        echo "         Reinstall the real binary before running agent-bridge." >&2
    fi
else
    # Looks like the real binary is currently at $WRAPPER_PATH (no wrapper yet).
    is_native_executable "$WRAPPER_PATH" || {
        echo "$WRAPPER_PATH is neither our wrapper nor a native executable." >&2
        exit 1
    }
    if [ -f "$REAL_PATH" ]; then
        echo "Both $WRAPPER_PATH and $REAL_PATH exist, and $WRAPPER_PATH"
        echo "doesn't look like our wrapper (not a shell script exec'ing agent-bridge.real)." >&2
        echo "Inspect manually, then re-run." >&2
        exit 1
    fi
    echo "Moving existing binary aside: $WRAPPER_PATH -> $REAL_PATH"
    run mv -f "$WRAPPER_PATH" "$REAL_PATH"
    if [ "$DRY_RUN" -eq 0 ]; then
        chmod 755 "$REAL_PATH" || fail "cannot set moved real binary mode to exact 0755"
        [ "$(file_owner_uid "$REAL_PATH")" = "$(id -u)" ] &&
            [ "$(file_mode "$REAL_PATH")" = 755 ] ||
            fail "moved real binary does not satisfy trusted owner/mode"
    fi
fi

echo "Installing wrapper atomically: $WRAPPER_TEMPLATE -> $WRAPPER_PATH"
if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] install private stage and rename it to $WRAPPER_PATH"
else
    WRAPPER_STAGE="$INSTALL_DIR/.agent-bridge.wrapper-stage.$$.$RANDOM"
    trap 'rm -f -- "${WRAPPER_STAGE:-}" 2>/dev/null || true' EXIT
    [ ! -e "$WRAPPER_STAGE" ] && [ ! -L "$WRAPPER_STAGE" ] ||
        fail "wrapper stage path already exists"
    install -m 755 "$WRAPPER_TEMPLATE" "$WRAPPER_STAGE"
    validate_owned_source_file "$WRAPPER_STAGE" 755 "staged wrapper"
    mv -f -- "$WRAPPER_STAGE" "$WRAPPER_PATH"
    WRAPPER_STAGE=""
    trap - EXIT
    [ -f "$WRAPPER_PATH" ] && [ ! -L "$WRAPPER_PATH" ] ||
        fail "installed wrapper is not a physical regular file: $WRAPPER_PATH"
    [ "$(file_owner_uid "$WRAPPER_PATH")" = "$(id -u)" ] ||
        fail "installed wrapper is not owned by the effective user: $WRAPPER_PATH"
    [ "$(file_mode "$WRAPPER_PATH")" = 755 ] ||
        fail "installed wrapper mode is not exact 0755: $WRAPPER_PATH"
fi

# Credentials file hint. Alternate roots never fall back to the legacy HOME
# notebook; the operator must provision any secret-bearing file deliberately.
account_home="${HOME:-}"
if [ -n "$account_home" ] && [ "$DEPLOY_ROOT" = "$account_home/.local" ]; then
    default_creds="$account_home/Documents/ClaudeCode.txt"
    [ -d "/Media/Ubuntu/Documents" ] && default_creds="/Media/Ubuntu/Documents/ClaudeCode.txt"
else
    default_creds="$DEPLOY_ROOT/config/agent-bridge/credentials"
fi
if [ -n "${AGENT_BRIDGE_CREDS_FILE:-}" ]; then
    creds_to_check="$AGENT_BRIDGE_CREDS_FILE"
else
    creds_to_check="$default_creds"
fi

echo
if [ -f "$creds_to_check" ]; then
    echo "Credentials file detected: $creds_to_check"
    if grep -q "^[[:space:]]*#[[:space:]]*Agent-Bridge[[:space:]]\+Primary" "$creds_to_check"; then
        echo "  Found '# Agent-Bridge Primary' section — wrapper will use it."
    else
        echo "  No '# Agent-Bridge Primary' section yet."
        echo "  Wrapper will leave the primary Anthropic token unset."
        echo "  To pin the active proxy, copy the section from $CREDS_TEMPLATE."
    fi
else
    echo "No credentials file at $creds_to_check yet."
    echo "  Copy the template:  cp $CREDS_TEMPLATE $creds_to_check"
    echo "  Edit and replace the REPLACE_ME placeholders with real tokens."
fi

echo
# Installing a runtime wrapper must not mutate source-control hooks. Repository
# hook setup remains a separate, explicit development action.
echo "Done. Verify with:  $WRAPPER_PATH --version"
