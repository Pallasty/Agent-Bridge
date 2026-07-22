# FH-L8 D5 双轨身份对账

## 结论

合并时发现两条从同一 D4 基线独立产生的证据轨道都使用了历史内部标识
`FH-L8-INDEPENDENT-REFERENCE-D5`。原始 contract/checker/result 均保持逐字节不变；裸标识
从此禁止用于证据查找或授权，必须使用 reconciliation 分配的唯一 lane alias，并同时绑定
artifact path、Git blob、raw SHA-256、bytes 与 commit。

```text
ae393577  common D4-containing base
├── 72fe3b79  D5 signed-D4 prefix/custody outcome
└── 6daf30da  D5 full-quotient protocol freeze (result absent)
    └── 2f9556a9  D5 full-quotient outcome

64438c47 + 2f9556a9 ──merge──> 17ff4b26
```

机器判决为 `VERIFIED_D5_DUAL_TRACK_IDENTITY_RECONCILIATION`。

本 R1 只绑定 D5 lanes 汇合于 `17ff4b26` 时的身份与 prospective selection snapshot。其后
出现的 byte-table support-orbit D6 descendant 不属于 R1 的 authority 输出；当前仓库级
选择与执行边界由 D5/D6 descendant R2 addendum 覆盖。

## 两条不可变证据轨道

| lane alias | chronology | certified scope | downstream use |
|---|---|---|---|
| `FH-L8-D5-EVIDENCE-SIGNED-D4-PREFIX-V1` | checker、contract、result 同见于 `72fe3b79`；未建立 result 前预注册 | signed-D4 custody、全 `+1` Néel character、observable map、depth 0--2 exact orbit counts，以及固定 depth-3 100,000-state prefix 的 71,064 representatives | 保留为历史 bounded evidence；不作为 full quotient 的 D6 设计父证据 |
| `FH-L8-D5-EVIDENCE-SYMMETRY-ORBIT-QUOTIENT-V1` | protocol `6daf30da` 先冻结且不含 result；outcome `2f9556a9` | 全部 1,704,285 depth-3 states 压缩为 213,099 representatives，并证明 source depth 0--2 的 quotient/full-vector transitions 严格一致 | 仅作为后续 D6 设计输入 |

两条轨道对 group order 8、全 `+1` Néel characters、observable invariance，以及 depth 0--2
的 `1/1 → 225/29 → 24,421/3,116` 计数一致。full-quotient lane 关闭了 prefix lane 未测的
完整 depth-3 与 quotient-transition 缺口，但不是它的 provenance successor，也不追溯验证
其特定 100,000-state prefix digest。

两边 orbit digest 的序列化与插入顺序不同，不能要求 digest 相等；prefix 的 71,064 也不能
被解释为 213,099 full representatives 的顺序无关比例或界。两条证据不可相加。

## Authority boundary

对账后的最高权限为 `D6_DESIGN_ELIGIBLE_ONLY`，选择 full-quotient lane 仅允许另行设计并
预提交一个使用全局唯一 contract ID 的 D6 协议。该协议必须显式 pin lane alias、路径、
commit/tree/blob、bytes 与 SHA-256，不能再引用裸历史 D5 ID。

第四次 Hamiltonian action、D6 execution/remainder、two-step/full-R100 error、physical
reference、hardware/quantum-advantage 与 READY 均未获授权。
