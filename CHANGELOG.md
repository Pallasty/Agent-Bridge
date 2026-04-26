# Changelog

All notable changes to **agent-bridge** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-04-26

First public release. **Linux-native AI-agent control plane** reaching feature
parity with the cmux core surface, plus Claude-Code-native superpowers via the
Model Context Protocol.

### Run modes (single binary)

- `agent-bridge daemon` — long-lived JSON-RPC server on
  `$XDG_RUNTIME_DIR/agent-bridge/bridge.sock`.
- `agent-bridge mcp` — stdio MCP server, drop-in for
  `claude mcp add agent-bridge ...`.

Both modes share the same backend bundle (`Hub`) so business logic is written
once and exposed through two ergonomically distinct interfaces (CLI for humans,
MCP for AI agents).

### 15 MCP tools

| Group | Tools |
|-------|-------|
| **Notify**    | `notify`, `notifications_recent`, `osc_parse` |
| **Terminal**  | `terminal_list`, `terminal_send_keys`, `terminal_split` |
| **Browser**   | `browser_navigate`, `browser_eval`, `browser_snapshot`, `browser_click`, `browser_screenshot` |
| **Agent**     | `agent_spawn` |
| **Worktree**  | `worktree_list`, `worktree_create`, `worktree_remove` (each accepts optional per-call `repo` param — switch repos without restarting the MCP server) |

### 6 pluggable trait boundaries

`Notifier` · `BrowserBackend` · `AgentRuntime` · `TerminalBackend` ·
`StateStore` · `McpTool`. Default impls land first; future backends only
need to satisfy the trait.

### Default backends shipped

- **DbusNotifier**       — pure-Rust D-Bus (`zbus`).
- **SqliteStore**        — bundled SQLite (`rusqlite/bundled`), WAL journal,
  zero system dependency.
- **WezTermBackend**     — wraps `wezterm cli list / send-text / split-pane`.
- **ChromiumCdpBackend** — Chrome DevTools Protocol via `chromiumoxide`,
  lazy-launch, headed by default (`AGENT_BRIDGE_HEADLESS=1` to flip).
- **ClaudeCodeRuntime**  — `claude -p` one-shot spawning.
- **GitWorktreeManager** — concrete (single impl by design) wrapper around
  `git worktree {add,list,remove}`.

### Engineering deltas vs P0 baseline

| Phase  | Surface added                                                            |
|--------|--------------------------------------------------------------------------|
| P0     | Unix-socket JSON-RPC daemon, D-Bus desktop notifications, agent-cli      |
| P1-A   | SQLite history store + `notifications.recent` + agent-cli `history`     |
| P1-B   | Streaming OSC 9/99/777 parser (10 unit tests) + WezTerm CLI backend     |
|        | + WezTerm Lua hook example                                               |
| P1-E   | MCP stdio server (initialize / tools/list / tools/call) + 6 tools first |
| P1-D   | ChromiumCdpBackend (CDP) + 5 browser tools                               |
| P1-C   | GitWorktreeManager + ClaudeCodeRuntime + agent_spawn + 3 worktree tools |

### End-to-end verifications (every claim has a paper trail)

- ✅ MCP `initialize` → `tools/list` → `tools/call` round-trip
- ✅ All 15 tools registered, JSON Schema valid
- ✅ Real Chromium navigation to https://news.ycombinator.com → 5 stories
  scraped via JS eval; full-page PNG ≈ 254 KB
- ✅ `browser_click` triggers real DOM event; URL transitions
  `/` → `/item?id=47909226`; subsequent eval scrapes 3 top comments
- ✅ `worktree_list(repo=...)` parallel calls across 4 different repos
  in a single Claude session (zero MCP-server restarts)
- ✅ `agent_spawn` launches a sibling Claude that reads a source file,
  writes the answer to `/tmp`, and exits — verified via filesystem
- ✅ Notifications persist across daemon restarts (SQLite WAL)
- ✅ stderr / stdout strict separation in MCP mode (no protocol pollution)
- ✅ 11 unit tests pass (10 OSC parser + 1 git porcelain parser)

### Stats

- 9 crates (8 lib + 1 daemon binary, plus `agent-cli`)
- ~3 700 lines of Rust
- 42 source files
- Zero system dependencies (zbus / rusqlite-bundled / chromiumoxide all
  pure-Rust paths)
- Release binary: 12 MB (`agent-bridge`) + 1.2 MB (`agent-cli`), strip+LTO
- Cold compile: ~2.5 min (chromiumoxide-heavy); incremental: < 15 s

### Known limits / non-goals (yet)

- `ClaudeCodeRuntime::send_input` returns an error — interactive PTY mode
  needs `portable-pty`; the one-shot `-p` path is sufficient for parallel
  agent orchestration today.
- `terminal.subscribe` returns an empty stream — wezterm has no native event
  firehose; OSC events are expected to arrive via the `osc.parse` RPC fed by
  the Lua hook in `examples/wezterm/`.
- No GUI. Two interfaces only: `agent-cli` (humans) and the MCP server (AI).
- Single-host: no Postgres / multi-machine `Hub` yet.

### Configuration (env vars)

| Variable                  | Default                                             | Effect                              |
|---------------------------|-----------------------------------------------------|-------------------------------------|
| `AGENT_BRIDGE_SOCKET`     | `$XDG_RUNTIME_DIR/agent-bridge/bridge.sock`         | Override daemon socket path         |
| `AGENT_BRIDGE_REPO`       | `$PWD`                                              | Default repo for `worktree_*` tools |
| `AGENT_BRIDGE_HEADLESS`   | unset (= headed)                                    | `1` for headless Chromium           |
| `AGENT_BRIDGE_CHROME`     | auto-detect                                         | Path to chrome/chromium binary      |
| `AGENT_BRIDGE_CLAUDE_BIN` | `claude`                                            | Override claude CLI path            |
| `RUST_LOG`                | `info`                                              | Standard tracing-subscriber filter  |

### Refinements after the P0..P1 baseline commit

- **fix(browser)**: per-PID user-data-dir avoids `SingletonLock` collisions
  when multiple agent-bridge processes share the same machine
  (`crates/browser/src/chromium_cdp.rs`).
- **feat(worktree)**: `worktree_list / _create / _remove` accept an optional
  per-call `repo` parameter, so Claude can hop between repos within one
  MCP session instead of restarting (`crates/bridge/src/mcp_tools.rs`).
- **docs**: README rewritten to match the final 15-tool surface.
