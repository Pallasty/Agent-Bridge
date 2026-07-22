# Free Recall Strategy R8 — Slice B Source Receipt

Date: 2026-07-22

Status: **SOURCE LANDED / STATIC PASS / FEATURE BUILD UNVERIFIED**

Parent gate:
`docs/design/FREE_RECALL_STRATEGY_R7_SLICE_B_MIGRATION_RESULT_2026_07_22.md`

## 1. Authorized source

R8 implements only the requested Slice B source:

- a new default-off `episode-observation-slice-b` feature which depends on the
  already-default-off Slice A feature;
- an explicit 43→44 schema-owner handoff, limited to Slice B builds;
- the independent `episode_observation_events` relation and its one
  `episode_id` index;
- a module-private inert `SqliteStore` adapter with append-validated-event and
  read-finalized-projection methods;
- source-level disposable-database tests for fresh migration, v43 upgrade,
  collision rollback, disabled no-write behavior, and exact finalized episode
  projection.

The default feature list remains `onnx-embed`; default builds neither compile
Slice B nor create its relation or advance `schema_meta`.

## 2. Schema-owner handoff

`temporal_evidence` continues to verify its exact v43 truth-table manifest.
Its verifier now accepts one *reviewed* successor cursor only when the caller
passes it explicitly. The Slice B compiled path passes only `44`; the default
path passes no successor and still accepts only `43`.

The Slice B migration takes an immediate transaction, requires cursor `43`,
rejects any pre-existing table/index collision, creates the frozen relation and
index, compare-and-set advances the cursor to `44`, then verifies the exact
stored DDL, zero foreign keys, and zero triggers before commit. Any error rolls
the transaction back. Reopening at `44` verifies rather than recreates.

## 3. Inert adapter boundary

All Slice B types and methods are module-private. There is no `StateStore`
change, public/MCP API, producer caller, runtime configuration loader, raw
memory-key read, `item_ref` derivation, retrieval path, sync/export path, or
sidecar write in the default-disabled state.

The only production runtime gate variant is `Disabled`; the enabled variant is
compiled under `cfg(test)` only. Thus even a future feature-built binary has no
production mechanism in this slice to make an adapter write. Test-only
projection accepts exactly open + contiguous items + one matching close and
otherwise abstains.

## 4. Static evidence

- `rustfmt --edition 2021 --config skip_children=true --check` passed on the
  four touched Rust roots and the new Slice B module;
- `git diff --check` passed;
- R7 public-synthetic parent validator passed;
- default feature list and new feature dependency were inspected statically;
- the Slice B module has no public visibility declaration and no operational
  coupling to `memory_save`, `memory_search`, `session_curate`, sync/export,
  MCP, or `StateStore`;
- Slice B source SHA-256:
  `157ffab154a4984c1f2a365dacf4adee20bfd1cea297bae5851c7793abb2e4ea`.

## 5. Claim boundary

No Cargo command was run. The new feature has not compiled, no Rust test has
run, and no database was opened by this task. The disposable-database tests
are source artifacts only. No user `state.db`, private capture, producer,
runtime enablement, retrieval, merge, or deployment was touched.

## 6. Next gate

The next separately authorized gate is a public-source feature build and test
on disposable databases only. It must first compile the exact feature-isolated
`ab-store` configuration, then run the Slice B tests locally and independently.
Passing that gate would verify Slice B source only; it would not authorize a
producer, runtime enablement, real capture, retrieval, merge, or deployment.
