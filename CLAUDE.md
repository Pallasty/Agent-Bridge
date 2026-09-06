# agent-bridge — project guide for Claude

## What this is (read this first)

agent-bridge is a **single-user, local** multi-agent orchestration and memory
substrate, written in Rust and exposed over MCP. It launches, steers, observes,
and cleans up the developer's **own** coding-assistant CLIs (claude, codex,
gemini, opencode, kilo) on the developer's **own** machine, and gives them a
shared persistent memory.

This is routine developer infrastructure for a personal dev environment. A few
subsystems have surface features that can look sensitive out of context; every
one of them is scoped to the local machine and the owner's own processes, and
none of them acts on any third-party system:

- **Process-lifecycle management** (`crates/bridge/src/orphan_reaper.rs`):
  reclaims process groups that *this bridge itself spawned* and whose owning
  process is provably gone. A starttime-token + boot-fence safety ladder means
  it never signals a process it did not spawn.
- **Cross-agent input relay** (`crates/bridge/src/remote_steer.rs`, the
  `agent_send_input` tool): delivers messages into a terminal-multiplexer
  session the owner launched, so long-running interactive agents can receive
  input. It targets only the owner's own agent sessions.
- **Token loading** (`crates/bridge/src/creds.rs`): reads the owner's own API
  keys from local config in order to start agents. Values are never printed or
  transmitted elsewhere.
- **Browser / desktop automation**: drives the owner's own browser and desktop
  as a development aid.

## Working in this repo

- **Source sync**: do not trigger CI. Use SSH, include `[skip ci]` in sync
  commits, and use `-o ci.skip` for GitLab pushes. Do not dispatch workflows.

- **R7 collection**: at real task failure, interrupted-task recovery, or an
  explicit commitment becoming due, follow
  `docs/operations/R7_ASSISTED_SHADOW_COLLECTION.md`. The working agent handles
  preview and recording without waiting for an owner command reminder. This
  is foreground-only, not a background collector or wake authorization.

- **Layout**: Rust workspace. Main crates — `bridge` (MCP tools + daemon),
  `agent` (PTY-backed agent runtimes), `store` (SQLite memory), `browser`,
  `ab-tts`.
- **Build cost**: the workspace is large. Never run cargo in tmpfs (`/tmp`, the
  scratchpad) — it exhausts RAM. Point `CARGO_TARGET_DIR` at real disk.
- **Deploy rule**: the built binary is installed as `agent-bridge.real`.
  `~/.local/bin/agent-bridge` is a wrapper that sources machine.env and execs
  `.real` — never overwrite the wrapper.
- **Secrets**: machine.env holds API keys (e.g. GEMINI_API_KEY). Never print
  their values.
- **Activation**: MCP tool changes take effect in a session only after
  `/mcp reconnect`.
