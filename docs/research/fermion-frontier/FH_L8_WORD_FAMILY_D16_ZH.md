# FH-L8 D16：观测量词族与资源收缩设计

D16 审计了 D15 的逐因子 D4-等变要求。`R90` 将原子 hopping 组映为 `H1→H4`、`H2→H3`、`H3→H2`、`H4→H1`；因此单独的 `H1`–`H4` 不是 D4-等变因子。当前原子 product-formula 词族不满足 D15，接受词数为零。

唯一留下的设计候选是固定完整 Hamiltonian 的 moment 词族：对两个固定对角观测量，在总 `H` 深度不超过 4 时，每个观测量有 15 个 `(a,b)` 分裂，共 30 个设计规格。这不是 q5 计算，也不是 product-formula 误差结论。

已知 q4 的 10,785,545 个代表元载荷为 345,137,440 字节；一个双 q4 向量收缩至少涉及 690,274,880 字节的向量载荷。观测量本身为固定对角量，不扩张支持。但尚未冻结 q0–q4 向量保管与双向量收缩协议，当前内存可行性仍未认证。

下一门是 **pinned q0–q4 vector custody and dual-vector contraction protocol**。不执行收缩，不提供 q5、D6、累计、R100、physical reference 或 READY 授权。
