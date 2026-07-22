# FH-L8 D15：词伴随分解与商空间内积证明

D15 处理 D14 留下的一般双侧 product-formula 项：`<psi|W_L^dagger O W_R|psi>`。

若 `W_L=L_m...L_1`，则必须显式记录反向伴随词 `W_L^dagger=L_1^dagger...L_m^dagger`。定义 `ell=W_L|psi>`、`r=W_R|psi>` 后，精确全空间恒等式是 `<psi|W_L^dagger O W_R|psi>=<ell|O|r>`；没有重新排序、交换子或近似。

在 D5 的同一 signed quotient 中，令 `G=diag(orbit_size)`，则仅当左右词的每个因子均保粒子扇区、G-等变，`O` 也等变且满足 `O_Q^dagger G=G O_Q` 时，才允许写成：

`<ell|O|r>=ell_Q^dagger G O_Q r_Q=(O_Q ell_Q)^dagger G r_Q`。

角色不一致、漏记伴随反转、商坐标不一致、观测量不满足度量 Hermiticity，或把截断词冒充精确词，都会被拒绝。

本门只给出代数表示，不枚举可用词族，不给资源上界，也不执行收缩；因此不提供 q5、D6、累计、R100、physical reference 或 READY 授权。下一门是 **observable-specific word-family and resource contraction design**。
