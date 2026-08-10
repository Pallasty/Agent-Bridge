# FH-L8 D60 managed IRQ 启动期方案

## 当前事实

当前内核命令行没有 `isolcpus`。IRQ175 是 `nvme0q15`，configured/effective affinity
均为 CPU15；D82R 的运行期 IRQ 写入被内核拒绝并已自动回滚。每个可选 CPU 都存在
至少一个 NVMe 单 CPU managed IRQ，因此换 CPU 不能满足 D82 的 zero-IRQ 条件。

## 批准的变更

在 GRUB 增加 `maxcpus=15 irqaffinity=0-14 isolcpus=managed_irq,15`。`maxcpus=15` 让
NVMe probe 在启动期只看到 CPU0–14，从而不创建只绑定 CPU15 的第 16 个队列；系统启动
完成后再通过 CPU hotplug 将 CPU15 online。Linux 文档规定 `maxcpus` 只限制启动期，其他
CPU 可通过 `cpu15/online` 后续上线。`irqaffinity` 先把默认 IRQ
分配限制到 housekeeping CPUs，`isolcpus=managed_irq,15` 再要求 managed IRQ 避开 CPU15；
这两项必须成对使用，因为内核文档明确指出：若队列 affinity mask 只包含 isolated CPU，
`managed_irq` 对该队列无效。普通调度域仍交给后续 cgroup v2 isolated partition 管理。内核文档定义
`HK_TYPE_MANAGED_IRQ` 正是由该参数移走的 IRQ handlers；至少保留 CPU0–14 作为
housekeeping CPUs。

变更前必须保存：`/etc/default/grub`、相关 `/etc/default/grub.d/*.cfg`、
`/boot/grub/grub.cfg`、`/proc/cmdline`、CPU topology、所有 IRQ configured/effective
affinity。写入后只运行 `update-grub`，不自动重启；重启是独立确认点。

## 回滚

删除本事务创建的 `/etc/default/grub.d/99-fh-l8-d82r-managed-irq.cfg`，运行
`update-grub`，再重启即可恢复原启动参数。若新内核无法启动，从 GRUB 编辑本次
`maxcpus=15 irqaffinity=0-14 isolcpus=managed_irq,15` 参数并启动旧条目，随后执行同一回滚步骤。不得覆盖并非
本事务创建的既有 `isolcpus` 配置。

## 重启后验收

读取 `/proc/cmdline` 必须含 `maxcpus=15 irqaffinity=0-14 isolcpus=managed_irq,15`；确认
`cpu15/online` 已由管理员写为 `1`；读取 NVMe IRQ 列表不得有 effective affinity 命中
CPU15；然后重新运行 D82R `plan/apply/verify/run/
rollback`。只有 fresh receipt、checker 与 owner admission 全部通过，才可讨论 D83。

本方案不授予 timing、scientific、numeric runtime 或 full53 authority。
