# Free Recall Strategy R14 — C2A Interface Decision

Date: 2026-07-22

Status: **DECISION PACKET / NO C2A SOURCE AUTHORITY**

Depends on:

- R9 Slice B storage acceptance;
- R12 C1 orchestration acceptance;
- R13 C2 authority preregistration.

## 1. Selected ownership model

C2A must use a **store-owned opaque attempt, bridge-owned private adapter**.

`ab-store` owns all of the following: episode/run/event identity allocation,
key-provider invocation, `item_ref` derivation, payload hashing, Slice B
append ordering, and all SQLite errors. `ab-bridge` owns only adaptation of
that store-owned attempt to C1's already-private
`CurationBatchObservationCapability` / `CurationBatchObservationAttempt`.

The bridge continues to pass a raw memory key only after a successful core
save. It never sees a key byte, `item_ref`, event ID, SQL result, or
projection. A store-owned attempt must derive the pseudonymous reference
immediately and retain no raw memory key after the async call returns.

## 2. Narrow future contract

The only prospective cross-crate surface is one feature-gated, opaque
`CurationBatchObservationHandle` plus its attempt. It has exactly this
semantic vocabulary:

```text
handle.begin() -> attempt | disabled | error
attempt.observe_saved(memory_key, saved_ordinal) -> ok | error
attempt.finish(item_count) -> finalized | incomplete/error
```

The surface has no general `append(event)`, no query/projection method, no
event struct constructor, no SQLite connection, no `StateStore` method, and
no key-provider getter. `disabled` is a normal abstention result, never a
successful finalized episode.

Construction is deliberately outside this contract: C2A may define the opaque
types and adapter, but only C2B may authorize a trusted constructor. C2C may
inject an already-constructed handle into `Hub`; the current `Hub` remains
`None` by default.

## 3. Feature and crate boundary

The proposed feature shape is:

```text
ab-store:  episode-observation-slice-c2
  -> depends on episode-observation-slice-b

ab-bridge: episode-observation-slice-c2
  -> depends on episode-observation-slice-c1
  -> forwards ab-store/episode-observation-slice-c2 only
```

Neither feature appears in `default`. C2 cannot enable C1 from a default build
or transitively activate C2 from an unrelated feature. `main.rs`, MCP tool
registration, `StateStore`, retrieval, sync/export, and schema migration
startup wiring remain out of scope.

## 4. Synthetic-provider decision

C2A tests may use only a store-private deterministic provider compiled under a
dedicated synthetic test feature. It must use fixed test bytes and a fixed
test epoch, must not inspect environment/CLI/database state, and must be
unconstructible from normal runtime code.

The synthetic provider proves only framing, ordering, collision/failure
semantics, and redaction boundaries. It is not a candidate production
custodian, does not establish key rotation, and may not cross the C2B gate by
being re-exported or selected at runtime.

## 5. Mandatory falsifiers

R14 requires a C2A implementation to fail its source/build gate if any of
these become possible:

| Falsifier | Required rejection |
| --- | --- |
| `StateStore` acquires an observation method or downcast | reject source |
| bridge imports `SqliteStore`, `tokio_rusqlite`, or a raw Slice B event | reject source |
| public API can append arbitrary events or read a projection | reject source |
| C2/C1 is default-on or `main.rs` constructs/injects a handle | reject source |
| a key comes from environment, CLI, generated fallback, or persisted raw key | reject source |
| duplicate/lookup/save failure emits an item or consumes an ordinal | reject tests |
| item/close failure yields a finalized projection | reject tests |
| disabled/missing-provider path writes any event | reject disposable-DB test |

## 6. Required C2A test packet

Before any C2A implementation can be accepted, its packet must contain:

1. a source checker covering every falsifier above;
2. synthetic disposable-DB tests for open/item/close, bad sequence,
   duplicate-event rollback, missing provider, item failure, and close failure;
3. a bridge-side fake/adapter test proving C1 preserves fail-open-core and
   fail-closed-sidecar behavior;
4. local and independent Linux `--locked` feature-isolated builds;
5. proof that default builds and runtime startup create no handle.

These tests must not open a user state database, emit a real observation,
enable retrieval, or use a production key.

## 7. Authority result

R14 resolves the four R13 interface questions at the design level, but grants
no C2A source authority. The next valid request is narrowly for a C2A source
preregistration/implementation gate that names the exact module paths, public
visibility, source checker, and synthetic test fixture. C2B key custody and
C2C runtime enablement remain separate owner decisions.
