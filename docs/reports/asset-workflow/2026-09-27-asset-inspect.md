# asset_inspect 首片验证

决策与接口见 [设计记录](../../design/ASSET-WORKFLOW-MODLY-2026-09-27.md)。
基线为 `6c4b1a9f332d8b9e9329f8d2914deed7db713453`；实现位于隔离分支
`codex/asset-workflow-20260927`。

## 实际覆盖

新增 PNG/GLB 单文件只读检查及 MCP 适配。复用已有 `png`、`sha2`、`serde_json`、
registry 和 structured result，无新依赖。工具 `Tier::Niche`，默认工具配置不扩展。

核心检查有 16 项测试：哈希及魔数、损坏与截断、普通文件与 FIFO、文件上限、PNG
解码上限/APNG/16 位透明度/调色板透明度、GLB 容器与基础引用/范围、BIN 填充、
4 MiB JSON 上限。MCP 层有 6 项测试覆盖真实 handler、参数和注册后的描述符。

先运行空实现：核心独立测试 12 项失败；完整 Cargo 测试 18 项中 15 项按预期失败，
其余 3 项为注册及拒绝行为。随后实现；JSON 上限和 BIN 填充另有针对性失败到
通过记录。最终 16 项核心独立测试通过；完整 Cargo 验证 **22 项通过，0 项失败**，
包括 16 项核心检查及 6 项 MCP 测试。

## 已有素材验收

调用真实 Rust `inspect_file` 检查上次离线试验的 7 个素材；没有重新生成模型或图片。

| 素材 | 观察结果 |
| --- | --- |
| `procedural_gatehouse.glb` | 8,676 bytes；7 meshes、14 accessors、7 primitives；部分结构检查通过 |
| `human_terrain_pass_v1.png` | 512×512；199,539 个全透明像素 |
| `candidate_512.png` | 512×512；214,595 个全透明像素 |
| `candidate_108x84.png` | 108×84；7,392 个全透明像素 |
| 3 张场景 PNG | 各 360×640；230,400 个不透明像素 |

损坏的 `invalid.glb` 和故意错误的预期 SHA 均被拒绝。另用 Python/Pillow 独立复核
7 个文件的长度与摘要、PNG 尺寸与透明度直方图及 GLB JSON 计数，全部一致。
场景图片具有 alpha 通道却没有透明像素，工具正确区分这两件事。

原始素材和前次 56 文件证据清单保持原位。此次命令、失败/通过日志、实际响应、
独立复核记录存放在本机 `/Data/CascadeProjects/.asset-inspect-validation/20260927/`。
关键文件为 `cargo-red.log`、`cargo-green.log`、`core-green-tests.log`、
`core-fixture-reports.json`、`independent-fixture-review.json`。

核心源码 SHA-256：
`6fcd7c255dfbde183f0f36c961877044d7a6204f6e17f26677c9a1d1227e78f2`。

## 复跑与限制

```sh
cargo test --locked -p ab-bridge --lib asset_inspect
```

实现提交为 `f4654ed60cfebb3bdc208f1038762ca5b552e89d`，其 Git tree 为
`4decd54dd9612ca7302bfe9feb1e9ffaaeb9e972`。以下提交钩子检查均已实际通过：

- S18–S21 四组源码/报告绑定，以及选择的边界与集成测试。
- 405 项纯行为案例及其负对照。
- 143 项新鲜 CLI 对比：Identity 30、Instinct 79、WorktreeSession 34。
- `cargo check -p ab-bridge --all-targets`；存在既有警告，退出码为 0。

CLI 对比报告绑定上述实现 tree；本报告的后续文档提交具有不同 tree，不能用它
替代被测实现身份。完整提交日志为证据目录中的 `precommit-posix.log`；
`governance-final/summary.json`、三组 CLI 报告及 `receipt.json` 保留对应身份和摘要。

首次提交尝试因验证环境失败，未产生提交：`/Data` 的 fuseblk 挂载将测试目录呈现为
root 所有，触发既有数据库目录所有权检查。使用同一候选二进制在 `/home` 的 ext4
用户私有目录（UID 1000、0700）复现后通过；随后将验证根目录改为
`/home/pallasting/.cache/agent-bridge-asset-inspect-target-20260927` 并重新运行完整钩子。
`debug` 链接复用原磁盘构建缓存，CLI 状态目录位于用户私有文件系统。没有修改
所有权安全检查，也没有绕过提交钩子。两次初始化诊断及失败日志均保留在证据目录。

按仓库 R7 普通任务诊断流程执行只读 `resident shadow-review` 时，已安装运行时
返回 `resident_m2_shadow_invalid_configuration`；依流程停止，没有预览、提交样本
或修改运行时策略。这不改变 R7 的 HOLD 状态。

新增两个 Rust 文件的格式检查和 `git diff --check` 通过。工作区
`cargo fmt --all -- --check` 暴露既有多个文件的格式差异；没有进行跨模块格式重写。

这证明文件检查可调用并符合所述有限合同；不证明生成模型在 MI50 可用、Modly 的
实际模型输出已兼容、资产符合视觉风格，或工作流提高了完成任务的效率。
GLB 动画/蒙皮、稀疏或矩阵 accessor、外部 URI 等超出本片支持范围。
源码提交不代表服务已部署或当前 MCP 客户端已看到新工具。
