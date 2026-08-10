# FH-L8 D60 离线启动演练（D91）

## 结果

D91 的直接 kernel 路径已通过：QEMU 10.2.1 启动 D90 kernel/initramfs，挂载 1 GiB 虚拟
ext4 rootfs，并进入 systemd `basic.target`；串口日志无 kernel panic。EFI binary 通过
`grub-file --is-x86_64-efi` 静态检查。

UEFI/GRUB 链未通过。三次仅在本地虚拟机中调整 FAT ESP、virtio/IDE 盘和 GRUB 映射后，
均停在 GRUB prompt，未进入 kernel。该负结果保留为 `GRUB_VIRTUAL_DEVICE_MAPPING_OR_EMBEDDED_CONFIG_REHEARSAL_BLOCKED`，
不被提升为物理 SD 启动证明。

## 边界

所有虚拟镜像、OVMF vars、ESP 和串口日志均在 `.fh-l8-staging/d91`，未挂载 MMC、未写入
EFI 变量、未重启宿主机。直接 kernel 成功只证明 kernel/initramfs/rootfs 组合在 QEMU 中可
启动；它不证明真实固件能从当前 SD 控制器加载 fallback EFI。

下一门需要 owner 选择：修复 D91R 的 GRUB 虚拟设备映射，或接受 direct-kernel rehearsal
作为有限证据并转回真实介质/固件准入门。D82R、测量和 full53 继续关闭。
