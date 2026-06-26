# Orca (stablyai/orca) 评估与可借设计规划 — 2026-06-19

Status: 裁决已出(借鉴 design-only),借鉴项按验证状态分级排期;未排期实现,等 owner GO。

裁决来源:13-agent workflow(4 路 recon × 8 维对映 × 1 综合),run `wf_68b9bc87-3aa`。
镜像既定「借设计不接 codebase」裁决:[[decision_rmux_steer_backend_p6_20260601]] /
[[decision_camofox_browser_no_adopt_borrow_stableref_20260602]] /
[[decision_skillopt_borrow_gate_not_codebase_20260616]] /
[[decision_artifacts_walkthrough_tdoc_borrow_not_adopt_20260618]]。

---

## 0. 一行裁决

**借鉴(design-only),不吸收、不加入。** 同栈错位(Electron/TS ↔ Rust/MCP = port 非 drop-in)+
不同产品类(GUI 多 vendor cockpit ↔ 单用户后端 substrate)。**殊途同归**:AB 已独立长出全套
fleet 原语(`agent_spawn` 多后端 + `remote_steer` tmux/ssh ≈ orca relay/PTY + `worktree_create`
配 spawn + `agent_orchestrate_scan` 黑板),且在 **gate 纪律 + verify-first / N 轮多数票**两轴
**领先** orca(orca「merge-the-winner」代码里没有 judge/scorer/voter)。orca 不是竞品,是
**缺位的可视前端候选**。

## 1. Orca 是什么(已厘清)

MIT,Electron + TypeScript(~97%),5.6k stars,625 releases,日更,Stably AI(YC)。tagline:
"The AI Orchestrator for 100x builders. Run Codex, ClaudeCode, OpenCode or Pi side-by-side —
each in its own worktree, tracked in one place." 把**任意 CLI agent** spawn 进 node-pty PTY、
往终端打字驱动(per-agent 硬编码 `TUI_AGENT_CONFIG`:detectCmd/launchCmd/expectedProcess/
promptInjectionMode),OSC-9999 + HTTP `agent.hook` 观测状态,人工 diff-review 选 winner;
远程经 SSH relay daemon(binary-framed JSON-RPC 2.0)。**刻意 MCP-unaware**。

## 2. 互补性(决定性结论)

- **orca** = headless-agnostic 的 GUI fleet 前端,PTY 里 spawn 任意 `claude`/`codex` 二进制,
  MCP-unaware。
- **agent-bridge** = 跑在被 spawn 的 claude **内部**的 MCP server(配在 `.claude.json`,wrapper
  在 **agent-bridge 二进制路径而非 claude 路径** → MCP 层对任何 launcher 正交不可见)。

→ **「orca 当 GUI cockpit 驱动 AB-wrapped Claude 当舰队一员」路径为真**,值一次 drop-in 试。
但**「零改动全保真」未证实**:spawn + argv 注入大概率通,但 orca 的 OSC-9999/agent-recognition
依赖 claude 原生进程名 + hook 输出;wrapper 若改进程名或抑制原生 hook 则 worker_done/heartbeat/
session-resume 断。**两段式验证**:
1. 验 launch + free-form steer + 手动 diff-merge(高把握);
2. 单独验 status 集成保真(需 wrapper 保留 claude 进程名 + 原生 hook/OSC)。

## 3. 可借设计 — 验证状态分级(核心)

每项标三个维度:**orca 源置信度**(borrow 是否依赖 orca 实现细节)/ **AB 侧 gap**(已对当前码核实)/
**落地前验证门**(verify-first,落码前必先证实/证伪的事)。

| ID | 借鉴项 | orca 源置信度 | AB 侧 gap(已核实) | 落地前验证门 | 优先级 |
|---|---|---|---|---|---|
| **OB-1** | `worktree_remove` 拆除安全流水线(orphan-proof + path-safety + kill 树内 PTY) | **design-level,不依赖 orca 实现**(orphan-proof/path-safety 是标准防御式 git;orca 6 步是 wiki-only,不需要) | ✅ `crates/agent/src/worktree.rs:72-81` 裸 `git worktree remove [-f]`,`force=true` 零护栏 | 单测:脏树拒删 / root·home·empty 拒 / `.git` 不指向本 repo 拒 / cwd 在路径下的 session 先 SIGTERM。**独立于 orca,可直接做** | ✅ **shipped master `e3fc906`** — path-safety(root/`$HOME`/repo-root/empty,canonicalize 防 symlink·`..`)+ registration(必在本 repo `worktree list`)两护栏入 `remove()` 内部(零改 mcp_tools.rs);8 纯单测(FS/env-free)。kill-树内-PTY + provenance-戳延 follow-up |
| **OB-2** | per-agent 配置表(收 `Frontend` 散落 match-arm 成单一声明 record)+ `preflightTrust` 预写 trust artifact | TUI_AGENT_CONFIG **primary-confirmed**(读了 src);preflightTrust 具体 artifact **wiki-only** | ✅ `crates/bridge/src/setup.rs:57` `Frontend` enum 9 变体散落;steer launch 按 frontend 特例 | 先证伪:AB tmux steer 是否真撞「trust/onboarding 提示吞首条注入」?若撞→preflightTrust 从 **orca 源**确认 artifact 格式再落。配置表重构 AB-内部无 orca 依赖 | P2 |
| **OB-3** | `promptInjectionMode` 5 态分类(argv / flag-prompt / flag-prompt-interactive / flag-interactive / stdin-after-start)+ paste-ready 信号 | **primary-confirmed**(读了 5 态 union) | partial:`agent_steer_drive` 现为 tmux send-keys 单模型 | 对已记 steer gotchas 验证([[lesson_remote_zsh_equals_expansion_breaks_unquoted_tmux_target_20260608]] 同族、long-prompt-not-submitted、bracketed-paste 吞 Enter):逐 backend 标注入模式,bracketed-paste + quiet-render 就绪启发式 | P2 — 📐 **注入模式 taxonomy 设计 done**(§4 OB-3,2026-06-20):当前单模型已核实 + orca 5 态映射 + per-backend 置信度表 + 两 gotcha 证伪器 + `InjectionProfile` spec;✅ **机制 shipped master `52ec1ba`**(冷模块 remote_steer.rs,零碰 mcp_tools.rs;20 lib 单测 + 真 tmux wet-test 4/4);per-backend 行 + drive 接线待逐行 wet-test |
| **OB-4** | annotation-as-steering review 环(diff 行评论 = 结构化 steer 消息注入回 agent) | **primary-confirmed**(README + diff UI) | ✅ `crates/bridge/src/project.rs:301` `changes_digest` 仅 numstat/name-status **无 hunk**;forge 工具只读无写回 | 分两步:① 先给 `changes_digest` 补 hunk/patch scope(小、可单测)② review 环 wire `present` → `agent_steer_drive`,forge 写回门控 `present_await_decision`。**需求驱动**,镜像已 defer 的 Palace Review Artifact | P3 — ✅ **step-1 shipped master `162e20a`**(changes_digest 加有界 `patches`/`patch_truncated`,签名不变零碰 mcp_tools.rs,4 单测+真 git end-to-end);step-2 review 环仍需求 gated |
| **OB-5** | 双通道 graceful-degradation 状态检测(OSC-stream-sniff **+** 可选 HTTP hook,退化到 tui-idle 启发式) | **primary-confirmed**(OSC-9999 + agent.hook) | steer_status 是 driver-written(un-driven worker 不可见);已有 `osc_parse`(OSC 9/99/133/777)+ `agent_steer_capture` PaneSnapshot | **与 Q1 强耦合**(见 §5):codex 无 hook → 必走 OSC/terminal-observe 兜底。验证门:codex CLI 是否吐 OSC?若否,退 tui-idle/PaneSnapshot diff 启发式 | P2 — 耦合 Q1 |

补充低优(park):
- **持久 PTY-host 跨重部署存活**(orca forked node-pty daemon + token-auth Unix socket)→ 验证
  AB「tmux session 跨 MCP-client 存活」模型;可缓解 `.real`-clobber orphan-session 痛。design-level park。
- **completion → 手机推送 + 远程跟进注入**(mobile 维度唯一可留)→ `notify`/Notifier trait 加 remote
  backend;低优,owner 与 agent 同机,off-box 控制需求弱。park。

## 4. 落地细节(P1/P2)

### OB-1 worktree_remove 安全流水线(P1,可立即做)

当前([worktree.rs:72-81](../../crates/agent/src/worktree.rs)):
```rust
pub async fn remove(&self, path: &Path, force: bool) -> Result<()> {
    let mut args = vec!["worktree", "remove"];
    if force { args.push("-f"); }      // ← 脏树 clobber,零护栏
    args.push(&path.display().to_string());
    self.git(&args).await
}
```
借入(纯 Rust,不引 orca 码):
1. **path-safety**:canonicalize 后拒 `/`、`$HOME`、空、repo root 本身(注意 symlink/`..`,呼应
   backlog #2 Theia workspace-boundary 的 canonical 规则)。
2. **git-registration 校验**:path 必须出现在 `git worktree list --porcelain`。
3. **orphan-proof**:该 worktree 的 `.git` 必须指向**本 repo** 的 admin dir(`.git/worktrees/<name>`)。
4. **kill 树内 agent/PTY**:AB 已有 `agent_session_list`/`agent_kill`,且 `worktree_create` 配
   `agent_spawn` —— 删前 SIGTERM 任何 cwd 在 worktree 路径下的 session,免孤儿活 sibling。
5. **provenance 戳**(可选,闭「分不清是不是我建的」gap):`worktree_create` 时写一个标记
   (store row 或 `.git/agent-bridge-created`),`worktree_list` 借此区分 bridge-managed vs 用户建。

**为何 P1 最高优**:这正是 AB 最痛的运维史(CLAUDE-SIBLING S5/S6 + 十余条 shared-tree churn /
`.real`-clobber / unsafe `push origin master` 教训)对应的 worktree 隔离问题 —— orca 结构性规避,
AB 现仅用 prose 缓解。几百行 Rust 防御加固,高把握低风险,**独立于所有 orca wiki-only 声明**。
镜像 deferred 的 `EnterWorktree`/`ExitWorktree` harness 已证 keep/remove + dirty-refusal 模式被需要。

⚠️ **非对称边界**:orca 的 worktree 机器是为 one-agent-per-worktree **隔离**;AB 的实痛是
many-agents-in-ONE-shared-tree —— orca 从不遇这个。所以可移植的是 remove/create 上的**小防御检查**,
**不是** orca 的 first-class-object 重机器(stable ID / store table / 三模 create)。

### OB-2/OB-3 steer 加固(P2)

`Frontend`(setup.rs:57)知识散在 match-arm,无单一「agent capability table」。借 orca 把
launchCmd/expectedProcess/promptInjectionMode/resumeCommand/trustArtifact 收成一行 data record;
`agent_steer_launch`/`agent_steer_drive` 读它。**先证伪再落**:跑一次真 steer,确认是否真撞
trust-prompt-swallow / 注入模式错配,再决定 preflightTrust 与 5 态分类的具体形状。

---

### OB-3 注入模式 taxonomy(2026-06-20 设计步,**无码** — owner 选「OB-3 设计步」)

落码前的 de-risk 设计件。**纪律**:per-backend 行全标置信度,confirmed 只给亲测路径,其余=
**待证伪假设**(镜像 verify-first / [[lesson_remote_zsh_equals_expansion_breaks_unquoted_tmux_target_20260608]]
「shipped≠跨真实环境验过」)。

#### A. 当前注入模型(已读码核实,`crates/bridge/src/remote_steer.rs:289-311`)

AB **对所有 backend 用同一条注入路径**,与 agent CLI 无关:
- `Multiplexer::send_cmd(session, text, submit)` → `tmux send-keys -t <bare-sess> -l -- '<text>'`,
  `submit=true` 再 `; tmux send-keys -t <sess> Enter`(Enter 是独立的非字面 key 事件)。
- gate 自动作答走 `send_key_cmd`(具名 key:`Enter`/`C-c`)。
- **关键**:`Multiplexer` trait 抽象的是 **MUX 层(tmux/rmux,见 [[decision_rmux_steer_backend_p6_20260601]])**,
  **不是** CLI 的输入契约。9 个 `Frontend` 因此共用一个隐含假设 =「字面打字 text,再按一次 Enter 提交」。
  **这就是 OB-3 的 gap**:不同 CLI 的输入控件对「打字+Enter」反应不同,单模型在多行/paste-aware composer 上会错配。

#### B. orca 5 态 promptInjectionMode → AB 术语映射

| orca 态 | 含义 | AB 对应 |
|---|---|---|
| `argv` | prompt 作 spawn 时位置参数 | 仅 launch 期(`launch_cmd` 的 command 串),无运行时注入 |
| `flag-prompt` | `--prompt <text>` flag,one-shot | 仅 launch 期 |
| `flag-prompt-interactive` | `--prompt` 后留交互 | launch 期 + 运行时 send |
| `flag-interactive` | bare 启动,运行时注入 | **AB 当前模型**(`send_cmd`) |
| `stdin-after-start` | 起进程后管道喂 stdin | **AB 未建模**(tmux send-keys ≠ stdin pipe) |

#### C. per-backend 分类(置信度标注;⚠️=待证伪假设)

| Frontend | 假设注入模式 | 提交机制 | gotcha 风险 | 置信度 |
|---|---|---|---|---|
| ClaudeCode | flag-interactive(TUI composer) | Enter | 多行/paste 模式下尾 Enter 可能当换行 | **基本路径 confirmed**(primary steer 亲测通);paste/多行 edge **未验** |
| Codex / CodexCli | flag-interactive(TUI) | Enter | 同上;且 06-20 转 OB-6 app-server 后此路降为 fallback | ⚠️ hook 已确认 [[decision_orca_borrow_not_adopt_20260619]],注入模式**未测** |
| CodexIde / Cursor | IDE 内嵌进程,**大概率非 tmux-TUI** | N/A | tmux send-keys 可能根本打不进 IDE 输入框 | ⚠️ 很可能 **N/A**,待 probe |
| GeminiCli | flag-interactive(TUI) | Enter | 同 CC | ⚠️ 未测 |
| Warp / Auggie | 终端 app 自有输入 | Enter | 未知 | ⚠️ 未测 |
| LocalCli | 取决于被包二进制 | 取决于 | 取决于 | ⚠️ 泛型,逐例定 |

#### D. 两条开放 gotcha — 机制 + 证伪器

1. **long-prompt-not-submitted**:多行 text 经 `-l` 送入,尾随的单个 `Enter` 被多行 composer 当
   「插入换行」而非「提交」吞掉。**证伪器**:wet-test 注入 3 行 prompt(submit=true)→ `capture_cmd`
   断言 prompt **已提交**(响应已开始)而非滞留 composer。
2. **bracketed-paste 吞 Enter**:app 自检测快速 `-l` 批量输入为 paste、进 paste 模式,尾 Enter 落在
   paste 括号内被当字面换行。**证伪器**:同 wet-test 用长单行;查是否提交。
   **缓解候选**(落码前不预设):(a) Enter 作独立、短延迟后的 key 发;(b) 注入前 capture 确认 composer
   非空 + quiet-render 再发 submit;(c) 逐 backend 用其显式提交 chord。

#### E. quiet-render 就绪启发式(orca paste-ready 信号的 AB 形态)

注入前 `capture_cmd` 确认 pane 停在 input-ready 提示符(非流式渲染中);注入 text 后、发 submit 前,
再 capture 确认 text 已落 composer。已有原语:`capture_cmd` / `capture_styled_cmd` / `snapshot_meta_cmd`
(含 cursor x/y)+ `agent_steer_capture` PaneSnapshot → **够搭这个启发式,无需新原语**。

#### F. 拟代码形态(spec,本步不实现)

per-`Frontend` 注入描述符 `InjectionProfile { mode, submit_key, needs_quiet_render, paste_safe }`
(= OB-2 配置表的泛化),由 `agent_steer_drive` 读。**保持 `Multiplexer`(MUX 层)正交**,CLI 级 profile
另立一层(=Q2 的「薄 frontend-adapter 层」,见 §5)。**落码门**:C 表每行先 wet-test 证伪/证实,
再写对应 profile —— 绝不凭假设落 9 行。

#### G. 范围诚实 + 06-20 frame shift

只有 **tmux-TUI backends**(CC/codex/gemini/warp/auggie)吃这套;**CodexIde/Cursor 很可能 IDE 内嵌
非 tmux-steerable**(待 probe 定 N/A)。且 06-20 裁决 codex 正转向 `app-server`/`--remote ws://`
结构化控制面(OB-6),将**绕开 tmux send-keys**——故注入 profile 投资应押在**会留在 tmux 驱动**的
backends,codex 的 tmux profile 视为 fallback。**净**:本设计件把 OB-3 从「凭感觉加 5 态」收敛成
「一张待逐行证伪的 backend×模式表 + 证伪器 + 正交分层 spec」,后续任一 wet-test 落实即可安全落对应行。

#### H. ✅ 机制 shipped(master `52ec1ba`,2026-06-20,双 forge)

落码全在**冷模块 `crates/bridge/src/remote_steer.rs`**,**零碰 mcp_tools.rs 热区**(镜像 OB-1 赢法):
- `InjectionMode`(FlagInteractive/LaunchOnly/StdinAfterStart,映 orca 5 态)+ `InjectionProfile`
  `{mode, submit_key, needs_quiet_render, paste_safe}` + `injection_profile(backend)` 分类器
  (**verify-first**:每 backend 现全解析为保守 default,显式 match 臂 = 待 wet-test 的证伪槽,绝不凭假设填)。
- `send_profiled(.., profile)`:default(`submit_key=="Enter"`)**字节等同历史路径**;非-Enter key 走
  split(打字不 Enter + 独立 `send_key` 提交)= 未来 gotcha 修复的接缝。`send()` 改委派 default profile
  → 单一调用方 `agent_steer_drive` **无需改、零回归**。
- 验证:**20 lib 单测**(分类器诚实 + default 不变量)+ `examples/ob3_injection_wettest.rs` **真 tmux
  端到端 4/4 PASS**(A 默认 Enter 提交 / B split 非-Enter 提交 / C LaunchOnly 拒 / D 分类器诚实默认;
  本地受控 bash,无 agent CLI,零生产写)。post-rebase lib check 绿。
- **延后续(wet-test-gated)**:① per-backend 行填实(逐行真 CLI wet-test);② drive 接线
  (`agent_steer_drive` 传真 backend 选非默认 profile)—— 因当前所有行 == default,接线本就零行为变更,
  待有 wet-tested 非默认行再做(且届时碰 mcp_tools.rs,需避 codex churn)。

## 5. 与当前两问题的耦合(讨论基底)

借鉴计划与 owner 提的两个问题**直接耦合**,先给初步立场,细节待讨论:

### Q1 — Codex-CLI 没有 Hook
- Claude Code 有 hooks(PreCompact/Stop/PostToolUse,注:[[lesson_cc_posttooluse_no_fire_on_tool_error]]),
  **Codex CLI 无 hook 机制**。故 OB-5 的「worker hook-push 状态」对 codex **天然失效**。
- **orca 的答案正是 OB-5 的双通道**:OSC-9999 stream-sniff 是**无 hook agent 的通用兜底**,
  agent.hook 是支持者的更富可选通道。AB 已有 `osc_parse` + `agent_steer_capture`(PaneSnapshot)。
- **初步立场**:codex 状态走 **terminal-observe 路**(OSC / tui-idle / PaneSnapshot diff 启发式),
  **不**指望 hook。验证门:codex 是否吐任何 OSC(9999/133)?若否,退 PaneSnapshot 静默-检测。
  这把 Q1 从「codex 缺能力」翻成「AB 缺一个 hookless 兜底观测通道」—— 而那正是 OB-5 要建的。

### Q2 — AB 对 CLI 环境的依赖,是否深度嵌入特定 CLI?
- 现状:AB MCP 层**已经 CLI-agnostic**(`setup.rs` 9 个 Frontend:ClaudeCode/Codex/CodexCli/
  CodexIde/GeminiCli/Cursor/Warp/Auggie/LocalCli);但**生命周期/记忆层 hook-coupled 于 Claude Code**
  (curate / precompact 蒸馏靠 CC hook)。
- **orca 是外部证据**:agnostic + 「terminal 里 spawn 任意 binary」的赌注**能 scale 到 33 agent**。
  它在 capability 层用 per-agent 配置表 + 双通道观测兜住 CLI 差异,而非深嵌某一个。
- **初步立场(待讨论)**:**不深度嵌入单一 CLI**。保持 MCP 层 agnostic(这正是 orca-frontend 路径
  免费、且 AB 跨 Claude/Codex/Gemini 可移植的来源),但把 CLI-specific 能力(hooks where available /
  OSC·terminal-observe where not / session-resume)收进一个**薄 frontend-adapter 层**(= OB-2 配置表
  泛化 + SSB adapter-conformance 模型)。深嵌 = 放弃 orca 路径 + 锁死单 vendor,与 AB 的多前端
  现状([[project_off_screen_dev_arc_2026_05_14_to_19]] codex multi-frontend profile)矛盾。
- **诚实的张力**:AB 最富的能力(记忆 curate、precompact 蒸馏)**确实** hook-coupled 于 CC;codex
  上这些会瞎。orca 的教训 = 加 terminal-observe 兜底让生命周期层在 hookless CLI 上**优雅退化**而非
  全瞎。这就是 Q1↔Q2 的桥。

## 6. 不要做(反建议)

- **不吸收代码** — Electron/TS → Rust/MCP 全量 port;orca 扩展哲学(终端 spawn + 打字 +
  filesystem-overlay 沙箱 + 零 MCP 感知)是 AB 深 MCP 契约 + 类型化 SSB descriptor 的刻意反面。
- **不加入** — MIT + 真 CONTRIBUTING 让 JOIN 可行,但 = 贡献进别人 Electron 路线图,零
  Rust/MCP/SSB 杠杆;单维护者 benevolent-dictator 治理非共治。
- **不建 GUI agent-bridge** — orca 的 WebGL cockpit / Design Mode / diff-UI / 移动 app 是
  Electron-native,headless Rust 后端结构上长不出。
- **不 unpark #1787 coordinator** — 除非真出现多 worker 硬需求;orca coordinator 自身也是 non-LLM
  机械式(AI 分解明确 deferred),非 AB 落后处。
- **不重做 sibling 已落工作** — 借鉴落子前 fetch origin + 扫近期提交(churn 期纪律,
  [[feedback_hot_lane_step_back_dont_pad_20260615]])。

## 7. 诚实:仍未核实、可能改变裁决的 orca 声明

recon 大量标 **wiki-only 未对源核实**,落码须自查不可假设:
- RuntimeRpcServer WebSocket 端口 6768/6769(**drop-in 试关键**:手机/CLI 连 runtime 的前提)。
- relay 13B 帧布局 / type 1·2·9 / 16MB cap / JSON-RPC-2.0-over-SSH + relay.sock fallback
  (protocol.ts 存在,body 未读)。
- PTY daemon 路径 daemon-entry.ts + Unix-socket+token-auth(只确认 src/main 顶层 dir)。
- worktree teardown 6 步 + ~25 state-key + 三模 create + orcaCreatedAt 戳(全 wiki;影响 OB-1
  精确度 —— 借的是**设计意图**,实现细节 AB 自定)。
- plugin-overlay 细节 / preflightTrust 具体 artifact(影响 OB-2 实现)。
- **【最关键】AB-wrapped Claude 零改动当 fleet agent = PARTIAL-yes(spawn/prompt)/ 未确认
  (status/hooks 全保真)** —— 未找到代码证明 recognition 在任意 wrapper 进程名下存活 → §2 两段式
  验证不可省。
- wiki 版本号相对 package.json(Electron ^42.3.3 / React ^19.2.5 / Node 24)已 stale,数字不信。

---

**净**:殊途同归 = AB 后端形态对的强外部背书。可落子 = 5 个小防御性补丁(OB-1..5),无新子系统
正当性。Kanban 任务见 `BORROWED_PATTERNS_BACKLOG_2026_06_09.md` 的 Orca 段(AB-BORROW-ORCA-*)。

---

# §8 实测验证结果(2026-06-20)— "嵌合体"目标的 research/verify

owner 设目标:基于 AB-as-host 嵌合体思路实测验证 + 规划落地。在本机(aio2)对 Codex 0.141.0
做了实测,**推翻了 Q1 的前提,并把嵌合体目标重构为两层**。证据优先,反推测。

## 8.1 决定性实测发现

| # | 发现 | 证据(本机实测) |
|---|---|---|
| F1 | **Q1「Codex 没有 hook」证伪** | `codex --help` 有 `--dangerously-bypass-hook-trust`;`~/.codex/config.toml` 有 `hooks = true` |
| F2 | **Codex 用 CC-兼容 hook taxonomy** | `~/.codex/hooks.json` 含 PreCompact(manual+auto)/Stop/SessionEnd/UserPromptSubmit/PostToolUse,schema 同 CC settings.json |
| F3 | **AB 的 hook 已全部装好且被 Codex 授信** | `[hooks.state]` 给 post_tool_use/pre_compact:0/pre_compact:1/stop/user_prompt_submit:0/user_prompt_submit:1 各一条 `trusted_hash = sha256:...` |
| F4 | **hook 今天真在 fire** | `~/.local/share/agent-bridge/hook-runs.jsonl` 有 2026-06-20 的 `stop` / `beforeSubmitPrompt` 记录,exit 0 |
| F5 | **AB 已是跨 CC+Codex 活体 substrate** | 同一份 `ab-*-hook` 脚本被 CC(`~/.claude/settings.json`)与 Codex(`~/.codex/hooks.json`)双方调用 → 同一个 agent-bridge MCP;`codex config.toml` 的 `[mcp_servers.agent-bridge]` env `AGENT_BRIDGE_CLIENT=codex` |
| F6 | **Codex 有比 tmux-scrape 更干净的 host 通道** | `codex` 子命令:`exec`(非交互)/`mcp-server`(Codex 当 MCP server)/`app-server`+`remote-control`+`exec-server`(daemon 远控)/`--remote ws://unix://`/`plugin`+marketplace/`sandbox`。这是结构化程序控制面,类 orca relay |

**结论**:CC 与 Codex 在 **hook 契约 + MCP 契约**上**双双殊途同归**。"嵌合体"的认知/记忆层
**不是待建,而是已 LIVE** —— 靠的是收敛的标准契约,不是 AB 托管 CLI。这同时是 Q1 的解
(Codex 有 hook)和 Q2 的实证答案(**别深嵌单一 CLI;agnostic substrate 已跨两大 CLI 工作,
因为它们收敛到兼容契约**——与 orca 同款殊途同归)。

## 8.2 嵌合体重构为两层(各自状态/工作量天差地别)

### Layer 1 — 认知 substrate(记忆/生命周期):**已 LIVE,只需验证 + 加固,不重建**
- 现状:CC(settings.json hooks)+ Codex(hooks.json,已授信+在 fire)都调同一 `ab-*-hook` →
  agent-bridge MCP。收敛契约(MCP + hooks.json)让它**零 per-CLI 代码**就跨 CLI。
- ✅ **fire-but-fail gate 基本 CLOSED(2026-06-20 只读探针更正先前判断)**:先前写"`ab-precompact-hook`
  按 CC 形状解析、无 CLI 分支"——**该判断错误**(只读了脚本前 50 行 session_id 解析,漏看 turn 抽取)。
  实测 hook **本就 Codex-aware**:① transcript 定位**已含** `$HOME/.codex/sessions`(实测 `rollout-*.jsonl`
  在那);② turn 抽取**显式分支** Codex 格式(`d.type=='response_item'` → `payload.role/content`,
  `extract_text` 处理 `input_text/output_text`),else 才是 CC;③ 实测 Codex rollout jsonl 结构
  = `response_item`+`payload.type=message`+`input_text/output_text`,**与 hook 的 Codex 分支吻合**。
- ⚠️**唯一残留(需活跑,gated)**:Codex 是否在 stdin payload 传 `session_id`(hook 也回退
  `CLAUDE_SESSION_ID` env)。`hook-runs.jsonl` 证 stop/beforeSubmitPrompt 在 fire(payload 在到达),
  但 pre_compact 全链真产出非空 curate 须实测——compact→curate **写生产 state.db = GATED 须 owner 批**。
  注:`hook-runs.jsonl` 的 `output_bytes` 是硬编码 0 占位,不能用来判 fail。
- **Layer-1 工作 = 仅剩残留验证,防御性 CLI 分支已存在**:只需(gated)实测一次 Codex pre_compact
  真产出 + 文档化"收敛契约 substrate"。

### Layer 2 — 编排/host(fleet steering):**真正的嵌合体前沿,增量提升**
- 现状:AB-as-host 雏形 = `remote_steer.rs` 的 `launch`(tmux new-session)+ `capture`/
  `capture_snapshot`(capture-pane 屏幕抓取)。这里 host 位给的是 **hook 给不了**的东西:跨 agent
  fleet 观测、un-driven worker 可见性、OSC/pane 状态、worktree 隔离。
- **Layer-2 工作**:
  - orca 借鉴 OB-1(worktree teardown 安全)/ OB-3(注入模式)/ OB-5(双通道状态)——见 §3。
  - **新增 OB-6(F6 触发):评估用 Codex `app-server`/`--remote ws://unix://` 结构化控制面替代
    tmux capture-pane 屏幕抓取**。屏幕抓取是 lossy(PaneSnapshot 解析终端字符);Codex 的
    app-server 给结构化事件/状态,是**质上更干净的 host 集成**。先证实 app-server 协议稳定性
    (experimental 标签)再决定是否落。这把"AB-as-host"从屏幕抓取升级到协议级。

## 8.3 重构后对两问的最终答复

- **Q1(Codex 无 hook)**:**前提证伪**。Codex 有 CC-兼容 hook,AB 已装+已授信+在 fire,且
  `ab-precompact-hook` 已 Codex-format-aware(transcript 定位 + response_item/input_text 解析,实测吻合)
  → **fire-but-fail gate 基本 closed**。残留仅 = Codex stdin payload 的 session_id 投递(需 gated 活跑确认),非"缺能力"。
- **Q2(深嵌单一 CLI?)**:**实证否决深嵌**。AB 已是跨 CC+Codex 活体 substrate,因两大 CLI 收敛到
  兼容契约(hooks.json + MCP)。这是 agnostic-substrate 赌注对的**实测背书**(不是推测)。
  保持 MCP-agnostic + 薄 adapter;host 位(Layer 2)留给 fleet 编排,**不**用于记忆层(那层 hook 已够)。
- **嵌合体净判**:认知层嵌合**已成、靠收敛契约非托管**;托管(AB-as-host)的真价值在 fleet
  编排层,且应往 Codex app-server 协议级方向走,而非 tmux 屏幕抓取。守住边界:**永不吞 harness**。

## 8.4 落地顺序(evidence-grounded)

1. **【P1 验证】Codex pre_compact payload parity** —— 实测 Codex 上 curate 真产出(非空),
   定位 fire-but-fail。这是 Layer-1 唯一真 gate。**需真跑一次 Codex 会话触发 compact + 写 prod
   state.db(curate)= 生产写,GATED 须 owner 批**(或设计只读探针:UserPromptSubmit 注入路径只读)。
2. ~~**【P1 码】OB-1 worktree_remove 安全流水线**~~ ✅ **shipped master `e3fc906`**(path-safety + registration 两护栏 + 8 纯单测;kill-树内-PTY + provenance-戳延 follow-up)。**未触发部署**(库改动下次 deploy 生效;deploy 本身 gated)。
3. **【P2 投石】OB-6 Codex app-server 作 host 通道** —— 只读评估协议稳定性,不落码。
4. **【P2 码】OB-3 注入模式 + OB-2 配置表** —— steer 加固。
5. OB-5 双通道状态 / OB-4 review 环 —— 需求 gated。
