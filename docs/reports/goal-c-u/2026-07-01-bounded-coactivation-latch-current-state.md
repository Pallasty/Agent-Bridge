# Bounded Coactivation Latch Current State

Date: 2026-07-01

## Verdict

The bounded coactivation latch is already implemented and verified in the current tree. The old design document status ("PROPOSE-ONLY / NOT IMPLEMENTED / OWNER-GATED") is stale.

Current state:

- v38 schema rung exists and adds `memory_coactivation.last_cofire_at`; current fresh/live schema version is v39, which includes v38.
- `record_coactivation` stamps `last_cofire_at` on every real co-fire and latches at the configured threshold.
- `decay_coactivation_once` uses the recency-conditioned immunity predicate and enforces the configured latched-edge cap by evicting coldest latched rows first.
- `memory_prune_coactivation_noise` uses the same recency-conditioned immunity predicate, so warm/cold latched behavior is consistent across both prune paths.
- The live store is currently at the cap, not over it: 1618 coactivation edges, 40 consolidated rows, 40 warm latched rows under the 4-day window, and 0 consolidated rows with `last_cofire_at = 0`.

## Source Evidence

- `crates/store/src/coactivation_latch.rs:32` defines `LatchConfig` with v38 knobs `stale_window_secs` and `max_latched_edges`; defaults are 4 days and 40 latched edges.
- `crates/store/src/sqlite.rs:1556` contains the v38 migration rung for `last_cofire_at`, with one-time backfill from `first_at` and version bump to `38`.
- `crates/store/src/sqlite.rs:6543` binds `consolidate_at_count` from `LatchConfig`; `crates/store/src/sqlite.rs:6585` inserts/updates `last_cofire_at` on real co-fire and sets `consolidated` at threshold.
- `crates/store/src/sqlite.rs:4332` applies the v38 immunity predicate in `memory_prune_coactivation_noise`.
- `crates/store/src/sqlite.rs:8623` applies the v38 immunity predicate in `decay_coactivation_once`; `crates/store/src/sqlite.rs:8669` enforces the cap by un-consolidating coldest latched rows.
- `crates/store/src/sqlite.rs:18526` through the v38 test block cover schema, upgrade backfill, co-fire stamping, unlatched regression behavior, cold/warm behavior in both prune paths, inclusive boundary behavior, and cap eviction.

## Verification

Commands run from `/Data/CascadeProjects/agent-bridge`:

```text
CARGO_BUILD_JOBS=1 cargo test -p ab-store coactivation_latch -- --nocapture
```

Result: 7 passed, 0 failed.

```text
CARGO_BUILD_JOBS=1 cargo test -p ab-store v38_ -- --nocapture
```

Result: 9 passed, 0 failed.

```text
CARGO_BUILD_JOBS=1 cargo test -p ab-store decay_coactivation -- --nocapture
```

Result: 6 passed, 0 failed.

```text
CARGO_BUILD_JOBS=1 cargo test -p ab-store memory_prune_coactivation_noise -- --nocapture
```

Result: 0 tests matched the filter. The noise-prune behavior is covered by the v38 tests `v38_cold_latched_edge_reaped_by_both_prune_paths` and `v38_warm_latched_edge_immune_in_both_paths_inclusive_boundary`.

Live DB read-only probe (`/home/pallasting/.local/share/agent-bridge/state.db`):

```text
schema_version 39
last_cofire_at_columns 1
edges 1618
consolidated 40
warm_latched_4d 40
consolidated_lcf_zero 0
over_cap False
```

## Remaining Action

No implementation change is needed for the bounded latch itself. The active next step is to remove stale queue/status references that still describe bounded coactivation latch as owner-gated or not implemented, and then continue with the next reversible retrieval-quality lane.
