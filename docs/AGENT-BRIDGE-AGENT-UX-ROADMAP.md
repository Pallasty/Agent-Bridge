# Agent-Bridge 智能体体验与可运维性 — 实施路径

> 来源：对当前架构的回顾与改进建议（与 `docs/PHASE-D-roadmap.md` 互补：Phase D 偏「能力缺口」，本文偏「谁读文档、谁排障、记忆拓扑迁移、安全默认」）。
>
> 状态：**部分已落地**（A–C 完成；D2/E 待办）· 2026-05-02

---

## 0. 用语：「使用者」指谁？

| 语境 | 主要指 | 智能体角色 |
|------|--------|------------|
| **文档 §「使用者应如何调 `memory_search`」** | 配置/运维 **人类**（选 fts / hybrid / semantic、调 threshold） | 通过同一说明 + MCP schema 间接受益；检索调用仍由模型发起 |
| **「智能体应内化分层边界」**（如 EVOLUTION-CORE） | **AI/智能体** 作为行为主体 | 直接受众 |

先前对话里第 3 点（嵌入上限透明）中的「使用者」**默认指人类运维**；智能体依赖清晰文档与 `capabilities`，避免因误期望云端 embedding 而选错检索模式。

---

## 1. 已纳入共识的建议（摘要）

1. **可观测性**：daemon / MCP 链路的结构化错误与近期失败摘要（与现有 `backend_id`、可扩展的 `hook_status` 互补）。
2. **图与导出**：`memory_export` 不含边；需可选「边导出 / import 后按规则补边」降低拓扑丢失成本。
3. **语义向量说明**：内置 512 维特征哈希（`embed_text`）与云端 embedding 的差异、适用规模、三模式选型表 — **人类 + 智能体** 共读的单一事实源（README + 本文互链）。
4. **多前端行为矩阵**：Warp / Claude Code 等与同一 MCP 的差异表（可随版本生成或挂 `capabilities` 扩展字段）。
5. **高能力面安全默认**：`agent_spawn`、终端注入、CDP 等路径的 opt-in / allowlist 故事（长期）。

---

## 2. 分阶段实施路径

### Phase A — 文档与记忆注入（本仓库可立即交付）

| ID | 交付物 | 验收 |
|----|--------|------|
| A1 | README「Memory search / embeddings」小节 | 明确 hash 向量、三模式、人类 vs 智能体读者 |
| A2 | `docs/AGENT-BRIDGE-EVOLUTION-CORE.md` 互链与 §8 补充 | 指向本 roadmap + inject 包 |
| A3 | `memory_snapshots/inject/ab_ai_bridge_feedback_v1.jsonl` | 可 `memory_import`；`tags` 含 `ab-feedback` |
| A4 | `memory_snapshots/README.md` 表项更新 | 新 inject 文件可查 |

**依赖**：无代码变更或仅文档。

### Phase B — 记忆拓扑迁移（store + MCP，中小工作量）

| ID | 内容 | 风险 |
|----|------|------|
| B1 | `memory_export` 可选导出 `memory_edges`（第二文件或 JSONL 尾段约定） | 需约定格式与 `memory_import` 对称 |
| B2 | 或新增 `memory_edges_export` / `memory_edges_import` MCP | API 面增加，更清晰 |

**验收**：导出 → 清空 DB → 导入 → `memory_neighbors` 与导入前一致（集成测试）。

### Phase C — 可观测性（bridge）

| ID | 内容 |
|----|------|
| C1 | 环形缓冲记录最近 N 次 MCP `tools/call` 错误（工具名、简短 message、时间戳） |
| C2 | 新工具 `mcp_recent_errors` 或扩展 `hook_status` JSON |

**验收**：故意触发错误后可在单次调用中读到结构化摘要。

### Phase D2 — 多前端矩阵（文档或生成）

| ID | 内容 |
|----|------|
| D2a | `docs/` 下 Markdown 表维护 Warp vs Claude Code 差异 |
| D2b | 可选：从 `capabilities` 输出嵌套字段减少双处维护 |

### Phase E — 安全与策略（跨版本）

| ID | 内容 |
|----|------|
| E1 | 设计文档：威胁模型 + spawn/exec 建议 allowlist |
| E2 | 配置项（env 或 settings）分阶段落地 |

---

## 3. 与 Phase D（`PHASE-D-roadmap.md`）的关系

- **D1 shell_exec / D2 block API** 解决的是「同步结构化执行与终端输出」— 与本文 **C 可观测性** 可并行。
- **D3.1 语义向量**：仓库已具备 **hash embedding + semantic/hybrid**；Phase D 若引入 **云端 embedding**，本文 **§1 建议 3** 的文档需同步升级为「双轨语义」说明。

---

## 4. 当前进度

| Phase | 状态 |
|-------|------|
| A | **已完成**（2026-05-02）：README「Memory search / embeddings」、`ab_ai_bridge_feedback_v1.jsonl`、`AGENT-BRIDGE-EVOLUTION-CORE` §8.2 互链 |
| B | **已完成**：`memory_export` / `memory_import` 可选 companion `MemoryEdgeExport` JSONL（双文件对称）+ 集成测试 |
| C | **已完成**：`mcp_tool_errors` 表 + stdio `tools/call` 失败写入 + MCP `mcp_recent_errors` |
| D2–E | 未启动；按上表顺序在后续 PR 推进 |
