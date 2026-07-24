# FH-L8 D42：双 seed 64-target 局部调查

D41 的 32-target fixture 不足以扩展到 64。D42 增加第二个 source-bound seed（Neel 列的首个 canonical target），确定性得到 64 个 targets；共 67 次受限动作。列条目数为 110–220，峰值 RSS 为 38,264 KiB，结构摘要为 `38aaef…dc12`。

该 fixture 仍不读取 packed-q3、不执行 full shard，不能外推为 full-53。
