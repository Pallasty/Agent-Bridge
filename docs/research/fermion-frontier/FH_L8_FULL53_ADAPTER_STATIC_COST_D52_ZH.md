# FH-L8 D52：静态 adapter IR 与操作计数

## 结论

`VERIFIED_D52_STATIC_ADAPTER_IR_AND_OPERATION_BOUNDS_COSTS_UNRESOLVED`。

D52 将 production 数据流固定为四个不可执行的 IR 阶段：解码单个 source record、调用
已绑定的 `_reduced_column`、编码 partition records，以及在下一个 source 前释放整列
引用。AST 审计确认 `_reduced_column` 仍只有一个 `_sector_action` 调用点、两个
`_canonical_info` 调用点、两个 `Fraction` 调用点和一个 child loop。

在 D51 的 213,099 sources 与每 source 225 candidates 上界下，静态放宽得到：

- `_canonical_info` 调用不超过 48,160,374；
- D4 images 不超过 385,282,992；
- `Fraction` 构造不超过 95,894,550；
- reduced-column 更新不超过 47,947,275。

这些是操作次数，不是对象存活数、分配字节或宿主运行时间。sector-action dictionary、
canonical/image/Fraction transient、reduced-column dictionary、partition writer state
和每操作耗时仍有七类成本未闭合。

D52 没有创建可执行 production adapter，不读 packed q3，不调用科学内核，也不授权
full-53。下一门是
`D53_OBJECT_ALLOCATION_AND_OPERATION_COST_MEASUREMENT_PROTOCOL_DESIGN`。
