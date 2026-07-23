# Free Recall Strategy R17 — C2B Key Custody Design

Date: 2026-07-23

Status: **DESIGN DECISION / C2B SOURCE NOT AUTHORIZED / C2C CLOSED**

Parent acceptance:
`docs/design/FREE_RECALL_STRATEGY_R16_C2A_BUILD_RESULT_2026_07_23.md`

## 1. Scope

C2B answers only how a future real observation provider may obtain key
material. It does not authorize a provider, a runtime constructor, a user
database, a release, or deployment. C2A's deterministic provider remains the
only executable path.

The design target is an opaque store-owned capability. The bridge may request
an observation attempt, but it must never receive a key, key epoch material,
provider object, raw event, SQLite handle, or custody error containing secret
data.

## 2. Decision

The canonical C2B boundary is a store-owned `TrustedEpisodeRefKeyProvider`
that is created only inside an explicitly authorized runtime session. It
returns borrowed key material for one derivation operation; the store derives
the item reference immediately and does not persist the bytes.

The initial real-provider implementation must use an OS- or daemon-owned
secret store, selected per deployment, behind a narrow store-side adapter.
The secret store is not selected or accessed by bridge code, MCP arguments,
environment variables, the SQLite database, or a repository file. A provider
must identify an epoch and key purpose, but must not expose the secret itself
outside the store process.

No single platform backend is accepted by R17. macOS Keychain, Linux Secret
Service, or a separately authorized local daemon are candidates for a later
implementation packet; each needs its own custody and availability evidence.

## 3. Non-negotiable invariants

1. **No source custody:** no key bytes, key path, token, or secret-store
   selector is committed to the repository or test fixture.
2. **No ambient configuration:** no `std::env`, CLI flag, MCP argument, or
   SQLite setting may select or carry key material.
3. **No bridge visibility:** `ab-bridge` depends only on the opaque C2A/C1
   adapter surface and never imports the provider, key material, or store
   internals.
4. **Bounded lifetime:** key material is borrowed for derivation and must not
   be cloned, serialized, logged, cached in a global, or retained by an
   observation attempt.
5. **Purpose and epoch binding:** derivation binds the fixed domain, purpose,
   and active epoch; an unknown, revoked, or mismatched epoch fails closed.
6. **Rotation without retroactive rewriting:** a new epoch may derive future
   references, while old references remain identifiable by epoch and are not
   re-derived in place.
7. **Redacted failure:** errors crossing the store/bridge boundary are coarse
   (`Begin`, `Item`, `Close`) and contain no provider path, backend response,
   epoch secret, or token.
8. **Revocation:** provider unavailability or revocation prevents new
   observation attempts; it must not disable core memory saves or make a
   previously finalized trace appear writable.

## 4. Required custody state machine

```text
unavailable/revoked
        │ authorized acquire
        ▼
  borrowed(active epoch) ── derive ──> released
        │                                │
        └──── error/revoke ──────────────┘
```

The runtime must distinguish `unavailable`, `revoked`, `unknown_epoch`, and
`derivation_failed` internally for diagnostics, while exposing only the
coarse fail-closed adapter errors externally. A failed item poisons the
attempt and suppresses close, preserving C2A's no-finalized-after-failure
invariant.

## 5. Required C2B source packet

Before any source implementation is authorized, the packet must specify:

- one exact custody backend and its platform scope;
- the acquisition API and proof that returned bytes are borrowed/bounded;
- purpose/epoch/rotation/revocation semantics;
- redaction tests covering errors, logs, tracing, panic text, and process
  arguments;
- source checker mutations for env/CLI/MCP/SQLite/key persistence and bridge
  leakage;
- deterministic fake-provider tests with no real secret or external account;
- a negative test proving normal startup cannot construct the provider;
- local and independent Linux replay commands, with no deployment claim.

## 6. Explicitly deferred

R17 does not authorize:

- selecting or installing a keychain/secret daemon;
- generating, importing, rotating, or revoking a real key;
- changing `StateStore`, schema, MCP tools, runtime startup, retrieval,
  sync/export, or training/BioCortex paths;
- user-facing observation, production data, merge to master, release, or
  deployment.

The next valid action is an owner-authorized C2B source preregistration that
names one custody backend and supplies the packet in §5. Until then C2A is
the accepted terminal implementation for this lane.
