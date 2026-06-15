# BioCortex Retrieval Live LSWR Action Result Runtime Evidence

Date: 2026-06-15

## Summary

The BioCortex downstream AIO handoff now has a live read-only LSWR
`world_visibility_query` runtime observation.

Machine-readable fixture:

- `docs/design/fixtures/biocortex-retrieval-live-lswr-action-result-runtime-evidence-2026-06-15.json`

Source adapter fixture:

- `docs/design/fixtures/biocortex-retrieval-read-only-ssb-adapter-fixture-2026-06-15.json`

## Result

The live MCP probe ran with `AGENT_BRIDGE_TOOL_PROFILE=all` and confirmed that
`world_visibility_query` is present. The call attempted to query the loopback
LSWR host at `127.0.0.1:37691` with `include_raw=false`.

The host was not reachable, so the observed action result is deliberately:

```text
verdict=not_verified
reason=world_host_unreachable
verified_to=null
recover=inspect_host_or_visibility_evidence
raw_available=false
```

The live envelope carried a `host_response` field with `null` value; no host raw
payload was included.

This is live runtime observation evidence, not verified LSWR action-result
evidence. It must not be ingested as a verified runtime result or used for
training.

## Boundary

This observation does not:

- execute LSWR actions;
- emit or persist a durable runtime `agent_bridge.semantic_bus.action_result.v0`;
- call AiOT runtime;
- call `memory_search`;
- run BioCortex;
- write approval state;
- mutate the default Agent-Bridge DB;
- change default `memory_search` return order;
- include host raw response, raw memory keys, memory content, raw side-signal
  rows, or human decision text.

## Next Step

Start or attach a loopback LSWR host, then rerun the same live action-result
probe:

```text
start_or_attach_loopback_lswr_host_then_rerun_live_action_result_probe
```
