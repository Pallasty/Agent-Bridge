# FH-L8 D18：干净 packed-q3 有界预飞

从 committed packed q3 checkpoint 的前 4,096 条记录，在全新独占 scratch root 中完成 signed spill、256 分区 hash-bound merge 与独立 naive 等价性复核。未读取遗留 q4 target 或 shared append spool。

结果为 868,786 个 spill/reduced columns、22 个 projected-zero、424,682 个 target；合并载荷为 13,589,824 bytes，SHA-256 为 `8b43b76f…9623fa5f`，与独立 naive 重算完全一致。

预飞运行在 `MemoryMax=1 GiB`、`MemoryHigh=768 MiB`、`MemorySwapMax=0` 的 user cgroup 内，实测峰值 218,451,968 bytes、耗时 66.543 秒。它只认证这个有界前缀；没有运行完整 53 分片、q5 或任何误差/READY 路线。

下一门是 **clean bounded preflight review and full 53-shard authorization decision**。
