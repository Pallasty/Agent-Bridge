# FH-L8 scalar supremum D4

## 预算门

两步 allocation 为 `1/200000`。扣除 D2 已知 D4 主项后，磁化量与双占据的 remainder slack
分别为 `127/30000000`、`277/60000000`。若写成 `M6*delta^6/720`，所需六阶导数
supremum ceiling 分别为 3,048,000,000 与 3,324,000,000。

## 三个候选的 failure-local 判决

1. **Generic derivative**：五组 Hamiltonian Pauli-L1 为 64、48、384、48、64，总和 608。
   两步 exact/product conjugation 的 derivative base 均为 `4*608=2432`，差的通用界为
   `2*2432^6=413819945587727925248`，比 ceiling 高约 `1.25e11--1.36e11` 倍。
2. **Complex Cauchy**：当前 global-norm majorant 为
   `2 exp(a x)/(x^5(x-1))`，`a=608/25`、`x>1`。用
   `exp(y)>=y^7/7!` 与 `x^2/(x-1)>=4`，其对所有半径的严格下界已经是
   `(608/25)^7/630≈7.987e6`，而可用 scalar slack 只有约 `4e-6`。这只关闭当前 majorant，
   不是所有复解析方法。
3. **Exact sector Krylov**：exact-CAR reachable states 为
   `1 -> 225 -> 24,421 -> 1,704,285`，各层 canonical digests 已固定。下一次 H 作用至少需要
   `1,704,285*225=383,464,125` candidate actions，超过 300M cap，因此未执行第四次 action。

## 下一分支

三条固定候选均不能给出 D6 remainder。下一目标为
`SYMMETRY_ORBIT_COMPRESSED_SCALAR_KRYLOV`：利用 L8 OBC 的 D4 格点对称、checkerboard Néel
稳定子以及可能的自旋交换，把 1.7M reachable states 先按有证明的 orbit quotient 合并；只有
在 action/eigenvalue/observable 都与 quotient 相容后，才能重试第四层。

最高 authority 为 `VERIFIED_D4_SCALAR_SUPREMUM_CANDIDATE_FAILURE_THRESHOLDS`，不认证 D6、
两步累计、full R100、physical reference 或 READY。
