# BioCortex Retrieval Onsen Step B Host Launch Plan

Date: 2026-06-15

Schema:

```text
agent_bridge.biocortex_retrieval.onsen_step_b_host_launch_plan.v0
```

Fixture:

```text
docs/design/fixtures/biocortex-retrieval-onsen-step-b-host-launch-plan-2026-06-15.json
```

## Status

```text
blocked_missing_onsen_step_b_source
```

The launch plan is now recorded as a stable, reviewable fixture. It consumes the
Onsen Step B source-resolution evidence and describes the next operator-owned
host launch step, but it does not start a host or collect runtime evidence.

The accepted Step B source is still missing from this Linux host:

- accepted macOS worktree:
  `/Users/pallasting/Projects/onsen-hd-live-semantic-phase0`;
- expected Linux checkout:
  `/Data/CascadeProjects/onsen-hd-live-semantic-phase0`;
- accepted branch: `codex/live-semantic-phase0-t1`;
- accepted head: `10d58ee`;
- expected endpoint: `127.0.0.1:37691`;
- expected protocol: newline-delimited JSON over TCP;
- required world tool: `world_visibility_query`.

## Launch Boundary

Agent-Bridge remains the client side of the LSWR host. Launching the accepted
Onsen Step B checkout belongs to the operator or Onsen runtime.

This launch-plan slice does not:

- clone repositories;
- start Godot or any host process;
- execute LSWR actions;
- call `memory_search`;
- run BioCortex;
- write approval state;
- mutate the default Agent-Bridge DB;
- change default retrieval order;
- call AiOT runtime;
- emit a durable runtime `agent_bridge.semantic_bus.action_result.v0`;
- include host responses, raw memory keys, memory content, raw side-signal
  rows, or human decision text.

## Next Commands

Once the accepted checkout or repository URL is available:

```text
scripts/probe-onsen-step-b-host-source.sh --strict --checkout /Data/CascadeProjects/onsen-hd-live-semantic-phase0
scripts/plan-onsen-step-b-host-launch.sh --checkout /Data/CascadeProjects/onsen-hd-live-semantic-phase0
```

After the operator launches the newline-JSON TCP dev host and confirms
`127.0.0.1:37691` is listening, rerun the live `world_visibility_query` evidence
collection through Agent-Bridge with `AGENT_BRIDGE_TOOL_PROFILE=all`.

## Next Step

```text
provide_or_sync_onsen_step_b_checkout_or_repository_url
```
