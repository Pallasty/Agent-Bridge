# FH-L8 D56 production adapter 与资源界闭合计划

## 目标

D56 不实现 adapter、不执行测量或科学 kernel，也不授予 full-53 权限。它把 D55 的六项
未决条件转换为 D57–D62 的有序验收路线，使每一项资源声明都有明确来源、检查器和停止条件。

## 路线

1. D57 固定 production streaming adapter 的 decode、kernel、spill、merge、publish 接口，
   保证逐 source 释放 column，并保持 full-53 入口 fail-closed。
2. D58 依据 D57 的真实存活期，为 Python runtime、column、writer、sort heap 等 allocation
   classes 提供独立静态上界；D54R 只能辅助排序热点，不能替代上界。
3. D59 针对同一 adapter 的 production spill/merge 路径，闭合 clean/dirty page、writeback、
   fsync 与两代 spill 同时存在时的 page-cache 项。
4. D60 在任何补充 timing 测量之前冻结 operation population、环境和 margin/static rule；
   两次 D54R 的离散程度本身不是 margin。
5. D61 汇合 D58–D60，按 D51 phase lifetime 重算峰值内存、运行时间、文件数与 scratch，
   并明确闭合或保留 D23 的 359,759,114-byte 缺口。
6. D62 只在 D61 完整通过后验证真实外部资源预留。缺失、过期或容量不足均返回 NO-GO。

D57 完成后 D58、D59、D60 可并行；D61 是三路汇合点，D62 是唯一可能讨论 full-53
授权的终门。

机器可检验的 coverage matrix 进一步固定了责任边界：D51 的 4 个 lifetime phases、
D52 的 4 个 adapter stages 和 6 个 operation bounds 都有明确后继门。D56 还逐门冻结
最小权限：D57 contract verification 的科学调用为零；D58 不获对象测量权；D59 不获
production I/O 执行权；D60 不获 timing 测量权；D61 不得假设外部容量；D62 的决议本身
不等于执行，且没有真实 reservation receipt 时必须 NO-GO。

## 当前边界

本门结果是 `VERIFIED_D56_ORDERED_PRODUCTION_ADAPTER_AND_RESOURCE_BOUND_CLOSURE_PLAN`。
production adapter、数值内存/时间界、外部资源预留和 full-53 授权均仍为 false。
下一门为 `D57_PRODUCTION_STREAMING_ADAPTER_IMPLEMENTATION_CONTRACT`。
