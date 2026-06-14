# BioCortex Retrieval Post-Runtime Live-Candidate Fixture

Date: 2026-06-13

## Summary

The post-runtime-evidence-backed final gate was exercised against a
non-production store containing live baseline candidates. Unlike the earlier
empty-store readiness probes, this run allowed the protected explicit opt-in FTS
path to call the external BioCortex side-signal adapter and return an
experimental order.

Machine-readable summary:

- `docs/design/fixtures/biocortex-retrieval-post-runtime-live-candidate-fixture-2026-06-13.json`

Local evidence artifacts:

- `target/biocortex-post-runtime-live-candidate-20260613/01-controlled-order-fixture-post-runtime.json`
- `target/biocortex-post-runtime-live-candidate-20260613/02-gated-store-trial-live-candidate.json`
- `target/biocortex-post-runtime-live-candidate-20260613/03-gated-batch-live-candidate.json`
- `target/biocortex-post-runtime-live-candidate-20260613/04-status-live-candidate.json`
- `target/biocortex-post-runtime-live-candidate-20260613/05-live-candidate-evidence-summary.json`

The result is a controlled influence proof, not a default retrieval change:

- the non-production fixture seeded `2` memories;
- the protected gated store trial saw `2` baseline candidates;
- the runtime adapter was allowed;
- side-signal status was `ok`;
- BioCortex ran for the explicitly opted-in call;
- the protected returned order changed;
- default calls remained unchanged.

## Evidence

Controlled fixture seed/run:

- schema: `agent_bridge.biocortex_retrieval.opt_in_controlled_order_fixture_run.v0`;
- status: `completed`;
- expected movement: met;
- seeded memory count: `2`;
- query count: `1`;
- actual order changed count: `1`;
- experimental source count: `1`;
- side-signal ok count: `1`.

Final gated store trial:

- schema: `agent_bridge.biocortex_retrieval.opt_in_gated_store_trial.v0`;
- status: `transition_gate_consumed`;
- store trial called: `true`;
- baseline key count: `2`;
- runtime adapter allowed: `true`;
- side-signal attempted: `true`;
- side-signal status: `ok`;
- runs BioCortex: `true`;
- protected opt-in order changed: `true`;
- default calls unchanged: `true`.

Final gated batch diagnostics:

- schema: `agent_bridge.biocortex_retrieval.opt_in_gated_batch_diagnostics.v0`;
- status: `completed`;
- query count: `1`;
- baseline empty count: `0`;
- transition gate allowed count: `1`;
- store trial called count: `1`;
- adapter allowed count: `1`;
- side-signal ok count: `1`;
- experimental source count: `1`;
- actual order changed count: `1`;
- runs BioCortex count: `1`;
- post-runtime evidence summary ready: `true`.

Live-candidate evidence summary:

- schema: `agent_bridge.biocortex_retrieval.opt_in_evidence_summary.v0`;
- status: `completed`;
- review state: `post_runtime_evidence_ready`;
- evidence ready: `true`;
- batch diagnostic class: `movement_observed`;
- movement observed: `true`;
- summary surface calls `memory_search=false`;
- summary surface runs BioCortex: `false`;
- summary surface changes memory search order: `false`;
- default search order change allowed: `false`.

## Status Surface Interpretation

`retrieval-opt-in-status` deliberately reports `blocked` for this live-candidate
artifact set:

- `gated_store_trial_not_consumed`;
- `gated_batch_diagnostics_not_ready`.

That is expected for this specific evidence type. The status readiness summary
accepts no-order-change gated evidence as readiness input. This live-candidate
fixture intentionally proves that the protected explicit opt-in call can change
the returned order, so it is influence evidence rather than a readiness packet
input.

The status surface itself remains side-effect free:

- `status_surface_calls_memory_search=false`;
- `status_surface_runs_biocortex=false`;
- `status_surface_changes_memory_search_order=false`;
- `default_calls_unchanged=true`.

## Boundary

This run used a caller-selected non-production `AGENT_BRIDGE_DB` under
`target/biocortex-post-runtime-live-candidate-20260613/`.

The observed order movement is scoped to the protected explicit opt-in FTS
store trial:

- compile feature `biocortex-retrieval-opt-in` was enabled;
- `AB_BIOCORTEX_RETRIEVAL_OPT_IN=1` was set;
- explicit per-call opt-in was supplied;
- the post-runtime-backed runtime transition gate was consumed;
- raw query text, raw memory keys, memory contents, and raw side-signal rows
  were not included in the redacted outputs;
- default `memory_search`, hybrid search, semantic search, approval writes, and
  default search order remain unchanged.

The next useful step is to turn this into a reusable runner or verifier slice so
future changes can re-run the post-runtime-backed live-candidate proof without
manual command assembly.
