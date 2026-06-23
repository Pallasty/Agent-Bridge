# Trigger Recall Baseline Acceptance Production Opt-In Design Review - 2026-06-23

Host: macOS `maxiaodeMac-Pro.local`

Review base: `cdf635d` (`docs(memory): align embedder gate with loader constraints`)

Scope: production-facing design review only. No runtime implementation, no MCP
tool registration, no default `memory_search` change, no memory writes, no graph
writes, no reindex, and no deploy behavior change.

Post-review integration note:

- After this review was written, GitHub commit `036ea17` implemented the
  approved Slice 1 read-only control plane.
- The implementation was merged into this tree and validated locally.
- Therefore `APPROVED-FOR-SLICE-1-IMPLEMENTATION` should be read as consumed by
  `036ea17`, not as a duplicate open claim.
- Current next gate is a post-implementation review / batch diagnostic decision
  before any gated baseline trial. `enforce_hold` remains `NO-GO`.

## Verdict

`APPROVED-FOR-SLICE-1-IMPLEMENTATION`.

The baseline acceptance evidence is strong enough to implement the first
read-only control-plane slice:

- `trigger_recall_opt_in_status`
- `trigger_recall_opt_in_runtime_transition_gate`

The review does not authorize the gated baseline trial yet, and it does not
authorize `enforce_hold`.

Current production boundary:

| Item | Review State |
|---|---|
| default `memory_search` behavior | `NO-GO` |
| hidden parameter on `memory_search` | `NO-GO` |
| read-only status surface | `GO` |
| read-only runtime transition gate | `GO` |
| gated baseline trial | `DEFERRED-UNTIL-SLICE-1-PROVES` |
| `enforce_hold` visible behavior | `NO-GO` |
| supplemental projected candidate trial | `OUT-OF-SCOPE` |

## Board And Repo Verification

Checked before writing this review:

- Thread #120 tail includes #3971 and #3972. No newer baseline-acceptance
  instruction supersedes the current opt-in design.
- Design digest shows #120 as the active controlling Goal C thread; no other
  design/general board thread carries a newer baseline-acceptance directive.
- Active `agent-bridge` presence shows only avatar heartbeat, no competing
  implementation owner.
- Local `master`, `origin/master`, and `github/master` were aligned at
  `cdf635d`.

Related board state:

- #3970 says the next useful aio2 lane is production-facing opt-in design review
  for baseline acceptance.
- #3972 records the embedder lane as separate and `LOADER-UPGRADE-FIRST`; it
  does not change the trigger baseline acceptance boundary.

## Reviewed Artifacts

Documents:

- `docs/reports/goal-c-u/2026-06-23-trigger-recall-baseline-acceptance-optin-runtime-design.md`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-runtime-opt-in-design-plan.md`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-baseline-acceptance-audit.md`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-runtime-shaped-audit.md`
- `docs/reports/goal-c-u/2026-06-23-goal-c-u-standing-report-refresh.md`

Code anchors:

- `crates/bridge/examples/trigger_recall_eval.rs`
- `crates/bridge/src/mcp_tools.rs` BioCortex opt-in status / transition-gate /
  gated-store-trial pattern

## Evidence Summary

The existing Aio2 baseline acceptance shadow audit reports:

| Metric | Value |
|---|---:|
| baseline-shadow R@10 | 0.857 |
| true hits lost by shadow gate | 0 |
| positive cases held | 0 |
| baseline false hits before shadow gate | 23 |
| baseline false hits after shadow gate | 0 |
| false hits removed by shadow gate | 23 |

The runtime-shaped supplemental audit reports:

| Metric | Value |
|---|---:|
| supplemental recovered baseline misses | 2 |
| runtime final lost baseline hits | 0 |
| supplemental false hits after gate | 0 |
| baseline false hits retained | 23 |
| runtime final false hits | 23 |

Read:

- baseline acceptance is useful for false-hit holding;
- supplemental projected recovery is a separate source problem;
- neither result improves the main held-out `recall_eval` hard tier by itself;
- therefore this line can only advance as explicit opt-in control-plane work.

## Design Findings

### Finding 1 - Separate Opt-In Surface Is Correct

The design correctly rejects changing default `memory_search` first.

Reason:

- production `memory_search` returns a bare array;
- a held query is not the same as an empty search;
- hidden post-filtering would blur query-intent policy, telemetry,
  coactivation, and output formatting;
- the BioCortex pattern already proves the safer shape: read-only gate first,
  explicit per-call opt-in, operator disable, redacted audit, and gated trial
  later.

Decision: keep default `memory_search` unchanged.

### Finding 2 - Slice 1 Should Not Call Store Search

Slice 1 is only:

- status;
- transition gate;
- readiness/eval-anchor consumption;
- no raw query/key/content;
- no baseline hit lookup;
- no coactivation;
- no access-count bump.

Required fields:

| Field | Requirement |
|---|---|
| schema | `agent_bridge.memory.trigger_recall.opt_in_runtime_transition_gate.v0` |
| read_only | true |
| mode | `fts` only |
| per_call_opt_in | required |
| operator enable env | reported |
| operator disable env | blocks |
| regression anchor | `aio2_trigger_recall_baseline_acceptance_shadow_20260623` |
| calls_memory_search | false |
| default_memory_search_unchanged | true |
| raw_query_included/raw_keys_included/content_included | false |

Decision: implement Slice 1 next.

### Finding 3 - Gated Baseline Trial Is Not Yet Authorized

The gated baseline trial may call store search, so it needs a prior transition
gate artifact and a separate review point.

Before Slice 2 can proceed, Slice 1 must prove:

- blocked gates cannot call `memory_search`;
- non-`fts` mode blocks;
- missing `per_call_opt_in` blocks;
- operator disable blocks;
- stale/missing regression evidence blocks;
- raw query/key/content is not echoed;
- default `memory_search` remains unregistered/unchanged.

Decision: defer `trigger_recall_opt_in_gated_baseline_trial` until a Slice 1
implementation exists and passes tests.

### Finding 4 - `enforce_hold` Must Stay Behind One More Review

The current evidence is enough to design held-query semantics, not enough to
make visible result suppression available.

Required before `enforce_hold`:

- Slice 2 gated baseline trial exists;
- redacted batch diagnostics over the 14 positive cases and negative controls;
- accepted queries preserve baseline order;
- held queries return explicit `held_by_query_intent`, not `[]`;
- no coactivation or access-count trace for withheld hits;
- operator-approved mode and operator-disable escape hatch are tested;
- board-visible review compares default baseline, allowed trial, held trial,
  and eval-only supplemental `union+cont`.

Decision: `enforce_hold` remains `NO-GO`.

## Open Question Resolutions

| Question | Review Resolution |
|---|---|
| first MCP surface name | Use `trigger_recall_opt_in_status` and `trigger_recall_opt_in_runtime_transition_gate`; avoid naming it as `memory_search_*` until the store trial exists. |
| `audit_only` include hits by default | For status/gate: no hits. For future single gated trial: returned visible hits only for accepted queries; batch diagnostics should default to counts/order hashes, not hit bodies. |
| pre-policy vs post-baseline for held queries | Slice 1 does not search. Slice 2 may search only after the transition gate allows and must use a wrapper that controls telemetry/coactivation. Future `enforce_hold` must support a pre-policy path if accurate baseline counts are not explicitly requested. |
| query-intent helper location | Keep Slice 1 in `ab-bridge`. For Slice 2, extract the deterministic query-intent helper into `ab-store` with copied tests if the store wrapper owns baseline search and response contract. |

## Required Implementation Shape For Slice 1

Minimum code changes:

- add a pure transition gate payload builder;
- add MCP schemas for status and transition gate;
- register in the appropriate non-standard profile only if the current tool
  surface policy requires a gated/diagnostic profile;
- add tests mirroring the BioCortex transition-gate tests:
  - schema is read-only;
  - required fields present;
  - raw input not echoed;
  - happy path allows only `fts` + `per_call_opt_in`;
  - non-`fts` blocks;
  - missing per-call opt-in blocks;
  - operator disabled blocks;
  - output says `calls_memory_search=false`.

Minimum validation:

```bash
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture
cargo check -p ab-bridge --examples
git diff --check
```

If the implementation touches MCP registry/profile exposure, also verify the
intended profile visibility explicitly.

## Next Step

Implementation state after reconciliation:

- `036ea17` implemented `trigger-recall-opt-in-slice1-status-transition-gate-v1`.
- The implementation report is
  `docs/reports/goal-c-u/2026-06-23-trigger-recall-optin-readonly-control-plane.md`.

Validated after merge:

```bash
cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo check -p ab-bridge --examples
git diff --check
```

Observed results:

- `trigger_recall_opt_in`: 7 passed.
- `trigger_recall_eval`: 27 passed.
- `cargo check -p ab-bridge --examples`: passed with existing warnings only.
- `git diff --check`: passed.

Next gate: post-implementation review and redacted batch diagnostic decision for
`trigger_recall_opt_in_gated_baseline_trial`.

Do not combine Slice 1 with the gated baseline trial. The next review should be
able to inspect a transition-gate artifact before any code path can call
baseline store search.
