# BioCortex Retrieval Post-Runtime Multi-Case Live-Candidate Fixture

Date: 2026-06-13

## Summary

The post-runtime live-candidate runner was replayed with a multi-case
non-production fixture. Unlike Slice 36's single query case, this fixture asks
the runner to process three batch query cases over the same controlled candidate
pair. Each case preserves baseline candidate recall, runs BioCortex through the
post-runtime transition gate, and observes protected explicit opt-in FTS order
movement.

Fixture:

- `docs/design/fixtures/biocortex-retrieval-post-runtime-multi-case-live-candidate-fixture-2026-06-13.json`

Machine-readable summary:

- `docs/design/fixtures/biocortex-retrieval-post-runtime-multi-case-live-candidate-2026-06-13.json`

Local evidence artifacts:

- `target/biocortex-post-runtime-multi-case-live-candidate-20260613/01-controlled-order-fixture-post-runtime.json`
- `target/biocortex-post-runtime-multi-case-live-candidate-20260613/02-gated-store-trial-live-candidate.json`
- `target/biocortex-post-runtime-multi-case-live-candidate-20260613/03-gated-batch-live-candidate.json`
- `target/biocortex-post-runtime-multi-case-live-candidate-20260613/04-status-live-candidate.json`
- `target/biocortex-post-runtime-multi-case-live-candidate-20260613/05-live-candidate-evidence-summary.json`
- `target/biocortex-post-runtime-multi-case-live-candidate-20260613/live-candidate-runner-summary.json`
- `target/biocortex-post-runtime-multi-case-live-candidate-20260613/LIVE_CANDIDATE_REPORT.md`

## Evidence

Runner summary:

- schema:
  `agent_bridge.biocortex_retrieval.post_runtime_live_candidate_runner_summary.v0`;
- status: `post_runtime_live_candidate_evidence_ready`;
- fixture query count: `3`;
- controlled fixture expected movement: met;
- controlled fixture actual order changed count: `3`;
- controlled fixture side-signal ok count: `3`;
- controlled fixture BioCortex run count: `3`;
- gated store status: `transition_gate_consumed`;
- gated store protected order changed: `true`;
- gated batch query count: `3`;
- gated batch baseline empty count: `0`;
- gated batch BioCortex run count: `3`;
- gated batch actual order changed count: `3`;
- evidence summary review state: `post_runtime_evidence_ready`;
- evidence diagnostic class: `movement_observed`.

The status surface remains conservative:

- controlled status: `blocked`;
- blockers:
  - `gated_store_trial_not_consumed`;
  - `gated_batch_diagnostics_not_ready`;
- `status_surface_calls_memory_search=false`;
- `status_surface_runs_biocortex=false`;
- `status_surface_changes_memory_search_order=false`.

That status result remains expected. This artifact set proves protected
explicit opt-in movement, while the status readiness surface accepts
no-order-change readiness evidence.

## Boundary

This run preserves the existing boundaries:

- writes only to the selected output directory and non-production DB;
- requires compile feature `biocortex-retrieval-opt-in`;
- requires runtime env `AB_BIOCORTEX_RETRIEVAL_OPT_IN=1`;
- requires explicit per-call opt-in;
- consumes the post-runtime-backed transition gate;
- does not write approval state;
- does not mutate the default Agent-Bridge DB;
- does not change default `memory_search`, hybrid search, semantic search, or
  default retrieval order;
- runner summary/report leak guards passed for raw query text, raw memory keys,
  memory contents, and raw side-signal rows.

## Interpretation

Slice 38 closes the immediate gap after Slice 37: the reusable runner now has a
multi-case fixture that proves repeated protected order movement. The corpus is
still intentionally controlled and non-production. The next useful expansion is
semantic variety: add independent candidate pairs whose baseline-vs-side-signal
behavior is stable without relying on the same canonical term set.
