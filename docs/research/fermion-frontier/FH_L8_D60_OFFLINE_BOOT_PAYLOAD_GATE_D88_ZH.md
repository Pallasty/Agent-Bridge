# FH-L8 D60 离线启动 payload 门（D88）

## 结论

D88 已固定当前 EFI loader、Python 运行时与 D82R 离线源码包的 SHA-256。完整启动 payload
仍未闭合：当前内核与 initramfs 位于 `/boot`、权限为 `root:root 0600`，普通用户无法读取
摘要；系统也未安装 `debootstrap` 或 `mmdebstrap`。因此本门为 `PARTIAL`，不授权构建或写盘。

已固定的运行基础为内核 `7.0.0-29-generic`、dracut 110、GRUB 2.14、shim 15.8 和
Python 3.14.3。Secure Boot 当前关闭且平台处于 Setup Mode，但这不替代 MMC 固件启动证明。

## D88R 边界

下一门只需要特权读取两个 `/boot` 文件以记录摘要，并选择/安装一个可重复的最小根镜像
构建器。D88R 不应挂载或写入 MMC；构建产物应先落在临时或独立 staging 目录，生成完整
manifest、容量和可启动性静态检查收据后，再返回 D87R。

任何 sudo 操作都必须限定为明确文件的只读 SHA-256，或明确软件包的安装；不得借此开放
分区、格式化、EFI 变量、重启、D82R、测量或 full53 权限。

## 复核

```bash
python3 docs/research/fermion-frontier/fh_l8_d60_offline_boot_payload_gate_d88.py
python3 -m unittest docs/research/fermion-frontier/test_fh_l8_d60_offline_boot_payload_gate_d88.py
```
