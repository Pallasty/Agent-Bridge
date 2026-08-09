# ADR: codebase-index A2 adoption review

Date: 2026-08-08  
Status: HOLD — default-off candidate only; caller/shadow/rollback evidence closed

## Decision

Keep `native_chunk_staged_v0` behind the
`codebase-index-bounded-native-a1` feature and the explicit A1/A2 environment
gates. Do not enable A2 by default and do not route MCP or daemon callers to a
new authority path in this review.

## Evidence accepted

- A0 selected bounded native rows over Arrow for the current SQLite boundary.
- A1 canonical attempt23 passed the frozen semantic, rollback, WAL, RSS, and
  transaction gates for the staged-native algorithm.
- The A2 dispatch seam preserves A2 precedence, A1 fallback, exact rollback,
  retry-after-staging-repair, and structured dispatch provenance.
- `ab-store` package verification passed with 487 unit tests and 21 A1/A2
  integration tests.
- Non-promotable diagnostic dogfood proved fresh-child and isolated SQLite
  execution without touching the live database.

## Open gates before any enablement

1. Obtain a fresh canonical receipt for the exact adoption commit on a host
   satisfying the frozen CPU39/79 quiet-window and `/home` ext4 contract.
2. Re-run the full package gate after any later caller or configuration change.

## Closed evidence on the rebased candidate

The ordinary `StateStore::codebase_index` result now retains an optional
dispatch receipt without changing the trait signature. The field is omitted
when the bounded-index feature is not compiled, preserving the historical JSON
shape. With the explicit default-off feature and environment gate, operational
callers receive the selected namespace, requested and effective strategies,
batch size, staging-parent presence, and fallback reason.

The integration fixture `codebase_index_a2_default_off_shadow_mutates_only_copied_database`
creates a schema-initialized source database, records its complete typed
snapshot and bytes, copies it, and opens only the copy for A2. It requires the
source bytes and snapshot to remain exact, the copied database to contain the
new generation, the receipt to name namespace `a2` and
`native_chunk_staged_v0`, and the private staging directory to be empty after
success. This is isolated-fixture evidence only; it does not open or claim
ownership of the live Agent-Bridge database.

Rollback is configuration-only and fail-closed:

- unset `AB_CODEBASE_INDEX_A2_STRATEGY` to return to A1 selection or the
  historical FullVec default;
- set `AB_CODEBASE_INDEX_A2_STRATEGY=full_vec` for an explicit A2-namespace
  FullVec rollback while retaining the operational receipt;
- an unknown A2 strategy falls back to a valid A1 strategy and records
  `fallback_reason=a2_strategy_unknown`;
- if neither namespace is valid, dispatch uses FullVec and records the invalid
  namespace reason;
- staging or replay failure preserves the prior authoritative generation, and
  a retry after repairing staging must match the explicit A1 baseline.

The feature remains absent from default features. No configuration file,
daemon environment, MCP schema, deployment script, or live database path is
changed by this evidence unit.

## Non-goals

This ADR does not authorize Arrow-wide migration, MI50/ROCm execution, GPU
device buffers, Arrow Flight/DataFusion, MCP schema changes, daemon deployment,
or a default strategy change.

## Current disposition

The original isolated candidate was `629dccb4`; its rebased evidence successor
must be identified by the final commit and a fresh canonical receipt before
promotion review. Operational caller delivery, copied-database shadow, and
rollback recording are now closed in code and tests. The candidate remains HOLD
because the exact-successor canonical receipt is not complete. A failed host
quiet-window check is an environmental block, not evidence for relaxing the
frozen thresholds.
