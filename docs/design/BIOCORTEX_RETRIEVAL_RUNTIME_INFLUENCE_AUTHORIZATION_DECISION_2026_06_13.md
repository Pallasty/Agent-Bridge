# BioCortex Retrieval Runtime Influence Authorization Decision

Date: 2026-06-13

## Decision

Authorization is granted for `explicit_opt_in_fts_runtime_influence` only.

Machine-readable decision record:

- `docs/design/fixtures/biocortex-retrieval-runtime-influence-authorization-decision-2026-06-13.json`

This decision authorizes the already-built explicit opt-in FTS runtime
adapter/order-connection path to be used behind its existing gates. It does not
authorize default retrieval influence, hybrid retrieval influence, semantic
retrieval influence, approval writes, or calls without explicit per-call opt-in.

## Reviewed Evidence

Reviewed request:

- `docs/design/BIOCORTEX_RETRIEVAL_RUNTIME_INFLUENCE_REVIEW_REQUEST_2026_06_13.md`
- `docs/design/fixtures/biocortex-retrieval-runtime-influence-review-request-summary-2026-06-13.json`

Evidence source:

- source implementation commit:
  `34bf2e3a3ee74135f6774381c094e3ad64bb2289`;
- review request commit:
  `aa9955cec9907035f7bacc85e16b56d73f2aeec9`;
- controlled-trial summary:
  `target/biocortex-runtime-review-request-20260613/controlled-trial-summary.json`.

Evidence state:

- `controlled_trial_redacted_evidence_ready`;
- `aggregate_evidence_ready=true`;
- `controlled_rank_movement_observed=true`;
- `expanded_coverage_without_additional_movement=true`;
- `default_influence_ready=false`;
- `default_search_order_change_allowed=false`;
- `default_calls_unchanged=true`;
- the review request has `this_packet_grants_request=false`, so this document is
  the separate decision artifact.

## Authorized Scope

Allowed:

- run the BioCortex runtime adapter for explicitly opted-in FTS calls only;
- connect ordering behavior for explicitly opted-in FTS calls only;
- require `biocortex-retrieval-opt-in` compile-time feature;
- require `AB_BIOCORTEX_RETRIEVAL_OPT_IN=1`;
- require explicit per-call opt-in;
- keep `AB_BIOCORTEX_RETRIEVAL_DISABLE=1` as the operator kill switch;
- preserve baseline candidate recall;
- return baseline without per-call opt-in;
- fail open to baseline on absent adapter, adapter error, timeout, malformed
  side signal, low coverage, missing runtime gate, or operator disable.

Not authorized:

- default `memory_search` order changes;
- default FTS retrieval influence;
- hybrid retrieval influence;
- semantic retrieval influence;
- calls that do not explicitly opt in;
- approval-state writes;
- embedding backend registration.

## Required Follow-Up

The decision must be consumed by
`agent-bridge bio-cortex retrieval-opt-in-runtime-influence-decision-packet`
and pass the machine-checkable packet boundary before downstream store-trial or
runtime-readiness evidence is treated as authorized.

Verified command:

```bash
agent-bridge bio-cortex retrieval-opt-in-runtime-influence-decision-packet \
  --runtime-influence-review-request-json target/biocortex-runtime-review-request-20260613/15-runtime-influence-review-request-with-aggregate.json \
  --runtime-influence-decision-json docs/design/fixtures/biocortex-retrieval-runtime-influence-authorization-decision-2026-06-13.json \
  --reviewer codex-runtime-decision \
  --commit 34bf2e3a3ee74135f6774381c094e3ad64bb2289 \
  --forum-post-id 2388 \
  --memory-key biocortex_runtime_influence_review_request_20260613
```

Local verification output:

- `target/biocortex-runtime-influence-decision-20260613/runtime-influence-decision-packet.json`

The decision packet is still a control-plane artifact. It should continue to
report:

- `default_search_order_change_allowed=false`;
- `default_retrieval_influence_authorized=false`;
- `hybrid_retrieval_influence_authorized=false`;
- `semantic_retrieval_influence_authorized=false`;
- `writes_approval=false`;
- `changes_memory_search_order=false`;
- `this_packet_changes_return_order=false`.

The verified packet reports `implementation_allowed=true`,
`runtime_adapter_approved=true`, and
`ordering_behavior_connection_authorized=true` for the explicit opt-in FTS
scope only. It also reports `this_packet_connects_ordering_behavior=false` and
`this_packet_changes_return_order=false`.
