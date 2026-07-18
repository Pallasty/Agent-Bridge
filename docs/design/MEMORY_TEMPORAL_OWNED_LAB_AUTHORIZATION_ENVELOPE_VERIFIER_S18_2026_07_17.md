# S18: authenticated owned-lab authorization envelope and offline verifier

Date: 2026-07-17

Status: positive schema and offline verification kernel only; no real owner trust anchor, no signed owner decision, no CAS claim, no runner, and no experiment.

## Outcome

S18 closes the ambiguity left deliberately open by S17. It defines how an owner may authorize the exact OL00/OL04/OL05, 60-attempt L1 canary without turning a JSON document into a reusable execution token.

The owner decision state is:

`AUTHORIZED_UNCLAIMED_OWNED_LAB_L1_OL00_OL04_OL05_CANARY`

This state means the owner has signed an exact subject and scope. It does **not** mean a run may start. The envelope forces all of the following:

- `owned_lab_execution_authorized=false`;
- `single_use_execution_capability_issued=false`;
- `execution_start_permitted=false`;
- CAS receipt, claimed run, and execution capability are `null`;
- post-run cleanup and custody receipts are `null`;
- `side_effects_unlocked=NONE`.

No real envelope or trust anchor is committed in this stage.

## Trust model

The authorization envelope cannot authenticate its own key. Verification requires a second, independently installed trust-anchor document whose exact canonical-document SHA-256 is pinned by the caller. The anchor binds:

- owner identity and role;
- key ID and exact key version;
- raw 32-byte Ed25519 public key;
- trust-policy digest and minimum revocation epoch;
- the owned-lab-only audience, claim level, and family namespace;
- out-of-band installation and identity-verification receipt digests.

The repository contains no production private key, seed, credential, or real anchor. RFC 8032 material is test-only and is never treated as owner authority.

## Canonical signed payload

Both the anchor and envelope use the deliberately narrower profile:

`AB_RESTRICTED_CANONICAL_JSON_S18_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT`

The parser rejects documents above 65,536 bytes, nesting above 16 levels, duplicate or unknown keys, missing keys, floats, non-finite numbers, non-ASCII keys or strings, and any byte sequence that is not the exact compact sorted-key serialization.

The owner signs the raw 32-byte SHA-256 of the canonical `payload` object. The signed message is:

```text
U32BE(len(domain)) || domain || U64BE(32) || raw_payload_sha256
```

where the domain is:

```text
agent-bridge/biocortex/owned-lab/owner-authorization/s18/v1
```

The verifier recomputes canonical payload bytes, payload SHA-256, message bytes, authorization ID, detached-signature SHA-256, and the Ed25519 signature. The authorization ID uses domain `agent-bridge/biocortex/owned-lab/owner-authorization-id/s18/v1` and:

```text
SHA256(U32BE(len(id_domain)) || id_domain || U64BE(32) ||
       SHA256(canonical payload without authorization_id_sha256))
```

Independent fixed known-answer vectors cover the message framing, authorization-ID derivation, RFC 8032 signature, and use of the independently pinned anchor public key. A receipt field such as `signature_valid=true` is neither present nor trusted.

## Signed subject and scope

The payload binds the final S17 source and integration commits, S16 integration, S17 plan and schemas, schedule and assignment-set digests, the final S19 integration commit, a closed S19 subject-manifest schema/document pair, and the runner source commit/source/binary/toolchain. Owner-authorization verification and live-observation verification have separate source/binary/toolchain/ruleset bindings. It also binds the positive schema, observation/control/SQLite/classifier/oracle artifacts, exact family counts, and the 60/59/59/113 canary accounting.

Resource and safety commitments are represented by exact digests for the resource scope, preflight policy, STOP policy, retention policy, cleanup policy, review policy, CAS namespace/key, and capability nonce. The future source-bound runner must expand those digests into the exact F2FS root, mount/device/kernel identity, SQLite profile, resource ceilings, deadlines, and allowed/forbidden operation sets frozen by S17.

All provider, production, network, credential, paid-resource, privilege, mount, reboot, power-fault, block-device-write, and Agent-Bridge application effects remain forbidden.

## Time and revocation

Issued and expiry timestamps are syntactically validated, ordered signed audit metadata. No trusted-time receipt exists, so wall-clock timestamps cannot provide freshness, currentness, or execution permission. The signed STOP value is likewise only `stop_state_at_signing_audit_only=false`; it is not use-time proof. Validity is instead controlled by:

- an independently pinned minimum revocation epoch;
- an exact envelope revocation epoch;
- a future single-use CAS claim;
- a fresh read from an external absorbing STOP ledger and the current external revocation state.

## Lifecycle separation

The immutable owner envelope, future preflight, future CAS claim, and post-run evidence are distinct objects:

1. S18 verifies `AUTHORIZED_UNCLAIMED`; no action is enabled.
2. S19 will freeze the exact runner and implement fresh preflight plus the claim ledger, still without a live run.
3. A later owner-controlled step may install a real anchor and sign the exact frozen S19 subject.
4. A future use-time CAS may perform the single transition `UNCLAIMED_TO_CONSUMED_FOR_EXACT_RUN` once.
5. A failed CAS grants nothing, leaves `UNCLAIMED` unchanged, and creates no automatic retry. After a successful claim, a crash leaves the authorization consumed and also creates no retry.
6. Retention, semantic-validation, batch-result, STOP-if-triggered, cleanup, and custody receipts are produced only after execution and only affect evidence validity.

There is no serializable intermediate bearer capability.

## Verification boundary

The S18 Rust component is default-off, private to the S16 model subtree, and has no public re-export or runtime caller. It performs restricted-canonical parsing, cross-field binding, authorization-ID recomputation, trust-anchor matching, revocation checks, and active Ed25519 verification. Its verified output is a private `#[must_use]` observation of an unclaimed owner decision, not an execution capability.

The S18 release gate also replays the complete S17 gate, preserving the 5,639-row catalog uniqueness, 113/113 target mapping, ACK/projection binding, and phase-digest KATs. S18 does not yet implement the live observation parser or runner integration.

## Current accounting and nonclaims

- real trust anchors: 0;
- real owner decisions and signatures: 0;
- CAS claims and capabilities: 0;
- roots, runners, attempts, SIGKILLs, fresh restarts, and observations: 0;
- global prerequisites satisfied: 0/16;
- provider or production evidence: 0;
- `side_effects_unlocked=NONE`.

Schema conformance, an RFC test vector, a valid synthetic signature, or a verified unclaimed envelope is not execution authority, institutional approval, currentness, an output permit, or scientific evidence.

## Direct successor

S19 is the source-bound runner and single-use claim implementation. It must freeze the exact runner, both validator builds, independent expected-binding builder, schedule, assignment set, F2FS/SQLite environment, fresh preflight, CAS ledger, external absorbing STOP ledger, and post-run receipt schemas in a closed typed subject manifest. The expected binding must be built from that manifest and never copied from the candidate envelope. S19 remains non-live.

S20 is the first possible real-authority/live stage: an owner-controlled out-of-band anchor, a signature over the exact final S19 manifest, fresh preflight, one successful CAS, and only then the exact 60-attempt canary.
