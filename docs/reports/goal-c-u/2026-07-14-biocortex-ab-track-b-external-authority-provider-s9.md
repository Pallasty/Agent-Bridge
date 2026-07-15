# BioCortex / Agent-Bridge Track B External Authority Provider S9

Date: 2026-07-14

Baseline: `ad3500c831228b1f0e7e1ff2330c515aa997fa7b`

Decision: `BLOCKED_FAIL_CLOSED`

Status: `PROVIDER_NEUTRAL_ED25519_CURRENTNESS_AND_CUSTODY_CONTRACT_PREREGISTERED_NO_PROVIDER_NO_OWNER_TRUST_ANCHOR_NOT_AUTHORIZED_NOT_TRANSPORT`

## Result

S9 converts the external-dependency requirements left by S8 into a private,
default-off, executable contract. It separates an external currentness
provider from an external key custodian, verifies currentness decisions with
an exactly pinned Ed25519 public key, and represents the three data-key roles
only as provider-scoped immutable opaque identities.

The result is a provider-neutral admission boundary, not a deployment. The
repository contains no selected currentness service, KMS/HSM adapter, network
client, owner trust pin, production constructor, Bridge feature forwarding,
`StateStore` caller, S8 verifier integration, or runtime side effect. Only a
deterministic `cfg(test)` provider and test trust pin exist.

## Why the boundary remains closed

Ed25519 proves that the holder of one private key signed exact bytes. It does
not prove that the signer is outside the rollback domain, that its facts are
true, that its state is linearizable, or that its data keys are held by a
KMS/HSM. Repository-owner permission to conduct this research is likewise not
an owner-issued provider trust anchor or custody receipt.

S9 therefore retains `AUTHORITY_POLICY_CUSTODY_UNRESOLVED` and the other four
original blockers. It adds explicit gaps for the unselected provider and
custodian, durable challenge uniqueness, linearizability, split-brain fencing,
provider rollback, signer rotation/revocation, clock/freshness behavior, and
ambiguous external results.

## Contract shape

Every currentness request binds:

- provider profile, authority namespace, tenant, and audience;
- one operation ID and one nonzero challenge;
- expected epoch and exact S8 epoch-record digest;
- exact S7 registry generation;
- receiver, build, allowlist, keyset, and trust-policy commitments; and
- the fixed algorithm and lease profile.

Every signed decision additionally binds the provider cluster and
incarnation, leader term, committed revision, authority sequence, exact ACTIVE
identity, revocation checkpoint, revoked-through epoch, custody and old-key
use-denied claim commitments, decision ID, and immutable signer ID/version. Any
field substitution, signature change, trust-key change, non-ACTIVE state, or
provider failure returns no token.

The key-custody interface accepts only immutable references containing provider
profile/namespace/cluster/incarnation, key ID/version, role, and algorithm. Its
identity digest is not `sha256(raw_key)`. The interface does not accept or
return secret key bytes. The current S9 custody code freezes this interface
and opaque identity only; it has no custodian trust permit or signature
verifier and does not verify a real KMS receipt. The two custody hashes signed
by the currentness provider are explicitly untrusted claims, not independent
custodian evidence and not a precondition that closes custody.

## Freshness and failure semantics

S9 freezes `ONE_ATTEMPT_NO_CACHE_NO_WALL_CLOCK`. One attempt makes one online
provider call. The response cannot be reused as a lease, and timeout,
unavailability, authentication failure, authorization failure, stale state,
revocation, conflict, rate limiting, malformed data, or an indeterminate
result has no local fallback.

This profile avoids inventing an unmeasured TTL and avoids relying on a local
wall clock, but it is not proof of freshness. Durable uniqueness must be
implemented by the selected external provider. The synthetic provider keeps
operation IDs and challenges only in memory.

## Deliberate negative evidence

Two passing tests preserve the most important limits:

1. reconstructing the synthetic provider loses its in-memory challenge burn
   history, so the same request can again receive a valid signed ACTIVE
   decision; and
2. after an ACTIVE decision returns a token, a later correctly signed REVOKED
   decision rejects new requests but cannot recall the already returned token.

Consequently S9 does not claim instant revocation, exactly-once admission,
same-epoch rollback detection, joint provider/database rollback detection, or
atomic external-currentness/local-consume semantics. Signed term and revision
fields also do not prove single-leader consensus or monotonic recovery.

## Deterministic evidence

The known-answer vector uses the RFC 8032 test-vector-1 seed solely in tests.
The independent checker reconstructs the exact request/keyset and decision
framing, implements the RFC 8032 Ed25519 calculation using Python standard
library primitives, and verifies:

```text
ed25519_public_key       d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a
request_sha256           01d433a73bee905b5d65556b9ba4165716a87cf6142f61ef4147198e390077f1
decision_message_sha256  e35d9917772887d0ffdbd17f8c8781d93e42e79250483139d400ea46392daab1
ed25519_signature        0f530350eb467fd7d10f3a6df04cbb988397d323633244e139f09ec5d33e79a62fb667a312fb495bc76f23a068a779c78aca8ae9ce88b8a3e77bbcd42496600f
```

The 14 Rust tests cover deterministic framing/signing, complete request and
decision-field tampering, exact private-token success, wrong trust roots and
signer versions, duplicate challenge/request rejection within one provider
instance, provider reconstruction, all non-ACTIVE states, all modeled provider
failures, sequence/revision overflow and floors, opaque key role/version/scope,
malformed inputs, post-snapshot token non-recall, and zero reusable lease
behavior. The stronger currentness-to-S7-consume race remains historical S8
negative evidence rather than a newly claimed S9 experiment.

## Verification

Low-memory targeted verification completed with `CARGO_BUILD_JOBS=1`,
`CARGO_INCREMENTAL=0`, `RUSTFLAGS=-C debuginfo=0`, one Cargo job, locked
offline dependencies, disabled default ONNX features, and one test thread.

- S9: 14 passed, 0 failed;
- S8: 14 passed, 0 failed;
- S7: 13 passed, 0 failed, with 3 helper tests ignored;
- S6, S5, and S4: 7 passed each, 0 failed;
- S2: 14 passed, 0 failed;
- S9 feature Store check: passed;
- default-off Store check: passed;
- Bridge S5 feature and default-off checks: passed;
- historical S8 and S7 receipts: byte-identical;
- Track B context-sampling receipt: byte-identical; and
- focused Rust formatting and `git diff --check`: passed.

The committed gate repeats the S9 tests and historical S8, S7, S6, S5, S4,
and S2 Rust regressions, historical S8/S7/S6/context checkers, and Store/Bridge
feature/default-off checks under the same low-memory profile. It additionally
requires a single-parent feature commit, the frozen baseline, a closed path
allowlist, regular-file modes, a symlink-free archive, deterministic receipts,
artifact digest bindings, a clean unchanged HEAD, and no replacement/graft or
shallow history.

## Independent review

Read-only infrastructure and threat reviews found no reusable production KMS,
HSM, keyring, or external currentness dependency. They also rejected existing
bearer-token clients, plain-HTTP peer transport, local JSON grants, and
automatic remote-embedding fallback as authority mechanisms. Those components
cannot satisfy S9's signed challenge, opaque immutable key identity, or
fail-closed rules.

The code/security review initially found two P1 evidence-boundary issues: a
dummy custody signature was stronger than the implemented custody boundary,
and the first revocation test overclaimed an S7 consume race. Both were closed
by making custody explicitly unauthenticated/interface-only, renaming its
currentness fields to provider claims, and replacing the revocation assertion
with a signed ACTIVE-then-REVOKED token-recall sequence. Final review also
moved signature verification before state interpretation, made key-state
requests hold a validated opaque reference, and aligned provider-claim wording.
The final result is P0/P1/P2 zero.

## Admission status

The successor remains `NOT_ADMITTED`; every external admission receipt remains
null and no side effect is unlocked. The original five gaps remain:

```text
AUTHORITY_POLICY_CUSTODY_UNRESOLVED
CAPTURE_PROVENANCE_UNATTESTED
CROSS_BIOCORTEX_OPAQUE_HANDLE_TRANSPORT_UNIMPLEMENTED
PHYSICAL_PRIVACY_DELETION_UNRESOLVED
PRODUCTION_PRODUCER_PROFILE_UNADMITTED
```

The S8 and S9 operational gaps are frozen in both JSON fixtures. No one may
infer production authority, legal/institutional approval, KMS custody, or
transport authorization from this test-only contract.

## Artifact manifest

- `crates/store/Cargo.toml`: `59fe3281dca881c8a9e2dd49b3cbd9131b99b565983d2a936b63020b9c4b7f4f`
- `crates/store/src/temporal_replay_transport.rs`: `66a1a3079831ca65724f309d7031811290b3a06da2d53aec18fc6d765248858e`
- `crates/store/src/temporal_replay_transport/external_restore_authority.rs`: `dd92c2b064c1a4c1e5a4119777f1b5bf21a46d0fc9cb77656845f05e48655d9b`
- `docs/design/MEMORY_TEMPORAL_EXTERNAL_AUTHORITY_PROVIDER_S9_2026_07_14.md`: `66b87609045ab1782c2904756ea178e40104b4275a0f10b5290baaff2c77b750`
- `docs/design/fixtures/biocortex-ab-track-b-external-authority-provider-s9-v0.json`: `d537b80ce0d2bbb3c4d01a988a9685432672078eae07d0b976b1268a27526fc4`
- `docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s9-v0.json`: `2181254b1e66444445734edb2f7dab70a85c0be5316d449f7152559d7e6428e5`
- `scripts/check-memory-temporal-external-authority-provider-s9.sh`: `093c7cd468c023927eafa0bd4a075762bf31ec9de194004bf0be8bf5b0f996ec`
- `scripts/eval/check_memory_temporal_external_authority_provider_s9.py`: `ad7e373f539b780dd71af7f226464412442e3274ce98b0246329c0401a42995f`
- `scripts/eval/fixtures/memory_temporal_external_authority_provider_s9.expected.v0.tsv`: `c4d495cac22b09ef44bf656efb7e5c77f035c13a0c54404cfee044e1e369c375`

## Next admissible step

Do not connect S9 to Bridge. A later tranche may implement an adapter only
after the owner selects the currentness provider and key custodian, supplies a
trust pin independently of the signed response, and provides evidence for
durable one-time challenges, linearizable/fenced state, rollback-safe recovery,
signer rotation and revocation, immutable key versions, and authoritative old
key use denial. Physical destruction remains a separate claim.
