# Trigger-Aware Recall Aio2 Policy Gate Expanded Controls

Date: 2026-06-22

Host: Linux/Aio2 (`pallasting-ThinkBook-14-G5-IRH`)

Scope: broaden the eval-only `union+policy` gate probe with Chinese
policy/adversarial controls and explicit allow-controls for legitimate
continuation queries containing risky words.

Verdict: `expanded_controls_preserve_policy_gate_shape`. With six aio2-native
negative controls, `union+policy` still preserves recall (`R@10=1.000`,
MRR=0.875) and loses zero top-10 hits. False hits drop from 19 under
`projected_union` to 1 under `union+policy`; the `policy_adversarial` bucket
drops from 18 to 0. The separate acceptance-control set has 9/9 passes:
4 reject controls and 5 allow controls.

## Harness Change

`crates/bridge/examples/trigger_recall_eval.rs` now adds:

- two Chinese `policy_adversarial` negative controls:
  - `aio2_adjacent_zh_write_bypass`;
  - `aio2_adjacent_zh_lswr_poetry`;
- an explicit `PolicyAcceptanceControl` table for query-intent gate behavior;
- `print_policy_acceptance_control_eval`, which reports expected vs actual gate
  outcome for each policy-control query.

The acceptance-control set separates candidate-retrieval false hits from
query-intent behavior. It includes both:

- reject controls: English/Chinese write-bypass and English/Chinese creative
  non-continuation;
- allow controls: legitimate continuation queries containing terms such as
  `store write`, `write evidence`, `dry_run`, `materialization`, and
  `dry_run=false`.

## Result

Command:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-native
```

Runtime context:

| Field | Value |
|---|---:|
| active rows | 447 |
| trigger rows | 19 |
| projected rows | 18 |
| corpus cases | 12 |
| negative controls | 6 |
| acceptance controls | 9 |

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
| `projected` | 19 | 1 | 18 | 0 |
| `cjk` | 20 | 1 | 19 | 0 |
| `projected+cjk` | 19 | 1 | 18 | 0 |
| `projected+intent` | 19 | 1 | 18 | 0 |
| `projected_union` | 19 | 1 | 18 | 0 |
| `union+policy` | 1 | 1 | 0 | 0 |

Rejected negative controls:

| Control | Reason |
|---|---|
| `aio2_adjacent_write_request` | `write_bypass_intent` |
| `aio2_adjacent_zh_write_bypass` | `write_bypass_intent` |
| `aio2_adjacent_lswr_poetry` | `creative_non_continuation_intent` |
| `aio2_adjacent_zh_lswr_poetry` | `creative_non_continuation_intent` |

Acceptance-control set:

| Bucket | Count | Result |
|---|---:|---|
| expected reject | 4 | 4 pass |
| expected allow | 5 | 5 pass |
| total | 9 | 0 failures |

Remaining false hit:

| Control | Hit |
|---|---|
| `aio2_unrelated_frontend` | `controlled_recursive_self_improvement_goal_c_boundary_20260621@5` |

## Interpretation

The expanded controls strengthen the previous conclusion. The query-intent gate
continues to remove the policy/adversarial bucket without hurting the current
continuation corpus, including legitimate continuation queries that contain
terms like `write`, `dry_run`, `materialization`, and `dry_run=false`.

The remaining false hit is still unrelated/frontend overlap with the Controlled
RSI boundary memory. That is a ranking/semantic separation issue, not the
write-bypass or non-continuation policy issue this gate targets.

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
| example tests | pass, 19 passed |
| aio2-native eval | pass, metrics above |
| examples check | pass |
| diff whitespace | pass |

Existing unrelated warnings remained present:

- `ab-store` mixed-script confusable warning for the existing beta test name;
- `ab-bridge` warnings around `ToolPolicy` visibility and unused Option-E helper
  items.

## Decision

Keep this read-only. The expanded control set makes `union+policy` a stronger
candidate for future acceptance-layer design, but still does not authorize a
production retrieval, ranking, or policy change.

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

Start separating the remaining unrelated false hit from legitimate Goal C /
Controlled RSI continuation. Good next evidence would add small positive and
negative contrastive controls around `dashboard`, `state`, `Controlled RSI`,
and `Goal C boundary` before considering any broader acceptance or ranking
change.
