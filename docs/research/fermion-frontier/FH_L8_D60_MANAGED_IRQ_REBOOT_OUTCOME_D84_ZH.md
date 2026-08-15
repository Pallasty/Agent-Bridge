# FH-L8 D60 managed IRQ 重启结果 D84

系统以 `isolcpus=managed_irq,15` 成功启动，但 D82 冻结的验收条件没有成立。IRQ175
仍是 `nvme0q15`，其 configured 与 effective affinity 均为 CPU15。该主机的 NVMe0
控制器创建 16 个 I/O 队列；在当前内核和设备拓扑上，启动参数没有把该队列的 managed
IRQ 从 CPU15 迁走。

D84 因而把原启动候选记录为真实 NO-GO，而不是再次循环到相同重启操作。事务 state 与
目标 cgroup 均不存在，没有残留主机变更；也没有生成 D82R fresh receipt。

后续提交 `e93f56a3` 已把下一启动候选收窄为成对使用
`irqaffinity=0-14 isolcpus=managed_irq,15`：先把默认 IRQ 分配限制到 housekeeping CPUs，
再隔离 CPU15 的 managed IRQ。本单元只记录第一次重启的结果，没有执行第二个启动候选，
也不放宽 D82 标准；runtime lock、measurement、numeric runtime 与 full53 authority 全部关闭。

运行 `python3 fh_l8_d60_managed_irq_reboot_outcome_d84.py --live` 可从当前 `/proc` 与
`/sys` 只读重采集同一验收面；它不会写 IRQ、cgroup 或启动配置。
