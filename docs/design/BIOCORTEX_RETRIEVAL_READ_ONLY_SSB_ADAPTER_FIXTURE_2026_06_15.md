# BioCortex Retrieval Read-Only SSB Adapter Fixture

Date: 2026-06-15

## Summary

The BioCortex downstream AIO handoff now has a read-only Semantic System Bus
adapter fixture:

```text
agent_bridge.biocortex_retrieval.read_only_ssb_adapter_fixture.v0
```

Machine-readable fixture:

- `docs/design/fixtures/biocortex-retrieval-read-only-ssb-adapter-fixture-2026-06-15.json`

Source review fixture:

- `docs/design/fixtures/biocortex-retrieval-ssb-lswr-action-result-review-fixture-2026-06-15.json`

## Candidate Action Result

The fixture projects the handoff into the SSB action-result field shape:

```text
agent_bridge.semantic_bus.action_result.v0
```

The projected `candidate_action_result` is deliberately conservative:

- `verdict=not_verified`;
- `reason=fixture_only_no_lswr_runtime_execution`;
- `verified_to=null`;
- `recover=inspect_host_or_visibility_evidence`;
- `raw_available=false`;
- `fixture_only=true` at the fixture boundary;
- `runtime_executed=false`;
- `executes_lswr_actions=false`.

This is a contract-shape fixture, not LSWR runtime evidence. It must not be
ingested as runtime evidence or used for training.

## Boundary

This adapter fixture does not:

- execute LSWR actions;
- emit a runtime `agent_bridge.semantic_bus.action_result.v0`;
- call AiOT runtime;
- call `memory_search`;
- run BioCortex;
- write approval state;
- mutate the default Agent-Bridge DB;
- change default `memory_search` return order;
- include raw query text, raw memory keys, memory content, raw side-signal
  rows, or human decision text.

## Next Step

Collect live LSWR action-result runtime evidence:

```text
collect_live_lswr_action_result_runtime_evidence
```
