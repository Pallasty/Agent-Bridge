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
