# AB Invocation Guardian v2：单入口 Canary 与晋级计划

日期：2026-09-01
状态：**C0/C1 已通过；C2 隔离预检与 C3 protected-witness 源码合同已实现；真实部署/provider 证据未执行，C2—C4 与 production `enforce` 继续 HOLD**

## 1. 决策

下一阶段只验证一条窄而真实的能力链路：由 trusted issuer 签发一次性 exact lease，经服务端持有的 stdio execution context 和不可变 finalized registry，到达独立 UID guardian；guardian 验证完整签名 scope，并把消费事实提交给受保护的单调 witness；只有本次请求第一次得到的 `FreshCommitted` 才能进入一个固定目录 marker effect。

这不是全局授权系统发布，也不改变以下边界：

- guardian protocol v1 **永久非授权**。v1 的所有响应继续固定为 `grants_authority=false`、`witness_class=volatile_lab`；v2 不通过翻转 v1 authority bit 或放宽 v1 decoder 实现。
- 内存 head、同机 SQLite、guardian UID 独占的普通本地文件、普通重启持久性和本地主机上的 mock 都**不是** protected monotonic witness。
- `AB_INVOCATION_LEASE_MODE=enforce` 的 production Invalid/HOLD 行为、默认值和现有恢复 carveout 不变。
- 即使单入口 canary 全部通过，也只能声明该 canary 链路已验收，不能声明 task custody、全 effect 面覆盖或全局 fail-closed。
- 本文描述目标协议和验收条件，不表示相关代码、服务、UID、密钥、witness 或 canary 已存在。

## 2. 安全目标与威胁边界

### 2.1 本阶段必须建立的事实

1. 请求来自被部署策略认可的 Bridge 服务身份，而不是仅凭 caller 提供的字段或一个可继承的 token。
2. guardian 自行验证 issuer 签名、完整 exact scope、服务端 stdio connection commitment 和 finalized registry digest，不信任 Bridge 传来的 opaque `scope_commitment` 结论。
3. 一次性消费与受保护单调位置在 witness 侧原子提交；Bridge、Agent、workspace、Bridge 主机磁盘或旧 VM/卷快照不能回滚该事实。
4. 只有 guard 成功返回后，finalized registry 才调用 canary effect；所有不确定结果都在 effect 前拒绝。
5. 同一 token、scope 或 receipt 的重复、并发和恢复请求不能产生第二次 canary dispatch。

### 2.2 明确纳入的攻击与故障

- Agent、工具子进程或失控调用方尝试继承 guardian socket group、已连接 FD、token 或同 UID 权限；
- malformed frame、未知字段、跨版本 frame、伪造 disposition、错误签名和错误 trust root；
- tool、JCS arguments、target、principal、stdio connection、registry digest、namespace 或时间窗口漂移；
- 同一最后一次 use 的并发双花；
- Bridge、guardian 或 witness 请求链路在提交前后崩溃、超时、断连或丢失响应；
- guardian 重启、Bridge 主机/卷回滚、旧 receipt 重放、provider epoch/revision 回退；
- socket path、parent、owner、group、mode、symlink、peer credential 或 provider identity 被替换。

### 2.3 本阶段仍不解决

- 同一 stdio connection 内多个 Agent 的可信 task 区分；connection commitment 仍不是 task identity。
- daemon HTTP、legacy Unix、native IPC、background/CLI、direct Hub/backend 和 composite child direct-call 的全局收口。
- 任意非幂等 effect 的 exactly-once 完成语义。首版选择安全的 at-most-once：不确定时烧掉 grant，而不是重试副作用。
- 通用租约撤销、长周期 key rotation、跨 provider migration 和 break-glass 的完整生产闭环。

## 3. v1 与 v2 的不可混用边界

v1 继续只用于协议状态机和 Unix 隔离实验。它的 `ExactOperation` 接受 caller-selected operation id、opaque scope commitment 和 expected previous head；它既不携带完整 signed lease，也不验证 issuer、principal、execution context 或 task custody，因此不能成为 v2 authority 的兼容子集。

v2 必须使用新的 magic/version 或不可混淆的 version/tag、独立 request/response 类型和独立 client 返回类型，并满足：

- v1 decoder 拒绝 v2 frame，v2 decoder 拒绝 v1 frame；
- v2 没有“允许 v1 volatile receipt 临时晋级”的配置；
- v1 `VolatileLabObservation` 永远不能转换为 v2 dispatch permit；
- provider class、trust root 或 authority disposition 未知时 fail closed；
- capabilities 和文档分别报告 v1 lab 与 v2 canary，不把两者合并成模糊的 guardian enabled 状态。

## 4. v2 Signed Self-contained Envelope

当前本地 lease token 只有 nonce 和 Ed25519 signature，完整 scope row 位于本地 SQLite。v2 guardian 不能依赖 Bridge 先查 row、再把一个 opaque digest 当成验证结论。最小闭环采用自包含、大小有界的 signed envelope；将来若改为 issuer→guardian 独立登记通道，需要新的协议评审。

envelope 至少绑定：

- schema/version 和 canary-only issuance lane；
- ledger generation、issuer verify-key id/commitment；guardian 从 trusted config 固定真实 verify public key，不能信任 envelope 自报 key；
- token nonce commitment、lease id；
- canonical registry-owned tool name；
- RFC 8785/JCS arguments digest 和规范化 target digest；
- exact finalized registry digest；
- deployment/witness namespace；
- principal kind/commitment；
- transport kind=`stdio`、server-created connection context kind/commitment；
- issued-at、not-before、expires-at；
- `max_uses=1`，首个 canary TTL 上限为 60 秒，部署可进一步收紧；
- domain-separated signature schema 和 key generation。

guardian 必须从收到的实际调用材料重新计算 tool、arguments、target、registry 和 execution-context commitment，再验证 envelope。请求不得提供或覆盖 witness 当前 head；guardian/witness 自己选择 namespace 中的线性化位置。首版 operation/idempotency key 由 guardian 从 namespace、token commitment 和固定 use index 派生，不接受 caller 选择一个可以碰撞或抢占的 operation id。

ledger generation 与 verify public key 是可用于 trust-root 的非秘密输入。guardian 的可信配置需要原始 pin；registry/capabilities 默认只发布二者的 domain-separated commitment，不发布 issuer 私钥，也不把 SQLite path、device 或 inode 当成跨主机 trust root。

## 5. Async Protected Monotonic Witness

v2 使用新的 async witness contract；不能把远端 I/O 塞入 v1 的同步 `InvocationWitness` 方法并阻塞 Tokio connection task。每个方法都有硬 deadline、取消语义和封闭 decision enum。

受保护 witness 的最小事务语义是：

1. 以 deployment namespace 和 token commitment 定位一次性消费；
2. 在同一受保护事务内拒绝已存在的消费，或插入 `(token_commitment, use_index=1, exact_scope_commitment)`；
3. 原子推进 namespace 的 protected epoch/revision/head；
4. 返回由稳定 provider identity 签名的 receipt，绑定 namespace、epoch、revision、previous/new head、token commitment、use index、exact scope、当前 request challenge 和 provider key generation；
5. 对同一 idempotency key 的后续请求只返回 `AlreadyCommitted` 审计事实，不再次返回 fresh authority。

provider identity、namespace、CA/transport trust、receipt verify key 和允许的 epoch 必须由 guardian trusted config 固定。低于已知 epoch/revision、断链、错误签名、未知 key generation、时钟不可用或 provider identity 漂移均返回 HOLD。

以下实现不满足该定义：

- `VolatileLabWitness` 或进程内 map；
- Bridge 或 guardian 同一可回滚主机上的普通 SQLite、append log 或 owner-only 文件；
- 只证明重启持久、但能随旧 VM/卷 snapshot 恢复的数据库；
- 单独使用 hardware counter，却把 token→use mapping 保存在可独立回滚的本地文件中；counter 推进与 exact mapping 不是同一个原子事实。

首选部署形态是位于 Bridge 主机快照域之外、能原子提交 exact consumption 与 chain position 的受控服务。硬件方案只有在 counter、exact mapping、恢复和迁移整体满足相同威胁模型时才可替代。

## 6. Outcome 与故障语义

v2 canary 采用严格的 at-most-once dispatch 规则：

| outcome | 是否可 dispatch | 说明 |
| --- | --- | --- |
| `FreshCommitted` | 仅当前 live request 可以 | 必须绑定当前 guardian session、request challenge、完整 exact scope 和 pinned provider receipt |
| `AlreadyCommitted` | 否 | 只证明过去存在同一消费；不能证明过去的 effect 未执行 |
| `LookupCommitted` 或其他 lookup 结果 | 否 | lookup 仅供审计、告警与人工 reconciliation |
| `Conflict` / `Exhausted` / `Expired` / `Revoked` | 否 | 确定拒绝 |
| `Indeterminate` / timeout / disconnect / malformed receipt | 否 | 消费可能已经发生，grant 按已烧掉处理 |
| `Hold` / unknown | 否 | 任何未审查状态默认拒绝 |

`FreshCommitted` 只能来自本次远端事务的首次插入结果，并绑定不可重放的 request challenge。client 使用独立、不可 `Clone`、构造函数私有的 canary permit；guard 消费 permit 后才返回成功。成功返回后由 finalized registry 立即进入固定 canary tool，不提供 raw executable handle。

如果 witness 已提交但 guardian 或 Bridge 没有收到响应，后续 lookup 会看到 `AlreadyCommitted`，但不会补发 dispatch authority。因此可能出现“grant 已消费、marker 未创建”；这是首版有意接受的可用性损失。未经 effect sink 自身的幂等协议和受保护 delivery-claim 状态，不得把 lookup 恢复描述为 exactly once。

## 7. 单一真实 Effect Ingress Canary

首个 effect 不使用 `shell_exec`、terminal、browser 或任意 caller-selected path。计划新增一个默认关闭、feature-gated、只在专用 stdio canary profile 中注册的 `invocation_guardian_canary_write`：

- operator 预创建并固定一个隔离目录；目录不位于 workspace，owner/mode/ancestor 全部验证；
- caller 不提供 path、command、payload、overwrite 或 append 参数；
- marker 文件名从 deployment namespace 和 token commitment 派生；
- 使用 no-follow/openat2 等价约束和 `create_new`/`O_EXCL`，拒绝已存在节点、symlink、目录漂移和跨目录解析；
- 写入固定 schema 的最小 marker，记录非秘密的 token/scope/receipt commitments，并执行必要的 file/directory sync；
- 同一 token 即使遭遇实现缺陷导致第二次 dispatch，也因 `create_new` fail closed。这个 effect-level 幂等只是 defense-in-depth，不证明其他工具幂等。

专用 stdio canary registry 只暴露该 canary 和经明确评审的只读诊断。调用必须经 `FinalizedToolRegistry` 的私有 transport dispatch 与 frozen guard-before-inner 路径，并绑定当前 canonical name、registry snapshot digest 和 server-owned stdio connection commitment。现有 serving lease 最多证明 transport 在该次 dispatch 开始时有效，不证明结果读取时仍在线；普通 in-process `invoke`、同名等价实现、direct backend 调用或 capabilities 报告都不等于当前 transport availability attestation。

主 AB serving profile 不因 canary 自动新增开放工具，也不把 canary lease 解释为其他 effect 的 authority。canary 未显式启用、guardian 不可用或任何配置 pin 缺失时，不注册该 effect 或在 guard 前置拒绝。

## 8. 故障矩阵

| 故障/攻击 | witness 允许的状态 | marker 预期 | 必须证明 |
| --- | --- | --- | --- |
| token 缺失、畸形、跨版本 | 不调用或确定拒绝 | 不存在 | parser 有界且 fail closed |
| issuer key/generation 不匹配 | 不消费 | 不存在 | guardian 使用外部 pin，不接受 envelope 自报 trust root |
| tool/args/target/registry/connection/namespace 漂移 | 不消费 | 不存在 | 每一字段由 guardian 重算并纳入签名 |
| 静态 SecurityPolicy/canary enable ceiling 关闭 | 不消费 | 不存在 | lease 不能重开 hard ceiling |
| provider 在提交前不可达或 timeout | 未提交或未知 | 不存在 | 不执行，不自动重试 effect |
| provider 已提交，响应在到达 guardian 前丢失 | `AlreadyCommitted` 可审计 | 不存在 | 后续 lookup/consume 不授予 dispatch |
| guardian 已拿到 fresh receipt，回 Bridge 前崩溃 | 已提交 | 不存在 | grant 烧掉，重启后不补发 |
| Bridge 收到 fresh permit，effect 前取消/崩溃 | 已提交 | 不存在 | grant 烧掉，不退款 |
| marker 创建或写入中崩溃 | 已提交 | 可能不存在或为可识别的不完整节点 | 不以同 token 重试；运维可隔离检查 |
| effect 完成后 Bridge 崩溃 | 已提交 | 恰有一个完整 marker | 重放只得 `AlreadyCommitted`，无第二次 dispatch |
| 同 token N 路并发 | 一个 fresh，其余 duplicate/conflict | 最多一个 marker | witness 原子唯一约束与 `create_new` 双重成立 |
| guardian 重启 | provider 保留已消费事实 | 无第二个 marker | provider identity/epoch 稳定且重新 pin |
| Bridge 主机、目录或 VM/卷恢复旧快照 | provider 仍处于新位置 | 无第二个 marker | protected witness 位于回滚域之外 |
| provider 返回更低 epoch/revision 或断链 receipt | HOLD | 不新增 | rollback/stale replica 被检测 |
| 旧 receipt/frame 被重放 | 拒绝 | 不新增 | receipt 绑定当前 challenge/session |
| wrong UID/GID、socket/symlink/parent 替换 | 不能建可信连接 | 不新增 | kernel/deployment probe fail closed |
| wall clock 回退或 skew 超限 | HOLD | 不新增 | 使用受保护 provider time/epoch 或明确的安全时间策略 |

该矩阵验证 at-most-once 进入 effect，不承诺每个 fresh consumption 最终一定形成完整 marker。

## 9. 实施切片与建议文件

### 9.1 仓库内源码切片

这些工作可以在无生产外部服务时完成，但只能使用 mock/volatile adapter 验证协议，不产生 protected-witness 声明：

1. 提取共享、唯一的 signed scope/envelope canonicalization 与 verifier，避免 issuer、guardian 和 client 各自实现一套字段顺序。
2. 新增独立 v2 protocol 与 provider-receipt module；保留 v1 文件和 lab disposition 不变。
3. 新增 v2 client 配置与 canary permit，固定 guardian UID/GID、provider verify key、namespace 和 issuer trust-root commitment。
4. 新增 async protected-witness trait、受控 fake adapter 与 fault injection；production constructor 在真实 provider 未配置时继续 HOLD。
5. 新增专用 canary tool/profile、guardian-backed guard policy snapshot 和 default-off Cargo feature。
6. 为真实 stdio `tools/call` 增加子进程 E2E；不能只用 direct registry invocation 代替 transport 测试。

建议的代码归属：

- `crates/bridge/src/invocation_lease_scope.rs`：signed self-contained scope/envelope、domain separation、唯一 verifier；
- `crates/bridge/src/invocation_guardian_receipt_v2.rs`：canonical signed provider receipt、provider pins、request/session binding 和唯一 verifier；
- `crates/bridge/src/invocation_guardian_protocol_v2.rs`：v2 bounded wire schema；
- `crates/bridge/src/invocation_guardian_client.rs`：独立 v2 canary client/type；
- `crates/bridge/src/invocation_guardian_service.rs` 与可拆分的 protected-witness adapter：v2 service/async provider seam；
- `crates/bridge/src/bin/invocation_guardian.rs`：显式 protected-canary 配置，不能复用 `--volatile-lab` 表示生产；
- `crates/bridge/src/invocation_lease.rs`：guardian canary backend 与诚实 status/policy commitment；
- `crates/bridge/src/mcp_tools.rs`：仅专用 profile 注册固定 marker tool；
- `crates/bridge/tests/` 与现有 module tests：协议、故障和真实 stdio E2E。

C0 的 scope、receipt 和 protocol 文件已经创建；client、service、witness、tool
与 E2E 文件仍只是后续实施建议，不能从文件名推断其存在或晋级状态。

### 9.2 外部部署切片

以下证据无法由本地单元测试、mock 或“代码支持”替代：

1. guardian 使用独立、非 root UID；Bridge、Agent、工具进程和 workspace 用户不能读取、写入、unlink、rename、替换或 ptrace guardian state/process。
2. Agent 不拥有 guardian socket group，不继承已连接 FD 或可重新获得的 IPC capability。若 Agent 与 Bridge 共享 UID，必须给出额外的不可继承进程能力或进一步 UID 分离；仅依赖相同 UID 下的 group 约定不构成 request authenticity。
3. protected provider 位于 Bridge 主机/卷/VM snapshot 域之外，具备稳定签名 identity、事务一致性、安全 epoch/time、stale replica 检测、备份恢复和 key rotation runbook。
4. issuer 私钥不进入 Hub、guardian、Agent、模型上下文或 canary marker；签发与验证部署职责保持分离。
5. 实际执行旧 DB、旧目录、旧 VM/卷 snapshot、guardian/Bridge 重启、网络分区和 provider failover 演练；旧 token 不得复活。
6. 以真实 service manager、UID/GID、socket parent、capability、ptrace 和启动顺序执行 deployment probe，而不是只调用纯函数模拟 credential。

## 10. 最低测试集合

### 10.1 仓库内必须常驻

- v1/v2 cross-decode、未知 tag/field、oversize、truncation、authority/class flip 全部拒绝；
- signed envelope 对每个字段敏感，wrong key/generation 与 attacker-inserted scope 拒绝；
- guardian 从实际调用重算 JCS arguments、target、registry 和 stdio context；arguments 内伪造 `_meta`/session/context 无效；
- `FreshCommitted` 是唯一可构造 canary permit 的 outcome；`AlreadyCommitted`、所有 lookup 和 indeterminate 路径为 compile/runtime negative tests；
- `max_uses=1` 并发压力下恰有一个 fresh decision；
- 在“提交前、提交后回包前、回包后 effect 前、marker 创建中、effect 后”注入 fault，并核对 witness/marker 状态；
- provider key、namespace、issuer trust root 或 canary policy 漂移会改变 finalized guard policy/composite digest；
- actual stdio child process 通过 `tools/call` 执行 valid exact lease 才创建 marker；missing/mismatch/replay 不创建；
- feature/config 默认关闭，普通 production enforce 继续 Invalid/HOLD；capabilities 不报告全局 fail-closed、task binding 或 deployment attestation。

### 10.2 外部验收必须执行

- Bridge/Agent UID 对 guardian state 的 read/write/unlink/rename/replace/ptrace 探针失败；
- Agent 直接连接 guardian、继承 socket FD/group、替换 socket node/parent 的探针失败；
- 旧主机/卷/VM snapshot 和 stale provider replica 不复活已消费 token；
- N 路真实并发、guardian restart、provider failover 和 response-loss 下最多一个 marker；
- receipt 签名、provider key generation、epoch/revision/head chain 可由独立 verifier 校验；
- clock skew、key rotation、namespace migration 和 provider unavailable 都按 runbook fail closed。

## 11. 晋级门槛与可声明范围

| Gate | 完成条件 | 通过后最多可声明 |
| --- | --- | --- |
| C0 — 协议冻结 | v2 envelope、outcome、receipt、domain separation 和 downgrade negative test 评审通过 | v2 schema candidate |
| C1 — 源码 canary | mock/fault tests和真实 stdio E2E通过；default-off | source-level canary candidate，witness 未受保护 |
| C2 — UID/IPC 隔离 | 真实 deployment probes 证明 Agent/Bridge 权限边界 | guardian deployment isolation for this canary |
| C3 — Protected witness | 外部 anti-rollback、provider identity、epoch/time、恢复演练通过 | protected consumption for this namespace |
| C4 — 单入口发布评审 | 精确版本、配置、测试、残余风险由 security/runtime owner 批准 | one stdio marker ingress canary enabled |

C4 通过后仍必须保持：

- `production_global_enforce=false`；
- `global_effect_coverage=false`；
- `task_identity_attested=false`、`task_binding_enforced=false`；
- `lookup_grants_dispatch=false`、`already_committed_grants_dispatch=false`；
- v1 `production_grants_authority=false`；
- 主 AB 默认值和未覆盖 effect ingress 的 HOLD 不变。

只有后续形成可信 task principal/custody、全 effect ingress 收口、撤销/轮换/break-glass 运维闭环，并完成独立发布评审，才可讨论解除全局 production HOLD。

## 12. 当前阶段状态

截至本文日期，C0 已在源码层冻结 signed self-contained scope、signed
provider receipt 和独立 v2 bounded wire protocol；C1 已完成默认关闭的源码 canary：

- `invocation_lease_scope.rs` 是 envelope canonicalization、Ed25519 signing
  message 和 exact observed-invocation verifier 的唯一实现；canary lane、tool、
  principal kind、stdio transport、server-created connection-context kind、正 TTL
  与 exclusive expiry 都是签名语义中的固定条件；
- `invocation_guardian_receipt_v2.rs` 是 provider receipt canonicalization、
  domain-separated signature 与 pinned verifier 的唯一实现；receipt 绑定 provider
  identity/key generation、namespace、epoch/revision、previous/new head、token、
  `use_index=1`、exact scope、当前 request challenge、guardian session 和 provider time；
- `invocation_guardian_protocol_v2.rs` 使用独立 `ABI2` magic、封闭 outcome
  与 typed signed receipt；wire decode 只产生未验证响应，不提供 dispatch/grant
  predicate。只有 receipt verifier 能形成不可 `Clone` 的 verified evidence，且它仍
  不是 permit；v1/v2 cross-decode、未知 tag/reserved bit、截断、oversize、wrong
  key/time/pin、所有 scope/receipt/request binding 漂移均被测试拒绝；
- `invocation_guardian_canary.rs` 提供 async fake witness、提交前/提交后丢包
  fault、只允许 `FreshCommitted` 构造的私有 non-`Clone` permit，以及固定 marker
  sink；`AlreadyCommitted`、conflict、indeterminate 和 hold 均不能 dispatch；
- `ToolContext` 的 guard handoff 绑定 canonical finalized dispatch，每次 invocation
  新建、最多安装一次且只能消费一次；effect 执行前清除 caller authorization meta；
- `invocation-guardian-v2-canary` Cargo feature 默认关闭；专用 stdio binary 只注册
  固定 marker tool，不接收 caller-selected path、payload 或 command；
- 真实子进程 stdio `tools/call` E2E 已验证 missing meta、arguments 内 `_meta`
  spoof 和同 token 并发 replay，最终恰好一个成功响应、一个 marker；
- C1 的 witness 和 guard 仍与 canary MCP 同进程，provider signing key 也只用于测试
  配置；它们不构成独立 guardian、IPC authentic channel 或 protected witness；
- 没有 protected witness provider；
- 没有创建部署 UID、socket、密钥、namespace 或 marker directory；
- 没有在任何安装或 production profile 中启用 canary；
- 没有改变 production `enforce`、capabilities 或发布结论。

C2 目前具备默认关闭的 Linux probe helper 与 root-only transient-systemd
harness：它要求三个既有、不同的非 root UID 和一个专用 socket group，实际探测
`SO_PEERCRED`、state read/write/unlink/rename、socket
unlink/rename/replace、ptrace 和 listener-FD 继承。harness 不创建用户、组、持久
unit 或 production path，所有变更限制在新的 `/run/ab-invocation-guardian-c2.*`
目录并在退出时清理。

当前主机只有一个普通用户，当前会话也没有免密 root，因此仅完成非特权 host
preflight，结果为 `HOLD`。即使临时隔离 substrate 后续通过，它仍运行一个明确
non-authoritative、protocol-free helper；在实际 v2 guardian composition 以同一
service-manager/UID/IPC 配置运行并重复探针前，不得把 substrate PASS 升格为 C2
PASS。C1 的 fake/map、测试私钥、marker 和 stdio 结果也不能替代 C2/C3 外部证据。

C3 目前新增默认关闭的 async protected-witness contract 与动态单调 floor
verifier。它复用 C0 signed receipt，拒绝 provider position/time rollback、history
fork、revision gap、epoch jump 和不连续 failover；`AlreadyCommitted` 仍只是证据。
当前源码不包含外部 provider、凭据、endpoint、durable backend 或可成功构造的
production transport，因此这只构成 C3 contract candidate，不构成 C3 PASS。
