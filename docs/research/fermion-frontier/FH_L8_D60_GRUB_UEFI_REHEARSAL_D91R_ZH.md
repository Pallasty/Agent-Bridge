# FH-L8 D60 GRUB UEFI 演练修复 D91R

D91R 保留前四次失败并在第五次关闭虚拟 UEFI 链。修复方式是把 kernel/initramfs 嵌入
standalone GRUB EFI 的 memdisk，消除 `(hd0)` 与 vvfat 搜索的不稳定映射；同时用
`rd.fstab=0 rd.hostonly=0` 禁止宿主 host-only initramfs 等待不存在的宿主 ESP UUID。

最终 QEMU/OVMF 日志证明 EFI 加载 kernel、发现 `/dev/vda`、switch-root，并进入真实 rootfs
的 systemd `basic.target`，没有 GRUB prompt 或 kernel panic。最小 rootfs 随后等待
`ttyS0.device`，但 multi-user 从未是 D91 的冻结要求，因此不阻断这条 UEFI kernel chain。

MMC 与宿主 bootloader 均未触碰，宿主未因本演练重启。该 PASS 不是物理 SD 启动证明，
也不授权 MMC 写入、固件启动、D82R、测量或 full53；下一门必须是单独的 D92 owner 准入。
