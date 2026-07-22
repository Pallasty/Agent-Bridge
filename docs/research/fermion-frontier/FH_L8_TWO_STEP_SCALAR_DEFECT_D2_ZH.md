# FH-L8 两步 scalar defect D2

## 判决

D2 没有把 D1 标量界乘二，也没有产生两步累计正证。正确的标量对象是直接差

`<q|(P_delta^2)^dagger O P_delta^2-(E_2delta)^dagger O E_2delta|q>`。

把两个九阶段 palindrome 的相邻 `H1/2` 合并后共有 17 stages。exact Fraction 合并得到：

| observable | D3 expectation | D4 expectation | D5 expectation | `delta^4 abs(D4)` |
|---|---:|---:|---:|---:|
| staggered magnetization | `0` | `230/3` | `0` | `23/30000000` |
| double occupancy | `0` | `-115/3` | `0` | `23/60000000` |

奇数阶零值和四阶主项都已机器重算，但四阶主项不能单独冒充累计误差界；首个未控对象是
degree-6 scalar Taylor remainder。

## Failure-local 阈值

17 stages 的 degree-6 product remainder 有 `C(22,6)=74,613` 条 weak compositions；若沿
D1 prefix-cache 架构完整托管，需要 `C(23,6)=100,947` 个 prefixes。两者都超过 D2 冻结的
4,096 caps，因此 terminal branch 是
`DEGREE6_REMAINDER_EXCEEDS_PREFIX_AND_PATH_CAPS`。checker 在计数门处停止，未执行或伪造
degree-6 数值 remainder。

到 D5 为止，磁化量使用 152,605,696 pair products、peak 272,832 terms；双占据使用
575,512,064 pair products、peak 731,693 terms，仍分别低于 650M/800k caps。这说明失败准确
定位在 degree-6 remainder architecture，而不是 D3--D5 exact merge。

## 下一分支

下一独立目标应为 `DEGREE6_SCALAR_REMAINDER_STREAMING_OR_MEET_IN_THE_MIDDLE`：不保留完整
100,947-prefix cache，优先按 split stage/order 做 streaming digest 或 meet-in-the-middle scalar
contraction，并在运行前重新冻结 visits、RSS、wall time 与 partial-prefix failure receipt。

最高 authority 仅为 `VERIFIED_D2_DEGREE6_REMAINDER_RESOURCE_THRESHOLD`。它不认证两步累计
误差、full R100、physical reference 或 READY。
