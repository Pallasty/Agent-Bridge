# 固定 GLB 预览配方验证

基线：`3aca36c815e5196dcfea2753ab332bbdad3f603a`。分支：
`codex/asset-workflow-20260927`。用户明确要求继续落地上轮建议的固定渲染流程。
接口及复跑方式见 [操作说明](../../operations/ASSET_GLB_PREVIEW.md)。

## 交付

- 本地 Python 固定配方：输入快照 → Rust 检查 → 私有 Xvfb/已有 DISPLAY →
  Godot → Rust PNG 检查 → 待人工审阅的 HTML 与 JSON 报告。
- Rust Cargo example 直接复用已有 `asset_inspect::inspect_file`；没有新依赖，
  不启动数据库、daemon 或 MCP 服务。
- 固定 Godot 项目：512² 透明 PNG、中性无光照材质、正交相机、包围盒归一化。
  原导入场景不加入活动树，只复制受支持的静态 mesh 和累计变换。
- 全新输出目录、拒绝覆盖、摘要对应检查、日志限额、总截止时间及 SIGINT/SIGTERM
  处理。自建进程组在成功、失败和取消路径均清理；先保留 leader 身份再回收。

成功状态为 `rendered_pending_review`，`visual_quality_reviewed=false`。本片没有
3D 模型推理、外部服务调用、模型下载、资产库写入、游戏项目修改或生产部署。

## 已执行验证

Rust 薄入口先跑 3 项失败测试，再实现后 3 项通过；既有核心/MCP 检查本轮重跑
22 项通过。Godot 独立副本语法检查通过；headless 拒绝测试从失败到通过；10 项
几何检查包括原试验的 7 mesh/204 顶点样件导入、有效三角形、无效 primitive、
非有限顶点及导入树不进入活动场景。

Python 流程测试使用实际子进程测试工具，覆盖已有文件保护、输入 FIFO、检查器拒绝、
渲染器非零退出、缺失/错误产物、错误回执、透明度、超时、取消、同组后代、日志
洪泛及私有 Xvfb 生命周期。测试工具不作为真实 Godot 渲染证据。

独立审阅实际复现并要求修复两个边界：带执行权限的 FIFO 工具路径会在读取摘要时
阻塞；最终预览文件写入期间收到取消可能发布成功。两者均已修复，先记录失败再验证
通过；新增工具 FIFO 有界拒绝，以及预览/报告写入边界的 SIGINT、SIGTERM 与截止
时间回归。最终 **16 项流程测试通过**，其中最终写入边界覆盖 6 个场景；源码复审
确认两个阻断问题关闭。

真实联跑使用测试内生成的原创带索引立方体和两层平移变换，不依赖 Nexus 素材。
不仅检查 mesh 数量，还验证实际累计变换后的 bounds，避免自动居中掩盖变换遗漏。
重复渲染只检验本机、当前工具链下的确定性，不据此推断其他 GPU 或 Godot 版本。

修复后最终真实集成测试 **2 项通过**：损坏输入在渲染前拒绝；有效样件完成两次
真实渲染。Godot 为 `4.6.2-stable (official)`，OpenGL Compatibility 使用
`llvmpipe (LLVM 21.1.8, 256 bits)`。累计变换 bounds 的 position 为
`[3.75, 2.0, -3.5]`、size 为 `[1, 1, 1]`。两次 PNG SHA-256 均为
`2f551de4a6dcce70fa53b3fcdb944e8742198a56333a7838a106c7f3553167a3`。

另用 Pillow 独立核对尺寸、完整 alpha 直方图与可见包围盒，并核对工具、固定源码、
输入和输出摘要。可见像素未触边；验证结束后没有存活的 Godot/Xvfb 进程。最终运行
目录为证据根下 `integration-4lqmurpe`；`independent-final-review.json` 保留复核结果。
流程源码 SHA-256 为 `d5edb0e2fc12a4d67e3c78ad9658e8ec4a4dd2c58eb802c18f59e92e6c7cac5b`。

## 证据与边界

本机证据目录：`/Data/CascadeProjects/.asset-workflow-validation/20260927/`。保留
RED/GREEN 日志、真实调用参数及产物、摘要、独立检查与提交钩子日志。
最终实现身份和验证数量在本报告的收口记录中绑定，不能把后续文档提交当成被测 tree。

新增 Rust 文件独立格式检查通过；不重写仓库既有无关格式差异。
R7 普通任务只读诊断仍返回 `resident_m2_shadow_invalid_configuration`，依操作规程
停止，没有提交样本或修改运行时配置。

PNG 的有效性和摘要不是美术验收；当前中性无光照结果主要表达轮廓，不能证明原材质
还原、视觉风格、实际模型输出兼容或节省了作者时间。人工视觉审阅仍待真实用途下的
接受/返工意见。源代码与本地调用通过不代表新版本已发布或当前 MCP 会话已更新。
