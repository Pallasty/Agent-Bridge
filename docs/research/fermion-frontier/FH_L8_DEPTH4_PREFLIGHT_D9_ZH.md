# FH-L8 D9：第四层 signed quotient-H 首分片 preflight

D9 重建了 depth-3 signed quotient 向量，并只处理首个 `4096` representative 分片。该分片产生 `877976` 个 raw Hamiltonian terms，约简后为 `864300` 个 quotient terms、`317124` 个非零目标；44 个候选因 projected-zero 规则丢弃。所有合并后系数均为整数，说明实测分片符合 D5B signed CAR/orbit-size 语义。

该分片耗时 `30.005` 秒，低于 600 秒分片上限。按 53 分片线性估算，计算时间本身尚未越过 1800 秒内部 stop rule，但这不是性能认证。

决定性边界是环境没有提供 D7 强制的 cgroup-v2 `memory.current` 读数。因而无法验证 high-water memory stop rule，full-run authority 保持 false；未执行完整 fourth action，也未物化 target vector。下一门固定为 `CGROUP_V2_MEMORY_CURRENT_REQUIRED_FOR_FULL_RUN_AUTHORIZATION`。
