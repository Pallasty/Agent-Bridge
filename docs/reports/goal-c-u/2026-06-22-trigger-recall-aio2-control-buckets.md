# Trigger-Aware Recall Aio2 Control Buckets

Date: 2026-06-22

Host: Linux/Aio2 (`pallasting-ThinkBook-14-G5-IRH`)

Scope: split aio2-native negative controls into semantic buckets so false-hit
counts can distinguish ordinary unrelated noise from policy/adversarial
adjacency.

Verdict: `false_hits_are_policy_adversarial_dominant`. On the current
12-case aio2-native corpus and four local controls, all evaluated modes still
show 12 false hits, but the bucket split is stable across modes:
`unrelated=1`, `policy_adversarial=11`. The next useful work is therefore not
more tokenizer probing; it is an acceptance/policy layer that can reject adjacent
write or creative-writing intent after retrieval.

## Harness Change

`crates/bridge/examples/trigger_recall_eval.rs` now carries a `ControlBucket`
on each `NegativeControl`:

- `unrelated`: control queries that should not retrieve corpus gold keys;
- `policy_adversarial`: adjacent queries that may retrieve relevant project
  state, but should be rejected by an acceptance or policy gate before action.

The output now prints false-hit bucket counts for:

- `projected`;
- `cjk`;
- `projected+cjk`;
- `projected+intent`;
- `projected_union`.

The default Mac-oriented eval path also prints the bucket summary, so this is a
general eval-harness improvement rather than an aio2-only special case.

## Result

Command:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-native
```

Per-mode recall:

| Mode | R@1 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|
| `intent_content` | 0.750 | 1.000 | 1.000 | 0.875 |
| `intent_projected` | 0.750 | 0.917 | 0.917 | 0.833 |
| `cjk_shingle_proj` | 0.750 | 0.917 | 0.917 | 0.833 |
| `projected+cjk_acc` | 0.750 | 0.917 | 0.917 | 0.833 |
| `projected+intent` | 0.750 | 0.917 | 0.917 | 0.833 |
| `projected_union` | 0.750 | 1.000 | 1.000 | 0.875 |
| `projected_oracle` | 0.750 | 1.000 | 1.000 | 0.875 |
| `exact_projected` | 0.917 | 1.000 | 1.000 | 0.958 |

False-hit buckets:

| Mode | False Hits | Unrelated | Policy/Adversarial | Parser Errors |
|---|---:|---:|---:|---:|
| `projected` | 12 | 1 | 11 | 0 |
| `cjk` | 12 | 1 | 11 | 0 |
| `projected+cjk` | 12 | 1 | 11 | 0 |
| `projected+intent` | 12 | 1 | 11 | 0 |
| `projected_union` | 12 | 1 | 11 | 0 |

Controls:

| Control | Bucket | Interpretation |
|---|---|---|
| `aio2_unrelated_desktop` | `unrelated` | desktop maintenance should not retrieve trigger-recall gold keys |
| `aio2_unrelated_frontend` | `unrelated` | frontend styling is adjacent to reports but outside this memory lane |
| `aio2_adjacent_write_request` | `policy_adversarial` | graph/write vocabulary with forbidden bypass intent |
| `aio2_adjacent_lswr_poetry` | `policy_adversarial` | LSWR vocabulary with creative-writing intent rather than project-state continuation |

The one unrelated false hit is from `aio2_unrelated_frontend`, which retrieves
`controlled_recursive_self_improvement_goal_c_boundary_20260621` at rank 5. The
remaining eleven hits come from the two policy/adversarial controls.

## Interpretation

`projected_union` still looks useful for recall because it recovers the known
`aio2_lswr_g25_store_write` miss and restores R@10 to 1.000. However, the
control-bucket evidence says the dominant risk is not generic off-topic recall.
It is adjacent project vocabulary that is relevant enough to retrieve, but whose
requested action should be rejected.

The existing `projected+intent` filter does not reduce these aio2 false hits
because it currently works as a narrow explicit-exclusion filter over the
existing candidate path. It is not yet a full acceptance classifier for write
intent, bypass intent, or creative-writing/non-continuation intent.

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
| example tests | pass, 16 passed |
| aio2-native eval | pass, metrics above |
| examples check | pass |
| diff whitespace | pass |

Existing unrelated warnings remained present:

- `ab-store` mixed-script confusable warning for the existing beta test name;
- `ab-bridge` warnings around `ToolPolicy` visibility and unused Option-E helper
  items.

## Decision

Keep this read-only. The bucket evidence supports a next slice that designs an
eval-only acceptance/policy gate for adjacent controls before considering any
production retrieval change.

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

Add eval-only acceptance labels for the two `policy_adversarial` controls and
measure whether a conservative gate can reject write-bypass and creative-writing
intent without harming the 12 aio2 continuation cases.
