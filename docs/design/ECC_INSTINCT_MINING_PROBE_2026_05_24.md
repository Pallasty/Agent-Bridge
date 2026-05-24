# delta① — auto-mine behavioral instincts from the session stream (probe spec)

**Source**: ECC (`affaan-m/ECC`) `continuous-learning-v2` 调研，2026-05-24（见 memory `research_ecc_operator_system_deepdive_2026_05_24`）。
**Lane**: agent-bridge learning loop.
**Status**: DESIGN — frozen falsifier, not yet built.
**Discipline**: 验—设计—行动。本 memo 是「设计」相，落地前 Phase 0 先验证再决定建不建（对照 AutoResearch ⑤ 的 frame-audit）。

## Question

ECC 的核心机制是：`PostToolUse` hook 100% 确定性捕获每次工具调用 → 后台 LLM agent 专挖三类信号（**user corrections / error-resolutions / repeated workflows**）→ 产出带 confidence 的 behavioral instinct（「when X → do Y」）。

agent-bridge 能否从会话/工具流里**自动**挖出这类行为信号、且挖出的东西**真的被后续 session 复用**？

## 已有什么（核实 2026-05-24，别重造）

存储与消费层**几乎全有**——缺的只是「自动生产」：

| ECC 概念 | agent-bridge 既有物 | 缺口 |
|---|---|---|
| correction → instinct | `memory_correction`（写 kind=feedback + `corrects` 边 + **L5 检索 boost**） | 只能**人手**调，无自动检测 |
| error-resolution → instinct | kind=**error_pattern** + `trigger_pattern`（在 `session_bootstrap` 的 `error_hint` 命中时浮现） | 同上，无自动检测 |
| 无-LLM 模式提炼 | `memory_auto_curate`（从 session_handoff 聚合两-pass 提炼） | 源是 handoff 文本，非工具流 |
| confidence | `importance`（已喂 FTS `+0.5×importance`） | 未映射到「自主度」（= delta②） |
| repeated workflows | — | 无直接对应（可走 skill 建议，低优先） |

当前 Claude Code hooks 只有 **PreCompact / Stop / UserPromptSubmit**，**无 PostToolUse 观测**。
**结论**：delta① 的唯一真空位 = **从会话/工具流*自动*检测 corrections + error-resolutions → 生成候选 feedback / error_pattern 记忆**。窄切口刻意排除「repeated workflows」「auto-synthesize skill」（后者按 AutoSearch 教训打折）。

## 设计纪律约束（来自 `vision_continuity_synaptic_dream`，硬性）

1. **不污染 α 协激活图**：corrections 是 author-intent，绝不写进 `memory_coactivation`（vision 明令「不要 write-triggered ghost-search 绕过 Hebbian」）。挖掘走**独立的 feedback/error_pattern lane**。
2. **行为突变必须人审**：候选进**审阅队列**，高置信只作*建议*浮现，**不**像 ECC 那样 0.9=core→auto-apply（这条我们**刻意与 ECC 分道**）。
3. **可逆**：观测日志 + 候选是独立可清空 sidecar，wipe 不动 memory/α。

## Phases（逐相位 gate，便宜的先）

### Phase 0a — 消费侧审计（最便宜，read-only，现在就能做）
建生产线之前先问：**既有的 behavioral 记忆有没有被复用？** 统计现存 kind=feedback + kind=error_pattern 的数量、`access_count` 分布、是否在 `session_bootstrap`/`memory_search` 真浮现。
- **Gate**：若既有 behavioral 记忆已有非零复用 → 消费链通，挖更多有价值，进 0b。
- **`NO_REUSE_EXISTING`**：若它们 access≈0、是死重 → 消费侧（浮现）才是瓶颈。**先修浮现，别建挖掘**（等同 ⑤「别为未验证的消费路径建生产」）。

### Phase 0b — 生产侧密度审计（便宜，~5 session 打点）
给 PostToolUse（新）+ UserPromptSubmit（已有）加**轻量观测日志**（append-only sidecar，不入 DB）。跑 ~5 session，量化每 session 有多少**真**的 corrections（用户负向/重定向）+ error-resolutions（工具报错→修复成功）可挖。可用一次 Haiku pass 辅助判定。
- **Gate**：密度 ≥ ~1 可挖信号/session（≥5 session 均值）→ 进 Phase 1。
- **`NO_SIGNAL`**：密度过低 → 流里没足够行为信号撑一个 miner → 停。

### Phase 1 — miner（gated on 0a ∧ 0b）
从观测日志检测两类事件 → 生成**候选** feedback / error_pattern 记忆，**入审阅队列**（不 auto-apply）：
- 先 **rule-based**（correction = 用户消息在助手动作后含负向/重定向 + diff 回退信号；error-resolution = 非零退出/编译错 → 后续同目标成功）。
- 噪音高再加 **LLM-assist**（复用 `LlmClient` + modelscope fallback，对标 ECC 的 Haiku miner）。
- 复用 daemon bg-task 模式（对照 P-α decay tick），低频跑。

### Phase 2 — 复用验证（**冻结 falsifier**，user 指定的核心门）
auto-mined 候选跑 N session 后，对比 auto-mined vs 既有 manual 基线的复用率。

## Falsifier（冻结 — 不许事后挪门柱）

- **`INSTINCT_VALUABLE`** — auto-mined behavioral 记忆在 ≥ **30%** 相关后续 session 被浮现+应用，且 re-correction（被再次纠正）率 < **20%** → 接进 hygiene cron、扩范围（仍守人审门）。
- **`NO_REUSE`** — mined instinct 只堆积、复用与噪音不可区分 / 从不浮现 → **null-path**：观测日志只留 observability，**不**自动写 memory（镜像 ⑤ 的 v22 P6）。
- **`INDETERMINATE`** — 挖出太少 / detector 太噪 → 换更好 detector 或加长窗口重做。

## Gate-safety / 可逆

- Phase 0a 纯 read-only（state.db 副本或只读查询）。
- 观测日志 = append-only sidecar 文件，与 state.db / α 隔离，可单独 wipe。
- 候选进审阅队列不自动入主 memory；人审通过才走既有 `memory_correction` 路径落地。
- 全程不触 α `memory_coactivation`，不触 AiOT daemon。

## Phase 0a 结果（2026-05-24，read-only 审计 state.db）

**不是**简单的「空 lane」或「消费坏了」——是**双存储分叉**，且改写了 delta① 该往哪写：

| 通道 | 实况 |
|---|---|
| substrate kind=feedback | 1 active(access 0) + **4 archived(总 access 207)**；`feedback_p4_evolve_cache` 被访问 **206 次**后归档 → 消费**历史上 work 过**，但 lane 现已基本归档 |
| substrate kind=error_pattern | **0 条**（从未被生产） |
| substrate `correction:*`(memory_correction/L5) | 数条，access 0–1，**几乎没被捡起** |
| **file-memory `feedback_*`** | **17 个 + 26 个 `lesson_`**，经 MEMORY.md **每 session 自动加载 → 浮现率 100% by construction** |

**判读（不触发 `NO_REUSE_EXISTING`，但强 reframe）**：
1. behavioral「instinct」职能现在压倒性由 **file-memory 承担**（自动注入 bootstrap 上下文）；substrate feedback lane 冷落是因为 file-memory 才是 de-facto 家，**非消费链坏**（206-access 归档行证明 active 时消费 work）。
2. **delta① 的写入目标改为 file-memory `feedback_` 通道**（已验证为热：auto-loaded、100% 浮现），而非冷的 substrate feedback 行。或：miner 出候选 → 人审决定是否晋升为 file-memory 条目。
3. **硬约束 — always-loaded 预算**：`MEMORY.md` 已 **210 行/超 ~200 警戒线**。自动挖更多 always-loaded 条目有**真实 context 成本**。这把 Phase 2 falsifier 从「是否被浮现」（file-memory 恒为是）**改为「是否挣得常驻槽位」**：auto-mined instinct 必须证明被*采纳/行动*，否则 = bootstrap 上下文 bloat = 净负。

**Phase 2 falsifier 修订（据 0a）**：
- `INSTINCT_VALUABLE` — auto-mined 候选经人审采纳率 ≥ **50%**，且被采纳者在后续 session 有可观测的行为影响（被引用/避免了重复纠正），同时**未把 MEMORY.md 推过可读性悬崖**。
- `NO_REUSE` — 候选多被人审拒（采纳 < 50%）或采纳后无行为影响 → null-path：observation 日志只留 observability，不自动建 feedback。
- 旧的「≥30% 后续 session 浮现」指标作废（file-memory 恒被浮现，不可证伪）。

**下一步 gate**：Phase 0b（生产侧密度审计）仍需做，但因涉及给 hook 链加 PostToolUse 观测 + 跨 ~5 真实 session 打点，**需 user 在环确认**后再动 hook。

## 与 v22/⑤ 的关系

正交于 substrate-recall（⑤ 已证伪 NO_RECALL_ADVANTAGE，是 *embedding 检索*；本条是 *behavioral 挖掘*）。这是 synaptic vision §α「突触痕迹」里**行为侧**最虚一块的具体、低摩擦、可证伪落地路径——且复用既有 feedback/error_pattern/L5 基建，工程量集中在「自动检测」一处。
