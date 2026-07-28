# FH-L8 D51：full-53 流式生命周期与运行时工作量设计

## 结论

`VERIFIED_D51_STREAMING_LIFETIME_AND_WORK_UNIT_DESIGN_RESOURCE_NOT_READY`。

D51 将 D50 的 47,947,275 candidate / 1,534,312,800-byte spill 结构上界拆成四个
生命周期阶段：source admission、kernel-and-spill、partition external merge 和 target
publication。固定设计按 partition `000..255`、最大 merge fan-in 32、两层 merge、每输入
与输出 buffer 1 MiB，并且在 terminal receipt 之前不删除旧 runs。

在该保守生命周期下，scratch 设计需求为：

- 两代同时存在的 spill：`2 × 1,534,312,800` bytes；
- source checkpoint：`6,819,168` bytes；
- 53 个 manifest 上限、54 个 receipt 上限和一个 result 上限；
- 合计 `3,110,572,064` bytes。

D23 登记的 `2,750,812,950` bytes 因而少 `359,759,114` bytes，不能满足 D51 设计。
这不是对真实运行磁盘占用的测量；它是在 receipt-first、no-delete-before-terminal 规则下的
保守设计容量。

## 内存与运行时边界

32 个 1-MiB merge input buffers、一个 output buffer、manifest、result 和 receipt 的已知
小计为 `35,520,512` bytes。但以下项尚无数值上界：

- Python runtime 基线；
- 单列 `_reduced_column` Python/Fraction 对象峰值；
- partition writer state；
- sort/merge heap Python 对象；
- page-cache/cgroup 计费；
- 每个工作单元的宿主时间。

因此 D51 不把 35,520,512 bytes 声明为进程或 cgroup 峰值。

运行时只闭合工作量计数：213,099 个计划 kernel calls、47,947,275 candidate visits、
两层 merge 各最多 95,894,550 次 record read/write，以及设计级最多 958,945,500 次
heap comparisons。它们没有被换算为秒数。

## 权限与下一门

D51 不实现 production adapter，不读取 packed q3，不调用科学内核，也不接纳外部资源
收据。`full53_execution_authorized=false`。

下一门为 `D52_PRODUCTION_ADAPTER_STATIC_ALLOCATION_AND_OPERATION_COST_BOUND`：先形成不可执行
的 adapter 实现骨架或静态 IR，逐项封闭 Python 对象分配、writer/heap 生命周期与工作单元
成本；在数值内存/时间上界和更新后的资源收据出现前，不得执行 full-53。
