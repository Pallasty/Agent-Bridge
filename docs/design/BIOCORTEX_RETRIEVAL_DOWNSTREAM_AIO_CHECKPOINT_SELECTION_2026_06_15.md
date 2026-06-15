# BioCortex Retrieval Downstream AIO Checkpoint Selection

Date: 2026-06-15

## Summary

The first downstream AIO integration checkpoint for the runtime-backed
BioCortex retrieval evidence is selected:

```text
semantic_system_bus_lswr_action_result_runtime_evidence_checkpoint
```

This checkpoint is intentionally inside Agent-Bridge before any direct AiOT or
production retrieval path. It consumes the BioCortex runtime-backed evidence as
a read-only Semantic System Bus handoff packet and checks whether the evidence
can be represented beside LSWR action/result runtime evidence without
laundering truth, exposing raw retrieval data, or changing default retrieval.

Machine-readable selection:

- `docs/design/fixtures/biocortex-retrieval-downstream-aio-checkpoint-selection-2026-06-15.json`

## Decision

Select the Semantic System Bus LSWR action/result checkpoint as the first AIO
consumer.

Reasons:

- LSWR is already the most mature Agent-Bridge action/result/no-laundering
  pilot.
- The Semantic System Bus roadmap already treats LSWR action/result envelopes
  as the first normalized action-bearing runtime surface.
- The BioCortex evidence is also runtime-backed, redacted, and gated, so it can
  be tested as an AIO evidence packet without changing retrieval behavior.
- Staying inside Agent-Bridge avoids turning AiOT into the first consumer
  before the evidence handoff shape is stable.

The first checkpoint must stay read-only. It may define an evidence handoff
packet and compare it against SSB/LSWR action-result contract expectations, but
it may not enable any new retrieval influence.

## Scope

Selected checkpoint:

- `semantic_system_bus_lswr_action_result_runtime_evidence_checkpoint`

Checkpoint family:

- Semantic System Bus / LSWR action-result runtime evidence

Primary references:

- `docs/design/SEMANTIC_SYSTEM_BUS_ROADMAP_2026_06_07.md`
- `docs/design/SEMANTIC_SYSTEM_BUS_LSWR_ACTION_RESULT_2026_06_07.md`
- `docs/design/BIOCORTEX_RETRIEVAL_POST_SEMANTIC_DIVERSE_REVIEW_2026_06_15.md`
- `docs/design/fixtures/biocortex-retrieval-post-semantic-diverse-review-2026-06-15.json`

First handoff artifact to build next:

- `agent_bridge.biocortex_retrieval.downstream_aio_runtime_evidence_handoff.v0`

## Required Contract

The next artifact should prove only that BioCortex runtime-backed evidence can
be represented as an AIO/SSB handoff packet.

It should include:

- source schema and source review status;
- selected checkpoint id and family;
- redacted evidence counts and safety booleans;
- SSB compatibility claims for runtime-backed evidence, verification boundary,
  no-laundering, and recoverability;
- explicit blockers if any source gate regresses.

It should not include:

- raw query text;
- raw memory keys;
- memory content;
- raw side-signal rows;
- human decision text;
- full input packet bodies.

## Boundary

This checkpoint selection does not authorize:

- default retrieval influence;
- hybrid retrieval influence;
- semantic retrieval influence;
- approval writes;
- default `memory_search` order changes;
- production use;
- direct AiOT runtime consumption;
- LSWR action execution from BioCortex evidence.

The selected checkpoint may only consume a redacted evidence handoff packet
under a read-only or explicitly opt-in boundary.

## Next Step

Build the read-only downstream AIO runtime evidence handoff packet:

```text
build_downstream_aio_runtime_evidence_handoff_packet
```
