# ADR: codebase-index A2 adoption review

Date: 2026-08-08  
Status: HOLD — default-off candidate only

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
2. Review receipt delivery to an operational caller; the ordinary
   `StateStore::codebase_index` API currently discards dispatch provenance.
3. Run a separately authorized default-off shadow against a copied or
   explicitly isolated AB database, with no live-database write claim until
   ownership and rollback policy are recorded.
4. Define rollback from A2 to FullVec/A1 and retain the selected namespace,
   effective strategy, batch size, and fallback reason in the operational
   evidence.
5. Re-run the full package gate after any caller or configuration change.

## Non-goals

This ADR does not authorize Arrow-wide migration, MI50/ROCm execution, GPU
device buffers, Arrow Flight/DataFusion, MCP schema changes, daemon deployment,
or a default strategy change.

## Current disposition

The implementation is reviewable and the isolated candidate commit is
`629dccb4`. The candidate remains HOLD because the fresh canonical receipt and
operational caller review are not complete. A failed host quiet-window check is
an environmental block, not evidence for relaxing the frozen thresholds.
