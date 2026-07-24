# FH-L8 D40：32-target 局部成本摘要

D38/D39 的 32-target 结构摘要完全一致（`d87e09…6376`）。每轮包含 1 次 seed collector 与 33 次 target/kernel action，共 34 次科学动作；replay 峰值 RSS 区间为 40,572–40,616 KiB，差 44 KiB。

该摘要只描述固定 Neel column 的局部样本。它不读取 packed-q3，不执行 full shard，也不构成 full-53 资源外推或授权。
