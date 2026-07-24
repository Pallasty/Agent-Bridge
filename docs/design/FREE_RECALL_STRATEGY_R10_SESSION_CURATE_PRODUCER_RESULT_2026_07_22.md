# Free Recall Strategy R10 — `session_curate` Producer Result

Date: 2026-07-22

Status: **PASS / R11 C1 SOURCE REQUEST ELIGIBLE / NO SOURCE OR BUILD AUTHORITY**

Preregistration:
`docs/design/FREE_RECALL_STRATEGY_R10_SESSION_CURATE_PRODUCER_PREREGISTRATION_2026_07_22.md`

Validator:
`scripts/eval/free_recall_strategy_r10_session_curate_producer.py`

## 1. Decision

R10 passes. The `session_curate:curation_batch` producer can be introduced as
an optional `Hub` capability without widening `StateStore`, and its sidecar
failure can be isolated from core memory curation while still refusing to
finalize incomplete observation traces.

The pass opens only a separately owner-authorized R11 **C1 source** request:
bridge-private orchestration, explicit candidate accounting, optional fake
capability injection, and unit tests. It does not open the Slice B storage
adapter to the bridge and does not permit real sidecar writes.

## 2. Source mapping findings

The live source review identified one prerequisite correctness defect and one
architecture constraint:

- `session_curate` currently mixes prior-handoff scan failures with candidate
  lookup/save failures, then subtracts that mixed count from candidate count to
  infer duplicates. R11 C1 must replace this with an explicit candidate
  outcome ledger before adding producer calls.
- `Hub` carries `Arc<dyn StateStore>`, while the Slice B adapter remains a
  private `SqliteStore` detail. R11 C1 must inject a separate optional
  curation-batch capability; it must not widen or downcast `StateStore`, open a
  second SQLite connection, or make the adapter public.

The existing aggregate semantic lifecycle event remains unchanged and is not
an episode event.

## 3. Public-synthetic evidence

Command shape, run twice:

```text
python3 scripts/eval/free_recall_strategy_r10_session_curate_producer.py \
  --selftest --out /tmp/free-recall-r10-{a,b}.json
cmp /tmp/free-recall-r10-a.json /tmp/free-recall-r10-b.json
```

Results:

- verdict: `PASS`;
- canonical errors: `0`;
- public-synthetic trace cases: `11`;
- trace errors: `0`;
- directed mutations rejected: `42 / 42`;
- canonical plan SHA-256:
  `ec7db6e5d2595083d8ec3343607141e8f27c39e08c66e6f41c4598e100e3c55e`;
- two report files were byte-identical;
- report SHA-256:
  `2c290487d5c370d02a3eed88ebf5ce069defc945e699154496c5d1494ca351cd`;
- validator SHA-256:
  `3f1ef065d5b9348f9b842d964195f5d37586443b7101a44356b5030fc8073623`;
- preregistration SHA-256:
  `98423a8b0c6ce058fb7ec4477755645feb618a9b46b16ff92d89b1813deba159`.

The traces cover dry-run, no-store, missing gate, empty batches, all
duplicates, mixed saved/duplicate/lookup/save/auxiliary errors, begin failure,
first and later item failure, close failure, and the auxiliary-error
underflow counterexample.

## 4. Frozen R11 C1 behavior

R11 C1, if separately authorized, may implement only:

1. an explicit saved/duplicate/lookup-error/save-error ledger, with auxiliary
   errors separate;
2. a bridge-private observation capability and optional `Hub` dependency that
   defaults to absent;
3. begin immediately before the non-empty candidate loop, after auxiliary
   scanning;
4. item only after memory-save success, positioned by successful-save ordinal;
5. close only for a positive, complete, gap-free observed set;
6. a first-failure latch that suppresses later sidecar calls while all core
   curation continues;
7. deterministic fake-capability unit tests only.

It may not wire `SqliteStore`, construct a production key provider, load a
secret or runtime flag, append a real event, change the MCP response schema, or
add retrieval/sync/export behavior.

## 5. Authority ledger

- R11 C1 source request eligible: **true**
- Rust/SQL/Cargo source changed by R10: **false**
- build or Cargo test authorized/run: **false**
- database accessed: **false**
- producer integrated: **false**
- C2 storage/key/runtime integration open: **false**
- real capture/retrieval/sync/MCP API open: **false**
- merge/release/deployment open: **false**

## 6. Next gate

The next gate is an explicit owner decision on R11 C1 source only. Acceptance
of that source would still require a separate build gate, followed by a
separate C2 design/authorization gate before any real sidecar event can exist.
