# FH-L8 D60 离线 rootfs staging（D89）

## 结果

D89 在 `/Data/CascadeProjects/.fh-l8-staging/d89/` 成功生成 Ubuntu resolute amd64
minbase rootfs tarball。压缩产物为 43,206,112 字节，XZ 完整性与 SHA-256 均通过，包含
11,397 个归档条目、116 个软件包以及 Python、util-linux、systemd、pciutils 等测量工具。

前三次无特权尝试分别被 user namespace、ownership 语义和缺失 `fakechroot` 阻断，均未
产生可接受产物。最终 root 模式只写独立 staging 路径；MMC 的容量、F2FS UUID 和未挂载
状态保持不变。

## 边界与下一门

该 tarball 只是基础 rootfs，尚未装入当前 kernel/initramfs、EFI loader、D82R 固定源码、
本机启动配置或证据目录。因此 `payload_bundle_complete=false`。

D90 应在新的本地 staging 目录组装这些已固定工件，生成单一 payload manifest，并完成
路径、摘要、容量与无 NVMe 运行依赖的静态检查。D90 仍不得挂载或写入 MMC、修改 EFI、
重启或执行测量。

构建脚本明确检查稳定 MMC 身份和未挂载状态，并拒绝覆盖既有 staging 目标。删除 D89
staging 目录即可回滚本地产物；已安装的 `mmdebstrap` 可保留为审计工具。
