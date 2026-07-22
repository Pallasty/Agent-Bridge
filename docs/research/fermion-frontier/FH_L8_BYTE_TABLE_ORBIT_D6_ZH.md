# FH-L8 独立参考 D6：字节表 signed D4 完整深度 3 轨道

D6 将 D5 的 eight signed-D4 模式置换编译为 16 个八位源块到 128 位目标掩码的查找表。对深度 3 的前 4096 个确定性状态及全部 8 个群元素，字节表输出与基准 signed Fock 作用的支持完全一致；符号仅影响振幅，轨道规范化只使用该已复核的支持作用。

完整深度 3 的 `1,704,285` 个 reachable states 归为 `213,099` 个 D4 轨道，digest 为 `7e4f0d2526b49c786b124a8b45dc82cc8892a7798e7c4c362cd4aa15db74ca26`。实测规范化耗时 `14.856` 秒，低于 240 秒上限，约实现八重对称压缩。

这证明完整深度 3 的轨道枚举可行，但尚未构造商空间 Hamiltonian 或执行第四层 Krylov action。因此下一门是 `QUOTIENT_HAMILTONIAN_ACTION_AND_FOURTH_LAYER_COST_GATE`；D6 remainder、累计误差、R100、physical reference 与 READY 仍全部关闭。
