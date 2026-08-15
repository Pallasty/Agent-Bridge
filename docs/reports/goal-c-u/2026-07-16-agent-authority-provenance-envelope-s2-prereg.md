# Agent Authority And Provenance Envelope S2 Preregistration

Date: 2026-07-16

Status: PREREGISTERED / STATIC / SOURCE_PINNED / NO_RUNTIME_AUTHORITY

## Question

Can a deterministic offline verifier distinguish an independently bound
authority receipt from Agent-controlled claims while preserving explicit
non-authority and without implementing real cryptography or runtime wiring?

## Frozen Inputs

- design:
  docs/design/AGENT_CONTROL_PLANE_AUTHORITY_PROVENANCE_ENVELOPE_S2_2026_07_16.md
- fixture:
  crates/bridge/tests/fixtures/agent_authority_provenance_envelope_s2.json
- checker:
  crates/bridge/examples/agent_authority_provenance_envelope_s2.rs
- S1 design:
  docs/design/CODEX_REDTEAM_MODE_T6_AGENT_COMPROMISE_MAPPING_S1_2026_07_16.md
- S1 mapping:
  crates/bridge/tests/fixtures/agent_compromise_resilience_s1_mapping.json
- S1 result:
  docs/reports/goal-c-u/2026-07-16-agent-compromise-resilience-s1-result.md

## Frozen State Machine

The checker derives one of:

- verified;
- invalid;
- stale;
- out_of_scope;
- replayed;
- unavailable.

Precedence is unavailable, invalid, stale, replayed, out_of_scope, verified.
The expected status and expected reasons are consulted only after derivation.

## Frozen Case Counts

- total cases: 23;
- verified controls: 4;
- invalid cases: 7;
- stale cases: 2;
- replayed cases: 1;
- out-of-scope cases: 8;
- unavailable cases: 1.

Every negative case is adversarial. No adversarial case may derive verified.
Every control must derive verified.

## Frozen Invalid Cases

1. receipt absent from the trusted fixture registry;
2. synthetic attestation differs from the trusted record;
3. presented claims differ from trusted claims;
4. issuer, principal, and verifier are outside trusted sets;
5. policy version is not accepted;
6. a required field is empty;
7. expiry does not follow issuance.

## Frozen Stale And Replay Cases

- expiry is beyond the allowed clock-skew boundary;
- issuance is beyond the allowed future-skew boundary;
- nonce is already listed as consumed.

The exact skew boundaries remain valid controls.

## Frozen Scope Cases

Independently bound receipts are rejected as out_of_scope when they mismatch:

- action class;
- target digest;
- scope digest;
- decision-source digest;
- session-epoch digest;
- resume-parent digest;
- adapter identity, build, or capabilities;
- evidence digest.

## Structural And Binding Rules

- all required strings are non-empty;
- all digest fields match sha256:<64 lowercase hex>;
- issued_at_unix is strictly less than expires_at_unix;
- receipt ids, case ids, trusted receipt ids, and trusted nonces are unique;
- trusted and presented claims are canonicalized independently;
- canonical bytes are domain-separated, typed, ordered, and length-bound;
- a presented digest or expected status cannot authorize itself;
- reasons are deterministic and exact.

## Source Pins

- T6 source commit:
  a1c9469e9a14cd73159d34974f0e99714ce5a1f0
- S1 result commit:
  232cadaced8ac1ab6e18907d451fba9208d03079
- S1 design SHA-256:
  0d9db25cc61bfe9ccd0f146b33a01ee033b5c5451784912419609c42fad5954d
- S1 mapping SHA-256:
  a08d3faf25b82fd84f5f0e27bba55485a6b3f9d3e00a9f22413eb9a971b37c8e
- S1 result SHA-256:
  8747ef00325852bdec3098565ca92c85000a8705e57a35e8381455ce8e98203e

## Required Tests

1. the frozen suite produces the exact six-state count distribution;
2. every case status and reason list matches independently derived output;
3. zero false accepts and zero control false rejects;
4. all claims bindings participate in canonical digest comparison;
5. malformed fixture structure and duplicate identities fail closed;
6. changing expected labels does not change the derived result;
7. repeated evaluation yields equal reports and byte-identical JSON;
8. every authority and production claim remains false.

## Pass Meaning

A pass proves only that this static synthetic fixture and verifier implement the
preregistered state machine and binding semantics reproducibly. It does not
prove cryptographic authenticity, identity-provider correctness, replay-store
durability, live T6 safety, runtime containment, or production authorization.

## Prohibited Actions

- no credentials, keys, real signatures, or secret access;
- no network or external verifier;
- no hostile upstream code execution or hostile MCP dispatch;
- no memory, graph, retrieval, session, adapter, approval, or runtime write;
- no T6/MCP integration, shadow execution, runtime enablement, deployment,
  authority grant, or master merge.
