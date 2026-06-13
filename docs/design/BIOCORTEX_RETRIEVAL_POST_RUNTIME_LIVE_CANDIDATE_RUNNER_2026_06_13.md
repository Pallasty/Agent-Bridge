# BioCortex Retrieval Post-Runtime Live-Candidate Runner

Date: 2026-06-13

## Summary

The post-runtime live-candidate proof is now reusable through a dedicated
runner:

- `scripts/run-biocortex-post-runtime-live-candidate.sh`

The runner replays the Slice 36 proof against a caller-selected
non-production `AGENT_BRIDGE_DB`, verifies each redacted artifact with `jq`,
and emits a compact summary/report. It is a verifier slice only: it does not
write approval state, mutate the default Agent-Bridge DB, or grant default
retrieval influence.

Machine-readable summary:

- `docs/design/fixtures/biocortex-retrieval-post-runtime-live-candidate-runner-2026-06-13.json`

Local evidence artifacts:

- `target/biocortex-post-runtime-live-candidate-runner-20260613/01-controlled-order-fixture-post-runtime.json`
- `target/biocortex-post-runtime-live-candidate-runner-20260613/02-gated-store-trial-live-candidate.json`
- `target/biocortex-post-runtime-live-candidate-runner-20260613/03-gated-batch-live-candidate.json`
- `target/biocortex-post-runtime-live-candidate-runner-20260613/04-status-live-candidate.json`
- `target/biocortex-post-runtime-live-candidate-runner-20260613/05-live-candidate-evidence-summary.json`
- `target/biocortex-post-runtime-live-candidate-runner-20260613/live-candidate-runner-summary.json`
- `target/biocortex-post-runtime-live-candidate-runner-20260613/LIVE_CANDIDATE_REPORT.md`

## Runner Contract

The runner consumes:

- a post-runtime-backed runtime influence decision packet;
- a runtime readiness packet;
- a runtime transition gate;
- the canonical controlled-order fixture;
- a local `biocortex-rs` checkout.

It then checks that:

- the controlled fixture can seed `2` non-production memories and meet expected
  movement evidence;
- the gated store trial consumes the transition gate, sees `2` baseline
  candidates, allows the runtime adapter, runs BioCortex, and returns the
  protected experimental order;
- the gated batch diagnostics reports one transition-allowed query, one
  BioCortex run, and one actual order movement;
- the status surface stays read-only and intentionally reports the
  live-candidate artifact set as `blocked`;
- the evidence summary reports `post_runtime_evidence_ready` and
  `movement_observed`;
- raw query text, raw memory keys, memory contents, and raw side-signal rows
  are absent from committed runner summaries.

## Evidence

Runner summary:

- schema:
  `agent_bridge.biocortex_retrieval.post_runtime_live_candidate_runner_summary.v0`;
- status: `post_runtime_live_candidate_evidence_ready`;
- controlled fixture expected movement: met;
- controlled fixture actual order changed count: `1`;
- gated store status: `transition_gate_consumed`;
- gated store runs BioCortex: `true`;
- gated store protected order changed: `true`;
- gated batch query count: `1`;
- gated batch actual order changed count: `1`;
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

That status result is expected for this artifact type. The status readiness
surface accepts no-order-change readiness evidence, while this runner proves
protected explicit opt-in order movement.

## Boundary

This runner preserves the existing boundaries:

- writes only to the selected output directory and non-production DB;
- requires compile feature `biocortex-retrieval-opt-in`;
- requires runtime env `AB_BIOCORTEX_RETRIEVAL_OPT_IN=1`;
- requires explicit per-call opt-in;
- respects operator disable `AB_BIOCORTEX_RETRIEVAL_DISABLE`;
- consumes the post-runtime-backed transition gate;
- keeps default `memory_search`, hybrid search, semantic search, approval
  writes, and default search order unchanged.

## Next Step

The next useful step is to expand this from the canonical one-query
live-candidate fixture to a multi-query non-production corpus, while keeping
the same runner-style assertions and redaction checks.
