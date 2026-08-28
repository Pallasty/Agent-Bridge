#!/bin/bash
# agent-bridge wrapper — injects environment variables from a credentials
# file before exec'ing the real binary.
#
# Why this exists: some MCP clients (Antigravity Claude, certain IDE
# integrations) silently drop the .claude.json `env` block when launching
# stdio-based MCP servers. Without this wrapper, the agent-bridge daemon
# starts with an empty token environment and tool calls (Anthropic API,
# GitHub PAT, Tailscale OAuth, etc.) fail.
#
# Layout: this wrapper is installed at $DEPLOY_ROOT/bin/agent-bridge and
# exec's its physical sibling $DEPLOY_ROOT/bin/agent-bridge.real. Runtime
# assets derive from the parent deployment root, so the same wrapper works at
# a permission-capable non-HOME root. The credentials file is plain text with
# named sections (see creds.example in this directory).
#
# Override paths via env:
#   AGENT_BRIDGE_CREDS_FILE  — credentials file path (default below)
#   AGENT_BRIDGE_REAL_BIN    — explicit real binary compatibility override

set -euo pipefail

# Wrapper bootstrap is part of the executable trust chain. Resolve every tool
# used to inspect credentials/configuration from the fixed system path; a
# caller-provided or HOME-writable PATH is handed to legacy children only after
# parsing is complete.
caller_path="${PATH:-}"
PATH=/usr/bin:/bin
export PATH
# These names can influence a later dynamic loader, shell, or language runtime.
# A trusted parent (for example the bounded systemd unit) must remove them
# before this interpreter starts; clear them again here so they never reach the
# real binary or repository-matched helpers.
unset LD_PRELOAD LD_LIBRARY_PATH LD_AUDIT LD_DEBUG LD_PROFILE GCONV_PATH \
    LOCPATH NLSPATH BASH_ENV ENV PYTHONPATH PYTHONHOME PERL5LIB RUBYLIB \
    NODE_OPTIONS NODE_PATH RUSTC_WRAPPER 2>/dev/null || true

# Resolve the installed wrapper itself, including a symlinked invocation, then
# bind the default executable and assets to that physical deployment tree. Do
# this before loading owner-controlled environment files so the executable
# identity cannot silently drift back to a HOME leaf on alternate-root hosts.
wrapper_source="${BASH_SOURCE[0]}"
case "$wrapper_source" in /*) ;; *) wrapper_source="$PWD/$wrapper_source" ;; esac
wrapper_link_depth=0
while [ -L "$wrapper_source" ]; do
    wrapper_link_depth=$((wrapper_link_depth + 1))
    [ "$wrapper_link_depth" -le 40 ] || {
        printf 'agent-bridge wrapper symlink depth exceeds 40\n' >&2
        exit 1
    }
    wrapper_link="$(readlink "$wrapper_source")"
    [ -n "$wrapper_link" ] || {
        printf 'agent-bridge wrapper cannot resolve its symlink target\n' >&2
        exit 1
    }
    case "$wrapper_link" in
        /*) wrapper_source="$wrapper_link" ;;
        *) wrapper_source="$(dirname "$wrapper_source")/$wrapper_link" ;;
    esac
done
wrapper_bin_dir="$(cd -P "$(dirname "$wrapper_source")" && pwd -P)"
wrapper_deploy_root="$(dirname "$wrapper_bin_dir")"
real_bin="${AGENT_BRIDGE_REAL_BIN:-$wrapper_bin_dir/agent-bridge.real}"

# An alternate trusted root must not fall back to executable configuration or
# credentials on HOME. Legacy ~/.local installs retain their historical
# defaults unless the caller explicitly opts into the pinned-root contract.
if [ "${AGENT_BRIDGE_DEPLOY_ROOT+x}" = x ] ||
        [ "$wrapper_deploy_root" != "$HOME/.local" ]; then
    default_config_dir="$wrapper_deploy_root/config/agent-bridge"
    default_creds="$default_config_dir/credentials"
    default_machine_env="$default_config_dir/machine.env"
else
    default_creds="${HOME}/Documents/ClaudeCode.txt"
    [ -f "/Media/Ubuntu/Documents/ClaudeCode.txt" ] && default_creds="/Media/Ubuntu/Documents/ClaudeCode.txt"
    default_machine_env="$HOME/.config/agent-bridge/machine.env"
fi
creds="${AGENT_BRIDGE_CREDS_FILE:-$default_creds}"
if [ "${AGENT_BRIDGE_DEPLOY_ROOT+x}" = x ] ||
        [ "$wrapper_deploy_root" != "$HOME/.local" ]; then
    wrapper_secure_mode=1
    child_path="$wrapper_bin_dir:/usr/bin:/bin"
else
    wrapper_secure_mode=0
    user_cli_path=""
    for dir in "$HOME/.local/bin" "$HOME/.npm-global/bin" "$HOME/.cargo/bin"; do
        [ -d "$dir" ] || continue
        case ":${caller_path:-}:" in
            *":$dir:"*) ;;
            *) user_cli_path="${user_cli_path:+$user_cli_path:}$dir" ;;
        esac
    done
    child_path="${user_cli_path:+$user_cli_path:}${caller_path:-/usr/bin:/bin}"
fi

activate_child_path() {
    PATH="$child_path"
    export PATH
}

wrapper_pin_fail() {
    printf 'agent-bridge pinned deployment root mismatch: %s\n' "$1" >&2
    exit 1
}

if [ "${AGENT_BRIDGE_DEPLOY_ROOT+x}" = x ]; then
    pinned_root="$AGENT_BRIDGE_DEPLOY_ROOT"
    [ "$pinned_root" = "$wrapper_deploy_root" ] || wrapper_pin_fail deploy_root
    [ "${AGENT_BRIDGE_INSTALL_DIR-$pinned_root/bin}" = "$pinned_root/bin" ] ||
        wrapper_pin_fail install_dir
    [ "${AGENT_BRIDGE_REAL_BIN-$pinned_root/bin/agent-bridge.real}" = "$pinned_root/bin/agent-bridge.real" ] ||
        wrapper_pin_fail real_bin
    [ "${AGENT_BRIDGE_STATE_DIR-$pinned_root/runtime-state}" = "$pinned_root/runtime-state" ] ||
        wrapper_pin_fail state_dir
    [ "${AGENT_BRIDGE_CGROUP_RECEIPT_DIR-$pinned_root/runtime-state/workload-receipts}" = "$pinned_root/runtime-state/workload-receipts" ] ||
        wrapper_pin_fail receipt_dir
    [ "${AGENT_BRIDGE_CGROUP_TRANSIENT_DIR-$pinned_root/runtime-state/workload-tmp}" = "$pinned_root/runtime-state/workload-tmp" ] ||
        wrapper_pin_fail cgroup_transient_dir
    [ "${AGENT_BRIDGE_AUDIO_EMBODY_SCRIPT-$pinned_root/share/ab-tts/audio_embody.py}" = "$pinned_root/share/ab-tts/audio_embody.py" ] ||
        wrapper_pin_fail audio_script
    [ "${AGENT_BRIDGE_RUNTIME_ASSET_DIR-$pinned_root/lib/agent-bridge/scripts}" = "$pinned_root/lib/agent-bridge/scripts" ] ||
        wrapper_pin_fail runtime_assets
    [ "${AGENT_BRIDGE_MACHINE_ENV-$pinned_root/config/agent-bridge/machine.env}" = "$pinned_root/config/agent-bridge/machine.env" ] ||
        wrapper_pin_fail machine_env
    [ "${AGENT_BRIDGE_CREDS_FILE-$pinned_root/config/agent-bridge/credentials}" = "$pinned_root/config/agent-bridge/credentials" ] ||
        wrapper_pin_fail credentials
fi

# Secure-root invocations receive a private HOME/XDG namespace derived only
# from the executable root. This prevents a validated machine.env from
# accidentally expanding `$HOME` back onto a replaceable legacy mount. The
# publisher/systemd admission path creates and validates these directories.
if [ "$wrapper_secure_mode" = 1 ]; then
    export HOME="$wrapper_deploy_root/runtime-state/home"
    export XDG_CONFIG_HOME="$wrapper_deploy_root/config"
    export XDG_DATA_HOME="$wrapper_deploy_root/runtime-state/data"
    export XDG_CACHE_HOME="$wrapper_deploy_root/runtime-state/cache"
    export XDG_STATE_HOME="$wrapper_deploy_root/runtime-state/xdg-state"
    export TMPDIR="$wrapper_deploy_root/runtime-state/tmp"
    export AGENT_BRIDGE_CGROUP_TRANSIENT_DIR="$wrapper_deploy_root/runtime-state/workload-tmp"
fi

# Legacy ~/.local invocations retain their historical CLI discovery. A pinned
# trusted-root service must provision executable paths explicitly instead of
# inheriting tools from the unsafe HOME mount.
if [ "$wrapper_secure_mode" = 0 ] &&
        [ -z "${AGENT_BRIDGE_CLAUDE_BIN:-}" ] && [ -x "$HOME/.local/bin/claude" ]; then
    export AGENT_BRIDGE_CLAUDE_BIN="$HOME/.local/bin/claude"
fi

# Resident cognition is handled before the shared credential notebook. The
# provider receives only an ephemeral copy of Codex auth inside the Rust
# broker's outer read-only envelope, so loading unrelated service tokens into
# this parent adds no value. Parse only the three path keys Resident needs;
# never source or eval the owner-controlled machine file on this path.
resident_machine_value() {
    local key="$1"
    local raw="$2"
    local prefix
    case "$raw" in
        \"*\") raw="${raw#\"}"; raw="${raw%\"}" ;;
        \'*\') raw="${raw#\'}"; raw="${raw%\'}" ;;
    esac
    prefix='${'"$key"':-'
    case "$raw" in
        "$prefix"*'}') raw="${raw#"$prefix"}"; raw="${raw%\}}" ;;
    esac
    case "$raw" in
        /*) printf '%s' "$raw" ;;
    esac
}

load_resident_machine_paths() {
    local resident_machine_env="${AGENT_BRIDGE_MACHINE_ENV:-$default_machine_env}"
    local line key raw value
    [ -f "$resident_machine_env" ] || return 0
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            'export AGENT_BRIDGE_STATE_DIR='*) key="AGENT_BRIDGE_STATE_DIR" ;;
            'export AB_APP_CONTROL_OPERATION_DIR='*) key="AB_APP_CONTROL_OPERATION_DIR" ;;
            'export AB_RESIDENT_CODEX_BIN='*) key="AB_RESIDENT_CODEX_BIN" ;;
            *) continue ;;
        esac
        raw="${line#*=}"
        value="$(resident_machine_value "$key" "$raw")"
        [ -n "$value" ] || continue
        case "$key" in
            AGENT_BRIDGE_STATE_DIR)
                [ -n "${AGENT_BRIDGE_STATE_DIR:-}" ] || export AGENT_BRIDGE_STATE_DIR="$value"
                ;;
            AB_APP_CONTROL_OPERATION_DIR)
                [ -n "${AB_APP_CONTROL_OPERATION_DIR:-}" ] || export AB_APP_CONTROL_OPERATION_DIR="$value"
                ;;
            AB_RESIDENT_CODEX_BIN)
                [ -n "${AB_RESIDENT_CODEX_BIN:-}" ] || export AB_RESIDENT_CODEX_BIN="$value"
                ;;
        esac
    done < "$resident_machine_env"
}

if [ "${1:-}" = "resident" ]; then
    load_resident_machine_paths
    if [ -z "${AGENT_BRIDGE_STATE_DIR:-}" ] && [ -n "${AB_APP_CONTROL_OPERATION_DIR:-}" ]; then
        resident_app_control_state="${AB_APP_CONTROL_OPERATION_DIR%/}"
        case "$resident_app_control_state" in
            /*/app_control_operations)
                export AGENT_BRIDGE_STATE_DIR="${resident_app_control_state%/app_control_operations}"
                ;;
        esac
    fi
    if [ "$wrapper_secure_mode" = 0 ] && [ -z "${AB_RESIDENT_CODEX_BIN:-}" ]; then
        for resident_codex_candidate in \
            "$HOME"/.local/opt/node-*/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex
        do
            [ -f "$resident_codex_candidate" ] || continue
            export AB_RESIDENT_CODEX_BIN="$resident_codex_candidate"
            break
        done
    fi
    activate_child_path
    exec "$real_bin" "$@"
fi

if [ -f "$creds" ]; then
    # ----- Tailscale OAuth (Section: # Tailscale API) -----
    tailscale_id=$(awk '
        /^[[:space:]]*#[[:space:]]*Tailscale[[:space:]]*API/ { in_ts=1; next }
        in_ts && /^[[:space:]]*#/ && !/Tailscale/ { in_ts=0 }
        in_ts && /Client[[:space:]]*ID[[:space:]]*[:=]/ {
            sub(/.*[:=][[:space:]]*/, ""); print; exit
        }
    ' "$creds" 2>/dev/null || true)
    tailscale_secret=$(awk '
        /^[[:space:]]*#[[:space:]]*Tailscale[[:space:]]*API/ { in_ts=1; next }
        in_ts && /^[[:space:]]*#/ && !/Tailscale/ { in_ts=0 }
        in_ts && /Client[[:space:]]*secret[[:space:]]*[:=]/ {
            sub(/.*[:=][[:space:]]*/, ""); print; exit
        }
    ' "$creds" 2>/dev/null || true)
    [ -n "$tailscale_id" ] && export TAILSCALE_OAUTH_CLIENT_ID="$tailscale_id"
    [ -n "$tailscale_secret" ] && export TAILSCALE_OAUTH_CLIENT_SECRET="$tailscale_secret"

    # ----- GitHub PAT (Section: # Github PAT Token) -----
    github_pat=$(awk '
        /^[[:space:]]*#[[:space:]]*Github[[:space:]]*PAT/ { in_gh=1; next }
        in_gh && /^[[:space:]]*#/ { in_gh=0; next }
        in_gh && /^[[:space:]]*$/ { next }
        in_gh && /^[[:space:]]*(github_pat_|ghp_|gho_)/ {
            sub(/^[[:space:]]+/, ""); print; exit
        }
    ' "$creds" 2>/dev/null || true)
    [ -n "$github_pat" ] && export GITHUB_TOKEN="$github_pat"

    # ----- GitLab PAT (Section: # GitLab PAT token) -----
    gitlab_pat=$(awk '
        /^[[:space:]]*#[[:space:]]*GitLab[[:space:]]*PAT/ { in_gl=1; next }
        in_gl && /^[[:space:]]*#/ { in_gl=0; next }
        in_gl && /^[[:space:]]*$/ { next }
        in_gl && /^[[:space:]]*glpat-/ {
            sub(/^[[:space:]]+/, ""); print; exit
        }
    ' "$creds" 2>/dev/null || true)
    [ -n "$gitlab_pat" ] && export GITLAB_TOKEN="$gitlab_pat"

    # ----- Notion integration token (Section: # Notion API) -----
    notion_pat=$(awk '
        /^[[:space:]]*#[[:space:]]*Notion[[:space:]]*API/ { in_n=1; next }
        in_n && /^[[:space:]]*#/ { in_n=0; next }
        in_n && /^[[:space:]]*$/ { next }
        in_n && /^[[:space:]]*(ntn_|secret_)/ {
            sub(/^[[:space:]]+/, ""); print; exit
        }
    ' "$creds" 2>/dev/null || true)
    [ -n "$notion_pat" ] && export NOTION_TOKEN="$notion_pat"

    # ----- Brave Search subscription token (Section: # Brave Search API) -----
    brave_pat=$(awk '
        /^[[:space:]]*#[[:space:]]*Brave[[:space:]]*Search[[:space:]]*API/ { in_b=1; next }
        in_b && /^[[:space:]]*#/ { in_b=0; next }
        in_b && /^[[:space:]]*$/ { next }
        in_b && /^[[:space:]]*BSA/ {
            sub(/^[[:space:]]+/, ""); print; exit
        }
    ' "$creds" 2>/dev/null || true)
    [ -n "$brave_pat" ] && export BRAVE_SEARCH_TOKEN="$brave_pat"

    # ----- Cloudflare Workers API token (Subsection: ## Cloudflare Workers API) -----
    cf_token=$(awk '
        /^[[:space:]]*##[[:space:]]*Cloudflare[[:space:]]*Workers[[:space:]]*API/ { in_cf=1; next }
        in_cf && /^[[:space:]]*#/ { in_cf=0; next }
        in_cf && /^[[:space:]]*$/ { next }
        in_cf {
            sub(/^[[:space:]]+/, ""); split($0, a, /[[:space:]]+/); if (length(a[1]) >= 16) { print a[1]; exit }
        }
    ' "$creds" 2>/dev/null || true)
    [ -n "$cf_token" ] && export CLOUDFLARE_API_TOKEN="$cf_token"

    # ----- Cloudflare Account ID (Section: # Cloudflare endpoint, inline `ID：<value>`) -----
    cf_acct=$(awk '
        /^[[:space:]]*#[[:space:]]*Cloudflare[[:space:]]*endpoint/ { in_cfe=1; next }
        in_cfe && /^[[:space:]]*#/ { in_cfe=0 }
        in_cfe && match($0, /ID[：:][[:space:]]*[^[:space:]]+/) {
            v=substr($0, RSTART, RLENGTH); sub(/^ID[：:][[:space:]]*/, "", v); print v; exit
        }
    ' "$creds" 2>/dev/null || true)
    [ -n "$cf_acct" ] && export CLOUDFLARE_ACCOUNT_ID="$cf_acct"

    # ----- Anthropic API token + base URL -----
    # ONLY read from `# Agent-Bridge Primary` section in creds file.
    # Section terminator: blank line. Lets user switch active proxy without
    # touching this script.
    #
    # No "first match anywhere in file" fallback: ClaudeCode.txt has many
    # historical export ANTHROPIC_AUTH_TOKEN= lines (anyrouter, rainapp,
    # openrouter, etc.) that are dead long-term but stay in the file for
    # reference. A first-match fallback resurfaces them and breaks the
    # primary endpoint silently. If the Primary section is missing we leave
    # ANTHROPIC_* unset and let LlmClient go straight to the modelscope
    # OpenAI-compat fallback (commit 16c463b).
    anthropic_token=$(awk '
        /^[[:space:]]*#[[:space:]]*Agent-Bridge[[:space:]]+Primary/ { in_p=1; next }
        in_p && /^[[:space:]]*$/ { in_p=0 }
        in_p && /^[[:space:]]*export[[:space:]]+ANTHROPIC_AUTH_TOKEN[[:space:]]*=[[:space:]]*sk-/ {
            sub(/^[^=]*=[[:space:]]*/, "");
            gsub(/["'"'"']/, "");
            if (length($1) >= 20) { print $1; exit }
        }
    ' "$creds" 2>/dev/null || true)
    # Honor caller-set env (per-call overrides like
    # `ANTHROPIC_BASE_URL=… agent-bridge dream replay`).
    [ -z "${ANTHROPIC_AUTH_TOKEN:-}" ] && [ -n "$anthropic_token" ] && \
        export ANTHROPIC_AUTH_TOKEN="$anthropic_token"

    anthropic_base=$(awk '
        /^[[:space:]]*#[[:space:]]*Agent-Bridge[[:space:]]+Primary/ { in_p=1; next }
        in_p && /^[[:space:]]*$/ { in_p=0 }
        in_p && /^[[:space:]]*export[[:space:]]+ANTHROPIC_BASE_URL[[:space:]]*=[[:space:]]*https/ {
            sub(/^[^=]*=[[:space:]]*/, "");
            gsub(/["'"'"']/, "");
            print $1; exit
        }
    ' "$creds" 2>/dev/null || true)
    [ -z "${ANTHROPIC_BASE_URL:-}" ] && [ -n "$anthropic_base" ] && \
        export ANTHROPIC_BASE_URL="$anthropic_base"

    # ----- OpenAI-protocol fallback (Section: # Agent-Bridge Fallback) -----
    # When LlmClient (commit 16c463b) primary fails, it auto-retries via the
    # secondary built from these OPENAI_* vars. Honor pre-existing env so
    # callers can override per-call.
    openai_token=$(awk '
        /^[[:space:]]*#[[:space:]]*Agent-Bridge[[:space:]]+Fallback/ { in_f=1; next }
        in_f && /^[[:space:]]*$/ { in_f=0 }
        in_f && /^[[:space:]]*export[[:space:]]+OPENAI_API_KEY[[:space:]]*=/ {
            sub(/^[^=]*=[[:space:]]*/, "");
            gsub(/["'"'"']/, "");
            if (length($1) >= 16) { print $1; exit }
        }
    ' "$creds" 2>/dev/null || true)
    [ -z "${OPENAI_API_KEY:-}" ] && [ -n "$openai_token" ] && \
        export OPENAI_API_KEY="$openai_token"

    openai_base=$(awk '
        /^[[:space:]]*#[[:space:]]*Agent-Bridge[[:space:]]+Fallback/ { in_f=1; next }
        in_f && /^[[:space:]]*$/ { in_f=0 }
        in_f && /^[[:space:]]*export[[:space:]]+OPENAI_BASE_URL[[:space:]]*=[[:space:]]*https/ {
            sub(/^[^=]*=[[:space:]]*/, "");
            gsub(/["'"'"']/, "");
            print $1; exit
        }
    ' "$creds" 2>/dev/null || true)
    [ -z "${OPENAI_BASE_URL:-}" ] && [ -n "$openai_base" ] && \
        export OPENAI_BASE_URL="$openai_base"

    # Fallback model is distinct from primary model: claude-haiku → 404 on
    # OpenAI protocol; gpt-4o-mini → 400 on modelscope. LlmClient reads
    # AGENT_BRIDGE_LLM_FALLBACK_MODEL only on the secondary path.
    fallback_model=$(awk '
        /^[[:space:]]*#[[:space:]]*Agent-Bridge[[:space:]]+Fallback/ { in_f=1; next }
        in_f && /^[[:space:]]*$/ { in_f=0 }
        in_f && /^[[:space:]]*export[[:space:]]+AGENT_BRIDGE_LLM_FALLBACK_MODEL[[:space:]]*=/ {
            sub(/^[^=]*=[[:space:]]*/, "");
            gsub(/["'"'"']/, "");
            print $1; exit
        }
    ' "$creds" 2>/dev/null || true)
    [ -z "${AGENT_BRIDGE_LLM_FALLBACK_MODEL:-}" ] && [ -n "$fallback_model" ] && \
        export AGENT_BRIDGE_LLM_FALLBACK_MODEL="$fallback_model"
fi

# ----- Per-machine env overrides (per-host, NOT committed to the repo) -----
# A machine-local file sets host-specific env that must not live in the shared
# wrapper. Canonical use: AGENT_BRIDGE_CONTEXT_WINDOW=1000000 on a host running
# the 1M-context beta — a 200K host must NOT set it or context_pressure_estimate
# would UNDER-report fatigue (same opus-4.x id, two SKUs; see forum #1758).
# Sourced BEFORE the always-on defaults so its values act like per-host caller
# env: the guarded `${VAR:-}` exports below won't clobber them, yet a true
# per-call `VAR=… agent-bridge …` still wins — so write entries here with
# `export VAR="${VAR:-value}"` guards to preserve that precedence. Override the
# file path via AGENT_BRIDGE_MACHINE_ENV. See scripts/wrapper/machine.env.example.
machine_env="${AGENT_BRIDGE_MACHINE_ENV:-$default_machine_env}"
# A caller such as the bounded systemd deployment profile may pin the complete
# deployment and receipt identity. Preserve those explicit parent values even
# if the validated owner-controlled machine.env assigns the same names.
caller_deploy_root_set="${AGENT_BRIDGE_DEPLOY_ROOT+x}"
caller_deploy_root="${AGENT_BRIDGE_DEPLOY_ROOT-}"
caller_install_dir_set="${AGENT_BRIDGE_INSTALL_DIR+x}"
caller_install_dir="${AGENT_BRIDGE_INSTALL_DIR-}"
caller_real_bin_set="${AGENT_BRIDGE_REAL_BIN+x}"
caller_real_bin="${AGENT_BRIDGE_REAL_BIN-}"
caller_state_dir_set="${AGENT_BRIDGE_STATE_DIR+x}"
caller_state_dir="${AGENT_BRIDGE_STATE_DIR-}"
caller_receipt_dir_set="${AGENT_BRIDGE_CGROUP_RECEIPT_DIR+x}"
caller_receipt_dir="${AGENT_BRIDGE_CGROUP_RECEIPT_DIR-}"
caller_cgroup_transient_dir_set="${AGENT_BRIDGE_CGROUP_TRANSIENT_DIR+x}"
caller_cgroup_transient_dir="${AGENT_BRIDGE_CGROUP_TRANSIENT_DIR-}"
caller_audio_script_set="${AGENT_BRIDGE_AUDIO_EMBODY_SCRIPT+x}"
caller_audio_script="${AGENT_BRIDGE_AUDIO_EMBODY_SCRIPT-}"
caller_runtime_assets_set="${AGENT_BRIDGE_RUNTIME_ASSET_DIR+x}"
caller_runtime_assets="${AGENT_BRIDGE_RUNTIME_ASSET_DIR-}"
caller_machine_env_set="${AGENT_BRIDGE_MACHINE_ENV+x}"
caller_machine_env="${AGENT_BRIDGE_MACHINE_ENV-}"
caller_creds_file_set="${AGENT_BRIDGE_CREDS_FILE+x}"
caller_creds_file="${AGENT_BRIDGE_CREDS_FILE-}"
caller_home="$HOME"
caller_xdg_config_home="${XDG_CONFIG_HOME-}"
caller_xdg_data_home="${XDG_DATA_HOME-}"
caller_xdg_cache_home="${XDG_CACHE_HOME-}"
caller_xdg_state_home="${XDG_STATE_HOME-}"
caller_tmpdir="${TMPDIR-}"
caller_xdg_runtime_dir_set="${XDG_RUNTIME_DIR+x}"
caller_xdg_runtime_dir="${XDG_RUNTIME_DIR-}"
caller_dbus_address_set="${DBUS_SESSION_BUS_ADDRESS+x}"
caller_dbus_address="${DBUS_SESSION_BUS_ADDRESS-}"
# shellcheck source=/dev/null
[ -f "$machine_env" ] && . "$machine_env"
[ -z "$caller_deploy_root_set" ] || export AGENT_BRIDGE_DEPLOY_ROOT="$caller_deploy_root"
[ -z "$caller_install_dir_set" ] || export AGENT_BRIDGE_INSTALL_DIR="$caller_install_dir"
[ -z "$caller_real_bin_set" ] || export AGENT_BRIDGE_REAL_BIN="$caller_real_bin"
[ -z "$caller_state_dir_set" ] || export AGENT_BRIDGE_STATE_DIR="$caller_state_dir"
[ -z "$caller_receipt_dir_set" ] || export AGENT_BRIDGE_CGROUP_RECEIPT_DIR="$caller_receipt_dir"
[ -z "$caller_cgroup_transient_dir_set" ] || export AGENT_BRIDGE_CGROUP_TRANSIENT_DIR="$caller_cgroup_transient_dir"
[ -z "$caller_audio_script_set" ] || export AGENT_BRIDGE_AUDIO_EMBODY_SCRIPT="$caller_audio_script"
[ -z "$caller_runtime_assets_set" ] || export AGENT_BRIDGE_RUNTIME_ASSET_DIR="$caller_runtime_assets"
[ -z "$caller_machine_env_set" ] || export AGENT_BRIDGE_MACHINE_ENV="$caller_machine_env"
[ -z "$caller_creds_file_set" ] || export AGENT_BRIDGE_CREDS_FILE="$caller_creds_file"
if [ "$wrapper_secure_mode" = 1 ]; then
    export HOME="$caller_home"
    export XDG_CONFIG_HOME="$caller_xdg_config_home"
    export XDG_DATA_HOME="$caller_xdg_data_home"
    export XDG_CACHE_HOME="$caller_xdg_cache_home"
    export XDG_STATE_HOME="$caller_xdg_state_home"
    export TMPDIR="$caller_tmpdir"
    [ -z "$caller_xdg_runtime_dir_set" ] || export XDG_RUNTIME_DIR="$caller_xdg_runtime_dir"
    [ -z "$caller_dbus_address_set" ] || export DBUS_SESSION_BUS_ADDRESS="$caller_dbus_address"
fi
unset LD_PRELOAD LD_LIBRARY_PATH LD_AUDIT LD_DEBUG LD_PROFILE GCONV_PATH \
    LOCPATH NLSPATH BASH_ENV ENV PYTHONPATH PYTHONHOME PERL5LIB RUBYLIB \
    NODE_OPTIONS NODE_PATH RUSTC_WRAPPER 2>/dev/null || true

# Use one host-local, permission-capable root for durable AB journals. Existing
# installations may only declare the older app-control journal location; when
# it has the canonical leaf name, safely derive the common parent without
# hard-coding a host path. A caller or machine.env can always set the common
# root explicitly and takes precedence.
if [ -z "${AGENT_BRIDGE_STATE_DIR:-}" ] && [ -n "${AB_APP_CONTROL_OPERATION_DIR:-}" ]; then
    app_control_state="${AB_APP_CONTROL_OPERATION_DIR%/}"
    case "$app_control_state" in
        /*/app_control_operations)
            export AGENT_BRIDGE_STATE_DIR="${app_control_state%/app_control_operations}"
            ;;
    esac
fi

# Always-on flags
export AGENT_BRIDGE_TOOL_PROFILE="${AGENT_BRIDGE_TOOL_PROFILE:-all}"
# Deploys install this adapter from the same repository revision as
# agent-bridge.real. A caller may still override it explicitly for an
# alternate checkout or test fixture.
export AGENT_BRIDGE_AUDIO_EMBODY_SCRIPT="${AGENT_BRIDGE_AUDIO_EMBODY_SCRIPT:-$wrapper_deploy_root/share/ab-tts/audio_embody.py}"
export AGENT_BRIDGE_RUNTIME_ASSET_DIR="${AGENT_BRIDGE_RUNTIME_ASSET_DIR:-$wrapper_deploy_root/lib/agent-bridge/scripts}"

# v22 Phase 2.4 — α-α SVD warm-start projection defaults.
# When AB_SUBSTRATE is opted in (manually or by future wrapper change),
# every wrapper-launched process auto-picks SVD instead of bucket-pool.
# We deliberately do NOT default AB_SUBSTRATE: substrate install pays
# NeuronGrid init (~1ms) per process, and short-lived dream/sync calls
# don't need it. Both vars use `${VAR:-}` guard so per-call overrides
# (`AB_SUBSTRATE_PROJECTION=bucket_pool agent-bridge ...`) keep working.
#
# Path resolves to the aio2 artifact location. Mac / hosts without the
# AiOT checkout silently hit `load_svd` IO error and the resolver falls
# back to bucket-pool via tracing::warn — no panic, no behavior change
# vs Phase 1. Cross-machine artifact distribution is AiOT memo §6 Open
# Q #3 follow-up (forum #6).
export AB_SUBSTRATE_PROJECTION="${AB_SUBSTRATE_PROJECTION:-svd}"
export AB_SUBSTRATE_SVD_PATH="${AB_SUBSTRATE_SVD_PATH:-/Data/CascadeProjects/AiOT/build/svd_projection_v1.bin}"

# Track MS — sync node identity for memory version-vector stamping. Every
# wrapper-launched process (MCP server, CLI, daemon, sync) stamps memory writes
# with this machine's name so the cross-machine conflict-aware merge
# (ImportConflictPolicy::VersionVectorMerge) can tell aio2 edits from mac edits.
# `SqliteStore::open` reads this via `node_id_from_env`; unset → no stamping →
# safe NewerWins fallback. `${VAR:-}` guard keeps per-call overrides working.
export AB_SYNC_NODE="${AB_SYNC_NODE:-$(hostname -s 2>/dev/null || hostname 2>/dev/null || echo unknown)}"

activate_child_path
exec "$real_bin" "$@"
