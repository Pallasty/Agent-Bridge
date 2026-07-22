# FH-L8 D14：观测量特异伴随收缩契约

D14 将 D13 所选的路线收缩为一个严格的设计边界；本交付不执行新的 Krylov/收缩计算。

对自伴 Hamiltonian `H`、Hermitian 观测量 `O` 与 `a,b >= 0`，只认证下式的单 Hamiltonian moment 形态：

`<psi|O H^(a+b)|psi> = <H^a O psi|H^b psi>`。

它来自 `(H^a O psi)^dagger=<psi|O H^a`，不需要也不声称 `[O,H]=0`。D5 的 signed quotient 必须使用代表元振幅及 `diag(orbit_size)` 度量，即 `<u,v>=sum_rep orbit_size(rep)*conjugate(u_rep)*v_rep`。

在固定 Néel 初态上，已固定的观测量本征值前提为：staggered magnetization 为 `64`，double occupancy 为 `0`。这些前提仅可简化适配的 moment 子式。

它们不自动处理 D2 的一般双侧 product-formula 项 `<psi|W_L^dagger O W_R|psi>`，也不允许交换 `O` 与 `H`。该项仍需下一门 **word-adjoint decomposition and quotient-inner-product proof** 显式证明词结构、伴随方向和商空间度量均正确。

因此 D14 不提供 q5 执行、D6 remainder、两步累计、R100、physical reference 或 READY 的授权。
