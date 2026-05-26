# delta① — auto-mine behavioral instincts from the session stream (probe spec)

**Source**: ECC (`affaan-m/ECC`) `continuous-learning-v2` 调研，2026-05-24（见 memory `research_ecc_operator_system_deepdive_2026_05_24`）。
**Lane**: agent-bridge learning loop.
**Status**: ⛔ CLOSED 2026-05-25 — `NO_SIGNAL` 结构性 null-path。error-resolution 自动挖掘在 Claude Code 上结构性不可行(**PostToolUse 对 tool-error 不 fire**,见末节 §2);corrections 可观测但稀疏。不建 miner;observer observability-only。镜像 ⑤ P6。
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

#### Phase 1 参考架构 — rustnet 被动观测管线（2026-05-25 外部调研，见 `reference_rustnet`）
`domcyrus/rustnet`（Rust TUI 网络监控)的管线是一个**成熟的被动观测流水线**,与本 miner 结构同构,Phase 1 触发时照此形状建:

| rustnet 阶段 | delta① miner 对应 | 状态 |
|---|---|---|
| Capture 线程 → crossbeam channel → 关闭写 JSONL sidecar | observer hook 写 `observations.jsonl` | **已有** |
| N worker 做 parse + DPI 分类（cheap header→选择性深检） | correction / error-resolution 分类器（**先 rule 启发式上界 → 候选才上 LLM 精判**）| 待建 |
| `DashMap<Key,Conn>` 分片并发存 | per-session 候选聚合 | 待建 |
| Snapshot Provider 周期读出**不可变快照**(`RwLock<Vec>`)→ 渲染 | 密度审计 / 候选人审快照 | 部分(audit 脚本) |
| Cleanup 线程 + **per-class TTL + 三档 staleness 着色**(白<75%/黄75-90%/红>90% TTL) | 候选 instinct 的生命周期/衰减(可借「按 kind 差异 TTL + 临过期着色」作候选过期 UX) | 待建 |

借鉴要点:**(a)** staged-cost(rustnet `--no-dpi` 省 20-40% = 我们 cheap-prefilter→LLM-precision,确认 spec 对);**(b)** 写侧并发存 / 读侧周期不可变快照分离(writers 不阻塞 readers);**(c)** per-class TTL + 临过期三档着色作候选生命周期显示约定。**纯架构借鉴,Phase 1 未触发前零代码**;repo https://github.com/domcyrus/rustnet。

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

## Phase 0b 结果（2026-05-25，gate ✅ PASSED → `DENSITY_OK_PROCEED_PHASE1`）

observer(`ab-instinct-observer-hook`)累计 5 distinct session、585 records,`scripts/instinct_density_audit.py`:

| | 值 |
|---|---|
| sessions | **5**（达 ≥5 阈值）|
| mean mineable/session | **4.0**（4× 的 1.0 gate）|
| verdict | **`DENSITY_OK_PROCEED_PHASE1`** |
| 趋势 | 4-session 1.75 → 4-session 2.5 → 5-session 4.0(单调上升)|

**诚实解读(防 over-claim)**：
1. **mean 4.0 是启发式分类器的*上界***(脚本自述 FP-tolerant upper-bound proxy)。Phase 0b 只证「**有足够候选信号值得建 miner**」,**不证**信号都高质量。真质量门 = Phase 2(人审采纳率 ≥50%)。
2. **信号压倒性是 error-resolutions 不是 corrections**:5 session corrections 共 **3**(1+0+0+1+0),error→fix 修复 **18**(8+5+5)。→ **Phase 1 优先建 error-resolution miner**(高密度 + 更确定:工具报错→同工具后续成功);corrections 次要(稀疏 + 负向-cue 分类器更噪)。

**Phase 1 解锁(0a∧0b 双绿),但是真 build,需 user 在环 + 验—设计—行动**。范围:(i) error-resolution 检测器(从 observations.jsonl 提 err→fix-success 对)→ 候选 file-memory `feedback_`/`error_pattern`;(ii) **入审阅队列,不 auto-apply**(硬约束);(iii) observer 从 probe-stage graduate:Codex desktop setup 已 wire `UserPromptSubmit` + `PostToolUse`,Claude Code 仍保持手动注册;(iv) 守 MEMORY.md always-loaded 预算(Phase 0a reframe)。

### ⚠️ Phase 1 验证步发现 — DENSITY_OK 是传感器 artifact(2026-05-25,verify-before-build)

开建前对真实 `observations.jsonl` 验证 error-resolution 对的实际形态 → **gate 是假阳性灌水**:
- observer 的 err 判定 = `tool_response.stderr 非空 → err=true`(`ab-instinct-observer-hook.py:58-60`)。**任何往 stderr 写东西的成功命令都被误判**:`git clone/push`(进度/remote 信息)、`cargo test`(`... ok`)、`flake8 rc=0`、maturin warning、`2>&1` 重定向。
- 实测:**44 个 err 记录,强失败标记命中 0/44,空-stdout(真失败候选)0/44,全部含真实 stdout = 成功命令**。真 error-resolution 密度 ≈ **0**。mean 4.0 / 7.67 pairs 全是 stderr-noise。
- corrections 信号本就稀疏(5 session 共 3,负向-cue 启发式)。

**裁决(不挪门柱,是发现仪器坏了)**:Phase 0b 按冻结 gate 的字面(启发式上界 ≥1.0)技术上 PASS,但验证揭示**上界由 FP 主导,真信号 ≈0**。同 M6/M7/⑤ 的「指标=测量 artifact」类。**不建 miner**(建=挖噪音=落 NO_SIGNAL null-path)。

**修正后的下一步(Phase 1 step 0 = 修传感器再重测,gated 在建 miner 之前)**:
1. **修 err 判定**:去掉 stderr-非空 启发式;只保留 `is_error`/`interrupted` 等干净信号。但**先 verify** Claude Code PostToolUse payload 对*真失败 Bash*(非零退出)到底给什么(is_error?exit_code?)——别凭假设重新埋点(守 `lesson_verify_code_semantics_not_field_names`)。
2. 修后 re-accumulate ~5 session,重测真密度。
3. **若真密度仍 ~0 → NO_SIGNAL null-path,收口**(这些 dev session 本就 success-heavy,模型少撞硬失败再修复;observer 留 observability,镜像 ⑤ P6)。若 >1 → 真 DENSITY_OK,再建 error-resolution miner。

### ⛔ §2 verify-before-instrument 决定性发现 — PostToolUse 对 tool-error 不 fire(2026-05-25)→ error-resolution 结构性 null-path

修传感器前先 verify「CC 对真失败给什么字段」,诱发真失败实测,结果**比 artifact 更根本**:

| 诱发命令 | exit | harness `<error>`? | observer 记录? |
|---|---|---|---|
| `ls /nonexistent` | 2 | 是 | **否** |
| `false` | 1 | 是 | **否** |
| `python sys.exit(3)` | 3 | 是 | **否** |
| `grep` no-match | 1 | 否(当成功) | 是(err=False) |
| 所有 exit-0 | 0 | 否 | 是 |

**根因(结构性,非可调)**:**Claude Code 的 PostToolUse hook 在工具结果被标 `<error>`(is_error)时根本不 fire**。observer 结构上**看不到真失败**;之前 44 个 err=true 全是 exit-0 成功命令被 stderr-非空 启发式误判。**修 err 启发式 moot**——失败事件到不了 hook。design memo 开篇假设「PostToolUse 100% 确定性捕获每次工具调用(含 errors)」**对 Claude Code 为假**。

**裁决 = `NO_SIGNAL` 结构性 null-path(收口,镜像 ⑤ P6/T31:假设的能力 CC 不提供)**:
- error-resolution 自动挖掘在 CC 上结构性不可行;**不建 miner**。传感器只做 hygiene 修正:不再把 stderr-only 当失败,避免 observability 本身继续制造假信号。
- corrections 经 UserPromptSubmit 仍可观测但稀疏(5 session 共 3)+ 分类器噪 → 单独不足以撑 miner。
- observer err 信号无意义 → 留 observability-only 或退役;**不 graduate 进 setup.rs**。
- **唯一可复活路径**(若将来,且证明 corrections 够):不走 PostToolUse,改 Stop/PreCompact hook 扒 session transcript(transcript 含 `<error>`)——更重的另一套设计,不在当前范围。
- **Codex 侧**已 wire PostToolUse,但其对 tool-error 是否 fire **未验证**;若 Codex 捕获错误,error-resolution 或 Codex-only 可行(待验,不投)。

通用基建教训沉淀 `lesson_cc_posttooluse_no_fire_on_tool_error`。**delta① 至此收口** — 见 Status 行。

### RNET-1/RNET-2 hygiene 落地(2026-05-25)

借 `domcyrus/rustnet` 的 Snapshot Provider / staged-cost 思路,把 observer 从“密度上界脚本”收敛为**只读审计快照**:

- `ab-instinct-observer-hook.py` 新增 clean error 语义:`err=true` 只来自 `is_error` / `error` / `interrupted` / 非零 `exit_code` / failed `status`;stderr-only 仅记录 `stderr_nonempty=true`,不计失败。
- `scripts/instinct_density_audit.py` 同时输出 clean verdict 与 legacy upper-bound verdict,把旧 `stderr=>err` 记录归为 `legacy_untrusted_errors`。
- 复跑历史 659 records / 5 sessions:clean mean/session **0.8** → `NO_SIGNAL`;legacy upper-bound mean/session **6.2** → `DENSITY_OK`,由 **44** 条 untrusted legacy errors 支撑。该对照固定为“传感器 artifact”证据。
- 新增 Python 单测覆盖 stderr-success 不算 error、非零 exit code 算 clean error、审计脚本分离 clean/legacy。

### RNET-6 sidecar 权限硬化(2026-05-26)

借 rustnet “先预创建输出,再收紧边界”的安全姿势,observer sidecar 做最小硬化:

- hook 创建/修正 `~/.cache/agent-bridge/instinct-probe` 为 `0700`。
- hook 创建/修正 `observations.jsonl` 为 `0600`。
- `agent-bridge doctor` / `capabilities.hooks.instinct_observer` 暴露 `permissions_ok`,
  `log_dir_mode_octal`, `log_mode_octal`;旧的 `775/664` 会被 doctor warn。
- 仍不引入网络/exec 沙箱,避免扩大改动面;本轮只解决本地日志隐私边界。

## 与 v22/⑤ 的关系

正交于 substrate-recall（⑤ 已证伪 NO_RECALL_ADVANTAGE，是 *embedding 检索*；本条是 *behavioral 挖掘*）。这是 synaptic vision §α「突触痕迹」里**行为侧**最虚一块的具体、低摩擦、可证伪落地路径——且复用既有 feedback/error_pattern/L5 基建，工程量集中在「自动检测」一处。
