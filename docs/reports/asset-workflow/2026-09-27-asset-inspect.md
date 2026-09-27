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

共享 Rust 改动还需经仓库 pre-commit 的四组 CLI governance 选择、实际 CLI 对比及
`cargo check -p ab-bridge --all-targets`；提交时执行，不能用旧报告替代。

新增两个 Rust 文件的格式检查和 `git diff --check` 通过。工作区
`cargo fmt --all -- --check` 暴露既有多个文件的格式差异；没有进行跨模块格式重写。

这证明文件检查可调用并符合所述有限合同；不证明生成模型在 MI50 可用、Modly 的
实际模型输出已兼容、资产符合视觉风格，或工作流提高了完成任务的效率。
GLB 动画/蒙皮、稀疏或矩阵 accessor、外部 URI 等超出本片支持范围。
源码提交不代表服务已部署或当前 MCP 客户端已看到新工具。
