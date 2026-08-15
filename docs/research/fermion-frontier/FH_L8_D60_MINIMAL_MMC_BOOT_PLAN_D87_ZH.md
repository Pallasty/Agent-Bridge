# FH-L8 D60 最小 MMC 独立启动镜像计划（D87）

## 决策

D87 将 D86 的结构候选收敛成一份闭合计划，但不授予执行权。计划目标是在
`/dev/mmcblk0` 上建立仅供 FH-L8 隔离测量使用的最小系统，使测量态可以完全脱离
`nvme0`。本门不会挂载、备份、分区、格式化、安装、修改 EFI/固件或重启。

## 拟议布局与容量

- GPT 分区表；512 MiB FAT32 ESP；其余空间为 ext4 最小根。
- 扣除 ESP 后理论根容量 63,327,698,944 字节，高于 40,000,000,000 字节预算。
- ESP 同时放置独立 UEFI loader 与标准回退路径 `EFI/BOOT/BOOTX64.EFI`。
- 根系统只包含内核/initramfs、Python、系统探测工具、D82R 固定源码与契约、校验和及
  `/var/lib/fh-l8/evidence`，不复制 `/Data`、`/home` 或日常工作区。

## 数据保护硬门

当前卡上已有 UUID `17a6b72c-efcc-4445-b447-385e96a109a2` 的 F2FS 分区。任何执行门
必须先二选一并形成收据：

1. 使用另一张明确可覆盖的介质；或
2. 记录现有数据处置决定，并在容量足够的独立目标生成整盘镜像，校验摘要且完成抽样恢复验证。

当前 `/Data` 的剩余空间不足以先验保证容纳 63.86 GB 整盘镜像，因此不得默认将它作为
备份目标。没有数据处置、备份容量和镜像摘要三项证据时，分区与格式化必须失败关闭。

## D87R 执行前证据

执行准入前必须全部具备：设备型号/容量/序列身份复核、未挂载复核、数据处置收据、备份
目标容量、备份摘要、固件可从 SD 启动的非破坏性证明、固定 payload manifest 摘要，以及
原 NVMe 启动项可回退的证明。实际命令必须使用 `/dev/disk/by-*` 稳定身份交叉校验，且在
每个破坏性步骤前再次核对整盘目标。

## 测量态验收

从 MMC 启动本身不等于准入。测量前必须证明根来自 `mmcblk0`，不存在 NVMe mount、swap、
打开块设备、日志或工具依赖；`nvme0` 已解绑或断电；MMC IRQ 仍排除 CPU15；CPU15 在线且
D82R 无残留。之后只允许生成一份 fresh D82R plan/apply/verify/run/rollback 收据。

任何一项失败都回退到原 NVMe 启动项，不执行测量。D83 与 full53 仍不在本计划权限内。

## 复核

```bash
python3 docs/research/fermion-frontier/fh_l8_d60_minimal_mmc_boot_plan_d87.py
python3 -m unittest docs/research/fermion-frontier/test_fh_l8_d60_minimal_mmc_boot_plan_d87.py
```
