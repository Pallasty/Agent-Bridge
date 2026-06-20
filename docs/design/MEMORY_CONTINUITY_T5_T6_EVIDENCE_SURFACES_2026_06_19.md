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
```

The feature-branch commit hook also ran `cargo check -p ab-bridge --all-targets`.

The broad `cargo fmt --check` path is not a clean signal for this slice: the
same checkout contains pre-existing rustfmt diffs in unrelated files/regions.
This slice keeps edits localized and does not run whole-file formatting to avoid
mixing unrelated churn into the review.
