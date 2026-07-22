# FH-L8 depth-3→depth-4 quotient-H 设计门

## 判决

新合同使用全局唯一、路线特定的 ID：
`FH-L8-QUOTIENT-H-D3-TO-D4-DESIGN-GATE-V1`。机器状态为
`VERIFIED_D7_QUOTIENT_H_DESIGN_GATE_FROZEN_NO_EXECUTION_AUTHORITY`。

这是纯设计门。checker 只执行 Git 元数据查询、原始字节哈希、JSON 解析和整数算术；没有
导入 D5/D6 checker，没有遍历科学状态或候选，也没有调用 quotient Hamiltonian。当前没有
result、runner 或 implementation 工件。

为避免与 Hamiltonian 的命名分组 `H4` 混淆，本文统一称目标操作为“第四次 Krylov
Hamiltonian 作用”，即 depth-3→depth-4 的唯一一次商空间作用。

## 证据输入及语义边界

合同同时固定两条互补但不可相加的证据路线：

- `FH-L8-D5-EVIDENCE-SYMMETRY-ORBIT-QUOTIENT-V1` 提供 signed CAR phase、orbit size、
  projected-zero 规则、每代表态 full-basis amplitude 坐标，以及 depth 0→3 商空间转移语义；
- `FH-L8-D6-EVIDENCE-BYTE-TABLE-SUPPORT-ORBIT-V1` 只提供 byte-table support
  canonicalization 的补充证据，不提供 fermionic phase 或 quotient amplitude。

两条路线共享 D4 输入；它们只在 depth-3 的 `1,704,285` 个 full states 和 `213,099` 个
representatives 上计数一致。D5B quotient digest `7230d8bd…` 与 D6 support digest
`7e4f0d25…` 的编码和语义不同，不能比较成“digest 等价”。裸的历史 D5/D6 contract ID
仍禁止用于证据查找或授权。

商空间坐标保持 D5B 的定义：`q3[r]` 是 canonical representative 对应的 full-basis
per-state amplitude，不是 orbit average 或归一化轨道系数。未来对源代表元 `s` 的一个子态
`x`，目标代表元 `t=rep(x)`，必须使用：

```text
q4[t] += q3[s] * H[x,s] * CAR_phase(x→t) * |Orbit(s)| / |Orbit(t)|
```

D6 byte table 最多只能提名 `t` 的 support representative；CAR phase、negative stabilizer
和 projected-zero 判定必须来自 D5B 的 signed 语义，并与 support 结果逐项交叉检查。

## 独立资源计数

| 计数 | 上界 |
|---|---:|
| depth-3 source representatives | 213,099 |
| 每个 source 的 row terms | 225 = 224 hopping + 1 diagonal |
| raw candidate actions / canonicalizations | 47,947,275 |
| candidate group images（群阶 8） | 383,578,200 |
| source canonicality group images | 1,704,792 |
| 全流程 group images | 385,282,992 |
| 每个 group image 的 16 次 8-bit-chunk table lookups | 6,164,527,872 |

这里的 `225` 不是群阶。D4/conditional-spin-swap 群阶是 `8`。D5B 的 300M cap 只能覆盖
raw candidate count，不能替代 group-image budget；因此本合同把两者作为不同 KPI 和硬计数。
这些整数只证明工作量边界已明确，不证明实际运行时间、RSS 或实现可行性。

## 分片、spill 与精确算术设计

未来数据面规划为 53 个确定性 source shards：52 个各 4,096 representatives，最后一个
107。每个满 shard 最多访问 921,600 个 row terms，并产生 7,372,800 个 candidate group
images；候选逐个处理，不保留完整 candidates 或全部 images。

贡献使用 32-byte fixed-width record：128-bit target representative、signed 64-bit
`scaled8`，以及 64-bit 的 orbit/flags/reserved 区。目标 128-bit 大端编码的 SHA-256 digest
首字节直接选择 256 个 partitions 之一，再通过最多 262,144 records 的 sort chunks 和
32-way external merge 做全局确定性归并。64 个 process FD 中为 merge 保留至少 4 个非输入
descriptor，因此满足 `32 + 4 <= 64`。只允许在 exact merge 后删除零项；scratch 必须位于
非 tmpfs/ramfs 文件系统。

分母固定为 8：

```text
scaled8 = q3_amp * H_coeff * CAR_phase
          * source_orbit_size * (8 / target_orbit_size)
```

单条 raw delta 的保守绝对值上界为 `357,287,591,936`，可放入 signed i64；但全 raw-record
的保守 partial-sum 上界为 `17,130,966,424,643,174,400`，超过 signed i64，所以归并必须
使用 checked signed i128。每个最终 target 的总和必须可被 8 整除。

## 1 GiB / zero-swap 规划边界

未来 runner 的规划停止规则为：

- `memory.max = 1,073,741,824`，`memory.swap.max = 0`；
- process peak RSS cap 512 MiB，algorithm-controlled live buffer cap 128 MiB；
- `memory.current` 768 MiB soft-abort watermark；
- 32-way merge、4 个 output/control FD reserve、64 个 process FD cap；
- live scratch cap 4 GiB，累计 spill writes cap 8 GiB，最多 1,024 files；
- internal / outer deadline 暂定 1,800 / 1,830 秒。

这些是未执行的规划 cap，不是观测值或性能预测。D6 result 只保留“240 秒 cap 内完成”，没有
保留精确时间；历史控制台中的 `14.856s` 不能用于外推。depth-4 target cardinality 也未知。

## 为什么下一步还不能运行第四次作用

D5B result 固定了 q3 的 count、digest 和轨道直方图，但没有保存可直接流式消费的 packed
q3 向量。若在未来 action process 内同时重放 full depth-3 dictionary 并构建 depth-4 输出，
会重新引入内存耦合。因此下一 bounded unit 必须先单独设计、生成并认证一个 hash-bound 的
packed depth-3 quotient checkpoint（213,099 条、32 bytes/条，规划上限 6,819,168 bytes）。

该 checkpoint 门还应在使用 byte table 前，对 `8 × 16 × 256 = 32,768` 个表项做全域定义
验证；这不能被 D6 历史上的 4,096-state sample 替代。checkpoint 通过后，仍需新的独立
preflight/execution 合同，当前设计合同不会自动授权 full run。

## 冻结顺序与权限

冻结顺序由 Git 拓扑机器验证：

1. R2 基线 `72e1e56a…`；
2. checker-only `8ecf55a7…`；
3. contract-only `4544d4c0…`。

checker 提交中不存在 contract；contract 提交只新增 contract，并且两次提交都没有 result、
runner 或 implementation。合同只能允许设计下一门 packed source checkpoint。它没有认证：

- packed q3 checkpoint、depth-3→4 quotient action 或第四次 Krylov Hamiltonian action；
- depth-4 target vector、count、digest、实际内存、RSS 或 elapsed time；
- degree-6 remainder、two-step/full-R100 error、physical reference；
- hardware、quantum advantage 或 READY。
