# FH-L8 D26：源绑定科学内核的小夹具边界

## 结论

`NO_GO_D26_SYNTHETIC_KERNEL_FIXTURE_ACTION_UNAUTHORIZED`。D26 静态固定了 D18-C 实际绑定的 D5 `_reduced_column`：它接受 `d4, backend, bonds, representative, symmetries`，并调用 `_sector_action`。因此它不是普通纯数据转换；即使构造一个小 representative，调用也会执行新的 Hamiltonian action。

源码中可见每列 225 个候选 action 的结构性上界，但这不是每记录运行时、峰值内存或 full-53 最坏情形证明。D26 不导入或调用该内核，不读 packed q3，两个动作计数均为零。

## 下一门

需要独立授权一个严格源绑定的微型科学 action，并同时记录可复核的内存和运行时收据；它仍不能自动扩展为 full-53 授权。
