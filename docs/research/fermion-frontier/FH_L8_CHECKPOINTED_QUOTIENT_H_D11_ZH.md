# FH-L8 D11：checkpointed signed quotient-H runner（分片验证）

完整 depth-3 source checkpoint 已被消费。runner 将每个 signed quotient contribution 以固定 32-byte `(target_u128, scaled_delta_i64, reserved)` 记录按 target SHA-256 首字节分到 256 个 partition；合并时按 target 排序、以 i128 语义累加并要求总量可被公共分母 8 整除。

在受限 cgroup scope 中，完整首分片（4096 source reps）产生 `868786` 个 reduced spill records。sort/merge 输出 `424682` 个 target，payload 为 `13589824` bytes，digest 为 `8b43b76f1e7a45f12e220905bcba41dc7cfef9fce66f0257cb3c9dff9623fa5f`。它与直接 signed quotient-H 的逐项结果完全一致。

此结果只认证单分片。全量 53 分片的持久化调度、跨分片 partition merge 与 resume 仍待实现；尚未执行完整 fourth action。
