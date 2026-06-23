# Trigger Recall Pre-Policy Hold Post-Install MCP Stale Check

Date: 2026-06-23

Scope: post-install verification for the already-recorded local
`agent-bridge.real` rollout of the Trigger Recall pre-policy hold simulation
surface.

This report does not deploy, change `memory_search`, enable production
`enforce_hold`, mutate memory data, or expose any non-Niche trigger recall
surface. It records the current post-reconnect blocker before runtime smoke.

## Verdict

`INSTALLED-BINARY-OK / MCP-SURFACE-STALE / RUNTIME-SMOKE-NOT-YET-AUTHORIZED`

The installed binary matches the rollout evidence from
`55b5618 docs(memory): record pre-policy hold install rollout`, but the active
Codex/Cursor MCP server processes still map the old deleted `.real` inode. The
new Niche tool surface should therefore be treated as installed but not yet
available to this MCP client session.

## Evidence

Repository state after fetch:

```text
HEAD = origin/master = 55b5618 docs(memory): record pre-policy hold install rollout
worktree = clean
```

Installed binary:

```text
/home/pallasting/.local/bin/agent-bridge.real
size   = 67113016 bytes
sha256 = fd7800aedef48732dd044a06b52916893cc246cf2b7f784d7d4f35f5e3a40b4a
mtime  = 2026-06-23 07:14:37 -0700
```

The size and hash match the rollout record in
`2026-06-23-trigger-recall-pre-policy-hold-install-rollout.md`.

Doctor result:

```text
/home/pallasting/.local/bin/agent-bridge.real doctor --json
ok=true
fails=0
warns=1
```

The single warning is the relevant runtime blocker:

```text
2 MCP server(s): 0 current .real, 2 stale .real
stale pids: 671351, 671929
exe=/home/pallasting/.local/bin/agent-bridge.real (deleted)
```

The current MCP capabilities report still shows the compact/essential tool
surface rather than the new trigger-recall Niche surface:

```text
client=codex
tool_profile_env=essential
exposed_tool_count=94
toolset=codex-essential
```

Tool discovery for the exact `trigger_recall_*` surface did not expose
`trigger_recall_opt_in_pre_policy_hold_simulation` in this session, consistent
with the stale deleted-inode diagnosis.

## Current Safe State

- Mainline docs and code are synced through `55b5618`.
- Local installed binary is the recorded rollout binary.
- Runtime lifecycle health is not failing.
- Current MCP clients should not be assumed to have the new tool manifest.
- No runtime smoke was executed from this stale MCP session.

## Required Gate Before Runtime Smoke

Before any runtime smoke claim, produce a fresh check where:

- `doctor --json` reports at least one current `.real` MCP server for this
  install path;
- stale deleted `.real` rows are either absent or clearly unrelated to the
  active client under test;
- the active tool surface exposes
  `trigger_recall_opt_in_pre_policy_hold_simulation`;
- the tool remains `Tier::Niche`;
- `AGENT_BRIDGE_TOOL_PROFILE=all` is explicit if the compact profile still hides
  Niche tools;
- `AB_TRIGGER_RECALL_PRE_POLICY_HOLD_OPT_IN=1` is set only for the smoke process;
- `AB_TRIGGER_RECALL_PRE_POLICY_HOLD_DISABLE` is unset for the smoke process;
- the call uses an explicit approval packet with per-call opt-in;
- default `memory_search` is not called as the behavior under test;
- no memory writes, graph writes, reindex, semantic retrieval, or production
  `enforce_hold` are enabled.

## Next Step

Refresh the active MCP client processes so they respawn from the current wrapper
and current `.real` binary, then rerun:

```text
/home/pallasting/.local/bin/agent-bridge.real doctor --json
```

If the stale-MCP warning clears and the Niche trigger tool appears in the active
tool list, the next allowed slice is a read-only runtime smoke packet. If it
does not clear, stay in install/runtime diagnosis rather than continuing recall
logic changes.
