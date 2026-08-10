# FH-L8 D60 NVMe queue-count 可行性门 D85

D85 将 D82R 的下一门收敛为 stock NVMe PCI driver 能否安全减少总 I/O queue 数。结论是
NO-GO：当前 `nvme` module 只公开 `io_queue_depth`、`write_queues`、`poll_queues` 等参数；
它们分别控制 queue depth 或读写/轮询 queue 分类，不是总 I/O queue 上限。本机
`/sys/class/nvme/nvme0/queue_count` 为只读 `0444`，当前值 16。

根文件系统位于 `/dev/nvme0n1p3`，`/Data` 与 `/home` 也在同一 controller，因此卸载或
重载 `nvme` driver 不是安全的运行期实验入口。重启后 IRQ 编号从 175 漂移为 174，但
action 始终是 `nvme0q15`；D85 从此以 action 身份匹配，不把 IRQ number 当稳定标识。

`maxcpus=15` 负试验已回滚：它仍产生 16 个 NVMe queues，并让 CPU7 而非 CPU15 离线。
当前 CPU0–15 均 online，启动参数恢复为
`irqaffinity=0-14 isolcpus=managed_irq,15`，D82R state/cgroup/receipt 均无残留。

下一门必须由 owner 在三类扩权中选择：自定义/补丁内核增加 total queue cap、使用不同
NVMe controller/hardware topology，或修改 D82 的 zero-IRQ target contract。D85 不授予
任何一类扩权，也不授予 measurement、D83 或 full53 authority。
