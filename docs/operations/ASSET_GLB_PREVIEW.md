# 固定 GLB 预览配方

从一个本地 GLB 生成 512×512 透明 PNG，用 AB 的 `asset_inspect` 检查输入和输出，
再交给人审阅。入口是显式运行的本地脚本，不需要启动 daemon 或部署新的 MCP 工具。

这是**中性几何预览**：固定相机、透明背景和中性材质替换。它帮助观察轮廓和几何，
不保留原纹理与材质效果，不代表最终游戏资产、3D 模型生成或美术质量通过。

## 准备与调用

本片在 Linux 上验证；需要 Python 3.13+、Godot 4.6.2 的 OpenGL Compatibility
渲染器，以及可用 X11 显示或显式指定的 Xvfb。其他 Godot 版本尚未验证。
使用已安装的受信任可执行文件；配方不会安装软件、下载模型或调用 Cargo。

先构建薄检查入口，它直接调用与 MCP 相同的 Rust 检查核心，不启动数据库：

```sh
# 使用真实磁盘上的构建目录，不能放在 /tmp 或 tmpfs。
export CARGO_TARGET_DIR=/absolute/user-owned/build-cache
cargo build --locked -p ab-bridge --example asset_inspect

python3 -B scripts/asset_workflow/render_glb.py \
  --input /absolute/model.glb \
  --output-dir /absolute/new-preview-run \
  --godot /absolute/godot \
  --inspector "$CARGO_TARGET_DIR/debug/examples/asset_inspect" \
  --xvfb /absolute/Xvfb \
  --timeout-seconds 90
```

输出目录必须尚不存在；即使是空目录也拒绝覆盖。如果已有可用 `DISPLAY`，可以省略
`--xvfb`。私有 Xvfb 使用自动分配的 display，不连接用户桌面。本地解包的 Xvfb 如需
额外动态库，可显式传 `--xvfb-library-dir /absolute/library-directory`。
不使用 `--headless` 代替图形渲染；dummy renderer 不能通过验收。

## 结果与审阅

新运行目录保留输入快照、固定 Godot 项目副本、`preview.png`、`rendering.json`、
`report.json`、`preview.html` 和子进程日志。报告绑定输入、输出、工具和脚本的摘要。
检查针对本次读取的快照；这些本地文件仍可能在运行结束后被用户修改。

退出码为 0 且报告 `status=rendered_pending_review` 时，表示：

1. 输入快照通过现有有限 GLB 结构检查。
2. Godot 成功完成实际图形渲染，存在有效渲染记录。
3. PNG 经 Rust 解码，尺寸正确，并同时包含可见与全透明像素。

此时 `visual_quality_reviewed=false`。打开 `preview.html`，检查物体是否完整、方向与
轮廓是否符合意图、有无裁切或异常几何，再给出实际用途下的接受/返工意见。
浏览器打开页面或自动文件检查都不会把视觉审阅改成通过。配方不写资产库、游戏项目、
plan outcome 或任务完成统计。

出错、超时或收到 SIGINT/SIGTERM 时，命令非零退出，报告分别标为 `failed`、
`timed_out` 或 `cancelled`；保留日志和部分产物供排查，不发布成功状态。
已有输出路径被拒绝时，该路径完全不写入。
报告先暂存，再在最后一次取消/截止时间检查后原子发布；这个检查是本次调用的完成
时点，随后到达的信号不撤销已完成结果。最终写入前取消也会移除本次预览 HTML。

## 边界与复验

- 支持范围继承 `asset_inspect`：本地普通文件、64 MiB 输入上限、嵌入式静态 GLB
  的有限子集；动画、蒙皮、外部资源等不在范围内。
- 固定脚本仅复制静态 mesh 和变换，导入树不会加入活动场景。中性材质覆盖及固定
  相机不是通用 glTF 查看器；使用可信本地输入，不把它当成恶意文件隔离沙箱。
- 生命周期管理覆盖本次创建的进程组及普通后代。强制杀死控制脚本、系统故障，或
  子进程主动脱离会话不在此保证内。运行过程中检查总截止时间，进程组清理另有短暂
  宽限；它不是操作系统层面的硬实时资源隔离。
- 持久产物、缓存和日志位于新运行目录；Xvfb 自身会创建临时 X11 socket/锁，随本次
  显示服务退出回收。工作流有总时限；相同图片的重复性只对已测工具链成立。

```sh
python3 -B tests/test_asset_workflow.py -v
cargo test --locked -p ab-bridge --example asset_inspect

# 真实集成测试另需上述已构建工具；生成原创带索引和嵌套变换的样件。
AB_ASSET_GODOT=/absolute/godot \
AB_ASSET_INSPECTOR="$CARGO_TARGET_DIR/debug/examples/asset_inspect" \
AB_ASSET_XVFB=/absolute/Xvfb \
python3 -B tests/test_asset_workflow_integration.py -v
```

集成测试可选 `AB_ASSET_XVFB_LIBRARY_DIR` 和 `AB_ASSET_TEST_OUTPUT_ROOT`；会打印并
保留本次证据目录。未配置实际工具时测试跳过，不计为真实渲染通过。
