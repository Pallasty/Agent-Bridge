# FH-L8 D60 离线 payload 组装（D90）

## 结果

D90 已在本地 staging 组装 296,304,560 字节的自包含 payload。12 项 manifest 全部通过，
包括 rootfs、kernel、initramfs、匹配版本的完整 modules tree、shim/GRUB、当前 canonical
Git history bundle、启动配置模板、D88R/D89 provenance 和本地 evidence 目录。

对抗检查在首次组装后发现 rootfs 未包含 kernel modules，因此未提前宣告完成；随后增加
`modules-7.0.0-29-generic.tar.xz`，验证 `sdhci-pci.ko.zst` 与 `modules.dep` 后重新生成
manifest。配置模板含 `irqaffinity=0-14 isolcpus=managed_irq,15`，且不含本机 NVMe 设备
路径或 UUID。

## 尚未开放的边界

`grub.cfg` 与 `fstab` 仍保留 root/ESP UUID 占位符，因为物理分区尚不存在。因此 D90 只
证明 payload 可复核地组装完成，不证明物理 MMC 可写、固件可从 SD 启动或测量可执行。

D91 应使用本地虚拟磁盘/UEFI 环境做离线 boot rehearsal，验证解包、模块布局、GRUB 配置
生成和早期启动链；不得以 rehearsal 替代真实固件 SD 启动证明，也不得挂载或写入 MMC。

D90 不授权 MMC 写入、引导变量变更、重启、D82R、测量或 full53。
