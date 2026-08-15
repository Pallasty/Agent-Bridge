# FH-L8 D60 maxcpus 与 NVMe 队列拓扑 D85

最新重启保留了 `irqaffinity=0-14 isolcpus=managed_irq,15`，但实际 GRUB 配置没有安装
`maxcpus=15`。CPU15 已 online，NVMe 仍创建 16 个队列；其中 `nvme0q15` 的 IRQ174
configured/effective affinity 都是 CPU15，D82R 仍有 1 个冲突。

D85 不执行主机写入、测量或科学 kernel。下一门是由管理员安装包含 `maxcpus=15` 的
启动配置并重新启动；重启后必须确认 CPU15 online、所有 NVMe IRQ 排除 CPU15，再运行
D82R。任何 cmdline 片段存在本身都不能产生 receipt 或 runtime/full53 authority。
