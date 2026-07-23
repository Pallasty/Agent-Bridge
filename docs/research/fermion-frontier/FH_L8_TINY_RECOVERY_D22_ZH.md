# FH-L8 D22-R：tiny-fixture receipt-chain 与恢复加固

D22-R 的状态为
`VERIFIED_D22_TINY_FIXTURE_SUCCESS_RESUME_AND_FAULT_MATRIX`。它实现并实时重放了真实的
shard spill、per-shard manifest、receipt SHA-256 chain、exact-frontier resume、
manifest-only merge、no-replace publication 和 terminal-receipt-last 数据面。

本门只使用 11 个 synthetic signed integers、3 shards、4 partitions。它不读取 packed q3，
不加载 scientific kernel，不产生完整 q4：

- `production_checkpoint_reads=0`；
- `production_q3_rows_acted=0`；
- `production_scientific_kernel_calls=0`；
- `full_53_shard_execution_authorized=false`。

## 与并发 D22 lane 的关系

远端先并发加入了 `FH-L8-INDEPENDENT-REFERENCE-D22-SYNTHETIC-CONSUMER-V1`
（commit `4ad711c775b0079dc4554710805a2bbdee47e86f`）。该 lane 用 53 个两行 synthetic
shards 和 8 partitions 验证基础成功、在 frontier 17 中断后恢复、gap、orphan、manifest
hash、fixture hash 和 no-replace target。

D22-R 使用独立全 ID
`FH-L8-INDEPENDENT-REFERENCE-D22-TINY-RECOVERY-V1`，不重写并发 lane。它补足：

- exclusive nonblocking custody lock；
- 每个 shard 的 receipt SHA-256 前向链；
- exact source slice、partition selector、排序与文件集复核；
- overlap、partition-byte drift、busy/stale lock 与 partial final publication；
- terminal receipt 对 receipt set、chain tail、target manifest 和 target bytes 的绑定；
- 独立 checker 每次验证 committed result 时实时重跑完整 tiny fixture/fault matrix；
- checker-first、contract-before-result 的 Git chronology。

两条 lane 都是 synthetic-only。并发 lane 提供 53-shard control-flow 覆盖，D22-R 提供更强
的 custody/recovery/publication 覆盖；二者都不构成生产 scientific execution authority。

## Deterministic fixture outcome

| 项目 | 结果 |
| --- | ---: |
| source records | 11 |
| shards | 3 |
| partitions | 4 |
| target records | 13 |
| target bytes | 208 |
| target SHA-256 | `f68d75d32458e4d5f89f5c4221105086ed7546c4e6eb7643e3f7a89ca2ca2876` |
| terminal receipt SHA-256 | `dbe9f4bb291e4f90ddd26fdb1a3715fd7879338cf69818e82b533dd0442efef3` |

clean run 与在 shard 1 后停止、重新取得 lock 并 resume 的 run，target identity 与 terminal
receipt identity 均逐字节相同。

## Fault matrix

| Fault | Fail-closed classification |
| --- | --- |
| shard 0 缺失但 shard 1 存在 | `FRONTIER_GAP` |
| shard 0 被复制为 shard 1 | `MANIFEST_DRIFT` |
| scratch 多出未列举文件 | `ORPHAN` |
| partition byte 被翻转 | `PARTITION_HASH` |
| lock 被另一 open description 持有 | `LOCK_BUSY` |
| target/manifest 已发布但 terminal receipt 缺失 | `PARTIAL_PUBLICATION` |
| production checkpoint attempt | `PRODUCTION_NOT_AUTHORIZED` |

partial publication 不被自动“猜测修复”；它要求丢弃 synthetic scratch 后 fresh replay。
生产实现未来若允许恢复该状态，必须另行冻结 recovery receipt 和规则。

## Publication model

每个 shard 先在独立 staging directory 中生成并 fsync partitions、manifest 和 receipt，
再以 hard-link no-replace 顺序发布到新 shard directory，receipt 最后可见。恢复只承认：

1. 从 shard 0 开始的连续前缀；
2. exact manifest-enumerated files；
3. source slice 与 partition bytes/hash/sort/selector 全部匹配；
4. receipt 的 `previous_receipt_sha256` 与前一 shard receipt 相同。

full merge 只读取上述 admitted manifests 列出的 partition files，以 signed i64 精确聚合，
先 no-replace 发布 target，再发布 target manifest，最后发布 terminal receipt。

## Chronology

初始 scaffold `66a5b4328cb86f355d3cef87b9a95553556173fd` 只加入
runner/checker/test。发现 runner contract schema 尚未包含 chronology 后，在 contract 和
任何 fixture execution freeze 之前以
`bb85c6734a92aad27731c3d6d8561a95fed2aa25` refreeze runner/checker。

随后：

- `7362c8b434e3aedf056ca355db4dc9fb3b5f659e`：只加入 synthetic-only contract；
- `7a3f8bbfedc1e589fd14a9a77e1597752f5aeb12`：只加入 live-replayed result。

checker 从 Git 历史验证 contract freeze 的唯一新增文件及其父提交，并确认 result 当时
不存在。

## Authority ceiling 与下一 gate

D22-R 新增的正 authority 只有：

- `tiny_fixture_executable_protocol_verified=true`；
- `tiny_fixture_exact_frontier_resume_verified=true`；
- `tiny_fixture_fault_matrix_verified=true`。

production scientific-kernel binding、worst-case resource bound、full-53 authorization/execution、
full q4、q5 和 READY 全部保持 false。

下一门为
`FULL_53_SHARD_SCIENTIFIC_KERNEL_BINDING_AND_WORST_CASE_RESOURCE_PROOF`。它必须将冻结的
D18-C kernel snapshots 接入一个仍默认拒绝 production action 的实现，并从 kernel fan-out、
53×256 文件布局、merge fan-in 和 recovery overhead 推导可验证的最坏资源上界；在新的
authorization commit 前仍不得读取真实 q3 或启动 full action。

本门冻结后，远端并发 D23
`FH-L8-INDEPENDENT-REFERENCE-D23-RESOURCE-ENVELOPE-V1` 已把样本规划值整理为
2,750,812,950-byte / 13,622-file capacity guardrail，并返回
`NO_GO_D23_FULL_53_RESOURCE_ENVELOPE_INCOMPLETE`。它的资源侧下一 gate 是
`FULL_53_EXPLICIT_MEMORY_RUNTIME_AND_EXTERNAL_RESOURCE_RESERVATION`。该 guardrail 仍非
worst-case proof，也没有完成 scientific-kernel binding；两个缺口必须在未来 authorization
前同时闭合。
