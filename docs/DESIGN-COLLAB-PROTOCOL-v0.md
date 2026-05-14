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

**实现路径** (轻→重)：
1. **prompt-only** (最便宜) — sibling agent system prompt 加 directive；user 监控 forum/memory 比是否上升
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

### 3.4 · C3 — Alert-on-Drift in daemon

**Rule**: daemon background tick 每 30s 跑 self-check；异常 → forum_post(kind=alert) + notify MCP。

**Self-check points** (每条 ≤5 行 SQL/syscall)：

| 检测项 | 信号 | 阈值 |
|---|---|---|
| S1 own state.db FD `(deleted)` | `readlink /proc/self/fd/<state.db>` 末尾匹配 ` (deleted)` | 立即 fire |
| S2 memories.count 突降 | 当前与 5min 前快照对比 | drop >5% in 1 tick |
| S3 forum_threads.count 突降 | 同上 | drop >0 in 1 tick (任何减少都报，forum 极少被删) |
| S4 memory_edges.count 突降 | 同上 | drop >5% |
| S5 schema_meta.version 变化 | tick 间对比 | 任何变化都报（migration 应是显式动作） |

**Alert post format**:
```
[ALERT] <signal> at <ts_utc>
[evidence] <metric_before> → <metric_after>
[fd_state] state.db = <path> [deleted|live]
[suggested action] <inspect_cmd> / <forum_post:thread/N>
```

**False-positive mitigation**:
- daemon checkpoint 不该触发 S1 (FD path 不变)；如果触发说明真有 unlink+replace
- S2-S4 排除"正常 GC tombstone / dream-promote / replay" 等已知大批量动作 — 这些动作前 daemon 已经写 `tool_invocations`，self-check 看到对应 tool 在窗口内可 suppress alert
- S5 永远是 explicit migration，无 false positive

**Alert rate-limit**:
- 同一 signal 1 hour 内最多 1 次 forum_post（避免 spam）
- alert 自身也是 memory write（kind=alert，自动 archive 30d 后 GC）

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

| Baseline | 反算方法 | 当前数值估计 |
|---|---|---|
| B-C1.1 sibling 知情延迟 | grep 14d hook-runs.jsonl + dream-replay.log + cross-sim log，看 sibling 跑了某 op 与对应 forum_post 时间差 | 估计 NaN（绝大多数 sibling op 无对应 post） |
| B-C1.2 sibling-initiated post 数 | sqlite `SELECT COUNT(*) FROM forum_posts WHERE author LIKE '%sibling%' AND created_at > unixepoch('now','-14 days')` | 估计 = 0 |
| B-C2.1 同 resource 多 sha | `find /tmp ~/.cache -name "state.db*" -newer ...` + sha256 去重 | 当前 = 3（blood-sample b3db70ba / recovered 1463275d / new 40MB 未 sha） |
| B-C3.1 unlink→detect 延迟 | 本次事件 user-observed = 6h+（10:13 unlink → 16:36 detect via audit） | ≥360 min |

**这步必须先做** —— Gate (§9) PASS 的前提是 C1/C2/C3 各有可比较的 before-after。

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

## 7 · Ship order (act phase)

```
C3 (daemon-self alert)  ←  最便宜，~3-4h impl，不需要 sibling 配合
   │
   ├── self-check S1-S5 各加 5 行
   ├── tick interval 调到 ≤60s（当前 30s 已够）
   ├── forum_post / notify 调用接入
   └── 单元测试 +5

   ↓ ship + 观察 7 天

C1 (forum broadcast obligation)  ←  prompt-only 一晚上 ship
   │
   ├── sibling agent system prompt directive
   ├── 监控 sibling-initiated forum_post 占比
   └── 14d 后判 P1/P2

   ↓ 观察 7 天

C2 (lockfile + canonical CLI)  ←  最大工程量，可能不必要
   │
   ├── 看 C3 是否已经把 F2/F3 频次降到 ≤1 (因为 alert 让 sibling 立即知情)
   ├── 如果是 → C2 可降优先级 或 skip
   └── 如果不是 → 上 lockfile + rescue-snapshot CLI
```

## 8 · Open questions

1. **Q-1**: sibling agent system prompt 改在哪？是 wrapper 启 sibling 时注入？还是 sibling 自带 CLAUDE.md/CLAUDE-SIBLING.md？(影响 C1 ship 路径)
2. **Q-2**: alert post 自动按 `discussed_at` 边连到 origin event 还是 caller 手动 wire？(影响 C3 implementation)
3. **Q-3**: rescue-snapshot CLI 是否 cross-machine（远端 daemon FD via tailnet）还是 same-machine only？(影响 C2 scope)
4. **Q-4**: forum_post 写入 state.db，但 alert 触发往往是 state.db 异常时——会不会写到错的 db？(关键 race 风险)
5. **Q-5**: 是否需要 forum board `collab-protocol` 单开一个，还是用现有 `main` / `v22-design`？

Open questions 在 forum 公告时 ping sibling 一起决。

## 9 · Gate

**Gate-collab v0 PASS 条件** (4-week review window, 2026-06-11)：

1. C1/C2/C3 三组 P1/P2/P3 全部有可判定的 PASS/FAIL/INCONCLUSIVE 结论
2. **新失败模式 < 旧失败模式** —— 14d 内若引入 ≥1 新失败模式（如 lockfile deadlock），需有 retro memo
3. sibling agent (至少 1 个独立 session) 在 28d 内**主动** 用过 forum_post 沟通过 ≥1 次共享资源操作（C1 真实命中信号）

**Gate-collab v0 FAIL 行动**: 写 retro memo `lesson_collab_protocol_v0_failed_<reason>.md`；不立刻 ship v1，先用 4 周观察换设计假设。

---

## 10 · Bookmarks

- [[project_state_db_rescue_event_2026_05_14]] — 触发本 memo 的事件
- [[lesson_sibling_sweep_window_commit_mismatch]] — F4 案例
- [[lesson_verify_code_semantics_not_field_names]] — F6 案例
- [[feedback_cargo_fmt_sweeps_protected_files]] — sibling fmt-sweep 模式
- [[feedback_sibling_overwrites_during_edit_window]] — F2 同形
- [[feedback_sibling_commit_bundles_dropped_deps]] — F4 同形
- [[lesson_codebase_index_delete_then_walk_footgun]] — 历史 wipe-recover dance
- DESIGN-P-alpha 本 memo 的"daemon tick host"
- DESIGN-P-epsilon 本 memo 的"observability primitive"

---

## Status checklist

- [x] §0 root causes 三条明确
- [x] §1 G1-G5 acceptance tests 可执行
- [x] §2 non-goals 排除
- [x] §3 三 proposals architecture
- [x] §4 falsifiable predictions matrix
- [ ] §5 baselines 反算 (**do before Gate-collab v0 act phase**)
- [x] §6 risks / mitigations
- [x] §7 ship order
- [ ] §8 open questions answered by forum + sibling
- [ ] §9 Gate-collab v0 PASS evaluable @ 2026-06-11
