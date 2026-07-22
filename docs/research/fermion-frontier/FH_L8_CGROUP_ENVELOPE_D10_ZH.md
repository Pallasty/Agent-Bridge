# FH-L8 D10：可回收 1 GiB cgroup-v2 运行信封

用户级 `systemd-run --user --collect` 可创建自动回收的 transient scope。实测该 scope 具有 `memory.max=1073741824`、`memory.swap.max=0`、`memory.high=805306368`。

在该 scope 中重跑 D9 的 4096-source preflight 成功：memory.current 从 `78999552` 到 `116690944` bytes，远低于 high-water；signed quotient-H 的 raw/reduced/target 计数与整数振幅检查均保持通过。

这只解除环境信封阻塞。完整第四层仍未执行：它需要依据 D8 的 shard、spill、fsync、hash-bound resume 规则实现专用 checkpointed full runner 并接受独立运行授权。
