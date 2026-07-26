# FH-L8 D55 测量可采性决议

## 结论

D54R 与 D54R2 的两套完整 70 样本回执可采为同环境回归基线、fixed64 描述性样本和
后续成本热点排序，不可采为 full-53 峰值内存、最坏运行时间、Python allocator 或
资源预留上界。

十个测量目标中，六项仅为 `OBSERVATIONAL_ONLY`，三项为
`NOT_SEPARATELY_IDENTIFIED`，filesystem page cache 为 `NOT_MEASURED`。总体决议为：

`NO_GO_D55_MEASUREMENTS_ADMISSIBLE_ONLY_AS_OBSERVATIONS_RESOURCE_BOUNDS_INCOMPLETE`

## 判断依据

- synthetic owned-graph 数据并非 production adapter 的存活对象图。
- fixed64 返回列对象和耗时只覆盖冻结的 64 个 representative；两次复放的观测最大值
  也不同，不能形成总体性或最坏情况论证。
- canonical-info 与 basis-image 瞬态仅混在整体 tracemalloc 轨迹中，不能单独归因。
- 新进程 cgroup/RSS peak 混合了 Python runtime、import、worker 与目标对象。
- 两次复放均未执行 production spill/merge，因而没有 page-cache 归因。
- timing protocol 没有预承诺且经论证的裕量规则。
- D51 的 359,759,114-byte scratch 缺口和外部资源预留仍未关闭。

两次复放的 fixed64 size=64 结构摘要完全一致，但主机最大观测并不相同：

- cgroup peak 相差 3,231,744 bytes，D54R2 相对 D54R 高 69,332 ppm（约 6.93%）；
- wall time 相差 85,298,967 ns，D54R2 相对 D54R 高 26,122 ppm（约 2.61%）；
- 两次网络隔离机制也不相同。

因此该 spread 只支持“结果结构可复现、成本观测有环境波动”，不能反向充当
precommitted margin rule。

## 下一门

D56 先设计 production streaming adapter 与资源界闭合方案：固定可执行 adapter，
为同时存活的 allocation classes 提供独立对象/allocator 界，覆盖 production I/O 的
page-cache，给出预承诺 timing margin 或静态时间界，并与 D51 phase lifetime 和 D23
scratch 缺口统一核算。D55 本身不执行任何科学 kernel、对象测量或 packed-q3 读取。
