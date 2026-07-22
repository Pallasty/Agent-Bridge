# FH-L8 D5/D6 descendant scope reconciliation

## 当前判决

`FH-L8-D5-D6-DESCENDANT-R2` 将 D5 双轨 R1 与其后出现的 byte-table D6 descendant 一并
对账，机器状态为 `VERIFIED_D5_D6_DESCENDANT_SCOPE_RECONCILIATION`。

```text
D5A signed-prefix lane ──> e45b5b9f byte-table D6 support-orbit outcome
D5B full-quotient lane ──> full CAR/quotient-transition semantics
                         \ /
          future quotient-H design requires both distinct scopes
```

D6 的唯一 alias 为 `FH-L8-D6-EVIDENCE-BYTE-TABLE-SUPPORT-ORBIT-V1`。其 contract 中的历史
parent ID 仍是有歧义的 `FH-L8-INDEPENDENT-REFERENCE-D5`，但 source pins 精确解析到 D5A
`FH-L8-D5-EVIDENCE-SIGNED-D4-PREFIX-V1`，不是 D5B。

## D6 实际完成与未完成的内容

D6 checker、contract、result 同时首次出现于 `e45b5b9f`，因此可以按固定源码复算，但没有
建立 result 前的 preregistration chronology。它对 4,096 个确定性 depth-3 states、每个八元
群作用验证 byte-table support transform，并完成全部 1,704,285 states 的 support-orbit
canonicalization，得到 213,099 个轨道。这与 D5B 的完整 quotient representative count
在共享 D4 输入上的并行实现中一致。

D6 result 只保留 `canonicalization_within_seconds_cap=true` 与 240 秒 cap，并未保留精确
elapsed time。因此此前报告的 `14.856s` 只能视为不可审计的控制台观察，不是认证性能数字。

D6 没有构造 quotient Hamiltonian amplitudes，没有执行 quotient H action，也没有执行第四次
Hamiltonian action。D5B 则证明了 CAR phases、negative stabilizer、metric Hermiticity 与
source depths 0--2 的 quotient/full-vector transitions；两者是互补证据，不能相加或互相替代。

## 下一门边界

当前允许的下一步只是设计 future quotient-H / fourth-layer cost gate。它必须使用新的全局唯一、
route-specific contract ID；历史 `FH-L8-INDEPENDENT-REFERENCE-D5` 与
`FH-L8-INDEPENDENT-REFERENCE-D6` 都已占用且不足以消歧。新协议应同时 pin：

- D5B full-quotient lane 的 alias、commit/tree/blob/bytes/SHA；
- D6 support-orbit lane 的 alias、commit/tree/blob/bytes/SHA；
- raw candidate actions 与 group-transform/canonicalization 成本的独立 caps。

D5B 已验证 source depths 0--2 的 quotient transitions；当前没有授权或执行的是
depth-3→4 quotient-H / 第四次 H action。degree-6 remainder、two-step/full-R100 error、
physical reference、hardware/quantum advantage 与 READY 仍未认证。
