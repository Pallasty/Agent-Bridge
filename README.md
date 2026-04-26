# agent-bridge

A Linux-native AI-agent control plane: notifications, MCP tool registry, terminal multiplexer
glue, browser automation (CDP), git-worktree orchestration, and sub-agent spawning — all
pluggable via Rust traits.

## Status

| Phase | Scope | State |
|-------|-------|-------|
| **P0**   | Unix-socket JSON-RPC daemon, D-Bus desktop notifications              | ✅ |
| **P1-A** | SQLite history store (`notifications.recent`)                          | ✅ |
| **P1-B** | OSC 9/99/777 streaming parser + WezTerm CLI backend + Lua hook         | ✅ |
| **P1-E** | MCP stdio server (15 tools)                                            | ✅ |
| **P1-D** | ChromiumCdpBackend — navigate / eval / a11y snapshot / click / screenshot | ✅ |
| **P1-C** | GitWorktreeManager + ClaudeCodeRuntime (one-shot)                       | ✅ |

15 / 15 MCP tools live • 13 JSON-RPC methods • zero system dependencies (everything via
pure-Rust crates: zbus, rusqlite-bundled, chromiumoxide).

## Build

```bash
cargo build --release
# → ./target/release/agent-bridge   (daemon + MCP server, single binary)
# → ./target/release/agent-cli      (human-facing CLI)
```

Cold compile ≈ 2–3 min (chromiumoxide brings ~150 deps); incremental < 15 s.

## Two run modes

### 1. Daemon mode (Unix-socket JSON-RPC)

```bash
agent-bridge daemon       # binds $XDG_RUNTIME_DIR/agent-bridge/bridge.sock
agent-cli ping
agent-cli capabilities
agent-cli notify -t "hi" "from human" -s success
agent-cli history -n 20
agent-cli osc demo 9
agent-cli osc parse '\x1b]9;hello\x07'
agent-cli term list                                  # WezTerm
```

### 2. MCP mode (Claude Code integration)

```bash
claude mcp add agent-bridge /absolute/path/to/agent-bridge mcp
```

Claude then sees these **15 tools**:

| Group     | Tool                    | What Claude can do                                       |
|-----------|-------------------------|----------------------------------------------------------|
| notify    | `notify`                | Ping the human via desktop notification                  |
|           | `notifications_recent`  | Self-check past pings to avoid duplicates                |
|           | `osc_parse`             | Parse OSC 9/99/777 sequences from any text and dispatch  |
| terminal  | `terminal_list`         | Discover panes (WezTerm)                                 |
|           | `terminal_send_keys`    | Type into a sibling pane (multi-agent coordination)      |
|           | `terminal_split`        | Spawn a new sibling pane                                 |
| browser   | `browser_navigate`      | Open a URL in the controlled Chromium                    |
|           | `browser_eval`          | Run JS in the page, get JSON back                        |
|           | `browser_snapshot`      | Get a structured A11y tree (10–50× cheaper than PNG)     |
|           | `browser_click`         | Click an element by CSS selector                         |
|           | `browser_screenshot`    | Capture full-page PNG (file or inline base64)            |
| agent     | `agent_spawn`           | Launch a sibling Claude Code one-shot in any cwd         |
| worktree  | `worktree_list`         | See all parallel branches in flight                      |
|           | `worktree_create`       | Fork a new worktree on a fresh branch                    |
|           | `worktree_remove`       | Tear down a worktree                                     |

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
                                   │  │  │ Notifier │  │  │ → D-Bus
                                   │  │  │ Store    │  │  │ → SQLite
                                   │  │  │ Terminal │  │  │ → wezterm cli
                                   │  │  │ Browser  │  │  │ → Chromium / CDP
                                   │  │  │ Agent    │  │  │ → claude -p
                                   │  │  │ Worktree │  │  │ → git worktree
                                   │  │  └──────────┘  │  │
                                   │  └────────────────┘  │
                                   └──────────────────────┘
```

## Trait extension points

| Trait              | Default impl                                      | Future impls                              |
|--------------------|---------------------------------------------------|-------------------------------------------|
| `Notifier`         | `DbusNotifier`                                    | webhook, slack, pushover                  |
| `BrowserBackend`   | `ChromiumCdpBackend` (chromiumoxide)              | webkitgtk, playwright, firefox-marionette |
| `AgentRuntime`     | `ClaudeCodeRuntime` (one-shot)                    | codex, aider, gemini-cli, opencode        |
| `TerminalBackend`  | `WezTermBackend`                                  | ghostty, zellij, tmux                     |
| `StateStore`       | `SqliteStore` (rusqlite-bundled)                  | in-memory (tests), postgres (multi-host)  |
| `McpTool`          | 15 built-in tools                                 | drop in any `Box<dyn McpTool>`            |

The non-trait helper `GitWorktreeManager` is intentionally a single concrete type — there is
exactly one implementation (git itself), so adding a trait would be premature abstraction.

## Configuration (env vars)

| Variable                  | Default                                    | Effect                                |
|---------------------------|--------------------------------------------|---------------------------------------|
| `AGENT_BRIDGE_SOCKET`     | `$XDG_RUNTIME_DIR/agent-bridge/bridge.sock` | Override the daemon socket path       |
| `AGENT_BRIDGE_REPO`       | `$PWD`                                     | Repo for `worktree_*` tools           |
| `AGENT_BRIDGE_HEADLESS`   | (unset = headed)                           | `1` to launch Chromium headless       |
| `AGENT_BRIDGE_CHROME`     | auto-detect                                | Path to chrome/chromium binary        |
| `AGENT_BRIDGE_CLAUDE_BIN` | `claude`                                   | Override the claude CLI path          |
| `RUST_LOG`                | `info`                                     | Standard tracing-subscriber filter    |

## Verified end-to-end

- ✅ MCP `initialize` → `tools/list` → `tools/call` round-trip
- ✅ 15/15 tools registered, schemas valid
- ✅ Real Chromium navigate to https://example.com → A11y tree returns `RootWebArea "Example Domain"`
- ✅ `browser_eval` returns `"Example Domain"` for `document.title`
- ✅ `browser_screenshot` produces 800×600 PNG (~18 KB)
- ✅ `worktree_create` / `_list` / `_remove` round-trip on a real git repo
- ✅ Notifications persist across daemon restarts (SQLite WAL)
- ✅ stderr / stdout strict separation in MCP mode (no protocol pollution)
- ✅ 11 unit tests pass (10 OSC parser + 1 git porcelain parser)

## License

MIT.
