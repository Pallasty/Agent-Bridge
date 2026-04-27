# Changelog

All notable changes to **agent-bridge** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project adheres to [Semantic Versioning](https://semver.org/).

## [0.5.1] — 2026-04-27

**Hotfix.** v0.5.0 shipped with a broken FTS5 sync trigger that made
`memory_delete` (and any DELETE-then-INSERT path on `memories`) raise
`SQL logic error`.

### Root cause

We created a content-stored FTS5 virtual table (`memories_fts` with no
`content=` clause) but used the contentless table's special `INSERT INTO
fts(fts, ...) VALUES('delete', ...)` command in the AFTER DELETE / AFTER
UPDATE triggers. That command is only valid on contentless FTS5 tables.
For content-stored tables the standard pattern is
`DELETE FROM fts WHERE rowid = old.rowid`.

### Fix

- `SCHEMA_V4` rewritten with the correct trigger pattern (for new installs).
- New **schema v5** migration drops + recreates the broken triggers on
  databases already at v4. Bumps `schema_meta.version` to `5`. Idempotent.

### Verification

`/tmp/hotfix_check.py` proves: previously-stuck `memory_delete` now succeeds;
fresh save→delete round-trip works; FTS index correctly drops the row
(post-delete search returns 0); pre-existing memories remain searchable
(no regression).

---

## [0.5.0] — 2026-04-27

Two ergonomic upgrades from using v0.4 in anger.

### Added

- **FTS5 full-text search for memories.** `memory_search` now uses SQLite's
  built-in FTS5 virtual table with bm25 ranking, replacing the previous
  `LIKE %query%` scan. Plain queries are tokenised + prefix-matched
  (`PageRank graph` → `PageRank* graph*`); inputs containing FTS5 operators
  (`"`, `*`, `:`, `(`, `)`, `AND`/`OR`/`NOT`/`NEAR`) pass through unchanged
  for power users (`"exit code" OR sigterm`). Rankings blend bm25 with the
  recency × frequency composite from v0.4.
- **Filterable `agent_session_list`.** Optional arguments:
  - `runtime_id` — exact match (`"claude-code"`).
  - `cwd_prefix` — prefix-match the working directory.
  - `state` — `"running"` (ended_at IS NULL) or `"finished"`.
  - `exit_code` — exact match (negative for signal kills, e.g. `-15` =
    SIGTERM, per the v0.3 convention).

  All filters combine with AND.

### Storage

- **schema v3 → v4 migration**: creates `memories_fts` (FTS5 virtual table)
  with `unicode61 remove_diacritics 2` tokeniser; INSERT/UPDATE/DELETE
  triggers keep it in sync with the base table; backfills the index from
  every existing memory row at upgrade time. Idempotent.

### Tools surface

| Group        | Count | Change |
|--------------|------:|-------|
| Notify       | 3 |  |
| Terminal     | 3 |  |
| Browser      | 5 |  |
| Agent        | 5 | (`agent_session_list` gains 4 filter args) |
| Worktree     | 3 |  |
| Memory       | 6 | (`memory_search` now FTS5-backed) |
| **Total**    | **25** | (no new tools — both upgrades are in-place) |

### End-to-end verification

`/tmp/v05_smoke.py`:

1. `memory_search "AiOT"` → 1 hit, `lesson_aiot_not_to_reuse`, score 3.32
2. `memory_search "PageRank graph"` → 2 hits, top is the lesson, score 3.11
3. `memory_search '"exit code"'` (quoted phrase, operator path) → 2 hits
4. `memory_search "Claude"` → 3 hits, top is `lesson_mcp_session_param_routing`
   because bm25 ranks the most-frequent "Claude Code" mentions higher
5. `memory_search "zzznonexistent"` → 0 hits ✅
6. `agent_session_list state=running` → returns running fakes
7. `agent_session_list cwd_prefix=/tmp/v05a` → only those rows
8. `agent_session_list runtime_id=codex` → 0 (correct empty)
9. `agent_session_list runtime_id=claude-code state=running` → AND combo
10. `agent_session_list exit_code=-15 cwd_prefix=/tmp/v05` after kills →
    matches the SIGTERMed bucket ✅

### Known FTS5 corner

The default `unicode61` tokeniser treats `_` as a token char, so
`v0.4.0_birth` tokenises to `["v0", "4", "0_birth"]`. Searching for `birth`
alone won't match — search for `0_birth` or just words from the body
(the content text is fully indexed). A future v0.6 may switch to the
`trigram` tokeniser if substring search becomes important.

---

## [0.4.0] — 2026-04-27

**Agent self-memory.** Cross-session persistence for the lessons / decisions /
todos / context that Claude (or any MCP-aware agent) accumulates while using
agent-bridge. Inspired by — but deliberately *not* a port of — the cognitive
graph memory in `/Data/CascadeProjects/AiOT`: that system optimises for 256-d
latent embeddings + PageRank-on-graphs at large scale; we want plain notes
indexed by key with optional hyperlink-style relationships, on the order of
a few thousand entries per user-year.

### Added

- **`memory_save(key, kind, content, tags?, related_keys?)`** — upsert one
  note. `key` is stable; same key overwrites content while preserving
  `created_at`. `related_keys` is a JSON array of OTHER memory keys the author
  thinks are causally linked (Web 1.0 hyperlinks, no graph algorithms).
- **`memory_get(key)`** — fetch one row. **Side effect**: atomically bumps
  `access_count` and `last_accessed_at`. This is what gives `memory_search`
  ranking and `memory_compact` something to score against.
- **`memory_search(query, tags_any?, limit?)`** — substring match over `key`
  and `content`, optional tag intersection. Hits are scored
  `recency_weight(30d half-life) + 0.3·ln(1 + access_count)` and ranked.
- **`memory_list(kind?, sort?, limit?)`** — `sort` ∈ `recent | frequent |
  newest`. Use this at session start with `kind="lesson"` to surface what
  previous-you learned.
- **`memory_delete(key)`** — drop one row by key.
- **`memory_compact({min_uses?, older_than_days?, dry_run?})`** — prune
  low-value rows; `dry_run=true` returns the keys that *would* be removed.

### Storage

- **schema v3 migration**: new `memories` table:
  ```
  key TEXT PK, kind TEXT, content TEXT, tags JSON, related_keys JSON,
  created_at, updated_at, last_accessed_at, access_count
  ```
  Indexes on `kind`, `last_accessed_at DESC`, `updated_at DESC`,
  `access_count DESC`. Idempotent migration — bumps `schema_meta.version`
  to `3`; v2 databases upgrade in place at next open.
- `MEMORY_CONTENT_CAP = 256 KiB` per row, clamped at write time.

### Why not graph + PageRank?

We considered AiOT's GraphMemoryBridge wholesale. Three things ruled it out:

1. **Quantitative**: PageRank is a power-law algorithm; on a few-thousand-node
   "graph" every node is "cold", the algorithm collapses to noise.
2. **Intent mismatch**: Claude reaches for memory via keyword recall ≫ graph
   walks ≫ vector similarity. SQL `LIKE` covers 90% of real lookups.
3. **Cross-language cost**: AiOT is Python + Rust FFI. agent-bridge's
   "zero system dependency" promise would die.

Verdict: keep the *idea* of recency decay + access-count weighting +
explicit relationships, ditch the algorithms.

### Tools surface

| Group        | Count | New |
|--------------|------:|-----|
| Notify       | 3 |  |
| Terminal     | 3 |  |
| Browser      | 5 |  |
| Agent        | 5 |  |
| Worktree     | 3 |  |
| **Memory**   | **6** | **all of `memory_*`** |
| **Total**    | **25** | (was 19 in v0.3.0) |

### End-to-end verification

`/tmp/v04_smoke.py` drives a fresh `agent-bridge mcp` subprocess through the
full lifecycle:

1. `tools/list` → 25 tools, the 6 `memory_*` present.
2. `memory_save` × 3 (lesson + decision + todo with cross-references).
3. `memory_get` twice on the lesson → `access_count` went `0 → 1 → 2`.
4. `memory_search "exit_code"` → ranked the lesson first (score 1.330).
5. `memory_search "v0" tags_any=["v0.3"]` → tag intersection works.
6. `memory_list sort=frequent` → lesson (ac=2) tops decision/todo (ac=0).
7. `memory_compact min_uses=10 dry_run=true` → reports 3 would-delete keys.
8. `memory_get` confirms dry-run preserved the data.
9. `memory_delete` × 3 → `{deleted: true}` for all.
10. Final `memory_get` → `null`. Clean. ✅

---

## [0.3.0] — 2026-04-26

Two ergonomic upgrades that came straight out of using v0.2 in anger.

### Added

- **`agent_kill`** — send SIGTERM to a running session. The background wait
  task still finalises the session row with the resulting exit code, so a
  killed session remains queryable via `agent_session_get` (with whatever
  partial stdout/stderr was captured up to the kill point).
- **MCP image content block** — `ContentBlock::Image { data, mimeType }` per
  MCP 2024-11-05 spec; `ToolResult::image` / `image_with_caption` helpers.
- **`browser_screenshot inline=true`** now returns the PNG as a real MCP
  image block (Claude renders it directly into context) plus a one-line
  text caption — instead of a `data:image/png;base64,…` string.

### Changed

- `ClaudeCodeRuntime` keeps a `DashMap<SessionId, pid>` of live children;
  the wait task removes entries on exit. This is the substrate `kill` uses.
- Exit codes recorded by the store now encode signal-killed sessions as
  **negative** numbers (e.g. `-15` for SIGTERM, `-9` for SIGKILL). On Unix
  `std::process::ExitStatus::code()` returns `None` for signal kills, so
  this is the agreed convention to keep the `exit_code` column non-null
  when something *did* happen.

### Tools surface

| Group        | Count | New |
|--------------|------:|-----|
| Notify       | 3 |  |
| Terminal     | 3 |  |
| Browser      | 5 | (`browser_screenshot inline=true` now returns image block) |
| **Agent**    | **5** | **`agent_kill`** |
| Worktree     | 3 |  |
| **Total**    | **19** | (was 18 in v0.2.0) |

### End-to-end verification

`/tmp/v03_smoke.py` drives a fresh `agent-bridge mcp` subprocess:

1. `browser_navigate` + `browser_screenshot inline=true` →
   2 content blocks: `image/png` (17 634 raw bytes, ~23 KB base64) +
   text caption ✅
2. `agent_spawn` → fake-claude blocker (`bash -c "echo …; sleep 30"`) →
   `agent_session_get` confirms `ended_at == null` (running) →
   `agent_kill` returns `SIGTERM sent` →
   `agent_session_wait` returns within milliseconds with `exit_code = -15`,
   captured stdout intact ✅
3. Second `agent_kill` on the same id → `NotFound` error (idempotent) ✅

---

## [0.2.0] — 2026-04-26

Closes the `agent_spawn` loop. Sub-agent stdout / stderr / exit_code are now
persisted to SQLite; three new MCP tools let the parent agent (and the human)
introspect every session that ever ran.

### Added

- **`agent_session_list(limit?)`** — newest-first summary of all sessions
  (id / runtime / cwd / started_at / ended_at / exit_code, plus stdout/stderr
  byte counts). stdout/stderr bodies omitted from this listing for token
  economy.
- **`agent_session_get(id)`** — full row including the captured stdout and
  stderr (each clamped to 64 KiB).
- **`agent_session_wait(id, timeout_secs?)`** — blocks (polls every 500 ms,
  default 60 s, max 600 s) until the session finishes; returns the final row
  on success, or `timed_out=true` plus the in-flight row on timeout.

### Changed

- `ClaudeCodeRuntime` accepts an optional [`StateStore`] (`with_store`). When
  attached it writes an in-flight row at spawn and an UPDATE with
  exit_code / stdout / stderr after the child exits.
- `StateStore::list_sessions` now takes a `limit` (was unbounded).

### Storage migration

- **schema v1 → v2**: `sessions` gains `exit_code INTEGER`, `stdout TEXT`,
  `stderr TEXT` columns. Migration is idempotent — existing rows keep their
  data and get NULL values for the new columns. Bumps `schema_meta.version`
  to `2`.

### Tools surface

| Group        | Count | Names |
|--------------|------:|-------|
| Notify       | 3 | `notify`, `notifications_recent`, `osc_parse` |
| Terminal     | 3 | `terminal_list`, `terminal_send_keys`, `terminal_split` |
| Browser      | 5 | `browser_navigate`, `browser_eval`, `browser_snapshot`, `browser_click`, `browser_screenshot` |
| **Agent**    | **4** | `agent_spawn`, **`agent_session_list`**, **`agent_session_get`**, **`agent_session_wait`** |
| Worktree     | 3 | `worktree_list`, `worktree_create`, `worktree_remove` |
| **Total**    | **18** | (was 15 in v0.1.0) |

### End-to-end verification

End-to-end Python harness (`/tmp/v02_smoke.py`) drives a fresh `agent-bridge
mcp` subprocess with `AGENT_BRIDGE_CLAUDE_BIN=/usr/bin/echo` (no API tokens
spent), proves:

1. `initialize` → server reports `agent-bridge / 0.1.0`
2. `tools/list` → 18 tools registered, the 3 new `agent_session_*` present
3. `agent_spawn` → returns session id, child runs to completion
4. `agent_session_wait` → returns `timed_out=false` + final row including
   `exit_code=0` and `stdout="-p this prompt becomes echo's argument\n"`
5. `agent_session_list` / `agent_session_get` → roundtrip same row

---

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
