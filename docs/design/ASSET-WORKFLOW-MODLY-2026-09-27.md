# 从 Modly 补全 AB 的资产工作流

日期：2026-09-27。AB 基线：`6c4b1a9f332d8b9e9329f8d2914deed7db713453`。
Modly 审阅版本：`1476fd0b1c19c9ab177c1ca3ee4d1842119e9f65`。

## 决策

用户请求将 Modly 中有价值、AB 尚缺少的组件补入 AB。本轮选择一个可独立交付的
组件：只读 `asset_inspect`。上一轮 GLB→PNG 试验需要临时脚本逐个核查文件、摘要和
尺寸；这正是本轮要消除的重复步骤。没有证据证明需要整体移植 Modly 工作台。

| 能力 | AB 已有基础 | 本轮取舍 |
| --- | --- | --- |
| 工具调用、输入 schema、权限和输出 | `ab-mcp` registry、MCP annotations、structured result | 直接复用 |
| 任务交接、观察、计划记录 | Agent runtime、session、plan 工具 | 复用；计划记录不等于执行 DAG |
| 图片/HTML 展示 | MCP image/resource、`present` | 复用；展示不等于文件验证 |
| 资产文件检查 | Avatar 专用 PNG audit、个别脚本摘要 | 补通用 PNG/GLB 单文件检查 |
| GLB→PNG 固定转换配方 | 已有独立 Godot 离线试验 | 候选下一片；本轮不接生产执行器 |
| 生成模型适配与设备兼容性 | 通用命令入口；缺少经过验证的 3D provider | 等真实可运行模型再适配，不能把 MI50 设备发现当推理通过 |
| 节点编辑器、模型下载管理、资产库 | 无同用途的完整工作台 | 暂不移植；须先出现具体使用需求 |

Modly 的扩展进程、桌面工作流节点与 CLI 单次生成接口不是同一套完整执行器。
AB 的普通 shell 工具也没有证明完整的资产进程组取消语义。Story supervisor 的强
进程监督目前明确属于 synthetic lane，不能为了资产工作流直接宣布生产准入。

## 本轮接口

工具名 `asset_inspect`，通过现有 `Tier::Niche` 注册。`profile=all` 或
`toolset=all-dev` 可见，默认及现有 Codex allowlist 不扩展。

```json
{
  "path": "/absolute/path/to/candidate.png",
  "expected_sha256": "<optional 64 hexadecimal characters>"
}
```

只读取指定本地普通文件，同一份有界字节用于摘要和格式分析。通过文件签名识别
PNG/GLB，不以扩展名为依据。输入上限 64 MiB，PNG 解码另有 64 MiB 界限；
GLB JSON 块上限 4 MiB，避免小文件中的密集 JSON 数组放大内存开销。这些是分别
约束各部分的上限，不是进程总内存额度。

成功响应包含 `schema`、`path`、`bytes`、`sha256`、
`expected_sha256_matches`、`format`、`inspection_level` 和 `details`。
未传入预期摘要时，匹配状态为 `null`。错误摘要、损坏文件或不支持的输入返回工具
错误。`mesh_semantics_verified=false`、`visual_quality_reviewed=false` 始终保留。

PNG 检查提供解码、尺寸及透明度事实。GLB 检查遵循
[Khronos GLB 2.0 容器规范](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#glb-file-format-specification)
的有限子集，提供容器和嵌入数据结构检查；不是完整 glTF validator，不证明拓扑、
材质、渲染器兼容性或视觉质量。不读取外部 buffer/纹理，不执行模型、脚本或下载。

工具不写入资产库、计划 outcome 或任务完成证据，不改变 R4/R7/R9/R10 冻结决策。
摘要是本次读取字节的身份，不能保证检查结束后路径内容不会改变。

## 验收与下一步

本轮必须通过核心格式/负例测试、真实 MCP handler 与 profile 注册测试；使用前次
试验保留的 `procedural_gatehouse.glb`、生成 PNG 和真实参考 PNG 做调用验收。
不重新生成资产来扩大样本。测试结果记录在同日期报告中。

若下一次真实任务需要重复烘焙，再补一条固定的“指定 GLB → Godot → PNG →
asset_inspect → 人工视觉审阅”配方。该片的验收重点应是参数可复现、限时与取消、
输出无覆盖及失败不报成功。真实 3D 模型适配放在设备/依赖兼容性实测之后。

源码实现、测试通过、部署和当前客户端工具可见性是不同状态。本轮默认交付本地
隔离分支，未部署时不能宣称当前 MCP 会话已经可以调用这个新工具。

## 续作：固定中性几何预览

用户随后明确要求“按照你的思路落地建议的目标”，将交付范围从单文件检查扩展到
上述固定 GLB→PNG 配方。采用 Python 显式命令、固定 Godot 脚本，以及直接复用
`asset_inspect::inspect_file` 的 Rust example 入口；不新增 MCP 执行器或通用 DAG。
使用方式见 [固定 GLB 预览配方](../operations/ASSET_GLB_PREVIEW.md)。

当前问题是既有离线试验依赖本机路径和临时驱动脚本，且缺少完整的普通进程组取消
验证。近 30 天的真实重复发生次数及每次人工成本未知，不能据此宣称效率收益。
最小闭环是：给定一个受支持 GLB，在全新目录生成可追溯、待人工审阅的透明预览，
遇到损坏输入、超时、取消或渲染失败则保留失败记录并回收自建进程。

渲染只提供中性材质下的静态几何观察，不承诺原材质忠实、完整 glTF 兼容或美术准入。
验收包含真实子进程的失败/取消测试、真实 Godot 与 Rust 检查入口联跑、带索引及嵌套
变换的原创样件，以及同工具链下重复输出检查。完成这条固定配方即可收口，未测的
3D provider、生产部署、资产库和冻结产品目标不因此自动启动。
