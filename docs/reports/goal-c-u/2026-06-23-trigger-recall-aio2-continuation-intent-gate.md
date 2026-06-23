# Trigger Recall Aio2 Continuation Intent Gate - 2026-06-23

## Purpose

This read-only slice follows
`de5573b test(memory): contrast trigger dashboard controls`.

The previous dashboard/state contrastive controls showed that `union+policy`
kept the AIO2-native Goal C continuation hits, but still returned unrelated
frontend/dashboard and health-dashboard false hits. This slice adds an
eval-only continuation-intent gate to test whether those dashboard/state
ambiguities can be rejected without losing the known Goal C continuation
queries.

## Changes

Code:

- `crates/bridge/examples/trigger_recall_eval.rs`

Added a diagnostic retrieval mode:

| Mode | Behavior |
|---|---|
| `union+cont` | Run `projected_union` only if the query passes the existing policy gate and the new continuation-intent gate |

Added `continuation_acceptance_reject_reason(query)`:

| Rule | Reject Reason |
|---|---|
| Reuse existing policy/adversarial gate | Existing policy reject reason |
| `dashboard` or `state` plus health/workout terms | `health_dashboard_intent` |
| `dashboard` or `state` plus frontend/visual-design terms | `frontend_dashboard_intent` |

Added diagnostics:

- per-mode `union+cont` recall/MRR;
- `union+cont` top-10 lost-hit count;
- `union+cont` negative-control false-hit and parser-error counts;
- explicit continuation gate rejection diagnostics.

Added/updated tests:

- `aio2_goal_c_dashboard_state_contrastives_pair_positive_and_unrelated_intents`
- `projected_union_continuation_gate_rejects_dashboard_role_mismatch`

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
| active rows | 449 |
| trigger rows | 21 |
| projected rows | 20 |
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
| `intent_content` | 0.643 | 0.929 | 0.929 | 0.786 |
| `intent_projected` | 0.714 | 0.857 | 0.857 | 0.786 |
| `projected_union` | 0.714 | 1.000 | 1.000 | 0.857 |
| `union+policy` | 0.714 | 1.000 | 1.000 | 0.857 |
| `union+cont` | 0.714 | 1.000 | 1.000 | 0.857 |
| `projected_oracle` | 0.714 | 1.000 | 1.000 | 0.857 |
| `exact_projected` | 0.929 | 1.000 | 1.000 | 0.964 |

Candidate assembly:

| Probe | Value |
|---|---:|
| `projected_union` added top-10 hits | 2 (`#3`, `#9`) |
| `union+policy` lost top-10 hits | 0 |
| `union+cont` lost top-10 hits | 0 |

False-hit buckets:

| Mode | False Hits | Unrelated | Policy/Adversarial | Parser Errors |
|---|---:|---:|---:|---:|
| `union+policy` | 4 | 4 | 0 | 0 |
| `union+cont` | 0 | 0 | 0 | 0 |

Continuation gate diagnostics:

| Control | Reject Reason |
|---|---|
| `aio2_unrelated_frontend` | `frontend_dashboard_intent` |
| `aio2_unrelated_frontend_goal_c_words` | `frontend_dashboard_intent` |
| `aio2_unrelated_controlled_rsi_health_dashboard` | `health_dashboard_intent` |

Honest-read summary:

| Mode | Misses |
|---|---:|
| `projected_union` | 0 |
| `union+policy` | 0 |
| `union+cont` | 0 |
| `projected_oracle` | 0 |

## Interpretation

The eval-only continuation-intent gate resolves the remaining dashboard/state
false-hit bucket in the AIO2-native mini-corpus:

- it preserves all current Goal C continuation hits;
- it rejects frontend/dashboard role mismatch;
- it rejects health/workout dashboard role mismatch;
- it introduces no FTS parser errors in the tested controls.

This is not yet production evidence. The gate is hand-authored and corpus-local,
but it gives the next runtime design a concrete shape: continuation retrieval
needs a separate query-intent acceptance layer after broad candidate assembly
and before any result is considered eligible.

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
| rustfmt | pass |
| example tests | pass, 21 passed |
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
- GHP materialization.

## Next Slice

Translate the eval-only `union+cont` result into a runtime design note before
any implementation: define where a query-intent acceptance layer would sit,
which signals are allowed, what audit fields it must emit, and which
dashboard/state controls become permanent regression tests.
