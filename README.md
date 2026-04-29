# agent-bridge

A Unix-native AI-agent control plane: desktop notifications, cross-session memory,
MCP tool registry, terminal multiplexer glue, browser automation (CDP), git-worktree
orchestration, and sub-agent spawning — all pluggable via Rust traits.

## Quick start (new machine)

```bash
# 1. Clone and build (cold compile ≈ 2–3 min; incremental < 15 s)
git clone git@github.com:pallasting/Agent-Bridge.git ~/agent-bridge
cd ~/agent-bridge && cargo build --release

# 2. Install binary + Claude Code hooks in one step
./target/release/agent-bridge setup

# 3. Add to PATH (fish)
fish_add_path ~/.local/bin
# bash/zsh: export PATH="$HOME/.local/bin:$PATH"

# 4. Start the long-lived daemon
agent-bridge daemon &

# 5. Register as MCP server (Claude Code reads this at startup)
claude mcp add agent-bridge agent-bridge mcp

# 6. (Optional) Clone the memory-sync repo for cross-machine memory
git clone git@github.com:<you>/agent-bridge-memory.git ~/agent-bridge-memory

# 7. Restart Claude Code — hooks fire automatically from here on
```

That's it. Claude Code now has persistent cross-session memory, automatic compaction,
and git-backed sync to any other machine running agent-bridge.

---

## Quick start (Warp)

[Warp](https://www.warp.dev) is supported as a first-class frontend. The
flow differs from Claude Code in two ways: there is no shell-out hook
model, and Warp registers MCP servers via its settings UI rather than a
`claude mcp add` CLI.

```bash
# 1. Build (same as above)
git clone git@github.com:pallasting/Agent-Bridge.git ~/agent-bridge
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
which detects Warp via env vars and falls back to claude-code).

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

### Hook scripts

| Script | Claude Code event | Purpose |
|--------|------------------|---------|
| `ab-memory-hook` | `UserPromptSubmit` | Inject scope-aware memory index at session start (once per session) |
| `ab-precompact-hook` | `PreCompact` (manual + auto) | Spawn a curator sub-agent that reads the conversation and saves lessons/decisions to memory before context is lost |
| `ab-session-end-hook` | `Stop` | Compact memories older than 90 days; sync to git remote |

### Memory lifecycle

```
Session start  ──► ab-memory-hook injects relevant memories into context
     │
     ▼
  conversation  ──► Claude calls memory_save / memory_link at will
     │
     ▼
/compact or     ──► ab-precompact-hook spawns curator sub-agent
context full         └─► reads transcript → calls memory_save (3–8 items)
     │
     ▼
Session end     ──► ab-session-end-hook compacts stale + syncs to git
```

### Cross-machine memory sync

Memory is stored in SQLite at `~/.local/share/agent-bridge/state.db`.
The optional `agent-bridge-memory` companion repo provides git-backed sync:

```bash
# Sync manually
AGENT_BRIDGE_BIN=agent-bridge bash ~/agent-bridge-memory/sync.sh

# Automatic: the Stop hook runs sync.sh in the background on every session end
# Point at a custom repo location:
export AGENT_BRIDGE_MEMORY_REPO=~/my-memory-repo
```

---

## MCP tools (29 total)

Claude Code sees these tools when agent-bridge is registered as an MCP server:

| Group | Tool | What Claude can do |
|-------|------|--------------------|
| notify | `notify` | Ping the human via desktop notification |
| | `notifications_recent` | Self-check past pings to avoid duplicates |
| | `osc_parse` | Parse OSC 9/99/777 sequences and dispatch |
| terminal | `terminal_list` | Discover panes (Kitty / Zellij / WezTerm) |
| | `terminal_send_keys` | Type into a sibling pane |
| | `terminal_split` | Spawn a new pane |
| browser | `browser_navigate` | Open a URL in the controlled Chromium |
| | `browser_eval` | Run JS in the page, get JSON back |
| | `browser_snapshot` | Get an A11y tree (10–50× cheaper than PNG) |
| | `browser_click` | Click an element by CSS selector |
| | `browser_screenshot` | Capture full-page PNG (file or inline) |
| agent | `agent_spawn` | Launch a sibling Claude Code one-shot |
| | `agent_kill` | SIGTERM a running sub-agent |
| | `agent_session_list` | List recent agent sessions |
| | `agent_session_get` | Fetch stdout/stderr of a session |
| | `agent_session_wait` | Block until a session finishes |
| worktree | `worktree_list` | See all parallel branches |
| | `worktree_create` | Fork a worktree on a fresh branch |
| | `worktree_remove` | Tear down a worktree |
| memory | `memory_save` | Persist a note (lesson / decision / context / …) |
| | `memory_get` | Fetch one note by key |
| | `memory_search` | FTS5 full-text search with recency ranking |
| | `memory_list` | List memories by kind / sort order |
| | `memory_delete` | Remove a note |
| | `memory_compact` | Prune stale memories by age or access count |
| | `memory_export` | Export to JSONL file |
| | `memory_import` | Import from JSONL (skip / overwrite / newer-wins) |
| | `memory_link` | Create a typed edge between two notes |
| | `memory_neighbors` | Walk the memory graph from a key |

### Memory scopes

`memory_save` accepts an optional `scope` field:

| Value | Visibility |
|-------|-----------|
| _(omitted)_ or `"global"` | All sessions everywhere |
| `"project:/abs/path"` | Only when cwd is inside `/abs/path` |
| `"domain:rust"` | Any session tagged with the `rust` domain |

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
| `AgentRuntime` | `ClaudeCodeRuntime` (one-shot), `OzAgentRuntime` (Warp cloud) | codex, aider, gemini-cli |
| `TerminalBackend` | `KittyBackend`, `ZellijBackend`, `WezTermBackend`, `WarpBackend` | ghostty, tmux |
| `StateStore` | `SqliteStore` (rusqlite-bundled) | in-memory, postgres |
| `McpTool` | 29 built-in tools | drop in any `Box<dyn McpTool>` |

## Configuration (env vars)

| Variable | Default | Effect |
|----------|---------|--------|
| `AGENT_BRIDGE_SOCKET` | `$XDG_RUNTIME_DIR/agent-bridge/bridge.sock` | Override socket path |
| `AGENT_BRIDGE_REPO` | `$PWD` | Repo for `worktree_*` tools |
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
| `ClaudeCodeRuntime` (default) | `claude-code` | `claude -p <prompt>` | One-shot local invocation; SIGTERM-able. |
| `OzAgentRuntime` | `warp-oz` | `oz agent run-cloud --prompt <prompt> [--environment <id>]` | Spawns a Warp Oz cloud agent. The local `oz` child exits quickly after POSTing to `https://app.warp.dev/api/v1/agent/run`; the run id is captured in the session's stdout. To cancel the cloud run itself, use `oz run cancel <run-id>` — `agent_kill` only signals the local CLI child. |

Switch with `export AGENT_BRIDGE_AGENT_RUNTIME=warp-oz`. Pin a default
cloud environment with `AGENT_BRIDGE_OZ_ENVIRONMENT_ID`, or override
per-spawn by passing `env.OZ_ENVIRONMENT_ID` to the `agent_spawn` MCP
tool.

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

### `WarpBackend` capabilities

Warp does not expose a public CLI for terminal mux control, only the
`warp://` URL scheme. The backend therefore supports a reduced
feature set:

| Op | Behaviour |
|----|-----------|
| `list_panes` | Returns one synthetic row for the current shell session (id from `WARP_SESSION_ID` if exported, else `warp:current`). |
| `send_keys`  | Returns `Error::Backend` — no public IPC for typing into another pane. |
| `split`      | Vertical → `warp://action/new_tab?path=<cwd>`; Horizontal → `warp://action/new_window?path=<cwd>`. New pane id is synthetic. |
| `subscribe`  | Empty stream (OSC notifications still flow through `osc.parse`). |

## Status

| Phase | Scope | State |
|-------|-------|-------|
| P0 | Unix-socket JSON-RPC daemon, D-Bus notifications | ✅ |
| P1-A | SQLite history store | ✅ |
| P1-B | OSC 9/99/777 parser + terminal backends | ✅ |
| P1-C | GitWorktreeManager + ClaudeCodeRuntime | ✅ |
| P1-D | ChromiumCdpBackend (CDP) | ✅ |
| P1-E | MCP stdio server (29 tools) | ✅ |
| P1-F | Cross-session memory (FTS5 + graph edges + scopes) | ✅ |
| P1-G | PreCompact curator hook + `agent-bridge setup` | ✅ |

## License

MIT.
