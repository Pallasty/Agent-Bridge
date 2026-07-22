# FH-L8 D16-F：packed q3 消费者准入与遗留 full-action 托管取证

D16-F 不执行新的 Hamiltonian action。它只完成两件事：独立复核 packed q3 源，并对遗留 full-action 的外部 scratch 证据做预注册、只读取证。最终结论是：packed C3 可以作为后续干净消费者的唯一 admissible q3 源；遗留 target 因生产托管链断裂而被隔离，不能作为权威 q4 结果。

## Packed q3 准入

唯一 admissible q3 源是 packed C3 `784f01b8e3c589b7c6ab25773f93937d5a1344f8`。独立解析确认 213,099 条、每条 32 bytes 的完整记录，checkpoint SHA-256 为 `db2ce0a338a378aef6e4a043e02388c4268addc951d0ae590c2ae1d65f840231`，53 个 source shard 的 manifest SHA-256 为 `c2b4586ed67c4e3b4fd029bc96c3004bfb313fd12e6330a5c24353bed9c60dfb`。C3 的 result 与 terminal receipt 也已精确绑定。

这项准入只说明该 checkpoint 可以成为未来消费者的输入，不表示 D16-F 已执行 q3→q4，也不允许遗留外部 manifest 反向授权执行。

## 遗留 spool 的确定事实

预期输入多重集是 shards `0..52` 各一次。实际保留的 256 个 partition 文件包含 shards `0..52`，并额外包含 shards `25..51` 各一次：

- 额外 gap 共 6,912 个，即 27 shards × 256 partitions；
- 额外 23,126,970 条记录，共 740,063,040 bytes；
- 每个 gap 都唯一、逐字节地匹配同一 partition 内 receipt 绑定的 chunk；
- 整个 retained spool 共 67,812,180 条记录、2,169,989,760 bytes。

四项预登记摘要均复现，包括完整 forensic manifest SHA-256 `869008057db5eb93129aca801dce2dab458ec2cfc6f7fa2894bf04538cb4d79b`。

但 `target_to_spool_provenance_proven=false`：现存 target 与受污染 spool 位于相关 scratch 树中，不等于已经证明该 target 恰由这组 spool bytes 生成。由于 full runner 与 result 同一提交出现、旧 contract 未授权 depth4 执行、packed C3 不是该 full-action 的祖先，并且没有提交 target payload 或 terminal execution/resource receipt，生产托管链已经断裂。因此 target 按 **broken custody** 隔离；其报告的 10,785,545 条记录和 digest 均不是权威 q3→q4 科学结果。这里的隔离结论不依赖、也不声称已经证明 target 与污染 spool 之间的生成因果。

## 与 D16-W 并行单元的关系

本报告把托管取证单元称为 **D16-F custody forensic**。远端后来新增的 observable word-family 代数设计称为 **D16-W algebra design**：feature commit 为 `0fdf571f4006e7f94f63708f37f7e8b634b7613d`，远端 merge commit 为 `69620e7743666c3fa3eb7e0be8cacbd89ee28493`。两者的完整 contract ID 分别为 `FH-L8-INDEPENDENT-REFERENCE-D16-PACKED-Q3-CUSTODY-FORENSIC-V1` 与 `FH-L8-INDEPENDENT-REFERENCE-D16`，不存在标识冲突。

D16-F 的 checker→contract→result 三提交链以当时最新的 `e6cc31c6987cc33d7fbb8890cc172a7ba817cf56` 为 evidence baseline 冻结；D16-W 不在该 baseline 中，而是在冻结后合入远端。因此不改写、不重放 D16-F 已冻结的三提交链。

D16-W 的 contract 明确 pin 了遗留 `fh_l8_d11_full_action_result` 与 D12 result，并把已被 D16-F 隔离的 `q4_representatives=10,785,545`、`packed_q4_payload_bytes=345,137,440` 用于资源设计。因此它的 full-H moment 以及 q0→q4 vector custody/resource 分支属于 invalid-input，不能成为下一数值 gate。仅“单个 atomic hopping factor 不满足 G-equivariance，故 atomic product-formula word family 被拒绝”这一抽象代数判据可以作为 post-hoc design 保留；D16-W 自身仍维持 `execution authority=false`，不能绕过 clean numeric lineage 要求或授权任何数值执行。

## 对 D12–D15 的影响

D12 的 q4→q5 成本是建立在被隔离 q4 基数上的事后条件算术，因此不再具有科学权威，也不能给出 q5 no-go。D13 继承了同一无效数值输入，其 full-q5 no-go 与 route-exclusivity 结论一并失效。

D14、D15 的抽象代数恒等式不因该托管问题被否定，可以保留为 post-hoc design；但它们没有执行权威，必须在未来干净的数值谱系上重新连接和验证，不能沿用当前 D12/D13 链直接升级结论。

## 官方 audit 的资源记录

官方 `audit` 在独立 cgroup v2 scope 中完成了取证读取，`scientific_action_calls=0`，所有 memory events 增量均为零，swap 为零：

| 指标 | 观测值 |
| --- | ---: |
| `memory.max` | 268,435,456 bytes |
| `memory.high` | 201,326,592 bytes |
| 初始 cgroup peak | 18,829,312 bytes |
| 取证快照 cgroup peak | 112,730,112 bytes |
| 取证快照 memory current | 111,521,792 bytes |
| 进程最大 RSS | 38,510,592 bytes |
| 外部读取量 | 2,523,861,175 bytes |
| 读取块大小 | 1,048,576 bytes |
| 取证读取耗时 | 8.997374120 s |

必须保留这个边界：该资源快照在 result 序列化和发布前截止，所以这些数据只证明 forensic reads 在冻结包络内；它们不是覆盖整个命令生命周期的 terminal execution/resource receipt。相应地，`d16_publication_resource_attested=false`、`d16_terminal_execution_receipt_available=false`。

## External 重放的已知工程限制

内建复合 `external` 模式先执行 static 复核，再在同一进程/cgroup 进入 external replay。static 阶段留下的累计 cgroup peak 约 77 MB，超过冻结的 initial-peak 上限 64 MiB（67,108,864 bytes），因此该模式 fail-closed 返回 `INDETERMINATE_D16_EXTERNAL_CUSTODY_AUDIT`。这不是外部证据摘要不一致，也不能被隐藏为“通过”。

为区分资源编排问题与证据问题，另行执行了独立 static 加 fresh-scope split external replay。拆分重放通过，重新得到完全相同的 forensic manifest；其 cgroup peak 为 98,095,104 bytes，进程最大 RSS 为 33,546,240 bytes，耗时 5.473 s。该补充重放证明外部证据仍可复现，但没有生成新的已提交 terminal receipt，也不提升上述发布资源权威。

## 下一 gate

下一 gate 仅限 **fresh exclusive packed-q3 consumer implementation/design 与 bounded-4096 preflight authorization**。实现必须从 packed C3 开始，使用全新且独占的 scratch root，禁止复用 shared append spool，并按 manifest-only merge 与 fail-closed 状态机处理恢复和发布。

当前仍未授权 bounded-4096 preflight 执行、full 53-shard 执行、q4→q5、degree-six remainder、累计误差、R100、physical reference、hardware、quantum advantage 或 READY 结论。
