# 小说多角色朗读（novel_tts_embodied）v1.1（AB 形态落地）

目标：把“中文小说多角色朗读（男女声 + 情绪）”变成可直接进入 AB 体系的能力形态。优先交付“可复盘、可回放、可退化”，模型能力先走可替换接口。

## 形态定义（v1.1）

- `pipeline.py`：纯逻辑内核（分段、角色/情绪判断、音色映射、输出组装），无副作用、可直接单测
- `ab_runner.py`：AB 任务入口（支持 `task-json`、模型标注注入、回放计划产物）
- `run_v0.py`：保留 v0.1 兼容入口，便于回归对比

## 输出约定

输入：TXT 文本（文件或 AB 任务中的 `input`）
输出：

- `segments.jsonl`：每段 `segment`（角色、情绪、音色计划、fallback）
- `manifest.json`：任务级摘要（字符数、失败数、统计）
- `embodiment_plan.jsonl`：每段可执行 playback 计划（`present_voice`）
- `needs_review.jsonl`：`status=needs_review` 的段落列表（只在需要时产出）
- `present_voice_calls.jsonl`：`--emit-voice` 时产出，AB action 层可直接下发的调用清单
- `present_voice_results.jsonl`：`--emit-voice` 时产出，执行器返回结果（如未配置执行器为 `skipped/queued`）
- `result.json`：AB 任务结果 envelope（路径、状态、审阅段）。包含 `present_voice_summary` 等扩展聚合字段

## 退化策略（继承 v0.1）

1. 角色/情绪模型置信度不足时，回退到更稳妥参数，并打上 `fallbacks`。
2. 不能识别角色时标 `needs_review`，但不阻断整书流程。
3. 分段失败/空段也只影响当前段，任务仍可继续；`manifest.summary.failed_segments` 可追溯。

该策略与 AB 的复验/人工审核天然兼容：失败段保留文本与计划，支持单段重跑。

## 运行方式

### AB 形态（推荐）

```bash
python3 ab_runner.py \
  --emit-voice \
  --task-json task_payload.json \
  --output-dir out/run-20260725
```
`--emit-voice` 当前行为：

- 默认生成 `present_voice_calls.jsonl`。
- 默认不直接执行（除非设置 `NOVEL_PRESENT_VOICE_EXECUTOR`）。
- 若设置了 `NOVEL_PRESENT_VOICE_EXECUTOR`，会将每条 `present_voice` 参数喂给该执行器，产出 `present_voice_results.jsonl`，并记录回执字段：
- `status`（如 `ok/failed/skipped/queued`）
- `status_code`（执行器返回码）
- `raw_status`（执行器明确信号）
- `verify_status`（校验状态）
- `executed`（是否实际触发执行器；dry-run 为 false）
- `started_at_ms` / `finished_at_ms` / `latency_ms`
- `output_file_exists` / `output_file_size` / `output_file_sha256`

  回执解析优先级：

  1. JSON 回执中的 `status` / `status_code` / `verify_status`
  2. 文本回执中的 `status=...` / `status_code=...` / `verify=...`
  3. 执行返回码

  冲突规则：若 `status` 与 `verify_status` 均为显式信号且语义冲突（如 `status=failed` + `verify_status=verified`），按失败处理，避免误放行。

可选的 plan 控制参数：

- `--plan-priority`：`low|normal|high|critical`，默认 `normal`
- `--plan-retry-limit`：重试次数上限，默认 `2`
- `--plan-cooldown-ms`：重试间隔下限，默认 `100`
- `--plan-backoff-ms`：退避基线，默认 `400`

### 标准执行器接线（推荐）

`novel_tts_embodied` 的执行器约定是：AB 运行时对每条 `present_voice` 调用以 JSON 写入 stdin，执行器返回 JSON（标准字段可被 `ab_runner` 自动解析）：

- 输入（执行器接收）：
  - `backend`：如 `ab-tts`
  - `text`：段落文本
  - `voice`：音色 key
  - `speed`、`pause_ms`、`gain_db`、`pitch_shift`
  - `output_file`：期望生成路径
  - `segment_hash`、`estimated_duration_sec`

- 标准回执（执行器输出）：
  - `status_code`：整数返回码
  - `status`：`ok/failed/skipped/queued`
  - `verify_status`：`verified/mismatch/invalid/error`
  - `output_file`：实际输出文件路径（可与输入不同）
  - `message`：可选文本

仓库内已提供最小可运行 adapter，用于先把 AB 能力打通：

```bash
export NOVEL_PRESENT_VOICE_EXECUTOR="python3 $(pwd)/adapters/present_voice_cli.py"
python3 ab_runner.py \
  --emit-voice \
  --input samples/demo_novel.txt \
  --output-dir out/voice_cli_smoke
```

这个 adapter 在 `backend=ab-tts` 下会产出一个有效的占位 `wav`，用于验证回执链路和文件归档；你可以改造它接到真实 TTS 后端：

```bash
export NOVEL_PRESENT_VOICE_BACKEND_CMD="tts-cli --backend {backend} --voice {voice} --speed {speed} --input {text} --out {output_file}"
```

并保持 ab_runner 输入/输出结构不变即可替换验证阶段实现。

### Rust-native Chinese multi-speaker backend (Sherpa-ONNX)

`ab-tts` includes an opt-in `sherpa` feature for the offline
`vits-icefall-zh-aishell3` model. Its Chinese text frontend, VITS ONNX model and
audio generation all execute through the official Rust API; no Python inference
server is involved. Build the dedicated CLI outside the default AB build:

```bash
CARGO_TARGET_DIR=/Data/ab-sherpa-target \
cargo build -p ab-tts --features sherpa --bin ab-sherpa-tts-synth
```

Download and unpack the official model under a non-repository directory, then
provide an *auditioned* voice-to-speaker mapping. The AISHELL-3 `sid` values have
no gender metadata, so `male_standard`, `female_standard` and `narrator_calm`
must only be assigned after listening review:

```bash
export AB_TTS_SHERPA_MODEL_DIR=/Data/Models/sherpa-onnx/vits-icefall-zh-aishell3
export AB_TTS_SHERPA_VOICE_MAP='male_standard=<sid>,female_standard=<sid>,narrator_calm=<sid>'
export NOVEL_PRESENT_VOICE_EXECUTOR="python3 $(pwd)/adapters/present_voice_cli.py"
export NOVEL_PRESENT_VOICE_BACKEND_CMD='/Data/ab-sherpa-target/debug/ab-sherpa-tts-synth --text {text} --voice {voice} --speed {speed} --out {output_file}'
```

The adapter shell-quotes every template value and requires the command to leave a non-trivial WAV at `output_file`.
An exit code of zero without a real audio file is a `failed/mismatch` receipt;
it is never replaced with a placeholder WAV.

### 声音试听与映射

AISHELL3 的 speaker ID 不提供性别元数据。可用下列命令生成不带性别预设的试听包；其 `audition_manifest.json` 会记录每个候选的 ID、WAV 哈希及待审听状态：

```bash
python3 tools/prepare_sherpa_audition.py \
  --synthesizer /Data/ab-sherpa-release/release/ab-sherpa-tts-synth \
  --model-dir /Data/Models/sherpa-onnx/vits-icefall-zh-aishell3 \
  --output-dir /Data/novel_sherpa_audition
```

审听后才可将候选 ID 映射到 `narrator_calm`、`male_standard` 或 `female_standard`；不能由编号推断性别。

`task_payload.json` 示例：

```json
{
  "task_id": "novel-tts-demo-001",
  "input": {
    "path": "samples/demo_novel.txt"
  },
  "config": {
    "tts_backend": "kokoro"
  }
}
```

如果已有子代理/模型输出（speaker + emotion），可直接注入：

```json
{
  "task_id": "novel-tts-demo-002",
  "input": { "path": "samples/demo_novel.txt" },
  "annotations": [
    {
      "index": 0,
      "speaker": { "id": "spk_周芷", "name": "周芷", "gender": "female", "confidence": 0.93 },
      "emotion": { "label": "tense", "confidence": 0.81, "intensity": 2 }
    }
  ]
}
```

也可传索引映射对象（键为段号）：

```json
{
  "1": {
    "speaker": { "id": "spk_周芷", "name": "周芷", "gender": "female", "confidence": 0.93 },
    "emotion": { "label": "tense", "confidence": 0.81, "intensity": 2 }
  },
  "3": {
    "speaker": { "id": "spk_小雨", "name": "小雨", "gender": "male", "confidence": 0.91 },
    "emotion": { "label": "calm", "intensity": 1, "confidence": 0.79 }
  }
}
```

注入契约见 `schema/annotations.schema.json`。建议字段含义如下：

- `speaker.id`：`speaker.id`（非空字符串）
- `speaker.name`：角色显示名
- `speaker.gender`：`male|female|narrator|unknown`
- `speaker.confidence`：`0~1`，非法/缺省回退为 `0.6`
- `emotion.label`：`neutral|calm|happy|sad|angry|tense`
- `emotion.intensity`：`0~2`，非法回退为 `1`
- `emotion.confidence`：`0~1`，非法/缺省回退为 `0.62`
- `index`：段号（从 `0` 开始）；不合法索引会写入 `annotation:index_invalid`

可追溯字段：

- `segment.debug.annotation_issues`（段级）
- `manifest.annotation_issues`（任务级，含 `summary`、`rows`、`all`）
- `result.json` 的 `annotation_issues_summary`

规则：

- `annotation` 写入非法时不阻断主流程；
- 受影响段会补充 `fallbacks` 上的 `annotation:...` 记录；
- 低置信度会补 `..._confidence_below_threshold`。

也可通过 CLI 文件注入：

```bash
python3 ab_runner.py \
  --annotation-json annotations.json \
  --input samples/demo_novel.txt \
  --output-dir out/run-20260725
```

### v0.1 兼容回归

```bash
python3 run_v0.py \
  --input samples/demo_novel.txt \
  --output-dir out/run-20260725 \
  --voice-male "male_standard" \
  --voice-female "female_standard" \
  --voice-narrator "narrator_calm"
```

## 目录

- `schema/segment.schema.json`
- `schema/manifest.schema.json`
- `schema/embodiment_plan.schema.json`
- `schema/annotations.schema.json`
- `adapters/present_voice_cli.py`
- `pipeline.py`
- `ab_runner.py`
- `validate_outputs.py`
- `run_v0.py`
- `DECISION_LOG.md`（决策沉淀/回滚点）
- `samples/demo_novel.txt`
- `fixtures/segment_sample.jsonl`
- `fixtures/manifest_sample.json`

## 下一步

1. 运行一键校验（schema + 产物完整性）：

```bash
python3 validate_outputs.py --output-dir out/run-20260725 --require-plan
```

2. 固定 AB 子代理输出 Schema（speaker/emotion JSON）并接线到具体工具（例如 `agent-bridge` 内部调用器）
3. 将 `NOVEL_PRESENT_VOICE_EXECUTOR` 指向真实 TTS 适配器命令，接管 `adapters/present_voice_cli.py` 中 `NOVEL_PRESENT_VOICE_BACKEND_CMD`

4. 回归脚本（建议每次改动后执行）：

```bash
python3 regression_present_voice.py --workdir /tmp/novel_tts_regression
```

脚本覆盖 3 类执行器行为：

- 未配置执行器（走 skipped/pending）
- JSON 回执执行器
- 非 JSON 回执执行器（`status=ok status_code=0 ...`）
- 支持重试的执行器（首次失败，随后成功）
