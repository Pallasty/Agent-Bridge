# Agent-Bridge 进化核心（智能体参照记忆）

> 用途：任何挂载 Agent-Bridge MCP 的智能体，可将本文作为**跨会话的架构与行为契约**，结合 `memory_save` / `session_handoff` 写入实例化教训，形成闭环自我改进。  
> 维护：重大行为或 schema 变更时同步更新本文与 `CHANGELOG.md`。

---

## 1. 一句话定位

**Agent-Bridge 是 Unix 原生的 AI 智能体控制面**：桌面通知、跨会话记忆、MCP 工具注册表、终端复用器粘合、浏览器（CDP）、git worktree 编排与子进程智能体——全部通过 **Rust trait 可插拔** 组合到同一 `Hub` 上（README 首段概括）。

---

## 2. 分层职责（谁拥有什么）

来自 `docs/DESIGN-warp-first-agent-shell.md` 的边界划分，智能体应内化：

| 层 | 拥有 | 不拥有 |
|----|------|--------|
| **L4 CLI Agent** | 任务执行、推理、工具选择 | 基础设施、持久化、展示 |
| **L3 agent-bridge** | MCP 工具注册、生命周期编排、记忆、浏览器、终端抽象、子 agent 派生 | Shell 渲染、用户输入、MCP 权限 UI |
| **L2 Shell（如 Warp）** | UI、Tab、MCP 注册、权限门、会话持久 | 记忆存储、curate 管线、CDP、worktree |

**推论**：智能体应把「可审计的长期状态」交给 bridge（SQLite），把「一次性推理」留在上下文；不要假设 IDE 会替你持久化计划或 diff。

---

## 3. 架构锚点：`Hub` 与 trait 束

`Hub` 是运行时后端束，字段全部为可选 `Arc<dyn Trait>`，便于在无显示器、无浏览器等环境降级：

```12:20:crates/bridge/src/hub.rs
#[derive(Clone)]
pub struct Hub {
    pub notifiers: Vec<Arc<dyn Notifier>>,
    pub store: Option<Arc<dyn StateStore>>,
    pub terminal: Option<Arc<dyn TerminalBackend>>,
    pub browser: Option<Arc<dyn BrowserBackend>>,
    pub agent: Option<Arc<dyn AgentRuntime>>,
    pub worktree: Option<Arc<GitWorktreeManager>>,
}
```

**`AgentRuntime`**（子智能体 CLI 抽象）核心契约：

```51:77:crates/agent/src/lib.rs
#[async_trait]
pub trait AgentRuntime: Send + Sync {
    fn id(&self) -> &str;

    async fn spawn(&self, cfg: SpawnConfig) -> Result<AgentSession>;

    async fn send_input(&self, session: &SessionId, text: &str) -> Result<()>;

    async fn kill(&self, session: &SessionId) -> Result<()> {
        Err(ab_core::Error::InvalidArgument(format!(
            "kill not supported by this runtime (session {session})"
        )))
    }

    fn pid_for(&self, _session: &SessionId) -> Option<u32> {
        None
    }

    async fn capabilities(&self) -> AgentCapabilities;
}
```

**自我改进含义**：新 runtime / notifier / backend 应实现相同 trait 语义，而不是在 MCP 层打特例；能力发现统一走 `capabilities` 工具。

---

## 4. 记忆模型（自我进化的数据面）

### 4.1 `MemoryRecord` 语义

```64:96:crates/store/src/lib.rs
pub struct MemoryRecord {
    pub key: String,
    pub kind: String,
    pub content: String,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default)]
    pub related_keys: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub scope: Option<String>,
    pub created_at: i64,
    pub updated_at: i64,
    pub last_accessed_at: i64,
    pub access_count: u64,
    #[serde(default = "default_importance")]
    pub importance: f64,
    #[serde(default = "default_status")]
    pub status: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub trigger_pattern: Option<String>,
}
```

- **`kind`**：业务分类字符串；`session_handoff` 在 bootstrap 排序中被**优先上浮**（跨会话连续性）。
- **`importance`**：按 kind 默认赋值，随 `session_finalize` 衰减；高价值教训应显式提高或定期 `memory_get` 刷新访问统计。
- **`scope`**：`global` / `project:/abs/path` / `domain:tag`（README「Memory scopes」表）— 避免把全局教训锁死在单仓库键下。
- **`memory_get` 副作用**：成功读取会更新 `access_count` / `last_accessed_at`，直接影响排序与压缩—**检索即强化**。

### 4.2 图边与遍历

- `memory_link`：`relates` | `contradicts` | `supersedes` | `derived_from` | `implements`（见 store 注释）。
- `memory_neighbors_bfs`：能量衰减 BFS，边类型带 `temporal_bonus`—用于「从一粒种子记忆点燃相关上下文」。

### 4.3 压缩策略（避免记忆库死寂或爆长）

`CompactPolicy::healthy_default()`：**低访问且陈旧** 才删，并带创建后宽限期（见 `crates/store/src/lib.rs` 内文档）。

---

## 5. 会话连续性与策展（自我进化的控制面）

### 5.1 结构化交接 `session_handoff`

`build_handoff_brief` 聚合：git 快照、`todo` 记忆、`session_handoff` 记忆、可选对话片段—**不新增表**，JSON 即契约：

```11:62:crates/bridge/src/session_handoff.rs
/// Collect a machine-readable handoff brief for the next agent session.
pub async fn build_handoff_brief(
    store: Arc<dyn StateStore>,
    cwd: PathBuf,
    max_todos: u32,
    max_handoff_memories: u32,
    last_task: Option<String>,
    status: Option<String>,
    open_questions: Vec<String>,
    conversation_text: Option<String>,
) -> Result<Value> {
    // ... git snapshot + list_memories(todo) + list_memories(session_handoff) ...
    Ok(json!({
        "last_task": last_task,
        "status": status,
        "pending_items": pending_items,
        "key_files_modified": key_files,
        // ...
        "session_handoff_memories": handoff_notes,
        "conversation_snippet": conversation_snippet,
    }))
}
```

### 5.2 `session_curate` 两阶段管线（摘录）

```1:20:crates/bridge/src/curate.rs
//! ## Pass 1 — explicit markers  (fast, zero-miss on annotated text)
//! Detects line-prefix markers (`lesson:`, `decision:`, …) and section
//! headers (`## Lessons:**`) whose bullet children inherit the kind.
//!
//! ## Pass 2 — implicit lexical scoring  (NEW)
//! Scores every unmarked line against five signal tables
//! (epistemic / normative / causal / decision / todo) using simple
//! substring matching.
```

**实践**：在对话中主动使用 `lesson:` / `decision:` 等标记 = Pass1 零遗漏；依赖模型自由发挥时靠 Pass2 与阈值/去重环境变量调参。

### 5.3 推荐生命周期钩子（智能体侧）

1. **会话开始**：`session_bootstrap` 或 `session_lifecycle_step(bootstrap)` + `capabilities`。
2. **会话中段**：`memory_save` / `plan_save` + `changes_digest` / `project_detect`（保持世界模型与仓库一致）。
3. **会话结束**：`session_curate` → `session_finalize`；必要时 `session_handoff` 写入结构化 JSON；跨机可 `memory_export` / git sync（README「Cross-machine memory sync」）。

---

## 6. MCP 工具分组（README 速查）

智能体应把工具当**能力总线**，而非一次性脚本：

| 组 | 代表工具 | 自我进化用途 |
|----|-----------|----------------|
| **memory_*** | `save` / `search` / `link` / `neighbors` / `consolidate` / `suggest` | 沉淀教训、建图、去冗余 |
| **session_*** | `bootstrap` / `curate` / `finalize` / `handoff` / `lifecycle_step` | 跨会话人格与任务连续 |
| **plan_*** | `save` / `load` / `update` | 可中断工作的可恢复计划 |
| **perceive** | `project_detect` / `changes_digest` | 减少幻觉路径与分支状态 |
| **meta** | `capabilities` / `context_budget` | 自知与环境门控 |
| **agent** / **multi-session** | `agent_spawn` / `agent_message` / `agent_inbox` | 并行与协作进化 |
| **worktree** | `create` / `list` / `remove` | 实验分支隔离 |

完整 60 工具表见根目录 `README.md`。

---

## 7. 可执行的「自我改进」检查清单（给智能体）

每条对应可验证的 MCP 或仓库事实：

1. **环境自知**：每次新会话调用 `capabilities`；终端读屏、浏览器、子 agent 可能缺失—不得假设存在。
2. **上下文预算**：长对话前 `context_budget`，按建议触发压缩或 handoff，而非硬撑全文。
3. **教训外化**：任何「以后别再犯」级结论 → `memory_save`，`kind` 用 `lesson` 或 `decision`，并打 `tags`。
4. **任务连续**：未完成项用 `kind=todo`；会话边界用 `session_handoff` JSON + `session_handoff` kind 记忆双轨（检索优先见 `prioritize_session_handoff`）。
5. **关系化知识**：相关决策 `memory_link`，用 `supersedes` 表达替代关系，便于 `memory_consolidate`。
6. **仓库真相**：改代码前 `changes_digest` + `project_detect`，避免基于陈旧路径推理。
7. **并行实验**：高风险重构 `worktree_create` 隔离，再在主 worktree 合并结论。
8. **收束债务**：定期 `memory_compact` 使用 `healthy_default()` 语义；导出备份见 `memory_snapshots/README.md`（注意：**export 不含边**，重要拓扑需单独 `memory_link` 或图导出工具）。

---

## 8. 与仓库外「记忆库」的关系

- 运行时权威：`~/.local/share/agent-bridge/state.db`（SQLite）。
- 可选 git 备份：私有 companion 仓库 + `sync.sh`（README）。
- **本文档**：语义层契约；变更应通过 PR 审查，避免与实现漂移。

### 8.1 AI 偏好批量注入 + 语义检索

- **注入包**：`memory_snapshots/inject/ab_ai_kernel_v1.jsonl` — 每条为原子卡片，`content` 顶部用 `SIGNAL:` / `FACTS:` / `MUST:` / `KEYWORDS:` 便于模型解析；内嵌英文关键词以配合 **512 维特征哈希向量**（`crates/store/src/vector.rs` 的 `embed_text`，无外部 API）。
- **导入**：`memory_import(..., conflict_policy="skip"|"newer_wins")`；导入路径与 `memory_save` **同样写入 `embedding` 列**，可直接 `memory_search(..., mode="semantic")`。
- **召回**：优先 `tags_any=["ab-inject"]` + `mode="hybrid"`（图扩展）；纯释义对齐用 `mode="semantic"` 调 `threshold`（宽 0.3、紧 0.7 量级，见 MCP `memory_search` 描述）。

### 8.2 智能体体验改进建议（已写入注入包 + 路线图）

- **路线图（分阶段）**：`docs/AGENT-BRIDGE-AGENT-UX-ROADMAP.md` — 说明「使用者」在文档里多指**人类运维**，智能体通过 schema + 同一事实源受益；并列出可观测性、图导出、多前端矩阵、安全默认等 **Phase B–E**。
- **可导入记忆卡片**：`memory_snapshots/inject/ab_ai_bridge_feedback_v1.jsonl` — `tags` 含 `ab-feedback`，与 `ab-inject` 内核包区分；导入后可用 `memory_search(..., tags_any=["ab-feedback"])` 拉取本组建议。

---

## 9. 版本与演进

以 `CHANGELOG.md` 为真相源；引入新 MCP 或破坏 `MemoryRecord` 字段时，必须更新 §4–§6 并考虑 `memory_import` 兼容策略。
