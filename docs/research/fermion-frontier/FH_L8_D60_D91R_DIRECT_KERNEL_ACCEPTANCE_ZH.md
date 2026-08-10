# FH-L8 D60 D91R 直接 kernel 证据接受

D91R 选择接受有限的 direct-kernel rehearsal 证据：QEMU 中 kernel/initramfs/rootfs 成功
进入 systemd `basic.target`，且 EFI 文件格式有效。此前三次 GRUB/OVMF 链失败保留为开放
问题，不被抹除或升级为成功。

因此当前只证明“离线 kernel 与 rootfs 组合可运行”，不证明 GRUB UEFI 链、真实固件 SD 启动、
当前 MMC 可写或 D82R 可执行。所有物理介质、EFI 变量、重启和测量权限仍关闭。

下一门回到外部硬件准入：提供明确可覆盖的至少 64 GB 介质，或满足整盘备份加安全余量的
独立目标，并提供固件 SD 启动证据。获得这些条件前不得格式化当前 F2FS 卡。
