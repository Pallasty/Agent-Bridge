# FH-L8 D54R 对象成本实测收口

## 处置

原 D54 runner 从授权根节点读取 `packed_q3_reads_authorized` 与
`full53_execution_authorized`，而冻结授权把二者放在 `authority` 下，因此原执行路径必然
拒绝真实授权。D54R 不改写历史文件，而以显式修订授权固定纠正后的 runner、worker、
launcher 和独立 aggregator。

## 已执行证据

- 精确完成 70 个新进程：42 个 synthetic、28 个 source-bound fixed64；其中 20 次 warmup、
  50 次保留测量。
- 每个样本由独立 user-systemd service 执行，绑定 CPU0、512 MiB `MemoryMax`、
  384 MiB `MemoryHigh`、零 swap、禁网和 240 秒超时。
- 完整回执集执行 791 次科学 kernel 调用，低于授权总上限 819；packed-q3 读取为零，
  未出现 swap、OOM 或超过 cgroup memory cap。
- fixed64 的 1/8/32/64 前缀各有 5 个测量样本且组内结构摘要一致。64 前缀观测到的
  cgroup peak 为 46,002,176–46,612,480 bytes，wall time 为
  2,992,888,732–3,265,341,182 ns。
- 外部 scratch 清单与按序 70 回执集合均由 SHA-256 身份绑定；提交结果可由 checker
  针对完整外部回执重新聚合。

## 非声明与下一门

这些数字是特定软件、主机和隔离条件下的有限样本，不是 Python allocator 上界、
最坏运行时间或 full-53 外推依据。`numeric_peak_memory_proven`、
`numeric_runtime_seconds_proven` 与 `full53_execution_authorized` 均保持 false。
下一门 D55 只审查这些观测对于 D51/D52 未决成本项的可采性，并决定需要补充何种
静态界、裕量或拒绝外推。
