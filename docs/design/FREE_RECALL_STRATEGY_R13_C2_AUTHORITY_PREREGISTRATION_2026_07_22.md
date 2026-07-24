# Free Recall Strategy R13 — C2 Authority Preregistration

Date: 2026-07-22

Status: **PREREGISTERED / DESIGN ONLY / C2 SOURCE AND RUNTIME CLOSED**

Prerequisites:

- R9 Slice B storage: accepted;
- R12 C1 orchestration: accepted;
- R10 producer and failure semantics: frozen.

## 1. Decision to be made

C2 must connect the default-off C1 `session_curate:curation_batch` observer
seam to Slice B's already-private SQLite observation storage without widening
`StateStore`, exposing SQLite through an MCP/API/retrieval surface, creating a
fallback key, or enabling a real producer by default.

R13 authorizes no source, Cargo, database, key, runtime, capture, retrieval,
merge, release, or deployment work. It is the decision packet required before
any such request.

## 2. Constraints already accepted

1. Core curation is fail-open; the observation sidecar is fail-closed.
2. C1's `Hub` field is optional and `None` by default. `build_hub` does not
   inject a capability.
3. Slice B's schema, append, and projection remain private `SqliteStore`
   details and its non-test gate denies I/O.
4. `StateStore` must not gain observation methods, downcasts, or an alternate
   database connection.
5. The bridge may provide a just-saved raw memory key only to one trusted
   in-process observation capability. That capability must derive a
   pseudonymous `item_ref` immediately and must not retain or log the raw key.
6. An open/partial trace is not a finalized episode and has no retrieval value.

## 3. Rejected shapes

| Shape | Rejection reason |
| --- | --- |
| Add observation methods to `StateStore` | Widens the general store contract and leaks a Slice B concern. |
| Let `ab-bridge` access `SqliteStore` or open a second SQLite connection | Breaks crate ownership and creates competing storage authority. |
| Make Slice B append/projection generally public | Creates an accidental API/retrieval surface before the protocol is proven. |
| Read a key from environment, CLI, database, or generated fallback | Violates explicit key custody and silently changes activation semantics. |
| Treat a disabled, missing-key, or append-failed path as finalized | Violates fail-closed sidecar truthfulness. |
| Couple this gate to retrieval, sync/export, MCP exposure, or training | Expands a write-side seam into unrelated authority. |

## 4. Proposed C2 decomposition

R13 intentionally separates three authorities that must not be collapsed.

### C2A — private storage adapter source

Possible source scope, only after a separate authorization:

- one feature-gated, narrow store-owned adapter/factory that can implement the
  C1 bridge capability through an adapter in `ab-bridge`;
- one opaque request path for `begin`, saved-key observation, and `finish`;
- no `StateStore` changes, no public retrieval API, no configuration loader,
  and no main-process injection;
- synthetic test-only key material and disposable SQLite tests only.

The boundary must ensure that the adapter, rather than the bridge caller,
allocates episode/run/event IDs, derives `item_ref`, computes payload hashes,
and owns append ordering. Bridge code may neither receive key bytes nor create
raw Slice B events.

### C2B — trusted key custody decision

This is not implied by C2A. Before a real provider can exist, an owner must
choose and authorize a key custodian, rotation/version semantics, in-memory
handling, observability redaction, and revocation behavior. The accepted
decision must prove that no environment/CLI fallback, generated key, plaintext
log, or durable raw-memory-key retention exists.

### C2C — runtime enablement experiment

This is not implied by C2A or C2B. It would separately define an explicit
default-off configuration and the required conjunction:

```text
C1 feature + C2 adapter + explicit runtime flag + trusted provider + injected capability
```

If any operand is absent, curation proceeds with no observation event. C2C
requires a disposable database, a bounded synthetic capture, and a falsifier
that proves disabled/missing-key/error paths emit no finalized episode.

## 5. C2A acceptance criteria

A future C2A source request must provide all of the following before source is
accepted:

- a cross-crate contract that is feature-gated and narrower than `StateStore`;
- compile-time evidence that no default feature enables C1/C2;
- a synthetic provider whose key cannot be supplied by normal runtime code;
- deterministic disposable-DB tests for finalized open/item/close, duplicate
  event rejection, append failure, missing provider, and item failure;
- negative source checks rejecting `StateStore` widening, direct bridge SQLite,
  public append/projection/retrieval exposure, environment/CLI keys, fallback
  keys, `main.rs` wiring, and default-on feature forwarding;
- separate local and independent Linux `--locked` build/test evidence.

Passing C2A would still leave C2B, C2C, retrieval, sync/export, MCP exposure,
real capture, merge, release, deployment, and training closed.

## 6. Required decision packet before C2A

The next owner-facing packet must answer these four questions explicitly:

1. What exact feature name gates C2A, and which crates may depend on it?
2. What is the single opaque cross-crate factory/adapter interface, including
   the ownership of raw saved keys and derived pseudonymous references?
3. Which synthetic-only provider is admissible in C2A tests, and what
   compile-time/runtime barrier prevents it from becoming a production key?
4. Which exact test traces falsify accidental activation, key leakage, and
   incomplete-episode visibility?

Until these are answered and separately authorized, C2 remains closed.

## 7. Negative authority

R13 does not authorize source edits, features, database migration/execution,
real keys or key generation, runtime configuration, producer injection,
observation capture, retrieval, sync/export, MCP/API exposure, merge, release,
deployment, training, or BioCortex integration.
