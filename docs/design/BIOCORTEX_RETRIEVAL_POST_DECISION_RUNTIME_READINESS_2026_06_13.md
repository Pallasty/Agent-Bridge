# BioCortex Retrieval Post-Decision Runtime Readiness

Date: 2026-06-13

## Summary

After the explicit opt-in FTS runtime influence authorization was recorded, the
formal decision packet was consumed by the runtime/store readiness chain.

Machine-readable summary:

- `docs/design/fixtures/biocortex-retrieval-post-decision-runtime-readiness-2026-06-13.json`

Local evidence artifacts:

- `target/biocortex-post-decision-readiness-20260613/01-store-trial.json`
- `target/biocortex-post-decision-readiness-20260613/02-batch-diagnostics.json`
- `target/biocortex-post-decision-readiness-20260613/03-runtime-readiness-packet.json`
- `target/biocortex-post-decision-readiness-20260613/04-runtime-transition-gate.json`
- `target/biocortex-post-decision-readiness-20260613/05-gated-store-trial.json`
- `target/biocortex-post-decision-readiness-20260613/06-gated-batch-diagnostics.json`
- `target/biocortex-post-decision-readiness-20260613/07-runtime-readiness-packet-gated-batch.json`
- `target/biocortex-post-decision-readiness-20260613/08-status.json`

The status surface reports
`ready_for_controlled_explicit_opt_in_fts_trial` with no blockers. This means
the control plane is ready to accept controlled explicit per-call FTS opt-in
trials through the runtime transition gate.

It does not mean default retrieval influence is enabled.

## Inputs

Decision packet:

- `target/biocortex-runtime-influence-decision-20260613/runtime-influence-decision-packet.json`

Decision scope:

- `authorization_scope=explicit_opt_in_fts_runtime_influence`
- `implementation_allowed=true`
- `runtime_adapter_approved=true`
- `ordering_behavior_connection_authorized=true`
- `default_search_order_change_allowed=false`
- `default_retrieval_influence_authorized=false`
- `hybrid_retrieval_influence_authorized=false`
- `semantic_retrieval_influence_authorized=false`

Execution isolation:

- all store probes used caller-selected non-production `AGENT_BRIDGE_DB` paths
  under `target/biocortex-post-decision-readiness-20260613/`;
- raw probe query/key strings were not included in the generated JSON outputs;
- the durable Agent-Bridge memory DB was not used for fixture writes.

## Evidence

Store trial:

- schema: `agent_bridge.biocortex_retrieval.opt_in_store_trial.v0`;
- status: `baseline_returned`;
- `calls_memory_search=true`;
- `runs_biocortex=false`;
- preflight blocker: `baseline_empty`;
- `changes_memory_search_order=false`;
- `default_calls_unchanged=true`.

Batch diagnostics:

- schema: `agent_bridge.biocortex_retrieval.opt_in_batch_diagnostics.v0`;
- status: `completed`;
- query count: `2`;
- all live probes returned empty baselines in the isolated store.

Runtime readiness packet with gated batch diagnostics:

- schema:
  `agent_bridge.biocortex_retrieval.opt_in_runtime_readiness_packet.v0`;
- status: `completed`;
- `control_plane_ready=true`;
- `runtime_readiness_ready=true`;
- `live_probe_state=control_plane_ready_no_live_candidates`;
- `may_accept_controlled_explicit_opt_in_fts_calls=true`;
- `live_order_influence_ready=false`;
- `default_influence_ready=false`;
- `batch_diagnostics_evidence_source=runtime_transition_gated_batch_diagnostics`;
- `batch_diagnostics_transition_gated=true`.

Runtime transition gate:

- schema: `agent_bridge.biocortex_retrieval.opt_in_runtime_transition_gate.v0`;
- status: `transition_allowed`;
- requested mode: `fts`;
- `per_call_opt_in=true`;
- `transition_allowed=true`;
- `may_call_controlled_store_trial=true`;
- `may_run_runtime_adapter_for_explicit_opt_in_fts=true`;
- `may_connect_ordering_behavior_for_explicit_opt_in_fts=true`;
- `may_change_default_memory_search_order=false`.

Gated store and batch diagnostics:

- gated store status: `transition_gate_consumed`;
- gated store called the protected store trial;
- gated batch status: `completed`;
- gated batch query count: `2`;
- gated batch `transition_gate_allowed_count=2`;
- gated batch `store_trial_called_count=2`;
- gated batch `calls_memory_search_count=2`;
- gated batch `runs_biocortex_count=0`;
- gated batch `actual_order_changed_count=0`.

Controlled trial readiness status:

- schema:
  `agent_bridge.biocortex_retrieval.controlled_trial_readiness_summary.v0`;
- status: `ready_for_controlled_explicit_opt_in_fts_trial`;
- `ready_for_controlled_trial=true`;
- blockers: `[]`;
- `status_surface_calls_memory_search=false`;
- `status_surface_runs_biocortex=false`;
- `status_surface_changes_memory_search_order=false`;
- `raw_packets_included=false`;
- `raw_queries_included=false`;
- `raw_keys_included=false`;
- `content_included=false`.

## Boundary

This post-decision run confirms that the existing explicit opt-in FTS runtime
authorization can be consumed by the protected runtime readiness chain. The
allowed path remains narrow:

- compile feature must be enabled;
- `AB_BIOCORTEX_RETRIEVAL_OPT_IN=1` must be set for the protected live probes;
- each call must pass explicit per-call opt-in;
- `AB_BIOCORTEX_RETRIEVAL_DISABLE` remains the operator kill switch;
- missing live candidates produce a control-plane-ready/no-live-candidates
  state, not a default-order change;
- default `memory_search`, hybrid search, and semantic search remain unchanged.

The current readiness packet is legacy-compatible with the aggregate-backed
decision packet. It is not post-runtime-evidence-summary-backed yet:

- `post_runtime_evidence_summary_backed=false`;
- `post_runtime_evidence_summary_ready=false`;
- `post_runtime_evidence_summary_state=not_provided_legacy_compatible`.

That is acceptable for controlled explicit opt-in FTS readiness. A later
post-runtime evidence summary can still be produced if the review boundary is
tightened to require post-runtime evidence before wider rollout.
