# 资产工作流合并验证

用户授权：“如果通过验证则合并提交，请清理工作树/临时文件。”

合并前主仓库及两个备份均为 `b7ff6151faf9b6f7bf2811acc9763553f1fac918`。
从该主线建立 landing 分支，合入资产分支 `90730fca92397ac38188e77d247418762d727acf`；
两边改动路径没有交集，自动合并没有冲突。原始功能提交和历史验证记录保留。

被测合并提交：`55e3b34660279e6607a956fbeeef0f862944cb02`。
被测 tree：`4e82f5b1ca21c010da025f4213b3eb3036f4034f`。
本文件的后续文档提交不改变实现，也不替代被测 tree。

## 本轮重新执行

| 验证 | 结果 |
| --- | --- |
| Rust 资产核心及 MCP | 22 项通过 |
| Rust 本地检查入口 | 3 项通过，实际二进制构建成功 |
| Python 流程 | 16 项通过 |
| 真实 Godot 联跑 | 2 项通过，含两次成功渲染及损坏输入拒绝 |
| 既有纯行为回归 | 405 项通过，负对照被检出 |
| 实际 CLI 对比 | 143 项通过：Identity 30、Instinct 79、WorktreeSession 34 |
| 全目标检查 | `cargo check -p ab-bridge --all-targets` 通过，保留既有警告 |

正常提交钩子退出 0。源码/报告绑定与 CLI 报告摘要已独立核验。真实渲染的尺寸、
完整 alpha 统计及累计变换 bounds 另行复核；两次 PNG 的 SHA-256 均为
`2f551de4a6dcce70fa53b3fcdb944e8742198a56333a7838a106c7f3553167a3`，与原验证一致。

合并验证原始日志、报告和样件位于本机
`/Data/CascadeProjects/.asset-workflow-merge-validation/20260927/`，其中
`validation.json` 绑定本轮实现身份和日志摘要。原来的两套资产验证目录仍作为历史证据。

## 发布与清理范围

按仓库发布约定，将同一个最终文档提交非强制推送到 `Pallasty/Agent-Bridge main`
及两个 `master` 备份，并核验远端 SHA。合并只改变源码，不安装 AB 或重启服务。

清理以远端托管和保留包验证为前提：正常移除本次干净工作树，保留分支；删除本次
临时测试程序、渲染缓存和独占 Cargo 验证目录。独占目录中的 `debug` 是共享缓存
链接，只移除链接，不跟随进入 `/Data/CascadeProjects/agent-bridge/target`。

保留原始素材、PNG/HTML 样件、日志和报告、Git bundle、固定配方副本及原检查器
压缩副本。保留包位于 `/Data/agent-bridge-labs/asset-workflow-20260927/retained/`。
清理计划和实际结果分别记录于本机
`/home/pallasting/.agent-bridge-secure/maintenance/asset-workflow-merge-cleanup-20260927/`；
本文件不将计划提前宣称为已删除。其他工作树、未提交改动、锁定实验、安装中的
AB 和共享构建缓存均不在删除范围。

本次确认的是工作流可运行和合并兼容性；视觉验收仍为 pending，真实 3D 模型推理、
风格适配与实际制作效率没有因此获得验证。
