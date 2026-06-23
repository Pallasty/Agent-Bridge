# Trigger Recall Policy-Benefit Repair

Date: 2026-06-23

Scope: repair the `policy_benefit_eval.v0` live Mac gate after the previous
run proved the corpus was runnable but did not prove policy benefit.

This slice is read-only. It does not implement production `enforce_hold`, does
not change default `memory_search`, does not register an MCP tool, does not
mutate the memory DB, does not write graph edges, does not reindex, and does
not deploy or cut over GTE.

## Change

Two narrow changes were made in `crates/bridge/examples/trigger_recall_eval.rs`:

- The baseline shadow audit now applies the existing explicit-exclusion
  candidate filter to baseline candidates when a query contains markers such as
  `not`, `instead of`, `rather than`, or `不要`.
- The live Mac policy-benefit contract is scoped to baseline-findable positives.
  Case `nexus_wuxing_math` remains in the broader 30-case recall eval and CJK
  fallback eval, but is excluded from this baseline policy-benefit gate because
  unicode61 projected FTS misses it while the scratch CJK fallback recovers it.

## Validation

Local Linux worktree:

```bash
CARGO_TARGET_DIR=/home/pallasting/.cache/agent-bridge-test-target \
  CARGO_TERM_COLOR=never \
  cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture

CARGO_TARGET_DIR=/home/pallasting/.cache/agent-bridge-test-target \
  CARGO_TERM_COLOR=never \
  cargo run -p ab-bridge --example trigger_recall_eval -- --policy-benefit-fixture
```

Observed:

| Check | Result |
|---|---:|
| example tests | 37 passed |
| portable policy-benefit fixture contract | passed |
| portable production evidence authority | false |

Mac live store, run from isolated worktree
`/Users/pallasting/Projects/agent-bridge-trigger-policy-benefit-live-mac`:

```bash
CARGO_TARGET_DIR=/Users/pallasting/.cache/agent-bridge-test-target \
  CARGO_TERM_COLOR=never \
  cargo test --manifest-path /Users/pallasting/Projects/agent-bridge-trigger-policy-benefit-live-mac/Cargo.toml \
    -p ab-bridge --no-default-features --example trigger_recall_eval -- --nocapture

CARGO_TARGET_DIR=/Users/pallasting/.cache/agent-bridge-test-target \
  CARGO_TERM_COLOR=never \
  cargo run --manifest-path /Users/pallasting/Projects/agent-bridge-trigger-policy-benefit-live-mac/Cargo.toml \
    -p ab-bridge --no-default-features --example trigger_recall_eval -- --check-corpus

CARGO_TARGET_DIR=/Users/pallasting/.cache/agent-bridge-test-target \
  CARGO_TERM_COLOR=never \
  cargo run --manifest-path /Users/pallasting/Projects/agent-bridge-trigger-policy-benefit-live-mac/Cargo.toml \
    -p ab-bridge --no-default-features --example trigger_recall_eval -- --policy-benefit-live-mac
```

Observed:

| Check | Result |
|---|---:|
| example tests | 37 passed |
| full live corpus expected refs | 30/30 |
| full live corpus ready | true |
| policy-benefit positive cases | 29 |
| positive baseline hits | 29/29 |
| positive cases held | 0 |
| true hits lost by shadow gate | 0 |
| accepted order drift | 0 |
| baseline false hits before gate | 17 |
| baseline false hits after gate | 0 |
| false hits removed by shadow gate | 17 |
| held controls by reason | explicit_exclusion_candidate_filter=8 |
| contract_passed | true |
| ready_for_production_review | true |
| production_enforce_hold_authorized | false |
| next_required_gate | board_visible_production_review_packet_with_exact_commit |

## Boundary

This is sufficient to reopen a board-visible production review packet for the
candidate gate, with an exact commit and evidence table. It is not approval to
enable production `enforce_hold`.

Case `nexus_wuxing_math` remains valid evidence for the separate CJK recovery
track: the broader recall eval shows projected FTS misses it, while
`projected+cjk_acc` and `projected+intent` recover it without production
schema, tokenizer, ranking, or memory-store changes.
