# FH-L8 D30：一次 owner-scoped 微型内核 action

在 D29 的可回滚自主授权下，D30 对 D5 契约固定的 Neel representative `0x66669999666699996666999966669999` 执行**恰好一次** `_reduced_column`。结果为 29 个非零 reduced-column 条目、零 projected-zero 输出，规范化输出摘要为 `eae426…f515`；进程峰值 RSS 为 40,384 KiB。

本次动作不读取 packed q3（`packed_q3_reads=0`），不运行 full shard，且 `full_53_scientific_execution_authorized=false`。它只证明固定内核在一个固定 representative 上可运行；不构成 per-record 最坏时间/内存模型，也不外推为 full-53 许可。

下一门是有界微型 replay 与资源模型：在同一边界内验证可重复性，并把这一点观测明确限定为局部测量而非全量外推。
