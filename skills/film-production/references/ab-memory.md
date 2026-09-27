# AB 调用与记忆约定

## 检索入口

优先使用已安装的 `$film-production`。AB 中的短入口键为 `film_production_workflow_v1`，技能索引包含 `film-production`。若入口未进入当前上下文，可用 `memory_search(query="film-production", mode="fts")` 或 `skills_recommend(query="影视制作 分镜 镜头选片")` 寻找，再读取记录指定的 SKILL.md。

任务恢复时，给 `session_bootstrap` 传当前作品目录 `cwd` 和具体任务描述。检索到旧交接后，用本地项目文件重新验证。工具不可用时，直接读取本技能和项目档案即可。

## 只保存三类高价值记忆

| 类型 | 建议 key / scope | 内容 |
|---|---|---|
| 技能入口 | `film_production_workflow_v1` / global | 触发条件、安装路径、源码仓库/commit、验证范围；一条短记录即可 |
| 作品交接 | `film_project_<id>_handoff` / `project:<绝对项目目录>` | 所处阶段、剧本/素材版本、已选镜头、具体问题、下一步、handoff 文件路径与哈希 |
| 经验案例 | `film_lesson_<model>_<case>` / 对应项目，跨项目复用有证据后再扩大 | 模型版本、输入条件、改动与结果证据、适用限制、尚未排除的解释 |

AB 的 scope 管理检索范围，不构成访问权限。全局入口尽量短，不将项目私有素材、全量提示词、密钥或生成历史写进全局记忆。影片二进制与完整记录留在项目文件中。

`memory_save` 可采用现有 `continuity` 字段：入口使用 `continuity_role=procedure`、`actionability=plan_influence`、`freshness_policy=version_bound`；项目交接使用 `continuity_role=state`、`freshness_policy=project_phase_bound`。confidence 描述该条记录的证据：技能文件存在可被核实，不代表制作收益已被证明。研究建议不要标为经过任务验证的经验。

## 恢复摘要的写法

示例结构（请以实际文件填值）：

> 作品 <id>，剪辑前选片阶段；brief 中剧本 v3；01/02 已选片，03 因道具跳变待重做；详细依据见项目 handoff.json 及源文件哈希。下一步核对 03 当前输入后修正，当前支付/发布权限以本次用户授权为准。

工作区绝对路径只适用于本机。跨机器恢复先定位相同 `project_id` 的项目和固定源码 commit，再验证文件哈希；缺失的媒体文件标为缺失，不能仅凭记忆恢复“已交付”。

## 验证范围

检查索引命中、bootstrap 是否实际包含入口、只用项目文件能否恢复版本与问题。重复检索会写 AB 的访问/遥测记录，命中次数不能用作任务收益证据。真实跨会话无重述恢复、画质、制作费用需在未来实际任务中观察。
