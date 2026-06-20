# Memory Continuity T5/T6 Evidence Surfaces

Date: 2026-06-19

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
```

The feature-branch commit hook also ran `cargo check -p ab-bridge --all-targets`.

The broad `cargo fmt --check` path is not a clean signal for this slice: the
same checkout contains pre-existing rustfmt diffs in unrelated files/regions.
This slice keeps edits localized and does not run whole-file formatting to avoid
mixing unrelated churn into the review.
