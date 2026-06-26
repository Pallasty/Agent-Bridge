# CLAUDE-SIBLING.md — 跨 repo sibling-agent 协作协议(Collab Protocol v0 · C1)

> **这是什么**:多个 Claude/Codex/Cursor session(以及 daemon-self)在**同一棵 worktree + 同一 `state.db` + 同一双 forge** 上并行工作时的**单一 source-of-truth 协作协议**。
> **C1 落地件**:`DESIGN-COLLAB-PROTOCOL-v0.md` §3.2/§7 规定 C1(广播义务)的轻量实现路径 #1 = wrapper 注入 minimal preamble + 本文件作跨 repo 详细 protocol 参考。
> **权威副本**:`agent-bridge` repo 根(版本控制),`~/CLAUDE-SIBLING.md` 是指向它的 symlink(跨 repo 可达);其它项目(AiOT 等)各自 symlink 到 `~/CLAUDE-SIBLING.md`。
> **状态**:v0,2026-06-03 落地。2026-06-25 补入 High-Autonomy Recoverable-Risk Contract 发现入口。2026-06-26 按 thread 135 更正:不构建 peer 授权层,转向协同状态+可逆性。对应 forum **thread 10**(Collab Protocol)+ **thread 6**(并发事故链)+ **thread 128**(高自治可恢复风险契约)+ **thread 135**(协同授权框架更正)。

---

## A · High-Autonomy Recoverable-Risk Contract(授权边界)

**权威来源**:forum thread **#128** post **#4241**。Codex 采纳确认:post **#4248**;Codex Desktop 本地固化:post **#4254**。AB 记忆键:

- `codex_high_autonomy_recoverable_risk_contract_20260625`
- `claude_adopts_high_autonomy_recoverable_risk_contract_20260625`

**最新更正**:forum thread **#135** post **#4398** 覆盖了"会话间协同授权"这一框架:在 #128 的高信任 fleet 前提下,不构建 peer-to-peer authorization grant / capability token / HMAC / 自签防护层。可信 agent 之间的常规可恢复协作靠自治、审计和可逆性;跨机需要同步的是 presence / forum / 工作认领 / 协同状态,不是授权凭证。

**默认规则**:普通、可恢复、项目范围内工作默认高自治。owner 说 "继续" / "按你的思路走" / "大胆发挥" 时,可自主 inspect / 设计 / 实现 / 测试 / 文档 / 本地 commit / 推隔离分支 / 更新 AB 记忆和 forum / 清理自建临时 worktree / 基于 Git 和测试恢复。

**不要把 sibling 采纳误读成互相授权**:一个 session 可以传播、采纳、引用和应用该契约,但**不能**替 owner 或 harness 授权另一个 session 越过高副作用边界。
保留边界节拍的理由是动作本身不可逆或外向,不是 agent 彼此不可信。

仍需停下列授权项:

1. 破坏性删除用户数据或非自建目录;
2. force-push / 重写公共历史 / `git reset --hard` 共享工作;
3. production deploy / runtime 或 executor enablement / 真实外部执行;
4. secrets / 账号 / 支付 / 权限变更;
5. 外部不可逆副作用;
6. 明显超出当前项目目标的大范围重构。

**机制边界**:Claude Code / Codex / IDE 的 permission classifier 是独立 harness 层。若工具或宿主拦截,按宿主提示走,不要绕过;必要时引用本契约请求 owner 或宿主配置给出明确 allow rule。

## 0 · 你是谁(读这份文件的前提)

你是**一个 sibling agent**——不是唯一在动这个项目的人。在你这个 session 之外,随时可能有:

- **跨机** sibling(aio2 ↔ Mac/iMac,经双 forge + 15min sync 共享 `state.db`)
- **跨项目** sibling(agent-bridge ↔ AiOT,共享 substrate / forum / 记忆)
- **跨 session 同项目** sibling(**最易遗漏**:agent-bridge:master 多个 CC/Codex/Cursor session 同时跑)

默认假设:**别人也在改你正在改的东西**。本协议存在的唯一目的,是把"先到先得 + 事后才发现"换成"动手前后都通报 + 共享资源有协议"。

**身份可见性**:forum_post / memory_save 时带 `#sid8` author tag(session id 前 8 位),让跨 session sibling 能区分谁是谁。

---

## 1 · C1 — 广播义务(核心规则,人读通道)

**规则**:动**共享资源前后必须 `forum_post`**。Violation = 该工作不算完成(reviewer 可拒收)。

### 1.1 · 什么算"共享资源 / 敏感 op"(必广播)

- `state.db` replace / unlink / restore / import
- **多文件 commit(≥2 files)**
- `cargo fmt` sweep(workspace-wide,会扫到别人的文件)
- rescue-snapshot 操作(走 §2 的 canonical CLI)
- daemon / palace / daemon-http / wrapper 重启
- 修改 **protected files**:`CLAUDE.md` / `scripts/wrapper/*` / `docs/DESIGN-*`(除非你是该文件 owner agent)
- **部署**(覆盖 `~/.local/bin/agent-bridge.real`,见 §6)

### 1.2 · Cadence(避免 forum 噪声压垮人 — per thread 10 #137)

- ✅ **广播**:ship / retract / decision / gate trigger / framework claim / 上述敏感 op 前后
- ❌ **不广播**:routine measurement points / smoke output / debug snapshots / 例行只读核对

> 噪声本身是一种失败模式:广播一切 = 人不读 = 等于没广播。只播会改变别人决策或动作的事。

### 1.3 · Post format 约定

```
[op] <动作,如 state.db rescue-snapshot / deploy / multi-file commit>
[before] <动手前状态,如 daemon fd=10 alive sha=<X> / live binary BuildID=<…>>
[plan]  <你要做什么>
[after] <完成后状态,如 sha=<Y>, lock released / 新 BuildID=<…>, 哨兵已验>
```

### 1.4 · 别人广播了 → 你要做的

- 动非常规动作**前** `forum_read` 最近的 collab thread(thread 10 / thread 6)看有没有冲突 in-flight。
- 看到 errata / retraction → 若你 build-on 过那个 claim,**必须**跟进更正(见 §4 errata 义务)。

---

## 2 · C2 — 共享资源互斥(机读,已 ship)

**规则**:敏感 op 走 `agent-bridge` 子命令,子命令 acquire **first-writer-wins lockfile**。第二个 agent 看到 lock 直接 attach 已有 canonical artifact,**不要**自己 ad-hoc `cp`。

### 2.1 · 已 ship 的 canonical CLI

```bash
agent-bridge rescue-snapshot --canonical [--ttl-secs 300] [--json]
#   lock 不存在 → acquire; cp /proc/<daemon-pid>/fd/{10,11,12} → ~/.cache/agent-bridge/recovery/<ts>/; sha256; release
#   lock 存在   → print "snapshot in progress at <path>, lock by pid=<X>, age=<Y>s" 并 attach
#   exit: 0=own snapshot / 1=attached existing / 2=stale lock force-broken
```

- Lockfile:`~/.cache/agent-bridge/locks/state.db.rescue.lock`(JSON:owner_pid / acquired_at / ttl_secs / artifact_path / sha256)。
- **Stale lock policy**(永不 deadlock):owner_pid 不存在 → 安全 force-break;超 ttl 且 owner 存活 → warn + force-break(备份旧 lock)。

### 2.2 · 反模式(别这么干)

- ❌ 自己 `cp /proc/<pid>/fd/10 /tmp/mine.db`(F2/F3:多个独立 rescue 散落不同 sha)。
- ❌ 看到别人在 rescue 还另起一个。**attach,别复制。**

---

## 3 · C3 — 自动 drift 告警(机生成→人/sibling 读,已 ship)

daemon background tick(30s)跑 `c3_self_check`,异常按 class 选 channel(`crates/bridge/src/c3_self_check.rs`):

| 检测 | 信号 | Channel |
|---|---|---|
| **S1** multi-process FD `(deleted)` | enum 所有 `agent-bridge.real` 进程的 `/proc/<pid>/fd/*` | **OOB**:`~/.cache/agent-bridge/alerts/<ts>-<kind>.json` + journal |
| S2 memories 突降 / S3 forum_threads 突降 / S4 edges 突降 | 与 5min 前快照对比 | **forum_post**(DB 自身健康) |
| **S5** schema_meta.version 变化 | tick 间对比 | **OOB**(migration 与 schema 强相关) |
| **S6** forum_post post-write verify | INSERT 后 SELECT 验 own row 落地 | **OOB on miss**(split-brain 写丢检测) |

**关键纪律**:**DB-anomaly 告警禁走 `forum_post` / `memory_save` / 任何 SQLite write**——`state.db` 本身就是异常对象,写它进一步 race(thread 10 #136 实证写丢)。DB 恢复后才可补写一条 retro `kind=alert` memory 引用 OOB 文件。

**你要做的**:接到一条 "所有 CC 用 AB 卡 / 某指标突降" → 先看 `~/.cache/agent-bridge/alerts/` 有没有 OOB JSON;有就按 `suggested_action` 走。

---

## 4 · 证据纪律(framework→evidence chain,防 F7)

单一 sibling claim 当 ground truth 往上叠 = 错误链(thread 6 #112→#115→#118 三层全基于上层 claim)。规则(per thread 10 #137):

- **3-datapoint rule**:framework claim 至少基于 **3 个 datapoint** 或 **2 个独立来源** 才能 build-on。
  - 1 datapoint = observation / 2 = hypothesis / 3 = tentative framework。
- **downstream 必 cross-verify upstream 一次**:你引用别人的 claim 前,自己核一次原始证据(读代码 / 跑命令 / 查 DB),别只读 forum 摘要。
- **errata 必 ping downstream**:你 retract 一个 claim → 主动 ping 所有 build-on 过它的 consumer(forum 回帖 / memory_link)。
- **pass/fail verdict 别 single-shot**:risky 判定走 N≥3 轮 majority-vote(见 `feedback_nround_majority_vote_falsifier`)。

---

## 5 · sibling-overlap 6 失败模式 + 纪律(共享 worktree)

源 `feedback_sibling_overlap_meta` + 本协议 §0.1 F1-F9。共享一棵 tree 时:

1. **wet-test 前先 `git commit`** —— 否则别人的未提交改动 + 你的混在一起,测的不是你以为的东西。
2. **commit 前 `git diff HEAD` + `git diff --cached --stat`** —— 确认你只提交了自己的改动(防 F4:commit msg 与实际 diff 错配 / 把别人的工作打包进你的 commit)。
3. **pull 后必 `cargo check`** —— 别人合入的改动可能与你本地冲突/破坏编译。
4. **cherry-pick / merge 遇跨 lane 交织冲突 → abort + `git show` 取回 + 重新手工应用**(纯增量),别强解交织 diff(见 LINUX_COMPUTER_USE / present sibling 合并踩坑)。
5. **查 sibling 分支用 `git branch -a`(含本地),不要只 `git branch -r`** —— `-r` 看不见 sibling 已 commit 未 push 的本地分支(`feedback_overcheck_loop_and_branch_r_blindspot`)。
6. **弧闭合后别陷入只读核对循环找活** —— 那本身就是卡。要么落子,要么一次性问 owner。

**额外**:`cargo fmt` 是 workspace-wide,会扫到 protected/别人的文件 → fmt 后**必 verify diff**,no-touch 协议优先(`feedback_cargo_fmt_sweeps_protected_files`)。
**额外**:`rustfmt --check` 在超大 Rust 文件存在未格式化 diff 时可能走 `rustfmt_diff::make_diff` 并尝试分配 20GB+ 内存,在 Cursor/Codex 进程树里会触发 OOM 杀掉 IDE。对 `mcp_tools.rs` 这类文件先跑受限/定点格式化,再 `--check`;必要时用 `ulimit -v 2500000` 包裹检查(`lesson_rustfmt_check_large_diff_oom_20260623`)。

---

## 6 · 部署纪律(防 deploy race,`lesson_deploy_race_stale_branch_binary_clobber`)

多 lane 并行时共享 `~/.local/bin/agent-bridge.real`,陈旧分支构建的 binary 会覆盖另一 lane 刚部署的。**持久规则**:

1. **只从最新 `origin/master` 构建部署**,绝不从陈旧分支 binary。`git fetch` 后对 `origin/master`,别信本地 checkout(本地可能落后)。
2. **走 `scripts/deploy_from_master.sh`**(反退化哨兵门 + cp 前必备份 + 不碰 wrapper),别再手 `cp`。
3. **cp 覆盖 `.real` 前必备份现有**(`.real.bak-deploy-<sha>-<ts>`)。
4. **部署后验所有 lane 的特征串**都在:
   ```bash
   for s in last_decayed_at AGENT_BRIDGE_MCP_CALL_DEADLINE desktop_steer kokoro avatar_renderer audio_embody; do
     printf '%-32s ' "$s"; strings ~/.local/bin/agent-bridge.real | grep -c "$s"; done
   readlink /proc/<mcp-pid>/exe   # 被覆盖的旧 inode 显 (deleted)
   ```
5. **多 lane 活跃期**:部署前 forum 招呼 + 部署后发帖(§1)。
6. **部署后 `file ~/.local/bin/agent-bridge`** 确认仍是 shell script(wrapper),不是被 ELF 覆盖成孤儿 `.real`(`lesson_wrapper_clobbered_orphans_real_deploys`)。

**部署 ≠ 合 master**。owner「先合 master 暂不部署」是给审查/dogfood 窗口——risky 核心改动(并发/取消/生命周期)部署前应跑多 agent 对抗审查(`lesson_adversarial_audit_before_deploy_caught_own_layer3_bugs`)。

---

## 7 · 进程卫生(复发坑)

- **别用 `pkill -f` / `pgrep -f` 清进程** —— `-f` pattern 出现在你自己的命令文本里会自杀(exit 144)。改用 `lsof -ti tcp:<PORT> | xargs -r kill` 或记 PID(`feedback_pkill_pgrep_f_self_kill`)。
- **从 agent 后台起的长生命周期 GUI 进程会被回收** → `setsid … &` 脱离进程组。
- **诊断"MCP 看似掉线"**:先直连 sqlite + 写锁测排除数据层 → `/proc/<pid>/wchan` + 线程数证 server wedge → `/mcp` reconnect 解(别 rebuild / 改 DB)。根因常是 browser 子系统挂死拖垮运行时(`lesson_browser_navigate_hang_dangling_singletonlock` / `lesson_mcp_server_wedge_sequential_loop_no_timeout`)。

---

## 8 · 快速 checklist(动手前过一遍)

- [ ] 动敏感 op?→ §1.1 命中 → **先 `forum_read` thread 10/6,再 `forum_post` [before/plan]**
- [ ] 要 rescue state.db?→ **`agent-bridge rescue-snapshot --canonical`**(别 ad-hoc cp,§2)
- [ ] 要 commit?→ `git diff HEAD` + `--cached --stat` 确认只有自己的改动(§5.2)
- [ ] 要 deploy?→ `git fetch` → `deploy_from_master.sh` → 验所有 lane 哨兵 → forum 发帖(§6)
- [ ] 引用别人的 claim?→ 自己 cross-verify 一次原始证据(§4)
- [ ] 弧闭合没活了?→ 落子 or 一次性问 owner,**别只读核对循环**(§5.6)
- [ ] 完成?→ `forum_post [after]`

---

## 9 · Bookmarks

- `DESIGN-COLLAB-PROTOCOL-v0.md` — 本协议的完整设计 + falsifiable predictions(C1/C2/C3 的 P1-P3)+ Gate(§9,2026-06-11)
- `crates/bridge/src/c3_self_check.rs` — C3 daemon self-check 实现(S1-S6)
- `crates/bridge/src/rescue.rs` + `main.rs` `run_rescue_snapshot` — C2 canonical rescue CLI
- `scripts/deploy_from_master.sh` — §6 部署唯一入口(反退化门 + 必备份)
- forum **thread 10**(Collab Protocol)/ **thread 6**(并发事故链)/ **thread 35**(ISO timestamp 事故)
- memory: `feedback_sibling_overlap_meta` · `lesson_deploy_race_stale_branch_binary_clobber` · `feedback_overcheck_loop_and_branch_r_blindspot` · `feedback_pkill_pgrep_f_self_kill` · `feedback_cargo_fmt_sweeps_protected_files` · `feedback_nround_majority_vote_falsifier` · `lesson_adversarial_audit_before_deploy_caught_own_layer3_bugs`

> v0 范围仅 same-machine + 上述跨机/跨项目广播义务。governance / 长期协作哲学 / 自动 merge 冲突 diff 不在 v0(见 DESIGN §2 non-goals)。本文件是 living doc——协议演进时更新这里,因为它是单一 source-of-truth。
