# FH-L8 独立参考路线 S0

## 结论

本门不产生物理参考值，而是把下一条可证路线唯一化为 `PER_STEP_STATE_SPECIFIC_EXACT_DEFECT_LEDGER`。下一最小单元为 `FH-L8-INDEPENDENT-REFERENCE-D1`：只处理 `k0 -> k1` 的 state-specific rotated-integrand 缺陷 enclosure；若不能在冻结预算内闭合，必须发布 failure-local 阈值，不得推进 D2。

## 决策证据

现有 exact-Fraction checker 的 R=100 uniform-sup floor 对磁化量与双占据分别为 `159187/16000000` 与 `133927/24000000`，是完整 observable allocation `1/4000` 的 `159187/4000` 与 `133927/6000` 倍。这个固定架构已关闭，但不是 actual Trotter error 下界。普通 support light cone 为 803 层，超过 L8 OBC 物理直径 14，也已饱和。

两个 observable 在 checkerboard Néel 初态上都严格满足 `<q|D3(O)|q>=0`。这不证明完整误差为零，却证明 Pauli-L1/operator-norm triangle 丢掉了与目标 expectation 相关的 cancellation。后继必须保留旋转积分 integrand、粒子数/自旋 sector 与 observable identity。

Childs 等建立了 commutator-scaling 与局域 observable 框架；Childs--Su 给出了 lattice product formula 的 local-error representation。Schubert--Mendl 又专门处理了 Fermi--Hubbard 二维方格 nested commutators，并说明不相交支撑的偶费米项可交换。但这些公开结论仍是全局 unitary/norm 上界，不能直接升级为 bounded observable reference。

## D1 边界

D1 只允许输出严格的 `k0 -> k1` state-specific integral defect enclosure，或首次超过 allocation/resource cap 的 failure-local 阈值。它不得声明 full R100、physical reference 或 READY，也不得由 `k0` 零值推断后续步骤为零。
