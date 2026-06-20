# IDE Perception Bridge — Facility Completion (Cursor-host findings + A/B/D)

> 2026-06-19 · author `aio2:agent-bridge:ide-bridge-completion` · board design (ref thread #112 tool-surface governance)
> Scope: **完善既有设施,不新增工具面**。契合 #112「能力建设峰已过,边际成本是工具面膨胀」立场。

## 0. 缘起

AiOT owner 问「Codex/Claude Code 插件在 Cursor vs VSCode 的环境支持差距」。代码核验后的结论改写了问题:

**铁律:harness 的环境支持(hooks / 生命周期 / MCP 工具集)来自 harness 自身,不来自宿主编辑器。**

- 实测本机 harness 自报 "VSCode native extension",但宿主其实是 **Cursor**(`CLAUDE_CODE_EXECPATH=~/.cursor/extensions/anthropic.claude-code-2.1.183.../claude`、`CURSOR_SPAWN_CHAIN=anthropic.claude-code`、`CURSOR_LAYOUT=unifiedAgent`);自报 VSCode 只因 Cursor fork 了 VSCode 扩展 API(`CLAUDE_CODE_ENTRYPOINT=claude-vscode`)。
- 因此 **Claude Code 在 Cursor / VSCode / 纯 CLI 几乎无能力差**。真正的差距轴是 **harness × 启动方式**:Claude Code 把自动 lifecycle 带到任何地方;**Codex 只有 Desktop 自带 hooks,进 codex-ide / codex-cli 都跳过 lifecycle**(`setup.rs:196/204`,toolset 降 codex-essential)。

## 1. 当前设施状态(实测 2026-06-19,verify-before-implement)

| 设施 | 状态 | 证据 |
|---|---|---|
| Claude Code 生命周期 hooks | ✅ 全活 | `hook_status`: beforeSubmitPrompt(ab-memory-hook)/preCompact/stop 均 exit 0 |
| `ide_snapshot` 读侧 | ✅ 活 | 返回 Cursor 1.105.1 + 64 条 rustc 诊断 |
| `ide_command` 写侧 | ✅ 活 | `write_snapshot` round-trip 完成 ~80ms(扩展确在 500ms 轮询 `ide-commands.jsonl` 回写 `ide-responses.jsonl`) |
| 快照扩展 | ✅ 已装进 Cursor | `agent-bridge.agent-bridge-ide-snapshot-0.1.0` |

**结论:重型基建已建且 live,无需重搭。** 待补的是三处窄缺口。

## 2. 缺口 + 修法(含 verify 纠正)

### A. 快照陈旧(freshness)
- **现象**:实测 `stale:true`,`age_ms≈775000`(13min)。
- **根因(verified)**:`extension.js:activate` 只在编辑器事件 + 500ms 命令轮询时写快照,**无周期刷新**。Cursor `unifiedAgent` 布局下你在跟 agent 对话,编辑器事件不触发 → 快照不更新。
- **修法**:`activate()` 增 `setInterval(writeNow, ~10s)` 周期刷新(可 gate「自上次写后有变更才写」省 IO)。bounds staleness ≤10s,零 hook 改动。

### B. `open_files` / `active_file` 抓不到
- **现象**:实测 `open_files:[]`、`active_file:null`(仅诊断 64 条非空)。
- **verify 纠正**:初判「writer 只读 activeTextEditor」**错**。`openFiles()`(extension.js:180-193)已枚举 `vscode.workspace.textDocuments`。空的真因 = **陈旧 + agent 面板聚焦时无已加载文档**(textDocuments ≠ 打开的标签页)。
- **修法**:切到 `vscode.window.tabGroups.all[].tabs[]` 取真实标签列表(并与 textDocuments 取并集补 dirty/language 信息)。与 A 合并为**同一扩展补丁 + 一次 vsix 重打**。

### D. `detect_frontend` 检测碰撞(robustness)
- **现象**:`mcp_tools.rs:26590-26651` 把 VSCode/Cursor env(`VSCODE_IPC_HOOK_CLI`/`VSCODE_GIT_IPC_HANDLE`/`CURSOR_TRACE_ID`)检查排在 harness 标记**之前**。谁泄漏这仨给 MCP 子进程,无论实际 harness 是谁都被判 `cursor`(丢 hooks + 降级 profile)。
- **本机为何幸免(verified)**:Cursor 的 Claude Code 扩展只设不带 `_CLI` 的 `VSCODE_IPC_HOOK`,不泄漏那三个 → 正确落 `claude-code`(实测 `capabilities.frontend=claude-code`)。但这是**侥幸,非保证**。
- **修法**:
  - **D1(即时,零代码)**:MCP 注册 env 显式 `AGENT_BRIDGE_FRONTEND=claude-code`,压掉启发式(`mcp_tools.rs:26591` 已支持 override)。注入点 = `~/.claude.json:1350-1357`(User-scope,现 env 已有 `AGENT_BRIDGE_TOOL_PROFILE=all`)。
  - **D2(根治,一个 PR)**:reorder detect_frontend,把 harness 标记(`CLAUDE_CODE_ENTRYPOINT`/`AGENT_BRIDGE_CLIENT`)优先级排到编辑器 env 之前。⚠️ 触 `mcp_tools.rs`(大文件,注意并发编辑约定)。

### (E/F 规划级,本轮不做)
- **E. `apply_workspace_edit`**:命令桥目前 open_file/reveal_range/run_task/write_snapshot,不能经 IDE 应用编辑(带审阅/撤销)。Phase 3 roadmap(`docs/IDE-SNAPSHOT-BRIDGE.md:153-159`)。仅当需要 IDE 内编辑语义才建。
- **F. Codex lifecycle 对等**:Codex 进 IDE/CLI 丢自动 hooks;若本机要用 Codex,需手动 `session_lifecycle_step` SOP 或在 ide 模式接 `~/.codex/hooks.json`。当前全程 Claude Code,暂缓。

## 3. 优先级 / 并行

两条独立 lane(不同文件,可并行):

- **Lane 1 — 扩展(A+B 合并)**:patch `examples/vscode-ide-snapshot/extension.js`(周期刷新 + tabGroups)→ `npx @vscode/vsce package` 重打 vsix → `cursor --install-extension` 重装。自包含。
- **Lane 2 — 检测健壮(D)**:D1 改 `~/.claude.json` env(即时);D2 reorder PR(可后置)。

**建议顺序**:D1(零成本,先消脆弱)→ Lane 1(A+B 一次重打)→ D2/E/F 按需。

## 4. vsix 重打 / 重装路径(verified 可用)

```bash
cd /Data/CascadeProjects/agent-bridge/examples/vscode-ide-snapshot
npx @vscode/vsce package                 # → agent-bridge-ide-snapshot-0.1.x.vsix
cursor --install-extension ./agent-bridge-ide-snapshot-0.1.x.vsix
# 或 Cursor 命令面板: Extensions: Install from VSIX
```

node/npx 在 PATH;package.json 无 build 脚本(纯 JS,vsce 直接打包)。

## 5. Verify-before-implement 记录(本轮已核验)

- ✅ hooks live(`hook_status`)、ide_snapshot 读 live、ide_command 写 round-trip live
- ✅ extension.js 全文读毕 → 纠正 B 归因、发现 A 更优的周期刷新实现
- ✅ D 注入点 = `~/.claude.json:1350` User-scope MCP env
- ✅ vsix 重打路径(npx vsce)可用
- ⏳ 未做:A/B 代码改动 + D1 env 改动(待 owner 授权实施)
