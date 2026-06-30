# shellcheck shell=bash

# Small, source-only helpers for scripts that need to run on both GNU/Linux and
# macOS without pulling in GNU coreutils.

ab_platform_os() {
    uname -s 2>/dev/null || printf 'unknown'
}

ab_is_linux() {
    [ "$(ab_platform_os)" = "Linux" ]
}

ab_is_macos() {
    [ "$(ab_platform_os)" = "Darwin" ]
}

ab_default_data_dir() {
    case "$(ab_platform_os)" in
        Darwin)
            printf '%s/Library/Application Support/agent-bridge' "${HOME:-.}"
            ;;
        Linux)
            if [ -n "${XDG_DATA_HOME:-}" ]; then
                printf '%s/agent-bridge' "$XDG_DATA_HOME"
            else
                printf '%s/.local/share/agent-bridge' "${HOME:-.}"
            fi
            ;;
        *)
            if [ -n "${XDG_DATA_HOME:-}" ]; then
                printf '%s/agent-bridge' "$XDG_DATA_HOME"
            else
                printf '%s/.local/share/agent-bridge' "${HOME:-.}"
            fi
            ;;
    esac
}

ab_default_state_db() {
    printf '%s/state.db' "$(ab_default_data_dir)"
}

ab_default_cache_dir() {
    case "$(ab_platform_os)" in
        Darwin)
            printf '%s/Library/Caches/agent-bridge' "${HOME:-.}"
            ;;
        *)
            if [ -n "${XDG_CACHE_HOME:-}" ]; then
                printf '%s/agent-bridge' "$XDG_CACHE_HOME"
            else
                printf '%s/.cache/agent-bridge' "${HOME:-.}"
            fi
            ;;
    esac
}

ab_default_system_control_audit_dir() {
    if [ -d /Data ] && [ -w /Data ]; then
        printf '/Data/agent-bridge/system-control'
    else
        printf '%s/system-control' "$(ab_default_data_dir)"
    fi
}

ab_file_bytes() {
    stat -c '%s' "$1" 2>/dev/null || stat -f '%z' "$1" 2>/dev/null || printf '?'
}

ab_file_mtime() {
    stat -c '%y' "$1" 2>/dev/null || stat -f '%Sm' "$1" 2>/dev/null || printf '?'
}

ab_sha256() {
    local path="$1"
    if [ ! -f "$path" ]; then
        printf '<missing>'
        return 1
    fi
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$path" | awk '{print $1}'
        return
    fi
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$path" | awk '{print $1}'
        return
    fi
    if command -v openssl >/dev/null 2>&1; then
        openssl dgst -sha256 -r "$path" 2>/dev/null | awk '{print $1}'
        return
    fi
    printf '<sha256-unavailable>'
    return 1
}

ab_same_file() {
    local lhs="$1"
    local rhs="$2"
    [ -n "$lhs" ] && [ -n "$rhs" ] && [ -f "$lhs" ] && [ -f "$rhs" ] && [ "$lhs" -ef "$rhs" ]
}

ab_list_agent_bridge_reader_pids() {
    if command -v pgrep >/dev/null 2>&1; then
        pgrep -f 'agent-bridge.real (daemon|daemon-http|mcp)' 2>/dev/null || true
        return
    fi
    ps -axo pid=,command= 2>/dev/null |
        awk '/agent-bridge\.real (daemon|daemon-http|mcp)/ {print $1}' || true
}

ab_reader_env_value() {
    local pid="$1"
    local key="$2"
    if [ -r "/proc/$pid/environ" ]; then
        tr '\0' '\n' <"/proc/$pid/environ" |
            awk -F= -v key="$key" '$1 == key {print $2; found=1} END {if (!found) print "<unset>"}'
        return
    fi
    printf '<unavailable>'
    return 1
}

ab_reader_cmdline() {
    local pid="$1"
    if [ -r "/proc/$pid/cmdline" ]; then
        tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true
        return
    fi
    ps -p "$pid" -o command= 2>/dev/null || true
}
