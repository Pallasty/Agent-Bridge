# agent-bridge

[![CI](https://github.com/pallasting/Agent-Bridge/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/pallasting/Agent-Bridge/actions/workflows/ci.yml)
[![Verify Warp Integration](https://github.com/pallasting/Agent-Bridge/actions/workflows/verify-warp-integration.yml/badge.svg?branch=master)](https://github.com/pallasting/Agent-Bridge/actions/workflows/verify-warp-integration.yml)

A Unix-native AI-agent control plane: desktop notifications, cross-session memory,
MCP tool registry, terminal multiplexer glue, browser automation (CDP), git-worktree
orchestration, and sub-agent spawning — all pluggable via Rust traits.

## Install

agent-bridge is distributed as **source only** — there are no prebuilt
binaries or release tarballs. The code is published to two forges; either
works as your install source:

- GitHub: `https://github.com/pallasting/Agent-Bridge`
- GitLab: `https://gitlab.com/pallasting/agent-bridge`

### Version provenance

`v*` tags are source release markers. The Cargo workspace package version tracks
the latest released baseline; unreleased source builds add `git describe` and a
short source SHA to CLI/capability output. Pin installations to a Git commit
when exact provenance matters. Run `scripts/agent-bridge-release-truth-gate.py`
to inspect the current state; choosing a new version or tag remains an explicit
owner release decision. `scripts/agent-bridge-release-candidate-audit.py`
profiles the post-tag change set, format debt, and clean-worktree evidence; it
recommends a candidate version but never writes one or creates a tag.

You need a Rust toolchain ([rustup](https://rustup.rs)) and a working C
linker; no system libraries otherwise (`zbus` and `rusqlite` with the
bundled feature are pure Rust).

### `cargo install --git` (recommended)

```bash
cargo install --git https://github.com/pallasting/Agent-Bridge.git --bin agent-bridge
# or from GitLab:
cargo install --git https://gitlab.com/pallasting/agent-bridge.git --bin agent-bridge
```

Cold compile ≈ 2–3 min on a modern laptop. Builds with default features,
including the local ONNX sentence-transformer embedding backend. Then jump
to **[Configure](#configure)**.

### Source build (for hacking on agent-bridge itself)

```bash
git clone https://github.com/pallasting/Agent-Bridge.git ~/agent-bridge
# or: git clone git@gitlab.com:pallasting/agent-bridge.git ~/agent-bridge
cd ~/agent-bridge && cargo build --release
```

Incremental rebuilds < 15 s. The binary lands at
`target/release/agent-bridge`. Then jump to **[Configure](#configure)**.

> **Lower-footprint build:** add `--no-default-features` to drop the ONNX
> embedding backend and use the built-in 384-dim hash-only backend —
> a ~3× smaller binary with no model download. Memory and embedding APIs
> work identically; semantic search quality is lower.

> **Windows users:** Linux + macOS only. Run agent-bridge inside WSL2
> (Ubuntu) — there is no native Windows build yet. See `docs/` for the
> Windows port roadmap.

## Configure

These steps are the same regardless of how you got the binary above.

```bash
# 1. Install hooks (Claude Code) and register MCP config.
agent-bridge setup --frontend claude-code
# (or --frontend codex / codex-cli / codex-ide / gemini-cli / warp / auggie / local-cli / auto)

# 2. Make sure ~/.local/bin is on PATH.
fish_add_path ~/.local/bin
# bash/zsh: export PATH="$HOME/.local/bin:$PATH"

# 3. Start the long-lived daemon.
agent-bridge daemon &

# 4. Register as an MCP server (Claude Code only — other frontends were
#    auto-configured in step 1). `-s user` registers it at user scope so the
#    server is reachable from any directory; without it the default is
#    project scope and the server is invisible when Claude Code starts from $HOME.
claude mcp add -s user agent-bridge agent-bridge mcp

# 5. (Optional) Bootstrap cross-device memory sync via GitHub. Creates
#    (or reuses) a private `<your-user>/agent-bridge-memory` repo, clones
#    it next to state.db, and runs the first sync. Subsequent syncs are
#    automatic — the Stop hook calls `agent-bridge sync` at session end.
gh auth login            # one-time; HTTPS token, no SSH keys needed
agent-bridge sync init

# 6. Restart Claude Code — hooks fire automatically from here on.
```

That's it. Claude Code now has persistent cross-session memory, automatic
compaction, and git-backed sync to any other machine running agent-bridge.

### Memory sync — what it does

`agent-bridge sync` is one idempotent round of:

1. `git pull --rebase --autostash` on the memory repo,
2. `memory_import` (newer-wins) from `memory.jsonl` into the local SQLite store,
3. `memory_export` of the local store back into `memory.jsonl`,
4. `git add` + commit + push if anything changed.

Run it manually any time, or let the Stop hook call it at session end.
Other useful subcommands:

- `agent-bridge sync init [--repo <name>]` — bootstrap via `gh` CLI
- `agent-bridge sync status` — print resolved repo path, remote, last commit

The repo location is resolved in this order: `AGENT_BRIDGE_MEMORY_REPO` env →
legacy `~/agent-bridge-memory` or `~/Projects/agent-bridge-memory` (if they
have a `.git`) → `<state-dir>/memory-sync` next to `state.db` (the new default).

### Skill library indexer

`agent-bridge skills` indexes third-party open-source Claude Code skill
repos into the local memory store, so you can search across them and
pick a skill on demand. It walks `**/SKILL.md`, `.claude/skills/*.md`,
and `skills/*.md`, parses YAML frontmatter, and runs a heuristic safety
lint (`pipe-to-shell`, `dangerous-rm`, `creds-path`, `eval-substitution`).

### Sway workstation runbook

For the local Sway workstation integration covering keyboard hotkeys, Wi-Fi
status-bar actions, display power policy, desktop doctor/heal/watchdog, and
status snapshot diagnostics, see
[`docs/SWAY-WORKSTATION-RUNBOOK.md`](docs/SWAY-WORKSTATION-RUNBOOK.md).
Lint findings are surfaced — they do **not** mean a skill is unsafe,
just that it warrants manual review before installing.

```bash
# Bootstrap with the curated 8-repo seed corpus (anthropics/skills + community libs).
agent-bridge skills seed

# Or index a specific repo:
agent-bridge skills index https://github.com/anthropics/skills

# Search across everything indexed so far.
agent-bridge skills search "review pdf document"

# List recent / show one.
agent-bridge skills list --limit 20
agent-bridge skills show skill:anthropics/skills/pdf

# Install one — re-clones source, copies SKILL.md plus any sibling
# scripts/data into ~/.claude/skills/<name>/. Lint warnings require --yes.
agent-bridge skills install skill:anthropics/skills/pdf --yes
```

Indexed skills are stored as memory records (`kind=skill`) and persist
across `state.db` sessions; running `index` again upserts by key.

The MCP tool `skills_recommend(query, limit)` exposes the same retrieval
to agents in-loop — when an agent describes a task ("audit a Helm chart",
"edit a PDF form"), it can call `skills_recommend` first and surface
matching pre-written skills with their lint status and install command,
instead of writing instructions from scratch.

### Wrapper for env injection (optional)

Some MCP clients (Antigravity Claude, certain IDE integrations) silently
drop the `.claude.json` `env` block when launching stdio MCP servers. Without
that env, the daemon starts with no API tokens and tool calls (Anthropic,
GitHub, Tailscale, …) fail. The fix is a thin shell wrapper at
`~/.local/bin/agent-bridge` that reads a credentials file and injects the
tokens before exec'ing the real binary at `~/.local/bin/agent-bridge.real`.

```bash
# Install (or upgrade) the wrapper. Idempotent; moves the existing binary
# to .real on first run, replaces the wrapper template on subsequent runs.
scripts/wrapper/install.sh

# First-time setup also needs a credentials file.
cp scripts/wrapper/creds.example ~/Documents/ClaudeCode.txt
$EDITOR ~/Documents/ClaudeCode.txt   # replace REPLACE_ME placeholders

# To remove and restore the plain binary:
scripts/wrapper/install.sh --uninstall
```

The credentials file is plain text with `# <SECTION>` markers. Two sections
are wired into the memory-layer LLM path:

- `# Agent-Bridge Primary` — Anthropic proxy (token + base URL). Active for
  P4b filter / P5 dream replay / dogfood loops.
- `# Agent-Bridge Fallback` — OpenAI-protocol secondary (token + base URL +
  fallback model). When the primary fails (network blip, quota, outage),
  the in-process `LlmClient` retries once via this provider. Optional —
  omit if you want strict single-provider semantics.

Switch proxies by editing those `export` lines, no script edit needed. See
`scripts/wrapper/creds.example` for the full layout.

Override paths via env: `AGENT_BRIDGE_CREDS_FILE`, `AGENT_BRIDGE_REAL_BIN`,
`AGENT_BRIDGE_INSTALL_DIR`.

---

## Quick start (Codex)

OpenAI Codex is supported as a first-class frontend. The MCP server uses
stdio and is registered in `~/.codex/config.toml`; Codex reloads that
configuration when a new session starts.

```bash
# 1. Build (same as above)
git clone git@gitlab.com:pallasting/agent-bridge.git ~/agent-bridge
cd ~/agent-bridge && cargo build --release

# 2. Install — Codex desktop profile copies the binary and merges MCP + hook config.
./target/release/agent-bridge setup --frontend codex
# For non-desktop hosts, use --frontend codex-cli or --frontend codex-ide.
# (Or rely on auto-detect when ~/.codex/config.toml exists:
#   ./target/release/agent-bridge setup)

# 3. Restart Codex or open a new Codex session.
```

The Codex desktop profile writes this MCP server entry:

```toml
[mcp_servers.agent-bridge]
command = "/home/you/.local/bin/agent-bridge"
args = ["mcp"]
enabled = true
startup_timeout_sec = 20
tool_timeout_sec = 300
supports_parallel_tool_calls = false

[mcp_servers.agent-bridge.env]
AGENT_BRIDGE_CLIENT = "codex"
AGENT_BRIDGE_TOOLSET = "codex-essential"
AGENT_BRIDGE_TOOL_PROFILE = "essential"
AGENT_BRIDGE_CODEX_HOST = "desktop"
```

The command path is written as the expanded absolute path on your
machine, for example `/Users/pallasting/.local/bin/agent-bridge` on
macOS.

`supports_parallel_tool_calls` is deliberately false because
agent-bridge tools share SQLite, browser, and terminal state.
The Codex profile defaults `AGENT_BRIDGE_TOOLSET` to `codex-essential`
so GPT/Codex sees a compact high-signal tool surface while still keeping
the IDE bridge tools (`ide_snapshot`, `ide_command`) available. For other
client shapes, set `AGENT_BRIDGE_TOOLSET` to `claude-standard`,
`gemini-lean`, `hook-lifecycle`, or `all-dev`. The older
`AGENT_BRIDGE_TOOL_PROFILE` setting is still supported as the compatibility
fallback.

The Codex profile also enables `features.hooks`, writes the three
`ab-*-hook` scripts to `~/.local/bin`, and merges Agent-Bridge entries
into `~/.codex/hooks.json` while preserving existing hooks. If Codex asks
you to trust the new hook commands after setup, approve the Agent-Bridge
entries.

Codex host variants share the same compact `codex-essential` toolset but mark
their host explicitly:

| Frontend | Host env | Hooks | Intended use |
|----------|----------|-------|--------------|
| `codex` | `AGENT_BRIDGE_CODEX_HOST=desktop` | yes | Codex desktop app with lifecycle hooks |
| `codex-cli` | `AGENT_BRIDGE_CODEX_HOST=cli` | no | Codex CLI or CLI-like MCP host |
| `codex-ide` | `AGENT_BRIDGE_CODEX_HOST=ide` | no | IDE-hosted Codex plus the file-based IDE snapshot bridge |

| Codex lifecycle moment | Agent-Bridge hook |
|------------------------|-------------------|
| First prompt submit | `ab-memory-hook` injects a compact memory primer once per session |
| `/compact` / context compaction | `ab-precompact-hook` reads Codex JSONL and calls `session_lifecycle_step(precompact)` |
| Stop | `ab-session-end-hook` compacts stale memories and syncs |
| SessionEnd | `ab-session-end-hook` first runs the transcript curator, then compacts and syncs |

---

## Quick start (local CLI clients)

agent-bridge is a stdio MCP server, so any local CLI client that can
spawn an MCP server command can use the same binary:

```bash
cargo build --release

# Register with local stdio-capable CLI clients in one pass:
# - Codex      → ~/.codex/config.toml
# - Gemini CLI → ~/.gemini/settings.json
# - Claude Code best effort via `claude mcp add`
./target/release/agent-bridge setup --frontend local-cli
```

You can also target one client explicitly:

```bash
./target/release/agent-bridge setup --frontend codex
./target/release/agent-bridge setup --frontend codex-cli
./target/release/agent-bridge setup --frontend codex-ide
./target/release/agent-bridge setup --frontend gemini-cli
./target/release/agent-bridge setup --frontend claude-code
```

Gemini CLI uses this JSON shape in `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "agent-bridge": {
      "command": "/home/you/.local/bin/agent-bridge",
      "args": ["mcp"],
      "env": {
        "AGENT_BRIDGE_CLIENT": "gemini",
        "AGENT_BRIDGE_TOOLSET": "gemini-lean",
        "AGENT_BRIDGE_TOOL_PROFILE": "essential"
      }
    }
  }
}
```

Claude Code registration uses `AGENT_BRIDGE_TOOLSET=claude-standard`;
Gemini CLI uses `AGENT_BRIDGE_TOOLSET=gemini-lean`.

Claude Code and Codex have automatic lifecycle hook installation. Gemini
CLI, Warp, and Auggie should use the lifecycle MCP tools directly:
`session_bootstrap`, `session_curate`, and `session_finalize`.

Read-only avatar/presence surfaces are also available without going through
an MCP client. The terminal report uses the same projection as the Standard
MCP `avatar_surface_report` tool:

```bash
agent-bridge avatar surface --project agent-bridge --include-stale
agent-bridge avatar surface --project agent-bridge --role dogfood --json
```

---

## Quick start (Warp)

[Warp](https://www.warp.dev) is supported as a first-class frontend. The
flow differs from Claude Code in two ways: there is no shell-out hook
model, and Warp registers MCP servers via its settings UI rather than a
`claude mcp add` CLI.

```bash
# 1. Build (same as above)
git clone git@gitlab.com:pallasting/agent-bridge.git ~/agent-bridge
cd ~/agent-bridge && cargo build --release

# 2. Install — Warp profile copies the binary only and prints UI guidance.
./target/release/agent-bridge setup --frontend warp
# (Or rely on auto-detect when running this from inside a Warp shell:
#   ./target/release/agent-bridge setup)

# 3. Add to PATH
export PATH="$HOME/.local/bin:$PATH"
```

Then in Warp itself:

1. Open **Settings → MCP servers → Add server**.
2. Set **Command** = `~/.local/bin/agent-bridge`, **Args** = `["mcp"]`.
3. Save and reload.

That's the whole adaptation surface. Warp does not have analogues for
the Claude Code `UserPromptSubmit / Stop / PreCompact` hook events, so
the `setup --frontend warp` profile deliberately skips writing the
three `ab-*-hook` scripts and the `~/.claude/settings.json` rewrite.
Instead, the agent should call the equivalent MCP tools directly:

| Lifecycle moment | What to call instead of a hook |
|------------------|--------------------------------|
| Session start    | Read `agent-bridge://session/bootstrap` resource, or call `session_bootstrap` |
| Before summarising / compacting context | `session_curate(conversation_text=...)` |
| Session end      | `session_finalize()` |

The `session_bootstrap` and `capabilities` tools auto-detect Warp via
`TERM_PROGRAM=WarpTerminal` / `WARP_IS_LOCAL_SHELL_SESSION=1` and emit
a compact, Block-UI-friendly format.

---

## What `setup` does

`agent-bridge setup` is idempotent and safe to re-run after upgrades.
The `--frontend` flag selects the install profile (default: `auto`,
which detects Warp, Codex, Gemini CLI, then Auggie before falling back
to claude-code).

Preview setup without touching local config:

```bash
agent-bridge setup --frontend codex --dry-run
agent-bridge setup --frontend codex --dry-run --json
```

The JSON form emits `agent_bridge_setup_plan.v0`: the binary target, frontend,
toolset, planned file writes, best-effort client CLI registrations, and a
plan-only install-state note. It is intentionally read-only and does not write
`setup-state.json`.

After a successful non-dry-run setup, Agent-Bridge writes
`agent_bridge_setup_state.v0` to the Agent-Bridge data directory:

- Linux: `$XDG_DATA_HOME/agent-bridge/setup-state.json`, or
  `~/.local/share/agent-bridge/setup-state.json`
- macOS: `~/Library/Application Support/agent-bridge/setup-state.json`

The state file records the applied frontend, toolset, MCP command, binary
target, operation list, and applied timestamp. Best-effort client CLI
registrations are still worth manually verifying in the target client.

Claude Code profile (`--frontend claude-code`):

| Step | What happens |
|------|-------------|
| Binary | Copies itself to `~/.local/bin/agent-bridge` |
| Hook scripts | Writes three scripts to `~/.local/bin/` (see below) |
| Curator settings | Writes `~/.config/agent-bridge/memory-curator-settings.json` |
| Claude Code hooks | Merges three hook entries into `~/.claude/settings.json` (never overwrites existing entries) |

Warp profile (`--frontend warp`):

| Step | What happens |
|------|-------------|
| Binary | Copies itself to `~/.local/bin/agent-bridge` |
| Hook scripts | **Skipped** — Warp has no equivalent hook events |
| Curator settings | **Skipped** — only consumed by `ab-precompact-hook.sh` |
| Settings file | **Skipped** — prints registration guidance for `Settings → MCP servers` instead |

Codex desktop profile (`--frontend codex`):

| Step | What happens |
|------|-------------|
| Binary | Copies itself to `~/.local/bin/agent-bridge` |
| Hook scripts | Writes three scripts to `~/.local/bin/` |
| Codex hooks | Enables `features.hooks` and merges Agent-Bridge entries into `~/.codex/hooks.json` |
| Settings file | Merges `[mcp_servers.agent-bridge]` into `~/.codex/config.toml` with `AGENT_BRIDGE_CLIENT=codex`, `AGENT_BRIDGE_TOOLSET=codex-essential`, `AGENT_BRIDGE_TOOL_PROFILE=essential`, and `AGENT_BRIDGE_CODEX_HOST=desktop`; snapshots Codex `model` / `model_reasoning_effort` into `AGENT_BRIDGE_MODEL` / `AGENT_BRIDGE_MODEL_REASONING_EFFORT` when present |

Codex CLI and IDE profiles (`--frontend codex-cli` / `--frontend codex-ide`)
write the same MCP entry with `AGENT_BRIDGE_CODEX_HOST=cli` or `ide`, but skip
desktop lifecycle hooks.

Gemini CLI profile (`--frontend gemini-cli`):

| Step | What happens |
|------|-------------|
| Binary | Copies itself to `~/.local/bin/agent-bridge` |
| Hook scripts | **Skipped** — Gemini CLI has no equivalent hook events |
| Curator settings | **Skipped** — only consumed by `ab-precompact-hook.sh` |
| Settings file | Merges `mcpServers.agent-bridge` into `~/.gemini/settings.json` with `AGENT_BRIDGE_TOOLSET=gemini-lean` |

Local CLI profile (`--frontend local-cli`):

| Step | What happens |
|------|-------------|
| Binary | Copies itself to `~/.local/bin/agent-bridge` |
| Codex | Merges `[mcp_servers.agent-bridge]` into `~/.codex/config.toml` |
| Gemini CLI | Merges `mcpServers.agent-bridge` into `~/.gemini/settings.json` with `AGENT_BRIDGE_TOOLSET=gemini-lean` |
| Claude Code | Best-effort `claude mcp add -s user` with `AGENT_BRIDGE_TOOLSET=claude-standard`; prints the manual command if unavailable |

### Hook scripts

| Script | Hook events | Purpose |
|--------|-------------|---------|
| `ab-memory-hook` | `UserPromptSubmit` | Inject scope-aware memory index at session start (once per session) |
| `ab-precompact-hook` | `PreCompact` (manual + auto) | Reads Claude/Cursor/Codex transcript JSONL, calls `session_lifecycle_step(precompact)` over MCP (runs `session_curate` then `session_finalize`; no sub-agent) |
| `ab-session-end-hook` | `Stop`, Codex `SessionEnd` | Compact memories older than 90 days; sync to git remote. On Codex `SessionEnd`, first runs the transcript curator. |

Hook-spawned MCP children use `AGENT_BRIDGE_TOOLSET=hook-lifecycle`,
which exposes only lifecycle-safe memory/session/pet-state tools instead
of the full developer registry.

### Memory lifecycle

```
Session start  ──► ab-memory-hook injects relevant memories into context
     │
     ▼
  conversation  ──► Claude calls memory_save / memory_link at will
     │
     ▼
/compact or     ──► ab-precompact-hook runs transcript → MCP
context full         └─► session_lifecycle_step(precompact) → curate + finalize
     │
     ▼
Session end     ──► ab-session-end-hook compacts stale + syncs to git
```

### Tuning `session_curate` (Pass-2 implicit extraction)

Pass-2 uses a score threshold and Jaccard deduplication. You can tune them in three ways (last wins per call: **MCP tool arguments** override **environment** for that request; the bridge still applies built-in clamps).

| Mechanism | Variables / fields |
|-----------|-------------------|
| Environment (stdio MCP process or shell that launches `agent-bridge`) | `AGENT_BRIDGE_CURATE_SCORE_THRESHOLD` (float, clamped 0.15–0.95), `AGENT_BRIDGE_CURATE_DEDUP_JACCARD` (float, clamped 0.1–0.95) |
| MCP `session_curate` arguments (optional) | `implicit_score_threshold`, `implicit_dedup_jaccard` — same semantics; override env for that call |
| Preview | `dry_run: true` — response JSON includes `candidates` and **`options`** (resolved thresholds used) |

Current `ab-precompact-hook` default profile (applied via MCP args): `implicit_score_threshold=0.50`, `implicit_dedup_jaccard=0.58`.

After upgrading or changing Cursor/Warp MCP settings, smoke-test the stdio server:

```bash
./scripts/verify_session_curate.sh
```

Requires `agent-bridge` on `PATH` or `~/.local/bin/agent-bridge`.

For W8 integration coverage (Warp-first roadmap), run:

```bash
./scripts/verify_warp_integration.sh
```

This validates end-to-end MCP calls for `capabilities`, lifecycle bootstrap,
`project_detect`, `changes_digest`, `session_handoff`, plan persistence,
`warp_status`, and `agent_message`/`agent_inbox`.

For Warp IPC + `terminal_read_output` path validation (MCP-level E2E with a
local Unix-socket stub), run:

```bash
./scripts/verify_warp_terminal_read_output_e2e.sh
```

This asserts `capabilities.terminal.can_read_output=true` when the Warp IPC
socket is available, and verifies `terminal_list` + `terminal_read_output`
through the full stdio MCP server path.

For profile tuning/regression on a real session transcript, run:

```bash
./scripts/compare_session_curate_profiles.sh --transcript /path/to/session.jsonl
```

This compares `baseline / balanced / strict / aggressive` profiles on the same
input, printing candidate counts, kind distributions, and sample diffs vs baseline.

After registering local CLI clients, ask any connected agent to call
`mcp_config_audit`. It checks Codex, Gemini CLI, and Claude Code MCP config,
client-reported connection status, and a direct stdio initialize smoke test.
For tool-surface tuning, call `mcp_dispatch_audit`; it summarizes MCP tool
traffic and can filter by `source`, `client_name`, `profile`, `model`, and
`model_reasoning_effort`. Filtered fields such as `hot_tools` and
`source_breakdown` follow the current filter; `global_hot_codex_tools` and
`global_hot_hook_tools` are source-only comparison panels.

For `context_budget` heuristic calibration against a tokenizer baseline:

```bash
# Example with a temporary venv:
python3 -m venv /tmp/ab-calib-venv
/tmp/ab-calib-venv/bin/pip install tiktoken
/tmp/ab-calib-venv/bin/python scripts/calibrate_context_budget.py --default-set
```

The script reports MAPE/worst error and exits non-zero if MAPE exceeds the target
(default 15%).

Optional JSON report:

```bash
./scripts/compare_session_curate_profiles.sh \
  --transcript /path/to/session.jsonl \
  --json-out ./curate-profile-report.json
```

### Cross-machine memory sync

Memory is stored in SQLite at `~/.local/share/agent-bridge/state.db`
(macOS: `~/Library/Application Support/agent-bridge/state.db`).
The companion repo **[pallasting/agent-bridge-memory](https://github.com/pallasting/agent-bridge-memory)**
(private) holds exported JSONL / sync scripts for git-backed backup across machines.

```bash
# Clone (requires GitHub access to the private repo)
git clone git@github.com:pallasting/agent-bridge-memory.git ~/agent-bridge-memory

# Sync manually — native command; round-trips memories + edges + forum with a
# version-vector merge (concurrent edits become non-destructive conflict copies).
agent-bridge sync

# Automatic: the Stop hook calls `agent-bridge sync` in the background on every
# session end (a systemd timer / macOS LaunchAgent also runs it on a cadence).
# Point at a custom checkout path:
export AGENT_BRIDGE_MEMORY_REPO=~/agent-bridge-memory

# The legacy ~/agent-bridge-memory/sync.sh (bash, newer-wins) is superseded by
# the native `agent-bridge sync` above.
```

### Cross-machine forum + presence (v20a — Tailscale daemon)

The git-roundtrip sync above carries memory + forum data across machines
on a 1–5 minute cadence (good for "store and forward" handoffs). For
near-real-time multi-CC collaboration on the same tailnet, run the
HTTP daemon and use the `peer:` arg on forum/presence MCP tools:

```bash
# On each tailnet node — bind 0.0.0.0:7878 so peers can reach you
agent-bridge daemon-http
# or pin a different port:
agent-bridge daemon-http --listen 0.0.0.0:8787

# Smoke test from another tailnet peer
curl http://<peer-tailscale-ip>:7878/forum/threads?board=general
curl http://<peer-tailscale-ip>:7878/.well-known/agent.json/<session_id>
```

Then in any MCP tool call, route to a remote peer with one extra arg:

```json
{ "name": "forum_list_threads",
  "arguments": { "board": "general", "peer": "100.91.146.24:7878" } }
```

`peer` is optional and accepted by `forum_list_threads`, `forum_read`,
`forum_post`, `agent_presence_list`. Omit for local-store behaviour.

For long-running deployment, ready-to-customise init unit templates:
- `docs/deploy/agent-bridge-daemon-http.service` — systemd user unit (Linux)
- `docs/deploy/com.pallasting.agent-bridge.daemon-http.plist` — launchd agent (macOS)

Plain HTTP — encryption is the tailnet's WireGuard layer (no HMAC; see
`docs/RFC-v20-tailscale-daemon.md` §2). Trusts whoever can reach the
socket; bind `127.0.0.1:7878` if you want local-only.

---

## MCP tools

The full registry is **~296 tools** (2026-07 count), gated per client by
toolsets/tiers (`claude-standard`, `codex-essential`, `gemini-lean`,
`hook-lifecycle`, … — see `AGENT_BRIDGE_TOOLSET` above), so no client sees
all of them at once. On top of the toolset gates, two availability gates
trim tools that could not work anyway (2026-07 prune):

- **Host surface** — device/credential-backed families (`mobile_*`,
  `macos_ax_*`, `brave`/`notion`/`cloudflare`/`github`/`gitlab`/`tailscale`)
  are only registered when the backing binary/token is present (e.g. `adb`
  on PATH, `GITHUB_TOKEN` set). `AGENT_BRIDGE_EXPOSE_UNAVAILABLE=1` restores
  the full nominal surface.
- **Ceremony gate** — concluded one-shot governance-ceremony surfaces
  (review packets, decision records, gate chains from finished arcs) are
  hidden from every profile including `all`. Re-expose with
  `AGENT_BRIDGE_EXPOSE_CEREMONY=1` or the `all-dev` toolset when a new gate
  cycle starts.

The table below is the stable core subset; discover the live surface with
the `capabilities` tool, audit real traffic with `mcp_dispatch_audit`, and
ask `mcp_config_audit` (`tool_surface`) what is hidden on this host and why.

| Group | Tool | What Claude can do |
|-------|------|--------------------|
| notify | `notify` | Ping the human via desktop notification |
| | `notifications_recent` | Self-check past pings to avoid duplicates (Niche since the 2026-07 prune — needs profile `all`) |
| | `osc_parse` | Parse OSC 9/99/777 sequences and dispatch |
| terminal | `terminal_list` | Discover panes (Kitty / Zellij / WezTerm) |
| | `terminal_send_keys` | Type into a sibling pane |
| | `terminal_split` | Spawn a new pane |
| browser | `browser_navigate` | Open a URL in the controlled Chromium |
| | `browser_eval` | Run JS in the page, get JSON back |
| | `browser_snapshot` | Get an A11y tree (10–50× cheaper than PNG) |
| | `browser_click` | Click an element by CSS selector |
| | `browser_screenshot` | Capture full-page PNG (file or inline) |
| | `browser_extract_text` | Visible page text (`innerText`), JSON `{ text, chars }` |
| | `browser_fill_form` | Fill first matching input/textarea (`selector` + `value`) |
| agent | `agent_spawn` | Launch a sibling agent one-shot, or a live `claude-code` PTY with `interactive=true` |
| | `agent_send_input` | Send one follow-up turn to a live interactive agent session |
| | `agent_kill` | SIGTERM a running sub-agent |
| | `agent_session_list` | List recent agent sessions |
| | `agent_session_get` | Fetch stdout/stderr of a session |
| | `agent_session_wait` | Block until a session finishes |
| worktree | `worktree_list` | See all parallel branches |
| | `worktree_create` | Fork a worktree on a fresh branch |
| | `worktree_remove` | Tear down a worktree |
| memory | `memory_save` | Persist a note (lesson / decision / context / …) |
| | `memory_get` | Fetch one note by key |
| | `memory_search` | FTS / hybrid / semantic recall with explicit scope modes |
| | `memory_list` | List memories by kind / sort order |
| | `memory_delete` | Remove a note |
| | `memory_compact` | Prune stale memories by age or access count |
| | `memory_export` | Export to JSONL file |
| | `memory_import` | Import from JSONL (skip / overwrite / newer-wins) |
| | `memory_link` | Create a typed edge between two notes |
| | `memory_neighbors` | Walk the memory graph from a key (BFS with energy decay) |
| | `memory_consolidate` | Find and merge duplicate/redundant memories by Jaccard similarity |
| | `memory_stats` | Aggregate statistics: counts by status/kind, edge count, top tags |
| | `memory_suggest` | Suggest related memory keys via tag/prefix/content overlap |
| | `memory_graph_topology` | Read-only PageRank-readiness snapshot: orphan rate, hubs, edge coverage; accepts optional `scope`/`scope_mode` plus `skip_kinds`/`skip_tags` for durable scoped checks |
| | `memory_orphan_candidates` | Scoped, read-only orphan-link candidate preview for graph hygiene |
| | `memory_orphan_inventory` | Scoped, read-only inventory of remaining orphan memories by kind/tag/age/key |
| | `memory_graph_export` | Export memory graph as Graphviz DOT or JSON (v0.11) |
| | `memory_auto_curate` | Scope-bounded batch curation from `session_handoff` memories; persists inferred confidence and source lineage (v0.12) |
| multi-session | `agent_message` | Append JSON payload to another session's inbox (`agent_messages`, SQLite v10 / W6; Niche since the 2026-07 prune — the forum tools are the live path) |
| | `agent_inbox` | Fetch inbox rows (`since_id`, `unread_only`, `limit`; Niche since the 2026-07 prune) |
| plan | `plan_save` | Persist a structured task plan (steps, deps, per-step status) to SQLite (W5) |
| | `plan_load` | Load plan + `progress` / `next_step_id` summary |
| | `plan_update` | Set one step's status by id |
| session | `session_bootstrap` | Build a compact memory bootstrap block for the current session |
| | `session_curate` | Extract structured memories from conversation text; lifecycle calls inherit project scope and mark outputs inferred (two-pass pipeline) |
| | `session_finalize` | Session-end: importance decay + compact stale memories + optional export |
| | `session_handoff` | Structured JSON brief: todos + `session_handoff` memories + git snapshot (W3; Niche since the 2026-07 prune — `session_lifecycle_step` is the live successor) |
| | `session_lifecycle_step` | Dispatch `bootstrap` / `precompact` (curate+finalize) / `finalize` in one call |
| meta | `capabilities` | Report what agent-bridge can do in this environment |
| | `readiness_audit` | Read-only readiness snapshot over setup/tool profiles, hooks, skills, audit surfaces, and ECC-derived non-goals |
| | `mcp_config_audit` | Audit Codex / Gemini CLI / Claude Code MCP config and direct stdio connectivity |
| | `mcp_dispatch_audit` | Audit MCP tool traffic by source, client, profile, model, and reasoning effort |
| | `context_budget` | Offline token estimate vs approximate model limit + compaction recommendation (W5) |
| | `hook_status` | Check installed hook scripts and their last run status |
| | `mcp_recent_errors` | List recent failed MCP `tools/call` rows from the SQLite ring buffer |
| ide | `ide_snapshot` | Read editor state from an IDE-written JSON snapshot: active file, selection, open files, diagnostics, recent tasks |
| | `ide_command` | Queue IDE actions for an extension to execute: open/reveal file, run task, write snapshot |
| perceive | `project_detect` | Detect languages / build hints / Rust workspace members / git snapshot from manifests (W2) |
| | `changes_digest` | Structured git diff summary (`working_tree` / `staged` / `last_commit` / `branch_vs_main`) |
| | `git_topology_preflight` | Read-only PR/MR target/source merge-base and diffstat preflight |
| warp-oz | `oz_run_get` | Fetch status of a Warp cloud agent run by `run_id` or `session_id` |
| | `oz_run_list` | List recent Warp cloud agent runs (optional state filter) |
| | `oz_run_cancel` | Cancel an in-progress Warp cloud agent run |
| warp (URI) | `warp_open_tab` | `warp://action/new_tab` — optional `path` for initial cwd (W4) |
| | `warp_open_window` | `warp://action/new_window` |
| | `warp_open_settings` | `warp://action/open_settings_page` (best-effort) |
| | `warp_launch_workflow` | `warp://launch/<configuration_name>` — saved Launch Configuration |
| | `warp_status` | Env / opener / IPC bridge socket / `oz` on PATH — does not open UI |

### Memory recall scopes (single-user, not ACLs)

`memory_save` accepts an optional `scope` field:

| Value | Recall visibility |
|-------|-------------------|
| _(omitted)_ or `"global"` | All sessions everywhere |
| `"project:/abs/path"` | Only when cwd is inside `/abs/path` |
| `"domain:rust"` | Any session tagged with the `rust` domain |

These scopes prevent accidental cross-project recall in the local single-user
store; they are **not** tenant, principal, ownership, or permission ACLs.
`memory_get` and `memory_list` remain explicit operator/all-store surfaces.
Do not expose one store to mutually untrusted users on the strength of `scope`.
Automatic contextual paths are stricter: semantic `session_bootstrap`, graph
BFS expansion, automatic evolution links, and lifecycle-driven curation admit
only the current project/domain lane plus global memories. Project matching is
path-segment-aware (`/repo/a` does not match `/repo/another`).

### Memory search / embeddings (operators & agents)

Memories get a model-aware embedding from the active local backend (`embed_text`
in `ab-store`) on every `memory_save` and `memory_import` row — **no external
embedding API**. With the default `onnx-embed` feature, the compiled default is
`gte-multilingual-base` at 768 dimensions. `AGENT_BRIDGE_ONNX_MODEL=e5-small`,
`all-minilm`, or `para-ml` selects a legacy 384-dimensional model. Set
`AGENT_BRIDGE_EMBED_BACKEND=hash` to force the deterministic FNV-1a fallback;
its output width follows the active `vector_dim()` (384 in a hash-only build,
otherwise the selected model width). Treat `capabilities.memory.embedding`
(`backend` + `dim`) as the runtime truth before migrating or reindexing a store.

When you pass a `scope`, choose the recall boundary deliberately:

| `scope_mode` | Use when | Recall behavior |
|--------------|----------|-----------------|
| `local_only` | Fixing, building, releasing, or reporting status inside one repo | Keeps only rows matching the requested project/domain scope |
| `local_plus_global` | Current repo work can benefit from general lessons | Keeps matching rows plus global/unscoped rows, with global/unscoped results demoted |
| `exploratory` | Design, research, analogy, or cross-domain ideation | Keeps cross-scope rows as demoted analogy candidates |

For compatibility, `include_global=true` maps to `local_plus_global` when
`scope_mode` is omitted. Exploratory cross-scope hits are read-time candidates;
they are not recorded as coactivation training evidence.

| Audience | What to read |
|----------|----------------|
| **Human operators** | Pick `memory_search` **scope_mode** first, then **mode**: `fts` (BM25 keywords), `hybrid` (FTS + graph RRF), `semantic` (cosine on local embeddings). Tune `threshold` on semantic (about 0.3 broad, about 0.7 tight). |
| **Coding agents** | Same rules via MCP schema; use `local_only` for implementation/status/release tasks, `local_plus_global` for local work plus general lessons, and `exploratory` only when cross-project analogies are part of the task. |

See also: `docs/AGENT-BRIDGE-EVOLUTION-CORE.md` §8, `docs/AGENT-BRIDGE-AGENT-UX-ROADMAP.md` (phased follow-ups).

### Context lanes (shadow-only)

The internal `agent_bridge.context_lane_decision.v0` contract keeps workflow
state, interaction memory, source evidence, entity relations, and tool
observations in typed lanes while evaluating scope, `as_of`, provenance, and
authority. `user_stated` evidence must retain an attributed claimant and may be
context-only; source-backed `verified` evidence is required for load-bearing
grounded answers. The contract is currently `shadow_only`: it has no MCP
surface and can neither write memory nor execute tools.

---

### MCP response diagnostics

Every `tools/call` response now includes a top-level `backend_id` object for
support logging and environment diagnostics:

```json
{
  "backend_id": {
    "terminal": "wezterm",
    "browser": "chromium-cdp",
    "agent_runtime": "claude-code",
    "memory": "sqlite"
  }
}
```

This metadata is injected by the MCP stdio server on both success and
tool-error results.

When a SQLite store is configured, failed `tools/call` outcomes (unknown tool,
handler `Err`, `isError` tool results, and a few serialization edge cases) are
also appended to a bounded ring buffer. Inspect them with the **`mcp_recent_errors`**
MCP tool (`limit` 1–500, default 20).

---

## Architecture

```
                    ┌──── agent-cli ──────────┐  (Unix-socket JSON-RPC)
                    │                         │
                    ▼                         ▼
                                   ┌──────────────────────┐
                                   │ agent-bridge daemon  │
                                   │  ┌────────────────┐  │
       Claude Code ─────stdio────▶ │  │      Hub       │  │
       (`agent-bridge mcp`)        │  │  ┌──────────┐  │  │
                                   │  │  │ Notifier │  │  │ → D-Bus / macOS
                                   │  │  │ Store    │  │  │ → SQLite (WAL)
                                   │  │  │ Terminal │  │  │ → Kitty / Zellij / WezTerm
                                   │  │  │ Browser  │  │  │ → Chromium / CDP
                                   │  │  │ Agent    │  │  │ → claude -p
                                   │  │  │ Worktree │  │  │ → git worktree
                                   │  │  └──────────┘  │  │
                                   │  └────────────────┘  │
                                   └──────────────────────┘
```

## Trait extension points

| Trait | Default impl | Future impls |
|-------|-------------|-------------|
| `Notifier` | `DbusNotifier` (Linux), `MacOsNotifier` | webhook, Slack, Pushover |
| `BrowserBackend` | `ChromiumCdpBackend` | webkit, playwright, Firefox |
| `AgentRuntime` | `ClaudeCodeRuntime`, `CodexRuntime`, `GeminiRuntime`, `OpenCodeFamilyRuntime` (kilo/opencode), `AuggieRuntime`, `OzAgentRuntime` (Warp cloud) | aider, ghostty-native |
| `TerminalBackend` | `KittyBackend`, `ZellijBackend`, `WezTermBackend`, `WarpBackend` | ghostty, tmux |
| `StateStore` | `SqliteStore` (rusqlite-bundled) | in-memory, postgres |
| `McpTool` | ~296 built-in tools (tier/toolset gated) | drop in any `Box<dyn McpTool>` |

## Configuration (env vars)

| Variable | Default | Effect |
|----------|---------|--------|
| `AGENT_BRIDGE_SOCKET` | `$XDG_RUNTIME_DIR/agent-bridge/bridge.sock` | Override socket path |
| `AGENT_BRIDGE_REPO` | `$PWD` | Repo for `worktree_*` tools |
| `AGENT_BRIDGE_DB` | platform default `state.db` | Override SQLite DB path (useful for isolated integration tests) |
| `AGENT_BRIDGE_HEADLESS` | (unset = headed) | `1` for headless Chromium |
| `AGENT_BRIDGE_CHROME` | auto-detect | Path to chrome/chromium binary |
| `AGENT_BRIDGE_CLAUDE_BIN` | `claude` | Override claude CLI path |
| `AGENT_BRIDGE_AGENT_RUNTIME` | `claude-code` | Pick agent runtime: `claude-code` \| `warp-oz` |
| `AGENT_BRIDGE_OZ_BIN` | `oz` | Override Warp `oz` CLI path (when runtime = `warp-oz`) |
| `AGENT_BRIDGE_OZ_ENVIRONMENT_ID` | _(none)_ | Default Oz cloud environment id; can be overridden per `agent_spawn` via `env.OZ_ENVIRONMENT_ID` |
| `AGENT_BRIDGE_TERMINAL` | auto-detect | Force: `wezterm` \| `kitty` \| `zellij` \| `warp` |
| `AGENT_BRIDGE_KITTY_SOCKET` | `$KITTY_LISTEN_ON` | kitty IPC socket |
| `AGENT_BRIDGE_WARP_OPENER` | `xdg-open` (Linux), `open` (macOS) | URL handler used by `WarpBackend` to dispatch `warp://` URIs |
| `AGENT_BRIDGE_MEMORY_REPO` | `~/agent-bridge-memory` | Path to memory sync repo |
| `RUST_LOG` | `info` | tracing-subscriber filter |

### Terminal backend auto-detection

1. `ZELLIJ` is set → `ZellijBackend`
2. `KITTY_WINDOW_ID` is set → `KittyBackend`
3. `TERM_PROGRAM=WarpTerminal` (or `WARP_IS_LOCAL_SHELL_SESSION=1` /
   `WARP_HONOR_PS1=1`) → `WarpBackend`
4. otherwise → `WezTermBackend`

### Agent runtime selection

| Runtime | id | Underlying CLI | Notes |
|---------|----|----------------|-------|
| `ClaudeCodeRuntime` (default) | `claude-code` | `claude -p <prompt>` or bare `claude` in a PTY | One-shot local invocation by default; set `interactive=true` on `agent_spawn` for a live PTY session that accepts follow-up turns via `agent_send_input`. |
| `OzAgentRuntime` | `warp-oz` | `oz agent run-cloud --prompt <prompt> [--environment <id>]` | Spawns a Warp Oz cloud agent. The local `oz` child exits quickly after POSTing to `https://app.warp.dev/api/v1/agent/run`; the run id is captured in the session's stdout. To cancel the cloud run itself, use `oz run cancel <run-id>` — `agent_kill` only signals the local CLI child. |

Switch with `export AGENT_BRIDGE_AGENT_RUNTIME=warp-oz`. Pin a default
cloud environment with `AGENT_BRIDGE_OZ_ENVIRONMENT_ID`, or override
per-spawn by passing `env.OZ_ENVIRONMENT_ID` to the `agent_spawn` MCP
tool.

Interactive agent sessions are currently supported only by
`backend=claude-code`. Other backends reject `interactive=true` before
spawning; one-shot sessions and finished sessions reject `agent_send_input`.

### Cloud Agent Lifecycle (warp-oz)

After `agent_spawn` returns a session id, agent-bridge automatically:

1. Parses `run_id` from the `oz` CLI JSON output.
2. Persists `run_id` in the session row (`cloud_run_id` column).
3. Starts a background poller (`oz run get <run_id>`) every 5 s for
   up to 30 min, writing the live `state` and `session_link` back into
   the store (`cloud_run_state` / `cloud_session_link`).

`agent_session_wait` is cloud-aware: for `warp-oz` sessions it continues
polling after the local CLI exits until the cloud run reaches a terminal
state (`SUCCEEDED` / `FAILED` / `CANCELLED`) or the timeout elapses.

#### New MCP tools (v0.10)

| Tool | Description |
|------|-------------|
| `oz_run_get` | Fetch current state of a cloud run by `run_id` or bridge `session_id`. Returns `state`, `title`, `session_link`. |
| `oz_run_list` | List recent cloud runs (optional `state` filter, `limit`). |
| `oz_run_cancel` | Cancel an in-progress cloud run by `run_id` or `session_id`. |

All three tools require the `oz` CLI on `$PATH` and an active session
(`oz login` or `WARP_API_KEY` set). `capabilities()` reports
`oz_run_tools: true` when the runtime is `warp-oz`.

**v0.12**: `memory_auto_curate` can be scheduled as a recurring Warp Oz
cloud agent task (daily cron via `oz schedule`) to automatically distil
accumulated `session_handoff` memories into structured lessons, decisions,
and facts — no human prompt required. Its `scope` (default `global`) bounds both
source selection and derived output; each saved result keeps source keys in
`related_keys`, writes `derived_from` edges, and is tagged
`continuity_confidence:inferred`. Use an explicit project/domain scope for
local runs; scoped derived keys include a stable scope digest so identical text
cannot collide across projects. Automatic curation never upgrades extracted
text to `verified`.

### `WarpBackend` capabilities

> **Status (2026-05-08, post-2f14d84):** the default terminal backend is
> now `PtyBackend` — it provides full `read_blocks` via OSC 133 prompt
> markers (`docs/SHELL-INTEGRATION-OSC133.md`), with no Warp fork or
> shell-integration patch needed. The section below describes the
> opt-in Warp IPC path (`AGENT_BRIDGE_TERMINAL=warp`) which remains
> available for users who specifically want it.

Warp does not expose a public CLI for terminal mux control, only the
`warp://` URL scheme. The backend therefore supports a reduced
feature set:

| Op | Behaviour |
|----|-----------|
| `list_panes` | Returns one synthetic row for the current shell session (id from `WARP_SESSION_ID` if exported, else `warp:current`). |
| `send_keys` / `read_output` | When the in-process Warp IPC Unix socket is present (`AGENT_BRIDGE_WARP_IPC_SOCKET` or default under `$XDG_RUNTIME_DIR`), uses bridge RPC; otherwise `Error::Backend` (URL scheme alone cannot drive another pane). |
| `split`      | Vertical → `warp://action/new_tab?path=<cwd>`; Horizontal → `warp://action/new_window?path=<cwd>`. New pane id is synthetic. |
| `subscribe`  | Empty stream (OSC notifications still flow through `osc.parse`). |

MCP **`capabilities`** reports `terminal.capabilities` (`TerminalCapabilities`), including `warp_ipc_socket_ready` and effective `can_read_output` / `can_send_keys`.

## Status

| Phase | Scope | State |
|-------|-------|-------|
| P0 | Unix-socket JSON-RPC daemon, D-Bus notifications | ✅ |
| P1-A | SQLite history store | ✅ |
| P1-B | OSC 9/99/777 parser + terminal backends | ✅ |
| P1-C | GitWorktreeManager + ClaudeCodeRuntime | ✅ |
| P1-D | ChromiumCdpBackend (CDP) | ✅ |
| P1-E | MCP stdio server (~296 tools, profile-gated) | ✅ |
| P1-F | Cross-session memory (FTS5 + graph edges + scopes) | ✅ |
| P1-G | PreCompact curator hook + `agent-bridge setup` | ✅ |

## Contributing

```bash
git clone <repo>
./scripts/wrapper/install.sh    # wrapper + creds template + githooks
```

The wrapper installer wires a **pre-commit hook** that runs
`cargo check -p ab-bridge --all-targets` on staged Rust changes (P23,
commit `a5d81b4`). This catches broken-HEAD commits like a missing fn
definition before they hit `master`. Bypass per-commit with
`--no-verify` or `AGENT_BRIDGE_SKIP_PRECOMMIT=1 git commit ...`; skip
the install entirely with `AGENT_BRIDGE_SKIP_GITHOOKS=1`.

For maintainers: GitHub branch protection is recommended on `master` —
require **CI** + **Verify Warp Integration** status checks to pass
before merging. The badges at the top of this README reflect master's
current state; if they go red, master shouldn't be pulled until fixed.

## License

MIT.
