# FH-L8 D45：受控资源 replay

D45 在 CPU 0 affinity、零 swap、统一 512 MiB 地址空间上限下重放 D42。wall time 为 1.10 s，`ru_maxrss` 为 40,664 KiB，结构摘要仍为 `38aaef…dc12`。这比自由环境下的 RSS 更可比，但仍只描述固定 64-target fixture，不外推 full-53。
