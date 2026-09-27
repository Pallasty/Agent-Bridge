# 五份项目记录

先运行 `init` 获得带 `schema_version: 1` 和同一 `project_id` 的五份 JSON。以下片段说明字段形状；路径、版本和哈希必须替换为实际值。脚本使用 Python 3.9+ 标准库。

| 文件 | 用途 | 维护时机 |
|---|---|---|
| `brief.json` | 创作目标、当前剧本、规格、预算与本次已知授权 | 要求或剧本变动时 |
| `bible.json` | 人物/地点/道具设定，当前参考资产 | 设定或资产审定时 |
| `shots.json` | 镜头意图、连续性、输入版本与选片指针 | 分镜、输入或选片变化时 |
| `generations.json` | 每次尝试、输出文件、评审、费用，剪辑工程与交付 | 生成、评审、剪辑时 |
| `handoff.json` | 简短交接、未解决问题、下一步与源记录哈希 | 每次收工前 |

其他字段可以按需要扩展。恢复工具检查镜头引用的剧本、资产、已选输出和当前待审候选，不检查所有历史素材、剪辑工程或交付文件。

## 1. Brief 与文件引用

`source_mode` 是 `fiction`、`documentary`、`simulation_replay` 之一。`phase` 可写 `brief`、`script`、`assets`、`storyboard`、`generation`、`editing`、`delivery`；它是人工更新的进度说明，工具不会自动判定制作阶段。

```json
{"revision": "v3", "path": "script/script-v3.md", "sha256": "<实际64位小写SHA256>"}
```

将上述结构写入 `brief.script`。所有文件引用采用项目内相对路径和实际文件的 SHA256；不允许绝对路径或指向项目外的软链接。用 `sha256sum <file>` 计算哈希。新建空项目允许暂无剧本文件；出现镜头后必须具备它。

`current_authorization` 仅记录来源与范围，不能替代当前用户授权。预算未知可保留 null，不能自动解释为无限额度。

## 2. Bible：稳定身份与可变状态

`entities` 存角色身份、外貌要点、关系以及地点/道具规则。按场次变化的服装、持有物、受伤或昼夜状态放到镜头连续性记录中，避免覆盖稳定身份。

`assets` 中每个逻辑 `id` 唯一，代表当前批准版本。例如：

```json
{
  "id": "hero_face", "version": "v2", "entity_id": "hero",
  "approved": true, "rights": "self_created; source record in rights/hero.md",
  "path": "assets/hero-face-v2.png", "sha256": "<实际SHA256>"
}
```

每种有独立用途的参考图使用不同 `id`，如 `hero_face`、`hero_costume_scene02`。保留旧文件与旧记录，可放在额外的 `asset_history` 数组或版本控制中；工具只读取当前 `assets`。`rights` 非空只是有记录，不是法律审查结论。换版后先列出受影响镜头，逐个重新核对，不能只批量改版本号使校验通过。

## 3. Shots：镜头输入与选片

```json
{
  "id": "sc02_sh03", "scene_id": "sc02", "script_revision": "v3",
  "intent": "角色发现门后的光，停步回望",
  "asset_versions": {"hero_face": "v2"},
  "continuity": {"start": "右手持灯，门关闭", "end": "门半开，灯仍在右手"},
  "camera": "中近景，缓慢推进", "duration_seconds": 5,
  "audio": "门轴声，无对白", "acceptance": ["脸部身份稳定", "持灯手无跳变"],
  "source_refs": [], "selected_generation_id": null
}
```

`fiction` 的虚构情节不需要事实来源；纪实/模拟复盘的每个事实性镜头须提供非空 `source_refs`，其中每项是 `{path, sha256}`。文件可以是事件记录、采访转录或授权素材说明。存在来源文件不证明画面忠于来源，仍需审片核对；未来可能发生的事件不能当作已经发生的事实。

选片必须显式填写 `selected_generation_id`。新尝试不会自动替换旧选择。

## 4. Generations：生成、评审与选择分开

```json
{
  "id": "sc02_sh03_g02", "shot_id": "sc02_sh03", "status": "generated",
  "script_revision": "v3", "asset_versions": {"hero_face": "v2"},
  "provider": "<实际服务>", "model": "<实际版本>",
  "prompt_file": "prompts/sc02-sh03-g02.txt", "parameters": {},
  "submitted_references": ["assets/hero-face-v2.png"],
  "output": {"path": "takes/sc02-sh03-g02.mp4", "sha256": "<实际SHA256>"},
  "review": {"decision": "unreviewed", "reviewer": null, "reason": ""},
  "cost": {"currency": null, "amount": null}, "latency_seconds": null
}
```

`status` 可用 `planned`、`failed`、`generated`；评审 decision 用 `unreviewed`、`accepted`、`rejected`。工具只允许 `generated` 且 `accepted`、归属正确镜头、输入版本一致、输出哈希吻合的条目作为有效选片。接受的条目也可以暂不选用。评审由实际观看、听音和任务验收得出，不能由文件存在推断。

保存真实提交请求和返回结果（去掉凭据），支持复现和费用核算；种子及其他模型参数只有平台实际支持时才记录为可复现条件。`edit.project_file`、`edit.timeline_file`、`deliveries` 保存剪辑/交付文件引用与验收结果；当前工具不检查这些扩展字段。

## 5. Handoff 与恢复结果

收工时先核对并更新 `summary`、`next_actions`、`unresolved`、`reviewed_by`，再运行 `checkpoint`。它只把其余四份 JSON 的哈希写进 `document_sha256`，不会改写或验证摘要语义。因此不能用它给未审阅的旧摘要重新盖章。

`recover` 输出：

- `planning`：没有镜头，继续填写目标/剧本；不表示项目已完成。
- `record_consistent`：被检查的镜头记录和引用文件一致；不表示全片通过验收。
- `needs_review` / `invalid`：当前记录有错，返回码 2；前者列出逐镜头问题，后者说明无法读取或识别记录。
- `selected`：有效的明确选片。`next_actions` 是逐镜头建议：`plan_generation`、`review_candidates`、`reconcile_records`，不执行操作，也不推断完整剪辑计划。
- `handoff_matches_files`：仅说明四份记录的哈希与交接保存值一致。哈希吻合且本轮无镜头错误时，才回传交接摘要、人工下一步与未决事项。发生错误或不匹配时重新核对本地记录。

空项目或无记录错误时返回码为 0；它不是交付完成、授权充分或画质达标信号。恢复在同一项目的稳定快照上运行，避免其他进程同时修改记录。它不恢复丢失文件、不自动迁移旧版本，也不上传任何素材。
