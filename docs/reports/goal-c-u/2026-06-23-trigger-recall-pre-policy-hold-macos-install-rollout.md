# Trigger Recall Pre-Policy Hold macOS Install Rollout

Date: 2026-06-23

Scope: macOS local installed-binary rollout verification for the already-merged
Trigger Recall pre-policy hold simulation, approval-packet validator, and
portable Stage-2 fixture mainline.

This report records only installed-binary and MCP-surface evidence on
`/Users/pallasting`. It does not change default `memory_search`, enable
production `enforce_hold`, mutate memory data, write graph edges, or widen
Codex eager tool surfaces.

## Rollout Target

| Field | Value |
|---|---|
| repository | `/Users/pallasting/Projects/agent-bridge` |
| deploy source | `origin/master @ 922fd5c` |
| deployed commit | `922fd5cb4426b0d532c2351d30ce749b62b56eea` |
| installed binary | `/Users/pallasting/.local/bin/agent-bridge.real` |
| deployed size | `54212944` bytes |
| deployed sha256 | `168db2c192bffd82010edbba13711dca967cf9436dbed544f317e522699949fa` |
| final deploy backup | `/Users/pallasting/.local/bin/agent-bridge.real.bak-deploy-922fd5c-20260623T072844` |

Both tracked remotes were converged at verification time:

```text
git rev-list --left-right --count origin/master...HEAD  = 0 0
git rev-list --left-right --count github/master...HEAD  = 0 0
```

The only local untracked files were unrelated probe examples:

```text
crates/store/examples/zh_embed_probe.rs
crates/store/examples/zh_recall_probe.rs
```

## Deploy Command

```text
scripts/deploy_from_master.sh --yes
```

The first deploy in this session built from `55b5618`, but main advanced during
the run. The final deploy rebuilt and installed from `922fd5c`, after the
portable Stage-2 fixture merge.

## Source-Level Gates

```text
CARGO_BUILD_JOBS=2 cargo test -p ab-bridge --lib \
  trigger_recall_opt_in_pre_policy_hold_simulation_schema_is_registered -- --nocapture
```

Result: passed, 1 test.

```text
CARGO_BUILD_JOBS=2 cargo test -p ab-bridge --lib \
  trigger_recall_enforce_hold_approval_packet_validator_schema_is_registered_niche -- --nocapture
```

Result: passed, 1 test.

These tests pin the expected policy boundary:

- `ToolProfile::All` exposes the Niche tools;
- `codex-essential` does not expose them.

## Direct MCP Surface Smoke

The installed binary was launched directly with newline-delimited JSON-RPC and
`tools/list`.

Profile-only all:

```text
AGENT_BRIDGE_TOOL_PROFILE=all
tools/list count=273
trigger_recall_opt_in_pre_policy_hold_simulation=present
trigger_recall_enforce_hold_approval_packet_validator=present
trigger_recall_opt_in_gated_batch_diagnostics=present
```

Explicit profile set to `profile` plus `all`:

```text
AGENT_BRIDGE_TOOLSET=profile
AGENT_BRIDGE_TOOL_PROFILE=all
tools/list count=273
trigger_recall_opt_in_pre_policy_hold_simulation=present
trigger_recall_enforce_hold_approval_packet_validator=present
trigger_recall_opt_in_gated_batch_diagnostics=present
```

Default Codex lean surface:

```text
AGENT_BRIDGE_CLIENT=codex
AGENT_BRIDGE_CODEX_HOST=desktop
AGENT_BRIDGE_TOOLSET=codex-lean
AGENT_BRIDGE_TOOL_PROFILE=essential
tools/list count=40
trigger_recall_opt_in_pre_policy_hold_simulation=absent
trigger_recall_enforce_hold_approval_packet_validator=absent
trigger_recall_opt_in_gated_batch_diagnostics=absent
```

Codex client plus `AGENT_BRIDGE_TOOL_PROFILE=all` still remained on the Codex
allowlist path:

```text
AGENT_BRIDGE_CLIENT=codex
AGENT_BRIDGE_TOOL_PROFILE=all
tools/list count=94
trigger_recall_opt_in_pre_policy_hold_simulation=absent
trigger_recall_enforce_hold_approval_packet_validator=absent
trigger_recall_opt_in_gated_batch_diagnostics=absent
```

This is expected from `ToolPolicy::from_values`: a named `codex` client maps to
the Codex toolset before the legacy profile is applied. To expose Niche tools
for direct smoke, use a profile-only run or `AGENT_BRIDGE_TOOLSET=profile`.

## Direct Tool Call Smoke

With `AGENT_BRIDGE_TOOL_PROFILE=all`, a direct `tools/call` to
`trigger_recall_enforce_hold_approval_packet_validator` with an empty approval
packet returned the expected redacted blocker packet:

```text
approval_packet_included=false
canonical_mode=invalid
decision.may_change_default_memory_search=false
decision.may_implement_audit_only=false
decision.may_implement_enforce_hold=false
```

This confirms the installed binary can execute the validator surface under the
explicit all-profile opt-in.

## Doctor Result

```text
/Users/pallasting/.local/bin/agent-bridge.real doctor --json
ok=true
fails=0
warns=3
```

Warnings:

- `mcp_servers`: 9 stale MCP server processes still map the old `.real`; no
  current `.real` MCP server is detected for this install path. Reconnect MCP
  clients before assuming an active client sees the new manifest.
- `system_control_api`: `/Users/pallasting/.local/bin/ab-system-control`
  missing.
- `desktop_runtime`: desktop status is unavailable because `ab-system-control`
  is missing.

The active MCP capability surface in this Codex session still reports
`toolset=codex-lean`, `tool_profile=essential`, and `exposed_tool_count=40`,
which is expected until this client reconnects and is also expected to hide the
new Niche tools by default.

## Residual Risk

The direct JSON-RPC smoke parsed complete `tools/list` and `tools/call`
responses, but the direct `agent-bridge.real mcp` subprocess exited with
`SIGSEGV` (`return=-11`) after stdin closed. This occurred for both profile-only
all and Codex lean/essential runs, so it is not specific to the new trigger
recall surfaces. Treat it as a separate MCP EOF/teardown bug to investigate
before relying on direct-process exit code as a clean smoke gate.

## Boundaries Preserved

This rollout confirms local installation and explicit opt-in visibility only.
It still does not authorize:

- default `memory_search` behavior, schema, or ordering changes;
- production `enforce_hold`;
- exposing trigger recall Niche tools in Codex lean/essential;
- semantic or graph retrieval changes;
- memory writes;
- graph writes;
- reindex.

Next safe step: reconnect the active MCP clients, then verify the live active
session has respawned from the current `.real`. If the user wants runtime
behavior smoke after reconnect, run it through an explicit all-profile or
profile-scoped direct process rather than the default Codex lean surface.
