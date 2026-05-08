# Agent-Bridge — 多前端行为矩阵

> 更新：2026-05-03 · 对应 agent-bridge v0.1.0（commit a319c0b+）
>
> 本文档覆盖同一 MCP server（`~/.local/bin/agent-bridge mcp`）在不同前端客户端下的
> 能力差异。`capabilities` 工具的输出是运行时权威来源；本文为快速参考。

---

## 1. 前端自动检测

`capabilities` 的 `hooks.frontend` 字段通过以下 env var 启发式推断：

| 前端 | 检测依据（任一命中即判定） |
|------|--------------------------|
| `claude-code` | `CLAUDE_SESSION_ID` 或 `CLAUDE_CODE_ENTRYPOINT` |
| `cursor` | `VSCODE_GIT_IPC_HANDLE`、`VSCODE_IPC_HOOK_CLI` 或 `CURSOR_TRACE_ID` |
| `warp` | `TERM_PROGRAM=WarpTerminal`、`WARP_IS_LOCAL_SHELL_SESSION=1` 或 `WARP_HONOR_PS1` |
| `generic` | 以上均不命中 |

---

## 2. 工具能力矩阵

### 2.1 终端工具

`auto_backend` 自 2f14d84 起默认选 PTY；显式 `AGENT_BRIDGE_TERMINAL=warp` 仍走 Warp IPC。

| 工具 | PTY (默认) | Warp (IPC, opt-in) | Claude Code | 其他 CLI |
|------|:----------:|:------------------:|:-----------:|:--------:|
| `terminal_list` | ✅ | ✅ | ⚠️ 仅合成行 | ⚠️ 仅合成行 |
| `terminal_read_output` | ✅ | ✅ | ✅ (tmux/Zellij) | ✅ (tmux/Zellij) |
| `terminal_read_blocks` | ✅¹ | ✅ | ❌² | ❌² |
| `terminal_send_keys` | ✅ | ✅ | ✅ | ✅ |
| `terminal_split` | ✅ | ✅ | ❌² | ❌² |

¹ 需要 shell 端 OSC 133 集成（`agent-bridge shell-init <bash|zsh|fish>`，详见 `docs/SHELL-INTEGRATION-OSC133.md`）。无集成时返回空数组而非错误。

² 非 PTY/Warp 后端缺乏底层接口；调用返回 `"not supported"`。

**检测方式**：`capabilities.terminal.backend`（`pty` / `warp` / `kitty` / `wezterm` / `zellij`）

### 2.2 浏览器工具

| 工具 | 任意前端 | 备注 |
|------|:--------:|------|
| `browser_navigate` | ✅ | 需要 Chrome/Chromium + CDP |
| `browser_eval` | ✅ | 同上 |
| `browser_snapshot` | ✅ | 返回 accessibility tree |
| `browser_screenshot` | ✅ | PNG base64 |
| `browser_click` / `browser_fill_form` | ✅ | |
| `browser_extract_text` | ✅ | |

`AB_ALLOW_BROWSER=false` 可全局禁用。`capabilities.browser.available` 反映当前状态。

### 2.3 记忆工具

| 工具 | 任意前端 | 备注 |
|------|:--------:|------|
| `memory_save` / `memory_get` / `memory_delete` | ✅ | SQLite，与前端无关 |
| `memory_search` (fts / hybrid / semantic) | ✅ | |
| `memory_compact` / `memory_consolidate` | ✅ | |
| `memory_export` / `memory_import` | ✅ | JSONL，含可选边文件 |

### 2.4 代码库工具

| 工具 | 任意前端 | 备注 |
|------|:--------:|------|
| `codebase_index` | ✅ | 首次调用耗时 1–5 秒，结果持久化到 SQLite |
| `codebase_search` (exact) | ✅ | LIKE 子串匹配 |
| `codebase_search` (semantic) | ✅ | 512 维特征哈希向量；词汇重叠时效果好，纯语义描述分数低 |

### 2.5 Shell / 子 Agent

| 工具 | 任意前端 | 限制 |
|------|:--------:|------|
| `shell_exec` | ✅ | `AB_ALLOW_SHELL_EXEC`；默认超时上限 300s |
| `agent_spawn` | ✅ | `AB_ALLOW_AGENT_SPAWN`；需要 `claude` CLI |
| `agent_message` / `agent_inbox` | ✅ | |

### 2.6 会话生命周期

| 工具 | 任意前端 | 备注 |
|------|:--------:|------|
| `session_bootstrap` | ✅ | 触发记忆预取；可传 `semantic_query` 参数 |
| `session_curate` | ✅ | 两阶段记忆提取（explicit markers + lexical scoring） |
| `session_finalize` | ✅ | 重要性衰减 + USER.md 更新 |
| `session_handoff` | ✅ | 生成结构化交接 JSON |
| `session_lifecycle_step` | ✅ | 一键执行 bootstrap/finalize/handoff |

### 2.7 Warp 专属工具

| 工具 | Warp | 其他前端 |
|------|:----:|:--------:|
| `warp_open_tab` | ✅ | ❌ 返回 `"Warp not detected"` |
| `warp_open_window` | ✅ | ❌ |
| `warp_open_settings` | ✅ | ❌ |
| `warp_launch_workflow` | ✅ | ❌ |
| `warp_status` | ✅ | ❌ |

---

## 3. 安全策略（Phase E）

`capabilities.security` 显示当前策略（由 env var 配置，进程生命周期内不变）：

```json
"security": {
  "shell_exec": true,
  "agent_spawn": true,
  "terminal_write": true,
  "browser": true,
  "shell_exec_timeout_max_ms": 300000
}
```

设 `false` 的能力会在工具调用时返回带说明的错误，不影响其他工具。控制粒度：

| 变量 | 影响范围 |
|------|---------|
| `AB_ALLOW_SHELL_EXEC=false` | `shell_exec` |
| `AB_ALLOW_AGENT_SPAWN=false` | `agent_spawn` |
| `AB_ALLOW_TERMINAL_WRITE=false` | `terminal_send_keys` + `terminal_split` |
| `AB_ALLOW_BROWSER=false` | 所有 `browser_*` 工具 |
| `AB_SHELL_EXEC_TIMEOUT_MAX=N` | `shell_exec` 最大超时毫秒数 |

---

## 4. 推荐会话启动序列

```
1. capabilities()                 # 确认后端可用性 + 安全策略
2. session_bootstrap(cwd=..., semantic_query=...) 
                                  # 注入项目上下文 + 触发记忆预取
3. project_detect() + changes_digest()
                                  # 掌握当前 git 状态，避免幻觉路径
```

会话结束：`session_curate()` → `session_finalize()` → 可选 `session_handoff()`。

---

## 5. 已知差异与注意事项

| 场景 | 说明 |
|------|------|
| Warp IPC 断连后 terminal_read_blocks 失败 | `capabilities.terminal.capabilities.warp_ipc_socket_ready` 会变 false；重启 Warp 后重连 |
| Claude Code 内 terminal_list 返回合成行 | Claude Code 没有可枚举的 PTY 列表；返回一行 `{id: "synthetic-0", ...}` |
| `codebase_search(mode=semantic)` 分数低 | 512 维特征哈希，非 LLM embedding；对词汇重叠查询有效，纯意图描述效果有限 |
| `memory_search(mode=semantic)` 同上限制 | 同一 embedding 实现，threshold 建议 0.3–0.5 |
| USER.md 路径 | `~/.local/share/agent-bridge/USER.md`；`session_finalize` 更新 |
