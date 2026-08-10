# FH-L8 D60 特权启动 payload staging 收据（D88R）

## 结果

D88R 的受限特权步骤成功完成。当前 kernel 与 initramfs 已获得 SHA-256，Ubuntu 仓库中的
`mmdebstrap 1.5.7-3` 已安装。授权前后 MMC 保持相同容量、F2FS UUID 和未挂载状态；未执行
MMC、EFI 或固件写入。

本收据只证明构建前提已齐，不声称 rootfs 镜像已经生成或可以启动。特权摘要来源文件仍为
`root:root 0600`，仓库只保存摘要和元数据，不复制受保护启动二进制。

## 下一门 D89

D89 可在一个明确的本地 staging 目录使用 `mmdebstrap` 构建最小 rootfs，固定 suite、
mirror、包清单、大小和 SHA-256。它必须排除 `/dev/mmcblk0`，不得挂载 MMC、安装 EFI
启动项或重启。构建完成后先做离线文件系统与 payload 静态检查，再重新进入介质执行门。

D88R 不授权 rootfs 构建、MMC 写入、引导变更、D82R、测量或 full53。
