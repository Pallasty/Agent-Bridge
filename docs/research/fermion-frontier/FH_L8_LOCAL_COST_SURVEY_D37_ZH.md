# FH-L8 D37：32-target 上限调查

固定 Neel 列实际只有 29 个 canonical targets，因此 D37 执行 seed 加 29 个 target，共 30 次动作，而非虚构 32 个。列条目数范围为 29–220，峰值 RSS 为 40,556 KiB，摘要 `953561…576f`。

调查零 packed-q3 读取、零 full shard；局部结果不外推为 full-53。
