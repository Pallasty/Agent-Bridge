# FH-L8 D13：q5 重设计选择门

D12 已排除当前 D10 信封内的完整 q5 物化。D13 进一步排除两个伪捷径：未经新授权的资源扩容，以及把交错磁化或双占据与 hopping Hamiltonian 交换的 contraction。两种 observable 都不具有该守恒关系。

因此唯一允许的后继是 `OBSERVABLE_SPECIFIC_ADJOINT_CONTRACTION_CONTRACT_DESIGN`。该门必须先给出并验证不依赖 `[O,H]=0` 的精确 adjoint/contraction 恒等式、输入输出坐标、资源上界与独立误差范围，之后才能执行任何新计算。
