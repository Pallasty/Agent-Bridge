# AB 下一阶段安全能力：Guardian 候选、连接托管与 Effect Inventory

日期：2026-08-31  
状态：**源码候选；默认关闭；production `enforce` 继续 HOLD；未部署**

## 1. 本阶段结论

本阶段没有把安全目标定义成“减少 Agent 能做的事”，而是把能力开放所依赖的三个事实做得更可验证：

1. 调用是否属于签发时指定的服务端执行连接；
2. effect 是否从最终 registry 进入同一个授权入口；
3. consume 结果是否来自一个与 Bridge 隔离、能够证明单调性的 witness。

前两项已经形成源码候选。第三项只形成了协议、Unix 客户端、独立服务和内存状态机的实验骨架；仓库中仍不存在受保护的单调 witness。因此：

- `AB_INVOCATION_LEASE_MODE=enforce` 在生产构建中仍映射为 Invalid/HOLD；
- guardian v1 的所有响应都固定为 `grants_authority=false`、`witness_class=volatile_lab`；
- guardian production constructor 固定返回 HOLD；
- 没有把 volatile 内存 head、同机 SQLite、UID 隔离或普通重启持久性称为 durable anti-replay。

这是一项能力基础设施交付，而不是生产安全放行。

## 2. 已落地的候选链路

```text
trusted issuer
  -> Ed25519 signed exact scope
     + tool / JCS arguments / target hint / time / uses / principal
     + optional server-owned stdio connection commitment

final MCP registry
  -> machine-readable conservative effect classification
  -> finalized guard (unknown/new names default require exact authority)
  -> static SecurityPolicy hard ceiling
  -> exact lease verification and pre-effect consumption

independent guardian candidate (default-off lab only)
  -> bounded private Unix protocol
  -> peer UID + socket/parent identity checks
  -> consume_exact / lookup_exact state machine
  -> volatile receipt, never authority
```

### 2.1 连接托管，不冒充任务身份

stdio transport 为每个服务端连接实例生成随机、服务端持有的标识，并只向调用上下文公开其域分离 SHA-256 commitment。caller 提供的 `_meta`、`session_id`、`task_id`、环境变量或 arguments 不能构造或替换该值。

租约 v3 可以把这个 commitment 纳入 SQLite 闭合 schema、JCS scope、Ed25519 签名和 receipt。缺失或不同连接的验证在消费前失败；失败不会占用 use。最终 registry 的候选 guard 要求 stdio exact lease 使用该绑定。

它仍然不是 task identity：复用同一 stdio 连接的两个 Agent 看到相同 commitment，在该连接内部仍可能转交 bearer authority。状态输出必须保持：

- `task_identity_attested=false`；
- `task_binding_enforced=false`；
- 不声称已经阻止同连接、同 principal 的任务间转交。

真正的 task custody 仍需要 runtime/transport 创建不可伪造的 task principal，并由 guardian 验证 task→target ownership。

### 2.2 Effect inventory 与未知默认保护

最终 MCP registry 现在可以产生稳定排序、可序列化且带 SHA-256 digest 的 effect inventory，字段包括：

- ingress、effect class、authority policy、target binding；
- unknown、exact、open-read、recovery 计数；
- compact summary 与完整 descriptor report；
- 明确的未覆盖 ingress 债务清单。

分类采用保守默认：缺失或不一致的 annotation 为 `Unknown + ExactInvocation`；已知 effectful 名称即使误标只读也不能变成 open-read。`McpTool::name()` 与 `schema.name` 不一致会在注册时 fail closed。

但 annotation 和分类仍不是 authority attestation。本阶段的 runtime finalizer **不从 `OpenRead` 或 `TargetCustodyRecovery` 自动生成豁免**，其 descriptor-derived exemption set 为空：

- 新增、改名或 finalization 后注册的未知工具仍走 exact path；
- `agent_kill` / `mobile_projection_stop` 目前只证明目标由 Bridge 看见，不证明当前 caller/task 拥有目标；
- Invalid/HOLD 继续保留显式的诊断/应急恢复 carveout，但必须把它描述为跨任务恢复权衡，而不是 task-scoped custody。

capabilities 不再从环境重建 registry，而是读取当前 canonical tool 调用所绑定的同一份不可变 dispatch snapshot，报告精确 descriptor 数量、composite digest、instance id、inventory 与静态策略。该证据只能声明 `dispatching_finalized_registry_bound=true`；普通 `FinalizedToolRegistry::invoke` 不等于 transport-owned live 服务，因此 `live_serving_registry_bound=false`、`transport_serving_registry_attested=false` 与 `runtime_authorization_attested=false` 保持诚实。compact 投影会省略重复 descriptor 清单，但 digest 仍承诺完整 security projection。

registry 已形成不可逆类型边界：非 `Clone` builder 独占 `Box<dyn McpTool>`，单次冻结 canonical name 后再做 profile admission，consuming finalizer 产出不提供注册、guard replacement API 或 executable handle retrieval 的 `FinalizedToolRegistry`；stdio/HTTP 只经 `invoke` 分派。snapshot evidence 同时绑定 canonical tool name，使按自身固定名称查询的已知工具不能从异名 composite parent 继承后冒充 direct dispatch；这不是对恶意实现的身份 attestation。摘要承诺 descriptor、声明 guard policy、effect inventory、静态 SecurityPolicy 与 lease ledger trust-root commitment；但仍不证明实现行为、guard 内部状态、同名等价实例、共享 Hub/backend 或 composite direct-call 被关闭。

### 2.3 独立 Guardian 候选

默认关闭的 `invocation-guardian-lab` feature 提供独立 binary。候选协议具备：

- 固定 magic/version/tag、固定字段长度和最大 frame；未知、畸形、超长或 authority-bit 翻转的 frame 均拒绝；
- hello 双 nonce 与 provider incarnation 派生 connection session nonce；
- `consume_exact` 返回 `Committed / AlreadyCommitted / Conflict / Indeterminate / Hold`；
- `lookup_exact` 可恢复“commit 已发生但响应丢失”的判断；
- receipt 绑定 operation id、exact scope、previous/new head、revision 和 provider incarnation；
- 单连接请求数、并发连接数和 I/O deadline 有界；
- Unix client/server 都验证内核 peer credential；客户端固定 socket、parent 的 owner/mode/device/inode，拒绝 symlink、root guardian、同 UID guardian和连接期间替换；
- 服务端拒绝 root client，socket 使用专用 shared group `0660`，parent 必须 guardian-owned、setgid、不可 group/world 写。

实验 witness 只在内存中保存 head/revision/operation receipt，重启即丢失，也不能抵抗主机快照回滚。它只用于验证协议状态机、故障语义和部署拓扑，不接入 `InvocationLeaseAuthorizer` 的 production authority path。

v1 还只用 kernel peer UID 识别客户端；请求虽含 caller-selected opaque `scope_commitment`，却不携带或验证 issuer 签名及可验证的 signed lease scope，也没有 task principal 或连接 commitment。与 Bridge 同 UID、且继承 shared socket group 的进程可以直连实验服务并抢先推进 volatile head，造成 lab DoS。由于所有结果固定不授予 authority，这不是 production 权限绕过；但在任何未来协议允许 dispatch 之前，必须把签名 exact scope 与不可由同 UID 子 Agent 冒充的 Bridge/task 身份端到端绑定，并禁止 Agent 继承 guardian socket capability。

## 3. 仍然明确未覆盖的入口

机器清单至少持续暴露以下债务，所有条目均为 `protected=false`、`attested=false`：

- daemon HTTP `POST /forum/post`；
- daemon HTTP `POST /agent/messages`；
- daemon HTTP `POST /avatar-surface/cortex-review-decision`；
- daemon startup embed-readiness reindex；
- Warp native IPC；
- direct Hub/backend handle；
- background/CLI effect。

此外，composite tool 直接调用 child `.execute` 时不会再次经过 registry guard；当前策略只能按外层工具的 effect closure 进行保守分类，不能把 child 名单当成独立 runtime attestation。

## 4. 下一次晋级需要的证据

以下条件任一未完成，production `enforce` 保持 HOLD：

1. **受保护单调 witness**：位于 Bridge/Agent 可写文件系统和可回滚主机快照之外；receipt 可验证 provider identity、incarnation、exact scope 与单调位置。
2. **不确定结果协议闭环**：consume 超时后只允许 exact lookup；`Committed/AlreadyCommitted` 才能 dispatch，`Conflict/Indeterminate/Hold` 一律不执行。
3. **真正 task identity**：由 transport/runtime 创建并证明，纳入 signed scope；guardian 验证 task 生命周期与 task→target custody。
4. **逐入口收拢**：daemon HTTP、native、direct、background/CLI 接统一较低层 guard，或在 enforce 模式显式禁用。
5. **恢复 ownership**：launch 时记录由 Bridge/guardian 生成的不可伪造 owner/context；kill/stop/cancel 必须解析并匹配该记录，之后才可从跨任务 carveout 晋级为 custody recovery。
6. **transport-owned registry 绑定**：不可变 registry 与 canonical-name dispatch snapshot 已完成；晋级仍需由 stdio/HTTP transport 注入不可委托的 serving evidence，不能把普通 in-process `invoke` 或同名等价实现当成 live 证明。
7. **部署隔离探针**：Bridge 只能连接 socket、不能读写 guardian state，也不能 unlink、rename、ptrace 或替换 guardian state/socket；Agent 不继承 socket group/capability，不能连接 guardian。错误 group、mode、UID、symlink、parent 或 peer credential 全部 fail closed。
8. **请求真实性**：guardian 验证 issuer 签名、exact lease scope、server-created connection/task principal 与 operation id；仅有相同 peer UID 或 shared GID 不得提交 consume/lookup。
9. **回滚与并发验收**：旧 DB、旧目录、旧卷/VM snapshot、guardian 重启和最后一次 use 的并发双花均不能复活 authority。

## 5. 操作约束

- 不启用或部署该 lab binary 作为生产 guardian。
- 不从 MCP/Unix/HTTP 暴露 issuer 或自签发接口。
- 不让 Hub、模型、子 Agent 或 volatile guardian 持有 issuer 私钥。
- 不把 inventory annotation、同名 session、caller-selected target id 或“Bridge 曾看见该对象”当作 ownership proof。
- 不改变生产默认值，不创建生产密钥，不迁移生产账本。

下一阶段的正确目标不是扩大 allowlist，而是先接入受保护 monotonic witness，并让一个真实但隔离的 effect ingress 完成“签发—连接/task 托管—单调消费—故障 lookup—dispatch”的端到端 canary。
