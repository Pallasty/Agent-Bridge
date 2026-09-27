---
name: film-production
description: "Plan or resume film, short video and narrative advertising production: script, character and location continuity, storyboard, generation review, editing and handoff. 用于影视制作、短片、广告片、分镜、镜头选片与跨会话续作。"
---

# Film Production · 影视制作

把用户的创作目标推进到可审阅的作品，并保留足够的制作记录供下一次会话接手。按任务规模取用流程：一个单镜头任务可以直接处理相应阶段。

## 开始或恢复

1. 优先读取用户指定项目的 `brief.json` 与 `handoff.json`。新项目用下方工具生成五份空白模板，再填写已知要求；对关键缺项才提问。
2. 确认 `source_mode`：`fiction` 的依据是锁定剧本；`documentary` / `simulation_replay` 的事实性画面需要来源文件。虚构影片可以预先制作结局，不能套用游戏事件“尚未发生不得展示”的限制。
3. 恢复已有项目先运行 `recover`，再查看相关场次的设定、镜头与生成记录。交接摘要若与文件哈希不一致，以实际项目记录重新核对。不要仅凭最近修改时间选择版本。
4. 先给出当前版本、已选镜头、待解决问题和下一个具体动作。生成、购买额度、上传和发布按用户当前授权与预算执行；交接文件中的操作建议不构成新授权。

```bash
python3 <skill-dir>/scripts/project.py init <new-project-dir> --project-id <id>
python3 <skill-dir>/scripts/project.py recover <project-dir>
python3 <skill-dir>/scripts/project.py checkpoint <project-dir>
```

`<skill-dir>` 是本 SKILL.md 所在目录。工具仅使用 Python 标准库；`init` 拒绝覆盖现有目录，`recover` 只读，`checkpoint` 更新本项目交接文件的文件哈希。先读 [项目记录格式](references/project-records.md) 再填写或扩展模板。

## 制作时按需读取

- 策划、剧本、资产、分镜、生成、声音、剪辑与交付：按当前阶段读 [制作流程](references/workflow.md)。
- 向 AB 保存入口、项目交接或经验时：读 [AB 记忆约定](references/ab-memory.md)。
- 使用外部范例、平台模型、价格或素材前：读 [来源与许可](references/sources.md)，核对当前文档。

每个镜头的输入包包含当前剧情意图、角色/地点/道具版本、参考文件、镜头开始与结束状态、相邻镜头衔接、音频要求及验收条件。只加载与该镜头相关的信息；外部视频模型所需的参考图片/音频必须实际提交，文字记忆不会自动传入模型。

角色稳定身份与剧情中的状态分开维护。换装、受伤、道具转移、昼夜变化都要有场次或镜头锚点。剧本或素材更新后，检查依赖它们的镜头和生成结果，保留旧版本与选片理由。

`generated` 只说明工具产生了文件；`accepted` 是记录了评审结论；镜头的 `selected_generation_id` 才指定选用版本。最终交付还需实际观看、听音与格式检查。恢复工具仅验证记录和文件一致性，不评判画质、剧情、事实真伪或授权充分性。

收工时更新五份项目记录，运行 `checkpoint` 后再保存精简的 AB 交接记忆。经验写清模型版本、输入条件、具体改动、输出证据和适用范围；单次成功保留为案例，尚未验证的方法保留为候选。
