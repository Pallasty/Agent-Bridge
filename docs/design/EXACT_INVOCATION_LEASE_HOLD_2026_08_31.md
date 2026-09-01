# AB 精确调用租约：阶段交付、HOLD 与晋级门槛

日期：2026-08-31
状态：**源码候选；production `enforce` = HOLD；未部署**

## 1. 决策

AB 的安全北极星不是把能力永久关掉，而是按风险、主体、目标和组织阶段调度能力：

- 静态 policy 定义不可被租约突破的能力硬上限；
- 精确调用租约决定某个已允许能力能否执行这一次具体调用；
- 资源 governor 限制并发、时长和扩张速度；
- 恢复控制只有在可验证 caller/task→target custody 后才能按 custody lane 放行；当前 Invalid/HOLD 中少量跨任务 stop/kill carveout 只是显式的应急可用性权衡，不冒充 custody；
- 风险低、只读或恢复性路径不因高风险写路径的控制而失去组织自由度。

本阶段把“允许某类工具”收敛为“允许指定主体在短时间内，对指定目标，以指定参数调用指定工具有限次”。这提高了能力开放的可调性，但不自动构成生产级持久反重放边界。

**放行结论：HOLD。** 当前 `enforce` 只能用于隔离测试。生产发布不得设置 `AB_INVOCATION_LEASE_MODE=enforce`，直到本文 B 类边界和全部 promotion gates 关闭。生产进程若仍请求 `enforce`，已接线的 MCP/Unix guard 会进入 Invalid/HOLD：除明确列出的诊断与恢复控制外默认拒绝，包括 effect inventory 尚未收录的名字。daemon HTTP、native client 和 direct handler 尚未统一接线，因此这仍不是全进程 fail-closed。当前同 UID SQLite 也无法识别合法旧快照，不能据此宣称 durable anti-replay。

## 2. 本阶段已经形成的调用链

```text
transport-owned authority metadata
  -> static SecurityPolicy hard ceiling
  -> exact scope + principal verification
  -> consumption commit before effect dispatch
  -> MCP/Unix effect handler
```

已接线的源码边界如下：

1. **MCP 不可变终态 registry**：工具只可进入非 `Clone` 的 `ToolRegistryBuilder`，注册对象由 `Box<dyn McpTool>` 独占；`finalize_with` 先消费 builder、冻结并排序完整 descriptors，再从同一只读切片生成 effect inventory、实际 guard、security projection 与 JCS/SHA-256 摘要。服务期 `FinalizedToolRegistry` 不提供 `register`、guard replacement API 或 executable `get`，stdio/HTTP 只能调用 `invoke`，因此所有经 serving registry 的 dispatch 都经过同一 guard；这不证明 guard 的内部可变状态或行为被冻结。该边界也不证明调用方没有另一个等价工具、共享 `Hub`/backend 或 composite child direct-call 能力。
2. **Unix JSON-RPC 前置检查**：路由器在 effect handler 前执行静态 capability 和租约检查；Unix socket 收紧为 `0600`，主体来自内核 peer credential。
3. **transport-owned metadata**：MCP 授权材料只从 `tools/call.params._meta` 进入私有 `ToolContext`；工具参数中的 `_meta`、`session_id`、`clientInfo` 和环境提示均不是身份。Unix 顶层授权元数据在路由前提取，并在交给 effect handler 前移除。
4. **精确 scope**：租约绑定 registry-owned `tool_name`、RFC 8785/JCS 参数摘要、由参数推导的归一化 target 提示、`not_before`/到期时间、最大使用次数、主体承诺和签发模式。当前上限为 TTL 300 秒、uses 64 次。完整参数绑定是真正约束；target 目前只是审计提示，还不是 host-resolved 实际资源标识。`shadow` 签发物在签名 scope 与 receipt 中均标记 `issuance_mode=shadow`，receipt 另标记 `grants_authority=false`，不能被 `enforce` authorizer 提升为执行权限。
5. **主体边界**：若 effect registry 经 HTTP MCP 暴露，只接受 transport 已验证且未过期的 OAuth subject；Unix 只接受内核提供的 UID；stdio 没有可验证用户身份，只能使用不冒充身份的 opaque bearer authority。当前 provider HTTP candidate 仍只暴露只读身份诊断，不暴露 AB effect registry。
6. **消费先于副作用**：`enforce` 在调用 effect handler 前提交消费记录。提交结果不确定时拒绝；消费后即使工具失败、取消、panic 或进程退出也不退款。
7. **静态 policy 是 hard ceiling**：租约不能重新打开被 `SecurityPolicy` 禁用的 shell、terminal、browser、agent 等能力。
8. **恢复可达性与 custody 分开声明**：`agent_kill` 可通过 Bridge session store/runtime live map 解析，`mobile_projection_stop` 可通过进程内 projection registry 解析；这只证明目标由 Bridge 管理或看见，不证明当前 caller/task 拥有目标。二者目前仅在 Invalid/HOLD 的显式跨任务应急 carveout 中保持可达；finalized inventory guard 不因 recovery 标签自动豁免。`agent_steer_kill` 只有可伪造的 `ab__` 命名且允许 caller 指定远端，`oz_run_cancel` 可直接接受 external run id，CDP page tracker 还会吸收非 AB 创建的 tab，因此 steer kill、Warp cancel 与 `browser_close_page` 在形成不可伪造 custody 前继续要求租约。
9. **签发与验证分离**：Hub 只持有 authorizer，不持有 issuer；没有 MCP/RPC 自签发工具，也没有从环境注入 grant 的捷径。
10. **任务绑定仍未完成**：系统没有自动向子 Agent 分发租约，但当前签名 scope 尚未绑定 transport-attested task/session。同一 bearer、Unix UID 或 OAuth principal 内，持有者仍可把未消费或多次使用 token 转交另一进程；因此不能声称已强制禁止继承。

模式语义：

| 模式 | 行为 | 可作出的声明 |
| --- | --- | --- |
| `off` | 不检查、不消费 | 历史兼容；无租约保护 |
| `shadow` | 验证并记录 would-allow/would-deny，不阻断、不消费 | 可观测性；不是安全执行边界 |
| `enforce` | 静态 policy 通过后，验证并在 dispatch 前消费；异常拒绝 | 仅隔离测试候选；生产仍 HOLD |
| 配置无效 / production `enforce` HOLD | 已接线 MCP/Unix 入口除明确诊断/恢复控制外默认拒绝 | 只证明 wired-ingress default-deny；不覆盖 daemon/native/direct 路径 |

## 3. 安全审计发现：为何当前 SQLite 不能支持生产声明

当前账本在 Unix 上使用 mode `0600`、由当前 effective UID 持有的 owner-only 文件，并执行非 symlink 检查、固定 generation、严格表结构、不可更新/删除 trigger、事务化消费和同步写入。这些机制能够处理正常并发、进程重启和诚实文件系统上的重复调用。

它们不能抵御与 Bridge 处于**同一 OS UID、具有相同文件权限**的攻击者或失控 Agent：

1. 攻击者可在消费前复制账本快照；
2. 等合法调用完成并写入 consumption tombstone；
3. 停止 Bridge，删除现有 SQLite 文件并恢复旧快照；
4. 旧快照仍可具有正确 owner/mode、合法 DDL、相同 generation 和完整性检查结果；
5. Bridge 无外部单调事实可判断该快照已经过时，于是旧租约可再次使用。

SQLite trigger 只能阻止经当前数据库执行的 `DELETE/UPDATE`，不能阻止同 UID 删除整个文件或恢复磁盘快照。JCS、TTL、token commitment、文件同步和普通重启测试也不证明抗回滚性。

因此必须区分：

- **restart-persistent replay detection**：在同一未回滚账本上，重启后仍能看到消费记录；当前实现可以验证这一点。
- **adversarial durable anti-replay**：账本文件或主机快照被回滚后，仍能证明某次授权已经消费；当前实现不具备这一点。

在 B 类边界完成前，文档、capabilities、发布说明和测试名称均不得把前者表述为后者。

## 4. A 类加固与 B 类信任边界

A 类是当前代码内可完成的 defense-in-depth；它们是内核验收候选，不是 production `enforce` 的充分条件。最终状态必须以合并代码和对应测试为准。

| A 类候选 | 当前基线 | 内核验收要求 | 无法解决的问题 |
| --- | --- | --- | --- |
| Ed25519 签名 scope | 已实现 nonce + exact scope + issuance mode + ledger generation + verify key 的 Ed25519 签名；Hub authorizer 只持公钥，本地 issuer 仅用于隔离测试/Shadow 候选 | 将 issuer 移至独立信任域；补齐 key id、轮换、撤销、过期和域分离迁移方案 | 有效旧租约及旧 consumption 快照仍可一起回滚重放 |
| 完整 DDL 指纹 | 已固定规范化完整 table/trigger DDL，并校验 application/user version、generation 与 `quick_check`；等名替换或增删对象拒绝 | 将该校验迁入独立 guardian，并建立显式 schema/version 迁移协议 | 合法旧数据库的 DDL 与当前完全一致，仍无法证明新鲜度 |
| FD / inode 身份钉住 | 已有 regular-file、Unix owner/mode、no-follow、canonical path 与 pathname `dev+ino` 漂移检查；尚未固定 SQLite 已打开 FD，也未钉住父目录 | 以 no-follow/openat2 风格打开；固定 fd、`dev+ino+nlink`、owner/mode 和父目录身份；事务前后复核，替换或 unlink 立即拒绝 | 进程重启后恢复旧 inode/卷快照，或连同外部路径状态一起回滚，仍可能不可见 |

B 类是生产放行的必要条件，不能在 Bridge 进程内用更多 SQLite 校验代替：

1. **独立 OS UID guardian**：guardian 以不同 UID 运行并独占账本写权限；Bridge、Agent、工具进程和 workspace 用户均不能打开、替换、快照恢复或修改账本。Bridge 只能通过私有 IPC 请求 `verify_and_consume`，guardian 使用内核 peer credential 验证调用方。
2. **受保护的单调账本**：消费事实必须锚定在 Bridge 可写文件系统和可回滚主机快照之外的 monotonic witness，例如独立受控服务或满足同等威胁模型的硬件/远端单调原语。一次消费与单调推进必须产生可校验 receipt；提交结果不确定时永不执行副作用。
3. **恢复与迁移协议**：备份恢复、主机克隆、guardian 重启、key rotation 和 ledger migration 不得复活已消费租约。恢复必须比较外部 epoch/counter，并对落后状态 fail-closed。
4. **职责继续分离**：issuer 私钥不进入 Hub 或 guardian 验证进程；guardian 不能自行扩大 scope，Bridge 不能自行签发，Agent 不能继承或刷新 authority。
5. **可信 task custody**：由 transport/runtime 证明不可伪造的 task/session identity，并纳入签名 scope；guardian 只接受该 task 的活跃执行上下文。仅在 receipt 中写 `task_inheritable=false` 或依赖调用约定不能阻止同一 principal 内转交 token。

仅把 SQLite `chown` 给另一个 UID 仍不充分：如果 guardian 的整个持久卷能随主机快照回滚，就仍然缺少外部单调事实。

## 5. Promotion gates

以下 gate 必须按顺序形成可复查证据；任何一项未关闭都保持 HOLD，不能用运行时长或“尚未发生事故”替代。

1. **G0 — 威胁模型冻结**：明确攻击者包括同 UID Agent、进程终止、文件替换、旧快照恢复、并发双花、时钟异常和 transport metadata 伪造；安全负责人签字确认声明边界。
2. **G1 — A 类内核验收**：Ed25519、完整 DDL 指纹和 FD/inode 检测以实际代码、负向测试和 key/格式迁移方案关闭；状态输出不得夸大它们的能力。
3. **G2 — Guardian 隔离**：独立 UID、私有 IPC、peer credential、最小系统权限和服务启动顺序完成；以 Bridge/Agent UID 直接读写、unlink、rename、ptrace 或替换 guardian 账本的探针必须失败。
4. **G3 — 单调反回滚证明**：消费后恢复旧 SQLite、旧目录、旧 VM/卷快照以及 guardian 重启，旧租约均被拒绝；receipt 能关联 exact scope 和单调位置。
5. **G4 — 全 effect 面覆盖**：effect inventory 有机器可读清单；MCP、Unix、daemon HTTP、native client 和内部调用不存在绕过。尚未接线的面必须显式禁用，而不是依赖调用约定。
6. **G5 — 并发与故障原子性**：同一最后一次 use 的并发请求仅一个进入 effect；consume 成功后 crash 不退款；consume 结果不确定不 dispatch；guardian 不可用时恢复控制仍可达。
7. **G6 — 运维闭环**：shadow 指标、拒绝告警、clock skew、key rotation、撤销、break-glass、备份恢复和 rollback runbook 完成；break-glass 有独立审计且不生成可继承的全局 grant。
8. **G7 — 发布授权**：精确版本、测试证据、覆盖清单和残余风险经安全/运行 owner 审核后，才可在一次受控 canary 中启用 `enforce`；默认值变化需要新的独立评审。

## 6. 覆盖边界

下表描述源码中的接线 seam，不等价于当前进程已经实例化全部入口。capabilities 用 `authorizer_gate_requested` 表示 authorizer 模式请求，而不是 guard 已实例化证明；`authorizer_denies_configured_protected_calls_when_invoked` 也只描述 authorizer 被实际调用时的行为。`signed_scope_protocol_supported`、`signed_scope_evaluated_for_protected_calls` 和 `signed_scope_enforced_for_protected_calls` 分别报告协议支持、在 `shadow`/测试态 `enforce` 中评估，以及仅在测试态 `enforce` 中强制。在具备入口级 runtime attestation 前，`current_process_ingress_attested=false`。

| 路径 | 本阶段状态 | 约束或缺口 |
| --- | --- | --- |
| MCP `FinalizedToolRegistry` 调用 | 已接线且服务期不可变 | 仅覆盖经 registry `invoke` 的工具；静态 policy 先于租约；终态摘要证明结构与声明策略冻结，不证明实现代码/行为 |
| streamable HTTP MCP | 通用 transport/guard seam 已具备；当前 candidate 无 AB effect tools | 未来接 effect registry 时，主体只可来自 transport 验证的 OAuth subject |
| stdio MCP | 已接线到同一 guard | 只有 bearer possession，不把客户端自报字段提升为身份 |
| legacy Unix JSON-RPC effect methods | 已接线路由前置检查 | 要求内核 UID；顶层 authority metadata 不进入 effect 参数 |
| daemon HTTP 写路由 | **未覆盖** | G4 前不得宣称全局 enforce |
| native client tools | **未覆盖** | 必须接 guardian 或保持禁用 |
| 直接 in-process handler / 等价 tool / `Hub` / backend / composite child call | **未覆盖** | serving registry 不再泄漏 handle，且 `Box` 关闭了“注册同一 Arc 后继续持有”的显式路径；调用方仍可能在装箱前复制实现、包装共享状态或绕过 registry 直接调用后端，必须在更低层或进程边界统一收口 |
| 子 Agent / 子任务 | 不自动分发，但协议尚未阻止转交 | 缺少可信 task/session commitment；同一 principal 内 token 可被转交，解除 HOLD 前必须建立 guardian custody |
| kill/cancel/stop/close 恢复控制 | custody lane 尚未成立；Invalid/HOLD 保留显式跨任务应急 carveout | `agent_kill` 与进程内 mobile stop 的目标可由 Bridge 解析，但 caller/task ownership 未被证明；finalized guard 不自动豁免。remote steer kill、raw Warp cancel 和未区分来源的 browser close 继续受保护，直到有不可伪造 custody proof |

受保护工具清单是版本化安全输入。新增 effectful 工具默认不得因“尚未列入清单”而获得生产放行；G4 要求 CI 对工具清单与 effect inventory 的差异 fail-closed。

本阶段红队审计已经实际发现并收口一组漏项：`desktop_invoke` 可返回 mutation grant，`desktop_confirm` 可消费它执行真实桌面操作；browser screenshot 类调用可写 caller-selected host path；`memory_save/delete` 会改变后续任务可见的持久知识。它们已加入候选保护清单。这个发现同时证明手工清单不能作为 G4 的终态，所以 Invalid/HOLD 在已接线入口改为“除明确诊断/恢复控制外默认拒绝未知名字”，而不是仅拒绝当时已枚举的 effect。

同一轮审计也否定了“恢复”标签本身足以获得开放权限：`agent_steer_kill` 的命名空间不是 custody proof，`oz_run_cancel(run_id=...)` 是 caller-selected external mutation，CDP tracker 中的 PageId 也可能来自 AB 启动前的 tab 或 popup。三者已从 HOLD 开放列表移除。未来重新开放必须由 Bridge/guardian 查到不可伪造、仍活跃且属于当前组织边界的 launch record，不能由请求参数或“已被 tracker 看见”自行声明所有权。

## 7. 最低测试矩阵

| 类别 | 必须证明 | 当前阶段处理 |
| --- | --- | --- |
| canonical scope | JSON key 顺序变化仍匹配；值、tool 或归一化 target 变化拒绝且不误消费 | 已有/保留单元验证 |
| mode separation | `issuance_mode=shadow` 的签发物不能被 `enforce` authorizer 接受或获得 authority | receipt 标志与 Shadow→Enforce 提升负向已有单元验证 |
| TTL / uses | not-before、到期边界、上限、撤销和多 use 次序正确 | 已有/保留单元验证 |
| principal | OAuth issuer+subject、Unix UID 不匹配拒绝；stdio 自报身份无效 | 已有单元与 transport 负向验证，继续做端到端 |
| metadata ownership | `arguments._meta` 或 session/client hint 伪造不能授权；Unix authority 字段不泄漏给 handler | MCP/Unix 边界测试必须常驻 |
| pre-effect consume | sentinel effect 仅在消费提交后发生；重放不再次触发；commit indeterminate 不触发 | 已有 registry 与真实 MCP 子进程的拒绝前 sentinel；有效 consume→真实 effect 和 commit-indeterminate fault injection 留待 guardian 闭环 |
| concurrency | `max_uses=1` 时多个并发调用只有一个获准 | 已有/保留单元验证；guardian 后重跑端到端 |
| honest restart | 使用同一未回滚账本重启后，tombstone 仍拒绝 | 只证明 restart persistence，不改名为 durable anti-replay |
| schema / file tamper | mode、owner、symlink、路径、DDL、generation、inode 漂移拒绝 | A 类完成后全部负向通过 |
| same-UID rollback | 删除账本、恢复消费前快照后旧租约不得成功 | **当前预期不满足，是 HOLD 的决定性测试** |
| protected rollback | guardian/Bridge 重启、旧卷/VM 快照、备份恢复均不复活租约 | B 类 G3 必须通过 |
| hard ceiling | 静态 policy 禁止时，有效租约也不能执行 | Unix 已验证 policy 先于消费；MCP 完整 transport 端到端仍待 guardian candidate |
| recovery lane | 授权系统失效时，显式应急 carveout 可达但不得声称 caller/task custody；仅命名匹配或 raw external id 不能绕过 | Invalid/HOLD 的恢复 carveout 与 finalized exact guard 分别验证；真实 task-owned 对象的端到端 stop 留待专用 harness |
| immutable registry | finalize 后不能注册或替换 guard；stdio/HTTP 无 raw handle；descriptor/guard/carveout/uncovered ingress/静态安全策略/ledger trust root 漂移改变 composite digest；capabilities 与本次 canonical dispatch 的 registry snapshot 同源 | Builder/Finalized 编译失败测试、deny-before-inner、digest 稳定/敏感性和 exact-dispatch capabilities 一致性测试已加入；只覆盖 registry 结构边界，不声称 transport live attestation |
| coverage bypass | daemon/native/direct handler 不能绕过统一边界 | G4 前为未通过 |

测试报告必须列出精确命令、commit、平台、通过/失败数和未运行项。当前源码中的单元测试不能替代 guardian 隔离、快照回滚和全路径端到端证据。

## 8. 本阶段非目标与操作约束

- 不提供 MCP、Unix、HTTP 或工具内自签发租约的接口。
- 不让 Hub、模型或子 Agent 持有 issuer 私钥。
- 不提供任务级通配 grant，不自动分发、续期或退款租约；当前协议不能阻止同一 principal 主动转交 token。
- 不以租约替代静态 capability、资源 governor、sandbox、审计或人工发布控制。
- 不宣称 daemon HTTP、native client、direct handler 已被覆盖。
- 不把 shadow 观测解释为 enforce 证据。
- 不改变生产默认值，不部署、不写生产账本、不生成真实生产密钥。

本轮已经完成不可变 serving registry 与 canonical-name-bound dispatch snapshot 的源码闭环，但没有把普通 in-process invoke 误报为 transport live attestation，也没有改变 production HOLD。下一阶段的落地目标不是继续堆叠同 UID SQLite 校验，而是先交付独立 UID guardian 与受保护单调账本的最小闭环；完成后再用同一精确 scope 协议逐面收拢尚未覆盖的 effect 路径。
