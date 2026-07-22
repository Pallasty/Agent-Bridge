# FH-L8 symmetry-orbit quotient D5

## 官方判决

固定协议 commit `6daf30daeeb375962b9986af5df91517d8a4a8ec`、tree
`9c7096bca41a1da8c440f37d93a08a4f51e5cef0` 的本次 official replay 返回：

`VERIFIED_D5_SYMMETRY_ORBIT_QUOTIENT_ADMISSIBLE_FOR_D6_DESIGN`

结果 JSON 为 9,319 bytes，SHA-256 为
`a04a4d0be6265dcaf9d39c7937fc133d19c7a2050e1434c7cb24be88b795baed`。该 PASS 只认证固定
L8 OBC、`N_up=N_down=32`、checkerboard Néel 初态、两个固定 observable 与 depth 0--3
上的 symmetry quotient 语义和等价性。

## 语义与 Krylov 等价性

- 八元 Néel-stabilizing D4 作用在改变 checkerboard parity 时配对全局 fermionic spin
  swap；群闭合、初态稳定且两个 observable 都取 trivial character。
- CAR 相位按 site permutation inversion 与 doublon spin-swap phase 计算；cocycle、doublon
  fixture 与 negative-stabilizer zero projection 均通过。
- quotient 存 canonical representative 的 full-basis per-state amplitude，内积 metric 为
  `diag(orbit_size)`，reduced column 使用 `source_orbit_size/target_orbit_size`；完整
  Hamiltonian equivariance 与 metric Hermiticity 均通过。
- depth `0→1`、`1→2`、`2→3` 的 quotient transitions 与完整 Krylov vectors 严格相同。

| depth | full states | orbit representatives | compression | orbit-size histogram |
|---:|---:|---:|---:|---|
| 0 | 1 | 1 | `1/1` | `1:1` |
| 1 | 225 | 29 | `225/29` | `1:1, 8:28` |
| 2 | 24,421 | 3,116 | `24421/3116` | `1:1, 4:125, 8:2990` |
| 3 | 1,704,285 | 213,099 | `1704285/213099` | `1:1, 4:125, 8:212973` |

三次 quotient action 的 raw candidate 上界分别为 225、6,525、701,100；各次预测都与下一层
完整 quotient 相同。后两次各发现 13 个 projected-zero action outputs，均按冻结的负稳定子
规则消去。

## 资源门

官方包络为 1,073,741,824 bytes memory、0 swap 与 600 秒 internal deadline。depth-3 的
213,099 个 representatives 低于 2,000,000 cap；本次完整 orbit audit 使用 13,831,456 次
group actions，低于 16,000,000 cap。预计下一次 raw Hamiltonian action 至多为
`213099*225=47,947,275` candidates，低于 300,000,000 cap。

`383,578,200` 是把每个 projected candidate 再乘八个 group transforms 得到的诊断上界，
不是当前 raw-candidate gate。它必须作为 D6 独立设计中的 canonicalization 成本输入；D5
没有因此执行 depth-3 到 depth-4 的第四次 Hamiltonian action。

## Authority boundary

最高 authority 仅为
`VERIFIED_D5_SYMMETRY_ORBIT_QUOTIENT_ADMISSIBLE_FOR_D6_DESIGN`：允许另行设计并冻结 D6
协议，但 `d6_execution_authorized=false`。

D5 不认证 degree-6 remainder、two-step cumulative error、full R100、physical reference、
hardware result、quantum advantage 或 READY。
