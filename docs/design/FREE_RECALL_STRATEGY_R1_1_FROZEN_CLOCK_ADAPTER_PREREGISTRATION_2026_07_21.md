# Free Recall Strategy R1.1 — Frozen-Clock Adapter Preregistration

Date: 2026-07-21

Status: **PREREGISTERED / EVALUATION ONLY / NO MCP OR RUNTIME AUTHORITY**

Parent blocker:
`docs/design/FREE_RECALL_STRATEGY_R1_FROZEN_SNAPSHOT_RESULT_2026_07_21.md`

## 1. Objective

Remove the one known uncontrolled input that blocked R1: wall-clock resolution
inside the three retrieval modes. R1.1 adds a store-level evaluation adapter
whose caller must bind one non-negative Unix `as_of_secs` for FTS, Hybrid, and
Semantic search.

The adapter exists only so the unchanged R1 strategy experiment can be
replayed deterministically. It is not a new retrieval strategy.

## 2. Frozen interface

One JSON request contains:

- a disposable SQLite clone path;
- one query;
- mode: exactly `fts`, `hybrid`, or `semantic`;
- limit: exactly the R1 budget of 20;
- one explicit non-negative `as_of_secs` shared by the entire replay;
- Hybrid constants `rrf_k=60`, `expand_top=10`;
- Semantic threshold `0.3`.

The response contains ordered keys and aggregate metadata needed by the private
runner. It is ephemeral and must not be committed. The final repository result
continues to expose only fixture IDs, ranks/counts/timings, and hashes.

## 3. Algorithm preservation

- FTS calls the existing `memory_search_as_of` implementation.
- Hybrid calls the existing `memory_search_hybrid_as_of` implementation with
  bounded, non-mutating graph reads.
- Semantic receives an additive `memory_search_semantic_as_of` store method
  that reuses the same embedding, threshold, scope visibility, configured
  blend weights, and score formula as production Semantic; only `now_secs()`
  is replaced by the caller's `as_of_secs`.
- Every score sort must use a deterministic key tie-breaker.
- The source snapshot and base clone are never opened writable by the adapter.

## 4. Negative authority

R1.1 must not:

- add an MCP tool or an `as_of_secs` argument to production `memory_search`;
- alter default retrieval ordering, weights, environment defaults, or telemetry;
- write access, coactivation, outcome, or retrieval-feedback state;
- access the live source database directly;
- run BioCortex, train a router, deploy a binary, or merge the branch;
- change any R1 fixture, arm, budget, route rule, score, or decision gate.

Unsupported stores and malformed requests fail closed.

## 5. Acceptance gates

### A — Surface isolation

- adapter is a store example/evaluation binary, absent from MCP capabilities;
- it uses `SqliteStore::open_read_only`;
- negative and unknown modes fail;
- a missing/negative clock fails before search.

### B — Algorithm parity

- at the same clock, frozen FTS equals existing FTS-as-of;
- frozen Hybrid equals existing Hybrid-as-of with non-mutating graph reads;
- frozen Semantic uses the production blend weights/formula and differs only
  in clock injection plus deterministic tie-breaking;
- repeated calls at the same clock return byte-identical ordered keys.

### C — Replay determinism

- one frozen `as_of_secs` is recorded for the whole run;
- each query×mode observation starts from a fresh clone of one base snapshot;
- forward and reverse replay produce exact-page equality for all three modes;
- any mismatch stops before strategy scoring and emits no result JSON.

### D — Original R1 result gate

Only after A–C pass may the unchanged R1 evaluator emit arm scores and apply
the preregistered R1 strategy, mechanism, router, and cost gates.

## 6. Rollback

The entire surface is removable by reverting its store trait method, SQLite
implementation, example binary, and replay-adapter invocation. Since no MCP or
runtime call site consumes it, rollback requires no migration or deployment.
