# BioCortex Retrieval Loopback LSWR Host Attach Preflight

Date: 2026-06-15

## Summary

The loopback fixture-host probe proved that Agent-Bridge can wrap a reachable
`world_visibility_query` host response into
`agent_bridge.semantic_bus.action_result.v0`. This preflight checks whether the
same client-side path can now attach to the intended real onsen Step B LSWR
host on this Linux checkout.

Machine-readable fixture:

- `docs/design/fixtures/biocortex-retrieval-loopback-lswr-host-attach-preflight-2026-06-15.json`

Source loopback fixture probe:

- `docs/design/fixtures/biocortex-retrieval-loopback-lswr-action-result-verified-probe-2026-06-15.json`

## Result

The preflight is blocked by missing host runtime state:

```text
status=blocked_missing_loopback_host_checkout
target_endpoint=127.0.0.1:37691
target_protocol=newline_json_tcp
port_37691_listening=false
onsen_step_b_checkout_present=false
```

The documented macOS checkout path
`/Users/pallasting/Projects/onsen-hd-live-semantic-phase0` is not present on
this Linux host, and no accepted onsen Step B host checkout was found at the
candidate Linux path. The local `prototypes/lswr-web-prototype` directory is
present, but it is not the newline-JSON TCP onsen world-tool host needed for the
runtime probe.

## Boundary

This preflight does not:

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
- include host response payloads, raw memory keys, memory content, raw
  side-signal rows, or human decision text.

## Next Step

Restore or clone the accepted onsen Step B host checkout, launch the
newline-JSON TCP dev host, then rerun the live `world_visibility_query` probe:

```text
restore_or_clone_onsen_step_b_host_checkout_then_launch_dev_host
```
