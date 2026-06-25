# Memory Continuity T5/T6 Evidence Surfaces

Date: 2026-06-19

Related local authorization ledger:
`MEMORY_AUTHORIZATION_CONTRACTS_2026_06_25.md`.

## Context

The first live T5/T6 batch after MCP reconnect produced useful shadow evidence,
but T6 stayed blocked because two review inputs were missing:

- a formal redacted evidence aggregate;
- a relevance-lift eval that T6 can consume without raw per-sample memory keys.

The existing BioCortex relevance-lift evaluator is intentionally more detailed
and includes per-sample rows for offline review. That is too much payload for the
Codex-essential continuity path, where T6 should consume only aggregate fields.

## Change

Two read-only Standard MCP tools bridge the gap:

- `memory_biocortex_redacted_evidence_aggregate`
- `memory_biocortex_relevance_lift_summary`

`memory_biocortex_redacted_evidence_aggregate` consumes redacted
`memory_biocortex_shadow_trial` packets and emits the aggregate schema expected
by `memory_biocortex_t6_influence_gate`:

```text
agent_bridge.biocortex_retrieval.opt_in_redacted_evidence_aggregate.v0
```

It never calls `memory_search`, runs BioCortex, writes memory, echoes shadow
packets, exposes raw query/key/content, or changes retrieval order.

`memory_biocortex_relevance_lift_summary` calls the existing relevance-lift
yardstick, then strips per-sample rows and raw side-signal errors. It returns
only schema/status/verdict, sampling, metrics, caveats, safety, and a redaction
contract. It is still read-only and does not change production retrieval order.

## Boundary

These tools are evidence surfaces, not influence surfaces.

They do not:

- approve runtime influence;
- enable default retrieval-order changes;
- write approval records;
- write memory or graph edges;
- claim BioCortex discovered selection.

T6 remains the gate. Even when these two inputs are present and valid,
`memory_biocortex_t6_influence_gate` can only report readiness for human opt-in
experiment review. It still reports `runtime_influence_approved=false` and
`may_change_search_order_now=false`.

## Evidence Strength Follow-up

Date: 2026-06-20

The post-reconnect stratified lift matrix showed that rank movement is broad but
measured relevance lift is weak and concentrated in `session_handoff` evidence.
That is useful for a narrow opt-in review path, but easy to misread as broad
memory-readiness evidence.

T6 now emits an `evidence_strength` block with:

- `tier`: `blocked`, `weak_narrow_lift`, or `review_ready`;
- `improved_rate`, alongside evaluated/improved/unchanged/worsened counts;
- `kind_filter` and `sort` copied from the redacted lift summary metadata;
- `review_caveats`, including low sample count, weak MRR margin, low improved
  rate, narrow kind-stratified evidence, or unstratified evidence.

T6 also accepts optional stricter thresholds:

- `min_improved_count`
- `min_improved_rate`

These thresholds can block weak positive lift without changing the default
runtime boundary. Even when evidence is strong enough for review, T6 still does
not approve runtime influence or retrieval-order changes.

## Hard Query Fixture Follow-up

Date: 2026-06-20

`memory_biocortex_relevance_lift_summary` now has a checked-in downstream-query
fixture:

```text
docs/design/fixtures/memory-biocortex-relevance-lift-hard-query-cases-2026-06-20.json
```

The fixture supplies operator-labelled `query_cases`: each case has a
downstream-style query, a set of known relevant memory keys, and a sanitized
class label. This closes the main weakness of self-retrieval sampling: the query
is no longer derived from the target memory itself.

The fixture is intentionally a local-memory evidence fixture, not a deterministic
unit-test corpus. Different machines may lack one of the referenced memory keys
or have different BioCortex side-signal availability. The invariant contract is
the summary surface:

- `sampling.query_source` must be `explicit_cases`;
- `sampling.query_cases_count` should match the valid fixture cases supplied;
- summary output must not include raw queries, raw relevant keys, memory content,
  per-sample rows, or raw side-signal errors;
- the tool remains read-only and cannot change production retrieval order.

Use this fixture as the next T6 evidence-strength step before deciding whether a
lean-safe Codex entrypoint is worth exposing. The default `codex-lean` toolset
should remain unchanged until the fixture shows repeatable value.

Current Mac verification caveat: the fixture smoke validates the redacted summary
contract, but the local sibling `/Users/pallasting/Projects/biocortex-rs`
checkout is behind and lacks the `ab_retrieval_side_signal_adapter` example.
That makes the hard-query run report `side_signal_unavailable`; it should not be
read as negative relevance-lift evidence. A clean, up-to-date BioCortex checkout
is required before using this fixture as a lift-quality measurement.

Follow-up with a clean detached BioCortex worktree at
`/Users/pallasting/.cache/agent-bridge-biocortex-rs-verify` (origin/main
`b7b3509`) removed the adapter caveat. The same fixture ran with
`side_signal_unavailable=0`, `evaluated_count=3`, and
`runs_biocortex_adapter=true`, while still preserving the summary redaction
contract. The measured verdict was `no_lift`: `mrr_baseline=1.0`,
`mrr_reordered=1.0`, `mrr_lift=0.0`, `improved=0`, `worsened=0`,
`unchanged=3`, and `order_changed_count=1`.

Interpretation: this first fixture is a valid contract smoke, not a useful lift
yardstick. Baseline FTS already ranks the chosen source memories at the top, so
there is little or no headroom for a side-signal to improve rank. The next
evidence step should build a held-out hard-query corpus whose acceptance
criteria include baseline source-rank headroom (for example: source found but
not already rank 1) before treating T6 lift as quality evidence.

## Headroom Fixture Follow-up

Date: 2026-06-20

The next evidence step now reuses the existing drift-free `recall_eval` harness
instead of adding a second baseline mechanism. On the current Mac state DB:

```bash
AGENT_BRIDGE_ONNX_MODEL=para-ml cargo run -p ab-bridge --example recall_eval
```

returned:

- overall FTS: `R@1=0.278`, `R@5=0.556`, `R@10=0.667`, `MRR=0.384`;
- hard-tier FTS: `R@1=0.000`, `R@5=0.125`, `R@10=0.375`, `MRR=0.073`;
- semantic was skipped because the real model was not confirmed within the
  readiness probe timeout, which is acceptable for this T6 rank-lift fixture
  because the relevance-lift evaluator's baseline candidate list is FTS.

The checked-in headroom fixture is:

```text
docs/design/fixtures/memory-biocortex-relevance-lift-headroom-cases-2026-06-20.json
```

Its selection rule is explicit: include only `recall_eval` cases where the first
relevant FTS hit is present in the top 10 and `baseline_fts_rank_observed > 1`.
That keeps this fixture focused on reorder lift. Pure FTS misses remain valuable
recall-expansion evidence, but they are not a fair rank-lift yardstick unless
the evaluator can introduce new candidate memories.

The selected cases are `recall_eval` #4, #5, #7, #10, #13, #15, and #18, with
observed baseline FTS ranks 7, 9, 3, 2, 3, 4, and 4. This gives BioCortex a
measurable opportunity to improve MRR while still preserving the same redacted
summary contract as the hard-query smoke fixture: raw queries, raw keys, memory
content, per-sample rows, and raw side-signal errors must stay out of the MCP
summary.

Clean BioCortex checkout smoke with
`/Users/pallasting/.cache/agent-bridge-biocortex-rs-verify` preserved the
redacted summary contract and confirmed the adapter path is available:
`side_signal_unavailable=0`, `evaluated_count=7`,
`runs_biocortex_adapter=true`, `raw_query_leaked=false`, and
`raw_key_leaked=false`. The measured relevance result is still negative for
quality gating: `verdict=no_lift`, `mrr_baseline=0.267`,
`mrr_reordered=0.267`, `mrr_lift=0.0`, `improved=0`, `worsened=0`,
`unchanged=7`, `order_changed_count=2`, and `source_found_count=6`.

Interpretation: the headroom fixture is now good enough as a stricter T6
yardstick, and it shows current BioCortex side-signal evidence is not yet strong
enough to justify influence. The next useful work is not to loosen T6; it is to
improve the side-signal/candidate scoring path or add a separate
recall-expansion experiment for the pure FTS misses.

## Recall-Expansion Graph-Holdout Sampler

Date: 2026-06-20

`memory_biocortex_recall_expansion_summary` now has an optional
`sample_graph_holdout=true` mode for the separate recall-expansion question:
when baseline FTS does not return a relevant memory, can direct graph neighbors
of the baseline candidates recover one?

The sampler is deliberately weakly labelled. It derives cases from existing
memory graph edges by selecting a source memory, building a sanitized query from
that source content, and treating one direct neighbor as the held-out relevant
target. This is less handpicked than the earlier one-off smoke case, but it is
not a gold human relevance corpus. It should be read as a graph-recovery
yardstick and candidate generator for review, not as authorization for runtime
influence.

The output keeps the same redaction and authority boundary as explicit
`query_cases`:

- `sampling.query_source=graph_holdout_sample`;
- raw source queries, source keys, target keys, and memory content are not
  returned;
- case rows include only hashes, counts, `case_source`, status, and aggregate
  graph-neighbor evidence;
- `telemetry_top_miss_query_hashes_included=false`, because this path samples
  graph structure, not historical mixed-version query logs;
- `read_only=true`, `writes_memory=false`, `writes_state=false`,
  `runs_biocortex=false`, and `changes_search_order=false`.

Use this sampler before any candidate-expansion experiment to estimate whether
existing graph structure contains recoverable neighbors for baseline misses. Do
not use it to approve edge materialization, default search-order changes, or
BioCortex influence; those still require the separate review and T6 gates.

## Recall-Expansion Candidate Set Evaluation

Date: 2026-06-20

`memory_biocortex_recall_expansion_summary` also reports an offline candidate
set view named `baseline_then_graph_neighbors`. For each case, the report
constructs a hypothetical redacted candidate list by keeping baseline FTS
candidates first and appending direct graph-neighbor candidates that are not
already in baseline. It then returns only aggregate/count/hash fields:

- `expanded_candidate_count`;
- `expanded_relevant_count`;
- `expanded_first_relevant_position`;
- `expanded_candidate_order_hash`;
- aggregate `expanded_hit_count`, `candidate_expansion_added_hit_count`, and
  `candidate_expansion_added_hit_rate`.

This is still a yardstick, not an online ranking policy. The position field is
the position in the hypothetical appended list, not a scored production rank.
The surface does not expose raw queries, keys, candidate contents, edge payloads,
or raw errors. It also keeps the same authority boundary:
`changes_candidate_set_now=false`, `changes_search_order=false`,
`changes_prod_retrieval_order=false`, `writes_memory=false`, and
`runs_biocortex=false`.

The fixed `recall_eval` harness now includes the same offline candidate-set
view as a local drift-free yardstick:

```bash
AGENT_BRIDGE_ONNX_MODEL=para-ml cargo run -p ab-bridge --example recall_eval
```

Current Linux live-store run on 2026-06-20:

- baseline FTS over the 18-case fixed corpus: `R@1=0.222`, `R@5=0.611`,
  `R@10=0.778`, `MRR=0.386`;
- offline `fts+graph` candidate expansion: `hit=0.833`, `added=1`,
  `added_hit_rate=0.250` over four FTS misses, `MRR=0.390`;
- the added hit was case #9, where the relevant memory was not in FTS top 10
  but appeared at appended candidate position 13 after direct graph-neighbor
  expansion;
- the example explicitly prints that baseline FTS order is preserved, graph
  neighbors are only appended and deduped, and live `memory_search` candidates
  or ranking are not changed.

Interpretation: the current graph has a real but narrow recall-expansion signal
on the fixed corpus. This supports further candidate-expansion experiment
design, but it is not authorization for default retrieval influence.

## Candidate-Expansion Review Gate

Date: 2026-06-20

`memory_biocortex_t6_influence_gate` now has a separate candidate-expansion
review path. In addition to the existing BioCortex rank-lift inputs, the gate
can consume a redacted `memory_biocortex_recall_expansion_summary` via
`recall_expansion_summary` with
`candidate_expansion_review_requested=true`.

This path is intentionally independent from the rank-lift opt-in decision:

- `ready_for_opt_in_experiment` still depends on shadow trials, relevance-lift
  evidence, and the redacted aggregate;
- `candidate_expansion_gate.ready_for_candidate_expansion_review` depends only
  on the redacted recall-expansion summary and candidate-expansion thresholds;
- `candidate_expansion_gate.candidate_expansion_experiment_approved=false`;
- `candidate_expansion_gate.may_expand_candidate_set_now=false`;
- `candidate_expansion_gate.changes_candidate_set_now=false`;
- the output does not echo recall summary `case_rows`, raw queries, keys, or
  content.

Default recall-expansion review thresholds are deliberately small because this
is still a review gate, not runtime authority: at least 8 evaluated cases, at
least one baseline miss, at least one added hit, added-hit rate at least 0.10,
and zero recall-summary search errors. Callers can raise these thresholds for a
stricter fixed-corpus or graph-holdout review.

Interpretation: this turns the current #9 fixed-corpus signal into a formal
human-review packet boundary. It still does not permit default candidate-set
expansion, BioCortex influence, memory writes, edge writes, or search-order
changes.

## Candidate-Expansion Review Packet

Date: 2026-06-21

`memory_biocortex_t6_candidate_expansion_review_packet` consumes a
`memory_biocortex_t6_influence_gate` output and emits a bounded human-review
packet for candidate-expansion review. It extracts only the aggregate
`candidate_expansion_gate` fields: readiness, block reasons, metrics,
thresholds, evidence-strength tier/caveats, and the next gate.

The packet is a review artifact, not an execution path:

- it never calls `memory_search`, `memory_neighbors`, or BioCortex;
- it never writes memory, graph edges, authorization rows, or approval packets;
- it never echoes the source gate, recall-expansion summary, `case_rows`, raw
  queries, raw keys, or content;
- it always forces `candidate_expansion_experiment_approved=false`,
  `may_expand_candidate_set_now=false`, and `changes_candidate_set_now=false`;
- if the source gate claims runtime candidate-expansion authority, the packet
  records a `source_gate_claims_candidate_expansion_authority` warning instead
  of preserving that claim.

Interpretation: this gives reviewers a stable handoff after the T6 gate and
before any separate owner-approved dry-run experiment plan. It keeps the current
v36 retrieval-trigger FTS projection as the first-stage baseline and leaves
candidate-set expansion behind a distinct future approval boundary.

## Candidate-Expansion Dry-Run Plan

Date: 2026-06-21

`memory_biocortex_t6_candidate_expansion_dry_run_plan` consumes a
`memory_biocortex_t6_candidate_expansion_review_packet` output and emits a
bounded sampling contract for a later dry-run executor. It exists to turn the
current weak/narrow candidate-expansion review signal into an explicit
less-handpicked baseline-miss corpus requirement before any runtime path exists.

The plan is deliberately not an executor:

- it never calls `memory_search`, `memory_neighbors`, or BioCortex;
- it never samples production memories or graph rows by itself;
- it never writes memory, graph edges, authorization rows, or approval packets;
- it never echoes the review packet, source gate, recall summary, case rows,
  raw queries, raw keys, or content;
- it always forces `candidate_expansion_experiment_approved=false`,
  `may_run_candidate_expansion_dry_run_now=false`,
  `may_expand_candidate_set_now=false`, and
  `changes_candidate_set_now=false`;
- it requires a separate owner decision before any dry-run executor is run and a
  separate post-dry-run decision before any runtime candidate-set expansion path
  exists.

The default sampling contract requires at least 30 redacted dry-run cases,
deterministic sampling seed, redacted case ids, baseline-miss strata,
graph-neighbor recovery strata, trigger-projection strata, and negative
controls. This is meant to prevent candidate expansion from winning by
construction on handpicked recovery examples.

Interpretation: this is the next handoff after the review packet. It can make a
future dry-run experiment auditable, but it still does not authorize running that
dry run or changing the live candidate set.

## Candidate-Expansion Dry-Run Report

Date: 2026-06-21

`memory_biocortex_t6_candidate_expansion_dry_run_report` is the next read-only
contract layer after the dry-run plan. It consumes a
`memory_biocortex_t6_candidate_expansion_dry_run_plan` output plus an
already-produced redacted `memory_biocortex_recall_expansion_summary`, and emits
aggregate evidence for human review.

`memory_biocortex_recall_expansion_summary` keeps its detailed default output
for inspection, but now accepts `include_case_rows=false` to emit an
aggregate-only summary. That mode keeps metrics, class aggregates, safety flags,
and input-contract flags while omitting `case_rows`; it exists so the dry-run
report can consume the summary without ever receiving per-case rows. It does not
change production retrieval, expand live candidate sets, or grant runtime
authority.

The report is deliberately not a sampler or executor:

- it never calls `memory_search`, `memory_neighbors`, or BioCortex;
- it never samples production memories or graph rows;
- it never writes memory, graph edges, authorization rows, or approval packets;
- it never echoes the source dry-run plan, recall-expansion summary, `case_rows`,
  raw queries, raw keys, content, or raw errors;
- it blocks source plans or summaries that claim runtime authority or expose raw
  payload fields;
- it always forces `candidate_expansion_experiment_approved=false`,
  `may_run_candidate_expansion_dry_run_now=false`,
  `may_expand_candidate_set_now=false`, and
  `changes_candidate_set_now=false`.

The default gate expects the redacted summary to satisfy the plan's minimum
dry-run case count, contain at least one baseline-miss stratum, and have zero
search errors. Passing this report only means the dry-run evidence is ready for
human review. It still requires a separate post-dry-run decision before any
runtime candidate-set expansion path exists.

Interpretation: this creates a safe place to compare a broader, less-handpicked
baseline-miss corpus against the existing v36 FTS baseline and graph-neighbor
candidate expansion evidence. It does not grant candidate-expansion authority.

## Candidate-Expansion Human-Review Packet

Date: 2026-06-21

`memory_biocortex_t6_candidate_expansion_human_review_packet` is the next
read-only contract layer after the dry-run report. It consumes only the safe
aggregate fields from `memory_biocortex_t6_candidate_expansion_dry_run_report`
and prepares a post-dry-run human decision surface.

The packet exists to make the boundary explicit:

- it verifies the source report schema, ready state, and authority-denial
  contract;
- it carries forward aggregate metrics, sampling-contract facts, and
  evidence-strength caveats;
- it lists human decision options such as requesting more evidence, rejecting
  the path, or approving the next design gate only;
- it never echoes the dry-run report, dry-run plan, recall-expansion summary,
  `case_rows`, raw queries, raw keys, content, or raw errors;
- it always forces `candidate_expansion_experiment_approved=false`,
  `may_run_candidate_expansion_dry_run_now=false`,
  `may_expand_candidate_set_now=false`, and
  `changes_candidate_set_now=false`.

Interpretation: a ready human-review packet means the evidence is presentable
for owner/operator judgment. It is not an authorization record and does not
create any runtime candidate-set expansion path.

## Candidate-Expansion Owner-Decision Record

Date: 2026-06-21

`memory_biocortex_t6_candidate_expansion_owner_decision_record` is the next
read-only contract layer after the human-review packet. It consumes a safe
`memory_biocortex_t6_candidate_expansion_human_review_packet` plus an explicit
external owner decision and records the next disposition.

Supported owner decisions are deliberately narrow:

- `request_more_redacted_dry_run_evidence`;
- `reject_candidate_expansion_path`;
- `approve_next_design_gate_only`.

The third option is intentionally named as a design gate, not an experiment or
runtime approval. It can only request follow-up design/preflight work for a
separate runtime gate. It does not authorize dry-run execution, search-order
changes, memory writes, BioCortex execution, or live candidate-set expansion.

The record requires an owner identity and a decision source, such as a forum
post, issue, or signed review note. This does not cryptographically prove human
approval, but it prevents silent model-only progression from looking equivalent
to an externally sourced owner decision.

The record never echoes the source human-review packet, dry-run report,
dry-run plan, recall-expansion summary, `case_rows`, raw queries, raw keys,
content, or raw errors. It always forces
`candidate_expansion_experiment_approved=false`,
`may_run_candidate_expansion_dry_run_now=false`,
`may_expand_candidate_set_now=false`, and
`changes_candidate_set_now=false`.

Interpretation: this is a review ledger surface for the owner/operator decision.
It may allow the next design/preflight artifact to be written, but it still does
not create runtime candidate-expansion authority.

## Candidate-Expansion Runtime-Gate Preflight

Date: 2026-06-21

`memory_biocortex_t6_candidate_expansion_runtime_gate_preflight` is the
design-only preflight surface after the owner-decision record. It consumes only
a safe `memory_biocortex_t6_candidate_expansion_owner_decision_record`.

The preflight blocks unless the source record is ready and the owner decision is
`approve_next_design_gate_only` with `next_design_gate_requested=true`. This
means ordinary continuation, evidence requests, or rejected paths cannot silently
turn into runtime gate work.

Even when ready, the preflight only allows a future design artifact. It requires
a separate runtime gate, separate owner runtime approval, feature flag default
off, shadow mode first, deterministic replay fixtures, bounded candidate delta,
negative controls, telemetry fields, and rollback planning.

The preflight never echoes the source owner-decision record, human-review
packet, dry-run report, dry-run plan, recall-expansion summary, `case_rows`, raw
queries, raw keys, content, or raw errors. It always forces
`may_implement_runtime_gate_code_now=false`,
`candidate_expansion_experiment_approved=false`,
`may_run_candidate_expansion_dry_run_now=false`,
`may_expand_candidate_set_now=false`, and `changes_candidate_set_now=false`.

Interpretation: this is not a runtime gate. It is the checklist that a later,
separately approved runtime gate must satisfy before any code path can influence
candidate expansion.

## T6 Candidate Expansion Runtime-Gate Design Artifact

Date: 2026-06-21

`memory_biocortex_t6_candidate_expansion_runtime_gate_design_artifact` is the
owner-reviewable design surface after the runtime-gate preflight. It consumes
only a safe
`memory_biocortex_t6_candidate_expansion_runtime_gate_preflight`.

The artifact blocks unless the source preflight is ready, read-only, explicitly
permits only design-artifact preparation, carries the required runtime-gate
design requirements, and still denies runtime code, dry-run execution,
candidate-set expansion, runtime influence, and search-order changes.

Even when ready, the artifact only prepares an owner review checklist. It names
the separate runtime gate, separate owner runtime approval, feature flag default
off, shadow mode first, deterministic replay, bounded candidate delta, negative
controls, telemetry fields, and rollback contract that must exist before a
future implementation path can be considered.

The artifact never echoes the source preflight, owner-decision record,
human-review packet, dry-run report, dry-run plan, recall-expansion summary,
`case_rows`, raw queries, raw keys, content, or raw errors. It always forces
`may_implement_runtime_gate_code_now=false`,
`candidate_expansion_experiment_approved=false`,
`may_run_candidate_expansion_dry_run_now=false`,
`may_expand_candidate_set_now=false`, and
`this_artifact_approves_runtime_candidate_expansion=false`.

Interpretation: this is still not a runtime gate and not runtime code. It is the
design artifact that a separate owner runtime approval must review before any
candidate-expansion implementation can be started.

## T6 Candidate Expansion Runtime-Gate Owner Review Record

Date: 2026-06-21

`memory_biocortex_t6_candidate_expansion_runtime_gate_owner_review_record` is
the explicit owner-review surface after the runtime-gate design artifact. It
consumes only a safe
`memory_biocortex_t6_candidate_expansion_runtime_gate_design_artifact` plus an
external owner decision.

The only positive owner decision accepted by this surface is
`approve_runtime_gate_implementation_plan_only`. That opens the next
implementation-plan gate, not runtime code. Requests for design changes,
rejections, missing owner/source fields, unknown decisions, raw payloads, or any
source artifact that claims runtime authority all block.

Even when ready, the record only permits preparing an implementation plan. It
requires a separate implementation-plan artifact and a separate code
implementation gate before runtime code can be considered.

The owner-review record never echoes the source design artifact, preflight,
owner-decision record, human-review packet, dry-run report, dry-run plan,
recall-expansion summary, `case_rows`, raw queries, raw keys, content, or raw
errors. It always forces `may_implement_runtime_gate_code_now=false`,
`candidate_expansion_experiment_approved=false`,
`may_run_candidate_expansion_dry_run_now=false`,
`may_expand_candidate_set_now=false`, and
`this_record_approves_runtime_candidate_expansion=false`.

Interpretation: this is owner approval to prepare an implementation plan only.
It is still not runtime approval, not runtime code approval, and not
candidate-expansion approval.

## T6 Candidate Expansion Runtime-Gate Implementation Plan Artifact

Date: 2026-06-21

`memory_biocortex_t6_candidate_expansion_runtime_gate_implementation_plan_artifact`
is the read-only implementation-plan surface after the runtime-gate
owner-review record. It consumes only a safe
`memory_biocortex_t6_candidate_expansion_runtime_gate_owner_review_record` whose
owner decision is `approve_runtime_gate_implementation_plan_only`.

When ready, the artifact can only open the next code-gate review:
`author_review_runtime_gate_code_implementation_gate_before_code`. It specifies
a default-off feature flag, shadow-first contract, deterministic replay
fixture, bounded candidate delta, negative controls, telemetry fields, and
rollback contract that a later code gate must review before any runtime code is
implemented.

The implementation-plan artifact never echoes the owner-review record,
runtime-gate design artifact, preflight, owner-decision record,
human-review packet, dry-run report, dry-run plan, recall-expansion summary,
`case_rows`, raw queries, raw keys, content, or raw errors. It always forces
`may_implement_runtime_gate_code_now=false`,
`candidate_expansion_experiment_approved=false`,
`may_run_candidate_expansion_dry_run_now=false`,
`may_expand_candidate_set_now=false`, and
`this_plan_approves_runtime_candidate_expansion=false`.

Interpretation: this is an implementation plan for a future code gate only. It
is still not runtime code approval, not runtime approval, and not
candidate-expansion approval.

## T6 Candidate Expansion Runtime-Gate Code Implementation Gate

Date: 2026-06-21

`memory_biocortex_t6_candidate_expansion_runtime_gate_code_implementation_gate`
is the explicit code-gate surface after the implementation-plan artifact. It
consumes only a safe
`memory_biocortex_t6_candidate_expansion_runtime_gate_implementation_plan_artifact`
plus an external code-gate decision.

The only positive code-gate decision accepted by this surface is
`approve_shadow_runtime_gate_code_implementation_only`. That can authorize
implementing default-off, shadow-only runtime-gate code. It does not authorize
enabling that code, running shadow mode, running dry-runs, changing search
order, writing memory or graph edges, or expanding candidate sets.

Even when ready, the code implementation contract only sets
`may_implement_shadow_runtime_gate_code=true`. It always forces
`may_enable_runtime_gate_now=false`, `may_run_shadow_mode_now=false`,
`may_run_candidate_expansion_dry_run_now=false`,
`may_expand_candidate_set_now=false`,
`runtime_influence_approved=false`, and
`this_gate_approves_runtime_candidate_expansion=false`.

The code gate never echoes the implementation-plan artifact,
owner-review record, runtime-gate design artifact, preflight,
owner-decision record, human-review packet, dry-run report, dry-run plan,
recall-expansion summary, `case_rows`, raw queries, raw keys, content, or raw
errors. Separate shadow-execution and runtime-enable gates remain required.

Interpretation: this is approval to implement a default-off shadow code path
only. It is not approval to run the code, enable runtime influence, or expand
candidate sets.

## Fixture Diagnostic Example Follow-up

Date: 2026-06-20

The redacted MCP summary is intentionally too compact to explain *why* a
headroom run did or did not lift. A read-only local example now exposes the
per-case rank fields without adding a new MCP tool:

```bash
AB_BIOCORTEX_RS=/Users/pallasting/.cache/agent-bridge-biocortex-rs-verify \
  cargo run -p ab-bridge --example biocortex_relevance_lift_fixture_eval
```

The example uses the same `biocortex_retrieval_relevance_lift_eval` ruler and
defaults to the headroom fixture. It prints aggregate metrics plus redacted
per-case rows: observed fixture FTS rank, current baseline source rank,
reordered source rank, rank delta, reciprocal-rank delta, side-signal match
count, coverage, whether the ordering changed, source/accept-set side-signal
rank and score, top-side relevance, distinct side-score count, and top-score tie
count. It also prints adapter-input saturation fields: current adapter query
term count, distinct overlap count, top-overlap tie count, distinct competition
spike count, and top-spike tie count.

Current source-run result on this Mac:

- `verdict=lift_demonstrated`, but only weakly;
- `mrr_baseline=0.260`, `mrr_reordered=0.267`, `mrr_lift=0.007`;
- `improved=1`, `worsened=0`, `unchanged=6`;
- `source_found_count=6`;
- side-signal coverage was not the blocker: all evaluated rows reported
  `side_signal_coverage=1.0`;
- side-signal score saturation is the concrete blocker:
  - cases #1, #2, and #4 had only one distinct side score, so every candidate
    tied;
  - cases #3 and #6 each had 11 candidates tied at the top score;
  - case #5 had 19 candidates tied at the top score;
  - in the hard cases, `top_rel=false` despite full side-signal coverage;
- the saturation now localizes inside the adapter before AB blending:
  - current adapter tokenization leaves the Chinese-heavy queries with only
    1-3 ASCII terms (`qterm=1` for cases #1/#2/#4/#5);
  - cases #1/#2/#4 also tie at the overlap stage (`overlap_tie` equals all
    candidates) and the competition stage (`spike_tie` equals all candidates).

Rejected probe: a local-only `biocortex-rs` adapter experiment added CJK
bigram/trigram terms. It reduced ties (`distinct` rose to 5-13 in the hard
cases), but did not improve relevance: the same fixture returned
`verdict=no_lift`, `mrr_lift=0.0`, `improved=0`, `unchanged=7`. The probe was
not kept in the verification checkout. Conclusion: tokenization alone makes the
lexical proxy less saturated, but it still ranks the wrong memories. The next
useful fix is Track B: feed real AB memory graph/co-retrieval edge evidence into
the side-signal adapter instead of relying on query-candidate lexical overlap.

Interpretation: this is still not strong enough for T6 runtime influence. The
useful next scoring work is to inspect why high-coverage side signals mostly
move distractors or leave source ranks unchanged. Also note the measurement
distinction surfaced by the example: the fixture's `baseline_fts_rank_observed`
is first-hit over the accept set, while `baseline_rank_of_source` tracks the
first listed primary source key. Case #4 demonstrates the difference: the
accept-set hit exists, but the primary source key is absent from the baseline
candidate list. Do not loosen T6 based on this; improve side-signal score
normalization/discrimination first, and treat graph-evidence integration as the
likely scoring fix rather than a pure tokenizer tweak.

Track B graph-readiness follow-up: the same example now prints read-only
candidate-induced memory graph evidence. For each fixture case, it reuses the
baseline candidate set, reads `memory_neighbors` for those candidates, keeps
only edges where both endpoints are in the candidate set, and reports induced
edge/node coverage plus a simple incident-weight graph ranking. This still does
not change production retrieval order or add a new MCP tool.

Current Mac run showed that graph evidence exists but is not yet usable as a
naive ranker:

- induced candidate-internal edge counts were non-zero for every case: 10, 22,
  7, 3, 9, 4, and 10;
- induced node counts were 12, 10, 6, 3, 7, 5, and 10;
- `top_graph_relevant=false` for all seven cases;
- the primary source key only appeared in positive graph-score ranking for
  cases #5 and #7, at graph ranks 2 and 5 respectively;
- observed edge types were dominated by existing continuity/provenance-style
  edges such as `evolved` and `derived_from`.

Interpretation: Track B should not start by assuming graph coverage is absent.
The local store has edge signal, but the naive incident-weight projection mostly
promotes distractors. The next useful design slice is to diagnose edge-type
semantics, directionality, temporal weighting, and source/accept-set proximity
before feeding graph evidence into the BioCortex side-signal adapter.

The follow-up graph scoring variant run split the same candidate-induced edges
into five read-only projections: all incident edges, incoming-only edges,
outgoing-only edges, non-continuity/provenance edges, and continuity/provenance
edges only. The observed pattern was sharper:

- `incoming`/`outgoing` did not make the graph ranker generally relevant; both
  still missed the relevant key at the top in all seven cases;
- `cont_only` covered many nodes, but behaved like the all-edge score and still
  promoted distractors;
- `non_cont` was sparse, scoring 0, 2, 4, or 5 nodes depending on the case, but
  it was the only projection that put a relevant key at graph rank 1, in cases
  #5 and #7;
- cases #3, #4, and #6 had no non-continuity candidate-induced graph signal at
  all, so they cannot benefit from a non-continuity graph boost without better
  edge materialization.

Interpretation: directionality alone is not the missing piece. Continuity and
provenance edges (`evolved`, `derived_from`, and related maintenance edges) are
useful context for explainability, but too noisy for direct rank influence in
this fixture. A future adapter payload should treat non-continuity edges as the
first rank-signal candidate and continuity/provenance edges as auxiliary
evidence or a capped prior, while keeping zero-coverage cases explicitly
visible.

The next read-only simulation normalized each graph-variant score into a
`0..1` opt-in side signal, then fed it through the existing
`biocortex_opt_in_apply_side_signal` blend function with alpha `0.8` and
coverage threshold `0.0` so sparse graph signals could be measured. This tests
whether graph evidence is immediately useful as a rank boost without changing
production retrieval.

Current result:

- `all` changed six cases and worsened three, with average MRR delta `-0.060`;
- `cont_only` matched that negative pattern: six changed, three worsened, MRR
  delta `-0.060`;
- `incoming` was less harmful but still negative: one worsened, MRR delta
  `-0.019`;
- `outgoing` worsened three, MRR delta `-0.040`;
- `non_cont` was safest but not useful yet: four cases had available sparse
  signal, three changed order, none improved, none worsened, MRR delta `0.000`.

Interpretation: even the promising non-continuity projection is not ready to
become adapter influence by simple normalized-score blending. The graph evidence
line should now focus on a better graph feature, such as source/accept-set
proximity, edge-type-specific caps, or materializing co-retrieval/semantic
neighbor edges for the zero-signal cases. Do not wire raw graph incident scores
into BioCortex adapter influence yet.

The graph proximity/materialization preflight then checked whether the fixture
failures are really missing-edge problems:

- all seven cases already had at least one labelled relevant key in the
  baseline FTS candidate set, so this fixture is not blocked by candidate
  generation;
- only two of seven cases had a direct candidate-induced explicit graph edge
  touching a relevant key;
- three of seven cases could reach a relevant key through capped BFS from the
  top graph hubs;
- candidate-set coactivation did not support the labelled relevant keys in any
  case;
- semantic cosine did not place any labelled relevant key in the top 20
  (`embedding_rows=2783`), so this fixture does not justify materializing
  semantic-neighbor edges from query similarity alone.

Interpretation: do not start with semantic/coactivation materialization for this
fixture. The labelled relevant memories are already inside the baseline
candidate sets, but explicit graph evidence is too sparse and raw incident
weights are harmful. The next useful design should test a bounded graph
proximity feature: direct relevant-edge presence, BFS energy from graph hubs,
edge-type caps, and zero-signal fallback. Only after that should materialization
be revisited, ideally with a fixture where relevant memories are semantically
near but absent from explicit graph structure.

The bounded proximity simulation added one more read-only graph variant,
`bounded_prox`. It does not use fixture labels while scoring. It scores baseline
candidates from candidate-internal graph structure, applies low caps to
continuity/provenance edge types, chooses non-continuity hubs when available,
falls back to all graph hubs when not, and adds capped BFS energy back into the
candidate set. The relevance labels are used only after scoring to measure
rank-lift.

Current result:

- `bounded_prox` was available in all seven cases and changed six rankings;
- it improved zero cases, worsened three, and left four effectively unchanged;
- average MRR delta was `-0.025`;
- average blend coverage was `0.579`;
- this is less harmful than raw `all` / `cont_only` graph incident scores
  (`-0.060`), but still worse than sparse `non_cont`, which stayed neutral at
  `0.000`.

Interpretation: edge-type caps plus hub BFS are not sufficient for T6 influence
on this fixture. The next graph line should not keep tuning this bounded
proximity score in place. It should either (a) use `non_cont` as the conservative
no-harm baseline while looking for a real improvement signal, or (b) build a
separate materialization fixture where the problem is genuinely missing graph
structure rather than candidate ranking. `bounded_prox` remains useful as a
negative control in the local evaluator.

The missing-graph materialization fixture was then split out:

```text
docs/design/fixtures/memory-biocortex-relevance-lift-missing-graph-cases-2026-06-20.json
```

It keeps the same `query_cases` shape as the existing relevance-lift fixtures so
the local evaluator can run it directly with an explicit fixture path. Extra
`missing_graph_contract` and per-case `materialization_observation` fields are
documentation/test metadata only. They do not change retrieval, register a new
tool, or write graph edges.

Selection rule: keep only headroom cases where a labelled relevant memory is
already present in the baseline candidate set, but no candidate-induced direct
graph edge touches the relevant key. On the current Mac state DB, that yields
five cases.

Current run:

- relevance lift still comes only from the existing BioCortex lexical side
  signal: `mrr_baseline=0.247`, `mrr_reordered=0.257`, `mrr_lift=0.010`,
  `improved=1`, `worsened=0`, `unchanged=4`;
- graph preflight confirms the fixture boundary:
  `cases=5`, `missing_candidate=0`, `direct_edge=0`, `bfs_reachable=1`,
  `coactivation=0`, `semantic_top20=0`;
- raw graph and bounded graph boosts still fail as influence candidates:
  `all=-0.083`, `cont_only=-0.083`, `bounded_prox=-0.035`,
  `incoming=-0.027`, `outgoing=-0.057`, while sparse `non_cont=0.000`.

Interpretation: this fixture is now a better next yardstick than the full
headroom fixture for materialization design. It proves the current hard subset
is not blocked by candidate generation, and it avoids mixing in the two cases
that already have direct relevant graph edges. It does not prove that edge
materialization will help; it gives the next slice a clean target for asking
which missing edge candidates would be safe, explainable, and no-harm before any
write-capable materializer or T6 influence path is considered.

The first missing-edge candidate-generation simulation used the safest existing
source: explicit `MemoryRecord.related_keys`. For each fixture case, the local
evaluator only inspected the baseline candidate set, proposed a missing
`relates` edge when one candidate's `related_keys` named another baseline
candidate and no candidate-induced edge already existed, then simulated the
proposed edges in memory without writing `memory_edges`. Fixture labels were
used only after scoring to count whether a proposed edge touched a labelled
relevant memory.

Current result on the missing-graph fixture:

- the latest rerun had no lexical side-signal lift:
  `mrr_baseline=0.257`, `mrr_reordered=0.257`, `mrr_lift=0.000`,
  `improved=0`, `worsened=0`, `unchanged=5`;
- candidate generation found proposals in four of five cases;
- total proposed missing edges: `16`;
- only one case had a proposed edge touching a labelled relevant memory;
- total relevance-touching proposed edges: `1`;
- simulated materialization remained negative:
  - `related_mat`: available in four cases, changed four, improved zero,
    worsened three, average MRR delta `-0.043`;
  - `bounded_mat`: available in four cases, changed four, improved zero,
    worsened three, average MRR delta `-0.045`.

Interpretation: explicit `related_keys` are a safe provenance source, but they
are too broad to justify a write-capable materializer for this fixture. The next
slice should not build a writer. It should add a stricter read-only candidate
quality gate first, for example requiring the proposed edge to touch the
labelled accept set in fixture evaluation, to pass a no-harm simulation, and to
carry a stronger reason bucket than "candidate related_key exists". For
production, the equivalent gate must be label-free and based on author intent,
scope compatibility, edge type, temporal relation, or repeated retrieval
evidence.

The first quality-gate simulation stays inside the local fixture evaluator. It
uses labels only as an evaluation oracle: a proposed missing edge is selected
only when it touches the labelled accept set and a single-edge no-harm trial
does not reduce that case's blended reciprocal rank. This is deliberately not a
production gate, because production retrieval does not have labels.

Current result on the missing-graph fixture:

- selected edges: `1` of `16`, in one of five cases;
- blocked for no labelled relevance contact: `15`;
- blocked for single-edge harm after label contact: `0`;
- `gated_rel`: available in one case, changed one, improved zero, worsened
  zero, average MRR delta `0.000`, average blend coverage `0.100`.

Interpretation: the quality gate is useful as a fixture-level safety check
because it filters the broad `related_keys` candidate set down to the one edge
that at least touches labelled relevance and does not hurt the local simulation.
It still does not demonstrate lift, and it still does not justify a writer or
T6 influence. The next production-grade design must replace labels with
auditable label-free reasons: explicit author intent, project/scope
compatibility, edge type and direction, temporal/causal relation, repeated
co-retrieval evidence, and a per-edge no-harm shadow check before any
materialization path is considered.

The first production-shaped label-free gate prototype then removed labels from
selection. It kept the same explicit `related_keys` candidate source, required
active endpoint metadata, compatible memory scope, endpoint update timestamps
within 30 days, and a single-edge shadow trial that preserves the baseline top
three prefix. Labels were used only after scoring to evaluate relevance contact.

Current result on the missing-graph fixture:

- selected edges: `4` of `16`, all in one case;
- selected edges touching labelled relevance: `0`;
- blocked by endpoint metadata: `0`;
- blocked by scope compatibility: `1`;
- blocked by temporal distance: `0`;
- blocked by top-three shadow stability: `11`;
- `prod_gate`: available in one case, changed one, improved zero, worsened one,
  average MRR delta `-0.050`, average blend coverage `0.300`.

Interpretation: the production-shaped gate is safer than broad `related_keys`
materialization in volume, but it still selects the wrong edges on this fixture.
The negative result is stronger than the previous broad regression: simple
metadata checks plus prefix stability can look conservative while still pushing
distractors. Do not build a materialization preview or writer from these
signals alone. The next useful line is to add stronger label-free evidence
before selection, especially repeated co-retrieval, explicit edge intent from
saved continuity metadata, or an operator-authored candidate reason that can be
audited independently of fixture labels.

The repeated co-retrieval gate then tested the first stronger label-free signal.
It kept the same explicit `related_keys` candidate source, required a
`memory_coactivation` row between the proposed endpoints with count at least
two, and would then apply the same top-three shadow-stability check before
simulation. Labels again stayed evaluation-only.

Current result on the missing-graph fixture:

- selected edges: `0` of `16`;
- selected edges touching labelled relevance: `0`;
- blocked by missing repeated co-retrieval signal: `16`;
- blocked by top-three shadow stability after co-retrieval: `0`;
- no `co_ret_gate` blend variant was available because no candidate passed the
  repeated co-retrieval signal gate.

Interpretation: repeated co-retrieval is the right kind of production signal,
but the current telemetry does not contain it for this fixture's missing-edge
candidates. That blocks materialization just as strongly as the negative
metadata gate, but for a better reason: the system lacks evidence instead of
selecting distractors. The next useful work is not a writer; it is either a
co-retrieval telemetry fixture that proves repeated candidate-pair evidence can
exist, or an operator-authored candidate-reason packet format that records
explicit materialization intent before any edge write path.

The operator-authored reason-packet prototype then tested that second path, still
entirely inside the fixture evaluator. The fixture can now attach
`materialization_reason_packets` to a case. A candidate missing edge is selected
only when it has an active packet for the same endpoint pair, the packet's edge
type matches the candidate, the edge type is on a small allow-list
(`relates`, `implements`, `derived_from`), the packet carries non-empty
`reason_kind` and `rationale`, and the shadow run either preserves the top-three
prefix or changes it only by introducing one of the packet endpoints. Labels
remain evaluation-only.

Current result on the missing-graph fixture:

- selected edges: `1` of `16`, in one of five cases;
- selected edges touching labelled relevance: `1`;
- blocked by absent or invalid packet: `15`;
- blocked by endpoint-alignment shadow: `0`;
- `reason_pkt`: available in one case, changed one, improved one, worsened
  zero, average MRR delta `0.667`, average blend coverage `0.100`.

Interpretation: an operator-authored reason packet is the first label-free
prototype in this sequence that selects the same useful edge as the oracle gate
on the fixture. It is still not a writer design. The next safe step is a
read-only materialization preview artifact that shows the candidate edge,
reason packet, shadow decision, and before/after ranking evidence for human
approval, without changing retrieval or writing graph edges.

The first read-only materialization preview slice keeps that boundary and adds
the missing review packet to the local evaluator output. For each selected
reason-packet candidate, the preview row includes:

- candidate source: currently `explicit_related_keys`;
- gate: currently `reason_packet`;
- candidate edge endpoints and edge type;
- packet `reason_kind` and rationale;
- shadow alignment result;
- baseline and preview ranks for both endpoints;
- baseline and preview top-three ranking evidence;
- preview coverage and preview-order-change flag;
- explicit `writes_memory=false` and `changes_search_order=false`.

Current result on the missing-graph fixture:

- preview rows: `1`;
- selected preview case: `missing_graph_moderate_case_15`;
- selected preview edge type: `relates`;
- gate/source: `reason_packet` from `explicit_related_keys`;
- endpoint rank movement: `from_rank=2->1`, `to_rank=4->3`;
- shadow alignment: `true`;
- preview order changed: `true`;
- blend coverage: `0.200`;
- write boundary: `writes_memory=false`, `changes_search_order=false`.

Interpretation: this preview artifact is a human-review surface only. It makes
the reason-packet decision inspectable, but it still does not approve automatic
materialization, production retrieval influence, or memory graph writes.

The next slice turns that preview evidence into a stable export shape without
leaving the local evaluator boundary. `biocortex_relevance_lift_fixture_eval`
now accepts `--packet-json` and emits a dedicated read-only review packet
schema:

- schema: `agent_bridge.biocortex_retrieval.materialization_review_packet.v0`;
- packet state: `review_state=needs_human_review`,
  `approval_state=not_approved`, `default_decision=keep_preview_only`;
- hard boundaries: `read_only=true`, `writes_memory=false`,
  `writes_edges=false`, `changes_search_order=false`,
  `approval_writes_allowed=false`, `can_materialize_edges=false`;
- packet source: evaluator id, fixture path, fixture schema, query-case count;
- summary: preview-case count, preview-candidate count, reason-packet selected /
  relevant / blocked counts;
- candidate rows: case index, class label, optional fixture review intent,
  endpoint keys, edge type, reason-kind/rationale, top-three rank evidence,
  endpoint rank movements, alignment, and coverage.

Current result on the missing-graph fixture:

- packet candidate rows: `1`;
- packet preview cases: `1`;
- selected packet case: `missing_graph_moderate_case_15`;
- candidate edge: `palace_review_artifact_v1_slice_committed_20260619` ->
  `palace_review_artifact_external_patterns_20260618`;
- approval boundary: `approval_writes_allowed=false`,
  `can_materialize_edges=false`, `changes_search_order=false`.

Interpretation: the review packet is now a stable handoff artifact for later
Palace/UI integration, but it is still evidence-only and does not authorize a
writer or runtime influence.

The next safe step is now landed as a Palace-side read-only consumer of that
packet contract:

- default fixture packet:
  `docs/design/fixtures/memory-biocortex-materialization-review-packet-2026-06-20.json`;
- Palace route: `GET /api/materialization-review-artifact`;
- Palace default source override:
  `AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON=/abs/path/to/packet.json`;
- Palace wrapper schema:
  `agent_bridge.palace.materialization_review_artifact.v0`.

This Palace artifact does not generate candidates or write graph state. It only
loads a packet JSON, validates the hard read-only boundary
(`read_only=true`, `writes_memory=false`, `writes_edges=false`,
`changes_search_order=false`, `can_change_retrieval_order=false`,
`approval_writes_allowed=false`, `can_materialize_edges=false`), and exposes
summary/questions/candidate evidence through the existing Palace review panel.
The route also rejects packets whose candidate rows carry write-capable or
retrieval-order-changing flags, even when the packet-level boundary is read-only.

The next Palace slice adds a human decision layer over the same packet without
adding a materializer:

- decision route: `POST /api/materialization-review-decision`;
- approved-plan route: `GET /api/materialization-review-approved-plan`;
- decision record schema:
  `agent_bridge.palace.materialization_review_decision.v0`;
- decision inbox schema:
  `agent_bridge.palace.materialization_review_decision_inbox.v0`;
- approved plan schema:
  `agent_bridge.palace.materialization_approved_edge_plan.v0`;
- default private decision log:
  `$HOME/.agent-bridge-private/palace-review/materialization-review-decisions.jsonl`;
- decision log override:
  `AB_PALACE_MATERIALIZATION_REVIEW_DECISIONS=/abs/path/to/decisions.jsonl`.

The decision log is append-only JSONL and private like the orphan-review queue.
It records only operator decisions (`approve`, `defer`, `reject`) over candidate
`from_key` / `to_key` / `edge_type` triples. Approving a candidate does **not**
write `memory_edges` and does **not** grant production retrieval influence. It
only makes the read-only approved-plan endpoint list the candidate in a dry-run
plan with `dry_run=true`, `writes_edges=false`,
`changes_search_order=false`, `approval_writes_allowed=false`, and
`can_materialize_edges=false`.

The follow-up Palace apply slice keeps materialization separate from approval:

- apply route: `POST /api/materialization-review-apply`;
- apply response schema:
  `agent_bridge.palace.materialization_approved_edge_apply.v0`;
- apply audit schema:
  `agent_bridge.palace.materialization_approved_edge_apply_audit.v0`;
- default private apply audit:
  `$HOME/.agent-bridge-private/palace-review/materialization-approved-edge-apply.jsonl`;
- apply audit override:
  `AB_PALACE_MATERIALIZATION_APPROVED_EDGE_APPLY_AUDIT=/abs/path/to/apply.jsonl`;
- live apply confirmation phrase: `APPLY MATERIALIZATION EDGES`.

The route recomputes the approved plan from the packet plus decision log on each
call. `dry_run` defaults to `true`; dry-run responses report
`would_write_edges` and never write `memory_edges`. Live apply requires the
exact confirmation phrase. When unblocked, the first implementation only writes
approved `relates` edges through the existing `memory_link` path, records an
append-only private audit row, and still sets
`changes_search_order=false` / `can_change_retrieval_order=false`. The apply
route can make graph topology durable, but it still does not grant BioCortex
runtime influence or production retrieval-order authority.

The approved-plan surface is idempotence-aware after apply. It preserves
`approved_pair_count` as the count of approved review decisions, but computes
`would_write_edges` only for approved edges not already present in the live
memory graph. Already materialized links are marked with
`already_materialized=true`, `materialization_status=already_materialized`, and
are counted in `already_materialized_edge_count`; pending writeable links are
counted in `pending_materialization_edge_count`.

The T6 candidate-expansion runtime-gate code path now has a default-off shadow
runtime gate surface:

- MCP tool:
  `memory_biocortex_t6_candidate_expansion_shadow_runtime_gate`;
- schema:
  `agent_bridge.memory_biocortex_t6_candidate_expansion.shadow_runtime_gate.v0`;
- runtime enable env:
  `AB_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW`;
- operator disable env:
  `AB_BIOCORTEX_T6_CANDIDATE_EXPANSION_DISABLE`.

The tool is a status and contract surface only. It reports redacted counts for
baseline/expanded/added candidates, checks that deterministic replay,
candidate-delta bounds, negative controls, telemetry fields, and rollback are
present, and keeps the feature flag default-off. Even when the runtime env is
set, the tool reports `blocked_before_shadow_execution_gate` and keeps
`may_run_shadow_mode_now=false`, `may_expand_candidate_set_now=false`,
`changes_candidate_set_now=false`, `may_change_search_order_now=false`, and
`may_write_memory_or_graph_edges=false`. It does not call `memory_search`,
`memory_neighbors`, or BioCortex, does not echo raw query/key/content/case rows,
and does not grant runtime enablement or candidate-expansion authority. A
separate shadow-execution gate is still required before any shadow run.

The next T6 candidate-expansion gate is the author-reviewed shadow-execution
gate:

- MCP tool:
  `memory_biocortex_t6_candidate_expansion_shadow_execution_gate`;
- schema:
  `agent_bridge.memory_biocortex_t6_candidate_expansion.shadow_execution_gate.v0`;
- required source:
  the redacted JSON object from
  `memory_biocortex_t6_candidate_expansion_shadow_runtime_gate`;
- author decision:
  `approve_shadow_execution_only`.

This tool can only report whether a later shadow-only executor is allowed to
run against a redacted deterministic replay fixture with append-only telemetry.
It never runs shadow mode itself, never calls `memory_search`,
`memory_neighbors`, or BioCortex, never writes memory or graph edges, and never
approves production runtime influence. The gate blocks if the source shadow
runtime gate is not `blocked_before_shadow_execution_gate`, if the source
contains raw query/key/content/case rows, if deterministic replay, candidate
delta bounds, negative controls, rollback, or telemetry requirements are
incomplete, or if the source claims runtime candidate-set authority. Even when
ready, the contract keeps runtime candidate expansion, runtime search-order
changes, memory/edge writes, and runtime enablement as non-claims for later
gates.

The following T6 candidate-expansion surface is the shadow-only executor
preflight:

- MCP tool:
  `memory_biocortex_t6_candidate_expansion_shadow_executor_preflight`;
- schema:
  `agent_bridge.memory_biocortex_t6_candidate_expansion.shadow_executor_preflight.v0`;
- required source:
  the redacted JSON object from
  `memory_biocortex_t6_candidate_expansion_shadow_execution_gate`;
- scope:
  redacted deterministic replay fixture only, with bounded case count and
  append-only shadow telemetry.

The preflight only reports whether a later shadow-only executor invocation is
allowed. It never invokes the executor, never calls `memory_search`,
`memory_neighbors`, or BioCortex, never writes memory or graph edges, and never
approves production runtime influence. It blocks if the source shadow-execution
gate is not `ready_for_shadow_execution_only`, if the source or request includes
raw query/key/content/case rows, if the source claims runtime authority, if the
executor id, redacted fixture id, or telemetry sink is missing, or if the bounded
shadow-case count exceeds the preflight limit. Even when ready, production
candidate-set mutation, search-order changes, runtime enablement, memory writes,
and graph-edge writes remain non-claims for later gates.

The next surface is the shadow-only invocation report:

- MCP tool:
  `memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report`;
- schema:
  `agent_bridge.memory_biocortex_t6_candidate_expansion.shadow_executor_invocation_report.v0`;
- required source:
  the redacted JSON object from
  `memory_biocortex_t6_candidate_expansion_shadow_executor_preflight`;
- scope:
  redacted invocation summary only: run id presence, fixture id presence,
  append-only telemetry sink presence, bounded case counts, failed-case count,
  candidate-delta count, and negative-control regression count.

The report does not invoke the executor and does not run shadow mode. It only
validates that an external shadow-only invocation summary is bounded,
append-only, redacted, and sourced from a ready preflight report. It blocks if
the source preflight is not ready, if either the source or request includes raw
query/key/content/case rows, if the source claims runtime authority, if run
metadata is missing, if case counts exceed the preflight bound, if completed and
failed case counts do not sum to the shadow case count, if any executor failures
or negative-control regressions are present, or if the caller cannot assert
append-only telemetry and redacted-summary-only handling. Even when ready, the
only opened follow-up is shadow telemetry review; runtime influence, candidate
mutation, search-order changes, memory writes, graph-edge writes, and production
enablement remain later-gated non-claims.

The next surface is the shadow telemetry review:

- MCP tool:
  `memory_biocortex_t6_candidate_expansion_shadow_telemetry_review`;
- schema:
  `agent_bridge.memory_biocortex_t6_candidate_expansion.shadow_telemetry_review.v0`;
- required source:
  the redacted JSON object from
  `memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report`;
- scope:
  redacted aggregate telemetry review only: reviewer/source presence, telemetry
  window presence, bounded observed/reviewed case counts, failed-case count,
  candidate-delta count, negative-control regression count, redaction-violation
  count, append-only confirmation, and redacted-aggregate-only confirmation.

The telemetry review does not invoke the executor, run shadow mode, read raw
telemetry rows, call BioCortex or memory tools, write memory or graph edges, or
approve runtime influence. It only validates that a bounded redacted aggregate
shadow telemetry review is sourced from a ready invocation report. It blocks if
the source invocation report is not ready, if either the source or request
includes raw query/key/content/case rows, if the source claims runtime authority,
if reviewer or provenance metadata is missing, if the decision is not
`approve_shadow_telemetry_only`, if observed/reviewed counts are inconsistent or
exceed the source bound, if failures, negative-control regressions, or redaction
violations are present, or if the caller cannot assert append-only telemetry and
redacted-aggregate-only handling. Even when ready, the only opened follow-up is
a later runtime-enablement review; production runtime influence, candidate
mutation, search-order changes, memory writes, graph-edge writes, and candidate
expansion enablement remain later-gated non-claims.

The next surface is the runtime-enablement review:

- MCP tool:
  `memory_biocortex_t6_candidate_expansion_runtime_enablement_review`;
- schema:
  `agent_bridge.memory_biocortex_t6_candidate_expansion.runtime_enablement_review.v0`;
- required source:
  the redacted JSON object from
  `memory_biocortex_t6_candidate_expansion_shadow_telemetry_review`;
- scope:
  owner-decision preparation only: reviewer/source presence, decision-source
  presence, bounded telemetry counts inherited from the source review,
  append-only confirmation, redacted-aggregate-only confirmation, and a decision
  that can open only an owner runtime-enablement decision review.

The runtime-enablement review does not enable runtime behavior, implement
runtime-enablement code, run shadow mode, call BioCortex or memory tools, change
candidate sets or search order, write memory or graph edges, or approve
production candidate expansion. It blocks if the source shadow telemetry review
is not ready, if either the source or request includes raw query/key/content/case
rows, if the source claims runtime authority, if reviewer or provenance metadata
is missing, if the decision is not
`approve_owner_runtime_enablement_review_only`, if failures, negative-control
regressions, or redaction violations are present, or if append-only/redacted
aggregate handling is not confirmed. Even when ready, the only opened follow-up
is a later explicit owner runtime-enablement decision; runtime enablement,
runtime influence, candidate expansion, search-order changes, memory writes,
and graph-edge writes remain later-gated non-claims.

The next surface is the runtime-enablement owner decision record:

- MCP tool:
  `memory_biocortex_t6_candidate_expansion_runtime_enablement_owner_decision_record`;
- schema:
  `agent_bridge.memory_biocortex_t6_candidate_expansion.runtime_enablement_owner_decision_record.v0`;
- required source:
  the redacted JSON object from
  `memory_biocortex_t6_candidate_expansion_runtime_enablement_review`;
- scope:
  explicit owner decision recording only: owner presence, decision-source
  presence, bounded telemetry counts inherited from the source review,
  append-only confirmation, redacted-aggregate-only confirmation, and a decision
  that can open only a later preflight or implementation-plan review artifact.

The owner decision record does not enable runtime behavior, implement
runtime-enablement code, run shadow mode, call BioCortex or memory tools, change
candidate sets or search order, write memory or graph edges, or approve
production candidate expansion. It blocks if the source runtime-enablement
review is not ready, if either the source or request includes raw
query/key/content/case rows, if the source claims runtime authority, if owner or
decision-source metadata is missing, if the owner decision is not
`approve_runtime_enablement_preflight_or_plan_review_only`, if failures,
negative-control regressions, or redaction violations are present, or if
append-only/redacted aggregate handling is not confirmed. Even when ready, the
only opened follow-up is a later preflight or implementation-plan review
artifact; runtime enablement, runtime influence, candidate expansion,
search-order changes, memory writes, and graph-edge writes remain later-gated
non-claims.

## Verification

Targeted validation for this slice after `/Data` space was recovered:

```bash
CARGO_TARGET_DIR=/home/pallasting/.cache/agent-bridge-target-evidence-surfaces cargo test -p ab-bridge --lib memory_biocortex_ -- --nocapture
CARGO_TARGET_DIR=/home/pallasting/.cache/agent-bridge-target-evidence-surfaces cargo test -p ab-bridge --lib tool_policy_codex_essential_exposes_extras_list -- --nocapture
CARGO_TARGET_DIR=/home/pallasting/.cache/agent-bridge-target-t6-evidence-strength cargo test -p ab-bridge --lib memory_biocortex_ -- --nocapture
git diff --check
cargo test -p ab-bridge memory_biocortex_ -- --nocapture
cargo test -p ab-bridge tool_policy_codex_essential_exposes_extras_list -- --nocapture
cargo test -p ab-bridge --lib memory_biocortex_relevance_lift_hard_query_fixture_contract -- --nocapture
cargo test -p ab-bridge --lib memory_biocortex_relevance_lift_headroom_fixture_contract -- --nocapture
cargo test -p ab-bridge memory_biocortex_relevance_lift_missing_graph_fixture_contract -- --nocapture
AB_BIOCORTEX_RS=/Users/pallasting/.cache/agent-bridge-biocortex-rs-verify cargo run -p ab-bridge --example biocortex_relevance_lift_fixture_eval
AB_BIOCORTEX_RS=/Users/pallasting/.cache/agent-bridge-biocortex-rs-verify cargo run -p ab-bridge --example biocortex_relevance_lift_fixture_eval docs/design/fixtures/memory-biocortex-relevance-lift-missing-graph-cases-2026-06-20.json
rustfmt --edition 2024 crates/bridge/examples/biocortex_relevance_lift_fixture_eval.rs
python3 -m json.tool docs/design/fixtures/memory-biocortex-relevance-lift-missing-graph-cases-2026-06-20.json >/dev/null
CARGO_TARGET_DIR=/home/pallasting/.cache/agent-bridge-target-t6-materialization-preview cargo test -p ab-bridge --example biocortex_relevance_lift_fixture_eval reason_packet_gate_emits_read_only_materialization_preview -- --nocapture
CARGO_TARGET_DIR=/home/pallasting/.cache/agent-bridge-target-t6-materialization-preview cargo test -p ab-bridge memory_biocortex_relevance_lift_missing_graph_fixture_contract -- --nocapture
CARGO_TARGET_DIR=/home/pallasting/.cache/agent-bridge-target-t6-materialization-preview AB_BIOCORTEX_RS=/Data/CascadeProjects/biocortex-rs cargo run -p ab-bridge --example biocortex_relevance_lift_fixture_eval docs/design/fixtures/memory-biocortex-relevance-lift-missing-graph-cases-2026-06-20.json
CARGO_TARGET_DIR=/home/pallasting/.cache/agent-bridge-target-t6-materialization-preview cargo check -p ab-bridge --all-targets
CARGO_TARGET_DIR=/home/pallasting/.cache/agent-bridge-target-t6-materialization-review-packet cargo test -p ab-bridge --example biocortex_relevance_lift_fixture_eval materialization_review_packet_is_read_only_and_redacted -- --nocapture
CARGO_TARGET_DIR=/home/pallasting/.cache/agent-bridge-target-t6-materialization-review-packet cargo test -p ab-bridge --example biocortex_relevance_lift_fixture_eval reason_packet_gate_emits_read_only_materialization_preview -- --nocapture
CARGO_TARGET_DIR=/home/pallasting/.cache/agent-bridge-target-t6-materialization-review-packet cargo test -p ab-bridge memory_biocortex_relevance_lift_missing_graph_fixture_contract -- --nocapture
CARGO_TARGET_DIR=/home/pallasting/.cache/agent-bridge-target-t6-materialization-review-packet cargo run -p ab-bridge --example biocortex_relevance_lift_fixture_eval -- docs/design/fixtures/memory-biocortex-relevance-lift-missing-graph-cases-2026-06-20.json --packet-json
CARGO_TARGET_DIR=/home/pallasting/.cache/agent-bridge-target-t6-materialization-review-packet cargo check -p ab-bridge --all-targets
```

The feature-branch commit hook also ran `cargo check -p ab-bridge --all-targets`.

The broad `cargo fmt --check` path is not a clean signal for this slice: the
same checkout contains pre-existing rustfmt diffs in unrelated files/regions.
This slice keeps edits localized and uses single-file `rustfmt` only for the
local evaluator touched by the preview-artifact change.
