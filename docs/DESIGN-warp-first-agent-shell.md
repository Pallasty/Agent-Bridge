# Warp-First Agent Super Shell — Architecture Blueprint

> Status: **Draft v2** · 2026-04-30
>
> Goal: Make `agent-bridge` + Warp the **best Linux CLI Agent workstation**,
> matching and exceeding macOS cmux capabilities — multi-page management,
> in-window browser, richer permissions, and unified MCP tool plane for
> Claude Code / Gemini / any CLI Agent.
>
> v2 adds: Agent-perspective capability gap analysis (§3.1), **11** new MCP tools
> (see §7), and an expanded 8-week roadmap integrating perception + continuity needs.
>
> **Implementation note (2026-05-01):** `terminal_read_output` and per-backend
> `TerminalBackend::read_output` are **shipped** for Kitty, WezTerm, and Zellij;
> Warp uses an **IPC-first** path when `warp-agent-bridge.sock` is available
> (see §9). A dedicated `TerminalCapabilities` Rust trait is still **planned**;
> today the `capabilities` MCP tool exposes `terminal.can_read_output` heuristically.

---

## 1. Product Vision

```
┌─────────────────────────────────────────────────────┐
│                  Warp (CLI shell)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Agent A  │  │ Agent B  │  │   Browser tab    │  │
│  │(Claude)  │  │(Gemini)  │  │ (in-window CDP)  │  │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
│       │              │                 │            │
│       └──────────────┼─────────────────┘            │
│                      │                              │
│            ┌─────────▼──────────┐                   │
│            │   agent-bridge     │                   │
│            │   (MCP 能力总线)    │                   │
│            │   ┌────────────┐   │                   │
│            │   │ Terminal   │   │  list/send/read   │
│            │   │ Browser    │   │  navigate/eval    │
│            │   │ Memory     │   │  save/search/link │
│            │   │ Agent      │   │  spawn/msg/wait   │
│            │   │ Worktree   │   │  create/remove    │
│            │   │ Notify     │   │  desktop alerts   │
│            │   │ Lifecycle  │   │  boot/curate/fin  │
│            │   │ Perceive   │   │  project/changes  │
│            │   │ Plan       │   │  save/load/update │
│            │   └────────────┘   │                   │
│            └────────────────────┘                   │
└─────────────────────────────────────────────────────┘
```

### Why Warp over Alacritty


| Dimension  | Warp                               | Alacritty        |
| ---------- | ---------------------------------- | ---------------- |
| Agent 会话模型 | 内建 (`CLIAgentSessionsModel`, 会话恢复) | 无                |
| MCP 生态     | 内建 provider/watcher/权限/UI          | 无                |
| 多页面管理      | Tabs + Blocks + Split              | 单窗口，需外挂 tmux     |
| 网页内嵌       | 有 WebView 技术栈基础                    | 纯 GPU 终端渲染，无 Web |
| 工具权限模型     | blocklist + autoexecute            | 无                |
| 可扩展性       | Rust workspace，模块化                 | 渲染器定位，API 极简     |


**结论**：Alacritty 是优秀的终端渲染引擎，但不是 Agent 工作台平台。
Warp 已经在「容器层」做了大量 Agent 集成工作，`agent-bridge` 补齐「能力层」即可。

---

## 2. Architecture Layers

```
Layer 4 — CLI Agents        Claude Code · Gemini CLI · Codex · custom
Layer 3 — MCP Capability    agent-bridge (tools + resources + lifecycle)
Layer 2 — Shell Container   Warp (session · tabs · blocks · permissions)
Layer 1 — OS / Kernel       Linux (PTY · D-Bus · CDP · filesystem)
```

### Responsibilities


| Layer                 | Owns                                                                                                | Does NOT own                                            |
| --------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| **Warp (L2)**         | UI · tabs · blocks · MCP server registry · permission gates · session persistence                   | Memory store · curate pipeline · browser CDP · worktree |
| **agent-bridge (L3)** | MCP tool registry · lifecycle orchestration · memory · browser · terminal abstraction · agent spawn | Shell rendering · user input · MCP permission UX        |
| **CLI Agent (L4)**    | Task execution · reasoning · tool selection                                                         | Infrastructure · persistence · display                  |


### Integration Surface (Warp ↔ agent-bridge)


| Channel                 | Direction     | Protocol                                                        |
| ----------------------- | ------------- | --------------------------------------------------------------- |
| MCP stdio               | Warp → bridge | JSON-RPC 2.0 (`tools/call`, `resources/read`)                   |
| Session events          | Warp → bridge | `PluggableNotification` OSC 777 → `session_lifecycle_step`      |
| URL dispatch            | bridge → Warp | `warp://action/*` URL scheme                                    |
| Local IPC (Unix socket) | bridge ↔ Warp | JSON line protocol (`BridgeRequest` / `BridgeResponse`; see §9) |
| Filesystem              | both          | `~/.local/share/agent-bridge/state.db` (SQLite)                 |


---

## 3. Capability Matrix (current → target)


| Capability                   | Current                                                                                                    | Target (Week 8)                                   | Who changes   |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------- | ------------- |
| Multi-page/tab management    | Warp native tabs (no bridge control)                                                                       | `warp_tab_open/close/switch` MCP tools            | bridge        |
| Terminal typing (cross-pane) | Unsupported on Warp                                                                                        | Warp IPC or `warp://` extension                   | bridge + Warp |
| In-window browser            | CDP (external Chromium process)                                                                            | CDP 保留 + Warp WebView 探索                          | bridge        |
| Session lifecycle            | Manual MCP calls                                                                                           | `session_lifecycle_step` 自动编排                     | bridge        |
| Capability introspection     | `capabilities` JSON includes `terminal.can_read_output` (per backend); no `TerminalCapabilities` trait yet | Typed `TerminalCapabilities` on `TerminalBackend` | bridge        |
| Memory/curate pipeline       | ✅ Done (tuned, verified)                                                                                   | Stable                                            | —             |
| Profile comparison tooling   | ✅ Done (`--json-out`)                                                                                      | Stable                                            | —             |
| **Terminal output reading**  | ✅ MCP + backends: Kitty / WezTerm / Zellij; Warp = IPC when served, else unsupported                       | Stable + Warp IPC completion                      | bridge + Warp |
| **Session handoff**          | ❌ Implicit (memory only)                                                                                   | `session_handoff` structured brief                | bridge        |
| **Project detection**        | ❌ Manual grep                                                                                              | `project_detect` auto-scan                        | bridge        |
| **Task plan persistence**    | ❌ IDE-ephemeral                                                                                            | `plan_save/load/update`                           | bridge        |
| **Change digest**            | ❌ Manual git diff                                                                                          | `changes_digest`                                  | bridge        |
| **Context budget**           | ❌ No self-awareness                                                                                        | `context_budget` estimation                       | bridge        |
| **Agent messaging**          | ❌ Fire-and-wait only                                                                                       | `agent_message` / `agent_inbox`                   | bridge        |


### 3.1 Agent-Perspective Capability Gap Analysis

The following gaps were identified from the agent's own operational
experience — real friction points encountered daily in terminal-based
Claude Code sessions.

#### Tier 1 — Daily pain (blocks every session)

`**terminal_read_output`** — Read N lines from a terminal pane.

**Status:** MCP tool `terminal_read_output` and `TerminalBackend::read_output`
are implemented for Kitty, WezTerm, and Zellij. Remaining gap is **Warp**
without the in-repo IPC service: the bridge already **prefers** a local Unix
socket (`read_scrollback` RPC) and falls back to a clear error when the
socket is absent (public `warp://` still cannot fetch scrollback).

```
terminal_read_output(pane_id, last_n_lines=50)
→ { "pane": "...", "lines": ["cargo test ... ok", ...], "truncated": false }
```

Implementation: backend-specific. Zellij: `zellij action dump-screen`. WezTerm:
`wezterm cli get-text`. Kitty: `kitten @ get-text`. Warp: **Unix socket IPC**
to Warp-side adapter (`list_sessions` / `send_text` / `read_scrollback`;
see §9), not URL scheme.

`**session_handoff`** — Structured context brief for the next session.

`session_curate` extracts memories; what's missing is a machine-readable
handoff document that the next agent instance can consume in one read.

```json
{
  "last_task": "tuning curate Pass-2 thresholds",
  "status": "completed, merged to master",
  "pending_items": ["warp integration W1 not started"],
  "key_files_modified": ["curate.rs", "mcp_tools.rs"],
  "active_branch": "master",
  "open_questions": ["Warp pane typing IPC feasibility"],
  "generated_at": "2026-04-30T14:22:00Z"
}
```

Implementation: aggregate `memory_list(kind=todo)` + `memory_list(kind=session_handoff)`

- `git status --porcelain` + `git log -1` into one structured response.

`**project_detect**` — Auto-detect project stack and conventions.

Every new session spends 2–3 minutes on the same reconnaissance:
grep Cargo.toml, read package.json, guess test commands. This should
be a single tool call.

```json
{
  "languages": ["rust"],
  "build_system": "cargo",
  "workspace_members": ["ab-core", "ab-terminal", "ab-browser", ...],
  "test_command": "cargo test --all",
  "lint_command": "cargo clippy --all -- -D warnings",
  "format_command": "cargo fmt --all",
  "git_branch": "master",
  "git_clean": true,
  "recent_commit": "feat: externalize curate Pass-2 tuning"
}
```

Implementation: scan cwd for `Cargo.toml` / `package.json` / `pyproject.toml`
/ `go.mod` / `Makefile`; parse workspace members; detect git state.

#### Tier 2 — Weekly pain (friction across sessions)

`**plan_save` / `plan_load` / `plan_update**` — Persistent task plans.

`memory_save` stores knowledge; task plans need richer structure:
ordered steps, status per step, dependencies. Plans survive session
boundaries so a new agent can resume exactly where the last one stopped.

```
plan_save(plan_id="warp-w1", steps=[
  { "id": "caps-trait",   "desc": "Add TerminalCapabilities", "status": "done" },
  { "id": "caps-warp",    "desc": "Implement for WarpBackend", "status": "in_progress" },
  { "id": "caps-mcp",     "desc": "Expose in capabilities tool", "status": "pending" }
])

plan_load(plan_id="warp-w1")
→ { steps: [...], progress: "1/3 done", next: "caps-warp" }
```

Implementation: new `plans` table in SQLite (`plan_id TEXT, steps_json TEXT, updated_at TEXT`). Lightweight — no new crate needed.

`**changes_digest**` — Agent-friendly git diff summary.

```
changes_digest(scope="working_tree"|"staged"|"last_commit")
→ {
    "files_changed": 3, "insertions": 142, "deletions": 38,
    "summary": [
      { "file": "curate.rs", "change": "+CurateOptions struct, env overrides" },
      { "file": "mcp_tools.rs", "change": "+session_curate threshold args" }
    ]
  }
```

Implementation: `git diff --stat` + `git diff --name-status` parsed into JSON.
Optional: use `git diff` per file and generate one-line summaries heuristically.

`**context_budget**` — Estimate remaining context window capacity.

The agent has no self-awareness of token consumption. In long sessions
this leads to abrupt truncation with no chance to curate/compact.

```
context_budget(model="claude-sonnet-4", conversation_turns=42)
→ { "estimated_tokens_used": 85000, "model_limit": 200000,
    "pct_used": 42.5, "recommendation": "nominal" }
```

Implementation: count approximate tokens from recent conversation text
using a fast heuristic (chars/3.5 for EN, chars/1.5 for CJK). Thresholds:

- < 60%: nominal
- 60–80%: suggest `session_curate`
- > 80%: urgent — trigger handoff

#### Tier 3 — Strategic enhancements

`**agent_message` / `agent_inbox**` — Inter-agent communication.

Current `agent_spawn` + `agent_session_wait` is fire-and-wait. Real
multi-agent collaboration needs runtime message passing.

```
agent_message(to_session="abc-123", payload={ "type": "result", "pr_url": "#142" })
agent_inbox(since="2026-04-30T14:00:00Z")
→ [{ "from": "abc-123", "payload": {...}, "ts": "..." }]
```

Implementation: new `agent_messages` table in SQLite. Poll-based (no
push needed — agents check inbox between tool calls).

`**codebase_index` / `codebase_search**` — Semantic code navigation.

`memory_search` searches knowledge; code navigation relies entirely on
grep/glob. A tree-sitter symbol index + TF-IDF scoring would enable
queries like "where is permission checking handled?" without filename guessing.

Implementation: complex — tree-sitter parsing, index build, ranking.
Candidate for a separate crate (`ab-index`). Long-term high value.

`**error_pattern**` — Negative lesson feedback loop.

Record "tried X, failed because Y" as a negative lesson. Surface
automatically when the agent is about to attempt a similar action.
Builds institutional debugging knowledge over time.

Implementation: extend `memory_save` with `kind=error_pattern` +
`trigger_pattern` field. `memory_suggest` or `session_bootstrap` checks
for matching error patterns before returning.

---

## 4. Eight-Week Roadmap

### Phase A — Foundation + Agent Perception (W1–W3)

**W1: terminal_read_output + TerminalCapabilities**

The highest-pain gap first: let agents read terminal output.

- **Done:** `async fn read_output(&self, pane: &PaneId, lines: usize) -> Result<Vec<String>>`
on `TerminalBackend`, plus MCP tool `terminal_read_output`.
- **Done (non-Warp):** per-backend scrollback:
  - Zellij: `zellij action dump-screen`
  - WezTerm: `wezterm cli get-text`
  - Kitty: `kitten @ get-text`
- **In progress (Warp):** `WarpBackend` tries Unix socket RPC `read_scrollback`
first, then errors if IPC unavailable; URL scheme remains split/new-tab only.
- **Done:** `capabilities` MCP output includes `terminal.can_read_output`
(heuristic: `false` for Warp until IPC path succeeds end-to-end).
- **Todo:** add a first-class `TerminalCapabilities` struct and
`fn capabilities(&self) -> TerminalCapabilities` on `TerminalBackend`
(today flags live only in the MCP `capabilities` tool).
- Files: `ab-terminal/src/lib.rs`, all backend files, `mcp_tools.rs`.

**W2: project_detect + changes_digest**

Let agents understand the project without manual reconnaissance.

- New MCP tool: `project_detect(cwd?)` → scans for `Cargo.toml`,
`package.json`, `pyproject.toml`, `go.mod`, `.git`; returns language,
build system, workspace members, test/lint/format commands, git state.
- New MCP tool: `changes_digest(scope)` where scope ∈
`{working_tree, staged, last_commit, branch_vs_main}`.
Wraps `git diff --stat` + `git diff --name-status` into structured JSON.
- Files: new `crates/bridge/src/project.rs`, `mcp_tools.rs`.

**W3: session_handoff + session_lifecycle_step**

Complete the session continuity story.

- New MCP tool: `session_handoff(conversation_text?, session_id?)`.
Aggregates: pending todos from memory, recent session_handoff records,
`git status --porcelain`, `git log -1 --oneline`, active branch, and
key files modified. Returns a machine-readable JSON handoff brief.
- New MCP tool: `session_lifecycle_step(step, ...)` combining
bootstrap / curate / finalize into one dispatcher.
- Update `ab-precompact-hook.sh` to use `session_lifecycle_step`.
- Files: `mcp_tools.rs`, `hooks/ab-precompact-hook.sh`, README.

### Phase B — Warp-Specific + Plan Persistence (W4–W5)

**W4: Warp-specific MCP tools**

- `warp_open_tab` — `warp://action/new_tab`
- `warp_open_window` — `warp://action/new_window`
- `warp_open_settings` — `warp://action/open_settings_page`
- `warp_launch_workflow` — `warp://action/launch_configuration?…`
- `warp_status` — env detection, opener binary check, oz availability.
- Files: `warp.rs` (URL builders), `mcp_tools.rs` (tool definitions).

**W5: plan_save / plan_load / plan_update + context_budget**

- New `plans` table in SQLite: `plan_id TEXT PK, title TEXT, steps_json TEXT, created_at TEXT, updated_at TEXT`.
- MCP tools:
  - `plan_save(plan_id, title, steps=[{id, desc, status, deps?}])`
  - `plan_load(plan_id)` → steps + progress summary + next action
  - `plan_update(plan_id, step_id, status)` — atomic step status update
- `context_budget(conversation_turns?, text_sample?)` → estimated token
count, model limit, percentage, recommendation enum
(`nominal | suggest_curate | urgent_handoff`).
- Heuristic: EN ≈ chars/3.5, CJK ≈ chars/1.5, mixed ≈ weighted average.
- Files: `ab-store` (new table), `mcp_tools.rs`.

### Phase C — Browser + Multi-Agent + Polish (W6–W8)

**W6: Browser enhancement + agent_message**

- Add `BrowserBackend::extract_text(page) -> String` and
`BrowserBackend::fill_form(page, selector, value)`.
- New MCP tools: `browser_extract_text`, `browser_fill_form`.
- New `agent_messages` table: `id INTEGER PK, from_session TEXT, to_session TEXT, payload_json TEXT, created_at TEXT, read INTEGER`.
- MCP tools:
  - `agent_message(to_session, payload)` — send
  - `agent_inbox(since?, unread_only?)` — receive
- Files: `ab-browser/src/lib.rs`, `chromium_cdp.rs`, `ab-store`,
`ab-agent`, `mcp_tools.rs`.

**W7: Error semantics + graceful degradation**

- `terminal_send_keys` on Warp returns structured
`{ "unsupported": true, "alternatives": ["warp_open_tab", "warp_launch_workflow"] }`.
- `terminal_read_output` on Warp: structured unsupported **only when** local IPC
is unavailable; once Warp hosts the socket service, same tool path succeeds.
- All tool responses carry `"backend_id"` for diagnostics.
- New `kind=error_pattern` support in memory: `memory_save` accepts
optional `trigger_pattern` field. `session_bootstrap` surfaces matching
error patterns in the bootstrap block.

**W8: Integration testing + documentation**

- End-to-end test: `scripts/verify_warp_integration.sh`
  - capability detection (including `can_read_output`)
  - lifecycle step orchestration
  - project_detect + changes_digest
  - session_handoff round-trip
  - plan save/load/update cycle
  - warp_* tools
  - browser tools
  - agent_message send/receive
- Update README: full "Warp-first" tool matrix.
- Update CHANGELOG.
- Publish design doc as `docs/DESIGN-warp-first-agent-shell.md`.

---

## 5. Key Technical Decisions


| #   | Decision                               | Rationale                                                                      |
| --- | -------------------------------------- | ------------------------------------------------------------------------------ |
| D1  | Warp 作为 Agent 工作台外壳，不用 Alacritty       | Warp 已有会话/MCP/权限模型；Alacritty 是渲染器，能力层全部要自建                                     |
| D2  | `agent-bridge` 保持终端后端抽象                | 避免 Warp 锁定；Kitty/Zellij/WezTerm 作为 fallback                                    |
| D3  | 生命周期通过 MCP 工具编排，不依赖 hook               | Warp 无 hook 事件；MCP 工具更通用                                                       |
| D4  | 浏览器保持 CDP 方案                           | in-process WebView 依赖 Warp 内部，短期不可控；CDP headless 已可用                           |
| D5  | session_curate 参数已定标 balanced          | 0.50/0.58 经真实 transcript 对比验证                                                  |
| D6  | 能力粒度显式化（TerminalCapabilities）          | 让 Agent 自动适配不同终端后端行为差异；**进展：`**capabilities` 已暴露 `can_read_output`，trait 收口仍待办 |
| D7  | JSON 对比报告支持长期趋势追踪                      | `--json-out` 可持久化，便于调参回归                                                       |
| D8  | terminal_read_output 列为最高优先级           | Agent 感知能力的基石；多 Agent 协作的前提                                                    |
| D9  | session_handoff 聚合现有数据，不新建存储           | 组合 memory + git status + git log，零新依赖                                          |
| D10 | project_detect 纯文件系统扫描，不引入 tree-sitter | 首版保持轻量；tree-sitter 留给 codebase_index (Tier 3)                                  |
| D11 | plan 持久化用 SQLite 新表，不复用 memory 表       | plan 有结构化步骤/状态语义，和自由文本 memory 不同                                               |
| D12 | context_budget 用字符启发式估算，不接入模型 API      | 快速、离线、零成本；精度够用（误差 < 15%）                                                       |
| D13 | agent_message 用 SQLite 轮询，不引入 IPC      | 简单可靠；Agent 在 tool call 间隙自然轮询 inbox                                            |
| D14 | codebase_index 推迟到 Phase D（W9+）        | 高价值但实现复杂；tree-sitter + 索引需独立 crate                                             |


---

## 6. Risk Register


| Risk                     | Likelihood | Impact | Mitigation                                                |
| ------------------------ | ---------- | ------ | --------------------------------------------------------- |
| Warp 未公开 pane typing IPC | 高          | 中      | 先返回结构化 unsupported + 替代方案；中期探索 warp:// 扩展                 |
| Warp 未公开 pane 输出读取 IPC   | 高          | 高      | bridge 侧 IPC 客户端已就绪；需 Warp 进程内服务落地后才能在 Warp 上读 scrollback |
| Warp 内部 WebView 不可外部驱动   | 中          | 中      | 保持 CDP (external Chromium) 路线；WebView 仅作探索                |
| Warp 闭源，API 变化不可控        | 中          | 高      | 抽象层隔离；保留 multi-backend fallback                           |
| 多 Agent 并发 MCP 冲突        | 低          | 中      | MCP tool 内部 session_id 隔离 + SQLite WAL                    |
| context_budget 估算偏差过大    | 低          | 低      | 保守阈值 (60% warn)；可校准                                       |
| plan 表与 memory 表职责模糊     | 中          | 低      | 明确语义边界：plan=结构化步骤 memory=自由文本知识                           |


---

## 7. New Tool Summary (11 tools planned in v2)


| Tool                     | Phase | Category       | Description                                    |
| ------------------------ | ----- | -------------- | ---------------------------------------------- |
| `terminal_read_output`   | A/W1  | Perception     | Read last N lines from a terminal pane         |
| `project_detect`         | A/W2  | Perception     | Auto-detect project language, build, git state |
| `changes_digest`         | A/W2  | Perception     | Agent-friendly git diff summary                |
| `session_handoff`        | A/W3  | Continuity     | Structured context brief for next session      |
| `session_lifecycle_step` | A/W3  | Lifecycle      | Unified start/precompact/end dispatcher        |
| `plan_save`              | B/W5  | Planning       | Persist structured task plan                   |
| `plan_load`              | B/W5  | Planning       | Restore plan with progress summary             |
| `plan_update`            | B/W5  | Planning       | Atomic step status update                      |
| `context_budget`         | B/W5  | Self-awareness | Estimate token usage + recommendation          |
| `agent_message`          | C/W6  | Multi-agent    | Send message to another agent session          |
| `agent_inbox`            | C/W6  | Multi-agent    | Read messages from other agents                |


(Plus 4 Warp-specific tools from v1: `warp_open_tab`, `warp_open_window`,
`warp_open_settings`, `warp_launch_workflow`, `warp_status`.)

---

## 8. Success Criteria (Week 8)

### Phase A gate (end of W3)

- `terminal_read_output` works on Zellij + WezTerm + Kitty
- `terminal_read_output` works on Warp (IPC server in Warp + E2E smoke)
- `project_detect` correctly identifies Rust/Node/Python/Go projects
- `changes_digest` produces structured JSON for all scopes
- `session_handoff` returns a machine-readable brief with git + memory data
- `session_lifecycle_step` dispatches all three phases

### Phase B gate (end of W5)

- `warp_*` tools work from inside Warp terminal
- `plan_save/load/update` persists across sessions
- `context_budget` returns estimates within 15% of actual token count

### Phase C gate (end of W8)

- `browser_extract_text` and `browser_fill_form` available
- `agent_message` + `agent_inbox` enable basic two-agent coordination
- Error patterns surfaced in `session_bootstrap` output
- `scripts/verify_warp_integration.sh` covers all new tools
- README "Warp-first" section documents full 50+ tool matrix
- All tool responses include `backend_id` for diagnostics

### Future (Phase D, W9+)

- `codebase_index` / `codebase_search` with tree-sitter (new `ab-index` crate)
- Warp WebView as alternative `BrowserBackend`
- Vector embedding search in `memory_search`

---

## 9. Warp In-Repo Migration Status

### 9.1 What was migrated now

We started direct in-repo migration inside the open-source Warp tree at:

- `warp/crates/agent_bridge/`

Initial crate includes:

- `src/lib.rs`:
  - `default_ipc_socket_path()` helper (`$XDG_RUNTIME_DIR/warp-agent-bridge.sock`)
- `src/protocol.rs`:
  - `BridgeRequest` / `BridgeResponse` envelopes
  - `BridgeError`
  - `TerminalSession`
  - `ReadScrollbackParams`
  - `AgentBridgeBackend` trait with:
    - `list_sessions`
    - `send_text`
    - `read_scrollback`

This is a **protocol-first adapter skeleton** that keeps migration traceable
without coupling immediately to Warp UI internals.

In parallel, `agent-bridge` side has now moved to **IPC-first Warp backend**
for the three key operations:

- `list_panes` → tries Unix socket RPC `list_sessions` first, then synthetic fallback
- `send_keys` → tries RPC `send_text`, returns structured unsupported only if IPC unavailable
- `read_output` → tries RPC `read_scrollback`, returns unsupported if IPC unavailable

This completes milestone 3 at the client side ("IPC preferred + URL fallback")
and unblocks Warp-side server implementation as the next critical step.

### 9.2 Recommended target layout in Warp repo

Primary location:

- `warp/crates/agent_bridge/` (adapter crate)

Optional split for long-term protocol versioning:

- `warp/crates/agent_bridge_ipc/` (serde protocol types + version negotiation)

Why this layout:

- Aligns with Warp's Rust workspace architecture (`crates/`*)
- Avoids over-coupling to `app/src` view/UI code
- Supports feature-gating and independent tests
- Makes upstream sync easier (external `agent-bridge` core + Warp-specific adapter)

### 9.3 Next migration milestones

1. Implement Warp-side backend for `AgentBridgeBackend`:
  - map active/internal terminal sessions to `TerminalSession`
  - wire text send path via existing terminal input routing APIs
  - expose scrollback read from terminal model
2. Add local IPC service in Warp (Unix socket):
  - methods: `list_sessions`, `send_text`, `read_scrollback`
3. Validate end-to-end with IPC enabled:
  - `agent-bridge` should auto-detect socket and stop falling back
  - add integration smoke test for list/send/read roundtrip

---

## 9. Warp In-Repo Migration Status

### 9.1 What was migrated now

We started direct in-repo migration inside the open-source Warp tree at:

- `warp/crates/agent_bridge/`

Initial crate includes:

- `src/lib.rs`:
  - `default_ipc_socket_path()` helper (`$XDG_RUNTIME_DIR/warp-agent-bridge.sock`)
- `src/protocol.rs`:
  - `BridgeRequest` / `BridgeResponse` envelopes
  - `BridgeError`
  - `TerminalSession`
  - `ReadScrollbackParams`
  - `AgentBridgeBackend` trait with:
    - `list_sessions`
    - `send_text`
    - `read_scrollback`

This is a **protocol-first adapter skeleton** that keeps migration traceable
without coupling immediately to Warp UI internals.

In parallel, `agent-bridge` side has now moved to **IPC-first Warp backend**
for the three key operations:

- `list_panes` → tries Unix socket RPC `list_sessions` first, then synthetic fallback
- `send_keys` → tries RPC `send_text`, returns structured unsupported only if IPC unavailable
- `read_output` → tries RPC `read_scrollback`, returns unsupported if IPC unavailable

This completes milestone 3 at the client side ("IPC preferred + URL fallback")
and unblocks Warp-side server implementation as the next critical step.

### 9.2 Recommended target layout in Warp repo

Primary location:

- `warp/crates/agent_bridge/` (adapter crate)

Optional split for long-term protocol versioning:

- `warp/crates/agent_bridge_ipc/` (serde protocol types + version negotiation)

Why this layout:

- Aligns with Warp's Rust workspace architecture (`crates/`*)
- Avoids over-coupling to `app/src` view/UI code
- Supports feature-gating and independent tests
- Makes upstream sync easier (external `agent-bridge` core + Warp-specific adapter)

### 9.3 Next migration milestones

1. Implement Warp-side backend for `AgentBridgeBackend`:
  - map active/internal terminal sessions to `TerminalSession`
  - wire text send path via existing terminal input routing APIs
  - expose scrollback read from terminal model
2. Add local IPC service in Warp (Unix socket):
  - methods: `list_sessions`, `send_text`, `read_scrollback`
3. Validate end-to-end with IPC enabled:
  - `agent-bridge` should auto-detect socket and stop falling back
  - add integration smoke test for list/send/read roundtrip

