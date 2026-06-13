# Agent-Bridge hooks — env-gate reference

集中文档化已部署 hook 及其环境变量门控。背景:ECC 调研的 delta④(b)「hook profile」——
经核实 agent-bridge **已有丰富的 per-hook env 门控**(只是没集中文档),所以真缺口是
*discoverability* 而非 profile 层。本文是那个缺口的补丁。

## Hooks(部署到 `~/.local/bin/`,注册在 `~/.claude/settings.json`)

| Hook | CC 事件 | 源 | 职责 |
|---|---|---|---|
| `ab-memory-hook` | UserPromptSubmit | `crates/bridge/src/hooks/ab-memory-hook.sh`(setup.rs `include_str!`)| 注入记忆上下文 |
| `ab-seed-familiarity-hook` | UserPromptSubmit | ⚠️ 已部署,**源不在 setup.rs/repo**(孤儿,pre-existing)| substrate familiarity 探针 |
| `ab-precompact-hook` | PreCompact | `crates/bridge/src/hooks/ab-precompact-hook.sh` | compact 前策展 |
| `ab-session-end-hook` | Stop | `crates/bridge/src/hooks/ab-session-end-hook.sh` | session-end finalize |
| `ab-instinct-observer-hook` | PostToolUse + UserPromptSubmit | `crates/bridge/src/hooks/ab-instinct-observer-hook.py` | delta① **探针**:append-only 观测日志 |

**安装**:`setup.rs::install_claude_code` 编译期嵌入并写 memory/precompact/session-end 三个 +
merge settings.json 的 `UserPromptSubmit/Stop/PreCompact`。
**observer 状态**:源已进 repo(防孤儿)。Claude Code 仍是手动注册
(PostToolUse + UserPromptSubmit 第 3 hook);Codex desktop 已随 `setup --frontend codex`
写入 `~/.codex/hooks.json` 的 `UserPromptSubmit` + `PostToolUse`。delta① 已收口为
`NO_SIGNAL` null-path:observer 保留 observability-only,不建 miner。`err=true` 只来自
显式 error/status/exit_code/interrupted 信号,**stderr-only 不算失败**。

## Env 门控

**Toggle(开关)**

| Env | Hook | 默认 | 效果 |
|---|---|---|---|
| `AB_INSTINCT_OBSERVER` | observer | `1`(开)| `=0` → no-op,关闭观测 |
| `AB_SEED_FAMILIARITY_OFF` | seed-familiarity | unset(开)| `=1` → `exit 0`,关闭 |
| `AB_PET_STATE_DISABLE` | memory, session-end | unset(开)| `=1` → 跳过 pet state |
| `AB_SESSION_END_CURATE` | session-end | unset(**关**)| `=1` → 跑 end-of-session 策展(+ precompact)|

**Config(配置值)**

| Env | Hook | 默认 | 含义 |
|---|---|---|---|
| `AB_MEMORY_COOLDOWN_TURNS` | memory | `8`(P-A1 locked)| 记忆注入间隔轮数;`999999` ≈ 还原 one-shot |
| `AB_PET_AUTO_TTS` | session-end | unset(关)| TTS spec |
| `AB_PET_AUTO_TTS_CHANNEL` | session-end | `tts` | TTS 通道 |
| `AB_PET_AUTO_TTS_COOLDOWN_SECONDS` | session-end | `1800` | TTS 冷却秒 |
| `AB_STATE_DIR` | 多数 | 默认 cache dir | state 目录覆盖 |

**Internal(内部协调,一般别手设)**

| Env | 说明 |
|---|---|
| `AB_MEMORY_CURATOR` | precompact 设 `=1`,memory-hook 见之即 `exit 0`(re-entry guard)|
| `AB_HOOK_LOG` / `AB_HOOK_PAYLOAD` / `AB_HOOK_START` / `AB_HOOK_EVENT` / `AB_HOOK_OUTPUT_BYTES` | hook 自我日志 plumbing |

## delta④(b) profile 判断

ECC 的 `ECC_HOOK_PROFILE=minimal|standard|strict` 是上述 toggle 的**便利分组**。agent-bridge
粒度门控已全有 → profile 仅是便利层,且要动多个 live 脚本。**定级:低边际价值,DEFER(task #54)**,
除非出现真实"一键切档"需求。镜像对象若要做:`setup.rs::SetupToolset::{Essential,Lean}` 的 enum 模式。

## 探针清理(observer)

```sh
# 关闭：AB_INSTINCT_OBSERVER=0（或从 settings.json 摘掉两处 hook 条目）
# 默认路径：有 /Data 时用 /Data/agent-bridge/instinct-probe/observations.jsonl
# 覆盖路径：AB_INSTINCT_OBSERVER_LOG=/path/to/observations.jsonl
# 清数据：rm -f "${AB_INSTINCT_OBSERVER_LOG:-/Data/agent-bridge/instinct-probe/observations.jsonl}"
# 跑只读审计快照：python3 scripts/instinct_density_audit.py
# JSON 输出：python3 scripts/instinct_density_audit.py --json
# Phase 1 候选预览：agent-bridge instinct candidates --limit 20 --json
# Phase 1 人工审核包预览：agent-bridge instinct review-packet --limit 20 --json
# 显式写出脱敏 JSON/Markdown 审核材料：agent-bridge instinct review-packet --limit 20 --write
```

`agent-bridge doctor` and the MCP `capabilities` tool also expose the observer
as read-only operational state. Missing or empty logs are not warnings: the
probe is optional, and `NO_SIGNAL` / `INSUFFICIENT_SESSIONS` should block miner
work rather than block normal Agent-Bridge startup.

Phase 1 candidate preview is also read-only: it reports redacted correction and
clean error-resolution candidates for human review, but does not write memories,
persist a review queue, or include raw prompt/tool input/output bodies.

`agent-bridge instinct review-packet` turns the same redacted candidates into a
human-review packet. It is a dry-run preview unless `--write` is passed; even
when writing packet files, it only creates private local JSON/Markdown review
materials and still does not write memory, persist an approval queue, auto-apply
anything, or include raw prompt/tool payload bodies. The default review
directory is `/Data/agent-bridge/instinct-review` when `/Data` is available, or
`~/.cache/agent-bridge/instinct-review` otherwise; `AB_INSTINCT_REVIEW_DIR` can
override it.

Security posture: the observer sidecar is local-only and private by default.
The hook honors `AB_INSTINCT_OBSERVER_LOG`; otherwise it prefers
`/Data/agent-bridge/instinct-probe/observations.jsonl` when `/Data` is writable,
falling back to `~/.cache/agent-bridge/instinct-probe/observations.jsonl`. The
hook creates the sidecar directory as `0700` and `observations.jsonl` as `0600`,
and `doctor` warns if an older file keeps wider permissions. The sidecar may
contain prompt/tool summaries, so do not make it group/world-readable.
