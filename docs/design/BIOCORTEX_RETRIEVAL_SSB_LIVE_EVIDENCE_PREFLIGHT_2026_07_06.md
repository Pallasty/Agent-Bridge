# BioCortex Retrieval SSB Live Evidence Preflight

Date: 2026-07-06

## Summary

This preflight defines the next owner gate before any attempt to collect
verified live LSWR `agent_bridge.semantic_bus.action_result.v0` evidence for
the BioCortex retrieval downstream handoff.

Machine-readable fixture:

- `docs/design/fixtures/biocortex-retrieval-ssb-live-evidence-preflight-2026-07-06.json`

Source status surface:

- `docs/design/fixtures/biocortex-retrieval-thread-104-status-surface-2026-07-06.json`

## Result

The preflight is blocked:

```text
status=blocked_pending_owner_live_runtime_gate
ready_for_live_runtime_contact=false
ready_for_verified_action_result_collection=false
```

The repository already has:

- read-only SSB adapter fixture shape;
- observed-not-verified live LSWR action-result runtime evidence;
- verified loopback fixture-host action result;
- blocked host attach/source-resolution records.

Those are not enough to contact a real LSWR runtime. A separate owner gate must
provide or confirm the accepted onsen Step B host source, endpoint, protocol,
timeout, identity, and redaction rules before any live runtime contact.

## Required Gates

Before a verified live runtime evidence collection attempt, the owner must
provide or approve:

- accepted onsen Step B host checkout/source;
- `world_visibility_query` newline-JSON TCP host endpoint;
- host identity and branch/head evidence;
- timeout budget;
- no-action-execution constraint;
- post-lookup redaction rule;
- human-visible viewport verification requirement;
- no ingestion of `not_verified` results as verified runtime evidence.

## Boundary

This preflight does not:

- contact a live runtime;
- open a socket;
- execute LSWR actions;
- emit or persist a durable runtime `agent_bridge.semantic_bus.action_result.v0`;
- call AiOT runtime;
- call `memory_search`;
- run BioCortex;
- write approval state;
- mutate the default Agent-Bridge DB;
- change default `memory_search` return order;
- include host response payloads, raw memory keys, memory content, raw
  side-signal rows, or raw capability-ledger reports.

## Next Step

```text
owner_supplies_onsen_step_b_host_source_or_declines_live_evidence_lane
```
