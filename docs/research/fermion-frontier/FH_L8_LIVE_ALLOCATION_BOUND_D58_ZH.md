# FH-L8 D58 活跃分配类上界清单

D58 将 D51 的四个 lifetime phases 与 D52/D57 的 adapter classes 对齐，得到八个需要独立证明
的符号变量：runtime、sector-action、canonical-info、basis-images、Fraction、reduced-column、
partition-writer 与 merge heap。

每个 phase 现在都有由已知 buffer 项和这些符号变量组成的峰值表达式。表达式是 D59/D60/D61
可消费的接口，不是数值内存上界：每一个变量仍需独立的对象表示与 allocator-overhead 论证。

两次 D54R 观测、当前 CPython 的 `getsizeof` 和 aggregate cgroup peak 都被明确禁止作为替代
证明。D58 执行零科学 kernel、零对象测量与零 packed-q3 读取，numeric peak/runtime 与 full-53
authority 保持 false。下一门为 D59 production I/O/page-cache bound。
