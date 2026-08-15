# FH-L8 D60 异构存储拓扑准入门（D86）

## 结论

D86 只读验证发现一条可继续研究的硬件路径：`mmcblk0` 位于独立的
`0000:2d:00.0` SD/MMC 控制器，其 MSI IRQ 有效亲和性为 CPU1，不占用目标
CPU15。63,847,792,640 字节的现有 F2FS 分区超过 40,000,000,000 字节的最小
测量镜像预算。因此它是**结构候选**，但尚未获得启动或测量准入。

当前根、EFI、`/Programs`、`/home` 和 `/Data` 均依赖 `nvme0`。MMC 上没有已证明的
独立 EFI 启动分区，也没有最小测量工具包。其容量还小于根、`/Data`、`/home`
当前已用空间之和 533,148,512,256 字节，所以“整机克隆到 MMC”不是可行方案。

## 闭合边界

D86 不授权挂载、格式化、迁移、修改引导、变更硬件、运行 D82R、执行测量或
full53。设备目前保持未挂载，现有 F2FS 数据不受改变。

## 下一门 D87

`OWNER_ADMIT_D87_MINIMAL_MMC_BOOT_IMAGE_PLAN` 只规划一个可回滚、最小化的独立
启动环境，而不是复制工作区。D87 至少必须证明：

1. 所有目标写入、分区和引导项均有精确对象、备份和回滚方法；
2. 最小系统、内核、D82R 工具与证据落盘路径在容量预算内；
3. 测量态没有任何 `nvme0` 挂载、swap、日志或工具依赖；
4. 从 MMC 启动后，控制器 IRQ 仍排除 CPU15；
5. 独立启动、失败回退和恢复原系统均有可验证验收项。

只有 D87 经 owner 单独准入并在后续执行收据中满足这些条件，才可重新判断 D82R。

## 复核

```bash
python3 docs/research/fermion-frontier/fh_l8_d60_alternate_storage_topology_gate_d86.py
python3 docs/research/fermion-frontier/fh_l8_d60_alternate_storage_topology_gate_d86.py --live
python3 -m unittest docs/research/fermion-frontier/test_fh_l8_d60_alternate_storage_topology_gate_d86.py
```
