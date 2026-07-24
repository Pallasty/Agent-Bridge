# FH-L8 D43：双 seed、64-target 独立复放

D43 重新构造 D42 的 Neel seed 加首个 canonical target 的固定选择，并在两个新进程中执行 64-column replay。两次结构摘要都为 `38aaef…dc12`，与 D42 一致；每次为 67 次受限科学动作，条目数范围 110–220。RSS 观测约为 38,220–103,108 KiB，主机噪声明显，因此 D43 不宣称资源包络通过。

该复放仅验证固定局部 fixture 的结构稳定性。它不读取 packed-q3、不执行 full shard、不构成 full-53 资源外推，也不授予 full-53 执行权限。下一步是 D44 资源观测归一化，而不是扩大科学规模。
