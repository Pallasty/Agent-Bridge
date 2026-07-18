# BioCortex × Agent-Bridge Track B：S19 source-bound runner 实施报告

日期：2026-07-17

阶段：S19

模式：non-live、private child、default-off、synthetic KAT only

## 结论

S19 已把 S18 opaque verified owner-authorization output 与 typed source-bound runner/CAS 内核组合起来，并冻结独立 expected manifest、fresh preflight、external authority-control、single-use claim、absorbing STOP、current revocation、affine permit 与 post-run evidence 的类型和状态机边界。

当前没有真实 owner manifest、trust anchor、signed envelope、external registration、claim、execution permit 或 run。所有实际执行计数为 0，`SIDE_EFFECTS_UNLOCKED=NONE`。因此本阶段结论不是“已获准运行”，而是：S20 首次具备在补齐独立 owner/control prerequisites 后尝试 exact live canary 的结构条件。

## 已落地边界

### S18 → S19 组合

- S19 作为 S18 private child，直接消费 opaque verified output。
- Expected binding 由 typed S19 manifest 与 pinned owner context 独立构造。
- Candidate envelope/payload 不能定义 expected manifest 或把自身字段提升为 truth。
- S18 verified-unclaimed output 不是 execution capability。

### Manifest 与 Schema

- 定义 closed typed S19 owner-review subject manifest。
- 定义 fresh preflight、external control snapshot、authority-control claim 与 post-run bundle 的 frozen S20 target Schema。
- 五份 Schema 都声明 Draft 2020-12，object shape 闭合并拒绝未知字段；但 S19 Rust 只实现 manifest typed/canonical path，另外四份 rich JSON packet 尚无 emitter/parser/validator。
- Synthetic manifest 是 compact sorted canonical JSON，明确 `test_only=true`，使用显眼占位 digest/OID，且不声明任何 real/live authority。

### Claim/control state machine

- Independent control plane 必须预先登记 exact `AUTHORIZED_UNCLAIMED` row；claim 不得创建缺失 row。
- Claim 使用 `BEGIN IMMEDIATE`。
- SQLite CAS `WHERE` 绑定 authorization ID、signed payload、S19 manifest、resource、revocation、namespace/key/revision、run/controller/runner/nonce、preflight/control snapshot 与 STOP/revocation ledger revision。
- Claim、`ABSORBING_STOP`、`CURRENT_REVOCATION` 在同一个 verified SQLite database instance/transaction 中读取和线性化。
- 成功 CAS：1 row，durable `CONSUMED_FOR_EXACT_RUN` tombstone，same-transaction receipt，commit 后才产生 affine permit。
- Failed CAS：0 row、不变更 authorized-unclaimed、不产生 permit；单次 S19 claim API 内不循环。
- S19 按值消费单个 preflight token，但 trusted caller 可重新 validate 新 token；没有 failed-attempt tombstone。`NO_AUTOMATIC_RETRY` 是 S20 controller orchestration hard obligation，不是 S19 已完成的 durable/cryptographic enforcement。
- 成功 claim 后 crash 或 post-claim STOP 不恢复 unclaimed，也不允许复用。
- SQLite trigger/revision checks 不构成 whole-file rollback resistance；action-start linearization 也尚未实现，二者均为 S20 hard gate。

### Receipt 分权

- Preflight receipt 只证明 fresh checks，不是 owner envelope/capability。
- Claim receipt 证明单次状态转移，不是可序列化 bearer capability。
- Retention、semantic、batch、optional STOP、cleanup、custody receipts 是 post-run evidence。
- Post-run receipts 不授予 authority、不允许 retry；cleanup/custody receipt 不得冒充 owner envelope。

## Exact future canary denominator

未来 S20 owner 批准的 exact canary 仍固定为：OL00=1、OL04=6、OL05=53；总 attempts=60，pidfd SIGKILL=59，distinct fresh-exec reads=59，S16 mapping phases=113，单 batch、单 repetition、无 implicit rerun。

## 验证记录

本报告的文档/fixture 子任务执行只读 JSON、Schema 与 release-packet 检查，不触发 runner、root creation、signals、network、credentials、paid resources 或其他 live side effect。

已完成：

- strict canonical synthetic payload + exactly-one-LF repository framing；签名/manifest digest 只覆盖剥离 framing LF 后的 payload；
- synthetic manifest 对 manifest Schema、五份 Schema 的 local refs 与 closed-object rules；
- independent expected builder 的 candidate-poisoning negative self-test；
- failed CAS/second claim/crash/STOP/revocation 等 14 个 Rust synthetic KAT；
- S18 frozen predecessor invariants 与 security audit；
- checker `--self-test` 输出和 frozen expected TSV 的 byte-for-byte compare；
- report 中 16 个 non-report packet path 的 raw SHA-256 逐项复算。

Clean source/integration topology 下的完整 source gate 与内存受控 Cargo build/replay 由 S19 集成验证统一记录；本报告不把这些尚未在 clean committed topology 上完成的步骤写成已通过。

## S20 admission 仍需满足

1. S19 最终 integration commit/tree 形成后，生成真实 canonical subject manifest；
2. owner 对 exact manifest/context 做新的独立 review 与 Ed25519 signature；
3. out-of-band trust anchor 独立安装，不能由 envelope carried key 替代；
4. external authority-control plane 独立登记 exact `AUTHORIZED_UNCLAIMED` row；
5. use-time fresh preflight、STOP=CLEAR、current revocation exact equality、no rollback 全部成立；
6. source gate、replay、resource/safety checks 全部通过；
7. Controller orchestration 在 trusted caller 可 revalidate 新 token 的前提下强制一次 CAS，失败或已 consumed 都不得自动重试；不得把 S19 单次 API 无循环误报为跨调用 enforcement。
8. 补齐 external anti-rollback checkpoint/whole-file control-ledger replacement protection、四类 rich packet builders/validators、manifest-bound real preflight observer，以及 control recheck 与真实 action start 的无间隙线性化。

S19 不预批准 S20；S20 是 first possible live stage，不是 guaranteed live stage。

## Release packet raw SHA-256

Report 自身为避免自引用不进入下列清单；其余 16 个 packet path 按 raw file bytes 冻结：

```text
5826f3e800b2337713499612317c158a8348bdc12e1e1420ea028019aa0cf66a  crates/store/Cargo.toml
59e03d3523ffe8fdcad5bdfb5032a4e02ab574d05b6240a5039ebd3188679eb2  crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model/owned_lab_owner_resource_authorization.rs
be93a0956540a20280ad4a6725dffb3a1c1f63d824ad7414fe912ae84b642945  crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model/owned_lab_owner_resource_authorization/source_bound_runner.rs
14ac70ac9e735839102bc46edd6598dd327361265c727f57dfc3ebd96ec77a60  docs/design/MEMORY_TEMPORAL_OWNED_LAB_SOURCE_BOUND_RUNNER_S19_2026_07_17.md
b61782e2f0b85a4cc125b56bce646a835eed08d15e0f10ee26bb16206617702e  docs/design/fixtures/biocortex-ab-track-b-owned-lab-source-bound-runner-contract-s19-v0.json
8d64f4533ef66970f2918ba50a6764be7d8f35ecda47dc9e80a27e4ecbca713f  docs/design/fixtures/biocortex-ab-track-b-owned-lab-source-bound-runner-status-s19-v0.json
e8c75dc6fc15d8ca745ff3c27dc3ab7306036429517de9bcfc06cbc063b22495  docs/design/fixtures/biocortex-ab-track-b-owned-lab-subject-manifest-schema-s19-v0.json
989091d08d3ffa48b97df8a85ef239846d5cee5581d398bcd0a22eee4dfb2aef  docs/design/fixtures/biocortex-ab-track-b-owned-lab-preflight-receipt-schema-s19-v0.json
fcfa9fb441385b30209af48ca130dc93362a98dd5f966c9516b1c8d512774481  docs/design/fixtures/biocortex-ab-track-b-owned-lab-control-snapshot-schema-s19-v0.json
723627a925c5d876bc210d0ce478a44a439ed7129a7f2f05620a0e63aba038fd  docs/design/fixtures/biocortex-ab-track-b-owned-lab-authority-control-claim-schema-s19-v0.json
f3ecbf2a03ba2c9def0e0d06c0fd2371aede65c79c09fe7f5cc7b907874de491  docs/design/fixtures/biocortex-ab-track-b-owned-lab-post-run-receipt-bundle-schema-s19-v0.json
07820514eb342fb5f3a0a262f13128945b3aa3751d5de19891f0a1a8267bf022  docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s19-v0.json
9d7bb8947ff5838d9e87fe9b71805603246881aba146e57eae9926e0fb0d9385  docs/design/fixtures/biocortex-ab-track-b-owned-lab-subject-manifest-synthetic-s19-v0.json
294c9fc3b9ecd12276959a498ff827a1b12df1d00c12f9595ddc73dc2d0771fa  scripts/eval/check_memory_temporal_owned_lab_source_bound_runner_s19.py
5468d235a8f9eebffad298b854152e7261d4436a79fa0846081470bc18e7f9d0  scripts/eval/fixtures/memory_temporal_owned_lab_source_bound_runner_s19.expected.v0.tsv
1b33ee073bb6fbf4446a4f92e4dfc195f32b54b0cdfb48311ab79cf171a02b8f  scripts/check-memory-temporal-owned-lab-source-bound-runner-s19.sh
```
