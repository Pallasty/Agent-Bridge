# FH-L8 state-specific defect D1

## 结论

D1 已为固定 L8 OBC、`U/t=8`、`T=1`、`R=100` 的第一步建立双 observable 的严格
PF-to-exact-Hubbard expectation defect 上界：

| observable | exact `D4` Néel coefficient | fifth-order remainder bound | total bound | `1/400000` 占用 |
|---|---:|---:|---:|---:|
| staggered magnetization | `115/6` | `22673197/19200000000000` | `8784399/6400000000000` | `8784399/16000000` |
| double occupancy | `-115/12` | `3648827/2560000000000` | `11682481/7680000000000` | `11682481/19200000` |

两者分别约为 `1.37256e-6` 与 `1.52116e-6`，均严格小于单步 allocation `2.5e-6`。

## 证明结构

既有 checker 已证明 formal degrees 0--2 相同，degree-3 Néel expectation 对两项 observable
均为零。D1 进一步完整合并 product 与 ideal 的 degree-4 Pauli expansion，直接计算
`<q|D4(O)|q>`；这里不以 `D4` 的 Pauli-L1 代替目标 expectation。余项则对 ideal
`ad_H^5(O)/5!` 和九阶段 product 的全部 `C(13,8)=1287` 条 degree-5 weak compositions
使用 operator-norm Pauli-L1 上界。由正 stage coefficients 与外层 unitary conjugation 的
norm isometry，得到对任意 `delta>=0` 的五阶积分 Taylor remainder；代入 `delta=1/100`
即为表中结果。

## 资源与边界

磁化量/双占据分别使用 103,506,944 / 443,025,920 个 commutator pair products，peak expansion
为 272,832 / 731,693 项；均低于预提交的 500,000,000 与 800,000 caps。每个 observable
的 degree-5 product ledger 都含 1,287 条路径与 2,002 个 cached prefixes。

最高 authority 仅为 `VERIFIED_FH_L8_K0_K1_STATE_SPECIFIC_DEFECT_WITHIN_ALLOCATION`。
它不覆盖 `k1` 之后的 evolved state/observable，不可乘 100，不认证 physical reference、
full R100 或 READY。下一阶段 D2 必须先决定是否能复用同一 scalar architecture 到
`k1 -> k2`，并为 evolved-state custody 与新增资源增长另发契约。
