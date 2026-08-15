# FH-L8 D60 MMC 镜像执行预检（D87R）

## 结论

D87R 完成只读执行预检，结论为 `NO_GO`。稳定设备
`/dev/disk/by-id/mmc-SL64G_0x6ae35823` 正确解析到 `/dev/mmcblk0`，序列号、容量、
既有 F2FS UUID 与 D87 一致，且分区未挂载；设备身份门通过。

执行门仍被四项证据阻断：

1. 没有满足“63,864,569,856 字节整盘镜像 + 20 GB 安全余量”的备份目标；
2. 现有 F2FS 数据既未声明可丢弃，也没有可验证的镜像、SHA-256 和恢复抽样；
3. 当前 UEFI 只证明 NVMe Ubuntu 回退项存在，未证明固件可从该 SD 控制器启动；
4. 最小系统的内核、initramfs、EFI loader 与离线工具 payload manifest 尚未闭合。

## 空间判定

根分区可用约 74.86 GB，表面上大于整卡 63.86 GB，但写完镜像仅余约 11 GB，低于
20 GB 安全线；`/Data` 约 30.75 GB、`/home` 约 2.13 GB，均不足。D87R 不采用压线备份，
也不假设镜像可以压缩，因为卡上数据的可压缩率未经读取证明。

## 恢复与启动边界

UEFI `Boot0002` 的 Ubuntu/NVMe 启动项可作为系统回退，但它不能证明 MMC 启动能力。
`Boot0000 Linpus lite` 是一个既有 MBR 设备路径，其几何信息与当前整卡布局不一致，不能
作为当前 MMC 的稳定启动证据。

下一步需要二选一：提供一张明确可覆盖的至少 64 GB 介质，或提供满足安全余量的独立备份
目标并完成镜像验证；同时用非破坏性固件启动菜单/厂商能力证据确认 SD 启动路径。条件未齐
之前，不授权备份写、分区、格式化、安装、EFI/固件变更、重启、D82R 或测量。

## 复核

```bash
python3 docs/research/fermion-frontier/fh_l8_d60_mmc_execution_preflight_d87r.py
python3 docs/research/fermion-frontier/fh_l8_d60_mmc_execution_preflight_d87r.py --live
python3 -m unittest docs/research/fermion-frontier/test_fh_l8_d60_mmc_execution_preflight_d87r.py
```
