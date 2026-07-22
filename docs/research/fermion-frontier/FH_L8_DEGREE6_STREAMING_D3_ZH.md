# FH-L8 degree-6 streaming D3

## 结论

D3 将 D2 的 100,947-prefix 内存问题改写为 depth-first trie。每个 prefix 只计算一次，同时仅
保留当前深度不超过 6 的路径，因此 peak live terms 对磁化量/双占据仅为 13,824 / 21,888。
streaming 的内存架构成立。

但总算术量在很小的 partial prefix 上已超过冻结的 2,000,000,000 prospective degree-6
pair cap：

| observable | 已完成 depth-5 leaves / 20,349 | 已算 prefixes | prefix work | D6 floor before → after |
|---|---:|---:|---:|---:|
| staggered magnetization | 3,958 | 4,757 | 246,977,024 | 1,999,928,832 → 2,000,279,040 |
| double occupancy | 1,108 | 1,301 | 196,990,976 | 1,998,983,680 → 2,000,065,024 |

checker 只用 `len(parent) * len(next_group)` 计算下一 commutator 必定发生的 pair products，在
超过 cap 前停止；没有生成任何 degree-6 child expansion，也没有给出虚构 remainder。

## MITM 边界

固定 `PAULI_L1_MEET_IN_THE_MIDDLE` 候选需要把左右半链记录组合成完整 nested commutator 的
exact Pauli-L1。L1 在合并与 cancellation 后才可取绝对值，单独的 half norms/digests 不满足
所需组合恒等式；当前没有该 proof，因此候选状态是
`BLOCKED_MISSING_COMPOSITION_PROOF`，且没有执行数值任务。这不构成对所有 MITM 方法的一般
no-go。

## 下一路线

下一目标为 `SCALAR_DERIVATIVE_SUPREMUM_ENCLOSURE`：绕开逐 path operator-L1 求和，直接寻找
两步 scalar expectation 六阶导数在 `t in [0,1/100]` 上的严格 supremum enclosure；候选包括
sector-restricted interval Krylov、带余项的 scalar Chebyshev/Taylor enclosure，或有来源常数的
复解析/Cauchy bound。

最高 authority 仅为 `VERIFIED_D3_STREAMING_PAIR_CAP_AND_MITM_COMPOSITION_GAP`，不认证
degree-6 remainder、两步累计误差、full R100、physical reference 或 READY。
