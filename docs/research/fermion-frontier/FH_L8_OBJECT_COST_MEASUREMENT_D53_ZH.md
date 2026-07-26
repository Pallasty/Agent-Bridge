# FH-L8 D53：对象分配与操作成本测量协议

## 结论

`VERIFIED_D53_OBJECT_COST_MEASUREMENT_PROTOCOL_DESIGN_NO_EXECUTION`。

D53 将 D51/D52 尚未闭合的术语映射为十类测量目标，并分成两级 fixture：

- synthetic object calibration：`0, 1, 8, 32, 64, 225` 六个规模，只测
  dictionary、`Fraction`、writer 与 heap 对象，不调用科学内核；
- source-bound fixed64 micro：冻结 `1, 8, 32, 64` 四个前缀及结构摘要，每次最多
  67 个科学动作；D53 不授权执行该级。

每个测量样本必须在 fresh process、CPU0、512 MiB memory max、384 MiB memory high、
零 swap、无网络与无外部写入的边界内运行。每个规模先做两次 warmup，再做五次保留原始
结果的测量。

## 指标与边界

协议同时要求 `tracemalloc` current/peak、`ru_maxrss`、cgroup current/peak/events/swap、
wall/CPU ns、operation count 和结构输出摘要。只有 `tracemalloc` 指标允许减去 runtime
baseline；`ru_maxrss` 与 cgroup peak 禁止做这种相减。

`tracemalloc` 观测不能单独升级为对象字节上界，timing 样本也不能直接升级为最坏时间。
后续仍需独立对象大小/allocator bound 与预注册 timing margin。

D53 没有实现 runner，没有执行对象测量，不读取 packed q3，也不授权 full-53。下一门为
`D54_FIXED64_INSTRUMENTED_OBJECT_COST_MEASUREMENT_AUTHORIZATION`。
