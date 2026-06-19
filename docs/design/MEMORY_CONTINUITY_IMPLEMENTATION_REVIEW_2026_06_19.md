# Memory Continuity Implementation Review - 2026-06-19

This packet summarizes the current AB memory-continuity branch for review and
merge planning. It covers the T0-T7 implementation slice only. It does not claim
that BioCortex has runtime authority over AB memory retrieval.

Review reconciliation note: the branch was transplanted onto `origin/master`
(`2abd93f`) in `/Data/CascadeProjects/agent-bridge-memory-continuity-review-20260619`.
The earlier `memory_continuity_baseline` MCP tool surface was removed because
T0 is now covered by the drift-free `recall_eval` harness already on master and
historical query telemetry is not a trustworthy current recall-quality metric.
After the Palace atlas spacing polish and the T0 recall-eval corpus increment
landed, this review branch merged latest `origin/master` (`f43b2c8`) before
final review.

## Scope

Working tree:

- `crates/bridge/src/mcp_tools.rs`
- `docs/design/MEMORY_CONTINUITY_IMPLEMENTATION_REVIEW_2026_06_19.md`
- `docs/design/MEMORY_CONTINUITY_T0_BASELINE_2026_06_19.md`
- `docs/design/MEMORY_CONTINUITY_T1_METADATA_2026_06_19.md`
- `docs/design/MEMORY_CONTINUITY_T2_BOOTSTRAP_KERNEL_2026_06_19.md`
- `docs/design/MEMORY_CONTINUITY_T3_RETRIEVAL_FEEDBACK_2026_06_19.md`
- `docs/design/MEMORY_CONTINUITY_T4_CONSOLIDATION_QUEUE_2026_06_19.md`
- `docs/design/MEMORY_CONTINUITY_T5_BIOCORTEX_SHADOW_TRIAL_2026_06_19.md`
- `docs/design/MEMORY_CONTINUITY_T6_INFLUENCE_GATE_2026_06_19.md`
- `docs/design/MEMORY_CONTINUITY_T7_NEURAL_CRITIC_SHADOW_EVAL_2026_06_19.md`

Topology preflight against `origin/master` found a merge base. The active review
branch is `codex/memory-continuity-review-20260619`; after merging latest
master, the branch contains the T1-T7 review commit plus a no-conflict merge of
the latest Palace/T0 work.

## Implemented Stages

T0, baseline:

- Keeps the baseline surface-free and relies on the master `recall_eval`
  held-out harness plus existing stats surfaces.
- Establishes that the first milestone measures deterministic memory retrieval
  before attempting learned influence.

T1, continuity metadata:

- Adds optional `continuity` input to `memory_save`.
- Encodes metadata in backward-compatible tags, avoiding a DB migration.
- Surfaces `continuity_metadata` from `memory_get`, `memory_search`, and
  `memory_list`.

T2, bootstrap kernel:

- Adds a bounded Continuity Kernel to `session_bootstrap`.
- Prioritizes state, constraints, procedures, evidence, preferences, warnings,
  and archive rows when continuity metadata is present.
- Keeps the kernel within a fixed section-level budget and continues to prepend
  `session_handoff` rows.

T3, retrieval feedback:

- Adds `memory_retrieval_feedback`.
- Records targeted feedback for useful, stale, missing, too-large, noisy,
  duplicate, and harmful retrieval outcomes.
- Writes compact feedback memory rows and graph edges to support later
  consolidation without changing search behavior immediately.

T4, consolidation queue:

- Adds `memory_consolidation_queue`.
- Produces a read-only candidate queue for stale rows, duplicates, missing
  context, oversized rows, high-feedback rows, and orphan-like graph hygiene
  cases.
- Does not mutate memory records or graph edges.

T5, BioCortex shadow trial:

- Adds `memory_biocortex_shadow_trial`.
- Projects deterministic AB retrieval and consolidation candidates into a
  redacted shadow packet suitable for external BioCortex comparison.
- Emits hash-only candidate/control order evidence and advisory metrics only.
- Does not run BioCortex and does not alter `memory_search`.

T6, BioCortex influence gate:

- Adds `memory_biocortex_t6_influence_gate`.
- Reviews T5-style redacted lift evidence for readiness.
- Can mark an experiment ready for opt-in review, but always keeps
  `runtime_influence_approved=false`, `ready_for_influence=false`, and
  `may_change_search_order_now=false`.

T7, neural critic shadow eval:

- Adds `memory_neural_critic_shadow_eval`.
- Evaluates externally produced neural critic labels against deterministic
  T3/T4 baseline labels on held-out stale, duplicate, missing, too-large, and
  ok cases.
- Does not run a model, does not write memory, and does not affect retrieval
  order.

## Safety Boundary

The branch deliberately separates three layers:

- Deterministic AB memory behavior: implemented and test-covered.
- BioCortex / neural advisory evidence: read-only, redacted, and shadow-only.
- Runtime influence over retrieval: explicitly denied by T5, T6, and T7 output
  contracts.

Current invariant:

- No T5/T6/T7 path changes `memory_search` order.
- No T5/T6/T7 path writes memory or graph edges.
- No BioCortex code is executed by the new AB memory-continuity tools.
- No neural model is executed by the T7 evaluator.

## Code Navigation

Primary implementation anchors in `crates/bridge/src/mcp_tools.rs`:

- T1 continuity metadata: constants near line 17883, parser near line 18023,
  tag encoding near line 18082, read projection near line 18162, `memory_save`
  schema near line 18194, `memory_get` projection near line 18570,
  `memory_search` projection near line 18650, and `memory_list` projection near
  line 18984.
- T3 retrieval feedback: source/content helpers near lines 20974 and 21004,
  tool schema near line 21035, tests near line 59965.
- T2 Continuity Kernel: bootstrap reason/tier helpers near line 21437, formatter
  near line 21508, session bootstrap insertion near line 22298, tests near lines
  46640 and 46679.
- T0 baseline: documented in
  `docs/design/MEMORY_CONTINUITY_T0_BASELINE_2026_06_19.md`; no new MCP tool
  surface is added for T0.
- T4 consolidation queue: queue builder near line 34538, tool section near line
  34700, tests near line 60117.
- T5 BioCortex shadow trial: tool section near line 34975, tests near line
  60260.
- T6 influence gate: schemas/helpers near line 35264, tool section near line
  35574, tests near line 60352.
- T7 neural critic shadow eval: schemas/helpers near line 35638, tool section
  near line 35882, tests near line 60524.
- Tool exposure/policy: Codex essential extras near line 41223, policy assertions
  near lines 50430 and 50538.

Reviewer checklist:

- Verify the new tool schemas describe read/write authority honestly.
- Verify T5/T6/T7 payload flags cannot be interpreted as permission to reorder
  retrieval or write memory.
- Verify T1 tag encoding is backward compatible with existing memories.
- Verify T2 kernel rows are bounded and do not replace existing handoff behavior.
- Verify tests assert both positive output shape and negative authority gates.

## Board Reconciliation

Thread #115 received a new BioCortex S93 anti-vacuity audit after T7 landed in
the working tree. The audit says S93 still has de-risk value, but its
candidate-set result can collapse to weight selection, so it is not enough to
prove outcome credit is irreducible to weight. S94 subsequently landed in the
BioCortex lane at `426245b` with a stricter candidate-set DIVERGE condition and
new substrate API work around `Synapse.consolidation_credit`.

Thread #89 records that S93 was landed and verified on BioCortex main, while
keeping non-claims explicit: supplied candidate set, controlled outcome replay,
no cognition, no planning, and no autonomous candidate-set discovery.

Impact on this branch:

- No code conflict is expected because this branch only touches AB
  `crates/bridge/src/mcp_tools.rs` and docs.
- The S93/S94 update strengthens the current AB boundary: T5/T6 must remain
  shadow/gate-only until S94-style evidence survives review.
- We should avoid BioCortex `src/lib.rs` and `Synapse` areas while S94 is active.

## Verification

Targeted tests run after the T7 implementation, and re-run after the review
navigation/checklist hardening:

- `cargo test -p ab-bridge memory_neural_critic_shadow_eval -- --nocapture`
  passed, 2 tests.
- `cargo test -p ab-bridge tool_policy_codex_essential_ -- --nocapture`
  passed, 3 tests.
- `cargo test -p ab-bridge memory_consolidation_queue -- --nocapture` passed,
  2 tests.
- `cargo test -p ab-bridge memory_retrieval_feedback -- --nocapture` passed,
  2 tests.
- `cargo test -p ab-bridge continuity -- --nocapture` passed, 7 tests.
- `cargo test -p ab-bridge memory_biocortex_ -- --nocapture` passed, 3 tests.
- `git diff --check -- crates/bridge/src/mcp_tools.rs
  docs/design/MEMORY_CONTINUITY_T7_NEURAL_CRITIC_SHADOW_EVAL_2026_06_19.md`
  passed before review reconciliation. Re-run after this packet's T0 surface
  cleanup before merge.
- Trailing-whitespace scan over T0-T7 docs and `mcp_tools.rs` found no matches.

Observed existing warnings during Rust tests:

- `mixed_script_confusables` in `crates/store/src/sqlite.rs`.
- `private_interfaces` around `ToolPolicy`.
- Existing dead-code warnings around `OPTION_E`.

These warnings predate the current memory-continuity slice and were not changed
by this work.

## Merge Risks

- `crates/bridge/src/mcp_tools.rs` is a large file, and this slice adds a large
  amount of code there. Review should focus on local contracts, tests, and
  policy registration rather than broad formatting churn.
- The T1 metadata approach uses tags for backward compatibility. That is a good
  first merge, but a future migration may still be warranted if continuity
  metadata becomes a high-volume query axis.
- Independent review found that `memories_fts` does not index tags. This is a
  safety positive because T1 tags cannot perturb current FTS ranking, but it also
  means `retrieval_trigger` is descriptive metadata only. If we want it to improve
  hard-tier cross-vocabulary recall, a later increment must index or project it
  into the searchable content path and prove the lift with `recall_eval` hard-tier
  before/after data.
- The T2 Continuity Kernel uses estimated section budgets, not measured
  tokenizer telemetry. T0 explicitly calls out section-level bootstrap token
  telemetry as a follow-up.
- T5/T6/T7 are intentionally advisory. Any later runtime influence path needs a
  separate opt-in experiment, review packet, and human gate.

## Review Questions

- Should this land as one branch because T1-T7 form one coherent architecture,
  or should it be split into deterministic memory changes (T1-T4) and advisory
  BioCortex/neural gates (T5-T7)?
- Is tag-based continuity metadata acceptable as the first persistence layer, or
  should a schema migration be required before merge?
- Should `retrieval_trigger` stay projection-only for this merge, with indexed
  recall behavior deferred to a measured hard-tier recall increment?
- Should the Continuity Kernel section budget be tightened now, or only after
  bootstrap token telemetry exists?

## Recommended Next Step

Prepare this branch for review as-is, with the explicit safety boundary above.
Do not add runtime BioCortex influence in this branch. The next implementation
lane should be either:

- a measured bootstrap token telemetry increment for T0/T2, or
- an indexed `retrieval_trigger` recall experiment evaluated on the `recall_eval`
  hard tier, or
- a held-out data producer for T7 critic labels, still with no write or ranking
  authority.
