#!/usr/bin/env bash
# agent-bridge wrapper — injects environment variables from a credentials
# file before exec'ing the real binary.
#
# Why this exists: some MCP clients (Antigravity Claude, certain IDE
# integrations) silently drop the .claude.json `env` block when launching
# stdio-based MCP servers. Without this wrapper, the agent-bridge daemon
# starts with an empty token environment and tool calls (Anthropic API,
# GitHub PAT, Tailscale OAuth, etc.) fail.
#
# Layout: this wrapper is installed at $HOME/.local/bin/agent-bridge and
# exec's the real binary at $HOME/.local/bin/agent-bridge.real. The
# credentials file is plain text with named sections (see creds.example
# in this directory).
#
# Override paths via env:
#   AGENT_BRIDGE_CREDS_FILE  — credentials file path (default below)
#   AGENT_BRIDGE_REAL_BIN    — real binary path (default ~/.local/bin/agent-bridge.real)

set -euo pipefail

# Default creds path — adjust per-host or override via AGENT_BRIDGE_CREDS_FILE.
# Common locations: ~/Documents/ClaudeCode.txt, /Media/Ubuntu/Documents/ClaudeCode.txt
default_creds="${HOME}/Documents/ClaudeCode.txt"
[ -f "/Media/Ubuntu/Documents/ClaudeCode.txt" ] && default_creds="/Media/Ubuntu/Documents/ClaudeCode.txt"
creds="${AGENT_BRIDGE_CREDS_FILE:-$default_creds}"

real_bin="${AGENT_BRIDGE_REAL_BIN:-$HOME/.local/bin/agent-bridge.real}"

# MCP/IDE launchers often provide a minimal PATH. Keep user-installed CLIs
# visible for tools such as agent_spawn without requiring every client config
# to duplicate shell rc setup.
user_cli_path=""
for dir in "$HOME/.local/bin" "$HOME/.npm-global/bin" "$HOME/.cargo/bin"; do
    [ -d "$dir" ] || continue
    case ":${PATH:-}:" in
        *":$dir:"*) ;;
        *) user_cli_path="${user_cli_path:+$user_cli_path:}$dir" ;;
    esac
done
if [ -n "$user_cli_path" ]; then
    export PATH="$user_cli_path${PATH:+:$PATH}"
else
    export PATH="${PATH:-}"
fi

if [ -z "${AGENT_BRIDGE_CLAUDE_BIN:-}" ] && [ -x "$HOME/.local/bin/claude" ]; then
    export AGENT_BRIDGE_CLAUDE_BIN="$HOME/.local/bin/claude"
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
machine_env="${AGENT_BRIDGE_MACHINE_ENV:-$HOME/.config/agent-bridge/machine.env}"
# shellcheck source=/dev/null
[ -f "$machine_env" ] && . "$machine_env"

# Always-on flags
export AGENT_BRIDGE_TOOL_PROFILE="${AGENT_BRIDGE_TOOL_PROFILE:-all}"

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

exec "$real_bin" "$@"
