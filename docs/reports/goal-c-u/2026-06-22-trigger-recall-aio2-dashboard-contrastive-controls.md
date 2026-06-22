# Trigger Recall Aio2 Dashboard Contrastive Controls - 2026-06-22

## Purpose

This read-only slice follows
`7ee0039 test(memory): expand trigger policy gate controls`.

The prior `union+policy` probe removed the policy/adversarial false-hit bucket
without hurting the AIO2-native continuation corpus, but one unrelated false
hit remained:

```text
aio2_unrelated_frontend -> controlled_recursive_self_improvement_goal_c_boundary_20260621@5
```

This slice adds a small contrastive set around `dashboard`, `state`,
`Controlled RSI`, and `Goal C boundary` to distinguish legitimate Goal C
continuation from unrelated frontend/dashboard wording.

## Changes

Code:

- `crates/bridge/examples/trigger_recall_eval.rs`

Added two positive AIO2-native continuation cases:

| Case | Expected |
|---|---|
| `aio2_goal_c_dashboard_state_boundary` | `controlled_recursive_self_improvement_goal_c_boundary_20260621` |
| `aio2_goal_c_dashboard_state_closure` | `controlled_rsi_goal_c_local_run_and_closure_20260621` |

Added two unrelated negative controls:

| Control | Intent |
|---|---|
| `aio2_unrelated_frontend_goal_c_words` | frontend/dashboard visual design with Goal C wording |
| `aio2_unrelated_controlled_rsi_health_dashboard` | health/workout Controlled RSI dashboard wording |

This remains scratch-only and read-only: SELECT from the live DB plus in-memory
FTS tables. It does not call `memory_get`, `memory_search`, reindex, write, or
change production ranking.

## Corpus Preflight

Command:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --check-aio2-native
```

Result:

| Metric | Value |
|---|---:|
| active rows | 448 |
| trigger rows | 20 |
| projected rows | 19 |
| corpus cases | 14 |
| expected key refs | 14 |
| present expected refs | 14 |
| missing expected refs | 0 |
| expected without trigger | 0 |
| ready | true |

## Eval Result

Command:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-native
```

Per-mode recall:

| Mode | R@1 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|
| `intent_content` | 0.786 | 1.000 | 1.000 | 0.893 |
| `intent_projected` | 0.786 | 0.929 | 0.929 | 0.857 |
| `cjk_shingle_proj` | 0.786 | 0.929 | 0.929 | 0.857 |
| `projected+cjk_acc` | 0.786 | 0.929 | 0.929 | 0.857 |
| `projected+intent` | 0.786 | 0.929 | 0.929 | 0.857 |
| `projected_union` | 0.786 | 1.000 | 1.000 | 0.893 |
| `union+policy` | 0.786 | 1.000 | 1.000 | 0.893 |
| `projected_oracle` | 0.786 | 1.000 | 1.000 | 0.893 |
| `exact_projected` | 0.929 | 1.000 | 1.000 | 0.964 |

Candidate assembly:

| Probe | Value |
|---|---:|
| `projected_union` added top-10 hits | 1 (`#3`) |
| `projected_union` improved rank | 1 (`#3`) |
| `union+policy` lost top-10 hits | 0 |
| `union+policy` misses | 0 |

False-hit buckets:

| Mode | False Hits | Unrelated | Policy/Adversarial | Parser Errors |
|---|---:|---:|---:|---:|
| `projected` | 23 | 5 | 18 | 0 |
| `cjk` | 24 | 5 | 19 | 0 |
| `projected+cjk` | 23 | 5 | 18 | 0 |
| `projected+intent` | 21 | 3 | 18 | 0 |
| `projected_union` | 23 | 5 | 18 | 0 |
| `union+policy` | 5 | 5 | 0 | 0 |

`union+policy` still preserves all continuation hits, including the new
dashboard/state Goal C positives. The added negatives show that the remaining
risk is broader than the original single frontend control: unrelated dashboard
or health-dashboard wording can retrieve Goal C boundary/closure memories.

Observed `union+policy` unrelated false hits:

| Control | Hit |
|---|---|
| `aio2_unrelated_frontend` | `controlled_recursive_self_improvement_goal_c_boundary_20260621@8` |
| `aio2_unrelated_frontend_goal_c_words` | `controlled_recursive_self_improvement_goal_c_boundary_20260621@1` |
| `aio2_unrelated_frontend_goal_c_words` | `controlled_rsi_goal_c_local_run_and_closure_20260621@10` |
| `aio2_unrelated_controlled_rsi_health_dashboard` | `controlled_recursive_self_improvement_goal_c_boundary_20260621@4` |
| `aio2_unrelated_controlled_rsi_health_dashboard` | `controlled_rsi_goal_c_local_run_and_closure_20260621@5` |

The existing policy/adversarial acceptance controls remain stable:

| Bucket | Count | Result |
|---|---:|---|
| expected reject | 4 | 4 pass |
| expected allow | 5 | 5 pass |
| total | 9 | 0 failures |

## Interpretation

This falsifies the simple story that only unsafe write-bypass or creative
non-continuation requests cause unacceptable false hits. The policy gate solved
that bucket, but not unrelated dashboard/state ambiguity.

The next design question is not whether to widen `projected_union`: widening is
still useful for recovering the known G25 miss, and the policy gate protects
the policy/adversarial bucket. The next question is whether an eval-only
continuation-intent layer can require Agent-Bridge / continuity-ledger /
self-improvement context when dashboard/state/Controlled-RSI terms appear.

## Verification

Commands:

```bash
rustfmt --edition 2024 crates/bridge/examples/trigger_recall_eval.rs
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval -- --check-aio2-native
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-native
cargo check -p ab-bridge --examples
git diff --check
```

Results:

| Check | Result |
|---|---|
| example tests | pass, 19 passed |
| corpus preflight | pass, ready=true |
| aio2-native eval | pass, metrics above |
| examples check | pass |
| diff whitespace | pass |

Existing unrelated warnings remained present:

- `ab-store` mixed-script confusable warning for the existing beta test name;
- `ab-bridge` warnings around `ToolPolicy` visibility and unused Option-E helper
  items.

## Decision

Keep this read-only. This report does not authorize:

- production `memory_search` changes;
- production ranking or candidate-order changes;
- tokenizer/schema migrations;
- memory reindexing;
- semantic expansion;
- graph/PageRank influence;
- memory writes;
- GHP-1b dry_run=false materialization.

## Next Slice

Add an eval-only continuation-intent classifier/probe for the dashboard/state
ambiguity. A first small rule should reject frontend/visual-design and
health/workout dashboard intents unless the query also carries Agent-Bridge,
continuity-ledger, report-first, self-improvement, or executor/no-executor
continuation context. It must preserve the two new positive Goal C dashboard
continuation cases before any production design is considered.
