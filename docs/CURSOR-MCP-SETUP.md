# Cursor — Agent-Bridge MCP setup

Cursor registers MCP servers in `~/.cursor/mcp.json` (same JSON shape as Gemini CLI).

## Install

```bash
agent-bridge setup --frontend cursor
# or with local CLI bundle:
agent-bridge setup --frontend local-cli
```

This merges:

```json
{
  "mcpServers": {
    "agent-bridge": {
      "command": "/home/you/.local/bin/agent-bridge",
      "args": ["mcp"],
      "env": {
        "AGENT_BRIDGE_CLIENT": "cursor",
        "AGENT_BRIDGE_TOOLSET": "claude-standard",
        "AGENT_BRIDGE_TOOL_PROFILE": "standard"
      }
    }
  }
}
```

Then **Developer: Reload Window** in Cursor so `tools/list` refreshes (~98 tools as of 2026-05-25).

## Verify

```bash
agent-bridge doctor
```

Call MCP `mcp_config_audit` from a Cursor session, or smoke-test stdio:

```bash
AGENT_BRIDGE_CLIENT=cursor AGENT_BRIDGE_TOOLSET=claude-standard \
  agent-bridge mcp   # then tools/list
```

## Session lifecycle (no Cursor hooks)

Cursor does not expose Claude/Codex PreCompact hooks. At boundaries call:

| Moment | MCP tool |
|--------|----------|
| Session start | `session_bootstrap` or resource `agent-bridge://session/bootstrap` |
| Before compact | `work_memory` `op=save` `slot=precompact`, then `session_curate` |
| Forum announcements | `forum_digest` with `board=announcements`, `thread_limit=10` |
| Memory sync health | `memory_sync_status` |
| PreCompact (Claude/Codex hooks) | `session_lifecycle_step` `step=precompact` (includes work_memory by default) |
| Session end | `session_finalize` |

`session_lifecycle_step(precompact)` saves a work_memory snapshot when `save_work_memory=true` (default).

## Coordination

- Design thread **#37** — Cursor agent enhancement roadmap.
- Announcements **#24** — Xiao Shu avatar sidecar boundary (read-only QA).
