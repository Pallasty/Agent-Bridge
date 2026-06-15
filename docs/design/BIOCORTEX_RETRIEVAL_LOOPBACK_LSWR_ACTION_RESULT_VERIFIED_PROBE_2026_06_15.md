# BioCortex Retrieval Loopback LSWR Action Result Verified Probe

Date: 2026-06-15

## Summary

The BioCortex downstream AIO handoff now has a read-only MCP
`world_visibility_query` action-result probe that reaches a one-shot loopback
fixture host and returns a verified SSB action-result wrapper.

Machine-readable fixture:

- `docs/design/fixtures/biocortex-retrieval-loopback-lswr-action-result-verified-probe-2026-06-15.json`

Source live observation fixture:

- `docs/design/fixtures/biocortex-retrieval-live-lswr-action-result-runtime-evidence-2026-06-15.json`

## Result

The short-lived probe ran with `AGENT_BRIDGE_TOOL_PROFILE=all`, started a
single-request loopback fixture host, and called `world_visibility_query` over
MCP with `include_raw=true`.

The MCP tool reached the loopback host, so the observed action result is:

```text
verdict=verified
reason=null
verified_to=onsen_live_root_viewport
recover=proceed
raw_available=true
```

This proves that the Agent-Bridge MCP world-tool surface can wrap a reachable
host response into `agent_bridge.semantic_bus.action_result.v0`.

It is not proof that a real onsen runtime or human-visible root viewport is
attached. The loopback host is a controlled fixture host and must not be treated
as training-eligible LSWR runtime evidence.

## Boundary

This probe does not:

- attach a real onsen runtime;
- verify the human-visible onsen root viewport;
- execute LSWR actions;
- emit or persist a durable runtime `agent_bridge.semantic_bus.action_result.v0`;
- call AiOT runtime;
- call `memory_search`;
- run BioCortex;
- write approval state;
- mutate the default Agent-Bridge DB;
- change default `memory_search` return order;
- include raw memory keys, memory content, raw side-signal rows, or human
  decision text.

## Next Step

The remaining next step is to attach a real onsen LSWR host, then collect
verified live-viewport action-result evidence:

```text
attach_real_onsen_lswr_host_then_collect_verified_live_viewport_action_result
```
