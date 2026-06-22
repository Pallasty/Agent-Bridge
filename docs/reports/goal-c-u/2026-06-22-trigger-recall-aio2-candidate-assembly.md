# Trigger-Aware Recall Aio2 Candidate Assembly

Date: 2026-06-22

Host: Linux/Aio2 (`pallasting-ThinkBook-14-G5-IRH`)

Scope: compare read-only candidate-set assembly strategies after diagnosing the
`aio2_lswr_g25_store_write` projected miss.

Verdict: `union_recovers_g25_without_new_observed_aio2_false_hits`. The
eval-only `projected_union` strategy recovers the one aio2-native projected miss
and restores R@10 to 1.000 on the 12-case local corpus. On the current four
aio2-native controls, it does not add observed false hits beyond the existing
projected path. This is promising evaluation evidence, not production
authorization.

## Harness Change

`crates/bridge/examples/trigger_recall_eval.rs` now compares two additional
scratch-only projected strategies in the existing `--aio2-native` output:

- `projected_union`: run precise projected FTS and OR projected FTS, then append
  OR candidates after precise candidates with deterministic de-duplication;
- `projected_oracle`: diagnostic-only upper bound that uses the gold expected
  key to decide whether to add OR candidates. This is never deployable.

The default `intent_projected` behavior remains the current `precise_else_OR`
contract: OR is used only when precise returns zero rows.

This slice was rebased over the concurrent negation-acceptance probe, so the
table also includes `projected+intent`, the remote eval-only exclusion/intent
filter. It is preserved as a separate axis from candidate assembly.

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

Candidate assembly probes:

| Probe | Value |
|---|---:|
| current projected misses | 1 (`aio2_lswr_g25_store_write`) |
| `projected_union` misses | 0 |
| `projected_oracle` misses | 0 |
| `projected_union` added top-10 hits | 1 (`#3`) |
| `projected_union` improved rank | 1 (`#3`) |
| `projected_oracle` added top-10 hits | 1 (`#3`) |
| `projected_oracle` improved rank | 1 (`#3`) |

Negative controls:

| Mode | False Hits | Parser Errors |
|---|---:|---:|
| projected | 12 | 0 |
| CJK | 12 | 0 |
| projected+CJK accepted | 12 | 0 |
| projected+intent accepted | 12 | 0 |
| projected precise+OR union | 12 | 0 |

The union strategy recovers the G25 row because `projected intent OR` already
ranked the expected key first; the previous projected miss happened only because
the non-empty precise distractor suppressed OR fallback. The intent/negation
filter does not recover this case because it receives the current projected/CJK
candidate set, which still lacks the expected G25 row.

The false-hit result should be read carefully. The four aio2-native controls
are intentionally mixed: two are unrelated-ish controls, while two are
policy/adversarial controls that mention real graph/LSWR terms. A relevant
memory may be a good retrieval candidate for an adversarial request, but it
should later be rejected by an acceptance/policy layer. Therefore the next
evidence step is to split those controls before treating false-hit counts as
precision metrics.

## Verification

Commands:

```bash
rustfmt --edition 2024 --check crates/bridge/examples/trigger_recall_eval.rs
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-native
cargo check -p ab-bridge --examples
```

Results:

| Check | Result |
|---|---|
| rustfmt | pass |
| example tests | pass, 14 passed |
| aio2-native eval | pass, metrics above |
| examples check | pass |

Existing unrelated warnings remained present:

- `ab-store` mixed-script confusable warning for the existing beta test name;
- `ab-bridge` warnings around `ToolPolicy` visibility and unused Option-E helper
  items.

## Decision

Keep this line read-only. `projected_union` is a good candidate for further
evaluation because it recovers the known miss without adding observed false hits
on the current aio2 control set, but the evidence is too small and the controls
are not yet semantically bucketed.

This report does not authorize:

- production `memory_search` changes;
- production ranking or search-order changes;
- tokenizer/schema migrations;
- memory reindexing;
- candidate-set widening in production;
- semantic expansion;
- graph/PageRank influence;
- memory sync/import;
- memory writes;
- GHP-1b dry_run=false materialization.

## Next Slice

Split aio2-native controls into:

1. unrelated controls, where any corpus-gold hit is a false hit;
2. policy/adversarial controls, where retrieval may be relevant but acceptance
   must reject action or write intent.

Then compare `projected_union` against those buckets separately before adding
any semantic or policy-aware acceptance layer.
