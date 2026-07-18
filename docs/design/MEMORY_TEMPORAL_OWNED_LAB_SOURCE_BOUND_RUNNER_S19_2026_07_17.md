# BioCortex × Agent-Bridge Track B：S19 source-bound owned-lab runner（non-live）

日期：2026-07-17

阶段：S19

状态：`S19_NON_LIVE_SOURCE_BOUND_RUNNER_AND_SINGLE_USE_CAS_IMPLEMENTED_REAL_AUTHORITY_AND_EXECUTION_ABSENT`

决策：`BLOCKED_PENDING_S20_REAL_OUT_OF_BAND_TRUST_ANCHOR_OWNER_SIGNED_FINAL_S19_MANIFEST_AND_INDEPENDENT_AUTHORIZED_UNCLAIMED_REGISTRATION`

## 1. 本阶段完成什么

S19 把 S18 的“离线验证过的 owner envelope”接到一个默认关闭、仅 synthetic KAT 可达的 source-bound runner 内核。它冻结以下实现合同：

1. S19 是 S18 verifier 的 private child，只接收 S18 返回的 opaque verified output；
2. expected binding 来自独立构造的 typed S19 manifest 与固定 owner context，不能从 candidate envelope 或 candidate payload 反推；
3. fresh preflight 只产生 non-authorizing receipt，不创建 live root、不启动 runner；
4. external authority-control SQLite ledger 预先登记精确的 `AUTHORIZED_UNCLAIMED` row；runner 不得创建缺失 row；
5. `BEGIN IMMEDIATE` 同一事务读取 claim、`ABSORBING_STOP`、`CURRENT_REVOCATION`，并执行一次精确 CAS；
6. 成功 CAS 先 durable commit `CONSUMED_FOR_EXACT_RUN` tombstone，再产生 process-local affine permit；
7. failed CAS 影响 0 行、不改变 `AUTHORIZED_UNCLAIMED`、不产生 permit；S19 API 内部不循环，manifest 声明 `NO_AUTOMATIC_RETRY`，但跨 revalidation 的 orchestration enforcement 留给 S20；
8. post-run retention、semantic、batch、STOP、cleanup、custody receipts 仅是 evidence，不是 owner authority。

这里的“source-bound runner”是运行边界与类型内核，不是已部署的 live executor。S19 没有真实 manifest、真实 trust anchor、真实 owner signature、真实 registration、真实 claim 或真实 run。`SIDE_EFFECTS_UNLOCKED=NONE`。S20 才是第一个可能进入 live canary 的阶段。

## 2. 与 S18 的 private-child 组合

S19 不重新解释 S18 candidate，也不把 candidate 里的任意字段当作 expected truth。组合边界是：

```text
independent typed S19 manifest + pinned owner context
                         |
                         v
                expected S18 bindings
                         |
candidate anchor + candidate envelope -> S18 verifier
                         |
                         v
             opaque VerifiedOwnerAuthorization
                         |
                         v
                 S19 private child
```

关键不变量：

- candidate envelope 不是 expected manifest builder 的输入；
- S19 直接消费 S18 opaque verified output，不复制一套公开可伪造的“verified=true”结构；
- verified S18 output 仍只是 `AUTHORIZED_UNCLAIMED...`，不是 execution capability；
- owner envelope 不携带可替代 out-of-band trust anchor 的自认证 key；
- synthetic RFC/KAT key、manifest 或 receipt 都不构成真实 owner 决策。

## 3. S19 subject manifest

真实 owner 需要审查并签署最终、精确的 S19 subject。这个 manifest 必须在 S19 最终 integration commit/tree 形成后，由 committed typed builder 在 tree 外生成；把带“未来 commit”的占位 manifest 提交进 S19 会造成自引用，不能成为真实 owner subject。

Manifest 绑定：

- 最终 S19 source/integration commit 与 tree；
- runner、controller、manifest builder、expected builder、claim/control implementations 的 source/binary/toolchain/ruleset；
- S18 verifier 与 S17/S18 frozen artifacts；
- 五个 S19 Schema、schedule、assignment、catalog、SQLite profile/schema、classifier、oracle；
- 精确 f2fs device/mount/root、boot/kernel、资源上限、timeout；
- 允许操作与明确禁止的 network、credential、provider、production、paid-resource、mount、root、reboot、block-write surface；
- single-use CAS、external STOP/revocation 与 post-run receipt protocol。

Canonical profile 是 `AB_RESTRICTED_CANONICAL_JSON_S19_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT`：UTF-8、compact、key 递增排序、无重复 key、无 float、无未知字段。仓库 fixture 的文件 framing 固定为 canonical JSON payload 后恰好一个 LF；parser 必须先确认只有这一个 framing LF，再剥离它。Schema validation、owner signature 与 manifest digest 只覆盖剥离 LF 后的 exact canonical payload bytes，LF 不进入签名或 manifest digest 域。

仓库中的 synthetic manifest 明确声明：

- `test_only=true`；
- `packet_kind=S19_OWNER_REVIEW_SUBJECT_MANIFEST`；
- `manifest_state=SYNTHETIC_KAT_NON_LIVE_SUBJECT`；
- 重复的 `11...` digest 与 `22...` Git OID 是显眼占位；
- 所有 real/live authority 与 actual execution count 均为 false/0；
- 它只用于 parser/schema/semantic KAT，不能被提升为 owner authority。

## 4. Fresh preflight 不是授权

Preflight 必须绑定同一个 authorization、signed payload、S19 manifest、resource scope、revocation epoch、run、controller、runner、capability nonce、claim key/revision、environment 与 control snapshot。它检查：

- exact schedule/assignment 与 5,639-row catalog、113 target phases；
- exact binaries/toolchains/validator rulesets；
- exact f2fs root/device/mount/kernel/boot；
- no network、no credentials、no paid resources、no privilege escalation；
- run root 不存在，且 path isolation 成立；
- external row 已由独立 control plane 登记为 `AUTHORIZED_UNCLAIMED`；
- use-time STOP 为 `CLEAR`，revocation epoch 精确匹配；
- 没有发生 side effect。

Preflight receipt 不是 owner envelope、不是 claim receipt、不是 affine permit。检查成功只允许尝试一次 CAS，不允许启动执行。

S19 的 compact preflight token 按值传入并消费于一次 claim API 调用，API 自身没有 retry loop。但 trusted module caller 仍可重新执行 validation 获得一个新 token；S19 没有 failed-attempt tombstone 阻止这种重新编排。因此这里的“一次”是单 token/API invocation 的边界，不是跨 caller orchestration 的密码学唯一性。No automatic retry 是 S20 controller orchestration 必须执行的策略，而不是 S19 已证明的跨调用保证。

## 5. External authority-control 与 single-use CAS

### 5.1 独立登记

真实 owner envelope 经 S18 验证后，独立 authority-control plane 必须登记一条完整绑定的 `AUTHORIZED_UNCLAIMED` row 并 durable commit registration receipt。Claim path：

- 只能 `UPDATE` 已存在 row；
- 禁止 `UPSERT`、`INSERT OR REPLACE`、`INSERT OR IGNORE`；
- 缺失 row fail closed；
- registration receipt 不是 owner authority。

### 5.2 同一事务线性化

CAS 的语义轮廓是：

```text
BEGIN IMMEDIATE;
read exact CLAIM row;
read ABSORBING_STOP row;
read CURRENT_REVOCATION row;
validate monotonic revisions, policy identities, STOP=CLEAR,
         anchor minimum <= current external key version,
         envelope revocation epoch == current external active epoch;
UPDATE exact existing row
   SET state=CONSUMED_FOR_EXACT_RUN, exact run/nonce tombstone, next revision
 WHERE state=AUTHORIZED_UNCLAIMED
   AND every frozen binding below is equal;
write successful claim receipt in the same transaction;
durable COMMIT;
only then create a non-cloneable, non-serializable process-local affine permit.
```

SQLite `WHERE` 的冻结 profile 是 `EXACT_ALL_BINDINGS_AND_CONTROLS_SINGLE_UPDATE`，必须按 Rust/SQLite 列名和顺序绑定全部 16 项：

1. `authorization_id_sha256`
2. `signed_payload_sha256`
3. `subject_manifest_sha256`
4. `resource_scope_sha256`
5. `signed_revocation_epoch`
6. `claim_namespace_sha256`
7. `claim_key_sha256`
8. `revision`
9. `run_id_sha256`
10. `controller_binary_sha256`
11. `runner_binary_sha256`
12. `capability_nonce_sha256`
13. `preflight_receipt_sha256`
14. `control_snapshot_sha256`
15. `stop_revision`
16. `revocation_revision`

STOP 与 revocation 不是 envelope 里的静态声明；它们是 owner envelope 外的 use-time external control state。Claim、STOP 与 revocation 必须来自同一个 SQLite transaction/domain，不能先读 control、释放锁后再 claim。

### 5.3 成功、失败与 crash

- 成功：`affected_rows=1`，形成 absorbing `CONSUMED_FOR_EXACT_RUN` tombstone 与 same-transaction claim receipt；durable commit 后才可产生 affine permit。
- 失败：`affected_rows=0`，不改变 `AUTHORIZED_UNCLAIMED`，不产生 permit，不解锁 side effect；S19 claim API 不自动循环。
- Retry 边界：manifest policy 是 `NO_AUTOMATIC_RETRY`，但 S19 不写 failed-attempt tombstone，也不阻止 trusted caller 重新 validate 新 token。S20 controller 必须在 orchestration 层强制失败后不重试；不能把这一策略写成 S19 已完成的 durable/cryptographic guarantee。
- 成功后 controller crash：row 仍为 consumed，不能复用原 envelope/assignment/run；重新执行需要新 assignment 与新 owner decision。
- 成功 claim 后、start 前 STOP/revocation 改变：执行仍被拒绝，但 consumed tombstone 不回滚。
- 缺失、未知、rollback、policy identity mismatch、revision regression 都 fail closed。

## 6. Absorbing STOP 与 current revocation

STOP 状态机只有 `CLEAR -> TRIGGERED`；`TRIGGERED` 是 absorbing，不能通过普通 runner/control API 清回 `CLEAR`。Revocation epoch、STOP ledger revision 与 revocation ledger revision 都必须单调不减。

Revocation 可执行条件不是“envelope epoch 不低于某个值”，而是同时满足：

```text
anchor.minimum_key_version <= current_external_key_version
envelope.revocation_epoch == current_external_active_epoch
```

可信 wall clock 不是 freshness proof。S19 要求：

- claim 线性化时同事务读取；
- claim 后、start 前再次读取；
- 每个有副作用的 action boundary 再次读取；
- signed stop field 不能替代这些 external reads。

## 7. Affine permit 与 non-live dispatch boundary

成功 CAS 后的 permit 必须：

- 仅存在于当前 process；
- 不实现 Clone/Copy/Serialize；
- 绑定 exact authorization、manifest、run、controller、runner、capability nonce 与 claim receipt；
- 每个 action boundary 都经 external control recheck；
- 不可由 JSON receipt、boolean 或 verified envelope 重建。

S19 只验证这个类型与状态机边界，不包含 live dispatch adapter。即便 synthetic KAT 获得 synthetic permit，也没有真实 root creation、signal、fresh exec read 或 Agent-Bridge application side effect。

## 8. Post-run evidence chain

未来 S20 exact canary 的固定 denominator 是：

- family：OL00=1、OL04=6、OL05=53；
- assigned attempts=60；
- pidfd SIGKILL attempts=59；
- distinct fresh-exec reads=59；
- S16 mapping-phase records=113；
- one canary batch、one repetition、no implicit rerun。

Receipt 链为：claim → retention → semantic → batch → optional STOP → cleanup → custody。若任何 action boundary 观测到 `TRIGGERED`，post-run bundle 必须携带 STOP receipt。每个 receipt 绑定 authorization、manifest、run 与 parent hash。

这些 receipts 只回答“发生了什么、证据是否完整、如何保留/清理/托管”，不能回答“owner 是否授权下一次执行”。Cleanup/custody receipt 不是 owner envelope；post-run evidence 不能把 consumed row 恢复为 unclaimed，也不能授予 retry。

## 9. 五份独立 Draft 2020-12 Schema

S19 定义五个互不引用外部文件、闭合且默认拒绝未知字段的 Schema：

- `agent_bridge.memory_temporal_owned_lab_subject_manifest_s19.v0`
- `agent_bridge.memory_temporal_owned_lab_preflight_receipt_s19.v0`
- `agent_bridge.memory_temporal_owned_lab_control_snapshot_s19.v0`
- `agent_bridge.memory_temporal_owned_lab_authority_control_claim_s19.v0`
- `agent_bridge.memory_temporal_owned_lab_post_run_receipt_bundle_s19.v0`

Authority-control claim Schema 内含四个 disjoint packet kind：registration receipt、ledger row、successful claim receipt、failed claim receipt。它们共享绑定语义，但 packet 不能相互替代。

实现声明必须区分两层：manifest Schema、typed builder 与 canonical synthetic fixture 是 S19 已实现边界；preflight、control snapshot、authority-control claim、post-run bundle 这四份 rich JSON Schema 是冻结给 S20 的 target contract。S19 Rust 当前只有 compact internal synthetic structs/digests，不会 emit、parse 或 validate 这四种 rich JSON packet。它们的存在不能被报告为已经产生真实 receipt。

另外，SQLite trigger 和 revision check 的保证范围只覆盖当前 verified database instance；它们不能单独抵抗整个数据库文件被旧副本替换。S19 的 post-claim/action-boundary recheck 与真正副作用开始之间仍可能存在调度间隙。因此 whole-file rollback resistance、rich packet builders/validators 和无间隙 action-start linearization 都是 S20 hard gate，而不是 S19 已完成能力。

## 10. 当前阻断与 S20

S19 当前明确为零：

- real final S19 manifest：0
- out-of-band trust anchor：0
- owner-signed envelope：0
- independent `AUTHORIZED_UNCLAIMED` registration：0
- successful live CAS：0
- affine live execution permit：0
- runner launch/root creation/observation：0
- provider/production authority：0
- `SIDE_EFFECTS_UNLOCKED=NONE`

S20 是第一个可能 live 的阶段，但不是自动解锁。必须在 S19 最终集成后生成 real canonical manifest，交由 owner 独立审查和签署，安装 out-of-band trust anchor，登记 exact `AUTHORIZED_UNCLAIMED` row，启用 manifest-bound real preflight observer，重新执行 fresh preflight 与全部 source gate，然后才可尝试一次 CAS。任一条件缺失都继续 fail closed。

S20 还必须补齐可验证的 whole-file control-ledger rollback protection，并把最后一次 control recheck 与每个真实 action start 线性化，不能留下“检查通过后、动作开始前”的窗口；controller orchestration 还必须在 trusted caller 可 revalidate 的前提下执行 `NO_AUTOMATIC_RETRY`。
