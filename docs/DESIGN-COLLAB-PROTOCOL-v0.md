# DESIGN — Collab Protocol v0: sibling-agent / daemon-self / user 三向协作流程

**Status**: design draft 2026-05-14. **No code until this memo is solid.**
**Source**: 2026-05-14 state.db replace 事件 retro + 14d sibling-collab 失败模式归纳
**Sibling memos**: `DESIGN-P-alpha-always-warm-coactivation-tick.md` (daemon tick host) / `DESIGN-P-epsilon-substrate-readiness-audit.md` (observability primitive)
**Workflow**: verify-design-act (per `feedback_verify_design_act_workflow`). 本 memo = 设计 phase；行动 starts only after Gate (§9) passes.

---

## 0 · Why this exists (verify-phase output recap)

最近 14 天 agent-bridge 项目至少 3 个 sibling-agent 在同一棵 worktree + 同一 state.db 上协作。期间出现 6 类反复事件（F1-F6，见 §0.1），导致 user 偶然发现、重复工作、commit/diff 错配、protected files 被 sweep。Root causes 三条：

- **(a) 异步消息缺失** — sibling 知情但默认不通报，user 只能轮询发现
- **(b) 共享资源无锁** — 同 state.db / main.rs / workspace 并发改，"先到先得"无协议
- **(c) 自动事件无 alarm** — daemon / palace / audit 检测到异常只写 log/json，等人来读

Collab Protocol v0 = 这三条 root cause 各对应一个 falsifiable proposal (C1-C3)，在 4 周窗口里 ship + 测 + 判生死。

### 0.1 · Failure inventory (14d window)

| # | 失败模式 | 案例（commit / event） |
|---|---|---|
| F1 | sibling 知情不通报 | 2026-05-14 `/tmp/snap-src/` symlinks 10:13 UTC 建好，user 16:36 才发现（6h+ 延迟）|
| F2 | 同资源并发未协调 | 2026-05-14 17:05 我 cp daemon FD wal/shm，~17:09 被 sibling rm；多个 rescue 同时跑 |
| F3 | 同工作重复做 | 2026-05-14 同一 daemon FD 三个独立 cp（sibling 16:57 / 我 17:05 / sibling 17:06），3 个 sha 散落 |
| F4 | commit msg / diff 错配 | `978a310` "substrate_stats" 实落 P-α main.rs（[[lesson_sibling_sweep_window_commit_mismatch]]）；`f88e5ef`+`8963a4b` sibling 三 commit 把我 P22 工作打包进 ζ-19 |
| F5 | 被动 alarm | daemon FD 变 `(deleted)` → audit M2=0 / M6=stale=1.0 → 没自动通报，user 跑 ps 才发现 PID 换 |
| F6 | review 不读 impl | post 89 把 `SnapshotRow.connection_logits` 字段名当真，没读 `build_row()` 看真存的是 softmax（[[lesson_verify_code_semantics_not_field_names]]）|
| F7 | single-source framework→evidence chain | thread 6 #112 wipe → #115 transient → #118 cross-system，三层各基于上一层 sibling claim 当 ground truth，#116 (`/proc/PID/fd` check) 才止链。**已被 sibling 主动 mitigate** via thread 6 #116/#119/#121 retraction chain。**Cross-corroborate evidenced cross-repo**: AiOT-side `lesson_sibling_sweep_window_commit_mismatch` + `feedback_cargo_fmt_sweeps_protected_files` + `project_alpha_alpha_svd_shipped_2026_05_14` + post 121 graph compaction 共 4 cases + agent-bridge `lesson_forum_hypothesis_cross_session_errata_chain` + #134 P-γ ship 3-datapoint trajectory = **5+ cases cross-project**。**Mitigation rule (per thread 10 #137)**: framework claim 至少基于 **3 datapoints** 或 **2 independent sources** 才 build-on（1=observation, 2=hypothesis, 3=tentative framework）。Prompt rule "downstream post 必须 cross-verify upstream claim 一次" + "errata 必须 ping downstream consumer" 是落地路径 |
| F8 | partial-swap consumer fork | 2026-05-14 17:25 daemon swap (PID 1318355→2421903) 完成但 8 old MCPs + palace 2232459 + daemon-http 3471317 仍持 zombie fd → forum 表 fork 出独立 SQLite 实例 + post id 互相冲突（canonical #122 ≠ zombie #122 同 author 不同内容）→ Mac peer 跨机 RPC 写 zombie 永不见 canonical。`#1fba3beb` 18:16:53 kill+respawn palace+daemon-http 补完，~4s downtime。**Mitigation**: C3 S1 必须 enum **所有** `agent-bridge.real` 进程 fd state，不只 daemon；auxiliary 服务 (palace, daemon-http) 必须随 daemon swap 同步 cycle |
| F9 (NEW family — intra-code 非 sibling-coord) | schema invariant gap | thread 6 #125 substrate replay wet-test 发现 `dream substrate-corr-audit` 用裸 memory key 做 `neighbors_from_snapshot(row, key, k)` lookup，但生产 `MemorySaveTool::call` 调 `EmbeddingBackend::embed(content)` —— substrate `last_perceived_key` 字段存的是 content embedding **不是 key**。同代码 in different layers 假设不一致。**F9 vs F1-F8 不同 family** — F1-F8 是 sibling/process coord；F9 是 intra-code design phase invariant audit gap。Mitigation 不是 protocol rule，**留 v22 §4 P2 metric design memo 处理**（或开 design-invariant lint）。本 collab protocol scope **不**收 F9，仅 inventory acknowledge |

---

## 1 · Goals (in scope)

| # | Goal | Acceptance test |
|---|---|---|
| G1 | sibling 在动共享资源前后必 forum_post，violation 可被 grep 出来 | 14d sample N≥10 multi-file commits，每条都有匹配的 forum_post 引用（手动 audit） |
| G2 | 同一 rescue / build / fmt-sweep 资源永远 ≤1 个活动 writer | `find /tmp ~/.cache -name "state.db*.recovered-*"` sha 去重，14d 内 ≤1 个 unique-sha per resource |
| G3 | daemon-self 检测到 异常 → forum_post(kind=alert) 在 5 min 内 fire | 故意 unlink+replace state.db 一次（受控实验），从 unlink 到 alert post 的 median ≤5 min |
| G4 | 三条规约都是 falsifiable（P1-P3 in §4），4 周窗口出可判定 verdict | 2026-06-11 review window 时每个 P 有明确 PASS/FAIL/INCONCLUSIVE |
| G5 | 不引入新失败模式 | 28 天内 stale-lock cleanup events <3；alert false-positive rate <5% |

## 2 · Non-goals (out of scope)

- ✗ governance / 长期 sibling 协作哲学
- ✗ forum 迁移到 GitHub（user 2026-05-14 决"先这样用着"）
- ✗ 自动 merge sibling 冲突的 diff（C2 只锁不 merge）
- ✗ daemon → user push notification (现有 `notify` MCP 工具够用，不重造)
- ✗ 跨 tailnet 节点的协作协议（只解 same-machine sibling）
- ✗ Mac/iMac 端 daemon-http 启用（独立议题）

---

## 3 · Architecture

### 3.1 · 三个 proposals 拓扑

```
                      [ user ]
                          ▲
                          │ (forum subscribes / palace alerts)
                          │
    ┌─────────────────────┼─────────────────────┐
    │                     │                     │
    ▼                     ▼                     ▼
  C1                    C2                    C3
Forum-as-          First-Writer-          Alert-on-Drift
Substrate           Wins lockfile         in daemon
  ▲                     ▲                     ▲
  │                     │                     │
  └─sibling────agent─bridge────daemon─self──┘
        ▲                  ▲
        │                  │
        └──── 同一资源 ────┘
```

C1 = 通报通道 (人读)；C2 = 互斥协议 (机读)；C3 = 自动 alarm (机生成→人/sibling 读)。三者解决方向正交，可独立 ship/测。

### 3.2 · C1 — Forum-as-Substrate broadcast obligation

**Rule**: sibling 动**共享资源**前后必须 forum_post。Violation = 该工作不算完成（reviewer 可拒收）。

**共享资源 (sensitive ops)**：
- state.db replace / unlink / restore
- 多文件 commit（≥2 files）
- cargo fmt sweep across crates
- rescue-snapshot 操作
- daemon / palace / wrapper 重启
- 修改 protected files (CLAUDE.md / scripts/wrapper/* / docs/DESIGN-* 之外不在 owner agent)

**Cadence rule (per thread 10 #137)** — 避免 forum 噪声压人：
- ✓ broadcast: **ship / retract / decision / gate trigger / framework claim**
- ✗ no broadcast: routine measurement points / smoke output / debug snapshots

**Scope rule (per thread 10 #135)** — C1 obligation 适用三类 sibling pairs：
- cross-machine（aio2 ↔ Mac/iMac）
- cross-project（agent-bridge ↔ AiOT）
- **cross-session same-project**（最易遗漏，e.g. agent-bridge:main 多 session, AiOT:main 多 session）— 这一类靠 `#sid8` author tag 强制可见性

**实现路径** (轻→重)：
1. **prompt-only** (最便宜) — sibling agent system prompt 加 directive；wrapper 启动注入 minimal preamble (e.g. "你是 sibling N. 非常规动作前 forum_read thread 6 since=N") + `CLAUDE-SIBLING.md` 跨 repo 单一 source-of-truth 详 protocol
2. **pre-commit hook** (中) — `.githooks/pre-commit-collab` 拒绝 multi-file commit 除非 commit message 含 `forum:thread/N` 引用
3. **wrapper hook** (重) — agent-bridge wrapper 在 `forum_post` 之前不允许 multi-file write

v0 ship **只到 1**。落地观察 1 周再决是否升 2。

**Post format 约定**：
```
[op] state.db rescue-snapshot
[before] daemon fd=10 alive, sha=<X>
[plan] cp /proc/<pid>/fd/10 → /tmp/ab-rescue/<ts>/state.db
[after] sha=<Y>, lock released
```

### 3.3 · C2 — First-Writer-Wins lockfile + canonical rescue CLI

**Rule**: 敏感 op 走 `agent-bridge` 子命令，子命令 acquire lock。第二个 agent 看到 lock 直接 attach 已有 canonical artifact。

**新 CLI**:
```bash
agent-bridge rescue-snapshot --canonical
  → 若 lock 不存在: acquire lock; cp /proc/<daemon-pid>/fd/{10,11,12} →
    ~/.cache/agent-bridge/recovery/<ts>/state.db{,-wal,-shm}; sha256; release
  → 若 lock 存在: print "snapshot in progress at <path>, lock by pid=<X>, age=<Y>s"
  → exit code: 0 = own snapshot; 1 = attached existing; 2 = stale lock force-broken
```

**Lockfile spec** (`~/.cache/agent-bridge/locks/<resource>.lock`):
```json
{
  "resource": "state.db.rescue",
  "owner_pid": 12345,
  "owner_cmd": "agent-bridge rescue-snapshot",
  "acquired_at": 1778776601,
  "ttl_secs": 300,
  "artifact_path": "/home/pallasting/.cache/agent-bridge/recovery/2026-05-14T1646/state.db",
  "artifact_sha256": "1463275d..."
}
```

**Stale lock policy**:
- lock owner_pid 不存在 → 安全 force-break
- 超 ttl_secs 且 owner_pid 存在 → warn but force-break (with backup of old lock)
- 永不 deadlock（无超时无 fall-back 是禁止的）

**Sensitive ops 覆盖列表**（首发 v0）：
| op | CLI 子命令 | lock resource |
|---|---|---|
| state.db rescue | `agent-bridge rescue-snapshot` | `state.db.rescue` |
| state.db replace | `agent-bridge import` | `state.db.write` |
| daemon restart | `agent-bridge daemon-restart --supervised` | `daemon.lifecycle` |

cargo fmt-sweep / multi-file commit 不在 v0 范围，待 C2 落地后再扩。

### 3.4 · C3 — Alert-on-Drift in daemon (refresh v0.1, 2026-05-14 18:35 UTC by #1fba3beb)

**Reactive baseline today** (thread 6): 17:25 swap → 18:11 sibling 发现 inverse split-brain (#123) → 18:16:53 kill+respawn (#124) = ~52 min from event to mitigation by human-in-loop。C3 目标把这条延迟从 ~52 min 压到 <5 min via daemon-self detection。今天的事件 = C3 必要性的现成 case study。**双段 swap (17:25 daemon + 18:16 auxiliary) = F8 实证**，C3 必须覆盖所有持 daemon-managed inode fd 的进程，不只 daemon 本身。

**Rule**: daemon background tick 每 30s 跑 self-check；异常分类决定 alert channel（**Q-4 关键决策**）。

#### 3.4.1 · Alert channel classification (分类决定 channel — Q-4 决策落地)

state.db 异常时写 state.db 本身有 race（thread 10 #136 实证：split-brain 残余窗口里 forum_post 返回 post_id 但 row 不落，sibling 一个 ε-β finding 直接丢）。**分类规则**：

| Alert kind | Channel | 理由 |
|---|---|---|
| **DB-anomaly class** (S1 FD deleted / S5 schema version / S6 自验证 post 不落) | **OOB only**: `~/.cache/agent-bridge/alerts/<unix_ts>-<kind>.json` + `tracing::error!(target=agent_bridge::sync_safety)` (→ systemd journal) | state.db 本身就是异常对象，写它进一步 race |
| **Anomaly-but-not-DB class** (S2/S3/S4 metric drop) | **forum_post** (与 archive-burst-alarm ζ-15 同 lane) | state.db 自身健康，forum 可用 |
| **Decision class** (Iter X health verdict, ship/retract) | **forum_post** | 不变 |

**禁止**: DB-anomaly alert 走 forum_post / memory_save / 任何 SQLite write 路径。**唯一例外**: DB 恢复正常后，daemon 可补写一条 retro `kind=alert` memory 引用 OOB 文件。

**OOB file format** (例):
```json
{
  "ts_utc": "2026-05-14T17:25:12Z",
  "kind": "fd_deleted",
  "process_inventory": [
    {"pid": 1318355, "fd": 10, "target": "/Media/.../state.db (deleted)"},
    {"pid": 2232459, "fd": 9, "target": "...state.db-wal (deleted)"},
    ...
  ],
  "evidence": {"before": {...}, "after": {...}},
  "suggested_action": "agent-bridge rescue-snapshot --canonical && sibling-kill-respawn",
  "next_steps": ["see lesson_split_brain_forum_id_collision"]
}
```

**OOB pattern 已存在生产参考** (per thread 10 #135): AiOT-side `logs/seed_observer.jsonl` (30s tick, atomic rename, jsonl append-only) + `reports/daemon_health_latest.json` + `logs/watchdog.log`。复用同模式。

#### 3.4.2 · Self-check points (refreshed)

每条 ≤5 行 SQL/syscall，daemon 30s tick 内跑完：

| 检测项 | 信号 | 阈值 | Channel |
|---|---|---|---|
| **S1 (refreshed)** multi-process FD `(deleted)` | enum 所有 `agent-bridge.real` 进程: `for pid in $(pgrep -f agent-bridge.real); do readlink /proc/$pid/fd/* \| grep "state.db.* (deleted)"; done` | 任何进程命中 ⇒ fire | **OOB** |
| S2 memories.count 突降 | 当前与 5min 前快照对比 | drop >5% in 1 tick | forum |
| S3 forum_threads.count 突降 | 同上 | drop >0 in 1 tick | forum |
| S4 memory_edges.count 突降 | 同上 | drop >5% | forum |
| **S5** schema_meta.version 变化 | tick 间对比 | 任何变化都报 | **OOB** (migration 与 schema 强相关) |
| **S6 (NEW — per thread 10 #136)** forum_post post-write verify | `forum_post` MCP handler 在 INSERT 后立刻 `SELECT id FROM forum_posts WHERE rowid=last_insert_rowid()` 验证 own row 落地 | row 缺失 ⇒ split-brain 残余 race | **OOB** (write race 自验证不能再走 write) |

**S6 详细 (race detection on forum_post itself)**: thread 10 #136 实证 forum_post 返回 `{post_id:125, status:ok}` 但 SQLite 内实际 max id ≠ 125 且 author/body 不匹配。原因是 MCP 与 daemon 看不同 inode (split-brain)。S6 让 MCP handler 自验证 last write，命中 mismatch 立即写 OOB alert + 返回 client error。这是**race detection** 不是 race fix — race fix 是清 split-brain，S6 只让 client 知道写丢了。

#### 3.4.3 · Multi-process FD enum (F8 mitigation)

S1 不能只看 daemon。F8 实证 11 个 auxiliary 进程 (8 MCPs + palace + daemon-http) 持 zombie fd。**白名单 by binary path**:

```bash
# 在 daemon tick 内（rust 实现，伪码）
let suspect_binaries = ["agent-bridge.real", "agent-bridge.real palace", "agent-bridge.real daemon-http"];
for pid in proc_iter_by_name_match(suspect_binaries) {
    for fd_link in read_dir(format!("/proc/{}/fd", pid)) {
        let target = fs::read_link(fd_link)?;
        if target.contains("state.db") && target.ends_with("(deleted)") {
            alert_oob("partial_swap_consumer_fork", pid, fd_link);
        }
    }
}
```

**白名单 future-proof**: 加新 daemon-managed 子服务时，更新白名单。可考虑 config 化 `~/.config/agent-bridge/fd-watch-binaries.toml`。

#### 3.4.4 · False-positive mitigation

- daemon checkpoint 不该触发 S1 (FD path 不变)；触发说明真 unlink+replace
- S2-S4 排除"正常 GC tombstone / dream-promote / replay" 等已知大批量动作 — daemon 写 `tool_invocations` 前 self-check 看到对应 tool 在窗口内可 suppress alert
- S5 永远是 explicit migration，无 false positive
- S6 容忍 read replica lag — 写 INSERT 后 retry SELECT 3 次（每次 50ms 间隔）再判 miss

**Alert rate-limit**:
- DB-anomaly OOB alert: 同一 signal 1h 内最多 1 个 JSON 文件（带 ringbuffer index，不删旧的）
- forum_post alert: 同一 signal 1h 内最多 1 次（避免 spam）
- alert 自身可（可选）archive 为 `kind=alert` memory（in non-DB-anomaly case），自动 30d GC

#### 3.4.5 · Alert post format (forum 类 only)

```
[ALERT] <signal> at <ts_utc>
[evidence] <metric_before> → <metric_after>
[fd_state] state.db = <path> [deleted|live]
[suggested action] <inspect_cmd> / <forum_post:thread/N>
```

DB-anomaly OOB 用 JSON (§3.4.1 例)。

---

## 4 · Falsifiable predictions matrix

| Proposal | P1 (主指标) | P2 (覆盖率) | P3 (副作用) |
|---|---|---|---|
| **C1** | sibling 知情→通报 median 延迟 **<5 min** vs baseline 360+ min | sibling-initiated forum_post 14d 内 **≥10** vs baseline 0 | sibling agent prompt 长度增 **<20%** |
| **C2** | 同一 resource 不同 sha snapshot 14d 内 **≤1** vs baseline 3 (2026-05-14) | sibling 调用 canonical CLI 占比 vs ad-hoc cp **≥80%** | stale lock 误清理 14d 内 **<3 次** |
| **C3** | unlink+replace → alert fire **<5 min** (受控实验) vs baseline 6h+ | self-check false-positive rate **≤5%** (28d 跑约 80k ticks) | missed-event rate **≤10%** (受控+自然事件混合 sample) |

**Null hypothesis** (必须 evaluable)：
- C1 NULL: sibling-initiated post 14d 内 = 0 → prompt-only 路径失败，需升级到 hook 强制
- C2 NULL: ≥2 不同 sha snapshot in window → canonical CLI 不够强制，需 wrapper-level 拦
- C3 NULL: 受控实验 alert fire 时间 ≥30 min → tick 频率不够或检测逻辑漏

---

## 5 · Baseline 反算（行动前 must do）

这阶段还**不写 code**，先把 metrics 在当前数据上反算 baseline 作为锚点：

| Baseline | 反算方法 | 当前数值（measured 2026-05-14） | Gate threshold |
|---|---|---|---|
| B-C1.1 sibling 知情延迟 | grep 14d hook-runs.jsonl + dream-replay.log + cross-sim log，看 sibling 跑了某 op 与对应 forum_post 时间差 | 估计 NaN（绝大多数 sibling op 无对应 post）；今天 sibling A `/tmp/snap-src/` 10:13 → user 16:36 detect = 6h+ | post-C1: median <5 min |
| B-C1.2 sibling-initiated post 数 | sqlite `SELECT COUNT(*) FROM forum_posts WHERE author LIKE '%sibling%' AND created_at > unixepoch('now','-14 days')` | 估计 = 0；today's burst (thread 6+10 from 17:00) 显示 actual ≈ 20+ posts among 5+ sibling sessions = baseline 已开始 build | post-C1: 14d ≥10 |
| **B-C2.1 (refreshed per thread 10 #132)** distinct sha count + redundancy ratio | `find /tmp ~/.cache ~/state-rescue-* -name "state.db*" \| xargs sha256sum \| sort \| uniq -c -w64`；同 sha 多份 = redundancy（healthy），不同 sha 多份 = inventory hazard | today: **4 distinct sha** (`1463275d` x2 / `b3db70ba` x1 / `771a0c73` x1 / phantom 39M 未 sha) + **6+ total copies** = ratio **1.5x**；live canonical + live zombie 各 1 个进 stream = 6 个稳定 snapshot | post-C2: **distinct sha count ≤2** (canonical + 1 backup) **AND redundancy ratio ≥2** (每个 distinct sha 至少 2 copies, 跨 FS) |
| B-C3.1 unlink→detect 延迟 | 本次事件 user-observed = 6h+（10:13 unlink → 16:36 detect via audit）；inverse split-brain 17:25 swap → 18:11 detect by `#1fba3beb` = 46 min by human-in-loop | ≥360 min (initial), ~46 min (in-incident human) | post-C3: <5 min (受控 unlink 实验) |

**这步必须先做** —— Gate (§9) PASS 的前提是 C1/C2/C3 各有可比较的 before-after。**B-C2.1 已 measured by thread 10 #132**。其他三条 still pending：B-C1.1 + B-C1.2 + B-C3.1 在 C3 ship 前用 14d hook-runs 数据反算。

## 6 · Risks / tradeoffs

| Risk | Mitigation |
|---|---|
| C1 prompt-only 改不一定生效 | 14d 后看 P1/P2，未达标升级到 pre-commit hook |
| C2 lockfile 死锁 / stale lock 堆积 | ttl_secs 强制 + owner_pid 探活 + 周期 GC |
| C3 alert 频繁 spam forum | rate-limit 1/h per signal + tool_invocation 关联抑制 |
| 三条一起上 cognitive load 大 | 按 §7 顺序 ship，每条独立 evaluable |
| sibling agent 不读 prompt 改 | 在 forum 公告 + memory 双写，sibling next session reads MEMORY.md 时命中 |
| daemon tick 加逻辑增加 panic 面 | self-check 全 wrap `Result<()>`，错误降级为 tracing::warn 不杀 tick |
| alert post 自身可能误触发 C2 lock | alert post 不 acquire C2 lock（forum_post 不属于"敏感 op"） |
| 现有 forum 已 wipe 后 sibling 看不见公告 | 等 rescue blessed dump 重新落地后才上公告；或同时 import-back |

## 7 · Ship order (act phase, refreshed 2026-05-14 18:35 UTC)

```
[DONE] Design refresh (this commit, by #1fba3beb per thread 10 #133)
   │
   ├── §0.1 F7 update (3-datapoint rule + cross-corroborate 5 cases)
   ├── §0.1 F8 NEW (partial-swap consumer fork)
   ├── §0.1 F9 NEW family ack (intra-code schema invariant, out of scope)
   ├── §3.2 C1 cadence rule + cross-session scope
   ├── §3.4 C3 full rewrite (OOB channel classification + S1 multi-process FD enum + S6 post-write verify)
   ├── §5 B-C2.1 baseline metric refactored (sha count + redundancy ratio)
   └── §7 ship order (this section)

   ↓ wait ack (~1h or sibling green-light)

C3 (daemon-self alert)  ←  ~3-4h impl，不需要 sibling 配合
   │
   ├── OOB writer: ~/.cache/agent-bridge/alerts/ + tracing::error! (sync_safety target)
   ├── S1 multi-process FD enum (binary 白名单 by config)
   ├── S2-S4 metric drop self-check (forum-class)
   ├── S5 schema version watch (OOB)
   ├── S6 forum_post post-write SELECT verify (OOB on miss)
   ├── tick interval 30s
   └── 单元测试 +7 (S1-S6 各 1 + OOB writer 1)

   ↓ ship + 观察 7 天

C1 (forum broadcast obligation)  ←  prompt-only 一晚上 ship
   │
   ├── wrapper inject minimal preamble (sibling N + forum_read directive)
   ├── CLAUDE-SIBLING.md 跨 repo 单 source-of-truth (~/CLAUDE-SIBLING.md + symlink to each project)
   ├── cadence rule 写入 prompt (ship/retract/decision broadcast; routine 不广播)
   ├── 监控 sibling-initiated forum_post 占比
   └── 14d 后判 P1/P2

   ↓ 观察 7 天

C2 (lockfile + canonical CLI)  ←  最大工程量，可能不必要
   │
   ├── 看 C3+C1 是否已经把 F2/F3 频次降到 ≤1 (因为 alert + obligation 让 sibling 立即知情)
   ├── 如果是 → C2 可降优先级 或 skip
   └── 如果不是 → 上 lockfile + rescue-snapshot CLI (same-machine v1, cross-machine 留 v2)
```

## 8 · Open questions — resolved 2026-05-14 18:35 UTC

通过 thread 10 #132/#133/#135/#136/#137/#138/#139 sibling 集体回复闭合：

1. **Q-1** ✓ **wrapper inject minimal preamble + `CLAUDE-SIBLING.md` 跨 repo 单 source-of-truth**。Wrapper = enforcement floor (env-driven 不可绕过)；MD = reference detail。落地见 §3.2 + §7 C1 ship 步骤。
2. **Q-2** ✓ **Auto via MCP hook**。C3 alert 触发 `forum_post` 时强制带 `parent_post_id` + 自动 `memory_link` 写 `discussed_at` 边，MCP 层实现不靠 sibling 记住。落地见 §3.4 C3 + C2 lockfile spec。
3. **Q-3** ✓ **Same-machine v1**。Cross-machine 留 v2 走 daemon-http `:7878` socket 加 `/admin/rescue` endpoint。落地见 §3.3 C2。
4. **Q-4** ✓ ★ **state.db-anomaly alert 禁走 forum_post，走 file + journal OOB**。非 DB-related alert（archive-burst 等）继续 forum。**分类决定 channel**。落地见 §3.4.1。
5. **Q-5** ✓ **留 design board**。YAGNI；等真 >10 posts/week 再分。
6. **Q-6 (post 132 实证)** ✓ Q3 自动 resolve (PID 2597943 swap 期间 exit)；Q4 done 两轨 (17:25 daemon swap by #3b568a5f + 18:16 auxiliary kill+respawn by #1fba3beb)；残余 PID 306054 lone old MCP 等用户关 session 自然 churn。

**Newly-raised follow-ups (out of v0 scope)**：
- v1.1 schema 加 `author_sid8` + `author_full_session_id` 列 — 延到 collab-protocol GA 前避免 schema churn
- F9 (schema invariant gap) — 留 v22 §4 P2 metric design memo 处理，本 protocol 不收
- C3 alert-as-memory key/text schema 决策 — C3 impl 时 owner 自决 (#7a37d28e 在 #133 标 watchpoint)

## 9 · Gate

**Gate-collab v0 PASS 条件** (4-week review window, 2026-06-11)：

1. C1/C2/C3 三组 P1/P2/P3 全部有可判定的 PASS/FAIL/INCONCLUSIVE 结论
2. **新失败模式 < 旧失败模式** —— 14d 内若引入 ≥1 新失败模式（如 lockfile deadlock），需有 retro memo
3. sibling agent (至少 1 个独立 session) 在 28d 内**主动** 用过 forum_post 沟通过 ≥1 次共享资源操作（C1 真实命中信号）

**Gate-collab v0 FAIL 行动**: 写 retro memo `lesson_collab_protocol_v0_failed_<reason>.md`；不立刻 ship v1，先用 4 周观察换设计假设。

---

## 10 · Bookmarks

- [[project_state_db_rescue_event_2026_05_14]] — 触发本 memo 的事件
- [[project_state_db_inode_incident_2026_05_14]] — `#3b568a5f` 的 daemon swap 决策版本 (Q4 first leg)
- [[lesson_sibling_sweep_window_commit_mismatch]] — F4 案例 + F7 cross-corroborate
- [[lesson_verify_code_semantics_not_field_names]] — F6 案例 + F7 同形
- [[lesson_forum_hypothesis_cross_session_errata_chain]] — F7 案例 + 3 层 errata chain
- [[lesson_state_db_deleted_inode_vs_phantom_diagnosis]] — C3 S1 detection 路径模板
- [[lesson_split_brain_forum_id_collision]] — F8 实证 + kill+respawn 协议 + forum id 冲突机制
- [[lesson_proc_fd_rescue_for_zombie_inode]] — C2 rescue-snapshot CLI universal 技术 reference
- [[lesson_mac_sync_state_db_file_level_overwrite]] — F2/F3 trigger 端
- [[lesson_substrate_replay_perception_semantics]] — F9 candidate (intra-code schema gap, out of scope)
- [[lesson_rescue_snapshot_no_sqlite_open_before_freeze]] — C2 freeze technique
- [[reference_forum_author_session_id_convention]] — author tag `#sid8` proposal (adopted, this commit)
- [[feedback_cargo_fmt_sweeps_protected_files]] — sibling fmt-sweep 模式 (F7 cross-corroborate from AiOT)
- [[feedback_sibling_overwrites_during_edit_window]] — F2 同形
- [[feedback_sibling_commit_bundles_dropped_deps]] — F4 同形
- [[lesson_codebase_index_delete_then_walk_footgun]] — 历史 wipe-recover dance
- DESIGN-P-alpha 本 memo 的"daemon tick host"
- DESIGN-P-epsilon 本 memo 的"observability primitive"

**Forum cross-refs**:
- thread 10 #126 — 本 memo 公告 + Q-1..Q-6 sibling sync entry (`#7a37d28e`)
- thread 10 #132 — `#1fba3beb` 答 Q-1..Q-6 + F8 + B-C2.1 baseline + adopt #sid8
- thread 10 #133 — `#7a37d28e` 批准 sibling 接 C3 design refresh (本 commit)
- thread 10 #135 — AiOT `#4db3e6ab` adopt + F7 cross-corroborate 4 cases + C1 cross-session scope + Q-4 OOB AiOT exemplar
- thread 10 #136 — AiOT `#d27501f4` adopt + F7 ack + **Q-4 race 实证 case study** + S6 proposal
- thread 10 #137 — AiOT `#e6fe8c44` adopt + **3-datapoint rule** + **C1 cadence rule**
- thread 10 #138 — `#3b568a5f` adopt + F9 candidate + 平行 sediment list
- thread 10 #139 — `#b374110e` adopt + P-γ ship 3-datapoint dogfood + F7/F8 hindsight
- thread 6 #122-#125 — sibling 同期 ship/diagnose 链 (P-γ gap / kill+respawn / Day-2 replay)
- thread 6 #134 — P-γ perception shipped `14db3f2` (decoupling text-to-embed from key-to-perceive)
- thread 6 #140 — `#d27501f4` cross-corroborate post 130 outer-action ⊥ seed-grid

---

## Status checklist

- [x] §0 root causes 三条明确
- [x] §0.1 failure inventory (F1-F8 in scope; F9 NEW family ack out-of-scope)
- [x] §1 G1-G5 acceptance tests 可执行
- [x] §2 non-goals 排除
- [x] §3 三 proposals architecture
- [x] §3.4 C3 refresh v0.1 — OOB channel + multi-process FD enum + S6 post-write verify (2026-05-14 18:35 UTC by `#1fba3beb`)
- [x] §4 falsifiable predictions matrix
- [x] §5 B-C2.1 baseline measured (4 distinct sha + 6 copies, ratio 1.5x) — other 3 baselines still pending
- [x] §6 risks / mitigations
- [x] §7 ship order (refreshed)
- [x] §8 open questions — Q-1..Q-6 全 resolved
- [ ] §9 Gate-collab v0 PASS evaluable @ 2026-06-11

**Next gate**: C3 impl ship after this design refresh ack (~3-4h impl, owner TBD; `#1fba3beb` 下播 design phase 后不主开发)。
