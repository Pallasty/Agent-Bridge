# FH-L8 D20：全量 53 分片消费者实现冻结

D20 冻结全量消费者的输入、分片、恢复、合并与发布语义：只能读取 committed packed q3（213,099 条）；必须恰好处理 53 个 source shard，使用 256 个 SHA-256 target 分区、manifest-only merge、无 gap/overlap/orphan-byte 的恢复检查，以及 atomic no-replace target 和终端资源回执。

该实现冻结故意拒绝 action：contract 的全量授权、q3 rows 与 kernel evaluations 都为零。任何 `--attempt-action` 在 Hamiltonian action 前失败关闭。

下一门是 **full 53-shard resource preflight and authorization**。需要独立为全量工作冻结资源模型和明确授权；D20 本身不执行 full action。
