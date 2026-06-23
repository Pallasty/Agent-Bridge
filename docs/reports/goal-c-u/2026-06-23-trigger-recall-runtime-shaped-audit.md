# Trigger Recall Runtime-Shaped Audit - 2026-06-23

Host: Linux/Aio2 (`pallasting-ThinkBook-14-G5-IRH`)

Worktree: `/Programs/Users/Pallasting/Documents/CascadeProjects/agent-bridge`

Base: `9d9733c` (`docs(memory): review case2 production readiness`)

Scope: eval-only; no production implementation

## Purpose

This slice follows
`0def902 docs(memory): design trigger query intent runtime gate`.

The design note required the next implementation step to remain eval-only and
model the runtime shape before any production `memory_search` change:

```text
baseline FTS + supplemental projected candidates + query-intent audit object
```

This report records that first runtime-shaped assembler. It intentionally gates
only supplemental projected candidates. Baseline FTS results are preserved so
the probe cannot silently become a global query rejection policy.

## Changes

Code:

- `crates/bridge/examples/trigger_recall_eval.rs`

Added:

- `--aio2-runtime-audit`;
- `RuntimeShapedAudit`;
- SHA-256 query hash in audit output;
- split policy vs continuation/domain gate decisions;
- audit JSON with:
  - schema;
  - explicit opt-in flag;
  - mode;
  - scope mode;
  - candidate source;
  - query hash;
  - policy and continuation gate decisions;
  - baseline/supplemental/final candidate counts;
  - fallback behavior;
  - regression anchor;
  - production-change booleans;
- tests proving:
  - accepted supplemental candidates can recover a baseline miss;
  - rejected dashboard/state intent drops supplemental candidates but preserves
    baseline results;
  - audit output does not echo the raw query.

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
| active rows | 450 |
| trigger rows | 22 |
| projected rows | 21 |
| corpus cases | 14 |
| expected key refs | 14 |
| present expected refs | 14 |
| missing expected refs | 0 |
| expected without trigger | 0 |
| ready | true |

## Runtime-Shaped Audit Result

Command:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-runtime-audit
```

Recall:

| Mode | R@1 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|
| `baseline_fts` | 0.714 | 0.857 | 0.857 | 0.786 |
| `projected_union` | 0.714 | 1.000 | 1.000 | 0.857 |
| `runtime_final` | 0.714 | 1.000 | 1.000 | 0.857 |

Candidate effect:

| Metric | Value |
|---|---:|
| supplemental recovered baseline misses | 2 (`#3`, `#9`) |
| runtime final lost baseline hits | 0 |

Negative controls:

| Metric | Value |
|---|---:|
| baseline false hits retained | 23 |
| supplemental false hits after gate | 0 |
| runtime final false hits | 23 |

Rejected control audit samples:

| Control | Gate | Reason | Fallback |
|---|---|---|---|
| `aio2_unrelated_frontend` | continuation | `frontend_dashboard_intent` | `baseline_fts_only` |
| `aio2_unrelated_frontend_goal_c_words` | continuation | `frontend_dashboard_intent` | `baseline_fts_only` |
| `aio2_unrelated_controlled_rsi_health_dashboard` | continuation | `health_dashboard_intent` | `baseline_fts_only` |
| `aio2_adjacent_write_request` | policy | `write_bypass_intent` | `baseline_fts_only` |
| `aio2_adjacent_zh_write_bypass` | policy | `write_bypass_intent` | `baseline_fts_only` |
| `aio2_adjacent_lswr_poetry` | policy | `creative_non_continuation_intent` | `baseline_fts_only` |
| `aio2_adjacent_zh_lswr_poetry` | policy | `creative_non_continuation_intent` | `baseline_fts_only` |

Example audit object shape:

```json
{
  "schema": "agent_bridge.memory.trigger_query_intent_acceptance.v0",
  "enabled": true,
  "read_only": true,
  "mode": "fts",
  "explicit_opt_in": true,
  "default_memory_search_unchanged": true,
  "scope_mode": "local_only",
  "candidate_source": "projected_union",
  "query_hash": "sha256:94ece9d53ed02a6143ddbb9f009287f02d62bcbeac48756c5c4732db08825e5b",
  "policy_gate": {
    "decision": "allow",
    "reject_reason": null
  },
  "continuation_gate": {
    "decision": "allow",
    "reject_reason": null
  },
  "baseline_candidates": 1,
  "supplemental_candidates_before_gate": 9,
  "supplemental_candidates_after_gate": 9,
  "final_candidates": 10,
  "fallback_behavior": "baseline_plus_supplemental_projected",
  "regression_anchor": "aio2_trigger_recall_union_cont_20260623",
  "changes_default_memory_search_order": false,
  "changes_production_retrieval": false
}
```

## Baseline False-Hit Finding

This slice intentionally changes the interpretation of the previous
`union+cont` result.

`union+cont` remains useful as an eval-only "what if the whole projected union
is accepted or rejected by query intent" probe:

| Mode | R@10 | Misses | False Hits |
|---|---:|---:|---:|
| `union+cont` | 1.000 | 0 | 0 |

But the runtime-shaped assembler is stricter and safer: it gates only
supplemental projected candidates and preserves baseline FTS. Under that
runtime shape:

- supplemental candidates recover the two known baseline misses;
- supplemental candidates add zero false hits after the gate;
- baseline FTS itself still carries 23 false hits on the negative controls;
- therefore this design is not sufficient to claim global false-hit reduction.

The result is useful because it prevents an unsafe leap: a production opt-in
supplemental path can be evaluated separately from any future baseline
acceptance/filtering policy.

## Verification

Commands:

```bash
rustfmt --edition 2024 crates/bridge/examples/trigger_recall_eval.rs
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-runtime-audit
cargo run -p ab-bridge --example trigger_recall_eval -- --check-aio2-native
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-native
cargo check -p ab-bridge --example trigger_recall_eval
git diff --check
```

Results:

| Check | Result |
|---|---|
| rustfmt | pass |
| example tests | pass, 23 passed |
| runtime-shaped audit | pass, metrics above |
| corpus preflight | pass, ready=true |
| aio2-native eval | pass, `union+cont` R@10=1.000 / false hits=0 |
| focused example check | pass |
| diff whitespace | pass |

Existing unrelated warnings remained present:

- `ab-store` mixed-script confusable warning for the existing beta test name;
- `ab-bridge` warnings around `ToolPolicy` visibility and unused Option-E helper
  items.

Full `cargo check -p ab-bridge --examples` was not a valid check for this
slice because an unrelated dirty `crates/bridge/examples/recall_eval.rs` change
was present in the worktree and failed on missing `remote_session_*` helper
definitions. This slice did not edit or stage that file.

## Decision

Keep this eval-only. This report does not authorize:

- production `memory_search` changes;
- production ranking or candidate-order changes;
- tokenizer/schema migrations;
- memory reindexing;
- semantic expansion;
- graph/PageRank influence;
- memory writes;
- GHP materialization.

## Next Slice

Decide the next evidence fork:

- if the goal is safe supplemental recall only, freeze this runtime-shaped audit
  command and add more host/local regression controls;
- if the goal is false-hit reduction, start a separate eval-only baseline
  acceptance/filtering design, because supplemental-only gating cannot remove
  false hits already present in baseline FTS.
