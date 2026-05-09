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
    # Preferred: read from `# Agent-Bridge Primary` section in creds file
    # (lets user switch active proxy without touching this script).
    # Section terminator: blank line.
    # Fallback: first `export ANTHROPIC_AUTH_TOKEN=sk-…` anywhere in file.
    anthropic_token=$(awk '
        /^[[:space:]]*#[[:space:]]*Agent-Bridge[[:space:]]+Primary/ { in_p=1; next }
        in_p && /^[[:space:]]*$/ { in_p=0 }
        in_p && /^[[:space:]]*export[[:space:]]+ANTHROPIC_AUTH_TOKEN[[:space:]]*=[[:space:]]*sk-/ {
            sub(/^[^=]*=[[:space:]]*/, "");
            gsub(/["'"'"']/, "");
            if (length($1) >= 20) { print $1; exit }
        }
    ' "$creds" 2>/dev/null || true)
    [ -z "$anthropic_token" ] && anthropic_token=$(awk '
        /^[[:space:]]*export[[:space:]]+ANTHROPIC_AUTH_TOKEN[[:space:]]*=[[:space:]]*sk-/ {
            sub(/^[^=]*=[[:space:]]*/, "");
            gsub(/["'"'"']/, "");
            if (length($1) >= 20) { print $1; exit }
        }
    ' "$creds" 2>/dev/null || true)
    # Only fall back to creds-file value when caller hasn't set anything.
    # Respects per-call overrides: `ANTHROPIC_BASE_URL=… agent-bridge dream replay`.
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
    [ -z "$anthropic_base" ] && anthropic_base=$(awk '
        /^[[:space:]]*export[[:space:]]+ANTHROPIC_BASE_URL[[:space:]]*=[[:space:]]*https/ {
            sub(/^[^=]*=[[:space:]]*/, "");
            gsub(/["'"'"']/, "");
            print $1; exit
        }
    ' "$creds" 2>/dev/null || true)
    [ -z "${ANTHROPIC_BASE_URL:-}" ] && [ -n "$anthropic_base" ] && \
        export ANTHROPIC_BASE_URL="$anthropic_base"
fi

# Always-on flags
export AGENT_BRIDGE_TOOL_PROFILE="${AGENT_BRIDGE_TOOL_PROFILE:-all}"

exec "$real_bin" "$@"
