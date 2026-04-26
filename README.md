# agent-bridge

A Linux-native AI-agent control plane: notification routing, MCP tool registry,
worktree orchestration, and (soon) CDP browser automation — all pluggable via
Rust traits.

## Status

- **P0** ✅  End-to-end desktop notification (Unix-socket JSON-RPC daemon).
- **P1-A** ✅  SQLite-backed audit/history store (`notifications.recent`).
- **P1-B** ✅  Pure-Rust OSC 9/99/777 parser + WezTerm CLI backend +
  `examples/wezterm/agent-bridge.lua` hook.
- **P1-E** ✅  MCP stdio server (`agent-bridge mcp`) exposing 6 tools to
  Claude Code, Codex, etc.
- P1-D  ⏳  ChromiumOxide BrowserBackend (CDP).
- P1-C  ⏳  ClaudeCodeRuntime + git-worktree orchestration.

## Build

```bash
cargo build --release
```

Cold compile ≈ 60 s, incremental < 10 s. Zero system dependencies (zbus = pure
Rust D-Bus, rusqlite = bundled SQLite).

## Two run modes

### 1. Daemon mode (Unix-socket JSON-RPC)

```bash
agent-bridge daemon                    # binds $XDG_RUNTIME_DIR/agent-bridge/bridge.sock
agent-cli ping                         # → { "pong": true }
agent-cli capabilities                 # list registered methods + backends
agent-cli notify -t "Hello" "body" -s success
agent-cli history -n 20                # tabular view of recent notifications
agent-cli osc demo 9                   # send a sample OSC 9 sequence
agent-cli osc parse '\x1b]9;hi\x07'    # parse arbitrary text for OSC notifications
agent-cli term list                    # list panes (requires WezTerm)
```

### 2. MCP mode (Claude Code integration)

```bash
agent-bridge mcp     # newline-delimited JSON-RPC on stdio
```

Hook it into Claude Code:

```bash
claude mcp add agent-bridge /absolute/path/to/agent-bridge mcp
```

Claude then sees these 6 tools:

| Tool                    | What Claude can do                                      |
|-------------------------|---------------------------------------------------------|
| `notify`                | Ping the human via desktop notification                 |
| `notifications_recent`  | See its own past pings (avoid duplicates)               |
| `osc_parse`             | Parse OSC 9/99/777 escape sequences and dispatch them   |
| `terminal_list`         | Discover panes (WezTerm)                                |
| `terminal_send_keys`    | Type into a sibling pane (e.g. another agent's session) |
| `terminal_split`        | Spawn a new sibling pane                                |

## Architecture

```
                    ┌──── agent-cli ──────────┐  (Unix-socket JSON-RPC)
                    │                         │
                    ▼                         ▼
                                   ┌────────────────────┐
                                   │ agent-bridge daemon │
                                   │ ┌─────────────────┐ │
       Claude Code ─────stdio────▶ │ │     Hub         │ │
       (`agent-bridge mcp`)        │ │  ┌────────────┐ │ │
                                   │ │  │ Notifier   │ │ │ → D-Bus
                                   │ │  │ StateStore │ │ │ → SQLite
                                   │ │  │ Terminal   │ │ │ → wezterm cli
                                   │ │  └────────────┘ │ │
                                   │ └─────────────────┘ │
                                   └────────────────────┘
```

## Trait extension points

| Trait              | Default impl                | Future impls                              |
|--------------------|-----------------------------|-------------------------------------------|
| `Notifier`         | `DbusNotifier`              | webhook, slack, pushover                  |
| `BrowserBackend`   | _(stub)_                    | chromiumoxide (CDP), webkitgtk            |
| `AgentRuntime`     | _(stub)_                    | claude-code, codex, aider, gemini-cli     |
| `TerminalBackend`  | `WezTermBackend`            | ghostty, zellij, tmux                     |
| `StateStore`       | `SqliteStore` (bundled)     | in-memory, postgres                       |
| `McpTool`          | 6 built-in tools            | browser.*, worktree.*, agent.*            |

## License

MIT.
