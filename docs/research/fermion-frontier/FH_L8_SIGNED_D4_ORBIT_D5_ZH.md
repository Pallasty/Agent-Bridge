# FH-L8 独立参考 D5：signed D4 轨道边界

本门验证了 L=8 OBC Hubbard Krylov 扇区上的八个 signed Fock 模式置换：纯空间中会翻转 Néel 棋盘奇偶性的旋转/轴反射必须与自旋交换组合。八个元素的 Néel signed character 全为 `+1`，并通过结构性映射检查证明交错磁化与双占据不变；深度 0–2 的 Hamiltonian 向量等变性也逐元素复核。

精确轨道结果为：深度 0 为 `1 → 1`，深度 1 为 `225 → 29`，深度 2 为 `24421 → 3116`。深度 3 共 `1704285` 个态；受确定性前缀上限约束，仅完成前 `100000` 个态，得到 `71064` 个轨道，digest 为 `fef172646dbf2ddadd913a0b67cc4f0360cc25dd48a261decaf6b9a5cbf5c68a`。因此本门是 custody-positive，但不是完整深度 3 商空间证明。

本门没有执行压缩 Hamiltonian、D6 剩余度或累计误差界，相关 authority 均明确保持为 false。下一路线固定为 `BYTE_TABLE_SIGNED_BIT_PERMUTATION_ORBIT_CANONICALIZATION`。
