# Agent Authority Signed Trust Root S3 Preregistration

Date: 2026-07-16

Status: PREREGISTERED_WITH_ERRATUM / OFFLINE_ED25519 / PUBLIC_TEST_ROOT / NO_RUNTIME_AUTHORITY

## Question

Can an offline verifier use a separated public trust registry and mature
Ed25519 implementation to reject forged, tampered, untrusted, revoked, stale,
replayed, transferred, or unavailable authority receipts without gaining any
runtime or persistence authority?

## Frozen Inputs

- design:
  docs/design/AGENT_AUTHORITY_SIGNED_TRUST_ROOT_S3_2026_07_16.md
- public trust registry:
  crates/bridge/tests/fixtures/agent_authority_trust_registry_s3.json
- signed receipt corpus:
  crates/bridge/tests/fixtures/agent_authority_signed_receipts_s3.json
- checker:
  crates/bridge/examples/agent_authority_signed_trust_root_s3.rs
- parent S2 design, fixture, result, and checker.

Frozen hashes:

- trust registry:
  1e26edf7a5c71ac972d5c1c7e2496d8c1baa772d9571db995cfac04fe6c3d573
- signed receipt corpus:
  1a15620e6dc16166d71b4458d5207eacf30579b8f631c48f85ac62fba2456d8d
- S2 design:
  5c34109bb215b017549f5012a0352f31b86d01f3d3cadbfcc7d5f62cc850a266
- S2 fixture:
  a51b545d91fceecf81ec03d5355a686e0728b6ab92130b9cfc75b9a1983cd82c
- S2 result:
  f56ee48902ffe60ce9a432c898a8d796ac3b998621b12483f3114d2c81fac31f

## Frozen State Counts

- total: 27;
- verified controls: 4;
- invalid: 4;
- untrusted: 3;
- revoked: 2;
- stale: 4;
- replayed: 1;
- out_of_scope: 8;
- unavailable: 1.

Every non-control is adversarial. No adversarial case may derive verified and
every control must derive verified.

## Pre-Pass Erratum

The first implementation run showed that `wrong_action_rejected` could not
reach the preregistered scope stage because its original primary key did not
authorize the changed action. The corrected freeze adds a same-owner public
test key that authorizes `memory_write`, selects it for that case, and
recomputes the signature. This preserves the key-binding-first pipeline and the
original expected state/counts. The correction occurred before any passing run;
the final hashes above are authoritative.

## Frozen Invalid Cases

1. malformed signature Base64;
2. decoded signature length is not 64 bytes;
3. a signature bit is changed;
4. a signed payload field is changed after signing.

## Frozen Untrusted Cases

1. key id absent from the evaluator registry;
2. receipt algorithm is not allowed and differs from the selected key;
3. selected key does not authorize the signed issuer, principal, action, or
   policy.

## Frozen Revocation, Time, And Replay Cases

- signing key revoked;
- receipt id revoked;
- receipt expired beyond skew;
- receipt issued beyond future skew;
- signing key expired beyond skew;
- signing key not yet valid beyond skew;
- receipt issuance predates the selected key validity window;
- nonce already consumed.

The exact receipt skew boundaries remain verified controls.

## Frozen Scope Cases

Validly signed receipts are out_of_scope when they mismatch:

- action;
- target;
- scope;
- decision source;
- session epoch;
- resume parent;
- adapter identity/build/capabilities;
- evidence.

## Frozen Pipeline

1. availability;
2. structural and signature encoding checks;
3. public key lookup, algorithm allowlist, and key-policy bindings;
4. ring Ed25519 verification over canonical bytes;
5. revocation;
6. key and receipt time validity;
7. read-only nonce replay snapshot;
8. current context;
9. verified.

Expected status/reasons are never classifier inputs.

## Required Tests

1. the frozen corpus derives the exact eight-state distribution;
2. every case status and exact lexical reason list matches;
3. zero false accepts and zero control false rejects;
4. changing expected labels cannot change derived output;
5. all 22 claims fields affect canonical bytes;
6. duplicate keys, duplicate case ids/nonces, invalid public keys, stale source
   pins, and unsorted reasons fail closed;
7. payload/signature mutation fails ring verification;
8. reports are structurally equal and byte-identical across runs;
9. read-only consumption preview and all authority nonclaims remain false.

## TDD Gate

The checker test skeleton must compile-fail first on missing fixture, registry,
canonicalization, signature verification, state, and suite APIs. The minimal
implementation may be added only after that RED is captured.

## Pass Meaning

A pass proves deterministic offline verification against the frozen public
test registry and receipt corpus. It does not prove that a production trust
root is authentic, available, uncompromised, correctly rotated, or bound to the
owner. It does not prove atomic replay protection or live T6 safety.

## Prohibited Actions

- no production/private credential or key;
- no secret store, network identity provider, or online verifier;
- no replay/revocation persistence or live state mutation;
- no MCP/T6 runtime consumer;
- no shadow/executor execution or runtime enablement;
- no deploy, authority grant, master merge, or production-security claim.
