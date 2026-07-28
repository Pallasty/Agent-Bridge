# FH-L8 D54：对象成本测量 runner 与有限授权

## 结论

`AUTHORIZED_D54_BOUNDED_OBJECT_COST_MEASUREMENT_NOT_EXECUTED`。

D54 先以独立提交冻结 one-process/one-sample runner。它把 D53 计划展开为 70 个唯一
样本：42 个 synthetic-object calibration 与 28 个 source-bound fixed64 样本，其中
20 个 warmup、50 个 measured。runner 没有精确匹配的授权 JSON 就拒绝运行。

第二笔提交只签发上述固定计划：

- 每个样本必须在独立进程执行；
- CPU 0、`MemoryMax=512 MiB`、`MemoryHigh=384 MiB`、零 swap、禁网；
- 外部 scratch
  `/Data/CascadeProjects/.ab-experiments/fh-l8-d54-object-cost-v1`
  必须在首次启动前不存在；
- synthetic 样本科学调用为零；
- fixed64 每进程最多 67 次，70 个样本合计最多 819 次；
- packed-q3 读取始终为零；
- 每进程必须有 terminal receipt，partial plan 不能成为完整结果。

runner 包含 alias-aware owned-graph 统计、`tracemalloc`、RSS、wall/CPU 时间和结构 digest
采集。它仍需要由后续 launcher 提供 cgroup peak/events、零 swap 与外部写路径强制。

## 当前状态与边界

本门没有创建 scratch，没有启动任何样本，没有执行对象测量或科学内核。授权结果中的
计数均为零。D54 只允许 fixed plan 的未来局部测量，不允许 full-53、packed-q3、网络、
其他外部写入或原位放宽。

即使 70 个样本全部完成，其结果也是实现相关的局部经验成本；不能直接成为 full-53
峰值或最坏运行时间证明。

下一门为 `D54_FRESH_SAMPLE_REPLAY_AND_INDEPENDENT_AGGREGATION`。

## D54-R2 独立隔离复现（2026-07-26）

D54-R2 在并行 D54R 结果出现后，仍从另一组提交后的源码独立执行完 70/70 个
fresh-process 样本，并由独立聚合器重新哈希全部 receipt。最初两次隔离启动均
fail-closed：第一次发现 user-systemd 无法真正落实
`PrivateNetwork`，第二次在 runner 启动前发现嵌套 namespace 被拒；两次均无科学调用，
也没有结果被采信。最终执行改由 bubblewrap 独立网络 namespace 强制只暴露 loopback。

最终闭环结果：

- 20 个 warmup、50 个 measured 全部齐备；
- fixed64 全尺寸结构 digest 精确匹配 `38aaeffb…`，各重复无漂移；
- 791 次科学 kernel 调用，packed-q3 读取为 0，full-53 未执行；
- 所有样本 swap、OOM 与 OOM-kill 增量均为 0；
- fixed64 size=64 的五次 measured cgroup peak 为
  48,824,320–49,844,224 bytes（中位 49,233,920）；
- 同组目标 wall time 为 3.155–3.351 秒（中位 3.213 秒）；
- `tracemalloc` peak 为 3,088,965–3,088,997 bytes。

该结果只证明本机、当前 CPython/实现和固定 64-prefix 工作负载的经验观测，不是
full-53 峰值内存或最坏运行时间上界，也不授予资源预留、full-53 或外推权限。
