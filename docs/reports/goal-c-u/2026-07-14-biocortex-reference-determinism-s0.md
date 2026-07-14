# BioCortex / AB reference determinism S0

Date: 2026-07-14

Status: **S0 mechanism implemented as an explicit query-only reference
surface; formal Track B capture remains blocked; no BioCortex runtime
influence**

## Scope

This slice closes the Reference Determinism S0 mechanism in the ordered Track B
path. It does not run BioCortex, add an MCP tool, change the default ranking
formula, prove that an arbitrary live database is a closed snapshot, or qualify
the mutable store as truth evidence. The new surface is deliberately opt-in and
fails closed on any backend that cannot bind the contract.

## What is bound

- `memory_search_as_of(..., as_of_secs)` uses one caller-supplied Unix-second
  clock for every FTS score in a request. Reference TTL suppression consumes
  the same clock and excludes a `ttl:<N>d` row exactly at its expiry boundary.
- FTS and every downstream ranking boundary use score-descending plus binary
  memory-key tie-breaking. Graph edge and RRF candidate lists are sorted by
  score, then key/edge identity before fusion. Case-insensitive exact-key
  fallback prefers a binary-exact key and otherwise uses binary key order.
- Reference hybrid expansion uses a caller-bound graph fan-out (default 64)
  and reads graph-only records through `memory_peek`, so graph expansion does
  not bump `access_count` or `last_accessed_at`. The cap is a provisional
  engineering bound: a content-free 2026-07-14 owner-store audit observed
  degree p99 36 and maximum 123; it is not a quality target.
- The frozen `limit=10` profile overfetches a fused pool of 50 before applying
  `exclude_kinds=["skill"]`; that fixes the FTS ranked pool at 200 and raw FTS
  scan cap at 800. Exclusion never silently shrinks the upstream pool.
- `coactivation_rerank=true` is request-bound and matches the preregistered
  reference policy (`AGENT_BRIDGE_COACTIVATION_RERANK_DISABLE=0`). Its read is
  side-effect-free, errors propagate, and post-boost ties resolve by binary key.
- Graph, exact-key, graph-record decode and coactivation read errors are
  terminal on the reference path. The legacy production hybrid keeps its
  existing best-effort graph behavior.
- `MemorySearchReferenceOptions` applies a hard exact UTF-8 context-byte
  budget. Model-token counts are intentionally not fabricated here; the exact
  model tokenizer/code/model binding remains a later Track B admission field.
- `MemorySearchReferenceHit` is a stable context projection. It includes key,
  kind, content, tags, related keys, scope, durable timestamps and lifecycle
  fields, but excludes mutable access telemetry, importance/score rerank
  metadata and graph-only relationship payloads.
- `scripts/run-memory-reference-s0.sh` requires a clean tracked worktree,
  opens the supplied DB query-only, and launches from `env -i` with only
  toolchain locations plus the preregistered reference-policy variables. The
  output says `query_only_connection=true` and `closed_snapshot_bound=false`;
  snapshot closure remains an admission responsibility.

## Verification

The store unit checks cover:

1. repeated frozen-as-of searches produce identical key order, binary exact-key
   priority and score-tie order;
2. bounded reference hybrid expansion never exceeds the requested fan-out;
3. graph-only reference reads preserve access telemetry, while graph-query and
   graph-record decode corruption fail closed;
4. TTL is live one second before expiry and suppressed exactly at expiry;
5. enabled coactivation reranking is stable and a missing coactivation table
   fails closed;
6. context projection omits access telemetry and fails closed when its exact
   UTF-8 byte budget is exceeded;
7. non-SQLite/default trait paths reject the reference surface rather than
   silently falling back to a wall-clock search.

The clean runner is a mechanism check only. It compiles offline with one job,
incremental compilation disabled, an isolated target directory and `ab-store`
default features disabled to keep its resource envelope small. A future
admission packet still has to bind the exact source/binary identity, SQLite
runtime, verified closed snapshot, effective request JSON, exact model
tokenizer, hardware, storage manifest and reviewer custody before any real
Track B capture.
