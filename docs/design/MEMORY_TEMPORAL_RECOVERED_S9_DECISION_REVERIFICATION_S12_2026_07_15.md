# S12 recovered S9 decision re-verification

Date: 2026-07-15
Decision: `BLOCKED_FAIL_CLOSED`
Scope: private, default-off, synthetic preregistration

## Outcome

S12 closes one narrow executable gap: given a private S10 `COMMITTED` recovery observation that has already passed the S10 verifier, complete canonical S9 request/decision bytes, and a signed S11 L1 operation record, Agent-Bridge can purely re-verify the historical S9 decision and return a new private historical observation.

It does **not** recover S9's one-attempt currentness token. It does not prove that the decision remains active, fresh, unrevoked, or safe at downstream use. It admits no payload and unlocks no side effect.

## Why the chain has three links

```text
verified S10 COMMITTED recovery projection
        │ operation / challenge / request / decision / journal identity
        ▼
signed S11 L1 operation record ── verify independent S11 Ed25519 permit
        │ frozen original request + canonical decision commitments
        ▼
complete canonical S9 request + signed decision ── verify S9 Ed25519 permit
        │
        ▼
private historical observation
NOT currentness · NOT admission · NOT transport authorization
```

S9 plus S11 alone would show that a signed wrapper freezes the same digests, but not that those digests came from an authenticated S10 recovery lookup. S10 is therefore a required private input. S12 does not repeat the S10 provider lookup or raw S10 signature verification; it accepts only the non-serializable result of the shared S10 verifier.

## Shared predecessor seams

S12 adds no public API. It exposes only `pub(super)` shapes and pure verifier seams inside the already private temporal replay module:

- S9 now separates the online provider call from `verify_external_currentness_decision_v1`. The online path still validates before calling the provider, then delegates exact decision verification to the shared pure function.
- S10 now separates provider lookup from `verify_external_operation_recovery_observation_v1` and carries exact scope/original-operation fields in its private verified projection.
- S11 now separates authenticated L1 verification from synthetic L2 checksum validation. S12 calls only `verify_signed_committed_operation_l1_v1`.

The shared S9 seam also rejects oversized decision labels before canonical
decision-message framing can allocate from attacker-controlled label lengths.
Accepted-request behavior and the online path's single provider call are
unchanged; malformed-input error priority and resource behavior are
intentionally hardened, with direct S9 and S12 regressions.

None of these types has a production permit constructor, public re-export, Bridge caller, `StateStore` caller, network adapter, or serde representation.

## Canonical input rule

S12 receives typed S9 values and the exact carried canonical messages. It reconstructs both S9 messages using the predecessor's fixed framing and requires byte-for-byte equality:

```text
frame(value) = u64be(len(value)) || value
message       = frame(domain) || frame(field_1) || ... || frame(field_n)
u64           = exactly 8-byte big endian
```

Empty messages and messages above 65,536 bytes fail closed. Truncation, appending, reordering, substitution, unknown schema interpretation, or any typed/raw mismatch yields no observation. S12 deliberately implements no runtime parser or carrier; test fixture availability is not production byte availability.

## Authentication and cross-binding

The following are independently required:

1. The original S9 request digest is recomputed from canonical bytes.
2. The original S9 decision signature is verified with an out-of-band S9 permit.
3. All S9 `ACTIVE`, provider/signer, term/revision, epoch/record/generation/keyset, predecessor-revocation, custody-claim, and decision-identity checks pass.
4. The S10 projection is already verified `COMMITTED` evidence and matches scope, provider, operation, challenge, request digest, decision digest, and journal identity.
5. The S11 request and record pass independent S11 L1 signature verification.
6. S11 scope, provider, operation, challenge, request digest, decision digest, trust policy, and journal generation match S9/S10.
7. The S11 authenticated L1 revision and record sequence exactly equal the operation record recovered by S10, the S10 lookup term does not regress below the S11 commit term, and the S10 observed high-water revision is equal or later. S9 authority revision is a separate domain and is never equated with the operation-journal revision.
8. S9 and S11 signer key IDs and public keys are role-distinct.

The S9 registry generation and S10/S11 journal generation remain different concepts. S12 never equates them.

## Authority snapshot

S11's `authority_snapshot_sha256` is no longer accepted as a meaningful name alone. S12 recomputes it under:

```text
agent-bridge/track-b/recovered-s9-decision-reverification/authority-snapshot/v1
```

It binds the S12 policy, S9 contract hash, exact request/decision digests, full scope, operation/challenge, provider identity, term/revision/sequence, active epoch/record/registry generation/keyset, revocation relationship commitments, decision ID, S9 signer identity/version, and trust policy.

This is a local digest formula over an independently verified signed decision. It is not a new signature or owner receipt.

## Historical chain commitment

The successful local observation commits under:

```text
agent-bridge/track-b/recovered-s9-decision-reverification/historical-chain/v1
```

It binds S9/S10/S11 contract identities, common scope/provider/operation/trust identity, verified S9 evidence, recomputed authority snapshot, verified S10 recovery identity and revisions, and authenticated S11 L1 request/prepared/sign-job/stable/message identities and revisions.

The following are deliberately excluded:

- raw signature bytes;
- trust permits;
- S11 `synthetic_l2_revision`;
- S11 `synthetic_l2_record_sha256`;
- any currentness, lease, admission, Bridge, or `StateStore` capability.

Changing S11 L2 revision to 99 and recomputing its public checksum leaves the historical chain unchanged. Even corrupt L2 metadata is unread by the S12 L1 path. This demonstrates the limitation; it does not authenticate L2 persistence.

## Fixed vector

The independent KAT uses RFC 8032 vector 1 for the S9 signer and vector 2 for the distinct S11 signer. Core frozen outputs are:

- S9 request: `01d433a73bee905b5d65556b9ba4165716a87cf6142f61ef4147198e390077f1`
- S9 decision: `e35d9917772887d0ffdbd17f8c8781d93e42e79250483139d400ea46392daab1`
- S10 result: `1d2e649278fa6000a2a3a743721b1991c68e6c33eafbe17ff8da7580d96252cd`
- authority snapshot: `f45f52e439dc247132c26cba67980a938cdcd7684026581177acd03a5ffff557`
- S11 L1 message: `330dded03657288687a5c0538a52d5bd2ed1ddee4cc560d70c3b103f8f3d917f`
- historical chain: `afb8aa4945f0e491937f75233c621d52f1bcc1307e6d497352fd9d0fc79b7204`

The Rust suite contains 32 non-ignored S12 tests covering the KAT, canonical byte and typed-label allocation boundaries, every major binding family, independent permits, non-`ACTIVE` states, monotonic and revocation constraints, deterministic repetition, later-revocation limitation, and L2 malleability evidence.

## Remaining blockers

The predecessor production blockers remain. In particular:

- no production external authority or key custodian;
- no owner-pinned production permit or owner approval receipt;
- no runtime carrier or durable source for the complete S9 envelope;
- no runtime delivery path for the private S10 verified projection;
- no external recovery/operation database durability, linearizability, rollback, or split-brain evidence;
- no database/KMS atomicity, exactly-once signing/action, signer non-equivocation, or old-key destruction proof;
- no atomic currentness-at-use plus replay consumption/downstream action;
- no Bridge, `StateStore`, BioCortex opaque-handle transport, or production admission.

Accordingly, `RECOVERY_OBSERVATION_TO_S9_REVERIFICATION_UNIMPLEMENTED` is closed only for this private synthetic executable chain. It is replaced by explicit carrier, byte-availability, external-durability, runtime-projection-delivery, and historical-not-current-at-use gaps.
