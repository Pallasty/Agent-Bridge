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

## What `setup` does

`agent-bridge setup` is idempotent and safe to re-run after upgrades:

| Step | What happens |
|------|-------------|
| Binary | Copies itself to `~/.local/bin/agent-bridge` |
| Hook scripts | Writes three scripts to `~/.local/bin/` (see below) |
| Curator settings | Writes `~/.config/agent-bridge/memory-curator-settings.json` |
| Claude Code hooks | Merges three hook entries into `~/.claude/settings.json` (never overwrites existing entries) |

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
| `AgentRuntime` | `ClaudeCodeRuntime` (one-shot) | codex, aider, gemini-cli |
| `TerminalBackend` | `KittyBackend`, `ZellijBackend`, `WezTermBackend` | ghostty, tmux |
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
| `AGENT_BRIDGE_TERMINAL` | auto-detect | Force: `wezterm` \| `kitty` \| `zellij` |
| `AGENT_BRIDGE_KITTY_SOCKET` | `$KITTY_LISTEN_ON` | kitty IPC socket |
| `AGENT_BRIDGE_MEMORY_REPO` | `~/agent-bridge-memory` | Path to memory sync repo |
| `RUST_LOG` | `info` | tracing-subscriber filter |

### Terminal backend auto-detection

1. `ZELLIJ` is set → `ZellijBackend`
2. `KITTY_WINDOW_ID` is set → `KittyBackend`
3. otherwise → `WezTermBackend`

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
