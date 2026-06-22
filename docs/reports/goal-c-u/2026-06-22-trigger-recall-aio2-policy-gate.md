# Trigger-Aware Recall Aio2 Policy Gate Probe

Date: 2026-06-22

Host: Linux/Aio2 (`pallasting-ThinkBook-14-G5-IRH`)

Scope: add a read-only, eval-only acceptance/policy gate probe after the
`projected_union` candidate assembly strategy.

Verdict: `policy_gate_removes_adversarial_hits_without_recall_loss`. On the
current 12-case aio2-native corpus, `union+policy` preserves the
`projected_union` recall result (`R@10=1.000`, MRR=0.875) and loses zero
top-10 hits. On the four aio2-native controls, false hits drop from 12 to 1;
the `policy_adversarial` bucket drops from 11 to 0. The remaining false hit is
the unrelated frontend/control-RSI overlap and is outside this policy gate's
target.

## Harness Change

`crates/bridge/examples/trigger_recall_eval.rs` now includes:

- `policy_acceptance_reject_reason(query)`, a conservative query-intent gate;
- `search_projected_union_then_policy_accepted`, which returns no candidates
  when the query is rejected, otherwise delegates to the eval-only
  `projected_union` strategy;
- the `union+policy` recall row and false-hit bucket summary in both default
  and aio2-native eval output;
- diagnostics listing which controls the policy gate rejects.

Current reject reasons:

| Reason | Query Shape |
|---|---|
| `write_bypass_intent` | direct graph/related-keys write plus bypass/dry-run/review surface |
| `creative_non_continuation_intent` | poem/poetry/creative-writing query shape |

The gate intentionally does not reject ordinary continuation queries that use
words such as `write`, `dry_run`, or `materialization` as project-state terms.

## Result

Command:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-native
```

Runtime context:

| Field | Value |
|---|---:|
| active rows | 446 |
| trigger rows | 18 |
| projected rows | 17 |
| corpus cases | 12 |
| negative controls | 4 |

Per-mode recall:

| Mode | R@1 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|
| `intent_content` | 0.750 | 1.000 | 1.000 | 0.875 |
| `intent_projected` | 0.750 | 0.917 | 0.917 | 0.833 |
| `cjk_shingle_proj` | 0.750 | 0.917 | 0.917 | 0.833 |
| `projected+cjk_acc` | 0.750 | 0.917 | 0.917 | 0.833 |
| `projected+intent` | 0.750 | 0.917 | 0.917 | 0.833 |
| `projected_union` | 0.750 | 1.000 | 1.000 | 0.875 |
| `union+policy` | 0.750 | 1.000 | 1.000 | 0.875 |
| `projected_oracle` | 0.750 | 1.000 | 1.000 | 0.875 |
| `exact_projected` | 0.917 | 1.000 | 1.000 | 0.958 |

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
| `projected` | 12 | 1 | 11 | 0 |
| `cjk` | 12 | 1 | 11 | 0 |
| `projected+cjk` | 12 | 1 | 11 | 0 |
| `projected+intent` | 12 | 1 | 11 | 0 |
| `projected_union` | 12 | 1 | 11 | 0 |
| `union+policy` | 1 | 1 | 0 | 0 |

Rejected controls:

| Control | Reason |
|---|---|
| `aio2_adjacent_write_request` | `write_bypass_intent` |
| `aio2_adjacent_lswr_poetry` | `creative_non_continuation_intent` |

Remaining false hit:

| Control | Hit |
|---|---|
| `aio2_unrelated_frontend` | `controlled_recursive_self_improvement_goal_c_boundary_20260621@5` |

## Interpretation

This slice supports the earlier bucket finding: the dominant false-hit risk is
not generic unrelated recall. It is adjacent project vocabulary paired with an
unsafe or non-continuation request. A conservative query-intent gate can remove
that `policy_adversarial` bucket without harming the current continuation
corpus.

This is still only eval evidence. The rule is deliberately narrow and should
not be treated as a complete policy classifier. It says that a future
acceptance layer is plausible and should be measured before any production
candidate widening.

## Verification

Commands:

```bash
rustfmt --edition 2024 --check crates/bridge/examples/trigger_recall_eval.rs
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-native
cargo check -p ab-bridge --examples
git diff --check
```

Results:

| Check | Result |
|---|---|
| rustfmt | pass |
| example tests | pass, 18 passed |
| aio2-native eval | pass, metrics above |
| examples check | pass |
| diff whitespace | pass |

Existing unrelated warnings remained present:

- `ab-store` mixed-script confusable warning for the existing beta test name;
- `ab-bridge` warnings around `ToolPolicy` visibility and unused Option-E helper
  items.

## Decision

Keep this line read-only. `union+policy` is promising enough for the next
evaluation slice, but it does not authorize a production retrieval, ranking, or
acceptance change.

This report does not authorize:

- production `memory_search` changes;
- production ranking or candidate-order changes;
- tokenizer/schema migrations;
- memory reindexing;
- semantic expansion;
- graph/PageRank influence;
- memory writes;
- GHP-1b dry_run=false materialization.

## Next Slice

Broaden the acceptance-gate eval set before production design:

1. add more policy/adversarial controls, including Chinese write-bypass and
   non-continuation variants;
2. add continuation queries that contain risky words in legitimate context;
3. report false-hit buckets and recall deltas for `union+policy` against both
   local aio2 and portable corpus slices.
