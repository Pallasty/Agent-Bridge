# Recall Eval Active-Corpus Snapshot Gate

Date: 2026-07-01
Host: `pallasting-ThinkBook-14-G5-IRH`
Worktree: `/Data/CascadeProjects/agent-bridge`
Scope: eval-only gate hygiene

## Why

`recall_eval` now distinguishes the defined 18-case corpus from the cases whose
expected keys are still active in the selected database. On the current live
aio2 store, the honest denominator is 9 active cases:

```text
cases_total:           18
cases_with_present:    9
cases_with_active:     9
```

That fixes live-store scoring, but canonical before/after comparisons still
need a frozen `AB_BASELINE_DB`. A frozen snapshot should now carry two
identities:

1. store identity: active row count, edge count, newest memory timestamp;
2. corpus identity: `recall_eval --check-corpus` expected-key health.

Without the second identity, two snapshots can both be "pinned" while answering
different subsets of the held-out corpus.

## Implementation

Updated `scripts/verify-gte-768-canonical-snapshot-gate.sh`.

Added flags:

```text
--check-corpus
--expect-corpus-total N
--expect-corpus-present N
--expect-corpus-active N
```

Behavior:

- `--check-corpus` runs `cargo run -p ab-bridge --example recall_eval --
  --check-corpus` with `AB_BASELINE_DB` pinned to the explicit snapshot.
- Any `--expect-corpus-*` flag implies `--check-corpus`.
- Corpus health is parsed into one compact summary line:

```text
corpus_health_summary=cases_total=18 cases_with_present=9 cases_with_active=9
```

- Mismatched corpus expectations set
  `NO_GO_CORPUS_HEALTH_MISMATCH`.
- A failed health command sets `NO_GO_CORPUS_HEALTH_FAILED`.
- `--run-rehearsal` always records corpus health for the copied snapshot before
  reindexing; if corpus health fails, rehearsal stops before reindex.
- Candidate classification now treats lowercase `snapshot` and `checkpointed`
  names as canonical-looking hints.

## Verification

Syntax and help:

```sh
bash -n scripts/verify-gte-768-canonical-snapshot-gate.sh
scripts/verify-gte-768-canonical-snapshot-gate.sh --help
```

No-snapshot strict gate still blocks:

```sh
scripts/verify-gte-768-canonical-snapshot-gate.sh --skip-preflight --strict
```

Result:

```text
status=NO_GO_CANONICAL_SNAPSHOT_MISSING warnings=0
```

Positive corpus-health check used a temporary copy of the live DB, not the live
DB itself:

```sh
scripts/verify-gte-768-canonical-snapshot-gate.sh \
  --skip-preflight \
  --search-roots /tmp/tmp.0EGWwMk0A9 \
  --snapshot /tmp/tmp.0EGWwMk0A9/state.snapshot.test.db \
  --check-corpus \
  --expect-corpus-total 18 \
  --expect-corpus-present 9 \
  --expect-corpus-active 9 \
  --strict
```

Result:

```text
corpus_health_summary=cases_total=18 cases_with_present=9 cases_with_active=9
status=READY_FOR_CANONICAL_REHEARSAL warnings=0
```

Negative expectation check:

```sh
scripts/verify-gte-768-canonical-snapshot-gate.sh \
  --skip-preflight \
  --search-roots /tmp/tmp.0EGWwMk0A9 \
  --snapshot /tmp/tmp.0EGWwMk0A9/state.snapshot.test.db \
  --check-corpus \
  --expect-corpus-total 18 \
  --expect-corpus-present 9 \
  --expect-corpus-active 10 \
  --strict
```

Result:

```text
BLOCK: corpus cases_with_active mismatch: expected 10 got 9
status=NO_GO_CORPUS_HEALTH_MISMATCH
```

The temporary DB copy was removed after validation.

## Boundary

This slice does not change production `memory_search`, tokenizer/schema/reindex,
ranking, graph expansion, semantic retrieval, MCP tools, memory rows, deploy
behavior, or the live production memory store.

It only extends an existing snapshot gate so canonical recall comparisons record
the active answerability of the held-out corpus before claims are made.
