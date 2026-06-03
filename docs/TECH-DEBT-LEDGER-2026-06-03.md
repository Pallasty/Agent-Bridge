# Agent-Bridge 技术债账本(2026-06-03)

> 来源:对照 8 大设计支柱,并行扫描 57 活跃记忆 + ~50 设计文档 + forum 开放线程 + 代码 deferred 标记,99 条原始 finding → 去重 + 对 HEAD 逐条代码核验 → 归并 **51 条**。
> 生成方式:multi-agent workflow(`tech-debt-ledger`)抽取 + 综合官裁决 + 人工亲验高优先级载荷声明。
> **核验勘误(重要)**:本账本初稿的 #1 优先级"MCP wedge 修复未合 master"在亲验后**已作废**——见文末「核验修正」。

---

## 设计支柱(债务对照系)

1. **记忆/substrate** — 可审计的长期认知数据面(L3 成熟,L2/L1 已 park 为 observability)。SQLite(WAL) 权威 + 384维本地嵌入 + FTS5 + 图边 + 协激活;"检索即强化";v22 Seed L2 因 T31/recall 证否而 park。
2. **跨节点同步** — SQLite-record-truth + JSONL-transport + 双 forge 镜像;15min timer + Stop hook;冲突解析下移到 per-record 版本向量;Tailscale daemon-http 近实时 forum/presence。
3. **Agent 编排与具身** — Hub 持全可选 `Arc<dyn Trait>` 便于降级;agent_spawn/message/inbox + worktree 隔离;桌面"功能性在场坞"(dock 只记录不执行)+ steer 跨进程人在回路控制面。
4. **Linux computer-use** — 看/视觉/坐标动/语义动四工具,默认 isolated-only + DENY;碰真桌面只经三条人确认 host 路径;诚实定位=防静默 mutation 非 agent-proof 沙箱。
5. **MCP 工具面** — 能力总线而非一次性脚本;多前端 toolset profile 矩阵;每 call 回 backend_id + 失败入环形缓冲。
6. **可观测性与自演化** — L5(行为记忆)→L6(元认知)→L7(自修改,提议永不自动应用);每 ship 挂 13-gap 闭集防 narrative-shopping,阈值不得事后下调,负结果计为证据。
7. **协作协议** — Collab Protocol v0(C1/C2/C3)+ forum/presence/inbox;sibling-overlap 6 失败模式纪律;部署只从最新 master + 反退化门 + 必备份。
8. **分层职责边界** — L4 Agent / L3 bridge / L2 Shell 各司其职;可审计长期状态交 bridge(SQLite),一次性推理留上下文。

**核心判定哲学**:`P6 null-path = 经证伪后故意不建,是裁决不是债务`。本账本严格区分**真债务**(shipped 代码缺陷/未跑验证/未治本复发/deferred 层)与**已证否死路 / PARKED 特性 / 外部约束**——后者列出仅防被误当待办翻案。

---

## 执行摘要

| 桶 | 计数 |
|---|---|
| **真债务**(is_true_debt=true) | **27** |
| 非债务 · 勿翻案(P6 null-path / 外部约束) | 15 |
| 非债务 · PARKED 等触发 | 9 |
| ⏰ 时间敏感 gate(活跃) | 4 |
| ✅ 已治本 · 勿重开 | 6 |

### 🔝 最该先动(亲验后修订)

1. ~~合 MCP wedge 修复入 master~~ → **已作废:修复 `4eae961` 早已在 `origin/master`(551bb8d),live binary(01:52)已含 `AGENT_BRIDGE_MCP_CALL_DEADLINE`,运行中 server 已激活。本条 SHIPPED+DEPLOYED,非债务。**(workflow 拿陈旧本地 HEAD 比对的假象)
2. **[high] AB stuck-task 不随 client-cancel 取消 + 线程无界累积(83→242 全 futex)** — Layer3(每 call spawn 独立 task + per-id cancel-token + blocking 池限额)有意 defer;Layer1+2 backstop 只压永久 wedge 不解线程泄漏根因。需核心循环重写。(TD-02)
3. **[med·逾期] GATE-2 sibling-activation 14d gate**(deadline 06-02)— **AiOT `#e6fe8c44` owns**,depth_ratio_ema 是 AiOT 指标非 AB;AB 侧 cross-reference(P-α Day-14)已 05-29 闭合 clean。binding verdict 待 owner。
4. **[med] F6 C3 s2-drop 误报族 5 个 open 线程(36/39/93/95/97)** — 分类器修复已合 master `119faca`,fleet 未全重部署 → peer 节点 pull+rebuild+restart 后批量 resolve。
5. **[med] memory-sync 真跨网两节点 wet-test 从未跑** — VersionVectorMerge stamping 靠 env 兜底,未 stamp 行回退 NewerWins(LWW data-loss 形状);唯一消除该窗口的验证未跑。

---

## A. 真债务(按设计支柱分组,组内 severity 降序)

### 🧩 MCP 工具面 / Agent 编排 — 并发健壮性
- **[high] stuck-task 不随 `notifications/cancelled` 取消 + blocking 线程无界累积(全 futex)** — 顺序循环卡死时连 cancel 都读不到=cancel 结构性失效。实现 Layer3=每 tools/call spawn 独立 task + stdout Mutex + req-id→cancel-token + blocking 池限额/超时回收。依赖核心循环重写。`lesson_browser_navigate_hang_dangling_singletonlock_20260602` (TD-02)
- **[med] 部署 binary 是否含 SingletonLock 清理待验** — 代码 `chromium_cdp.rs:265` 已无条件 `remove_file`(已治本),仅"部署 binary 含此修"待体检 + 可选 `AGENT_BRIDGE_HEADLESS=1` 默认。(TD-04)
- **[资讯] MCP wedge Layer1+2(deadline + browser launch/connect timeout)** — **已 ship `4eae961` + 已 deployed**。非债务,记录闭环。

### 🔄 跨节点同步
- **[med] memory-sync 真跨网两节点 wet-test 从未跑** — 仅单机模拟绿。Mac 先 install.sh+重建 .real,跑 Runbook Test A(异 key 干净合并)+ Test B(并发同 key 必留双版本+恰 1 冲突副本+零丢失)。`project_memory_sync_version_vector_track_2026_05_24` (MS-1)
- **[med] VersionVectorMerge stamping 靠 `AB_SYNC_NODE` env 兜底,未 stamp 行回退 NewerWins(LWW data-loss 形状)** — 确认所有写路径经 node_id stamp;wet-test 后把 stamping 改成 store 内在不变量。(MS-2)
- **[med] D2-G1 跨机 forum 同步 17-post 缺口,仅 peer-query 在线兜底** — `main.rs:12049` status=VIOLATED。修 forum store-and-forward 收敛,或确认 Track MS 覆盖 forum 表后关 G1。(DEBT-01)
- **[low]** memory_import 不 stamp embedding_backend → M6 stale~60% 永报(标签产物,语义搜索不受影响)(TD-05) / 冲突副本合并回 canonical 无自动化(MS-4) / Phase 2 MS-4 index-diff、MS-5 staggered 未实现(MS-3) / forge Mac Pro 待切 multi-push + github fallback 待移除(06-08 review)(FORGE-1)

### 🧠 记忆/substrate
- **[med] memory_decay_importance 复合衰减把耐久记忆压到阈下,importance 虚低污染排序** — `sqlite.rs:4484-4487` 注释自承 thread 97 collateral root cause(每次调用重乘 0.5^(age/hl) 且不 bump updated_at)。改为基于原始 importance + 绝对 age 单次计算。(F5)
- **[med] M5 edge-coverage 须排除 kind=skill(catalog 污染分母)+ memory_edges 无 ON DELETE CASCADE 致悬空边** — M5 暴跌 0.0346→0.006 是测量假象。修 M5 定义 + 加 CASCADE。`lesson_substrate_stock_metrics_confounded_by_skill_catalog_20260529` (TD-06)
- **[low]** P4b.2 源记忆 tag/content 重写推迟(`mcp_tools.rs:12046`)(DEBT-02) / M7 age-gate 未 ship(已自愈,nice-to-have)(TD-07) / theme_cos 后续 prompt 再注入 backlog 未建(AB-DEBT-09)

### 🤖 Agent 编排与具身
- **[med] send_input 在 codex/gemini/opencode 后端未实现(交互 PTY 模式 P2)** — 三后端直返 InvalidArgument。revive=master-worker(#1787)复活且需向运行中子 agent 续发输入时实现。(DEBT-04)
- **[med] steer 控制平面新增常驻跨进程注入信任面** — 已 ship/live;诚实威胁模型=防静默/意外注入,非防 shell-可达直跑。接受为 owner 选 B 的有意信任面,保持守护集。`project_desktop_embodiment_dock_20260601` (STEER-1)
- **[low]** R2.5 跨域 OOPIF 裸 CDP websocket 旁路(`chromium_cdp.rs:1384`,等上游 chromiumoxide 修)(DEBT-03) / steer probe 过渡产物 `steer_release.py` 去留未定(STEER-2)

### 🖱️ Linux computer-use
- **[med] host-confirm 诚实威胁模型=防静默 mutation 非 agent-proof 沙箱**(有意边界)— shell-可达机器不可能做成沙箱。`project_linux_computer_use_v0_v1_shipped_20260528` (HC-1)
- **[med] daemon headed 浏览器在 tiling compositor 抢布局(VK_SURFACE_LOST)** — 靠 sway 浮动缓解(已 canonical 进文档);根治待 dock webview 迁 Tauri(owner-gated)。(HC-2)
- **[low]** vision_grounding_ocr 硬化已 ship 但 MCP 新参未 live 验证(VIS-1) / 确定性 OCR cage 测试难做(VIS-2) / Qt a11y 路径整体 untested(AB-DEBT-12)

### 📊 可观测性与自演化
- **[low] gap 表 C2/C3 注释陈旧:标 `defer #7a37d28e` 但 `context_pressure_estimate`/`tool_call_attention_report` 已是注册工具** — `main.rs:12022/12031` 规约-实现漂移,会误导"还没建"。改 status=Closed/Shipped 防 narrative-shopping。(DEBT-06)
- **[low]** Replay `--seed` 形参保留但无效(等上游 AiOT seeded 接线)(DEBT-05) / A1/B1/B3 recall-timing v0 待 sibling cross-check(AB-DEBT-10) / Avatar 协议长会话非-Codex dogfood pending(AB-DEBT-08) / event-spine 10 轨只 ship 2 轨(AB-DEBT-05) / avatar 透明仅 wlroots 验证,GNOME/KDE/X11 alpha 未验(owner 用 sway 不阻塞)(DEBT-10)

### 🏗️ 协作协议 / 基础设施脆弱性
- **[med] daemon trio 非 systemd 管理:reboot 后靠 ad-hoc shell 启动** — `.service` 已存在于 `scripts/systemd/`,本机未 enable。`systemctl --user enable --now` 3 个 service。(TD-14)
- **[med] /Data /Programs /Media 在 ntfs-3g fuseblk,重 CPU 负载下 D-state wedge** — state.db 在 /home ext4 不受影响。治本=热路径迁原生 ext4/xfs。`lesson_data_partition_ntfs3g_fuseblk_dstate_under_load_20260602` (TD-15)
- **[med] aio2 kernel vmap lock 争用 soft-hang** — 主源 AiOT daemon 已 P6 停用,26.04+内核7.0 是治本赌注(需累积 uptime 复核)。`lesson_kernel_vmap_softhang_2026_05_19` (TD-16)
- **[med] deploy 后跑的 binary 非 deploy 的那个(wrapper 被 ELF 覆盖→.real 孤儿+SVD env 丢)** — 部署后必 `file ~/.local/bin/agent-bridge` 确认是 shell script。`lesson_wrapper_clobbered_orphans_real_deploys_2026_05_23` (TD-11)
- **[med] `COORDINATION_STATE_MACHINE_LAYER.md` untracked(owner 选不提交)** — 知识仅活在 untracked 文件+MEMORY.md,节点重装有丢失风险。确认 owner 意图:保留则 `git add`,有意不提交则显式标"不入库"。(AB-DEBT-04)
- **[low]** cargo incremental 漏更(部署前验特征串,HC-3) / stash pop 静默部分还原(改用独立 worktree clean-build,TD-12) / 升级前 fstab nofail + DM fallback(已沉淀硬规则,TD-18)

---

## B. 非债务 · 勿翻案(P6 null-path / 外部约束 / 有意边界)

> 均经证伪或属外部硬约束,**不应被当待办或缺口**。列出仅防被误当 open gate 翻案。

**P6 死路**:substrate 作 recall backend 无增益(NO_RECALL_ADVANTAGE,`decision_substrate_no_recall_value_v22_p6`)/ neighbors_of attention-bias 继承 T31 五层证否 / PageRank 图排序 observability-only / ECC delta① error-resolution 在 CC 上结构性不可行(PostToolUse 不 fire `tool-error`,`lesson_cc_posttooluse_no_fire_on_tool_error`)/ P-α 作认知结构路径证否(co-firing 太稀疏)/ rmux-sdk 采纳 P6(走 `AB_TMUX_BIN=rmux` 一行 drop-in,`decision_rmux_steer_backend_p6_20260601`)

**外部硬约束/有意降级**:CGNAT 阻断 Tailscale direct(修在 ISP 侧,`lesson_aio2_cgnat_blocks_tailscale_direct`)/ `/mcp reconnect` 不刷已有工具 schema(MCP 客户端约束,`lesson_mcp_reconnect_stale_existing_tool_schema`)/ Store trait 默认桩 `not implemented`(只对非 SQLite 后端 fire,有意降级非 bug)/ codebase_symbols NULL embedding lazy-fill(有意设计)

---

## C. 非债务 · PARKED 等触发(revive 条件未满,勿主动建)

- **master-worker RFC #1787 整体 PARKED** — revive 双条件:① crates/agent/ quiesce 或 owner ACK 碰撞 #4 + 真多-agent 硬需求;② Codex essential 暴露 agent_inbox/agent_message + durable worker-loop 契约。`project_master_worker_orchestration_rfc_posted_20260524` (MW-1)
- MS-P2P 全对等同步 PARKED(触发=DERP-only 破 SLO)/ camofox 稳定元素引用唯一可借但未排期(`decision_camofox_browser_no_adopt_borrow_stableref_20260602`)/ Synaptic Dream β/γ trigger-gated(等 α 数据,`vision_continuity_synaptic_dream`)/ Dream-autotune v0 PARKED / Shadow Cortex(RFC-v25)review-only / D3.3 Warp WebView 延期 / dock 原生托盘留给 Tauri
- **另**:LCC-A1/A2/E1/V1、LCC affect/voice 暂缓 — codex/其它车道有序排期中,**非 debt**,记录为开放协调面(forum #98 / #92 / #79 / #94)。

---

## ⏰ 时间敏感 gate 日历

| 日期 | gate | owner | 状态 | action |
|---|---|---|---|---|
| **06-02**(逾期1天) | sibling-activation 14d observability | **AiOT `#e6fe8c44`** | binding verdict 待 owner;**AB cross-reference(P-α Day-14)已 05-29 闭 clean** | depth_ratio_ema 是 AiOT 指标非 AB;AB 不越权裁决,verdict 去 AiOT 侧确认 (GATE-2) |
| **06-08** | forge migration 30d review | AB/Mac Pro | OPEN | 确认 Mac Pro 已切 multi-push;稳定则移除 github fallback (FORGE-1) |
| **06-10** | P-ε Day-28 P1..3 复审 | AB | OPEN(prep 已做) | fresh substrate_audit,M5 必排除 kind=skill;P3 预标 CONFOUNDED(0.022 仍<<0.20) (PE-1) |
| **06-11** | Collab Protocol v0(C1/C2/C3) | AB | OPEN | C2/C3 已 ship;**C1 `CLAUDE-SIBLING.md` 未落地**(~ 与 repo 根均无)→ 反算 baseline 出裁决 (GATE-3) |
| **06-15** | §7 strategic decoupling park-deadline | AB | OPEN | 验 `dream weekly` 是否 autonomous 跑出;看 AiOT 是否给 L2-readiness 信号 (GATE-4) |

> **已闭勿误当 open**:GATE-5 Day-14 P-α(CLOSED 05-29,3/4 HELD)/ GATE-6 #1787 决策窗(RESOLVED 05-29 回落 A1+PARK)。

---

## ✅ 已治本 · 勿重开

- stale `.git/index.lock` 破坏 sync → `0d01d49` `reap_stale_index_lock()` + 故障注入 live 自愈
- ISO-8601 TEXT 时间戳破坏 export → codex v32 `e81b295`(双节点 bad rows=0;仅 incidents thread 35 status 待翻 resolved)
- deploy race 陈旧分支覆盖 → `scripts/deploy_from_master.sh`(反退化特征门+必备份)
- sync fallback 不修 branch divergence → `sync.rs` 已加 `reset --hard origin` + alert + reaper
- chrome 悬空 SingletonLock `exists()` 失效 → `chromium_cdp.rs:265` 无条件 `remove_file`
- **MCP wedge(deadline + browser timeout)→ `4eae961` 已合 origin/master(551bb8d)+ live binary 已部署(01:52)+ 运行中 server 已激活**(本账本初稿误标"未合",亲验勘误)

---

## 核验修正(初稿 finding vs 代码现实)

- **#1 优先级作废**:workflow 综合官标"MCP wedge 修复未合 master(HEAD 9fff602 无 mcp_call_deadline)"。亲验:`origin/master=551bb8d`,`merge-base --is-ancestor 4eae961 origin/master`=YES,live binary 含 `AGENT_BRIDGE_MCP_CALL_DEADLINE ×2`,运行中 server(PID 1125005,02:00 启动)执行非-`(deleted)` 新 binary。**根因=综合官拿陈旧本地 HEAD(落后 origin/master 4 commit)比对**。教训:跨多 lane 高速 ship 期,"未合"判断必须对 `origin/master` 而非本地 checkout。
- **GATE-2 归属修正**:rollback 目标 `dd40fd3/2d4e5b6/c3b28a2` 在 agent-bridge 仓全 MISSING(是 AiOT 仓 commit);depth_ratio_ema 是 AiOT 认知 daemon 指标。**agent-bridge 是 cross-reference 观测方,不是裁决方**,不得单方面 `git revert` 或判 VALIDATE/OBSERVE/ROLLBACK。
- TD-04 SingletonLock 清理代码已修(`chromium_cdp.rs:265` 无条件 `remove_file`),非 `exists()`。
- DEBT-06(gap 表 C2/C3 陈旧注释)确证为真。
- AB-DEBT-04(COORDINATION_STATE_MACHINE_LAYER.md untracked)确证为真。
- F5(decay 复合衰减)代码注释 `sqlite.rs:4484-4487` 自承,确证为真。
