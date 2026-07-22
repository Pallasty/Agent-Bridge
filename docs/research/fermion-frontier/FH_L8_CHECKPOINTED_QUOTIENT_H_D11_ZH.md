# FH-L8 D11：checkpointed signed quotient-H runner（分片验证）

完整 depth-3 source checkpoint 已被消费。runner 将每个 signed quotient contribution 以固定 32-byte `(target_u128, scaled_delta_i64, reserved)` 记录按 target SHA-256 首字节分到 256 个 partition；合并时按 target 排序、以 i128 语义累加并要求总量可被公共分母 8 整除。

在受限 cgroup scope 中，完整首分片（4096 source reps）产生 `868786` 个 reduced spill records。sort/merge 输出 `424682` 个 target，payload 为 `13589824` bytes，digest 为 `8b43b76f1e7a45f12e220905bcba41dc7cfef9fce66f0257cb3c9dff9623fa5f`。它与直接 signed quotient-H 的逐项结果完全一致。

全量 53 分片随后在同一 1 GiB、zero-swap scope 内完成。每个分片均保留 offset/bytes/SHA-256 的 durable manifest，恢复前重新验证对应 spool 段。全局 256-partition merge 产生 `10785545` 个 depth-4 target，payload `345137440` bytes，SHA-256 为 `9769bbcd39cb5d48a83f42e8a8fa838c7577f8ab4978876f0fc4fe582250587c`。全量 spill 与 merge 的峰值均为 768.5 MiB，swap 为 0。

这只完成 fourth signed quotient-H action；D6 remainder、累计误差、R100、physical reference 与 READY 仍未获认证。
