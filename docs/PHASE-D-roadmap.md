# Phase D Roadmap — agent-bridge

> Status: **D1–D3.2 完成** · 2026-05-03 · D3.3 延期（Warp WebView 架构评估后决策）
>
> Baseline: W1–W8 全部完成并验证。Warp IPC 通道可用，50+ MCP 工具可用。
> Phase D 目标: 补齐「同步命令执行」「结构化终端输出」「语义记忆搜索」三个核心缺口。
>
> **See also:** `docs/AGENT-BRIDGE-AGENT-UX-ROADMAP.md` — agent/operator UX,
> memory-graph export, observability, multi-frontend matrix, security phases **A–E**
> (complementary to D1–D3 here).

---

## 优先级矩阵

| 任务 | 影响 | 工作量 | 优先级 | 状态 |
|------|------|--------|--------|------|
| D1.1 shell_exec 工具 | 高 | 低 | **最高** | ✅ 完成 |
| D1.2 warp_open_tab → session UUID | 中高 | 低中 | **高** | ✅ 完成 |
| D2.1 Warp block-level API | 高 | 中 | **高** | ✅ 完成 |
| D2.2 USER.md 用户画像合成 | 中 | 低 | **中** | ✅ 完成 |
| D2.3 Per-turn 记忆预取 | 中 | 低中 | **中** | ✅ 完成 |
| D3.1 语义向量搜索 | 高 | 高 | **中高** | ✅ 完成 |
| D3.2 codebase_index / codebase_search | 高 | 高 | **中高** | ✅ 完成 |
| D3.3 Warp WebView BrowserBackend | 中 | 高 | **低中** | ⏸ 延期 |

---

## D1 — 快速收益（各 ≤ 2 天）

### D1.1 shell_exec 工具

**动机**：`terminal_send_keys` + `terminal_read_output` 是异步 PTY 通道；Agent 无法同步得到
结构化的 exit_code/stdout/stderr。每次跑 `cargo test` 都要猜输出在哪里结束。

**接口**:
```json
// 调用
{"cmd": "cargo test --lib", "cwd": "/Data/CascadeProjects/agent-bridge", "timeout_ms": 60000}

// 返回
{"exit_code": 0, "stdout": "...", "stderr": "...", "duration_ms": 4321, "truncated": false}
```

**实现**:
- `crates/bridge/src/mcp_tools.rs` — 新增 `ShellExecTool`
- `tokio::process::Command::new("sh").arg("-c").arg(cmd)` + `.stdout(Stdio::piped())` + `.stderr(Stdio::piped())`
- `timeout_ms` 默认 30000，上限 300000
- stdout/stderr 超过 128KB 时截断并设 `truncated: true`
- 注册到 `tool_registry()` 列表

**回归测试**: `verify_warp_integration.sh` 不需要改动（不涉及 Warp IPC）

---

### D1.2 warp_open_tab 返回 session UUID

**动机**：当前 `warp_open_tab` 发送 `warp://action/open-tab?cwd=...` URI，Warp 打开新 tab，
但 MCP 工具立刻返回而不知道新 tab 的 session_id，Agent 无法立即向新 tab 发命令。

**修复方案**（两步）:

1. **Warp fork 侧** (`app/src/agent_bridge/server.rs`):
   - 新增 IPC 消息 `{"action": "open_tab", "cwd": "...", "title": "..."}` → `{"session_id": "<uuid>"}`
   - 在 `handle_request()` 中调用 `cx.update(|cx| warp_tab_manager.open_tab(cwd, title, cx))` 并等待新 session 注册到 `AgentBridgeRegistry`

2. **agent-bridge 侧** (`crates/bridge/src/mcp_tools.rs`):
   - `WarpOpenTabTool::execute()` 改为调用 IPC `open_tab` 消息
   - 将返回的 `session_id` 写入 `ToolResult`

**替代方案**（现在可用）：用 `terminal_split` — 同步返回新 pane UUID，功能等价。

---

## D2 — 中期（各 3–7 天）

### D2.1 Warp block-level API

**动机**：`terminal_read_output` 返回原始滚动缓冲文本；Agent 需要自己解析 prompt、命令、输出边界。
Warp 内部已有 `Block` 数据结构存储每个命令的结构化信息。

**接口**（新 MCP 工具 `terminal_read_blocks`）:
```json
// 调用
{"session_id": "...", "since_block": 5, "limit": 20}

// 返回
[
  {"block_idx": 6, "cmd": "cargo build", "output": "...", "exit_code": 0,
   "start_ms": 1746192000000, "end_ms": 1746192004321}
]
```

**Warp fork 修改**:
- `server.rs` 新增 `read_blocks` IPC 消息处理
- 从 `AgentBridgeRegistry::get_session()` 取到 `Arc<FairMutex<TerminalModel>>`，读取 Block 列表

**agent-bridge 修改**:
- `mcp_tools.rs` 新增 `TerminalReadBlocksTool`
- 协议扩展: `protocol.rs` 新增 `ReadBlocksRequest` / `ReadBlocksResponse`

---

### D2.2 USER.md 用户画像合成

**动机**：借鉴 Hermes Agent 的 USER.md 模式。Agent 每次会话都要从零认识用户。

**实现**:
- `session_finalize` 工具末尾，LLM 调用生成/更新 `~/.local/share/agent-bridge/USER.md`
- 字段: `name`, `role`, `expertise_areas`, `preferences`, `communication_style`, `recent_focus`, `updated_at`
- `session_bootstrap` 时读取并注入为 `<user_profile>` 系统上下文

**USER.md 示例**:
```markdown
# User Profile
- **Name**: pallasting
- **Role**: 独立开发者 / 系统工程师
- **Expertise**: Rust, Linux 系统编程, LLM 工具链, Warp 终端
- **Preferences**: 简洁回答，不重复总结，中文交流
- **Recent focus**: agent-bridge Warp IPC 集成，Phase D 路线图规划
- **Updated**: 2026-05-02
```

---

### D2.3 Per-turn 记忆预取

**动机**：Hermes Agent 的核心创新：隐式重要性评估 + 非阻塞预取，消除记忆检索延迟。

**实现**:
```rust
// session_bootstrap 完成后立即后台执行
let prefetch = Arc::new(Mutex::new(None::<Vec<MemorySuggestion>>));
let p = prefetch.clone();
tokio::spawn(async move {
    let suggestions = memory_suggest(project_context).await.ok();
    *p.lock().await = suggestions;
});
```
- 第一次调用 `memory_search` 时先检查 prefetch 槽，命中则 0 延迟

---

## D3 — 长期（各 1–2 周）

### D3.1 语义向量搜索 ✅

**最终落地**（2026-05-03）：
1. `crates/store/src/vector.rs` — `embed_text()` + `cosine_similarity()`，运行时双 backend
2. **嵌入后端**：`fastembed 5` 包 `all-MiniLM-L6-v2` ONNX，384-dim 句向量；ORT 静态链接 38 MB；模型 ~22 MB 首次自动下载到 `~/.cache/fastembed/`。`onnx-embed` feature 关闭时回落 FNV-1a hash（同 384-dim）
3. SQLite `memories.embedding BLOB` 列（schema v12）+ `codebase_symbols.embedding`（v15）
4. v16 migration 清空 512-dim 旧向量；新增 `memory_reindex` MCP 工具批量重建
5. `memory_search` 三模式：fts / hybrid / **semantic**（threshold 0.3=宽，0.7=紧；ONNX 真语义下相关结果分数典型 0.5–0.75）

**性能**（实测）：
- `memory_save`: ~55 ms（embed 50 ms + SQL 5 ms）
- `memory_search(semantic)`: ~25 ms（embed query + cosine over in-memory cache）
- `memory_search(fts)`: ~15 ms（不变）
- 模型首次加载：~1 s（每个 MCP 进程仅一次）

**未做**：
- `hnsw` 索引（当前 ~280 条记忆线性扫足够）
- 远程 embedding API（无外部依赖是显式目标）

**长期方向**：抽 `EmbeddingBackend` trait，未来可换 AIoT Rust Seed 神经网络（见 `docs/AGENT-BRIDGE-EVOLUTION-CORE.md` §8.4）

---

### D3.2 codebase_index / codebase_search

**动机**：Agent 阅读大型代码库需要逐文件读取，效率低。符号索引可直接定位定义。

**接口**:
```json
// codebase_index
{"path": "/Data/CascadeProjects/agent-bridge", "languages": ["rust"]}
// → {"indexed_files": 47, "symbols": 1203, "duration_ms": 2100}

// codebase_search  
{"query": "TerminalBackend", "kind": "trait", "limit": 10}
// → [{"file": "crates/bridge/src/terminal.rs", "line": 23, "kind": "trait", "name": "TerminalBackend", "signature": "pub trait TerminalBackend: Send + Sync"}]
```

**实现**: `tree-sitter-rust` crate + SQLite FTS5 符号表

---

### D3.3 Warp WebView BrowserBackend

**动机**：当前 BrowserBackend 需要外部 Chrome 进程 + CDP。Warp 有内建 WebView 技术栈。

**实现**: Warp IPC 新增 `browser_*` 消息族，路由到 Warp WebView；
agent-bridge `BrowserBackend` trait 新增 `WarpWebViewBackend` 实现。

---

## 执行顺序

```
D1.1 shell_exec ──────────────────────────────► merge
D1.2 warp_open_tab UUID ─────────────────────► merge
D2.1 Warp blocks ────────────────────────────► merge
D2.2 USER.md ────────────────────────────────► merge
D2.3 prefetch ───────────────────────────────► merge
D3.1 vector search ──────────────────────────► merge
D3.2 codebase_index ─────────────────────────► merge
D3.3 WebView backend ────────────────────────► merge
```

每个 D1/D2 任务完成后运行 `scripts/verify_warp_integration.sh` 作为回归测试。
