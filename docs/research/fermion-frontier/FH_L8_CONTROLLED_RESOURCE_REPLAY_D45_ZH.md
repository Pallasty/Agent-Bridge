# FH-L8 D45：受控资源复放

D45 在可用时固定 CPU 0，并以两个 fresh baseline 与两个 fresh D43 replay 比较 RSS。结构摘要必须保持 `38aaef…dc12`，每次 replay 为 67 个动作；资源观测只在同一 CPU 条件下记录，不解释为 full-run 上界。

本门仍不读取 packed-q3、不执行 full shard、不构成 full-53 外推或授权。若 replay RSS 的同条件跨度超过 4 MiB，下一门转入资源方差降低，而不是扩大规模。
