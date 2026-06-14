# BioCortex Retrieval Post-Runtime Evidence-Backed Decision

Date: 2026-06-13

## Summary

Slice 34 proved that the explicit opt-in FTS runtime authorization packet can be
consumed by the gated runtime readiness chain. This follow-up tightens that
proof: the runtime-influence review request and decision packet now include a
post-runtime evidence summary, and the downstream readiness/gate/status chain
confirms `post_runtime_evidence_summary_ready=true`.

Machine-readable summary:

- `docs/design/fixtures/biocortex-retrieval-post-runtime-evidence-backed-decision-2026-06-13.json`

Local evidence artifacts:

- `target/biocortex-post-runtime-evidence-20260613/01-evidence-summary-with-gated-readiness.json`
- `target/biocortex-post-runtime-evidence-20260613/02-runtime-influence-review-request-post-runtime.json`
- `target/biocortex-post-runtime-evidence-20260613/03-runtime-influence-decision-packet-post-runtime.json`
- `target/biocortex-post-runtime-evidence-20260613/04-store-trial-post-runtime.json`
- `target/biocortex-post-runtime-evidence-20260613/05-gated-store-trial-post-runtime-old-gate.json`
- `target/biocortex-post-runtime-evidence-20260613/06-gated-batch-post-runtime-old-gate.json`
- `target/biocortex-post-runtime-evidence-20260613/07-runtime-readiness-packet-post-runtime.json`
- `target/biocortex-post-runtime-evidence-20260613/08-runtime-transition-gate-post-runtime.json`
- `target/biocortex-post-runtime-evidence-20260613/09-gated-store-trial-post-runtime-final.json`
- `target/biocortex-post-runtime-evidence-20260613/10-gated-batch-post-runtime-final.json`
- `target/biocortex-post-runtime-evidence-20260613/11-status-post-runtime.json`

The final status surface reports
`ready_for_controlled_explicit_opt_in_fts_trial` with
`post_runtime_evidence_summary_ready=true` and no blockers.

## Evidence Chain

Post-runtime evidence summary:

- schema: `agent_bridge.biocortex_retrieval.opt_in_evidence_summary.v0`;
- `evidence_ready=true`;
- `review_state=post_runtime_evidence_ready`;
- `runtime_readiness_requirement_met=true`;
- `readiness_gated_batch_evidence_ready=true`;
- `batch_diagnostics_transition_gated=true`;
- `batch_diagnostics_evidence_source=runtime_transition_gated_batch_diagnostics`;
- no approval state is written and default influence remains unready.

Runtime influence review request:

- schema:
  `agent_bridge.biocortex_retrieval.opt_in_runtime_influence_review_request.v0`;
- `runtime_influence_review_request_ready=true`;
- `post_runtime_evidence_summary_ready=true`;
- `post_runtime_evidence_summary_review_state=post_runtime_evidence_ready`;
- the request remains review-only and grants no runtime influence by itself.

Runtime influence decision packet:

- schema:
  `agent_bridge.biocortex_retrieval.opt_in_runtime_influence_decision_packet.v0`;
- `runtime_influence_authorized=true`;
- `post_runtime_evidence_summary_backed_review_request=true`;
- `post_runtime_evidence_summary_ready=true`;
- `post_runtime_evidence_summary_state=post_runtime_evidence_ready`;
- `default_search_order_change_allowed=false`;
- `default_retrieval_influence_authorized=false`;
- `hybrid_retrieval_influence_authorized=false`;
- `semantic_retrieval_influence_authorized=false`.

Store/readiness/gate replay with the post-runtime-backed decision:

- store trial status: `baseline_returned`;
- store trial `compile_feature_enabled=true`;
- store trial post-runtime preflight ready: `true`;
- store trial blocker: `baseline_empty`;
- runtime readiness packet status: `completed`;
- runtime readiness `runtime_readiness_ready=true`;
- runtime readiness `post_runtime_evidence_summary_ready=true`;
- runtime readiness state: `post_runtime_evidence_ready`;
- runtime readiness `live_probe_state=control_plane_ready_no_live_candidates`;
- runtime transition gate status: `transition_allowed`;
- runtime transition gate `post_runtime_evidence_summary_ready=true`.

Final gated probes:

- final gated store status: `transition_gate_consumed`;
- final gated store called the protected store trial;
- final gated store post-runtime preflight ready: `true`;
- final gated batch status: `completed`;
- final gated batch query count: `1`;
- final gated batch post-runtime preflight ready: `true`;
- final gated batch `runs_biocortex_count=0` because the isolated test store
  has no live baseline candidates.

Controlled trial readiness:

- schema:
  `agent_bridge.biocortex_retrieval.controlled_trial_readiness_summary.v0`;
- status: `ready_for_controlled_explicit_opt_in_fts_trial`;
- `ready_for_controlled_trial=true`;
- `post_runtime_evidence_summary_backed=true`;
- `post_runtime_evidence_summary_ready=true`;
- `post_runtime_evidence_summary_state=post_runtime_evidence_ready`;
- blockers: `[]`;
- `status_surface_calls_memory_search=false`;
- `status_surface_runs_biocortex=false`;
- `status_surface_changes_memory_search_order=false`.

## Boundary

This packet set is stronger than Slice 34 because the decision/readiness/status
chain is now post-runtime-evidence-backed instead of legacy-compatible only.

The runtime surface is still narrow:

- only explicit per-call FTS opt-in calls are in scope;
- compile feature `biocortex-retrieval-opt-in` is required;
- `AB_BIOCORTEX_RETRIEVAL_OPT_IN=1` is required for protected live probes;
- `AB_BIOCORTEX_RETRIEVAL_DISABLE` remains the operator kill switch;
- missing live candidates still return baseline and produce
  `control_plane_ready_no_live_candidates`;
- default `memory_search`, hybrid search, semantic search, approval writes, raw
  query/key/content exposure, and default search order remain unchanged.

The next useful step is a non-production controlled live-candidate fixture that
exercises the post-runtime-backed final gate with non-empty baseline candidates,
so the chain can observe side-signal execution under the tightened decision
packet while still avoiding default retrieval influence.
